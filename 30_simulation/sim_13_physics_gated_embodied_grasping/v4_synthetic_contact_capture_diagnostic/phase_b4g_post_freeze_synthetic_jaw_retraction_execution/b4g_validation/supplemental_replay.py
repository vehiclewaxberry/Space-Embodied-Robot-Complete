"""Independent replay of authoritative B4G mutation supplemental traces.

The three artifacts handled here are not receipt annotations.  They are
byte-bound members of both replay bundles and prove that NC08, NC17 fallback,
and NC21 reached the registered numerical detector path.  This module imports
no B4G solver, campaign runner, or mutation executor code.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .core import canonical_bytes, read_json_strict, resolve_declared
from .geometry_replay import (
    GeometryReplayError,
    centered_gap_jacobian,
    recompute_active_gap_rate,
    recompute_mutation_only_no_domain_guard_active_geometry,
    reconstruct_active_target_state_13,
)
from .forced_propagation_replay import (
    ForcedPropagationReplayError,
    LEDGER_NAMES as FORCED_REPLAY_LEDGER_NAMES,
    replay_forced_propagation,
)


class SupplementalReplayError(ValueError):
    """Fail-closed malformed or non-replayed supplemental evidence."""


@dataclass(frozen=True)
class SupplementalReplayResult:
    parent_id: str
    subvariant_index: int
    role: str | None
    artifact_path: str | None
    artifact_sha256: str | None
    diagnostics: dict[str, Any]


DWELL_ROLE = "MUTANT_DWELL_FORCE_TRACE"
A2_ROLE = "A2_DETECTOR_SIX_LANE_TRACE"
GEOMETRY_ROLE = "GEOMETRY_CLIP_EXTRAPOLATE_TRACE"
SUPPLEMENTAL_ROLES = frozenset((DWELL_ROLE, A2_ROLE, GEOMETRY_ROLE))

LANES = (
    "RK4_COARSE", "RK4_FINE", "RK4_REFERENCE",
    "MIDPOINT_COARSE", "MIDPOINT_FINE", "MIDPOINT_REFERENCE",
)
LANE_DEFINITIONS = {
    "RK4_COARSE": ("rk4", 0.001),
    "RK4_FINE": ("rk4", 0.0005),
    "RK4_REFERENCE": ("rk4", 0.00025),
    "MIDPOINT_COARSE": ("midpoint", 0.0005),
    "MIDPOINT_FINE": ("midpoint", 0.00025),
    "MIDPOINT_REFERENCE": ("midpoint", 0.000125),
}
_FORCED_RUN_FIELDS = {
    "case_id", "method", "step_s", "event", "acquisition", "command", "raw",
    "clearance", "terminal_status", "geometry_domain_pass",
    "synthetic_removal_executed", "post_release", "failure", "search_endpoint",
    "physical_release_claimed", "minimum_required_force_or_work_claimed",
}
_FORCED_RAW_FIELDS = {
    "time_s", "state_30_service_29_plus_signed_W_act_J",
    "applied_Q_P_left_right_N", "command_Q_14", "actuator_power_W",
    "left_gap_m", "right_gap_m", "left_gap_rate_m_s", "right_gap_rate_m_s",
    "target_position_m", "target_quaternion_wxyz", "target_twist_mixed",
    "total_linear_momentum_N_s", "total_angular_momentum_N_m_s",
    "total_kinetic_energy_J", "sample_ledgers", "stage_audits",
}
_ACTIVE_STAGE_FIELDS = {
    "time_s", "stage_label", "P_coordinates_m_left_right",
    "raw_gap_jacobian_dimensionless", "diagonal_gap_derivatives_dimensionless",
    "opening_sign_left_right", "nominal_gap_m_left_right",
    "nominal_gap_rate_m_s_left_right", "contact_force_max_N",
    "contact_torque_max_N_m", "generalized_force_14",
    "consumed_opening_sign_left_right",
    "consumed_sigma_equals_raw_and_registered", "Q_base_and_R_exact_zero",
    "contact_kernel_enabled", "service_state_29", "stage_code",
    "mass_cholesky_min_diagonal", "actuator_power_W", "accepted",
}
_NC08_LEDGER_NAMES = {
    "linear_momentum_drift_N_s",
    "angular_momentum_drift_N_m_s",
    "energy_minus_work_residual_J",
    "ideal_constraint_power_W",
    "active_contact_force_N",
    "active_contact_torque_N_m",
    "forced_full_residual_service_base_linear_N",
    "forced_full_residual_service_base_angular_N_m",
    "forced_full_residual_service_R_joint_N_m",
    "forced_full_residual_service_P_joint_N",
    "forced_full_residual_target_linear_N",
    "forced_full_residual_target_angular_N_m",
    "reduced_residual_base_linear_N",
    "reduced_residual_base_angular_N_m",
    "reduced_residual_R_joint_N_m",
    "reduced_residual_P_joint_N",
}
_MUTATION_BOUNDARY = (
    "mutation replay evidence only; no A1/A2 outcome, physical, current-system, "
    "formal NC19, Owner, production, release or next-stage credit"
)
def _fail(code: str, detail: Any = None) -> None:
    suffix = "" if detail is None else f":{detail}"
    raise SupplementalReplayError(f"{code}{suffix}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _exact_fields(value: Any, fields: set[str], code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        _fail(code, {
            "missing": sorted(fields - set(value) if isinstance(value, Mapping) else fields),
            "extra": sorted(set(value) - fields if isinstance(value, Mapping) else []),
        })
    return value


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, (bool, np.bool_)) and math.isfinite(float(value))


def _array(value: Any, shape: tuple[int, ...] | None, code: str) -> np.ndarray:
    try:
        result = np.asarray(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise SupplementalReplayError(f"{code}_NOT_ARRAY") from error
    if result.dtype.kind not in "iuf" or result.dtype.itemsize > 8:
        _fail(f"{code}_DTYPE", str(result.dtype))
    result = np.asarray(result, dtype=float)
    if shape is not None and result.shape != shape:
        _fail(f"{code}_SHAPE", {"actual": list(result.shape), "expected": list(shape)})
    if not np.all(np.isfinite(result)):
        _fail(f"{code}_NONFINITE")
    return result


def _close(actual: Any, expected: Any, code: str, tolerance: float = 1.0e-12) -> None:
    left = _array(actual, None, f"{code}_ACTUAL")
    right = _array(expected, left.shape, f"{code}_EXPECTED")
    if float(np.max(np.abs(left - right), initial=0.0)) > tolerance:
        _fail(code, float(np.max(np.abs(left - right))))


def _record_map(records: Sequence[Mapping[str, Any]], project_root: Path, phase_root: Path) -> dict[str, tuple[Mapping[str, Any], Path]]:
    result: dict[str, tuple[Mapping[str, Any], Path]] = {}
    for row in records:
        if not isinstance(row, Mapping) or set(row) != {"role", "path", "bytes", "sha256"}:
            _fail("SUPPLEMENTAL_ARTIFACT_RECORD_FIELDS")
        role = row.get("role")
        if not isinstance(role, str) or role in result:
            _fail("SUPPLEMENTAL_ARTIFACT_ROLE_DUPLICATE", role)
        path = resolve_declared(project_root, phase_root, row.get("path"))
        if not path.is_file():
            _fail("SUPPLEMENTAL_ARTIFACT_MISSING", role)
        size = row.get("bytes")
        digest = row.get("sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0 or path.stat().st_size != size:
            _fail("SUPPLEMENTAL_ARTIFACT_BYTES", role)
        if not isinstance(digest, str) or _sha256(path) != digest:
            _fail("SUPPLEMENTAL_ARTIFACT_SHA256", role)
        result[role] = (row, path)
    return result


def _record_without_role(row: Mapping[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in ("path", "bytes", "sha256")}


def _load_canonical(path: Path, code: str) -> dict[str, Any]:
    try:
        value = read_json_strict(path)
    except Exception as error:
        raise SupplementalReplayError(f"{code}_INVALID_JSON:{error}") from error
    if path.read_bytes() != canonical_bytes(value) + b"\n":
        _fail(f"{code}_NOT_CANONICAL_JSON")
    return value


def _sin2(elapsed: float, duration: float) -> float:
    if duration == 0.0 or elapsed <= 0.0 or elapsed >= duration:
        return 0.0
    value = math.sin(math.pi * elapsed / duration)
    return value * value


def _command_force(command: Mapping[str, Any], acquisition_time: float, q_ref: float, time_s: float) -> np.ndarray:
    result = np.zeros(14)
    for index, side in ((12, "left"), (13, "right")):
        arm = command.get(side)
        if not isinstance(arm, Mapping) or set(arm) != {"alpha", "delay_s", "duration_s"}:
            _fail("COMMAND_ARM_FIELDS", side)
        alpha, delay, duration = (arm.get("alpha"), arm.get("delay_s"), arm.get("duration_s"))
        if not all(_finite_number(value) for value in (alpha, delay, duration)):
            _fail("COMMAND_ARM_NONFINITE", side)
        result[index] = float(alpha) * q_ref * _sin2(time_s - acquisition_time - float(delay), float(duration))
    return result


def _mutant_dwell_force(command: Mapping[str, Any], acquisition_time: float, q_ref: float, time_s: float, q_index: int, window: tuple[float, float]) -> np.ndarray:
    result = _command_force(command, acquisition_time, q_ref, time_s)
    if window[0] <= time_s <= window[1]:
        result[q_index] += q_ref
    return result


def _validate_nc08(
    payload: Mapping[str, Any], *, subvariant_index: int,
    records: Mapping[str, tuple[Mapping[str, Any], Path]], q_ref: float,
) -> dict[str, Any]:
    fields = {
        "schema", "parent_id", "subvariant_index", "side", "q_index",
        "source_finite_harness", "injection_window_s", "injection_N",
        "nominal_finite_clearance", "execution_branch", "mutant_run",
        "claim_boundary",
    }
    _exact_fields(payload, fields, "NC08_SUPPLEMENTAL_FIELDS")
    side = "left" if subvariant_index == 1 else "right"
    q_index = 12 if side == "left" else 13
    if payload.get("schema") != "SIM13_V4B4G_MUTANT_DWELL_FORCE_TRACE_V1" or payload.get("parent_id") != "B4FNC08" or payload.get("subvariant_index") != subvariant_index or payload.get("side") != side or payload.get("q_index") != q_index:
        _fail("NC08_SUPPLEMENTAL_ID_BINDING")
    if payload.get("execution_branch") != "PATCHED_FORCE_VECTOR_THEN_FORCED_PROPAGATION" or payload.get("claim_boundary") != _MUTATION_BOUNDARY:
        _fail("NC08_SUPPLEMENTAL_BRANCH_OR_BOUNDARY")
    finite_record, finite_path = records["EXECUTED_FINITE_HARNESS_RAW_OUTPUT"]
    if payload.get("source_finite_harness") != _record_without_role(finite_record):
        _fail("NC08_FINITE_SOURCE_BINDING")
    finite = _load_canonical(finite_path, "NC08_FINITE_SOURCE")
    clearance = finite.get("clearance")
    if not isinstance(clearance, Mapping) or payload.get("nominal_finite_clearance") != clearance:
        _fail("NC08_NOMINAL_CLEARANCE_BINDING")
    tau = clearance.get("tau_c_s")
    removal = clearance.get("removal_time_s")
    if not _finite_number(tau) or not _finite_number(removal):
        _fail("NC08_FINITE_CLEARANCE_TIME")
    window = (float(tau), float(removal))
    if payload.get("injection_window_s") != [window[0], window[1]] or payload.get("injection_N") != q_ref:
        _fail("NC08_INJECTION_CONTRACT")

    run = _exact_fields(payload.get("mutant_run"), _FORCED_RUN_FIELDS, "NC08_MUTANT_RUN_FIELDS")
    raw = _exact_fields(run.get("raw"), _FORCED_RAW_FIELDS, "NC08_MUTANT_RAW_FIELDS")
    if run.get("physical_release_claimed") is not False or run.get("minimum_required_force_or_work_claimed") is not False:
        _fail("NC08_MUTANT_FORBIDDEN_CLAIM")
    if run.get("case_id") != f"B4FNC08_{side.upper()}_REAL_DWELL_FORCE_MUTANT":
        _fail("NC08_MUTANT_CASE_ID")
    if run.get("method") != finite.get("method") or run.get("step_s") != finite.get("step_s") or run.get("command") != finite.get("command"):
        _fail("NC08_MUTANT_PARENT_EXECUTION_BINDING")
    event = run.get("event")
    acquisition = run.get("acquisition")
    if not isinstance(event, Mapping) or not isinstance(acquisition, Mapping):
        _fail("NC08_MUTANT_EVENT_ACQUISITION")
    acquisition_time = acquisition.get("acquisition_time_s")
    if not _finite_number(acquisition_time) or event.get("time_s") != acquisition_time:
        _fail("NC08_MUTANT_ACQUISITION_TIME")
    if {key: value for key, value in event.items() if key != "run_id"} != {key: value for key, value in finite.get("event", {}).items() if key != "run_id"}:
        _fail("NC08_MUTANT_EVENT_PARENT_DRIFT")
    if {key: value for key, value in acquisition.items() if key != "run_id"} != {key: value for key, value in finite.get("acquisition", {}).items() if key != "run_id"}:
        _fail("NC08_MUTANT_ACQUISITION_PARENT_DRIFT")

    if (
        run.get("geometry_domain_pass") is not True
        or run.get("synthetic_removal_executed") is not False
        or run.get("post_release") is not None
        or run.get("failure") is not None
        or run.get("search_endpoint") is not None
        or run.get("terminal_status")
        != "DIAGNOSTIC_INCONCLUSIVE_HORIZON_EXHAUSTED_NO_REMOVAL_OBSERVED"
        or not isinstance(run.get("clearance"), Mapping)
        or run["clearance"].get("finite_event") is not False
    ):
        _fail("NC08_MUTANT_PROPAGATION_TERMINAL_SEMANTICS")

    time = _array(raw.get("time_s"), None, "NC08_TIME")
    if time.ndim != 1 or len(time) < 2 or not np.all(np.diff(time) > 0.0):
        _fail("NC08_TIME_GRID")
    step = float(run["step_s"])
    expected_step_count = max(
        1,
        int(math.ceil(
            (float(removal) - float(acquisition_time)) / step - 1.0e-12
        )) + 1,
    )
    expected_time = (
        float(acquisition_time)
        + np.arange(expected_step_count + 1, dtype=float) * step
    )
    if not np.array_equal(time, expected_time):
        _fail(
            "NC08_COMPLETE_PROPAGATION_TIME_GRID",
            {"actual_count": len(time), "expected_count": len(expected_time)},
        )
    n = len(time)
    state = _array(raw.get("state_30_service_29_plus_signed_W_act_J"), (n, 30), "NC08_STATE")

    service_record = event.get("service")
    eta_plus = acquisition.get("eta_plus")
    if not isinstance(service_record, Mapping):
        _fail("NC08_EVENT_SERVICE_OBJECT")
    try:
        expected_initial_service = np.concatenate((
            _array(
                service_record.get("base_position_inertial_m"), (3,),
                "NC08_INITIAL_POSITION",
            ),
            _array(
                service_record.get("base_quaternion_body_to_inertial_wxyz"),
                (4,), "NC08_INITIAL_QUATERNION",
            ),
            _array(
                service_record.get("joint_coordinates_mixed"), (8,),
                "NC08_INITIAL_JOINTS",
            ),
            _array(eta_plus, (14,), "NC08_INITIAL_ETA_PLUS"),
        ))
    except AttributeError as error:
        raise SupplementalReplayError("NC08_INITIAL_SERVICE_FIELDS") from error
    _close(
        state[0, :29], expected_initial_service,
        "NC08_INITIAL_STATE_NOT_FRESH_EVENT_ACQUISITION", 0.0,
    )
    if state[0, 29] != 0.0:
        _fail("NC08_INITIAL_WORK_NOT_EXACT_ZERO")
    q = _array(raw.get("command_Q_14"), (n, 14), "NC08_Q")
    q_p = _array(raw.get("applied_Q_P_left_right_N"), (n, 2), "NC08_QP")
    power = _array(raw.get("actuator_power_W"), (n,), "NC08_POWER")
    if not np.array_equal(q_p, q[:, 12:14]) or not np.all(q[:, :12] == 0.0):
        _fail("NC08_Q_CHANNEL_BINDING")
    expected_q = np.asarray([
        _mutant_dwell_force(run["command"], float(acquisition_time), q_ref, float(item), q_index, window)
        for item in time
    ])
    if float(np.max(np.abs(q - expected_q))) > 1.0e-15:
        _fail("NC08_SAMPLE_COMMAND_REPLAY", float(np.max(np.abs(q - expected_q))))
    expected_power = np.sum(q[:, 12:14] * state[:, 27:29], axis=1)
    if float(np.max(np.abs(power - expected_power))) > 1.0e-12:
        _fail("NC08_SAMPLE_POWER_REPLAY")
    work = state[:, 29]
    cumulative = np.concatenate((
        np.asarray([work[0]]),
        work[0] + np.cumsum(0.5 * (power[:-1] + power[1:]) * np.diff(time)),
    ))
    if float(np.max(np.abs(cumulative - work))) > 1.0e-7:
        _fail("NC08_SAMPLE_WORK_REPLAY", float(np.max(np.abs(cumulative - work))))
    if not np.any(np.diff(state[:, 27 + (q_index - 12)]) != 0.0):
        _fail("NC08_FORCED_STATE_RESPONSE_NOT_OBSERVED")

    try:
        propagation = replay_forced_propagation(
            time_s=time,
            initial_state_30=state[0],
            method=str(run["method"]),
            step_s=step,
            event=event,
            acquisition=acquisition,
            command=run["command"],
            q_ref_N=q_ref,
            dwell_q_index=q_index,
            dwell_window_s=window,
        )
    except ForcedPropagationReplayError as error:
        raise SupplementalReplayError(
            f"NC08_INDEPENDENT_PROPAGATION_REPLAY:{error}"
        ) from error
    _close(
        state, propagation.state_30,
        "NC08_INDEPENDENT_PROPAGATION_STATE_REPLAY", 5.0e-12,
    )
    _close(
        q, propagation.command_Q_14,
        "NC08_INDEPENDENT_PROPAGATION_COMMAND_REPLAY", 1.0e-15,
    )
    _close(
        power, propagation.actuator_power_W,
        "NC08_INDEPENDENT_PROPAGATION_POWER_REPLAY", 5.0e-14,
    )

    linear = _array(
        raw.get("total_linear_momentum_N_s"), (n, 3), "NC08_LINEAR",
    )
    angular = _array(
        raw.get("total_angular_momentum_N_m_s"), (n, 3), "NC08_ANGULAR",
    )
    energy = _array(
        raw.get("total_kinetic_energy_J"), (n,), "NC08_ENERGY",
    )
    ledgers = raw.get("sample_ledgers")
    if not isinstance(ledgers, Mapping) or set(ledgers) != _NC08_LEDGER_NAMES:
        _fail("NC08_SAMPLE_LEDGER_INVENTORY")
    ledger_arrays = {
        name: _array(value, (n,), f"NC08_LEDGER_{name}")
        for name, value in ledgers.items()
    }
    if set(FORCED_REPLAY_LEDGER_NAMES) != _NC08_LEDGER_NAMES:
        _fail("NC08_INDEPENDENT_LEDGER_IMPLEMENTATION_INVENTORY")
    for name in FORCED_REPLAY_LEDGER_NAMES:
        tolerance = (
            1.0e-12 if name.startswith("forced_full_residual_")
            else 5.0e-15
        )
        _close(
            ledger_arrays[name], propagation.sample_ledgers[name],
            f"NC08_INDEPENDENT_LEDGER_REPLAY_{name}", tolerance,
        )
    expected_linear_drift = np.linalg.norm(linear - linear[0], axis=1)
    expected_angular_drift = np.linalg.norm(angular - angular[0], axis=1)
    expected_energy_residual = np.abs(
        (energy - energy[0]) - (work - work[0])
    )
    _close(
        ledger_arrays["linear_momentum_drift_N_s"], expected_linear_drift,
        "NC08_LINEAR_LEDGER_REPLAY", 1.0e-12,
    )
    _close(
        ledger_arrays["angular_momentum_drift_N_m_s"], expected_angular_drift,
        "NC08_ANGULAR_LEDGER_REPLAY", 1.0e-12,
    )
    _close(
        ledger_arrays["energy_minus_work_residual_J"],
        expected_energy_residual, "NC08_ENERGY_LEDGER_REPLAY", 1.0e-12,
    )
    if (
        np.max(ledger_arrays["linear_momentum_drift_N_s"]) > 1.0e-9
        or np.max(ledger_arrays["angular_momentum_drift_N_m_s"]) > 1.0e-9
        or np.max(ledger_arrays["energy_minus_work_residual_J"]) > 1.0e-7
        or np.max(ledger_arrays["ideal_constraint_power_W"]) > 1.0e-10
        or not np.all(ledger_arrays["active_contact_force_N"] == 0.0)
        or not np.all(ledger_arrays["active_contact_torque_N_m"] == 0.0)
        or any(
            np.any(values < 0.0) for values in ledger_arrays.values()
        )
    ):
        _fail("NC08_SAMPLE_LEDGER_NOT_CLOSED")

    target = np.column_stack((
        _array(raw.get("target_position_m"), (n, 3), "NC08_TARGET_POSITION"),
        _array(raw.get("target_quaternion_wxyz"), (n, 4), "NC08_TARGET_QUATERNION"),
        _array(raw.get("target_twist_mixed"), (n, 6), "NC08_TARGET_TWIST"),
    ))
    _close(
        target, propagation.target_state_13,
        "NC08_INDEPENDENT_TARGET_STATE_REPLAY", 5.0e-12,
    )
    _close(
        linear, propagation.total_linear_momentum_N_s,
        "NC08_INDEPENDENT_LINEAR_MOMENTUM_REPLAY", 5.0e-12,
    )
    _close(
        angular, propagation.total_angular_momentum_N_m_s,
        "NC08_INDEPENDENT_ANGULAR_MOMENTUM_REPLAY", 5.0e-12,
    )
    _close(
        energy, propagation.total_kinetic_energy_J,
        "NC08_INDEPENDENT_KINETIC_ENERGY_REPLAY", 5.0e-12,
    )
    gaps = np.column_stack((
        _array(raw.get("left_gap_m"), (n,), "NC08_LEFT_GAP"),
        _array(raw.get("right_gap_m"), (n,), "NC08_RIGHT_GAP"),
    ))
    rates = np.column_stack((
        _array(raw.get("left_gap_rate_m_s"), (n,), "NC08_LEFT_RATE"),
        _array(raw.get("right_gap_rate_m_s"), (n,), "NC08_RIGHT_RATE"),
    ))
    snapshot = acquisition.get("snapshot")
    for index in range(n):
        try:
            expected_target = reconstruct_active_target_state_13(state[index, :29], snapshot)
            replay = recompute_active_gap_rate(state[index, :29], snapshot)
        except GeometryReplayError as error:
            raise SupplementalReplayError(f"NC08_SAMPLE_GEOMETRY:{index}:{error}") from error
        _close(target[index], expected_target, f"NC08_TARGET_REPLAY_{index}")
        _close(gaps[index], replay.gaps_m, f"NC08_GAP_REPLAY_{index}")
        _close(rates[index], replay.gap_rates_m_s, f"NC08_RATE_REPLAY_{index}")

    stages = raw.get("stage_audits")
    if not isinstance(stages, list) or not stages:
        _fail("NC08_STAGE_TRACE_MISSING")
    expected_stages: list[tuple[str, int, float, int | None]] = [
        ("ACCEPTED_SAMPLE_0", 0, float(time[0]), 0),
    ]
    for interval in range(n - 1):
        left = float(time[interval])
        if run["method"] == "rk4":
            expected_stages.extend((
                (f"STEP_{interval}_K1", 1, left, None),
                (f"STEP_{interval}_K2", 2, left + 0.5 * step, None),
                (f"STEP_{interval}_K3", 3, left + 0.5 * step, None),
                (f"STEP_{interval}_K4", 4, left + step, None),
            ))
        elif run["method"] == "midpoint":
            expected_stages.extend((
                (f"STEP_{interval}_K1", 1, left, None),
                (
                    f"STEP_{interval}_MIDPOINT", 5,
                    left + 0.5 * step, None,
                ),
            ))
        else:
            _fail("NC08_STAGE_METHOD")
        expected_stages.append((
            f"ACCEPTED_SAMPLE_{interval + 1}", 0,
            float(time[interval + 1]), interval + 1,
        ))
    if len(stages) != len(expected_stages):
        _fail(
            "NC08_COMPLETE_STAGE_COUNT",
            {"actual": len(stages), "expected": len(expected_stages)},
        )
    if len(propagation.stages) != len(expected_stages):
        _fail(
            "NC08_INDEPENDENT_COMPLETE_STAGE_COUNT",
            {
                "actual": len(propagation.stages),
                "expected": len(expected_stages),
            },
        )
    stage_dwell_count = 0
    for index, (row, expected_stage, propagated_stage) in enumerate(
        zip(stages, expected_stages, propagation.stages)
    ):
        allowed = _ACTIVE_STAGE_FIELDS | {"mass_min_eigenvalue"}
        if not isinstance(row, Mapping) or set(row) not in (_ACTIVE_STAGE_FIELDS, allowed) or row.get("accepted") is not True:
            _fail("NC08_STAGE_FIELDS_OR_STATUS", index)
        stage_time = row.get("time_s")
        if not _finite_number(stage_time):
            _fail("NC08_STAGE_TIME", index)
        expected_label, expected_code, expected_time_value, stored_index = (
            expected_stage
        )
        if (
            row.get("stage_label") != expected_label
            or row.get("stage_code") != expected_code
            or abs(float(stage_time) - expected_time_value) > 1.0e-15
        ):
            _fail(
                "NC08_STAGE_PATTERN",
                {
                    "index": index,
                    "expected": expected_stage[:3],
                    "actual": (
                        row.get("stage_label"), row.get("stage_code"),
                        row.get("time_s"),
                    ),
                },
            )
        service = _array(row.get("service_state_29"), (29,), f"NC08_STAGE_SERVICE_{index}")
        force = _array(row.get("generalized_force_14"), (14,), f"NC08_STAGE_Q_{index}")
        _close(
            service, propagated_stage.state_30[:29],
            f"NC08_INDEPENDENT_STAGE_STATE_REPLAY_{index}", 5.0e-12,
        )
        _close(
            force, propagated_stage.generalized_force_14,
            f"NC08_INDEPENDENT_STAGE_COMMAND_REPLAY_{index}", 1.0e-15,
        )
        expected = _mutant_dwell_force(run["command"], float(acquisition_time), q_ref, float(stage_time), q_index, window)
        if float(np.max(np.abs(force - expected))) > 1.0e-15 or not np.all(force[:12] == 0.0):
            _fail("NC08_STAGE_COMMAND_REPLAY", index)
        if window[0] <= float(stage_time) <= window[1]:
            stage_dwell_count += 1
        try:
            replay = centered_gap_jacobian(service, snapshot=snapshot, step_m=1.0e-7)
        except GeometryReplayError as error:
            raise SupplementalReplayError(f"NC08_STAGE_GEOMETRY:{index}:{error}") from error
        _close(row.get("P_coordinates_m_left_right"), replay.p_coordinates_m, f"NC08_STAGE_P_{index}")
        _close(row.get("raw_gap_jacobian_dimensionless"), replay.raw_gap_jacobian_p, f"NC08_STAGE_JAC_{index}")
        _close(
            row.get("diagonal_gap_derivatives_dimensionless"),
            replay.diagonal_derivatives,
            f"NC08_STAGE_DIAGONAL_DERIVATIVE_{index}",
        )
        _close(row.get("nominal_gap_m_left_right"), replay.nominal_gaps_m, f"NC08_STAGE_GAP_{index}")
        _close(row.get("nominal_gap_rate_m_s_left_right"), replay.nominal_gap_rates_m_s, f"NC08_STAGE_RATE_{index}")
        if row.get("opening_sign_left_right") != [1, 1] or row.get("consumed_opening_sign_left_right") != [1, 1] or row.get("consumed_sigma_equals_raw_and_registered") is not True:
            _fail("NC08_STAGE_SIGN", index)
        stage_power = float(force[12:14] @ service[27:29])
        if not _finite_number(row.get("actuator_power_W")) or abs(float(row["actuator_power_W"]) - stage_power) > 1.0e-12:
            _fail("NC08_STAGE_POWER", index)
        if abs(float(row["actuator_power_W"]) - propagated_stage.actuator_power_W) > 5.0e-14:
            _fail("NC08_INDEPENDENT_STAGE_POWER_REPLAY", index)
        if row.get("Q_base_and_R_exact_zero") is not True or row.get("contact_kernel_enabled") is not False:
            _fail("NC08_STAGE_CHANNEL_OR_CONTACT", index)
        if (
            not _finite_number(row.get("contact_force_max_N"))
            or float(row["contact_force_max_N"]) != 0.0
            or not _finite_number(row.get("contact_torque_max_N_m"))
            or float(row["contact_torque_max_N_m"]) != 0.0
        ):
            _fail("NC08_STAGE_CONTACT_NOT_EXACT_ZERO", index)
        if (
            not _finite_number(row.get("mass_cholesky_min_diagonal"))
            or float(row["mass_cholesky_min_diagonal"]) <= 0.0
            or (
                "mass_min_eigenvalue" in row
                and (
                    not _finite_number(row.get("mass_min_eigenvalue"))
                    or float(row["mass_min_eigenvalue"]) <= 0.0
                )
            )
        ):
            _fail("NC08_STAGE_MASS_NOT_SPD", index)
        if abs(
            float(row["mass_cholesky_min_diagonal"])
            - propagated_stage.mass_cholesky_min_diagonal
        ) > 1.0e-12:
            _fail("NC08_INDEPENDENT_STAGE_CHOLESKY_REPLAY", index)
        expected_eigenvalue = propagated_stage.mass_min_eigenvalue
        if expected_eigenvalue is None:
            if "mass_min_eigenvalue" in row:
                _fail("NC08_ACCEPTED_STAGE_HAS_EIGENVALUE", index)
        elif (
            "mass_min_eigenvalue" not in row
            or abs(float(row["mass_min_eigenvalue"]) - expected_eigenvalue)
            > 1.0e-12
        ):
            _fail("NC08_INDEPENDENT_STAGE_EIGENVALUE_REPLAY", index)
        if stored_index is not None:
            if (
                not np.array_equal(service, state[stored_index, :29])
                or not np.array_equal(force, q[stored_index])
                or float(row["actuator_power_W"]) != float(power[stored_index])
            ):
                _fail("NC08_STORED_STAGE_NOT_RAW_SAMPLE", index)
    sample_mask = (time >= window[0]) & (time <= window[1])
    if not np.any(sample_mask) or stage_dwell_count == 0:
        _fail("NC08_DWELL_SUPPORT_NOT_SAMPLED")
    if not np.all(q[sample_mask, q_index] == q_ref) or not np.all(np.delete(q[sample_mask], q_index, axis=1) == 0.0):
        _fail("NC08_DWELL_FORCE_NOT_ACTUALLY_APPLIED")
    return {
        "side": side,
        "q_index": q_index,
        "sample_count": n,
        "stage_count": len(stages),
        "dwell_sample_count": int(np.count_nonzero(sample_mask)),
        "dwell_stage_count": stage_dwell_count,
        "independent_g08_predicate": False,
    }


def _validate_nc17(
    payload: Mapping[str, Any], *, records: Mapping[str, tuple[Mapping[str, Any], Path]],
    schedule: Mapping[str, Any], q_ref: float, phase_root: Path,
    base_payload: Mapping[str, Any],
) -> dict[str, Any]:
    del phase_root  # fallback is deliberately independent of B3/B4E dynamics.
    fields = {
        "schema", "parent_id", "harness_id", "source_schedule",
        "parent_level", "lane_order", "trace_order", "detector_model",
        "lanes", "capabilities", "claim_boundary",
    }
    _exact_fields(payload, fields, "NC17_SUPPLEMENTAL_FIELDS")
    if (
        payload.get("schema")
        != "SIM13_V4B4G_A2_DETECTOR_SIX_LANE_TRACE_V1"
        or payload.get("parent_id") != "B4FNC17"
        or payload.get("harness_id")
        != "ALGORITHM_ONLY_A2_DETECTOR_HARNESS"
        or payload.get("claim_boundary") != _MUTATION_BOUNDARY
    ):
        _fail("NC17_SUPPLEMENTAL_ID_OR_BOUNDARY")
    schedule_record, schedule_path = records["FROZEN_REGISTERED_SCHEDULE"]
    try:
        bound_schedule = read_json_strict(schedule_path)
    except Exception as error:
        raise SupplementalReplayError(
            f"NC17_SCHEDULE_INVALID_JSON:{error}"
        ) from error
    if (
        payload.get("source_schedule") != _record_without_role(schedule_record)
        or bound_schedule != schedule
    ):
        _fail("NC17_SCHEDULE_BINDING")
    trace_order = (
        "RIGHT_HALF_DELAY_BASE", "RIGHT_HALF_DELAY_MUTANT",
        "LEFT_HALF_DELAY_MIRROR", "RIGHT_COMMAND_OFF_BASE",
        "RIGHT_COMMAND_OFF_MUTANT", "LEFT_COMMAND_OFF_MIRROR",
    )
    model = {
        "model_id": "SYMMETRIC_DETERMINISTIC_BILATERAL_COMMAND_RESPONSE_V1",
        "initial_gap_m": 2.0e-6,
        "symmetric_mobility_m_s_N": 0.01,
        "integration": "CUMULATIVE_TRAPEZOID_ON_FROZEN_RELATIVE_GRID",
        "terminal_status": (
            "ALGORITHM_ONLY_DETECTOR_HORIZON_COMPLETE_NO_PHYSICAL_OUTCOME"
        ),
    }
    capabilities = {
        "a1_outcome_credit": False,
        "a2_outcome_credit": False,
        "physical_credit": False,
        "current_system_bound": False,
    }
    if (
        payload.get("parent_level") != base_payload.get("parent_level")
        or payload.get("lane_order") != list(LANES)
        or payload.get("trace_order") != list(trace_order)
        or payload.get("detector_model") != model
        or payload.get("capabilities") != capabilities
    ):
        _fail("NC17_PARENT_OR_ORDER")
    parent = payload.get("parent_level")
    if not isinstance(parent, Mapping) or not all(_finite_number(parent.get(key)) for key in ("alpha", "command_duration_s", "Q_ref_N")) or float(parent["Q_ref_N"]) != q_ref:
        _fail("NC17_PARENT_LEVEL")
    alpha = float(parent["alpha"])
    duration = float(parent["command_duration_s"])
    lanes = payload.get("lanes")
    if not isinstance(lanes, list) or len(lanes) != 6:
        _fail("NC17_LANE_COUNT")
    detector_rows: list[dict[str, Any]] = []
    trace_fields = {
        "trace_id", "pair_kind", "side", "command_variant", "command_Q_14",
        "left_gap_m", "right_gap_m", "left_gap_rate_m_s",
        "right_gap_rate_m_s", "signed_W_act_J", "outcome",
    }
    trace_definitions = {
        "RIGHT_HALF_DELAY_BASE": (
            "HALF_DELAY", "RIGHT", "RIGHT_HALF_DELAY",
            ((alpha, 0.0), (0.5 * alpha, 0.005)),
        ),
        "RIGHT_HALF_DELAY_MUTANT": (
            "HALF_DELAY", "RIGHT", "RIGHT_HALF_DELAY",
            ((alpha, 0.0), (0.75 * alpha, 0.005)),
        ),
        "LEFT_HALF_DELAY_MIRROR": (
            "HALF_DELAY", "LEFT_MIRROR", "LEFT_HALF_DELAY_MIRROR",
            ((0.5 * alpha, 0.005), (alpha, 0.0)),
        ),
        "RIGHT_COMMAND_OFF_BASE": (
            "COMMAND_OFF", "RIGHT", "RIGHT_COMMAND_OFF",
            ((alpha, 0.0), (0.0, 0.0)),
        ),
        "RIGHT_COMMAND_OFF_MUTANT": (
            "COMMAND_OFF", "RIGHT", "RIGHT_COMMAND_OFF",
            ((alpha, 0.0), (0.25 * alpha, 0.0)),
        ),
        "LEFT_COMMAND_OFF_MIRROR": (
            "COMMAND_OFF", "LEFT_MIRROR", "LEFT_COMMAND_OFF_MIRROR",
            ((0.0, 0.0), (alpha, 0.0)),
        ),
    }
    outcome = {
        "finite_removal_event": False,
        "removal_time_s": None,
        "post_release_passed": False,
        "terminal_status": model["terminal_status"],
    }

    def cumulative_trapezoid(values: np.ndarray, grid: np.ndarray) -> np.ndarray:
        if values.ndim == 1:
            increments = 0.5 * (values[:-1] + values[1:]) * np.diff(grid)
            return np.concatenate((np.zeros(1), np.cumsum(increments)))
        increments = 0.5 * (values[:-1] + values[1:]) * np.diff(grid)[:, None]
        return np.vstack((np.zeros((1, values.shape[1])), np.cumsum(increments, axis=0)))

    def comparator(
        left: Mapping[str, Any], right: Mapping[str, Any], grid: np.ndarray,
    ) -> dict[str, Any]:
        left_gap = np.column_stack((left["left_gap_m"], left["right_gap_m"]))
        right_gap = np.column_stack((right["left_gap_m"], right["right_gap_m"]))
        left_rate = np.column_stack((left["left_gap_rate_m_s"], left["right_gap_rate_m_s"]))
        right_rate = np.column_stack((right["left_gap_rate_m_s"], right["right_gap_rate_m_s"]))
        gap = float(max(
            np.max(np.abs(left_gap[:, 0] - right_gap[:, 1])),
            np.max(np.abs(left_gap[:, 1] - right_gap[:, 0])),
        ))
        rate = float(max(
            np.max(np.abs(left_rate[:, 0] - right_rate[:, 1])),
            np.max(np.abs(left_rate[:, 1] - right_rate[:, 0])),
        ))
        work = abs(float(left["signed_W_act_J"][-1] - right["signed_W_act_J"][-1]))
        parity = left["outcome"] == right["outcome"]
        predicate = bool(
            gap <= 1.0e-9 and rate <= 1.0e-9
            and work <= 1.0e-9 and parity
        )
        return {
            "full_relative_grid_equal": True,
            "sample_count": len(grid),
            "gap_residual_m": gap,
            "gap_rate_residual_m_s": rate,
            "work_residual_J": work,
            "outcome_parity": parity,
            "scientific_predicate": predicate,
        }

    for lane_index, lane_row in enumerate(lanes):
        lane = LANES[lane_index]
        _exact_fields(
            lane_row,
            {"lane_id", "method", "step_s", "relative_time_s", "traces"},
            "NC17_LANE_FIELDS",
        )
        method, step = LANE_DEFINITIONS[lane]
        if lane_row.get("lane_id") != lane or lane_row.get("method") != method or lane_row.get("step_s") != step:
            _fail("NC17_LANE_DEFINITION", lane)
        step_count = int(round(0.08 / step))
        expected_grid = np.arange(step_count + 1, dtype=float) * step
        grid = _array(
            lane_row.get("relative_time_s"), expected_grid.shape,
            "NC17_RELATIVE_TIME",
        )
        if not np.array_equal(grid, expected_grid) or float(grid[-1]) != 0.08:
            _fail("NC17_FROZEN_FULL_GRID", lane)
        traces = lane_row.get("traces")
        if (
            not isinstance(traces, list) or len(traces) != 6
            or [row.get("trace_id") for row in traces if isinstance(row, Mapping)]
            != list(trace_order)
        ):
            _fail("NC17_TRACE_ORDER", lane)
        replayed: dict[str, dict[str, Any]] = {}
        for trace_id, trace in zip(trace_order, traces):
            _exact_fields(trace, trace_fields, "NC17_TRACE_FIELDS")
            pair_kind, side, command_variant, definitions = trace_definitions[trace_id]
            if (
                trace.get("trace_id") != trace_id
                or trace.get("pair_kind") != pair_kind
                or trace.get("side") != side
                or trace.get("command_variant") != command_variant
                or trace.get("outcome") != outcome
            ):
                _fail("NC17_TRACE_ID_BINDING", {"lane": lane, "trace": trace_id})
            n = len(grid)
            q = _array(trace.get("command_Q_14"), (n, 14), "NC17_Q")
            if not np.all(q[:, :12] == 0.0):
                _fail("NC17_Q_NON_P_CHANNEL", trace_id)
            left_arm, right_arm = definitions
            command = {
                "left": {"alpha": left_arm[0], "delay_s": left_arm[1], "duration_s": duration},
                "right": {"alpha": right_arm[0], "delay_s": right_arm[1], "duration_s": duration},
            }
            expected_q = np.asarray([
                _command_force(command, 0.0, q_ref, float(item))
                for item in grid
            ])
            if float(np.max(np.abs(q - expected_q))) > 1.0e-15:
                _fail("NC17_MUTANT_COMMAND_REPLAY", {"lane": lane, "trace": trace_id})
            expected_rate = model["symmetric_mobility_m_s_N"] * q[:, 12:14]
            expected_gap = model["initial_gap_m"] + cumulative_trapezoid(
                expected_rate, grid,
            )
            expected_power = np.sum(q[:, 12:14] * expected_rate, axis=1)
            expected_work = cumulative_trapezoid(expected_power, grid)
            reported = {
                "left_gap_m": _array(trace.get("left_gap_m"), (n,), "NC17_LEFT_GAP"),
                "right_gap_m": _array(trace.get("right_gap_m"), (n,), "NC17_RIGHT_GAP"),
                "left_gap_rate_m_s": _array(trace.get("left_gap_rate_m_s"), (n,), "NC17_LEFT_RATE"),
                "right_gap_rate_m_s": _array(trace.get("right_gap_rate_m_s"), (n,), "NC17_RIGHT_RATE"),
                "signed_W_act_J": _array(trace.get("signed_W_act_J"), (n,), "NC17_WORK"),
                "outcome": trace["outcome"],
            }
            _close(reported["left_gap_m"], expected_gap[:, 0], f"NC17_LEFT_GAP_REPLAY_{lane}_{trace_id}", 1.0e-15)
            _close(reported["right_gap_m"], expected_gap[:, 1], f"NC17_RIGHT_GAP_REPLAY_{lane}_{trace_id}", 1.0e-15)
            _close(reported["left_gap_rate_m_s"], expected_rate[:, 0], f"NC17_LEFT_RATE_REPLAY_{lane}_{trace_id}", 1.0e-15)
            _close(reported["right_gap_rate_m_s"], expected_rate[:, 1], f"NC17_RIGHT_RATE_REPLAY_{lane}_{trace_id}", 1.0e-15)
            _close(reported["signed_W_act_J"], expected_work, f"NC17_WORK_REPLAY_{lane}_{trace_id}", 1.0e-15)
            replayed[trace_id] = reported
        comparisons = (
            ("HALF_DELAY_BASE", "LEFT_HALF_DELAY_MIRROR", "RIGHT_HALF_DELAY_BASE", True),
            ("HALF_DELAY_MUTANT", "LEFT_HALF_DELAY_MIRROR", "RIGHT_HALF_DELAY_MUTANT", False),
            ("COMMAND_OFF_BASE", "LEFT_COMMAND_OFF_MIRROR", "RIGHT_COMMAND_OFF_BASE", True),
            ("COMMAND_OFF_MUTANT", "LEFT_COMMAND_OFF_MIRROR", "RIGHT_COMMAND_OFF_MUTANT", False),
        )
        for comparison_id, left_id, right_id, expected_predicate in comparisons:
            metrics = comparator(replayed[left_id], replayed[right_id], grid)
            if metrics["scientific_predicate"] is not expected_predicate:
                _fail(
                    "NC17_DETECTOR_EXPECTED_PREDICATE",
                    {"lane": lane, "comparison": comparison_id, "expected": expected_predicate, "actual": metrics["scientific_predicate"]},
                )
            detector_rows.append({
                "lane_id": lane, "comparison_id": comparison_id,
                "expected_predicate": expected_predicate, **metrics,
            })
    return {
        "lane_count": 6,
        "trace_count": 36,
        "algorithm_only_harness": True,
        "detector_pair_count": len(detector_rows),
        "all_base_pair_predicates_true": all(
            row["scientific_predicate"] is True
            for row in detector_rows if row["expected_predicate"] is True
        ),
        "all_mutant_pair_predicates_false": all(
            row["scientific_predicate"] is False
            for row in detector_rows if row["expected_predicate"] is False
        ),
        "detector_rows": detector_rows,
    }


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    try:
        with np.load(path, allow_pickle=False) as archive:
            arrays = {name: np.asarray(archive[name]) for name in archive.files}
    except Exception as error:
        raise SupplementalReplayError(f"NC21_NPZ_READ:{error}") from error
    for name, value in arrays.items():
        if value.dtype.kind not in "biuf" or value.dtype.itemsize > 8 or (value.dtype.kind == "f" and not np.all(np.isfinite(value))):
            _fail("NC21_NPZ_DTYPE_OR_FINITE", {"name": name, "dtype": str(value.dtype)})
    return arrays


def _validate_nc21(
    payload: Mapping[str, Any], *, subvariant_index: int,
    records: Mapping[str, tuple[Mapping[str, Any], Path]],
    mutation_spec: Mapping[str, Any], base_payload: Mapping[str, Any],
) -> dict[str, Any]:
    fields = {
        "schema", "parent_id", "subvariant_index", "source_case_metadata",
        "source_case_npz", "stage_index", "mutation_target",
        "nominal_service_state_29", "acquisition_snapshot",
        "raw_P_coordinates_m", "transformed_P_coordinates_m", "branch",
        "domain_exit_record", "branch_trace",
        "no_domain_guard_evaluation", "claim_boundary",
    }
    _exact_fields(payload, fields, "NC21_SUPPLEMENTAL_FIELDS")
    if payload.get("schema") != "SIM13_V4B4G_GEOMETRY_CLIP_EXTRAPOLATE_TRACE_V1" or payload.get("parent_id") != "B4FNC21" or payload.get("subvariant_index") != subvariant_index or payload.get("claim_boundary") != _MUTATION_BOUNDARY:
        _fail("NC21_SUPPLEMENTAL_ID_OR_BOUNDARY")
    metadata_record, metadata_path = records["REGISTERED_CASE_METADATA"]
    npz_record, npz_path = records["REGISTERED_CASE_RAW_NPZ"]
    if payload.get("source_case_metadata") != _record_without_role(metadata_record) or payload.get("source_case_npz") != _record_without_role(npz_record):
        _fail("NC21_SOURCE_CASE_BINDING")
    metadata = _load_canonical(metadata_path, "NC21_CASE_METADATA")
    arrays = _load_npz(npz_path)
    stage_index = payload.get("stage_index")
    if not isinstance(stage_index, int) or isinstance(stage_index, bool) or stage_index < 0:
        _fail("NC21_STAGE_INDEX")
    stages = arrays.get("stage_service_state_29")
    stage_time = arrays.get("stage_time_s")
    if stages is None or stage_time is None or stages.ndim != 2 or stages.shape[1:] != (29,) or stage_index >= len(stages) or stage_time.shape != (len(stages),):
        _fail("NC21_STAGE_SOURCE_SHAPE")
    service = _array(payload.get("nominal_service_state_29"), (29,), "NC21_SERVICE")
    if not np.array_equal(service, np.asarray(stages[stage_index], dtype=float)):
        _fail("NC21_SERVICE_NOT_SOURCE_STAGE")
    if base_payload.get("P_coordinates_m") != service[13:15].tolist():
        _fail("NC21_BASE_P_NOT_SOURCE_STAGE")
    certificate = metadata.get("event_provenance", {}).get("acquisition_certificate_payload", {})
    snapshot = certificate.get("acquisition", {}).get("snapshot") if isinstance(certificate, Mapping) else None
    if payload.get("acquisition_snapshot") != snapshot or not isinstance(snapshot, Mapping):
        _fail("NC21_ACQUISITION_SNAPSHOT_BINDING")
    targets = mutation_spec.get("deterministic_targets_and_amplitudes", {}).get("P_domain_mutants")
    if not isinstance(targets, list) or len(targets) != 6 or payload.get("mutation_target") != targets[subvariant_index - 1]:
        _fail("NC21_MUTATION_TARGET_BINDING")
    base_p = service[13:15].copy()
    raw_p = base_p.copy()
    target = targets[subvariant_index - 1]
    if subvariant_index <= 4:
        side = 0 if target.get("side") == "left" else 1 if target.get("side") == "right" else None
        if side is None or not _finite_number(target.get("value_m")):
            _fail("NC21_DIRECT_TARGET")
        raw_p[side] = float(target["value_m"])
        transformed: np.ndarray | None = None
        branch = "DIRECT_DOMAIN_REJECT_NO_TRANSFORM"
        failed_side = side
        policy_outcome = "G16_FAIL_DIRECT_OUT_OF_DOMAIN"
    else:
        raw_p[0] = 0.071500001
        failed_side = 0
        if subvariant_index == 5:
            transformed = raw_p.copy(); transformed[0] = 0.0715
            branch = "CLIP_TO_UPPER_BOUND"
            policy_outcome = "G16_FAIL_CLIPPING_USED"
        else:
            transformed = raw_p.copy()
            branch = "EXTRAPOLATE_AFTER_UPPER_BOUND"
            policy_outcome = "G16_FAIL_EXTRAPOLATION_USED"
    if payload.get("raw_P_coordinates_m") != raw_p.tolist() or payload.get("transformed_P_coordinates_m") != (None if transformed is None else transformed.tolist()) or payload.get("branch") != branch:
        _fail("NC21_RAW_TRANSFORM_BRANCH")
    record = payload.get("domain_exit_record")
    expected_record = {
        "time_s": float(stage_time[stage_index]),
        "stage_label": f"B4FNC21_SUPPLEMENTAL_SV{subvariant_index:02d}",
        "P_coordinates_m_left_right": raw_p.tolist(),
        "centered_step_m": 1.0e-7,
        "failed_side": failed_side,
        "reason": "P_COORDINATE_OUTSIDE_CLOSED_DOMAIN",
    }
    if record != expected_record:
        _fail("NC21_DOMAIN_EXIT_RECORD", {"expected": expected_record, "actual": record})

    branch_trace = [
        {
            "ordinal": 0,
            "operation": "APPLY_RAW_REGISTERED_MUTANT_P",
            "P_coordinates_m": raw_p.tolist(),
            "outcome": "APPLIED",
        },
        {
            "ordinal": 1,
            "operation": "FROZEN_P_DOMAIN_GUARD",
            "P_coordinates_m": raw_p.tolist(),
            "outcome": "DOMAIN_EXIT",
        },
    ]
    if transformed is None:
        branch_trace.extend((
            {
                "ordinal": 2,
                "operation": "NO_TRANSFORM",
                "P_coordinates_m": None,
                "outcome": "NOT_EXECUTED",
            },
            {
                "ordinal": 3,
                "operation": "G16_POLICY",
                "P_coordinates_m": raw_p.tolist(),
                "outcome": policy_outcome,
            },
        ))
    else:
        transform_operation = (
            "CLIP_TO_UPPER_BOUND"
            if subvariant_index == 5
            else "EXTRAPOLATE_IDENTITY_OUTSIDE_DOMAIN"
        )
        branch_trace.extend((
            {
                "ordinal": 2,
                "operation": transform_operation,
                "P_coordinates_m": transformed.tolist(),
                "outcome": "TRANSFORMED",
            },
            {
                "ordinal": 3,
                "operation": "MUTATION_ONLY_NO_DOMAIN_GUARD_FK",
                "P_coordinates_m": transformed.tolist(),
                "outcome": "EXECUTED",
            },
            {
                "ordinal": 4,
                "operation": "G16_POLICY",
                "P_coordinates_m": transformed.tolist(),
                "outcome": policy_outcome,
            },
        ))
    if payload.get("branch_trace") != branch_trace:
        _fail(
            "NC21_BRANCH_TRACE",
            {"expected": branch_trace, "actual": payload.get("branch_trace")},
        )

    raw_invalid = service.copy()
    raw_invalid[13:15] = raw_p
    try:
        recompute_active_gap_rate(raw_invalid, snapshot)
    except GeometryReplayError as error:
        if f"P_COORDINATE_OUTSIDE_DOMAIN:{failed_side}" not in str(error):
            raise SupplementalReplayError(
                f"NC21_RAW_DOMAIN_WRONG_FAILURE:{error}"
            ) from error
    else:
        _fail("NC21_RAW_DOMAIN_NOT_INDEPENDENTLY_REJECTED")

    evaluation = payload.get("no_domain_guard_evaluation")
    if transformed is not None:
        transformed_service = service.copy()
        transformed_service[13:15] = transformed
        try:
            replay = recompute_mutation_only_no_domain_guard_active_geometry(
                transformed_service, snapshot, step_m=1.0e-7,
            )
        except GeometryReplayError as error:
            raise SupplementalReplayError(
                f"NC21_NO_DOMAIN_GUARD_GEOMETRY:{error}"
            ) from error
        evaluation_fields = {
            "schema", "evaluator_id", "mutation_audit_only",
            "domain_guard_bypassed", "selector_or_scientific_credit",
            "service_state_29", "P_coordinates_m",
            "pad_positions_inertial_m_left_right", "target_state_13",
            "nominal_gap_m_left_right", "nominal_gap_rate_m_s_left_right",
            "centered_step_m",
            "centered_minus_P_coordinates_m_by_column",
            "centered_plus_P_coordinates_m_by_column",
            "centered_minus_gap_m_by_column",
            "centered_plus_gap_m_by_column", "raw_gap_jacobian_P",
        }
        _exact_fields(
            evaluation, evaluation_fields,
            "NC21_NO_DOMAIN_GUARD_EVALUATION_FIELDS",
        )
        if (
            evaluation.get("schema")
            != "SIM13_V4B4G_MUTATION_ONLY_NO_DOMAIN_GUARD_FK_V1"
            or evaluation.get("evaluator_id")
            != "INDEPENDENT_B601_6R2P_ACTIVE_GEOMETRY_NO_P_DOMAIN_GUARD_V1"
            or evaluation.get("mutation_audit_only") is not True
            or evaluation.get("domain_guard_bypassed") is not True
            or evaluation.get("selector_or_scientific_credit") is not False
        ):
            _fail("NC21_NO_DOMAIN_GUARD_EVALUATION_ID_OR_CREDIT")
        _close(
            evaluation.get("service_state_29"), transformed_service,
            "NC21_NO_DOMAIN_SERVICE", 0.0,
        )
        _close(
            evaluation.get("P_coordinates_m"), replay.p_coordinates_m,
            "NC21_NO_DOMAIN_P", 0.0,
        )
        _close(
            evaluation.get("pad_positions_inertial_m_left_right"),
            replay.pad_positions_inertial_m,
            "NC21_NO_DOMAIN_PAD", 1.0e-12,
        )
        _close(
            evaluation.get("target_state_13"), replay.target_state_13,
            "NC21_NO_DOMAIN_TARGET", 1.0e-12,
        )
        _close(
            evaluation.get("nominal_gap_m_left_right"),
            replay.nominal_gaps_m, "NC21_NO_DOMAIN_GAP", 1.0e-12,
        )
        _close(
            evaluation.get("nominal_gap_rate_m_s_left_right"),
            replay.nominal_gap_rates_m_s, "NC21_NO_DOMAIN_RATE", 1.0e-12,
        )
        if evaluation.get("centered_step_m") != 1.0e-7:
            _fail("NC21_NO_DOMAIN_CENTERED_STEP")
        _close(
            evaluation.get("centered_minus_P_coordinates_m_by_column"),
            replay.centered_minus_p_coordinates_m,
            "NC21_NO_DOMAIN_MINUS_P", 0.0,
        )
        _close(
            evaluation.get("centered_plus_P_coordinates_m_by_column"),
            replay.centered_plus_p_coordinates_m,
            "NC21_NO_DOMAIN_PLUS_P", 0.0,
        )
        _close(
            evaluation.get("centered_minus_gap_m_by_column"),
            replay.centered_minus_gaps_m,
            "NC21_NO_DOMAIN_MINUS_GAP", 1.0e-12,
        )
        _close(
            evaluation.get("centered_plus_gap_m_by_column"),
            replay.centered_plus_gaps_m,
            "NC21_NO_DOMAIN_PLUS_GAP", 1.0e-12,
        )
        _close(
            evaluation.get("raw_gap_jacobian_P"),
            replay.raw_gap_jacobian_p,
            "NC21_NO_DOMAIN_JACOBIAN", 1.0e-10,
        )
    else:
        if evaluation is not None:
            _fail("NC21_DIRECT_OUT_OF_DOMAIN_EVALUATION_MUST_BE_NULL")
    return {
        "branch": branch,
        "failed_side": failed_side,
        "domain_exit_reason": "P_COORDINATE_OUTSIDE_CLOSED_DOMAIN",
        "no_domain_guard_fk_executed": transformed is not None,
        "g16_policy_outcome": policy_outcome,
        "independent_g16_predicate": False,
    }


def validate_supplemental_trace(
    parent_id: str,
    subvariant_index: int,
    artifact_records: Sequence[Mapping[str, Any]],
    *,
    project_root: str | Path,
    phase_root: str | Path,
    mutation_spec: Mapping[str, Any],
    frozen_schedule: Mapping[str, Any],
    frozen_q_ref: float,
    base_payload: Mapping[str, Any],
) -> SupplementalReplayResult:
    """Validate the required authoritative trace for one receipt.

    NC17's selected-parent branch legitimately has no supplemental role; the
    fallback branch is detected by its frozen fallback contract role and then
    requires the six-lane trace.  All other parents return a no-op result.
    """

    root = Path(project_root).resolve()
    phase = Path(phase_root).resolve()
    raw_roles = [
        row.get("role") for row in artifact_records
        if isinstance(row, Mapping)
    ]
    role: str | None
    if parent_id == "B4FNC08":
        role = DWELL_ROLE
    elif parent_id == "B4FNC21":
        role = GEOMETRY_ROLE
    elif parent_id == "B4FNC17" and "FROZEN_MUTATION_FALLBACK_CONTRACT" in raw_roles:
        role = A2_ROLE
    else:
        unexpected = SUPPLEMENTAL_ROLES & set(raw_roles)
        if unexpected:
            _fail("UNEXPECTED_SUPPLEMENTAL_ROLE", sorted(unexpected))
        return SupplementalReplayResult(parent_id, subvariant_index, None, None, None, {"required": False})
    records = _record_map(artifact_records, root, phase)
    if role not in records:
        _fail("REQUIRED_SUPPLEMENTAL_ROLE_MISSING", role)
    row, path = records[role]
    payload = _load_canonical(path, role)
    if role == DWELL_ROLE:
        diagnostics = _validate_nc08(payload, subvariant_index=subvariant_index, records=records, q_ref=float(frozen_q_ref))
    elif role == A2_ROLE:
        diagnostics = _validate_nc17(payload, records=records, schedule=frozen_schedule, q_ref=float(frozen_q_ref), phase_root=phase, base_payload=base_payload)
    else:
        diagnostics = _validate_nc21(payload, subvariant_index=subvariant_index, records=records, mutation_spec=mutation_spec, base_payload=base_payload)
    return SupplementalReplayResult(
        parent_id=parent_id,
        subvariant_index=subvariant_index,
        role=role,
        artifact_path=str(path),
        artifact_sha256=str(row["sha256"]),
        diagnostics=diagnostics,
    )


__all__ = [
    "A2_ROLE", "DWELL_ROLE", "GEOMETRY_ROLE", "SUPPLEMENTAL_ROLES",
    "SupplementalReplayError", "SupplementalReplayResult",
    "validate_supplemental_trace",
]
