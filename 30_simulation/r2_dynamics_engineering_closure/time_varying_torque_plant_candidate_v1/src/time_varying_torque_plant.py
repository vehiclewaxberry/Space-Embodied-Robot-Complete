"""Hash-bound current-R2 time-varying generalized-effort plant candidate.

This module deliberately implements only the zero-total-momentum rigid design
diagnostic admitted by the contract.  The six-component base twist is an
algebraic consequence of the eight joint rates; it is not an independently
integrated momentum state.  No contact, target, flexible, actuator-hardware, or
control model is present here.
"""

from __future__ import annotations

from dataclasses import dataclass
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Sequence
import xml.etree.ElementTree as ET

import numpy as np
from scipy.integrate import solve_ivp


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = (
    PACKAGE_ROOT
    / "contracts"
    / "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_CONTRACT_V1.json"
)
EXPECTED_CONTRACT_CANONICAL_SHA256 = (
    "696494D39C9246E19269B4F92577D8EAB74C848D9A08B56639080A2D75996565"
)
GATE_IDS = tuple(f"G{index:02d}" for index in range(1, 25))
EXPECTED_DIRECT_RUNTIME_PIN_IDS = (
    "parent_dynamics_source",
    "free_floating_tree",
    "unified_r2_backend",
)
EXPECTED_TRANSITIVE_RUNTIME_PIN_IDS = (
    "sim13_v2_package_init",
    "sim13_v2_authority_resolver",
    "sim13_v2_contracts_module",
    "sim13_v2_env_module",
    "sim13_v2_system_model",
    "sim13_v2_backends_package_init",
    "sim13_v2_backends_canonical",
)


class ContractError(RuntimeError):
    """Raised when an authority, source, state, or execution contract fails."""


def _reject_constant(token: str) -> None:
    raise ValueError(f"NONFINITE_JSON_CONSTANT_REJECTED:{token}")


def _unique_pairs(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"DUPLICATE_JSON_KEY_REJECTED:{key}")
        result[key] = value
    return result


def loads_json_strict(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=_unique_pairs,
        parse_constant=_reject_constant,
    )


def load_json_strict(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError(f"JSON_UTF8_REQUIRED:{path}") from exc
    return loads_json_strict(text)


def _finite_float(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ContractError(f"{field}_BOOLEAN_NOT_NUMERIC")
    result = float(value)
    if not math.isfinite(result):
        raise ContractError(f"{field}_NONFINITE")
    return result


def finite_vector(values: Sequence[float], size: int, field: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise ContractError(f"{field}_MUST_HAVE_{size}_FINITE_VALUES")
    return result


def to_builtin(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [to_builtin(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return to_builtin(value.item())
    if isinstance(value, Mapping):
        return {str(key): to_builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_builtin(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("NONFINITE_EVIDENCE_VALUE_REJECTED")
        return value
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(f"UNSUPPORTED_EVIDENCE_TYPE:{type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        to_builtin(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def file_record(path: Path, project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(project_root.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest().upper(),
    }


def _require(condition: bool, code: str) -> None:
    if not bool(condition):
        raise ContractError(code)


def validate_contract_semantics(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Validate semantic boundaries without relying on the canonical hash."""

    _require(
        contract.get("schema")
        == "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_CONTRACT_V1",
        "CONTRACT_SCHEMA_MISMATCH",
    )
    _require(
        contract.get("authority_scope")
        == "CURRENT_R2_ZERO_MOMENTUM_RIGID_DESIGN_DIAGNOSTIC_ONLY",
        "AUTHORITY_SCOPE_MISMATCH",
    )
    model = contract.get("model_contract", {})
    _require(model.get("expected_links") == 19, "LINK_COUNT_CONTRACT_MISMATCH")
    _require(model.get("expected_joints") == 18, "JOINT_COUNT_CONTRACT_MISMATCH")
    _require(model.get("expected_physical_links") == 16, "PHYSICAL_LINK_COUNT_MISMATCH")
    _require(model.get("expected_frame_only_links") == 3, "FRAME_ONLY_COUNT_MISMATCH")
    _require(model.get("expected_movable_dof") == 8, "MOVABLE_DOF_CONTRACT_MISMATCH")
    _require(model.get("integrated_state_dimension") == 23, "STATE_DIMENSION_MISMATCH")
    _require(model.get("derived_base_twist_dimension") == 6, "BASE_TWIST_DIMENSION_MISMATCH")
    expected_joint_order = [f"joint{i}" for i in range(1, 7)] + [
        "gripper_joint1",
        "gripper_joint2",
    ]
    _require(model.get("joint_order") == expected_joint_order, "JOINT_ORDER_MISMATCH")
    _require(
        model.get("joint_types") == ["revolute"] * 6 + ["prismatic"] * 2,
        "JOINT_TYPES_MISMATCH",
    )
    _require(
        model.get("coordinate_units") == ["rad"] * 6 + ["m"] * 2,
        "COORDINATE_UNITS_NOT_SEPARATED",
    )
    _require(
        model.get("rate_units") == ["rad/s"] * 6 + ["m/s"] * 2,
        "RATE_UNITS_NOT_SEPARATED",
    )
    _require(
        model.get("effort_units") == ["N*m"] * 6 + ["N"] * 2,
        "EFFORT_UNITS_NOT_SEPARATED",
    )
    lower = finite_vector(model.get("joint_lower_mixed_rad_m", []), 8, "JOINT_LOWER")
    upper = finite_vector(model.get("joint_upper_mixed_rad_m", []), 8, "JOINT_UPPER")
    scales = finite_vector(
        model.get("reference_scales_mixed_rad_m", []), 8, "REFERENCE_SCALES"
    )
    _require(np.all(upper > lower), "JOINT_LIMIT_ORDER_INVALID")
    _require(np.all(scales > 0.0), "REFERENCE_SCALE_NONPOSITIVE")
    _require(
        model.get("total_momentum_scope")
        == "EXACTLY_ZERO__NONZERO_TOTAL_MOMENTUM_INPUT_FAILS_CLOSED",
        "NONZERO_MOMENTUM_SCOPE_NOT_CLOSED",
    )
    initial = contract.get("initial_state", {})
    q0 = finite_vector(initial.get("q0_mixed_rad_m", []), 8, "q0")
    finite_vector(initial.get("qdot0_mixed_rad_s_m_s", []), 8, "dq0")
    finite_vector(initial.get("base_position_inertial_initial_m", []), 3, "r0")
    quaternion = finite_vector(
        initial.get("base_quaternion_body_to_inertial_initial_wxyz", []), 4, "Q0"
    )
    _require(float(np.linalg.norm(quaternion)) > 0.0, "INITIAL_QUATERNION_ZERO")
    _require(np.all(q0 >= lower) and np.all(q0 <= upper), "INITIAL_STATE_LIMIT_VIOLATION")
    _require(initial.get("backend_default_initial_state_allowed") is False, "BACKEND_DEFAULT_NOT_REJECTED")
    _require(initial.get("required_backend_default_invalid_joint") == "gripper_joint2", "DEFAULT_INVALID_JOINT_MISMATCH")
    _require(
        _finite_float(initial.get("required_backend_default_invalid_value_m"), "DEFAULT_INVALID_VALUE")
        == -0.004,
        "DEFAULT_INVALID_VALUE_MISMATCH",
    )
    profile = contract.get("effort_profile", {})
    _require(profile.get("profile") == "tau_i(t)=amplitude_i*sin(pi*t/T)^2", "EFFORT_PROFILE_MISMATCH")
    _require(_finite_float(profile.get("duration_s"), "DURATION") > 0.0, "DURATION_NONPOSITIVE")
    _require(_finite_float(profile.get("fixed_step_s"), "STEP") > 0.0, "STEP_NONPOSITIVE")
    finite_vector(profile.get("amplitude_mixed_Nm_N", []), 8, "EFFORT_AMPLITUDE")
    _require(profile.get("hardware_limit_enforcement") is False, "HARDWARE_LIMIT_CLAIM_FORBIDDEN")
    lanes = contract.get("lanes", {})
    _require(lanes.get("ACTUATED_8DOF", {}).get("active_coordinates") == 8, "ACTUATED_LANE_MISMATCH")
    locked = lanes.get("LOCKED_2P_6R_PULSE", {})
    _require(locked.get("active_coordinates") == 6, "LOCKED_LANE_MISMATCH")
    finite_vector(locked.get("qP_star_m", []), 2, "LOCKED_qP")
    _require(np.array_equal(finite_vector(locked.get("dqP_m_s", []), 2, "LOCKED_dqP"), np.zeros(2)), "LOCKED_dqP_NONZERO")
    _require(np.array_equal(finite_vector(locked.get("tauP_N", []), 2, "LOCKED_tauP"), np.zeros(2)), "LOCKED_tauP_NONZERO")
    solver = contract.get("solver_contract", {})
    _require(solver.get("primary") == "FIXED_STEP_RK4_WITH_OUTPUT_QUATERNION_RENORMALIZATION", "PRIMARY_SOLVER_MISMATCH")
    _require(solver.get("cross") == "SCIPY_DOP853", "CROSS_SOLVER_MISMATCH")
    _require(_finite_float(solver.get("cross_rtol"), "DOP853_RTOL") > 0.0, "DOP853_RTOL_INVALID")
    _require(_finite_float(solver.get("cross_atol"), "DOP853_ATOL") > 0.0, "DOP853_ATOL_INVALID")
    _require(solver.get("explicit_inverse_forbidden") is True, "EXPLICIT_INVERSE_NOT_FORBIDDEN")
    _require(solver.get("raw_mixed_unit_spectrum_or_condition_credit") is False, "RAW_MIXED_SPECTRUM_CREDIT_FORBIDDEN")
    guards = contract.get("execution_guards", {})
    _require(bool(guards) and all(value is False for value in guards.values()), "EXECUTION_GUARD_TRUE")
    release = contract.get("release_boundary", {})
    required_false = (
        "flex_valid",
        "contact_valid",
        "target_attachment_valid",
        "hardware_valid",
        "control_valid",
        "parent_dynamics_engineering_complete",
        "sim13_non_abort_authorized",
        "next_stage_authorized",
        "release_credit",
    )
    _require(release.get("candidate_only") is True, "CANDIDATE_ONLY_FLAG_MISSING")
    _require(all(release.get(key) is False for key in required_false), "RELEASE_BOUNDARY_ESCALATED")
    _require(contract.get("next_stage_authorized") is False, "TOP_LEVEL_NEXT_STAGE_ESCALATED")
    _require(contract.get("release_credit") is False, "TOP_LEVEL_RELEASE_CREDIT_ESCALATED")
    pins = contract.get("source_pins", [])
    _require(isinstance(pins, list) and len(pins) == 19, "SOURCE_PIN_COUNT_MISMATCH")
    _require(len({item.get("id") for item in pins}) == 19, "SOURCE_PIN_ID_DUPLICATE")
    for item in pins:
        _require(isinstance(item.get("path"), str) and bool(item["path"]), "SOURCE_PIN_PATH_INVALID")
        _require(isinstance(item.get("bytes"), int) and item["bytes"] > 0, "SOURCE_PIN_BYTES_INVALID")
        sha = item.get("sha256")
        _require(isinstance(sha, str) and len(sha) == 64 and sha == sha.upper(), "SOURCE_PIN_SHA_INVALID")
    binding = contract.get("runtime_project_module_binding", {})
    _require(
        tuple(binding.get("direct_pinned_module_ids", []))
        == EXPECTED_DIRECT_RUNTIME_PIN_IDS,
        "DIRECT_RUNTIME_PIN_SET_MISMATCH",
    )
    _require(
        tuple(binding.get("transitive_pinned_module_ids", []))
        == EXPECTED_TRANSITIVE_RUNTIME_PIN_IDS,
        "TRANSITIVE_RUNTIME_PIN_SET_MISMATCH",
    )
    _require(
        binding.get("expected_project_runtime_module_count_excluding_candidate") == 10
        and binding.get("runtime_transitive_module_count") == 7
        and binding.get("unpinned_project_runtime_modules_allowed") is False,
        "RUNTIME_PROJECT_MODULE_BINDING_MISMATCH",
    )
    _require(contract.get("review_status") == "PENDING_OWNER_REVIEW", "REVIEW_STATUS_MISMATCH")
    return {
        "semantic_contract_valid": True,
        "joint_domains_separated": True,
        "source_pin_count": len(pins),
        "all_guards_false": True,
        "all_release_authorities_false": True,
    }


def load_contract() -> dict[str, Any]:
    contract = load_json_strict(CONTRACT_PATH)
    if canonical_sha256(contract) != EXPECTED_CONTRACT_CANONICAL_SHA256:
        raise ContractError("CONTRACT_CANONICAL_SHA256_DRIFT")
    validate_contract_semantics(contract)
    return contract


def validate_source_pins(contract: Mapping[str, Any], project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for pin in contract["source_pins"]:
        path = (project_root / pin["path"]).resolve()
        _require(path.is_file(), f"SOURCE_PIN_MISSING:{pin['id']}")
        actual = file_record(path, project_root)
        match = actual["bytes"] == pin["bytes"] and actual["sha256"] == pin["sha256"]
        records.append({"id": pin["id"], **actual, "match": match})
        _require(match, f"SOURCE_PIN_DRIFT:{pin['id']}")
    return {"records": records, "all_match": all(row["match"] for row in records)}


def audit_runtime_project_modules(
    contract: Mapping[str, Any], project_root: Path = PROJECT_ROOT
) -> dict[str, Any]:
    """Inventory every imported project module outside this candidate package."""

    root = project_root.resolve()
    package = PACKAGE_ROOT.resolve()
    actual_by_module: dict[str, str] = {}
    for name, module in sorted(sys.modules.items()):
        source = getattr(module, "__file__", None)
        if not source:
            continue
        path = Path(source).resolve()
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            continue
        try:
            path.relative_to(package)
            continue
        except ValueError:
            pass
        actual_by_module[name] = relative
    binding = contract["runtime_project_module_binding"]
    ids = tuple(binding["direct_pinned_module_ids"]) + tuple(
        binding["transitive_pinned_module_ids"]
    )
    pins = {item["id"]: item for item in contract["source_pins"]}
    expected_paths = sorted(pins[identifier]["path"] for identifier in ids)
    actual_paths = sorted(set(actual_by_module.values()))
    return {
        "expected_module_source_paths": expected_paths,
        "actual_module_source_paths": actual_paths,
        "actual_module_names_to_paths": actual_by_module,
        "direct_pinned_module_count": len(binding["direct_pinned_module_ids"]),
        "transitive_pinned_module_count": len(binding["transitive_pinned_module_ids"]),
        "all_project_runtime_modules_pinned_exactly": actual_paths == expected_paths,
        "unpinned_project_runtime_modules": sorted(set(actual_paths) - set(expected_paths)),
        "pinned_but_not_imported_modules": sorted(set(expected_paths) - set(actual_paths)),
    }


def _load_parent_module(project_root: Path = PROJECT_ROOT) -> Any:
    path = project_root / "30_simulation" / "r2_dynamics_engineering_closure" / "src" / "r2_dynamics.py"
    name = "_r2_time_varying_parent_dynamics"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ContractError("PARENT_DYNAMICS_IMPORT_SPEC_FAILED")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def parse_urdf_contract(contract: Mapping[str, Any], project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    pin = next(item for item in contract["source_pins"] if item["id"] == "unified_r2_urdf")
    root = ET.parse(project_root / pin["path"]).getroot()
    links = root.findall("link")
    joints = root.findall("joint")
    movable: list[dict[str, Any]] = []
    for joint in joints:
        if joint.attrib.get("type") not in {"revolute", "continuous", "prismatic"}:
            continue
        limit = joint.find("limit")
        movable.append(
            {
                "name": joint.attrib["name"],
                "type": joint.attrib["type"],
                "lower": None if limit is None else float(limit.attrib["lower"]),
                "upper": None if limit is None else float(limit.attrib["upper"]),
            }
        )
    by_name = {item["name"]: item for item in movable}
    order = contract["model_contract"]["joint_order"]
    _require(set(by_name) == set(order), "URDF_MOVABLE_JOINT_SET_MISMATCH")
    ordered = [by_name[name] for name in order]
    expected_types = contract["model_contract"]["joint_types"]
    _require([item["type"] for item in ordered] == expected_types, "URDF_JOINT_TYPE_MISMATCH")
    lower = [item["lower"] for item in ordered]
    upper = [item["upper"] for item in ordered]
    _require(lower == contract["model_contract"]["joint_lower_mixed_rad_m"], "URDF_LOWER_LIMIT_MISMATCH")
    _require(upper == contract["model_contract"]["joint_upper_mixed_rad_m"], "URDF_UPPER_LIMIT_MISMATCH")
    return {
        "robot_name": root.attrib.get("name"),
        "links": len(links),
        "joints": len(joints),
        "movable_dof": len(ordered),
        "joint_order": order,
        "joint_types": expected_types,
        "lower_mixed_rad_m": lower,
        "upper_mixed_rad_m": upper,
    }


def quat_normalize(quaternion: Sequence[float]) -> np.ndarray:
    q = finite_vector(quaternion, 4, "QUATERNION")
    norm = float(np.linalg.norm(q))
    if norm <= 0.0:
        raise ContractError("QUATERNION_ZERO_NORM")
    return q / norm


def quat_product(left: Sequence[float], right: Sequence[float]) -> np.ndarray:
    lw, lx, ly, lz = finite_vector(left, 4, "QUATERNION_LEFT")
    rw, rx, ry, rz = finite_vector(right, 4, "QUATERNION_RIGHT")
    return np.asarray(
        [
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        ]
    )


def quat_rotation_body_to_inertial(quaternion: Sequence[float]) -> np.ndarray:
    w, x, y, z = quat_normalize(quaternion)
    return np.asarray(
        [
            [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - w * z), 2.0 * (x * z + w * y)],
            [2.0 * (x * y + w * z), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - w * x)],
            [2.0 * (x * z - w * y), 2.0 * (y * z + w * x), 1.0 - 2.0 * (x * x + y * y)],
        ]
    )


def attitude_distance_rad(left: Sequence[float], right: Sequence[float]) -> float:
    q1 = quat_normalize(left)
    q2 = quat_normalize(right)
    if float(q1 @ q2) < 0.0:
        q2 = -q2
    relative = quat_product(np.asarray([q1[0], -q1[1], -q1[2], -q1[3]]), q2)
    return float(2.0 * math.atan2(np.linalg.norm(relative[1:]), abs(relative[0])))


def validate_physical_state(
    position: Sequence[float],
    quaternion: Sequence[float],
    q: Sequence[float],
    dq: Sequence[float],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    finite_vector(position, 3, "BASE_POSITION")
    quat_normalize(quaternion)
    qv = finite_vector(q, 8, "q")
    finite_vector(dq, 8, "dq")
    lower = finite_vector(contract["model_contract"]["joint_lower_mixed_rad_m"], 8, "LOWER")
    upper = finite_vector(contract["model_contract"]["joint_upper_mixed_rad_m"], 8, "UPPER")
    violations = np.flatnonzero((qv < lower) | (qv > upper))
    if violations.size:
        names = contract["model_contract"]["joint_order"]
        raise ContractError("JOINT_POSITION_LIMIT_VIOLATION:" + ",".join(names[index] for index in violations))
    return {
        "valid": True,
        "revolute_min_margin_rad": float(np.min(np.minimum(qv[:6] - lower[:6], upper[:6] - qv[:6]))),
        "prismatic_min_margin_m": float(np.min(np.minimum(qv[6:] - lower[6:], upper[6:] - qv[6:]))),
    }


def reject_nonzero_total_momentum(momentum6: Sequence[float]) -> None:
    value = finite_vector(momentum6, 6, "TOTAL_MOMENTUM")
    if not np.array_equal(value, np.zeros(6)):
        raise ContractError("NONZERO_TOTAL_MOMENTUM_UNSUPPORTED_FAIL_CLOSED")


def effort_profile(t_s: float, contract: Mapping[str, Any]) -> np.ndarray:
    time = _finite_float(t_s, "EFFORT_TIME")
    cfg = contract["effort_profile"]
    duration = float(cfg["duration_s"])
    if time < -1.0e-15 or time > duration + 1.0e-15:
        raise ContractError("EFFORT_TIME_OUTSIDE_CONTRACT")
    amplitude = finite_vector(cfg["amplitude_mixed_Nm_N"], 8, "EFFORT_AMPLITUDE")
    return amplitude * math.sin(math.pi * min(duration, max(0.0, time)) / duration) ** 2


@dataclass
class PlantKernel:
    model: Any
    contract: Mapping[str, Any]
    lane: str
    effort_function: Callable[[float], np.ndarray]

    def effective_state(self, q: np.ndarray, dq: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        if self.lane == "ACTUATED_8DOF":
            return q, dq
        if self.lane != "LOCKED_2P_6R_PULSE":
            raise ContractError(f"UNKNOWN_LANE:{self.lane}")
        locked = self.contract["lanes"]["LOCKED_2P_6R_PULSE"]
        q_effective = q.copy()
        dq_effective = dq.copy()
        q_effective[6:] = finite_vector(locked["qP_star_m"], 2, "qP_STAR")
        dq_effective[6:] = 0.0
        return q_effective, dq_effective

    def acceleration(self, t_s: float, q: np.ndarray, dq: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        tau = finite_vector(self.effort_function(float(t_s)), 8, "EFFORT")
        q_effective, dq_effective = self.effective_state(q, dq)
        if self.lane == "ACTUATED_8DOF":
            ddq = np.asarray(
                self.model.actuated_acceleration(q_effective, dq_effective, tau)["acceleration"],
                dtype=float,
            )
            return ddq, tau
        if not np.array_equal(tau[6:], np.zeros(2)):
            raise ContractError("LOCKED_LANE_PRISMATIC_EFFORT_MUST_BE_ZERO")
        result = self.model.locked_acceleration(
            q_effective[:6], dq_effective[:6], tau[:6], tau[6:]
        )
        ddq = np.asarray(result["kkt_acceleration"], dtype=float)
        ddq[6:] = 0.0
        return ddq, tau

    def rhs(self, t_s: float, augmented_state: np.ndarray) -> np.ndarray:
        state = np.asarray(augmented_state, dtype=float)
        if state.shape != (24,) or not np.all(np.isfinite(state)):
            raise ContractError("AUGMENTED_STATE_MUST_HAVE_24_FINITE_VALUES")
        position = state[0:3]
        quaternion = quat_normalize(state[3:7])
        q = state[7:15]
        dq = state[15:23]
        q_effective, dq_effective = self.effective_state(q, dq)
        ddq, tau = self.acceleration(t_s, q_effective, dq_effective)
        base_twist = np.asarray(self.model.backend.mechanical_connection(q_effective), dtype=float) @ dq_effective
        rotation = quat_rotation_body_to_inertial(quaternion)
        position_rate = rotation @ base_twist[:3]
        quaternion_rate = 0.5 * quat_product(quaternion, np.asarray([0.0, *base_twist[3:]]))
        q_rate = dq_effective.copy()
        if self.lane == "LOCKED_2P_6R_PULSE":
            q_rate[6:] = 0.0
        work_rate = float(tau @ dq_effective)
        return np.concatenate((position_rate, quaternion_rate, q_rate, ddq, [work_rate]))

    def project(self, state: np.ndarray) -> np.ndarray:
        result = np.asarray(state, dtype=float).copy()
        result[3:7] = quat_normalize(result[3:7])
        if self.lane == "LOCKED_2P_6R_PULSE":
            result[13:15] = finite_vector(
                self.contract["lanes"]["LOCKED_2P_6R_PULSE"]["qP_star_m"], 2, "qP_STAR"
            )
            result[21:23] = 0.0
        return result


def initial_augmented_state(contract: Mapping[str, Any], lane: str) -> np.ndarray:
    cfg = contract["initial_state"]
    state = np.concatenate(
        (
            finite_vector(cfg["base_position_inertial_initial_m"], 3, "r0"),
            quat_normalize(cfg["base_quaternion_body_to_inertial_initial_wxyz"]),
            finite_vector(cfg["q0_mixed_rad_m"], 8, "q0"),
            finite_vector(cfg["qdot0_mixed_rad_s_m_s"], 8, "dq0"),
            np.zeros(1),
        )
    )
    if lane == "LOCKED_2P_6R_PULSE":
        state[13:15] = finite_vector(contract["lanes"][lane]["qP_star_m"], 2, "qP_STAR")
        state[21:23] = 0.0
    elif lane != "ACTUATED_8DOF":
        raise ContractError(f"UNKNOWN_LANE:{lane}")
    return state


def integrate_rk4(kernel: PlantKernel, times: np.ndarray, initial: np.ndarray) -> np.ndarray:
    if times.ndim != 1 or len(times) < 2 or not np.all(np.diff(times) > 0.0):
        raise ContractError("RK4_TIME_GRID_INVALID")
    state = kernel.project(initial)
    history = [state.copy()]
    for left, right in zip(times[:-1], times[1:]):
        step = float(right - left)
        k1 = kernel.rhs(float(left), state)
        k2 = kernel.rhs(float(left + 0.5 * step), state + 0.5 * step * k1)
        k3 = kernel.rhs(float(left + 0.5 * step), state + 0.5 * step * k2)
        k4 = kernel.rhs(float(right), state + step * k3)
        state = kernel.project(state + (step / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4))
        history.append(state.copy())
    return np.stack(history)


def integrate_dop853(kernel: PlantKernel, times: np.ndarray, initial: np.ndarray) -> np.ndarray:
    cfg = kernel.contract["solver_contract"]
    solution = solve_ivp(
        kernel.rhs,
        (float(times[0]), float(times[-1])),
        kernel.project(initial),
        method="DOP853",
        t_eval=times,
        rtol=float(cfg["cross_rtol"]),
        atol=float(cfg["cross_atol"]),
        max_step=float(cfg["cross_max_step_s"]),
    )
    if not solution.success or solution.y.shape != (24, len(times)):
        raise ContractError(f"DOP853_FAILED:{solution.message}")
    history = solution.y.T.copy()
    for index in range(len(history)):
        history[index] = kernel.project(history[index])
    return history


def time_grid(contract: Mapping[str, Any], duration_s: float | None = None, step_s: float | None = None) -> np.ndarray:
    cfg = contract["effort_profile"]
    duration = float(cfg["duration_s"] if duration_s is None else duration_s)
    step = float(cfg["fixed_step_s"] if step_s is None else step_s)
    if not math.isfinite(duration) or not math.isfinite(step) or duration <= 0.0 or step <= 0.0:
        raise ContractError("TIME_GRID_PARAMETERS_INVALID")
    steps_float = duration / step
    steps = int(round(steps_float))
    _require(steps >= 1 and abs(steps_float - steps) <= 1.0e-12, "TIME_GRID_NOT_INTEGRAL")
    return np.linspace(0.0, duration, steps + 1)


def run_lane(model: Any, contract: Mapping[str, Any], lane: str, *, effort_fn: Callable[[float], np.ndarray] | None = None) -> dict[str, Any]:
    if effort_fn is not None:
        profile = effort_fn
    elif lane == "LOCKED_2P_6R_PULSE":
        def profile(time: float) -> np.ndarray:
            value = effort_profile(time, contract).copy()
            value[6:] = 0.0
            return value
    else:
        profile = lambda time: effort_profile(time, contract)
    kernel = PlantKernel(model=model, contract=contract, lane=lane, effort_function=profile)
    times = time_grid(contract)
    initial = initial_augmented_state(contract, lane)
    rk4 = integrate_rk4(kernel, times, initial)
    dop853 = integrate_dop853(kernel, times, initial)
    return {"lane": lane, "time_s": times, "rk4": rk4, "dop853": dop853, "kernel": kernel}


def _body_momentum_inertial(tree: Any, q: np.ndarray, dq: np.ndarray, base_twist: np.ndarray, position: np.ndarray, quaternion: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    rotation = quat_rotation_body_to_inertial(quaternion)
    generalized_velocity = np.concatenate((base_twist, dq))
    linear = np.zeros(3)
    angular = np.zeros(3)
    for body in tree.body_kinematics(q):
        velocity_root = body.linear_jacobian @ generalized_velocity
        omega_root = body.angular_jacobian @ generalized_velocity
        position_inertial = position + rotation @ body.com_root_m
        velocity_inertial = rotation @ velocity_root
        omega_inertial = rotation @ omega_root
        inertia_inertial = rotation @ body.inertia_root_kg_m2 @ rotation.T
        body_linear = body.mass_kg * velocity_inertial
        linear += body_linear
        angular += inertia_inertial @ omega_inertial + np.cross(position_inertial, body_linear)
    return linear, angular


def _matrix_momentum_inertial(tree: Any, q: np.ndarray, dq: np.ndarray, base_twist: np.ndarray, position: np.ndarray, quaternion: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    root_momentum = tree.mass_matrix(q) @ np.concatenate((base_twist, dq))
    rotation = quat_rotation_body_to_inertial(quaternion)
    linear = rotation @ root_momentum[:3]
    angular = rotation @ root_momentum[3:6] + np.cross(position, linear)
    return linear, angular


def audit_history(model: Any, contract: Mapping[str, Any], lane: str, times: np.ndarray, history: np.ndarray) -> dict[str, Any]:
    thresholds = contract["thresholds"]
    lower = finite_vector(contract["model_contract"]["joint_lower_mixed_rad_m"], 8, "LOWER")
    upper = finite_vector(contract["model_contract"]["joint_upper_mixed_rad_m"], 8, "UPPER")
    scales = finite_vector(contract["model_contract"]["reference_scales_mixed_rad_m"], 8, "SCALES")
    scale_matrix = np.diag(scales)
    energy: list[float] = []
    work = history[:, 23].copy()
    base_twists: list[np.ndarray] = []
    p_body_norm: list[float] = []
    h_body_norm: list[float] = []
    p_matrix_norm: list[float] = []
    h_matrix_norm: list[float] = []
    p_cross: list[float] = []
    h_cross: list[float] = []
    connection_linear: list[float] = []
    connection_angular: list[float] = []
    quat_error: list[float] = []
    mass_rr: list[float] = []
    mass_rp: list[float] = []
    mass_pp: list[float] = []
    scaled_condition: list[float] = []
    cholesky_ok: list[bool] = []
    qR_margin: list[float] = []
    qP_margin: list[float] = []
    for state in history:
        position = state[:3]
        quaternion = state[3:7]
        q = state[7:15].copy()
        dq = state[15:23].copy()
        if lane == "LOCKED_2P_6R_PULSE":
            q[6:] = contract["lanes"][lane]["qP_star_m"]
            dq[6:] = 0.0
        base_twist = np.asarray(model.backend.mechanical_connection(q), dtype=float) @ dq
        base_twists.append(base_twist)
        matrix = np.asarray(model.mass(q), dtype=float)
        mass_rr.append(float(np.max(np.abs(matrix[:6, :6] - matrix[:6, :6].T))))
        mass_rp.append(float(np.max(np.abs(matrix[:6, 6:] - matrix[6:, :6].T))))
        mass_pp.append(float(np.max(np.abs(matrix[6:, 6:] - matrix[6:, 6:].T))))
        scaled = scale_matrix.T @ matrix @ scale_matrix
        try:
            np.linalg.cholesky(scaled)
            cholesky_ok.append(True)
        except np.linalg.LinAlgError:
            cholesky_ok.append(False)
        scaled_condition.append(float(np.linalg.cond(scaled)))
        body_p, body_h = _body_momentum_inertial(
            model.backend.tree, q, dq, base_twist, position, quaternion
        )
        matrix_p, matrix_h = _matrix_momentum_inertial(
            model.backend.tree, q, dq, base_twist, position, quaternion
        )
        p_body_norm.append(float(np.linalg.norm(body_p)))
        h_body_norm.append(float(np.linalg.norm(body_h)))
        p_matrix_norm.append(float(np.linalg.norm(matrix_p)))
        h_matrix_norm.append(float(np.linalg.norm(matrix_h)))
        p_cross.append(float(np.linalg.norm(body_p - matrix_p)))
        h_cross.append(float(np.linalg.norm(body_h - matrix_h)))
        blocks = model.backend.tree.mass_matrix_blocks(q)
        closure = blocks.Hbb @ base_twist + blocks.Hbm @ dq
        connection_linear.append(float(np.linalg.norm(closure[:3])))
        connection_angular.append(float(np.linalg.norm(closure[3:])))
        energy.append(float(model.backend.tree.kinetic_energy_j(q, base_twist, dq)))
        quat_error.append(abs(float(np.linalg.norm(quaternion)) - 1.0))
        qR_margin.append(float(np.min(np.minimum(q[:6] - lower[:6], upper[:6] - q[:6]))))
        qP_margin.append(float(np.min(np.minimum(q[6:] - lower[6:], upper[6:] - q[6:]))))
    energy_array = np.asarray(energy)
    energy_change = energy_array - energy_array[0]
    work_energy = energy_change - work
    pointwise_relative = np.zeros_like(work_energy)
    denominator = np.maximum.reduce((np.abs(energy_change), np.abs(work), np.full_like(work, 1.0e-15)))
    pointwise_relative[1:] = np.abs(work_energy[1:]) / denominator[1:]
    global_relative = float(
        np.max(np.abs(work_energy))
        / max(float(np.max(np.abs(energy_change))), float(np.max(np.abs(work))), 1.0e-15)
    )
    return {
        "lane": lane,
        "samples": len(times),
        "integrated_physical_state_dimension": 23,
        "auxiliary_work_state_dimension_no_physical_credit": 1,
        "derived_base_twist_dimension": 6,
        "base_twist_body_history_mixed_m_s_rad_s": np.asarray(base_twists),
        "kinetic_energy_history_J": energy_array,
        "work_history_J": work,
        "max_work_energy_absolute_J": float(np.max(np.abs(work_energy))),
        "max_work_energy_relative": global_relative,
        "max_pointwise_relative_near_zero_diagnostic_no_gate_credit": float(
            np.max(pointwise_relative)
        ),
        "max_linear_momentum_body_inertial_kg_m_s": max(p_body_norm),
        "max_angular_momentum_body_inertial_kg_m2_s": max(h_body_norm),
        "max_linear_momentum_matrix_inertial_kg_m_s": max(p_matrix_norm),
        "max_angular_momentum_matrix_inertial_kg_m2_s": max(h_matrix_norm),
        "max_matrix_vs_body_linear_kg_m_s": max(p_cross),
        "max_matrix_vs_body_angular_kg_m2_s": max(h_cross),
        "max_connection_linear_residual_kg_m_s": max(connection_linear),
        "max_connection_angular_residual_kg_m2_s": max(connection_angular),
        "max_quaternion_norm_error": max(quat_error),
        "mass_symmetry_RR_max_abs_kg_m2": max(mass_rr),
        "mass_symmetry_RP_max_abs_kg_m": max(mass_rp),
        "mass_symmetry_PP_max_abs_kg": max(mass_pp),
        "reference_scaled_cholesky_all_pass": all(cholesky_ok),
        "reference_scaled_condition_number_max_diagnostic_no_gate_credit": max(scaled_condition),
        "revolute_joint_limit_min_margin_rad": min(qR_margin),
        "prismatic_joint_limit_min_margin_m": min(qP_margin),
        "finite_history": bool(np.all(np.isfinite(history))),
        "thresholds_repeated_for_local_audit": {
            "work_energy_absolute_max_J": thresholds["work_energy_absolute_max_J"],
            "work_energy_relative_max": thresholds["work_energy_relative_max"],
        },
    }


def solver_cross_audit(run: Mapping[str, Any], model: Any, contract: Mapping[str, Any]) -> dict[str, float]:
    left = np.asarray(run["rk4"])
    right = np.asarray(run["dop853"])
    q_error = np.abs(left[:, 7:15] - right[:, 7:15])
    dq_error = np.abs(left[:, 15:23] - right[:, 15:23])
    attitude = [attitude_distance_rad(a[3:7], b[3:7]) for a, b in zip(left, right)]
    v_linear: list[float] = []
    v_angular: list[float] = []
    for a, b in zip(left, right):
        va = np.asarray(model.backend.mechanical_connection(a[7:15])) @ a[15:23]
        vb = np.asarray(model.backend.mechanical_connection(b[7:15])) @ b[15:23]
        v_linear.append(float(np.max(np.abs(va[:3] - vb[:3]))))
        v_angular.append(float(np.max(np.abs(va[3:] - vb[3:]))))
    return {
        "qR_max_abs_rad": float(np.max(q_error[:, :6])),
        "qP_max_abs_m": float(np.max(q_error[:, 6:])),
        "dqR_max_abs_rad_s": float(np.max(dq_error[:, :6])),
        "dqP_max_abs_m_s": float(np.max(dq_error[:, 6:])),
        "base_position_max_abs_m": float(np.max(np.abs(left[:, :3] - right[:, :3]))),
        "base_attitude_max_rad": max(attitude),
        "base_linear_twist_max_abs_m_s": max(v_linear),
        "base_angular_twist_max_abs_rad_s": max(v_angular),
    }


def independent_christoffel_bias(derivatives: np.ndarray, dq: np.ndarray) -> np.ndarray:
    result = np.zeros(8)
    for i in range(8):
        for j in range(8):
            for k in range(8):
                gamma = 0.5 * (
                    derivatives[k, i, j]
                    + derivatives[j, i, k]
                    - derivatives[i, j, k]
                )
                result[i] += gamma * dq[j] * dq[k]
    return result


def bias_cross_audit(model: Any, contract: Mapping[str, Any]) -> dict[str, Any]:
    q = finite_vector(contract["initial_state"]["q0_mixed_rad_m"], 8, "q0")
    dq = finite_vector(contract["initial_state"]["qdot0_mixed_rad_s_m_s"], 8, "dq0")
    derivatives = np.asarray(model.mass_derivatives(q), dtype=float)
    reference = np.asarray(model.bias(q, dq), dtype=float)
    independent = independent_christoffel_bias(derivatives, dq)
    difference = np.abs(reference - independent)
    return {
        "parent_bias_mixed_Nm_N": reference,
        "independent_christoffel_bias_mixed_Nm_N": independent,
        "revolute_max_abs_Nm": float(np.max(difference[:6])),
        "prismatic_max_abs_N": float(np.max(difference[6:])),
        "derivative_method": "INDEPENDENT_EXPLICIT_CHRISTOFFEL_LOOP_OVER_PARENT_RICHARDSON_MASS_DERIVATIVES",
    }


def locked_kkt_audit(model: Any, contract: Mapping[str, Any], times: np.ndarray, history: np.ndarray) -> dict[str, Any]:
    eq_r: list[float] = []
    eq_p: list[float] = []
    constraint: list[float] = []
    accel_r: list[float] = []
    accel_p: list[float] = []
    reaction_cross: list[float] = []
    reaction_power: list[float] = []
    for time, state in zip(times, history):
        q = state[7:15]
        dq = state[15:23]
        tau = effort_profile(float(time), contract).copy()
        tau[6:] = 0.0
        result = model.locked_acceleration(q[:6], dq[:6], tau[:6], tau[6:])
        equilibrium = np.abs(result["kkt_equilibrium_residual"])
        eq_r.append(float(np.max(equilibrium[:6])))
        eq_p.append(float(np.max(equilibrium[6:])))
        constraint.append(float(np.max(np.abs(result["constraint_acceleration"]))))
        accel_r.append(float(result["acceleration_cross_revolute_max_abs_rad_s2"]))
        accel_p.append(float(result["acceleration_cross_prismatic_max_abs_m_s2"]))
        reaction_cross.append(float(result["reaction_cross_max_abs_N"]))
        reaction_power.append(float(abs(np.asarray(result["kkt_reaction_N"]) @ dq[6:])))
    q0 = history[0, 7:15]
    dq0 = history[0, 15:23]
    tau0 = effort_profile(float(times[len(times) // 2]), contract)
    free = model.actuated_acceleration(q0, dq0, np.concatenate((tau0[:6], np.zeros(2))))
    return {
        "max_kkt_equilibrium_R_abs_Nm": max(eq_r),
        "max_kkt_equilibrium_P_abs_N": max(eq_p),
        "max_constraint_acceleration_abs_m_s2": max(constraint),
        "max_kkt_vs_elimination_acceleration_R_abs_rad_s2": max(accel_r),
        "max_kkt_vs_elimination_acceleration_P_abs_m_s2": max(accel_p),
        "max_reaction_cross_abs_N": max(reaction_cross),
        "max_reaction_power_abs_W": max(reaction_power),
        "tauP_zero_free_prismatic_acceleration_max_abs_m_s2": float(
            np.max(np.abs(free["acceleration"][6:]))
        ),
        "reaction_is_constraint_force_not_contact_force": True,
    }


def coordinate_scale_audit(model: Any, contract: Mapping[str, Any]) -> dict[str, Any]:
    q = finite_vector(contract["initial_state"]["q0_mixed_rad_m"], 8, "q0")
    dq = finite_vector(contract["initial_state"]["qdot0_mixed_rad_s_m_s"], 8, "dq0")
    tau = 0.37 * finite_vector(contract["effort_profile"]["amplitude_mixed_Nm_N"], 8, "TAU")
    scales = finite_vector(contract["model_contract"]["reference_scales_mixed_rad_m"], 8, "SCALES")
    S = np.diag(scales)
    Sinv = np.diag(1.0 / scales)
    mass = np.asarray(model.mass(q), dtype=float)
    bias = np.asarray(model.bias(q, dq), dtype=float)
    native_acceleration = np.linalg.solve(mass, tau - bias)
    dx = Sinv @ dq
    transformed_mass = S.T @ mass @ S
    transformed_bias = S.T @ bias
    transformed_tau = S.T @ tau
    transformed_acceleration = np.linalg.solve(transformed_mass, transformed_tau - transformed_bias)
    recovered = S @ transformed_acceleration
    native_energy = float(0.5 * dq @ mass @ dq)
    transformed_energy = float(0.5 * dx @ transformed_mass @ dx)
    native_power = float(tau @ dq)
    transformed_power = float(transformed_tau @ dx)
    energy_relative = abs(native_energy - transformed_energy) / max(abs(native_energy), 1.0e-15)
    power_relative = abs(native_power - transformed_power) / max(abs(native_power), 1.0e-15)
    return {
        "reference_scales_mixed_rad_m": scales,
        "revolute_acceleration_max_abs_rad_s2": float(np.max(np.abs(recovered[:6] - native_acceleration[:6]))),
        "prismatic_acceleration_max_abs_m_s2": float(np.max(np.abs(recovered[6:] - native_acceleration[6:]))),
        "energy_relative": float(energy_relative),
        "power_relative": float(power_relative),
        "raw_mixed_unit_spectrum_or_condition_used_for_credit": False,
    }


def zero_effort_audit(model: Any, contract: Mapping[str, Any]) -> dict[str, Any]:
    zero = lambda _time: np.zeros(8)
    kernel = PlantKernel(model, contract, "ACTUATED_8DOF", zero)
    times = time_grid(contract)
    history = integrate_rk4(kernel, times, initial_augmented_state(contract, "ACTUATED_8DOF"))
    audit = audit_history(model, contract, "ACTUATED_8DOF", times, history)
    energy = np.asarray(audit["kinetic_energy_history_J"])
    relative = float(np.max(np.abs(energy - energy[0])) / max(abs(energy[0]), 1.0e-15))
    return {
        "max_kinetic_energy_relative_drift": relative,
        "max_linear_momentum_body_inertial_kg_m_s": audit["max_linear_momentum_body_inertial_kg_m_s"],
        "max_angular_momentum_body_inertial_kg_m2_s": audit["max_angular_momentum_body_inertial_kg_m2_s"],
        "effort_exactly_zero": True,
    }


def constant_backend_regression(parent: Any, model: Any, contract: Mapping[str, Any]) -> dict[str, Any]:
    cfg = contract["lanes"]["CONSTANT_EFFORT_BACKEND_REGRESSION"]
    duration = float(cfg["duration_s"])
    step = float(cfg["fixed_step_s"])
    times = time_grid(contract, duration_s=duration, step_s=step)
    amplitude = finite_vector(contract["effort_profile"]["amplitude_mixed_Nm_N"], 8, "AMPLITUDE")
    constant = lambda _time: amplitude.copy()
    kernel = PlantKernel(model, contract, "ACTUATED_8DOF", constant)
    initial = initial_augmented_state(contract, "ACTUATED_8DOF")
    ours = integrate_rk4(kernel, times, initial)[-1]
    q0 = initial[7:15]
    dq0 = initial[15:23]
    position0 = initial[:3]
    quaternion0 = initial[3:7]
    base_twist0 = np.asarray(model.backend.mechanical_connection(q0)) @ dq0
    ee0 = model.backend.ee_centroid_inertial(q0, position0, quaternion0)
    default = model.backend.initial_state()
    state_class = type(default)
    valid_state = state_class(
        tuple(q0),
        tuple(dq0),
        tuple(position0),
        tuple(quaternion0),
        tuple(base_twist0),
        tuple(ee0),
        "READY_VALID_CURRENT_R2_REGRESSION",
    )
    after, assessment, backend_audit = model.backend.advance(
        valid_state,
        generalized_effort=amplitude,
        step_s=step,
        steps=len(times) - 1,
    )
    q_backend = np.asarray(after.q_mixed_rad_m)
    dq_backend = np.asarray(after.qdot_mixed_rad_s_m_s)
    return {
        "valid_state_used_instead_of_backend_default": True,
        "backend_physical_state_changed": assessment["physical_state_changed"],
        "backend_momentum_conserved_within_limit": backend_audit["momentum_conserved_within_limit"],
        "qR_max_abs_rad": float(np.max(np.abs(ours[7:13] - q_backend[:6]))),
        "qP_max_abs_m": float(np.max(np.abs(ours[13:15] - q_backend[6:]))),
        "dqR_max_abs_rad_s": float(np.max(np.abs(ours[15:21] - dq_backend[:6]))),
        "dqP_max_abs_m_s": float(np.max(np.abs(ours[21:23] - dq_backend[6:]))),
        "base_position_max_abs_m": float(np.max(np.abs(ours[:3] - np.asarray(after.base_position_inertial_m)))),
        "base_attitude_max_rad": attitude_distance_rad(ours[3:7], after.base_quaternion_body_to_inertial_wxyz),
    }


def backend_default_audit(model: Any, contract: Mapping[str, Any]) -> dict[str, Any]:
    default = model.backend.initial_state()
    q = np.asarray(default.q_mixed_rad_m)
    names = contract["model_contract"]["joint_order"]
    lower = np.asarray(contract["model_contract"]["joint_lower_mixed_rad_m"])
    upper = np.asarray(contract["model_contract"]["joint_upper_mixed_rad_m"])
    violation_indices = np.flatnonzero((q < lower) | (q > upper))
    rejected = False
    reason = None
    try:
        validate_physical_state(
            default.base_position_inertial_m,
            default.base_quaternion_body_to_inertial_wxyz,
            default.q_mixed_rad_m,
            default.qdot_mixed_rad_s_m_s,
            contract,
        )
    except ContractError as exc:
        rejected = True
        reason = str(exc)
    expected_name = contract["initial_state"]["required_backend_default_invalid_joint"]
    expected_value = float(contract["initial_state"]["required_backend_default_invalid_value_m"])
    expected_index = names.index(expected_name)
    return {
        "backend_default_accepted_for_execution": False,
        "validation_rejected": rejected,
        "reason": reason,
        "violating_joints": [names[index] for index in violation_indices],
        "required_invalid_joint_detected": expected_index in violation_indices,
        "required_invalid_value_exact": float(q[expected_index]) == expected_value,
        "replacement_qP_m": contract["initial_state"]["q0_mixed_rad_m"][6:],
    }


def topology_audit(model: Any, contract: Mapping[str, Any], urdf: Mapping[str, Any]) -> dict[str, Any]:
    summary = model.backend.tree.model_summary()
    expected = contract["model_contract"]
    checks = {
        "urdf_links_exact": urdf["links"] == expected["expected_links"],
        "urdf_joints_exact": urdf["joints"] == expected["expected_joints"],
        "backend_physical_links_exact": summary["physical_links"] == expected["expected_physical_links"],
        "backend_frame_only_links_exact": summary["frame_only_links"] == expected["expected_frame_only_links"],
        "backend_movable_dof_exact": summary["movable_dof"] == expected["expected_movable_dof"],
        "backend_joint_order_exact": summary["movable_joint_names"] == expected["joint_order"],
        "backend_total_mass_exact_kg": float(summary["total_mass_kg"]) == float(expected["expected_total_mass_kg"]),
    }
    return {"backend_summary": summary, "checks": checks, "all_match": all(checks.values())}


def effort_profile_audit(contract: Mapping[str, Any]) -> dict[str, Any]:
    duration = float(contract["effort_profile"]["duration_s"])
    amplitude = np.asarray(contract["effort_profile"]["amplitude_mixed_Nm_N"])
    start = effort_profile(0.0, contract)
    middle = effort_profile(0.5 * duration, contract)
    end = effort_profile(duration, contract)
    return {
        "start_exact_zero": np.array_equal(start, np.zeros(8)),
        "midpoint_exact_amplitude": np.array_equal(middle, amplitude),
        "end_max_abs_mixed_Nm_N": float(np.max(np.abs(end))),
        "end_within_machine_roundoff": float(np.max(np.abs(end))) <= np.finfo(float).eps * max(1.0, float(np.max(np.abs(amplitude)))),
        "hardware_limit_enforcement": False,
    }


def run_negative_controls(contract: Mapping[str, Any], source_pins: Mapping[str, Any], model: Any) -> dict[str, Any]:
    records: list[dict[str, Any]] = []

    def expect(identifier: str, function: Callable[[], Any], token: str) -> None:
        caught = False
        message = "NO_EXCEPTION"
        try:
            function()
        except Exception as exc:  # deliberately audits the public fail-closed surface
            message = str(exc)
            caught = token in message
        records.append({"id": identifier, "expected_token": token, "observed": message, "pass": caught})

    expect("NC01_DUPLICATE_JSON_KEY", lambda: loads_json_strict('{"a":1,"a":2}'), "DUPLICATE_JSON_KEY_REJECTED")
    expect("NC02_JSON_NAN", lambda: loads_json_strict('{"a":NaN}'), "NONFINITE_JSON_CONSTANT_REJECTED")
    expect("NC03_JSON_INFINITY", lambda: loads_json_strict('{"a":Infinity}'), "NONFINITE_JSON_CONSTANT_REJECTED")
    mutated = copy.deepcopy(contract)
    mutated["model_contract"]["integrated_state_dimension"] = 24
    expect("NC04_STATE_DIMENSION_MUTATION", lambda: validate_contract_semantics(mutated), "STATE_DIMENSION_MISMATCH")
    mutated = copy.deepcopy(contract)
    mutated["model_contract"]["coordinate_units"][-1] = "rad"
    expect("NC05_UNIT_DOMAIN_MUTATION", lambda: validate_contract_semantics(mutated), "COORDINATE_UNITS_NOT_SEPARATED")
    mutated = copy.deepcopy(contract)
    mutated["execution_guards"]["contact_called"] = True
    expect("NC06_CONTACT_GUARD_ESCALATION", lambda: validate_contract_semantics(mutated), "EXECUTION_GUARD_TRUE")
    mutated = copy.deepcopy(contract)
    mutated["release_boundary"]["next_stage_authorized"] = True
    expect("NC07_RELEASE_ESCALATION", lambda: validate_contract_semantics(mutated), "RELEASE_BOUNDARY_ESCALATED")
    mutated = copy.deepcopy(contract)
    mutated["lanes"]["LOCKED_2P_6R_PULSE"]["tauP_N"] = [0.01, 0.0]
    expect("NC08_LOCKED_TAUP_MUTATION", lambda: validate_contract_semantics(mutated), "LOCKED_tauP_NONZERO")
    default = model.backend.initial_state()
    expect(
        "NC09_BACKEND_DEFAULT_INVALID_QP",
        lambda: validate_physical_state(default.base_position_inertial_m, default.base_quaternion_body_to_inertial_wxyz, default.q_mixed_rad_m, default.qdot_mixed_rad_s_m_s, contract),
        "JOINT_POSITION_LIMIT_VIOLATION",
    )
    bad_q = np.asarray(contract["initial_state"]["q0_mixed_rad_m"], dtype=float)
    bad_q[0] = 2.8001
    expect(
        "NC10_UPPER_JOINT_LIMIT",
        lambda: validate_physical_state([0, 0, 0], [1, 0, 0, 0], bad_q, np.zeros(8), contract),
        "JOINT_POSITION_LIMIT_VIOLATION:joint1",
    )
    expect("NC11_ZERO_QUATERNION", lambda: quat_normalize([0, 0, 0, 0]), "QUATERNION_ZERO_NORM")
    expect("NC12_NONZERO_TOTAL_MOMENTUM", lambda: reject_nonzero_total_momentum([1e-12, 0, 0, 0, 0, 0]), "NONZERO_TOTAL_MOMENTUM_UNSUPPORTED")
    expect("NC13_NONFINITE_EFFORT", lambda: finite_vector([0, 0, 0, 0, 0, 0, 0, math.nan], 8, "EFFORT"), "EFFORT_MUST_HAVE_8_FINITE_VALUES")
    expect("NC14_NEGATIVE_TIME_STEP", lambda: time_grid(contract, duration_s=0.01, step_s=-0.001), "TIME_GRID_PARAMETERS_INVALID")
    bad_kernel = PlantKernel(model, contract, "LOCKED_2P_6R_PULSE", lambda _time: np.asarray([0, 0, 0, 0, 0, 0, 1e-3, 0]))
    state = initial_augmented_state(contract, "LOCKED_2P_6R_PULSE")
    expect("NC15_LOCKED_RUNTIME_TAUP", lambda: bad_kernel.rhs(0.0, state), "LOCKED_LANE_PRISMATIC_EFFORT_MUST_BE_ZERO")
    mutated = copy.deepcopy(contract)
    mutated["source_pins"][0]["sha256"] = "0" * 64
    expect("NC16_SOURCE_HASH_MUTATION", lambda: validate_source_pins(mutated), "SOURCE_PIN_DRIFT:unified_r2_urdf")
    mutated = copy.deepcopy(contract)
    mutated["solver_contract"]["cross_rtol"] = -1.0
    expect("NC17_DOP853_TOLERANCE_MUTATION", lambda: validate_contract_semantics(mutated), "DOP853_RTOL_INVALID")
    mutated = copy.deepcopy(contract)
    mutated["source_pins"][0]["path"] = "30_simulation/does_not_exist.urdf"
    expect("NC18_SOURCE_PATH_MUTATION", lambda: validate_source_pins(mutated), "SOURCE_PIN_MISSING:unified_r2_urdf")
    mutated = copy.deepcopy(contract)
    mutated["source_pins"][-1]["sha256"] = "0" * 64
    expect(
        "NC19_TRANSITIVE_RUNTIME_HASH_MUTATION",
        lambda: validate_source_pins(mutated),
        "SOURCE_PIN_DRIFT:sim13_v2_backends_canonical",
    )
    mutated = copy.deepcopy(contract)
    mutated["runtime_project_module_binding"]["transitive_pinned_module_ids"].pop()
    expect(
        "NC20_TRANSITIVE_RUNTIME_BINDING_MUTATION",
        lambda: validate_contract_semantics(mutated),
        "TRANSITIVE_RUNTIME_PIN_SET_MISMATCH",
    )
    return {
        "records": records,
        "count": len(records),
        "passed": sum(record["pass"] for record in records),
        "all_pass": all(record["pass"] for record in records),
        "minimum_required": 12,
        "source_pin_baseline_all_match": source_pins["all_match"],
    }


def _maximum(records: Sequence[Mapping[str, Any]], field: str) -> float:
    return max(float(record[field]) for record in records)


def _lane_passes_history(audit: Mapping[str, Any], thresholds: Mapping[str, Any]) -> dict[str, bool]:
    return {
        "finite_and_within_limits": audit["finite_history"]
        and audit["revolute_joint_limit_min_margin_rad"] >= thresholds["joint_limit_min_margin_mixed_rad_m"]
        and audit["prismatic_joint_limit_min_margin_m"] >= thresholds["joint_limit_min_margin_mixed_rad_m"],
        "mass": audit["mass_symmetry_RR_max_abs_kg_m2"] <= thresholds["mass_symmetry_RR_max_abs_kg_m2"]
        and audit["mass_symmetry_RP_max_abs_kg_m"] <= thresholds["mass_symmetry_RP_max_abs_kg_m"]
        and audit["mass_symmetry_PP_max_abs_kg"] <= thresholds["mass_symmetry_PP_max_abs_kg"]
        and audit["reference_scaled_cholesky_all_pass"],
        "linear_momentum": audit["max_linear_momentum_body_inertial_kg_m_s"] <= thresholds["linear_momentum_residual_max_kg_m_s"],
        "angular_momentum": audit["max_angular_momentum_body_inertial_kg_m2_s"] <= thresholds["angular_momentum_residual_max_kg_m2_s"],
        "matrix_body": audit["max_matrix_vs_body_linear_kg_m_s"] <= thresholds["matrix_vs_body_linear_max_kg_m_s"]
        and audit["max_matrix_vs_body_angular_kg_m2_s"] <= thresholds["matrix_vs_body_angular_max_kg_m2_s"],
        "work_energy": audit["max_work_energy_absolute_J"] <= thresholds["work_energy_absolute_max_J"]
        and audit["max_work_energy_relative"] <= thresholds["work_energy_relative_max"],
        "connection": audit["max_connection_linear_residual_kg_m_s"] <= thresholds["connection_linear_residual_max_kg_m_s"]
        and audit["max_connection_angular_residual_kg_m2_s"] <= thresholds["connection_angular_residual_max_kg_m2_s"],
        "quaternion": audit["max_quaternion_norm_error"] <= thresholds["quaternion_norm_error_max"],
    }


def build_candidate(project_root: Path = PROJECT_ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    contract = load_contract()
    source_pins = validate_source_pins(contract, project_root)
    parent = _load_parent_module(project_root)
    backend = parent.load_backend(project_root)
    runtime_modules = audit_runtime_project_modules(contract, project_root)
    model = parent.ReducedR2Model(
        backend=backend,
        qP_star_m=np.asarray(contract["lanes"]["LOCKED_2P_6R_PULSE"]["qP_star_m"]),
    )
    urdf = parse_urdf_contract(contract, project_root)
    topology = topology_audit(model, contract, urdf)
    default_audit = backend_default_audit(model, contract)
    initial = contract["initial_state"]
    candidate_state = validate_physical_state(
        initial["base_position_inertial_initial_m"],
        initial["base_quaternion_body_to_inertial_initial_wxyz"],
        initial["q0_mixed_rad_m"],
        initial["qdot0_mixed_rad_s_m_s"],
        contract,
    )
    profile_audit = effort_profile_audit(contract)
    runs = {
        lane: run_lane(model, contract, lane)
        for lane in ("ACTUATED_8DOF", "LOCKED_2P_6R_PULSE")
    }
    lane_evidence: dict[str, Any] = {}
    for lane, run in runs.items():
        rk4_audit = audit_history(model, contract, lane, run["time_s"], run["rk4"])
        dop853_audit = audit_history(model, contract, lane, run["time_s"], run["dop853"])
        lane_evidence[lane] = {
            "time_s": run["time_s"],
            "rk4_physical_state_history_23": run["rk4"][:, :23],
            "rk4_auxiliary_work_history_J": run["rk4"][:, 23],
            "dop853_physical_state_history_23": run["dop853"][:, :23],
            "dop853_auxiliary_work_history_J": run["dop853"][:, 23],
            "rk4_audit": rk4_audit,
            "dop853_audit": dop853_audit,
            "solver_cross": solver_cross_audit(run, model, contract),
        }
    bias = bias_cross_audit(model, contract)
    locked = locked_kkt_audit(
        model,
        contract,
        runs["LOCKED_2P_6R_PULSE"]["time_s"],
        runs["LOCKED_2P_6R_PULSE"]["rk4"],
    )
    scale = coordinate_scale_audit(model, contract)
    zero = zero_effort_audit(model, contract)
    constant = constant_backend_regression(parent, model, contract)
    replay: dict[str, Any] = {}
    for lane in ("ACTUATED_8DOF", "LOCKED_2P_6R_PULSE"):
        kernel = runs[lane]["kernel"]
        repeated = integrate_rk4(
            kernel,
            runs[lane]["time_s"],
            initial_augmented_state(contract, lane),
        )
        first_hash = canonical_sha256(runs[lane]["rk4"])
        second_hash = canonical_sha256(repeated)
        replay[lane] = {
            "first_history_canonical_sha256": first_hash,
            "second_history_canonical_sha256": second_hash,
            "byte_identical_canonical_replay": first_hash == second_hash,
        }
    negative = run_negative_controls(contract, source_pins, model)
    threshold = contract["thresholds"]
    history_audits = [
        lane_evidence[lane][solver + "_audit"]
        for lane in lane_evidence
        for solver in ("rk4", "dop853")
    ]
    history_passes = [_lane_passes_history(item, threshold) for item in history_audits]
    crosses = [lane_evidence[lane]["solver_cross"] for lane in lane_evidence]
    cross_pass = all(
        item["qR_max_abs_rad"] <= threshold["rk4_dop853_qR_max_abs_rad"]
        and item["qP_max_abs_m"] <= threshold["rk4_dop853_qP_max_abs_m"]
        and item["dqR_max_abs_rad_s"] <= threshold["rk4_dop853_dqR_max_abs_rad_s"]
        and item["dqP_max_abs_m_s"] <= threshold["rk4_dop853_dqP_max_abs_m_s"]
        and item["base_position_max_abs_m"] <= threshold["rk4_dop853_base_position_max_abs_m"]
        and item["base_attitude_max_rad"] <= threshold["rk4_dop853_base_attitude_max_rad"]
        and item["base_linear_twist_max_abs_m_s"] <= threshold["rk4_dop853_base_linear_twist_max_abs_m_s"]
        and item["base_angular_twist_max_abs_rad_s"] <= threshold["rk4_dop853_base_angular_twist_max_abs_rad_s"]
        for item in crosses
    )
    q_actuated = runs["ACTUATED_8DOF"]["rk4"][:, 7:15]
    actuated_evolution = {
        "qR_peak_change_rad": float(np.max(np.abs(q_actuated[:, :6] - q_actuated[0, :6]))),
        "qP_peak_change_m": float(np.max(np.abs(q_actuated[:, 6:] - q_actuated[0, 6:]))),
    }
    kkt_pass = (
        locked["max_kkt_equilibrium_R_abs_Nm"] <= threshold["kkt_equilibrium_R_max_abs_Nm"]
        and locked["max_kkt_equilibrium_P_abs_N"] <= threshold["kkt_equilibrium_P_max_abs_N"]
        and locked["max_constraint_acceleration_abs_m_s2"] <= threshold["kkt_constraint_acceleration_max_abs_m_s2"]
        and locked["max_kkt_vs_elimination_acceleration_R_abs_rad_s2"] <= threshold["kkt_equilibrium_R_max_abs_Nm"]
        and locked["max_kkt_vs_elimination_acceleration_P_abs_m_s2"] <= threshold["kkt_constraint_acceleration_max_abs_m_s2"]
        and locked["max_reaction_cross_abs_N"] <= threshold["kkt_reaction_cross_max_abs_N"]
        and locked["max_reaction_power_abs_W"] <= threshold["kkt_reaction_power_max_abs_W"]
    )
    constant_pass = (
        constant["valid_state_used_instead_of_backend_default"]
        and constant["backend_physical_state_changed"]
        and constant["qR_max_abs_rad"] <= threshold["constant_regression_qR_max_abs_rad"]
        and constant["qP_max_abs_m"] <= threshold["constant_regression_qP_max_abs_m"]
        and constant["dqR_max_abs_rad_s"] <= threshold["constant_regression_dqR_max_abs_rad_s"]
        and constant["dqP_max_abs_m_s"] <= threshold["constant_regression_dqP_max_abs_m_s"]
        and constant["base_position_max_abs_m"] <= threshold["constant_regression_base_position_max_abs_m"]
        and constant["base_attitude_max_rad"] <= threshold["constant_regression_base_attitude_max_rad"]
    )
    boundaries = {
        **contract["release_boundary"],
        "contact_called": False,
        "target_attached": False,
        "flex_model_called": False,
        "hardware_actuator_model_used": False,
        "control_loop_used": False,
        "nonzero_total_momentum_used": False,
    }
    check_rows = [
        (
            "G01",
            "SOURCE_PINS_EXACT",
            source_pins["all_match"]
            and runtime_modules["all_project_runtime_modules_pinned_exactly"],
            {
                "matched": len(source_pins["records"]),
                "expected": 19,
                "direct_runtime_modules": runtime_modules["direct_pinned_module_count"],
                "transitive_runtime_modules": runtime_modules[
                    "transitive_pinned_module_count"
                ],
                "runtime_module_set_exact": runtime_modules[
                    "all_project_runtime_modules_pinned_exactly"
                ],
            },
        ),
        ("G02", "UNIFIED_R2_TOPOLOGY_AND_MASS_EXACT", topology["all_match"], topology["checks"]),
        ("G03", "VALID_CANDIDATE_STATE_AND_INVALID_BACKEND_DEFAULT_REJECTED", candidate_state["valid"] and default_audit["validation_rejected"] and default_audit["required_invalid_joint_detected"] and default_audit["required_invalid_value_exact"], default_audit),
        ("G04", "MIXED_COORDINATE_RATE_AND_EFFORT_UNITS_SEPARATED", validate_contract_semantics(contract)["joint_domains_separated"], {"coordinate_units": contract["model_contract"]["coordinate_units"], "effort_units": contract["model_contract"]["effort_units"]}),
        ("G05", "TIME_VARYING_EFFORT_PROFILE_EXACT", profile_audit["start_exact_zero"] and profile_audit["midpoint_exact_amplitude"] and profile_audit["end_within_machine_roundoff"], profile_audit),
        ("G06", "ALL_HISTORIES_FINITE_AND_WITHIN_URDF_LIMITS", all(item["finite_and_within_limits"] for item in history_passes), {"minimum_revolute_margin_rad": min(item["revolute_joint_limit_min_margin_rad"] for item in history_audits), "minimum_prismatic_margin_m": min(item["prismatic_joint_limit_min_margin_m"] for item in history_audits)}),
        ("G07", "REDUCED_MASS_BLOCK_SYMMETRY_AND_REFERENCE_SCALED_SPD", all(item["mass"] for item in history_passes), {"RR_max_abs_kg_m2": _maximum(history_audits, "mass_symmetry_RR_max_abs_kg_m2"), "RP_max_abs_kg_m": _maximum(history_audits, "mass_symmetry_RP_max_abs_kg_m"), "PP_max_abs_kg": _maximum(history_audits, "mass_symmetry_PP_max_abs_kg")}),
        ("G08", "BIAS_EXPLICIT_CHRISTOFFEL_CROSS", bias["revolute_max_abs_Nm"] <= threshold["bias_cross_R_max_abs_Nm"] and bias["prismatic_max_abs_N"] <= threshold["bias_cross_P_max_abs_N"], bias),
        ("G09", "ACTUATED_8DOF_TIME_VARYING_STATE_EVOLUTION", actuated_evolution["qR_peak_change_rad"] > 0.0 and actuated_evolution["qP_peak_change_m"] > 0.0, actuated_evolution),
        ("G10", "LOCKED_2P_KKT_ELIMINATION_REACTION_AND_ZERO_POWER", kkt_pass, locked),
        ("G11", "ZERO_TAUP_DOES_NOT_IMPLY_FREE_PRISMATIC_LOCK", locked["tauP_zero_free_prismatic_acceleration_max_abs_m_s2"] >= threshold["tauP_zero_free_acceleration_min_m_s2"], {"observed_m_s2": locked["tauP_zero_free_prismatic_acceleration_max_abs_m_s2"], "minimum_m_s2": threshold["tauP_zero_free_acceleration_min_m_s2"]}),
        ("G12", "RK4_DOP853_NATIVE_UNIT_CROSS", cross_pass, {"lanes": crosses}),
        ("G13", "QUATERNION_NORM_AND_SIGN_INVARIANT_ATTITUDE", all(item["quaternion"] for item in history_passes) and all(item["base_attitude_max_rad"] <= threshold["rk4_dop853_base_attitude_max_rad"] for item in crosses), {"max_norm_error": _maximum(history_audits, "max_quaternion_norm_error"), "max_cross_attitude_rad": max(item["base_attitude_max_rad"] for item in crosses)}),
        ("G14", "PER_BODY_INERTIAL_LINEAR_MOMENTUM_ZERO", all(item["linear_momentum"] for item in history_passes), {"max_kg_m_s": _maximum(history_audits, "max_linear_momentum_body_inertial_kg_m_s")}),
        ("G15", "PER_BODY_INERTIAL_ORIGIN_ANGULAR_MOMENTUM_ZERO", all(item["angular_momentum"] for item in history_passes), {"max_kg_m2_s": _maximum(history_audits, "max_angular_momentum_body_inertial_kg_m2_s")}),
        ("G16", "GENERALIZED_MATRIX_VS_PER_BODY_MOMENTUM_CROSS", all(item["matrix_body"] for item in history_passes), {"linear_max_kg_m_s": _maximum(history_audits, "max_matrix_vs_body_linear_kg_m_s"), "angular_max_kg_m2_s": _maximum(history_audits, "max_matrix_vs_body_angular_kg_m2_s")}),
        ("G17", "GENERALIZED_WORK_EQUALS_KINETIC_ENERGY_CHANGE", all(item["work_energy"] for item in history_passes), {"absolute_max_J": _maximum(history_audits, "max_work_energy_absolute_J"), "relative_max": _maximum(history_audits, "max_work_energy_relative")}),
        ("G18", "MECHANICAL_CONNECTION_ZERO_MOMENTUM_CLOSURE", all(item["connection"] for item in history_passes), {"linear_max_kg_m_s": _maximum(history_audits, "max_connection_linear_residual_kg_m_s"), "angular_max_kg_m2_s": _maximum(history_audits, "max_connection_angular_residual_kg_m2_s")}),
        ("G19", "REFERENCE_COORDINATE_SCALE_EQUATION_ENERGY_POWER_INVARIANCE", scale["revolute_acceleration_max_abs_rad_s2"] <= threshold["scale_acceleration_R_max_abs_rad_s2"] and scale["prismatic_acceleration_max_abs_m_s2"] <= threshold["scale_acceleration_P_max_abs_m_s2"] and scale["energy_relative"] <= threshold["scale_energy_relative_max"] and scale["power_relative"] <= threshold["scale_power_relative_max"] and scale["raw_mixed_unit_spectrum_or_condition_used_for_credit"] is False, scale),
        ("G20", "ZERO_EFFORT_ENERGY_AND_MOMENTUM_DEGENERATION", zero["max_kinetic_energy_relative_drift"] <= threshold["zero_effort_energy_relative_max"] and zero["max_linear_momentum_body_inertial_kg_m_s"] <= threshold["linear_momentum_residual_max_kg_m_s"] and zero["max_angular_momentum_body_inertial_kg_m2_s"] <= threshold["angular_momentum_residual_max_kg_m2_s"], zero),
        ("G21", "VALID_CONSTANT_EFFORT_CURRENT_BACKEND_REGRESSION", constant_pass, constant),
        ("G22", "DETERMINISTIC_RK4_REPLAY_BYTE_IDENTICAL_CANONICAL", all(item["byte_identical_canonical_replay"] for item in replay.values()), replay),
        ("G23", "MUTATION_AND_PHYSICS_NEGATIVE_CONTROLS", negative["all_pass"] and negative["passed"] >= negative["minimum_required"], {"passed": negative["passed"], "count": negative["count"], "minimum_required": negative["minimum_required"]}),
        ("G24", "ALL_SCOPE_GUARDS_AND_DOWNSTREAM_AUTHORITIES_FALSE", all(value is False for key, value in boundaries.items() if key != "candidate_only") and boundaries["candidate_only"] is True, boundaries),
    ]
    _require(tuple(row[0] for row in check_rows) == GATE_IDS, "GATE_ID_SET_OR_ORDER_MISMATCH")
    checks = [
        {"id": identifier, "name": name, "pass": bool(passed), "evidence": evidence_row}
        for identifier, name, passed, evidence_row in check_rows
    ]
    all_pass = all(row["pass"] for row in checks)
    verdict = (
        contract["maximum_claim"]
        if all_pass
        else "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_HOLD__NO_DOWNSTREAM_AUTHORITY"
    )
    evidence = to_builtin(
        {
            "schema": "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_EVIDENCE_V1",
            "contract_canonical_sha256": EXPECTED_CONTRACT_CANONICAL_SHA256,
            "authority_scope": contract["authority_scope"],
            "source_pins": source_pins,
            "runtime_project_module_inventory": runtime_modules,
            "urdf_contract": urdf,
            "topology": topology,
            "backend_default_state_audit": default_audit,
            "candidate_initial_state_audit": candidate_state,
            "effort_profile_audit": profile_audit,
            "lanes": lane_evidence,
            "bias_cross": bias,
            "locked_kkt": locked,
            "coordinate_scale_invariance": scale,
            "zero_effort_degeneration": zero,
            "constant_effort_backend_regression": constant,
            "deterministic_replay": replay,
            "negative_controls": negative,
            "execution_boundaries": boundaries,
            "measurement_uncertainty_boundary": "NO_HARDWARE_MEASUREMENTS_OR_UNCERTAINTY_MODEL_USED__DESIGN_NUMBERS_ONLY",
            "next_stage_authorized": False,
            "release_credit": False,
        }
    )
    gate = to_builtin(
        {
            "schema": "R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_GATE_V1",
            "authority_scope": contract["authority_scope"],
            "contract_canonical_sha256": EXPECTED_CONTRACT_CANONICAL_SHA256,
            "checks": checks,
            "passed": sum(row["pass"] for row in checks),
            "total": 24,
            "all_checks_pass": all_pass,
            "verdict": verdict,
            "maximum_claim": contract["maximum_claim"],
            "review_status": contract["review_status"],
            "flex_valid": False,
            "contact_valid": False,
            "target_attachment_valid": False,
            "hardware_valid": False,
            "control_valid": False,
            "parent_dynamics_engineering_complete": False,
            "sim13_non_abort_authorized": False,
            "next_stage_authorized": False,
            "release_credit": False,
        }
    )
    return evidence, gate
