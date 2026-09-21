"""Append-only current-R2 free-floating time-domain twist-rate diagnostic.

The controller is deliberately narrow: six revolute joints are active, the two
prismatic gripper joints are ideal holonomic locks, total system momentum is
exactly zero, and the commanded task-rate components are expressed in the
instantaneous spacecraft-bus root frame.  There is no target-relative pose
state, contact, collision, flexible-body, actuator-hardware, or release model.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import numpy as np


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = PACKAGE_ROOT / "contracts" / "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_CONTRACT_V1.json"
EXPECTED_CONTRACT_CANONICAL_SHA256 = "581B838410F7E48E5B8BCABE00180727E9F773C29B85875BDF16DA2DB031A711"
EXPECTED_SCENARIOS = (
    ("C0_UNCONTROLLED_5D_REFERENCE", "PAIR_5D", "FAR_APPROACH_5D", False, 5),
    ("C1_CONTROLLED_5D", "PAIR_5D", "FAR_APPROACH_5D", True, 5),
    ("C0_UNCONTROLLED_6D_REFERENCE", "PAIR_6D", "FINAL_ALIGNMENT_6D", False, 6),
    ("C2_CONTROLLED_6D", "PAIR_6D", "FINAL_ALIGNMENT_6D", True, 6),
)


class CandidateError(RuntimeError):
    """Fail-closed contract, source, physics, or authority violation."""


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
    return json.loads(text, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant)


def load_json_strict(path: Path) -> Any:
    try:
        return loads_json_strict(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise CandidateError(f"JSON_UTF8_REQUIRED:{path}") from exc


def _require(condition: bool, code: str) -> None:
    if not bool(condition):
        raise CandidateError(code)


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise CandidateError(f"{field}_BOOLEAN_NOT_NUMERIC")
    result = float(value)
    if not math.isfinite(result):
        raise CandidateError(f"{field}_NONFINITE")
    return result


def finite_vector(values: Sequence[float], size: int, field: str) -> np.ndarray:
    result = np.asarray(values, dtype=float)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise CandidateError(f"{field}_MUST_HAVE_{size}_FINITE_VALUES")
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
            raise CandidateError("NONFINITE_EVIDENCE_VALUE_REJECTED")
        return value
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(f"UNSUPPORTED_EVIDENCE_TYPE:{type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        to_builtin(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
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


def _authority_boundaries(contract: Mapping[str, Any]) -> Mapping[str, Any]:
    return contract["claim_boundary"]


def validate_contract(contract: Mapping[str, Any], *, check_canonical: bool = True) -> dict[str, Any]:
    _require(contract.get("schema") == "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_CONTRACT_V1", "CONTRACT_SCHEMA_MISMATCH")
    _require(
        contract.get("authority_scope")
        == "APPEND_ONLY_ZERO_MOMENTUM_RIGID_ROOT_FRAME_TWIST_RATE_DIAGNOSTIC_ONLY",
        "AUTHORITY_SCOPE_MISMATCH",
    )
    _require("PLANNED_NOT_YET_EXECUTED" in str(contract.get("maximum_contract_claim")), "CONTRACT_MUST_NOT_SELF_CERTIFY_EXECUTION")
    admission = contract.get("execution_resource_admission", {})
    _require(admission.get("scientific_or_release_authority") is False, "MEMORY_GATE_AUTHORITY_ESCALATION")
    _require(admission.get("classification") == "EXECUTION_RESOURCE_GATE_ONLY__NOT_SCIENTIFIC_THRESHOLD", "MEMORY_GATE_CLASSIFICATION_MISMATCH")
    _require(admission.get("admission_pass") is True and admission.get("runtime_pre_solve_pass") is True, "MEMORY_EXECUTION_GATE_NOT_PASSED")
    samples = finite_vector(admission.get("runtime_pre_solve_samples_gib", []), 3, "RUNTIME_MEMORY_SAMPLES_GIB")
    threshold_gib = _finite(admission.get("threshold_gib"), "MEMORY_THRESHOLD_GIB")
    _require(float(np.min(samples)) >= threshold_gib, "MEMORY_SAMPLES_BELOW_DECLARED_THRESHOLD")

    plant = contract.get("plant", {})
    _require(plant.get("upstream_lane_identifier") == "LOCKED_2P_6R_PULSE", "UPSTREAM_LANE_MISMATCH")
    _require("IDENTIFIER_REUSE_ONLY" in str(plant.get("upstream_lane_identifier_interpretation")), "PULSE_IDENTIFIER_NOT_DISAMBIGUATED")
    _require(plant.get("model_scope") == "CURRENT_R2_RIGID_ZERO_TOTAL_MOMENTUM_6R_ACTIVE_2P_IDEALLY_LOCKED", "PLANT_SCOPE_MISMATCH")
    _require(plant.get("total_momentum_scope") == "EXACTLY_ZERO", "NONZERO_TOTAL_MOMENTUM_UNSUPPORTED_FAIL_CLOSED")
    _require(finite_vector(plant.get("qP_star_m", []), 2, "QP_STAR").tolist() == [0.03575, 0.03575], "QP_STAR_MISMATCH")
    _require(np.array_equal(finite_vector(plant.get("dqP_m_s", []), 2, "DQP"), np.zeros(2)), "LOCKED_DQP_NONZERO")
    _require(np.array_equal(finite_vector(plant.get("tauP_N", []), 2, "TAUP"), np.zeros(2)), "LOCKED_TAUP_NONZERO")
    for field in ("external_force_or_torque_present", "contact_or_target_present", "flex_present"):
        _require(plant.get(field) is False, f"PLANT_SCOPE_ESCALATION:{field}")
    duration = _finite(plant.get("duration_s"), "DURATION_S")
    step = _finite(plant.get("fixed_step_s"), "FIXED_STEP_S")
    _require(duration > 0.0 and step > 0.0 and abs(duration / step - round(duration / step)) <= 1e-12, "TIME_GRID_INVALID")
    initial = contract.get("initial_state", {})
    finite_vector(initial.get("base_position_inertial_m", []), 3, "INITIAL_BASE_POSITION")
    quaternion = finite_vector(initial.get("base_quaternion_body_to_inertial_wxyz", []), 4, "INITIAL_QUATERNION")
    _require(float(np.linalg.norm(quaternion)) > 0.0, "INITIAL_QUATERNION_ZERO_NORM")
    initial_q = finite_vector(initial.get("q8_mixed_rad_m", []), 8, "INITIAL_Q8")
    initial_dq = finite_vector(initial.get("dq8_mixed_rad_s_m_s", []), 8, "INITIAL_DQ8")
    _require(np.array_equal(initial_q[6:], finite_vector(plant.get("qP_star_m", []), 2, "QP_STAR")), "INITIAL_QP_NOT_LOCKED")
    _require(np.array_equal(initial_dq[6:], np.zeros(2)), "INITIAL_DQP_NOT_LOCKED")

    task = contract.get("task_semantics", {})
    _require(task.get("tool_link") == "gripper_link", "TASK_TOOL_LINK_NOT_FROZEN")
    _require(task.get("twist_expression_frame") == "INSTANTANEOUS_SPACECRAFT_BUS_ROOT_FRAME", "TASK_FRAME_NOT_FROZEN")
    _require(task.get("tool_point") == "GRIPPER_LINK_URDF_FRAME_ORIGIN", "TASK_TOOL_POINT_NOT_FROZEN")
    _require(task.get("weighted_error_unit") == "1/s", "WEIGHTED_ERROR_UNIT_MISMATCH")
    _require(task.get("six_d_command_interpretation") == "CONSTANT_COMPONENTS_IN_THE_INSTANTANEOUS_SPACECRAFT_BUS_ROOT_FRAME", "SIX_D_COMMAND_SEMANTICS_MISMATCH")
    for field in ("reference_is_inertial_trajectory", "pose_error_state_present", "pose_or_attitude_tracking_claim_allowed", "mixed_unweighted_linear_angular_norm_credit"):
        _require(task.get(field) is False, f"TASK_SEMANTIC_ESCALATION:{field}")
    _require("CONFIGURATION_DEPENDENT_LOCAL_APPROACH_AXIS_PLANE_BASIS" in str(task.get("five_d_last_two_channels_interpretation")), "FIVE_D_LOCAL_BASIS_SEMANTICS_MISSING")

    controller = contract.get("controller", {})
    _require(controller.get("law") == "qdd_cmd=Kv*(qdot_cmd-dqR); tauR=M_RR*qdd_cmd+bias_R; tauP=0", "CONTROLLER_LAW_MISMATCH")
    _require(_finite(controller.get("Kv_per_s"), "KV_PER_S") > 0.0, "KV_MUST_BE_POSITIVE")
    _require(controller.get("gain_authority") == "PROVISIONAL_DESIGN_DIAGNOSTIC_ONLY", "GAIN_AUTHORITY_MISMATCH")
    _require(controller.get("stability_proof_present") is False, "STABILITY_PROOF_ESCALATION")
    _require(controller.get("secondary_nullspace_objective_present") is False, "UNAUTHORIZED_SECONDARY_OBJECTIVE")
    _require(controller.get("hardware_effort_rate_delay_saturation_or_bandwidth_model") is False, "HARDWARE_MODEL_ESCALATION")
    _require(_finite(controller.get("dls_lambda_dimensionless"), "DLS_LAMBDA") > 0.0, "DLS_LAMBDA_INVALID")
    _require(_finite(controller.get("sigma_min_dimensionless_threshold"), "SIGMA_THRESHOLD") > 0.0, "SIGMA_THRESHOLD_INVALID")

    rows = contract.get("scenarios", [])
    _require(len(rows) == len(EXPECTED_SCENARIOS), "SCENARIO_COUNT_MISMATCH")
    expected_units = {
        5: ["m/s", "m/s", "m/s", "1/s", "1/s"],
        6: ["m/s", "m/s", "m/s", "rad/s", "rad/s", "rad/s"],
    }
    for row, expected in zip(rows, EXPECTED_SCENARIOS):
        identifier, pair, task_id, enabled, dimension = expected
        _require((row.get("id"), row.get("comparison_pair"), row.get("task"), row.get("controller_enabled")) == (identifier, pair, task_id, enabled), f"SCENARIO_CONTRACT_MISMATCH:{identifier}")
        finite_vector(row.get("desired_twist_native", []), dimension, f"DESIRED:{identifier}")
        _require(row.get("desired_units") == expected_units[dimension], f"DESIRED_UNITS_MISMATCH:{identifier}")
    for pair in ("PAIR_5D", "PAIR_6D"):
        pair_rows = [row for row in rows if row["comparison_pair"] == pair]
        _require(len(pair_rows) == 2, f"COMPARISON_PAIR_CARDINALITY_MISMATCH:{pair}")
        _require(pair_rows[0]["task"] == pair_rows[1]["task"], f"COMPARISON_TASK_MISMATCH:{pair}")
        _require(pair_rows[0]["desired_twist_native"] == pair_rows[1]["desired_twist_native"], f"COMPARISON_REFERENCE_MISMATCH:{pair}")
        _require(pair_rows[0]["desired_units"] == pair_rows[1]["desired_units"], f"COMPARISON_UNITS_MISMATCH:{pair}")

    thresholds = contract.get("thresholds", {})
    required_thresholds = (
        "controlled_final_error_ratio_to_same_task_uncontrolled_max",
        "controlled_rms_error_ratio_to_same_task_uncontrolled_max",
        "step_sigma_min_dimensionless_min",
        "rk4_dop853_qR_max_abs_rad",
        "rk4_dop853_dqR_max_abs_rad_s",
        "rk4_dop853_base_position_max_abs_m",
        "rk4_dop853_base_attitude_max_rad",
        "rk4_dop853_weighted_task_error_max_abs_per_s",
        "linear_momentum_residual_max_kg_m_s",
        "angular_momentum_about_fixed_inertial_origin_residual_max_kg_m2_s",
        "work_energy_absolute_max_J",
        "work_energy_relative_max",
        "quaternion_norm_error_max",
        "qP_position_lock_max_abs_m",
        "dqP_lock_max_abs_m_s",
        "ddqP_lock_max_abs_m_s2",
        "kkt_equilibrium_R_max_abs_Nm",
        "kkt_equilibrium_P_max_abs_N",
        "kkt_vs_elimination_acceleration_R_max_abs_rad_s2",
        "kkt_reaction_cross_max_abs_N",
        "constraint_reaction_power_max_abs_W",
        "computed_acceleration_closure_max_abs_rad_s2",
        "negative_controls_minimum",
    )
    _require(set(thresholds) == set(required_thresholds) | {"approach_basis_seed_switch_count_max", "approach_basis_fixed_seed_cross_norm_min", "joint_limit_min_margin_mixed_rad_m"}, "THRESHOLD_SET_MISMATCH")
    for name in required_thresholds:
        _require(_finite(thresholds[name], f"THRESHOLD:{name}") > 0.0, f"THRESHOLD_NOT_POSITIVE:{name}")
    _require(_finite(thresholds["joint_limit_min_margin_mixed_rad_m"], "JOINT_MARGIN_THRESHOLD") == 0.0, "JOINT_MARGIN_THRESHOLD_MISMATCH")
    _require(_finite(thresholds["approach_basis_seed_switch_count_max"], "BASIS_SWITCH_THRESHOLD") == 0.0, "BASIS_SWITCH_THRESHOLD_MISMATCH")
    _require(_finite(thresholds["approach_basis_fixed_seed_cross_norm_min"], "BASIS_CROSS_NORM_THRESHOLD") > 0.0, "BASIS_CROSS_NORM_THRESHOLD_INVALID")

    pins = contract.get("source_pins", [])
    _require(len(pins) == 10 and len({row.get("id") for row in pins}) == 10, "SOURCE_PIN_SET_MISMATCH")
    for pin in pins:
        _require(isinstance(pin.get("path"), str) and bool(pin["path"]), "SOURCE_PIN_PATH_INVALID")
        _require(isinstance(pin.get("bytes"), int) and pin["bytes"] > 0, "SOURCE_PIN_BYTES_INVALID")
        sha = pin.get("sha256")
        _require(isinstance(sha, str) and len(sha) == 64 and sha == sha.upper(), "SOURCE_PIN_SHA_INVALID")

    boundaries = _authority_boundaries(contract)
    _require(boundaries.get("time_domain_diagnostic_executed") is False, "CONTRACT_EXECUTION_SELF_CERTIFICATION")
    _require(boundaries.get("parent_gates_changed") is False, "PARENT_GATE_MUTATION_CLAIM")
    for key, value in boundaries.items():
        if key != "parent_gates_changed":
            _require(value is False, f"AUTHORITY_BOUNDARY_ESCALATED:{key}")
    _require(contract.get("next_stage_authorized") is False and contract.get("release_credit") is False, "RELEASE_BOUNDARY_ESCALATED")
    _require(contract.get("review_status") == "PENDING_OWNER_REVIEW", "REVIEW_STATUS_MISMATCH")
    if check_canonical and EXPECTED_CONTRACT_CANONICAL_SHA256 != "TO_BE_BOUND_AFTER_CONTRACT_FREEZE":
        _require(canonical_sha256(contract) == EXPECTED_CONTRACT_CANONICAL_SHA256, "CONTRACT_CANONICAL_SHA256_DRIFT")
    return {"valid": True, "scenario_count": len(rows), "source_pin_count": len(pins)}


def load_contract() -> dict[str, Any]:
    contract = load_json_strict(CONTRACT_PATH)
    validate_contract(contract)
    return contract


def _pin(contract: Mapping[str, Any], identifier: str, project_root: Path = PROJECT_ROOT) -> Path:
    matches = [row for row in contract["source_pins"] if row["id"] == identifier]
    _require(len(matches) == 1, f"SOURCE_PIN_ID_NOT_UNIQUE:{identifier}")
    return (project_root / matches[0]["path"]).resolve()


def validate_source_pins(contract: Mapping[str, Any], project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for pin in contract["source_pins"]:
        path = (project_root / pin["path"]).resolve()
        _require(path.is_file(), f"SOURCE_PIN_MISSING:{pin['id']}")
        actual = file_record(path, project_root)
        match = actual["bytes"] == pin["bytes"] and actual["sha256"] == pin["sha256"]
        records.append({"id": pin["id"], **actual, "declared_bytes": pin["bytes"], "declared_sha256": pin["sha256"], "match": match})
        _require(match, f"SOURCE_PIN_DRIFT:{pin['id']}")
    return {"all_match": True, "matched": len(records), "total": len(records), "records": records}


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise CandidateError(f"MODULE_IMPORT_SPEC_FAILED:{name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def validate_upstream_parameter_lock(contract: Mapping[str, Any], metric_contract: Mapping[str, Any]) -> dict[str, bool]:
    metric_generalized = metric_contract["generalized_coordinate_metric"]
    checks = {
        "rank_rtol_exact": float(contract["controller"]["rank_rtol"]) == float(metric_contract["dls"]["rank_rtol"]),
        "sigma_threshold_exact": float(contract["controller"]["sigma_min_dimensionless_threshold"]) == float(metric_contract["dls"]["sigma_min_dimensionless_threshold"]),
        "dls_lambda_exact": float(contract["controller"]["dls_lambda_dimensionless"]) == float(metric_contract["dls"]["lambda_dimensionless"]),
        "characteristic_length_exact_m": float(contract["controller"]["characteristic_length_m"]) == float(metric_contract["derivation"]["characteristic_length_m"]),
        "reference_inertia_exact_kg_m2": float(contract["controller"]["reference_inertia_kg_m2"]) == float(metric_generalized["reference_inertia_kg_m2"]),
        "q_rate_scale_exact": list(contract["controller"]["q_rate_scale_diagonal_rad_inverse"]) == list(metric_generalized["q_rate_scale_diagonal_rad_inverse"]),
    }
    _require(all(checks.values()), "UPSTREAM_METRIC_PARAMETER_LOCK_MISMATCH")
    return checks


def load_upstream(contract: Mapping[str, Any], project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    plant = _load_module("_td_tracking_upstream_plant", _pin(contract, "time_varying_plant_source", project_root))
    metric = _load_module("_td_tracking_upstream_metric", _pin(contract, "task_metric_source", project_root))
    plant_contract = plant.load_json_strict(_pin(contract, "time_varying_plant_contract", project_root))
    metric_contract = metric.load_json_strict(_pin(contract, "task_metric_contract", project_root))
    plant.validate_contract_semantics(plant_contract)
    metric.validate_contract(metric_contract)
    upstream_parameter_lock = validate_upstream_parameter_lock(contract, metric_contract)
    plant_binding = plant.validate_source_pins(plant_contract, project_root)
    metric_binding = metric.validate_source_pins(metric_contract, project_root)
    control = metric._load_parent_source(metric_contract, project_root)
    parent = plant._load_parent_module(project_root)
    backend = parent.load_backend(project_root)
    model = parent.ReducedR2Model(backend=backend, qP_star_m=np.asarray(contract["plant"]["qP_star_m"], dtype=float))
    return {
        "plant": plant,
        "metric": metric,
        "control": control,
        "parent": parent,
        "backend": backend,
        "model": model,
        "plant_contract": plant_contract,
        "metric_contract": metric_contract,
        "plant_binding": plant_binding,
        "metric_binding": metric_binding,
        "upstream_parameter_lock": upstream_parameter_lock,
    }


def effective_plant_contract(contract: Mapping[str, Any], upstream_contract: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(upstream_contract))
    result["effort_profile"]["duration_s"] = float(contract["plant"]["duration_s"])
    result["effort_profile"]["fixed_step_s"] = float(contract["plant"]["fixed_step_s"])
    result["solver_contract"]["cross_max_step_s"] = min(
        float(result["solver_contract"]["cross_max_step_s"]), float(contract["plant"]["fixed_step_s"])
    )
    result["lanes"]["LOCKED_2P_6R_PULSE"]["qP_star_m"] = list(contract["plant"]["qP_star_m"])
    initial = contract["initial_state"]
    result["initial_state"]["base_position_inertial_initial_m"] = list(initial["base_position_inertial_m"])
    result["initial_state"]["base_quaternion_body_to_inertial_initial_wxyz"] = list(initial["base_quaternion_body_to_inertial_wxyz"])
    result["initial_state"]["q0_mixed_rad_m"] = list(initial["q8_mixed_rad_m"])
    result["initial_state"]["qdot0_mixed_rad_s_m_s"] = list(initial["dq8_mixed_rad_s_m_s"])
    return result


class RootFrameTwistRateController:
    def __init__(self, model: Any, backend: Any, control: Any, metric: Any, metric_contract: Mapping[str, Any], plant_contract: Mapping[str, Any], contract: Mapping[str, Any], scenario: Mapping[str, Any]):
        self.model = model
        self.backend = backend
        self.control = control
        self.metric = metric
        self.metric_contract = metric_contract
        self.plant_contract = plant_contract
        self.contract = contract
        self.scenario = scenario
        q0 = finite_vector(contract["initial_state"]["q8_mixed_rad_m"], 8, "INITIAL_Q8_FOR_BASIS")
        transform0, _, _, _ = self.control._tool_jacobians(self.backend, q0, self.contract["task_semantics"]["tool_link"])
        axis0 = np.asarray(transform0[:3, 2], dtype=float)
        self.approach_basis_seed_index = int(np.argmin(np.abs(axis0)))

    @property
    def dimension(self) -> int:
        return 5 if self.scenario["task"] == "FAR_APPROACH_5D" else 6

    def fixed_seed_approach_basis(self, approach_axis: np.ndarray) -> tuple[np.ndarray, float]:
        axis = finite_vector(approach_axis, 3, "APPROACH_AXIS")
        axis /= np.linalg.norm(axis)
        seed = np.eye(3)[self.approach_basis_seed_index]
        first = np.cross(axis, seed)
        cross_norm = float(np.linalg.norm(first))
        _require(cross_norm >= float(self.contract["thresholds"]["approach_basis_fixed_seed_cross_norm_min"]), "FIXED_SEED_APPROACH_BASIS_DEGENERATE_FAIL_CLOSED")
        first /= cross_norm
        second = np.cross(axis, first)
        return np.vstack((first, second)), cross_norm

    def evaluate(self, q8: Sequence[float], dq8: Sequence[float]) -> dict[str, Any]:
        q = finite_vector(q8, 8, "CONTROLLER_Q8")
        dq = finite_vector(dq8, 8, "CONTROLLER_DQ8")
        qP_star = finite_vector(self.contract["plant"]["qP_star_m"], 2, "QP_STAR")
        _require(np.array_equal(q[6:], qP_star), "LOCKED_QP_RUNTIME_MISMATCH")
        _require(np.array_equal(dq[6:], np.zeros(2)), "LOCKED_DQP_RUNTIME_NONZERO")
        lower = finite_vector(self.plant_contract["model_contract"]["joint_lower_mixed_rad_m"], 8, "JOINT_LOWER")
        upper = finite_vector(self.plant_contract["model_contract"]["joint_upper_mixed_rad_m"], 8, "JOINT_UPPER")
        _require(bool(np.all(q >= lower) and np.all(q <= upper)), "RUNTIME_JOINT_LIMIT_FAIL_CLOSED")
        transform, fixed8, generalized8, connection8 = self.control._tool_jacobians(
            self.backend, q, self.contract["task_semantics"]["tool_link"]
        )
        approach_axis = np.asarray(transform[:3, 2], dtype=float)
        approach_basis, approach_basis_cross_norm = self.fixed_seed_approach_basis(approach_axis)
        _, generalized = self.metric._weighted_task(
            self.control,
            self.scenario["task"],
            np.asarray(fixed8[:, :6], dtype=float),
            np.asarray(generalized8[:, :6], dtype=float),
            approach_basis,
            approach_axis,
        )
        dimension = self.dimension
        weight_diagonal = self.metric._metric_diagonal(float(self.contract["controller"]["characteristic_length_m"]), dimension)
        weight = np.diag(weight_diagonal)
        weighted_jacobian = weight @ generalized
        desired_native = finite_vector(self.scenario["desired_twist_native"], dimension, "DESIRED_TWIST")
        weighted_desired = weight @ desired_native
        guard = self.metric._rank_guard(weighted_jacobian, dimension, self.metric_contract)
        _require(bool(guard["allow"]), f"RANK_OR_SIGMA_FAIL_CLOSED:{self.scenario['id']}")
        _require(float(guard["sigma_min_dimensionless"]) >= float(self.contract["thresholds"]["step_sigma_min_dimensionless_min"]), "STEP_SIGMA_BELOW_PREDECLARED_THRESHOLD")
        mass8 = np.asarray(self.model.mass(q), dtype=float)
        bias8 = np.asarray(self.model.bias(q, dq), dtype=float)
        mass6 = mass8[:6, :6]
        _require(np.all(np.isfinite(mass6)) and np.allclose(mass6, mass6.T, atol=1e-13, rtol=0.0), "MASS6_NOT_FINITE_SYMMETRIC")
        _require(float(np.min(np.linalg.eigvalsh(mass6))) > 0.0, "MASS6_NOT_SPD")
        qdot_cmd, dls_audit = self.metric.dimensionless_mass_weighted_dls(
            weighted_jacobian,
            weighted_desired,
            mass6,
            finite_vector(self.contract["controller"]["q_rate_scale_diagonal_rad_inverse"], 6, "Q_RATE_SCALE"),
            float(self.contract["controller"]["reference_inertia_kg_m2"]),
            float(self.contract["controller"]["dls_lambda_dimensionless"]),
        )
        qdd_cmd = float(self.contract["controller"]["Kv_per_s"]) * (qdot_cmd - dq[:6])
        if bool(self.scenario["controller_enabled"]):
            tau6 = mass6 @ qdd_cmd + bias8[:6]
        else:
            tau6 = np.zeros(6)
        tau8 = np.concatenate((tau6, np.zeros(2)))
        actual_weighted = weighted_jacobian @ dq[:6]
        error = actual_weighted - weighted_desired
        return {
            "tau8_mixed_Nm_N": tau8,
            "qdot_cmd_rad_s": qdot_cmd,
            "qdd_cmd_rad_s2": qdd_cmd,
            "weighted_actual_per_s": actual_weighted,
            "weighted_desired_per_s": weighted_desired,
            "weighted_error_per_s": error,
            "weighted_error_norm_per_s": float(np.linalg.norm(error)),
            "guard": guard,
            "dls_audit": dls_audit,
            "approach_axis_root_frame": approach_axis,
            "approach_plane_basis_root_frame": approach_basis,
            "approach_basis_seed_index": self.approach_basis_seed_index,
            "approach_basis_cross_norm": approach_basis_cross_norm,
            "base_connection_6x8": connection8,
        }


def make_feedback_kernel(plant: Any, model: Any, effective_contract: Mapping[str, Any], controller: RootFrameTwistRateController) -> Any:
    class FeedbackPlantKernel(plant.PlantKernel):
        def __init__(self) -> None:
            super().__init__(model=model, contract=effective_contract, lane="LOCKED_2P_6R_PULSE", effort_function=lambda _time: np.zeros(8))

        def acceleration(self, t_s: float, q: np.ndarray, dq: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            _finite(t_s, "CONTROL_TIME_S")
            q_effective, dq_effective = self.effective_state(q, dq)
            command = controller.evaluate(q_effective, dq_effective)
            tau = finite_vector(command["tau8_mixed_Nm_N"], 8, "CONTROL_EFFORT")
            _require(np.array_equal(tau[6:], np.zeros(2)), "LOCKED_LANE_PRISMATIC_EFFORT_MUST_BE_ZERO")
            result = model.locked_acceleration(q_effective[:6], dq_effective[:6], tau[:6], tau[6:])
            ddq = np.asarray(result["kkt_acceleration"], dtype=float)
            ddq[6:] = 0.0
            return ddq, tau

    return FeedbackPlantKernel()


def _direct_qp_lock_audit(history: np.ndarray, qP_star: np.ndarray) -> dict[str, float]:
    values = np.asarray(history, dtype=float)
    _require(values.ndim == 2 and values.shape[1] == 24 and np.all(np.isfinite(values)), "HISTORY_SHAPE_OR_FINITE_FAIL")
    return {
        "qP_position_lock_max_abs_m": float(np.max(np.abs(values[:, 13:15] - qP_star))),
        "dqP_lock_max_abs_m_s": float(np.max(np.abs(values[:, 21:23]))),
    }


def audit_scenario_history(
    plant: Any,
    model: Any,
    effective_contract: Mapping[str, Any],
    controller: RootFrameTwistRateController,
    times: np.ndarray,
    history: np.ndarray,
) -> dict[str, Any]:
    physical = plant.audit_history(model, effective_contract, "LOCKED_2P_6R_PULSE", times, history)
    error_vectors: list[np.ndarray] = []
    error_norms: list[float] = []
    sigma_values: list[float] = []
    basis_seed_indices: list[int] = []
    basis_cross_norms: list[float] = []
    ranks: list[int] = []
    effort_peaks: list[float] = []
    equilibrium_r: list[float] = []
    equilibrium_p: list[float] = []
    constraint_accel: list[float] = []
    reaction_power: list[float] = []
    reaction_cross: list[float] = []
    accel_cross: list[float] = []
    computed_closure: list[float] = []
    for state in np.asarray(history, dtype=float):
        q = state[7:15].copy()
        dq = state[15:23].copy()
        q[6:] = np.asarray(effective_contract["lanes"]["LOCKED_2P_6R_PULSE"]["qP_star_m"], dtype=float)
        dq[6:] = 0.0
        command = controller.evaluate(q, dq)
        tau = np.asarray(command["tau8_mixed_Nm_N"], dtype=float)
        result = model.locked_acceleration(q[:6], dq[:6], tau[:6], tau[6:])
        equilibrium = np.abs(np.asarray(result["kkt_equilibrium_residual"], dtype=float))
        error = np.asarray(command["weighted_error_per_s"], dtype=float)
        error_vectors.append(error)
        error_norms.append(float(np.linalg.norm(error)))
        sigma_values.append(float(command["guard"]["sigma_min_dimensionless"]))
        basis_seed_indices.append(int(command["approach_basis_seed_index"]))
        basis_cross_norms.append(float(command["approach_basis_cross_norm"]))
        ranks.append(int(command["guard"]["rank"]))
        effort_peaks.append(float(np.max(np.abs(tau[:6]))))
        equilibrium_r.append(float(np.max(equilibrium[:6])))
        equilibrium_p.append(float(np.max(equilibrium[6:])))
        constraint_accel.append(float(np.max(np.abs(result["constraint_acceleration"]))))
        reaction_power.append(float(abs(np.asarray(result["kkt_reaction_N"], dtype=float) @ dq[6:])))
        reaction_cross.append(float(result["reaction_cross_max_abs_N"]))
        accel_cross.append(float(result["acceleration_cross_revolute_max_abs_rad_s2"]))
        if bool(controller.scenario["controller_enabled"]):
            computed_closure.append(float(np.max(np.abs(np.asarray(result["kkt_acceleration"][:6]) - np.asarray(command["qdd_cmd_rad_s2"])))))
    errors = np.asarray(error_vectors, dtype=float)
    norms = np.asarray(error_norms, dtype=float)
    qp = _direct_qp_lock_audit(np.asarray(history, dtype=float), np.asarray(controller.contract["plant"]["qP_star_m"], dtype=float))
    return {
        "weighted_error_history_per_s": errors,
        "weighted_error_norm_initial_per_s": float(norms[0]),
        "weighted_error_norm_final_per_s": float(norms[-1]),
        "weighted_error_norm_rms_per_s": float(np.sqrt(np.mean(norms * norms))),
        "weighted_error_norm_peak_per_s": float(np.max(norms)),
        "step_rank_min": min(ranks),
        "step_sigma_min_dimensionless": min(sigma_values),
        "effort_R_peak_max_abs_Nm": max(effort_peaks),
        "max_kkt_equilibrium_R_abs_Nm": max(equilibrium_r),
        "max_kkt_equilibrium_P_abs_N": max(equilibrium_p),
        "max_constraint_acceleration_abs_m_s2": max(constraint_accel),
        "max_constraint_reaction_power_abs_W": max(reaction_power),
        "max_kkt_reaction_cross_abs_N": max(reaction_cross),
        "max_kkt_vs_elimination_acceleration_R_abs_rad_s2": max(accel_cross),
        "max_computed_acceleration_closure_abs_rad_s2": max(computed_closure) if computed_closure else 0.0,
        "approach_basis_seed_index_history": basis_seed_indices,
        "approach_basis_seed_switch_count": sum(left != right for left, right in zip(basis_seed_indices[:-1], basis_seed_indices[1:])),
        "approach_basis_cross_norm_min": min(basis_cross_norms),
        "constraint_reaction_is_not_contact_force": controller.contract["plant"]["contact_or_target_present"] is False,
        "secondary_nullspace_objective_present": False,
        "qP_lock": qp,
        "physics_ledger": physical,
    }


def run_scenario(contract: Mapping[str, Any], upstream: Mapping[str, Any], scenario: Mapping[str, Any]) -> dict[str, Any]:
    plant = upstream["plant"]
    effective = effective_plant_contract(contract, upstream["plant_contract"])
    controller = RootFrameTwistRateController(
        upstream["model"], upstream["backend"], upstream["control"], upstream["metric"], upstream["metric_contract"], effective, contract, scenario
    )
    kernel = make_feedback_kernel(plant, upstream["model"], effective, controller)
    times = plant.time_grid(effective)
    initial = plant.initial_augmented_state(effective, "LOCKED_2P_6R_PULSE")
    rk4 = plant.integrate_rk4(kernel, times, initial)
    dop853 = plant.integrate_dop853(kernel, times, initial)
    replay = plant.integrate_rk4(kernel, times, initial)
    rk4_audit = audit_scenario_history(plant, upstream["model"], effective, controller, times, rk4)
    dop853_audit = audit_scenario_history(plant, upstream["model"], effective, controller, times, dop853)
    cross = plant.solver_cross_audit({"rk4": rk4, "dop853": dop853}, upstream["model"], effective)
    task_cross = 0.0
    for left, right in zip(rk4, dop853):
        left_eval = controller.evaluate(left[7:15], left[15:23])
        right_eval = controller.evaluate(right[7:15], right[15:23])
        task_cross = max(task_cross, float(np.max(np.abs(np.asarray(left_eval["weighted_error_per_s"]) - np.asarray(right_eval["weighted_error_per_s"])))))
    return {
        "id": scenario["id"],
        "comparison_pair": scenario["comparison_pair"],
        "task": scenario["task"],
        "dimension": controller.dimension,
        "controller_enabled": bool(scenario["controller_enabled"]),
        "desired_twist_native": list(scenario["desired_twist_native"]),
        "desired_units": list(scenario["desired_units"]),
        "task_expression_frame": contract["task_semantics"]["twist_expression_frame"],
        "characteristic_length_m": contract["controller"]["characteristic_length_m"],
        "time_s": times,
        "rk4_physical_state_history_23": rk4[:, :23],
        "rk4_auxiliary_work_history_J": rk4[:, 23],
        "dop853_physical_state_history_23": dop853[:, :23],
        "dop853_auxiliary_work_history_J": dop853[:, 23],
        "rk4_audit": rk4_audit,
        "dop853_audit": dop853_audit,
        "solver_cross": {**cross, "weighted_task_error_max_abs_per_s": task_cross},
        "deterministic_replay": {
            "first_history_canonical_sha256": canonical_sha256(rk4),
            "second_history_canonical_sha256": canonical_sha256(replay),
            "byte_identical_canonical_replay": canonical_sha256(rk4) == canonical_sha256(replay),
        },
    }


def comparison_audit(scenarios: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_pair: dict[str, list[Mapping[str, Any]]] = {}
    for row in scenarios:
        by_pair.setdefault(str(row["comparison_pair"]), []).append(row)
    result: dict[str, Any] = {}
    for pair, rows in sorted(by_pair.items()):
        uncontrolled = next(row for row in rows if not row["controller_enabled"])
        controlled = next(row for row in rows if row["controller_enabled"])
        u = uncontrolled["rk4_audit"]
        c = controlled["rk4_audit"]
        result[pair] = {
            "uncontrolled_id": uncontrolled["id"],
            "controlled_id": controlled["id"],
            "final_error_ratio_controlled_to_uncontrolled": float(c["weighted_error_norm_final_per_s"] / u["weighted_error_norm_final_per_s"]),
            "rms_error_ratio_controlled_to_uncontrolled": float(c["weighted_error_norm_rms_per_s"] / u["weighted_error_norm_rms_per_s"]),
            "same_task_dimension_reference_units_frame_metric": uncontrolled["task"] == controlled["task"]
            and uncontrolled["dimension"] == controlled["dimension"]
            and uncontrolled["desired_twist_native"] == controlled["desired_twist_native"]
            and uncontrolled["desired_units"] == controlled["desired_units"]
            and uncontrolled["task_expression_frame"] == controlled["task_expression_frame"]
            and uncontrolled["characteristic_length_m"] == controlled["characteristic_length_m"],
        }
    return result


def run_negative_controls(contract: Mapping[str, Any], upstream: Mapping[str, Any]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []

    def expect(identifier: str, fn: Any, token: str) -> None:
        message = "NO_EXCEPTION"
        passed = False
        try:
            fn()
        except Exception as exc:
            message = str(exc)
            passed = token in message
        records.append({"id": identifier, "expected_token": token, "observed": message, "pass": passed})

    expect("NC01_DUPLICATE_JSON_KEY", lambda: loads_json_strict('{"x":1,"x":2}'), "DUPLICATE_JSON_KEY_REJECTED")
    expect("NC02_JSON_NAN", lambda: loads_json_strict('{"x":NaN}'), "NONFINITE_JSON_CONSTANT_REJECTED")
    mutated = copy.deepcopy(contract)
    mutated["claim_boundary"]["control_valid"] = True
    expect("NC03_CONTROL_AUTHORITY_ESCALATION", lambda: validate_contract(mutated, check_canonical=False), "AUTHORITY_BOUNDARY_ESCALATED:control_valid")
    mutated = copy.deepcopy(contract)
    mutated["claim_boundary"]["time_domain_diagnostic_executed"] = True
    expect("NC04_CONTRACT_SELF_CERTIFICATION", lambda: validate_contract(mutated, check_canonical=False), "CONTRACT_EXECUTION_SELF_CERTIFICATION")
    mutated = copy.deepcopy(contract)
    mutated["task_semantics"]["mixed_unweighted_linear_angular_norm_credit"] = True
    expect("NC05_MIXED_UNIT_NORM_ESCALATION", lambda: validate_contract(mutated, check_canonical=False), "TASK_SEMANTIC_ESCALATION:mixed_unweighted_linear_angular_norm_credit")
    mutated = copy.deepcopy(contract)
    mutated["plant"]["total_momentum_scope"] = "NONZERO"
    expect("NC06_NONZERO_TOTAL_MOMENTUM", lambda: validate_contract(mutated, check_canonical=False), "NONZERO_TOTAL_MOMENTUM_UNSUPPORTED")
    mutated = copy.deepcopy(contract)
    mutated["plant"]["qP_star_m"][0] += 1e-4
    expect("NC07_QP_UNLOCK_CONTRACT", lambda: validate_contract(mutated, check_canonical=False), "QP_STAR_MISMATCH")
    mutated = copy.deepcopy(contract)
    mutated["controller"]["secondary_nullspace_objective_present"] = True
    expect("NC08_UNAUTHORIZED_SECONDARY_OBJECTIVE", lambda: validate_contract(mutated, check_canonical=False), "UNAUTHORIZED_SECONDARY_OBJECTIVE")
    mutated = copy.deepcopy(contract)
    mutated["thresholds"]["step_sigma_min_dimensionless_min"] = -1.0
    expect("NC09_NEGATIVE_SIGMA_THRESHOLD", lambda: validate_contract(mutated, check_canonical=False), "THRESHOLD_NOT_POSITIVE")
    mutated = copy.deepcopy(contract)
    mutated["source_pins"][0]["sha256"] = "0" * 64
    expect("NC10_SOURCE_HASH_DRIFT", lambda: validate_source_pins(mutated), "SOURCE_PIN_DRIFT")
    expect("NC11_NONFINITE_STATE", lambda: finite_vector([0, 0, 0, 0, 0, math.inf, 0, 0], 8, "STATE"), "STATE_MUST_HAVE_8_FINITE_VALUES")
    zero_jacobian = np.zeros((6, 6))
    expect(
        "NC12_RANK_LOSS",
        lambda: _require(bool(upstream["metric"]._rank_guard(zero_jacobian, 6, upstream["metric_contract"])["allow"]), "RANK_OR_SIGMA_FAIL_CLOSED"),
        "RANK_OR_SIGMA_FAIL_CLOSED",
    )
    fake = np.zeros((2, 24))
    fake[:, 13:15] = np.asarray(contract["plant"]["qP_star_m"])
    fake[1, 13] += 1e-6
    expect(
        "NC13_QP_UNLOCK_HISTORY",
        lambda: _require(_direct_qp_lock_audit(fake, np.asarray(contract["plant"]["qP_star_m"]))["qP_position_lock_max_abs_m"] <= contract["thresholds"]["qP_position_lock_max_abs_m"], "QP_HISTORY_UNLOCK_FAIL_CLOSED"),
        "QP_HISTORY_UNLOCK_FAIL_CLOSED",
    )
    mutated = copy.deepcopy(contract)
    mutated["task_semantics"]["reference_is_inertial_trajectory"] = True
    expect("NC14_INERTIAL_TRAJECTORY_ESCALATION", lambda: validate_contract(mutated, check_canonical=False), "TASK_SEMANTIC_ESCALATION:reference_is_inertial_trajectory")
    mutated = copy.deepcopy(contract)
    mutated["scenarios"][1]["desired_twist_native"][0] += 1e-6
    expect("NC15_PAIRED_REFERENCE_MISMATCH", lambda: validate_contract(mutated, check_canonical=False), "COMPARISON_REFERENCE_MISMATCH:PAIR_5D")
    mutated = copy.deepcopy(contract)
    mutated["scenarios"][3]["desired_units"][-1] = "1/s"
    expect("NC16_DESIRED_UNIT_MISMATCH", lambda: validate_contract(mutated, check_canonical=False), "DESIRED_UNITS_MISMATCH:C2_CONTROLLED_6D")
    mutated = copy.deepcopy(contract)
    mutated["task_semantics"]["tool_link"] = "link6"
    expect("NC17_TOOL_LINK_DRIFT", lambda: validate_contract(mutated, check_canonical=False), "TASK_TOOL_LINK_NOT_FROZEN")
    mutated = copy.deepcopy(contract)
    mutated["controller"]["rank_rtol"] *= 10.0
    expect("NC18_UPSTREAM_METRIC_PARAMETER_DRIFT", lambda: validate_upstream_parameter_lock(mutated, upstream["metric_contract"]), "UPSTREAM_METRIC_PARAMETER_LOCK_MISMATCH")
    effective = effective_plant_contract(contract, upstream["plant_contract"])
    runtime_controller = RootFrameTwistRateController(
        upstream["model"], upstream["backend"], upstream["control"], upstream["metric"], upstream["metric_contract"], effective, contract, contract["scenarios"][1]
    )
    q0 = finite_vector(contract["initial_state"]["q8_mixed_rad_m"], 8, "NC_Q0")
    dq0 = finite_vector(contract["initial_state"]["dq8_mixed_rad_s_m_s"], 8, "NC_DQ0")
    q_unlocked = q0.copy()
    q_unlocked[6] += 1e-6
    expect("NC19_RUNTIME_QP_UNLOCK", lambda: runtime_controller.evaluate(q_unlocked, dq0), "LOCKED_QP_RUNTIME_MISMATCH")
    q_outside = q0.copy()
    q_outside[0] = 3.0
    expect("NC20_RUNTIME_JOINT_LIMIT", lambda: runtime_controller.evaluate(q_outside, dq0), "RUNTIME_JOINT_LIMIT_FAIL_CLOSED")
    return {
        "records": records,
        "count": len(records),
        "passed": sum(row["pass"] for row in records),
        "all_pass": all(row["pass"] for row in records),
        "minimum_required": int(contract["thresholds"]["negative_controls_minimum"]),
    }


def _audit_passes(row: Mapping[str, Any], thresholds: Mapping[str, Any]) -> dict[str, bool]:
    physics = row["physics_ledger"]
    qp = row["qP_lock"]
    return {
        "finite_limits_quaternion": bool(physics["finite_history"])
        and float(physics["revolute_joint_limit_min_margin_rad"]) >= float(thresholds["joint_limit_min_margin_mixed_rad_m"])
        and float(physics["prismatic_joint_limit_min_margin_m"]) >= float(thresholds["joint_limit_min_margin_mixed_rad_m"])
        and float(physics["max_quaternion_norm_error"]) <= float(thresholds["quaternion_norm_error_max"]),
        "linear_momentum": float(physics["max_linear_momentum_body_inertial_kg_m_s"]) <= float(thresholds["linear_momentum_residual_max_kg_m_s"]),
        "angular_momentum": float(physics["max_angular_momentum_body_inertial_kg_m2_s"]) <= float(thresholds["angular_momentum_about_fixed_inertial_origin_residual_max_kg_m2_s"]),
        "work_energy": float(physics["max_work_energy_absolute_J"]) <= float(thresholds["work_energy_absolute_max_J"])
        and float(physics["max_work_energy_relative"]) <= float(thresholds["work_energy_relative_max"]),
        "rank_sigma": float(row["step_sigma_min_dimensionless"]) >= float(thresholds["step_sigma_min_dimensionless_min"]),
        "qp_lock": float(qp["qP_position_lock_max_abs_m"]) <= float(thresholds["qP_position_lock_max_abs_m"])
        and float(qp["dqP_lock_max_abs_m_s"]) <= float(thresholds["dqP_lock_max_abs_m_s"]),
        "kkt": float(row["max_constraint_acceleration_abs_m_s2"]) <= float(thresholds["ddqP_lock_max_abs_m_s2"])
        and float(row["max_kkt_equilibrium_R_abs_Nm"]) <= float(thresholds["kkt_equilibrium_R_max_abs_Nm"])
        and float(row["max_kkt_equilibrium_P_abs_N"]) <= float(thresholds["kkt_equilibrium_P_max_abs_N"])
        and float(row["max_kkt_vs_elimination_acceleration_R_abs_rad_s2"]) <= float(thresholds["kkt_vs_elimination_acceleration_R_max_abs_rad_s2"])
        and float(row["max_kkt_reaction_cross_abs_N"]) <= float(thresholds["kkt_reaction_cross_max_abs_N"])
        and float(row["max_constraint_reaction_power_abs_W"]) <= float(thresholds["constraint_reaction_power_max_abs_W"]),
        "computed_acceleration": float(row["max_computed_acceleration_closure_abs_rad_s2"]) <= float(thresholds["computed_acceleration_closure_max_abs_rad_s2"]),
    }


def build_candidate(project_root: Path = PROJECT_ROOT) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract = load_contract()
    source_binding = validate_source_pins(contract, project_root)
    upstream = load_upstream(contract, project_root)
    plant_gate = load_json_strict(_pin(contract, "time_varying_plant_gate", project_root))
    metric_gate = load_json_strict(_pin(contract, "task_metric_gate", project_root))
    parent_dynamics_gate = load_json_strict(_pin(contract, "parent_dynamics_gate_hold", project_root))
    parent_control_gate = load_json_strict(_pin(contract, "parent_control_gate_hold", project_root))
    upstream_gate_state = {
        "time_varying_plant_candidate_24_of_24": plant_gate.get("all_checks_pass") is True and plant_gate.get("passed") == plant_gate.get("total") == 24,
        "task_metric_candidate_17_of_17": metric_gate.get("passed") == metric_gate.get("total") == 17,
        "parent_dynamics_hold_retained": parent_dynamics_gate.get("dynamics_engineering_complete") is False and parent_dynamics_gate.get("next_stage_authorized") is False,
        "parent_control_hold_retained": parent_control_gate.get("control_engineering_complete") is False and parent_control_gate.get("next_stage_authorized") is False,
    }
    _require(all(upstream_gate_state.values()), "UPSTREAM_GATE_STATE_MISMATCH")

    scenario_results = [run_scenario(contract, upstream, row) for row in contract["scenarios"]]
    comparisons = comparison_audit(scenario_results)
    negative = run_negative_controls(contract, upstream)
    thresholds = contract["thresholds"]
    all_audits = [row[solver + "_audit"] for row in scenario_results for solver in ("rk4", "dop853")]
    audit_checks = [_audit_passes(row, thresholds) for row in all_audits]
    solver_checks = []
    for row in scenario_results:
        cross = row["solver_cross"]
        solver_checks.append(
            float(cross["qR_max_abs_rad"]) <= float(thresholds["rk4_dop853_qR_max_abs_rad"])
            and float(cross["dqR_max_abs_rad_s"]) <= float(thresholds["rk4_dop853_dqR_max_abs_rad_s"])
            and float(cross["base_position_max_abs_m"]) <= float(thresholds["rk4_dop853_base_position_max_abs_m"])
            and float(cross["base_attitude_max_rad"]) <= float(thresholds["rk4_dop853_base_attitude_max_rad"])
            and float(cross["weighted_task_error_max_abs_per_s"]) <= float(thresholds["rk4_dop853_weighted_task_error_max_abs_per_s"])
        )
    comparison_pass = all(
        row["same_task_dimension_reference_units_frame_metric"]
        and float(row["final_error_ratio_controlled_to_uncontrolled"]) <= float(thresholds["controlled_final_error_ratio_to_same_task_uncontrolled_max"])
        and float(row["rms_error_ratio_controlled_to_uncontrolled"]) <= float(thresholds["controlled_rms_error_ratio_to_same_task_uncontrolled_max"])
        for row in comparisons.values()
    )
    authority_boundaries = {
        "parent_gate_reissued": False,
        "parent_gate_credit": False,
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
    }
    checks = {
        "G01_CONTRACT_PREDECLARED_AND_NOT_SELF_CERTIFYING": validate_contract(contract)["valid"],
        "G02_EXECUTION_MEMORY_GATE_PASSED_WITHOUT_SCIENTIFIC_AUTHORITY": contract["execution_resource_admission"]["runtime_pre_solve_pass"] is True and contract["execution_resource_admission"]["scientific_or_release_authority"] is False,
        "G03_ALL_TEN_DIRECT_SOURCE_PINS_EXACT": source_binding["all_match"] and source_binding["matched"] == 10,
        "G04_UPSTREAM_TRANSITIVE_SOURCE_AND_METRIC_PARAMETER_LOCKS_EXACT": upstream["plant_binding"]["all_match"] and upstream["metric_binding"]["all_match"] and all(upstream["upstream_parameter_lock"].values()),
        "G05_UPSTREAM_CANDIDATE_GATES_AND_PARENT_HOLDS_EXACT": all(upstream_gate_state.values()),
        "G06_FOUR_SCENARIOS_TWO_SAME_DIMENSION_COMPARISON_PAIRS": len(scenario_results) == 4 and len(comparisons) == 2,
        "G07_PER_STAGE_DIMENSIONLESS_RANK_SIGMA_AND_FIXED_SEED_LOCAL_BASIS_GUARD": all(row["rank_sigma"] for row in audit_checks)
        and all(row["approach_basis_seed_switch_count"] <= thresholds["approach_basis_seed_switch_count_max"] for row in all_audits)
        and all(row["approach_basis_cross_norm_min"] >= thresholds["approach_basis_fixed_seed_cross_norm_min"] for row in all_audits),
        "G08_CONTROLLED_5D_AND_6D_WEIGHTED_ERROR_IMPROVE_PREDECLARED_RATIOS": comparison_pass,
        "G09_RK4_DOP853_STATE_AND_WEIGHTED_TASK_CROSS": all(solver_checks),
        "G10_SEPARATE_LINEAR_MOMENTUM_LEDGER": all(row["linear_momentum"] for row in audit_checks),
        "G11_SEPARATE_ANGULAR_MOMENTUM_ABOUT_FIXED_INERTIAL_ORIGIN_LEDGER": all(row["angular_momentum"] for row in audit_checks),
        "G12_CONTROL_WORK_TO_KINETIC_ENERGY_LEDGER": all(row["work_energy"] for row in audit_checks),
        "G13_QP_POSITION_RATE_AND_ACCELERATION_LOCK": all(row["qp_lock"] and row["kkt"] for row in audit_checks),
        "G14_CONSTRAINT_REACTION_ZERO_POWER_AND_NOT_CONTACT": all(row["max_constraint_reaction_power_abs_W"] <= thresholds["constraint_reaction_power_max_abs_W"] and row["constraint_reaction_is_not_contact_force"] for row in all_audits),
        "G15_COMPUTED_ACCELERATION_CLOSURE": all(row["computed_acceleration"] for row in audit_checks),
        "G16_FINITE_LIMITED_UNIT_QUATERNION_HISTORY": all(row["finite_limits_quaternion"] for row in audit_checks),
        "G17_DETERMINISTIC_RK4_REPLAY": all(row["deterministic_replay"]["byte_identical_canonical_replay"] for row in scenario_results),
        "G18_NEGATIVE_CONTROLS_FAIL_CLOSED": negative["all_pass"] and negative["passed"] >= negative["minimum_required"],
        "G19_ROOT_FRAME_RATE_ONLY_SEMANTICS_NO_POSE_OR_ATTITUDE_CLAIM": contract["task_semantics"]["reference_is_inertial_trajectory"] is False and contract["task_semantics"]["pose_or_attitude_tracking_claim_allowed"] is False,
        "G20_ALL_DOWNSTREAM_AUTHORITY_BOUNDARIES_FALSE": all(value is False for value in authority_boundaries.values()),
    }
    passed = sum(bool(value) for value in checks.values())
    gate_passed = passed == len(checks)
    evidence = {
        "schema": "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_EVIDENCE_V1",
        "scope": contract["authority_scope"],
        "task_semantics": contract["task_semantics"],
        "execution_resource_admission": contract["execution_resource_admission"],
        "source_binding": source_binding,
        "upstream_transitive_binding": {"plant": upstream["plant_binding"], "metric": upstream["metric_binding"]},
        "upstream_metric_parameter_lock": upstream["upstream_parameter_lock"],
        "upstream_gate_state": upstream_gate_state,
        "scenarios": scenario_results,
        "same_dimension_comparisons": comparisons,
        "authority_boundaries": authority_boundaries,
    }
    gate = {
        "schema": "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_GATE_V1",
        "technical_verdict": "TIME_DOMAIN_TWIST_TRACKING_DIAGNOSTIC_EXECUTED__PARENT_GATES_UNCHANGED__NO_CONTROL_RELEASE" if gate_passed else "TIME_DOMAIN_TWIST_TRACKING_DIAGNOSTIC_REPEAT_REQUIRED__PARENT_GATES_UNCHANGED__NO_CONTROL_RELEASE",
        "maximum_claim": "TIME_DOMAIN_TWIST_TRACKING_DIAGNOSTIC_EXECUTED" if gate_passed else "TIME_DOMAIN_TWIST_TRACKING_DIAGNOSTIC_ATTEMPTED_REPEAT_REQUIRED",
        "checks": checks,
        "summary": {"passed": passed, "total": len(checks), "failed": [name for name, value in checks.items() if not value]},
        "gate_passed": gate_passed,
        "time_domain_diagnostic_executed": True,
        "root_frame_twist_rate_diagnostic_pass": gate_passed,
        "parent_dynamics_gate_reissued": False,
        "parent_control_gate_reissued": False,
        "authority_boundaries": authority_boundaries,
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    return to_builtin(evidence), to_builtin(gate), to_builtin(negative)
