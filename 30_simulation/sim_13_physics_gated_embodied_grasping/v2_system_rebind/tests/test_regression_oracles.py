"""Tests for pinned historical oracles and the current V2 hard-lock limit."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pytest
import yaml

from sim13_v2.free_floating_dynamics import URDFTreeDynamics
from sim13_v2.regression_oracles import (
    CURRENT_OBSERVED_THRESHOLD_REGISTRY_SHA256,
    CURRENT_REEXECUTION_HOLD,
    EXPLICIT_FIXTURE_NO_AUTHORITY,
    HARD_LOCK_SCOPE,
    HISTORICAL_ARTIFACT_PINS,
    SIM10_EXPECTED_THRESHOLD_REGISTRY_SHA256,
    ExplicitTargetFixture,
    audit_current_reexecution_inputs,
    combine_unified_r2_service_body,
    half_last_digit_crosscheck,
    half_last_digit_tolerance,
    ideal_two_body_hard_lock,
    load_historical_regression_anchors,
    single_link_capture_sensitivity,
    validate_artifact_payload,
    validate_historical_artifacts,
)


HERE = Path(__file__).resolve()
PROJECT_ROOT = HERE.parents[4]


def _load_source_only_model() -> URDFTreeDynamics:
    source_dir = (
        PROJECT_ROOT
        / "20_engineering"
        / "F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
        / "unified_r2_digital_prototype_prebind"
        / "source_only_v2"
    )
    module_path = source_dir / "unified_r2_urdf_source_v2.py"
    module_name = "unified_r2_source_for_regression_oracle_test"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    inputs = yaml.safe_load(
        (source_dir / "UNIFIED_R2_URDF_SOURCE_INPUTS_V2.yaml").read_text(encoding="utf-8-sig")
    )
    # This source-only validator entry point builds an Element in memory.  It
    # neither calls the authorization-gated generator nor writes a URDF.
    robot = module._build_robot(inputs)
    return URDFTreeDynamics(ET.tostring(robot, encoding="utf-8"))


@pytest.fixture(scope="module")
def current_model() -> URDFTreeDynamics:
    return _load_source_only_model()


@pytest.fixture(scope="module")
def explicit_target() -> ExplicitTargetFixture:
    return ExplicitTargetFixture(
        fixture_id="TEST_TARGET_22KG_NO_AUTHORITY",
        mass_kg=22.0,
        com_root_m=np.array((0.85, 0.12, -0.04)),
        inertia_about_com_root_kg_m2=np.array(
            ((0.42, 0.015, 0.0), (0.015, 0.51, -0.01), (0.0, -0.01, 0.60))
        ),
        linear_velocity_root_m_s=np.zeros(3),
        angular_velocity_root_rad_s=np.deg2rad(3.0)
        * np.array((1.0, 0.15, 0.4))
        / np.linalg.norm((1.0, 0.15, 0.4)),
    )


def test_all_historical_artifact_byte_and_sha_pins_are_exact():
    report = validate_historical_artifacts(PROJECT_ROOT)
    assert report["all_required_exact"] is True
    assert report["all_present_artifacts_exact"] is True
    assert report["historical_gate_preserved"] is True
    assert report["unified_r2_pass_inherited"] is False
    records = report["artifacts"]
    assert records["sim05_base_attitude_csv"].actual_bytes == 69231
    assert records["sim06_capture_matrix_csv"].actual_bytes == 6431
    assert records["sim10_gate_json"].actual_bytes == 5951
    assert records["e19_diagnostic_gate_json"].actual_bytes == 5425


def test_artifact_pin_rejects_even_one_appended_byte():
    pin = next(item for item in HISTORICAL_ARTIFACT_PINS if item.artifact_id == "sim05_base_attitude_csv")
    payload = (PROJECT_ROOT / pin.relative_path).read_bytes()
    validation = validate_artifact_payload(pin, payload + b"\n")
    assert validation.exact is False
    assert validation.status == "BYTE_OR_SHA_MISMATCH"
    assert validation.actual_bytes == pin.bytes + 1


def test_sim05_peak_is_only_a_stored_resolution_historical_anchor():
    anchors = load_historical_regression_anchors(PROJECT_ROOT)
    assert anchors["sim05"]["peak_base_deviation_text_deg"] == "19.199852"
    assert anchors["sim05"]["peak_base_deviation_deg"] == pytest.approx(19.199852)
    assert anchors["sim05"]["classification"] == "HISTORICAL_CSV_STORAGE_RESOLUTION_ANCHOR"
    assert anchors["unified_r2_pass_inherited"] is False


def test_sim06_three_stored_capture_anchors_are_exact():
    sim06 = load_historical_regression_anchors(PROJECT_ROOT)["sim06"]
    assert sim06["debris_3dps"]["stored_post_rate_text_dps"] == "3.06333"
    assert sim06["satellite_3dps"]["stored_post_rate_text_dps"] == "1.38721"
    assert sim06["satellite_0p5dps"]["stored_post_rate_text_dps"] == "0.231202"
    assert all(item["v_app_mps"] == pytest.approx(0.01) for item in sim06.values())


def test_sim10_exact_anchors_regions_and_half_last_digit_crosschecks():
    sim10 = load_historical_regression_anchors(PROJECT_ROOT)["sim10"]
    debris = sim10["debris_sim06"]
    satellite = sim10["satellite_sim06"]
    assert debris["exact_post_rate_dps"] == 3.0633304945807067
    assert debris["region"] == "INFEASIBLE_RATE"
    assert satellite["exact_post_rate_dps"] == 1.3872061825379134
    assert satellite["region"] == "WHEELS_ONLY_FEASIBLE"
    assert debris["csv_crosscheck"].within_tolerance is True
    assert satellite["csv_crosscheck"].within_tolerance is True
    assert debris["csv_crosscheck"].half_last_digit_tolerance == pytest.approx(5.0e-6)
    assert satellite["csv_crosscheck"].half_last_digit_tolerance == pytest.approx(5.0e-6)


def test_half_last_digit_rule_tracks_explicit_storage_precision():
    assert half_last_digit_tolerance("0.231202") == pytest.approx(5.0e-7)
    assert half_last_digit_crosscheck(0.2312024, "0.231202").within_tolerance is True
    assert half_last_digit_crosscheck(0.2312026, "0.231202").within_tolerance is False


def test_optional_e19_remains_hold_without_release_credit():
    e19 = load_historical_regression_anchors(PROJECT_ROOT)["e19_optional"]
    assert e19 is not None
    assert e19["gate"] == "HOLD"
    assert e19["release_credit"] is False
    assert e19["next_stage_authorized"] is False
    assert e19["authority_scope"] == "ISOLATED_NUMERIC_DIAGNOSTIC_EXECUTION_ONLY"


def test_current_reexecution_is_held_for_legacy_paths_and_registry_hash_drift():
    audit = audit_current_reexecution_inputs(PROJECT_ROOT)
    assert audit["current_reexecution_status"] == CURRENT_REEXECUTION_HOLD
    assert audit["legacy_default_path_missing"] is True
    assert all(not item["exists"] for item in audit["legacy_default_inputs"].values())
    registry = audit["threshold_registry"]
    assert registry["expected_sha256"] == SIM10_EXPECTED_THRESHOLD_REGISTRY_SHA256
    assert registry["actual_sha256"] == CURRENT_OBSERVED_THRESHOLD_REGISTRY_SHA256
    assert registry["matches_sim10_frozen_expected"] is False
    assert registry["matches_observed_current_pin"] is True
    assert audit["historical_sim10_gate_preserved"] is True
    assert audit["historical_gate_is_current_reexecution"] is False
    assert audit["unified_r2_pass_inherited"] is False


def test_current_v2_service_mass_com_and_inertia_are_combined_from_bodies(current_model):
    q = np.linspace(-0.12, 0.08, current_model.movable_dof)
    aggregate = combine_unified_r2_service_body(current_model, q)
    assert aggregate.mass_kg == pytest.approx(31.022864807342987, abs=1.0e-12)
    assert aggregate.physical_link_count == 16
    assert np.all(np.isfinite(aggregate.com_root_m))
    np.testing.assert_allclose(
        aggregate.inertia_about_com_root_kg_m2,
        aggregate.inertia_about_com_root_kg_m2.T,
        atol=1.0e-13,
        rtol=0.0,
    )
    assert np.min(np.linalg.eigvalsh(aggregate.inertia_about_com_root_kg_m2)) > 0.0


def test_ideal_two_body_hard_lock_conserves_momentum_and_dissipates_energy(
    current_model, explicit_target
):
    aggregate = combine_unified_r2_service_body(current_model, np.zeros(current_model.movable_dof))
    result = ideal_two_body_hard_lock(
        aggregate,
        explicit_target,
        service_linear_velocity_root_m_s=(-0.01, 0.002, 0.0),
        service_angular_velocity_root_rad_s=(0.0, 0.0, 0.0),
    )
    assert result.scope == HARD_LOCK_SCOPE
    assert result.target_authority_class == EXPLICIT_FIXTURE_NO_AUTHORITY
    assert result.linear_momentum_relative_residual < 1.0e-14
    assert result.angular_momentum_relative_residual < 1.0e-14
    np.testing.assert_allclose(
        result.linear_momentum_pre_kg_m_s,
        result.linear_momentum_post_kg_m_s,
        atol=1.0e-14,
        rtol=0.0,
    )
    np.testing.assert_allclose(
        result.angular_momentum_pre_about_root_kg_m2_s,
        result.angular_momentum_post_about_root_kg_m2_s,
        atol=1.0e-14,
        rtol=0.0,
    )
    assert result.kinetic_energy_post_j <= result.kinetic_energy_pre_j + 1.0e-14
    assert result.plastic_energy_nonincrease is True
    assert result.contact_force_available is False
    assert result.contact_time_history_available is False


def test_one_link_perturbation_changes_current_capture_limit(current_model, explicit_target):
    result = single_link_capture_sensitivity(
        current_model,
        np.zeros(current_model.movable_dof),
        explicit_target,
        "link3",
        mass_scale=1.02,
        inertia_scale=1.03,
        com_delta_link_m=(0.001, 0.0, 0.0),
        service_linear_velocity_root_m_s=(-0.01, 0.0, 0.0),
    )
    assert result["capture_output_changed"] is True
    assert result["omega_vector_delta_norm_rad_s"] > 0.0
    assert abs(result["post_rate_delta_dps"]) > 0.0
    assert result["baseline"].scope == HARD_LOCK_SCOPE
    assert result["perturbed"].scope == HARD_LOCK_SCOPE

