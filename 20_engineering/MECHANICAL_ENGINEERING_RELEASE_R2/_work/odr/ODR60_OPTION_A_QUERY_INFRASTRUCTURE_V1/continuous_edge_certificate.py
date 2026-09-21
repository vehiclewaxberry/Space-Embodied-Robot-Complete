"""Fail-closed continuous certificate for a linear joint-space edge.

The proof uses a certified *relative* scalar-clearance Lipschitz vector.  Each
coefficient must already contain the sum of both objects' motion bounds.  For
a linear edge, ``0.5 * sum((L_Ai + L_Bi) * |dq_i|)`` bounds clearance loss
from the interval midpoint to any point in that interval.  If that physical
bound is absent, non-finite, or exhausted by the required margin, recursion
ends in UNKNOWN rather than ALLOW.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Callable, Mapping, Sequence


SAFE = "SAFE_CERTIFIED"
UNSAFE = "UNSAFE_SAMPLE_WITNESS"
UNKNOWN = "UNKNOWN_ABORT"


@dataclass(frozen=True)
class CertifiedJointLipschitzBound:
    coefficients_mm_per_coordinate: tuple[float, ...]
    source_id: str
    source_sha256: str
    authority_class: str = "SYNTHETIC_FIXTURE_ONLY"
    pair_id: str | None = None
    object_a_id: str | None = None
    object_b_id: str | None = None
    object_a_geometry_sha256: str | None = None
    object_b_geometry_sha256: str | None = None
    scene_state_sha256: str | None = None
    acm_sha256: str | None = None
    oracle_implementation_sha256: str | None = None
    joint_coordinate_units: tuple[str, ...] | None = None
    q_domain_lower: tuple[float, ...] | None = None
    q_domain_upper: tuple[float, ...] | None = None

    @staticmethod
    def _valid_sha256(value: Any) -> bool:
        return isinstance(value, str) and len(value) == 64 and all(
            char in "0123456789ABCDEF" for char in value.upper()
        )

    def validate(
        self,
        dimension: int,
        q0: Sequence[float] | None = None,
        q1: Sequence[float] | None = None,
    ) -> tuple[bool, list[str]]:
        issues: list[str] = []
        try:
            coefficient_count = len(self.coefficients_mm_per_coordinate)
        except TypeError:
            coefficient_count = -1
        if coefficient_count != dimension:
            issues.append("BOUND_DIMENSION_MISMATCH")
        if not self.source_id:
            issues.append("BOUND_SOURCE_ID_ABSENT")
        if not self._valid_sha256(self.source_sha256):
            issues.append("BOUND_SOURCE_SHA256_INVALID")
        if self.authority_class not in {
            "SYNTHETIC_FIXTURE_ONLY",
            "CERTIFIED_GEOMETRY_RELATIVE_MOTION_BOUND",
        }:
            issues.append("BOUND_AUTHORITY_NOT_CERTIFIED")
        try:
            coefficients = tuple(float(value) for value in self.coefficients_mm_per_coordinate)
        except (TypeError, ValueError, OverflowError):
            coefficients = ()
            issues.append("BOUND_COEFFICIENT_NOT_NUMERIC")
        if coefficients and any(
            not math.isfinite(value) or value < 0.0 for value in coefficients
        ):
            issues.append("BOUND_COEFFICIENT_NONFINITE_OR_NEGATIVE")

        if self.authority_class == "CERTIFIED_GEOMETRY_RELATIVE_MOTION_BOUND":
            text_fields = {
                "PAIR_ID_ABSENT": self.pair_id,
                "OBJECT_A_ID_ABSENT": self.object_a_id,
                "OBJECT_B_ID_ABSENT": self.object_b_id,
            }
            for issue, value in text_fields.items():
                if not isinstance(value, str) or not value:
                    issues.append(issue)
            if self.object_a_id == self.object_b_id:
                issues.append("PAIR_OBJECT_IDS_NOT_DISTINCT")
            hash_fields = {
                "OBJECT_A_GEOMETRY_SHA256_INVALID": self.object_a_geometry_sha256,
                "OBJECT_B_GEOMETRY_SHA256_INVALID": self.object_b_geometry_sha256,
                "SCENE_STATE_SHA256_INVALID": self.scene_state_sha256,
                "ACM_SHA256_INVALID": self.acm_sha256,
                "ORACLE_IMPLEMENTATION_SHA256_INVALID": (
                    self.oracle_implementation_sha256
                ),
            }
            for issue, value in hash_fields.items():
                if not self._valid_sha256(value):
                    issues.append(issue)
            if (
                self.joint_coordinate_units is None
                or len(self.joint_coordinate_units) != dimension
                or any(unit != "rad" for unit in self.joint_coordinate_units)
            ):
                issues.append("JOINT_COORDINATE_UNITS_NOT_ALL_RAD")
            try:
                lower = tuple(float(value) for value in (self.q_domain_lower or ()))
                upper = tuple(float(value) for value in (self.q_domain_upper or ()))
            except (TypeError, ValueError, OverflowError):
                lower, upper = (), ()
                issues.append("Q_DOMAIN_NOT_NUMERIC")
            if len(lower) != dimension or len(upper) != dimension:
                issues.append("Q_DOMAIN_DIMENSION_MISMATCH")
            elif any(
                not math.isfinite(lo)
                or not math.isfinite(hi)
                or lo > hi
                for lo, hi in zip(lower, upper)
            ):
                issues.append("Q_DOMAIN_INVALID")
            elif q0 is not None and q1 is not None and any(
                value < lo or value > hi
                for q in (q0, q1)
                for value, lo, hi in zip(q, lower, upper)
            ):
                issues.append("EDGE_ENDPOINT_OUTSIDE_CERTIFIED_Q_DOMAIN")
        return not issues, issues

    def interval_bound_mm(
        self, q0: Sequence[float], q1: Sequence[float]
    ) -> float:
        return float(
            sum(
                coefficient * abs(float(b) - float(a))
                for coefficient, a, b in zip(
                    self.coefficients_mm_per_coordinate, q0, q1
                )
            )
        )


def _q_tuple(q: Sequence[float], dimension: int | None = None) -> tuple[float, ...]:
    if isinstance(q, (str, bytes)):
        raise ValueError("q must be a numeric sequence")
    values = tuple(float(value) for value in q)
    if dimension is not None and len(values) != dimension:
        raise ValueError("edge endpoint dimension mismatch")
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("edge endpoint must be finite and non-empty")
    return values


def _sample_or_unknown(
    oracle: Callable[[tuple[float, ...]], Mapping[str, Any]],
    q: tuple[float, ...],
) -> dict[str, Any]:
    try:
        raw = oracle(q)
    except Exception as exc:  # fail closed at the adapter boundary
        return {
            "status": UNKNOWN,
            "q": list(q),
            "clearance_mm": None,
            "reason": f"ORACLE_EXCEPTION_{type(exc).__name__}",
        }
    if not isinstance(raw, Mapping):
        return {
            "status": UNKNOWN,
            "q": list(q),
            "clearance_mm": None,
            "reason": "ORACLE_RESULT_NOT_MAPPING",
        }
    status = raw.get("status")
    clearance = raw.get("clearance_mm")
    if status not in {"PASS", "FAIL", "UNKNOWN"}:
        return {
            "status": UNKNOWN,
            "q": list(q),
            "clearance_mm": None,
            "reason": "ORACLE_STATUS_INVALID",
        }
    if status == "UNKNOWN" or clearance is None:
        return {
            "status": UNKNOWN,
            "q": list(q),
            "clearance_mm": None,
            "reason": str(raw.get("reason", "ORACLE_UNKNOWN")),
        }
    if status == "FAIL":
        try:
            value = float(clearance)
            if not math.isfinite(value):
                value = None
        except (TypeError, ValueError, OverflowError):
            value = None
        return {
            "status": UNSAFE,
            "q": list(q),
            "clearance_mm": value,
            "reason": str(raw.get("reason", "ORACLE_REPORTED_FAIL")),
            "witness": raw.get("witness"),
        }
    try:
        value = float(clearance)
    except (TypeError, ValueError, OverflowError):
        return {
            "status": UNKNOWN,
            "q": list(q),
            "clearance_mm": None,
            "reason": "ORACLE_CLEARANCE_NOT_NUMERIC",
        }
    if not math.isfinite(value):
        return {
            "status": UNKNOWN,
            "q": list(q),
            "clearance_mm": None,
            "reason": "ORACLE_CLEARANCE_NONFINITE",
        }
    return {
        "status": "EVALUATED",
        "q": list(q),
        "clearance_mm": value,
        "reason": str(raw.get("reason", "ORACLE_EVALUATED")),
        "witness": raw.get("witness"),
    }


def certify_linear_joint_edge(
    q0: Sequence[float],
    q1: Sequence[float],
    *,
    oracle: Callable[[tuple[float, ...]], Mapping[str, Any]],
    motion_bound: CertifiedJointLipschitzBound | None,
    required_clearance_mm: float = 0.0,
    numerical_reserve_mm: float = 0.0,
    max_depth: int = 18,
    minimum_joint_span: float = 1e-8,
) -> dict[str, Any]:
    """Certify, falsify, or return UNKNOWN for one linear q-space edge."""

    a = _q_tuple(q0)
    b = _q_tuple(q1, len(a))
    if not math.isfinite(required_clearance_mm) or required_clearance_mm < 0.0:
        raise ValueError("required_clearance_mm must be finite and non-negative")
    if not math.isfinite(numerical_reserve_mm) or numerical_reserve_mm < 0.0:
        raise ValueError("numerical_reserve_mm must be finite and non-negative")
    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")
    if not math.isfinite(minimum_joint_span) or minimum_joint_span < 0.0:
        raise ValueError("minimum_joint_span must be finite and non-negative")

    if motion_bound is None:
        return {
            "schema": "ODR60_CONTINUOUS_EDGE_CERTIFICATE_V1",
            "status": UNKNOWN,
            "reason": "CERTIFIED_RELATIVE_MOTION_BOUND_ABSENT",
            "q0": list(a),
            "q1": list(b),
            "sample_count": 0,
            "path_search_authorized": False,
            "next_stage_authorized": False,
            "release_credit": False,
        }
    bound_ok, bound_issues = motion_bound.validate(len(a), a, b)
    if not bound_ok:
        return {
            "schema": "ODR60_CONTINUOUS_EDGE_CERTIFICATE_V1",
            "status": UNKNOWN,
            "reason": "CERTIFIED_RELATIVE_MOTION_BOUND_INVALID",
            "bound_issues": bound_issues,
            "q0": list(a),
            "q1": list(b),
            "sample_count": 0,
            "path_search_authorized": False,
            "next_stage_authorized": False,
            "release_credit": False,
        }

    cache: dict[tuple[float, ...], dict[str, Any]] = {}
    leaves: list[dict[str, Any]] = []
    unsafe_witness: dict[str, Any] | None = None
    unknown_reason: str | None = None
    max_depth_reached = 0

    def sample(q: tuple[float, ...]) -> dict[str, Any]:
        if q not in cache:
            cache[q] = _sample_or_unknown(oracle, q)
        return cache[q]

    def recurse(left: tuple[float, ...], right: tuple[float, ...], depth: int) -> str:
        nonlocal unsafe_witness, unknown_reason, max_depth_reached
        max_depth_reached = max(max_depth_reached, depth)
        s_left = sample(left)
        s_right = sample(right)
        for current in (s_left, s_right):
            if current["status"] == UNKNOWN:
                unknown_reason = current["reason"]
                return UNKNOWN
            if current["status"] == UNSAFE:
                unsafe_witness = current
                return UNSAFE
            if float(current["clearance_mm"]) <= (
                required_clearance_mm + numerical_reserve_mm
            ):
                unsafe_witness = {
                    **current,
                    "reason": "SAMPLE_DOES_NOT_STRICTLY_EXCEED_CLEARANCE_THRESHOLD",
                }
                return UNSAFE

        midpoint = tuple(0.5 * (x + y) for x, y in zip(left, right))
        s_mid = sample(midpoint)
        if s_mid["status"] == UNKNOWN:
            unknown_reason = s_mid["reason"]
            return UNKNOWN
        if s_mid["status"] == UNSAFE:
            unsafe_witness = s_mid
            return UNSAFE
        if float(s_mid["clearance_mm"]) <= (
            required_clearance_mm + numerical_reserve_mm
        ):
            unsafe_witness = {
                **s_mid,
                "reason": "SAMPLE_DOES_NOT_STRICTLY_EXCEED_CLEARANCE_THRESHOLD",
            }
            return UNSAFE

        full_interval_bound = motion_bound.interval_bound_mm(left, right)
        midpoint_relative_motion_bound = 0.5 * full_interval_bound
        midpoint_clearance = float(s_mid["clearance_mm"])
        certified_lower = midpoint_clearance - midpoint_relative_motion_bound
        if certified_lower > (required_clearance_mm + numerical_reserve_mm):
            leaves.append(
                {
                    "depth": depth,
                    "q0": list(left),
                    "q1": list(right),
                    "full_interval_relative_motion_bound_mm": full_interval_bound,
                    "midpoint_relative_motion_bound_mm": midpoint_relative_motion_bound,
                    "midpoint_clearance_mm": midpoint_clearance,
                    "certified_clearance_lower_bound_mm": certified_lower,
                }
            )
            return SAFE

        span = max(abs(y - x) for x, y in zip(left, right))
        if depth >= max_depth:
            unknown_reason = "MAX_RECURSION_DEPTH_WITHOUT_CERTIFICATE"
            return UNKNOWN
        if span <= minimum_joint_span:
            unknown_reason = "MINIMUM_JOINT_SPAN_REACHED_WITHOUT_CERTIFICATE"
            return UNKNOWN

        left_status = recurse(left, midpoint, depth + 1)
        if left_status != SAFE:
            return left_status
        return recurse(midpoint, right, depth + 1)

    status = recurse(a, b, 0)
    payload = {
        "schema": "ODR60_CONTINUOUS_EDGE_CERTIFICATE_V1",
        "proof_method": "RECURSIVE_LINEAR_Q_EDGE_MIDPOINT_SUBDIVISION_WITH_CERTIFIED_CLEARANCE_LIPSCHITZ_BOUND",
        "status": status,
        "reason": (
            "ALL_LEAF_INTERVALS_STRICTLY_EXCEED_REQUIRED_CLEARANCE_AND_RESERVE"
            if status == SAFE
            else str(
                (unsafe_witness or {}).get(
                    "reason", "EXACT_SAMPLE_DOES_NOT_EXCEED_REQUIRED_CLEARANCE"
                )
            )
            if status == UNSAFE
            else unknown_reason or "UNKNOWN_ABORT"
        ),
        "q0": list(a),
        "q1": list(b),
        "required_clearance_mm": float(required_clearance_mm),
        "numerical_reserve_mm": float(numerical_reserve_mm),
        "strict_acceptance_threshold_mm": float(
            required_clearance_mm + numerical_reserve_mm
        ),
        "motion_bound": {
            "coefficients_mm_per_coordinate": list(
                motion_bound.coefficients_mm_per_coordinate
            ),
            "source_id": motion_bound.source_id,
            "source_sha256": motion_bound.source_sha256,
            "authority_class": motion_bound.authority_class,
            "pair_binding": {
                "pair_id": motion_bound.pair_id,
                "object_a_id": motion_bound.object_a_id,
                "object_b_id": motion_bound.object_b_id,
                "object_a_geometry_sha256": motion_bound.object_a_geometry_sha256,
                "object_b_geometry_sha256": motion_bound.object_b_geometry_sha256,
                "scene_state_sha256": motion_bound.scene_state_sha256,
                "acm_sha256": motion_bound.acm_sha256,
                "oracle_implementation_sha256": (
                    motion_bound.oracle_implementation_sha256
                ),
                "joint_coordinate_units": (
                    list(motion_bound.joint_coordinate_units)
                    if motion_bound.joint_coordinate_units is not None
                    else None
                ),
                "q_domain_lower": (
                    list(motion_bound.q_domain_lower)
                    if motion_bound.q_domain_lower is not None
                    else None
                ),
                "q_domain_upper": (
                    list(motion_bound.q_domain_upper)
                    if motion_bound.q_domain_upper is not None
                    else None
                ),
            },
        },
        "certificate_scope": motion_bound.authority_class,
        "sample_count": len(cache),
        "samples": list(cache.values()),
        "certified_leaf_count": len(leaves),
        "certified_leaves": leaves,
        "maximum_depth_reached": max_depth_reached,
        "unsafe_witness": unsafe_witness,
        "unknown_is_never_safe": True,
        "threshold_contact_is_never_safe": True,
        "system_pair_evaluation_authorized": False,
        "path_search_authorized": False,
        "path_search_executed": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    payload["canonical_payload_sha256"] = hashlib.sha256(canonical).hexdigest().upper()
    return payload
