"""Frozen G04/G06 evaluators over supplied saved-history arrays.

These functions do not integrate a trajectory.  They independently recompute
instantaneous power in W and cumulative work in J from caller-supplied arrays.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

from .strict_json import canonical_sha256


G04_RULE_ID = "B4G_R2_G04_UNIFIED_STAGE_CUMULATIVE_TERMINAL_AND_POST_CARRY_V1"
G04_REQUIRED_FIELDS = (
    "W_act_initial_J", "sample_power_recomputed_W", "sample_power_reported_W",
    "sample_power_max_abs_error_W", "stage_power_recomputed_W", "stage_power_reported_W",
    "stage_power_max_abs_error_W", "cumulative_trapezoid_work_J", "cumulative_max_abs_error_J",
    "terminal_native_abs_error_J", "terminal_every_second_abs_error_J", "finite_removal_present",
    "active_terminal_W_act_J", "post_W_act_J", "post_actuator_work_reset_on_removal",
    "post_generalized_force_Q_14", "all_terms_finite", "scientific_predicate",
)
G04_PASS_EXPRESSION = "all_terms_finite AND W_act_initial_J==0.0 AND sample_power_max_abs_error_W<=1e-14_W_with_rtol_0 AND stage_power_max_abs_error_W<=1e-14_W_with_rtol_0 AND cumulative_max_abs_error_J<=1e-7_J AND terminal_native_abs_error_J<=1e-7_J AND (terminal_native_abs_error_J<=terminal_every_second_abs_error_J+1e-15_J OR terminal_every_second_abs_error_J<=1e-7_J) AND ((finite_removal_present==false) OR (all(post_W_act_J[j]==active_terminal_W_act_J for every saved post sample j) AND post_actuator_work_reset_on_removal==false AND all(post_generalized_force_Q_14[j,k]==0.0 for every saved post sample j and k=0..13)))"
SAMPLE_STAGE_POWER_TOLERANCE_W = 1e-14
WORK_LIMIT_J = 1e-7
REFINEMENT_SLACK_J = 1e-15
G06_LIMIT_J = 1e-7
G06_RULE_ID = "B4G_R2_G06_ENERGY_MINUS_WORK_AND_ORDER_V1"
G06_WORK_STATE_PROVENANCE = "INDEPENDENT_AUGMENTED_WORK_STATE_INTEGRATED_AT_MECHANICAL_STAGES"
G06_STAGE_EVIDENCE_KEYS = {
    "schema", "work_state_provenance", "method", "step_s", "saved_time_s", "saved_W_act_J", "stage_time_s",
    "stage_command_Q_14", "stage_service_state_29",
    "augmented_work_state_stage_values_J", "mechanical_state_stage_codes",
}
G06_REQUIRED_FIELDS = (
    "rule_id", "work_state_provenance", "stage_evidence_sha256",
    "residual_J", "active_max_abs_residual_J", "active_max_abs_limit_J",
    "stage_work_recurrence_max_abs_error_J", "stage_work_recurrence_limit_J",
    "all_terms_finite", "independent_work_state_provenance_pass",
    "scientific_predicate",
)


class WorkEnergyError(ValueError):
    pass


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _vector(value: Any, length: int, label: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != length or any(not _finite(item) for item in value):
        raise WorkEnergyError(f"FINITE_VECTOR_REQUIRED:{label}:{length}")
    return [float(item) for item in value]


def _rows(value: Any, width: int, label: str) -> list[list[float]]:
    if not isinstance(value, (list, tuple)):
        raise WorkEnergyError(f"ROWS_REQUIRED:{label}")
    return [_vector(row, width, f"{label}[{index}]") for index, row in enumerate(value)]


def recompute_power_W(command_Q_14: Sequence[Sequence[float]], service_state_29: Sequence[Sequence[float]]) -> list[float]:
    q_rows = _rows(command_Q_14, 14, "command_Q_14")
    state_rows = _rows(service_state_29, 29, "service_state_29")
    if len(q_rows) != len(state_rows):
        raise WorkEnergyError("POWER_ROW_COUNT_MISMATCH")
    return [q[12] * state[27] + q[13] * state[28] for q, state in zip(q_rows, state_rows)]


def cumulative_trapezoid_J(time_s: Sequence[float], power_W: Sequence[float]) -> list[float]:
    times = _vector(time_s, len(time_s), "time_s")
    powers = _vector(power_W, len(power_W), "power_W")
    if len(times) != len(powers) or not times:
        raise WorkEnergyError("TIME_POWER_LENGTH_MISMATCH_OR_EMPTY")
    if any(right <= left for left, right in zip(times, times[1:])):
        raise WorkEnergyError("STRICTLY_INCREASING_TIME_REQUIRED")
    result = [0.0]
    for index in range(1, len(times)):
        result.append(result[-1] + 0.5 * (powers[index - 1] + powers[index]) * (times[index] - times[index - 1]))
    return result


def runner_g04_signature() -> dict[str, Any]:
    return {"rule_id": G04_RULE_ID, "required_fields": list(G04_REQUIRED_FIELDS), "pass_expression": G04_PASS_EXPRESSION}


def _hex64(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(char in "0123456789ABCDEF" for char in value)


def evaluate_g04(
    *,
    time_s: Sequence[float],
    command_Q_14: Sequence[Sequence[float]],
    service_state_29: Sequence[Sequence[float]],
    sample_power_reported_W: Sequence[float],
    stage_command_Q_14: Sequence[Sequence[float]],
    stage_service_state_29: Sequence[Sequence[float]],
    stage_power_reported_W: Sequence[float],
    W_act_J: Sequence[float],
    finite_removal_present: bool,
    post_W_act_J: Sequence[float],
    post_actuator_work_reset_on_removal: bool,
    post_generalized_force_Q_14: Sequence[Sequence[float]],
) -> dict[str, Any]:
    sample_power = recompute_power_W(command_Q_14, service_state_29)
    stage_power = recompute_power_W(stage_command_Q_14, stage_service_state_29)
    if len(sample_power) < 2:
        raise WorkEnergyError("AT_LEAST_TWO_ACTIVE_SAMPLES_REQUIRED")
    if len(stage_power) < 1:
        raise WorkEnergyError("NONEMPTY_STAGE_HISTORY_REQUIRED")
    reported_sample = _vector(sample_power_reported_W, len(sample_power), "sample_power_reported_W")
    reported_stage = _vector(stage_power_reported_W, len(stage_power), "stage_power_reported_W")
    work = _vector(W_act_J, len(sample_power), "W_act_J")
    post_work = _vector(post_W_act_J, len(post_W_act_J), "post_W_act_J")
    post_q = _rows(post_generalized_force_Q_14, 14, "post_generalized_force_Q_14")
    if type(finite_removal_present) is not bool or type(post_actuator_work_reset_on_removal) is not bool:
        raise WorkEnergyError("REMOVAL_FLAGS_MUST_BE_BOOL")
    if len(reported_sample) != len(sample_power) or len(work) != len(sample_power):
        raise WorkEnergyError("ACTIVE_HISTORY_LENGTH_MISMATCH")
    if len(reported_stage) != len(stage_power):
        raise WorkEnergyError("STAGE_HISTORY_LENGTH_MISMATCH")
    if finite_removal_present and (not post_work or not post_q or len(post_work) != len(post_q)):
        raise WorkEnergyError("FINITE_REMOVAL_REQUIRES_NONEMPTY_ALIGNED_POST_HISTORY")
    trapezoid = cumulative_trapezoid_J(time_s, sample_power)
    sample_error = max((abs(left - right) for left, right in zip(sample_power, reported_sample)), default=0.0)
    stage_error = max((abs(left - right) for left, right in zip(stage_power, reported_stage)), default=0.0)
    cumulative_error = max(abs(left - right) for left, right in zip(trapezoid, work))
    terminal_native = abs(trapezoid[-1] - work[-1])
    indices = list(range(0, len(sample_power), 2))
    if indices[-1] != len(sample_power) - 1:
        indices.append(len(sample_power) - 1)
    sub_time = [float(time_s[index]) for index in indices]
    sub_power = [sample_power[index] for index in indices]
    terminal_every_second = abs(cumulative_trapezoid_J(sub_time, sub_power)[-1] - work[-1])
    post_carry = bool(
        (not finite_removal_present)
        or (
            all(value == work[-1] for value in post_work)
            and post_actuator_work_reset_on_removal is False
            and all(value == 0.0 for row in post_q for value in row)
        )
    )
    all_terms_finite = all(
        _finite(value)
        for values in (sample_power, reported_sample, stage_power, reported_stage, trapezoid, work, post_work)
        for value in values
    ) and all(_finite(value) for row in post_q for value in row)
    scientific_predicate = bool(
        all_terms_finite and work[0] == 0.0
        and sample_error <= SAMPLE_STAGE_POWER_TOLERANCE_W
        and stage_error <= SAMPLE_STAGE_POWER_TOLERANCE_W
        and cumulative_error <= WORK_LIMIT_J and terminal_native <= WORK_LIMIT_J
        and (terminal_native <= terminal_every_second + REFINEMENT_SLACK_J or terminal_every_second <= WORK_LIMIT_J)
        and post_carry
    )
    report = {
        "W_act_initial_J": work[0], "sample_power_recomputed_W": sample_power,
        "sample_power_reported_W": reported_sample, "sample_power_max_abs_error_W": sample_error,
        "stage_power_recomputed_W": stage_power, "stage_power_reported_W": reported_stage,
        "stage_power_max_abs_error_W": stage_error, "cumulative_trapezoid_work_J": trapezoid,
        "cumulative_max_abs_error_J": cumulative_error, "terminal_native_abs_error_J": terminal_native,
        "terminal_every_second_abs_error_J": terminal_every_second, "finite_removal_present": finite_removal_present,
        "active_terminal_W_act_J": work[-1], "post_W_act_J": post_work,
        "post_actuator_work_reset_on_removal": post_actuator_work_reset_on_removal,
        "post_generalized_force_Q_14": post_q, "all_terms_finite": all_terms_finite,
        "scientific_predicate": scientific_predicate,
    }
    if tuple(report) != G04_REQUIRED_FIELDS:
        raise WorkEnergyError("G04_REPORT_FIELD_ORDER_OR_SET_DRIFT")
    return report


def evaluate_g06(
    total_kinetic_energy_J: Sequence[float],
    signed_W_act_J: Sequence[float],
    *,
    stage_evidence_payload: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate G06 while requiring evidence of an independent work state.

    Numerical equality between ``W_act`` and ``delta T`` is not itself proof of
    an implementation shortcut: it can occur in a valid conservative sample.
    The source contract therefore binds the independently integrated augmented
    state to a 64-hex digest of the saved stage history.  The future execution
    package must produce that evidence; this source-only freeze never does so.
    """

    kinetic = _vector(total_kinetic_energy_J, len(total_kinetic_energy_J), "total_kinetic_energy_J")
    work = _vector(signed_W_act_J, len(signed_W_act_J), "signed_W_act_J")
    if len(kinetic) < 2 or len(kinetic) != len(work):
        raise WorkEnergyError("G06_HISTORY_LENGTH_MISMATCH_OR_EMPTY")
    residual = [(t - kinetic[0]) - (w - work[0]) for t, w in zip(kinetic, work)]
    maximum = max(abs(value) for value in residual)
    if not isinstance(stage_evidence_payload, dict) or set(stage_evidence_payload) != G06_STAGE_EVIDENCE_KEYS:
        raise WorkEnergyError("G06_EXACT_STAGE_EVIDENCE_SCHEMA_REQUIRED")
    saved_time = _vector(stage_evidence_payload["saved_time_s"], len(stage_evidence_payload["saved_time_s"]), "stage_evidence.saved_time_s")
    saved_work = _vector(stage_evidence_payload["saved_W_act_J"], len(stage_evidence_payload["saved_W_act_J"]), "stage_evidence.saved_W_act_J")
    stage_time = _vector(stage_evidence_payload["stage_time_s"], len(stage_evidence_payload["stage_time_s"]), "stage_evidence.stage_time_s")
    stage_q = _rows(stage_evidence_payload["stage_command_Q_14"], 14, "stage_evidence.stage_command_Q_14")
    stage_state = _rows(stage_evidence_payload["stage_service_state_29"], 29, "stage_evidence.stage_service_state_29")
    stage_work = _vector(
        stage_evidence_payload["augmented_work_state_stage_values_J"],
        len(stage_evidence_payload["augmented_work_state_stage_values_J"]),
        "stage_evidence.augmented_work_state_stage_values_J",
    )
    stage_codes = stage_evidence_payload["mechanical_state_stage_codes"]
    method = stage_evidence_payload["method"]
    step_s = stage_evidence_payload["step_s"]
    if (
        stage_evidence_payload["schema"] != "B4G_R2_G06_INDEPENDENT_STAGE_EVIDENCE_V1"
        or stage_evidence_payload["work_state_provenance"] != G06_WORK_STATE_PROVENANCE
        or method not in {"rk4", "midpoint"}
        or not _finite(step_s) or float(step_s) <= 0.0
        or not saved_time or len(saved_time) != len(kinetic) or saved_work != work
        or any(right <= left for left, right in zip(saved_time, saved_time[1:]))
        or not stage_time or len(stage_time) != len(stage_q) or len(stage_q) != len(stage_state) or len(stage_state) != len(stage_work)
        or not isinstance(stage_codes, list) or len(stage_codes) != len(stage_time)
        or any(type(code) is not str or not code for code in stage_codes)
    ):
        raise WorkEnergyError("G06_STAGE_EVIDENCE_BINDING_INVALID")
    stages_per_step = 4 if method == "rk4" else 2
    if len(stage_time) != stages_per_step * (len(saved_time) - 1):
        raise WorkEnergyError("G06_METHOD_SPECIFIC_STAGE_COUNT_INVALID")
    stage_power = recompute_power_W(stage_q, stage_state)
    recurrence_errors: list[float] = []
    expected_codes = ("RK4_K1", "RK4_K2", "RK4_K3", "RK4_K4") if method == "rk4" else ("MIDPOINT_K1", "MIDPOINT_K2")
    for index, (left, right) in enumerate(zip(saved_time, saved_time[1:])):
        h = right - left
        if h <= 0.0 or abs(h - float(step_s)) > 1e-15:
            raise WorkEnergyError("G06_SAVED_GRID_NOT_EXACT_REGISTERED_STEP")
        offset = stages_per_step * index
        powers = stage_power[offset:offset + stages_per_step]
        times = stage_time[offset:offset + stages_per_step]
        values = stage_work[offset:offset + stages_per_step]
        codes = tuple(stage_codes[offset:offset + stages_per_step])
        if method == "rk4":
            expected_times = (left, left + 0.5 * h, left + 0.5 * h, right)
            expected_stage_work = (
                saved_work[index],
                saved_work[index] + 0.5 * h * powers[0],
                saved_work[index] + 0.5 * h * powers[1],
                saved_work[index] + h * powers[2],
            )
            expected_next = saved_work[index] + h * (powers[0] + 2.0 * powers[1] + 2.0 * powers[2] + powers[3]) / 6.0
        else:
            expected_times = (left, left + 0.5 * h)
            expected_stage_work = (saved_work[index], saved_work[index] + 0.5 * h * powers[0])
            expected_next = saved_work[index] + h * powers[1]
        if codes != expected_codes or any(abs(actual - expected) > 1e-15 for actual, expected in zip(times, expected_times)):
            raise WorkEnergyError("G06_METHOD_SPECIFIC_STAGE_CODE_OR_TIME_INVALID")
        recurrence_errors.extend(abs(actual - expected) for actual, expected in zip(values, expected_stage_work))
        recurrence_errors.append(abs(saved_work[index + 1] - expected_next))
    recurrence_max = max(recurrence_errors, default=math.inf)
    recurrence_limit = 1e-14
    # Canonical hashing consumes every stage leaf and rejects null/non-finite.
    stage_evidence_sha256 = canonical_sha256(stage_evidence_payload)
    provenance_pass = _hex64(stage_evidence_sha256) and recurrence_max <= recurrence_limit
    report = {
        "rule_id": G06_RULE_ID,
        "work_state_provenance": stage_evidence_payload["work_state_provenance"],
        "stage_evidence_sha256": stage_evidence_sha256,
        "residual_J": residual,
        "active_max_abs_residual_J": maximum,
        "active_max_abs_limit_J": G06_LIMIT_J,
        "stage_work_recurrence_max_abs_error_J": recurrence_max,
        "stage_work_recurrence_limit_J": recurrence_limit,
        "all_terms_finite": all(_finite(value) for value in residual),
        "independent_work_state_provenance_pass": provenance_pass,
        "scientific_predicate": bool(maximum <= G06_LIMIT_J and provenance_pass),
    }
    if tuple(report) != G06_REQUIRED_FIELDS:
        raise WorkEnergyError("G06_REPORT_FIELD_ORDER_OR_SET_DRIFT")
    return report


__all__ = [
    "G04_PASS_EXPRESSION", "G04_REQUIRED_FIELDS", "G04_RULE_ID", "G06_REQUIRED_FIELDS",
    "G06_RULE_ID", "G06_WORK_STATE_PROVENANCE", "WorkEnergyError", "cumulative_trapezoid_J",
    "evaluate_g04", "evaluate_g06", "recompute_power_W", "runner_g04_signature",
]
