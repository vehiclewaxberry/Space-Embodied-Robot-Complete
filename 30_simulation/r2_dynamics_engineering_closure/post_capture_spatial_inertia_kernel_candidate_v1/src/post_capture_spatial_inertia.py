"""Synthetic-fixture spatial-inertia composition and momentum initialization kernel.

This module does not implement contact, capture, attachment acquisition, or an
attached-target plant.  It only evaluates rigid mass-property composition after
an authoritative attachment transform has already been supplied.  Current C08
and C09 instances are deliberately rejected because that transform is null.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = (
    PACKAGE_ROOT
    / "contracts"
    / "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_CONTRACT_V1.json"
)
EXPECTED_CONTRACT_CANONICAL_SHA256 = (
    "135757E5B9D42D39D59C7289B754115D97F01BAACA4AEEF121A96F01E17A395C"
)
GATE_IDS = tuple(f"K{index:02d}" for index in range(1, 23))
EXPECTED_MINIMUM_INPUT_IDS = tuple(f"PC{index:02d}_" for index in range(1, 8))
COORDINATE_UNITS = ("rad",) * 6 + ("m",) * 2
RATE_UNITS = ("rad/s",) * 6 + ("m/s",) * 2
REQUIRED_ATTACHMENT_STATUS = (
    "UNKNOWN_NOT_AUTHORITY_BOUND__M5_DISPLAY_TRANSFORM_NOT_PROMOTED"
)
REQUIRED_TARGET_SEMANTICS = (
    "MASS_PROPERTY_SCENARIO_SEMANTIC_ONLY__NO_PLANT_OR_CONTACT_AUTHORITY"
)
CURRENT_NOT_EVALUATED = "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3"


class KernelError(RuntimeError):
    """Fail-closed contract, frame, unit, or physical-input error."""


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
    return loads_json_strict(path.read_text(encoding="utf-8"))


def to_builtin(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [to_builtin(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): to_builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_builtin(item) for item in value]
    return value


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


def file_record(path: Path, root: Path = PROJECT_ROOT) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": path.resolve().relative_to(root.resolve()).as_posix(),
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest().upper(),
    }


def _require(condition: bool, token: str) -> None:
    if not condition:
        raise KernelError(token)


def validate_contract_semantics(contract: Mapping[str, Any]) -> dict[str, Any]:
    _require(
        contract.get("schema") == "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_CONTRACT_V1",
        "CONTRACT_SCHEMA_MISMATCH",
    )
    _require(contract.get("review_status") == "PENDING_OWNER_REVIEW", "REVIEW_STATUS_MISMATCH")
    model = contract.get("model_contract", {})
    _require(
        model.get("se3_convention")
        == "T_A_B maps coordinates expressed in B into A: x_A=R_A_B*x_B+p_A_B",
        "SE3_CONVENTION_MISMATCH",
    )
    mapping = model.get("state_mapping", {})
    _require(mapping.get("existing_plant_physical_state_dimension") == 23, "STATE_DIMENSION_MISMATCH")
    _require(tuple(mapping.get("joint_coordinate_units", [])) == COORDINATE_UNITS, "COORDINATE_UNITS_MISMATCH")
    _require(tuple(mapping.get("joint_rate_units", [])) == RATE_UNITS, "RATE_UNITS_MISMATCH")
    _require(
        model.get("energy_semantics")
        == "PERFECTLY_INELASTIC_RIGIDIFICATION_ENERGY_IS_NOT_CONSERVED_OR_CREDITED",
        "ENERGY_SEMANTICS_ESCALATED",
    )
    authority = contract.get("current_system_authority_contract", {})
    _require(authority.get("required_status") == REQUIRED_ATTACHMENT_STATUS, "ATTACHMENT_STATUS_CONTRACT_MISMATCH")
    _require(authority.get("required_value") is None, "ATTACHMENT_NULL_CONTRACT_MISMATCH")
    _require(authority.get("operational_attachment_authority") is False, "ATTACHMENT_AUTHORITY_ESCALATED")
    _require(authority.get("target_attached_semantics") == REQUIRED_TARGET_SEMANTICS, "TARGET_SEMANTICS_MISMATCH")
    _require(authority.get("display_transform_promotion_forbidden") is True, "DISPLAY_PROMOTION_GUARD_MISSING")
    _require(authority.get("zero_fill_forbidden") is True, "ZERO_FILL_GUARD_MISSING")
    _require(authority.get("kernel_call_for_current_instance_allowed") is False, "CURRENT_KERNEL_CALL_ESCALATED")
    admission = authority.get("successful_admission_receipt_contract", {})
    _require(
        admission.get("required_schema") == "AUTHORITY_BOUND_ATTACHMENT_SE3_RECEIPT_V1",
        "ATTACHMENT_RECEIPT_SCHEMA_CONTRACT_MISMATCH",
    )
    _require(
        admission.get("required_contract_source_pin_id") == "attachment_authority_receipt",
        "ATTACHMENT_RECEIPT_PIN_ID_CONTRACT_MISMATCH",
    )
    _require(
        admission.get("required_frame_ids")
        == {"parent_frame": "E", "child_frame": "T", "transform_field": "T_E_T_rows"},
        "ATTACHMENT_RECEIPT_FRAME_CONTRACT_MISMATCH",
    )
    _require(
        admission.get("caller_supplied_status_or_boolean_without_pinned_receipt_forbidden") is True,
        "BARE_ATTACHMENT_AUTHORITY_INPUT_FORBIDDEN_GUARD_MISSING",
    )
    _require(
        admission.get("current_contract_contains_attachment_authority_receipt_pin") is False,
        "CURRENT_ATTACHMENT_RECEIPT_AUTHORITY_ESCALATED",
    )
    for configuration_id, expected_mass, expected_use in (
        ("C08", 22.0, "TARGET_22KG_MASS_INERTIA_FIXTURE_ONLY__NO_ATTACHED_PLANT"),
        ("C09", 150.0, "TARGET_150KG_MASS_INERTIA_FIXTURE_ONLY__NO_ATTACHED_PLANT"),
    ):
        item = authority.get("configurations", {}).get(configuration_id, {})
        _require(item.get("design_mass_kg") == expected_mass, f"{configuration_id}_DESIGN_MASS_MISMATCH")
        _require(item.get("maximum_permitted_use") == expected_use, f"{configuration_id}_USE_BOUNDARY_MISMATCH")
        _require(item.get("target_attachment_plant_allowed") is False, f"{configuration_id}_PLANT_AUTHORITY_ESCALATED")
        _require(item.get("current_instance_status") == CURRENT_NOT_EVALUATED, f"{configuration_id}_STATUS_MISMATCH")
    minimum = contract.get("minimum_true_inputs_to_bind_existing_23d_plant", [])
    _require(len(minimum) == 7, "MINIMUM_TRUE_INPUT_COUNT_MISMATCH")
    _require(
        all(item.get("id", "").startswith(prefix) for item, prefix in zip(minimum, EXPECTED_MINIMUM_INPUT_IDS)),
        "MINIMUM_TRUE_INPUT_ID_ORDER_MISMATCH",
    )
    pins = contract.get("source_pins", [])
    _require(isinstance(pins, list) and len(pins) == 7, "SOURCE_PIN_COUNT_MISMATCH")
    _require(len({item.get("id") for item in pins}) == 7, "SOURCE_PIN_ID_DUPLICATE")
    for pin in pins:
        _require(isinstance(pin.get("bytes"), int) and pin["bytes"] > 0, "SOURCE_PIN_BYTES_INVALID")
        sha = pin.get("sha256")
        _require(isinstance(sha, str) and len(sha) == 64 and sha == sha.upper(), "SOURCE_PIN_SHA_INVALID")
    boundary = contract.get("release_boundary", {})
    _require(boundary.get("candidate_only") is True, "CANDIDATE_ONLY_MISSING")
    _require(boundary.get("synthetic_fixture_only") is True, "SYNTHETIC_ONLY_MISSING")
    for key, value in boundary.items():
        if key not in {"candidate_only", "synthetic_fixture_only"}:
            _require(value is False, f"RELEASE_BOUNDARY_ESCALATED:{key}")
    _require(contract.get("next_stage_authorized") is False, "NEXT_STAGE_ESCALATED")
    _require(contract.get("release_credit") is False, "RELEASE_CREDIT_ESCALATED")
    return {
        "semantic_contract_valid": True,
        "source_pin_count": 7,
        "minimum_true_input_count": 7,
        "all_authority_false": True,
    }


def load_contract() -> dict[str, Any]:
    contract = load_json_strict(CONTRACT_PATH)
    _require(
        canonical_sha256(contract) == EXPECTED_CONTRACT_CANONICAL_SHA256,
        "CONTRACT_CANONICAL_SHA256_DRIFT",
    )
    validate_contract_semantics(contract)
    return contract


def validate_source_pins(contract: Mapping[str, Any]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for pin in contract["source_pins"]:
        path = (PROJECT_ROOT / pin["path"]).resolve()
        _require(path.is_file(), f"SOURCE_PIN_MISSING:{pin['id']}")
        actual = file_record(path)
        match = actual["bytes"] == pin["bytes"] and actual["sha256"] == pin["sha256"]
        records.append({"id": pin["id"], **actual, "match": match})
        _require(match, f"SOURCE_PIN_DRIFT:{pin['id']}")
    return {"records": records, "all_match": all(item["match"] for item in records)}


def _pin_path(contract: Mapping[str, Any], identifier: str) -> Path:
    match = next((item for item in contract["source_pins"] if item["id"] == identifier), None)
    _require(match is not None, f"SOURCE_PIN_ID_MISSING:{identifier}")
    return PROJECT_ROOT / match["path"]


def audit_current_system_authority(contract: Mapping[str, Any]) -> dict[str, Any]:
    state_path = _pin_path(contract, "configuration_state_vector_contract")
    use_path = _pin_path(contract, "configuration_dynamics_use_matrix")
    display_path = _pin_path(contract, "display_only_transform_candidates")
    states = load_json_strict(state_path)
    uses = load_json_strict(use_path)
    _require(states.get("schema") == "R2_CONFIGURATION_STATE_VECTOR_CONTRACT_V1", "STATE_AUTHORITY_SCHEMA_MISMATCH")
    _require(uses.get("schema") == "R2_CONFIGURATION_DYNAMICS_USE_MATRIX_V1", "DYNAMICS_USE_SCHEMA_MISMATCH")
    state_by_id = {item["configuration_id"]: item for item in states["configurations"]}
    use_by_id = {item["configuration_id"]: item for item in uses["records"]}
    expected = contract["current_system_authority_contract"]["configurations"]
    records: dict[str, Any] = {}
    for configuration_id in ("C08", "C09"):
        state = state_by_id[configuration_id]
        target = state["authoritative_state"]["target"]
        attachment = target["attachment_transform_S_rows"]
        use = use_by_id[configuration_id]
        facts = {
            "attachment_status_exact": attachment["status"] == REQUIRED_ATTACHMENT_STATUS,
            "attachment_value_is_null": attachment["value"] is None,
            "operational_attachment_authority_false": target["operational_attachment_authority"] is False,
            "target_attached_semantic_only": target["target_attached"]["status"] == REQUIRED_TARGET_SEMANTICS,
            "state_parent_gate_credit_false": state["parent_gate_credit"] is False,
            "operational_state_not_authorized": state["operational_state"] == "NOT_OPERATIONALLY_AUTHORIZED",
            "design_mass_matches_contract": target["design_mass_kg"]["value"] == expected[configuration_id]["design_mass_kg"],
            "design_inertia_matches_contract": target["design_inertia_diag_kg_m2"]["value"] == expected[configuration_id]["design_inertia_diag_kg_m2"],
            "design_mass_fixture_loading_allowed": use["design_mass_property_loading_allowed"] is True,
            "maximum_permitted_use_exact": use["maximum_permitted_use"] == expected[configuration_id]["maximum_permitted_use"],
            "target_attachment_plant_allowed_false": use["target_attachment_plant_allowed"] is False,
            "non_abort_operational_authority_false": use["non_abort_operational_authority"] is False,
            "use_parent_gate_credit_false": use["parent_gate_credit"] is False,
        }
        records[configuration_id] = {
            "facts": facts,
            "all_facts_exact": all(facts.values()),
            "kernel_called": False,
            "status": CURRENT_NOT_EVALUATED,
            "reason": "AUTHORITATIVE_T_E_T_IS_NULL__DISPLAY_TRANSFORM_NOT_PROMOTED",
        }
    display_text = display_path.read_text(encoding="utf-8")
    display_checks = {
        "display_only_not_baseline": "target capture transforms are display-only in M5 and are not written back to any baseline" in display_text,
        "pregrasp_not_dynamics_validated": "PREGRASP scene candidate is not dynamics-validated for 22 kg or 150 kg capture" in display_text,
    }
    all_pass = all(item["all_facts_exact"] for item in records.values()) and all(display_checks.values())
    return {
        "records": records,
        "display_transform_source_checks": display_checks,
        "all_pass": all_pass,
        "current_system_instance_evaluated": False,
        "current_system_kernel_call_count": 0,
    }


def admit_current_system_attachment(
    authority_receipt: Mapping[str, Any] | None,
    configuration_id: str,
) -> np.ndarray:
    """Admit a current-system attachment only through a contract-pinned receipt.

    A caller cannot manufacture authority by passing a status string or booleans.
    The receipt document must be named in the already hash-bound contract, must
    exactly match the pinned file, and must link the named configuration record.
    The current V1 contract deliberately contains no such pin, so current C08/C09
    calls remain fail-closed.
    """
    contract = load_contract()
    if authority_receipt is None:
        raise KernelError("MISSING_AUTHORITATIVE_ATTACHMENT_SE3")
    _require(isinstance(authority_receipt, Mapping), "ATTACHMENT_AUTHORITY_RECEIPT_NOT_MAPPING")
    _require(configuration_id in {"C08", "C09"}, "ATTACHMENT_CONFIGURATION_ID_UNSUPPORTED")
    pin = next(
        (item for item in contract.get("source_pins", []) if item.get("id") == "attachment_authority_receipt"),
        None,
    )
    _require(pin is not None, "ATTACHMENT_AUTHORITY_SOURCE_PIN_MISSING")
    receipt_path = (PROJECT_ROOT / str(pin["path"])).resolve()
    _require(receipt_path.is_file(), "ATTACHMENT_AUTHORITY_RECEIPT_FILE_MISSING")
    actual = file_record(receipt_path)
    _require(
        actual["bytes"] == pin.get("bytes") and actual["sha256"] == pin.get("sha256"),
        "ATTACHMENT_AUTHORITY_RECEIPT_SOURCE_HASH_MISMATCH",
    )
    pinned_receipt = load_json_strict(receipt_path)
    _require(
        canonical_bytes(pinned_receipt) == canonical_bytes(authority_receipt),
        "ATTACHMENT_AUTHORITY_RECEIPT_ARGUMENT_NOT_PINNED_DOCUMENT",
    )
    if authority_receipt.get("schema") != "AUTHORITY_BOUND_ATTACHMENT_SE3_RECEIPT_V1":
        raise KernelError("ATTACHMENT_RECEIPT_SCHEMA_MISMATCH")
    if authority_receipt.get("status") != "AUTHORITY_BOUND_OPERATIONAL_ATTACHMENT_SE3":
        raise KernelError("ATTACHMENT_STATUS_NOT_OPERATIONAL_AUTHORITY")
    if authority_receipt.get("operational_attachment_authority") is not True:
        raise KernelError("ATTACHMENT_OPERATIONAL_AUTHORITY_FALSE")
    if authority_receipt.get("target_attachment_plant_allowed") is not True:
        raise KernelError("TARGET_ATTACHMENT_PLANT_NOT_ALLOWED")
    _require(
        authority_receipt.get("attachment_frame_ids")
        == {"parent_frame": "E", "child_frame": "T", "transform_field": "T_E_T_rows"},
        "ATTACHMENT_FRAME_IDS_MISMATCH",
    )
    linkage = authority_receipt.get("system_configuration_linkage", {})
    _require(linkage.get("configuration_id") == configuration_id, "ATTACHMENT_CONFIGURATION_LINKAGE_MISMATCH")
    state_pin = next(
        (item for item in contract.get("source_pins", []) if item.get("id") == "configuration_state_vector_contract"),
        None,
    )
    _require(state_pin is not None, "CONFIGURATION_STATE_SOURCE_PIN_MISSING")
    state_path = (PROJECT_ROOT / str(state_pin["path"])).resolve()
    _require(state_path.is_file(), "CONFIGURATION_STATE_SOURCE_FILE_MISSING")
    state_actual = file_record(state_path)
    _require(
        state_actual["bytes"] == state_pin.get("bytes")
        and state_actual["sha256"] == state_pin.get("sha256"),
        "CONFIGURATION_STATE_SOURCE_HASH_MISMATCH",
    )
    _require(
        linkage.get("configuration_state_contract_raw_sha256") == state_pin.get("sha256"),
        "ATTACHMENT_STATE_CONTRACT_HASH_LINKAGE_MISMATCH",
    )
    states = load_json_strict(state_path)
    record = next(
        (item for item in states.get("configurations", []) if item.get("configuration_id") == configuration_id),
        None,
    )
    _require(record is not None, "ATTACHMENT_CONFIGURATION_RECORD_MISSING")
    _require(
        linkage.get("configuration_state_record_canonical_sha256") == canonical_sha256(record),
        "ATTACHMENT_CONFIGURATION_RECORD_HASH_LINKAGE_MISMATCH",
    )
    transform = _matrix(authority_receipt.get("T_E_T_rows"), (4, 4), "T_E_T")
    validate_transform(transform, "T_E_T")
    return transform


def _vector(value: Any, size: int, token: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    _require(array.shape == (size,), f"{token}_SHAPE")
    _require(bool(np.all(np.isfinite(array))), f"{token}_NONFINITE")
    return array


def _matrix(value: Any, shape: tuple[int, int], token: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    _require(array.shape == shape, f"{token}_SHAPE")
    _require(bool(np.all(np.isfinite(array))), f"{token}_NONFINITE")
    return array


def _mass(value: Any, token: str, *, allow_zero: bool = False) -> float:
    try:
        mass = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise KernelError(f"{token}_NOT_NUMERIC") from exc
    _require(math.isfinite(mass), f"{token}_NONFINITE")
    _require(mass >= 0.0 if allow_zero else mass > 0.0, f"{token}_{'NEGATIVE' if allow_zero else 'NOT_POSITIVE'}")
    return mass


def skew(vector: Sequence[float]) -> np.ndarray:
    x, y, z = _vector(vector, 3, "SKEW_VECTOR")
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]], dtype=float)


def parallel_axis(mass_kg: float, displacement_m: Sequence[float]) -> np.ndarray:
    mass = _mass(mass_kg, "PARALLEL_AXIS_MASS", allow_zero=True)
    displacement = _vector(displacement_m, 3, "PARALLEL_AXIS_DISPLACEMENT")
    return mass * (
        float(displacement @ displacement) * np.eye(3) - np.outer(displacement, displacement)
    )


def axis_angle_rotation(axis: Sequence[float], angle_rad: float) -> np.ndarray:
    direction = _vector(axis, 3, "AXIS")
    norm = float(np.linalg.norm(direction))
    _require(norm > 0.0 and math.isfinite(angle_rad), "AXIS_ANGLE_INVALID")
    direction = direction / norm
    generator = skew(direction)
    return np.eye(3) + math.sin(angle_rad) * generator + (1.0 - math.cos(angle_rad)) * (generator @ generator)


def make_transform(rotation: Sequence[Sequence[float]], translation_m: Sequence[float]) -> np.ndarray:
    transform = np.eye(4)
    transform[:3, :3] = np.asarray(rotation, dtype=float)
    transform[:3, 3] = _vector(translation_m, 3, "TRANSFORM_TRANSLATION")
    validate_transform(transform, "GENERATED_TRANSFORM")
    return transform


def validate_rotation(rotation: Any, token: str) -> dict[str, float]:
    matrix = _matrix(rotation, (3, 3), token)
    orthonormal = float(np.max(np.abs(matrix.T @ matrix - np.eye(3))))
    determinant_error = float(abs(np.linalg.det(matrix) - 1.0))
    _require(orthonormal <= 2.0e-12, f"{token}_ROTATION_NOT_ORTHONORMAL")
    _require(determinant_error <= 2.0e-12, f"{token}_ROTATION_NOT_PROPER")
    return {
        "orthonormal_max": orthonormal,
        "determinant_abs_error": determinant_error,
    }


def validate_transform(transform: Any, token: str) -> dict[str, Any]:
    matrix = _matrix(transform, (4, 4), token)
    _require(
        float(np.max(np.abs(matrix[3] - np.array([0.0, 0.0, 0.0, 1.0])))) <= 1.0e-14,
        f"{token}_HOMOGENEOUS_ROW_INVALID",
    )
    rotation = validate_rotation(matrix[:3, :3], token)
    return {"rotation": rotation, "translation_finite": True}


def validate_inertia(
    inertia: Any,
    token: str,
    *,
    allow_zero: bool = False,
) -> dict[str, Any]:
    matrix = _matrix(inertia, (3, 3), token)
    symmetry = float(np.max(np.abs(matrix - matrix.T)))
    _require(symmetry <= 2.0e-12, f"{token}_NOT_SYMMETRIC")
    eigenvalues = np.linalg.eigvalsh(0.5 * (matrix + matrix.T))
    lower = -1.0e-13 if allow_zero else 1.0e-10
    _require(float(eigenvalues[0]) >= lower, f"{token}_NOT_POSITIVE_DEFINITE")
    if not allow_zero:
        _require(
            float(eigenvalues[-1]) <= float(eigenvalues[0] + eigenvalues[1]) + 1.0e-10,
            f"{token}_PRINCIPAL_MOMENT_TRIANGLE_VIOLATION",
        )
        condition = float(np.linalg.cond(matrix))
        _require(math.isfinite(condition), f"{token}_SINGULAR")
        _require(condition <= 1.0e14, f"{token}_ILL_CONDITIONED")
        try:
            np.linalg.solve(matrix, np.ones(3))
        except np.linalg.LinAlgError as exc:
            raise KernelError(f"{token}_SINGULAR") from exc
    else:
        condition = None
    return {
        "symmetry_max_kg_m2": symmetry,
        "eigenvalues_kg_m2": eigenvalues,
        "minimum_eigenvalue_kg_m2": float(eigenvalues[0]),
        "principal_moment_triangle_satisfied": bool(
            eigenvalues[-1] <= eigenvalues[0] + eigenvalues[1] + 1.0e-10
        ),
        "condition_number": condition,
        "invertible": not allow_zero,
    }


def validate_body(body: Mapping[str, Any], prefix: str, *, allow_zero: bool = False) -> dict[str, Any]:
    mass = _mass(body.get("mass_kg", math.nan), f"{prefix}_MASS", allow_zero=allow_zero)
    cg = _vector(body.get("cg_m"), 3, f"{prefix}_CG")
    inertia = _matrix(body.get("inertia_cg_kg_m2"), (3, 3), f"{prefix}_INERTIA")
    if mass == 0.0:
        _require(float(np.max(np.abs(inertia))) == 0.0, f"{prefix}_ZERO_MASS_NONZERO_INERTIA")
    audit = validate_inertia(inertia, f"{prefix}_INERTIA", allow_zero=allow_zero and mass == 0.0)
    return {"mass_kg": mass, "cg_m": cg, "inertia_cg_kg_m2": inertia, "inertia_audit": audit}


def transform_body_to_B(target: Mapping[str, Any], transform_B_T: Any) -> dict[str, Any]:
    transform = _matrix(transform_B_T, (4, 4), "T_B_T")
    validate_transform(transform, "T_B_T")
    body = validate_body(target, "TARGET")
    rotation = transform[:3, :3]
    return {
        "mass_kg": body["mass_kg"],
        "cg_m": rotation @ body["cg_m"] + transform[:3, 3],
        "inertia_cg_kg_m2": rotation @ body["inertia_cg_kg_m2"] @ rotation.T,
    }


def combine_mass_properties(
    service: Mapping[str, Any],
    target: Mapping[str, Any],
    transform_B_T: Any,
    *,
    allow_zero_target: bool = False,
) -> dict[str, Any]:
    service_body = validate_body(service, "SERVICE")
    if allow_zero_target and float(target.get("mass_kg", math.nan)) == 0.0:
        target_body = validate_body(target, "TARGET", allow_zero=True)
        target_B = {
            "mass_kg": 0.0,
            "cg_m": _vector(target_body["cg_m"], 3, "TARGET_CG"),
            "inertia_cg_kg_m2": np.zeros((3, 3)),
        }
        validate_transform(transform_B_T, "T_B_T")
    else:
        target_body = validate_body(target, "TARGET")
        target_B = transform_body_to_B(target_body, transform_B_T)
    mass_service = service_body["mass_kg"]
    mass_target = target_B["mass_kg"]
    mass = mass_service + mass_target
    _require(mass > 0.0, "COMBINED_MASS_NOT_POSITIVE")
    cg = (mass_service * service_body["cg_m"] + mass_target * target_B["cg_m"]) / mass
    displacement_service = service_body["cg_m"] - cg
    displacement_target = target_B["cg_m"] - cg
    inertia = (
        service_body["inertia_cg_kg_m2"]
        + parallel_axis(mass_service, displacement_service)
        + target_B["inertia_cg_kg_m2"]
        + parallel_axis(mass_target, displacement_target)
    )
    audit = validate_inertia(inertia, "COMBINED_INERTIA")
    return {
        "mass_kg": mass,
        "cg_B_m": cg,
        "inertia_cg_B_kg_m2": inertia,
        "target_cg_B_m": target_B["cg_m"],
        "target_inertia_cg_B_kg_m2": target_B["inertia_cg_kg_m2"],
        "inertia_audit": audit,
    }


def spatial_inertia_about_origin(
    mass_kg: float,
    cg_m: Sequence[float],
    inertia_cg_kg_m2: Any,
) -> np.ndarray:
    mass = _mass(mass_kg, "SPATIAL_MASS")
    cg = _vector(cg_m, 3, "SPATIAL_CG")
    inertia = _matrix(inertia_cg_kg_m2, (3, 3), "SPATIAL_INERTIA_CG")
    validate_inertia(inertia, "SPATIAL_INERTIA_CG")
    cross = skew(cg)
    result = np.zeros((6, 6))
    result[:3, :3] = mass * np.eye(3)
    result[:3, 3:] = -mass * cross
    result[3:, :3] = mass * cross
    result[3:, 3:] = inertia + parallel_axis(mass, cg)
    _require(bool(np.all(np.isfinite(result))), "SPATIAL_MATRIX_NONFINITE")
    return result


def recover_mass_properties_from_spatial(spatial: Any) -> dict[str, Any]:
    matrix = _matrix(spatial, (6, 6), "SPATIAL_MATRIX")
    _require(float(np.max(np.abs(matrix - matrix.T))) <= 2.0e-11, "SPATIAL_MATRIX_NOT_SYMMETRIC")
    mass = float(np.trace(matrix[:3, :3]) / 3.0)
    _require(mass > 0.0, "SPATIAL_RECOVERED_MASS_NOT_POSITIVE")
    cross = -matrix[:3, 3:] / mass
    cg = np.array([cross[2, 1], cross[0, 2], cross[1, 0]])
    inertia = matrix[3:, 3:] - parallel_axis(mass, cg)
    validate_inertia(inertia, "SPATIAL_RECOVERED_INERTIA")
    return {"mass_kg": mass, "cg_B_m": cg, "inertia_cg_B_kg_m2": inertia}


def spatial_formula_cross(
    service: Mapping[str, Any],
    target: Mapping[str, Any],
    transform_B_T: Any,
    direct: Mapping[str, Any],
) -> dict[str, Any]:
    service_body = validate_body(service, "SERVICE")
    target_B = transform_body_to_B(target, transform_B_T)
    spatial = spatial_inertia_about_origin(
        service_body["mass_kg"], service_body["cg_m"], service_body["inertia_cg_kg_m2"]
    ) + spatial_inertia_about_origin(
        target_B["mass_kg"], target_B["cg_m"], target_B["inertia_cg_kg_m2"]
    )
    recovered = recover_mass_properties_from_spatial(spatial)
    return {
        "spatial_inertia_B_v_omega_order": spatial,
        "recovered": recovered,
        "mass_abs_kg": abs(recovered["mass_kg"] - float(direct["mass_kg"])),
        "cg_max_abs_m": float(np.max(np.abs(recovered["cg_B_m"] - direct["cg_B_m"]))),
        "inertia_max_abs_kg_m2": float(
            np.max(np.abs(recovered["inertia_cg_B_kg_m2"] - direct["inertia_cg_B_kg_m2"]))
        ),
    }


def rotation_to_quaternion_wxyz(rotation: Any) -> np.ndarray:
    matrix = _matrix(rotation, (3, 3), "QUATERNION_ROTATION")
    validate_rotation(matrix, "QUATERNION_ROTATION")
    trace = float(np.trace(matrix))
    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        quaternion = np.array([
            0.25 * scale,
            (matrix[2, 1] - matrix[1, 2]) / scale,
            (matrix[0, 2] - matrix[2, 0]) / scale,
            (matrix[1, 0] - matrix[0, 1]) / scale,
        ])
    else:
        index = int(np.argmax(np.diag(matrix)))
        if index == 0:
            scale = math.sqrt(1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2]) * 2.0
            quaternion = np.array([(matrix[2, 1] - matrix[1, 2]) / scale, 0.25 * scale, (matrix[0, 1] + matrix[1, 0]) / scale, (matrix[0, 2] + matrix[2, 0]) / scale])
        elif index == 1:
            scale = math.sqrt(1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2]) * 2.0
            quaternion = np.array([(matrix[0, 2] - matrix[2, 0]) / scale, (matrix[0, 1] + matrix[1, 0]) / scale, 0.25 * scale, (matrix[1, 2] + matrix[2, 1]) / scale])
        else:
            scale = math.sqrt(1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1]) * 2.0
            quaternion = np.array([(matrix[1, 0] - matrix[0, 1]) / scale, (matrix[0, 2] + matrix[2, 0]) / scale, (matrix[1, 2] + matrix[2, 1]) / scale, 0.25 * scale])
    quaternion /= np.linalg.norm(quaternion)
    if quaternion[0] < 0.0:
        quaternion = -quaternion
    return quaternion


def initialize_rigid_post_capture_state(
    composite: Mapping[str, Any],
    transform_I_B: Any,
    linear_momentum_I_kg_m_s: Any,
    angular_momentum_about_O_I_kg_m2_s: Any,
    origin_O_in_I_m: Any,
    joint_positions_mixed_rad_m: Any,
) -> dict[str, Any]:
    transform = _matrix(transform_I_B, (4, 4), "T_I_B")
    validate_transform(transform, "T_I_B")
    linear = _vector(linear_momentum_I_kg_m_s, 3, "LINEAR_MOMENTUM_I")
    angular = _vector(angular_momentum_about_O_I_kg_m2_s, 3, "ANGULAR_MOMENTUM_O_I")
    origin_O = _vector(origin_O_in_I_m, 3, "ORIGIN_O_IN_I")
    joints = _vector(joint_positions_mixed_rad_m, 8, "JOINT_POSITIONS")
    mass = _mass(composite.get("mass_kg"), "COMPOSITE_MASS")
    cg_B = _vector(composite["cg_B_m"], 3, "COMPOSITE_CG_B")
    inertia_B = _matrix(composite["inertia_cg_B_kg_m2"], (3, 3), "COMPOSITE_INERTIA_B")
    validate_inertia(inertia_B, "COMPOSITE_INERTIA_B")
    rotation = transform[:3, :3]
    base_position = transform[:3, 3]
    offset_I = rotation @ cg_B
    cg_position_I = base_position + offset_I
    inertia_I = rotation @ inertia_B @ rotation.T
    lever_O_to_C_I = cg_position_I - origin_O
    intrinsic_angular = angular - np.cross(lever_O_to_C_I, linear)
    try:
        omega_I = np.linalg.solve(inertia_I, intrinsic_angular)
    except np.linalg.LinAlgError as exc:
        raise KernelError("COMPOSITE_INERTIA_I_SINGULAR") from exc
    _require(bool(np.all(np.isfinite(omega_I))), "POST_CAPTURE_OMEGA_NONFINITE")
    velocity_cg_I = linear / mass
    velocity_base_I = velocity_cg_I - np.cross(omega_I, offset_I)
    recomputed_velocity_cg = velocity_base_I + np.cross(omega_I, offset_I)
    recomputed_linear = mass * recomputed_velocity_cg
    recomputed_angular = inertia_I @ omega_I + np.cross(lever_O_to_C_I, recomputed_linear)
    quaternion = rotation_to_quaternion_wxyz(rotation)
    joint_rates = np.zeros(8)
    state_23 = np.concatenate((base_position, quaternion, joints, joint_rates))
    twist_I = np.concatenate((velocity_base_I, omega_I))
    twist_B = np.concatenate((rotation.T @ velocity_base_I, rotation.T @ omega_I))
    return {
        "base_position_I_m": base_position,
        "base_quaternion_B_to_I_wxyz": quaternion,
        "joint_positions_mixed_rad_m": joints,
        "joint_rates_mixed_rad_s_m_s": joint_rates,
        "physical_state_23": state_23,
        "derived_base_twist_I_m_s_rad_s": twist_I,
        "derived_base_twist_B_m_s_rad_s": twist_B,
        "combined_cg_position_I_m": cg_position_I,
        "origin_O_in_I_m": origin_O,
        "lever_O_to_combined_cg_I_m": lever_O_to_C_I,
        "combined_inertia_cg_I_kg_m2": inertia_I,
        "input_linear_momentum_I_kg_m_s": linear,
        "input_angular_momentum_about_O_I_kg_m2_s": angular,
        "recomputed_linear_momentum_I_kg_m_s": recomputed_linear,
        "recomputed_angular_momentum_about_O_I_kg_m2_s": recomputed_angular,
        "linear_momentum_residual_kg_m_s": float(np.max(np.abs(recomputed_linear - linear))),
        "angular_momentum_residual_kg_m2_s": float(np.max(np.abs(recomputed_angular - angular))),
        "joint_lock_exact": bool(np.array_equal(joint_rates, np.zeros(8))),
        "quaternion_norm_error": abs(float(np.linalg.norm(quaternion)) - 1.0),
        "energy_conservation_evaluated": False,
    }


def make_synthetic_fixture(configuration_id: str) -> dict[str, Any]:
    if configuration_id == "C08":
        target_mass = 22.0
        target_inertia = np.diag([0.231629, 0.422149, 0.489336])
        attachment_rotation = axis_angle_rotation([0.3, -0.4, 0.8], 0.41)
        attachment_translation = [0.12, -0.04, 0.07]
        momentum = ([0.8, -0.4, 0.2], [4.0, -1.5, 2.2])
    elif configuration_id == "C09":
        target_mass = 150.0
        target_inertia = np.diag([74.805599, 74.829903, 26.592617])
        attachment_rotation = axis_angle_rotation([-0.2, 0.7, 0.5], -0.29)
        attachment_translation = [0.18, 0.06, -0.09]
        momentum = ([1.1, -0.7, 0.45], [7.0, -2.0, 5.5])
    else:
        raise KernelError("SYNTHETIC_CONFIGURATION_ID_UNSUPPORTED")
    return {
        "fixture_id": f"SYNTHETIC_{configuration_id}_DESIGN_MASS_INERTIA_FIXTURE",
        "classification": "SYNTHETIC_EXACT_NUMERICAL_FIXTURE__NOT_CURRENT_SYSTEM_INSTANCE",
        "design_mass_inertia_lineage_only": configuration_id,
        "service": {
            "frame": "B",
            "mass_kg": 31.0,
            "cg_m": [0.08, -0.02, 0.03],
            "inertia_cg_kg_m2": [[2.1, 0.04, -0.02], [0.04, 2.8, 0.03], [-0.02, 0.03, 3.1]],
        },
        "target": {
            "frame": "T",
            "mass_kg": target_mass,
            "cg_m": [0.03, -0.02, 0.01],
            "inertia_cg_kg_m2": target_inertia,
        },
        "T_B_E_rows": make_transform(axis_angle_rotation([0.2, 0.6, -0.3], 0.37), [1.05, 0.14, -0.11]),
        "T_E_T_rows": make_transform(attachment_rotation, attachment_translation),
        "T_I_B_rows": make_transform(axis_angle_rotation([0.5, -0.1, 0.4], 0.23), [10.0, -2.0, 5.0]),
        "linear_momentum_I_kg_m_s": momentum[0],
        "angular_momentum_about_O_I_kg_m2_s": momentum[1],
        "inertial_origin_O_definition": "SYNTHETIC_FIXED_INERTIAL_ORIGIN",
        "origin_O_in_I_m": [1.2, -0.7, 0.4],
        "joint_positions_mixed_rad_m": [-0.15, 0.28, -0.22, 0.19, -0.11, 0.07, 0.03575, 0.03575],
        "frames": {
            "service_mass_properties": "B",
            "target_mass_properties": "T",
            "T_B_E": "B_FROM_E",
            "T_E_T": "E_FROM_T",
            "T_I_B": "I_FROM_B",
            "momentum": "I_ABOUT_O",
        },
        "units": {
            "mass": "kg",
            "cg_translation": "m",
            "inertia": "kg*m^2",
            "linear_momentum": "kg*m/s",
            "angular_momentum": "kg*m^2/s",
            "joint_coordinates": list(COORDINATE_UNITS),
            "joint_rates": list(RATE_UNITS),
        },
        "attachment_transform_authority": "SYNTHETIC_TEST_ONLY",
        "contact_or_attachment_evidence": False,
    }


def validate_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    _require(
        fixture.get("classification")
        == "SYNTHETIC_EXACT_NUMERICAL_FIXTURE__NOT_CURRENT_SYSTEM_INSTANCE",
        "FIXTURE_CLASSIFICATION_MISMATCH",
    )
    _require(fixture.get("attachment_transform_authority") == "SYNTHETIC_TEST_ONLY", "FIXTURE_ATTACHMENT_AUTHORITY_MISMATCH")
    _require(fixture.get("contact_or_attachment_evidence") is False, "FIXTURE_CONTACT_CREDIT_ESCALATED")
    frames = fixture.get("frames", {})
    expected_frames = {
        "service_mass_properties": "B",
        "target_mass_properties": "T",
        "T_B_E": "B_FROM_E",
        "T_E_T": "E_FROM_T",
        "T_I_B": "I_FROM_B",
        "momentum": "I_ABOUT_O",
    }
    _require(frames == expected_frames, "FRAME_CONTRACT_MISMATCH")
    units = fixture.get("units", {})
    _require(units.get("mass") == "kg", "MASS_UNIT_MISMATCH")
    _require(units.get("cg_translation") == "m", "LENGTH_UNIT_MISMATCH")
    _require(units.get("inertia") == "kg*m^2", "INERTIA_UNIT_MISMATCH")
    _require(units.get("linear_momentum") == "kg*m/s", "LINEAR_MOMENTUM_UNIT_MISMATCH")
    _require(units.get("angular_momentum") == "kg*m^2/s", "ANGULAR_MOMENTUM_UNIT_MISMATCH")
    _require(tuple(units.get("joint_coordinates", [])) == COORDINATE_UNITS, "JOINT_COORDINATE_UNIT_MISMATCH")
    _require(tuple(units.get("joint_rates", [])) == RATE_UNITS, "JOINT_RATE_UNIT_MISMATCH")
    _require(bool(fixture.get("inertial_origin_O_definition")), "INERTIAL_ORIGIN_O_UNDEFINED")
    _vector(fixture.get("origin_O_in_I_m"), 3, "ORIGIN_O_IN_I")
    service = dict(fixture["service"])
    target = dict(fixture["target"])
    _require(service.pop("frame") == "B", "SERVICE_BODY_FRAME_MISMATCH")
    _require(target.pop("frame") == "T", "TARGET_BODY_FRAME_MISMATCH")
    service_audit = validate_body(service, "SERVICE")
    target_audit = validate_body(target, "TARGET")
    transform_audits = {
        "T_B_E": validate_transform(fixture["T_B_E_rows"], "T_B_E"),
        "T_E_T": validate_transform(fixture["T_E_T_rows"], "T_E_T"),
        "T_I_B": validate_transform(fixture["T_I_B_rows"], "T_I_B"),
    }
    _vector(fixture["linear_momentum_I_kg_m_s"], 3, "LINEAR_MOMENTUM_I")
    _vector(fixture["angular_momentum_about_O_I_kg_m2_s"], 3, "ANGULAR_MOMENTUM_O_I")
    _vector(fixture["joint_positions_mixed_rad_m"], 8, "JOINT_POSITIONS")
    return {
        "service": service_audit,
        "target": target_audit,
        "transforms": transform_audits,
        "frames_exact": True,
        "units_exact": True,
    }


def run_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_fixture(fixture)
    service = dict(fixture["service"]); service.pop("frame")
    target = dict(fixture["target"]); target.pop("frame")
    transform_B_T = np.asarray(fixture["T_B_E_rows"], dtype=float) @ np.asarray(fixture["T_E_T_rows"], dtype=float)
    validate_transform(transform_B_T, "T_B_T")
    direct = combine_mass_properties(service, target, transform_B_T)
    spatial = spatial_formula_cross(service, target, transform_B_T, direct)
    state = initialize_rigid_post_capture_state(
        direct,
        fixture["T_I_B_rows"],
        fixture["linear_momentum_I_kg_m_s"],
        fixture["angular_momentum_about_O_I_kg_m2_s"],
        fixture["origin_O_in_I_m"],
        fixture["joint_positions_mixed_rad_m"],
    )
    return to_builtin({
        "fixture": fixture,
        "input_validation": validation,
        "T_B_T_rows": transform_B_T,
        "composite_direct": direct,
        "independent_spatial_formula_cross": spatial,
        "post_capture_state_initialization": state,
    })


def diagnostic_rigid_degenerations(fixture: Mapping[str, Any]) -> dict[str, Any]:
    service = dict(fixture["service"]); service.pop("frame")
    target = dict(fixture["target"]); target.pop("frame")
    transform_B_T = np.asarray(fixture["T_B_E_rows"]) @ np.asarray(fixture["T_E_T_rows"])
    zero_target = {"mass_kg": 0.0, "cg_m": [9.0, -8.0, 7.0], "inertia_cg_kg_m2": np.zeros((3, 3))}
    zero = combine_mass_properties(service, zero_target, transform_B_T, allow_zero_target=True)
    target_colocated = copy.deepcopy(target)
    target_colocated["cg_m"] = list(service["cg_m"])
    colocated = combine_mass_properties(service, target_colocated, np.eye(4))
    return {
        "zero_target": {
            "mass_abs_kg": abs(zero["mass_kg"] - service["mass_kg"]),
            "cg_max_abs_m": float(np.max(np.abs(zero["cg_B_m"] - service["cg_m"]))),
            "inertia_max_abs_kg_m2": float(np.max(np.abs(zero["inertia_cg_B_kg_m2"] - service["inertia_cg_kg_m2"]))),
        },
        "colocated_axis_aligned": {
            "cg_max_abs_m": float(np.max(np.abs(colocated["cg_B_m"] - service["cg_m"]))),
            "inertia_sum_max_abs_kg_m2": float(np.max(np.abs(colocated["inertia_cg_B_kg_m2"] - (np.asarray(service["inertia_cg_kg_m2"]) + np.asarray(target_colocated["inertia_cg_kg_m2"]))))),
        },
    }


def diagnostic_mass_scaling(fixture: Mapping[str, Any]) -> dict[str, Any]:
    service = dict(fixture["service"]); service.pop("frame")
    target = dict(fixture["target"]); target.pop("frame")
    transform_B_T = np.asarray(fixture["T_B_E_rows"]) @ np.asarray(fixture["T_E_T_rows"])
    target_B = transform_body_to_B(target, transform_B_T)
    service_spatial = spatial_inertia_about_origin(service["mass_kg"], service["cg_m"], service["inertia_cg_kg_m2"])
    target_spatial = spatial_inertia_about_origin(target_B["mass_kg"], target_B["cg_m"], target_B["inertia_cg_kg_m2"])
    records = []
    for scale in (0.5, 2.0):
        scaled = copy.deepcopy(target)
        scaled["mass_kg"] *= scale
        scaled["inertia_cg_kg_m2"] = np.asarray(scaled["inertia_cg_kg_m2"]) * scale
        direct = combine_mass_properties(service, scaled, transform_B_T)
        recovered = recover_mass_properties_from_spatial(service_spatial + scale * target_spatial)
        records.append({
            "scale": scale,
            "mass_affine_abs_kg": abs(direct["mass_kg"] - (service["mass_kg"] + scale * target["mass_kg"])),
            "cg_formula_max_abs_m": float(np.max(np.abs(direct["cg_B_m"] - recovered["cg_B_m"]))),
            "inertia_formula_max_abs_kg_m2": float(np.max(np.abs(direct["inertia_cg_B_kg_m2"] - recovered["inertia_cg_B_kg_m2"]))),
        })
    return {"records": records, "max_formula_error": max(max(item["mass_affine_abs_kg"], item["cg_formula_max_abs_m"], item["inertia_formula_max_abs_kg_m2"]) for item in records)}


def diagnostic_attachment_sensitivity(fixture: Mapping[str, Any]) -> dict[str, Any]:
    service = dict(fixture["service"]); service.pop("frame")
    target = dict(fixture["target"]); target.pop("frame")
    transform_B_E = np.asarray(fixture["T_B_E_rows"], dtype=float)
    nominal_E_T = np.asarray(fixture["T_E_T_rows"], dtype=float)
    nominal = combine_mass_properties(service, target, transform_B_E @ nominal_E_T)
    translated = nominal_E_T.copy(); translated[:3, 3] += np.array([0.2, -0.1, 0.05])
    translated_result = combine_mass_properties(service, target, transform_B_E @ translated)
    rotated = nominal_E_T.copy(); rotated[:3, :3] = nominal_E_T[:3, :3] @ axis_angle_rotation([0.4, 0.1, -0.7], 0.53)
    rotated_result = combine_mass_properties(service, target, transform_B_E @ rotated)
    return {
        "translation_cg_change_m": float(np.linalg.norm(translated_result["cg_B_m"] - nominal["cg_B_m"])),
        "translation_inertia_change_kg_m2": float(np.linalg.norm(translated_result["inertia_cg_B_kg_m2"] - nominal["inertia_cg_B_kg_m2"])),
        "rotation_cg_change_m": float(np.linalg.norm(rotated_result["cg_B_m"] - nominal["cg_B_m"])),
        "rotation_inertia_change_kg_m2": float(np.linalg.norm(rotated_result["inertia_cg_B_kg_m2"] - nominal["inertia_cg_B_kg_m2"])),
    }


def diagnostic_frame_covariance(fixture: Mapping[str, Any]) -> dict[str, Any]:
    service = dict(fixture["service"]); service.pop("frame")
    target = dict(fixture["target"]); target.pop("frame")
    transform_B_T = np.asarray(fixture["T_B_E_rows"]) @ np.asarray(fixture["T_E_T_rows"])
    nominal = combine_mass_properties(service, target, transform_B_T)
    transform_Bp_B = make_transform(axis_angle_rotation([0.2, -0.5, 0.9], -0.44), [-0.3, 0.2, 0.1])
    rotation = transform_Bp_B[:3, :3]
    service_prime = {
        "mass_kg": service["mass_kg"],
        "cg_m": rotation @ np.asarray(service["cg_m"]) + transform_Bp_B[:3, 3],
        "inertia_cg_kg_m2": rotation @ np.asarray(service["inertia_cg_kg_m2"]) @ rotation.T,
    }
    transformed = combine_mass_properties(service_prime, target, transform_Bp_B @ transform_B_T)
    expected_cg = rotation @ np.asarray(nominal["cg_B_m"]) + transform_Bp_B[:3, 3]
    expected_inertia = rotation @ np.asarray(nominal["inertia_cg_B_kg_m2"]) @ rotation.T
    return {
        "cg_max_abs_m": float(np.max(np.abs(transformed["cg_B_m"] - expected_cg))),
        "inertia_max_abs_kg_m2": float(np.max(np.abs(transformed["inertia_cg_B_kg_m2"] - expected_inertia))),
    }


def diagnostic_reference_point_translation(fixture: Mapping[str, Any]) -> dict[str, Any]:
    """Exercise H_O translation and expose the opposite-cross-sign falsifier."""
    baseline_run = run_fixture(fixture)
    baseline = baseline_run["post_capture_state_initialization"]
    shifted = copy.deepcopy(fixture)
    delta = np.array([0.37, -0.21, 0.16])
    momentum = _vector(fixture["linear_momentum_I_kg_m_s"], 3, "LINEAR_MOMENTUM_I")
    origin = _vector(fixture["origin_O_in_I_m"], 3, "ORIGIN_O_IN_I")
    angular = _vector(fixture["angular_momentum_about_O_I_kg_m2_s"], 3, "ANGULAR_MOMENTUM_O_I")
    shifted["origin_O_in_I_m"] = origin + delta
    shifted["angular_momentum_about_O_I_kg_m2_s"] = angular - np.cross(delta, momentum)
    shifted_state = run_fixture(shifted)["post_capture_state_initialization"]
    twist_error = float(np.max(np.abs(
        np.asarray(shifted_state["derived_base_twist_I_m_s_rad_s"])
        - np.asarray(baseline["derived_base_twist_I_m_s_rad_s"])
    )))
    wrong_state = initialize_rigid_post_capture_state(
        baseline_run["composite_direct"],
        fixture["T_I_B_rows"],
        fixture["linear_momentum_I_kg_m_s"],
        angular + np.cross(delta, momentum),
        origin + delta,
        fixture["joint_positions_mixed_rad_m"],
    )
    wrong_sign_twist_delta = float(np.max(np.abs(
        np.asarray(wrong_state["derived_base_twist_I_m_s_rad_s"])
        - np.asarray(baseline["derived_base_twist_I_m_s_rad_s"])
    )))
    return {
        "translation_delta_I_m": delta,
        "H_translation_law": "H_O_prime=H_O-delta_r_O_cross_P",
        "twist_invariance_max_abs": twist_error,
        "wrong_cross_sign_twist_delta": wrong_sign_twist_delta,
    }


def run_negative_controls(contract: Mapping[str, Any], fixture: Mapping[str, Any]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []

    def expect(identifier: str, operation: Callable[[], Any], token: str) -> None:
        observed = "NO_EXCEPTION"
        try:
            operation()
        except Exception as exc:
            observed = str(exc)
        records.append({"id": identifier, "expected_token": token, "observed": observed, "pass": token in observed})

    expect("NC01_DUPLICATE_JSON", lambda: loads_json_strict('{"a":1,"a":2}'), "DUPLICATE_JSON_KEY_REJECTED")
    expect("NC02_JSON_NAN", lambda: loads_json_strict('{"a":NaN}'), "NONFINITE_JSON_CONSTANT_REJECTED")
    mutated_contract = copy.deepcopy(contract); mutated_contract["source_pins"][0]["sha256"] = "0" * 64
    expect("NC03_SOURCE_HASH_MUTATION", lambda: validate_source_pins(mutated_contract), "SOURCE_PIN_DRIFT:configuration_state_vector_contract")
    expect("NC04_CURRENT_NULL_ATTACHMENT", lambda: admit_current_system_attachment(None, "C08"), "MISSING_AUTHORITATIVE_ATTACHMENT_SE3")
    forged_receipt = {
        "schema": "AUTHORITY_BOUND_ATTACHMENT_SE3_RECEIPT_V1",
        "status": "AUTHORITY_BOUND_OPERATIONAL_ATTACHMENT_SE3",
        "operational_attachment_authority": True,
        "target_attachment_plant_allowed": True,
        "attachment_frame_ids": {"parent_frame": "E", "child_frame": "T", "transform_field": "T_E_T_rows"},
        "T_E_T_rows": np.eye(4),
        "system_configuration_linkage": {"configuration_id": "C08"},
    }
    expect("NC05_FORGED_UNPINNED_AUTHORITY_RECEIPT", lambda: admit_current_system_attachment(forged_receipt, "C08"), "ATTACHMENT_AUTHORITY_SOURCE_PIN_MISSING")
    expect("NC06_BARE_BOOLEAN_LEGACY_API_REJECTED", lambda: admit_current_system_attachment(np.eye(4), REQUIRED_ATTACHMENT_STATUS), "ATTACHMENT_AUTHORITY_RECEIPT_NOT_MAPPING")
    forged_wrong_config = copy.deepcopy(forged_receipt)
    expect("NC07_UNPINNED_RECEIPT_CANNOT_REACH_CONFIG_LINKAGE", lambda: admit_current_system_attachment(forged_wrong_config, "C09"), "ATTACHMENT_AUTHORITY_SOURCE_PIN_MISSING")
    bad = np.asarray(fixture["T_E_T_rows"]).copy(); bad[0, 0] += 0.01
    expect("NC08_NONORTHONORMAL_ROTATION", lambda: validate_transform(bad, "T_E_T"), "ROTATION_NOT_ORTHONORMAL")
    bad = np.eye(4); bad[0, 0] = -1.0
    expect("NC09_IMPROPER_ROTATION", lambda: validate_transform(bad, "T_E_T"), "ROTATION_NOT_PROPER")
    bad = np.asarray(fixture["T_E_T_rows"]).copy(); bad[3, 0] = 1.0
    expect("NC10_HOMOGENEOUS_ROW", lambda: validate_transform(bad, "T_E_T"), "HOMOGENEOUS_ROW_INVALID")
    mutated = copy.deepcopy(fixture); mutated["target"]["mass_kg"] = -1.0
    expect("NC11_NEGATIVE_TARGET_MASS", lambda: validate_fixture(mutated), "TARGET_MASS_NOT_POSITIVE")
    mutated = copy.deepcopy(fixture); mutated["target"]["inertia_cg_kg_m2"][0][1] += 0.1
    expect("NC12_NONSYMMETRIC_INERTIA", lambda: validate_fixture(mutated), "TARGET_INERTIA_NOT_SYMMETRIC")
    mutated = copy.deepcopy(fixture); mutated["target"]["inertia_cg_kg_m2"] = [[1.0, 0, 0], [0, 1.0, 0], [0, 0, 3.0]]
    expect("NC13_INERTIA_TRIANGLE", lambda: validate_fixture(mutated), "PRINCIPAL_MOMENT_TRIANGLE_VIOLATION")
    mutated = copy.deepcopy(fixture); mutated["frames"]["T_E_T"] = "T_FROM_E"
    expect("NC14_FRAME_DIRECTION_SWAP", lambda: validate_fixture(mutated), "FRAME_CONTRACT_MISMATCH")
    mutated = copy.deepcopy(fixture); mutated["units"]["inertia"] = "kg*m"
    expect("NC15_INERTIA_UNIT_MUTATION", lambda: validate_fixture(mutated), "INERTIA_UNIT_MISMATCH")
    mutated = copy.deepcopy(fixture); mutated["linear_momentum_I_kg_m_s"][0] = math.nan
    expect("NC16_NONFINITE_MOMENTUM", lambda: validate_fixture(mutated), "LINEAR_MOMENTUM_I_NONFINITE")
    mutated = copy.deepcopy(fixture); mutated["inertial_origin_O_definition"] = ""
    expect("NC17_UNDEFINED_ANGULAR_MOMENTUM_ORIGIN", lambda: validate_fixture(mutated), "INERTIAL_ORIGIN_O_UNDEFINED")
    mutated = copy.deepcopy(fixture); mutated["joint_positions_mixed_rad_m"] = [0.0] * 7
    expect("NC18_JOINT_DIMENSION", lambda: validate_fixture(mutated), "JOINT_POSITIONS_SHAPE")
    mutated = copy.deepcopy(fixture); mutated["units"]["joint_coordinates"][-1] = "rad"
    expect("NC19_MIXED_JOINT_UNIT_MUTATION", lambda: validate_fixture(mutated), "JOINT_COORDINATE_UNIT_MISMATCH")
    mutated_contract = copy.deepcopy(contract); mutated_contract["model_contract"]["energy_semantics"] = "ENERGY_CONSERVED"
    expect("NC20_ENERGY_CLAIM_ESCALATION", lambda: validate_contract_semantics(mutated_contract), "ENERGY_SEMANTICS_ESCALATED")
    mutated_contract = copy.deepcopy(contract); mutated_contract["release_boundary"]["attachment_valid"] = True
    expect("NC21_ATTACHMENT_AUTHORITY_ESCALATION", lambda: validate_contract_semantics(mutated_contract), "RELEASE_BOUNDARY_ESCALATED:attachment_valid")
    result = run_fixture(fixture); forged = copy.deepcopy(result); forged["composite_direct"]["inertia_cg_B_kg_m2"][0][0] += 1.0e-3
    residual = abs(forged["composite_direct"]["inertia_cg_B_kg_m2"][0][0] - result["independent_spatial_formula_cross"]["recovered"]["inertia_cg_B_kg_m2"][0][0])
    records.append({"id": "NC22_DIRECT_SPATIAL_RESULT_MUTATION", "observed_residual_kg_m2": residual, "pass": residual > 2.0e-11})
    state = result["post_capture_state_initialization"]; forged_h = np.asarray(state["recomputed_angular_momentum_about_O_I_kg_m2_s"]); forged_h[0] += 1.0e-4
    momentum_residual = float(np.max(np.abs(forged_h - np.asarray(state["input_angular_momentum_about_O_I_kg_m2_s"]))))
    records.append({"id": "NC23_ANGULAR_MOMENTUM_RESULT_MUTATION", "observed_residual_kg_m2_s": momentum_residual, "pass": momentum_residual > 5.0e-11})
    expect("NC24_SPATIAL_ZERO_MASS", lambda: spatial_inertia_about_origin(0.0, [0, 0, 0], np.eye(3)), "SPATIAL_MASS_NOT_POSITIVE")
    expect("NC25_SPATIAL_NONFINITE_MASS", lambda: spatial_inertia_about_origin(math.inf, [0, 0, 0], np.eye(3)), "SPATIAL_MASS_NONFINITE")
    expect("NC26_SPATIAL_UNPHYSICAL_INERTIA", lambda: spatial_inertia_about_origin(1.0, [0, 0, 0], np.diag([1.0, 1.0, 3.0])), "PRINCIPAL_MOMENT_TRIANGLE_VIOLATION")
    bad_composite = copy.deepcopy(result["composite_direct"]); bad_composite["mass_kg"] = 0.0
    expect("NC27_STATE_ZERO_COMPOSITE_MASS", lambda: initialize_rigid_post_capture_state(bad_composite, fixture["T_I_B_rows"], fixture["linear_momentum_I_kg_m_s"], fixture["angular_momentum_about_O_I_kg_m2_s"], fixture["origin_O_in_I_m"], fixture["joint_positions_mixed_rad_m"]), "COMPOSITE_MASS_NOT_POSITIVE")
    bad_composite = copy.deepcopy(result["composite_direct"]); bad_composite["inertia_cg_B_kg_m2"] = np.diag([1.0, 1.0, 3.0])
    expect("NC28_STATE_UNPHYSICAL_COMPOSITE_INERTIA", lambda: initialize_rigid_post_capture_state(bad_composite, fixture["T_I_B_rows"], fixture["linear_momentum_I_kg_m_s"], fixture["angular_momentum_about_O_I_kg_m2_s"], fixture["origin_O_in_I_m"], fixture["joint_positions_mixed_rad_m"]), "PRINCIPAL_MOMENT_TRIANGLE_VIOLATION")
    mutated = copy.deepcopy(fixture); mutated["origin_O_in_I_m"][0] = math.nan
    expect("NC29_NONFINITE_REFERENCE_POINT", lambda: validate_fixture(mutated), "ORIGIN_O_IN_I_NONFINITE")
    reference = diagnostic_reference_point_translation(fixture)
    records.append({"id": "NC30_REFERENCE_POINT_CROSS_SIGN_FALSIFIER", "wrong_cross_sign_twist_delta": reference["wrong_cross_sign_twist_delta"], "pass": reference["wrong_cross_sign_twist_delta"] > 1.0e-8})
    return {
        "records": records,
        "count": len(records),
        "passed": sum(item["pass"] for item in records),
        "minimum_required": 16,
        "all_pass": len(records) >= 16 and all(item["pass"] for item in records),
    }


def build_candidate() -> tuple[dict[str, Any], dict[str, Any]]:
    contract = load_contract()
    semantics = validate_contract_semantics(contract)
    sources = validate_source_pins(contract)
    current = audit_current_system_authority(contract)
    fixtures = {identifier: make_synthetic_fixture(identifier) for identifier in ("C08", "C09")}
    runs = {identifier: run_fixture(fixture) for identifier, fixture in fixtures.items()}
    diagnostics = {
        identifier: {
            "rigid_degenerations": diagnostic_rigid_degenerations(fixture),
            "mass_scaling": diagnostic_mass_scaling(fixture),
            "attachment_sensitivity": diagnostic_attachment_sensitivity(fixture),
            "frame_covariance": diagnostic_frame_covariance(fixture),
            "reference_point_translation": diagnostic_reference_point_translation(fixture),
        }
        for identifier, fixture in fixtures.items()
    }
    negative = run_negative_controls(contract, fixtures["C08"])
    replay = {
        identifier: {
            "first_canonical_sha256": canonical_sha256(runs[identifier]),
            "second_canonical_sha256": canonical_sha256(run_fixture(fixtures[identifier])),
        }
        for identifier in fixtures
    }
    for item in replay.values():
        item["canonical_identical"] = item["first_canonical_sha256"] == item["second_canonical_sha256"]
    threshold = contract["thresholds"]
    crosses = [run["independent_spatial_formula_cross"] for run in runs.values()]
    states = [run["post_capture_state_initialization"] for run in runs.values()]
    inertias = [run["composite_direct"]["inertia_audit"] for run in runs.values()]
    degenerations = [item["rigid_degenerations"] for item in diagnostics.values()]
    scalings = [item["mass_scaling"] for item in diagnostics.values()]
    sensitivities = [item["attachment_sensitivity"] for item in diagnostics.values()]
    covariances = [item["frame_covariance"] for item in diagnostics.values()]
    reference_points = [item["reference_point_translation"] for item in diagnostics.values()]
    boundary = contract["release_boundary"]
    check_rows = [
        ("K01", "HASH_BOUND_SOURCE_PINS_EXACT", sources["all_match"], {"pin_count": len(sources["records"])}),
        ("K02", "CONTRACT_FRAME_UNIT_STATE_AND_AUTHORITY_SEMANTICS_EXACT", semantics["semantic_contract_valid"], semantics),
        ("K03", "C08_AUTHORITATIVE_ATTACHMENT_NULL_FAIL_CLOSED_NOT_EVALUATED", current["records"]["C08"]["all_facts_exact"] and current["records"]["C08"]["kernel_called"] is False and current["records"]["C08"]["status"] == CURRENT_NOT_EVALUATED, current["records"]["C08"]),
        ("K04", "C09_AUTHORITATIVE_ATTACHMENT_NULL_FAIL_CLOSED_NOT_EVALUATED", current["records"]["C09"]["all_facts_exact"] and current["records"]["C09"]["kernel_called"] is False and current["records"]["C09"]["status"] == CURRENT_NOT_EVALUATED, current["records"]["C09"]),
        ("K05", "DISPLAY_TRANSFORM_NOT_PROMOTED_AND_PREGRASP_NOT_DYNAMICS_VALIDATED", all(current["display_transform_source_checks"].values()), current["display_transform_source_checks"]),
        ("K06", "SYNTHETIC_FIXTURE_CLASS_FRAME_UNITS_AND_SE3_VALID", all(run["input_validation"]["frames_exact"] and run["input_validation"]["units_exact"] for run in runs.values()), {key: value["input_validation"] for key, value in runs.items()}),
        ("K07", "PARALLEL_AXIS_AND_ROTATION_COMPOSITE_INERTIA_FINITE", all(np.all(np.isfinite(run["composite_direct"]["inertia_cg_B_kg_m2"])) for run in runs.values()), {key: value["composite_direct"] for key, value in runs.items()}),
        ("K08", "DIRECT_VS_SPATIAL_INERTIA_FORMULA_CROSS", all(item["mass_abs_kg"] <= threshold["direct_vs_spatial_mass_max_kg"] and item["cg_max_abs_m"] <= threshold["direct_vs_spatial_cg_max_m"] and item["inertia_max_abs_kg_m2"] <= threshold["direct_vs_spatial_inertia_max_kg_m2"] for item in crosses), {key: {metric: value["independent_spatial_formula_cross"][metric] for metric in ("mass_abs_kg", "cg_max_abs_m", "inertia_max_abs_kg_m2")} for key, value in runs.items()}),
        ("K09", "COMPOSITE_INERTIA_SYMMETRIC_POSITIVE_AND_PHYSICAL", all(item["symmetry_max_kg_m2"] <= threshold["inertia_symmetry_max_kg_m2"] and item["minimum_eigenvalue_kg_m2"] >= threshold["inertia_min_eigenvalue_min_kg_m2"] and item["principal_moment_triangle_satisfied"] for item in inertias), {key: value["composite_direct"]["inertia_audit"] for key, value in runs.items()}),
        ("K10", "POST_CAPTURE_23D_STATE_AND_DERIVED_6D_BASE_TWIST", all(len(item["physical_state_23"]) == 23 and len(item["derived_base_twist_B_m_s_rad_s"]) == 6 and item["joint_lock_exact"] for item in states), {key: {"state_dimension": len(value["post_capture_state_initialization"]["physical_state_23"]), "twist_dimension": len(value["post_capture_state_initialization"]["derived_base_twist_B_m_s_rad_s"]), "joint_lock_exact": value["post_capture_state_initialization"]["joint_lock_exact"]} for key, value in runs.items()}),
        ("K11", "EVENT_LINEAR_MOMENTUM_CONSERVED", all(item["linear_momentum_residual_kg_m_s"] <= threshold["linear_momentum_residual_max_kg_m_s"] for item in states), {key: value["post_capture_state_initialization"]["linear_momentum_residual_kg_m_s"] for key, value in runs.items()}),
        ("K12", "EVENT_ANGULAR_MOMENTUM_ABOUT_NUMERIC_REFERENCE_POINT_CONSERVED_AND_TRANSLATION_COVARIANT", all(item["angular_momentum_residual_kg_m2_s"] <= threshold["angular_momentum_residual_max_kg_m2_s"] for item in states) and all(item["twist_invariance_max_abs"] <= 2.0e-12 and item["wrong_cross_sign_twist_delta"] > 1.0e-8 for item in reference_points), {"momentum_residuals": {key: value["post_capture_state_initialization"]["angular_momentum_residual_kg_m2_s"] for key, value in runs.items()}, "reference_point_translation": {key: value["reference_point_translation"] for key, value in diagnostics.items()}}),
        ("K13", "ZERO_TARGET_RIGID_DEGENERATION_TO_SERVICE_EXACT", all(item["zero_target"]["mass_abs_kg"] <= threshold["rigid_degenerate_mass_max_kg"] and item["zero_target"]["cg_max_abs_m"] <= threshold["rigid_degenerate_cg_max_m"] and item["zero_target"]["inertia_max_abs_kg_m2"] <= threshold["rigid_degenerate_inertia_max_kg_m2"] for item in degenerations), {key: value["rigid_degenerations"]["zero_target"] for key, value in diagnostics.items()}),
        ("K14", "COLOCATED_AXIS_ALIGNED_RIGID_INERTIA_SUM_DEGENERATION", all(item["colocated_axis_aligned"]["cg_max_abs_m"] <= threshold["rigid_degenerate_cg_max_m"] and item["colocated_axis_aligned"]["inertia_sum_max_abs_kg_m2"] <= threshold["rigid_degenerate_inertia_max_kg_m2"] for item in degenerations), {key: value["rigid_degenerations"]["colocated_axis_aligned"] for key, value in diagnostics.items()}),
        ("K15", "TARGET_MASS_AND_INERTIA_SCALING_AFFINE_SPATIAL_CHECK", all(item["max_formula_error"] <= threshold["mass_scaling_formula_max"] for item in scalings), {key: value["mass_scaling"] for key, value in diagnostics.items()}),
        ("K16", "ATTACHMENT_TRANSLATION_SENSITIVITY_OBSERVED", all(item["translation_cg_change_m"] >= threshold["translation_sensitivity_min_m"] for item in sensitivities), {key: value["attachment_sensitivity"] for key, value in diagnostics.items()}),
        ("K17", "ATTACHMENT_ROTATION_SENSITIVITY_OBSERVED", all(item["rotation_inertia_change_kg_m2"] >= threshold["rotation_sensitivity_min_kg_m2"] for item in sensitivities), {key: value["attachment_sensitivity"] for key, value in diagnostics.items()}),
        ("K18", "REFERENCE_FRAME_COVARIANCE_OF_CG_AND_INERTIA", all(item["cg_max_abs_m"] <= threshold["frame_covariance_cg_max_m"] and item["inertia_max_abs_kg_m2"] <= threshold["frame_covariance_inertia_max_kg_m2"] for item in covariances), {key: value["frame_covariance"] for key, value in diagnostics.items()}),
        ("K19", "INELASTIC_EVENT_ENERGY_NOT_CLAIMED", all(item["energy_conservation_evaluated"] is False for item in states), {"energy_semantics": contract["model_contract"]["energy_semantics"]}),
        ("K20", "DETERMINISTIC_SYNTHETIC_FIXTURE_REPLAY", all(item["canonical_identical"] for item in replay.values()), replay),
        ("K21", "MUTATION_AND_FAIL_CLOSED_NEGATIVE_CONTROLS", negative["all_pass"] and negative["passed"] >= negative["minimum_required"], {"passed": negative["passed"], "count": negative["count"], "minimum_required": negative["minimum_required"]}),
        ("K22", "MINIMUM_REAL_INPUTS_LISTED_AND_ALL_DOWNSTREAM_AUTHORITY_FALSE", len(contract["minimum_true_inputs_to_bind_existing_23d_plant"]) == 7 and all(value is False for key, value in boundary.items() if key not in {"candidate_only", "synthetic_fixture_only"}), {"minimum_inputs": contract["minimum_true_inputs_to_bind_existing_23d_plant"], "release_boundary": boundary}),
    ]
    _require(tuple(item[0] for item in check_rows) == GATE_IDS, "GATE_ID_ORDER_MISMATCH")
    checks = [
        {"id": identifier, "name": name, "pass": bool(passed), "evidence": detail}
        for identifier, name, passed, detail in check_rows
    ]
    all_pass = all(item["pass"] for item in checks)
    verdict = contract["maximum_claim"] if all_pass else "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_CANDIDATE_HOLD__NO_DOWNSTREAM_AUTHORITY"
    evidence = to_builtin({
        "schema": "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_EVIDENCE_V1",
        "contract_canonical_sha256": EXPECTED_CONTRACT_CANONICAL_SHA256,
        "source_pins": sources,
        "current_system_authority_audit": current,
        "synthetic_fixture_runs": runs,
        "diagnostics": diagnostics,
        "deterministic_replay": replay,
        "negative_controls": negative,
        "minimum_true_inputs_to_bind_existing_23d_plant": contract["minimum_true_inputs_to_bind_existing_23d_plant"],
        "measurement_uncertainty_boundary": "NO_HARDWARE_MEASUREMENTS_OR_UNCERTAINTY_PROPAGATION__SYNTHETIC_EXACT_FIXTURE_VALUES_ONLY",
        "energy_boundary": contract["model_contract"]["energy_semantics"],
        "release_boundary": boundary,
        "next_stage_authorized": False,
        "release_credit": False,
    })
    gate = to_builtin({
        "schema": "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_GATE_V1",
        "authority_scope": contract["authority_scope"],
        "contract_canonical_sha256": EXPECTED_CONTRACT_CANONICAL_SHA256,
        "checks": checks,
        "passed": sum(item["pass"] for item in checks),
        "total": len(checks),
        "all_checks_pass": all_pass,
        "verdict": verdict,
        "maximum_claim": contract["maximum_claim"],
        "review_status": contract["review_status"],
        "current_C08_status": CURRENT_NOT_EVALUATED,
        "current_C09_status": CURRENT_NOT_EVALUATED,
        "current_system_instance_evaluated": False,
        "contact_valid": False,
        "attachment_valid": False,
        "target_attachment_plant_valid": False,
        "hardware_valid": False,
        "non_abort_authorized": False,
        "parent_dynamics_engineering_complete": False,
        "next_stage_authorized": False,
        "release_credit": False,
    })
    return evidence, gate
