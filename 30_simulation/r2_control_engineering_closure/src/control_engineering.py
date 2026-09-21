"""Fail-closed R2 control engineering helpers.

This module is intentionally velocity-level and non-contact.  It consumes the
hash-pinned Unified R2 tree for one declared diagnostic configuration, but it
never calls ``advance``, a collision oracle, an edge checker, contact logic, or
an M01 search routine.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence
import xml.etree.ElementTree as ET

import numpy as np


MODULE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO_ROOT = MODULE_ROOT.parents[1]
CONFIG_PATH = MODULE_ROOT / "config" / "CTRL_R2_CONTROL_ENGINEERING_CONFIG_V1.json"
PHASE_CONTRACT_PATH = MODULE_ROOT / "contracts" / "CTRL_R2_PHASE_TASK_CONTRACT_V1.json"
SUPERVISOR_CONTRACT_PATH = MODULE_ROOT / "contracts" / "CTRL_R2_SUPERVISOR_INTERFACE_V1.json"
RESULTS_DIR = MODULE_ROOT / "results"


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def loads_json_strict(text: str) -> dict[str, Any]:
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
    )


def load_json_strict(path: Path) -> dict[str, Any]:
    return loads_json_strict(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def canonical_sha256(value: Any) -> str:
    data = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(data).hexdigest().upper()


def _pin(config: Mapping[str, Any], pin_id: str) -> Mapping[str, Any]:
    matches = [pin for pin in config["source_pins"] if pin["id"] == pin_id]
    if len(matches) != 1:
        raise ValueError(f"SOURCE_PIN_ID_NOT_UNIQUE:{pin_id}")
    return matches[0]


def pinned_path(
    repo_root: Path, config: Mapping[str, Any], pin_id: str
) -> Path:
    return repo_root / str(_pin(config, pin_id)["path"])


def validate_source_pins(
    repo_root: Path, config: Mapping[str, Any]
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    ids: set[str] = set()
    for pin in config["source_pins"]:
        pin_id = str(pin["id"])
        if pin_id in ids:
            raise ValueError(f"DUPLICATE_SOURCE_PIN_ID:{pin_id}")
        ids.add(pin_id)
        path = repo_root / str(pin["path"])
        exists = path.is_file()
        actual_bytes = path.stat().st_size if exists else None
        actual_sha256 = sha256_file(path) if exists else None
        match = (
            exists
            and actual_bytes == int(pin["bytes"])
            and actual_sha256 == str(pin["sha256"]).upper()
        )
        records.append(
            {
                "id": pin_id,
                "path": str(pin["path"]),
                "declared_bytes": int(pin["bytes"]),
                "actual_bytes": actual_bytes,
                "declared_sha256": str(pin["sha256"]).upper(),
                "actual_sha256": actual_sha256,
                "match": match,
            }
        )
    mismatches = [record["id"] for record in records if not record["match"]]
    return {
        "schema": "R2_CONTROL_SOURCE_BINDING_V1",
        "pin_count": len(records),
        "match_count": len(records) - len(mismatches),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "pins": records,
        "pass": not mismatches,
    }


def _install_unified_imports(repo_root: Path) -> None:
    rebind = (
        repo_root
        / "30_simulation"
        / "sim_13_physics_gated_embodied_grasping"
        / "v2_system_rebind"
    )
    paths = (rebind / "runtime_fail_closed_backends_v2", rebind)
    for path in reversed(paths):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)


def _skew(vector: Sequence[float]) -> np.ndarray:
    x, y, z = np.asarray(vector, dtype=float)
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def _parse_urdf_limits(
    path: Path,
    expected_names: Sequence[str],
    expected_types: Sequence[str],
) -> tuple[np.ndarray, list[str]]:
    root = ET.parse(path).getroot()
    movable: dict[str, tuple[str, float, float]] = {}
    for joint in root.findall("joint"):
        joint_type = joint.attrib.get("type")
        if joint_type not in {"revolute", "prismatic", "continuous"}:
            continue
        name = joint.attrib["name"]
        limit = joint.find("limit")
        if limit is None or "lower" not in limit.attrib or "upper" not in limit.attrib:
            raise ValueError(f"FINITE_LIMIT_REQUIRED:{name}")
        movable[name] = (
            str(joint_type),
            float(limit.attrib["lower"]),
            float(limit.attrib["upper"]),
        )
    names = list(expected_names)
    if set(movable) != set(names):
        raise ValueError("UNIFIED_R2_MOVABLE_JOINT_SET_MISMATCH")
    types = [movable[name][0] for name in names]
    if types != list(expected_types):
        raise ValueError("UNIFIED_R2_JOINT_TYPE_ORDER_MISMATCH")
    limits = np.asarray([[movable[name][1], movable[name][2]] for name in names])
    if not np.all(np.isfinite(limits)) or np.any(limits[:, 0] >= limits[:, 1]):
        raise ValueError("UNIFIED_R2_LIMITS_INVALID")
    return limits, types


def validate_joint_state_fail_closed(
    q: Sequence[float], limits: Sequence[Sequence[float]]
) -> tuple[np.ndarray, np.ndarray]:
    state = np.asarray(q, dtype=float)
    bounds = np.asarray(limits, dtype=float)
    if state.ndim != 1 or bounds.shape != (state.size, 2) or state.size == 0:
        raise ValueError("JOINT_STATE_LIMIT_SHAPE_MISMATCH")
    if not np.all(np.isfinite(state)) or not np.all(np.isfinite(bounds)):
        raise ValueError("JOINT_STATE_OR_LIMIT_NONFINITE_FAIL_CLOSED")
    margins = np.column_stack((state - bounds[:, 0], bounds[:, 1] - state))
    if np.any(margins <= 0.0):
        raise ValueError("JOINT_AT_OR_OUTSIDE_LIMIT_FAIL_CLOSED")
    return state, margins


def singularity_guard(
    jacobian: Sequence[Sequence[float]],
    expected_rank: int,
    sigma_min_threshold: float,
    rank_rtol: float,
) -> dict[str, Any]:
    matrix = np.asarray(jacobian, dtype=float)
    if matrix.ndim != 2 or matrix.size == 0 or not np.all(np.isfinite(matrix)):
        return {
            "allow": False,
            "reason": "NONFINITE_OR_MALFORMED_JACOBIAN",
            "rank": None,
            "sigma_min": None,
        }
    singular = np.linalg.svd(matrix, compute_uv=False)
    threshold = float(rank_rtol) * float(singular[0])
    rank = int(np.sum(singular > threshold))
    sigma_min = float(singular[-1])
    reasons: list[str] = []
    if rank != int(expected_rank):
        reasons.append("TASK_RANK_MISMATCH")
    if sigma_min < float(sigma_min_threshold):
        reasons.append("SIGMA_BELOW_AUTHORIZED_THRESHOLD")
    return {
        "allow": not reasons,
        "reason": "ALLOW_LOCAL_DIAGNOSTIC" if not reasons else "__".join(reasons),
        "rank": rank,
        "expected_rank": int(expected_rank),
        "singular_values": singular.tolist(),
        "sigma_min": sigma_min,
        "sigma_min_threshold": float(sigma_min_threshold),
        "rank_rtol": float(rank_rtol),
    }


def euclidean_dls(
    jacobian: np.ndarray, desired: np.ndarray, damping: float
) -> np.ndarray:
    rows = jacobian.shape[0]
    return jacobian.T @ np.linalg.solve(
        jacobian @ jacobian.T + float(damping) ** 2 * np.eye(rows),
        desired,
    )


def mass_weighted_dls(
    jacobian: np.ndarray,
    desired: np.ndarray,
    reduced_mass: np.ndarray,
    damping: float,
) -> np.ndarray:
    mass = np.asarray(reduced_mass, dtype=float)
    if mass.shape != (jacobian.shape[1], jacobian.shape[1]):
        raise ValueError("REDUCED_MASS_SHAPE_MISMATCH")
    if not np.allclose(mass, mass.T, rtol=0.0, atol=1e-12):
        raise ValueError("REDUCED_MASS_NOT_SYMMETRIC")
    if float(np.min(np.linalg.eigvalsh(mass))) <= 0.0:
        raise ValueError("REDUCED_MASS_NOT_POSITIVE_DEFINITE")
    mass_inverse = np.linalg.inv(mass)
    rows = jacobian.shape[0]
    return mass_inverse @ jacobian.T @ np.linalg.solve(
        jacobian @ mass_inverse @ jacobian.T
        + float(damping) ** 2 * np.eye(rows),
        desired,
    )


def _canonical_null_vector(matrix: np.ndarray) -> tuple[np.ndarray, int, float]:
    _, singular, vh = np.linalg.svd(matrix, full_matrices=True)
    rank = int(np.linalg.matrix_rank(matrix, tol=float(singular[0]) * 1e-9))
    nullity = int(matrix.shape[1] - rank)
    if nullity != 1:
        raise ValueError("EXACT_ONE_DIMENSIONAL_NULLSPACE_REQUIRED")
    vector = vh[-1].copy()
    pivot = int(np.argmax(np.abs(vector)))
    if vector[pivot] < 0.0:
        vector *= -1.0
    vector /= np.linalg.norm(vector)
    return vector, nullity, float(np.linalg.norm(matrix @ vector))


def _approach_plane_basis(axis: np.ndarray) -> np.ndarray:
    unit = np.asarray(axis, dtype=float)
    unit /= np.linalg.norm(unit)
    seeds = np.eye(3)
    seed = seeds[int(np.argmin(np.abs(seeds @ unit)))]
    first = np.cross(unit, seed)
    first /= np.linalg.norm(first)
    second = np.cross(unit, first)
    return np.vstack((first, second))


def _tool_jacobians(
    backend: Any, q8: np.ndarray, tool_link: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    transforms, joint_states = backend.tree.forward_kinematics(q8)
    if tool_link not in transforms:
        raise ValueError(f"TOOL_LINK_ABSENT:{tool_link}")
    transform = np.asarray(transforms[tool_link], dtype=float)
    point = transform[:3, 3]
    base_jacobian = np.block(
        [
            [np.eye(3), -_skew(point)],
            [np.zeros((3, 3)), np.eye(3)],
        ]
    )
    joint_jacobian = np.zeros((6, backend.tree.movable_dof))
    for joint in backend.tree._ancestor_joints(tool_link):
        if joint.joint_type == "fixed":
            continue
        index = backend.tree._movable_index[joint.name]
        state = joint_states[joint.name]
        if joint.joint_type == "revolute":
            joint_jacobian[:3, index] = np.cross(
                state.axis_root,
                point - state.origin_root_m,
            )
            joint_jacobian[3:, index] = state.axis_root
        elif joint.joint_type == "prismatic":
            joint_jacobian[:3, index] = state.axis_root
        else:
            raise ValueError(f"UNSUPPORTED_MOVABLE_JOINT_TYPE:{joint.joint_type}")
    connection = np.asarray(backend.mechanical_connection(q8), dtype=float)
    generalized = joint_jacobian + base_jacobian @ connection
    return transform, joint_jacobian, generalized, connection


def _task_comparison(
    task_id: str,
    fixed_jacobian_6: np.ndarray,
    generalized_jacobian_6: np.ndarray,
    connection_6: np.ndarray,
    reduced_mass_6: np.ndarray,
    desired: np.ndarray,
    config: Mapping[str, Any],
    approach_basis: np.ndarray,
    approach_axis: np.ndarray,
) -> dict[str, Any]:
    if task_id == "FAR_APPROACH_5D":
        # The two orientation channels are the derivative of the tool z-axis
        # projected into its orthogonal plane: a_dot = omega x a.
        axis_rate_map = -_skew(approach_axis)
        fixed = np.vstack(
            (
                fixed_jacobian_6[:3],
                approach_basis @ axis_rate_map @ fixed_jacobian_6[3:],
            )
        )
        generalized = np.vstack(
            (
                generalized_jacobian_6[:3],
                approach_basis @ axis_rate_map @ generalized_jacobian_6[3:],
            )
        )
        expected_rank = 5
    elif task_id == "FINAL_ALIGNMENT_6D":
        fixed = fixed_jacobian_6
        generalized = generalized_jacobian_6
        expected_rank = 6
    else:
        raise ValueError(f"UNKNOWN_TASK:{task_id}")

    damping = float(config["dls"]["lambda"])
    raw_guard = singularity_guard(
        generalized,
        expected_rank,
        float(config["dls"]["singularity_sigma_min"]),
        float(config["dls"]["rank_rtol"]),
    )
    metric = config.get("task_space_metric", {})
    characteristic_length_m = metric.get("characteristic_length_m")
    weighting_matrix = metric.get("weighting_matrix")
    metric_bound = bool(
        metric.get("status") == "FROZEN"
        and characteristic_length_m is not None
        and float(characteristic_length_m) > 0.0
        and weighting_matrix is not None
    )
    guard = {
        "allow": False,
        "reason": "TASK_SPACE_UNIT_METRIC_UNBOUND_FAIL_CLOSED",
        "task_space_metric_bound": metric_bound,
        "characteristic_length_m": characteristic_length_m,
        "weighting_matrix_bound": weighting_matrix is not None,
        "raw_mixed_unit_diagnostic": raw_guard,
    }
    if not raw_guard["allow"]:
        guard["reason"] += "__RAW_DIAGNOSTIC_" + raw_guard["reason"]
        return {
            "task": task_id,
            "task_dimension": expected_rank,
            "guard": guard,
            "command_emitted": False,
            "status": "UNKNOWN_FAIL_CLOSED_NO_COMMAND",
        }

    naive_rate = euclidean_dls(fixed, desired, damping)
    compensated_primary = mass_weighted_dls(
        generalized,
        desired,
        reduced_mass_6,
        damping,
    )
    compensated_rate = compensated_primary.copy()
    nullspace: dict[str, Any]
    if task_id == "FAR_APPROACH_5D":
        vector, nullity, leakage = _canonical_null_vector(generalized)
        reaction_map = connection_6[3:, :]
        reaction_vector = reaction_map @ vector
        denominator = float(reaction_vector @ reaction_vector)
        alpha = (
            -float(reaction_vector @ (reaction_map @ compensated_primary))
            / denominator
            if denominator > 1e-18
            else 0.0
        )
        compensated_rate = compensated_primary + alpha * vector
        nullspace = {
            "allowed": True,
            "dimension": nullity,
            "basis_vector": vector.tolist(),
            "task_leakage_norm": leakage,
            "secondary_objective": "MINIMIZE_PREDICTED_BASE_ANGULAR_RATE_AT_ONE_STATE",
            "alpha": alpha,
            "joint_limit_barrier": {
                "present_as_fail_closed_domain_guard": True,
                "continuous_barrier_velocity_not_emitted": True,
                "reason": "AUTHORIZED_CONTROL_INTERVAL_AND_HARDWARE_RATE_LIMITS_ABSENT",
            },
        }
    else:
        singular = np.linalg.svd(generalized, compute_uv=False)
        rank = int(
            np.linalg.matrix_rank(
                generalized,
                tol=float(singular[0]) * float(config["dls"]["rank_rtol"]),
            )
        )
        nullspace = {
            "allowed": False,
            "dimension": int(generalized.shape[1] - rank),
            "secondary_objective": None,
            "reason": "STRICT_6D_ON_PHYSICAL_6R_HAS_NO_REDUNDANCY_AT_FULL_RANK",
        }

    naive_internal_residual = float(np.linalg.norm(fixed @ naive_rate - desired))
    naive_actual_residual = float(
        np.linalg.norm(generalized @ naive_rate - desired)
    )
    compensated_residual = float(
        np.linalg.norm(generalized @ compensated_rate - desired)
    )
    improvement = (
        100.0 * (naive_actual_residual - compensated_residual) / naive_actual_residual
        if naive_actual_residual > 0.0
        else 0.0
    )
    base_naive = connection_6 @ naive_rate
    base_compensated_primary = connection_6 @ compensated_primary
    base_compensated = connection_6 @ compensated_rate
    naive_base_angular_norm = float(np.linalg.norm(base_naive[3:]))
    primary_base_angular_norm = float(
        np.linalg.norm(base_compensated_primary[3:])
    )
    selected_base_angular_norm = float(np.linalg.norm(base_compensated[3:]))
    return {
        "task": task_id,
        "task_dimension": expected_rank,
        "task_angular_semantics": (
            "TOOL_Z_AXIS_RATE_PROJECTED_INTO_ORTHOGONAL_PLANE_1_PER_S"
            if task_id == "FAR_APPROACH_5D"
            else "TOOL_ANGULAR_VELOCITY_RAD_PER_S"
        ),
        "guard": guard,
        "command_emitted": False,
        "diagnostic_reference_rate_computed": True,
        "command_scope": "RAW_MIXED_UNIT_DIAGNOSTIC_ONLY__NO_CONTROL_COMMAND_OR_CREDIT",
        "metric_semantics": {
            "status": "UNBOUND",
            "unit_invariant": False,
            "linear_rows": "m/s",
            "angular_rows": (
                "1/s" if task_id == "FAR_APPROACH_5D" else "rad/s"
            ),
            "credit": False,
        },
        "fixed_base_naive": {
            "joint_rate": naive_rate.tolist(),
            "raw_mixed_unit_internal_task_residual_norm_no_credit": naive_internal_residual,
            "raw_mixed_unit_actual_task_residual_norm_no_credit": naive_actual_residual,
            "raw_mixed_unit_base_twist_norm_no_credit": float(np.linalg.norm(base_naive)),
            "predicted_base_angular_rate_norm_rad_s": float(
                np.linalg.norm(base_naive[3:])
            ),
        },
        "free_floating_mass_weighted_dls": {
            "primary_joint_rate": compensated_primary.tolist(),
            "selected_joint_rate": compensated_rate.tolist(),
            "raw_mixed_unit_actual_task_residual_norm_no_credit": compensated_residual,
            "raw_mixed_unit_residual_improvement_pct_no_credit": improvement,
            "raw_mixed_unit_primary_base_twist_norm_no_credit": float(
                np.linalg.norm(base_compensated_primary)
            ),
            "predicted_primary_base_angular_rate_norm_rad_s": primary_base_angular_norm,
            "raw_mixed_unit_selected_base_twist_norm_no_credit": float(
                np.linalg.norm(base_compensated)
            ),
            "predicted_selected_base_angular_rate_norm_rad_s": float(
                np.linalg.norm(base_compensated[3:])
            ),
        },
        "base_reaction_tradeoff": {
            "selected_reduces_angular_rate_vs_free_floating_primary": selected_base_angular_norm
            < primary_base_angular_norm,
            "selected_reduces_angular_rate_vs_naive": selected_base_angular_norm
            < naive_base_angular_norm,
            "selected_vs_naive_angular_rate_ratio": selected_base_angular_norm
            / naive_base_angular_norm,
            "interpretation": "GENERALIZED_DLS_RECOVERS_FREE_FLOATING_TASK_TRACKING_AT_THIS_STATE_BUT_DOES_NOT_ESTABLISH_MINIMUM_BASE_DISTURBANCE",
        },
        "nullspace": nullspace,
        "hardware_rate_limit_checked": False,
        "hardware_torque_limit_checked": False,
        "status": "HOLD_TASK_SPACE_UNIT_METRIC_UNBOUND__RAW_MIXED_UNIT_DIAGNOSTIC_NO_CREDIT",
    }


def precontact_tracking_once(
    repo_root: Path, config: Mapping[str, Any]
) -> dict[str, Any]:
    _install_unified_imports(repo_root)
    from sim13_v2_backends.dynamics_backend import UnifiedR2DynamicsBackend

    backend = UnifiedR2DynamicsBackend(project_root=repo_root)
    expected_names = list(config["joint_order"])
    expected_types = list(config["joint_types"])
    if list(backend.tree.movable_joint_names) != expected_names:
        raise ValueError("BACKEND_JOINT_ORDER_MISMATCH")
    if backend.tree.root_link != "spacecraft_bus":
        raise ValueError("BACKEND_ROOT_FRAME_MISMATCH")
    limits, parsed_types = _parse_urdf_limits(
        pinned_path(repo_root, config, "unified_r2_urdf"),
        expected_names,
        expected_types,
    )
    q8, margins = validate_joint_state_fail_closed(
        config["diagnostic_state"]["q8_mixed_rad_m"],
        limits,
    )
    qdotP = np.asarray(config["diagnostic_state"]["qdotP_m_s"], dtype=float)
    if qdotP.shape != (2,) or np.any(qdotP != 0.0):
        raise ValueError("PRECONTACT_QDOTP_MUST_BE_EXACT_ZERO")

    transform, fixed8, generalized8, connection8 = _tool_jacobians(
        backend,
        q8,
        "gripper_link",
    )
    if not np.all(fixed8[:, 6:] == 0.0):
        raise ValueError("GRIPPER_P_JOINTS_MUST_NOT_MOVE_GRIPPER_LINK_FRAME")
    reduced8 = np.asarray(backend.reduced_mass_matrix(q8), dtype=float)
    reduced6 = reduced8[:6, :6]
    approach_axis = np.asarray(transform[:3, 2], dtype=float)
    approach_basis = _approach_plane_basis(approach_axis)
    tasks = []
    for task_id in ("FAR_APPROACH_5D", "FINAL_ALIGNMENT_6D"):
        desired = np.asarray(
            config["diagnostic_task_twists"][task_id]["value"],
            dtype=float,
        )
        tasks.append(
            _task_comparison(
                task_id,
                fixed8[:, :6],
                generalized8[:, :6],
                connection8[:, :6],
                reduced6,
                desired,
                config,
                approach_basis,
                approach_axis,
            )
        )
    checks = {
        "root_frame_spacecraft_bus": backend.tree.root_link == "spacecraft_bus",
        "joint_order_exact_6R2P": list(backend.tree.movable_joint_names)
        == expected_names,
        "joint_types_exact_6R2P": parsed_types == expected_types,
        "no_virtual_seventh_revolute_joint": parsed_types[:6]
        == ["revolute"] * 6
        and parsed_types[6:] == ["prismatic"] * 2,
        "state_strictly_inside_all_urdf_limits": bool(np.all(margins > 0.0)),
        "qP_exact_static_for_precontact_probe": bool(np.all(qdotP == 0.0)),
        "gripper_link_jacobian_has_zero_P_columns": bool(
            np.all(fixed8[:, 6:] == 0.0)
        ),
        "reduced6_positive_definite": float(
            np.min(np.linalg.eigvalsh(reduced6))
        )
        > 0.0,
        "both_local_task_guards_allow": all(
            task["guard"]["allow"] for task in tasks
        ),
        "task_space_unit_metric_bound": all(
            task["guard"]["task_space_metric_bound"] for task in tasks
        ),
        "raw_mixed_unit_residuals_improve_no_credit": all(
            task["free_floating_mass_weighted_dls"][
                "raw_mixed_unit_actual_task_residual_norm_no_credit"
            ]
            < task["fixed_base_naive"][
                "raw_mixed_unit_actual_task_residual_norm_no_credit"
            ]
            for task in tasks
            if task.get("diagnostic_reference_rate_computed")
        ),
        "five_d_nullity_exact_one": tasks[0]["nullspace"]["dimension"] == 1,
        "six_d_nullity_exact_zero": tasks[1]["nullspace"]["dimension"] == 0,
    }
    joint_rows = []
    units = ["rad"] * 6 + ["m"] * 2
    for index, name in enumerate(expected_names):
        joint_rows.append(
            {
                "joint": name,
                "type": expected_types[index],
                "unit": units[index],
                "q": float(q8[index]),
                "lower": float(limits[index, 0]),
                "upper": float(limits[index, 1]),
                "lower_margin": float(margins[index, 0]),
                "upper_margin": float(margins[index, 1]),
            }
        )
    return {
        "schema": "CTRL_R2_PRECONTACT_TRACKING_INSTANCE_V1",
        "scope": config["scope"],
        "model": "HASH_PINNED_UNIFIED_R2_STATIC_AND_VELOCITY_LEVEL_INTERFACE",
        "frame_semantics": {
            "root": "spacecraft_bus",
            "tool": "gripper_link",
            "linear_then_angular_twist_expressed_in": "SPACECRAFT_BUS_ROOT_FRAME",
            "joint_axes": "HASH_PINNED_URDF_JOINT_FRAME_AXES_PROPAGATED_TO_ROOT",
        },
        "joint_limit_audit": joint_rows,
        "minimum_joint_margins": {
            "revolute_rad": float(np.min(margins[:6])),
            "prismatic_m": float(np.min(margins[6:])),
        },
        "qP_semantics": {
            "qdotP_exact_zero_in_diagnostic_state": True,
            "dynamic_lock_or_constraint_reaction_proven": False,
            "tauP_zero_interpreted_as_lock": False,
            "required_next_binding": "R2_8DOF_CONSTRAINED_DYNAMICS_GATE_V1",
        },
        "tasks": tasks,
        "checks": checks,
        "candidate_packaging_pass": all(checks.values()),
        "time_domain_tracking_executed": False,
        "collision_or_path_query_executed": False,
        "backend_advance_executed": False,
        "control_performance_validated": False,
    }


def build_precontact_tracking_gate(
    repo_root: Path, config: Mapping[str, Any], source_binding: Mapping[str, Any]
) -> dict[str, Any]:
    first = precontact_tracking_once(repo_root, config)
    replay = precontact_tracking_once(repo_root, config)
    first_hash = canonical_sha256(first)
    replay_hash = canonical_sha256(replay)
    deterministic = first_hash == replay_hash
    candidate_pass = bool(
        source_binding["pass"] and first["candidate_packaging_pass"] and deterministic
    )
    return {
        "schema": "CTRL_R2_PRECONTACT_TRACKING_GATE_V1",
        "scope": "LOCAL_STATIC_AND_VELOCITY_LEVEL_CANDIDATE_ONLY",
        "source_binding_pass": source_binding["pass"],
        "first": first,
        "determinism": {
            "first_canonical_sha256": first_hash,
            "replay_canonical_sha256": replay_hash,
            "bitwise_canonical_equal": deterministic,
        },
        "candidate_packaging_pass": candidate_pass,
        "precontact_tracking_validated": False,
        "reason_not_validated": [
            "TASK_SPACE_UNIT_METRIC_OR_CHARACTERISTIC_LENGTH_NOT_FROZEN",
            "NO_TIME_DOMAIN_REFERENCE_OR_PLANT_ADVANCE",
            "NO_HARDWARE_VALID_RATE_TORQUE_DELAY_OR_BANDWIDTH",
            "NO_AUTHORIZED_M01_PATH_OR_TIME_PARAMETERIZATION",
            "NO_COLLISION_HARNESS_OR_SOLAR_KEEPOUT_BINDING",
            "LOCKED_2P_CONSTRAINT_REACTIONS_BELONG_TO_OPEN_DYNAMICS_GATE",
        ],
        "verdict": (
            "PASS_CANDIDATE_PACKAGING__HOLD_TIME_DOMAIN_HARDWARE_AND_MECHANICAL_BINDING"
            if candidate_pass
            else "HOLD_TASK_SPACE_UNIT_METRIC_UNBOUND__CANDIDATE_PACKAGING_NOT_PASSED"
        ),
        "next_stage_authorized": False,
        "release_credit": False,
    }


def build_ctrl01_causal_ledger(
    classification: Mapping[str, Any],
    legacy_gate: Mapping[str, Any],
    replay_audit: Mapping[str, Any],
) -> dict[str, Any]:
    rows = {row["id"]: row for row in replay_audit["runs"]}
    if legacy_gate.get("verdict") != "REPEAT":
        raise ValueError("CTRL01_SOURCE_VERDICT_MUST_REMAIN_REPEAT")
    if rows["CTRL01_CURRENT_TREE"]["status"] != "HOLD_CURRENT_REPLAY":
        raise ValueError("CTRL01_CURRENT_TREE_REPLAY_HOLD_REQUIRED")
    categories = classification["categories"]
    ledger = [
        {
            "candidate_cause": "TRACKING_ERROR_UNDER_FROZEN_GAIN_AND_TRAJECTORY",
            "evidence_class": "DIRECT_RECORDED_GATE_EVIDENCE",
            "state": "CONFIRMED_FAILURE",
            "evidence": categories["tracking"]["evidence"],
            "causal_strength": "FAILURE_PRESENT__SOLE_ROOT_CAUSE_NOT_PROVEN",
        },
        {
            "candidate_cause": "JOINT_LIMIT_CONFLICT",
            "evidence_class": "DIRECT_RECORDED_GATE_EVIDENCE",
            "state": categories["joint_limit"]["state"],
            "minimum_margin_rad": categories["joint_limit"][
                "minimum_margin_rad"
            ],
            "causal_strength": "CONSTRAINT_FAILURE_CONFIRMED",
        },
        {
            "candidate_cause": "SINGULARITY_OR_NEAR_SINGULARITY",
            "evidence_class": "DIRECT_RECORDED_RISK_METRIC",
            "state": categories["singularity"]["state"],
            "minimum_task_sigma": categories["singularity"][
                "minimum_task_sigma"
            ],
            "threshold": categories["singularity"]["global_limit"],
            "causal_strength": "RISK_OBSERVED__TRAJECTORY_LEVEL_CAUSALITY_NOT_CERTIFIED",
        },
        {
            "candidate_cause": "FIXED_BASE_JACOBIAN_USED_FOR_FREE_FLOATING_PLANT",
            "evidence_class": "BOUNDED_ARCHITECTURE_INFERENCE",
            "state": "NOT_SUPPORTED_AS_SOLE_CAUSE",
            "evidence": "CTRL01 included generalized-Jacobian C1/C2/C3 variants and still retained REPEAT",
            "causal_strength": "FIXED_BASE_NAIVE_IS_INVALID_BASELINE__NOT_THE_ONLY_RECORDED_FAILURE",
        },
        {
            "candidate_cause": "FREE_FLOATING_REACTION_COMPENSATION_INEFFECTIVE",
            "evidence_class": "DIRECT_FROZEN_COMPARATOR_EVIDENCE",
            "state": categories["base_reaction"]["state"],
            "improvement_pct": categories["base_reaction"][
                "c3_vs_c2_match5_improvement_pct"
            ],
            "required_pct": categories["base_reaction"]["required_pct"],
            "causal_strength": "COMPARATOR_FAILURE_CONFIRMED__GENERAL_CAUSE_NOT_PROVEN",
        },
        {
            "candidate_cause": "PATH_OR_TASK_CONSTRAINT_INFEASIBILITY",
            "evidence_class": "PREREGISTERED_CONSTRAINT_CONFLICT",
            "state": categories["task_infeasibility"]["state"],
            "causal_strength": "SUPPORTED__NOT_M01_GEOMETRICALLY_RECERTIFIED",
        },
        {
            "candidate_cause": "NUMERICAL_INTEGRATION_OR_CONSERVATION_ERROR",
            "evidence_class": "DIRECT_RECORDED_NEGATIVE_EVIDENCE",
            "state": categories["numerical"]["state"],
            "metrics": categories["numerical"],
            "causal_strength": "NOT_SUPPORTED_AS_ROOT_CAUSE_IN_FROZEN_RUN",
        },
        {
            "candidate_cause": "GAIN_SELECTION",
            "evidence_class": "UNTESTED_HYPOTHESIS",
            "state": "NOT_ISOLATED",
            "causal_strength": "NO_GAIN_ONLY_CAUSAL_CREDIT__GAIN_TUNING_TO_GREEN_FORBIDDEN",
        },
        {
            "candidate_cause": "MISSING_HARDWARE_ACTUATOR_DYNAMICS",
            "evidence_class": "DIRECT_OPEN_DEPENDENCY",
            "state": categories["missing_actuator_model"]["state"],
            "causal_strength": "BLOCKS_HARDWARE_VALID_CONTROL__NOT_RETROACTIVE_CTRL01_CAUSE",
        },
    ]
    return {
        "schema": "CTRL01_R2_FAILURE_CAUSAL_LEDGER",
        "source_verdict": "REPEAT",
        "source_negative_result_retained": True,
        "current_tree_replay": {
            "status": rows["CTRL01_CURRENT_TREE"]["status"],
            "passed": rows["CTRL01_CURRENT_TREE"]["passed"],
            "failed": rows["CTRL01_CURRENT_TREE"]["failed"],
            "total": rows["CTRL01_CURRENT_TREE"]["total"],
            "exact_legacy_reproduction_claimed": False,
        },
        "classification_scope": "EVIDENCE_BOUND_LEDGER__NO_NEW_CTRL01_PLANT_RERUN",
        "causal_certification_complete": False,
        "entries": ledger,
        "disposition": "KEEP_REPEAT__REDESIGN_STAGE_TASK_AND_BIND_DYNAMICS_HARDWARE_MECHANICAL_CONSTRAINTS_BEFORE_TIME_DOMAIN_RERUN",
        "next_stage_authorized": False,
        "release_credit": False,
    }


def build_flex_robustness_gate(
    rom: Mapping[str, Any],
    static_screen: Mapping[str, Any],
    e23_gate: Mapping[str, Any],
    supervisor_contract: Mapping[str, Any],
    source_binding: Mapping[str, Any],
) -> dict[str, Any]:
    labels = list(rom["mode_labels"])
    corner_order = ["LOW", "NOMINAL", "HIGH"]
    frequencies = rom["rom_eigenfrequencies_by_corner_hz"]
    corner_rows = []
    all_positive = True
    for corner in corner_order:
        values = [float(value) for value in frequencies[corner]]
        if len(values) != 7 or any(value <= 0.0 for value in values):
            all_positive = False
        corner_rows.append(
            {
                "corner": corner,
                "mode_count_per_wing": len(values),
                "frequencies_hz": values,
                "minimum_frequency_hz": min(values),
                "maximum_frequency_hz": max(values),
                "maximum_modal_period_s": 1.0 / min(values),
            }
        )
    checks = {
        "source_binding_pass": bool(source_binding["pass"]),
        "rom_schema_exact": rom.get("schema") == "R2_SEVEN_MODE_ROM_V3",
        "mode_labels_exact_seven": len(labels) == 7,
        "low_nominal_high_each_have_seven_positive_modes": all_positive,
        "dual_wing_total_modes_exact_fourteen": 2 * len(labels) == 14,
        "static_screen_passed_without_mission_credit": static_screen.get("pass")
        is True
        and static_screen.get("next_stage_authorized") is False,
        "e23_provisional_scope_retained": e23_gate.get("technical_verdict")
        == "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS"
        and e23_gate.get("release_credit") is False,
        "coefficient_emission_forbidden_without_task_inputs": supervisor_contract[
            "flex_trajectory_shaping"
        ]["coefficient_emission_allowed"]
        is False,
    }
    candidate_pass = all(checks.values())
    return {
        "schema": "CTRL_R2_FLEX_ROBUSTNESS_GATE_V1",
        "scope": "ROM_FREQUENCY_CATALOG_AND_SHAPING_INTERFACE_ONLY",
        "wing_order": ["LEFT", "RIGHT"],
        "mode_labels_per_wing": labels,
        "corner_catalog": corner_rows,
        "checks": checks,
        "candidate_packaging_pass": candidate_pass,
        "trajectory_shaper_coefficients_emitted": False,
        "mission_time_history_executed": False,
        "flex_robustness_validated": False,
        "remaining_inputs": [
            "AUTHORIZED_M01_GEOMETRIC_PATH",
            "TIME_PARAMETERIZATION",
            "TASK_EXCITATION_SPECTRUM",
            "HARDWARE_VALID_ACTUATOR_BANDWIDTH",
            "ROOT_LOAD_LIMITS_AND_TASK_BOUND FLEX_THRESHOLDS",
        ],
        "verdict": (
            "PASS_INTERFACE_PACKAGING__HOLD_NO_TASK_TIME_HISTORY_OR_ACTUATOR_BANDWIDTH"
            if candidate_pass
            else "HOLD_FLEX_INTERFACE_PACKAGING_FAILURE"
        ),
        "next_stage_authorized": False,
        "release_credit": False,
    }


def build_supervisor_assessment(
    supervisor_contract: Mapping[str, Any],
    ctrl02_gate: Mapping[str, Any],
    safe_gate: Mapping[str, Any],
    actuator_audit: Mapping[str, Any],
    contact_gate: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "CTRL_R2_SUPERVISOR_ASSESSMENT_V1",
        "interface_contract_complete": supervisor_contract[
            "interface_packaging_complete"
        ]
        is True,
        "base_attitude": {
            "state_machine_enum_complete": len(
                supervisor_contract["base_attitude_and_momentum"]["states"]
            )
            == 5,
            "historical_ctrl02_verdict": ctrl02_gate.get("verdict"),
            "historical_review_status": ctrl02_gate.get("review_status"),
            "hardware_valid": False,
            "operational": False,
        },
        "wheel_momentum": {
            "thresholds_present": False,
            "threshold_status": supervisor_contract["base_attitude_and_momentum"][
                "threshold_status"
            ],
            "physics_veto_150kg_3dps": "ABORT_OR_RECOVERY",
            "operational": False,
        },
        "actuator": {
            "minimum_intake_schema_complete": actuator_audit.get(
                "minimum_intake_schema_complete"
            ),
            "semantic_requirements_complete": actuator_audit.get(
                "semantic_requirements_complete"
            ),
            "hardware_model_valid": actuator_audit.get("hardware_model_valid"),
            "zero_fill_forbidden": True,
        },
        "hybrid_capture": {
            "state_machine_enum_complete": len(
                supervisor_contract["hybrid_capture"]["states"]
            )
            == 5,
            "contact_model_gate": contact_gate.get("verdict"),
            "contact_model_scope": "BOUNDED_PROVISIONAL",
            "as_built_parameters_present": False,
            "operational": False,
        },
        "safe": {
            "historical_verdict": safe_gate.get("verdict"),
            "review_status": safe_gate.get("review_status"),
            "source_next_stage_authorized": safe_gate.get(
                "next_stage_authorized"
            ),
            "current_tree_replay_clean": False,
            "operational_authorization": False,
        },
        "operational_supervisor_complete": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def build_control_engineering_gate(
    source_binding: Mapping[str, Any],
    causal_ledger: Mapping[str, Any],
    phase_contract: Mapping[str, Any],
    precontact_gate: Mapping[str, Any],
    flex_gate: Mapping[str, Any],
    supervisor_assessment: Mapping[str, Any],
    predevelopment_gate: Mapping[str, Any],
) -> dict[str, Any]:
    criteria = [
        {
            "id": "CG0",
            "name": "CTRL01 causal reproduction and classification",
            "candidate_packaging_pass": causal_ledger["source_verdict"]
            == "REPEAT"
            and causal_ledger["current_tree_replay"]["status"]
            == "HOLD_CURRENT_REPLAY",
            "engineering_pass": False,
            "status": "REPEAT_RETAINED__CAUSAL_CERTIFICATION_INCOMPLETE",
        },
        {
            "id": "CG1",
            "name": "precontact end-effector tracking",
            "candidate_packaging_pass": precontact_gate[
                "candidate_packaging_pass"
            ],
            "engineering_pass": precontact_gate["precontact_tracking_validated"],
            "status": precontact_gate["verdict"],
        },
        {
            "id": "CG2",
            "name": "joint harness collision constraints",
            "candidate_packaging_pass": phase_contract[
                "task_contract_complete"
            ]
            is True,
            "engineering_pass": False,
            "status": "JOINT_DOMAIN_GUARD_PRESENT__HARNESS_COLLISION_AND_M01_BINDING_HOLD",
        },
        {
            "id": "CG3",
            "name": "base attitude",
            "candidate_packaging_pass": supervisor_assessment["base_attitude"][
                "state_machine_enum_complete"
            ],
            "engineering_pass": False,
            "status": "INTERFACE_ONLY__CTRL02_PROVISIONAL_AND_HARDWARE_HOLD",
        },
        {
            "id": "CG4",
            "name": "wheel momentum and actuator resource",
            "candidate_packaging_pass": bool(
                supervisor_assessment["wheel_momentum"]["thresholds_present"]
                and supervisor_assessment["actuator"]["hardware_model_valid"]
            ),
            "engineering_pass": False,
            "status": "STATE_ENUM_PRESENT__MEASUREMENTS_AND_THRESHOLDS_PENDING",
        },
        {
            "id": "CG5",
            "name": "flex robustness",
            "candidate_packaging_pass": flex_gate["candidate_packaging_pass"],
            "engineering_pass": flex_gate["flex_robustness_validated"],
            "status": flex_gate["verdict"],
        },
        {
            "id": "CG6",
            "name": "contact and post-capture supervisor",
            "candidate_packaging_pass": supervisor_assessment[
                "hybrid_capture"
            ]["state_machine_enum_complete"],
            "engineering_pass": False,
            "status": "INTERFACE_ONLY__AS_BUILT_CONTACT_AND_PAYLOAD_RECONFIGURATION_HOLD",
        },
        {
            "id": "CG7",
            "name": "fail-closed SAFE integration",
            "candidate_packaging_pass": bool(
                supervisor_assessment["safe"]["current_tree_replay_clean"]
                and supervisor_assessment["safe"]["operational_authorization"]
            ),
            "engineering_pass": False,
            "status": "HISTORICAL_SAFE_PASS_BOUND__CURRENT_REPLAY_AND_REVIEW_HOLD",
        },
    ]
    candidate_pass = bool(
        source_binding["pass"]
        and all(row["candidate_packaging_pass"] for row in criteria)
    )
    engineering_complete = all(row["engineering_pass"] for row in criteria)
    if engineering_complete:
        raise AssertionError(
            "CONTROL_ENGINEERING_COMPLETE_CANNOT_BE_TRUE_WITH_DECLARED_HOLDS"
        )
    return {
        "schema": "R2_CONTROL_ENGINEERING_GATE_V1",
        "scope": "R2_CONTROL_ENGINEERING_CANDIDATE_PACKAGING__NO_EXECUTION_RELEASE",
        "source_binding": {
            "pin_count": source_binding["pin_count"],
            "match_count": source_binding["match_count"],
            "pass": source_binding["pass"],
        },
        "criteria": criteria,
        "candidate_package_complete": candidate_pass,
        "candidate_packaging_complete": candidate_pass,
        "artifact_package_generated": True,
        "control_engineering_complete": False,
        "collision_constrained_tracking_valid": False,
        "hardware_valid": False,
        "safe_review_pass": False,
        "predevelopment_source_technical_complete": predevelopment_gate.get(
            "technical_predevelopment_complete"
        ),
        "execution_guards": {
            "backend_advance_executed": False,
            "collision_query_executed": False,
            "pair_or_edge_query_executed": False,
            "m01_path_search_executed": False,
            "contact_execution_executed": False,
        },
        "hard_blockers": [
            "CTRL01_REPEAT_AND_CURRENT_TREE_REPLAY_HOLD",
            "TASK_SPACE_UNIT_METRIC_OR_CHARACTERISTIC_LENGTH_NOT_FROZEN",
            "NO_TIME_DOMAIN_FREE_FLOATING_TRACKING_VALIDATION",
            "NO_HARDWARE_VALID_ACTUATOR_RATE_TORQUE_DELAY_BANDWIDTH_OR_WHEEL_THRESHOLDS",
            "RAW_MIXED_UNIT_GENERALIZED_DLS_DIAGNOSTIC_HAS_NO_TRACKING_OR_SINGULARITY_CREDIT_AND_MINIMUM_BASE_DISTURBANCE_NOT_ESTABLISHED",
            "M01_MECHANICAL_COLLISION_HARNESS_AND_TIME_PARAMETERIZATION_NOT_BOUND_TO_CONTROL",
            "LOCKED_2P_REACTION_AND_ACTUATED_2P_DYNAMICS_NOT_BOUND",
            "FLEX_TASK_TIME_HISTORY_AND_SHAPER_COEFFICIENTS_ABSENT",
            "CONTACT_AS_BUILT_MEASUREMENT_PENDING_AND_POST_CAPTURE_PLANT_NOT_BOUND",
            "SAFE_CURRENT_REPLAY_AND_REVIEW_HOLD",
        ],
        "unknowns": [
            "TASK_SPACE_CHARACTERISTIC_LENGTH_OR_WEIGHTING_MATRIX",
            "HARDWARE_ACTUATOR_DYNAMICS_AND_WHEEL_LIMITS",
            "AUTHORIZED_M01_PATH_TIME_HISTORY_AND_COLLISION_CONSTRAINTS",
            "TASK_BOUND_FLEX_EXCITATION_AND_ROOT_LOAD_RESPONSE",
            "AS_BUILT_CONTACT_TRANSITION_AND_POST_CAPTURE_COMBINED_PLANT",
            "SAFE_INDEPENDENT_REVIEW_ON_CURRENT_TREE",
        ],
        "technical_verdict": (
            "PASS_CANDIDATE_PACKAGING__CONTROL_ENGINEERING_HOLD"
            if candidate_pass
            else "HOLD_TASK_SPACE_UNIT_METRIC_UNBOUND__CONTROL_ENGINEERING_INCOMPLETE__NO_RELEASE_CREDIT"
        ),
        "next_stage_authorized": False,
        "release_credit": False,
        "rl_vla_execution_authorized": False,
    }


def write_manifest(package_root: Path, manifest_path: Path) -> dict[str, Any]:
    files = sorted(
        path
        for path in package_root.rglob("*")
        if path.is_file()
        and path != manifest_path
        and "__pycache__" not in path.parts
        and ".pytest_cache" not in path.parts
    )
    rows = []
    for path in files:
        relative = path.relative_to(package_root).as_posix()
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["path", "bytes", "sha256"])
        writer.writeheader()
        writer.writerows(rows)
    return {
        "file_count": len(rows),
        "manifest_path": manifest_path.relative_to(package_root).as_posix(),
        "all_hashes_uppercase_sha256": all(
            len(row["sha256"]) == 64 and row["sha256"] == row["sha256"].upper()
            for row in rows
        ),
    }
