"""Unit-labelled R2 distances, contractions, and total-order comparator."""

from __future__ import annotations

import math
from typing import Any, Sequence


MIDPOINT_CONTRACTION = 2.0 ** -1.8
RK4_CONTRACTION = 0.125
ACQUISITION_CONTRACTION = 0.60

COMMON_PROP_CHANNELS: dict[str, dict[str, Any]] = {
    "service_position_m": {"metric": "Linf", "floor": 1e-12, "unit": "m"},
    "service_quaternion_body_to_inertial_wxyz": {"metric": "B4G_R2_STABLE_SIGN_INVARIANT_QUATERNION_GEODESIC_V1", "floor": 1e-12, "unit": "rad"},
    "R_joint_coordinates_rad": {"metric": "Linf", "floor": 1e-12, "unit": "rad"},
    "P_joint_coordinates_m": {"metric": "Linf", "floor": 1e-12, "unit": "m"},
    "service_base_linear_velocity_m_s": {"metric": "Linf", "floor": 1e-12, "unit": "m/s"},
    "service_base_angular_velocity_rad_s": {"metric": "Linf", "floor": 1e-12, "unit": "rad/s"},
    "R_joint_velocity_rad_s": {"metric": "Linf", "floor": 1e-12, "unit": "rad/s"},
    "P_joint_velocity_m_s": {"metric": "Linf", "floor": 1e-12, "unit": "m/s"},
    "target_position_m": {"metric": "Linf", "floor": 1e-12, "unit": "m"},
    "target_quaternion_body_to_inertial_wxyz": {"metric": "B4G_R2_STABLE_SIGN_INVARIANT_QUATERNION_GEODESIC_V1", "floor": 1e-12, "unit": "rad"},
    "target_linear_velocity_m_s": {"metric": "Linf", "floor": 1e-12, "unit": "m/s"},
    "target_angular_velocity_rad_s": {"metric": "Linf", "floor": 1e-12, "unit": "rad/s"},
    "total_linear_momentum_kg_m_s": {"metric": "Linf", "floor": 1e-12, "unit": "kg*m/s"},
    "total_angular_momentum_kg_m2_s": {"metric": "Linf", "floor": 1e-12, "unit": "kg*m^2/s"},
    "total_kinetic_energy_J": {"metric": "absolute", "floor": 2e-12, "unit": "J"},
    "energy_minus_work_residual_J": {"metric": "absolute", "floor": 2e-12, "unit": "J"},
}

FRESH_ACQ_CHANNELS: dict[str, dict[str, Any]] = {
    "service_position_m": {"metric": "Linf", "floor": 1e-12, "unit": "m"},
    "service_quaternion": {"metric": "stable_geodesic", "floor": 1e-12, "unit": "rad"},
    "R_joint_coordinates_rad": {"metric": "Linf", "floor": 1e-12, "unit": "rad"},
    "P_joint_coordinates_m": {"metric": "Linf", "floor": 1e-12, "unit": "m"},
    "service_base_linear_velocity_m_s": {"metric": "Linf", "floor": 1e-12, "unit": "m/s"},
    "service_base_angular_velocity_rad_s": {"metric": "Linf", "floor": 1e-12, "unit": "rad/s"},
    "R_joint_velocity_rad_s": {"metric": "Linf", "floor": 1e-12, "unit": "rad/s"},
    "P_joint_velocity_m_s": {"metric": "Linf", "floor": 1e-12, "unit": "m/s"},
    "target_position_m": {"metric": "Linf", "floor": 1e-12, "unit": "m"},
    "target_quaternion": {"metric": "stable_geodesic", "floor": 1e-12, "unit": "rad"},
    "target_linear_velocity_m_s": {"metric": "Linf", "floor": 1e-12, "unit": "m/s"},
    "target_angular_velocity_rad_s": {"metric": "Linf", "floor": 1e-12, "unit": "rad/s"},
    "linear_momentum_native": {"metric": "Linf", "floor": 1e-12, "unit": "kg*m/s"},
    "angular_momentum_native": {"metric": "Linf", "floor": 1e-12, "unit": "kg*m^2/s"},
    "D_B3_minus_J": {"metric": "absolute", "floor": 2e-12, "unit": "J"},
    "switch_energy_identity_J": {"metric": "absolute", "floor": 2e-12, "unit": "J"},
}

# Backward-compatible name is deliberately the COMMON_PROP map; fresh callers
# must name FRESH_ACQ_CHANNELS explicitly.
CHANNELS = COMMON_PROP_CHANNELS

CHANNEL_WIDTHS = {
    "service_position_m": 3,
    "service_quaternion_body_to_inertial_wxyz": 4,
    "service_quaternion": 4,
    "R_joint_coordinates_rad": 6,
    "P_joint_coordinates_m": 2,
    "service_base_linear_velocity_m_s": 3,
    "service_base_angular_velocity_rad_s": 3,
    "R_joint_velocity_rad_s": 6,
    "P_joint_velocity_m_s": 2,
    "target_position_m": 3,
    "target_quaternion_body_to_inertial_wxyz": 4,
    "target_quaternion": 4,
    "target_linear_velocity_m_s": 3,
    "target_angular_velocity_rad_s": 3,
    "total_linear_momentum_kg_m_s": 3,
    "linear_momentum_native": 3,
    "total_angular_momentum_kg_m2_s": 3,
    "angular_momentum_native": 3,
    "total_kinetic_energy_J": 1,
    "energy_minus_work_residual_J": 1,
    "D_B3_minus_J": 1,
    "switch_energy_identity_J": 1,
}


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def stable_quaternion_geodesic_rad(q1_wxyz: Sequence[float], q2_wxyz: Sequence[float], *, unit_norm_tolerance: float = 1e-12) -> dict[str, Any]:
    invalid = {"valid": False, "category": "INVALID_QUATERNION", "distance_rad": "NOT_EVALUATED_INVALID_QUATERNION"}
    if (
        not isinstance(q1_wxyz, (list, tuple)) or not isinstance(q2_wxyz, (list, tuple))
        or len(q1_wxyz) != 4 or len(q2_wxyz) != 4
        or not _number(unit_norm_tolerance) or unit_norm_tolerance < 0.0
        or any(not _number(value) for value in (*q1_wxyz, *q2_wxyz))
    ):
        return invalid
    norm1 = math.sqrt(sum(float(value) ** 2 for value in q1_wxyz))
    norm2 = math.sqrt(sum(float(value) ** 2 for value in q2_wxyz))
    if norm1 == 0.0 or norm2 == 0.0 or abs(norm1 - 1.0) > unit_norm_tolerance or abs(norm2 - 1.0) > unit_norm_tolerance:
        return invalid
    q1 = tuple(float(value) / norm1 for value in q1_wxyz)
    q2 = tuple(float(value) / norm2 for value in q2_wxyz)
    sign = 1.0 if sum(left * right for left, right in zip(q1, q2)) >= 0.0 else -1.0
    numerator = math.sqrt(sum((left - sign * right) ** 2 for left, right in zip(q1, q2)))
    denominator = math.sqrt(sum((left + sign * right) ** 2 for left, right in zip(q1, q2)))
    distance = 4.0 * math.atan2(numerator, denominator)
    if not math.isfinite(distance) or distance < 0.0 or distance > math.pi:
        return invalid
    return {"valid": True, "category": "VALID_QUATERNION_GEODESIC", "distance_rad": distance}


def _samples(value: Any, width: int) -> list[list[float]]:
    if width == 1 and _number(value):
        return [[float(value)]]
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError("CHANNEL_HISTORY_EMPTY_OR_NOT_SEQUENCE")
    if width == 1 and all(_number(item) for item in value):
        return [[float(item)] for item in value]
    if len(value) == width and all(_number(item) for item in value):
        return [[float(item) for item in value]]
    rows: list[list[float]] = []
    for row in value:
        if not isinstance(row, (list, tuple)) or len(row) != width or any(not _number(item) for item in row):
            raise ValueError("CHANNEL_SAMPLE_WIDTH_OR_VALUE_INVALID")
        rows.append([float(item) for item in row])
    if not rows:
        raise ValueError("CHANNEL_HISTORY_EMPTY")
    return rows


def channel_distance(channel: str, left: Any, right: Any, *, channel_specs: dict[str, dict[str, Any]] = COMMON_PROP_CHANNELS) -> float:
    if channel not in channel_specs or channel not in CHANNEL_WIDTHS:
        raise ValueError(f"UNREGISTERED_CHANNEL:{channel}")
    metric = channel_specs[channel]["metric"]
    left_rows = _samples(left, CHANNEL_WIDTHS[channel])
    right_rows = _samples(right, CHANNEL_WIDTHS[channel])
    if len(left_rows) != len(right_rows):
        raise ValueError("CHANNEL_HISTORY_SAMPLE_COUNT_MISMATCH")
    if metric in {"stable_geodesic", "B4G_R2_STABLE_SIGN_INVARIANT_QUATERNION_GEODESIC_V1"}:
        distances = []
        for q1, q2 in zip(left_rows, right_rows):
            result = stable_quaternion_geodesic_rad(q1, q2)
            if not result["valid"]:
                raise ValueError("INVALID_QUATERNION_CHANNEL")
            distances.append(float(result["distance_rad"]))
        return max(distances, default=0.0)
    return max(abs(a - b) for lrow, rrow in zip(left_rows, right_rows) for a, b in zip(lrow, rrow))


def channel_sample_count(channel: str, value: Any, *, channel_specs: dict[str, dict[str, Any]] = COMMON_PROP_CHANNELS) -> int:
    if channel not in channel_specs or channel not in CHANNEL_WIDTHS:
        raise ValueError(f"UNREGISTERED_CHANNEL:{channel}")
    return len(_samples(value, CHANNEL_WIDTHS[channel]))


def evaluate_channel_triplet(channel: str, coarse: Any, fine: Any, reference: Any, *, contraction: float, channel_specs: dict[str, dict[str, Any]] = COMMON_PROP_CHANNELS) -> dict[str, Any]:
    if channel not in channel_specs or not _number(contraction) or contraction < 0.0:
        return {"passed": False, "status": "INVALID_CHANNEL_OR_CONTRACTION"}
    try:
        d_cf = channel_distance(channel, coarse, fine, channel_specs=channel_specs)
        d_fr = channel_distance(channel, fine, reference, channel_specs=channel_specs)
    except ValueError as exc:
        return {"passed": False, "status": str(exc)}
    floor = float(channel_specs[channel]["floor"])
    passed = d_fr <= float(contraction) * d_cf + floor
    return {"passed": passed, "status": "PASS" if passed else "FAIL_CONTRACTION", "channel": channel, "unit": channel_specs[channel]["unit"], "D_CF": d_cf, "D_FR": d_fr, "floor": floor, "contraction": float(contraction)}


def evaluate_direct_order_triplet(errors_J: Any, *, floor_J: float, p_min: float, floor_scope: str) -> dict[str, Any]:
    invalid_order = "NOT_EVALUATED_INVALID_INPUT"
    invalid = {"passed": False, "category": "INVALID_INPUT_NONFINITE_NEGATIVE_OR_SCHEMA", "CF": {"passed": False, "order_status": invalid_order, "order_value": invalid_order}, "FR": {"passed": False, "order_status": invalid_order, "order_value": invalid_order}}
    if (
        not isinstance(errors_J, (list, tuple)) or len(errors_J) != 3
        or not _number(floor_J) or floor_J <= 0.0 or not _number(p_min) or p_min < 0.0
        or floor_scope not in {"FINE_AND_REFERENCE", "ALL_THREE"}
        or any(not _number(value) or float(value) < 0.0 for value in errors_J)
    ):
        return invalid
    coarse, fine, reference = (float(value) for value in errors_J)
    relevant = (fine, reference) if floor_scope == "FINE_AND_REFERENCE" else (coarse, fine, reference)
    if all(value <= floor_J for value in relevant):
        sentinel = "NOT_EVALUATED_OVERALL_FLOOR_RESOLVED"
        return {"passed": True, "category": "OVERALL_FLOOR_RESOLVED", "CF": {"passed": True, "order_status": sentinel, "order_value": sentinel}, "FR": {"passed": True, "order_status": sentinel, "order_value": sentinel}}

    def pair(left: float, right: float) -> dict[str, Any]:
        if left <= floor_J and right <= floor_J:
            status = "NOT_EVALUATED_PAIR_FLOOR_RESOLVED"
            return {"passed": True, "order_status": status, "order_value": status}
        if left <= floor_J and right > floor_J:
            status = "NOT_EVALUATED_REGRESSION_FROM_FLOOR"
            return {"passed": False, "order_status": status, "order_value": status}
        if left > floor_J and right == 0.0:
            status = "EXACT_ZERO_FINE_POSITIVE_ORDER_LIMIT"
            return {"passed": True, "order_status": status, "order_value": status}
        if left > floor_J and 0.0 < right <= floor_J:
            status = "FINE_FLOOR_RESOLVED_POSITIVE_ORDER_LIMIT"
            return {"passed": True, "order_status": status, "order_value": status}
        order = math.log2(left) - math.log2(right)
        return {"passed": order >= p_min, "order_status": "FINITE_LOG2_ORDER", "order_value": order}

    cf, fr = pair(coarse, fine), pair(fine, reference)
    passed = bool(cf["passed"] and fr["passed"])
    return {"passed": passed, "category": "PAIRWISE_ORDER_PASS" if passed else "PAIRWISE_ORDER_FAIL", "CF": cf, "FR": fr}


def finest_cross_method_limit(d_fr_midpoint: float, d_fr_rk4: float, floor: float) -> float:
    if any(not _number(value) or float(value) < 0.0 for value in (d_fr_midpoint, d_fr_rk4, floor)):
        raise ValueError("INVALID_RICHARDSON_INPUT")
    return float(d_fr_midpoint) / (2.0 ** 1.8 - 1.0) + float(d_fr_rk4) / (2.0 ** 3.0 - 1.0) + float(floor)
