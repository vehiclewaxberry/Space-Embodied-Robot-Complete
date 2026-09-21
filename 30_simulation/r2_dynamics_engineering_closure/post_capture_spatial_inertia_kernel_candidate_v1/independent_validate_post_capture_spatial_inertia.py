#!/usr/bin/env python3
"""Standalone internal validation of the post-capture spatial-inertia candidate.

The validator intentionally does not import the kernel, evaluator, or builder,
but it remains package-local and is not organizationally independent. A separate
package-external audit holds frozen source and artifact pins.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np


PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[2]
CONTRACT_PATH = PACKAGE_ROOT / "contracts" / "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_CONTRACT_V1.json"
EVIDENCE_PATH = PACKAGE_ROOT / "results" / "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_EVIDENCE_V1.json"
GATE_PATH = PACKAGE_ROOT / "results" / "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_GATE_V1.json"
MANIFEST_PATH = PACKAGE_ROOT / "results" / "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_MANIFEST_V1.json"
RECEIPT_PATH = PACKAGE_ROOT / "results" / "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_INDEPENDENT_VALIDATION_V1.json"

EXPECTED_CONTRACT_BYTES = 10212
EXPECTED_CONTRACT_RAW_SHA256 = "6097B139D85C322E80348FCD3B41B31962ACC97C42ACFE6DB467EC2E8B455664"
EXPECTED_CONTRACT_CANONICAL_SHA256 = "135757E5B9D42D39D59C7289B754115D97F01BAACA4AEEF121A96F01E17A395C"
EXPECTED_EVIDENCE_BYTES = 45238
EXPECTED_EVIDENCE_RAW_SHA256 = "0F8F0718FBBC569F740907E8308A65B54B617E22BBE472EE2437757B74900709"
EXPECTED_GATE_BYTES = 23814
EXPECTED_GATE_RAW_SHA256 = "2F4CFEC3AB45A4F006ADDC62E33E4EEB22CC96CC4376D6C793CD0ABC4E3269CF"
EXPECTED_REVIEW_STATUS = "PENDING_OWNER_REVIEW"
EXPECTED_MAXIMUM_CLAIM = "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_SYNTHETIC_FIXTURE_PASS__CURRENT_C08_C09_NOT_EVALUATED__NO_CONTACT_ATTACHMENT_NONABORT_PARENT_OR_RELEASE_CREDIT"
EXPECTED_CURRENT_STATUS = "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3"
EXPECTED_ATTACHMENT_STATUS = "UNKNOWN_NOT_AUTHORITY_BOUND__M5_DISPLAY_TRANSFORM_NOT_PROMOTED"
EXPECTED_TARGET_SEMANTICS = "MASS_PROPERTY_SCENARIO_SEMANTIC_ONLY__NO_PLANT_OR_CONTACT_AUTHORITY"
COORDINATE_UNITS = ("rad",) * 6 + ("m",) * 2
RATE_UNITS = ("rad/s",) * 6 + ("m/s",) * 2

EXPECTED_SOURCE_PINS = (
    ("configuration_state_vector_contract", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/m4_l02_configuration_state_contract_v1/R2_CONFIGURATION_STATE_VECTOR_CONTRACT_V1.yaml", 40064, "C60744D6978AFA8987D3D294792044380ACA27E0F30C2E3DE7C0AA2747F23D63"),
    ("configuration_dynamics_use_matrix", "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/m4_l02_configuration_state_contract_v1/R2_CONFIGURATION_DYNAMICS_USE_MATRIX_V1.yaml", 5597, "5DCC1661F268D388C5E78B8A25531E5D20CAB0EF494209C6234D27234AAD73E7"),
    ("display_only_transform_candidates", "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp2_mass_properties/CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml", 20434, "F43D871FAA6831652441C75916B1E890D760EAE3D5781DDF3650CFB65159DE51"),
    ("existing_23d_plant_contract", "30_simulation/r2_dynamics_engineering_closure/time_varying_torque_plant_candidate_v1/contracts/R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_CONTRACT_V1.json", 13875, "570256E08C982712EFDECC9FA4A38586018779040AC33B53DDFC0AB45C9A3BD7"),
    ("existing_23d_plant_source", "30_simulation/r2_dynamics_engineering_closure/time_varying_torque_plant_candidate_v1/src/time_varying_torque_plant.py", 69319, "5C3D281FBC17847FAEA7A4A4453B6DB8401B7551A9CC1C074F49AB3234AD1C9F"),
    ("existing_23d_plant_gate", "30_simulation/r2_dynamics_engineering_closure/time_varying_torque_plant_candidate_v1/results/R2_TIME_VARYING_TORQUE_PLANT_CANDIDATE_GATE_V1.json", 11641, "5DC60E93A881AB35BDA912115A4782DD11DA0903B444201491D06642326DA2D1"),
    ("current_mech_rl_system_interface", "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml", 6716, "B105766EC1F19EEC25D4A40F4D4AFAEAB3955AE9E0EDFFCD691754E5A3DBB8E8"),
)

EXPECTED_GATE_ROWS = (
    ("K01", "HASH_BOUND_SOURCE_PINS_EXACT"),
    ("K02", "CONTRACT_FRAME_UNIT_STATE_AND_AUTHORITY_SEMANTICS_EXACT"),
    ("K03", "C08_AUTHORITATIVE_ATTACHMENT_NULL_FAIL_CLOSED_NOT_EVALUATED"),
    ("K04", "C09_AUTHORITATIVE_ATTACHMENT_NULL_FAIL_CLOSED_NOT_EVALUATED"),
    ("K05", "DISPLAY_TRANSFORM_NOT_PROMOTED_AND_PREGRASP_NOT_DYNAMICS_VALIDATED"),
    ("K06", "SYNTHETIC_FIXTURE_CLASS_FRAME_UNITS_AND_SE3_VALID"),
    ("K07", "PARALLEL_AXIS_AND_ROTATION_COMPOSITE_INERTIA_FINITE"),
    ("K08", "DIRECT_VS_SPATIAL_INERTIA_FORMULA_CROSS"),
    ("K09", "COMPOSITE_INERTIA_SYMMETRIC_POSITIVE_AND_PHYSICAL"),
    ("K10", "POST_CAPTURE_23D_STATE_AND_DERIVED_6D_BASE_TWIST"),
    ("K11", "EVENT_LINEAR_MOMENTUM_CONSERVED"),
    ("K12", "EVENT_ANGULAR_MOMENTUM_ABOUT_NUMERIC_REFERENCE_POINT_CONSERVED_AND_TRANSLATION_COVARIANT"),
    ("K13", "ZERO_TARGET_RIGID_DEGENERATION_TO_SERVICE_EXACT"),
    ("K14", "COLOCATED_AXIS_ALIGNED_RIGID_INERTIA_SUM_DEGENERATION"),
    ("K15", "TARGET_MASS_AND_INERTIA_SCALING_AFFINE_SPATIAL_CHECK"),
    ("K16", "ATTACHMENT_TRANSLATION_SENSITIVITY_OBSERVED"),
    ("K17", "ATTACHMENT_ROTATION_SENSITIVITY_OBSERVED"),
    ("K18", "REFERENCE_FRAME_COVARIANCE_OF_CG_AND_INERTIA"),
    ("K19", "INELASTIC_EVENT_ENERGY_NOT_CLAIMED"),
    ("K20", "DETERMINISTIC_SYNTHETIC_FIXTURE_REPLAY"),
    ("K21", "MUTATION_AND_FAIL_CLOSED_NEGATIVE_CONTROLS"),
    ("K22", "MINIMUM_REAL_INPUTS_LISTED_AND_ALL_DOWNSTREAM_AUTHORITY_FALSE"),
)

FROZEN_PACKAGE_PATHS = (
    "README.md",
    "contracts/POST_CAPTURE_SPATIAL_INERTIA_KERNEL_CONTRACT_V1.json",
    "evaluate_post_capture_spatial_inertia.py",
    "independent_validate_post_capture_spatial_inertia.py",
    "results/POST_CAPTURE_SPATIAL_INERTIA_KERNEL_EVIDENCE_V1.json",
    "results/POST_CAPTURE_SPATIAL_INERTIA_KERNEL_GATE_V1.json",
    "run_validation.py",
    "src/__init__.py",
    "src/post_capture_spatial_inertia.py",
    "tests/conftest.py",
    "tests/test_candidate.py",
)


class IndependentValidationError(RuntimeError):
    pass


def reject_constant(token: str) -> None:
    raise ValueError(f"STRICT_JSON_NONFINITE:{token}")


def unique_pairs(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"STRICT_JSON_DUPLICATE:{key}")
        result[key] = value
    return result


def strict_loads(text: str) -> Any:
    return json.loads(text, object_pairs_hook=unique_pairs, parse_constant=reject_constant)


def strict_read(path: Path) -> Any:
    return strict_loads(path.read_text(encoding="utf-8"))


def builtin(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [builtin(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [builtin(item) for item in value]
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(builtin(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def raw_record(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest().upper()}


def expected_pin_documents() -> list[dict[str, Any]]:
    return [
        {"id": identifier, "path": path, "bytes": size, "sha256": sha}
        for identifier, path, size, sha in EXPECTED_SOURCE_PINS
    ]


def check_no_forbidden_imports() -> dict[str, Any]:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    forbidden_tokens = (
        "post_capture_spatial_inertia",
        "evaluate_post_capture_spatial_inertia",
    )
    violations = [name for name in imports if any(token in name for token in forbidden_tokens)]
    return {"imports": imports, "forbidden": violations, "pass": not violations}


def audit_contract(contract: Mapping[str, Any]) -> dict[str, Any]:
    raw = raw_record(CONTRACT_PATH)
    current = contract.get("current_system_authority_contract", {})
    minimum = contract.get("minimum_true_inputs_to_bind_existing_23d_plant", [])
    boundary = contract.get("release_boundary", {})
    admission = current.get("successful_admission_receipt_contract", {})
    event = contract.get("model_contract", {}).get("event_momentum", {})
    checks = {
        "raw_bytes": raw["bytes"] == EXPECTED_CONTRACT_BYTES,
        "raw_sha": raw["sha256"] == EXPECTED_CONTRACT_RAW_SHA256,
        "canonical_sha": canonical_hash(contract) == EXPECTED_CONTRACT_CANONICAL_SHA256,
        "schema": contract.get("schema") == "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_CONTRACT_V1",
        "review_status": contract.get("review_status") == EXPECTED_REVIEW_STATUS,
        "maximum_claim": contract.get("maximum_claim") == EXPECTED_MAXIMUM_CLAIM,
        "source_pins": contract.get("source_pins") == expected_pin_documents(),
        "attachment_null": current.get("required_value") is None,
        "attachment_status": current.get("required_status") == EXPECTED_ATTACHMENT_STATUS,
        "operational_authority_false": current.get("operational_attachment_authority") is False,
        "target_semantics": current.get("target_attached_semantics") == EXPECTED_TARGET_SEMANTICS,
        "display_promotion_forbidden": current.get("display_transform_promotion_forbidden") is True,
        "zero_fill_forbidden": current.get("zero_fill_forbidden") is True,
        "kernel_call_false": current.get("kernel_call_for_current_instance_allowed") is False,
        "receipt_schema": admission.get("required_schema") == "AUTHORITY_BOUND_ATTACHMENT_SE3_RECEIPT_V1",
        "receipt_pin_required_but_currently_absent": admission.get("required_contract_source_pin_id") == "attachment_authority_receipt"
        and admission.get("current_contract_contains_attachment_authority_receipt_pin") is False
        and not any(item.get("id") == "attachment_authority_receipt" for item in contract.get("source_pins", [])),
        "receipt_frame_ids": admission.get("required_frame_ids") == {"parent_frame": "E", "child_frame": "T", "transform_field": "T_E_T_rows"},
        "bare_authority_inputs_forbidden": admission.get("caller_supplied_status_or_boolean_without_pinned_receipt_forbidden") is True,
        "numeric_reference_point_contract": event.get("origin_O_in_I_m", "").startswith("position of angular-momentum reference point O")
        and event.get("angular_momentum_translation_law") == "H_O_prime=H_O-(r_O_prime-r_O)xP",
        "state_dimension": contract.get("model_contract", {}).get("state_mapping", {}).get("existing_plant_physical_state_dimension") == 23,
        "coordinate_units": tuple(contract.get("model_contract", {}).get("state_mapping", {}).get("joint_coordinate_units", [])) == COORDINATE_UNITS,
        "rate_units": tuple(contract.get("model_contract", {}).get("state_mapping", {}).get("joint_rate_units", [])) == RATE_UNITS,
        "energy_not_conserved": contract.get("model_contract", {}).get("energy_semantics") == "PERFECTLY_INELASTIC_RIGIDIFICATION_ENERGY_IS_NOT_CONSERVED_OR_CREDITED",
        "minimum_inputs": len(minimum) == 7 and [item.get("id", "")[:4] for item in minimum] == [f"PC{i:02d}" for i in range(1, 8)],
        "authority_false": boundary.get("candidate_only") is True
        and boundary.get("synthetic_fixture_only") is True
        and all(value is False for key, value in boundary.items() if key not in {"candidate_only", "synthetic_fixture_only"})
        and contract.get("next_stage_authorized") is False
        and contract.get("release_credit") is False,
    }
    return {"raw": raw, "checks": checks, "all_pass": all(checks.values())}


def audit_sources(contract: Mapping[str, Any]) -> dict[str, Any]:
    records = []
    for expected in expected_pin_documents():
        path = PROJECT_ROOT / expected["path"]
        actual = raw_record(path) if path.is_file() else {"bytes": None, "sha256": None}
        records.append({"id": expected["id"], "path": expected["path"], **actual, "match": actual["bytes"] == expected["bytes"] and actual["sha256"] == expected["sha256"]})
    return {
        "contract_exact": contract.get("source_pins") == expected_pin_documents(),
        "records": records,
        "all_match": contract.get("source_pins") == expected_pin_documents() and all(item["match"] for item in records),
    }


def authoritative_facts(states: Mapping[str, Any], uses: Mapping[str, Any]) -> dict[str, Any]:
    state_by_id = {item["configuration_id"]: item for item in states["configurations"]}
    use_by_id = {item["configuration_id"]: item for item in uses["records"]}
    records = {}
    for identifier, mass, inertia, maximum_use in (
        ("C08", 22.0, [0.231629, 0.422149, 0.489336], "TARGET_22KG_MASS_INERTIA_FIXTURE_ONLY__NO_ATTACHED_PLANT"),
        ("C09", 150.0, [74.805599, 74.829903, 26.592617], "TARGET_150KG_MASS_INERTIA_FIXTURE_ONLY__NO_ATTACHED_PLANT"),
    ):
        state = state_by_id[identifier]
        target = state["authoritative_state"]["target"]
        use = use_by_id[identifier]
        checks = {
            "attachment_null": target["attachment_transform_S_rows"]["value"] is None,
            "attachment_status": target["attachment_transform_S_rows"]["status"] == EXPECTED_ATTACHMENT_STATUS,
            "operational_authority_false": target["operational_attachment_authority"] is False,
            "semantic_only": target["target_attached"]["status"] == EXPECTED_TARGET_SEMANTICS,
            "design_mass": target["design_mass_kg"]["value"] == mass,
            "design_inertia": target["design_inertia_diag_kg_m2"]["value"] == inertia,
            "operational_state": state["operational_state"] == "NOT_OPERATIONALLY_AUTHORIZED",
            "state_parent_false": state["parent_gate_credit"] is False,
            "fixture_loading_only": use["design_mass_property_loading_allowed"] is True and use["maximum_permitted_use"] == maximum_use,
            "plant_false": use["target_attachment_plant_allowed"] is False,
            "nonabort_false": use["non_abort_operational_authority"] is False,
            "use_parent_false": use["parent_gate_credit"] is False,
        }
        records[identifier] = {"checks": checks, "all_pass": all(checks.values())}
    return {"records": records, "all_pass": all(item["all_pass"] for item in records.values())}


def audit_authority_sources() -> dict[str, Any]:
    states = strict_read(PROJECT_ROOT / EXPECTED_SOURCE_PINS[0][1])
    uses = strict_read(PROJECT_ROOT / EXPECTED_SOURCE_PINS[1][1])
    facts = authoritative_facts(states, uses)
    display = (PROJECT_ROOT / EXPECTED_SOURCE_PINS[2][1]).read_text(encoding="utf-8")
    display_checks = {
        "display_only_not_baseline": "target capture transforms are display-only in M5 and are not written back to any baseline" in display,
        "pregrasp_not_validated": "PREGRASP scene candidate is not dynamics-validated for 22 kg or 150 kg capture" in display,
    }
    return {"facts": facts, "display_checks": display_checks, "all_pass": facts["all_pass"] and all(display_checks.values())}


def authority_false(document: Mapping[str, Any]) -> bool:
    return all(
        document.get(key) is False
        for key in (
            "current_system_instance_evaluated",
            "contact_valid",
            "attachment_valid",
            "target_attachment_plant_valid",
            "hardware_valid",
            "non_abort_authorized",
            "parent_dynamics_engineering_complete",
            "next_stage_authorized",
            "release_credit",
        )
    )


def audit_gate_structure(gate: Mapping[str, Any]) -> dict[str, Any]:
    rows = gate.get("checks", [])
    checks = {
        "raw_bytes": raw_record(GATE_PATH)["bytes"] == EXPECTED_GATE_BYTES,
        "raw_sha": raw_record(GATE_PATH)["sha256"] == EXPECTED_GATE_RAW_SHA256,
        "rows_exact": tuple((row.get("id"), row.get("name")) for row in rows) == EXPECTED_GATE_ROWS,
        "unique": len({row.get("id") for row in rows}) == 22,
        "all_rows_pass": all(row.get("pass") is True for row in rows),
        "summary": gate.get("passed") == 22 and gate.get("total") == 22 and gate.get("all_checks_pass") is True,
        "review_status": gate.get("review_status") == EXPECTED_REVIEW_STATUS,
        "maximum_claim": gate.get("maximum_claim") == EXPECTED_MAXIMUM_CLAIM and gate.get("verdict") == EXPECTED_MAXIMUM_CLAIM,
        "current_status": gate.get("current_C08_status") == EXPECTED_CURRENT_STATUS and gate.get("current_C09_status") == EXPECTED_CURRENT_STATUS,
        "authority_false": authority_false(gate),
    }
    return {"raw": raw_record(GATE_PATH), "checks": checks, "all_pass": all(checks.values())}


def directory_payload_audit() -> dict[str, Any]:
    actual = sorted(path.relative_to(PACKAGE_ROOT).as_posix() for path in PACKAGE_ROOT.rglob("*") if path.is_file())
    required = set(FROZEN_PACKAGE_PATHS) | {MANIFEST_PATH.relative_to(PACKAGE_ROOT).as_posix()}
    allowed = {RECEIPT_PATH.relative_to(PACKAGE_ROOT).as_posix()}
    actual_set = set(actual)
    return {
        "actual_file_paths": actual,
        "missing": sorted(required - actual_set),
        "unexpected": sorted(actual_set - required - allowed),
        "exact": not (required - actual_set) and not (actual_set - required - allowed),
    }


def expected_manifest_entries() -> list[dict[str, Any]]:
    entries = []
    for relative in FROZEN_PACKAGE_PATHS:
        path = PACKAGE_ROOT / relative
        raw = path.read_bytes()
        entries.append({"path": relative, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest().upper()})
    return entries


def manifest_is_exact(manifest: Mapping[str, Any]) -> tuple[bool, dict[str, bool]]:
    entries = manifest.get("package_entries", [])
    paths = [item.get("path") for item in entries]
    expected = expected_manifest_entries()
    payload = directory_payload_audit()
    checks = {
        "schema": manifest.get("schema") == "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_MANIFEST_V1",
        "entries_exact": entries == expected,
        "count": manifest.get("package_entry_count") == 11 == len(entries),
        "unique": len(paths) == len(set(paths)) == 11,
        "ordered": paths == list(FROZEN_PACKAGE_PATHS),
        "entries_hash": manifest.get("package_entries_canonical_sha256") == canonical_hash(expected),
        "allowlist": manifest.get("frozen_package_path_allowlist") == list(FROZEN_PACKAGE_PATHS),
        "self_excluded": manifest.get("self_excluded") is True and manifest.get("self_excluded_path") == MANIFEST_PATH.relative_to(PACKAGE_ROOT).as_posix() and manifest.get("self_excluded_path") not in paths,
        "receipt_only_exclusion": manifest.get("exclusions") == [RECEIPT_PATH.relative_to(PACKAGE_ROOT).as_posix()] and manifest.get("independent_validation_receipt_excluded") is True,
        "cache_forbidden": manifest.get("cache_bytecode_or_unlisted_payload_allowed") is False,
        "payload_exact": payload["exact"] and manifest.get("directory_payload_exact_at_generation") is True,
        "pins": manifest.get("external_source_pins") == expected_pin_documents() and manifest.get("external_source_pin_count") == 7,
        "authority": manifest.get("next_stage_authorized") is False and manifest.get("release_credit") is False,
    }
    return all(checks.values()), checks


def vec(value: Any, size: int, token: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.shape != (size,) or not np.all(np.isfinite(array)):
        raise IndependentValidationError(token)
    return array


def mat(value: Any, shape: tuple[int, int], token: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.shape != shape or not np.all(np.isfinite(array)):
        raise IndependentValidationError(token)
    return array


def cross_matrix(value: Any) -> np.ndarray:
    x, y, z = vec(value, 3, "CROSS_VECTOR_INVALID")
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def paa(mass: float, displacement: Any) -> np.ndarray:
    d = vec(displacement, 3, "PAA_DISPLACEMENT_INVALID")
    return mass * ((d @ d) * np.eye(3) - np.outer(d, d))


def validate_transform_independent(value: Any) -> np.ndarray:
    transform = mat(value, (4, 4), "TRANSFORM_SHAPE_OR_FINITE")
    if np.max(np.abs(transform[3] - np.array([0.0, 0.0, 0.0, 1.0]))) > 1.0e-14:
        raise IndependentValidationError("TRANSFORM_HOMOGENEOUS_ROW")
    rotation = transform[:3, :3]
    if np.max(np.abs(rotation.T @ rotation - np.eye(3))) > 2.0e-12:
        raise IndependentValidationError("TRANSFORM_ROTATION_ORTHONORMAL")
    if abs(np.linalg.det(rotation) - 1.0) > 2.0e-12:
        raise IndependentValidationError("TRANSFORM_ROTATION_PROPER")
    return transform


def validate_fixture_independent(fixture: Mapping[str, Any]) -> None:
    if fixture.get("classification") != "SYNTHETIC_EXACT_NUMERICAL_FIXTURE__NOT_CURRENT_SYSTEM_INSTANCE":
        raise IndependentValidationError("FIXTURE_CLASSIFICATION")
    if fixture.get("attachment_transform_authority") != "SYNTHETIC_TEST_ONLY" or fixture.get("contact_or_attachment_evidence") is not False:
        raise IndependentValidationError("FIXTURE_AUTHORITY")
    expected_frames = {"service_mass_properties": "B", "target_mass_properties": "T", "T_B_E": "B_FROM_E", "T_E_T": "E_FROM_T", "T_I_B": "I_FROM_B", "momentum": "I_ABOUT_O"}
    if fixture.get("frames") != expected_frames:
        raise IndependentValidationError("FIXTURE_FRAMES")
    units = fixture.get("units", {})
    if (units.get("mass"), units.get("cg_translation"), units.get("inertia"), units.get("linear_momentum"), units.get("angular_momentum")) != ("kg", "m", "kg*m^2", "kg*m/s", "kg*m^2/s"):
        raise IndependentValidationError("FIXTURE_UNITS")
    if tuple(units.get("joint_coordinates", [])) != COORDINATE_UNITS or tuple(units.get("joint_rates", [])) != RATE_UNITS:
        raise IndependentValidationError("FIXTURE_JOINT_UNITS")
    if not fixture.get("inertial_origin_O_definition"):
        raise IndependentValidationError("FIXTURE_ORIGIN")
    vec(fixture.get("origin_O_in_I_m"), 3, "FIXTURE_ORIGIN_VECTOR")
    for key, expected_frame in (("service", "B"), ("target", "T")):
        body = fixture[key]
        if body.get("frame") != expected_frame:
            raise IndependentValidationError(f"FIXTURE_{key.upper()}_BODY_FRAME")
        if float(body["mass_kg"]) <= 0:
            raise IndependentValidationError("FIXTURE_MASS")
        vec(body["cg_m"], 3, "FIXTURE_CG")
        inertia = mat(body["inertia_cg_kg_m2"], (3, 3), "FIXTURE_INERTIA")
        if np.max(np.abs(inertia - inertia.T)) > 2.0e-12:
            raise IndependentValidationError("FIXTURE_INERTIA_SYMMETRY")
        eig = np.linalg.eigvalsh(inertia)
        if eig[0] < 1.0e-10 or eig[-1] > eig[0] + eig[1] + 1.0e-10:
            raise IndependentValidationError("FIXTURE_INERTIA_PHYSICAL")
    for key in ("T_B_E_rows", "T_E_T_rows", "T_I_B_rows"):
        validate_transform_independent(fixture[key])
    vec(fixture["linear_momentum_I_kg_m_s"], 3, "FIXTURE_P")
    vec(fixture["angular_momentum_about_O_I_kg_m2_s"], 3, "FIXTURE_H")
    vec(fixture["joint_positions_mixed_rad_m"], 8, "FIXTURE_Q")


def independent_combine(fixture: Mapping[str, Any], *, mass_scale: float = 1.0, transform_E_T: Any | None = None) -> dict[str, Any]:
    service = fixture["service"]; target = fixture["target"]
    transform_B_E = validate_transform_independent(fixture["T_B_E_rows"])
    transform_E_T = validate_transform_independent(fixture["T_E_T_rows"] if transform_E_T is None else transform_E_T)
    with np.errstate(over="ignore", invalid="ignore"):
        composed_transform = transform_B_E @ transform_E_T
    transform_B_T = validate_transform_independent(composed_transform)
    rotation = transform_B_T[:3, :3]
    if not math.isfinite(mass_scale) or mass_scale < 0.0:
        raise IndependentValidationError("MASS_SCALE_INVALID")
    mass_s = float(service["mass_kg"]); mass_t = mass_scale * float(target["mass_kg"])
    cg_s = vec(service["cg_m"], 3, "SERVICE_CG")
    cg_t = rotation @ vec(target["cg_m"], 3, "TARGET_CG") + transform_B_T[:3, 3]
    inertia_s = mat(service["inertia_cg_kg_m2"], (3, 3), "SERVICE_INERTIA")
    inertia_t = mass_scale * rotation @ mat(target["inertia_cg_kg_m2"], (3, 3), "TARGET_INERTIA") @ rotation.T
    mass = mass_s + mass_t
    cg = (mass_s * cg_s + mass_t * cg_t) / mass
    inertia_origin = inertia_s + paa(mass_s, cg_s) + inertia_t + paa(mass_t, cg_t)
    inertia_cg = inertia_origin - paa(mass, cg)
    return {"mass_kg": mass, "cg_B_m": cg, "inertia_cg_B_kg_m2": inertia_cg, "target_cg_B_m": cg_t, "target_inertia_cg_B_kg_m2": inertia_t, "T_B_T": transform_B_T}


def spatial_matrix(mass: float, cg: Any, inertia_cg: Any) -> np.ndarray:
    cg = vec(cg, 3, "SPATIAL_CG"); inertia_cg = mat(inertia_cg, (3, 3), "SPATIAL_INERTIA")
    s = cross_matrix(cg)
    return np.block([[mass * np.eye(3), -mass * s], [mass * s, inertia_cg + paa(mass, cg)]])


def quaternion_rotation(quaternion: Any) -> np.ndarray:
    q = vec(quaternion, 4, "QUATERNION")
    if abs(np.linalg.norm(q) - 1.0) > 2.0e-12:
        raise IndependentValidationError("QUATERNION_NORM")
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def reproduce_case(run: Mapping[str, Any]) -> dict[str, Any]:
    fixture = run["fixture"]
    validate_fixture_independent(fixture)
    independent = independent_combine(fixture)
    stored = run["composite_direct"]
    direct_errors = {
        "mass_kg": abs(independent["mass_kg"] - float(stored["mass_kg"])),
        "cg_m": float(np.max(np.abs(independent["cg_B_m"] - np.asarray(stored["cg_B_m"])))),
        "inertia_kg_m2": float(np.max(np.abs(independent["inertia_cg_B_kg_m2"] - np.asarray(stored["inertia_cg_B_kg_m2"])))),
        "target_cg_m": float(np.max(np.abs(independent["target_cg_B_m"] - np.asarray(stored["target_cg_B_m"])))),
        "target_inertia_kg_m2": float(np.max(np.abs(independent["target_inertia_cg_B_kg_m2"] - np.asarray(stored["target_inertia_cg_B_kg_m2"])))),
    }
    service = fixture["service"]
    target_J = spatial_matrix(float(fixture["target"]["mass_kg"]), independent["target_cg_B_m"], independent["target_inertia_cg_B_kg_m2"])
    total_J = spatial_matrix(float(service["mass_kg"]), service["cg_m"], service["inertia_cg_kg_m2"]) + target_J
    stored_J = np.asarray(run["independent_spatial_formula_cross"]["spatial_inertia_B_v_omega_order"])
    spatial_error = float(np.max(np.abs(total_J - stored_J)))
    transform_I_B = validate_transform_independent(fixture["T_I_B_rows"])
    rotation = transform_I_B[:3, :3]; base_position = transform_I_B[:3, 3]
    mass = independent["mass_kg"]; cg_B = independent["cg_B_m"]; inertia_B = independent["inertia_cg_B_kg_m2"]
    offset_I = rotation @ cg_B; cg_I = base_position + offset_I; inertia_I = rotation @ inertia_B @ rotation.T
    P = vec(fixture["linear_momentum_I_kg_m_s"], 3, "P"); H = vec(fixture["angular_momentum_about_O_I_kg_m2_s"], 3, "H")
    origin_O = vec(fixture["origin_O_in_I_m"], 3, "ORIGIN_O")
    lever_O_C = cg_I - origin_O
    omega = np.linalg.solve(inertia_I, H - np.cross(lever_O_C, P))
    velocity_base = P / mass - np.cross(omega, offset_I)
    state = run["post_capture_state_initialization"]
    stored_twist = np.asarray(state["derived_base_twist_I_m_s_rad_s"])
    expected_twist = np.concatenate((velocity_base, omega))
    recomputed_P = mass * (stored_twist[:3] + np.cross(stored_twist[3:], offset_I))
    recomputed_H = inertia_I @ stored_twist[3:] + np.cross(lever_O_C, recomputed_P)
    state_23 = np.asarray(state["physical_state_23"])
    state_checks = {
        "dimension_23": state_23.shape == (23,),
        "base_position": float(np.max(np.abs(state_23[:3] - base_position))),
        "quaternion_rotation": float(np.max(np.abs(quaternion_rotation(state_23[3:7]) - rotation))),
        "q": float(np.max(np.abs(state_23[7:15] - np.asarray(fixture["joint_positions_mixed_rad_m"])))),
        "qdot": float(np.max(np.abs(state_23[15:23]))),
        "twist": float(np.max(np.abs(stored_twist - expected_twist))),
        "linear_momentum": float(np.max(np.abs(recomputed_P - P))),
        "angular_momentum": float(np.max(np.abs(recomputed_H - H))),
        "energy_not_evaluated": state["energy_conservation_evaluated"] is False,
        "origin_O": float(np.max(np.abs(np.asarray(state["origin_O_in_I_m"]) - origin_O))),
    }
    eig = np.linalg.eigvalsh(independent["inertia_cg_B_kg_m2"])
    return {
        "direct_errors": direct_errors,
        "spatial_matrix_max_abs": spatial_error,
        "state": state_checks,
        "inertia_symmetry": float(np.max(np.abs(independent["inertia_cg_B_kg_m2"] - independent["inertia_cg_B_kg_m2"].T))),
        "inertia_eigenvalues": eig,
        "inertia_triangle": bool(eig[-1] <= eig[0] + eig[1] + 1.0e-10),
        "finite": bool(np.all(np.isfinite(independent["inertia_cg_B_kg_m2"]))),
        "independent_output": independent,
    }


def independent_diagnostics(
    run: Mapping[str, Any], stored_diagnostic: Mapping[str, Any]
) -> dict[str, Any]:
    fixture = run["fixture"]
    service = fixture["service"]; target = fixture["target"]
    nominal = independent_combine(fixture)
    zero_result = independent_combine(fixture, mass_scale=0.0)
    zero = {
        "mass_abs_kg": abs(zero_result["mass_kg"] - float(service["mass_kg"])),
        "cg_max_abs_m": float(
            np.max(np.abs(zero_result["cg_B_m"] - np.asarray(service["cg_m"])))
        ),
        "inertia_max_abs_kg_m2": float(
            np.max(
                np.abs(
                    zero_result["inertia_cg_B_kg_m2"]
                    - np.asarray(service["inertia_cg_kg_m2"])
                )
            )
        ),
    }
    colocated_fixture = copy.deepcopy(fixture)
    colocated_fixture["T_B_E_rows"] = np.eye(4)
    colocated_fixture["T_E_T_rows"] = np.eye(4)
    colocated_fixture["target"]["cg_m"] = copy.deepcopy(service["cg_m"])
    colocated_result = independent_combine(colocated_fixture)
    colocated_target_inertia = np.asarray(target["inertia_cg_kg_m2"])
    colocated = {
        "cg_max_abs_m": float(
            np.max(
                np.abs(colocated_result["cg_B_m"] - np.asarray(service["cg_m"]))
            )
        ),
        "inertia_sum_max_abs_kg_m2": float(
            np.max(
                np.abs(
                    colocated_result["inertia_cg_B_kg_m2"]
                    - (
                        np.asarray(service["inertia_cg_kg_m2"])
                        + colocated_target_inertia
                    )
                )
            )
        ),
    }
    scaling = []
    for scale in (0.5, 2.0):
        scaled = independent_combine(fixture, mass_scale=scale)
        scaling.append({
            "scale": scale,
            "mass_affine_abs_kg": abs(scaled["mass_kg"] - (float(service["mass_kg"]) + scale * float(target["mass_kg"]))),
            "finite": bool(np.all(np.isfinite(scaled["inertia_cg_B_kg_m2"]))),
        })
    nominal_E_T = np.asarray(fixture["T_E_T_rows"], dtype=float)
    translated = nominal_E_T.copy(); translated[:3, 3] += np.array([0.2, -0.1, 0.05])
    translated_result = independent_combine(fixture, transform_E_T=translated)
    axis = np.array([0.4, 0.1, -0.7]); axis /= np.linalg.norm(axis); s = cross_matrix(axis); angle = 0.53
    rotation_delta = np.eye(3) + math.sin(angle) * s + (1 - math.cos(angle)) * (s @ s)
    rotated = nominal_E_T.copy(); rotated[:3, :3] = nominal_E_T[:3, :3] @ rotation_delta
    rotated_result = independent_combine(fixture, transform_E_T=rotated)
    sensitivity = {
        "translation_cg_change_m": float(np.linalg.norm(translated_result["cg_B_m"] - nominal["cg_B_m"])),
        "rotation_inertia_change_kg_m2": float(np.linalg.norm(rotated_result["inertia_cg_B_kg_m2"] - nominal["inertia_cg_B_kg_m2"])),
    }
    axis = np.array([0.2, -0.5, 0.9]); axis /= np.linalg.norm(axis); s = cross_matrix(axis); angle = -0.44
    R = np.eye(3) + math.sin(angle) * s + (1 - math.cos(angle)) * (s @ s); p = np.array([-0.3, 0.2, 0.1])
    service_prime = copy.deepcopy(service); service_prime["cg_m"] = R @ np.asarray(service["cg_m"]) + p; service_prime["inertia_cg_kg_m2"] = R @ np.asarray(service["inertia_cg_kg_m2"]) @ R.T
    fixture_prime = copy.deepcopy(fixture); fixture_prime["service"] = service_prime
    T_Bp_B = np.eye(4); T_Bp_B[:3, :3] = R; T_Bp_B[:3, 3] = p
    fixture_prime["T_B_E_rows"] = T_Bp_B @ np.asarray(fixture["T_B_E_rows"])
    transformed = independent_combine(fixture_prime)
    covariance = {
        "cg_max_abs_m": float(np.max(np.abs(transformed["cg_B_m"] - (R @ nominal["cg_B_m"] + p)))),
        "inertia_max_abs_kg_m2": float(np.max(np.abs(transformed["inertia_cg_B_kg_m2"] - R @ nominal["inertia_cg_B_kg_m2"] @ R.T))),
    }
    stored_reference = stored_diagnostic["reference_point_translation"]
    delta = vec(stored_reference["translation_delta_I_m"], 3, "REFERENCE_DELTA")
    T_I_B = validate_transform_independent(fixture["T_I_B_rows"])
    R_I_B = T_I_B[:3, :3]
    cg_I = T_I_B[:3, 3] + R_I_B @ nominal["cg_B_m"]
    inertia_I = R_I_B @ nominal["inertia_cg_B_kg_m2"] @ R_I_B.T
    P = vec(fixture["linear_momentum_I_kg_m_s"], 3, "REFERENCE_P")
    H = vec(fixture["angular_momentum_about_O_I_kg_m2_s"], 3, "REFERENCE_H")
    origin = vec(fixture["origin_O_in_I_m"], 3, "REFERENCE_ORIGIN")
    omega = np.linalg.solve(inertia_I, H - np.cross(cg_I - origin, P))
    shifted_omega = np.linalg.solve(
        inertia_I,
        H - np.cross(delta, P) - np.cross(cg_I - origin - delta, P),
    )
    wrong_omega = np.linalg.solve(
        inertia_I,
        H + np.cross(delta, P) - np.cross(cg_I - origin - delta, P),
    )
    reference_point = {
        "twist_invariance_max_abs": float(np.max(np.abs(shifted_omega - omega))),
        "wrong_cross_sign_omega_delta": float(np.max(np.abs(wrong_omega - omega))),
        "law_exact": stored_reference.get("H_translation_law") == "H_O_prime=H_O-delta_r_O_cross_P",
    }
    stored_zero = stored_diagnostic["rigid_degenerations"]["zero_target"]
    stored_colocated = stored_diagnostic["rigid_degenerations"][
        "colocated_axis_aligned"
    ]
    stored_scaling = stored_diagnostic["mass_scaling"]["records"]
    stored_sensitivity = stored_diagnostic["attachment_sensitivity"]
    stored_covariance = stored_diagnostic["frame_covariance"]
    stored_cross = {
        "zero_max_abs": max(
            abs(zero[key] - float(stored_zero[key])) for key in zero
        ),
        "colocated_max_abs": max(
            abs(colocated[key] - float(stored_colocated[key])) for key in colocated
        ),
        "scaling_mass_affine_max_abs": max(
            abs(item["mass_affine_abs_kg"] - float(stored["mass_affine_abs_kg"]))
            for item, stored in zip(scaling, stored_scaling)
        ),
        "translation_sensitivity_abs": abs(
            sensitivity["translation_cg_change_m"]
            - float(stored_sensitivity["translation_cg_change_m"])
        ),
        "rotation_sensitivity_abs": abs(
            sensitivity["rotation_inertia_change_kg_m2"]
            - float(stored_sensitivity["rotation_inertia_change_kg_m2"])
        ),
        "frame_cg_abs": abs(
            covariance["cg_max_abs_m"] - float(stored_covariance["cg_max_abs_m"])
        ),
        "frame_inertia_abs": abs(
            covariance["inertia_max_abs_kg_m2"]
            - float(stored_covariance["inertia_max_abs_kg_m2"])
        ),
        "reference_twist_invariance_abs": abs(
            reference_point["twist_invariance_max_abs"]
            - float(stored_reference["twist_invariance_max_abs"])
        ),
    }
    return {
        "zero": zero,
        "colocated": colocated,
        "scaling": scaling,
        "sensitivity": sensitivity,
        "covariance": covariance,
        "reference_point": reference_point,
        "stored_diagnostic_numeric_cross": stored_cross,
    }


def reproduce_physics(evidence: Mapping[str, Any]) -> dict[str, Any]:
    cases = {}
    diagnostics = {}
    for identifier in ("C08", "C09"):
        run = evidence["synthetic_fixture_runs"][identifier]
        cases[identifier] = reproduce_case(run)
        diagnostics[identifier] = independent_diagnostics(
            run, evidence["diagnostics"][identifier]
        )
    return {"cases": cases, "diagnostics": diagnostics}


def gate_document_valid(gate: Mapping[str, Any]) -> bool:
    rows = gate.get("checks", [])
    return (
        tuple((row.get("id"), row.get("name")) for row in rows) == EXPECTED_GATE_ROWS
        and len({row.get("id") for row in rows}) == 22
        and all(row.get("pass") is True for row in rows)
        and gate.get("passed") == 22
        and gate.get("total") == 22
        and gate.get("all_checks_pass") is True
        and gate.get("review_status") == EXPECTED_REVIEW_STATUS
        and gate.get("current_C08_status") == EXPECTED_CURRENT_STATUS
        and gate.get("current_C09_status") == EXPECTED_CURRENT_STATUS
        and authority_false(gate)
    )


def require_attachment(receipt: Mapping[str, Any] | None, configuration_id: str, contract: Mapping[str, Any]) -> None:
    if receipt is None:
        raise IndependentValidationError("MISSING_ATTACHMENT")
    if not isinstance(receipt, Mapping):
        raise IndependentValidationError("RECEIPT_NOT_MAPPING")
    if configuration_id not in {"C08", "C09"}:
        raise IndependentValidationError("CONFIGURATION_ID")
    pin = next((item for item in contract.get("source_pins", []) if item.get("id") == "attachment_authority_receipt"), None)
    if pin is None:
        raise IndependentValidationError("ATTACHMENT_AUTHORITY_SOURCE_PIN_MISSING")
    path = PROJECT_ROOT / pin["path"]
    actual = raw_record(path)
    if actual["bytes"] != pin["bytes"] or actual["sha256"] != pin["sha256"]:
        raise IndependentValidationError("ATTACHMENT_AUTHORITY_SOURCE_PIN_DRIFT")
    pinned = strict_read(path)
    if canonical_bytes(pinned) != canonical_bytes(receipt):
        raise IndependentValidationError("ATTACHMENT_RECEIPT_NOT_PINNED")
    if receipt.get("schema") != "AUTHORITY_BOUND_ATTACHMENT_SE3_RECEIPT_V1":
        raise IndependentValidationError("ATTACHMENT_RECEIPT_SCHEMA")
    if receipt.get("status") != "AUTHORITY_BOUND_OPERATIONAL_ATTACHMENT_SE3":
        raise IndependentValidationError("ATTACHMENT_RECEIPT_STATUS")
    if receipt.get("operational_attachment_authority") is not True:
        raise IndependentValidationError("ATTACHMENT_RECEIPT_OPERATIONAL_FALSE")
    if receipt.get("target_attachment_plant_allowed") is not True:
        raise IndependentValidationError("ATTACHMENT_RECEIPT_PLANT_FALSE")
    if receipt.get("attachment_frame_ids") != {"parent_frame": "E", "child_frame": "T", "transform_field": "T_E_T_rows"}:
        raise IndependentValidationError("ATTACHMENT_FRAME_IDS")
    state_pin = next((item for item in contract.get("source_pins", []) if item.get("id") == "configuration_state_vector_contract"), None)
    if state_pin is None:
        raise IndependentValidationError("STATE_PIN_MISSING")
    state_path = PROJECT_ROOT / state_pin["path"]
    state_actual = raw_record(state_path)
    if state_actual["bytes"] != state_pin["bytes"] or state_actual["sha256"] != state_pin["sha256"]:
        raise IndependentValidationError("STATE_PIN_DRIFT")
    linkage = receipt.get("system_configuration_linkage", {})
    if linkage.get("configuration_id") != configuration_id:
        raise IndependentValidationError("CONFIGURATION_LINKAGE")
    if linkage.get("configuration_state_contract_raw_sha256") != state_pin["sha256"]:
        raise IndependentValidationError("STATE_RAW_HASH_LINKAGE")
    states = strict_read(state_path)
    record = next((item for item in states.get("configurations", []) if item.get("configuration_id") == configuration_id), None)
    if record is None or linkage.get("configuration_state_record_canonical_sha256") != canonical_hash(record):
        raise IndependentValidationError("STATE_RECORD_CANONICAL_HASH_LINKAGE")
    validate_transform_independent(receipt.get("T_E_T_rows"))


def negative_controls(contract: Mapping[str, Any], evidence: Mapping[str, Any], gate: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    records = []

    def exception(identifier: str, operation: Callable[[], Any]) -> None:
        observed = "NO_EXCEPTION"
        try:
            operation()
        except Exception as exc:
            observed = type(exc).__name__ + ":" + str(exc)
        records.append({"id": identifier, "pass": observed != "NO_EXCEPTION", "observed": observed})

    def boolean(identifier: str, condition: bool) -> None:
        records.append({"id": identifier, "pass": bool(condition)})

    exception("INC01_DUPLICATE_JSON", lambda: strict_loads('{"a":1,"a":2}'))
    exception("INC02_JSON_NAN", lambda: strict_loads('{"a":NaN}'))
    exception("INC03_JSON_INFINITY", lambda: strict_loads('{"a":Infinity}'))
    boolean("INC04_EVIDENCE_HASH_MUTATION", hashlib.sha256(EVIDENCE_PATH.read_bytes() + b"x").hexdigest().upper() != EXPECTED_EVIDENCE_RAW_SHA256)
    mutated = copy.deepcopy(contract); mutated["review_status"] = "APPROVED"
    boolean("INC05_CONTRACT_REVIEW_MUTATION", canonical_hash(mutated) != EXPECTED_CONTRACT_CANONICAL_SHA256)
    mutated = copy.deepcopy(contract); mutated["source_pins"][0]["sha256"] = "0" * 64
    boolean("INC06_SOURCE_PIN_MUTATION_REHASHED", not audit_sources(mutated)["all_match"])
    exception("INC07_NULL_ATTACHMENT_BEHAVIOR", lambda: require_attachment(None, "C08", contract))
    forged_receipt = {"schema": "AUTHORITY_BOUND_ATTACHMENT_SE3_RECEIPT_V1", "T_E_T_rows": np.eye(4), "attachment_frame_ids": {"parent_frame": "E", "child_frame": "T", "transform_field": "T_E_T_rows"}}
    exception("INC08_FORGED_UNPINNED_RECEIPT", lambda: require_attachment(forged_receipt, "C08", contract))
    exception("INC09_WRONG_CONFIGURATION_ID", lambda: require_attachment(forged_receipt, "C99", contract))
    exception("INC10_BARE_MATRIX_NOT_RECEIPT", lambda: require_attachment(np.eye(4), "C08", contract))
    mutated_gate = copy.deepcopy(gate); mutated_gate["attachment_valid"] = True
    boolean("INC11_GATE_AUTHORITY_ESCALATION", not authority_false(mutated_gate))
    resigned_gate = copy.deepcopy(gate); resigned_gate["review_status"] = "APPROVED"
    resigned_raw = (json.dumps(builtin(resigned_gate), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    resigned_manifest = copy.deepcopy(manifest); gate_relative = GATE_PATH.relative_to(PACKAGE_ROOT).as_posix(); entry = next(item for item in resigned_manifest["package_entries"] if item["path"] == gate_relative); entry["bytes"] = len(resigned_raw); entry["sha256"] = hashlib.sha256(resigned_raw).hexdigest().upper(); resigned_manifest["package_entries_canonical_sha256"] = canonical_hash(resigned_manifest["package_entries"])
    boolean("INC12_GATE_REVIEW_CONSISTENT_RESIGN", not gate_document_valid(resigned_gate) and resigned_manifest["package_entries_canonical_sha256"] == canonical_hash(resigned_manifest["package_entries"]))
    duplicate_manifest = copy.deepcopy(manifest); duplicate_manifest["package_entries"].append(copy.deepcopy(duplicate_manifest["package_entries"][0]))
    boolean("INC13_MANIFEST_DUPLICATE", not manifest_is_exact(duplicate_manifest)[0])
    extra_manifest = copy.deepcopy(manifest); extra_manifest["package_entries"].append({"path": "extra.json", "bytes": 0, "sha256": "0" * 64})
    boolean("INC14_MANIFEST_EXTRA", not manifest_is_exact(extra_manifest)[0])
    self_manifest = copy.deepcopy(manifest); self_manifest["package_entries"].append({"path": manifest["self_excluded_path"], "bytes": 0, "sha256": "0" * 64})
    boolean("INC15_MANIFEST_SELF_INCLUDE", not manifest_is_exact(self_manifest)[0])
    allowlist = copy.deepcopy(manifest); allowlist["frozen_package_path_allowlist"].append("forged.py")
    boolean("INC16_ALLOWLIST_MUTATION", not manifest_is_exact(allowlist)[0])
    cache = copy.deepcopy(manifest); cache["cache_bytecode_or_unlisted_payload_allowed"] = True
    boolean("INC17_CACHE_POLICY_MUTATION", not manifest_is_exact(cache)[0])
    fixture = copy.deepcopy(evidence["synthetic_fixture_runs"]["C08"]["fixture"]); fixture["frames"]["T_E_T"] = "T_FROM_E"
    exception("INC18_FRAME_DIRECTION_MUTATION", lambda: validate_fixture_independent(fixture))
    fixture = copy.deepcopy(evidence["synthetic_fixture_runs"]["C08"]["fixture"]); fixture["units"]["inertia"] = "kg*m"
    exception("INC19_UNIT_MUTATION", lambda: validate_fixture_independent(fixture))
    fixture = copy.deepcopy(evidence["synthetic_fixture_runs"]["C08"]["fixture"]); fixture["target"]["mass_kg"] = -1.0
    exception("INC20_MASS_MUTATION", lambda: validate_fixture_independent(fixture))
    fixture = copy.deepcopy(evidence["synthetic_fixture_runs"]["C08"]["fixture"]); fixture["T_E_T_rows"][0][0] += 0.1
    exception("INC21_ROTATION_MUTATION", lambda: validate_fixture_independent(fixture))
    fixture = copy.deepcopy(evidence["synthetic_fixture_runs"]["C08"]["fixture"]); fixture["joint_positions_mixed_rad_m"] = [0.0] * 7
    exception("INC22_STATE_DIMENSION_MUTATION", lambda: validate_fixture_independent(fixture))
    run = evidence["synthetic_fixture_runs"]["C08"]; independent = independent_combine(run["fixture"]); forged = np.asarray(run["composite_direct"]["inertia_cg_B_kg_m2"]).copy(); forged[0, 0] += 1.0e-3
    boolean("INC23_STORED_INERTIA_MUTATION", np.max(np.abs(forged - independent["inertia_cg_B_kg_m2"])) > 2.0e-11)
    stored = run["post_capture_state_initialization"]; forged_P = np.asarray(stored["recomputed_linear_momentum_I_kg_m_s"]).copy(); forged_P[0] += 1.0e-4
    boolean("INC24_STORED_MOMENTUM_MUTATION", np.max(np.abs(forged_P - np.asarray(stored["input_linear_momentum_I_kg_m_s"]))) > 2.0e-12)
    states = strict_read(PROJECT_ROOT / EXPECTED_SOURCE_PINS[0][1]); uses = strict_read(PROJECT_ROOT / EXPECTED_SOURCE_PINS[1][1]); mutated_states = copy.deepcopy(states); target = next(item for item in mutated_states["configurations"] if item["configuration_id"] == "C08")["authoritative_state"]["target"]; target["attachment_transform_S_rows"]["value"] = np.eye(4).tolist()
    boolean("INC25_C08_ZERO_FILL_OR_DISPLAY_PROMOTION", not authoritative_facts(mutated_states, uses)["records"]["C08"]["all_pass"])
    mutated_uses = copy.deepcopy(uses); next(item for item in mutated_uses["records"] if item["configuration_id"] == "C09")["target_attachment_plant_allowed"] = True
    boolean("INC26_C09_PLANT_AUTHORITY_MUTATION", not authoritative_facts(states, mutated_uses)["records"]["C09"]["all_pass"])
    fixture = copy.deepcopy(evidence["synthetic_fixture_runs"]["C08"]["fixture"]); fixture["service"]["frame"] = "T"
    exception("INC27_SERVICE_BODY_FRAME_MUTATION", lambda: validate_fixture_independent(fixture))
    fixture = copy.deepcopy(evidence["synthetic_fixture_runs"]["C08"]["fixture"]); fixture["T_B_E_rows"][0][3] = 1.0e308; fixture["T_E_T_rows"][0][3] = 1.0e308
    exception("INC28_COMPOSED_T_B_T_NONFINITE", lambda: independent_combine(fixture))
    reference = evidence["diagnostics"]["C08"]["reference_point_translation"]
    boolean("INC29_REFERENCE_POINT_CROSS_SIGN_FALSIFIER", reference["twist_invariance_max_abs"] <= 2.0e-12 and reference["wrong_cross_sign_twist_delta"] > 1.0e-8)
    return {"records": records, "count": len(records), "passed": sum(item["pass"] for item in records), "minimum_required": 16, "all_pass": len(records) >= 16 and all(item["pass"] for item in records)}


def audit_evidence_chain(evidence: Mapping[str, Any], gate: Mapping[str, Any], manifest: Mapping[str, Any]) -> dict[str, Any]:
    evidence_raw = raw_record(EVIDENCE_PATH); gate_raw = raw_record(GATE_PATH)
    by_path = {item["path"]: item for item in manifest.get("package_entries", [])}
    evidence_rel = EVIDENCE_PATH.relative_to(PACKAGE_ROOT).as_posix(); gate_rel = GATE_PATH.relative_to(PACKAGE_ROOT).as_posix()
    checks = {
        "evidence_bytes": evidence_raw["bytes"] == EXPECTED_EVIDENCE_BYTES,
        "evidence_sha": evidence_raw["sha256"] == EXPECTED_EVIDENCE_RAW_SHA256,
        "gate_bytes": gate_raw["bytes"] == EXPECTED_GATE_BYTES,
        "gate_sha": gate_raw["sha256"] == EXPECTED_GATE_RAW_SHA256,
        "evidence_schema": evidence.get("schema") == "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_EVIDENCE_V1",
        "contract_hash": evidence.get("contract_canonical_sha256") == EXPECTED_CONTRACT_CANONICAL_SHA256 and gate.get("contract_canonical_sha256") == EXPECTED_CONTRACT_CANONICAL_SHA256,
        "manifest_evidence": by_path.get(evidence_rel, {}).get("bytes") == EXPECTED_EVIDENCE_BYTES and by_path.get(evidence_rel, {}).get("sha256") == EXPECTED_EVIDENCE_RAW_SHA256,
        "manifest_gate": by_path.get(gate_rel, {}).get("bytes") == EXPECTED_GATE_BYTES and by_path.get(gate_rel, {}).get("sha256") == EXPECTED_GATE_RAW_SHA256,
        "source_records": evidence.get("source_pins", {}).get("all_match") is True and len(evidence.get("source_pins", {}).get("records", [])) == 7,
        "current_not_evaluated": evidence.get("current_system_authority_audit", {}).get("current_system_instance_evaluated") is False and evidence.get("current_system_authority_audit", {}).get("current_system_kernel_call_count") == 0,
        "authority_false": evidence.get("next_stage_authorized") is False and evidence.get("release_credit") is False,
    }
    return {"evidence_raw": evidence_raw, "gate_raw": gate_raw, "checks": checks, "all_pass": all(checks.values())}


def build_receipt() -> dict[str, Any]:
    contract = strict_read(CONTRACT_PATH); evidence = strict_read(EVIDENCE_PATH); gate = strict_read(GATE_PATH); manifest = strict_read(MANIFEST_PATH)
    independence = check_no_forbidden_imports()
    strict_checks = {}
    for name, text in (("duplicate", '{"x":1,"x":2}'), ("nan", '{"x":NaN}'), ("infinity", '{"x":Infinity}')):
        try:
            strict_loads(text); strict_checks[name] = False
        except ValueError:
            strict_checks[name] = True
    contract_audit = audit_contract(contract); source_audit = audit_sources(contract); authority_audit = audit_authority_sources(); gate_audit = audit_gate_structure(gate); manifest_pass, manifest_checks = manifest_is_exact(manifest); chain = audit_evidence_chain(evidence, gate, manifest); physics = reproduce_physics(evidence); controls = negative_controls(contract, evidence, gate, manifest)
    cases = physics["cases"]; diagnostics = physics["diagnostics"]
    direct_pass = all(max(case["direct_errors"].values()) <= 2.0e-11 for case in cases.values())
    spatial_pass = all(case["spatial_matrix_max_abs"] <= 2.0e-11 for case in cases.values())
    inertia_pass = all(case["finite"] and case["inertia_symmetry"] <= 2.0e-12 and case["inertia_eigenvalues"][0] >= 1.0e-10 and case["inertia_triangle"] for case in cases.values())
    state_pass = all(case["state"]["dimension_23"] and case["state"]["base_position"] <= 2.0e-12 and case["state"]["quaternion_rotation"] <= 2.0e-12 and case["state"]["q"] <= 1.0e-14 and case["state"]["qdot"] == 0.0 and case["state"]["twist"] <= 2.0e-12 and case["state"]["origin_O"] <= 1.0e-14 for case in cases.values())
    linear_pass = all(case["state"]["linear_momentum"] <= 2.0e-12 for case in cases.values())
    angular_pass = all(case["state"]["angular_momentum"] <= 5.0e-11 for case in cases.values())
    diagnostic_pass = all(
        diagnostic["zero"]["mass_abs_kg"] <= 1.0e-13
        and diagnostic["zero"]["cg_max_abs_m"] <= 1.0e-13
        and diagnostic["zero"]["inertia_max_abs_kg_m2"] <= 1.0e-12
        and diagnostic["colocated"]["cg_max_abs_m"] <= 1.0e-13
        and diagnostic["colocated"]["inertia_sum_max_abs_kg_m2"] <= 1.0e-12
        and all(
            item["finite"] and item["mass_affine_abs_kg"] <= 2.0e-11
            for item in diagnostic["scaling"]
        )
        and diagnostic["sensitivity"]["translation_cg_change_m"] >= 1.0e-4
        and diagnostic["sensitivity"]["rotation_inertia_change_kg_m2"] >= 1.0e-5
        and diagnostic["covariance"]["cg_max_abs_m"] <= 2.0e-12
        and diagnostic["covariance"]["inertia_max_abs_kg_m2"] <= 2.0e-11
        and diagnostic["reference_point"]["twist_invariance_max_abs"] <= 2.0e-12
        and diagnostic["reference_point"]["wrong_cross_sign_omega_delta"] > 1.0e-8
        and diagnostic["reference_point"]["law_exact"]
        and max(diagnostic["stored_diagnostic_numeric_cross"].values()) <= 2.0e-11
        for diagnostic in diagnostics.values()
    )
    independent_gate = {
        "K01": source_audit["all_match"], "K02": contract_audit["all_pass"],
        "K03": authority_audit["facts"]["records"]["C08"]["all_pass"] and gate["current_C08_status"] == EXPECTED_CURRENT_STATUS,
        "K04": authority_audit["facts"]["records"]["C09"]["all_pass"] and gate["current_C09_status"] == EXPECTED_CURRENT_STATUS,
        "K05": all(authority_audit["display_checks"].values()),
        "K06": all(case["finite"] for case in cases.values()), "K07": direct_pass, "K08": direct_pass and spatial_pass, "K09": inertia_pass,
        "K10": state_pass, "K11": linear_pass, "K12": angular_pass and all(item["reference_point"]["twist_invariance_max_abs"] <= 2.0e-12 and item["reference_point"]["wrong_cross_sign_omega_delta"] > 1.0e-8 for item in diagnostics.values()),
        "K13": all(
            item["zero"]["mass_abs_kg"] <= 1e-13
            and item["zero"]["cg_max_abs_m"] <= 1e-13
            and item["zero"]["inertia_max_abs_kg_m2"] <= 1e-12
            for item in diagnostics.values()
        ),
        "K14": all(
            item["colocated"]["cg_max_abs_m"] <= 1e-13
            and item["colocated"]["inertia_sum_max_abs_kg_m2"] <= 1e-12
            for item in diagnostics.values()
        ),
        "K15": diagnostic_pass, "K16": all(item["sensitivity"]["translation_cg_change_m"] >= 1e-4 for item in diagnostics.values()), "K17": all(item["sensitivity"]["rotation_inertia_change_kg_m2"] >= 1e-5 for item in diagnostics.values()), "K18": all(item["covariance"]["cg_max_abs_m"] <= 2e-12 and item["covariance"]["inertia_max_abs_kg_m2"] <= 2e-11 for item in diagnostics.values()),
        "K19": contract_audit["checks"]["energy_not_conserved"] and all(case["state"]["energy_not_evaluated"] for case in cases.values()),
        "K20": canonical_hash(reproduce_physics(evidence)) == canonical_hash(physics), "K21": controls["all_pass"],
        "K22": contract_audit["checks"]["minimum_inputs"] and contract_audit["checks"]["authority_false"] and authority_false(gate),
    }
    reproduced_rows = [{"id": identifier, "name": name, "pass": bool(independent_gate[identifier])} for identifier, name in EXPECTED_GATE_ROWS]
    top = [
        ("IV01", "STANDALONE_INTERNAL_NO_KERNEL_EVALUATOR_OR_BUILDER_IMPORT", independence["pass"]),
        ("IV02", "STRICT_JSON_DUPLICATE_NAN_INFINITY", all(strict_checks.values())),
        ("IV03", "HELD_CONTRACT_RAW_CANONICAL_AND_SEMANTICS", contract_audit["all_pass"]),
        ("IV04", "HELD_EXTERNAL_SOURCE_PINS_REHASHED", source_audit["all_match"]),
        ("IV05", "C08_C09_AUTHORITY_NULL_AND_FIXTURE_ONLY_REPARSED", authority_audit["all_pass"]),
        ("IV06", "GATE_STRUCTURE_REVIEW_STATUS_AND_AUTHORITY", gate_audit["all_pass"]),
        ("IV07", "EVIDENCE_GATE_INTERNAL_HASH_CHAIN", chain["all_pass"]),
        ("IV08", "FROZEN_MANIFEST_AND_DIRECTORY_PAYLOAD", manifest_pass),
        ("IV09", "INDEPENDENT_ORIGIN_PARALLEL_AXIS_AND_SPATIAL_FORMULAS", direct_pass and spatial_pass and inertia_pass),
        ("IV10", "INDEPENDENT_POST_CAPTURE_STATE_AND_MOMENTUM", state_pass and linear_pass and angular_pass),
        ("IV11", "INDEPENDENT_DEGENERATION_SCALING_SENSITIVITY_AND_FRAME_COVARIANCE", diagnostic_pass),
        ("IV12", "INDEPENDENT_MUTATION_CONTROLS", controls["all_pass"]),
    ]
    checks = [{"id": identifier, "name": name, "pass": bool(passed)} for identifier, name, passed in top] + [{"id": "IR" + row["id"][1:], "name": "INDEPENDENT_REPRODUCTION__" + row["name"], "pass": row["pass"]} for row in reproduced_rows]
    return builtin({
        "schema": "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_STANDALONE_INTERNAL_VALIDATION_V1",
        "validator_architecture": "STANDALONE_INTERNAL_NO_KERNEL_EVALUATOR_OR_BUILDER_IMPORT__NOT_ORGANIZATIONALLY_INDEPENDENT",
        "independence_classification": "PACKAGE_LOCAL_STANDALONE_INTERNAL__EXTERNAL_AUDIT_REQUIRED_FOR_INDEPENDENCE_CLAIM",
        "checks": checks, "passed": sum(item["pass"] for item in checks), "total": len(checks), "all_checks_pass": all(item["pass"] for item in checks),
        "independent_gate_reproduction": reproduced_rows, "independence_import_audit": independence, "strict_json_self_test": strict_checks,
        "contract_audit": contract_audit, "source_audit": source_audit, "authority_source_audit": authority_audit, "gate_structure_audit": gate_audit,
        "evidence_hash_chain": chain, "manifest_audit": {"raw": raw_record(MANIFEST_PATH), "checks": manifest_checks, "all_pass": manifest_pass, "declared_entries_canonical_sha256": manifest.get("package_entries_canonical_sha256"), "independently_recomputed_entries_canonical_sha256": canonical_hash(expected_manifest_entries())},
        "physics_recomputation": physics, "negative_controls": controls, "maximum_claim_unchanged": EXPECTED_MAXIMUM_CLAIM,
        "current_C08_status": EXPECTED_CURRENT_STATUS, "current_C09_status": EXPECTED_CURRENT_STATUS,
        "current_system_instance_evaluated": False, "contact_valid": False, "attachment_valid": False, "target_attachment_plant_valid": False, "hardware_valid": False, "non_abort_authorized": False, "parent_dynamics_engineering_complete": False, "next_stage_authorized": False, "release_credit": False,
    })


def pretty_bytes(value: Any) -> bytes:
    return (json.dumps(builtin(value), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(); mode = parser.add_mutually_exclusive_group(required=True); mode.add_argument("--write", action="store_true"); mode.add_argument("--check", action="store_true"); mode.add_argument("--stdout", action="store_true"); args = parser.parse_args()
    receipt = build_receipt()
    if args.write:
        RECEIPT_PATH.parent.mkdir(parents=True, exist_ok=True); RECEIPT_PATH.write_bytes(pretty_bytes(receipt)); print(json.dumps({"receipt": raw_record(RECEIPT_PATH), "checks": f"{receipt['passed']}/{receipt['total']}", "negative_controls": f"{receipt['negative_controls']['passed']}/{receipt['negative_controls']['count']}"}, indent=2, sort_keys=True)); return 0 if receipt["all_checks_pass"] else 2
    if args.check:
        stored = strict_read(RECEIPT_PATH); exact = canonical_bytes(stored) == canonical_bytes(receipt); result = {"standalone_recompute_pass": receipt["all_checks_pass"], "stored_receipt_canonical_exact": exact, "checks": f"{receipt['passed']}/{receipt['total']}", "negative_controls": f"{receipt['negative_controls']['passed']}/{receipt['negative_controls']['count']}", "all_pass": receipt["all_checks_pass"] and exact}; print(json.dumps(result, indent=2, sort_keys=True)); return 0 if result["all_pass"] else 3
    print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)); return 0 if receipt["all_checks_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
