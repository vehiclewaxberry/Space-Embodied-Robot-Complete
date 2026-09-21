"""Deterministic synthetic source-only fixtures for tests and mutation controls.

All callers supply a temporary project root.  Nothing is written to the
package's evidence tree and no physical state is advanced.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
from typing import Any, Callable

import numpy as np

from .adapter import (
    COMMON_DONOR_HASHES,
    COMMON_GROUP_SHA256,
    DONOR_PAYLOAD_SHA256,
    OUTCOME_A0,
    OUTCOME_COMMON,
    OUTCOME_FINITE,
    OUTCOME_NO_REMOVAL,
    common_donor_projection,
)
from .array_contract import ARRAY_CONTRACT_DOCUMENT_SHA256, OUTCOME_TO_PROFILE, PROFILE_SHA256
from .schedule_binding import expected_binding


ArrayMutator = Callable[[dict[str, np.ndarray]], None]
SidecarMutator = Callable[[dict[str, Any]], None]


def _times(step_s: float, horizon_s: float, *, finite: bool) -> np.ndarray:
    count = int(horizon_s // step_s)
    values = [index * step_s for index in range(count + 1)]
    if values[-1] < horizon_s - 1e-15:
        if not finite:
            raise ValueError("NO_EVENT_FIXTURE_HORIZON_MUST_BE_EXACT_NOMINAL_GRID")
        values.append(horizon_s)
    elif abs(values[-1] - horizon_s) <= 1e-15:
        values[-1] = horizon_s
    return np.asarray(values, dtype="<f8")


def build_arrays(
    *, method: str, step_s: float, outcome: str, horizon_s: float,
) -> dict[str, np.ndarray]:
    finite = outcome == OUTCOME_FINITE
    a0 = outcome == OUTCOME_A0
    common = outcome == OUTCOME_COMMON
    donor = common_donor_projection() if common else None
    relative_time = _times(step_s, horizon_s, finite=finite)
    time = np.asarray(relative_time + (donor.acquisition_time_s if donor else 0.0), dtype="<f8")
    n = time.size
    stages_per_step = 4 if method == "rk4" else 2
    s = stages_per_step * (n - 1)
    service = np.zeros((n, 29), dtype="<f8")
    if donor:
        service[:] = np.asarray(donor.service_state_29, dtype="<f8")
        service[:, 0] += relative_time
    else:
        service[:, 3] = 1.0
        service[:, 0] = time
        service[:, 13:15] = 0.03
        service[:, 15] = 1.0
        service[:, 27] = 2.0
    target = np.zeros((n, 13), dtype="<f8")
    if donor:
        target[:] = np.asarray(donor.target_state_13, dtype="<f8")
        target[:, 0] += relative_time
    else:
        target[:, 3] = 1.0
        target[:, 0] = 1.0 + time
        target[:, 7] = 1.0
    command = np.zeros((n, 14), dtype="<f8")
    if not a0:
        command[:, 12] = 1.0
    saved_work = np.zeros(n, dtype="<f8") if a0 else 2.0 * (time - time[0])

    stage_time: list[float] = []
    stage_code: list[int] = []
    stage_work: list[float] = []
    for index, (left, right) in enumerate(zip(time, time[1:])):
        h = float(right - left)
        if method == "rk4":
            codes = [1, 2, 3, 4]
            offsets = [0.0, 0.5, 0.5, 1.0]
            work_offsets = [0.0, h, h, 2.0 * h] if not a0 else [0.0, 0.0, 0.0, 0.0]
        else:
            codes = [1, 5]
            offsets = [0.0, 0.5]
            work_offsets = [0.0, h] if not a0 else [0.0, 0.0]
        stage_code.extend(codes)
        stage_time.extend(float(left + offset * h) for offset in offsets)
        stage_work.extend(float(saved_work[index] + offset) for offset in work_offsets)
    stage_service = np.zeros((s, 29), dtype="<f8")
    stage_service[:, 3] = 1.0
    stage_service[:, 13:15] = 0.03
    stage_service[:, 27] = 2.0
    stage_command = np.zeros((s, 14), dtype="<f8")
    if not a0:
        stage_command[:, 12] = 1.0

    p = int(round(0.005 / step_s)) + 1 if finite else 0
    post_time = (
        np.asarray(horizon_s + np.arange(p, dtype="<f8") * step_s, dtype="<f8")
        if p else np.empty((0,), dtype="<f8")
    )
    post_service = np.zeros((p, 29), dtype="<f8")
    post_target = np.zeros((p, 13), dtype="<f8")
    if p:
        post_service[:] = service[-1]
        post_target[:] = target[-1]
    post_stage_time: list[float] = []
    post_stage_code: list[int] = []
    if p:
        for left, right in zip(post_time, post_time[1:]):
            h = float(right - left)
            if method == "rk4":
                post_stage_code.extend([1, 2, 3, 4])
                post_stage_time.extend([float(left), float(left + 0.5 * h), float(left + 0.5 * h), float(right)])
            else:
                post_stage_code.extend([1, 5])
                post_stage_time.extend([float(left), float(left + 0.5 * h)])
    ps = len(post_stage_code)
    post_stage_service = np.tile(service[-1], (ps, 1)).astype("<f8")
    if ps:
        post_stage_service[:, 13:15] = 0.03
    removal_count = 1 if finite else 0
    arrays: dict[str, np.ndarray] = {
        "command_Q_14": command,
        "contact_force_N": np.zeros(n, dtype="<f8"),
        "contact_torque_N_m": np.zeros(n, dtype="<f8"),
        "energy_minus_work_residual_J": np.zeros(n, dtype="<f8"),
        "ideal_constraint_power_W": np.zeros(n, dtype="<f8"),
        "left_gap_m": np.full(n, 0.001, dtype="<f8"),
        "left_gap_rate_m_s": np.zeros(n, dtype="<f8"),
        "right_gap_m": np.full(n, 0.001, dtype="<f8"),
        "right_gap_rate_m_s": np.zeros(n, dtype="<f8"),
        "service_state_29": service,
        "signed_W_act_J": saved_work.astype("<f8"),
        "stage_P_coordinates_m": np.full((s, 2), 0.03, dtype="<f8"),
        "stage_code": np.asarray(stage_code, dtype="<i8"),
        "stage_command_Q_14": stage_command,
        "stage_domain_and_sign_pass": np.ones(s, dtype="|b1"),
        "stage_gap_jacobian_P": np.zeros((s, 2, 2), dtype="<f8"),
        "stage_mass_cholesky_min_diagonal": np.ones(s, dtype="<f8"),
        "stage_power_W": np.full(s, 0.0 if a0 else 2.0, dtype="<f8"),
        "stage_service_state_29": stage_service,
        "stage_time_s": np.asarray(stage_time, dtype="<f8"),
        "target_state_13": target,
        "time_s": time,
        "total_angular_momentum_N_m_s": np.zeros((n, 3), dtype="<f8"),
        "total_kinetic_energy_J": (10.0 + saved_work).astype("<f8"),
        "total_linear_momentum_N_s": np.zeros((n, 3), dtype="<f8"),
        "post_contact_force_N": np.zeros(p, dtype="<f8"),
        "post_contact_torque_N_m": np.zeros(p, dtype="<f8"),
        "post_left_gap_m": np.full(p, 0.001, dtype="<f8"),
        "post_left_gap_rate_m_s": np.zeros(p, dtype="<f8"),
        "post_right_gap_m": np.full(p, 0.001, dtype="<f8"),
        "post_right_gap_rate_m_s": np.zeros(p, dtype="<f8"),
        "post_service_state_29": post_service,
        "post_stage_P_coordinates_m": np.full((ps, 2), 0.03, dtype="<f8"),
        "post_stage_code": np.asarray(post_stage_code, dtype="<i8"),
        "post_stage_domain_and_sign_pass": np.ones(ps, dtype="|b1"),
        "post_stage_gap_jacobian_P": np.tile(np.eye(2, dtype="<f8"), (ps, 1, 1)),
        "post_stage_service_state_29": post_stage_service,
        "post_stage_target_state_13": np.tile(target[-1], (ps, 1)).astype("<f8"),
        "post_stage_time_s": np.asarray(post_stage_time, dtype="<f8"),
        "post_target_state_13": post_target,
        "post_time_s": post_time,
        "post_total_angular_momentum_N_m_s": np.zeros((p, 3), dtype="<f8"),
        "post_total_kinetic_energy_J": np.full(p, 10.0 + saved_work[-1], dtype="<f8"),
        "post_total_linear_momentum_N_s": np.zeros((p, 3), dtype="<f8"),
        "sample_power_reported_W": np.full(n, 0.0 if a0 else 2.0, dtype="<f8"),
        "stage_augmented_W_act_J": np.asarray(stage_work, dtype="<f8"),
        "post_signed_W_act_J": np.full(p, saved_work[-1], dtype="<f8"),
        "post_command_Q_14": np.zeros((p, 14), dtype="<f8"),
        "acquisition_event_count": np.asarray(0 if a0 else 1, dtype="<i8"),
        "acquisition_event_sample_index": np.asarray([] if a0 else [0], dtype="<i8"),
        "acquisition_event_time_s": np.asarray([] if a0 else [time[0]], dtype="<f8"),
        "bilateral_removal_event_count": np.asarray(removal_count, dtype="<i8"),
        "bilateral_removal_active_sample_index": np.asarray([n - 1] if finite else [], dtype="<i8"),
        "bilateral_removal_event_time_s": np.asarray([time[-1]] if finite else [], dtype="<f8"),
        "saved_window_end_index": np.asarray(n - 1, dtype="<i8"),
        "active_interval_ledger_certified": np.ones(n - 1, dtype="|b1"),
    }
    return arrays


def encode_npz(arrays: dict[str, np.ndarray]) -> bytes:
    stream = BytesIO()
    np.savez(stream, **arrays)
    return stream.getvalue()


def write_case(
    project_root: Path,
    *,
    case_id: str | None = None,
    method: str = "rk4",
    step_s: float = 0.00025,
    outcome: str = OUTCOME_FINITE,
    horizon_s: float = 0.0025,
    alpha: float = 16.0,
    command_duration_s: float = 0.005,
    bookend_sentinel: str = "PRE",
    array_mutator: ArrayMutator | None = None,
    sidecar_mutator: SidecarMutator | None = None,
) -> str:
    project_root.mkdir(parents=True, exist_ok=True)
    marker = project_root / "PROJECT_MAP.md"
    if not marker.exists():
        marker.write_text("temporary source-only fixture root\n", encoding="utf-8")
    lane_lookup = {
        ("rk4", 0.00025): "RK4_H_MS_0P25",
        ("rk4", 0.000125): "RK4_H_MS_0P125",
        ("rk4", 0.0000625): "RK4_H_MS_0P0625",
        ("midpoint", 0.00025): "MIDPOINT_H_MS_0P25",
        ("midpoint", 0.000125): "MIDPOINT_H_MS_0P125",
        ("midpoint", 0.0000625): "MIDPOINT_H_MS_0P0625",
    }
    lane = lane_lookup[(method, step_s)]
    duration_ms = int(round(command_duration_s * 1000.0))
    alpha_token = "0P5" if alpha == 0.5 else str(int(alpha))
    if case_id is None:
        case_id = (
            f"FRESH__{lane}__A0__{bookend_sentinel}"
            if outcome == OUTCOME_A0
            else
            f"COMMON_PROP__{lane}__A_16__T_MS_{duration_ms}"
            if outcome == OUTCOME_COMMON
            else f"FRESH__{lane}__A1__A_{alpha_token}__T_MS_{duration_ms}"
        )
    binding = expected_binding(case_id)
    relative_json = f"evidence/cases/{case_id}.json"
    relative_npz = f"evidence/cases/{case_id}.npz"
    arrays = build_arrays(method=method, step_s=step_s, outcome=outcome, horizon_s=horizon_s)
    if array_mutator:
        array_mutator(arrays)
    payload = encode_npz(arrays)
    npz_path = project_root / relative_npz
    npz_path.parent.mkdir(parents=True, exist_ok=True)
    npz_path.write_bytes(payload)
    profile = OUTCOME_TO_PROFILE[outcome]
    sidecar: dict[str, Any] = {
        "schema": "SIM13_V4B4G_R2_RAW_CASE_SIDECAR_V1",
        "case_id": case_id,
        "lane_id": binding["row"]["lane_id"],
        "method": method,
        "step_s": float(step_s),
        "execution_family": "COMMON_PROP" if outcome == OUTCOME_COMMON else "FRESH",
        "outcome": outcome,
        "array_profile": profile,
        "npz_relative_path": relative_npz,
        "npz_bytes": len(payload),
        "npz_sha256": hashlib.sha256(payload).hexdigest().upper(),
        "array_contract_sha256": PROFILE_SHA256[profile],
        "array_contract_document_sha256": ARRAY_CONTRACT_DOCUMENT_SHA256,
        "acquisition_time_s": "NOT_APPLICABLE_A0" if outcome == OUTCOME_A0 else float(arrays["acquisition_event_time_s"][0]),
        "command_duration_s": "NOT_APPLICABLE_A0" if outcome == OUTCOME_A0 else float(command_duration_s),
        "alpha": "NOT_APPLICABLE_A0" if outcome == OUTCOME_A0 else float(alpha),
        "schedule_index": binding["schedule_index"],
        "matrix_row_sha256": binding["matrix_row_sha256"],
        "source_hashes": binding["source_hashes"],
        "registered_roles": binding["row"]["roles"],
    }
    if outcome == OUTCOME_FINITE:
        sidecar["removal_time_s"] = float(arrays["bilateral_removal_event_time_s"][0])
    if outcome == OUTCOME_A0:
        sidecar["bookend_sentinel"] = bookend_sentinel
    if outcome == OUTCOME_COMMON:
        sidecar.update({
            "common_donor_certificate_sha256": DONOR_PAYLOAD_SHA256,
            "common_state_group_sha256": COMMON_GROUP_SHA256,
            "common_donor_hashes_before": dict(COMMON_DONOR_HASHES),
            "common_donor_hashes_after": dict(COMMON_DONOR_HASHES),
        })
    if sidecar_mutator:
        sidecar_mutator(sidecar)
    (project_root / relative_json).write_text(
        json.dumps(sidecar, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return relative_json


__all__ = ["build_arrays", "encode_npz", "write_case"]
