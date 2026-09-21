from __future__ import annotations

import numpy as np

from r2_full_integrity.clearance import certify_clearance_independent


def test_constant_bilateral_clearance_observes_one_millisecond_dwell() -> None:
    result = certify_clearance_independent(
        [0.0, 0.001, 0.002],
        [2.0e-6, 2.0e-6, 2.0e-6],
        [2.0e-6, 2.0e-6, 2.0e-6],
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0],
        acquisition_time_s=-0.001,
        ledger_interval_certified=[True, True],
    )
    assert result["finite_event"] is True
    assert result["removal_time_s"] == 0.001
    assert result["endpoint_only"] is False


def test_endpoint_good_but_hermite_interior_bad_is_rejected() -> None:
    result = certify_clearance_independent(
        [0.0, 0.001],
        [2.0e-6, 2.0e-6],
        [2.0e-6, 2.0e-6],
        [-0.01, 0.01],
        [0.0, 0.0],
        acquisition_time_s=-0.001,
        ledger_interval_certified=[True],
    )
    assert result["finite_event"] is False


def test_single_side_clearance_cannot_create_bilateral_event() -> None:
    result = certify_clearance_independent(
        np.asarray([0.0, 0.001, 0.002]),
        np.asarray([2.0e-6, 2.0e-6, 2.0e-6]),
        np.asarray([0.5e-6, 0.5e-6, 0.5e-6]),
        np.zeros(3),
        np.zeros(3),
        acquisition_time_s=-0.001,
        ledger_interval_certified=np.ones(2, dtype=bool),
    )
    assert result["finite_event"] is False
