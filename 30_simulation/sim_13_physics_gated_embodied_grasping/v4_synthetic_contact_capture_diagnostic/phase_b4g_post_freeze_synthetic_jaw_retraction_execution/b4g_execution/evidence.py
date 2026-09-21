"""Translate one fresh solver result into the frozen B4G evidence schema."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from b4g_solver import campaign
from b4g_solver import forced_retraction as forced

from .io import (
    array_payload_sha256,
    canonical_bytes,
    canonical_sha256,
    read_json,
    sha256_file,
)


CLAIM_BOUNDARY = (
    "registered synthetic discrete-domain execution only; no physical, current-system, "
    "formal NC19, Owner, production or next-stage credit"
)

ACTIVE_NPZ_ARRAYS = (
    "time_s", "service_state_29", "target_state_13", "command_Q_14",
    "signed_W_act_J", "left_gap_m", "right_gap_m", "left_gap_rate_m_s",
    "right_gap_rate_m_s", "total_linear_momentum_N_s",
    "total_angular_momentum_N_m_s", "total_kinetic_energy_J",
    "energy_minus_work_residual_J", "ideal_constraint_power_W",
    "contact_force_N", "contact_torque_N_m", "stage_time_s", "stage_code",
    "stage_service_state_29", "stage_command_Q_14", "stage_power_W",
    "stage_P_coordinates_m", "stage_gap_jacobian_P",
    "stage_mass_cholesky_min_diagonal", "stage_domain_and_sign_pass",
)

POST_NPZ_ARRAYS = (
    "post_time_s", "post_service_state_29", "post_target_state_13",
    "post_left_gap_m", "post_right_gap_m", "post_left_gap_rate_m_s",
    "post_right_gap_rate_m_s", "post_total_linear_momentum_N_s",
    "post_total_angular_momentum_N_m_s", "post_total_kinetic_energy_J",
    "post_contact_force_N", "post_contact_torque_N_m", "post_stage_time_s",
    "post_stage_code", "post_stage_service_state_29",
    "post_stage_target_state_13", "post_stage_P_coordinates_m",
    "post_stage_gap_jacobian_P", "post_stage_domain_and_sign_pass",
)

_INTEGER_ARRAYS = {"stage_code", "post_stage_code"}
_BOOLEAN_ARRAYS = {"stage_domain_and_sign_pass", "post_stage_domain_and_sign_pass"}

_PHASE_ROOT = Path(__file__).resolve().parent.parent
_B4E_EVIDENCE_ROOT = (
    _PHASE_ROOT.parent / "phase_b4_post_freeze_synthetic_6d_solver" / "evidence"
)
_B4E_PROVENANCE_FILES = {
    "events": (
        _B4E_EVIDENCE_ROOT / "SIM13_V4B4E_EVENT_INPUTS_V1.json",
        25710,
        "FEAA39031CA73F4EC78174B53B63F9A993A7966FD26B1397C8BACD3076BDA224",
    ),
    "acquisitions": (
        _B4E_EVIDENCE_ROOT / "SIM13_V4B4E_ACQUISITION_LEDGER_V1.json",
        384551,
        "326DF1707D6B88310F441290D1D1DE34BBEB79B57453D3934CA4CF2826388B8A",
    ),
}

_FROZEN_B4E_EVENT_SOURCE = "HASH_BOUND_B3_REFERENCE_RECORD_205"
_FRESH_B3_EVENT_SOURCE = "INDEPENDENT_B3_RERUN_FIRST_QUALIFYING_SAMPLE"


def _nonnegative_float64_ulp_distance(left: Any, right: Any) -> int:
    """Return the exact binary64 ULP distance for finite nonnegative values."""

    left_value = float(left)
    right_value = float(right)
    if (
        not math.isfinite(left_value)
        or not math.isfinite(right_value)
        or left_value < 0.0
        or right_value < 0.0
    ):
        raise ValueError("B4E_TEMPLATE_ULP_INPUT_NOT_FINITE_NONNEGATIVE")
    left_bits = int(np.asarray(left_value, dtype="<f8").view("<u8"))
    right_bits = int(np.asarray(right_value, dtype="<f8").view("<u8"))
    return abs(left_bits - right_bits)


def _compare_fresh_b4e_to_frozen_template(
    *,
    lane_id: str,
    case_id: str,
    event: Mapping[str, Any],
    acquisition: Mapping[str, Any],
    loaded: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Fail closed on every parent difference outside the frozen fresh-run whitelist.

    The immutable B4E ledgers describe their source as the hash-bound parent
    record.  A genuine B3 rerun necessarily carries the independent-rerun
    source label, and two duplicated dissipation fields may differ from that
    parent record by at most two binary64 ULPs.  No other field is relaxed.
    """

    candidates = [
        row for row in loaded["events"].get("runs", [])
        if row.get("method") == event.get("method")
        and row.get("step_s") == event.get("step_s")
    ]
    if len(candidates) != 1:
        raise ValueError("B4E_EVENT_METHOD_STEP_TEMPLATE_NOT_UNIQUE")
    event_template = candidates[0]
    template_run_id = str(event_template.get("run_id"))
    if template_run_id.upper() != str(lane_id).upper():
        raise ValueError("B4E_EVENT_TEMPLATE_LANE_MISMATCH")
    acquisition_template = loaded["acquisitions"].get("runs", {}).get(
        template_run_id,
    )
    if not isinstance(acquisition_template, dict):
        raise ValueError("B4E_ACQUISITION_TEMPLATE_MISSING")
    if event.get("run_id") != case_id or acquisition.get("run_id") != case_id:
        raise ValueError("B4E_FRESH_RUN_ID_NOT_REBOUND_TO_CASE")
    if event_template.get("source") not in {
        _FROZEN_B4E_EVENT_SOURCE, _FRESH_B3_EVENT_SOURCE,
    }:
        raise ValueError("B4E_FROZEN_EVENT_SOURCE_UNEXPECTED")
    if event.get("source") != _FRESH_B3_EVENT_SOURCE:
        raise ValueError("B4E_FRESH_EVENT_SOURCE_UNEXPECTED")

    try:
        fresh_event_dissipation = event["b3_dissipation_J"]
        frozen_event_dissipation = event_template["b3_dissipation_J"]
        fresh_acquisition_dissipation = acquisition["energy_audit"]["D_B3_minus_J"]
        frozen_acquisition_dissipation = acquisition_template["energy_audit"][
            "D_B3_minus_J"
        ]
    except (KeyError, TypeError) as error:
        raise ValueError("B4E_FRESH_DISSIPATION_FIELD_MISSING") from error
    if any(
        type(value) is not float
        for value in (
            fresh_event_dissipation, frozen_event_dissipation,
            fresh_acquisition_dissipation, frozen_acquisition_dissipation,
        )
    ):
        raise ValueError("B4E_DISSIPATION_NOT_BINARY64_JSON_FLOAT")
    if int(np.asarray(fresh_event_dissipation, dtype="<f8").view("<u8")) != int(
        np.asarray(fresh_acquisition_dissipation, dtype="<f8").view("<u8")
    ):
        raise ValueError("B4E_FRESH_DISSIPATION_DUPLICATES_NOT_EXACT")
    event_ulp = _nonnegative_float64_ulp_distance(
        frozen_event_dissipation, fresh_event_dissipation,
    )
    acquisition_ulp = _nonnegative_float64_ulp_distance(
        frozen_acquisition_dissipation, fresh_acquisition_dissipation,
    )
    if event_ulp > 2 or acquisition_ulp > 2:
        raise ValueError("B4E_FRESH_DISSIPATION_EXCEEDS_TWO_ULP")

    normalized_event = dict(event)
    normalized_event.update({
        "run_id": template_run_id,
        "source": event_template["source"],
        "b3_dissipation_J": event_template["b3_dissipation_J"],
    })
    normalized_acquisition = dict(acquisition)
    normalized_acquisition["run_id"] = template_run_id
    normalized_energy = dict(normalized_acquisition.get("energy_audit", {}))
    normalized_energy["D_B3_minus_J"] = acquisition_template["energy_audit"][
        "D_B3_minus_J"
    ]
    normalized_acquisition["energy_audit"] = normalized_energy
    expected_acquisition = dict(acquisition_template)
    if "matrices" not in acquisition:
        expected_acquisition.pop("matrices", None)
    if canonical_bytes(normalized_event) != canonical_bytes(event_template):
        raise ValueError("B4E_FRESH_EVENT_UNREGISTERED_TEMPLATE_DIFFERENCE")
    if canonical_bytes(normalized_acquisition) != canonical_bytes(expected_acquisition):
        raise ValueError("B4E_FRESH_ACQUISITION_UNREGISTERED_TEMPLATE_DIFFERENCE")
    project_root = forced.b4e._project_root().resolve()
    fixed_source_bindings = {
        name: {
            "path": path.resolve().relative_to(project_root).as_posix(),
            "bytes": int(expected_bytes),
            "sha256": str(expected_sha256),
        }
        for name, (path, expected_bytes, expected_sha256)
        in _B4E_PROVENANCE_FILES.items()
    }
    return {
        "fixed_source_bindings": fixed_source_bindings,
        "allowed_pointer_differences": [
            "/event/run_id",
            "/acquisition/run_id",
            "/event/source",
            "/event/b3_dissipation_J",
            "/acquisition/energy_audit/D_B3_minus_J",
        ],
        "dissipation_comparisons": {
            "event_b3_dissipation_J": {
                "fixed": float(frozen_event_dissipation),
                "fresh": float(fresh_event_dissipation),
                "ulp_distance": event_ulp,
                "maximum_ulp": 2,
            },
            "acquisition_D_B3_minus_J": {
                "fixed": float(frozen_acquisition_dissipation),
                "fresh": float(fresh_acquisition_dissipation),
                "ulp_distance": acquisition_ulp,
                "maximum_ulp": 2,
            },
        },
        "all_other_pointers_exact": True,
        "passed": True,
    }


def _verified_b4e_acquisition_certificate_payload(
    *,
    lane_id: str,
    case_id: str,
    event: Mapping[str, Any],
    acquisition: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind one fresh case to the fixed B4E event/acquisition provenance."""

    loaded: dict[str, dict[str, Any]] = {}
    for name, (path, expected_bytes, expected_sha256) in _B4E_PROVENANCE_FILES.items():
        if (
            not path.is_file()
            or path.stat().st_size != expected_bytes
            or sha256_file(path) != expected_sha256
        ):
            raise ValueError(f"B4E_{name.upper()}_PROVENANCE_DRIFT")
        loaded[name] = read_json(path)

    published_event = dict(event)
    published_event["run_id"] = case_id
    published_acquisition = dict(acquisition)
    published_acquisition["run_id"] = case_id
    _compare_fresh_b4e_to_frozen_template(
        lane_id=lane_id,
        case_id=case_id,
        event=published_event,
        acquisition=published_acquisition,
        loaded=loaded,
    )
    return {
        "lane_id": lane_id,
        "case_id": case_id,
        "event": published_event,
        "acquisition": published_acquisition,
    }


def validate_acquisition_certificate_binding(metadata: Mapping[str, Any]) -> None:
    """Reject a missing, coordinated or source-divergent acquisition certificate."""

    event_provenance = metadata.get("event_provenance", {})
    status = metadata.get("execution_status")
    payload = event_provenance.get("acquisition_certificate_payload")
    digest = event_provenance.get("acquisition_certificate_sha256")
    if status == "NOT_EVALUATED_NO_A1_SUCCESS":
        if payload is not None or digest is not None:
            raise ValueError("NA_A2_ACQUISITION_CERTIFICATE_MUST_BE_NULL")
        return
    if status != "EXECUTED_FRESH_REGISTERED_SLOT" or not isinstance(payload, dict):
        raise ValueError("EXECUTED_ACQUISITION_CERTIFICATE_PAYLOAD_MISSING")
    if set(payload) != {"lane_id", "case_id", "event", "acquisition"}:
        raise ValueError("ACQUISITION_CERTIFICATE_PAYLOAD_KEY_SET_MISMATCH")
    if (
        payload.get("lane_id") != metadata.get("lane_id")
        or payload.get("case_id") != metadata.get("case_id")
        or payload.get("acquisition") != metadata.get("acquisition")
    ):
        raise ValueError("ACQUISITION_CERTIFICATE_METADATA_BINDING_MISMATCH")
    if digest != canonical_sha256(payload):
        raise ValueError("ACQUISITION_CERTIFICATE_SHA256_MISMATCH")
    if payload.get("event", {}).get("run_id") != metadata.get("case_id"):
        raise ValueError("ACQUISITION_CERTIFICATE_EVENT_RUN_ID_MISMATCH")
    if payload.get("acquisition", {}).get("run_id") != metadata.get("case_id"):
        raise ValueError("ACQUISITION_CERTIFICATE_ACQUISITION_RUN_ID_MISMATCH")
    verified = _verified_b4e_acquisition_certificate_payload(
        lane_id=str(metadata.get("lane_id")),
        case_id=str(metadata.get("case_id")),
        event=payload["event"],
        acquisition=payload["acquisition"],
    )
    if payload != verified:
        raise ValueError("ACQUISITION_CERTIFICATE_FIXED_PROVENANCE_MISMATCH")


def gate_record(
    gate_id: str,
    status: str,
    predicate: bool | None,
    reason: str,
    detail: Any,
) -> dict[str, Any]:
    if status not in {"PASS", "FAIL", "NOT_APPLICABLE"}:
        raise ValueError(f"INVALID_GATE_STATUS:{gate_id}:{status}")
    if status == "NOT_APPLICABLE" and predicate is not None:
        raise ValueError(f"NA_GATE_PREDICATE_MUST_BE_NULL:{gate_id}")
    return {
        "gate_id": gate_id,
        "evaluation_status": status,
        "scientific_predicate": predicate,
        "applicability_reason": reason,
        "detail": detail,
    }


def _max(values: Any, default: float = 0.0) -> float:
    array = np.asarray(values, dtype=float)
    return default if array.size == 0 else float(np.max(array))


def _finite_max_abs(values: Any, default: float = 0.0) -> tuple[float, bool]:
    """Return a conservative absolute maximum and an explicit finiteness flag."""

    array = np.asarray(values, dtype=float)
    if array.size == 0:
        return float(default), True
    finite = bool(np.all(np.isfinite(array)))
    if not finite:
        return math.inf, False
    return float(np.max(np.abs(array))), True


def _published_active_stage_rows(result: forced.ForcedRunResult) -> list[Mapping[str, Any]]:
    """Select only raw rows that belong to the accepted published trajectory.

    The frozen solver retains a full attached right-bracket step solely to find
    an off-grid clearance root.  That counterfactual suffix is not part of the
    accepted trajectory.  A domain-exit probe lacks a complete stage state by
    frozen design, so it remains verbatim in metadata rather than being padded
    or fabricated into fixed-shape NPZ arrays.
    """

    rows = list(result.stage_audits)
    if result.clearance.get("finite_event") and len(result.time_s):
        exact = [
            row for row in rows
            if str(row.get("stage_label", "")).startswith("EXACT_EVENT_RECONSTRUCTION")
            or row.get("stage_label") == "EXACT_REMOVAL_EVENT"
        ]
        if exact and len(result.time_s) >= 2:
            left_time = float(result.time_s[-2])
            prefix_end = max(
                index for index, row in enumerate(rows)
                if str(row.get("stage_label", "")).startswith("ACCEPTED_SAMPLE")
                and abs(float(row.get("time_s", math.inf)) - left_time) <= 1.0e-14
            )
            rows = rows[:prefix_end + 1] + exact
        elif not exact:
            event_time = float(result.time_s[-1])
            prefix_end = max(
                index for index, row in enumerate(rows)
                if str(row.get("stage_label", "")).startswith("ACCEPTED_SAMPLE")
                and abs(float(row.get("time_s", math.inf)) - event_time) <= 1.0e-14
            )
            rows = rows[:prefix_end + 1]
    if not result.geometry_domain_pass:
        rows = [row for row in rows if row.get("accepted") is True]
    required = (
        "time_s", "stage_code", "service_state_29", "generalized_force_14",
        "P_coordinates_m_left_right", "raw_gap_jacobian_dimensionless",
        "mass_cholesky_min_diagonal",
    )
    if any(not all(key in row for key in required) for row in rows):
        raise ValueError("PUBLISHED_ACCEPTED_STAGE_ROW_MISSING_RAW_FIELD")
    return rows


def _active_stage_arrays(result: forced.ForcedRunResult) -> dict[str, np.ndarray]:
    rows = _published_active_stage_rows(result)
    return {
        "stage_time_s": np.asarray([row["time_s"] for row in rows], dtype=float),
        "stage_code": np.asarray([row["stage_code"] for row in rows], dtype=np.int64),
        "stage_service_state_29": np.asarray(
            [row["service_state_29"] for row in rows], dtype=float,
        ).reshape((-1, 29)),
        "stage_command_Q_14": np.asarray(
            [row["generalized_force_14"] for row in rows], dtype=float,
        ).reshape((-1, 14)),
        "stage_power_W": np.asarray(
            [row.get("actuator_power_W", 0.0) for row in rows], dtype=float,
        ),
        "stage_P_coordinates_m": np.asarray(
            [row["P_coordinates_m_left_right"] for row in rows], dtype=float,
        ).reshape((-1, 2)),
        "stage_gap_jacobian_P": np.asarray(
            [row["raw_gap_jacobian_dimensionless"] for row in rows], dtype=float,
        ).reshape((-1, 2, 2)),
        "stage_mass_cholesky_min_diagonal": np.asarray(
            [row["mass_cholesky_min_diagonal"] for row in rows], dtype=float,
        ),
        "stage_domain_and_sign_pass": np.asarray([
            bool(row.get("accepted"))
            and bool(row.get("consumed_sigma_equals_raw_and_registered"))
            and bool(row.get("Q_base_and_R_exact_zero"))
            for row in rows
        ], dtype=np.bool_),
    }


def _post_arrays(post: Mapping[str, Any]) -> dict[str, np.ndarray]:
    trace = post["instrumented_trace"]
    rows = [
        row for row in trace.get("stage_audits", [])
        if all(key in row for key in (
            "time_s", "stage_code", "service_state_29", "target_state_13",
            "P_coordinates_m_left_right", "raw_gap_jacobian_dimensionless",
        ))
    ]
    return {
        "post_time_s": np.asarray(trace["time_s"], dtype=float),
        "post_service_state_29": np.asarray(trace["service_state_29"], dtype=float).reshape((-1, 29)),
        "post_target_state_13": np.asarray(trace["target_state_13"], dtype=float).reshape((-1, 13)),
        "post_left_gap_m": np.asarray(trace["left_gap_m"], dtype=float),
        "post_right_gap_m": np.asarray(trace["right_gap_m"], dtype=float),
        "post_left_gap_rate_m_s": np.asarray(trace["left_gap_rate_m_s"], dtype=float),
        "post_right_gap_rate_m_s": np.asarray(trace["right_gap_rate_m_s"], dtype=float),
        "post_total_linear_momentum_N_s": np.asarray(
            trace["total_linear_momentum_N_s"], dtype=float,
        ).reshape((-1, 3)),
        "post_total_angular_momentum_N_m_s": np.asarray(
            trace["total_angular_momentum_N_m_s"], dtype=float,
        ).reshape((-1, 3)),
        "post_total_kinetic_energy_J": np.asarray(trace["total_kinetic_energy_J"], dtype=float),
        "post_contact_force_N": np.asarray(trace["contact_force_N"], dtype=float),
        "post_contact_torque_N_m": np.asarray(trace["contact_torque_N_m"], dtype=float),
        "post_stage_time_s": np.asarray([row["time_s"] for row in rows], dtype=float),
        "post_stage_code": np.asarray([row["stage_code"] for row in rows], dtype=np.int64),
        "post_stage_service_state_29": np.asarray(
            [row["service_state_29"] for row in rows], dtype=float,
        ).reshape((-1, 29)),
        "post_stage_target_state_13": np.asarray(
            [row["target_state_13"] for row in rows], dtype=float,
        ).reshape((-1, 13)),
        "post_stage_P_coordinates_m": np.asarray(
            [row["P_coordinates_m_left_right"] for row in rows], dtype=float,
        ).reshape((-1, 2)),
        "post_stage_gap_jacobian_P": np.asarray(
            [row["raw_gap_jacobian_dimensionless"] for row in rows], dtype=float,
        ).reshape((-1, 2, 2)),
        "post_stage_domain_and_sign_pass": np.asarray([
            bool(row.get("accepted"))
            and bool(row.get("consumed_sigma_equals_raw_and_registered"))
            for row in rows
        ], dtype=np.bool_),
    }


def result_npz_arrays(result: forced.ForcedRunResult) -> dict[str, np.ndarray]:
    target = np.concatenate((
        result.target_position_m,
        result.target_quaternion_wxyz,
        result.target_twist_mixed,
    ), axis=1) if len(result.time_s) else np.empty((0, 13))
    arrays: dict[str, np.ndarray] = {
        "time_s": np.asarray(result.time_s, dtype=float),
        "service_state_29": np.asarray(result.state_30[:, :29], dtype=float).reshape((-1, 29)),
        "target_state_13": np.asarray(target, dtype=float).reshape((-1, 13)),
        "command_Q_14": np.asarray(result.command_q_14, dtype=float).reshape((-1, 14)),
        "signed_W_act_J": np.asarray(result.signed_work_j, dtype=float),
        "left_gap_m": np.asarray(result.left_gap_m, dtype=float),
        "right_gap_m": np.asarray(result.right_gap_m, dtype=float),
        "left_gap_rate_m_s": np.asarray(result.left_gap_rate_m_s, dtype=float),
        "right_gap_rate_m_s": np.asarray(result.right_gap_rate_m_s, dtype=float),
        "total_linear_momentum_N_s": np.asarray(
            result.total_linear_momentum_n_s, dtype=float,
        ).reshape((-1, 3)),
        "total_angular_momentum_N_m_s": np.asarray(
            result.total_angular_momentum_n_m_s, dtype=float,
        ).reshape((-1, 3)),
        "total_kinetic_energy_J": np.asarray(result.total_kinetic_energy_j, dtype=float),
        "energy_minus_work_residual_J": np.asarray(
            result.sample_ledgers["energy_minus_work_residual_J"], dtype=float,
        ),
        "ideal_constraint_power_W": np.asarray(
            result.sample_ledgers["ideal_constraint_power_W"], dtype=float,
        ),
        "contact_force_N": np.asarray(
            result.sample_ledgers["active_contact_force_N"], dtype=float,
        ),
        "contact_torque_N_m": np.asarray(
            result.sample_ledgers["active_contact_torque_N_m"], dtype=float,
        ),
    }
    arrays.update(_active_stage_arrays(result))
    if result.post_release is not None:
        arrays.update(_post_arrays(result.post_release))
    return arrays


def _clearance_certificate_payload(result: forced.ForcedRunResult) -> dict[str, Any]:
    """Recompute the complete all-root certificate from the published raw trace.

    The frozen B4E routine returns only the qualifying interval when it finds a
    finite event.  Publication additionally needs *all* certified intervals so
    an independent validator can compare the complete partition.  Recomputing
    here also removes the counterfactual right bracket from that certificate.
    """

    algorithm = "PIECEWISE_CUBIC_HERMITE_ALL_ROOT_PARTITION_EARLIEST_DWELL"
    time = np.asarray(result.time_s, dtype=float)
    if len(time) < 2:
        return {
            "finite_event": False,
            "tau_c_s": None,
            "removal_time_s": None,
            "certified_good_intervals_s": [],
            "algorithm": algorithm,
            "endpoint_only": False,
        }

    p = np.asarray(result.state_30[:, 13:15], dtype=float)
    linear = np.asarray(result.total_linear_momentum_n_s, dtype=float)
    angular = np.asarray(result.total_angular_momentum_n_m_s, dtype=float)
    ledgers = result.sample_ledgers
    sample_good = (
        np.all((p >= 0.0) & (p <= 0.0715), axis=1)
        & (np.linalg.norm(linear - linear[0], axis=1) <= 1.0e-9)
        & (np.linalg.norm(angular - angular[0], axis=1) <= 1.0e-9)
        & (np.abs(np.asarray(ledgers["energy_minus_work_residual_J"])) <= 1.0e-7)
        & (np.abs(np.asarray(ledgers["ideal_constraint_power_W"])) <= 1.0e-10)
        & (np.abs(np.asarray(ledgers["active_contact_force_N"])) <= 1.0e-12)
        & (np.abs(np.asarray(ledgers["active_contact_torque_N_m"])) <= 1.0e-12)
    )
    command_zero = np.all(np.asarray(result.command_q_14) == 0.0, axis=1)
    acquisition = float(result.event.time_s)
    command_end = float(result.command.end_time_s(acquisition))
    interval_certified = (
        sample_good[:-1]
        & sample_good[1:]
        & command_zero[:-1]
        & command_zero[1:]
        & (time[:-1] >= command_end - 1.0e-12)
    )
    good: list[tuple[float, float]] = []
    for index, certified in enumerate(interval_certified):
        step = float(time[index + 1] - time[index])
        left_coeff = forced.b4e._hermite_coefficients(
            float(result.left_gap_m[index]), float(result.left_gap_m[index + 1]),
            float(result.left_gap_rate_m_s[index]), float(result.left_gap_rate_m_s[index + 1]),
            step,
        )
        right_coeff = forced.b4e._hermite_coefficients(
            float(result.right_gap_m[index]), float(result.right_gap_m[index + 1]),
            float(result.right_gap_rate_m_s[index]), float(result.right_gap_rate_m_s[index + 1]),
            step,
        )
        good.extend(forced.b4e._segment_good_intervals(
            float(time[index]), float(time[index + 1]), left_coeff, right_coeff,
            ledger_interval_certified=bool(certified),
        ))
    merged = forced.b4e._merge_intervals(good)
    eligible_start = max(acquisition, command_end - 0.001) + 0.001
    payload: dict[str, Any] = {
        "finite_event": False,
        "tau_c_s": None,
        "removal_time_s": None,
        "certified_good_intervals_s": merged,
        "algorithm": algorithm,
        "endpoint_only": False,
    }
    for lower, upper in merged:
        tau_c = max(float(lower), eligible_start)
        if float(upper) - tau_c >= 0.001 - 1.0e-12:
            payload.update({
                "finite_event": True,
                "tau_c_s": tau_c,
                "removal_time_s": tau_c + 0.001,
                "certified_good_interval_s": [float(lower), float(upper)],
            })
            break

    frozen_finite = bool(result.clearance.get("finite_event"))
    if bool(payload["finite_event"]) is not frozen_finite:
        raise ValueError("PUBLISHED_CLEARANCE_RECOMPUTATION_OUTCOME_MISMATCH")
    if frozen_finite and abs(
        float(payload["removal_time_s"]) - float(result.clearance["removal_time_s"])
    ) > 1.0e-12:
        raise ValueError("PUBLISHED_CLEARANCE_RECOMPUTATION_REMOVAL_TIME_MISMATCH")
    return payload


def validate_case_npz_schema(path: Path, metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the exact frozen array set, native shapes/dtypes, finiteness and payload."""

    finite_event = bool(metadata["responses"].get("finite_removal_event"))
    expected = set(ACTIVE_NPZ_ARRAYS) | (set(POST_NPZ_ARRAYS) if finite_event else set())
    with np.load(path, allow_pickle=False) as archive:
        observed = set(archive.files)
        if observed != expected:
            raise ValueError(
                f"NPZ_EXACT_ARRAY_SET_MISMATCH:missing={sorted(expected-observed)}:extra={sorted(observed-expected)}"
            )
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    for name, value in arrays.items():
        if name in _BOOLEAN_ARRAYS:
            if value.dtype.str != "|b1":
                raise ValueError(f"NPZ_BOOL_DTYPE_MISMATCH:{name}:{value.dtype.str}")
        elif name in _INTEGER_ARRAYS:
            if value.dtype.str != "<i8":
                raise ValueError(f"NPZ_INT64_NOT_LITTLE_ENDIAN:{name}:{value.dtype.str}")
        elif value.dtype.str != "<f8":
            raise ValueError(f"NPZ_FLOAT64_NOT_LITTLE_ENDIAN:{name}:{value.dtype.str}")
        if value.dtype.kind == "f" and not np.all(np.isfinite(value)):
            raise ValueError(f"NPZ_NONFINITE_VALUE:{name}")

    n = arrays["time_s"].shape[0]
    s = arrays["stage_time_s"].shape[0]
    shapes = {
        "time_s": (n,), "service_state_29": (n, 29), "target_state_13": (n, 13),
        "command_Q_14": (n, 14), "signed_W_act_J": (n,), "left_gap_m": (n,),
        "right_gap_m": (n,), "left_gap_rate_m_s": (n,), "right_gap_rate_m_s": (n,),
        "total_linear_momentum_N_s": (n, 3), "total_angular_momentum_N_m_s": (n, 3),
        "total_kinetic_energy_J": (n,), "energy_minus_work_residual_J": (n,),
        "ideal_constraint_power_W": (n,), "contact_force_N": (n,), "contact_torque_N_m": (n,),
        "stage_time_s": (s,), "stage_code": (s,), "stage_service_state_29": (s, 29),
        "stage_command_Q_14": (s, 14), "stage_power_W": (s,),
        "stage_P_coordinates_m": (s, 2), "stage_gap_jacobian_P": (s, 2, 2),
        "stage_mass_cholesky_min_diagonal": (s,), "stage_domain_and_sign_pass": (s,),
    }
    if finite_event:
        m = arrays["post_time_s"].shape[0]
        u = arrays["post_stage_time_s"].shape[0]
        shapes.update({
            "post_time_s": (m,), "post_service_state_29": (m, 29),
            "post_target_state_13": (m, 13), "post_left_gap_m": (m,),
            "post_right_gap_m": (m,), "post_left_gap_rate_m_s": (m,),
            "post_right_gap_rate_m_s": (m,), "post_total_linear_momentum_N_s": (m, 3),
            "post_total_angular_momentum_N_m_s": (m, 3), "post_total_kinetic_energy_J": (m,),
            "post_contact_force_N": (m,), "post_contact_torque_N_m": (m,),
            "post_stage_time_s": (u,), "post_stage_code": (u,),
            "post_stage_service_state_29": (u, 29), "post_stage_target_state_13": (u, 13),
            "post_stage_P_coordinates_m": (u, 2), "post_stage_gap_jacobian_P": (u, 2, 2),
            "post_stage_domain_and_sign_pass": (u,),
        })
    for name, expected_shape in shapes.items():
        if arrays[name].shape != expected_shape:
            raise ValueError(f"NPZ_NATIVE_SHAPE_MISMATCH:{name}:{arrays[name].shape}:{expected_shape}")
    if int(metadata["responses"]["sample_count"]) != n:
        raise ValueError("NPZ_SAMPLE_COUNT_METADATA_MISMATCH")
    if sorted(metadata.get("npz_arrays", [])) != sorted(expected):
        raise ValueError("NPZ_METADATA_ARRAY_SET_MISMATCH")
    payload_sha = array_payload_sha256(arrays)
    if payload_sha != metadata.get("numeric_payload_sha256"):
        raise ValueError("NPZ_NUMERIC_PAYLOAD_SHA256_MISMATCH")
    return {
        "array_count": len(arrays),
        "active_sample_count": n,
        "active_stage_count": s,
        "post_release_present": finite_event,
        "numeric_payload_sha256": payload_sha,
        "pass": True,
    }


def _command_parameters(result: forced.ForcedRunResult, q_ref_n: float) -> dict[str, Any]:
    return {
        "Q_ref_per_finger_N": float(q_ref_n),
        "only_nonzero_generalized_force_indices_zero_based": [12, 13],
        "left": {
            "alpha": result.command.left.alpha,
            "delay_s": result.command.left.delay_s,
            "duration_s": result.command.left.duration_s,
        },
        "right": {
            "alpha": result.command.right.alpha,
            "delay_s": result.command.right.delay_s,
            "duration_s": result.command.right.duration_s,
        },
        "physical_actuator_force_capacity_N": None,
    }


def _command_path_pass(result: forced.ForcedRunResult, q_ref_n: float) -> bool:
    if len(result.time_s) == 0:
        return True
    expected = np.asarray([
        forced.force_vector(
            result.command, time, result.acquisition.acquisition_time_s,
            q_ref_n, forced.REGISTERED_OPENING_SIGNS,
        )
        for time in result.time_s
    ])
    return bool(
        np.all(result.command_q_14[:, :12] == 0.0)
        and np.array_equal(expected, result.command_q_14)
    )


def _removal_mapping_pass(post: Mapping[str, Any]) -> tuple[bool, dict[str, Any]]:
    mapping = post["mapping"]
    maxima = mapping["native_velocity_jump_maxima"]
    z_before = np.asarray(mapping["z_before"], dtype=float)
    z_after = np.asarray(mapping["z_after"], dtype=float)
    linear_impulse = np.asarray(mapping["linear_impulse_N_s"], dtype=float)
    angular_impulse = np.asarray(mapping["angular_impulse_N_m_s"], dtype=float)
    kinetic_jump = float(mapping["kinetic_energy_jump_J"])
    stored_energy = float(mapping["ideal_constraint_stored_energy_J"])
    passed = bool(
        all(math.isfinite(float(value)) and abs(float(value)) <= 1.0e-12 for value in maxima.values())
        and np.array_equal(z_before, z_after)
        and np.all(np.isfinite(linear_impulse))
        and np.linalg.norm(linear_impulse) <= 1.0e-12
        and np.all(np.isfinite(angular_impulse))
        and np.linalg.norm(angular_impulse) <= 1.0e-12
        and math.isfinite(kinetic_jump) and abs(kinetic_jump) <= 1.0e-12
        and stored_energy == 0.0
    )
    return passed, {
        "native_velocity_jump_maxima": maxima,
        "linear_impulse_N_s": mapping["linear_impulse_N_s"],
        "angular_impulse_N_m_s": mapping["angular_impulse_N_m_s"],
        "kinetic_energy_jump_J": mapping["kinetic_energy_jump_J"],
        "ideal_constraint_stored_energy_J": mapping["ideal_constraint_stored_energy_J"],
    }


def case_gate_records(
    result: forced.ForcedRunResult,
    *,
    arm: str,
    q_ref_n: float,
    a0_comparison: Mapping[str, Any] | None,
    clearance_payload: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ledgers = result.sample_ledgers
    work = (
        campaign.work_quadrature_audit(result)
        if len(result.time_s) >= 2
        else {
            "augmented_signed_work_J": 0.0,
            "native_composite_trapezoid_J": 0.0,
            "every_second_sample_composite_trapezoid_J": 0.0,
            "native_absolute_error_J": 0.0,
            "every_second_absolute_error_J": 0.0,
            "native_absolute_error_limit_J": 1.0e-7,
            "refinement_slack_J": 1.0e-15,
            "passed": True,
            "classification": "TRIVIAL_NO_ACCEPTED_INTERVAL_BEFORE_FAIL_CLOSED_DOMAIN_EXIT",
        }
    )
    p_only = bool(np.all(result.command_q_14[:, :12] == 0.0))
    energy, active_energy_finite = _finite_max_abs(
        ledgers["energy_minus_work_residual_J"],
    )
    momentum = {
        "linear_momentum_drift_N_s": _max(ledgers["linear_momentum_drift_N_s"]),
        "angular_momentum_drift_N_m_s": _max(ledgers["angular_momentum_drift_N_m_s"]),
    }
    contact = {
        "active_contact_force_N": _max(ledgers["active_contact_force_N"]),
        "active_contact_torque_N_m": _max(ledgers["active_contact_torque_N_m"]),
    }
    if result.post_release is not None:
        post_max = result.post_release["maxima"]
        momentum["post_linear_momentum_drift_N_s"] = post_max["linear_momentum_drift_N_s"]
        momentum["post_angular_momentum_drift_N_m_s"] = post_max["angular_momentum_drift_N_m_s"]
        contact["post_contact_force_N"] = post_max["contact_force_N"]
        contact["post_contact_torque_N_m"] = post_max["contact_torque_N_m"]
    momentum_pass = bool(
        momentum["linear_momentum_drift_N_s"] <= 1.0e-9
        and momentum["angular_momentum_drift_N_m_s"] <= 1.0e-9
        and momentum.get("post_linear_momentum_drift_N_s", 0.0) <= 1.0e-9
        and momentum.get("post_angular_momentum_drift_N_m_s", 0.0) <= 1.0e-9
    )
    post_energy = (
        None
        if result.post_release is None
        else float(result.post_release["maxima"]["energy_drift_J"])
    )
    post_energy_finite = post_energy is None or math.isfinite(post_energy)
    energy_pass = bool(
        active_energy_finite
        and energy <= 1.0e-7
        and post_energy_finite
        and (post_energy is None or abs(post_energy) <= 1.0e-7)
    )
    contact_pass = bool(all(float(value) <= 1.0e-12 for value in contact.values()))
    command_pass = _command_path_pass(result, q_ref_n)
    records: list[dict[str, Any]] = []
    if arm == "A0":
        a0_pass = bool(
            a0_comparison and a0_comparison.get("passed")
            and not clearance_payload.get("finite_event")
        )
        records.append(gate_record(
            "B4F-G02-A0-EXACT-REPLAY", "PASS" if a0_pass else "FAIL", a0_pass,
            "A0_EXECUTED_SENTINEL",
            {"comparison": a0_comparison, "finite_removal": result.synthetic_removal_executed},
        ))
    records.extend([
        gate_record(
            "B4F-G03-P-ONLY-INTERNAL-GENERALIZED-FORCE",
            "PASS" if p_only else "FAIL", p_only, "EXECUTED_CASE",
            {"Q_shape": 14, "allowed_nonzero_indices": [12, 13]},
        ),
        gate_record(
            "B4F-G04-ACTUATOR-WORK-LEDGER",
            "PASS" if work["passed"] else "FAIL", bool(work["passed"]), "EXECUTED_CASE",
            work,
        ),
        gate_record(
            "B4F-G05-P-H-CONSERVATION",
            "PASS" if momentum_pass else "FAIL", momentum_pass, "EXECUTED_CASE", momentum,
        ),
        gate_record(
            "B4F-G06-ENERGY-MINUS-WORK-IDENTITY",
            "PASS" if energy_pass else "FAIL", energy_pass, "EXECUTED_CASE",
            {
                "active_max_residual_J": energy,
                "active_residual_all_finite": active_energy_finite,
                "post_max_energy_drift_J": (
                    None if post_energy is None else abs(post_energy)
                ),
                "post_energy_drift_finite": post_energy_finite,
            },
        ),
        gate_record(
            "B4F-G07-CONTACT-CONSTRAINT-MUTUAL-EXCLUSION",
            "PASS" if contact_pass else "FAIL", contact_pass, "EXECUTED_CASE", contact,
        ),
        gate_record(
            "B4F-G08-COMMAND-ZERO-BEFORE-REMOVAL",
            "PASS" if command_pass else "FAIL", command_pass, "EXECUTED_CASE",
            {"exact_profile_and_zero_outside_support": command_pass},
        ),
    ])
    if not result.geometry_domain_pass:
        records.append(gate_record(
            "B4F-G09-CONTINUOUS-BILATERAL-CLEARANCE", "NOT_APPLICABLE", None,
            "CASE_TERMINATED_GEOMETRY_BEFORE_OUTCOME", result.failure,
        ))
    else:
        records.append(gate_record(
            "B4F-G09-CONTINUOUS-BILATERAL-CLEARANCE", "PASS",
            bool(clearance_payload.get("finite_event")), "EXECUTED_OUTCOME_GATE",
            {"clearance": dict(clearance_payload), "negative_outcome_is_execution_failure": False},
        ))
    if clearance_payload.get("finite_event") and result.post_release is not None:
        mapping_pass, mapping_detail = _removal_mapping_pass(result.post_release)
        records.append(gate_record(
            "B4F-G10-EXACT-ZERO-JUMP-REMOVAL", "PASS" if mapping_pass else "FAIL",
            mapping_pass, "CERTIFIED_FINITE_REMOVAL_EVENT", mapping_detail,
        ))
        post_pass = bool(result.post_release.get("post_release_passed"))
        records.append(gate_record(
            "B4F-G11-INDEPENDENT-POST-RELEASE-5MS", "PASS" if post_pass else "FAIL",
            post_pass, "CERTIFIED_FINITE_REMOVAL_EVENT",
            {"terminal_status": result.post_release.get("terminal_status"), "maxima": result.post_release.get("maxima"), "parent_b4e_crosscheck": result.post_release.get("parent_b4e_crosscheck")},
        ))
    elif not clearance_payload.get("finite_event"):
        reason = (
            "CASE_TERMINATED_GEOMETRY_BEFORE_EVENT"
            if not result.geometry_domain_pass else "NO_FINITE_REMOVAL_EVENT"
        )
        records.extend([
            gate_record("B4F-G10-EXACT-ZERO-JUMP-REMOVAL", "NOT_APPLICABLE", None, reason, {"finite_removal": False}),
            gate_record("B4F-G11-INDEPENDENT-POST-RELEASE-5MS", "NOT_APPLICABLE", None, reason, {"finite_removal": False}),
        ])
    else:
        records.extend([
            gate_record(
                "B4F-G10-EXACT-ZERO-JUMP-REMOVAL", "FAIL", False,
                "CERTIFIED_FINITE_REMOVAL_EVENT", {"post_release_mapping_missing": True},
            ),
            gate_record(
                "B4F-G11-INDEPENDENT-POST-RELEASE-5MS", "FAIL", False,
                "CERTIFIED_FINITE_REMOVAL_EVENT", {"post_release_evidence_missing": True},
            ),
        ])
    records.append(gate_record(
        "B4F-G16-SYNTHETIC-GEOMETRY-DOMAIN", "PASS",
        bool(result.geometry_domain_pass), "FAIL_CLOSED_DOMAIN_DETECTOR_EVALUATED",
        {
            "geometry_domain_pass": result.geometry_domain_pass,
            "failure": result.failure,
            "active_stage_audit_count": len(result.stage_audits),
            "post_stage_audit_count": 0 if result.post_release is None else result.post_release.get("post_release_stage_audit_count", 0),
            "domain_exit_is_valid_registered_case_outcome": True,
        },
    ))
    metrics = {
        "work_quadrature": work,
        "momentum": momentum,
        "energy_minus_work_max_residual_J": energy,
        "energy_minus_work_residual_all_finite": active_energy_finite,
        "contact": contact,
        "command_path_pass": command_pass,
    }
    return records, metrics


def executed_case_payload(
    result: forced.ForcedRunResult,
    *,
    slot: Mapping[str, Any],
    execution_ordinal: int,
    q_ref_n: float,
    source_hashes: Mapping[str, Any],
    a0_comparison: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    arrays = result_npz_arrays(result)
    clearance_payload = _clearance_certificate_payload(result)
    gates, gate_metrics = case_gate_records(
        result,
        arm=str(slot["arm"]),
        q_ref_n=q_ref_n,
        a0_comparison=a0_comparison,
        clearance_payload=clearance_payload,
    )
    event_json = forced.b4e.event_to_json(result.event)
    acquisition_json = forced.b4e.acquisition_to_json(
        result.acquisition, include_matrices=True,
    )
    acquisition_certificate_payload = _verified_b4e_acquisition_certificate_payload(
        lane_id=str(slot["lane_id"]),
        case_id=str(slot["case_id"]),
        event=event_json,
        acquisition=acquisition_json,
    )
    event_json = acquisition_certificate_payload["event"]
    acquisition_json = acquisition_certificate_payload["acquisition"]
    acquisition_certificate = canonical_sha256(acquisition_certificate_payload)
    clearance_certificate = canonical_sha256({
        "lane_id": slot["lane_id"], "case_id": slot["case_id"],
        "clearance": clearance_payload,
    })
    initial_opening = next((
        row for row in result.stage_audits
        if row.get("stage_label") == "ACCEPTED_SAMPLE_0"
    ), {})
    responses = {
        "sample_count": len(result.time_s),
        "active_end_time_s": None if len(result.time_s) == 0 else float(result.time_s[-1]),
        "synthetic_removal_executed": bool(result.synthetic_removal_executed),
        "finite_removal_event": bool(result.clearance.get("finite_event")),
        "removal_time_s": result.clearance.get("removal_time_s"),
        "post_release_passed": bool(result.post_release and result.post_release.get("post_release_passed")),
        "clearance_certificate_payload": clearance_payload,
        "post_signed_W_act_carried_constant_J": (
            None
            if not clearance_payload.get("finite_event")
            else float(result.signed_work_j[-1])
        ),
        "post_actuator_work_reset_on_removal": (
            None if not clearance_payload.get("finite_event") else False
        ),
        "post_release_generalized_force_14": (
            None if not clearance_payload.get("finite_event") else [0.0] * 14
        ),
        "signed_work_terminal_J": 0.0 if len(result.signed_work_j) == 0 else float(result.signed_work_j[-1]),
        "left_gap_terminal_m": None if len(result.left_gap_m) == 0 else float(result.left_gap_m[-1]),
        "right_gap_terminal_m": None if len(result.right_gap_m) == 0 else float(result.right_gap_m[-1]),
        "a0_replay_comparison": a0_comparison,
        "gate_metrics": gate_metrics,
        "selector_case_integrity_pass": bool(
            result.geometry_domain_pass
            and all(
                record["evaluation_status"] != "FAIL"
                for record in gates
                if record["gate_id"] not in {"B4F-G09-CONTINUOUS-BILATERAL-CLEARANCE"}
            )
        ),
    }
    payload = {
        "schema": "SIM13_V4B4G_CASE_METADATA_V1",
        "slot_index": int(slot["slot_index"]),
        "execution_ordinal": int(execution_ordinal),
        "registered_slot": dict(slot),
        "case_id": slot["case_id"],
        "lane_id": slot["lane_id"],
        "arm": slot["arm"],
        "execution_status": "EXECUTED_FRESH_REGISTERED_SLOT",
        "terminal_status": result.terminal_status,
        "source_hashes": dict(source_hashes),
        "acquisition": acquisition_json,
        "event_provenance": {
            "lane_id": slot["lane_id"],
            "fresh_b3_reconstruction": True,
            "first_qualifying_event_index": int(result.event.index),
            "acquisition_time_s": float(result.event.time_s),
            "acquisition_certificate_payload": acquisition_certificate_payload,
            "acquisition_certificate_sha256": acquisition_certificate,
            "clearance_certificate_sha256": clearance_certificate,
            "removal_time_s": result.clearance.get("removal_time_s"),
        },
        "command_parameters": _command_parameters(result, q_ref_n),
        "geometry_domain": {
            "P_coordinate_m_closed_interval_left_right": [[0.0, 0.0715], [0.0, 0.0715]],
            "passed": bool(result.geometry_domain_pass),
            "clipping_or_extrapolation_used": False,
            "failure": result.failure,
            "failure_probe_source": (
                "FROZEN_SOLVER_DOMAINEXIT_RECORD"
                if result.failure is not None else None
            ),
            "failure_probe_published_in_fixed_shape_npz": False,
            "published_stage_rows_are_raw_pre_failure_only": (
                not result.geometry_domain_pass
            ),
        },
        "opening_sign": {
            "registered_left_right": [1, 1],
            "initial_recomputed_left_right": initial_opening.get("opening_sign_left_right"),
            "all_consumed_signs_bound_to_raw_and_registered": bool(
                all(
                    row.get("consumed_sigma_equals_raw_and_registered", True)
                    for row in result.stage_audits
                )
            ),
        },
        "responses": responses,
        "gate_records": gates,
        "numeric_payload_sha256": array_payload_sha256(arrays),
        "npz_path": None,
        "npz_bytes": None,
        "npz_sha256": None,
        "npz_arrays": sorted(arrays),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    validate_acquisition_certificate_binding(payload)
    return payload, arrays


def not_evaluated_a2_payload(
    *,
    slot: Mapping[str, Any],
    execution_ordinal: int,
    source_hashes: Mapping[str, Any],
) -> dict[str, Any]:
    reason = "A2_NOT_EVALUATED_NO_A1_PARENT"
    gates = [
        gate_record(gate_id, "NOT_APPLICABLE", None, reason, {"selected_parent": None})
        for gate_id in (
            "B4F-G03-P-ONLY-INTERNAL-GENERALIZED-FORCE",
            "B4F-G04-ACTUATOR-WORK-LEDGER",
            "B4F-G05-P-H-CONSERVATION",
            "B4F-G06-ENERGY-MINUS-WORK-IDENTITY",
            "B4F-G07-CONTACT-CONSTRAINT-MUTUAL-EXCLUSION",
            "B4F-G08-COMMAND-ZERO-BEFORE-REMOVAL",
            "B4F-G09-CONTINUOUS-BILATERAL-CLEARANCE",
            "B4F-G10-EXACT-ZERO-JUMP-REMOVAL",
            "B4F-G11-INDEPENDENT-POST-RELEASE-5MS",
            "B4F-G16-SYNTHETIC-GEOMETRY-DOMAIN",
        )
    ]
    payload = {
        "schema": "SIM13_V4B4G_CASE_METADATA_V1",
        "slot_index": int(slot["slot_index"]),
        "execution_ordinal": int(execution_ordinal),
        "registered_slot": dict(slot),
        "case_id": slot["case_id"],
        "lane_id": slot["lane_id"],
        "arm": "A2",
        "execution_status": "NOT_EVALUATED_NO_A1_SUCCESS",
        "terminal_status": "NOT_EVALUATED_NO_A1_SUCCESS",
        "source_hashes": dict(source_hashes),
        "acquisition": {"status": "NOT_EVALUATED", "acquisition_time_s": None},
        "event_provenance": {
            "lane_id": slot["lane_id"],
            "fresh_b3_reconstruction": False,
            "first_qualifying_event_index": None,
            "acquisition_time_s": None,
            "acquisition_certificate_payload": None,
            "acquisition_certificate_sha256": None,
            "clearance_certificate_sha256": None,
            "removal_time_s": None,
        },
        "command_parameters": {"selected_parent": None, "variant_id": slot["variant_id"]},
        "geometry_domain": {"status": "NOT_EVALUATED", "passed": None},
        "opening_sign": {"status": "NOT_EVALUATED", "registered_left_right": [1, 1]},
        "responses": {"synthetic_removal_executed": False, "finite_removal_event": False, "selector_case_integrity_pass": False},
        "gate_records": gates,
        "numeric_payload_sha256": None,
        "npz_path": None,
        "npz_bytes": None,
        "npz_sha256": None,
        "npz_arrays": [],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    validate_acquisition_certificate_binding(payload)
    return payload


def compare_a2_mirror_pair(
    left_meta: Mapping[str, Any],
    right_meta: Mapping[str, Any],
    left_npz: Path,
    right_npz: Path,
) -> dict[str, Any]:
    with np.load(left_npz, allow_pickle=False) as left, np.load(right_npz, allow_pickle=False) as right:
        left_relative = left["time_s"] - float(left_meta["event_provenance"]["acquisition_time_s"])
        right_relative = right["time_s"] - float(right_meta["event_provenance"]["acquisition_time_s"])
        full_relative_grid_equal = bool(np.array_equal(left_relative, right_relative))
        common = left_relative if full_relative_grid_equal else np.intersect1d(
            left_relative, right_relative, assume_unique=True,
        )
        missing = not full_relative_grid_equal
        if missing:
            gap = gap_rate = work = math.inf
        else:
            gap = float(max(
                np.max(np.abs(left["left_gap_m"] - right["right_gap_m"])),
                np.max(np.abs(left["right_gap_m"] - right["left_gap_m"])),
            ))
            gap_rate = float(max(
                np.max(np.abs(left["left_gap_rate_m_s"] - right["right_gap_rate_m_s"])),
                np.max(np.abs(left["right_gap_rate_m_s"] - right["left_gap_rate_m_s"])),
            ))
            work = abs(float(left["signed_W_act_J"][-1]) - float(right["signed_W_act_J"][-1]))
    outcome_parity = (
        left_meta["responses"]["finite_removal_event"]
        == right_meta["responses"]["finite_removal_event"]
        and left_meta["terminal_status"] == right_meta["terminal_status"]
    )
    predicate = bool(
        not missing and gap <= 1.0e-9 and gap_rate <= 1.0e-9
        and work <= 1.0e-9 and outcome_parity
    )
    return {
        "evaluation_status": "PASS",
        "scientific_predicate": predicate,
        "common_relative_sample_count": int(len(common)),
        "left_relative_sample_count": int(len(left_relative)),
        "right_relative_sample_count": int(len(right_relative)),
        "full_relative_grid_equal": full_relative_grid_equal,
        "missing_exact_common_grid": missing,
        "direct_left_right_swapped_gap_residual_m": None if not math.isfinite(gap) else gap,
        "direct_left_right_swapped_gap_rate_residual_m_s": None if not math.isfinite(gap_rate) else gap_rate,
        "signed_work_terminal_common_interval_residual_J": None if not math.isfinite(work) else work,
        "outcome_parity": outcome_parity,
        "baseline_correction_or_fitted_transform_used": False,
    }
