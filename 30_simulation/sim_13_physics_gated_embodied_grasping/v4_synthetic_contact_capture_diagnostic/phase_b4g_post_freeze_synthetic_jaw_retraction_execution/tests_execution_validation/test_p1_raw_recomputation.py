from __future__ import annotations

import copy
import math

import numpy as np
import pytest

from b4g_validation.core import ValidationReport, canonical_sha256
from b4g_validation.mutation_replay import (
    apply_restricted_patch,
    certify_clearance_independent,
    evaluate_payload,
    expected_patch_target,
    validate_patch_semantics,
)
from b4g_validation import validator


def test_registered_a1_command_dose_cannot_be_coordinately_relabelled() -> None:
    slot = {
        "arm": "A1", "case_id": "RK4_REFERENCE__A1__ALPHA_2__TCMD_MS_10",
        "alpha": 2.0, "command_duration_s": 0.01,
    }
    metadata = {
        "case_id": slot["case_id"],
        "command_parameters": {
            "left": {"alpha": 4.0, "delay_s": 0.0, "duration_s": 0.01},
            "right": {"alpha": 4.0, "delay_s": 0.0, "duration_s": 0.01},
        },
    }
    report = ValidationReport(mode="campaign")
    assert not validator._validate_registered_command(report, metadata, slot)
    assert "CASE_REGISTERED_COMMAND_MISMATCH" in {row["code"] for row in report.failures}


def test_registered_a2_variant_binds_ratio_delay_and_full_parent_duration() -> None:
    parent = {"alpha": 2.0, "command_duration_s": 0.02}
    slot = {"arm": "A2", "case_id": "A2", "variant_id": "RIGHT_HALF_DELAY"}
    metadata = {
        "case_id": "A2",
        "command_parameters": {
            "selected_parent_level": parent,
            "left": {"alpha": 2.0, "delay_s": 0.0, "duration_s": 0.02},
            "right": {"alpha": 1.0, "delay_s": 0.005, "duration_s": 0.02},
        },
    }
    clean = ValidationReport(mode="campaign")
    assert validator._validate_registered_command(clean, metadata, slot)
    assert clean.passed
    metadata["command_parameters"]["right"]["duration_s"] = 0.01
    tampered = ValidationReport(mode="campaign")
    assert not validator._validate_registered_command(tampered, metadata, slot)


def _stage_fixture() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sample_time = np.asarray([0.0, 0.001], dtype="<f8")
    codes, stage_time = validator._expected_stage_rows(sample_time, method="rk4")
    service = np.zeros((len(codes), 29), dtype="<f8")
    return sample_time, codes, stage_time, service


def test_valid_domain_exit_keeps_only_true_raw_prefailure_stage_prefix() -> None:
    sample_time, codes, stage_time, service = _stage_fixture()
    codes = np.concatenate((codes, np.asarray([1], dtype="<i8")))
    stage_time = np.concatenate((stage_time, np.asarray([0.001], dtype="<f8")))
    service = np.vstack((service, np.zeros((1, 29), dtype="<f8")))
    flags = np.ones(len(codes), dtype=np.bool_)
    report = ValidationReport(mode="campaign")
    assert validator._validate_stage_contract(
        report, prefix="TEST", lane="RK4_COARSE",
        sample_time=sample_time, sample_service=np.zeros((2, 29), dtype="<f8"),
        stage_time=stage_time, stage_code=codes, stage_service=service,
        stage_flags=flags, domain_exit=True,
    )
    assert report.passed, report.failures


def _opening_audit_record() -> dict:
    return {
        "P_coordinates_m_left_right": [0.02, 0.03],
        "raw_gap_jacobian_dimensionless": [[1.0, 0.0], [0.0, 1.0]],
        "diagonal_gap_derivatives_dimensionless": [1.0, 1.0],
        "opening_sign_left_right": [1, 1],
        "nominal_gap_m_left_right": [0.0, 0.0],
        "nominal_gap_rate_m_s_left_right": [0.0, 0.0],
        "contact_force_max_N": 0.0,
        "contact_torque_max_N_m": 0.0,
    }


def test_consumed_sign_domain_exit_uses_native_variable_shape_without_centered_step() -> None:
    failure = {
        "time_s": 0.0105,
        "stage_label": "STEP_10_K2",
        **_opening_audit_record(),
        "generalized_force_14": [0.0] * 14,
        "consumed_opening_sign_left_right": [-1, 1],
        "consumed_sigma_equals_raw_and_registered": False,
        "Q_base_and_R_exact_zero": True,
        "contact_kernel_enabled": False,
        "accepted": False,
        "reason": "CONSUMED_OPENING_SIGN_MISMATCH",
    }
    report = ValidationReport(mode="campaign")
    assert validator._validate_domain_exit_record(
        report,
        geometry={
            "failure_probe_source": "FROZEN_SOLVER_DOMAINEXIT_RECORD",
            "failure": failure,
        },
        case_id="DOMAIN_EXIT_CONSUMED",
        accepted_end_time_s=0.01,
        frozen_step_s=0.001,
    )
    assert report.passed, report.failures


def test_opening_sign_domain_exit_cannot_omit_raw_sign_audit() -> None:
    failure = {
        "time_s": 0.0105,
        "stage_label": "STEP_10_K2",
        "P_coordinates_m_left_right": [0.02, 0.03],
        "centered_step_m": 1.0e-7,
        "raw_gap_jacobian_dimensionless": [[-1.0, 0.0], [0.0, 1.0]],
        "diagonal_gap_derivatives_dimensionless": [-1.0, 1.0],
        # opening_sign_left_right deliberately absent
        "nominal_gap_m_left_right": [0.0, 0.0],
        "nominal_gap_rate_m_s_left_right": [0.0, 0.0],
        "contact_force_max_N": 0.0,
        "contact_torque_max_N_m": 0.0,
        "reason": "OPENING_SIGN_CHANGED_OR_NONPOSITIVE",
    }
    report = ValidationReport(mode="campaign")
    assert not validator._validate_domain_exit_record(
        report,
        geometry={
            "failure_probe_source": "FROZEN_SOLVER_DOMAINEXIT_RECORD",
            "failure": failure,
        },
        case_id="DOMAIN_EXIT_SIGN",
        accepted_end_time_s=0.01,
        frozen_step_s=0.001,
    )
    assert "CASE_DOMAIN_EXIT_OPENING_SIGN_JACOBIAN_BINDING" in {
        row["code"] for row in report.failures
    }


@pytest.mark.parametrize(
    "operation",
    [
        {"op": "replace", "path": "/payload/items/-1", "value": 9},
        {"op": "replace", "path": "/payload/items/01", "value": 9},
        {"op": "replace", "path": "/payload/~2items/0", "value": 9},
        {"op": "replace", "path": "/payload/items/0", "value": 9, "from": "/x"},
    ],
)
def test_restricted_patch_rejects_noncanonical_or_ambiguous_pointer(
    operation: dict,
) -> None:
    patch = {
        "schema": "SIM13_V4B4G_MUTATION_PATCH_V1",
        "receipt_id": "TEST",
        "target": operation["path"],
        "format": "RFC6902_JSON_V1_RESTRICTED",
        "base_sha256": "A" * 64,
        "mutant_sha256": "B" * 64,
        "operations": [operation],
    }
    with pytest.raises((KeyError, ValueError)):
        apply_restricted_patch({"payload": {"items": [1, 2]}}, patch)


def test_displaced_governance_or_terminal_credit_is_rejected_recursively() -> None:
    report = ValidationReport(mode="campaign")
    validator._reject_displaced_governance_claims(
        report,
        {
            "innocent": {
                "owner_authorized": True,
                "physical_left_actuator_force_capacity_N": 12.0,
                "audited": True,
            },
        },
        required_false={"owner_authorized": False},
        required_null_names=["physical_left_actuator_force_capacity_N"],
        code="TEST_GOVERNANCE",
    )
    codes = {row["code"] for row in report.failures}
    assert "TEST_GOVERNANCE_REQUIRED_FALSE_DISPLACED" in codes
    assert "TEST_GOVERNANCE_REQUIRED_NULL_DISPLACED" in codes
    assert "TEST_GOVERNANCE_TERMINAL_CREDIT_DISPLACED" in codes


def test_rk4_stage_pattern_cannot_be_relabelled_as_midpoint_lane() -> None:
    sample_time, codes, stage_time, service = _stage_fixture()
    flags = np.ones(len(codes), dtype=np.bool_)
    report = ValidationReport(mode="campaign")
    assert not validator._validate_stage_contract(
        report, prefix="TEST", lane="MIDPOINT_COARSE",
        sample_time=sample_time, sample_service=np.zeros((2, 29), dtype="<f8"),
        stage_time=stage_time, stage_code=codes, stage_service=service,
        stage_flags=flags, domain_exit=False,
    )
    assert "TEST_STAGE_CODE_PATTERN" in {row["code"] for row in report.failures}


def test_all_root_clearance_rejects_endpoint_only_interior_dip_and_selects_earliest() -> None:
    endpoint_only = certify_clearance_independent(
        [0.002, 0.003], [2.0e-6, 2.0e-6], [2.0e-6, 2.0e-6],
        [0.012, 0.012], [0.0, 0.0], acquisition_time_s=0.0,
        ledger_interval_certified=[True],
    )
    assert endpoint_only["finite_event"] is False
    assert endpoint_only["endpoint_only"] is False

    earliest = certify_clearance_independent(
        [0.002, 0.003, 0.004], [2.0e-6] * 3, [2.0e-6] * 3,
        [0.0] * 3, [0.0] * 3, acquisition_time_s=0.0,
        ledger_interval_certified=[True, True],
    )
    assert earliest["finite_event"] is True
    assert earliest["tau_c_s"] == pytest.approx(0.002, abs=1.0e-14)
    assert earliest["removal_time_s"] == pytest.approx(0.003, abs=1.0e-14)


def test_incomplete_a2_acquisition_relative_grid_is_predicate_false() -> None:
    def item(time: list[float]) -> dict:
        count = len(time)
        return {
            "metadata": {
                "event_provenance": {"acquisition_time_s": 1.0},
                "responses": {"finite_removal_event": False},
                "terminal_status": "NO_EVENT",
            },
            "arrays": {
                "time_s": np.asarray(time, dtype="<f8"),
                "left_gap_m": np.zeros(count), "right_gap_m": np.zeros(count),
                "left_gap_rate_m_s": np.zeros(count), "right_gap_rate_m_s": np.zeros(count),
                "signed_W_act_J": np.zeros(count),
            },
        }
    metrics = validator._mirror_metrics(item([1.0, 1.001]), item([1.0, 1.002]))
    assert metrics["scientific_predicate"] is False
    assert metrics["full_relative_grid_equal"] is False
    assert metrics["missing_exact_common_grid"] is True
    assert metrics["common_relative_sample_count"] == 1


def _reference_item(lane: str, alpha: float, integrity: bool, self_report: bool) -> dict:
    case_id = f"{lane}__{alpha}"
    return {
        "slot": {"arm": "A1", "lane_id": lane, "alpha": alpha, "command_duration_s": 0.005},
        "metadata": {
            "arm": "A1", "lane_id": lane, "case_id": case_id,
            "event_provenance": {
                "fresh_b3_reconstruction": True, "lane_id": lane,
                "acquisition_time_s": 0.01, "removal_time_s": 0.02,
                "acquisition_certificate_sha256": ("A" if lane.startswith("RK4") else "B") * 64,
                "clearance_certificate_sha256": ("C" if lane.startswith("RK4") else "D") * 64,
            },
            "responses": {"selector_case_integrity_pass": self_report},
        },
        "arrays": {"signed_W_act_J": np.asarray([0.0, alpha * 1.0e-6])},
        "metrics": {
            "g16_predicate": True, "g09_predicate": True, "g11_pass": True,
            "independent_integrity_pass": integrity,
            "clearance": {"removal_time_s": 0.02},
        },
    }


def test_selector_uses_raw_integrity_not_coordinated_self_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(validator, "ALPHAS", (0.5, 1.0))
    monkeypatch.setattr(validator, "DURATIONS", (0.005,))
    records = {}
    index = 0
    for alpha in validator.ALPHAS:
        for lane in validator.REFERENCE_LANES:
            records[index] = _reference_item(lane, alpha, integrity=True, self_report=False)
            index += 1
    report = ValidationReport(mode="campaign")
    _gates, eligible = validator._compute_reference_eligibility(report, records)
    assert [row["alpha"] for row in eligible] == [0.5, 1.0]
    assert eligible[0]["alpha"] == 0.5


def test_exactly_one_reference_finite_is_evaluated_negative_not_na(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(validator, "ALPHAS", (1.0,))
    monkeypatch.setattr(validator, "DURATIONS", (0.005,))
    rk = _reference_item("RK4_REFERENCE", 1.0, integrity=True, self_report=True)
    midpoint = _reference_item(
        "MIDPOINT_REFERENCE", 1.0, integrity=True, self_report=True,
    )
    midpoint["metrics"]["g09_predicate"] = False
    report = ValidationReport(mode="campaign")
    gates, eligible = validator._compute_reference_eligibility(
        report, {0: rk, 1: midpoint},
    )
    assert report.passed, report.failures
    assert eligible == []
    assert gates == [{
        "gate_id": validator.G12,
        "evaluation_status": "PASS",
        "scientific_predicate": False,
        "applicability_reason": "EXACTLY_ONE_REFERENCE_FINITE_EVENT_EVALUATED_NEGATIVE_OUTCOME",
        "detail": {
            "level_id": "ALPHA_1P0__TCMD_MS_5",
            "alpha": 1.0,
            "T_cmd_s": 0.005,
            "rk4_finite": True,
            "midpoint_finite": False,
            "eligible": False,
            "one_reference_success_only_rule_applied": True,
        },
    }]


def test_a0_fake_metadata_pass_cannot_hide_raw_parent_trace_error() -> None:
    count = 2
    state = np.zeros((count, 29), dtype="<f8")
    state[:, 3] = 1.0
    raw = {
        "service_state_29": state,
        "left_gap_m": np.zeros(count), "right_gap_m": np.zeros(count),
        "left_gap_rate_m_s": np.zeros(count), "right_gap_rate_m_s": np.zeros(count),
    }
    parent = {
        "service_position_m": np.zeros((count, 3)),
        "service_quaternion_wxyz": np.tile([1.0, 0.0, 0.0, 0.0], (count, 1)),
        "R_joint_coordinates_rad": np.zeros((count, 6)),
        "P_joint_coordinates_m": np.zeros((count, 2)),
        "base_linear_m_s": np.zeros((count, 3)),
        "base_angular_rad_s": np.zeros((count, 3)),
        "R_joint_rad_s": np.zeros((count, 6)),
        "P_joint_m_s": np.zeros((count, 2)),
        "left_gap_m": np.zeros(count), "right_gap_m": np.zeros(count),
        "left_gap_rate_m_s": np.zeros(count), "right_gap_rate_m_s": np.zeros(count),
    }
    raw["service_state_29"][1, 13] = 1.0e-6
    computed = validator._a0_channel_maxima(raw, parent, np.asarray([True, True]))
    forged_metadata_maxima = {name: 0.0 for name in computed}
    assert forged_metadata_maxima != computed
    assert computed["P_joint_coordinates_m"] > 1.0e-12


def test_a0_nonunit_quaternion_cannot_pass_by_dot_product_clipping() -> None:
    count = 2
    state = np.zeros((count, 29), dtype="<f8")
    state[:, 3] = 1.0
    state[1, 4] = 100.0
    raw = {
        "service_state_29": state,
        "left_gap_m": np.zeros(count), "right_gap_m": np.zeros(count),
        "left_gap_rate_m_s": np.zeros(count), "right_gap_rate_m_s": np.zeros(count),
    }
    parent = {
        "service_position_m": np.zeros((count, 3)),
        "service_quaternion_wxyz": np.tile([1.0, 0.0, 0.0, 0.0], (count, 1)),
        "R_joint_coordinates_rad": np.zeros((count, 6)),
        "P_joint_coordinates_m": np.zeros((count, 2)),
        "base_linear_m_s": np.zeros((count, 3)),
        "base_angular_rad_s": np.zeros((count, 3)),
        "R_joint_rad_s": np.zeros((count, 6)),
        "P_joint_m_s": np.zeros((count, 2)),
        "left_gap_m": np.zeros(count), "right_gap_m": np.zeros(count),
        "left_gap_rate_m_s": np.zeros(count), "right_gap_rate_m_s": np.zeros(count),
    }
    computed = validator._a0_channel_maxima(
        raw, parent, np.asarray([True, True]),
    )
    assert computed["service_quaternion_geodesic_rad"] == np.inf


def test_a0_parent_oracle_is_the_hash_bound_b4e_active_trace() -> None:
    report = ValidationReport(mode="campaign")
    events, acquisitions, traces = validator._load_b4e_provenance_templates(report)
    assert report.passed, report.failures
    assert set(events) == set(validator.LANES)
    assert set(acquisitions) == set(validator.LANES)
    assert set(traces) == set(validator.LANES)
    for lane, arrays in traces.items():
        assert set(arrays) == validator.A0_PARENT_ARRAYS, lane
        assert arrays["time_s"][-1] == pytest.approx(0.08, abs=1.0e-15)


def _immutable_geometry_fixture() -> tuple[dict, dict[str, np.ndarray]]:
    active = validator.read_json_strict(
        validator.B4E_PROVENANCE_FILES["active_traces"][0]
    )["runs"]["rk4_coarse"]["trace"]
    acquisition = validator.read_json_strict(
        validator.B4E_PROVENANCE_FILES["acquisitions"][0]
    )["runs"]["rk4_coarse"]
    service = np.hstack((
        np.asarray(active["service_position_m"], dtype="<f8"),
        np.asarray(active["service_quaternion_wxyz"], dtype="<f8"),
        np.asarray(active["service_joint_coordinates_mixed"], dtype="<f8"),
        np.asarray(active["eta_mixed"], dtype="<f8"),
    ))[:2]
    target = np.hstack((
        np.asarray(active["target_position_m"], dtype="<f8"),
        np.asarray(active["target_quaternion_wxyz"], dtype="<f8"),
        np.asarray(active["target_twist_mixed"], dtype="<f8"),
    ))[:2]
    snapshot = acquisition["snapshot"]
    jacobians = np.asarray([
        validator.centered_gap_jacobian(row, snapshot=snapshot).raw_gap_jacobian_p
        for row in service
    ], dtype="<f8")
    arrays = {
        "service_state_29": service,
        "target_state_13": target,
        "left_gap_m": np.asarray(active["left_gap_m"], dtype="<f8")[:2],
        "right_gap_m": np.asarray(active["right_gap_m"], dtype="<f8")[:2],
        "left_gap_rate_m_s": np.asarray(active["left_gap_rate_m_s"], dtype="<f8")[:2],
        "right_gap_rate_m_s": np.asarray(active["right_gap_rate_m_s"], dtype="<f8")[:2],
        "stage_service_state_29": service.copy(),
        "stage_P_coordinates_m": service[:, 13:15].copy(),
        "stage_gap_jacobian_P": jacobians,
    }
    return snapshot, arrays


def test_active_geometry_replay_rejects_coordinated_raw_target_gap_and_jacobian_tamper() -> None:
    snapshot, arrays = _immutable_geometry_fixture()
    clean = validator._replay_active_geometry_arrays(arrays, snapshot)
    assert clean["active_target_state_max_abs_error"] <= 1.0e-12
    assert clean["active_gap_max_abs_error_m"] <= 1.0e-12
    assert clean["active_gap_rate_max_abs_error_m_s"] <= 1.0e-12
    assert clean["active_stage_gap_jacobian_max_abs_error"] <= 1.0e-12

    tampered = copy.deepcopy(arrays)
    tampered["target_state_13"][0, 0] += 1.0e-6
    observation = validator.recompute_gap_rate(
        tampered["service_state_29"][0], tampered["target_state_13"][0]
    )
    tampered["left_gap_m"][0], tampered["right_gap_m"][0] = observation.gaps_m
    tampered["left_gap_rate_m_s"][0], tampered["right_gap_rate_m_s"][0] = (
        observation.gap_rates_m_s
    )
    tampered["stage_gap_jacobian_P"][0, 0, 0] += 1.0e-6
    replay = validator._replay_active_geometry_arrays(tampered, snapshot)
    assert replay["active_target_state_max_abs_error"] > 1.0e-12
    assert replay["active_gap_max_abs_error_m"] > 1.0e-12
    assert replay["active_stage_gap_jacobian_max_abs_error"] > 1.0e-12


def test_post_geometry_replay_rejects_stored_gap_and_jacobian_tamper() -> None:
    _snapshot, active = _immutable_geometry_fixture()
    service = active["service_state_29"]
    target = active["target_state_13"]
    observations = [
        validator.recompute_gap_rate(service_row, target_row)
        for service_row, target_row in zip(service, target)
    ]
    jacobians = np.asarray([
        validator.centered_gap_jacobian(
            service_row, independent_target_state_13=target_row,
        ).raw_gap_jacobian_p
        for service_row, target_row in zip(service, target)
    ], dtype="<f8")
    arrays = {
        "post_service_state_29": service,
        "post_target_state_13": target,
        "post_left_gap_m": np.asarray([row.gaps_m[0] for row in observations]),
        "post_right_gap_m": np.asarray([row.gaps_m[1] for row in observations]),
        "post_left_gap_rate_m_s": np.asarray([
            row.gap_rates_m_s[0] for row in observations
        ]),
        "post_right_gap_rate_m_s": np.asarray([
            row.gap_rates_m_s[1] for row in observations
        ]),
        "post_stage_service_state_29": service.copy(),
        "post_stage_target_state_13": target.copy(),
        "post_stage_P_coordinates_m": service[:, 13:15].copy(),
        "post_stage_gap_jacobian_P": jacobians,
    }
    clean = validator._replay_post_geometry_arrays(arrays)
    assert clean["post_gap_max_abs_error_m"] == 0.0
    assert clean["post_gap_rate_max_abs_error_m_s"] == 0.0
    assert clean["post_stage_gap_jacobian_max_abs_error"] == 0.0
    arrays["post_left_gap_m"][0] += 1.0e-6
    arrays["post_stage_gap_jacobian_P"][0, 1, 1] -= 1.0e-6
    rejected = validator._replay_post_geometry_arrays(arrays)
    assert rejected["post_gap_max_abs_error_m"] > 1.0e-12
    assert rejected["post_stage_gap_jacobian_max_abs_error"] > 1.0e-12


def test_active_initial_state_is_rebuilt_from_event_configuration_and_z_plus() -> None:
    report = ValidationReport(mode="campaign")
    events, acquisitions, traces = validator._load_b4e_provenance_templates(report)
    assert report.passed, report.failures
    lane = "RK4_COARSE"
    case_id = "INITIAL_STATE_BINDING_TEST"
    event = copy.deepcopy(events[lane])
    acquisition = copy.deepcopy(acquisitions[lane])
    event["run_id"] = case_id
    acquisition["run_id"] = case_id
    metadata = {
        "case_id": case_id,
        "event_provenance": {
            "acquisition_certificate_payload": {
                "lane_id": lane, "case_id": case_id,
                "event": event, "acquisition": acquisition,
            },
        },
    }
    expected = validator._expected_initial_states_from_acquisition_payload(
        report, metadata,
    )
    assert expected is not None
    service, target = expected
    immutable = traces[lane]
    immutable_service = np.concatenate((
        immutable["service_position_m"][0],
        immutable["service_quaternion_wxyz"][0],
        immutable["R_joint_coordinates_rad"][0],
        immutable["P_joint_coordinates_m"][0],
        immutable["base_linear_m_s"][0],
        immutable["base_angular_rad_s"][0],
        immutable["R_joint_rad_s"][0],
        immutable["P_joint_m_s"][0],
    ))
    assert np.max(np.abs(service - immutable_service)) <= 1.0e-12
    assert target.shape == (13,)
    assert np.array_equal(service[15:29], np.asarray(acquisition["z_plus_reduced"][:14]))


@pytest.mark.parametrize(
    "template_source",
    [
        "INDEPENDENT_B3_RERUN_FIRST_QUALIFYING_SAMPLE",
        "HASH_BOUND_B3_REFERENCE_RECORD_205",
    ],
)
def test_fresh_certificate_allows_only_source_and_two_ulp_dissipation(
    template_source: str,
) -> None:
    lane = "RK4_COARSE"
    case_id = "RK4_COARSE__A1__ALPHA_1__TCMD_MS_5"
    fixed_dissipation = 2.0e-6
    fresh_dissipation = float(np.nextafter(fixed_dissipation, math.inf))
    event_template = {
        "run_id": lane.lower(), "method": "rk4", "step_s": 0.001,
        "index": 52, "time_s": 0.052, "source": template_source,
        "b3_dissipation_J": fixed_dissipation,
        "criteria": {"soft_capture_transient_qualifies": True},
    }
    acquisition_template = {
        "run_id": lane.lower(), "acquisition_time_s": 0.052,
        "reference_length_m": 0.04,
        "energy_audit": {"D_B3_minus_J": fixed_dissipation},
    }
    event = {
        **event_template, "run_id": case_id,
        "source": "INDEPENDENT_B3_RERUN_FIRST_QUALIFYING_SAMPLE",
        "b3_dissipation_J": fresh_dissipation,
    }
    acquisition = copy.deepcopy(acquisition_template)
    acquisition["run_id"] = case_id
    acquisition["energy_audit"]["D_B3_minus_J"] = fresh_dissipation
    payload = {
        "lane_id": lane, "case_id": case_id,
        "event": event, "acquisition": acquisition,
    }
    metadata = {
        "lane_id": lane, "case_id": case_id, "acquisition": acquisition,
        "event_provenance": {
            "first_qualifying_event_index": 52,
            "acquisition_time_s": 0.052,
            "acquisition_certificate_payload": payload,
            "acquisition_certificate_sha256": canonical_sha256(payload),
        },
    }
    clean = ValidationReport(mode="campaign")
    validator._validate_acquisition_provenance(
        clean, metadata=metadata,
        event_templates={lane: event_template},
        acquisition_templates={lane: acquisition_template},
    )
    assert clean.passed, clean.failures

    two_ulp = float(np.nextafter(fresh_dissipation, math.inf))
    internally_split = copy.deepcopy(metadata)
    split_payload = internally_split["event_provenance"]["acquisition_certificate_payload"]
    split_payload["acquisition"]["energy_audit"]["D_B3_minus_J"] = two_ulp
    internally_split["acquisition"] = copy.deepcopy(split_payload["acquisition"])
    internally_split["event_provenance"]["acquisition_certificate_sha256"] = canonical_sha256(split_payload)
    split_report = ValidationReport(mode="campaign")
    validator._validate_acquisition_provenance(
        split_report, metadata=internally_split,
        event_templates={lane: event_template},
        acquisition_templates={lane: acquisition_template},
    )
    assert not split_report.passed
    assert "CASE_FRESH_DISSIPATION_INTERNAL_NOT_BIT_EXACT" in {
        row["code"] for row in split_report.failures
    }

    extra_pointer = copy.deepcopy(metadata)
    extra_payload = extra_pointer["event_provenance"]["acquisition_certificate_payload"]
    extra_payload["acquisition"]["reference_length_m"] = 0.4
    extra_pointer["acquisition"] = copy.deepcopy(extra_payload["acquisition"])
    extra_pointer["event_provenance"]["acquisition_certificate_sha256"] = canonical_sha256(extra_payload)
    rejected = ValidationReport(mode="campaign")
    validator._validate_acquisition_provenance(
        rejected, metadata=extra_pointer,
        event_templates={lane: event_template},
        acquisition_templates={lane: acquisition_template},
    )
    assert not rejected.passed
    assert "CASE_FRESH_CERTIFICATE_NONALLOWLIST_DRIFT" in {
        row["code"] for row in rejected.failures
    }

    three_ulp = fixed_dissipation
    for _ in range(3):
        three_ulp = float(np.nextafter(three_ulp, math.inf))
    over = copy.deepcopy(metadata)
    over_payload = over["event_provenance"]["acquisition_certificate_payload"]
    over_payload["event"]["b3_dissipation_J"] = three_ulp
    over_payload["acquisition"]["energy_audit"]["D_B3_minus_J"] = three_ulp
    over["acquisition"] = copy.deepcopy(over_payload["acquisition"])
    over["event_provenance"]["acquisition_certificate_sha256"] = canonical_sha256(over_payload)
    rejected_ulp = ValidationReport(mode="campaign")
    validator._validate_acquisition_provenance(
        rejected_ulp, metadata=over,
        event_templates={lane: event_template},
        acquisition_templates={lane: acquisition_template},
    )
    assert not rejected_ulp.passed
    assert "CASE_FRESH_DISSIPATION_EXCEEDS_2_ULP" in {
        row["code"] for row in rejected_ulp.failures
    }


def test_actual_six_lane_fixed_sources_accept_one_ulp_fresh_certificates() -> None:
    load_report = ValidationReport(mode="campaign")
    events, acquisitions, _traces = validator._load_b4e_provenance_templates(
        load_report,
    )
    assert load_report.passed, load_report.failures
    for lane in validator.LANES:
        case_id = f"A0_PARENT_{lane}"
        event = copy.deepcopy(events[lane])
        acquisition = copy.deepcopy(acquisitions[lane])
        event["run_id"] = case_id
        acquisition["run_id"] = case_id
        event["source"] = validator.FRESH_B3_EVENT_SOURCE
        fixed_d = float(events[lane]["b3_dissipation_J"])
        fresh_d = float(np.nextafter(fixed_d, math.inf))
        event["b3_dissipation_J"] = fresh_d
        acquisition["energy_audit"]["D_B3_minus_J"] = fresh_d
        payload = {
            "lane_id": lane, "case_id": case_id,
            "event": event, "acquisition": acquisition,
        }
        report = ValidationReport(mode="campaign")
        audit = validator._validate_fresh_certificate_template_comparison(
            report,
            payload=payload,
            lane=lane,
            case_id=case_id,
            event_templates=events,
            acquisition_templates=acquisitions,
            code_prefix="A0_PARENT",
        )
        assert report.passed, (lane, report.failures)
        assert audit is not None and audit["passed"] is True
        assert audit["dissipation_comparisons"]["event"]["ulp_distance"] == 1
        assert audit["dissipation_comparisons"]["acquisition"]["ulp_distance"] == 1


def test_command_mutation_replay_binds_full_frozen_slot_and_qref() -> None:
    schedule = validator.read_json_strict(
        validator.CONTRACT_ROOT / validator.CONTRACT_FILES["schedule"][0]
    )
    reference = validator.read_json_strict(
        validator.CONTRACT_ROOT / validator.CONTRACT_FILES["reference"][0]
    )
    slot = next(
        row for row in schedule["slots"]
        if row["case_id"] == "RK4_REFERENCE__A0__PRE"
    )
    command = {
        "left": {"alpha": 0.0, "delay_s": 0.0, "duration_s": 0.0},
        "right": {"alpha": 0.0, "delay_s": 0.0, "duration_s": 0.0},
    }
    payload = {
        "arm": "A0", "slot": slot, "acquisition_time_s": 0.052,
        "sample_time_s": 0.052,
        "Q_ref_N": reference["individual_finger_reference_force_N"],
        "command_parameters": command,
        "observed_Q_14": [0.0] * 14,
        "clearance_dwell_active": False,
        "trace_origin": "REGISTERED_CAMPAIGN_CASE",
        "harness_id": None,
        "harness_command": None,
    }
    kwargs = {
        "frozen_schedule": schedule,
        "frozen_q_ref": reference["individual_finger_reference_force_N"],
        "mutation_spec": validator.read_json_strict(
            validator.CONTRACT_ROOT / validator.CONTRACT_FILES["mutations"][0]
        ),
        "required_false": {}, "required_null_names": (),
        "project_root": validator.PROJECT_ROOT, "phase_root": validator.PHASE_ROOT,
    }
    assert evaluate_payload(
        "COMMAND_TRACE", "B4F-G02-A0-EXACT-REPLAY", payload,
        parent_id="B4FNC02", **kwargs,
    )
    coordinated = copy.deepcopy(payload)
    coordinated["slot"]["step_s"] = 0.002
    assert not evaluate_payload(
        "COMMAND_TRACE", "B4F-G02-A0-EXACT-REPLAY", coordinated,
        parent_id="B4FNC02", **kwargs,
    )
    coordinated = copy.deepcopy(payload)
    coordinated["Q_ref_N"] *= 2.0
    assert not evaluate_payload(
        "COMMAND_TRACE", "B4F-G02-A0-EXACT-REPLAY", coordinated,
        parent_id="B4FNC02", **kwargs,
    )


def test_selector_mutation_replay_requires_global_unreachability_false() -> None:
    report_payload = {
        "reported_label": "lowest_tested_reachable_alpha_in_registered_discrete_grid",
        "minimum_required_force_or_work_claimed": False,
        "continuous_threshold_or_interpolation_claimed": False,
        "global_unreachability_claimed": False,
    }
    kwargs = {
        "frozen_schedule": {}, "frozen_q_ref": 1.0, "mutation_spec": {},
        "required_false": {}, "required_null_names": (),
        "project_root": validator.PROJECT_ROOT, "phase_root": validator.PHASE_ROOT,
    }
    assert evaluate_payload(
        "SELECTOR_REPORT", "B4F-G17-DISCRETE-GRID-REPORTING-BOUNDARY",
        {"report": report_payload}, parent_id="B4FNC22", **kwargs,
    )
    report_payload["global_unreachability_claimed"] = True
    assert not evaluate_payload(
        "SELECTOR_REPORT", "B4F-G17-DISCRETE-GRID-REPORTING-BOUNDARY",
        {"report": report_payload}, parent_id="B4FNC22", **kwargs,
    )


def test_mutation_patch_target_is_independently_rebuilt_from_parent_and_index() -> None:
    spec = validator.read_json_strict(
        validator.CONTRACT_ROOT / validator.CONTRACT_FILES["mutations"][0]
    )
    expected = "/payload/observed_Q_14/4"
    assert expected_patch_target("B4FNC03", 5, spec) == expected
    patch = {"target": expected, "operations": [{"op": "replace", "path": expected, "value": 0.0245423356892756}]}
    assert validate_patch_semantics(
        parent_id="B4FNC03", subvariant_index=5, target=expected,
        patch=patch, base_payload={}, mutation_spec=spec,
        frozen_q_ref=0.0245423356892756,
    )
    patch["operations"][0]["path"] = "/payload/observed_Q_14/5"
    assert not validate_patch_semantics(
        parent_id="B4FNC03", subvariant_index=5, target=expected,
        patch=patch, base_payload={}, mutation_spec=spec,
        frozen_q_ref=0.0245423356892756,
    )


def test_nc08_only_accepts_exact_frozen_finite_harness_and_zero_dwell_command() -> None:
    schedule = validator.read_json_strict(
        validator.CONTRACT_ROOT / validator.CONTRACT_FILES["schedule"][0]
    )
    reference = validator.read_json_strict(
        validator.CONTRACT_ROOT / validator.CONTRACT_FILES["reference"][0]
    )
    spec = validator.read_json_strict(
        validator.CONTRACT_ROOT / validator.CONTRACT_FILES["mutations"][0]
    )
    targets = spec["deterministic_targets_and_amplitudes"]
    finite = spec["finite_event_harness"]
    slot = next(row for row in schedule["slots"] if row["case_id"] == targets["default_registered_forced_slot"])
    force = finite["force_pulse"]
    command = {
        "left": {"alpha": force["alpha_left"], "delay_s": 0.0, "duration_s": force["T_cmd_s"]},
        "right": {"alpha": force["alpha_right"], "delay_s": 0.0, "duration_s": force["T_cmd_s"]},
    }
    payload = {
        "arm": "A1", "slot": slot, "acquisition_time_s": 0.052,
        "sample_time_s": 0.054,
        "Q_ref_N": reference["individual_finger_reference_force_N"],
        "command_parameters": command, "observed_Q_14": [0.0] * 14,
        "clearance_dwell_active": True,
        "trace_origin": "FROZEN_FINITE_EVENT_HARNESS",
        "harness_id": finite["id"],
        "harness_command": {"force_pulse": force, "dwell_hold_N": {"left": 0.0, "right": 0.0}},
    }
    kwargs = {
        "parent_id": "B4FNC08", "frozen_schedule": schedule,
        "frozen_q_ref": reference["individual_finger_reference_force_N"],
        "mutation_spec": spec, "required_false": {}, "required_null_names": (),
        "project_root": validator.PROJECT_ROOT, "phase_root": validator.PHASE_ROOT,
    }
    assert evaluate_payload(
        "COMMAND_TRACE", "B4F-G08-COMMAND-ZERO-BEFORE-REMOVAL", payload, **kwargs,
    )
    mutant = copy.deepcopy(payload)
    qref = reference["individual_finger_reference_force_N"]
    mutant["observed_Q_14"][12] = qref
    mutant["harness_command"]["dwell_hold_N"]["left"] = qref
    assert not evaluate_payload(
        "COMMAND_TRACE", "B4F-G08-COMMAND-ZERO-BEFORE-REMOVAL", mutant, **kwargs,
    )


def test_all_65_frozen_subvariant_patch_targets_are_independently_resolvable() -> None:
    spec = validator.read_json_strict(
        validator.CONTRACT_ROOT / validator.CONTRACT_FILES["mutations"][0]
    )
    identities = []
    for variant in spec["variants"]:
        parent = variant["id"].split("_", 1)[0]
        for subvariant in range(1, int(variant["count"]) + 1):
            target = expected_patch_target(parent, subvariant, spec)
            assert target is not None, (parent, subvariant)
            identities.append((parent, subvariant, repr(target)))
    assert len(identities) == 65
    assert len(set(identities)) == 65


def test_clearance_mutation_replay_locks_history_to_frozen_fixture() -> None:
    spec = validator.read_json_strict(
        validator.CONTRACT_ROOT / validator.CONTRACT_FILES["mutations"][0]
    )
    fixture = spec["deterministic_targets_and_amplitudes"]["single_side_classifier_fixture"]["canonical_payload"]
    payload = {
        **copy.deepcopy(fixture),
        "ledger_interval_certified": [True] * (len(fixture["time_s"]) - 1),
        "observed_finite_event": False,
        "classifier_mode": "BILATERAL_HERMITE_ALL_ROOT_EARLIEST_DWELL",
    }
    kwargs = {
        "parent_id": "B4FNC09", "frozen_schedule": {}, "frozen_q_ref": 1.0,
        "mutation_spec": spec, "required_false": {}, "required_null_names": (),
        "project_root": validator.PROJECT_ROOT, "phase_root": validator.PHASE_ROOT,
    }
    assert evaluate_payload(
        "CLEARANCE_TRACE", "B4F-G09-CONTINUOUS-BILATERAL-CLEARANCE",
        payload, **kwargs,
    )
    coordinated = copy.deepcopy(payload)
    coordinated["time_s"][1] += 1.0e-5
    assert not evaluate_payload(
        "CLEARANCE_TRACE", "B4F-G09-CONTINUOUS-BILATERAL-CLEARANCE",
        coordinated, **kwargs,
    )
