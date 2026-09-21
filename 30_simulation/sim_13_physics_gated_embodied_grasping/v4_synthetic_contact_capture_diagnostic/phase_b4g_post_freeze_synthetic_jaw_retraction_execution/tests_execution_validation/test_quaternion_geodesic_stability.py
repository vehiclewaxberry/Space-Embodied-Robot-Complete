"""Adversarial tests for the validator's independent A0 quaternion metric."""

from __future__ import annotations

import math

import numpy as np
import pytest

from b4g_validation import validator
from b4g_validation.core import ValidationReport


def _a0_inputs(
    raw_quaternion: np.ndarray,
    parent_quaternion: np.ndarray,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], np.ndarray]:
    raw_q = np.asarray(raw_quaternion, dtype=float)
    count = int(raw_q.shape[0])
    state = np.zeros((count, 29), dtype="<f8")
    state[:, 3:7] = raw_q
    raw = {
        "service_state_29": state,
        "left_gap_m": np.zeros(count, dtype="<f8"),
        "right_gap_m": np.zeros(count, dtype="<f8"),
        "left_gap_rate_m_s": np.zeros(count, dtype="<f8"),
        "right_gap_rate_m_s": np.zeros(count, dtype="<f8"),
    }
    parent = {
        "service_position_m": np.zeros((count, 3), dtype="<f8"),
        "service_quaternion_wxyz": np.asarray(parent_quaternion, dtype=float),
        "R_joint_coordinates_rad": np.zeros((count, 6), dtype="<f8"),
        "P_joint_coordinates_m": np.zeros((count, 2), dtype="<f8"),
        "base_linear_m_s": np.zeros((count, 3), dtype="<f8"),
        "base_angular_rad_s": np.zeros((count, 3), dtype="<f8"),
        "R_joint_rad_s": np.zeros((count, 6), dtype="<f8"),
        "P_joint_m_s": np.zeros((count, 2), dtype="<f8"),
        "left_gap_m": np.zeros(count, dtype="<f8"),
        "right_gap_m": np.zeros(count, dtype="<f8"),
        "left_gap_rate_m_s": np.zeros(count, dtype="<f8"),
        "right_gap_rate_m_s": np.zeros(count, dtype="<f8"),
    }
    return raw, parent, np.ones(count, dtype=bool)


def _rotation_about_x(angle_rad: float) -> np.ndarray:
    return np.asarray([
        math.cos(0.5 * angle_rad), math.sin(0.5 * angle_rad), 0.0, 0.0,
    ])


def test_pathological_self_dot_one_ulp_is_exact_zero() -> None:
    quaternion = np.asarray([1.0, 1.0, 1.0, 5.0], dtype=float)
    quaternion /= np.linalg.norm(quaternion)
    assert float(quaternion @ quaternion) == np.nextafter(1.0, 0.0)
    legacy_acos_error = 2.0 * math.acos(abs(float(quaternion @ quaternion)))
    assert legacy_acos_error > 1.0e-12
    assert validator._stable_quaternion_geodesic_max(
        quaternion[None, :], quaternion[None, :],
    ) == 0.0


def test_antipodal_quaternions_are_the_same_attitude() -> None:
    quaternion = np.asarray([0.5, -0.5, 0.5, -0.5], dtype=float)
    assert validator._stable_quaternion_geodesic_max(
        quaternion[None, :], -quaternion[None, :],
    ) == 0.0


def test_orthogonal_unit_quaternions_are_pi_apart() -> None:
    value = validator._stable_quaternion_geodesic_max(
        np.asarray([[1.0, 0.0, 0.0, 0.0]]),
        np.asarray([[0.0, 1.0, 0.0, 0.0]]),
    )
    assert value == pytest.approx(math.pi, rel=0.0, abs=4.0e-16)


@pytest.mark.parametrize(
    ("angle_rad", "within_threshold"),
    [(5.0e-13, True), (2.0e-12, False)],
)
def test_a0_channel_preserves_registered_one_picoradian_threshold(
    angle_rad: float,
    within_threshold: bool,
) -> None:
    raw, parent, mask = _a0_inputs(
        _rotation_about_x(angle_rad)[None, :],
        np.asarray([[1.0, 0.0, 0.0, 0.0]]),
    )
    computed = validator._a0_channel_maxima(raw, parent, mask)
    value = computed["service_quaternion_geodesic_rad"]
    assert value == pytest.approx(angle_rad, rel=0.0, abs=1.0e-27)
    assert (value <= 1.0e-12) is within_threshold


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (np.zeros((1, 4)), np.asarray([[1.0, 0.0, 0.0, 0.0]])),
        (np.asarray([[1.0 + 2.0e-12, 0.0, 0.0, 0.0]]), np.asarray([[1.0, 0.0, 0.0, 0.0]])),
        (np.asarray([[np.nan, 0.0, 0.0, 0.0]]), np.asarray([[1.0, 0.0, 0.0, 0.0]])),
        (np.asarray([[np.inf, 0.0, 0.0, 0.0]]), np.asarray([[1.0, 0.0, 0.0, 0.0]])),
        (np.asarray([[10**1000, 0, 0, 0]], dtype=object), np.asarray([[1.0, 0.0, 0.0, 0.0]])),
        (np.asarray([1.0, 0.0, 0.0, 0.0]), np.asarray([1.0, 0.0, 0.0, 0.0])),
        (np.asarray([[1.0, 0.0, 0.0]]), np.asarray([[1.0, 0.0, 0.0]])),
        (np.asarray([[1.0, 0.0, 0.0, 0.0]]), np.ones((2, 4)) / 2.0),
        (np.empty((0, 4)), np.empty((0, 4))),
    ],
    ids=("zero", "nonunit", "nan", "inf", "overflow", "rank", "width", "row-count", "empty"),
)
def test_invalid_quaternion_arrays_fail_closed_to_infinity(
    left: np.ndarray,
    right: np.ndarray,
) -> None:
    assert math.isinf(validator._stable_quaternion_geodesic_max(left, right))


def test_a0_invalid_parent_quaternion_fails_closed_to_infinity() -> None:
    raw, parent, mask = _a0_inputs(
        np.asarray([[1.0, 0.0, 0.0, 0.0]]),
        np.asarray([[0.0, 0.0, 0.0, 0.0]]),
    )
    computed = validator._a0_channel_maxima(raw, parent, mask)
    assert math.isinf(computed["service_quaternion_geodesic_rad"])


def test_all_six_frozen_parent_self_geodesics_are_exact_zero() -> None:
    report = ValidationReport(mode="campaign")
    _, _, traces = validator._load_b4e_provenance_templates(report)
    assert report.passed, report.failures
    assert set(traces) == set(validator.LANES)
    for lane in validator.LANES:
        parent = traces[lane]
        count = len(parent["time_s"])
        state = np.zeros((count, 29), dtype="<f8")
        state[:, 0:3] = parent["service_position_m"]
        state[:, 3:7] = parent["service_quaternion_wxyz"]
        state[:, 7:13] = parent["R_joint_coordinates_rad"]
        state[:, 13:15] = parent["P_joint_coordinates_m"]
        state[:, 15:18] = parent["base_linear_m_s"]
        state[:, 18:21] = parent["base_angular_rad_s"]
        state[:, 21:27] = parent["R_joint_rad_s"]
        state[:, 27:29] = parent["P_joint_m_s"]
        raw = {
            "service_state_29": state,
            "left_gap_m": parent["left_gap_m"],
            "right_gap_m": parent["right_gap_m"],
            "left_gap_rate_m_s": parent["left_gap_rate_m_s"],
            "right_gap_rate_m_s": parent["right_gap_rate_m_s"],
        }
        computed = validator._a0_channel_maxima(
            raw, parent, np.ones(count, dtype=bool),
        )
        assert computed == {name: 0.0 for name in computed}, lane
