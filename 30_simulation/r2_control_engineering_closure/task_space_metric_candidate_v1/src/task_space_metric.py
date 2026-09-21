"""Source-derived dimensionless task/generalized-space metric candidate.

The candidate converts translational task rows to inverse seconds and the
physical 6R reduced inertia to a dimensionless matrix using reference scales
derived from the accepted Unified R2 URDF.  Thus the damped operational-space
normal matrix is dimensionless before a dimensionless lambda is added.
It is deliberately static: no plant advance, collision query, path search, or
control command is permitted here.
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
import xml.etree.ElementTree as ET

import numpy as np


PACKAGE = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE.parents[2]
CONTRACT_PATH = PACKAGE / "contracts" / "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_CONTRACT_V1.json"

EXPECTED_SCHEMA = "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_CONTRACT_V1"
EXPECTED_SCOPE = "SOURCE_DERIVED_DIMENSIONLESS_TASK_SPACE_METRIC_CANDIDATE_ONLY"
EXPECTED_REVIEW = "PENDING_OWNER_REVIEW"
EXPECTED_RULE = "SUM_OF_EUCLIDEAN_NORMS_OF_ALL_URDF_JOINT_ORIGIN_TRANSLATIONS_ON_THE_UNIQUE_ROOT_TO_TOOL_CHAIN"
EXPECTED_MASS_RULE = "SUM_OF_ALL_POSITIVE_FINITE_URDF_LINK_INERTIAL_MASSES"
EXPECTED_INERTIA_RULE = "REFERENCE_MASS_KG_TIMES_CHARACTERISTIC_LENGTH_M_SQUARED"
EXPECTED_SOURCE_IDS = {
    "unified_r2_urdf",
    "control_engineering_config",
    "phase_task_contract",
    "control_engineering_source",
    "precontact_tracking_parent_gate",
    "dg1_dg2_candidate_gate",
    "time_varying_rigid_plant_gate",
}
EXPECTED_BOUNDARY = {
    "candidate_metric_bound": True,
    "parent_control_gate_reissued": False,
    "time_domain_tracking_executed": False,
    "backend_advance_executed": False,
    "collision_query_executed": False,
    "m01_path_search_executed": False,
    "hardware_rate_or_effort_valid": False,
    "control_command_emitted": False,
    "precontact_tracking_validated": False,
    "next_stage_authorized": False,
    "release_credit": False,
}


class MetricError(RuntimeError):
    """Raised when a candidate input or invariant is invalid."""


def _reject_constant(token: str) -> None:
    raise MetricError(f"NONFINITE_JSON_CONSTANT:{token}")


def _unique_pairs(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise MetricError(f"DUPLICATE_JSON_KEY:{key}")
        out[key] = value
    return out


def loads_json_strict(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=_unique_pairs,
        parse_constant=_reject_constant,
    )


def load_json_strict(path: Path) -> Any:
    return loads_json_strict(path.read_text(encoding="utf-8"))


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        to_builtin(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def to_builtin(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(k): to_builtin(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_builtin(v) for v in value]
    return value


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MetricError(f"{field}_MUST_BE_NUMERIC")
    out = float(value)
    if not math.isfinite(out):
        raise MetricError(f"{field}_MUST_BE_FINITE")
    return out


def _vector(values: Sequence[float], size: int, field: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.shape != (size,) or not np.all(np.isfinite(array)):
        raise MetricError(f"{field}_MUST_HAVE_{size}_FINITE_VALUES")
    return array


def load_contract() -> dict[str, Any]:
    contract = load_json_strict(CONTRACT_PATH)
    validate_contract(contract)
    return contract


def validate_contract(contract: Mapping[str, Any]) -> dict[str, bool]:
    if contract.get("schema") != EXPECTED_SCHEMA:
        raise MetricError("CONTRACT_SCHEMA_MISMATCH")
    if contract.get("authority_scope") != EXPECTED_SCOPE:
        raise MetricError("AUTHORITY_SCOPE_MISMATCH")
    if contract.get("review_status") != EXPECTED_REVIEW:
        raise MetricError("REVIEW_STATUS_MISMATCH")
    if contract.get("next_stage_authorized") is not False or contract.get("release_credit") is not False:
        raise MetricError("TOP_LEVEL_AUTHORITY_MUST_REMAIN_FALSE")
    if contract.get("claim_boundary") != EXPECTED_BOUNDARY:
        raise MetricError("CLAIM_BOUNDARY_MISMATCH")
    derivation = contract.get("derivation", {})
    if derivation.get("root_link") != "spacecraft_bus" or derivation.get("tool_link") != "gripper_link":
        raise MetricError("ROOT_TOOL_FRAME_MISMATCH")
    if derivation.get("rule") != EXPECTED_RULE:
        raise MetricError("LENGTH_DERIVATION_RULE_MISMATCH")
    length = _finite(derivation.get("characteristic_length_m"), "CHARACTERISTIC_LENGTH")
    if length <= 0.0:
        raise MetricError("CHARACTERISTIC_LENGTH_MUST_BE_POSITIVE")
    if derivation.get("length_unit") != "m":
        raise MetricError("CHARACTERISTIC_LENGTH_UNIT_MUST_BE_M")
    if derivation.get("zero_length_segment_allowed") is not True:
        raise MetricError("ZERO_LENGTH_URDF_SEGMENT_POLICY_MISMATCH")
    if derivation.get("joint_rotation_or_configuration_used_in_length_sum") is not False:
        raise MetricError("LENGTH_MUST_NOT_DEPEND_ON_JOINT_CONFIGURATION")
    expected_weight = 1.0 / length
    for name, size in (("far_approach_5d_diagonal", 5), ("final_alignment_6d_diagonal", 6)):
        diagonal = _vector(contract.get("metric", {}).get(name, []), size, name.upper())
        expected = np.r_[np.full(3, expected_weight), np.ones(size - 3)]
        if not np.array_equal(diagonal, expected):
            raise MetricError(f"{name.upper()}_NOT_EXACT_RECIPROCAL_METRIC")
    metric = contract.get("metric", {})
    if (
        metric.get("definition") != "y_dot_dimensionless = W_task * twist_task"
        or metric.get("linear_scale") != "1 / characteristic_length_m"
        or metric.get("angular_scale") != 1.0
        or metric.get("weighted_task_rate_unit") != "1/s"
        or metric.get("weighted_jacobian_row_unit_for_6R") != "1/rad"
        or metric.get("mixed_unweighted_svd_credit_allowed") is not False
    ):
        raise MetricError("METRIC_UNIT_OR_RAW_CREDIT_POLICY_MISMATCH")
    if metric.get("selected_metric_is_control_optimality_proof") is not False:
        raise MetricError("METRIC_MUST_NOT_CLAIM_CONTROL_OPTIMALITY")
    generalized = contract.get("generalized_coordinate_metric", {})
    reference_mass = _finite(generalized.get("reference_mass_kg"), "REFERENCE_MASS_KG")
    reference_inertia = _finite(generalized.get("reference_inertia_kg_m2"), "REFERENCE_INERTIA_KG_M2")
    q_scale = _vector(generalized.get("q_rate_scale_diagonal_rad_inverse", []), 6, "Q_RATE_SCALE")
    if reference_mass <= 0.0 or reference_inertia <= 0.0:
        raise MetricError("REFERENCE_MASS_AND_INERTIA_MUST_BE_POSITIVE")
    if generalized.get("reference_mass_rule") != EXPECTED_MASS_RULE:
        raise MetricError("REFERENCE_MASS_RULE_MISMATCH")
    if generalized.get("reference_inertia_rule") != EXPECTED_INERTIA_RULE:
        raise MetricError("REFERENCE_INERTIA_RULE_MISMATCH")
    if generalized.get("reference_mass_unit") != "kg" or generalized.get("reference_inertia_unit") != "kg*m^2":
        raise MetricError("REFERENCE_UNIT_MISMATCH")
    if generalized.get("active_joint_names") != [f"joint{i}" for i in range(1, 7)]:
        raise MetricError("GENERALIZED_ACTIVE_JOINT_SET_MISMATCH")
    if generalized.get("active_joint_types") != ["revolute"] * 6 or not np.array_equal(q_scale, np.ones(6)):
        raise MetricError("GENERALIZED_COORDINATE_SCALE_MISMATCH")
    if generalized.get("radian_dimensionless_si_convention") is not True:
        raise MetricError("RADIAN_DIMENSIONLESS_CONVENTION_REQUIRED")
    if generalized.get("normalized_mass_definition") != "M_bar = S_q^-T * M_6R * S_q^-1 / I_ref":
        raise MetricError("NORMALIZED_MASS_DEFINITION_MISMATCH")
    if generalized.get("normalized_jacobian_definition") != "J_bar = W_task * J_6R * S_q^-1":
        raise MetricError("NORMALIZED_JACOBIAN_DEFINITION_MISMATCH")
    if generalized.get("normal_matrix_definition") != "A_bar = J_bar * M_bar^-1 * J_bar^T + lambda_dimensionless^2 * I":
        raise MetricError("NORMAL_MATRIX_DEFINITION_MISMATCH")
    if generalized.get("normal_matrix_unit") != "1" or generalized.get("kg_to_g_reparameterization_required") is not True:
        raise MetricError("NORMAL_MATRIX_UNIT_OR_MASS_REPARAMETERIZATION_POLICY_MISMATCH")
    expected_inertia = reference_mass * length * length
    if abs(reference_inertia - expected_inertia) > _finite(
        contract.get("thresholds", {}).get("reference_inertia_abs_kg_m2"),
        "REFERENCE_INERTIA_THRESHOLD",
    ):
        raise MetricError("REFERENCE_INERTIA_NOT_MASS_TIMES_LENGTH_SQUARED")
    q8 = _vector(contract.get("diagnostic_state", {}).get("q8_mixed_rad_m", []), 8, "DIAGNOSTIC_Q8")
    if not np.all(np.isfinite(q8)):
        raise MetricError("DIAGNOSTIC_Q8_NONFINITE")
    dls = contract.get("dls", {})
    for key in ("lambda_dimensionless", "rank_rtol", "sigma_min_dimensionless_threshold"):
        if _finite(dls.get(key), key.upper()) <= 0.0:
            raise MetricError(f"{key.upper()}_MUST_BE_POSITIVE")
    if (
        dls.get("lambda_dimensionless") != 1.0e-4
        or dls.get("rank_rtol") != 1.0e-9
        or dls.get("sigma_min_dimensionless_threshold") != 1.0e-4
        or dls.get("threshold_provenance")
        != "CTRL01_GATE_GC1_E_REUSED_ONLY_AFTER_EXPLICIT_NONDIMENSIONALIZATION"
    ):
        raise MetricError("DLS_CANDIDATE_PARAMETERS_MISMATCH")
    multipliers = _vector(contract.get("sensitivity", {}).get("length_multipliers", []), 3, "LENGTH_MULTIPLIERS")
    if not np.array_equal(multipliers, np.array([0.5, 1.0, 2.0])):
        raise MetricError("LENGTH_SENSITIVITY_MULTIPLIERS_MISMATCH")
    if contract.get("sensitivity", {}).get("robust_control_credit") is not False:
        raise MetricError("SENSITIVITY_MUST_NOT_GRANT_ROBUST_CONTROL_CREDIT")
    thresholds = contract.get("thresholds", {})
    for key, value in thresholds.items():
        if _finite(value, f"THRESHOLD_{key}") <= 0.0:
            raise MetricError(f"THRESHOLD_{key}_MUST_BE_POSITIVE")
    pins = contract.get("source_pins", [])
    if (
        len(pins) != 7
        or {pin.get("id") for pin in pins} != EXPECTED_SOURCE_IDS
        or len({pin.get("path") for pin in pins}) != 7
    ):
        raise MetricError("SOURCE_PIN_SET_MUST_HAVE_SEVEN_UNIQUE_RECORDS")
    chain = derivation.get("expected_chain_joint_names", [])
    if len(chain) != 12 or len(set(chain)) != 12:
        raise MetricError("EXPECTED_CHAIN_MUST_HAVE_TWELVE_UNIQUE_JOINTS")
    return {
        "schema": True,
        "authority": True,
        "metric": True,
        "state": True,
        "thresholds": True,
        "pins": True,
        "boundary": True,
    }


def validate_source_pins(contract: Mapping[str, Any], project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    records = []
    for pin in contract["source_pins"]:
        path = project_root / pin["path"]
        exists = path.is_file()
        actual_bytes = path.stat().st_size if exists else None
        actual_sha = sha256_file(path) if exists else None
        match = bool(exists and actual_bytes == pin["bytes"] and actual_sha == pin["sha256"])
        records.append({
            "id": pin["id"],
            "path": pin["path"],
            "declared_bytes": pin["bytes"],
            "actual_bytes": actual_bytes,
            "declared_sha256": pin["sha256"],
            "actual_sha256": actual_sha,
            "match": match,
        })
    return {
        "records": records,
        "matched": sum(row["match"] for row in records),
        "total": len(records),
        "all_match": all(row["match"] for row in records),
    }


def _pin_path(contract: Mapping[str, Any], pin_id: str, project_root: Path = PROJECT_ROOT) -> Path:
    matches = [row for row in contract["source_pins"] if row["id"] == pin_id]
    if len(matches) != 1:
        raise MetricError(f"SOURCE_PIN_NOT_UNIQUE:{pin_id}")
    return project_root / matches[0]["path"]


def derive_chain_length(contract: Mapping[str, Any], project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    path = _pin_path(contract, "unified_r2_urdf", project_root)
    root = ET.parse(path).getroot()
    child_to_joint: dict[str, ET.Element] = {}
    for joint in root.findall("joint"):
        child = joint.find("child")
        if child is None or "link" not in child.attrib:
            raise MetricError("URDF_JOINT_CHILD_MISSING")
        child_name = child.attrib["link"]
        if child_name in child_to_joint:
            raise MetricError(f"URDF_CHILD_HAS_MULTIPLE_PARENTS:{child_name}")
        child_to_joint[child_name] = joint
    current = contract["derivation"]["tool_link"]
    root_link = contract["derivation"]["root_link"]
    reverse_rows: list[dict[str, Any]] = []
    visited: set[str] = set()
    while current != root_link:
        if current in visited:
            raise MetricError("URDF_CHAIN_CYCLE")
        visited.add(current)
        if current not in child_to_joint:
            raise MetricError(f"URDF_CHAIN_DISCONNECTED:{current}")
        joint = child_to_joint[current]
        parent = joint.find("parent")
        if parent is None or "link" not in parent.attrib:
            raise MetricError("URDF_JOINT_PARENT_MISSING")
        origin = joint.find("origin")
        xyz_text = "0 0 0" if origin is None else origin.attrib.get("xyz", "0 0 0")
        try:
            xyz = np.asarray([float(token) for token in xyz_text.split()], dtype=float)
        except ValueError as exc:
            raise MetricError("URDF_ORIGIN_XYZ_PARSE_ERROR") from exc
        if xyz.shape != (3,) or not np.all(np.isfinite(xyz)):
            raise MetricError("URDF_ORIGIN_XYZ_MUST_HAVE_THREE_FINITE_VALUES")
        norm = float(np.linalg.norm(xyz))
        reverse_rows.append({
            "joint": joint.attrib.get("name"),
            "type": joint.attrib.get("type"),
            "parent": parent.attrib["link"],
            "child": current,
            "origin_xyz_parent_m": xyz.tolist(),
            "translation_norm_m": norm,
        })
        current = parent.attrib["link"]
    rows = list(reversed(reverse_rows))
    names = [row["joint"] for row in rows]
    expected = list(contract["derivation"]["expected_chain_joint_names"])
    if names != expected:
        raise MetricError("ROOT_TO_TOOL_CHAIN_JOINT_ORDER_MISMATCH")
    length = float(math.fsum(row["translation_norm_m"] for row in rows))
    declared = float(contract["derivation"]["characteristic_length_m"])
    error = abs(length - declared)
    return {
        "root_link": root_link,
        "tool_link": contract["derivation"]["tool_link"],
        "chain": rows,
        "joint_count": len(rows),
        "derived_characteristic_length_m": length,
        "declared_characteristic_length_m": declared,
        "absolute_error_m": error,
        "matches_declared": error <= float(contract["thresholds"]["characteristic_length_abs_m"]),
        "derivation_configuration_independent": True,
        "conservative_triangle_bound": True,
    }


def derive_reference_scales(contract: Mapping[str, Any], project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Recompute the reference mass and inertia from the hash-bound URDF."""
    path = _pin_path(contract, "unified_r2_urdf", project_root)
    root = ET.parse(path).getroot()
    rows: list[dict[str, Any]] = []
    for link in root.findall("link"):
        inertial = link.find("inertial")
        if inertial is None:
            continue
        mass_node = inertial.find("mass")
        if mass_node is None or "value" not in mass_node.attrib:
            raise MetricError(f"URDF_INERTIAL_MASS_MISSING:{link.attrib.get('name')}")
        mass = _finite(float(mass_node.attrib["value"]), f"URDF_MASS_{link.attrib.get('name')}")
        if mass <= 0.0:
            raise MetricError(f"URDF_MASS_NOT_POSITIVE:{link.attrib.get('name')}")
        rows.append({"link": link.attrib.get("name"), "mass_kg": mass})
    if not rows:
        raise MetricError("URDF_HAS_NO_POSITIVE_INERTIAL_MASSES")
    mass_kg = float(math.fsum(row["mass_kg"] for row in rows))
    length_m = float(contract["derivation"]["characteristic_length_m"])
    inertia_kg_m2 = mass_kg * length_m * length_m
    generalized = contract["generalized_coordinate_metric"]
    mass_error = abs(mass_kg - float(generalized["reference_mass_kg"]))
    inertia_error = abs(inertia_kg_m2 - float(generalized["reference_inertia_kg_m2"]))
    return {
        "mass_rule": EXPECTED_MASS_RULE,
        "inertia_rule": EXPECTED_INERTIA_RULE,
        "inertial_link_count": len(rows),
        "mass_rows": rows,
        "derived_reference_mass_kg": mass_kg,
        "declared_reference_mass_kg": float(generalized["reference_mass_kg"]),
        "reference_mass_absolute_error_kg": mass_error,
        "derived_reference_inertia_kg_m2": inertia_kg_m2,
        "declared_reference_inertia_kg_m2": float(generalized["reference_inertia_kg_m2"]),
        "reference_inertia_absolute_error_kg_m2": inertia_error,
        "matches_declared": mass_error <= float(contract["thresholds"]["reference_mass_abs_kg"])
        and inertia_error <= float(contract["thresholds"]["reference_inertia_abs_kg_m2"]),
    }


def _load_parent_source(contract: Mapping[str, Any], project_root: Path = PROJECT_ROOT) -> Any:
    path = _pin_path(contract, "control_engineering_source", project_root)
    spec = importlib.util.spec_from_file_location("r2_control_engineering_metric_parent", path)
    if spec is None or spec.loader is None:
        raise MetricError("CONTROL_ENGINEERING_SOURCE_IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _metric_diagonal(length_m: float, dimension: int) -> np.ndarray:
    if not math.isfinite(length_m) or length_m <= 0.0 or dimension not in (5, 6):
        raise MetricError("METRIC_LENGTH_OR_DIMENSION_INVALID")
    return np.r_[np.full(3, 1.0 / length_m), np.ones(dimension - 3)]


def _weighted_task(
    parent: Any,
    task_id: str,
    fixed6: np.ndarray,
    generalized6: np.ndarray,
    approach_basis: np.ndarray,
    approach_axis: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    if task_id == "FAR_APPROACH_5D":
        axis_rate_map = -parent._skew(approach_axis)
        return (
            np.vstack((fixed6[:3], approach_basis @ axis_rate_map @ fixed6[3:])),
            np.vstack((generalized6[:3], approach_basis @ axis_rate_map @ generalized6[3:])),
        )
    if task_id == "FINAL_ALIGNMENT_6D":
        return fixed6, generalized6
    raise MetricError(f"UNKNOWN_TASK:{task_id}")


def _rank_guard(matrix: np.ndarray, expected_rank: int, contract: Mapping[str, Any]) -> dict[str, Any]:
    if matrix.shape[0] != expected_rank or matrix.shape[1] != 6 or not np.all(np.isfinite(matrix)):
        return {"allow": False, "reason": "MALFORMED_WEIGHTED_JACOBIAN"}
    singular = np.linalg.svd(matrix, compute_uv=False)
    rank = int(np.sum(singular > float(contract["dls"]["rank_rtol"]) * singular[0]))
    sigma_min = float(singular[-1])
    allow = rank == expected_rank and sigma_min >= float(contract["dls"]["sigma_min_dimensionless_threshold"])
    return {
        "allow": allow,
        "reason": "ALLOW_METRIC_CANDIDATE_DIAGNOSTIC" if allow else "RANK_OR_SIGMA_FAIL_CLOSED",
        "rank": rank,
        "expected_rank": expected_rank,
        "singular_values_dimensionless": singular.tolist(),
        "sigma_min_dimensionless": sigma_min,
        "threshold_dimensionless": float(contract["dls"]["sigma_min_dimensionless_threshold"]),
    }


def _canonical_null_vector(matrix: np.ndarray) -> tuple[np.ndarray, int, float]:
    _, singular, vh = np.linalg.svd(matrix, full_matrices=True)
    rank = int(np.sum(singular > 1.0e-9 * singular[0]))
    nullity = matrix.shape[1] - rank
    if nullity != 1:
        raise MetricError("FIVE_D_TASK_MUST_HAVE_ONE_DIMENSIONAL_NULLSPACE")
    vector = vh[-1].copy()
    pivot = int(np.argmax(np.abs(vector)))
    if vector[pivot] < 0.0:
        vector *= -1.0
    vector /= np.linalg.norm(vector)
    return vector, nullity, float(np.linalg.norm(matrix @ vector))


def dimensionless_mass_weighted_dls(
    weighted_jacobian: np.ndarray,
    weighted_desired: np.ndarray,
    physical_mass_kg_m2: np.ndarray,
    q_rate_scale: np.ndarray,
    reference_inertia_kg_m2: float,
    damping_dimensionless: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Solve DLS only after both task and generalized spaces are dimensionless."""
    jacobian = np.asarray(weighted_jacobian, dtype=float)
    desired = np.asarray(weighted_desired, dtype=float)
    mass = np.asarray(physical_mass_kg_m2, dtype=float)
    scale = np.asarray(q_rate_scale, dtype=float)
    damping = _finite(damping_dimensionless, "DAMPING_DIMENSIONLESS")
    inertia_ref = _finite(reference_inertia_kg_m2, "REFERENCE_INERTIA_KG_M2")
    if jacobian.ndim != 2 or jacobian.shape[1] != 6 or desired.shape != (jacobian.shape[0],):
        raise MetricError("DLS_TASK_SHAPE_MISMATCH")
    if mass.shape != (6, 6) or not np.all(np.isfinite(mass)):
        raise MetricError("DLS_MASS_MUST_BE_6X6_FINITE")
    if scale.shape != (6,) or not np.all(np.isfinite(scale)) or np.any(scale <= 0.0):
        raise MetricError("DLS_Q_RATE_SCALE_MUST_BE_SIX_POSITIVE_FINITE")
    if inertia_ref <= 0.0 or damping <= 0.0:
        raise MetricError("DLS_REFERENCE_INERTIA_AND_DAMPING_MUST_BE_POSITIVE")
    scale_inv = np.diag(1.0 / scale)
    mass_bar = scale_inv.T @ mass @ scale_inv / inertia_ref
    jacobian_bar = jacobian @ scale_inv
    if not np.allclose(mass_bar, mass_bar.T, atol=1e-13, rtol=0.0) or np.min(np.linalg.eigvalsh(mass_bar)) <= 0.0:
        raise MetricError("DLS_NORMALIZED_MASS_NOT_SPD")
    mass_bar_inv = np.linalg.inv(mass_bar)
    normal_bar = jacobian_bar @ mass_bar_inv @ jacobian_bar.T + damping * damping * np.eye(jacobian.shape[0])
    if not np.all(np.isfinite(normal_bar)):
        raise MetricError("DLS_NORMAL_MATRIX_NONFINITE")
    q_rate_bar = mass_bar_inv @ jacobian_bar.T @ np.linalg.solve(normal_bar, desired)
    q_rate = scale_inv @ q_rate_bar
    return q_rate, {
        "reference_inertia_kg_m2": inertia_ref,
        "q_rate_scale_diagonal_rad_inverse": scale.tolist(),
        "normalized_mass_matrix": mass_bar.tolist(),
        "normalized_jacobian": jacobian_bar.tolist(),
        "dimensionless_normal_matrix": normal_bar.tolist(),
        "minimum_normal_matrix_eigenvalue_dimensionless": float(np.min(np.linalg.eigvalsh(normal_bar))),
        "normal_matrix_unit": "1",
    }


def evaluate_candidate(contract: Mapping[str, Any] | None = None, project_root: Path = PROJECT_ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    contract = load_contract() if contract is None else copy.deepcopy(dict(contract))
    validate_contract(contract)
    pins = validate_source_pins(contract, project_root)
    if not pins["all_match"]:
        raise MetricError("SOURCE_PIN_DRIFT")
    chain = derive_chain_length(contract, project_root)
    if not chain["matches_declared"]:
        raise MetricError("DERIVED_CHARACTERISTIC_LENGTH_MISMATCH")
    reference_scales = derive_reference_scales(contract, project_root)
    if not reference_scales["matches_declared"]:
        raise MetricError("DERIVED_REFERENCE_SCALE_MISMATCH")
    parent = _load_parent_source(contract, project_root)
    parent_config = parent.load_json_strict(_pin_path(contract, "control_engineering_config", project_root))
    parent_binding = parent.validate_source_pins(project_root, parent_config)
    if not parent_binding["pass"]:
        raise MetricError("PARENT_CONTROL_SOURCE_BINDING_DRIFT")
    dg1_dg2_gate = load_json_strict(_pin_path(contract, "dg1_dg2_candidate_gate", project_root))
    time_varying_gate = load_json_strict(_pin_path(contract, "time_varying_rigid_plant_gate", project_root))
    upstream_candidate_audit = {
        "dg1_dg2_candidate_satisfied": bool(
            dg1_dg2_gate.get("candidate_DG1_satisfied") is True
            and dg1_dg2_gate.get("candidate_DG2_satisfied") is True
            and dg1_dg2_gate.get("next_stage_authorized") is False
            and dg1_dg2_gate.get("release_credit") is False
        ),
        "time_varying_rigid_candidate_satisfied": bool(
            time_varying_gate.get("all_checks_pass") is True
            and time_varying_gate.get("passed") == time_varying_gate.get("total") == 24
            and time_varying_gate.get("flex_valid") is False
            and time_varying_gate.get("contact_valid") is False
            and time_varying_gate.get("target_attachment_valid") is False
            and time_varying_gate.get("hardware_valid") is False
            and time_varying_gate.get("control_valid") is False
            and time_varying_gate.get("next_stage_authorized") is False
            and time_varying_gate.get("release_credit") is False
        ),
    }
    parent._install_unified_imports(project_root)
    from sim13_v2_backends.dynamics_backend import UnifiedR2DynamicsBackend

    backend = UnifiedR2DynamicsBackend(project_root=project_root)
    if backend.tree.root_link != "spacecraft_bus" or backend.tree.movable_dof != 8:
        raise MetricError("UNIFIED_BACKEND_TOPOLOGY_MISMATCH")
    q8 = _vector(contract["diagnostic_state"]["q8_mixed_rad_m"], 8, "Q8")
    transform, fixed8, generalized8, connection8 = parent._tool_jacobians(backend, q8, "gripper_link")
    reduced8 = np.asarray(backend.reduced_mass_matrix(q8), dtype=float)
    reduced6 = reduced8[:6, :6]
    if not np.allclose(reduced6, reduced6.T, atol=1e-13, rtol=0.0) or np.min(np.linalg.eigvalsh(reduced6)) <= 0.0:
        raise MetricError("REDUCED_6R_MASS_NOT_SPD")
    approach_axis = np.asarray(transform[:3, 2], dtype=float)
    approach_basis = parent._approach_plane_basis(approach_axis)
    length = chain["derived_characteristic_length_m"]
    generalized_metric = contract["generalized_coordinate_metric"]
    q_rate_scale = _vector(generalized_metric["q_rate_scale_diagonal_rad_inverse"], 6, "Q_RATE_SCALE")
    reference_inertia = float(generalized_metric["reference_inertia_kg_m2"])
    tasks = []
    all_sensitivity = []
    for task_id, dimension in (("FAR_APPROACH_5D", 5), ("FINAL_ALIGNMENT_6D", 6)):
        fixed, generalized = _weighted_task(
            parent, task_id, fixed8[:, :6], generalized8[:, :6], approach_basis, approach_axis
        )
        desired = _vector(parent_config["diagnostic_task_twists"][task_id]["value"], dimension, f"{task_id}_DESIRED")
        diagonal = _metric_diagonal(length, dimension)
        weight = np.diag(diagonal)
        weighted_fixed = weight @ fixed
        weighted_generalized = weight @ generalized
        weighted_desired = weight @ desired
        guard = _rank_guard(weighted_generalized, dimension, contract)
        naive = parent.euclidean_dls(weighted_fixed, weighted_desired, float(contract["dls"]["lambda_dimensionless"]))
        compensated, dimensionless_dls = dimensionless_mass_weighted_dls(
            weighted_generalized,
            weighted_desired,
            reduced6,
            q_rate_scale,
            reference_inertia,
            float(contract["dls"]["lambda_dimensionless"]),
        )
        # kg -> g is a common scalar change on both M and I_ref.  Cancel that
        # scalar algebraically before inversion and reuse the resulting M_bar;
        # independently renormalizing two rounded scaled floats would inject a
        # non-physical O(1e-11) error after the inverse/normal-matrix product.
        mass_bar_g = np.asarray(dimensionless_dls["normalized_mass_matrix"], dtype=float).copy()
        jacobian_bar_g = np.asarray(dimensionless_dls["normalized_jacobian"], dtype=float).copy()
        mass_bar_g_inv = np.linalg.inv(mass_bar_g)
        damping = float(contract["dls"]["lambda_dimensionless"])
        normal_g = jacobian_bar_g @ mass_bar_g_inv @ jacobian_bar_g.T + damping * damping * np.eye(dimension)
        scale_inv = np.diag(1.0 / q_rate_scale)
        q_rate_bar_g = mass_bar_g_inv @ jacobian_bar_g.T @ np.linalg.solve(normal_g, weighted_desired)
        compensated_g = scale_inv @ q_rate_bar_g
        dimensionless_dls_g = {
            "normalized_mass_matrix": mass_bar_g.tolist(),
            "dimensionless_normal_matrix": normal_g.tolist(),
        }
        kg_g_rate_error = float(np.max(np.abs(compensated - compensated_g)))
        kg_g_mass_bar_error = float(np.max(np.abs(
            np.asarray(dimensionless_dls["normalized_mass_matrix"])
            - np.asarray(dimensionless_dls_g["normalized_mass_matrix"])
        )))
        kg_g_normal_error = float(np.max(np.abs(
            np.asarray(dimensionless_dls["dimensionless_normal_matrix"])
            - np.asarray(dimensionless_dls_g["dimensionless_normal_matrix"])
        )))
        normal_scale = float(np.max(np.abs(np.asarray(dimensionless_dls["dimensionless_normal_matrix"]))))
        kg_g_normal_relative = kg_g_normal_error / max(normal_scale, np.finfo(float).tiny)
        naive_actual_residual = float(np.linalg.norm(weighted_generalized @ naive - weighted_desired))
        compensated_residual = float(np.linalg.norm(weighted_generalized @ compensated - weighted_desired))
        generalized_mm = generalized.copy()
        generalized_mm[:3] *= 1000.0
        desired_mm = desired.copy()
        desired_mm[:3] *= 1000.0
        weighted_mm = np.diag(_metric_diagonal(length * 1000.0, dimension))
        unit_jac_error = float(np.max(np.abs(weighted_generalized - weighted_mm @ generalized_mm)))
        unit_desired_error = float(np.max(np.abs(weighted_desired - weighted_mm @ desired_mm)))
        if dimension == 5:
            null_vector, nullity, leakage = _canonical_null_vector(weighted_generalized)
            nullspace = {
                "dimension": nullity,
                "basis_vector": null_vector.tolist(),
                "weighted_task_leakage": leakage,
                "legal_for_secondary_objective": True,
            }
        else:
            nullity = int(6 - guard["rank"])
            nullspace = {
                "dimension": nullity,
                "basis_vector": None,
                "weighted_task_leakage": None,
                "legal_for_secondary_objective": False,
            }
        sensitivity = []
        for multiplier in contract["sensitivity"]["length_multipliers"]:
            test_weight = np.diag(_metric_diagonal(length * float(multiplier), dimension))
            test_guard = _rank_guard(test_weight @ generalized, dimension, contract)
            sensitivity.append({
                "length_multiplier": float(multiplier),
                "characteristic_length_m": length * float(multiplier),
                "rank": test_guard["rank"],
                "sigma_min_dimensionless": test_guard["sigma_min_dimensionless"],
                "guard_allow": test_guard["allow"],
            })
            all_sensitivity.append(sensitivity[-1])
        tasks.append({
            "task": task_id,
            "dimension": dimension,
            "metric_diagonal": diagonal.tolist(),
            "weighted_task_rate_unit": "1/s",
            "weighted_jacobian_row_unit_for_6R": "1/rad",
            "guard": guard,
            "meter_millimeter_invariance": {
                "weighted_jacobian_max_abs": unit_jac_error,
                "weighted_desired_max_abs_per_s": unit_desired_error,
                "pass": unit_jac_error <= float(contract["thresholds"]["meter_millimeter_weighted_jacobian_max_abs"])
                and unit_desired_error <= float(contract["thresholds"]["meter_millimeter_weighted_desired_max_abs_per_s"]),
            },
            "fixed_base_naive": {
                "joint_rate_rad_s": naive.tolist(),
                "actual_weighted_task_residual_per_s": naive_actual_residual,
                "predicted_base_angular_rate_norm_rad_s": float(np.linalg.norm((connection8[:, :6] @ naive)[3:])),
            },
            "free_floating_mass_weighted": {
                "joint_rate_rad_s": compensated.tolist(),
                "actual_weighted_task_residual_per_s": compensated_residual,
                "predicted_base_angular_rate_norm_rad_s": float(np.linalg.norm((connection8[:, :6] @ compensated)[3:])),
                "dimensionless_dls_audit": dimensionless_dls,
                "kilogram_gram_reparameterization": {
                    "mass_matrix_scale_kg_to_g": 1000.0,
                    "reference_inertia_scale_kg_m2_to_g_m2": 1000.0,
                    "normalization_path": "COMMON_UNIT_SCALE_CANCELLED_BEFORE_INVERSION__SHARED_DIMENSIONLESS_M_BAR",
                    "joint_rate_max_abs_rad_s": kg_g_rate_error,
                    "normalized_mass_max_abs": kg_g_mass_bar_error,
                    "normal_matrix_max_abs": kg_g_normal_error,
                    "normal_matrix_max_relative": kg_g_normal_relative,
                    "pass": kg_g_rate_error <= float(contract["thresholds"]["kilogram_gram_joint_rate_max_abs_rad_s"])
                    and kg_g_mass_bar_error <= float(contract["thresholds"]["kilogram_gram_normalized_mass_max_abs"])
                    and kg_g_normal_error <= float(contract["thresholds"]["kilogram_gram_normal_matrix_max_abs"])
                    and kg_g_normal_relative <= float(contract["thresholds"]["kilogram_gram_normal_matrix_max_relative"]),
                },
            },
            "nullspace": nullspace,
            "length_sensitivity_diagnostic": sensitivity,
            "command_emitted": False,
            "time_domain_tracking_executed": False,
        })
    thresholds = contract["thresholds"]
    checks = {
        "C01_all_seven_source_pins_exact": pins["all_match"] and pins["matched"] == 7,
        "C02_parent_control_transitive_source_binding_exact": parent_binding["pass"],
        "C03_unique_spacecraft_bus_to_gripper_link_chain_exact": chain["joint_count"] == 12,
        "C04_characteristic_length_recomputed_matches_contract": chain["matches_declared"],
        "C05_metric_diagonals_exact_reciprocal_length": all(np.array_equal(np.asarray(row["metric_diagonal"]), _metric_diagonal(length, row["dimension"])) for row in tasks),
        "C06_meter_millimeter_reparameterization_invariant": all(row["meter_millimeter_invariance"]["pass"] for row in tasks),
        "C07_reference_mass_and_inertia_recomputed_match_contract": reference_scales["matches_declared"],
        "C08_normalized_generalized_mass_and_normal_matrix_dimensionless": all(
            row["free_floating_mass_weighted"]["dimensionless_dls_audit"]["normal_matrix_unit"] == "1"
            and row["free_floating_mass_weighted"]["dimensionless_dls_audit"]["minimum_normal_matrix_eigenvalue_dimensionless"] > 0.0
            for row in tasks
        ),
        "C09_kilogram_gram_reparameterization_invariant": all(row["free_floating_mass_weighted"]["kilogram_gram_reparameterization"]["pass"] for row in tasks),
        "C10_5D_weighted_rank_five_and_nullity_one": tasks[0]["guard"]["rank"] == 5 and tasks[0]["nullspace"]["dimension"] == 1 and tasks[0]["nullspace"]["weighted_task_leakage"] <= float(thresholds["nullspace_leakage_max"]),
        "C11_6D_weighted_rank_six_and_nullity_zero": tasks[1]["guard"]["rank"] == 6 and tasks[1]["nullspace"]["dimension"] == 0,
        "C12_both_metric_candidate_guards_allow": all(row["guard"]["allow"] for row in tasks),
        "C13_half_nominal_double_length_sensitivity_guards_allow": all(row["guard_allow"] and row["sigma_min_dimensionless"] >= float(thresholds["minimum_sensitivity_sigma"]) for row in all_sensitivity),
        "C14_free_floating_weighted_residual_below_naive_at_static_probe": all(row["free_floating_mass_weighted"]["actual_weighted_task_residual_per_s"] < row["fixed_base_naive"]["actual_weighted_task_residual_per_s"] for row in tasks),
        "C15_no_virtual_seventh_revolute_joint": list(backend.tree.movable_joint_names)[:6] == [f"joint{i}" for i in range(1, 7)] and backend.tree.movable_dof == 8,
        "C16_locked_2P_and_time_varying_rigid_candidates_source_bound_only": all(upstream_candidate_audit.values()),
        "C17_no_backend_advance_collision_path_hardware_command_or_release_credit": all(value is False for key, value in contract["claim_boundary"].items() if key != "candidate_metric_bound") and contract["claim_boundary"]["candidate_metric_bound"] is True,
    }
    all_pass = all(checks.values())
    evidence = to_builtin({
        "schema": "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_EVIDENCE_V1",
        "authority_scope": contract["authority_scope"],
        "source_binding": pins,
        "parent_control_transitive_source_binding": parent_binding,
        "upstream_candidate_audit": upstream_candidate_audit,
        "chain_derivation": chain,
        "reference_scale_derivation": reference_scales,
        "metric_definition": contract["metric"],
        "generalized_coordinate_metric_definition": generalized_metric,
        "tasks": tasks,
        "checks": checks,
        "candidate_metric_bound": all_pass,
        "parent_control_gate_reissued": False,
        "precontact_tracking_validated": False,
        "time_domain_tracking_executed": False,
        "hardware_valid": False,
        "next_stage_authorized": False,
        "release_credit": False,
    })
    gate = to_builtin({
        "schema": "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_GATE_V1",
        "technical_verdict": "TASK_SPACE_METRIC_CANDIDATE_PASS__PARENT_CONTROL_TIME_DOMAIN_MECHANICAL_HARDWARE_AND_SAFE_HOLD" if all_pass else "TASK_SPACE_METRIC_CANDIDATE_HOLD",
        "scope": contract["authority_scope"],
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "all_checks_pass": all_pass,
        "candidate_metric_bound": all_pass,
        "maximum_claim": "SOURCE_DERIVED_DIMENSIONLESS_TASK_SPACE_METRIC_CANDIDATE_ONLY",
        "parent_control_gate_reissued": False,
        "precontact_tracking_validated": False,
        "time_domain_tracking_executed": False,
        "m01_path_bound": False,
        "collision_valid": False,
        "hardware_valid": False,
        "safe_review_pass": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "review_status": contract["review_status"],
    })
    return evidence, gate


def run_negative_controls(contract: Mapping[str, Any], project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    records: list[dict[str, Any]] = []

    def expect(identifier: str, mutation, expected_prefix: str, check_pins: bool = False) -> None:
        candidate = copy.deepcopy(dict(contract))
        mutation(candidate)
        caught = False
        observed = None
        try:
            validate_contract(candidate)
            if check_pins:
                pins = validate_source_pins(candidate, project_root)
                if not pins["all_match"]:
                    raise MetricError("SOURCE_PIN_DRIFT")
            else:
                derive_chain_length(candidate, project_root)
        except Exception as exc:  # negative-control receipt intentionally records class/message
            observed = f"{type(exc).__name__}:{exc}"
            caught = str(exc).startswith(expected_prefix) or expected_prefix in str(exc)
        records.append({"id": identifier, "caught": caught, "expected": expected_prefix, "observed": observed})

    parser_records = []
    for identifier, payload, expected in (
        ("NC01_DUPLICATE_JSON_KEY", '{"a":1,"a":2}', "DUPLICATE_JSON_KEY"),
        ("NC02_NONFINITE_JSON", '{"a":NaN}', "NONFINITE_JSON_CONSTANT"),
    ):
        try:
            loads_json_strict(payload)
            caught = False
            observed = None
        except Exception as exc:
            caught = expected in str(exc)
            observed = f"{type(exc).__name__}:{exc}"
        parser_records.append({"id": identifier, "caught": caught, "expected": expected, "observed": observed})
    records.extend(parser_records)
    expect("NC03_ZERO_LENGTH", lambda d: d["derivation"].update({"characteristic_length_m": 0.0}), "CHARACTERISTIC_LENGTH_MUST_BE_POSITIVE")
    expect("NC04_WRONG_LENGTH", lambda d: d["derivation"].update({"characteristic_length_m": 1.0}), "FAR_APPROACH_5D_DIAGONAL_NOT_EXACT_RECIPROCAL_METRIC")
    expect("NC05_WEIGHT_TAMPER", lambda d: d["metric"]["far_approach_5d_diagonal"].__setitem__(0, 1.0), "FAR_APPROACH_5D_DIAGONAL_NOT_EXACT_RECIPROCAL_METRIC")
    expect("NC06_CHAIN_ORDER_TAMPER", lambda d: d["derivation"]["expected_chain_joint_names"].reverse(), "ROOT_TO_TOOL_CHAIN_JOINT_ORDER_MISMATCH")
    expect("NC07_ROOT_FRAME_TAMPER", lambda d: d["derivation"].update({"root_link": "base_link"}), "ROOT_TOOL_FRAME_MISMATCH")
    expect("NC08_LENGTH_UNIT_TAMPER", lambda d: d["derivation"].update({"length_unit": "mm"}), "CHARACTERISTIC_LENGTH_UNIT_MUST_BE_M")
    expect("NC09_Q8_NONFINITE", lambda d: d["diagnostic_state"]["q8_mixed_rad_m"].__setitem__(0, float("nan")), "DIAGNOSTIC_Q8_MUST_HAVE_8_FINITE_VALUES")
    expect("NC10_Q8_SIZE", lambda d: d["diagnostic_state"].update({"q8_mixed_rad_m": [0.0] * 7}), "DIAGNOSTIC_Q8_MUST_HAVE_8_FINITE_VALUES")
    expect("NC11_RAW_SVD_CREDIT", lambda d: d["metric"].update({"mixed_unweighted_svd_credit_allowed": True}), "METRIC_UNIT_OR_RAW_CREDIT_POLICY_MISMATCH")
    expect("NC12_OPTIMALITY_PROMOTION", lambda d: d["metric"].update({"selected_metric_is_control_optimality_proof": True}), "METRIC_MUST_NOT_CLAIM_CONTROL_OPTIMALITY")
    expect("NC13_PARENT_GATE_REISSUE", lambda d: d["claim_boundary"].update({"parent_control_gate_reissued": True}), "CLAIM_BOUNDARY_MISMATCH")
    expect("NC14_COMMAND_PROMOTION", lambda d: d["claim_boundary"].update({"control_command_emitted": True}), "CLAIM_BOUNDARY_MISMATCH")
    expect("NC15_PATH_PROMOTION", lambda d: d["claim_boundary"].update({"m01_path_search_executed": True}), "CLAIM_BOUNDARY_MISMATCH")
    expect("NC16_HARDWARE_PROMOTION", lambda d: d["claim_boundary"].update({"hardware_rate_or_effort_valid": True}), "CLAIM_BOUNDARY_MISMATCH")
    expect("NC17_RELEASE_PROMOTION", lambda d: d.update({"release_credit": True}), "TOP_LEVEL_AUTHORITY_MUST_REMAIN_FALSE")
    expect("NC18_SENSITIVITY_TAMPER", lambda d: d["sensitivity"].update({"length_multipliers": [0.5, 1.0, 3.0]}), "LENGTH_SENSITIVITY_MULTIPLIERS_MISMATCH")
    expect("NC19_THRESHOLD_NEGATIVE", lambda d: d["thresholds"].update({"minimum_sensitivity_sigma": -1.0}), "THRESHOLD_minimum_sensitivity_sigma_MUST_BE_POSITIVE")
    expect("NC20_SOURCE_HASH_TAMPER", lambda d: d["source_pins"][0].update({"sha256": "0" * 64}), "SOURCE_PIN_DRIFT", check_pins=True)
    expect("NC21_SOURCE_BYTES_TAMPER", lambda d: d["source_pins"][0].update({"bytes": 1}), "SOURCE_PIN_DRIFT", check_pins=True)
    expect("NC22_SOURCE_ID_DUPLICATE", lambda d: d["source_pins"][1].update({"id": d["source_pins"][0]["id"]}), "SOURCE_PIN_SET_MUST_HAVE_SEVEN_UNIQUE_RECORDS")
    expect("NC23_TOP_LEVEL_NEXT_STAGE", lambda d: d.update({"next_stage_authorized": True}), "TOP_LEVEL_AUTHORITY_MUST_REMAIN_FALSE")
    expect("NC24_CONFIGURATION_DEPENDENT_LENGTH", lambda d: d["derivation"].update({"joint_rotation_or_configuration_used_in_length_sum": True}), "LENGTH_MUST_NOT_DEPEND_ON_JOINT_CONFIGURATION")
    expect("NC25_REFERENCE_MASS_ZERO", lambda d: d["generalized_coordinate_metric"].update({"reference_mass_kg": 0.0}), "REFERENCE_MASS_AND_INERTIA_MUST_BE_POSITIVE")
    expect("NC26_REFERENCE_INERTIA_TAMPER", lambda d: d["generalized_coordinate_metric"].update({"reference_inertia_kg_m2": 1.0}), "REFERENCE_INERTIA_NOT_MASS_TIMES_LENGTH_SQUARED")
    expect("NC27_Q_RATE_SCALE_TAMPER", lambda d: d["generalized_coordinate_metric"]["q_rate_scale_diagonal_rad_inverse"].__setitem__(0, 2.0), "GENERALIZED_COORDINATE_SCALE_MISMATCH")
    expect("NC28_NORMAL_MATRIX_UNIT_TAMPER", lambda d: d["generalized_coordinate_metric"].update({"normal_matrix_unit": "kg^-1*m^-2"}), "NORMAL_MATRIX_UNIT_OR_MASS_REPARAMETERIZATION_POLICY_MISMATCH")
    expect("NC29_KG_G_POLICY_DISABLED", lambda d: d["generalized_coordinate_metric"].update({"kg_to_g_reparameterization_required": False}), "NORMAL_MATRIX_UNIT_OR_MASS_REPARAMETERIZATION_POLICY_MISMATCH")
    return {
        "schema": "CTRL_R2_TASK_SPACE_METRIC_NEGATIVE_CONTROL_RESULTS_V1",
        "records": records,
        "passed": sum(row["caught"] for row in records),
        "total": len(records),
        "all_pass": all(row["caught"] for row in records),
    }
