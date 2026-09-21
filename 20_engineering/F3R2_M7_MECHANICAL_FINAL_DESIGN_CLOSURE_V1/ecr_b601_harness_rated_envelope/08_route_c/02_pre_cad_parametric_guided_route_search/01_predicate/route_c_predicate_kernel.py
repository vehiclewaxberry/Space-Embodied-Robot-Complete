#!/usr/bin/env python3
"""Pure-standard-library synthetic predicate kernel for Route-C C1.5.

This module intentionally consumes no CAD, FreeCAD, URDF parser, mesh library or
third-party numerical package.  It qualifies fail-closed semantics on analytic
closed boxes, line segments and sampled curves only.  A self-test PASS is not a
physical Route-C design result.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from copy import deepcopy
from typing import Any, Dict, Iterable, List, Sequence, Tuple

sys.dont_write_bytecode = True

EPS = 1.0e-12
ALLOWED_CONTACT_CLASSES = {
    "GUIDED_SPAN": {"GUIDE"},
    "CLAMPED_SPAN": {"CLAMP"},
    "CONNECTOR_TRANSITION": {"CONNECTOR"},
    "FREE_SPAN": set(),
}
FORBIDDEN_EXEMPTION_TOKENS = {
    "WHOLE_LINK",
    "WHOLE_ROBOT",
    "INFINITE_VOLUME",
    "UNBOUNDED_HALFSPACE",
    "OWNER_WILDCARD",
}
FAILURE_FIELDS = ("state", "q", "segment", "point", "object_pair", "margin")
IDENTIFIER_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*$")
SEGMENT_ID_RE = re.compile(r"^SEG-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
SAMPLE_ID_RE = re.compile(r"^SMP-[A-Z0-9]+(?:-[A-Z0-9]+)*$")
FORBIDDEN_SCOPE_MARKERS = ("WHOLE-LINK", "WHOLE_LINK", "WHOLELINK", "WHOLE-ROBOT", "INFINITE", "UNBOUNDED", "WILDCARD")


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _finite_vector(value: Any, size: int) -> bool:
    return isinstance(value, (list, tuple)) and len(value) == size and all(_finite_number(v) for v in value)


def _result(status: str, reason: str, **extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"status": status, "reason": reason}
    payload.update(extra)
    return payload


def validate_finite_volume(volume: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a named, finite AABB contact or obstacle volume."""
    required = ("object_id", "object_class", "scope_kind", "owner_segment", "bounds_min_mm", "bounds_max_mm")
    if any(field not in volume for field in required):
        return _result("UNKNOWN", "MISSING_VOLUME_FIELD")
    object_id = volume["object_id"]
    object_class = volume["object_class"]
    scope_kind = volume["scope_kind"]
    owner = volume["owner_segment"]
    if not isinstance(object_id, str) or not IDENTIFIER_RE.fullmatch(object_id):
        return _result("UNKNOWN", "INVALID_OBJECT_ID")
    normalized_object_id = object_id.upper()
    if any(marker in normalized_object_id for marker in FORBIDDEN_SCOPE_MARKERS):
        return _result("FAIL", "FORBIDDEN_OBJECT_SCOPE_MARKER")
    upper_tokens = {str(object_id).upper(), str(object_class).upper(), str(owner).upper()}
    if upper_tokens & FORBIDDEN_EXEMPTION_TOKENS:
        return _result("FAIL", "FORBIDDEN_UNBOUNDED_OR_WILDCARD_EXEMPTION")
    if scope_kind != "LOCAL_FINITE_CONTACT_VOLUME":
        return _result("FAIL", "NONLOCAL_OR_UNBOUNDED_SCOPE_KIND")
    if object_class not in {"GUIDE", "CLAMP", "CONNECTOR", "OBSTACLE"}:
        return _result("UNKNOWN", "UNSUPPORTED_OBJECT_CLASS")
    if object_class in {"GUIDE", "CLAMP", "CONNECTOR"} and (
        not isinstance(owner, str) or not SEGMENT_ID_RE.fullmatch(owner)
    ):
        return _result("UNKNOWN", "MISSING_OR_INVALID_SINGLE_CONTACT_OWNER")
    if object_class == "OBSTACLE" and owner not in (None, ""):
        return _result("FAIL", "OBSTACLE_CANNOT_GRANT_CONTACT_EXEMPTION")
    bmin = volume["bounds_min_mm"]
    bmax = volume["bounds_max_mm"]
    if not _finite_vector(bmin, 3) or not _finite_vector(bmax, 3):
        return _result("FAIL", "NONFINITE_OR_UNBOUNDED_VOLUME")
    if not all(float(lo) < float(hi) for lo, hi in zip(bmin, bmax)):
        return _result("FAIL", "DEGENERATE_OR_REVERSED_VOLUME")
    return _result("PASS", "FINITE_NAMED_VOLUME")


def signed_distance_closed_aabb_mm(
    point_mm: Sequence[float], bounds_min_mm: Sequence[float], bounds_max_mm: Sequence[float]
) -> float:
    """Return robust signed distance to a finite closed axis-aligned box.

    Positive is outside, zero is on the boundary, and negative is inside.  The
    interior branch returns the nearest-face depth; it never collapses deep
    penetration to unsigned zero.
    """
    if not (_finite_vector(point_mm, 3) and _finite_vector(bounds_min_mm, 3) and _finite_vector(bounds_max_mm, 3)):
        raise ValueError("point and bounds must be finite three-vectors")
    if not all(float(lo) < float(hi) for lo, hi in zip(bounds_min_mm, bounds_max_mm)):
        raise ValueError("bounds must be finite and strictly ordered")
    outside_components = [
        max(float(lo) - float(p), 0.0, float(p) - float(hi))
        for p, lo, hi in zip(point_mm, bounds_min_mm, bounds_max_mm)
    ]
    outside_distance = math.sqrt(sum(component * component for component in outside_components))
    if outside_distance > 0.0:
        return outside_distance
    face_depth = min(
        min(float(p) - float(lo), float(hi) - float(p))
        for p, lo, hi in zip(point_mm, bounds_min_mm, bounds_max_mm)
    )
    return -face_depth


def serialize_failure(
    *,
    state: str,
    q: Sequence[float],
    segment: str,
    point: Sequence[float],
    object_pair: Sequence[str],
    margin: float,
    failure_type: str,
) -> Dict[str, Any]:
    return {
        "failure_type": failure_type,
        "state": state,
        "q": [float(value) for value in q],
        "segment": segment,
        "point": [float(value) for value in point],
        "object_pair": list(object_pair),
        "margin": float(margin),
        "margin_unit": "mm",
    }


def failure_record_complete(record: Dict[str, Any]) -> bool:
    if not isinstance(record, dict) or any(field not in record for field in FAILURE_FIELDS):
        return False
    return (
        isinstance(record["state"], str)
        and bool(record["state"].strip())
        and _finite_vector(record["q"], 6)
        and isinstance(record["segment"], str)
        and bool(record["segment"].strip())
        and _finite_vector(record["point"], 3)
        and isinstance(record["object_pair"], (list, tuple))
        and len(record["object_pair"]) == 2
        and all(isinstance(value, str) and value.strip() for value in record["object_pair"])
        and _finite_number(record["margin"])
    )


def evaluate_contact(comparison: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate one centerline-point versus one finite closed volume."""
    required = ("state", "q", "segment_id", "segment_class", "point_mm", "cable_radius_mm", "object")
    if any(field not in comparison for field in required):
        return _result("UNKNOWN", "MISSING_COMPARISON_FIELD")
    state = comparison["state"]
    q = comparison["q"]
    segment_id = comparison["segment_id"]
    segment_class = comparison["segment_class"]
    point = comparison["point_mm"]
    cable_radius = comparison["cable_radius_mm"]
    if not isinstance(state, str) or not state.strip() or not _finite_vector(q, 6):
        return _result("UNKNOWN", "MISSING_OR_INVALID_STATE")
    if not isinstance(segment_id, str) or not SEGMENT_ID_RE.fullmatch(segment_id) or segment_class not in ALLOWED_CONTACT_CLASSES:
        return _result("UNKNOWN", "INVALID_SEGMENT_SEMANTICS")
    if not _finite_vector(point, 3) or not _finite_number(cable_radius) or float(cable_radius) < 0.0:
        return _result("UNKNOWN", "INVALID_POINT_OR_RADIUS")
    volume = comparison["object"]
    volume_check = validate_finite_volume(volume)
    if volume_check["status"] != "PASS":
        return volume_check
    signed_distance = signed_distance_closed_aabb_mm(point, volume["bounds_min_mm"], volume["bounds_max_mm"])
    margin = signed_distance - float(cable_radius)
    if margin > 0.0:
        return _result("PASS", "NO_CONTACT", margin_mm=margin, signed_distance_mm=signed_distance)
    permitted_class = volume["object_class"] in ALLOWED_CONTACT_CLASSES[segment_class]
    owner_matches = volume["owner_segment"] == segment_id
    if permitted_class and owner_matches:
        return _result(
            "PASS",
            "FINITE_NAMED_OWNER_MATCHED_CONTACT",
            margin_mm=margin,
            signed_distance_mm=signed_distance,
            permitted_object_id=volume["object_id"],
        )
    failure = serialize_failure(
        state=state,
        q=q,
        segment=segment_id,
        point=point,
        object_pair=(segment_id, volume["object_id"]),
        margin=margin,
        failure_type="COLLISION",
    )
    return _result("FAIL", "CONTACT_NOT_AUTHORIZED", failure=failure)


def evaluate_scene(scene: Dict[str, Any]) -> Dict[str, Any]:
    if scene.get("source_hash_drift") is True:
        return _result("UNKNOWN", "SOURCE_HASH_DRIFT")
    if not isinstance(scene.get("state"), str) or not scene["state"].strip():
        return _result("UNKNOWN", "MISSING_STATE")
    if not _finite_vector(scene.get("q"), 6):
        return _result("UNKNOWN", "MISSING_Q")
    comparisons = scene.get("comparisons")
    if not isinstance(comparisons, list) or len(comparisons) == 0:
        return _result("UNKNOWN", "EMPTY_COMPARISON_SET")
    objects = scene.get("objects")
    if not isinstance(objects, list) or len(objects) == 0:
        return _result("UNKNOWN", "MISSING_OBJECT_REGISTRY")
    object_ids: List[str] = []
    object_registry: Dict[str, Dict[str, Any]] = {}
    for volume in objects:
        if not isinstance(volume, dict):
            return _result("UNKNOWN", "INVALID_OBJECT_REGISTRY_ENTRY")
        object_id = volume.get("object_id")
        if not isinstance(object_id, str) or not object_id.strip():
            return _result("UNKNOWN", "MISSING_OBJECT_ID")
        object_ids.append(object_id)
        object_registry[object_id] = volume
    if len(set(object_ids)) != len(object_ids):
        return _result("UNKNOWN", "DUPLICATE_OBJECT_ID_IN_SCENE_REGISTRY")
    segments = scene.get("segments")
    if not isinstance(segments, list) or len(segments) == 0:
        return _result("UNKNOWN", "MISSING_SEGMENT_REGISTRY")
    segment_ids: List[str] = []
    segment_registry: Dict[str, str] = {}
    for segment_record in segments:
        if not isinstance(segment_record, dict) or set(segment_record) != {"segment_id", "segment_class"}:
            return _result("UNKNOWN", "INVALID_SEGMENT_REGISTRY_ENTRY")
        segment_id = segment_record["segment_id"]
        segment_class = segment_record["segment_class"]
        if not isinstance(segment_id, str) or not SEGMENT_ID_RE.fullmatch(segment_id):
            return _result("UNKNOWN", "INVALID_SEGMENT_REGISTRY_ID")
        if segment_class not in ALLOWED_CONTACT_CLASSES:
            return _result("UNKNOWN", "INVALID_SEGMENT_REGISTRY_CLASS")
        segment_ids.append(segment_id)
        segment_registry[segment_id] = segment_class
    if len(set(segment_ids)) != len(segment_ids):
        return _result("UNKNOWN", "DUPLICATE_SEGMENT_ID_IN_SCENE_REGISTRY")
    for volume in objects:
        volume_check = validate_finite_volume(volume)
        if volume_check["status"] != "PASS":
            return _result("UNKNOWN", "INVALID_OBJECT_REGISTRY", object_validation=volume_check)
        if volume["object_class"] in {"GUIDE", "CLAMP", "CONNECTOR"} and volume["owner_segment"] not in segment_registry:
            return _result("UNKNOWN", "OBJECT_OWNER_NOT_IN_SEGMENT_REGISTRY")
    samples = scene.get("samples")
    if not isinstance(samples, list) or len(samples) == 0:
        return _result("UNKNOWN", "MISSING_SAMPLE_REGISTRY")
    sample_ids: List[str] = []
    sample_registry: Dict[str, Dict[str, Any]] = {}
    required_sample_fields = {"sample_id", "segment_id", "point_mm", "cable_radius_mm"}
    for sample in samples:
        if not isinstance(sample, dict) or set(sample) != required_sample_fields:
            return _result("UNKNOWN", "INVALID_SAMPLE_REGISTRY_ENTRY")
        sample_id = sample["sample_id"]
        segment_id = sample["segment_id"]
        if not isinstance(sample_id, str) or not SAMPLE_ID_RE.fullmatch(sample_id):
            return _result("UNKNOWN", "INVALID_SAMPLE_REGISTRY_ID")
        if segment_id not in segment_registry:
            return _result("UNKNOWN", "SAMPLE_SEGMENT_NOT_IN_REGISTRY")
        if not _finite_vector(sample["point_mm"], 3) or not _finite_number(sample["cable_radius_mm"]) or float(sample["cable_radius_mm"]) < 0.0:
            return _result("UNKNOWN", "INVALID_SAMPLE_POINT_OR_RADIUS")
        sample_ids.append(sample_id)
        sample_registry[sample_id] = sample
    if len(set(sample_ids)) != len(sample_ids):
        return _result("UNKNOWN", "DUPLICATE_SAMPLE_ID_IN_SCENE_REGISTRY")
    comparison_pairs: List[Tuple[str, str]] = []
    for raw in comparisons:
        if not isinstance(raw, dict) or set(raw) != {"sample_id", "object_id"}:
            return _result("UNKNOWN", "INLINE_OR_EXTRA_COMPARISON_FIELDS_FORBIDDEN")
        sample_id = raw["sample_id"]
        object_id = raw["object_id"]
        if sample_id not in sample_registry:
            return _result("UNKNOWN", "MISSING_SAMPLE_REGISTRY_REFERENCE")
        if object_id not in object_registry:
            return _result("UNKNOWN", "MISSING_OBJECT_REGISTRY_REFERENCE")
        comparison_pairs.append((sample_id, object_id))
    if len(set(comparison_pairs)) != len(comparison_pairs):
        return _result("UNKNOWN", "DUPLICATE_SAMPLE_OBJECT_COMPARISON_PAIR")
    expected_pairs = {(sample_id, object_id) for sample_id in sample_ids for object_id in object_ids}
    actual_pairs = set(comparison_pairs)
    if actual_pairs != expected_pairs:
        return _result(
            "UNKNOWN",
            "INCOMPLETE_SAMPLE_OBJECT_COMPARISON_COVERAGE",
            missing_pairs=[list(pair) for pair in sorted(expected_pairs - actual_pairs)],
            extra_pairs=[list(pair) for pair in sorted(actual_pairs - expected_pairs)],
        )
    results: List[Dict[str, Any]] = []
    for sample_id, object_id in comparison_pairs:
        sample = sample_registry[sample_id]
        segment_id = sample["segment_id"]
        item = deepcopy(sample)
        item.pop("sample_id", None)
        item["segment_class"] = segment_registry[segment_id]
        item["object"] = object_registry[object_id]
        item["state"] = scene["state"]
        item["q"] = scene["q"]
        result = evaluate_contact(item)
        results.append(result)
        if result["status"] == "UNKNOWN":
            return _result("UNKNOWN", "COMPARISON_UNKNOWN", comparisons=results)
        if result["status"] == "FAIL":
            return _result("FAIL", "COLLISION", comparisons=results, failure=result["failure"])
    return _result("PASS", "ALL_COMPARISONS_PASS", comparisons=results)


def evaluate_pinch(
    *, state: str, q: Sequence[float], segment: str, point: Sequence[float], object_pair: Sequence[str], margin_mm: float
) -> Dict[str, Any]:
    if not isinstance(state, str) or not state.strip() or not _finite_vector(q, 6):
        return _result("UNKNOWN", "MISSING_OR_INVALID_STATE")
    if not isinstance(segment, str) or not segment.strip():
        return _result("UNKNOWN", "MISSING_OR_INVALID_SEGMENT")
    if (
        not isinstance(object_pair, (list, tuple))
        or len(object_pair) != 2
        or not all(isinstance(value, str) and value.strip() for value in object_pair)
    ):
        return _result("UNKNOWN", "MISSING_OR_INVALID_OBJECT_PAIR")
    if not _finite_vector(point, 3) or not _finite_number(margin_mm):
        return _result("UNKNOWN", "INVALID_PINCH_INPUT")
    if margin_mm > 0.0:
        return _result("PASS", "POSITIVE_PINCH_MARGIN", margin_mm=float(margin_mm))
    failure = serialize_failure(
        state=state,
        q=q,
        segment=segment,
        point=point,
        object_pair=object_pair,
        margin=margin_mm,
        failure_type="PINCH",
    )
    return _result("FAIL", "PINCH_MARGIN_NONPOSITIVE", failure=failure)


def _sub(a: Sequence[float], b: Sequence[float]) -> Tuple[float, float, float]:
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b))


def _norm(a: Sequence[float]) -> float:
    return math.sqrt(_dot(a, a))


def _cross(a: Sequence[float], b: Sequence[float]) -> Tuple[float, float, float]:
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _add(a: Sequence[float], b: Sequence[float]) -> Tuple[float, float, float]:
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]), float(a[2]) + float(b[2]))


def _scale(a: Sequence[float], scalar: float) -> Tuple[float, float, float]:
    return (float(a[0]) * scalar, float(a[1]) * scalar, float(a[2]) * scalar)


def common_circle_crosscheck(points: Sequence[Sequence[float]]) -> Dict[str, Any]:
    """Prove sampled points share one plane, one center and one radius."""
    p0, p1, p2 = points[0], points[1], points[2]
    a = _sub(p1, p0)
    b = _sub(p2, p0)
    normal = _cross(a, b)
    normal_sq = _dot(normal, normal)
    if normal_sq <= EPS:
        return _result("FAIL", "CIRCULAR_ARC_REFERENCE_TRIPLE_COLLINEAR")
    unit_normal = _scale(normal, 1.0 / math.sqrt(normal_sq))
    term_a = _scale(_cross(b, normal), _dot(a, a))
    term_b = _scale(_cross(normal, a), _dot(b, b))
    center_offset = _scale(_add(term_a, term_b), 1.0 / (2.0 * normal_sq))
    center = _add(p0, center_offset)
    radii = [_norm(_sub(point, center)) for point in points]
    mean_radius = sum(radii) / len(radii)
    tolerance = max(1.0e-7, 1.0e-7 * mean_radius)
    maximum_plane_deviation = max(abs(_dot(_sub(point, p0), unit_normal)) for point in points)
    maximum_radius_deviation = max(abs(radius - mean_radius) for radius in radii)
    if maximum_plane_deviation > tolerance:
        return _result(
            "FAIL",
            "DECLARED_CIRCULAR_ARC_NOT_COPLANAR",
            max_plane_deviation_mm=maximum_plane_deviation,
            tolerance_mm=tolerance,
        )
    if maximum_radius_deviation > tolerance:
        return _result(
            "FAIL",
            "DECLARED_CIRCULAR_ARC_HAS_NO_COMMON_CENTER_AND_RADIUS",
            max_radius_deviation_mm=maximum_radius_deviation,
            tolerance_mm=tolerance,
        )
    return _result(
        "PASS",
        "COMMON_PLANE_CENTER_AND_RADIUS",
        center_mm=list(center),
        plane_normal=list(unit_normal),
        radius_mm=mean_radius,
        max_plane_deviation_mm=maximum_plane_deviation,
        max_radius_deviation_mm=maximum_radius_deviation,
        tolerance_mm=tolerance,
    )


def validate_arc_sample_order(
    points: Sequence[Sequence[float]], center: Sequence[float], plane_normal: Sequence[float]
) -> Dict[str, Any]:
    """Require a regular, single-direction, sub-revolution arc parameterization."""
    first_radial = _sub(points[0], center)
    first_radius = _norm(first_radial)
    if first_radius <= EPS:
        return _result("FAIL", "ARC_SAMPLE_AT_CIRCLE_CENTER")
    basis_u = _scale(first_radial, 1.0 / first_radius)
    basis_v_raw = _cross(plane_normal, basis_u)
    basis_v_norm = _norm(basis_v_raw)
    if basis_v_norm <= EPS:
        return _result("FAIL", "ARC_PLANE_BASIS_DEGENERATE")
    basis_v = _scale(basis_v_raw, 1.0 / basis_v_norm)
    raw_angles = [
        math.atan2(_dot(_sub(point, center), basis_v), _dot(_sub(point, center), basis_u))
        for point in points
    ]
    angular_tolerance = 1.0e-10
    increments: List[float] = []
    unwrapped = [raw_angles[0]]
    direction = 0
    for previous, current in zip(raw_angles, raw_angles[1:]):
        delta = (current - previous + math.pi) % (2.0 * math.pi) - math.pi
        if abs(abs(delta) - math.pi) <= angular_tolerance:
            return _result("FAIL", "ARC_ADJACENT_ANGULAR_STEP_AMBIGUOUS_OR_TOO_LARGE")
        if abs(delta) <= angular_tolerance:
            return _result("FAIL", "ARC_ZERO_ANGULAR_INCREMENT")
        step_direction = 1 if delta > 0.0 else -1
        if direction == 0:
            direction = step_direction
        elif step_direction != direction:
            return _result(
                "FAIL",
                "ARC_PARAMETER_DIRECTION_REVERSAL",
                angular_increments_rad=increments + [delta],
            )
        increments.append(delta)
        unwrapped.append(unwrapped[-1] + delta)
    total_sweep = unwrapped[-1] - unwrapped[0]
    if abs(total_sweep) >= 2.0 * math.pi - angular_tolerance:
        return _result("FAIL", "ARC_TOTAL_SWEEP_NOT_STRICTLY_BELOW_ONE_REVOLUTION", total_sweep_rad=total_sweep)
    return _result(
        "PASS",
        "STRICTLY_MONOTONIC_SINGLE_DIRECTION_ARC_PARAMETERIZATION",
        angular_increments_rad=increments,
        total_sweep_rad=total_sweep,
        direction="CCW" if direction > 0 else "CW",
    )


def circumradius_mm(a: Sequence[float], b: Sequence[float], c: Sequence[float]) -> float:
    ab = _sub(b, a)
    bc = _sub(c, b)
    ac = _sub(c, a)
    denominator = 2.0 * _norm(_cross(ab, ac))
    if denominator <= EPS:
        return math.inf
    return (_norm(ab) * _norm(bc) * _norm(ac)) / denominator


def has_cusp(points: Sequence[Sequence[float]]) -> bool:
    for a, b in zip(points, points[1:]):
        if _norm(_sub(b, a)) <= EPS:
            return True
    for a, b, c in zip(points, points[1:], points[2:]):
        incoming = _sub(b, a)
        outgoing = _sub(c, b)
        cosine = _dot(incoming, outgoing) / (_norm(incoming) * _norm(outgoing))
        if cosine <= -1.0 + 1.0e-10:
            return True
    return False


def segment_segment_distance_mm(
    p0: Sequence[float], p1: Sequence[float], q0: Sequence[float], q1: Sequence[float]
) -> float:
    """Shortest distance between two finite 3-D segments.

    The clamped closest-point formulation covers skew, parallel, collinear,
    overlapping and endpoint-touching segments.  Degenerate segments are
    rejected earlier as cusps by ``evaluate_curve``.
    """
    u = _sub(p1, p0)
    v = _sub(q1, q0)
    w = _sub(p0, q0)
    uu = _dot(u, u)
    uv = _dot(u, v)
    vv = _dot(v, v)
    uw = _dot(u, w)
    vw = _dot(v, w)
    denominator = uu * vv - uv * uv
    s_denominator = denominator
    t_denominator = denominator
    if uu <= EPS or vv <= EPS:
        raise ValueError("degenerate segment")
    if denominator <= EPS * max(uu * vv, 1.0):
        s_numerator = 0.0
        s_denominator = 1.0
        t_numerator = vw
        t_denominator = vv
    else:
        s_numerator = uv * vw - vv * uw
        t_numerator = uu * vw - uv * uw
        if s_numerator < 0.0:
            s_numerator = 0.0
            t_numerator = vw
            t_denominator = vv
        elif s_numerator > s_denominator:
            s_numerator = s_denominator
            t_numerator = vw + uv
            t_denominator = vv
    if t_numerator < 0.0:
        t_numerator = 0.0
        if -uw < 0.0:
            s_numerator = 0.0
        elif -uw > uu:
            s_numerator = s_denominator
        else:
            s_numerator = -uw
            s_denominator = uu
    elif t_numerator > t_denominator:
        t_numerator = t_denominator
        if -uw + uv < 0.0:
            s_numerator = 0.0
        elif -uw + uv > uu:
            s_numerator = s_denominator
        else:
            s_numerator = -uw + uv
            s_denominator = uu
    s = 0.0 if abs(s_numerator) <= EPS else s_numerator / s_denominator
    t = 0.0 if abs(t_numerator) <= EPS else t_numerator / t_denominator
    separation = (
        w[0] + s * u[0] - t * v[0],
        w[1] + s * u[1] - t * v[1],
        w[2] + s * u[2] - t * v[2],
    )
    return _norm(separation)


def has_self_intersection(points: Sequence[Sequence[float]]) -> bool:
    for i in range(len(points) - 1):
        for j in range(i + 2, len(points) - 1):
            if segment_segment_distance_mm(points[i], points[i + 1], points[j], points[j + 1]) <= 1.0e-9:
                return True
    return False


def evaluate_curve(curve: Dict[str, Any]) -> Dict[str, Any]:
    if curve.get("generator") == "UNCONSTRAINED_CATMULL_ROM":
        return _result("FAIL", "UNCONSTRAINED_CATMULL_ROM_FORBIDDEN")
    points = curve.get("points_mm")
    if not isinstance(points, list) or len(points) < 3 or not all(_finite_vector(point, 3) for point in points):
        return _result("UNKNOWN", "MISSING_OR_INVALID_CURVE_POINTS")
    if curve.get("continuity") not in {"C2", "CURVATURE_CONTINUOUS"}:
        return _result("FAIL", "CURVATURE_CONTINUITY_NOT_QUALIFIED")
    travel = curve.get("carrier_travel_mm")
    travel_bounds = curve.get("carrier_travel_bounds_mm")
    if not _finite_number(travel) or not _finite_vector(travel_bounds, 2):
        return _result("UNKNOWN", "MISSING_CARRIER_TRAVEL_OR_BOUNDS")
    if float(travel_bounds[0]) > float(travel_bounds[1]):
        return _result("UNKNOWN", "REVERSED_CARRIER_TRAVEL_BOUNDS")
    if not float(travel_bounds[0]) <= float(travel) <= float(travel_bounds[1]):
        return _result("FAIL", "CARRIER_TRAVEL_OUT_OF_BOUNDS")
    if has_cusp(points):
        return _result("FAIL", "CUSP_OR_ZERO_LENGTH_TANGENT")
    if has_self_intersection(points):
        return _result("FAIL", "CURVE_SELF_INTERSECTION")
    if curve.get("generator") != "ANALYTIC_CIRCULAR_ARC":
        return _result("FAIL", "GENERATOR_NOT_GEOMETRICALLY_QUALIFIED_FOR_C2")
    if len(points) < 5:
        return _result("UNKNOWN", "INSUFFICIENT_POINTS_FOR_CIRCULAR_ARC_QUALIFICATION")
    evidence = curve.get("continuity_evidence")
    if evidence != "ANALYTIC_CIRCLE_C_INFINITY_WITH_DISCRETE_GEOMETRY_CROSSCHECK":
        return _result("UNKNOWN", "MISSING_ANALYTIC_CONTINUITY_EVIDENCE")
    minimum_required = curve.get("minimum_bend_radius_required_mm")
    if not _finite_number(minimum_required) or float(minimum_required) < 0.0:
        return _result("UNKNOWN", "MISSING_MINIMUM_BEND_REQUIREMENT")
    radii = [circumradius_mm(a, b, c) for a, b, c in zip(points, points[1:], points[2:])]
    if not radii or not all(math.isfinite(radius) and radius > EPS for radius in radii):
        return _result("FAIL", "CIRCULAR_ARC_GEOMETRY_DEGENERATE")
    mean_radius = sum(radii) / len(radii)
    radius_spread = max(abs(radius - mean_radius) for radius in radii)
    allowed_radius_spread = max(1.0e-7, 1.0e-7 * mean_radius)
    if radius_spread > allowed_radius_spread:
        return _result(
            "FAIL",
            "DECLARED_ANALYTIC_CIRCULAR_ARC_FAILS_GEOMETRY_CROSSCHECK",
            mean_radius_mm=mean_radius,
            radius_spread_mm=radius_spread,
        )
    common_circle = common_circle_crosscheck(points)
    if common_circle["status"] != "PASS":
        return common_circle
    arc_order = validate_arc_sample_order(points, common_circle["center_mm"], common_circle["plane_normal"])
    if arc_order["status"] != "PASS":
        return arc_order
    declared_radius = curve.get("analytic_radius_mm")
    if not _finite_number(declared_radius) or abs(float(declared_radius) - common_circle["radius_mm"]) > allowed_radius_spread:
        return _result("UNKNOWN", "ANALYTIC_RADIUS_MISSING_OR_INCONSISTENT")
    path_minimum = min(radii)
    if path_minimum + 1.0e-9 < float(minimum_required):
        return _result("FAIL", "BEND_RADIUS_BELOW_REQUIREMENT", R_path_min_mm=path_minimum)
    return _result(
        "PASS",
        "C2_CURVATURE_CONTINUOUS_SYNTHETIC_CURVE",
        R_path_min_mm=path_minimum,
        common_circle_center_mm=common_circle["center_mm"],
        common_circle_radius_mm=common_circle["radius_mm"],
        arc_parameter_direction=arc_order["direction"],
        total_sweep_rad=arc_order["total_sweep_rad"],
    )


def feasible_candidate_ids(
    candidates: Iterable[Dict[str, float]], *, bundle_od_mm: float, bend_required_mm: float, keepout_mm: float
) -> List[str]:
    feasible: List[str] = []
    for candidate in candidates:
        clearance = float(candidate["base_centerline_clearance_mm"]) - 0.5 * float(bundle_od_mm) - float(keepout_mm)
        if (
            float(candidate["max_bundle_od_mm"]) + EPS >= float(bundle_od_mm)
            and float(candidate["path_min_radius_mm"]) + EPS >= float(bend_required_mm)
            and clearance + EPS >= 0.0
        ):
            feasible.append(str(candidate["id"]))
    return sorted(feasible)


def _test(test_id: str, control_class: str, condition: bool, observed: Any) -> Dict[str, Any]:
    return {
        "id": test_id,
        "control_class": control_class,
        "passed": bool(condition),
        "observed": observed,
    }


def run_qualification() -> Dict[str, Any]:
    q0 = [0.0] * 6
    obstacle = {
        "object_id": "OBS-BOX-01",
        "object_class": "OBSTACLE",
        "scope_kind": "LOCAL_FINITE_CONTACT_VOLUME",
        "owner_segment": None,
        "bounds_min_mm": [-10.0, -10.0, -10.0],
        "bounds_max_mm": [10.0, 10.0, 10.0],
    }
    guide = {
        "object_id": "GUIDE-J2-FINITE-01",
        "object_class": "GUIDE",
        "scope_kind": "LOCAL_FINITE_CONTACT_VOLUME",
        "owner_segment": "SEG-J2",
        "bounds_min_mm": [-2.0, -2.0, -2.0],
        "bounds_max_mm": [2.0, 2.0, 2.0],
    }
    clamp = {
        "object_id": "CLAMP-J3-FINITE-01",
        "object_class": "CLAMP",
        "scope_kind": "LOCAL_FINITE_CONTACT_VOLUME",
        "owner_segment": "SEG-J3",
        "bounds_min_mm": [-2.0, -2.0, -2.0],
        "bounds_max_mm": [2.0, 2.0, 2.0],
    }
    connector = {
        "object_id": "CONNECTOR-J6-FINITE-01",
        "object_class": "CONNECTOR",
        "scope_kind": "LOCAL_FINITE_CONTACT_VOLUME",
        "owner_segment": "SEG-J6",
        "bounds_min_mm": [-2.0, -2.0, -2.0],
        "bounds_max_mm": [2.0, 2.0, 2.0],
    }
    base_comparison = {
        "state": "SYNTH-Q0",
        "q": q0,
        "segment_id": "SEG-FREE",
        "segment_class": "FREE_SPAN",
        "point_mm": [0.0, 0.0, 0.0],
        "cable_radius_mm": 1.0,
        "object": obstacle,
    }
    positive: List[Dict[str, Any]] = []
    negative: List[Dict[str, Any]] = []

    exterior = signed_distance_closed_aabb_mm([13.0, 10.0, 10.0], [-10.0] * 3, [10.0] * 3)
    positive.append(_test("P01_SIGNED_DISTANCE_EXTERIOR", "POSITIVE", abs(exterior - 3.0) <= EPS, exterior))
    interior = signed_distance_closed_aabb_mm([0.0, 0.0, 0.0], [-10.0] * 3, [10.0] * 3)
    positive.append(_test("P02_DEEP_PENETRATION_RETAINS_SIGNED_DEPTH", "POSITIVE", abs(interior + 10.0) <= EPS, interior))

    guided = deepcopy(base_comparison)
    guided.update({"segment_id": "SEG-J2", "segment_class": "GUIDED_SPAN", "object": guide})
    guided_result = evaluate_contact(guided)
    positive.append(_test("P03_OWNER_MATCHED_FINITE_GUIDE_CONTACT", "POSITIVE", guided_result["status"] == "PASS", guided_result))

    clamped = deepcopy(base_comparison)
    clamped.update({"segment_id": "SEG-J3", "segment_class": "CLAMPED_SPAN", "object": clamp})
    clamped_result = evaluate_contact(clamped)
    positive.append(_test("P04_OWNER_MATCHED_FINITE_CLAMP_CONTACT", "POSITIVE", clamped_result["status"] == "PASS", clamped_result))

    connected = deepcopy(base_comparison)
    connected.update({"segment_id": "SEG-J6", "segment_class": "CONNECTOR_TRANSITION", "object": connector})
    connected_result = evaluate_contact(connected)
    positive.append(_test("P05_OWNER_MATCHED_FINITE_CONNECTOR_CONTACT", "POSITIVE", connected_result["status"] == "PASS", connected_result))

    multi_sample_scene = evaluate_scene(
        {
            "state": "SYNTH-MULTI-SAMPLE",
            "q": q0,
            "objects": [deepcopy(guide)],
            "segments": [{"segment_id": "SEG-J2", "segment_class": "GUIDED_SPAN"}],
            "samples": [
                {
                    "sample_id": "SMP-J2-01",
                    "segment_id": "SEG-J2",
                    "point_mm": [0.0, 0.0, 0.0],
                    "cable_radius_mm": 1.0,
                },
                {
                    "sample_id": "SMP-J2-02",
                    "segment_id": "SEG-J2",
                    "point_mm": [1.0, 0.0, 0.0],
                    "cable_radius_mm": 1.0,
                },
            ],
            "comparisons": [
                {"sample_id": "SMP-J2-01", "object_id": "GUIDE-J2-FINITE-01"},
                {"sample_id": "SMP-J2-02", "object_id": "GUIDE-J2-FINITE-01"},
            ],
        }
    )
    positive.append(_test("P06_UNIQUE_REGISTRY_OBJECT_SUPPORTS_MULTI_SAMPLE_REFERENCE", "POSITIVE", multi_sample_scene["status"] == "PASS", multi_sample_scene))

    no_contact = deepcopy(base_comparison)
    no_contact["point_mm"] = [20.0, 0.0, 0.0]
    no_contact_result = evaluate_contact(no_contact)
    positive.append(_test("P07_FREE_SPAN_WITH_POSITIVE_CLEARANCE", "POSITIVE", no_contact_result["status"] == "PASS", no_contact_result))

    radius = 50.0
    arc_points = [[radius * math.cos(math.radians(a)), radius * math.sin(math.radians(a)), 0.0] for a in range(0, 91, 15)]
    curve_ok = evaluate_curve(
        {
            "generator": "ANALYTIC_CIRCULAR_ARC",
            "continuity": "C2",
            "continuity_evidence": "ANALYTIC_CIRCLE_C_INFINITY_WITH_DISCRETE_GEOMETRY_CROSSCHECK",
            "analytic_radius_mm": radius,
            "points_mm": arc_points,
            "carrier_travel_mm": 20.0,
            "carrier_travel_bounds_mm": [0.0, 40.0],
            "minimum_bend_radius_required_mm": 45.0,
        }
    )
    positive.append(_test("P08_C2_CURVATURE_CONTINUOUS_ARC", "POSITIVE", curve_ok["status"] == "PASS", curve_ok))

    candidates = [
        {"id": "A", "max_bundle_od_mm": 8.0, "path_min_radius_mm": 20.0, "base_centerline_clearance_mm": 9.0},
        {"id": "B", "max_bundle_od_mm": 12.0, "path_min_radius_mm": 40.0, "base_centerline_clearance_mm": 14.0},
        {"id": "C", "max_bundle_od_mm": 18.0, "path_min_radius_mm": 70.0, "base_centerline_clearance_mm": 20.0},
    ]
    od_better = set(feasible_candidate_ids(candidates, bundle_od_mm=6.0, bend_required_mm=15.0, keepout_mm=1.0))
    od_worse = set(feasible_candidate_ids(candidates, bundle_od_mm=14.0, bend_required_mm=15.0, keepout_mm=1.0))
    positive.append(_test("P09_OD_WORSENING_MONOTONIC", "POSITIVE", od_worse <= od_better, {"better": sorted(od_better), "worse": sorted(od_worse)}))
    bend_better = set(feasible_candidate_ids(candidates, bundle_od_mm=6.0, bend_required_mm=15.0, keepout_mm=1.0))
    bend_worse = set(feasible_candidate_ids(candidates, bundle_od_mm=6.0, bend_required_mm=60.0, keepout_mm=1.0))
    positive.append(_test("P10_BEND_WORSENING_MONOTONIC", "POSITIVE", bend_worse <= bend_better, {"better": sorted(bend_better), "worse": sorted(bend_worse)}))
    keepout_better = set(feasible_candidate_ids(candidates, bundle_od_mm=6.0, bend_required_mm=15.0, keepout_mm=0.0))
    keepout_worse = set(feasible_candidate_ids(candidates, bundle_od_mm=6.0, bend_required_mm=15.0, keepout_mm=15.0))
    positive.append(_test("P11_KEEPOUT_WORSENING_MONOTONIC", "POSITIVE", keepout_worse <= keepout_better, {"better": sorted(keepout_better), "worse": sorted(keepout_worse)}))

    collision = evaluate_contact(base_comparison)
    negative.append(_test("N01_FREE_SPAN_CONTACT_FAILS", "NEGATIVE", collision["status"] == "FAIL", collision))
    negative.append(_test("N02_COLLISION_FAILURE_SERIALIZED", "NEGATIVE", failure_record_complete(collision.get("failure", {})), collision.get("failure")))

    wrong_owner = deepcopy(guided)
    wrong_owner["segment_id"] = "SEG-J3"
    wrong_owner_result = evaluate_contact(wrong_owner)
    negative.append(_test("N03_GUIDE_OWNER_MISMATCH_FAILS", "NEGATIVE", wrong_owner_result["status"] == "FAIL", wrong_owner_result))

    whole_link = deepcopy(guide)
    whole_link.update({"object_id": "GUIDE-LOCAL-TEST-01", "scope_kind": "WHOLE_LINK", "bounds_min_mm": [-2.0] * 3, "bounds_max_mm": [2.0] * 3})
    whole_link_result = validate_finite_volume(whole_link)
    negative.append(_test("N04_WHOLE_LINK_EXEMPTION_FORBIDDEN", "NEGATIVE", whole_link_result["status"] == "FAIL", whole_link_result))

    infinite = deepcopy(guide)
    infinite["bounds_max_mm"] = [math.inf, 2.0, 2.0]
    infinite_result = validate_finite_volume(infinite)
    negative.append(_test("N05_INFINITE_EXEMPTION_FORBIDDEN", "NEGATIVE", infinite_result["status"] == "FAIL", infinite_result))

    pinch = evaluate_pinch(
        state="SYNTH-PINCH", q=q0, segment="SEG-J5", point=[1.0, 2.0, 3.0], object_pair=["SEG-J5", "LINK5"], margin_mm=-0.5
    )
    negative.append(_test("N06_PINCH_NONPOSITIVE_FAILS", "NEGATIVE", pinch["status"] == "FAIL", pinch))
    negative.append(_test("N07_PINCH_FAILURE_SERIALIZED", "NEGATIVE", failure_record_complete(pinch.get("failure", {})), pinch.get("failure")))

    empty_scene = evaluate_scene({"state": "SYNTH", "q": q0, "comparisons": []})
    negative.append(_test("N08_EMPTY_COMPARISON_UNKNOWN", "NEGATIVE", empty_scene["status"] == "UNKNOWN", empty_scene))
    missing_state = evaluate_scene({"q": q0, "comparisons": [base_comparison]})
    negative.append(_test("N09_MISSING_STATE_UNKNOWN", "NEGATIVE", missing_state["status"] == "UNKNOWN", missing_state))
    missing_q = evaluate_scene({"state": "SYNTH", "comparisons": [base_comparison]})
    negative.append(_test("N10_MISSING_Q_UNKNOWN", "NEGATIVE", missing_q["status"] == "UNKNOWN", missing_q))
    hash_drift = evaluate_scene({"state": "SYNTH", "q": q0, "comparisons": [base_comparison], "source_hash_drift": True})
    negative.append(_test("N11_HASH_DRIFT_UNKNOWN", "NEGATIVE", hash_drift["status"] == "UNKNOWN", hash_drift))

    catmull = evaluate_curve(
        {
            "generator": "UNCONSTRAINED_CATMULL_ROM",
            "continuity": "C2",
            "points_mm": [[0.0, 0.0, 0.0], [1.0, 1.0, 0.0], [2.0, 0.0, 0.0]],
            "carrier_travel_mm": 1.0,
            "carrier_travel_bounds_mm": [0.0, 2.0],
            "minimum_bend_radius_required_mm": 0.1,
        }
    )
    negative.append(_test("N12_UNCONSTRAINED_CATMULL_ROM_FAILS", "NEGATIVE", catmull["status"] == "FAIL", catmull))

    cusp = evaluate_curve(
        {
            "generator": "PIECEWISE_ANALYTIC",
            "continuity": "C2",
            "points_mm": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
            "carrier_travel_mm": 1.0,
            "carrier_travel_bounds_mm": [0.0, 2.0],
            "minimum_bend_radius_required_mm": 0.1,
        }
    )
    negative.append(_test("N13_CUSP_INJECTION_FAILS", "NEGATIVE", cusp["status"] == "FAIL", cusp))

    self_intersection = evaluate_curve(
        {
            "generator": "PIECEWISE_ANALYTIC",
            "continuity": "C2",
            "points_mm": [[0.0, 0.0, 0.0], [2.0, 2.0, 0.0], [0.0, 2.0, 0.0], [2.0, 0.0, 0.0]],
            "carrier_travel_mm": 1.0,
            "carrier_travel_bounds_mm": [0.0, 2.0],
            "minimum_bend_radius_required_mm": 0.1,
        }
    )
    negative.append(_test("N14_SELF_INTERSECTION_FAILS", "NEGATIVE", self_intersection["status"] == "FAIL", self_intersection))

    travel_overrun = evaluate_curve(
        {
            "generator": "ANALYTIC_CIRCULAR_ARC",
            "continuity": "C2",
            "points_mm": arc_points,
            "carrier_travel_mm": 50.0,
            "carrier_travel_bounds_mm": [0.0, 40.0],
            "minimum_bend_radius_required_mm": 45.0,
        }
    )
    negative.append(_test("N15_CARRIER_TRAVEL_OVERRUN_FAILS", "NEGATIVE", travel_overrun["status"] == "FAIL", travel_overrun))

    continuity_fail = evaluate_curve(
        {
            "generator": "PIECEWISE_LINEAR",
            "continuity": "C0",
            "points_mm": [[0.0, 0.0, 0.0], [1.0, 1.0, 0.0], [2.0, 0.0, 0.0]],
            "carrier_travel_mm": 1.0,
            "carrier_travel_bounds_mm": [0.0, 2.0],
            "minimum_bend_radius_required_mm": 0.1,
        }
    )
    negative.append(_test("N16_NON_C2_CONTINUITY_FAILS", "NEGATIVE", continuity_fail["status"] == "FAIL", continuity_fail))

    malformed_failure = deepcopy(collision["failure"])
    malformed_failure.pop("object_pair")
    negative.append(_test("N17_MISSING_FAILURE_FIELD_REJECTED", "NEGATIVE", not failure_record_complete(malformed_failure), malformed_failure))

    obstacle_exemption = deepcopy(obstacle)
    obstacle_exemption["owner_segment"] = "SEG-FREE"
    obstacle_exemption_result = validate_finite_volume(obstacle_exemption)
    negative.append(_test("N18_OBSTACLE_CANNOT_GRANT_CONTACT", "NEGATIVE", obstacle_exemption_result["status"] == "FAIL", obstacle_exemption_result))

    crossing_3d = evaluate_curve(
        {
            "generator": "ANALYTIC_CIRCULAR_ARC",
            "continuity": "C2",
            "continuity_evidence": "ANALYTIC_CIRCLE_C_INFINITY_WITH_DISCRETE_GEOMETRY_CROSSCHECK",
            "analytic_radius_mm": 1.0,
            "points_mm": [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [1.0, 0.0, -1.0], [1.0, 0.0, 1.0], [2.0, 1.0, 1.0]],
            "carrier_travel_mm": 1.0,
            "carrier_travel_bounds_mm": [0.0, 2.0],
            "minimum_bend_radius_required_mm": 0.1,
        }
    )
    negative.append(_test("N19_TRUE_3D_NONADJACENT_INTERSECTION_FAILS", "NEGATIVE", crossing_3d["status"] == "FAIL" and crossing_3d["reason"] == "CURVE_SELF_INTERSECTION", crossing_3d))

    collinear_overlap = evaluate_curve(
        {
            "generator": "ANALYTIC_CIRCULAR_ARC",
            "continuity": "C2",
            "continuity_evidence": "ANALYTIC_CIRCLE_C_INFINITY_WITH_DISCRETE_GEOMETRY_CROSSCHECK",
            "analytic_radius_mm": 1.0,
            "points_mm": [[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [3.0, 1.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
            "carrier_travel_mm": 1.0,
            "carrier_travel_bounds_mm": [0.0, 2.0],
            "minimum_bend_radius_required_mm": 0.1,
        }
    )
    negative.append(_test("N20_COLLINEAR_NONADJACENT_OVERLAP_FAILS", "NEGATIVE", collinear_overlap["status"] == "FAIL" and collinear_overlap["reason"] == "CURVE_SELF_INTERSECTION", collinear_overlap))

    endpoint_touch = evaluate_curve(
        {
            "generator": "ANALYTIC_CIRCULAR_ARC",
            "continuity": "C2",
            "continuity_evidence": "ANALYTIC_CIRCLE_C_INFINITY_WITH_DISCRETE_GEOMETRY_CROSSCHECK",
            "analytic_radius_mm": 1.0,
            "points_mm": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            "carrier_travel_mm": 1.0,
            "carrier_travel_bounds_mm": [0.0, 2.0],
            "minimum_bend_radius_required_mm": 0.1,
        }
    )
    negative.append(_test("N21_NONADJACENT_ENDPOINT_TOUCH_FAILS", "NEGATIVE", endpoint_touch["status"] == "FAIL" and endpoint_touch["reason"] == "CURVE_SELF_INTERSECTION", endpoint_touch))

    fake_c2_polyline = evaluate_curve(
        {
            "generator": "PIECEWISE_LINEAR",
            "continuity": "C2",
            "continuity_evidence": "ANALYTIC_CIRCLE_C_INFINITY_WITH_DISCRETE_GEOMETRY_CROSSCHECK",
            "analytic_radius_mm": 1.0,
            "points_mm": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [1.0, 2.0, 0.0], [2.0, 2.0, 0.0]],
            "carrier_travel_mm": 1.0,
            "carrier_travel_bounds_mm": [0.0, 2.0],
            "minimum_bend_radius_required_mm": 0.1,
        }
    )
    negative.append(_test("N22_PIECEWISE_LINEAR_FALSE_C2_LABEL_FAILS", "NEGATIVE", fake_c2_polyline["status"] == "FAIL" and fake_c2_polyline["reason"] == "GENERATOR_NOT_GEOMETRICALLY_QUALIFIED_FOR_C2", fake_c2_polyline))

    duplicate_guide_second = deepcopy(guide)
    duplicate_guide_second["owner_segment"] = "SEG-J3"
    duplicate_scene = evaluate_scene(
        {
            "state": "SYNTH-DUP",
            "q": q0,
            "objects": [deepcopy(guide), duplicate_guide_second],
            "segments": [
                {"segment_id": "SEG-J2", "segment_class": "GUIDED_SPAN"},
                {"segment_id": "SEG-J3", "segment_class": "GUIDED_SPAN"},
            ],
            "samples": [
                {
                    "sample_id": "SMP-J2-01",
                    "segment_id": "SEG-J2",
                    "point_mm": [0.0, 0.0, 0.0],
                    "cable_radius_mm": 1.0,
                }
            ],
            "comparisons": [
                {"sample_id": "SMP-J2-01", "object_id": "GUIDE-J2-FINITE-01"}
            ],
        }
    )
    negative.append(_test("N23_DUPLICATE_OBJECT_ID_UNKNOWN", "NEGATIVE", duplicate_scene["status"] == "UNKNOWN" and duplicate_scene["reason"] == "DUPLICATE_OBJECT_ID_IN_SCENE_REGISTRY", duplicate_scene))

    class_mismatch = deepcopy(guided)
    class_mismatch["object"] = deepcopy(clamp)
    class_mismatch["object"]["owner_segment"] = "SEG-J2"
    class_mismatch_result = evaluate_contact(class_mismatch)
    negative.append(_test("N24_CONTACT_CLASS_MISMATCH_FAILS", "NEGATIVE", class_mismatch_result["status"] == "FAIL", class_mismatch_result))

    pinch_missing_segment = evaluate_pinch(
        state="SYNTH-PINCH", q=q0, segment="", point=[1.0, 2.0, 3.0], object_pair=["SEG-J5", "LINK5"], margin_mm=-0.5
    )
    negative.append(_test("N25_PINCH_MISSING_SEGMENT_UNKNOWN", "NEGATIVE", pinch_missing_segment["status"] == "UNKNOWN", pinch_missing_segment))

    pinch_missing_pair = evaluate_pinch(
        state="SYNTH-PINCH", q=q0, segment="SEG-J5", point=[1.0, 2.0, 3.0], object_pair=["LINK5"], margin_mm=-0.5
    )
    negative.append(_test("N26_PINCH_MISSING_OBJECT_PAIR_UNKNOWN", "NEGATIVE", pinch_missing_pair["status"] == "UNKNOWN", pinch_missing_pair))

    wildcard_owner = deepcopy(guide)
    wildcard_owner["owner_segment"] = "*"
    wildcard_owner_result = validate_finite_volume(wildcard_owner)
    negative.append(_test("N27_WILDCARD_OWNER_FAILS_CLOSED", "NEGATIVE", wildcard_owner_result["status"] in {"FAIL", "UNKNOWN"}, wildcard_owner_result))

    multi_owner = deepcopy(guide)
    multi_owner["owner_segment"] = "SEG-J2|SEG-J3"
    multi_owner_result = validate_finite_volume(multi_owner)
    negative.append(_test("N28_MULTI_OWNER_STRING_FAILS_CLOSED", "NEGATIVE", multi_owner_result["status"] in {"FAIL", "UNKNOWN"}, multi_owner_result))

    disguised_scope = deepcopy(guide)
    disguised_scope["object_id"] = "GUIDE-WHOLE_LINK-link3"
    disguised_scope_result = validate_finite_volume(disguised_scope)
    negative.append(_test("N29_DISGUISED_WHOLE_LINK_ID_FAILS_CLOSED", "NEGATIVE", disguised_scope_result["status"] in {"FAIL", "UNKNOWN"}, disguised_scope_result))

    helix_angles = [math.radians(value) for value in range(0, 91, 15)]
    helix_points = [[50.0 * math.cos(theta), 50.0 * math.sin(theta), 25.0 * theta] for theta in helix_angles]
    helix_discrete_radius = circumradius_mm(helix_points[0], helix_points[1], helix_points[2])
    helix_false_arc = evaluate_curve(
        {
            "generator": "ANALYTIC_CIRCULAR_ARC",
            "continuity": "C2",
            "continuity_evidence": "ANALYTIC_CIRCLE_C_INFINITY_WITH_DISCRETE_GEOMETRY_CROSSCHECK",
            "analytic_radius_mm": helix_discrete_radius,
            "points_mm": helix_points,
            "carrier_travel_mm": 1.0,
            "carrier_travel_bounds_mm": [0.0, 2.0],
            "minimum_bend_radius_required_mm": 1.0,
        }
    )
    negative.append(_test("N30_EQUAL_STEP_HELIX_CANNOT_MASQUERADE_AS_CIRCULAR_ARC", "NEGATIVE", helix_false_arc["status"] == "FAIL" and helix_false_arc["reason"] in {"DECLARED_CIRCULAR_ARC_NOT_COPLANAR", "DECLARED_CIRCULAR_ARC_HAS_NO_COMMON_CENTER_AND_RADIUS"}, helix_false_arc))

    inline_state_scene = evaluate_scene(
        {
            "state": "SCENE-POSE",
            "q": q0,
            "objects": [deepcopy(guide)],
            "segments": [{"segment_id": "SEG-J2", "segment_class": "GUIDED_SPAN"}],
            "samples": [
                {
                    "sample_id": "SMP-J2-01",
                    "segment_id": "SEG-J2",
                    "point_mm": [0.0, 0.0, 0.0],
                    "cable_radius_mm": 1.0,
                }
            ],
            "comparisons": [
                {
                    "state": "OVERRIDE-POSE",
                    "sample_id": "SMP-J2-01",
                    "object_id": "GUIDE-J2-FINITE-01",
                }
            ],
        }
    )
    negative.append(_test("N31_COMPARISON_STATE_OVERRIDE_UNKNOWN", "NEGATIVE", inline_state_scene["status"] == "UNKNOWN" and inline_state_scene["reason"] == "INLINE_OR_EXTRA_COMPARISON_FIELDS_FORBIDDEN", inline_state_scene))

    inline_q_scene = evaluate_scene(
        {
            "state": "SCENE-POSE",
            "q": q0,
            "objects": [deepcopy(guide)],
            "segments": [{"segment_id": "SEG-J2", "segment_class": "GUIDED_SPAN"}],
            "samples": [
                {
                    "sample_id": "SMP-J2-01",
                    "segment_id": "SEG-J2",
                    "point_mm": [0.0, 0.0, 0.0],
                    "cable_radius_mm": 1.0,
                }
            ],
            "comparisons": [
                {
                    "q": [1.0] * 6,
                    "sample_id": "SMP-J2-01",
                    "object_id": "GUIDE-J2-FINITE-01",
                }
            ],
        }
    )
    negative.append(_test("N32_COMPARISON_Q_OVERRIDE_UNKNOWN", "NEGATIVE", inline_q_scene["status"] == "UNKNOWN" and inline_q_scene["reason"] == "INLINE_OR_EXTRA_COMPARISON_FIELDS_FORBIDDEN", inline_q_scene))

    reversal_points = [
        [radius * math.cos(math.radians(angle)), radius * math.sin(math.radians(angle)), 0.0]
        for angle in [0.0, 60.0, 40.0, 20.0, 10.0]
    ]
    reversal_curve = evaluate_curve(
        {
            "generator": "ANALYTIC_CIRCULAR_ARC",
            "continuity": "C2",
            "continuity_evidence": "ANALYTIC_CIRCLE_C_INFINITY_WITH_DISCRETE_GEOMETRY_CROSSCHECK",
            "analytic_radius_mm": radius,
            "points_mm": reversal_points,
            "carrier_travel_mm": 1.0,
            "carrier_travel_bounds_mm": [0.0, 2.0],
            "minimum_bend_radius_required_mm": 1.0,
        }
    )
    negative.append(
        _test(
            "N33_ARC_PARAMETER_DIRECTION_REVERSAL_FAILS",
            "NEGATIVE",
            reversal_curve["status"] == "FAIL" and reversal_curve["reason"] == "ARC_PARAMETER_DIRECTION_REVERSAL",
            reversal_curve,
        )
    )

    colocated_obstacle = deepcopy(obstacle)
    colocated_obstacle.update(
        {
            "object_id": "OBS-COLOCATED-01",
            "bounds_min_mm": [-2.0, -2.0, -2.0],
            "bounds_max_mm": [2.0, 2.0, 2.0],
        }
    )
    coverage_scene_base = {
        "state": "SYNTH-COVERAGE",
        "q": q0,
        "objects": [deepcopy(guide), colocated_obstacle],
        "segments": [{"segment_id": "SEG-J2", "segment_class": "GUIDED_SPAN"}],
        "samples": [
            {
                "sample_id": "SMP-J2-01",
                "segment_id": "SEG-J2",
                "point_mm": [0.0, 0.0, 0.0],
                "cable_radius_mm": 1.0,
            }
        ],
    }
    omitted_obstacle_scene = deepcopy(coverage_scene_base)
    omitted_obstacle_scene["comparisons"] = [
        {"sample_id": "SMP-J2-01", "object_id": "GUIDE-J2-FINITE-01"}
    ]
    omitted_obstacle = evaluate_scene(omitted_obstacle_scene)
    negative.append(
        _test(
            "N34_OMITTED_COLOCATED_OBSTACLE_COMPARISON_UNKNOWN",
            "NEGATIVE",
            omitted_obstacle["status"] == "UNKNOWN"
            and omitted_obstacle["reason"] == "INCOMPLETE_SAMPLE_OBJECT_COMPARISON_COVERAGE",
            omitted_obstacle,
        )
    )

    duplicate_pair_scene = {
        "state": "SYNTH-DUP-PAIR",
        "q": q0,
        "objects": [deepcopy(guide)],
        "segments": [{"segment_id": "SEG-J2", "segment_class": "GUIDED_SPAN"}],
        "samples": deepcopy(coverage_scene_base["samples"]),
        "comparisons": [
            {"sample_id": "SMP-J2-01", "object_id": "GUIDE-J2-FINITE-01"},
            {"sample_id": "SMP-J2-01", "object_id": "GUIDE-J2-FINITE-01"},
        ],
    }
    duplicate_pair = evaluate_scene(duplicate_pair_scene)
    negative.append(
        _test(
            "N35_DUPLICATE_SAMPLE_OBJECT_PAIR_UNKNOWN",
            "NEGATIVE",
            duplicate_pair["status"] == "UNKNOWN"
            and duplicate_pair["reason"] == "DUPLICATE_SAMPLE_OBJECT_COMPARISON_PAIR",
            duplicate_pair,
        )
    )

    complete_obstacle_scene = deepcopy(coverage_scene_base)
    complete_obstacle_scene["comparisons"] = [
        {"sample_id": "SMP-J2-01", "object_id": "GUIDE-J2-FINITE-01"},
        {"sample_id": "SMP-J2-01", "object_id": "OBS-COLOCATED-01"},
    ]
    complete_obstacle = evaluate_scene(complete_obstacle_scene)
    negative.append(
        _test(
            "N36_COMPLETE_COVERAGE_DETECTS_COLOCATED_OBSTACLE",
            "NEGATIVE",
            complete_obstacle["status"] == "FAIL" and complete_obstacle["reason"] == "COLLISION",
            complete_obstacle,
        )
    )

    all_tests = positive + negative
    return {
        "schema": "ROUTE_C_PREDICATE_QUALIFICATION_V1",
        "authority_class": "SYNTHETIC_PREDICATE_QUALIFICATION_ONLY",
        "kernel": "PURE_PYTHON_STANDARD_LIBRARY_ANALYTIC_GEOMETRY",
        "physical_route_c_candidate_evaluated": False,
        "physical_guide_volumes_evaluated": False,
        "summary": {
            "positive_controls_total": len(positive),
            "positive_controls_passed": sum(item["passed"] for item in positive),
            "negative_controls_total": len(negative),
            "negative_controls_passed": sum(item["passed"] for item in negative),
            "tests_total": len(all_tests),
            "tests_passed": sum(item["passed"] for item in all_tests),
            "qualification": "PASS_SYNTHETIC_SEMANTICS_ONLY" if all(item["passed"] for item in all_tests) else "FAIL",
        },
        "positive_controls": positive,
        "negative_controls": negative,
        "authority_effect": "NONE__TEST_PASS_DOES_NOT_AUTHORIZE_CAD_OR_ESTABLISH_GEOMETRIC_FEASIBILITY",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="run the preregistered synthetic qualification suite")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    args = parser.parse_args(argv)
    if not args.self_test:
        parser.error("this non-mutating kernel currently supports --self-test only")
    report = run_qualification()
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=None if args.compact else 2))
    return 0 if report["summary"]["qualification"] == "PASS_SYNTHETIC_SEMANTICS_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
