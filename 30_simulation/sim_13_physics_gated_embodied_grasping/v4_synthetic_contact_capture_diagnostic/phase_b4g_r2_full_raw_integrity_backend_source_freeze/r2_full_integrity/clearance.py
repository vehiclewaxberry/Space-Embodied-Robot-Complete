"""Independent continuous bilateral-clearance classifier.

The implementation uses every real root of each cubic-Hermite gap and rate
threshold polynomial; endpoint-only classification is impossible.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np


class ClearanceError(ValueError):
    pass


def _real_roots_unit(coefficients: Sequence[float]) -> list[float]:
    values = np.asarray(coefficients, dtype=float)
    scale = float(np.max(np.abs(values))) if len(values) else 0.0
    if not math.isfinite(scale) or scale == 0.0:
        return []
    values = values / scale
    first = 0
    while first < len(values) - 1 and abs(float(values[first])) <= 1.0e-14:
        first += 1
    values = values[first:]
    if len(values) <= 1:
        return []
    roots = np.roots(values)
    accepted = [
        float(root.real) for root in roots
        if abs(float(root.imag)) <= 1.0e-10
        and -1.0e-12 <= float(root.real) <= 1.0 + 1.0e-12
    ]
    return sorted(set(round(min(1.0, max(0.0, item)), 14) for item in accepted))


def _hermite(y0: float, y1: float, d0: float, d1: float, dt: float) -> tuple[float, float, float, float]:
    return (
        2.0 * y0 - 2.0 * y1 + dt * (d0 + d1),
        -3.0 * y0 + 3.0 * y1 - dt * (2.0 * d0 + d1),
        dt * d0,
        y0,
    )


def certify_clearance_independent(
    time_s: Any,
    left_gap_m: Any,
    right_gap_m: Any,
    left_gap_rate_m_s: Any,
    right_gap_rate_m_s: Any,
    *,
    acquisition_time_s: float,
    ledger_interval_certified: Any,
) -> dict[str, Any]:
    time = np.asarray(time_s, dtype=float)
    left_gap = np.asarray(left_gap_m, dtype=float)
    right_gap = np.asarray(right_gap_m, dtype=float)
    left_rate = np.asarray(left_gap_rate_m_s, dtype=float)
    right_rate = np.asarray(right_gap_rate_m_s, dtype=float)
    ledger = np.asarray(ledger_interval_certified, dtype=bool)
    if not (
        time.ndim == 1 and len(time) >= 2
        and np.all(np.isfinite(time)) and np.all(np.diff(time) > 0.0)
        and math.isfinite(float(acquisition_time_s))
    ):
        raise ClearanceError("CLEARANCE_TIME_INVALID")
    if (
        any(value.shape != time.shape for value in (left_gap, right_gap, left_rate, right_rate))
        or ledger.shape != (len(time) - 1,)
    ):
        raise ClearanceError("CLEARANCE_SHAPE_INVALID")
    if not all(np.all(np.isfinite(value)) for value in (left_gap, right_gap, left_rate, right_rate)):
        raise ClearanceError("CLEARANCE_NONFINITE")

    eligible: list[tuple[float, float]] = []
    for index in range(len(time) - 1):
        if not ledger[index]:
            continue
        dt = float(time[index + 1] - time[index])
        polynomials = [
            _hermite(float(gap[index]), float(gap[index + 1]), float(rate[index]), float(rate[index + 1]), dt)
            for gap, rate in ((left_gap, left_rate), (right_gap, right_rate))
        ]
        boundaries = {0.0, 1.0}
        for a, b, c, d in polynomials:
            boundaries.update(_real_roots_unit((a, b, c, d - 1.0e-6)))
            boundaries.update(_real_roots_unit((3.0 * a / dt, 2.0 * b / dt, c / dt + 1.0e-6)))
        ordered = sorted(boundaries)
        for lower, upper in zip(ordered[:-1], ordered[1:]):
            if upper - lower <= 1.0e-13:
                continue
            middle = 0.5 * (lower + upper)
            passed = True
            for a, b, c, d in polynomials:
                gap_value = ((a * middle + b) * middle + c) * middle + d
                rate_value = (3.0 * a * middle * middle + 2.0 * b * middle + c) / dt
                passed &= gap_value >= 1.0e-6 and rate_value >= -1.0e-6
            if passed:
                eligible.append((float(time[index] + lower * dt), float(time[index] + upper * dt)))

    merged: list[list[float]] = []
    for lower, upper in sorted(eligible):
        if merged and lower <= merged[-1][1] + 1.0e-12:
            merged[-1][1] = max(merged[-1][1], upper)
        else:
            merged.append([lower, upper])
    earliest = float(acquisition_time_s) + 0.001
    for lower, upper in merged:
        tau = max(lower, earliest)
        if upper - tau >= 0.001 - 1.0e-12:
            return {
                "finite_event": True,
                "tau_c_s": tau,
                "removal_time_s": tau + 0.001,
                "certified_good_interval_s": [lower, upper],
                "certified_good_intervals_s": merged,
                "algorithm": "PIECEWISE_CUBIC_HERMITE_ALL_ROOT_PARTITION_EARLIEST_DWELL",
                "endpoint_only": False,
            }
    return {
        "finite_event": False,
        "tau_c_s": None,
        "removal_time_s": None,
        "certified_good_intervals_s": merged,
        "algorithm": "PIECEWISE_CUBIC_HERMITE_ALL_ROOT_PARTITION_EARLIEST_DWELL",
        "endpoint_only": False,
    }


__all__ = ["ClearanceError", "certify_clearance_independent"]
