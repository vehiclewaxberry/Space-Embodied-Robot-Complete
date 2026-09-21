"""Independent raw-array recomputation of B4G G03-G11 and G16.

This module evaluates a hash-bound *technical fixture* only.  A true predicate
therefore proves the backend can discriminate its contract; it never promotes
the source-freeze package to a numerical run or scientific result.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np

from .clearance import ClearanceError, certify_clearance_independent
from .context import BoundIntegrityContext
from .source_api import (
    REFERENCE_Q_PER_FINGER_N,
    SourceAPIError,
    load_geometry_module,
    load_raw_modules,
    load_reference_force,
    verify_source_bindings,
)


G03 = "B4F-G03-P-ONLY-INTERNAL-GENERALIZED-FORCE"
G04 = "B4F-G04-ACTUATOR-WORK-LEDGER"
G05 = "B4F-G05-P-H-CONSERVATION"
G06 = "B4F-G06-ENERGY-MINUS-WORK-IDENTITY"
G07 = "B4F-G07-CONTACT-CONSTRAINT-MUTUAL-EXCLUSION"
G08 = "B4F-G08-COMMAND-ZERO-BEFORE-REMOVAL"
G09 = "B4F-G09-CONTINUOUS-BILATERAL-CLEARANCE"
G10 = "B4F-G10-EXACT-ZERO-JUMP-REMOVAL"
G11 = "B4F-G11-INDEPENDENT-POST-RELEASE-5MS"
G16 = "B4F-G16-SYNTHETIC-GEOMETRY-DOMAIN"
REQUIRED_GATES = (G03, G04, G05, G06, G07, G08, G09, G10, G11, G16)


class IntegrityError(ValueError):
    pass


def _maximum_abs(value: np.ndarray) -> float:
    return float(np.max(np.abs(value))) if value.size else math.inf


def _vector_drift(value: np.ndarray) -> float:
    if len(value) == 0:
        return math.inf
    return float(np.max(np.linalg.norm(value - value[0], axis=1)))


def _profile(times: np.ndarray, acquisition: float, alpha: float, duration: float) -> np.ndarray:
    result = np.zeros_like(times, dtype="<f8")
    if duration <= 0.0 or alpha == 0.0:
        return result
    interior = (times > acquisition) & (times < acquisition + duration)
    result[interior] = (
        alpha * REFERENCE_Q_PER_FINGER_N
        * np.sin(np.pi * (times[interior] - acquisition) / duration) ** 2
    )
    return result


def _gate(predicate: bool, detail: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "evaluation_status": "PASS" if predicate else "FAIL",
        "scientific_predicate": bool(predicate),
        "detail": dict(detail),
    }


def _g04_g06(case: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    modules = load_raw_modules()
    work_energy = modules["production_api"].load_production_modules()["work_energy"]
    finite = case.sidecar["outcome"] == "FINITE_BILATERAL_REMOVAL_OBSERVED"
    inputs = {
        "time_s": case.arrays["time_s"].tolist(),
        "command_Q_14": case.arrays["command_Q_14"].tolist(),
        "service_state_29": case.arrays["service_state_29"].tolist(),
        "sample_power_reported_W": case.arrays["sample_power_reported_W"].tolist(),
        "stage_command_Q_14": case.arrays["stage_command_Q_14"].tolist(),
        "stage_service_state_29": case.arrays["stage_service_state_29"].tolist(),
        "stage_power_reported_W": case.arrays["stage_power_W"].tolist(),
        "W_act_J": case.arrays["signed_W_act_J"].tolist(),
        "finite_removal_present": finite,
        "post_W_act_J": case.arrays["post_signed_W_act_J"].tolist(),
        "post_actuator_work_reset_on_removal": False,
        "post_generalized_force_Q_14": case.arrays["post_command_Q_14"].tolist(),
    }
    g04 = work_energy.evaluate_g04(**inputs)
    g06, _ = modules["adapter"]._evaluate_g06_actual_dt(case)
    return g04, g06


def _geometry_replay(case: Any, context: BoundIntegrityContext) -> dict[str, Any]:
    geometry = load_geometry_module()
    arrays = case.arrays
    snapshot = context.snapshot
    active_target_error = 0.0
    active_gap_error = 0.0
    active_rate_error = 0.0
    for index, service in enumerate(arrays["service_state_29"]):
        target = geometry.reconstruct_active_target_state_13(service, snapshot)
        observation = geometry.recompute_gap_rate(service, target)
        active_target_error = max(active_target_error, _maximum_abs(target - arrays["target_state_13"][index]))
        active_gap_error = max(active_gap_error, _maximum_abs(observation.gaps_m - np.asarray((arrays["left_gap_m"][index], arrays["right_gap_m"][index]))))
        active_rate_error = max(active_rate_error, _maximum_abs(observation.gap_rates_m_s - np.asarray((arrays["left_gap_rate_m_s"][index], arrays["right_gap_rate_m_s"][index]))))

    active_stage_p_error = 0.0
    active_stage_jacobian_error = 0.0
    active_signs = True
    for index, service in enumerate(arrays["stage_service_state_29"]):
        replay = geometry.centered_gap_jacobian(service, snapshot=snapshot)
        active_stage_p_error = max(active_stage_p_error, _maximum_abs(replay.p_coordinates_m - arrays["stage_P_coordinates_m"][index]))
        active_stage_jacobian_error = max(active_stage_jacobian_error, _maximum_abs(replay.raw_gap_jacobian_p - arrays["stage_gap_jacobian_P"][index]))
        active_signs &= replay.opening_signs == (1, 1)

    service = arrays["service_state_29"]
    stage_service = arrays["stage_service_state_29"]
    target = arrays["target_state_13"]
    active_quaternion_error = max(
        _maximum_abs(np.linalg.norm(service[:, 3:7], axis=1) - 1.0),
        _maximum_abs(np.linalg.norm(target[:, 3:7], axis=1) - 1.0),
        _maximum_abs(np.linalg.norm(stage_service[:, 3:7], axis=1) - 1.0),
    )
    sample_domain = bool(np.all((service[:, 13:15] >= 0.0) & (service[:, 13:15] <= 0.0715)))
    stage_p = arrays["stage_P_coordinates_m"]
    stage_domain = bool(np.all((stage_p - 1.0e-7 >= 0.0) & (stage_p + 1.0e-7 <= 0.0715)))
    active_pass = bool(
        sample_domain and stage_domain
        and np.array_equal(stage_p, stage_service[:, 13:15])
        and np.all(arrays["stage_domain_and_sign_pass"])
        and active_quaternion_error <= 1.0e-12
        and active_target_error <= 1.0e-12
        and active_gap_error <= 1.0e-12
        and active_rate_error <= 1.0e-12
        and active_stage_p_error <= 1.0e-15
        and active_stage_jacobian_error <= 1.0e-12
        and active_signs
    )

    post_gap_error = 0.0
    post_rate_error = 0.0
    for index, (post_service, post_target) in enumerate(zip(arrays["post_service_state_29"], arrays["post_target_state_13"])):
        observation = geometry.recompute_gap_rate(post_service, post_target)
        post_gap_error = max(post_gap_error, _maximum_abs(observation.gaps_m - np.asarray((arrays["post_left_gap_m"][index], arrays["post_right_gap_m"][index]))))
        post_rate_error = max(post_rate_error, _maximum_abs(observation.gap_rates_m_s - np.asarray((arrays["post_left_gap_rate_m_s"][index], arrays["post_right_gap_rate_m_s"][index]))))

    post_stage_p_error = 0.0
    post_stage_jacobian_error = 0.0
    post_signs = True
    for index, (post_service, post_target) in enumerate(zip(arrays["post_stage_service_state_29"], arrays["post_stage_target_state_13"])):
        replay = geometry.centered_gap_jacobian(post_service, independent_target_state_13=post_target)
        post_stage_p_error = max(post_stage_p_error, _maximum_abs(replay.p_coordinates_m - arrays["post_stage_P_coordinates_m"][index]))
        post_stage_jacobian_error = max(post_stage_jacobian_error, _maximum_abs(replay.raw_gap_jacobian_p - arrays["post_stage_gap_jacobian_P"][index]))
        post_signs &= replay.opening_signs == (1, 1)

    post_service = arrays["post_service_state_29"]
    post_target = arrays["post_target_state_13"]
    post_stage_service = arrays["post_stage_service_state_29"]
    post_stage_target = arrays["post_stage_target_state_13"]
    post_quaternion_error = max(
        _maximum_abs(np.linalg.norm(post_service[:, 3:7], axis=1) - 1.0),
        _maximum_abs(np.linalg.norm(post_target[:, 3:7], axis=1) - 1.0),
        _maximum_abs(np.linalg.norm(post_stage_service[:, 3:7], axis=1) - 1.0),
        _maximum_abs(np.linalg.norm(post_stage_target[:, 3:7], axis=1) - 1.0),
    )
    post_stage_p = arrays["post_stage_P_coordinates_m"]
    post_pass = bool(
        np.all((post_service[:, 13:15] >= 0.0) & (post_service[:, 13:15] <= 0.0715))
        and np.all((post_stage_p - 1.0e-7 >= 0.0) & (post_stage_p + 1.0e-7 <= 0.0715))
        and np.array_equal(post_stage_p, post_stage_service[:, 13:15])
        and np.all(arrays["post_stage_domain_and_sign_pass"])
        and post_quaternion_error <= 1.0e-12
        and post_gap_error <= 1.0e-12
        and post_rate_error <= 1.0e-12
        and post_stage_p_error <= 1.0e-15
        and post_stage_jacobian_error <= 1.0e-12
        and post_signs
    )
    return {
        "active_pass": active_pass,
        "post_pass": post_pass,
        "active_target_state_max_abs_error": active_target_error,
        "active_gap_max_abs_error_m": active_gap_error,
        "active_gap_rate_max_abs_error_m_s": active_rate_error,
        "active_stage_P_max_abs_error_m": active_stage_p_error,
        "active_stage_gap_jacobian_max_abs_error": active_stage_jacobian_error,
        "active_stage_opening_signs_all_registered": bool(active_signs),
        "active_quaternion_norm_max_abs_error": active_quaternion_error,
        "post_gap_max_abs_error_m": post_gap_error,
        "post_gap_rate_max_abs_error_m_s": post_rate_error,
        "post_stage_P_max_abs_error_m": post_stage_p_error,
        "post_stage_gap_jacobian_max_abs_error": post_stage_jacobian_error,
        "post_stage_opening_signs_all_registered": bool(post_signs),
        "post_quaternion_norm_max_abs_error": post_quaternion_error,
    }


def _evaluate_parent_trace(case: Any, context: BoundIntegrityContext) -> dict[str, Any]:
    arrays = case.arrays
    parent = context.parent_trace
    removal_index = int(arrays["bilateral_removal_active_sample_index"][0])
    active_mapping = np.concatenate((
        arrays["service_state_29"][removal_index, 15:29],
        arrays["target_state_13"][removal_index, 7:13],
    ))
    parent_mapping = np.asarray(parent["mapping_z_before_20"], dtype="<f8")
    parent_terminal_service = np.asarray(parent["terminal_service_state_29"], dtype="<f8")
    parent_terminal_target = np.asarray(parent["terminal_target_state_13"], dtype="<f8")
    mapping_active_error = _maximum_abs(parent_mapping - active_mapping)
    terminal_service_error = _maximum_abs(parent_terminal_service - arrays["post_service_state_29"][-1])
    terminal_target_error = _maximum_abs(parent_terminal_target - arrays["post_target_state_13"][-1])
    expected_sources = [dict(item) for item in load_geometry_module().validate_frozen_source_bindings()]
    observed_sources = [dict(item) for item in parent["parent_source_bindings"]]
    sources_exact = observed_sources == expected_sources
    passed = bool(
        parent["post_release_passed"] is True and sources_exact
        and mapping_active_error <= 1.0e-12
        and terminal_service_error <= 1.0e-12
        and terminal_target_error <= 1.0e-12
    )
    return {
        "passed": passed,
        "producer_id": parent["producer_id"],
        "parent_source_execution_credit": False,
        "parent_source_bindings_exact": sources_exact,
        "parent_post_release_passed": parent["post_release_passed"],
        "mapping_z_before_to_active_terminal_max_abs_error": mapping_active_error,
        "terminal_service_state_max_abs_error": terminal_service_error,
        "terminal_target_state_max_abs_error": terminal_target_error,
        "parent_terminal_status": parent["terminal_status"],
    }


def evaluate_full_raw_integrity(case: Any, context: BoundIntegrityContext) -> dict[str, Any]:
    if context.payload["raw_binding"] != case.raw_binding():
        raise IntegrityError("CONTEXT_RAW_BINDING_CHANGED_AFTER_LOAD")
    if case.sidecar["execution_family"] != "FRESH" or case.sidecar["outcome"] != "FINITE_BILATERAL_REMOVAL_OBSERVED":
        raise IntegrityError("FINITE_FRESH_RAW_CASE_REQUIRED")
    try:
        source_report = verify_source_bindings()
        reference_force = load_reference_force()
        geometry_report = _geometry_replay(case, context)
        g04_detail, g06_detail = _g04_g06(case)
    except (SourceAPIError, ClearanceError, ValueError, KeyError, TypeError) as exc:
        raise IntegrityError(f"SOURCE_OR_RAW_RECOMPUTATION_FAILED:{type(exc).__name__}:{exc}") from exc

    arrays = case.arrays
    g03_pass = bool(
        np.all(arrays["command_Q_14"][:, :12] == 0.0)
        and np.all(arrays["stage_command_Q_14"][:, :12] == 0.0)
    )
    g03_detail = {
        "active_non_P_max_abs": _maximum_abs(arrays["command_Q_14"][:, :12]),
        "stage_non_P_max_abs": _maximum_abs(arrays["stage_command_Q_14"][:, :12]),
        "allowed_zero_based_indices": [12, 13],
        "post_generalized_force_evaluated_under": [G04, G11],
    }

    active_linear = _vector_drift(arrays["total_linear_momentum_N_s"])
    active_angular = _vector_drift(arrays["total_angular_momentum_N_m_s"])
    post_linear = _vector_drift(arrays["post_total_linear_momentum_N_s"])
    post_angular = _vector_drift(arrays["post_total_angular_momentum_N_m_s"])
    g05_pass = bool(active_linear <= 1.0e-9 and active_angular <= 1.0e-9 and post_linear <= 1.0e-9 and post_angular <= 1.0e-9)
    g05_detail = {
        "active_linear_momentum_drift_N_s": active_linear,
        "active_angular_momentum_drift_N_m_s": active_angular,
        "post_linear_momentum_drift_N_s": post_linear,
        "post_angular_momentum_drift_N_m_s": post_angular,
        "limit_each_native_unit": 1.0e-9,
    }

    active_force = _maximum_abs(arrays["contact_force_N"])
    active_torque = _maximum_abs(arrays["contact_torque_N_m"])
    ideal_power = _maximum_abs(arrays["ideal_constraint_power_W"])
    post_force = _maximum_abs(arrays["post_contact_force_N"])
    post_torque = _maximum_abs(arrays["post_contact_torque_N_m"])
    g07_pass = bool(active_force <= 1.0e-12 and active_torque <= 1.0e-12 and post_force <= 1.0e-12 and post_torque <= 1.0e-12)
    g07_detail = {
        "active_contact_force_N": active_force,
        "active_contact_torque_N_m": active_torque,
        "post_contact_force_N": post_force,
        "post_contact_torque_N_m": post_torque,
        "ideal_constraint_power_is_shared_integrity_precondition": True,
    }

    acquisition = float(arrays["time_s"][0])
    duration = float(case.sidecar["command_duration_s"])
    alpha = float(case.sidecar["alpha"])
    expected_saved = _profile(arrays["time_s"], acquisition, alpha, duration)
    expected_stage = _profile(arrays["stage_time_s"], acquisition, alpha, duration)
    saved_left_error = _maximum_abs(arrays["command_Q_14"][:, 12] - expected_saved)
    saved_right_error = _maximum_abs(arrays["command_Q_14"][:, 13] - expected_saved)
    stage_left_error = _maximum_abs(arrays["stage_command_Q_14"][:, 12] - expected_stage)
    stage_right_error = _maximum_abs(arrays["stage_command_Q_14"][:, 13] - expected_stage)
    exact_saved_zeros = bool(np.all(arrays["command_Q_14"][expected_saved == 0.0, 12:14] == 0.0))
    exact_stage_zeros = bool(np.all(arrays["stage_command_Q_14"][expected_stage == 0.0, 12:14] == 0.0))
    g08_pass = bool(
        max(saved_left_error, saved_right_error, stage_left_error, stage_right_error) <= 2.0e-15
        and exact_saved_zeros and exact_stage_zeros
        and np.all(arrays["command_Q_14"][-1] == 0.0)
    )
    g08_detail = {
        "reference_force_N": REFERENCE_Q_PER_FINGER_N,
        "reference_force_binding": reference_force["binding"],
        "alpha": alpha,
        "duration_s": duration,
        "saved_left_max_abs_error_N": saved_left_error,
        "saved_right_max_abs_error_N": saved_right_error,
        "stage_left_max_abs_error_N": stage_left_error,
        "stage_right_max_abs_error_N": stage_right_error,
        "exact_zero_outside_and_at_endpoints": bool(exact_saved_zeros and exact_stage_zeros),
    }

    energy_residual = np.abs((arrays["total_kinetic_energy_J"] - arrays["signed_W_act_J"]) - (arrays["total_kinetic_energy_J"][0] - arrays["signed_W_act_J"][0]))
    sample_good = (
        np.all((arrays["service_state_29"][:, 13:15] >= 0.0) & (arrays["service_state_29"][:, 13:15] <= 0.0715), axis=1)
        & (np.linalg.norm(arrays["total_linear_momentum_N_s"] - arrays["total_linear_momentum_N_s"][0], axis=1) <= 1.0e-9)
        & (np.linalg.norm(arrays["total_angular_momentum_N_m_s"] - arrays["total_angular_momentum_N_m_s"][0], axis=1) <= 1.0e-9)
        & (energy_residual <= 1.0e-7)
        & (np.abs(arrays["ideal_constraint_power_W"]) <= 1.0e-10)
        & (np.abs(arrays["contact_force_N"]) <= 1.0e-12)
        & (np.abs(arrays["contact_torque_N_m"]) <= 1.0e-12)
    )
    command_end = acquisition + duration
    command_zero = np.all(arrays["command_Q_14"] == 0.0, axis=1)
    ledger = (
        arrays["active_interval_ledger_certified"]
        & sample_good[:-1] & sample_good[1:]
        & command_zero[:-1] & command_zero[1:]
        & (arrays["time_s"][:-1] >= command_end - 1.0e-12)
    )
    clearance = certify_clearance_independent(
        arrays["time_s"], arrays["left_gap_m"], arrays["right_gap_m"],
        arrays["left_gap_rate_m_s"], arrays["right_gap_rate_m_s"],
        acquisition_time_s=max(acquisition, command_end - 0.001),
        ledger_interval_certified=ledger,
    )
    raw_removal = float(arrays["bilateral_removal_event_time_s"][0])
    g09_pass = bool(
        clearance["finite_event"] is True
        and abs(float(clearance["removal_time_s"]) - raw_removal) <= 1.0e-12
        and abs(raw_removal - float(arrays["time_s"][-1])) <= 1.0e-12
        and raw_removal == case.sidecar["removal_time_s"]
        and int(arrays["bilateral_removal_active_sample_index"][0]) == len(arrays["time_s"]) - 1
        and raw_removal + 1.0e-12 >= command_end + 0.001
    )
    g09_detail = {
        "clearance": clearance,
        "raw_removal_time_s": raw_removal,
        "command_end_s": command_end,
        "ledger_certified_interval_count": int(np.count_nonzero(ledger)),
        "sidecar_outcome_used_as_oracle": False,
    }

    removal_index = int(arrays["bilateral_removal_active_sample_index"][0])
    service_jump_exact = bool(np.array_equal(arrays["post_service_state_29"][0], arrays["service_state_29"][removal_index]))
    target_jump_exact = bool(np.array_equal(arrays["post_target_state_13"][0], arrays["target_state_13"][removal_index]))
    jump_maxima = {
        "service_base_linear_m_s": _maximum_abs(arrays["post_service_state_29"][0, 15:18] - arrays["service_state_29"][removal_index, 15:18]),
        "service_base_angular_rad_s": _maximum_abs(arrays["post_service_state_29"][0, 18:21] - arrays["service_state_29"][removal_index, 18:21]),
        "service_R_joint_rad_s": _maximum_abs(arrays["post_service_state_29"][0, 21:27] - arrays["service_state_29"][removal_index, 21:27]),
        "service_P_joint_m_s": _maximum_abs(arrays["post_service_state_29"][0, 27:29] - arrays["service_state_29"][removal_index, 27:29]),
        "target_linear_m_s": _maximum_abs(arrays["post_target_state_13"][0, 7:10] - arrays["target_state_13"][removal_index, 7:10]),
        "target_angular_rad_s": _maximum_abs(arrays["post_target_state_13"][0, 10:13] - arrays["target_state_13"][removal_index, 10:13]),
    }
    linear_impulse = _maximum_abs(arrays["post_total_linear_momentum_N_s"][0] - arrays["total_linear_momentum_N_s"][removal_index])
    angular_impulse = _maximum_abs(arrays["post_total_angular_momentum_N_m_s"][0] - arrays["total_angular_momentum_N_m_s"][removal_index])
    kinetic_jump = abs(float(arrays["post_total_kinetic_energy_J"][0] - arrays["total_kinetic_energy_J"][removal_index]))
    g10_pass = bool(
        service_jump_exact and target_jump_exact
        and all(value <= 1.0e-12 for value in jump_maxima.values())
        and linear_impulse <= 1.0e-12 and angular_impulse <= 1.0e-12
        and kinetic_jump <= 1.0e-12
    )
    g10_detail = {
        "service_state_exact_mapping": service_jump_exact,
        "target_state_exact_mapping": target_jump_exact,
        "native_velocity_jump_maxima": jump_maxima,
        "linear_impulse_N_s_max_abs": linear_impulse,
        "angular_impulse_N_m_s_max_abs": angular_impulse,
        "kinetic_energy_jump_J_abs": kinetic_jump,
        "ideal_constraint_stored_energy_J": 0.0,
        "stored_energy_basis": "HASH_BOUND_IDEAL_VELOCITY_CONSTRAINT_HAS_NO_STORAGE_STATE",
    }

    post_clearance = certify_clearance_independent(
        arrays["post_time_s"], arrays["post_left_gap_m"], arrays["post_right_gap_m"],
        arrays["post_left_gap_rate_m_s"], arrays["post_right_gap_rate_m_s"],
        acquisition_time_s=float(arrays["post_time_s"][0]) - 0.001,
        ledger_interval_certified=np.ones(len(arrays["post_time_s"]) - 1, dtype=bool),
    )
    intervals = post_clearance["certified_good_intervals_s"]
    full_post_clearance = bool(
        len(intervals) == 1
        and abs(float(intervals[0][0]) - float(arrays["post_time_s"][0])) <= 1.0e-12
        and abs(float(intervals[0][1]) - float(arrays["post_time_s"][-1])) <= 1.0e-12
    )
    post_energy = _maximum_abs(arrays["post_total_kinetic_energy_J"] - arrays["post_total_kinetic_energy_J"][0])
    post_horizon = bool(
        abs(float(arrays["post_time_s"][0]) - raw_removal) <= 1.0e-12
        and abs(float(arrays["post_time_s"][-1]) - raw_removal - 0.005) <= 1.0e-12
    )
    post_step = bool(np.all(np.abs(np.diff(arrays["post_time_s"]) - case.sidecar["step_s"]) <= 1.0e-15))
    post_work = bool(
        np.all(arrays["post_signed_W_act_J"] == arrays["signed_W_act_J"][-1])
        and np.all(arrays["post_command_Q_14"] == 0.0)
    )
    parent = _evaluate_parent_trace(case, context)
    g11_pass = bool(
        post_horizon and post_step and post_linear <= 1.0e-9 and post_angular <= 1.0e-9
        and post_energy <= 1.0e-7 and post_force <= 1.0e-12
        and post_torque <= 1.0e-12 and full_post_clearance and post_work
        and geometry_report["post_pass"] and parent["passed"]
    )
    g11_detail = {
        "post_5ms_horizon_exact": post_horizon,
        "post_saved_step_matches_lane": post_step,
        "linear_momentum_drift_N_s": post_linear,
        "angular_momentum_drift_N_m_s": post_angular,
        "energy_drift_J": post_energy,
        "contact_force_N": post_force,
        "contact_torque_N_m": post_torque,
        "full_continuous_clearance": full_post_clearance,
        "work_carried_and_generalized_force_zero": post_work,
        "post_geometry_replay_pass": geometry_report["post_pass"],
        "parent_trace_crosscheck": parent,
    }

    g16_pass = bool(geometry_report["active_pass"] and geometry_report["post_pass"])
    gates = {
        G03: _gate(g03_pass, g03_detail),
        G04: _gate(bool(g04_detail["scientific_predicate"]), g04_detail),
        G05: _gate(g05_pass, g05_detail),
        G06: _gate(bool(g06_detail["scientific_predicate"]), g06_detail),
        G07: _gate(g07_pass, g07_detail),
        G08: _gate(g08_pass, g08_detail),
        G09: _gate(g09_pass, g09_detail),
        G10: _gate(g10_pass, g10_detail),
        G11: _gate(g11_pass, g11_detail),
        G16: _gate(g16_pass, geometry_report),
    }
    shared_integrity_preconditions = {
        "active_ideal_constraint_power_max_abs_W": ideal_power,
        "active_ideal_constraint_power_limit_W": 1.0e-10,
        "active_ideal_constraint_power_pass": ideal_power <= 1.0e-10,
        "all_active_sample_ledger_predicates_pass": bool(np.all(sample_good)),
    }
    technical_pass = bool(
        source_report["passed"]
        and context.execution_credit_allowed is False
        and shared_integrity_preconditions["active_ideal_constraint_power_pass"]
        and shared_integrity_preconditions["all_active_sample_ledger_predicates_pass"]
        and all(gates[gate_id]["scientific_predicate"] is True for gate_id in REQUIRED_GATES)
    )
    return {
        "schema": "SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_RECOMPUTATION_V1",
        "passed": False,
        "status": (
            "HOLD_SOURCE_ONLY_TECHNICAL_FIXTURE_ALL_RAW_PREDICATES_TRUE_NO_EXECUTION_CREDIT"
            if technical_pass else
            "HOLD_SOURCE_ONLY_TECHNICAL_FIXTURE_RAW_PREDICATE_FAILURE_NO_EXECUTION_CREDIT"
        ),
        "case_id": case.sidecar["case_id"],
        "raw_binding": case.raw_binding(),
        "context_binding": {
            "path": context.relative_path,
            "bytes": context.byte_count,
            "sha256": context.sha256,
        },
        "source_bindings": source_report,
        "required_gate_ids": list(REQUIRED_GATES),
        "gate_records": gates,
        "shared_integrity_preconditions": shared_integrity_preconditions,
        "full_gate_set_recomputed": True,
        "technical_fixture_full_raw_integrity_predicate_pass": technical_pass,
        "actual_case_full_raw_integrity_recomputed": False,
        "source_only_candidate_predicate_pass": False,
        "trajectory_count": 0,
        "r2_numerical_preflight_executed": False,
        "current_system_bound": False,
        "formal_nc19_credit": False,
        "scientific_credit": False,
        "owner_authorized": False,
        "production_credit": False,
        "release_authorized": False,
        "next_stage_authorized": False,
    }


__all__ = [
    "G03", "G04", "G05", "G06", "G07", "G08", "G09", "G10",
    "G11", "G16", "IntegrityError", "REQUIRED_GATES",
    "evaluate_full_raw_integrity",
]
