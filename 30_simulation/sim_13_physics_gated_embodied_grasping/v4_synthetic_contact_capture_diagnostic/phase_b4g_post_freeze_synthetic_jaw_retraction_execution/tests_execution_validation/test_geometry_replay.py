"""Independent checks for the solver-free B4G geometry replay."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from b4g_validation import geometry_replay as geometry


PHASE_ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC_ROOT = PHASE_ROOT.parent
B4E_EVIDENCE = (
    DIAGNOSTIC_ROOT
    / "phase_b4_post_freeze_synthetic_6d_solver"
    / "evidence"
)
EVENT_INPUTS = B4E_EVIDENCE / "SIM13_V4B4E_EVENT_INPUTS_V1.json"
ACQUISITION_LEDGER = B4E_EVIDENCE / "SIM13_V4B4E_ACQUISITION_LEDGER_V1.json"
ACTIVE_TRACES = B4E_EVIDENCE / "SIM13_V4B4E_ACTIVE_TRACES_V1.json"
LANES = (
    "rk4_coarse",
    "rk4_fine",
    "rk4_reference",
    "midpoint_coarse",
    "midpoint_fine",
    "midpoint_reference",
)


def _read(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def _immutable_records() -> tuple[dict, dict, dict]:
    events = {record["run_id"]: record for record in _read(EVENT_INPUTS)["runs"]}
    acquisitions = _read(ACQUISITION_LEDGER)["runs"]
    traces = _read(ACTIVE_TRACES)["runs"]
    return events, acquisitions, traces


def _service_rows(trace: dict) -> np.ndarray:
    return np.hstack(
        (
            np.asarray(trace["service_position_m"], dtype=float),
            np.asarray(trace["service_quaternion_wxyz"], dtype=float),
            np.asarray(trace["service_joint_coordinates_mixed"], dtype=float),
            np.asarray(trace["eta_mixed"], dtype=float),
        )
    )


def _target_rows(trace: dict) -> np.ndarray:
    return np.hstack(
        (
            np.asarray(trace["target_position_m"], dtype=float),
            np.asarray(trace["target_quaternion_wxyz"], dtype=float),
            np.asarray(trace["target_twist_mixed"], dtype=float),
        )
    )


def test_frozen_geometry_source_bindings_are_exact_and_solver_free() -> None:
    records = geometry.validate_frozen_source_bindings()
    assert len(records) == 5
    assert {record["sha256"] for record in records} == {
        "3EC187C850F72EB1CAFF18713C71D6D0AC1773AF6C7AA8BFF4285FC26055C998",
        "21A3A5555215119684146FD2278181E70A0854ADF17A4A7B52E9DD3D954D5D96",
        "9D01439C8C658F95AB403C21752466D78018CC35701E7F4F54931B7228FF78B9",
        "7AAF83E067019B3CA69FF78E61CADBC25BF9FAEC94699E7EA388859D8144295D",
        "E337E79F7F5D5095080ABDE93DF9982F80A0AD925E0F21FDA90D527AA075F239",
    }
    source = Path(geometry.__file__).read_text(encoding="utf-8")
    assert "from b4_solver" not in source
    assert "import b4_solver" not in source
    assert "from b3_contact" not in source
    assert "import b3_contact" not in source
    assert "from b4g_solver" not in source
    assert "import b4g_solver" not in source


def test_constant_ledger_exposes_registered_geometry_semantics() -> None:
    ledger = geometry.frozen_constant_ledger()
    assert ledger["registered_centered_step_m"] == 1.0e-7
    assert ledger["registered_opening_signs"] == [1, 1]
    assert ledger["P_domain_m"] == [[0.0, 0.0715], [0.0, 0.0715]]
    assert ledger["sphere_radius_m"] == 0.040
    assert len(ledger["arm_joint_axes_parent"]) == 6


@pytest.mark.parametrize("lane", LANES)
def test_active_target_gap_and_rate_replay_matches_immutable_b4e(
    lane: str,
) -> None:
    events, acquisitions, active = _immutable_records()
    event = events[lane]
    acquisition = acquisitions[lane]
    trace = active[lane]["trace"]
    service_rows = _service_rows(trace)
    target_rows = _target_rows(trace)

    # Event, acquisition, and active evidence must refer to one frozen lane.
    assert event["run_id"] == acquisition["run_id"] == active[lane]["run_id"] == lane
    assert np.max(
        np.abs(
            service_rows[0, :15]
            - np.concatenate(
                (
                    np.asarray(event["service"]["base_position_inertial_m"]),
                    np.asarray(
                        event["service"][
                            "base_quaternion_body_to_inertial_wxyz"
                        ]
                    ),
                    np.asarray(event["service"]["joint_coordinates_mixed"]),
                )
            )
        )
    ) <= 1.0e-12
    assert np.max(np.abs(service_rows[0, 15:29] - acquisition["eta_plus"])) <= 1.0e-12

    snapshot = acquisition["snapshot"]
    expected_gaps = np.column_stack(
        (np.asarray(trace["left_gap_m"]), np.asarray(trace["right_gap_m"]))
    )
    expected_rates = np.column_stack(
        (
            np.asarray(trace["left_gap_rate_m_s"]),
            np.asarray(trace["right_gap_rate_m_s"]),
        )
    )
    rebuilt_targets = []
    rebuilt_gaps = []
    rebuilt_rates = []
    for service in service_rows:
        target = geometry.reconstruct_active_target_state_13(service, snapshot)
        observation = geometry.recompute_gap_rate(service, target)
        rebuilt_targets.append(target)
        rebuilt_gaps.append(observation.gaps_m)
        rebuilt_rates.append(observation.gap_rates_m_s)
    assert np.max(np.abs(np.asarray(rebuilt_targets) - target_rows)) <= 1.0e-12
    assert np.max(np.abs(np.asarray(rebuilt_gaps) - expected_gaps)) <= 1.0e-12
    assert np.max(np.abs(np.asarray(rebuilt_rates) - expected_rates)) <= 1.0e-12


@pytest.mark.parametrize("lane", LANES)
def test_registered_active_jacobian_and_mutation_fixture_are_usable(
    lane: str,
) -> None:
    _, acquisitions, active = _immutable_records()
    service = _service_rows(active[lane]["trace"])[0]
    snapshot = acquisitions[lane]["snapshot"]
    replay = geometry.centered_gap_jacobian(service, snapshot=snapshot)
    fixture = geometry.build_geometry_sign_fixture(service, snapshot=snapshot)

    assert replay.raw_gap_jacobian_p.shape == (2, 2)
    assert replay.opening_signs == (1, 1)
    assert np.max(np.abs(np.asarray(fixture["raw_gap_jacobian_P"]) - replay.raw_gap_jacobian_p)) == 0.0
    assert fixture == {
        "P_coordinates_m": replay.p_coordinates_m.tolist(),
        "centered_step_m": 1.0e-7,
        "raw_gap_jacobian_P": replay.raw_gap_jacobian_p.tolist(),
        "registered_signs": [1, 1],
        "consumed_signs": [1, 1],
        "clipping_used": False,
        "extrapolation_used": False,
        "terminal_status": "INDEPENDENT_GEOMETRY_REPLAY_COMPLETE",
    }

    # B4FNC04 can patch a consumed sign without changing the independently
    # reconstructed raw Jacobian; the mismatch is then explicit.
    nc04 = deepcopy(fixture)
    nc04["consumed_signs"][0] = -1
    assert nc04["registered_signs"] != nc04["consumed_signs"]
    assert nc04["raw_gap_jacobian_P"] == fixture["raw_gap_jacobian_P"]


def test_post_release_jacobian_holds_target_fixed() -> None:
    _, _, active = _immutable_records()
    trace = active["rk4_reference"]["trace"]
    service = _service_rows(trace)[0]
    target = _target_rows(trace)[0]
    replay = geometry.centered_gap_jacobian(
        service, independent_target_state_13=target
    )
    nominal = geometry.recompute_gap_rate(service, target)
    assert replay.target_mode == "POST_RELEASE_TARGET_FIXED_INDEPENDENTLY"
    assert np.max(np.abs(replay.nominal_gaps_m - nominal.gaps_m)) == 0.0
    assert np.max(np.abs(replay.nominal_gap_rates_m_s - nominal.gap_rates_m_s)) == 0.0
    assert replay.opening_signs == (1, 1)


@pytest.mark.parametrize(
    ("mutator", "message"),
    (
        (lambda state: state.__setitem__(0, np.nan), "SERVICE_STATE_29_NONFINITE"),
        (lambda state: state.__setitem__(3, 2.0), "SERVICE_QUATERNION_NOT_UNIT"),
        (lambda state: state.__setitem__(13, -1.0e-12), "P_COORDINATE_OUTSIDE_DOMAIN"),
        (lambda state: state.__setitem__(14, 0.071500000001), "P_COORDINATE_OUTSIDE_DOMAIN"),
    ),
)
def test_service_validation_rejects_nonfinite_nonunit_and_p_domain(
    mutator, message: str,
) -> None:
    _, _, active = _immutable_records()
    state = _service_rows(active["rk4_coarse"]["trace"])[0].copy()
    mutator(state)
    with pytest.raises(geometry.GeometryReplayError, match=message):
        geometry.validate_service_state_29(state)


def test_target_snapshot_and_perturbation_validation_fail_closed() -> None:
    _, acquisitions, active = _immutable_records()
    service = _service_rows(active["rk4_coarse"]["trace"])[0]
    target = _target_rows(active["rk4_coarse"]["trace"])[0]
    snapshot = deepcopy(acquisitions["rk4_coarse"]["snapshot"])

    target[3] = 1.5
    with pytest.raises(geometry.GeometryReplayError, match="TARGET_QUATERNION_NOT_UNIT"):
        geometry.validate_target_state_13(target)

    snapshot["translation_palm_to_target_m"][0] = float("inf")
    with pytest.raises(geometry.GeometryReplayError, match="SNAPSHOT_TRANSLATION.*NONFINITE"):
        geometry.reconstruct_active_target_state_13(service, snapshot)

    boundary = service.copy()
    boundary[13] = 0.0
    with pytest.raises(
        geometry.GeometryReplayError,
        match="CENTERED_PERTURBATION_OUTSIDE_DOMAIN:0",
    ):
        geometry.build_geometry_sign_fixture(
            boundary,
            independent_target_state_13=_target_rows(
                active["rk4_coarse"]["trace"]
            )[0],
        )
    with pytest.raises(geometry.GeometryReplayError, match="INVALID_CENTERED_STEP"):
        geometry.centered_gap_jacobian(
            service,
            independent_target_state_13=_target_rows(
                active["rk4_coarse"]["trace"]
            )[0],
            step_m=float("nan"),
        )


def test_exactly_one_active_or_post_target_source_is_required() -> None:
    _, acquisitions, active = _immutable_records()
    service = _service_rows(active["rk4_coarse"]["trace"])[0]
    target = _target_rows(active["rk4_coarse"]["trace"])[0]
    snapshot = acquisitions["rk4_coarse"]["snapshot"]
    with pytest.raises(geometry.GeometryReplayError, match="EXACTLY_ONE_TARGET_SOURCE"):
        geometry.centered_gap_jacobian(service)
    with pytest.raises(geometry.GeometryReplayError, match="EXACTLY_ONE_TARGET_SOURCE"):
        geometry.centered_gap_jacobian(
            service,
            snapshot=snapshot,
            independent_target_state_13=target,
        )
