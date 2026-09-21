"""Build deterministic evidence and a fail-closed machine gate for DG4 candidate V1."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import numpy as np
import yaml


HERE = Path(__file__).resolve().parent
SRC = HERE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from dg4_contact_hybrid import (  # noqa: E402
    ABORT_ONLY,
    BOUNDED_CONTACT_DIAGNOSTIC,
    FailClosedError,
    POST_IMPACT_DIAGNOSTIC,
    PRECONTACT,
    diagonal_inertia,
    inertia_from_components,
    solve_case,
    validate_request,
)


DEFAULT_CONTRACT = HERE / "contracts" / "DG4_CONTACT_HYBRID_CANDIDATE_CONTRACT_V1.yaml"
DEFAULT_EVIDENCE = HERE / "results" / "DG4_CONTACT_HYBRID_EVIDENCE_V1.json"
DEFAULT_GATE = HERE / "results" / "DG4_CONTACT_HYBRID_GATE_V1.json"
SOLVER = HERE / "src" / "dg4_contact_hybrid.py"
TEST_FILE = HERE / "tests" / "test_dg4_contact_hybrid.py"
REQUIRED_QUANTITY_FIELDS = (
    "estimate",
    "lower_bound",
    "upper_bound",
    "si_unit",
    "standard_uncertainty",
    "uncertainty_type",
    "distribution",
    "degrees_of_freedom",
    "authority",
    "source",
    "confidence",
    "status",
)

# Exact dimensional contract for every named input.  Merely checking that a unit
# string is present is not sufficient: a mass tagged as metres is still invalid.
EXPECTED_QUANTITY_UNITS = {
    "first_contact_speed_hard_upper_bound": "m/s",
    "original_provisional_contact_speed": "m/s",
    "diagnostic_closing_speed": "m/s",
    "diagnostic_contact_normal_axis": "1",
    "service_contact_lever_about_service_com": "m",
    "service_mass_c01": "kg",
    "service_inertia_c01_components": "kg*m^2",
    "target_satellite_mass": "kg",
    "target_satellite_inertia_diag": "kg*m^2",
    "target_satellite_contact_lever": "m",
    "target_satellite_tumble_rate": "rad/s",
    "target_satellite_tumble_axis": "1",
    "target_debris_mass": "kg",
    "target_debris_inertia_diag": "kg*m^2",
    "target_debris_contact_lever": "m",
    "target_debris_tumble_rate": "rad/s",
    "target_debris_tumble_axis": "1",
    "restitution_lower": "1",
    "restitution_nominal": "1",
    "restitution_upper": "1",
    "diagnostic_contact_window": "s",
    "linear_momentum_residual_limit": "N*s",
    "angular_momentum_residual_limit": "N*m*s",
    "restitution_residual_limit": "m/s",
    "contact_origin_coincidence_residual_limit": "m",
    "energy_identity_residual_limit": "J",
}
EXPECTED_NUMERICAL_THRESHOLDS = {
    "linear_momentum_residual_limit": 1.0e-12,
    "angular_momentum_residual_limit": 1.0e-12,
    "restitution_residual_limit": 1.0e-12,
    "contact_origin_coincidence_residual_limit": 1.0e-12,
    "energy_identity_residual_limit": 1.0e-12,
}
EXPECTED_QUANTITY_FRAMES = {
    "diagnostic_contact_normal_axis": "I",
    "service_contact_lever_about_service_com": "S",
    "service_inertia_c01_components": "S",
    "target_satellite_inertia_diag": "T",
    "target_satellite_contact_lever": "T",
    "target_satellite_tumble_axis": "T",
    "target_debris_inertia_diag": "D",
    "target_debris_contact_lever": "D",
    "target_debris_tumble_axis": "D",
}
EXPECTED_CLAIM_SENSITIVE_METADATA = {
    "target_satellite_contact_lever": {
        "uncertainty_type": "NOT_EVALUATED",
        "distribution": "UNKNOWN_NOT_DECLARED",
        "authority": "TARGET_MODELS_V1_WITH_AXIS_ALIGNED_DIAGNOSTIC_INTERPRETATION",
        "source": "target_satellite_v0.grasp_primary.lever_to_com_m and approach +X_T",
        "confidence": "LOW",
        "status": "MATHEMATICAL_LEVER_ONLY__PHYSICAL_PATCH_UNKNOWN",
    },
    "restitution_lower": {
        "uncertainty_type": "SOURCE_BOUND_NOT_A_STANDARD_UNCERTAINTY",
        "distribution": "UNKNOWN_NOT_DECLARED",
        "authority": "DESIGN_CONTACT_MODEL_V1",
        "source": "normal_contact.coefficient_of_restitution.lower",
        "confidence": "LOW",
        "status": "BOUNDED_PROVISIONAL_CORNER",
    },
    "restitution_nominal": {
        "uncertainty_type": "SOURCE_NOMINAL_WITHOUT_EVALUATED_UNCERTAINTY",
        "distribution": "UNKNOWN_NOT_DECLARED",
        "authority": "DESIGN_CONTACT_MODEL_V1",
        "source": "normal_contact.coefficient_of_restitution.nominal",
        "confidence": "LOW",
        "status": "BOUNDED_PROVISIONAL_NOMINAL",
    },
    "restitution_upper": {
        "uncertainty_type": "SOURCE_BOUND_NOT_A_STANDARD_UNCERTAINTY",
        "distribution": "UNKNOWN_NOT_DECLARED",
        "authority": "DESIGN_CONTACT_MODEL_V1",
        "source": "normal_contact.coefficient_of_restitution.upper",
        "confidence": "LOW",
        "status": "BOUNDED_PROVISIONAL_CORNER",
    },
    "diagnostic_contact_window": {
        "uncertainty_type": "SOURCE_PROVISIONAL_SWEEP_WITHOUT_EVALUATED_UNCERTAINTY",
        "distribution": "UNKNOWN_NOT_DECLARED",
        "authority": "DESIGN_CONTACT_MODEL_V1__SIM11_PROVISIONAL_SWEEP",
        "source": "gripper_actuator.contact_window_T_c_s",
        "confidence": "MEDIUM_PROVISIONAL",
        "status": "EQUIVALENT_HALF_SINE_FORCE_DIAGNOSTIC_ONLY",
    },
}

EXPECTED_AUTHORITY_SCOPE = "MATHEMATICAL_PRECONTACT_TO_POST_IMPACT_DIAGNOSTIC_ONLY"
EXPECTED_RECORD_TYPE = (
    "ADDITIVE_DESIGN_DIAGNOSTIC_CANDIDATE__PARENT_DG4_UNCHANGED"
)
EXPECTED_CONTRACT_BYTES = 18743
EXPECTED_CONTRACT_SHA256 = (
    "38D65406849948627ADAC364CF413774B6249DA4439FD40D8AAFA6F1E0890ACB"
)
IDENTITY_3 = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def project_root() -> Path:
    for candidate in (HERE, *HERE.parents):
        if (candidate / "PROJECT_MAP.md").is_file() and (candidate / "AGENTS.md").is_file():
            return candidate
    raise RuntimeError("project root not found")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def finite_numbers(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, list):
        return bool(value) and all(finite_numbers(item) for item in value)
    return False


def all_nonnegative(value: Any) -> bool:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) >= 0.0
    if isinstance(value, list):
        return all(all_nonnegative(item) for item in value)
    return False


def close(a: Any, b: float, tol: float = 1e-15) -> bool:
    return isinstance(a, (int, float)) and not isinstance(a, bool) and math.isclose(
        float(a), b, rel_tol=0.0, abs_tol=tol
    )


def vector_close(a: Any, b: list[float], tol: float = 1e-15) -> bool:
    try:
        return bool(np.allclose(np.asarray(a, dtype=float), np.asarray(b, dtype=float), rtol=0.0, atol=tol))
    except (TypeError, ValueError):
        return False


def quantity_record(
    estimate: float | list[float] | None,
    *,
    unit: str,
    source: str,
    status: str,
    lower: float | list[float] | None = None,
    upper: float | list[float] | None = None,
    authority: str = "DG4_DETERMINISTIC_EVALUATOR",
    confidence: str = "HIGH_NUMERICAL_ONLY",
) -> dict[str, Any]:
    return {
        "estimate": estimate,
        "lower_bound": lower,
        "upper_bound": upper,
        "si_unit": unit,
        "standard_uncertainty": None,
        "uncertainty_type": "NOT_PROPAGATED__DESIGN_DIAGNOSTIC_NOT_A_PHYSICAL_MEASUREMENT",
        "distribution": "NOT_APPLICABLE_DETERMINISTIC_MAP",
        "degrees_of_freedom": None,
        "authority": authority,
        "source": source,
        "confidence": confidence,
        "status": status,
    }


def validate_quantity_metadata(quantities: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(quantities, dict) or not quantities:
        return ["quantities missing or empty"]
    missing_names = sorted(set(EXPECTED_QUANTITY_UNITS) - set(quantities))
    unexpected_names = sorted(set(quantities) - set(EXPECTED_QUANTITY_UNITS))
    if missing_names:
        errors.append(f"missing named quantities: {missing_names}")
    if unexpected_names:
        errors.append(f"unexpected named quantities: {unexpected_names}")
    for name, record in quantities.items():
        if not isinstance(record, dict):
            errors.append(f"{name}: not a mapping")
            continue
        missing = [field for field in REQUIRED_QUANTITY_FIELDS if field not in record]
        if missing:
            errors.append(f"{name}: missing {missing}")
            continue
        expected_unit = EXPECTED_QUANTITY_UNITS.get(name)
        if expected_unit is None or record.get("si_unit") != expected_unit:
            errors.append(
                f"{name}: si_unit {record.get('si_unit')!r} != {expected_unit!r}"
            )
        if name in EXPECTED_NUMERICAL_THRESHOLDS:
            expected_threshold = EXPECTED_NUMERICAL_THRESHOLDS[name]
            if not close(record.get("estimate"), expected_threshold):
                errors.append(
                    f"{name}: estimate is not frozen at {expected_threshold}"
                )
            if not close(record.get("lower_bound"), 0.0):
                errors.append(f"{name}: lower_bound is not frozen at 0")
            if not close(record.get("upper_bound"), expected_threshold):
                errors.append(
                    f"{name}: upper_bound is not frozen at {expected_threshold}"
                )
        expected_frame = EXPECTED_QUANTITY_FRAMES.get(name)
        if expected_frame is not None and record.get("reference_frame") != expected_frame:
            errors.append(
                f"{name}: reference_frame {record.get('reference_frame')!r} != {expected_frame!r}"
            )
        expected_metadata = EXPECTED_CLAIM_SENSITIVE_METADATA.get(name)
        if expected_metadata is not None:
            for field, expected_value in expected_metadata.items():
                if record.get(field) != expected_value:
                    errors.append(
                        f"{name}: claim-sensitive {field} {record.get(field)!r} != {expected_value!r}"
                    )
        estimate = record["estimate"]
        lower = record["lower_bound"]
        upper = record["upper_bound"]
        uncertainty = record["standard_uncertainty"]
        if estimate is not None and not finite_numbers(estimate):
            errors.append(f"{name}: estimate is not finite numeric data")
        if lower is not None and not finite_numbers(lower):
            errors.append(f"{name}: lower bound is not finite numeric data")
        if upper is not None and not finite_numbers(upper):
            errors.append(f"{name}: upper bound is not finite numeric data")
        if uncertainty is not None and (
            not finite_numbers(uncertainty) or not all_nonnegative(uncertainty)
        ):
            errors.append(f"{name}: standard uncertainty invalid")
        if isinstance(estimate, (int, float)) and isinstance(lower, (int, float)) and isinstance(upper, (int, float)):
            if not float(lower) <= float(estimate) <= float(upper):
                errors.append(f"{name}: scalar estimate outside bounds")
        for field in (
            "si_unit",
            "uncertainty_type",
            "distribution",
            "authority",
            "source",
            "confidence",
            "status",
        ):
            if not isinstance(record[field], str) or not record[field].strip():
                errors.append(f"{name}: {field} must be non-empty text")
    return errors


def validate_contract_boundary(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("record_type") != EXPECTED_RECORD_TYPE:
        errors.append("record_type promotion or drift")
    if contract.get("authority_scope") != EXPECTED_AUTHORITY_SCOPE:
        errors.append("authority_scope promotion or drift")
    if contract.get("frozen_inputs_modified") is not False:
        errors.append("frozen_inputs_modified must remain false")
    fixture = contract.get("diagnostic_frame_fixture")
    expected_fixture = {
        "inertial_frame": "I",
        "service_source_frame": "S",
        "satellite_source_frame": "T",
        "debris_source_frame": "D",
        "R_I_from_S": IDENTITY_3,
        "R_I_from_T": IDENTITY_3,
        "R_I_from_D": IDENTITY_3,
        "orientation_interpretation": "SYNTHETIC_IDENTITY_ORIENTATION_FOR_CONSERVATION_FIXTURE_ONLY",
        "origin_interpretation": "TARGET_SOURCE_FRAME_ORIGIN_TREATED_AS_COM_FOR_SYNTHETIC_FIXTURE_ONLY",
        "physical_pose_or_patch_authority": False,
    }
    if fixture != expected_fixture:
        errors.append("diagnostic_frame_fixture must match the exact synthetic identity fixture")
    release = contract.get("release_boundary")
    expected_release = {
        "design_diagnostic_candidate_allowed": True,
        "real_attachment_claimed": False,
        "physical_contact_claimed": False,
        "production_ready": False,
        "non_abort_grasp_ready": False,
        "hardware_valid": False,
        "flight_valid": False,
        "parent_DG4_satisfied": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    if release != expected_release:
        errors.append("release_boundary promotion or drift")
    return errors


def _case_evidence(raw: dict[str, Any], thresholds: dict[str, float]) -> dict[str, Any]:
    residual_status = "PASS_NUMERICAL_DIAGNOSTIC"
    q: dict[str, Any] = {
        "closing_speed": quantity_record(
            raw["closing_speed_m_s"],
            unit="m/s",
            source="contract quantities.diagnostic_closing_speed",
            status="WITHIN_CURRENT_HARD_UPPER_BOUND",
            lower=0.0,
            upper=raw["hard_upper_bound_m_s"],
        ),
        "relative_normal_pre": quantity_record(
            raw["relative_normal_pre_m_s"],
            unit="m/s",
            source="target contact velocity minus service contact velocity",
            status="CLOSING_DIAGNOSTIC",
        ),
        "relative_normal_post": quantity_record(
            raw["relative_normal_post_m_s"],
            unit="m/s",
            source="post-impulse target contact velocity minus service contact velocity",
            status="SEPARATING_DIAGNOSTIC",
        ),
        "restitution_residual": quantity_record(
            raw["restitution_residual_m_s"],
            unit="m/s",
            source="abs(v_post_n + restitution*v_pre_n)",
            status=residual_status,
            lower=0.0,
            upper=thresholds["restitution"],
        ),
        "effective_mass": quantity_record(
            raw["effective_mass_kg"],
            unit="kg",
            source="inverse normal contact compliance of two rigid bodies",
            status="MATHEMATICAL_DIAGNOSTIC_ONLY",
        ),
        "normal_impulse": quantity_record(
            raw["impulse_magnitude_N_s"],
            unit="N*s",
            source="frictionless restitution impulse",
            status="BOUNDED_CONTACT_DIAGNOSTIC_ONLY",
        ),
        "equivalent_half_sine_peak_force": quantity_record(
            raw["equivalent_half_sine_peak_force_N"],
            unit="N",
            source="pi*J/(2*T_c); equivalent solver stimulus, not hardware contact force",
            status="SOLVER_STIMULUS_PROXY_NOT_PHYSICAL_FORCE",
        ),
        "impulse_on_service": quantity_record(
            raw["impulse_on_service_N_s"],
            unit="N*s",
            source="equal-and-opposite internal impulse pair",
            status="MATHEMATICAL_DIAGNOSTIC_ONLY",
        ),
        "impulse_on_target": quantity_record(
            raw["impulse_on_target_N_s"],
            unit="N*s",
            source="equal-and-opposite internal impulse pair",
            status="MATHEMATICAL_DIAGNOSTIC_ONLY",
        ),
        "impulse_pair_residual": quantity_record(
            raw["impulse_pair_residual_N_s"],
            unit="N*s",
            source="norm(J_service + J_target)",
            status=residual_status,
            lower=0.0,
            upper=thresholds["linear"],
        ),
        "linear_momentum_pre": quantity_record(
            raw["linear_momentum_pre_N_s"],
            unit="N*s",
            source="sum of separate-body linear momenta before impulse",
            status="DESIGN_DIAGNOSTIC_ONLY",
        ),
        "linear_momentum_post": quantity_record(
            raw["linear_momentum_post_N_s"],
            unit="N*s",
            source="sum of separate-body linear momenta after impulse",
            status="DESIGN_DIAGNOSTIC_ONLY",
        ),
        "linear_momentum_residual": quantity_record(
            raw["linear_momentum_residual_N_s"],
            unit="N*s",
            source="norm(P_post-P_pre)",
            status=residual_status,
            lower=0.0,
            upper=thresholds["linear"],
        ),
        "angular_momentum_pre": quantity_record(
            raw["angular_momentum_pre_N_m_s"],
            unit="N*m*s",
            source="sum of orbital plus spin angular momentum about inertial contact origin",
            status="DESIGN_DIAGNOSTIC_ONLY",
        ),
        "angular_momentum_post": quantity_record(
            raw["angular_momentum_post_N_m_s"],
            unit="N*m*s",
            source="sum of orbital plus spin angular momentum about inertial contact origin",
            status="DESIGN_DIAGNOSTIC_ONLY",
        ),
        "angular_momentum_residual": quantity_record(
            raw["angular_momentum_residual_N_m_s"],
            unit="N*m*s",
            source="norm(H_post-H_pre) about inertial contact origin",
            status=residual_status,
            lower=0.0,
            upper=thresholds["angular"],
        ),
        "service_spin_impulse_residual": quantity_record(
            raw["service_spin_angular_impulse_residual_N_m_s"],
            unit="N*m*s",
            source="service spin change minus r_service cross J_service",
            status=residual_status,
            lower=0.0,
            upper=thresholds["angular"],
        ),
        "target_spin_impulse_residual": quantity_record(
            raw["target_spin_angular_impulse_residual_N_m_s"],
            unit="N*m*s",
            source="target spin change minus r_target cross J_target",
            status=residual_status,
            lower=0.0,
            upper=thresholds["angular"],
        ),
        "kinetic_energy_pre": quantity_record(
            raw["kinetic_energy_pre_J"],
            unit="J",
            source="separate-body translational plus rotational energy before impulse",
            status="DESIGN_DIAGNOSTIC_ONLY",
        ),
        "kinetic_energy_post": quantity_record(
            raw["kinetic_energy_post_J"],
            unit="J",
            source="separate-body translational plus rotational energy after impulse",
            status="DESIGN_DIAGNOSTIC_ONLY",
        ),
        "kinetic_energy_loss": quantity_record(
            raw["kinetic_energy_loss_J"],
            unit="J",
            source="T_pre-T_post",
            status="NONNEGATIVE_DISSIPATION_DIAGNOSTIC",
            lower=0.0,
        ),
        "analytic_energy_loss": quantity_record(
            raw["analytic_energy_loss_J"],
            unit="J",
            source="0.5*m_eff*(1-e^2)*v_pre_n^2 independent identity",
            status="INDEPENDENT_ANALYTIC_DIAGNOSTIC",
            lower=0.0,
        ),
        "energy_identity_residual": quantity_record(
            raw["energy_identity_residual_J"],
            unit="J",
            source="abs(numerical energy loss - analytic effective-mass identity)",
            status=residual_status,
            lower=0.0,
            upper=thresholds["energy"],
        ),
        "contact_origin_coincidence_residual": quantity_record(
            raw["contact_coincidence_residual_m"],
            unit="m",
            source="norm((x_service+r_service) - (x_target+r_target))",
            status=residual_status,
            lower=0.0,
            upper=thresholds["contact_origin"],
        ),
    }
    return {
        "case_id": raw["case_id"],
        "target_id": raw["target_id"],
        "state_sequence": raw["state_sequence"],
        "terminal_state": raw["terminal_state"],
        "separate_body_ledger": {
            "body_count_pre": raw["body_count_pre"],
            "body_count_post": raw["body_count_post"],
            "attachment_created": raw["attachment_created"],
            "persistent_contact_created": raw["persistent_contact_created"],
            "physical_contact_claimed": raw["physical_contact_claimed"],
        },
        "restitution_corner": raw["restitution"],
        "quantities": q,
        "audits": {
            "speed_bound_pass": raw["closing_speed_m_s"] <= raw["hard_upper_bound_m_s"],
            "precontact_is_closing": raw["relative_normal_pre_m_s"] < 0.0,
            "postimpact_is_separating": raw["relative_normal_post_m_s"] >= 0.0,
            "restitution_pass": raw["restitution_residual_m_s"] <= thresholds["restitution"],
            "impulse_pair_pass": raw["impulse_pair_residual_N_s"] <= thresholds["linear"],
            "linear_momentum_pass": raw["linear_momentum_residual_N_s"] <= thresholds["linear"],
            "angular_momentum_pass": raw["angular_momentum_residual_N_m_s"] <= thresholds["angular"],
            "spin_angular_impulse_pass": max(
                raw["service_spin_angular_impulse_residual_N_m_s"],
                raw["target_spin_angular_impulse_residual_N_m_s"],
            )
            <= thresholds["angular"],
            "energy_nonincrease_pass": raw["kinetic_energy_loss_J"] >= -thresholds["energy"],
            "energy_identity_pass": raw["energy_identity_residual_J"] <= thresholds["energy"],
            "contact_origin_coincident_pass": raw["contact_coincidence_residual_m"] <= thresholds["contact_origin"],
            "two_separate_bodies_pass": raw["body_count_post"] == 2 and raw["attachment_created"] is False,
        },
    }


def evaluate(contract_path: Path, evidence_path: Path, gate_path: Path) -> tuple[dict[str, Any], dict[str, Any], bool]:
    root = project_root()
    contract = load_yaml(contract_path)
    errors: list[str] = []
    criteria: list[dict[str, Any]] = []

    def criterion(cid: str, name: str, passed: bool, observed: Any) -> None:
        criteria.append({"id": cid, "name": name, "state": "PASS" if passed else "FAIL", "observed": observed})
        if not passed:
            errors.append(f"{cid}: {name}")

    pins = contract.get("source_pins", {})
    pin_rows: list[dict[str, Any]] = []
    pins_ok = isinstance(pins, dict) and len(pins) == 9
    if isinstance(pins, dict):
        for pin_id in sorted(pins):
            pin = pins[pin_id]
            path = root / pin.get("path", "__invalid__") if isinstance(pin, dict) else root / "__invalid__"
            exists = path.is_file()
            actual_bytes = path.stat().st_size if exists else None
            actual_sha = sha256(path) if exists else None
            match = bool(
                exists
                and isinstance(pin, dict)
                and actual_bytes == pin.get("bytes")
                and actual_sha == pin.get("sha256")
            )
            pins_ok = pins_ok and match
            pin_rows.append({"id": pin_id, "path": pin.get("path") if isinstance(pin, dict) else None, "match": match, "actual_bytes": actual_bytes, "actual_sha256": actual_sha})
    criterion("DG4-C01", "nine required source pins match byte count and SHA-256", pins_ok, pin_rows)

    quantity_errors = validate_quantity_metadata(contract.get("quantities"))
    boundary_errors = validate_contract_boundary(contract)
    if (
        not contract_path.is_file()
        or contract_path.stat().st_size != EXPECTED_CONTRACT_BYTES
        or sha256(contract_path) != EXPECTED_CONTRACT_SHA256
    ):
        boundary_errors.append(
            "entire DG4 candidate contract bytes/SHA-256 drifted from the frozen contract"
        )
    metadata_and_boundary_errors = quantity_errors + boundary_errors
    criterion(
        "DG4-C02",
        "all named quantities, frames, units and top-level authority boundaries are exact",
        not metadata_and_boundary_errors,
        metadata_and_boundary_errors,
    )
    quantities = contract.get("quantities", {}) if isinstance(contract.get("quantities"), dict) else {}

    def q(name: str) -> dict[str, Any]:
        value = quantities.get(name, {})
        return value if isinstance(value, dict) else {}

    def claim_sensitive_metadata_exact(name: str) -> bool:
        expected = EXPECTED_CLAIM_SENSITIVE_METADATA[name]
        return all(q(name).get(field) == value for field, value in expected.items())

    source_semantics: dict[str, Any] = {}
    velocity_ok = False
    contact_ok = False
    target_ok = False
    unified_ok = False
    parent_ok = False
    frame_fixture = contract.get("diagnostic_frame_fixture", {})
    source_semantics["diagnostic_frame_fixture"] = {
        "orientation_interpretation": frame_fixture.get("orientation_interpretation")
        if isinstance(frame_fixture, dict)
        else None,
        "origin_interpretation": frame_fixture.get("origin_interpretation")
        if isinstance(frame_fixture, dict)
        else None,
        "physical_pose_or_patch_authority": frame_fixture.get(
            "physical_pose_or_patch_authority"
        )
        if isinstance(frame_fixture, dict)
        else None,
    }
    try:
        velocity_contract = load_yaml(root / pins["contact_velocity_contract"]["path"])
        velocity_gate = load_json(root / pins["contact_velocity_gate"]["path"])
        vq = velocity_contract["quantities"]
        velocity_ok = (
            close(vq["current_design_target_hard_upper_bound"]["estimate"], 0.005)
            and close(vq["reduced_current_contact_consumer_candidate"]["upper_bound"], 0.005)
            and close(vq["original_provisional_contact_scenario_speed"]["estimate"], 0.05)
            and velocity_gate["semantic_reconciliation"] == "PASS"
            and velocity_gate["original_0p05_current_contact_consumer"] == "REJECT"
            and velocity_gate["physical_contact_ready"] is False
            and close(q("first_contact_speed_hard_upper_bound").get("estimate"), 0.005)
            and close(q("first_contact_speed_hard_upper_bound").get("lower_bound"), 0.0)
            and close(q("first_contact_speed_hard_upper_bound").get("upper_bound"), 0.005)
            and q("first_contact_speed_hard_upper_bound").get("si_unit") == "m/s"
            and close(q("diagnostic_closing_speed").get("estimate"), 0.005)
            and close(q("diagnostic_closing_speed").get("lower_bound"), 0.0)
            and close(q("diagnostic_closing_speed").get("upper_bound"), 0.005)
            and q("diagnostic_closing_speed").get("si_unit") == "m/s"
            and close(q("original_provisional_contact_speed").get("estimate"), 0.05)
            and close(q("original_provisional_contact_speed").get("lower_bound"), 0.01)
            and close(q("original_provisional_contact_speed").get("upper_bound"), 0.1)
            and q("original_provisional_contact_speed").get("si_unit") == "m/s"
            and "REJECTED_FOR_DG4_CURRENT_CONSUMER" in str(q("original_provisional_contact_speed").get("status"))
            and contract["consumer_policy"]["original_0p05_disposition"] == "REJECT_CURRENT_CONSUMER"
        )
        source_semantics["contact_velocity"] = {
            "hard_bound_quantity_ref": "first_contact_speed_hard_upper_bound",
            "diagnostic_speed_quantity_ref": "diagnostic_closing_speed",
            "original_0p05_disposition": velocity_gate["original_0p05_current_contact_consumer"],
            "physical_contact_ready": velocity_gate["physical_contact_ready"],
        }

        contact = load_yaml(root / pins["design_contact_model"]["path"])
        coeff = contact["normal_contact"]["coefficient_of_restitution"]
        window = contact["gripper_actuator"]["contact_window_T_c_s"]
        original_speed = contact["gripper_actuator"]["first_contact_closing_velocity_mps"]
        contact_ok = (
            contact["class"] == "BOUNDED_PROVISIONAL__NOT_A_MEASUREMENT__NOT_AS_BUILT"
            and all(
                claim_sensitive_metadata_exact(name)
                for name in (
                    "restitution_lower",
                    "restitution_nominal",
                    "restitution_upper",
                    "diagnostic_contact_window",
                )
            )
            and close(coeff["lower"], q("restitution_lower").get("estimate"))
            and close(coeff["nominal"], q("restitution_nominal").get("estimate"))
            and close(coeff["upper"], q("restitution_upper").get("estimate"))
            and close(window["nominal"], q("diagnostic_contact_window").get("estimate"))
            and close(window["lower"], q("diagnostic_contact_window").get("lower_bound"))
            and close(window["upper"], q("diagnostic_contact_window").get("upper_bound"))
            and close(original_speed["nominal"], 0.05)
            and original_speed["authority"] == "DESIGN_ESTIMATE_UNVERIFIED"
            and contact["next_stage_authorized"] is False
        )
        source_semantics["contact_model"] = {
            "class": contact["class"],
            "restitution_quantity_refs": ["restitution_lower", "restitution_nominal", "restitution_upper"],
            "contact_window_quantity_ref": "diagnostic_contact_window",
            "original_speed_quantity_ref": "original_provisional_contact_speed",
            "as_built_status": original_speed["as_built_status"],
        }

        targets = load_yaml(root / pins["target_models"]["path"])
        sat = targets["target_satellite_v0"]
        debris = targets["target_debris_v0"]
        target_ok = (
            close(sat["mass_kg"], q("target_satellite_mass").get("estimate"))
            and claim_sensitive_metadata_exact("target_satellite_contact_lever")
            and vector_close(sat["inertia_diag_kgm2"], q("target_satellite_inertia_diag").get("estimate"))
            and close(sat["grasp_primary"]["lever_to_com_m"], q("target_satellite_contact_lever").get("estimate", [None])[0])
            and close(debris["mass_kg"], q("target_debris_mass").get("estimate"))
            and vector_close(debris["inertia_diag_kgm2"], q("target_debris_inertia_diag").get("estimate"))
            and vector_close([x / 1000.0 for x in debris["grasp_primary"]["point_mm_D"]], q("target_debris_contact_lever").get("estimate"))
            and q("target_debris_contact_lever").get("status")
            == "SYNTHETIC_POINT_VECTOR_USED_AS_COM_LEVER__NOT_SSOT_LEVER_OR_PHYSICAL_PATCH"
            and q("target_debris_contact_lever").get("authority")
            == "DG4_SYNTHETIC_FIXTURE_FROM_TARGET_MODELS_V1_POINT_VECTOR"
            and targets["target_satellite_v0"]["confidence"].startswith("low")
            and targets["target_debris_v0"]["confidence"].startswith("low")
        )
        source_semantics["targets"] = {
            "target_ids": ["TARGET_SATELLITE_22KG", "TARGET_DEBRIS_150KG"],
            "authority": "TARGET_MASS_AND_INERTIA_SOURCE_BOUND__CONTACT_VECTORS_DIAGNOSTIC_FIXTURES",
            "debris_point_vector_disposition": "SYNTHETIC_COM_LEVER_FIXTURE__D_ORIGIN_TO_COM_NOT_ESTABLISHED",
            "physical_qualification_credit": False,
        }

        interface = load_yaml(root / pins["unified_r2_interface"]["path"])
        mass_ledger = load_yaml(root / pins["unified_r2_mass_ledger"]["path"])
        frame_tree = load_yaml(root / pins["unified_r2_frame_tree"]["path"])
        urdf_path = root / pins["unified_r2_urdf"]["path"]
        robot = ET.parse(urdf_path).getroot()
        urdf_links = robot.findall("link")
        urdf_joints = robot.findall("joint")
        urdf_mass = sum(float(node.attrib["value"]) for node in robot.findall("./link/inertial/mass"))
        c01 = next(item for item in mass_ledger["configurations"] if item["configuration_id"] == "C01")
        source_components = c01["inertia"]["components_kg_m2"]
        source_uncertainties = c01["inertia"]["standard_uncertainty_components_kg_m2"]
        component_order = ["Ixx", "Iyy", "Izz", "Ixy", "Ixz", "Iyz"]
        contract_components = q("service_inertia_c01_components").get("estimate")
        contract_uncertainties = q("service_inertia_c01_components").get("standard_uncertainty")
        bindings = interface["bindings"]
        unified_ok = (
            interface["schema"] == "UNIFIED_R2_SYSTEM_INTERFACE_V1"
            and interface["configuration"] == "C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT"
            and bindings["system_urdf_candidate"]["sha256"] == pins["unified_r2_urdf"]["sha256"]
            and bindings["system_frame_tree"]["sha256"] == pins["unified_r2_frame_tree"]["sha256"]
            and bindings["design_contact_model"]["sha256"] == pins["design_contact_model"]["sha256"]
            and bindings["nine_configuration_mass_properties"]["sha256"] == pins["unified_r2_mass_ledger"]["sha256"]
            and frame_tree["schema"] == "UNIFIED_R2_SYSTEM_FRAME_TREE_V2"
            and len(urdf_links) == 19
            and len(urdf_joints) == 18
            and close(urdf_mass, 31.022864807342987, 1e-12)
            and close(c01["mass"]["value_kg"], q("service_mass_c01").get("estimate"))
            and close(c01["mass"]["standard_uncertainty_kg"], q("service_mass_c01").get("standard_uncertainty"))
            and vector_close([source_components[k] for k in component_order], contract_components)
            and vector_close([source_uncertainties[k] for k in component_order], contract_uncertainties)
            and c01["mass"]["authority"] == "DESIGN_MODEL_R2"
        )
        source_semantics["unified_r2"] = {
            "system_mass_quantity_ref": "service_mass_c01",
            "system_inertia_quantity_ref": "service_inertia_c01_components",
            "urdf_link_count": len(urdf_links),
            "urdf_joint_count": len(urdf_joints),
            "as_built_status": "MEASUREMENT_PENDING",
        }

        parent = load_yaml(root / pins["parent_dynamics_authority"]["path"])
        boundary = parent["contact_target_actuator_boundary"]
        parent_ok = (
            parent["authority_scope"] == "CANDIDATE_ENGINEERING_ONLY"
            and boundary["contact"] == "BOUNDED_PROVISIONAL_NOT_AS_BUILT"
            and boundary["contact_transition_executed"] is False
            and boundary["target_attachment_executed"] is False
            and parent["next_stage_authorized"] is False
            and parent["release_credit"] is False
        )
        source_semantics["parent_boundary"] = boundary
    except (KeyError, StopIteration, TypeError, ValueError, ET.ParseError) as exc:
        source_semantics["exception"] = f"{type(exc).__name__}: {exc}"

    criterion("DG4-C03", "0.005 m/s hard bound is active and original 0.05 m/s is rejected", velocity_ok, source_semantics.get("contact_velocity"))
    criterion("DG4-C04", "bounded provisional contact parameters are bound without physical promotion", contact_ok, source_semantics.get("contact_model"))
    criterion("DG4-C05", "22 kg and 150 kg mass/inertia are source-bound and contact vectors remain synthetic frame fixtures", target_ok, source_semantics.get("targets"))
    criterion("DG4-C06", "Unified R2 interface, 19/18 URDF topology and C01 mass properties agree", unified_ok, source_semantics.get("unified_r2"))
    criterion("DG4-C07", "parent dynamics authority remains pre-contact and non-attached", parent_ok, source_semantics.get("parent_boundary"))

    state_machine = contract.get("state_machine", {})
    expected_transitions = [
        {"from": PRECONTACT, "event": "VALIDATED_BOUNDED_DIAGNOSTIC_ENTRY", "to": BOUNDED_CONTACT_DIAGNOSTIC},
        {"from": BOUNDED_CONTACT_DIAGNOSTIC, "event": "CONSERVATIVE_INTERNAL_IMPULSE_SOLVED", "to": POST_IMPACT_DIAGNOSTIC},
    ]
    state_machine_ok = (
        state_machine.get("initial_state") == PRECONTACT
        and state_machine.get("transitions") == expected_transitions
        and state_machine.get("terminal_state") == POST_IMPACT_DIAGNOSTIC
        and {"ATTACHED", "CAPTURED", "LOCKED_TARGET", "PRODUCTION_CONTACT", "NON_ABORT_OPERATIONAL"}.issubset(set(state_machine.get("prohibited_states", [])))
    )
    criterion("DG4-C08", "state machine contains only precontact, bounded impulse and separate post-impact states", state_machine_ok, state_machine)

    thresholds = {
        "linear": float(q("linear_momentum_residual_limit").get("estimate", -1.0)),
        "angular": float(q("angular_momentum_residual_limit").get("estimate", -1.0)),
        "restitution": float(q("restitution_residual_limit").get("estimate", -1.0)),
        "contact_origin": float(
            q("contact_origin_coincidence_residual_limit").get("estimate", -1.0)
        ),
        "energy": float(q("energy_identity_residual_limit").get("estimate", -1.0)),
    }
    cases: list[dict[str, Any]] = []
    solve_errors: list[str] = []
    prerequisite = pins_ok and not metadata_and_boundary_errors and velocity_ok and contact_ok and target_ok and unified_ok and parent_ok and state_machine_ok
    if prerequisite:
        rotation_i_from_s = np.asarray(frame_fixture["R_I_from_S"], dtype=float)
        rotation_i_from_t = np.asarray(frame_fixture["R_I_from_T"], dtype=float)
        rotation_i_from_d = np.asarray(frame_fixture["R_I_from_D"], dtype=float)
        service_inertia_s = inertia_from_components(
            q("service_inertia_c01_components")["estimate"]
        )
        service_inertia = rotation_i_from_s @ service_inertia_s @ rotation_i_from_s.T
        service_contact_lever_i = rotation_i_from_s @ np.asarray(
            q("service_contact_lever_about_service_com")["estimate"], dtype=float
        )
        for case in contract.get("cases", []):
            for corner in contract.get("restitution_corners", []):
                try:
                    target_rotation = (
                        rotation_i_from_t
                        if case["target_id"] == "TARGET_SATELLITE_22KG"
                        else rotation_i_from_d
                    )
                    target_inertia_source = diagonal_inertia(
                        q(case["inertia_quantity_ref"])["estimate"]
                    )
                    target_inertia = (
                        target_rotation @ target_inertia_source @ target_rotation.T
                    )
                    target_contact_lever_i = target_rotation @ np.asarray(
                        q(case["contact_lever_quantity_ref"])["estimate"], dtype=float
                    )
                    target_tumble_axis_i = target_rotation @ np.asarray(
                        q(case["tumble_axis_quantity_ref"])["estimate"], dtype=float
                    )
                    raw = solve_case(
                        case_id=f"{case['target_id']}__E_{corner['corner']}",
                        target_id=case["target_id"],
                        service_mass_kg=q("service_mass_c01")["estimate"],
                        service_inertia_kg_m2=service_inertia,
                        target_mass_kg=q(case["mass_quantity_ref"])["estimate"],
                        target_inertia_kg_m2=target_inertia,
                        service_contact_lever_m=service_contact_lever_i,
                        target_contact_lever_m=target_contact_lever_i,
                        contact_normal_axis=q("diagnostic_contact_normal_axis")["estimate"],
                        closing_speed_m_s=q("diagnostic_closing_speed")["estimate"],
                        hard_upper_bound_m_s=q("first_contact_speed_hard_upper_bound")["estimate"],
                        restitution=q(corner["quantity_ref"])["estimate"],
                        contact_window_s=q("diagnostic_contact_window")["estimate"],
                        target_tumble_rate_rad_s=q(case["tumble_rate_quantity_ref"])["estimate"],
                        target_tumble_axis=target_tumble_axis_i,
                        request_scope=contract["consumer_policy"]["accepted_request_scope"],
                        unknown_disposition=contract["consumer_policy"]["unknown_disposition"],
                        source_bindings_valid=True,
                    )
                    cases.append(_case_evidence(raw, thresholds))
                except (KeyError, TypeError, ValueError, FailClosedError, np.linalg.LinAlgError) as exc:
                    solve_errors.append(f"{case.get('target_id')}:{corner.get('corner')}:{type(exc).__name__}:{exc}")

    complete_case_set = len(cases) == 6 and not solve_errors and {item["target_id"] for item in cases} == {"TARGET_SATELLITE_22KG", "TARGET_DEBRIS_150KG"}
    criterion("DG4-C09", "six target-by-restitution design cases execute deterministically", complete_case_set, {"case_ids": [item["case_id"] for item in cases], "errors": solve_errors})

    speed_and_rejection_ok = bool(cases) and all(item["audits"]["speed_bound_pass"] for item in cases)
    original_rejected_runtime = False
    try:
        validate_request(
            scope="BOUNDED_DESIGN_DIAGNOSTIC_ONLY",
            requested_speed_m_s=0.05,
            hard_upper_bound_m_s=0.005,
            unknown_disposition=ABORT_ONLY,
            source_bindings_valid=True,
        )
    except FailClosedError as exc:
        original_rejected_runtime = str(exc) == "DG4_SPEED_BOUND_EXCEEDED_ABORT_ONLY"
    speed_and_rejection_ok = speed_and_rejection_ok and original_rejected_runtime
    criterion("DG4-C10", "all executed cases obey 0.005 m/s and runtime rejects 0.05 m/s", speed_and_rejection_ok, {"executed_case_count": len(cases), "original_0p05_runtime_disposition": "ABORT_ONLY" if original_rejected_runtime else "NOT_REJECTED"})

    transitions_ok = bool(cases) and all(item["state_sequence"] == [PRECONTACT, BOUNDED_CONTACT_DIAGNOSTIC, POST_IMPACT_DIAGNOSTIC] for item in cases)
    criterion("DG4-C11", "all cases traverse the exact three-state diagnostic sequence", transitions_ok, [item["state_sequence"] for item in cases])

    momentum_ok = bool(cases) and all(
        item["audits"]["impulse_pair_pass"]
        and item["audits"]["linear_momentum_pass"]
        and item["audits"]["angular_momentum_pass"]
        and item["audits"]["spin_angular_impulse_pass"]
        for item in cases
    )
    criterion("DG4-C12", "linear and inertial-origin angular momentum audits pass for both targets", momentum_ok, {"case_count": len(cases), "all_pass": momentum_ok})

    contact_math_ok = bool(cases) and all(
        item["audits"]["precontact_is_closing"]
        and item["audits"]["postimpact_is_separating"]
        and item["audits"]["restitution_pass"]
        and item["audits"]["contact_origin_coincident_pass"]
        for item in cases
    )
    criterion("DG4-C13", "restitution and contact-origin mathematical identities pass", contact_math_ok, {"case_count": len(cases), "all_pass": contact_math_ok})

    energy_ok = bool(cases) and all(item["audits"]["energy_nonincrease_pass"] and item["audits"]["energy_identity_pass"] for item in cases)
    criterion("DG4-C14", "kinetic energy never increases and independent loss identity closes", energy_ok, {"case_count": len(cases), "all_pass": energy_ok})

    physical = contract.get("physical_as_built", {})
    boundary = contract.get("release_boundary", {})
    diagnostic_fixture_boundary_ok = (
        q("diagnostic_contact_normal_axis").get("status")
        == "NOT_PHYSICAL_CONTACT_NORMAL_AUTHORITY"
        and q("service_contact_lever_about_service_com").get("status")
        == "EXPLICIT_ZERO_MODEL_CHOICE__NOT_UNKNOWN_ZERO_FILL"
        and q("target_debris_contact_lever").get("status")
        == "SYNTHETIC_POINT_VECTOR_USED_AS_COM_LEVER__NOT_SSOT_LEVER_OR_PHYSICAL_PATCH"
        and all(
            claim_sensitive_metadata_exact(name)
            for name in EXPECTED_CLAIM_SENSITIVE_METADATA
        )
        and frame_fixture.get("physical_pose_or_patch_authority") is False
        and contract.get("authority_scope") == EXPECTED_AUTHORITY_SCOPE
    )
    fail_closed_ok = (
        isinstance(physical, dict)
        and physical
        and all(value is None for value in physical.values())
        and contract.get("consumer_policy", {}).get("unknown_disposition") == ABORT_ONLY
        and bool(cases)
        and all(item["audits"]["two_separate_bodies_pass"] for item in cases)
        and all(item["separate_body_ledger"]["physical_contact_claimed"] is False for item in cases)
        and boundary.get("design_diagnostic_candidate_allowed") is True
        and all(
            boundary.get(field) is False
            for field in (
                "real_attachment_claimed",
                "physical_contact_claimed",
                "production_ready",
                "non_abort_grasp_ready",
                "hardware_valid",
                "flight_valid",
                "parent_DG4_satisfied",
                "next_stage_authorized",
                "release_credit",
            )
        )
        and contract.get("frozen_inputs_modified") is False
        and diagnostic_fixture_boundary_ok
    )
    criterion("DG4-C15", "physical/as-built nulls, UNKNOWN->ABORT and all release boundaries remain closed", fail_closed_ok, {"physical_as_built_all_null": isinstance(physical, dict) and bool(physical) and all(value is None for value in physical.values()), "unknown_disposition": contract.get("consumer_policy", {}).get("unknown_disposition"), "diagnostic_fixture_boundary_ok": diagnostic_fixture_boundary_ok, "release_boundary": boundary})

    support_files = []
    for path, role in ((contract_path, "CONTRACT"), (SOLVER, "SOLVER"), (Path(__file__), "EVALUATOR"), (TEST_FILE, "TEST_SUITE")):
        support_files.append({"role": role, "path": path.resolve().relative_to(root).as_posix() if path.resolve().is_relative_to(root) else str(path.resolve()), "bytes": path.stat().st_size if path.is_file() else None, "sha256": sha256(path) if path.is_file() else None})

    evidence = {
        "schema": "DG4_CONTACT_HYBRID_EVIDENCE_V1",
        "evaluation_time_policy": "OMITTED_FOR_BYTE_DETERMINISM",
        "authority_scope": contract.get("authority_scope"),
        "subject_sha256": sha256(contract_path),
        "source_semantics": source_semantics,
        "case_count": len(cases),
        "cases": cases,
        "consumer_decisions": {
            "0p005_m_s": "BOUNDED_DESIGN_DIAGNOSTIC_ONLY" if speed_and_rejection_ok else "ABORT_ONLY",
            "0p05_m_s": "ABORT_ONLY",
            "UNKNOWN": "ABORT_ONLY",
        },
        "physical_as_built": physical,
        "separate_postimpact_body_count": 2 if cases else None,
        "attachment_created": False,
        "physical_contact_claimed": False,
        "production_ready": False,
        "non_abort_grasp_ready": False,
    }
    evidence_payload = json.dumps(evidence, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(evidence_payload, encoding="utf-8", newline="\n")

    all_pass = all(item["state"] == "PASS" for item in criteria)
    unknown_auto_allow_count = (
        0
        if contract.get("consumer_policy", {}).get("unknown_disposition") == ABORT_ONLY
        else 1
    )
    gate = {
        "schema": "DG4_CONTACT_HYBRID_GATE_V1",
        "evaluation_time_policy": "OMITTED_FOR_BYTE_DETERMINISM",
        "subject": {"path": contract_path.resolve().relative_to(root).as_posix() if contract_path.resolve().is_relative_to(root) else str(contract_path.resolve()), "bytes": contract_path.stat().st_size, "sha256": sha256(contract_path)},
        "evidence": {"path": evidence_path.resolve().relative_to(root).as_posix() if evidence_path.resolve().is_relative_to(root) else str(evidence_path.resolve()), "bytes": len(evidence_payload.encode("utf-8")), "sha256": hashlib.sha256(evidence_payload.encode("utf-8")).hexdigest().upper()},
        "support_files": support_files,
        "criteria": criteria,
        "criteria_total": len(criteria),
        "criteria_passed": sum(item["state"] == "PASS" for item in criteria),
        "errors": errors,
        "design_diagnostic_candidate_complete": all_pass,
        "parent_DG4_satisfied": False,
        "real_attachment_ready": False,
        "physical_contact_ready": False,
        "production_ready": False,
        "non_abort_grasp_ready": False,
        "hardware_valid": False,
        "unknown_auto_allow_count": unknown_auto_allow_count,
        "verdict": (
            "DG4_CONTACT_HYBRID_CANDIDATE_15_OF_15_PASS__DESIGN_DIAGNOSTIC_ONLY__PARENT_DG4_PHYSICAL_HOLD"
            if all_pass
            else "DG4_CONTACT_HYBRID_CANDIDATE_FAIL__ABORT_ONLY"
        ),
        "gate": "PASS_CANDIDATE_WITH_PHYSICAL_HOLD" if all_pass else "FAIL",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }
    gate_payload = json.dumps(gate, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.write_text(gate_payload, encoding="utf-8", newline="\n")
    return evidence, gate, all_pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    args = parser.parse_args()
    _, gate, passed = evaluate(args.contract.resolve(), args.evidence.resolve(), args.gate.resolve())
    print(gate["verdict"])
    print(f"criteria: {gate['criteria_passed']}/{gate['criteria_total']}")
    print(f"gate_sha256: {sha256(args.gate.resolve())}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
