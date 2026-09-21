from __future__ import annotations

import copy
import hashlib
import json
import math

import numpy as np
import pytest

import b4g_solver as solver
from b4g_solver import forced_retraction as forced


def _canonical_sha(value) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


@pytest.fixture(scope="module")
def reference_state():
    model = forced.b4e.BranchedGripperServiceModel()
    event = forced.b4e.extract_frozen_primary_event()
    acquisition = forced.b4e.acquisition_projection(model, event)
    service = forced.b4e.ServiceState(
        event.service.base_position_inertial_m.copy(),
        event.service.base_quaternion_body_to_inertial_wxyz.copy(),
        event.service.joint_coordinates_mixed.copy(),
        acquisition.eta_plus.copy(),
    )
    state_30 = np.concatenate((
        forced.b4e._service_to_active_vector(service),
        np.zeros(1, dtype=float),
    ))
    return model, event, acquisition, service, state_30


def test_public_solver_constants_match_frozen_contract(contracts):
    state = contracts["run_spec"]["active_state_and_stages"]
    assert solver.P_DOMAIN_M == tuple(tuple(row) for row in state["P_coordinate_m_closed_interval_left_right"])
    assert solver.CENTERED_SIGN_STEP_M == state["centered_sign_step_m"]
    assert solver.REFERENCE_FORCE_N == contracts["reference_force"][
        "individual_finger_reference_force_N"
    ]
    assert solver.REGISTERED_OPENING_SIGNS == tuple(
        contracts["reference_force"]["registered_and_recomputed_opening_sign_left_right"]
    )
    assert solver.ACTIVE_DURATION_S == contracts["run_spec"]["time_semantics"][
        "active_duration_after_each_acquisition_s"
    ]


@pytest.mark.parametrize("elapsed", [-1.0, -1e-15, 0.0, 0.01, 0.0100000000001, 1.0])
def test_sin_squared_profile_is_exact_zero_at_and_outside_endpoints(elapsed):
    assert solver.sin2_profile_exact(elapsed, 0.01) == 0.0


def test_sin_squared_profile_has_registered_interior_shape():
    assert solver.sin2_profile_exact(0.005, 0.01) == pytest.approx(1.0, abs=0.0)
    quarter = solver.sin2_profile_exact(0.0025, 0.01)
    assert quarter == pytest.approx(0.5, abs=2e-16)
    assert solver.sin2_profile_exact(0.0, 0.0) == 0.0


@pytest.mark.parametrize("elapsed,duration", [(0.1, -0.1), (math.nan, 0.1), (0.1, math.nan)])
def test_sin_squared_profile_rejects_invalid_numeric_inputs(elapsed, duration):
    with pytest.raises(solver.ForcedRetractionError):
        solver.sin2_profile_exact(elapsed, duration)


@pytest.mark.parametrize(
    "values",
    [(-1.0, 0.0, 0.01), (1.0, -0.001, 0.01), (1.0, 0.0, -0.01), (math.nan, 0.0, 0.01)],
)
def test_command_arm_rejects_negative_or_nonfinite_parameters(values):
    with pytest.raises(solver.ForcedRetractionError):
        solver.CommandArm(*values)


def test_force_vector_is_p_only_and_exact_zero_at_support_endpoints(contracts):
    q_ref = contracts["reference_force"]["individual_finger_reference_force_N"]
    acquisition = 0.05125
    arm = solver.CommandArm(2.0, 0.0, 0.01)
    command = solver.ForcedCommand(arm, arm, "UNIT_SYMMETRIC")
    at_start = solver.force_vector(command, acquisition, acquisition, q_ref)
    at_mid = solver.force_vector(command, acquisition + 0.005, acquisition, q_ref)
    at_end = solver.force_vector(command, acquisition + 0.01, acquisition, q_ref)
    after_end = solver.force_vector(command, acquisition + 0.010001, acquisition, q_ref)
    assert np.array_equal(at_start, np.zeros(14))
    assert np.array_equal(at_end, np.zeros(14))
    assert np.array_equal(after_end, np.zeros(14))
    assert np.array_equal(at_mid[:12], np.zeros(12))
    assert at_mid[12] == pytest.approx(2.0 * q_ref, abs=1e-18)
    assert at_mid[13] == pytest.approx(2.0 * q_ref, abs=1e-18)


def test_force_vector_respects_independent_delays_and_full_durations():
    acquisition = 1.0
    command = solver.ForcedCommand(
        solver.CommandArm(1.0, 0.0, 0.01),
        solver.CommandArm(0.5, 0.005, 0.01),
        "UNIT_ASYMMETRIC",
    )
    before_right = solver.force_vector(command, 1.0025, acquisition, 2.0)
    right_mid = solver.force_vector(command, 1.010, acquisition, 2.0)
    assert before_right[12] > 0.0
    assert before_right[13] == 0.0
    assert right_mid[12] == 0.0
    assert right_mid[13] == pytest.approx(1.0, abs=1e-15)
    assert command.end_time_s(acquisition) == pytest.approx(1.015, abs=0.0)


def test_force_vector_rejects_invalid_reference_and_consumed_signs():
    command = solver.ForcedCommand(
        solver.CommandArm(1.0, 0.0, 0.01),
        solver.CommandArm(1.0, 0.0, 0.01),
    )
    with pytest.raises(solver.ForcedRetractionError):
        solver.force_vector(command, 0.005, 0.0, 0.0)
    with pytest.raises(solver.ForcedRetractionError):
        solver.force_vector(command, 0.005, 0.0, 1.0, (1, 0))


def test_raw_opening_signs_match_registered_signs_at_reference_acquisition(reference_state):
    model, _, acquisition, service, _ = reference_state
    audit = solver.opening_signs(model, service, acquisition.snapshot)
    assert audit.raw_gap_jacobian.shape == (2, 2)
    assert np.all(np.isfinite(audit.raw_gap_jacobian))
    assert np.all(audit.diagonal_derivatives > 0.0)
    assert audit.signs == solver.REGISTERED_OPENING_SIGNS == (1, 1)
    assert audit.contact_force_max_n <= 1e-12
    assert audit.contact_torque_max_n_m <= 1e-12


def test_consumed_sigma_must_equal_raw_recomputed_and_registered(reference_state):
    model, _, acquisition, _, state_30 = reference_state
    command = solver.ForcedCommand(
        solver.CommandArm(1.0, 0.0, 0.01),
        solver.CommandArm(1.0, 0.0, 0.01),
        "UNIT_SIGN_AUDIT",
    )
    audit_sink: list[dict] = []
    solver.forced_rhs(
        model,
        acquisition.snapshot,
        command,
        acquisition.acquisition_time_s,
        solver.REFERENCE_FORCE_N,
        acquisition.acquisition_time_s + 0.005,
        state_30,
        audit_sink=audit_sink,
        consumed_opening_signs=(1, 1),
    )
    assert len(audit_sink) == 1
    assert audit_sink[0]["opening_sign_left_right"] == [1, 1]
    assert audit_sink[0]["consumed_opening_sign_left_right"] == [1, 1]
    assert audit_sink[0]["consumed_sigma_equals_raw_and_registered"] is True
    with pytest.raises(solver.DomainExit) as error:
        solver.forced_rhs(
            model,
            acquisition.snapshot,
            command,
            acquisition.acquisition_time_s,
            solver.REFERENCE_FORCE_N,
            acquisition.acquisition_time_s + 0.005,
            state_30,
            consumed_opening_signs=(-1, 1),
        )
    assert error.value.reason == "CONSUMED_OPENING_SIGN_MISMATCH"
    assert error.value.record["opening_sign_left_right"] == [1, 1]
    assert error.value.record["consumed_opening_sign_left_right"] == [-1, 1]
    assert error.value.record["accepted"] is False


def test_centered_sign_audit_fails_closed_at_domain_boundary_without_clipping(reference_state):
    model, _, acquisition, service, _ = reference_state
    coordinates = service.joint_coordinates_mixed.copy()
    coordinates[6] = 0.0
    boundary = forced.b4e.ServiceState(
        service.base_position_inertial_m.copy(),
        service.base_quaternion_body_to_inertial_wxyz.copy(),
        coordinates,
        service.nu_s_mixed.copy(),
    )
    with pytest.raises(solver.DomainExit) as error:
        solver.opening_signs(model, boundary, acquisition.snapshot)
    assert error.value.reason == "CENTERED_GAP_DERIVATIVE_OUTSIDE_DOMAIN"
    assert error.value.record["P_coordinates_m_left_right"][0] == 0.0
    assert error.value.record["failed_side"] == 0


def test_forced_rhs_last_state_is_signed_q_dot_p_velocity(reference_state):
    model, _, acquisition, service, state_30 = reference_state
    command = solver.ForcedCommand(
        solver.CommandArm(2.0, 0.0, 0.01),
        solver.CommandArm(2.0, 0.0, 0.01),
        "UNIT_SIGNED_WORK",
    )
    time_s = acquisition.acquisition_time_s + 0.005
    derivative = solver.forced_rhs(
        model,
        acquisition.snapshot,
        command,
        acquisition.acquisition_time_s,
        solver.REFERENCE_FORCE_N,
        time_s,
        state_30,
    )
    generalized_force = solver.force_vector(
        command, time_s, acquisition.acquisition_time_s, solver.REFERENCE_FORCE_N
    )
    expected_power = float(generalized_force[12:14] @ service.nu_s_mixed[12:14])
    assert derivative.shape == (30,)
    assert derivative[29] == pytest.approx(expected_power, rel=0.0, abs=1e-18)
    assert derivative[29] < 0.0


def test_reference_force_recomputes_from_raw_parent_with_linear_solve(contracts):
    audit = solver.recompute_reference_force()
    registered = contracts["reference_force"]
    tolerances = registered["recomputation_absolute_tolerances"]
    assert abs(audit.symmetric_effective_mass_kg - registered["symmetric_effective_mass_kg"]) <= tolerances["effective_mass_kg"]
    assert abs(audit.reference_closing_speed_m_s - registered["reference_closing_speed_m_s"]) <= tolerances["reference_speed_m_s"]
    assert abs(audit.individual_finger_reference_force_n - registered["individual_finger_reference_force_N"]) <= tolerances["reference_force_N"]
    assert audit.opening_signs == (1, 1)
    assert audit.as_dict()["linear_solve_used"] is True
    assert audit.as_dict()["explicit_inverse_used"] is False


def test_schedule_loader_and_validator_accept_exact_frozen_schedule(contracts):
    loaded = solver.load_registered_schedule()
    assert loaded == contracts["schedule"]
    solver.validate_registered_schedule(copy.deepcopy(loaded))


def test_schedule_validator_rejects_slot_hash_drift(contracts):
    mutant = copy.deepcopy(contracts["schedule"])
    mutant["slots"][1]["alpha"] = 32.0
    with pytest.raises(solver.CampaignContractError):
        solver.validate_registered_schedule(mutant)


def test_schedule_validator_rejects_reordered_a1_even_with_new_valid_hash(contracts):
    mutant = copy.deepcopy(contracts["schedule"])
    mutant["slots"][1], mutant["slots"][2] = mutant["slots"][2], mutant["slots"][1]
    mutant["slots"][1]["slot_index"] = 1
    mutant["slots"][2]["slot_index"] = 2
    mutant["slots_sha256"] = _canonical_sha(mutant["slots"])
    with pytest.raises(solver.CampaignContractError):
        solver.validate_registered_schedule(mutant)


def test_schedule_validator_rejects_unregistered_factor_even_when_self_consistent(contracts):
    mutant = copy.deepcopy(contracts["schedule"])
    slot = mutant["slots"][1]
    slot["alpha"] = 32.0
    slot["case_id"] = f"{slot['lane_id']}__A1__ALPHA_32__TCMD_MS_5"
    slot["permutation_key_sha256"] = hashlib.sha256(
        f"20260824|{slot['lane_id']}|A1|{slot['case_id']}".encode("utf-8")
    ).hexdigest().upper()
    block = mutant["slots"][1:19]
    block.sort(key=lambda row: row["permutation_key_sha256"])
    for index, row in enumerate(block, start=1):
        row["slot_index"] = index
    mutant["slots"][1:19] = block
    mutant["slots_sha256"] = _canonical_sha(mutant["slots"])
    with pytest.raises(solver.CampaignContractError):
        solver.validate_registered_schedule(mutant)


def test_schedule_validator_rejects_declared_counts_or_lane_order_drift(contracts):
    count_mutant = copy.deepcopy(contracts["schedule"])
    count_mutant["a1_slot_count"] = 107
    with pytest.raises(solver.CampaignContractError):
        solver.validate_registered_schedule(count_mutant)
    order_mutant = copy.deepcopy(contracts["schedule"])
    order_mutant["lane_order"] = list(reversed(order_mutant["lane_order"]))
    with pytest.raises(solver.CampaignContractError):
        solver.validate_registered_schedule(order_mutant)


def test_command_mapping_rejects_unregistered_a1_or_missing_a2_parent():
    with pytest.raises(solver.CampaignContractError):
        solver.command_for_slot({
            "arm": "A1",
            "case_id": "UNIT_UNREGISTERED_A1",
            "alpha": 32.0,
            "command_duration_s": 0.005,
        })
    with pytest.raises(solver.CampaignContractError):
        solver.command_for_slot({
            "arm": "A2",
            "case_id": "UNIT_A2",
            "variant_id": "RIGHT_HALF_DELAY",
        })


@pytest.mark.parametrize(
    "variant,expected",
    [
        ("RIGHT_HALF_DELAY", ((2.0, 0.0), (1.0, 0.005))),
        ("LEFT_HALF_DELAY_MIRROR", ((1.0, 0.005), (2.0, 0.0))),
        ("RIGHT_COMMAND_OFF", ((2.0, 0.0), (0.0, 0.0))),
        ("LEFT_COMMAND_OFF_MIRROR", ((0.0, 0.0), (2.0, 0.0))),
    ],
)
def test_a2_command_mapping_keeps_full_parent_duration(variant, expected):
    command = solver.command_for_slot(
        {"arm": "A2", "case_id": f"UNIT_{variant}", "variant_id": variant},
        selected_parent={"alpha": 2.0, "command_duration_s": 0.01},
    )
    assert (command.left.alpha, command.left.delay_s) == expected[0]
    assert (command.right.alpha, command.right.delay_s) == expected[1]
    assert command.left.duration_s == command.right.duration_s == 0.01


def test_tiny_zero_input_propagation_preserves_exact_zero_force_and_work(reference_state):
    model, event, acquisition, _, _ = reference_state
    result = solver.propagate_forced_case(
        model,
        event,
        acquisition,
        solver.ForcedCommand.zero("UNIT_TINY_A0"),
        case_id="UNIT_TINY_A0",
        method="rk4",
        step_s=0.00025,
        end_time_s=acquisition.acquisition_time_s + 0.0005,
    )
    assert result.time_s.shape == (3,)
    assert result.state_30.shape == (3, 30)
    assert np.array_equal(result.applied_q_p_n, np.zeros((3, 2)))
    assert np.array_equal(result.signed_work_j, np.zeros(3))
    assert result.synthetic_removal_executed is False
    assert result.geometry_domain_pass is True


def test_tiny_forced_path_preserves_signed_work_and_passes_bounded_quadrature(reference_state):
    model, event, acquisition, _, _ = reference_state
    arm = solver.CommandArm(0.5, 0.0, 0.0005)
    result = solver.propagate_forced_case(
        model,
        event,
        acquisition,
        solver.ForcedCommand(arm, arm, "UNIT_TINY_SIGNED_WORK"),
        case_id="UNIT_TINY_SIGNED_WORK",
        method="rk4",
        step_s=0.000125,
        end_time_s=acquisition.acquisition_time_s + 0.0005,
    )
    assert result.time_s.shape == (5,)
    assert result.signed_work_j[-1] < 0.0
    assert not np.array_equal(result.signed_work_j, np.abs(result.signed_work_j))
    audit = solver.work_quadrature_audit(result)
    assert audit["augmented_signed_work_J"] == result.signed_work_j[-1]
    assert audit["native_absolute_error_limit_J"] == 1e-7
    assert audit["refinement_slack_J"] == 1e-15
    assert audit["native_absolute_error_J"] <= 1e-7
    assert audit["passed"] is True
