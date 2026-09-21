from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pytest

from b4g_validation.core import canonical_bytes
from b4g_validation.geometry_replay import (
    centered_gap_jacobian,
    recompute_active_gap_rate,
    recompute_mutation_only_no_domain_guard_active_geometry,
    reconstruct_active_target_state_13,
)
from b4g_validation.forced_propagation_replay import replay_forced_propagation
from b4g_validation.supplemental_replay import (
    SupplementalReplayError,
    validate_supplemental_trace,
)
from b4g_validation import validator


BOUNDARY = (
    "mutation replay evidence only; no A1/A2 outcome, physical, current-system, "
    "formal NC19, Owner, production, release or next-stage credit"
)
PHASE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = validator.PROJECT_ROOT


def _write(path: Path, value: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value) + b"\n")
    return path


def _record(role: str, path: Path) -> dict[str, object]:
    return {
        "role": role,
        "path": path.resolve().as_posix(),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
    }


@pytest.fixture(scope="module")
def contracts() -> dict[str, object]:
    return {
        "spec": json.loads((validator.CONTRACT_ROOT / validator.CONTRACT_FILES["mutations"][0]).read_text()),
        "schedule": json.loads((validator.CONTRACT_ROOT / validator.CONTRACT_FILES["schedule"][0]).read_text()),
        "qref": json.loads((validator.CONTRACT_ROOT / validator.CONTRACT_FILES["reference"][0]).read_text())["individual_finger_reference_force_N"],
    }


def _b4e_templates(lane: str = "RK4_COARSE") -> tuple[dict, dict]:
    root = PHASE_ROOT.parent / "phase_b4_post_freeze_synthetic_6d_solver" / "evidence"
    events = json.loads((root / "SIM13_V4B4E_EVENT_INPUTS_V1.json").read_text())
    acquisitions = json.loads((root / "SIM13_V4B4E_ACQUISITION_LEDGER_V1.json").read_text())
    event = next(row for row in events["runs"] if str(row["run_id"]).upper() == lane)
    acquisition = acquisitions["runs"][event["run_id"]]
    return deepcopy(event), deepcopy(acquisition)


def _service_vector(event: dict) -> np.ndarray:
    service = event["service"]
    return np.asarray(
        service["base_position_inertial_m"]
        + service["base_quaternion_body_to_inertial_wxyz"]
        + service["joint_coordinates_mixed"]
        + service["nu_s_mixed"],
        dtype=float,
    )


def _nc08_fixture(tmp_path: Path, qref: float) -> tuple[list[dict], dict]:
    event, acquisition = _b4e_templates()
    acquisition.pop("matrices", None)
    acquisition_time = float(acquisition["acquisition_time_s"])
    tau = acquisition_time + 0.008
    removal = tau + 0.001
    command = {
        "command_id": "B4G_MUTATION_FINITE_HARNESS",
        "left": {"alpha": 0.0, "delay_s": 0.0, "duration_s": 0.0},
        "right": {"alpha": 0.0, "delay_s": 0.0, "duration_s": 0.0},
    }
    clearance = {
        "algorithm": "PIECEWISE_CUBIC_HERMITE_ALL_ROOTS_EARLIEST_BILATERAL_DWELL",
        "endpoint_only": False,
        "finite_event": True,
        "tau_c_s": tau,
        "removal_time_s": removal,
        "certified_good_intervals_s": [[tau, removal]],
    }
    finite_event = deepcopy(event); finite_event["run_id"] = "FINITE_PARENT"
    finite_acquisition = deepcopy(acquisition); finite_acquisition["run_id"] = "FINITE_PARENT"
    finite = {
        "method": "rk4", "step_s": 0.001,
        "event": finite_event, "acquisition": finite_acquisition,
        "command": command, "clearance": clearance,
    }
    finite_path = _write(tmp_path / "finite.json", finite)
    finite_record = _record("EXECUTED_FINITE_HARNESS_RAW_OUTPUT", finite_path)

    case_id = "B4FNC08_LEFT_REAL_DWELL_FORCE_MUTANT"
    run_event = deepcopy(event); run_event["run_id"] = case_id
    run_acquisition = deepcopy(acquisition); run_acquisition["run_id"] = case_id
    snapshot = acquisition["snapshot"]
    service_record = event["service"]
    initial_service = np.asarray(
        service_record["base_position_inertial_m"]
        + service_record["base_quaternion_body_to_inertial_wxyz"]
        + service_record["joint_coordinates_mixed"]
        + acquisition["eta_plus"],
        dtype=float,
    )
    step = 0.001
    expected_steps = max(
        1, int(math.ceil((removal - acquisition_time) / step - 1.0e-12)) + 1,
    )
    time = acquisition_time + np.arange(expected_steps + 1) * step

    propagation = replay_forced_propagation(
        time_s=time,
        initial_state_30=np.append(initial_service, 0.0),
        method="rk4",
        step_s=step,
        event=run_event,
        acquisition=run_acquisition,
        command=command,
        q_ref_N=qref,
        dwell_q_index=12,
        dwell_window_s=(tau, removal),
    )
    q = propagation.command_Q_14
    state = propagation.state_30
    power = propagation.actuator_power_W
    targets = np.asarray([
        reconstruct_active_target_state_13(row[:29], snapshot) for row in state
    ])
    observations = [
        recompute_active_gap_rate(row[:29], snapshot) for row in state
    ]
    gaps = np.asarray([row.gaps_m for row in observations])
    rates = np.asarray([row.gap_rates_m_s for row in observations])

    def stage_row(stage: object) -> dict:
        service = stage.state_30[:29]
        force = stage.generalized_force_14
        geometry = centered_gap_jacobian(
            service, snapshot=snapshot, step_m=1.0e-7,
        )
        row = {
            "time_s": float(stage.time_s), "stage_label": stage.stage_label,
            "P_coordinates_m_left_right": geometry.p_coordinates_m.tolist(),
            "raw_gap_jacobian_dimensionless": geometry.raw_gap_jacobian_p.tolist(),
            "diagonal_gap_derivatives_dimensionless": geometry.diagonal_derivatives.tolist(),
            "opening_sign_left_right": [1, 1],
            "nominal_gap_m_left_right": geometry.nominal_gaps_m.tolist(),
            "nominal_gap_rate_m_s_left_right": geometry.nominal_gap_rates_m_s.tolist(),
            "contact_force_max_N": 0.0, "contact_torque_max_N_m": 0.0,
            "generalized_force_14": force.tolist(),
            "consumed_opening_sign_left_right": [1, 1],
            "consumed_sigma_equals_raw_and_registered": True,
            "Q_base_and_R_exact_zero": True, "contact_kernel_enabled": False,
            "service_state_29": service.tolist(), "stage_code": stage.stage_code,
            "mass_cholesky_min_diagonal": stage.mass_cholesky_min_diagonal,
            "actuator_power_W": stage.actuator_power_W,
            "accepted": True,
        }
        if stage.mass_min_eigenvalue is not None:
            row["mass_min_eigenvalue"] = stage.mass_min_eigenvalue
        return row

    stages = [stage_row(stage) for stage in propagation.stages]
    raw = {
        "time_s": time.tolist(),
        "state_30_service_29_plus_signed_W_act_J": state.tolist(),
        "applied_Q_P_left_right_N": q[:, 12:14].tolist(),
        "command_Q_14": q.tolist(), "actuator_power_W": power.tolist(),
        "left_gap_m": gaps[:, 0].tolist(), "right_gap_m": gaps[:, 1].tolist(),
        "left_gap_rate_m_s": rates[:, 0].tolist(), "right_gap_rate_m_s": rates[:, 1].tolist(),
        "target_position_m": targets[:, :3].tolist(),
        "target_quaternion_wxyz": targets[:, 3:7].tolist(),
        "target_twist_mixed": targets[:, 7:13].tolist(),
        "total_linear_momentum_N_s": propagation.total_linear_momentum_N_s.tolist(),
        "total_angular_momentum_N_m_s": propagation.total_angular_momentum_N_m_s.tolist(),
        "total_kinetic_energy_J": propagation.total_kinetic_energy_J.tolist(),
        "sample_ledgers": {
            name: value.tolist()
            for name, value in propagation.sample_ledgers.items()
        },
        "stage_audits": stages,
    }
    run = {
        "case_id": case_id, "method": "rk4", "step_s": 0.001,
        "event": run_event, "acquisition": run_acquisition, "command": command,
        "raw": raw, "clearance": {
            "finite_event": False,
            "status": "DIAGNOSTIC_INCONCLUSIVE_HORIZON_EXHAUSTED_NO_REMOVAL_OBSERVED",
        },
        "terminal_status": "DIAGNOSTIC_INCONCLUSIVE_HORIZON_EXHAUSTED_NO_REMOVAL_OBSERVED",
        "geometry_domain_pass": True, "synthetic_removal_executed": False,
        "post_release": None, "failure": None, "search_endpoint": None,
        "physical_release_claimed": False,
        "minimum_required_force_or_work_claimed": False,
    }
    supplemental = {
        "schema": "SIM13_V4B4G_MUTANT_DWELL_FORCE_TRACE_V1",
        "parent_id": "B4FNC08", "subvariant_index": 1,
        "side": "left", "q_index": 12,
        "source_finite_harness": {key: finite_record[key] for key in ("path", "bytes", "sha256")},
        "injection_window_s": [tau, removal], "injection_N": qref,
        "nominal_finite_clearance": clearance,
        "execution_branch": "PATCHED_FORCE_VECTOR_THEN_FORCED_PROPAGATION",
        "mutant_run": run, "claim_boundary": BOUNDARY,
    }
    supplemental_path = _write(tmp_path / "nc08.json", supplemental)
    return [finite_record, _record("MUTANT_DWELL_FORCE_TRACE", supplemental_path)], supplemental


def _coordinated_structural_nc08_forgery(payload: dict) -> dict:
    """Rebuild every old structural channel around a non-physical trajectory."""

    forged = deepcopy(payload)
    run = forged["mutant_run"]
    raw = run["raw"]
    time = np.asarray(raw["time_s"], dtype=float)
    acquisition_time = float(run["acquisition"]["acquisition_time_s"])
    initial = np.asarray(
        raw["state_30_service_29_plus_signed_W_act_J"][0], dtype=float,
    )
    state = np.tile(initial, (len(time), 1))
    elapsed = time - acquisition_time
    state[:, 27] = initial[27] + 0.01 * elapsed
    state[:, 13] = initial[13] + 0.005 * elapsed**2
    q = np.asarray(raw["command_Q_14"], dtype=float)
    power = np.sum(q[:, 12:14] * state[:, 27:29], axis=1)
    state[:, 29] = np.concatenate((
        np.zeros(1),
        np.cumsum(0.5 * (power[:-1] + power[1:]) * np.diff(time)),
    ))
    snapshot = run["acquisition"]["snapshot"]
    targets = np.asarray([
        reconstruct_active_target_state_13(row[:29], snapshot) for row in state
    ])
    observations = [
        recompute_active_gap_rate(row[:29], snapshot) for row in state
    ]
    gaps = np.asarray([row.gaps_m for row in observations])
    rates = np.asarray([row.gap_rates_m_s for row in observations])
    raw["state_30_service_29_plus_signed_W_act_J"] = state.tolist()
    raw["actuator_power_W"] = power.tolist()
    raw["target_position_m"] = targets[:, :3].tolist()
    raw["target_quaternion_wxyz"] = targets[:, 3:7].tolist()
    raw["target_twist_mixed"] = targets[:, 7:].tolist()
    raw["left_gap_m"] = gaps[:, 0].tolist()
    raw["right_gap_m"] = gaps[:, 1].tolist()
    raw["left_gap_rate_m_s"] = rates[:, 0].tolist()
    raw["right_gap_rate_m_s"] = rates[:, 1].tolist()
    raw["total_linear_momentum_N_s"] = [[0.0, 0.0, 0.0] for _ in time]
    raw["total_angular_momentum_N_m_s"] = [[0.0, 0.0, 0.0] for _ in time]
    raw["total_kinetic_energy_J"] = (10.0 + state[:, 29]).tolist()
    raw["sample_ledgers"] = {
        name: [0.0] * len(time) for name in raw["sample_ledgers"]
    }

    for row in raw["stage_audits"]:
        label = row["stage_label"]
        if label.startswith("ACCEPTED_SAMPLE_"):
            service = state[int(label.rsplit("_", 1)[1]), :29]
        else:
            interval = int(label.split("_", 2)[1])
            if label.endswith("_K1"):
                service = state[interval, :29]
            elif label.endswith("_K4"):
                service = state[interval + 1, :29]
            else:
                service = 0.5 * (
                    state[interval, :29] + state[interval + 1, :29]
                )
        force = np.asarray(row["generalized_force_14"], dtype=float)
        geometry = centered_gap_jacobian(
            service, snapshot=snapshot, step_m=1.0e-7,
        )
        row["service_state_29"] = service.tolist()
        row["P_coordinates_m_left_right"] = geometry.p_coordinates_m.tolist()
        row["raw_gap_jacobian_dimensionless"] = (
            geometry.raw_gap_jacobian_p.tolist()
        )
        row["diagonal_gap_derivatives_dimensionless"] = (
            geometry.diagonal_derivatives.tolist()
        )
        row["nominal_gap_m_left_right"] = geometry.nominal_gaps_m.tolist()
        row["nominal_gap_rate_m_s_left_right"] = (
            geometry.nominal_gap_rates_m_s.tolist()
        )
        row["actuator_power_W"] = float(force[12:14] @ service[27:29])
    return forged


def test_nc08_complete_mutant_trace_is_replayed_and_zeroed_copy_fails(
    tmp_path: Path, contracts: dict[str, object],
) -> None:
    qref = float(contracts["qref"])
    records, payload = _nc08_fixture(tmp_path, qref)
    result = validate_supplemental_trace(
        "B4FNC08", 1, records, project_root=PROJECT_ROOT, phase_root=PHASE_ROOT,
        mutation_spec=contracts["spec"], frozen_schedule=contracts["schedule"],
        frozen_q_ref=qref, base_payload={},
    )
    assert result.diagnostics["independent_g08_predicate"] is False

    coordinated = _coordinated_structural_nc08_forgery(payload)
    coordinated_path = _write(tmp_path / "nc08_coordinated_forgery.json", coordinated)
    with pytest.raises(
        SupplementalReplayError,
        match="NC08_INDEPENDENT_PROPAGATION_STATE_REPLAY",
    ):
        validate_supplemental_trace(
            "B4FNC08", 1,
            [
                records[0],
                _record("MUTANT_DWELL_FORCE_TRACE", coordinated_path),
            ],
            project_root=PROJECT_ROOT, phase_root=PHASE_ROOT,
            mutation_spec=contracts["spec"],
            frozen_schedule=contracts["schedule"], frozen_q_ref=qref,
            base_payload={},
        )

    wrong_diagonal = deepcopy(payload)
    wrong_diagonal["mutant_run"]["raw"]["stage_audits"][0][
        "diagonal_gap_derivatives_dimensionless"
    ][0] += 1.0e-4
    wrong_diagonal_path = _write(
        tmp_path / "nc08_wrong_diagonal.json", wrong_diagonal,
    )
    with pytest.raises(
        SupplementalReplayError, match="NC08_STAGE_DIAGONAL_DERIVATIVE_0",
    ):
        validate_supplemental_trace(
            "B4FNC08", 1,
            [
                records[0],
                _record("MUTANT_DWELL_FORCE_TRACE", wrong_diagonal_path),
            ],
            project_root=PROJECT_ROOT, phase_root=PHASE_ROOT,
            mutation_spec=contracts["spec"],
            frozen_schedule=contracts["schedule"], frozen_q_ref=qref,
            base_payload={},
        )

    active_contact = deepcopy(payload)
    active_contact["mutant_run"]["raw"]["stage_audits"][0][
        "contact_force_max_N"
    ] = 1.0e-12
    active_contact_path = _write(
        tmp_path / "nc08_active_contact.json", active_contact,
    )
    with pytest.raises(
        SupplementalReplayError, match="NC08_STAGE_CONTACT_NOT_EXACT_ZERO",
    ):
        validate_supplemental_trace(
            "B4FNC08", 1,
            [
                records[0],
                _record("MUTANT_DWELL_FORCE_TRACE", active_contact_path),
            ],
            project_root=PROJECT_ROOT, phase_root=PHASE_ROOT,
            mutation_spec=contracts["spec"],
            frozen_schedule=contracts["schedule"], frozen_q_ref=qref,
            base_payload={},
        )

    forged = deepcopy(payload)
    forged["mutant_run"]["raw"]["command_Q_14"] = [
        [0.0] * 14 for _ in forged["mutant_run"]["raw"]["time_s"]
    ]
    forged_path = _write(tmp_path / "nc08_forged.json", forged)
    forged_records = [records[0], _record("MUTANT_DWELL_FORCE_TRACE", forged_path)]
    with pytest.raises(SupplementalReplayError, match="NC08_Q_CHANNEL_BINDING|NC08_SAMPLE_COMMAND_REPLAY"):
        validate_supplemental_trace(
            "B4FNC08", 1, forged_records, project_root=PROJECT_ROOT,
            phase_root=PHASE_ROOT, mutation_spec=contracts["spec"],
            frozen_schedule=contracts["schedule"], frozen_q_ref=qref,
            base_payload={},
        )

    static = deepcopy(payload)
    first = static["mutant_run"]["raw"][
        "state_30_service_29_plus_signed_W_act_J"
    ][0]
    static["mutant_run"]["raw"][
        "state_30_service_29_plus_signed_W_act_J"
    ] = [deepcopy(first) for _ in static["mutant_run"]["raw"]["time_s"]]
    static_path = _write(tmp_path / "nc08_static.json", static)
    with pytest.raises(
        SupplementalReplayError,
        match="NC08_SAMPLE_POWER_REPLAY|NC08_FORCED_STATE_RESPONSE_NOT_OBSERVED|NC08_STORED_STAGE_NOT_RAW_SAMPLE",
    ):
        validate_supplemental_trace(
            "B4FNC08", 1,
            [records[0], _record("MUTANT_DWELL_FORCE_TRACE", static_path)],
            project_root=PROJECT_ROOT, phase_root=PHASE_ROOT,
            mutation_spec=contracts["spec"],
            frozen_schedule=contracts["schedule"], frozen_q_ref=qref,
            base_payload={},
        )


def _sin2(elapsed: float, duration: float) -> float:
    if elapsed <= 0.0 or elapsed >= duration:
        return 0.0
    return math.sin(math.pi * elapsed / duration) ** 2


def _a2_algorithm_trace(
    trace_id: str, grid: np.ndarray, alpha: float, duration: float, qref: float,
) -> dict:
    definitions = {
        "RIGHT_HALF_DELAY_BASE": ("HALF_DELAY", "RIGHT", "RIGHT_HALF_DELAY", ((alpha, 0.0), (0.5 * alpha, 0.005))),
        "RIGHT_HALF_DELAY_MUTANT": ("HALF_DELAY", "RIGHT", "RIGHT_HALF_DELAY", ((alpha, 0.0), (0.75 * alpha, 0.005))),
        "LEFT_HALF_DELAY_MIRROR": ("HALF_DELAY", "LEFT_MIRROR", "LEFT_HALF_DELAY_MIRROR", ((0.5 * alpha, 0.005), (alpha, 0.0))),
        "RIGHT_COMMAND_OFF_BASE": ("COMMAND_OFF", "RIGHT", "RIGHT_COMMAND_OFF", ((alpha, 0.0), (0.0, 0.0))),
        "RIGHT_COMMAND_OFF_MUTANT": ("COMMAND_OFF", "RIGHT", "RIGHT_COMMAND_OFF", ((alpha, 0.0), (0.25 * alpha, 0.0))),
        "LEFT_COMMAND_OFF_MIRROR": ("COMMAND_OFF", "LEFT_MIRROR", "LEFT_COMMAND_OFF_MIRROR", ((0.0, 0.0), (alpha, 0.0))),
    }
    pair, side, variant, arms = definitions[trace_id]
    q = np.zeros((len(grid), 14))
    for row, current in enumerate(grid):
        for index, (amplitude, delay) in zip((12, 13), arms):
            q[row, index] = amplitude * qref * _sin2(float(current - delay), duration)
    rate = 0.01 * q[:, 12:14]
    dt = np.diff(grid)
    gap_increment = 0.5 * (rate[:-1] + rate[1:]) * dt[:, None]
    gaps = 2.0e-6 + np.vstack((np.zeros((1, 2)), np.cumsum(gap_increment, axis=0)))
    power = np.sum(q[:, 12:14] * rate, axis=1)
    work = np.concatenate((np.zeros(1), np.cumsum(0.5 * (power[:-1] + power[1:]) * dt)))
    return {
        "trace_id": trace_id, "pair_kind": pair, "side": side,
        "command_variant": variant, "command_Q_14": q.tolist(),
        "left_gap_m": gaps[:, 0].tolist(), "right_gap_m": gaps[:, 1].tolist(),
        "left_gap_rate_m_s": rate[:, 0].tolist(),
        "right_gap_rate_m_s": rate[:, 1].tolist(),
        "signed_W_act_J": work.tolist(),
        "outcome": {
            "finite_removal_event": False, "removal_time_s": None,
            "post_release_passed": False,
            "terminal_status": "ALGORITHM_ONLY_DETECTOR_HORIZON_COMPLETE_NO_PHYSICAL_OUTCOME",
        },
    }


def _nc17_fixture(tmp_path: Path, contracts: dict[str, object]) -> tuple[list[dict], dict, dict]:
    schedule = contracts["schedule"]
    qref = float(contracts["qref"])
    parent = {"alpha": 2.0, "command_duration_s": 0.01, "Q_ref_N": qref}
    trace_order = [
        "RIGHT_HALF_DELAY_BASE", "RIGHT_HALF_DELAY_MUTANT",
        "LEFT_HALF_DELAY_MIRROR", "RIGHT_COMMAND_OFF_BASE",
        "RIGHT_COMMAND_OFF_MUTANT", "LEFT_COMMAND_OFF_MIRROR",
    ]
    lanes = []
    for lane in validator.LANES:
        method, step = validator.LANE_DEFINITIONS[lane]
        grid = np.arange(int(round(0.08 / step)) + 1, dtype=float) * step
        lanes.append({
            "lane_id": lane, "method": method, "step_s": step,
            "relative_time_s": grid.tolist(),
            "traces": [
                _a2_algorithm_trace(trace_id, grid, 2.0, 0.01, qref)
                for trace_id in trace_order
            ],
        })
    schedule_path = _write(tmp_path / "schedule.json", schedule)
    schedule_record = _record("FROZEN_REGISTERED_SCHEDULE", schedule_path)
    fallback_path = _write(tmp_path / "fallback.json", {"fixture": True})
    payload = {
        "schema": "SIM13_V4B4G_A2_DETECTOR_SIX_LANE_TRACE_V1",
        "parent_id": "B4FNC17", "harness_id": "ALGORITHM_ONLY_A2_DETECTOR_HARNESS",
        "source_schedule": {key: schedule_record[key] for key in ("path", "bytes", "sha256")},
        "parent_level": parent, "lane_order": list(validator.LANES),
        "trace_order": trace_order,
        "detector_model": {
            "model_id": "SYMMETRIC_DETERMINISTIC_BILATERAL_COMMAND_RESPONSE_V1",
            "initial_gap_m": 2.0e-6, "symmetric_mobility_m_s_N": 0.01,
            "integration": "CUMULATIVE_TRAPEZOID_ON_FROZEN_RELATIVE_GRID",
            "terminal_status": "ALGORITHM_ONLY_DETECTOR_HORIZON_COMPLETE_NO_PHYSICAL_OUTCOME",
        },
        "lanes": lanes,
        "capabilities": {
            "a1_outcome_credit": False, "a2_outcome_credit": False,
            "physical_credit": False, "current_system_bound": False,
        },
        "claim_boundary": BOUNDARY,
    }
    path = _write(tmp_path / "nc17.json", payload)
    records = [
        schedule_record, _record("FROZEN_MUTATION_FALLBACK_CONTRACT", fallback_path),
        _record("A2_DETECTOR_SIX_LANE_TRACE", path),
    ]
    return records, payload, {"parent_level": parent}


def test_nc17_algorithm_only_base_pass_mutants_fail_and_missing_grid_fails(
    tmp_path: Path, contracts: dict[str, object],
) -> None:
    records, payload, base = _nc17_fixture(tmp_path, contracts)
    result = validate_supplemental_trace(
        "B4FNC17", 1, records, project_root=PROJECT_ROOT, phase_root=PHASE_ROOT,
        mutation_spec=contracts["spec"], frozen_schedule=contracts["schedule"],
        frozen_q_ref=float(contracts["qref"]), base_payload=base,
    )
    assert result.diagnostics["trace_count"] == 36
    assert result.diagnostics["all_base_pair_predicates_true"] is True
    assert result.diagnostics["all_mutant_pair_predicates_false"] is True

    forged = deepcopy(payload)
    forged["lanes"][0]["relative_time_s"].pop()
    for key in ("command_Q_14", "left_gap_m", "right_gap_m", "left_gap_rate_m_s", "right_gap_rate_m_s", "signed_W_act_J"):
        for trace in forged["lanes"][0]["traces"]:
            trace[key].pop()
    forged_path = _write(tmp_path / "nc17_forged.json", forged)
    forged_records = [records[0], records[1], _record("A2_DETECTOR_SIX_LANE_TRACE", forged_path)]
    with pytest.raises(SupplementalReplayError, match="NC17_FROZEN_FULL_GRID|NC17_RELATIVE_TIME_SHAPE"):
        validate_supplemental_trace(
            "B4FNC17", 1, forged_records, project_root=PROJECT_ROOT,
            phase_root=PHASE_ROOT, mutation_spec=contracts["spec"],
            frozen_schedule=contracts["schedule"], frozen_q_ref=float(contracts["qref"]),
            base_payload=base,
        )


def _nc21_fixture(tmp_path: Path, contracts: dict[str, object], subvariant: int) -> tuple[list[dict], dict, dict]:
    event, acquisition = _b4e_templates()
    service = _service_vector(event)
    stage_time = float(event["time_s"])
    npz_path = tmp_path / f"nc21_{subvariant}.npz"
    np.savez(npz_path, stage_service_state_29=service[None, :], stage_time_s=np.asarray([stage_time]))
    npz_record = _record("REGISTERED_CASE_RAW_NPZ", npz_path)
    metadata = {
        "event_provenance": {
            "acquisition_certificate_payload": {"acquisition": acquisition}
        }
    }
    metadata_path = _write(tmp_path / f"nc21_{subvariant}_metadata.json", metadata)
    metadata_record = _record("REGISTERED_CASE_METADATA", metadata_path)
    targets = contracts["spec"]["deterministic_targets_and_amplitudes"]["P_domain_mutants"]
    raw_p = service[13:15].copy()
    transformed = None
    if subvariant <= 4:
        target = targets[subvariant - 1]
        side = 0 if target["side"] == "left" else 1
        raw_p[side] = target["value_m"]
        branch = "DIRECT_DOMAIN_REJECT_NO_TRANSFORM"
        failed_side = side
        policy_outcome = "G16_FAIL_DIRECT_OUT_OF_DOMAIN"
    else:
        raw_p[0] = 0.071500001
        transformed = raw_p.copy()
        failed_side = 0
        if subvariant == 5:
            transformed[0] = 0.0715
            branch = "CLIP_TO_UPPER_BOUND"
            policy_outcome = "G16_FAIL_CLIPPING_USED"
        else:
            branch = "EXTRAPOLATE_AFTER_UPPER_BOUND"
            policy_outcome = "G16_FAIL_EXTRAPOLATION_USED"
    branch_trace = [
        {
            "ordinal": 0, "operation": "APPLY_RAW_REGISTERED_MUTANT_P",
            "P_coordinates_m": raw_p.tolist(), "outcome": "APPLIED",
        },
        {
            "ordinal": 1, "operation": "FROZEN_P_DOMAIN_GUARD",
            "P_coordinates_m": raw_p.tolist(), "outcome": "DOMAIN_EXIT",
        },
    ]
    no_domain = None
    if transformed is None:
        branch_trace.extend((
            {
                "ordinal": 2, "operation": "NO_TRANSFORM",
                "P_coordinates_m": None, "outcome": "NOT_EXECUTED",
            },
            {
                "ordinal": 3, "operation": "G16_POLICY",
                "P_coordinates_m": raw_p.tolist(), "outcome": policy_outcome,
            },
        ))
    else:
        transformed_service = service.copy()
        transformed_service[13:15] = transformed
        replay = recompute_mutation_only_no_domain_guard_active_geometry(
            transformed_service, acquisition["snapshot"], step_m=1.0e-7,
        )
        no_domain = {
            "schema": "SIM13_V4B4G_MUTATION_ONLY_NO_DOMAIN_GUARD_FK_V1",
            "evaluator_id": "INDEPENDENT_B601_6R2P_ACTIVE_GEOMETRY_NO_P_DOMAIN_GUARD_V1",
            "mutation_audit_only": True, "domain_guard_bypassed": True,
            "selector_or_scientific_credit": False,
            "service_state_29": transformed_service.tolist(),
            "P_coordinates_m": replay.p_coordinates_m.tolist(),
            "pad_positions_inertial_m_left_right": replay.pad_positions_inertial_m.tolist(),
            "target_state_13": replay.target_state_13.tolist(),
            "nominal_gap_m_left_right": replay.nominal_gaps_m.tolist(),
            "nominal_gap_rate_m_s_left_right": replay.nominal_gap_rates_m_s.tolist(),
            "centered_step_m": replay.centered_step_m,
            "centered_minus_P_coordinates_m_by_column": replay.centered_minus_p_coordinates_m.tolist(),
            "centered_plus_P_coordinates_m_by_column": replay.centered_plus_p_coordinates_m.tolist(),
            "centered_minus_gap_m_by_column": replay.centered_minus_gaps_m.tolist(),
            "centered_plus_gap_m_by_column": replay.centered_plus_gaps_m.tolist(),
            "raw_gap_jacobian_P": replay.raw_gap_jacobian_p.tolist(),
        }
        branch_trace.extend((
            {
                "ordinal": 2,
                "operation": (
                    "CLIP_TO_UPPER_BOUND" if subvariant == 5
                    else "EXTRAPOLATE_IDENTITY_OUTSIDE_DOMAIN"
                ),
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
                "ordinal": 4, "operation": "G16_POLICY",
                "P_coordinates_m": transformed.tolist(),
                "outcome": policy_outcome,
            },
        ))
    payload = {
        "schema": "SIM13_V4B4G_GEOMETRY_CLIP_EXTRAPOLATE_TRACE_V1",
        "parent_id": "B4FNC21", "subvariant_index": subvariant,
        "source_case_metadata": {key: metadata_record[key] for key in ("path", "bytes", "sha256")},
        "source_case_npz": {key: npz_record[key] for key in ("path", "bytes", "sha256")},
        "stage_index": 0, "mutation_target": targets[subvariant - 1],
        "nominal_service_state_29": service.tolist(),
        "acquisition_snapshot": acquisition["snapshot"],
        "raw_P_coordinates_m": raw_p.tolist(),
        "transformed_P_coordinates_m": None if transformed is None else transformed.tolist(),
        "branch": branch,
        "domain_exit_record": {
            "time_s": stage_time,
            "stage_label": f"B4FNC21_SUPPLEMENTAL_SV{subvariant:02d}",
            "P_coordinates_m_left_right": raw_p.tolist(),
            "centered_step_m": 1.0e-7, "failed_side": failed_side,
            "reason": "P_COORDINATE_OUTSIDE_CLOSED_DOMAIN",
        },
        "branch_trace": branch_trace,
        "no_domain_guard_evaluation": no_domain,
        "claim_boundary": BOUNDARY,
    }
    path = _write(tmp_path / f"nc21_{subvariant}_trace.json", payload)
    records = [metadata_record, npz_record, _record("GEOMETRY_CLIP_EXTRAPOLATE_TRACE", path)]
    return records, payload, {"P_coordinates_m": service[13:15].tolist()}


@pytest.mark.parametrize("subvariant", [1, 5, 6])
def test_nc21_domain_clip_extrapolate_paths_are_independently_replayed(
    tmp_path: Path, contracts: dict[str, object], subvariant: int,
) -> None:
    records, payload, base = _nc21_fixture(tmp_path, contracts, subvariant)
    result = validate_supplemental_trace(
        "B4FNC21", subvariant, records, project_root=PROJECT_ROOT,
        phase_root=PHASE_ROOT, mutation_spec=contracts["spec"],
        frozen_schedule=contracts["schedule"], frozen_q_ref=float(contracts["qref"]),
        base_payload=base,
    )
    assert result.diagnostics["independent_g16_predicate"] is False
    if subvariant in (5, 6):
        forged = deepcopy(payload)
        forged["no_domain_guard_evaluation"]["raw_gap_jacobian_P"][0][0] += 1.0e-4
        forged_path = _write(
            tmp_path / f"nc21_{subvariant}_forged_jac.json", forged,
        )
        with pytest.raises(
            SupplementalReplayError, match="NC21_NO_DOMAIN_JACOBIAN",
        ):
            validate_supplemental_trace(
                "B4FNC21", subvariant,
                [records[0], records[1], _record(
                    "GEOMETRY_CLIP_EXTRAPOLATE_TRACE", forged_path,
                )],
                project_root=PROJECT_ROOT, phase_root=PHASE_ROOT,
                mutation_spec=contracts["spec"],
                frozen_schedule=contracts["schedule"],
                frozen_q_ref=float(contracts["qref"]), base_payload=base,
            )

        missing = deepcopy(payload)
        missing["no_domain_guard_evaluation"] = None
        missing_path = _write(
            tmp_path / f"nc21_{subvariant}_missing_eval.json", missing,
        )
        with pytest.raises(
            SupplementalReplayError,
            match="NC21_NO_DOMAIN_GUARD_EVALUATION_FIELDS",
        ):
            validate_supplemental_trace(
                "B4FNC21", subvariant,
                [records[0], records[1], _record(
                    "GEOMETRY_CLIP_EXTRAPOLATE_TRACE", missing_path,
                )],
                project_root=PROJECT_ROOT, phase_root=PHASE_ROOT,
                mutation_spec=contracts["spec"],
                frozen_schedule=contracts["schedule"],
                frozen_q_ref=float(contracts["qref"]), base_payload=base,
            )


def test_supplemental_role_cannot_be_replaced_by_execution_detail(
    tmp_path: Path, contracts: dict[str, object],
) -> None:
    finite = _write(tmp_path / "finite_only.json", {"clearance": {}})
    with pytest.raises(SupplementalReplayError, match="REQUIRED_SUPPLEMENTAL_ROLE_MISSING"):
        validate_supplemental_trace(
            "B4FNC08", 1, [_record("EXECUTED_FINITE_HARNESS_RAW_OUTPUT", finite)],
            project_root=PROJECT_ROOT, phase_root=PHASE_ROOT,
            mutation_spec=contracts["spec"], frozen_schedule=contracts["schedule"],
            frozen_q_ref=float(contracts["qref"]), base_payload={},
        )
