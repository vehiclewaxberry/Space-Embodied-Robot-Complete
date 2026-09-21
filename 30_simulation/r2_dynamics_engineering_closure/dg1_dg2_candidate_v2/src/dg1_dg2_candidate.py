"""Bounded DG1/DG2 candidate diagnostics for the hash-fixed Unified R2 model.

DG1 declares an explicit dimensionless reference coordinate and tests energy,
virtual-power, equation, and physical-acceleration invariance.  DG2 propagates
the full base pose for prescribed 8-DOF joint motion at nonzero inertial
momentum, then recomputes momentum by summing every physical body.  Nothing in
this module is a torque-driven, contact, actuator, hardware, or release model.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence
import xml.etree.ElementTree as ET

for _name in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "BLIS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_name, "1")

import numpy as np
from scipy.integrate import solve_ivp


PACKAGE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_DIR.parents[2]
CONTRACT_PATH = PACKAGE_DIR / "contracts" / "DG1_DG2_CANDIDATE_CONTRACT_V2.json"
PARENT_SRC = PACKAGE_DIR.parent / "src"
if str(PARENT_SRC) not in sys.path:
    sys.path.insert(0, str(PARENT_SRC))

from r2_dynamics import ReducedR2Model, load_backend  # noqa: E402


class CandidateContractError(RuntimeError):
    """Raised when a candidate input or hash-bound source is invalid."""


def _reject_duplicate_key(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CandidateContractError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def load_json_strict(path: Path) -> dict[str, Any]:
    return json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_key
    )


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            jsonable(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest().upper()


def jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _vector(values: Sequence[float], size: int, field: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise CandidateContractError(f"{field}_MUST_HAVE_{size}_FINITE_VALUES")
    return result


def _relative_error(left: float, right: float, floor: float = 1.0e-30) -> float:
    return abs(left - right) / max(abs(left), abs(right), floor)


def load_contract() -> dict[str, Any]:
    contract = load_json_strict(CONTRACT_PATH)
    if contract.get("schema") != "DG1_DG2_CANDIDATE_CONTRACT_V2":
        raise CandidateContractError("CONTRACT_SCHEMA_MISMATCH")
    return contract


def validate_source_pins(contract: Mapping[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for pin_id, pin in contract["source_pins"].items():
        path = PROJECT_ROOT / pin["path"]
        exists = path.is_file()
        actual_bytes = path.stat().st_size if exists else None
        actual_sha = file_sha256(path) if exists else None
        match = bool(
            exists
            and actual_bytes == int(pin["bytes"])
            and actual_sha == str(pin["sha256"]).upper()
        )
        rows.append(
            {
                "id": pin_id,
                "path": pin["path"],
                "expected_bytes": int(pin["bytes"]),
                "actual_bytes": actual_bytes,
                "expected_sha256": str(pin["sha256"]).upper(),
                "actual_sha256": actual_sha,
                "match": match,
            }
        )
    return {
        "schema": "DG1_DG2_SOURCE_BINDING_V2",
        "pins": rows,
        "summary": {
            "matched": sum(bool(row["match"]) for row in rows),
            "total": len(rows),
        },
        "all_match": all(bool(row["match"]) for row in rows),
    }


def _urdf_joint_limits(contract: Mapping[str, Any]) -> dict[str, Any]:
    pin = contract["source_pins"]["unified_r2_urdf"]
    root = ET.parse(PROJECT_ROOT / pin["path"]).getroot()
    parsed: dict[str, dict[str, Any]] = {}
    for joint in root.findall("joint"):
        joint_type = joint.attrib.get("type")
        if joint_type not in {"revolute", "prismatic"}:
            continue
        limit = joint.find("limit")
        if limit is None or "lower" not in limit.attrib or "upper" not in limit.attrib:
            raise CandidateContractError(f"FINITE_LIMIT_MISSING:{joint.attrib.get('name')}")
        parsed[joint.attrib["name"]] = {
            "type": joint_type,
            "lower": float(limit.attrib["lower"]),
            "upper": float(limit.attrib["upper"]),
        }
    order = list(contract["coordinate_contract"]["joint_order"])
    if set(parsed) != set(order):
        raise CandidateContractError("MOVABLE_JOINT_SET_MISMATCH")
    ordered = [parsed[name] for name in order]
    types = [row["type"] for row in ordered]
    if types != list(contract["coordinate_contract"]["joint_types"]):
        raise CandidateContractError("MOVABLE_JOINT_TYPE_MISMATCH")
    limits = np.asarray([[row["lower"], row["upper"]] for row in ordered])
    spans = limits[:, 1] - limits[:, 0]
    if np.any(~np.isfinite(limits)) or np.any(spans <= 0.0):
        raise CandidateContractError("JOINT_LIMIT_SPAN_INVALID")
    return {"limits": limits, "spans": spans, "types": types, "order": order}


def evaluate_dg1(contract: Mapping[str, Any], backend: Any) -> dict[str, Any]:
    case = contract["dg1_case"]
    threshold = contract["thresholds"]
    q = _vector(case["q_mixed_rad_m"], 8, "DG1_Q")
    qdot = _vector(case["qdot_mixed_rad_s_m_s"], 8, "DG1_QDOT")
    tau = _vector(case["tau_mixed_Nm_N"], 8, "DG1_TAU")
    limits = _urdf_joint_limits(contract)
    reference = _vector(
        contract["coordinate_contract"]["reference_scales_mixed_rad_m"],
        8,
        "REFERENCE_SCALE",
    )
    scale_span_error = float(np.max(np.abs(reference - limits["spans"])))
    scale = np.diag(reference)
    inverse_scale = np.diag(1.0 / reference)
    alternate_factor = _vector(
        contract["coordinate_contract"]["alternate_scale_factors_dimensionless"],
        8,
        "ALTERNATE_SCALE_FACTOR",
    )
    alternate_reference = reference * alternate_factor
    alternate_scale = np.diag(alternate_reference)
    alternate_inverse = np.diag(1.0 / alternate_reference)

    model = ReducedR2Model(backend, q[6:])
    mass = np.asarray(backend.reduced_mass_matrix(q), dtype=float)
    bias = np.asarray(model.bias(q, qdot), dtype=float)
    raw_acceleration = np.linalg.solve(mass, tau - bias)

    xdot = inverse_scale @ qdot
    mass_reference = scale.T @ mass @ scale
    bias_reference = scale.T @ bias
    effort_reference = scale.T @ tau
    xddot = np.linalg.solve(mass_reference, effort_reference - bias_reference)
    physical_acceleration_reference = scale @ xddot

    xdot_alternate = alternate_inverse @ qdot
    mass_alternate = alternate_scale.T @ mass @ alternate_scale
    bias_alternate = alternate_scale.T @ bias
    effort_alternate = alternate_scale.T @ tau
    xddot_alternate = np.linalg.solve(
        mass_alternate, effort_alternate - bias_alternate
    )
    physical_acceleration_alternate = alternate_scale @ xddot_alternate

    raw_energy = float(0.5 * qdot @ mass @ qdot)
    reference_energy = float(0.5 * xdot @ mass_reference @ xdot)
    alternate_energy = float(
        0.5 * xdot_alternate @ mass_alternate @ xdot_alternate
    )
    raw_power = float(tau @ qdot)
    reference_power = float(effort_reference @ xdot)
    alternate_power = float(effort_alternate @ xdot_alternate)
    reference_equation_residual = (
        mass_reference @ xddot + bias_reference - effort_reference
    )
    alternate_equation_residual = (
        mass_alternate @ xddot_alternate + bias_alternate - effort_alternate
    )

    reference_cross = physical_acceleration_reference - raw_acceleration
    alternate_cross = physical_acceleration_alternate - raw_acceleration
    metrics = {
        "urdf_joint_limits_mixed_rad_m": limits["limits"],
        "urdf_joint_spans_mixed_rad_m": limits["spans"],
        "declared_reference_scales_mixed_rad_m": reference,
        "scale_span_max_abs_mixed_rad_m": scale_span_error,
        "raw_unscaled_condition_number_no_credit": float(np.linalg.cond(mass)),
        "declared_reference_metric_condition_number": float(
            np.linalg.cond(mass_reference)
        ),
        "alternate_metric_condition_number_no_credit": float(
            np.linalg.cond(mass_alternate)
        ),
        "raw_kinetic_energy_J": raw_energy,
        "reference_metric_kinetic_energy_J": reference_energy,
        "alternate_metric_kinetic_energy_J": alternate_energy,
        "reference_energy_relative_error": _relative_error(
            raw_energy, reference_energy
        ),
        "alternate_energy_relative_error": _relative_error(
            raw_energy, alternate_energy
        ),
        "raw_virtual_power_W": raw_power,
        "reference_metric_virtual_power_W": reference_power,
        "alternate_metric_virtual_power_W": alternate_power,
        "reference_virtual_power_relative_error": _relative_error(
            raw_power, reference_power
        ),
        "alternate_virtual_power_relative_error": _relative_error(
            raw_power, alternate_power
        ),
        "reference_equation_residual_max_abs_J": float(
            np.max(np.abs(reference_equation_residual))
        ),
        "alternate_equation_residual_max_abs_J": float(
            np.max(np.abs(alternate_equation_residual))
        ),
        "reference_acceleration_cross_revolute_max_abs_rad_s2": float(
            np.max(np.abs(reference_cross[:6]))
        ),
        "reference_acceleration_cross_prismatic_max_abs_m_s2": float(
            np.max(np.abs(reference_cross[6:]))
        ),
        "alternate_acceleration_cross_revolute_max_abs_rad_s2": float(
            np.max(np.abs(alternate_cross[:6]))
        ),
        "alternate_acceleration_cross_prismatic_max_abs_m_s2": float(
            np.max(np.abs(alternate_cross[6:]))
        ),
        "raw_acceleration_mixed_rad_s2_m_s2": raw_acceleration,
        "reference_recovered_acceleration_mixed_rad_s2_m_s2": physical_acceleration_reference,
        "alternate_recovered_acceleration_mixed_rad_s2_m_s2": physical_acceleration_alternate,
    }
    checks = {
        "reference_scales_equal_finite_URDF_joint_spans": scale_span_error
        <= threshold["scale_span_max_abs_mixed_rad_m"],
        "reference_metric_mass_positive_definite": bool(
            np.min(np.linalg.eigvalsh(mass_reference)) > 0.0
        ),
        "energy_invariant_under_reference_metric": metrics[
            "reference_energy_relative_error"
        ]
        <= threshold["energy_invariance_relative_max"],
        "energy_invariant_under_alternate_metric": metrics[
            "alternate_energy_relative_error"
        ]
        <= threshold["energy_invariance_relative_max"],
        "virtual_power_invariant_under_reference_metric": metrics[
            "reference_virtual_power_relative_error"
        ]
        <= threshold["virtual_power_invariance_relative_max"],
        "virtual_power_invariant_under_alternate_metric": metrics[
            "alternate_virtual_power_relative_error"
        ]
        <= threshold["virtual_power_invariance_relative_max"],
        "reference_equation_residual_bounded": metrics[
            "reference_equation_residual_max_abs_J"
        ]
        <= threshold["equation_residual_normalized_max_abs_J"],
        "alternate_equation_residual_bounded": metrics[
            "alternate_equation_residual_max_abs_J"
        ]
        <= threshold["equation_residual_normalized_max_abs_J"],
        "reference_revolute_acceleration_invariant": metrics[
            "reference_acceleration_cross_revolute_max_abs_rad_s2"
        ]
        <= threshold["acceleration_invariance_revolute_max_abs_rad_s2"],
        "reference_prismatic_acceleration_invariant": metrics[
            "reference_acceleration_cross_prismatic_max_abs_m_s2"
        ]
        <= threshold["acceleration_invariance_prismatic_max_abs_m_s2"],
        "alternate_revolute_acceleration_invariant": metrics[
            "alternate_acceleration_cross_revolute_max_abs_rad_s2"
        ]
        <= threshold["acceleration_invariance_revolute_max_abs_rad_s2"],
        "alternate_prismatic_acceleration_invariant": metrics[
            "alternate_acceleration_cross_prismatic_max_abs_m_s2"
        ]
        <= threshold["acceleration_invariance_prismatic_max_abs_m_s2"],
    }
    return {
        "schema": "DG1_REFERENCE_METRIC_DIAGNOSTIC_V2",
        "scope": "CURRENT_R2_8DOF_6R2P_DIMENSIONLESS_REFERENCE_COORDINATE",
        "reference_scale_authority": contract["coordinate_contract"][
            "reference_scale_definition"
        ],
        "condition_number_scope": contract["coordinate_contract"][
            "metric_credit_boundary"
        ],
        "metrics": metrics,
        "checks": checks,
        "candidate_pass": all(checks.values()),
        "hardware_valid": False,
        "release_credit": False,
    }


def quaternion_product(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return np.array(
        (
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        )
    )


def normalized_quaternion(value: Sequence[float]) -> np.ndarray:
    quaternion = _vector(value, 4, "QUATERNION")
    norm = float(np.linalg.norm(quaternion))
    if norm <= 0.0:
        raise CandidateContractError("QUATERNION_NORM_NONPOSITIVE")
    return quaternion / norm


def quaternion_rotation_body_to_inertial(value: Sequence[float]) -> np.ndarray:
    w, x, y, z = normalized_quaternion(value)
    return np.array(
        (
            (1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)),
            (2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)),
            (2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)),
        )
    )


def _orientation_distance_rad(left: Sequence[float], right: Sequence[float]) -> float:
    q_left = normalized_quaternion(left)
    q_right = normalized_quaternion(right)
    alignment = min(1.0, max(0.0, abs(float(q_left @ q_right))))
    return 2.0 * math.acos(alignment)


def _solve_base_twist(
    tree: Any,
    q: np.ndarray,
    qdot: np.ndarray,
    position_inertial: np.ndarray,
    quaternion_body_to_inertial: np.ndarray,
    linear_momentum_inertial: np.ndarray,
    angular_momentum_origin_inertial: np.ndarray,
) -> np.ndarray:
    rotation = quaternion_rotation_body_to_inertial(quaternion_body_to_inertial)
    desired_linear_root = rotation.T @ linear_momentum_inertial
    desired_angular_root = rotation.T @ (
        angular_momentum_origin_inertial
        - np.cross(position_inertial, linear_momentum_inertial)
    )
    desired_root = np.concatenate((desired_linear_root, desired_angular_root))
    blocks = tree.mass_matrix_blocks(q)
    return np.linalg.solve(blocks.Hbb, desired_root - blocks.Hbm @ qdot)


def _pose_joint_rhs(
    tree: Any,
    qdot: np.ndarray,
    linear_momentum_inertial: np.ndarray,
    angular_momentum_origin_inertial: np.ndarray,
):
    def rhs(_time_s: float, state: np.ndarray) -> np.ndarray:
        position = state[:3]
        quaternion = normalized_quaternion(state[3:7])
        q = state[7:]
        base_twist = _solve_base_twist(
            tree,
            q,
            qdot,
            position,
            quaternion,
            linear_momentum_inertial,
            angular_momentum_origin_inertial,
        )
        rotation = quaternion_rotation_body_to_inertial(quaternion)
        quaternion_rate = 0.5 * quaternion_product(
            quaternion, np.array((0.0, *base_twist[3:]))
        )
        return np.concatenate((rotation @ base_twist[:3], quaternion_rate, qdot))

    return rhs


def _rk4_history(
    rhs: Any, initial: np.ndarray, step_s: float, steps: int
) -> tuple[np.ndarray, np.ndarray]:
    state = np.asarray(initial, dtype=float).copy()
    history = [state.copy()]
    times = [0.0]
    for index in range(steps):
        time_s = index * step_s
        k1 = rhs(time_s, state)
        k2 = rhs(time_s + 0.5 * step_s, state + 0.5 * step_s * k1)
        k3 = rhs(time_s + 0.5 * step_s, state + 0.5 * step_s * k2)
        k4 = rhs(time_s + step_s, state + step_s * k3)
        state = state + (step_s / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
        state[3:7] = normalized_quaternion(state[3:7])
        history.append(state.copy())
        times.append((index + 1) * step_s)
    return np.asarray(times), np.asarray(history)


def _momentum_audit_at_state(
    tree: Any,
    state: np.ndarray,
    qdot: np.ndarray,
    linear_target: np.ndarray,
    angular_target: np.ndarray,
) -> dict[str, Any]:
    position = state[:3]
    quaternion = normalized_quaternion(state[3:7])
    q = state[7:]
    rotation = quaternion_rotation_body_to_inertial(quaternion)
    base_twist = _solve_base_twist(
        tree, q, qdot, position, quaternion, linear_target, angular_target
    )
    matrix_state = tree.momentum(q, base_twist, qdot)
    matrix_linear_root = np.asarray(matrix_state.linear_root_kg_m_s)
    matrix_angular_root = np.asarray(matrix_state.angular_about_root_kg_m2_s)

    generalized_velocity = np.concatenate((base_twist, qdot))
    body_linear_root = np.zeros(3)
    body_angular_root = np.zeros(3)
    for body in tree.body_kinematics(q):
        linear_velocity = body.linear_jacobian @ generalized_velocity
        angular_velocity = body.angular_jacobian @ generalized_velocity
        body_linear = body.mass_kg * linear_velocity
        body_linear_root += body_linear
        body_angular_root += (
            body.inertia_root_kg_m2 @ angular_velocity
            + np.cross(body.com_root_m, body_linear)
        )

    body_linear_inertial = rotation @ body_linear_root
    body_angular_origin_inertial = (
        rotation @ body_angular_root
        + np.cross(position, body_linear_inertial)
    )
    matrix_linear_inertial = rotation @ matrix_linear_root
    matrix_angular_origin_inertial = (
        rotation @ matrix_angular_root
        + np.cross(position, matrix_linear_inertial)
    )
    return {
        "base_twist_body_mixed_m_s_rad_s": base_twist,
        "body_linear_inertial_kg_m_s": body_linear_inertial,
        "body_angular_origin_inertial_kg_m2_s": body_angular_origin_inertial,
        "matrix_linear_inertial_kg_m_s": matrix_linear_inertial,
        "matrix_angular_origin_inertial_kg_m2_s": matrix_angular_origin_inertial,
        "body_linear_target_residual_norm_kg_m_s": float(
            np.linalg.norm(body_linear_inertial - linear_target)
        ),
        "body_angular_target_residual_norm_kg_m2_s": float(
            np.linalg.norm(body_angular_origin_inertial - angular_target)
        ),
        "matrix_vs_body_linear_norm_kg_m_s": float(
            np.linalg.norm(matrix_linear_inertial - body_linear_inertial)
        ),
        "matrix_vs_body_angular_norm_kg_m2_s": float(
            np.linalg.norm(
                matrix_angular_origin_inertial - body_angular_origin_inertial
            )
        ),
    }


def _history_momentum_metrics(
    tree: Any,
    history: np.ndarray,
    qdot: np.ndarray,
    linear_target: np.ndarray,
    angular_target: np.ndarray,
) -> dict[str, Any]:
    rows = [
        _momentum_audit_at_state(tree, state, qdot, linear_target, angular_target)
        for state in history
    ]
    return {
        "samples": len(rows),
        "linear_target_residual_max_kg_m_s": max(
            row["body_linear_target_residual_norm_kg_m_s"] for row in rows
        ),
        "angular_target_residual_max_kg_m2_s": max(
            row["body_angular_target_residual_norm_kg_m2_s"] for row in rows
        ),
        "matrix_vs_body_linear_max_kg_m_s": max(
            row["matrix_vs_body_linear_norm_kg_m_s"] for row in rows
        ),
        "matrix_vs_body_angular_max_kg_m2_s": max(
            row["matrix_vs_body_angular_norm_kg_m2_s"] for row in rows
        ),
        "initial": rows[0],
        "final": rows[-1],
    }


def evaluate_dg2(contract: Mapping[str, Any], backend: Any) -> dict[str, Any]:
    case = contract["dg2_case"]
    threshold = contract["thresholds"]
    q0 = _vector(case["q0_mixed_rad_m"], 8, "DG2_Q0")
    qdot = _vector(case["prescribed_qdot_mixed_rad_s_m_s"], 8, "DG2_QDOT")
    position0 = _vector(
        case["base_position_inertial_initial_m"], 3, "DG2_POSITION0"
    )
    quaternion0 = normalized_quaternion(
        case["base_quaternion_body_to_inertial_initial_wxyz"]
    )
    linear_target = _vector(
        case["linear_momentum_inertial_target_kg_m_s"], 3, "DG2_LINEAR_TARGET"
    )
    angular_target = _vector(
        case["angular_momentum_about_inertial_origin_target_kg_m2_s"],
        3,
        "DG2_ANGULAR_TARGET",
    )
    duration = float(case["duration_s"])
    step = float(case["fixed_step_s"])
    steps_float = duration / step
    steps = int(round(steps_float))
    if steps < 1 or abs(steps - steps_float) > 1.0e-12:
        raise CandidateContractError("DG2_DURATION_NOT_INTEGER_FIXED_STEPS")
    initial = np.concatenate((position0, quaternion0, q0))
    rhs = _pose_joint_rhs(backend.tree, qdot, linear_target, angular_target)
    times, rk4 = _rk4_history(rhs, initial, step, steps)

    cross = solve_ivp(
        rhs,
        (0.0, duration),
        initial,
        method="DOP853",
        t_eval=times,
        rtol=float(case["cross_rtol"]),
        atol=float(case["cross_atol"]),
        max_step=float(case["cross_max_step_s"]),
    )
    if not cross.success or cross.y.shape != (15, steps + 1):
        raise CandidateContractError("DG2_DOP853_INTEGRATION_FAILED")
    dop853 = cross.y.T.copy()
    for row in dop853:
        row[3:7] = normalized_quaternion(row[3:7])

    limits = _urdf_joint_limits(contract)["limits"]
    all_q = np.vstack((rk4[:, 7:], dop853[:, 7:]))
    lower_margin = all_q - limits[:, 0]
    upper_margin = limits[:, 1] - all_q
    minimum_margin = float(min(np.min(lower_margin), np.min(upper_margin)))
    position_cross = np.linalg.norm(rk4[:, :3] - dop853[:, :3], axis=1)
    orientation_cross = np.asarray(
        [
            _orientation_distance_rad(left, right)
            for left, right in zip(rk4[:, 3:7], dop853[:, 3:7], strict=True)
        ]
    )
    joint_cross = np.abs(rk4[:, 7:] - dop853[:, 7:])
    quaternion_norm_error = max(
        float(np.max(np.abs(np.linalg.norm(rk4[:, 3:7], axis=1) - 1.0))),
        float(np.max(np.abs(np.linalg.norm(dop853[:, 3:7], axis=1) - 1.0))),
    )
    expected_q = q0[None, :] + times[:, None] * qdot[None, :]
    prescribed_cross = max(
        float(np.max(np.abs(rk4[:, 7:] - expected_q))),
        float(np.max(np.abs(dop853[:, 7:] - expected_q))),
    )
    rk4_momentum = _history_momentum_metrics(
        backend.tree, rk4, qdot, linear_target, angular_target
    )
    dop853_momentum = _history_momentum_metrics(
        backend.tree, dop853, qdot, linear_target, angular_target
    )
    metrics = {
        "duration_s": duration,
        "fixed_step_s": step,
        "samples_per_solver": steps + 1,
        "linear_momentum_target_inertial_kg_m_s": linear_target,
        "angular_momentum_target_about_inertial_origin_kg_m2_s": angular_target,
        "RK4": rk4_momentum,
        "DOP853": dop853_momentum,
        "rk4_dop853_position_cross_max_m": float(np.max(position_cross)),
        "rk4_dop853_orientation_cross_max_rad": float(np.max(orientation_cross)),
        "rk4_dop853_joint_cross_revolute_max_rad": float(
            np.max(joint_cross[:, :6])
        ),
        "rk4_dop853_joint_cross_prismatic_max_m": float(
            np.max(joint_cross[:, 6:])
        ),
        "prescribed_joint_trajectory_cross_max_mixed_rad_m": prescribed_cross,
        "quaternion_norm_error_max": quaternion_norm_error,
        "minimum_joint_limit_margin_mixed_rad_m": minimum_margin,
        "final_base_position_inertial_RK4_m": rk4[-1, :3],
        "final_base_quaternion_body_to_inertial_RK4_wxyz": rk4[-1, 3:7],
        "final_q_RK4_mixed_rad_m": rk4[-1, 7:],
    }
    checks = {
        "nonzero_linear_momentum_case": float(np.linalg.norm(linear_target)) > 0.0,
        "nonzero_angular_momentum_case": float(np.linalg.norm(angular_target)) > 0.0,
        "base_position_integrated": float(np.linalg.norm(rk4[-1, :3] - position0))
        > 0.0,
        "base_attitude_integrated": _orientation_distance_rad(
            rk4[-1, 3:7], quaternion0
        )
        > 0.0,
        "RK4_linear_momentum_conserved_by_per_body_sum": rk4_momentum[
            "linear_target_residual_max_kg_m_s"
        ]
        <= threshold["linear_momentum_residual_max_kg_m_s"],
        "RK4_angular_momentum_conserved_by_per_body_sum": rk4_momentum[
            "angular_target_residual_max_kg_m2_s"
        ]
        <= threshold["angular_momentum_residual_max_kg_m2_s"],
        "DOP853_linear_momentum_conserved_by_per_body_sum": dop853_momentum[
            "linear_target_residual_max_kg_m_s"
        ]
        <= threshold["linear_momentum_residual_max_kg_m_s"],
        "DOP853_angular_momentum_conserved_by_per_body_sum": dop853_momentum[
            "angular_target_residual_max_kg_m2_s"
        ]
        <= threshold["angular_momentum_residual_max_kg_m2_s"],
        "matrix_vs_body_linear_cross_bounded": max(
            rk4_momentum["matrix_vs_body_linear_max_kg_m_s"],
            dop853_momentum["matrix_vs_body_linear_max_kg_m_s"],
        )
        <= threshold["matrix_vs_body_linear_max_kg_m_s"],
        "matrix_vs_body_angular_cross_bounded": max(
            rk4_momentum["matrix_vs_body_angular_max_kg_m2_s"],
            dop853_momentum["matrix_vs_body_angular_max_kg_m2_s"],
        )
        <= threshold["matrix_vs_body_angular_max_kg_m2_s"],
        "RK4_DOP853_position_cross_bounded": metrics[
            "rk4_dop853_position_cross_max_m"
        ]
        <= threshold["rk4_dop853_position_cross_max_m"],
        "RK4_DOP853_orientation_cross_bounded": metrics[
            "rk4_dop853_orientation_cross_max_rad"
        ]
        <= threshold["rk4_dop853_orientation_cross_max_rad"],
        "RK4_DOP853_revolute_joint_cross_bounded": metrics[
            "rk4_dop853_joint_cross_revolute_max_rad"
        ]
        <= threshold["rk4_dop853_joint_cross_revolute_max_rad"],
        "RK4_DOP853_prismatic_joint_cross_bounded": metrics[
            "rk4_dop853_joint_cross_prismatic_max_m"
        ]
        <= threshold["rk4_dop853_joint_cross_prismatic_max_m"],
        "quaternion_norm_bounded": quaternion_norm_error
        <= threshold["quaternion_norm_error_max"],
        "joint_limits_respected": minimum_margin
        >= threshold["minimum_joint_limit_margin_mixed_rad_m"],
    }
    return {
        "schema": "DG2_NONZERO_MOMENTUM_FULL_STATE_DIAGNOSTIC_V2",
        "scope": case["model_boundary"],
        "independent_recalculation": "PER_PHYSICAL_BODY_JACOBIAN_SUM__NO_GENERALIZED_MOMENTUM_MATRIX_MULTIPLICATION",
        "metrics": metrics,
        "checks": checks,
        "candidate_pass": all(checks.values()),
        "torque_driven": False,
        "contact_evaluated": False,
        "hardware_valid": False,
        "release_credit": False,
    }


def run_candidate() -> dict[str, Any]:
    contract = load_contract()
    source_binding = validate_source_pins(contract)
    if not source_binding["all_match"]:
        return {
            "schema": "DG1_DG2_CANDIDATE_EVIDENCE_V2",
            "technical_verdict": "SOURCE_HASH_DRIFT__FAIL_CLOSED",
            "source_binding": source_binding,
            "dg1": None,
            "dg2": None,
            "candidate_pass": False,
            "next_stage_authorized": False,
            "release_credit": False,
        }
    backend = load_backend(PROJECT_ROOT)
    dg1 = evaluate_dg1(contract, backend)
    dg2 = evaluate_dg2(contract, backend)
    return {
        "schema": "DG1_DG2_CANDIDATE_EVIDENCE_V2",
        "technical_verdict": (
            "DG1_DG2_BOUNDED_CANDIDATE_PASS__NO_DG3_DG4_DG5_OR_RELEASE_CREDIT"
            if dg1["candidate_pass"] and dg2["candidate_pass"]
            else "DG1_DG2_CANDIDATE_HOLD__SEE_FAILED_CHECKS"
        ),
        "authority_scope": contract["authority_scope"],
        "source_binding": source_binding,
        "dg1": dg1,
        "dg2": dg2,
        "execution_guards": contract["execution_guards"],
        "candidate_pass": bool(dg1["candidate_pass"] and dg2["candidate_pass"]),
        "parent_gate_mutated": False,
        "dynamics_engineering_complete": False,
        "hardware_valid": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
