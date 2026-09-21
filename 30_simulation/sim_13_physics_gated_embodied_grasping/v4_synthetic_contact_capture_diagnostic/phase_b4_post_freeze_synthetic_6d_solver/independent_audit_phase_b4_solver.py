"""Independent, read-only-math audit and final signer for B4E.

This module intentionally does not import the solver, validator, tests, or a
shared evidence helper.  It reconstructs the primary event mathematics from
hash-bound raw evidence and upstream B3 primitives.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Sequence

import numpy as np


PHASE_ROOT = Path(__file__).resolve().parent
DIAGNOSTIC_ROOT = PHASE_ROOT.parent
B3_ROOT = DIAGNOSTIC_ROOT / "phase_b3_branched_dual_contact_soft_capture"
for candidate in (DIAGNOSTIC_ROOT, B3_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from b3_contact.branched_model import BranchedGripperServiceModel  # noqa: E402
from b3_contact.dual_contact_kernel import DualContactConfig, evaluate_dual_contact  # noqa: E402
from sim13_v4a.full_floating import (  # noqa: E402
    ServiceState, TargetState, TARGET_INERTIA_BODY_KG_M2, TARGET_MASS_KG,
    normalize_quaternion, quat_product, quat_to_rotation, quaternion_geodesic,
    target_momentum_energy,
)


EVIDENCE = PHASE_ROOT / "evidence"
RESULTS = PHASE_ROOT / "results"
RECEIPT = EVIDENCE / "SIM13_V4B4E_INDEPENDENT_AUDIT_RECEIPT_V1.json"
FINAL_GATE = RESULTS / "SIM13_V4B4E_AUDITED_GATE_V1.json"
TERMINAL = RESULTS / "SIM13_V4B4E_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"
PRE_AUDIT = RESULTS / "SIM13_V4B4E_PRE_AUDIT_GATE_V1.json"
EVIDENCE_MANIFEST = EVIDENCE / "SIM13_V4B4E_EVIDENCE_MANIFEST_V1.json"


def project_root() -> Path:
    for parent in PHASE_ROOT.parents:
        if (parent / "PROJECT_MAP.md").is_file():
            return parent
    raise RuntimeError("PROJECT_ROOT_NOT_FOUND")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON_ROOT_NOT_OBJECT:{path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def record(path: Path, role: str) -> dict[str, Any]:
    return {"path": path.relative_to(PHASE_ROOT).as_posix(), "role": role, "bytes": path.stat().st_size, "sha256": sha256(path)}


def rank_relative(matrix: np.ndarray, tolerance: float = 1.0e-10) -> int:
    singular = np.linalg.svd(matrix, compute_uv=False)
    return int(np.count_nonzero(singular > tolerance * singular[0]))


def skew(value: Sequence[float]) -> np.ndarray:
    x, y, z = np.asarray(value, dtype=float)
    return np.array(((0.0, -z, y), (z, 0.0, -x), (-y, x, 0.0)))


def block_diagonal(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    result = np.zeros((left.shape[0] + right.shape[0], left.shape[1] + right.shape[1]))
    result[: left.shape[0], : left.shape[1]] = left
    result[left.shape[0] :, left.shape[1] :] = right
    return result


def clean_final() -> None:
    for path in (RECEIPT, FINAL_GATE, TERMINAL):
        if path.is_file():
            path.unlink()


def verify_manifest_entries(manifest: dict[str, Any], *, root: Path, key: str) -> bool:
    for item in manifest[key]:
        path = root / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
            return False
    return True


def hermite_minimum(g0: float, g1: float, v0: float, v1: float, h: float) -> float:
    coefficients = np.array((2 * g0 - 2 * g1 + h * (v0 + v1), -3 * g0 + 3 * g1 - h * (2 * v0 + v1), h * v0, g0))
    candidates = [0.0, 1.0]
    for root in np.roots(np.polyder(coefficients)):
        if abs(root.imag) <= 1.0e-12 and 0.0 <= root.real <= 1.0:
            candidates.append(float(root.real))
    return min(float(np.polyval(coefficients, value)) for value in candidates)


def _canonical_quaternion_independent(quaternion: Sequence[float], tolerance: float = 1.0e-15) -> np.ndarray:
    value = normalize_quaternion(quaternion)
    if value[0] < -tolerance:
        return -value
    if abs(value[0]) <= tolerance:
        for component in value[1:]:
            if abs(component) > tolerance:
                return -value if component < 0.0 else value
    return value


def _service_from_29(vector: Sequence[float]) -> ServiceState:
    value = np.asarray(vector, dtype=float)
    if value.shape != (29,) or not np.all(np.isfinite(value)):
        raise ValueError("INDEPENDENT_SERVICE_29_INVALID")
    return ServiceState(
        value[:3].copy(), normalize_quaternion(value[3:7], strict_unit=True),
        value[7:15].copy(), value[15:29].copy(),
    )


def _target_from_13(vector: Sequence[float]) -> TargetState:
    value = np.asarray(vector, dtype=float)
    if value.shape != (13,) or not np.all(np.isfinite(value)):
        raise ValueError("INDEPENDENT_TARGET_13_INVALID")
    return TargetState(
        value[:3].copy(), normalize_quaternion(value[3:7], strict_unit=True),
        value[7:13].copy(),
    )


def _service_to_29(service: ServiceState) -> np.ndarray:
    return np.concatenate((
        service.base_position_inertial_m,
        service.base_quaternion_body_to_inertial_wxyz,
        service.joint_coordinates_mixed,
        service.nu_s_mixed,
    ))


def _snapshot_target_independent(
    model: BranchedGripperServiceModel,
    service: ServiceState,
    translation_palm_to_target_m: np.ndarray,
    rotation_palm_to_target: np.ndarray,
    velocity: np.ndarray | None = None,
) -> tuple[TargetState, np.ndarray]:
    eta = service.nu_s_mixed if velocity is None else np.asarray(velocity, dtype=float)
    if eta.shape != (14,):
        raise ValueError("INDEPENDENT_SNAPSHOT_VELOCITY_INVALID")
    palm, palm_rotation, palm_jv, palm_jw = model.palm_frame_and_jacobians(service)
    offset = palm_rotation @ translation_palm_to_target_m
    target_rotation = palm_rotation @ rotation_palm_to_target
    embedding = np.vstack((palm_jv - skew(offset) @ palm_jw, palm_jw))
    target = TargetState(
        palm + offset,
        _rotation_to_quaternion_independent(target_rotation),
        embedding @ eta,
    )
    return target, embedding


def _target_spatial_mass_independent(target: TargetState) -> np.ndarray:
    rotation = quat_to_rotation(target.quaternion_body_to_inertial_wxyz)
    result = np.zeros((6, 6))
    result[:3, :3] = TARGET_MASS_KG * np.eye(3)
    result[3:, 3:] = rotation @ TARGET_INERTIA_BODY_KG_M2 @ rotation.T
    return result


def _active_rhs_independent(
    model: BranchedGripperServiceModel,
    translation_palm_to_target_m: np.ndarray,
    rotation_palm_to_target: np.ndarray,
    vector: np.ndarray,
    *,
    difference_step_s: float = 2.0e-6,
) -> np.ndarray:
    service = _service_from_29(vector)
    target, embedding = _snapshot_target_independent(
        model, service, translation_palm_to_target_m, rotation_palm_to_target,
    )
    plus = model._shift_state_along_velocity(service, service.nu_s_mixed, difference_step_s)
    minus = model._shift_state_along_velocity(service, service.nu_s_mixed, -difference_step_s)
    _, embedding_plus = _snapshot_target_independent(
        model, plus, translation_palm_to_target_m, rotation_palm_to_target,
    )
    _, embedding_minus = _snapshot_target_independent(
        model, minus, translation_palm_to_target_m, rotation_palm_to_target,
    )
    embedding_rate_eta = (
        (embedding_plus - embedding_minus) / (2.0 * difference_step_s)
    ) @ service.nu_s_mixed
    target_mass = _target_spatial_mass_independent(target)
    target_omega = target.twist_inertial_mixed[3:]
    target_bias = np.concatenate((
        np.zeros(3),
        np.cross(target_omega, target_mass[3:, 3:] @ target_omega),
    ))
    mass = model.mass_matrix(service) + embedding.T @ target_mass @ embedding
    bias = model.bias_effort(service, difference_step_s=difference_step_s) + embedding.T @ (
        target_bias + target_mass @ embedding_rate_eta
    )
    acceleration = np.linalg.solve(0.5 * (mass + mass.T), -bias)
    quaternion_rate = 0.5 * quat_product(
        np.array((0.0, *service.nu_s_mixed[3:6])),
        service.base_quaternion_body_to_inertial_wxyz,
    )
    return np.concatenate((
        service.nu_s_mixed[:3], quaternion_rate,
        service.nu_s_mixed[6:], acceleration,
    ))


def _partial_active_step_independent(
    model: BranchedGripperServiceModel,
    translation_palm_to_target_m: np.ndarray,
    rotation_palm_to_target: np.ndarray,
    state: np.ndarray,
    step_s: float,
    method: str,
) -> np.ndarray:
    rhs = lambda value: _active_rhs_independent(
        model, translation_palm_to_target_m, rotation_palm_to_target, value,
    )
    if method == "rk4":
        k1 = rhs(state)
        k2 = rhs(state + 0.5 * step_s * k1)
        k3 = rhs(state + 0.5 * step_s * k2)
        k4 = rhs(state + step_s * k3)
        result = state + step_s * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0
    elif method == "midpoint":
        k1 = rhs(state)
        result = state + step_s * rhs(state + 0.5 * step_s * k1)
    else:
        raise ValueError(f"INDEPENDENT_ACTIVE_METHOD_INVALID:{method}")
    result[3:7] = _canonical_quaternion_independent(result[3:7])
    return result


def _hermite_coefficients_independent(
    gap0: float, gap1: float, rate0: float, rate1: float, step_s: float,
) -> np.ndarray:
    return np.array((
        2.0 * gap0 - 2.0 * gap1 + step_s * (rate0 + rate1),
        -3.0 * gap0 + 3.0 * gap1 - step_s * (2.0 * rate0 + rate1),
        step_s * rate0,
        gap0,
    ))


def _real_unit_roots_independent(coefficients: Sequence[float]) -> list[float]:
    value = np.asarray(coefficients, dtype=float)
    scale = float(np.max(np.abs(value)))
    if scale == 0.0:
        return []
    value = value / scale
    first = 0
    while first < len(value) - 1 and abs(value[first]) <= 1.0e-14:
        first += 1
    value = value[first:]
    if len(value) <= 1:
        return []
    result: list[float] = []
    for root in np.roots(value):
        if abs(float(np.imag(root))) <= 1.0e-10:
            real = float(np.real(root))
            if -1.0e-12 <= real <= 1.0 + 1.0e-12:
                result.append(min(1.0, max(0.0, real)))
    return sorted(set(round(item, 14) for item in result))


def _polynomial_minimum_independent(
    coefficients: Sequence[float], lower: float = 0.0, upper: float = 1.0,
) -> float:
    value = np.asarray(coefficients, dtype=float)
    candidates = [float(lower), float(upper)]
    for root in _real_unit_roots_independent(np.polyder(value)):
        if lower <= root <= upper:
            candidates.append(root)
    return min(float(np.polyval(value, item)) for item in candidates)


def _continuous_native_minima_independent(
    time_s: np.ndarray,
    left_gap_m: np.ndarray,
    right_gap_m: np.ndarray,
    left_gap_rate_m_s: np.ndarray,
    right_gap_rate_m_s: np.ndarray,
    *,
    start_s: float | None = None,
    end_s: float | None = None,
) -> dict[str, float]:
    start = float(time_s[0]) if start_s is None else float(start_s)
    end = float(time_s[-1]) if end_s is None else float(end_s)
    if start < float(time_s[0]) - 1.0e-12 or end > float(time_s[-1]) + 1.0e-12 or end < start:
        raise ValueError("INDEPENDENT_CLEARANCE_WINDOW_INVALID")
    minima = {
        "left_gap_m": math.inf,
        "right_gap_m": math.inf,
        "left_gap_rate_m_s": math.inf,
        "right_gap_rate_m_s": math.inf,
    }
    covered = 0.0
    for index in range(len(time_s) - 1):
        segment_start = max(start, float(time_s[index]))
        segment_end = min(end, float(time_s[index + 1]))
        if segment_end < segment_start - 1.0e-15:
            continue
        h = float(time_s[index + 1] - time_s[index])
        lower = max(0.0, min(1.0, (segment_start - float(time_s[index])) / h))
        upper = max(0.0, min(1.0, (segment_end - float(time_s[index])) / h))
        left = _hermite_coefficients_independent(
            left_gap_m[index], left_gap_m[index + 1],
            left_gap_rate_m_s[index], left_gap_rate_m_s[index + 1], h,
        )
        right = _hermite_coefficients_independent(
            right_gap_m[index], right_gap_m[index + 1],
            right_gap_rate_m_s[index], right_gap_rate_m_s[index + 1], h,
        )
        minima["left_gap_m"] = min(
            minima["left_gap_m"], _polynomial_minimum_independent(left, lower, upper),
        )
        minima["right_gap_m"] = min(
            minima["right_gap_m"], _polynomial_minimum_independent(right, lower, upper),
        )
        minima["left_gap_rate_m_s"] = min(
            minima["left_gap_rate_m_s"],
            _polynomial_minimum_independent(np.polyder(left) / h, lower, upper),
        )
        minima["right_gap_rate_m_s"] = min(
            minima["right_gap_rate_m_s"],
            _polynomial_minimum_independent(np.polyder(right) / h, lower, upper),
        )
        covered += max(0.0, segment_end - segment_start)
    if covered < end - start - 1.0e-12 or any(not np.isfinite(item) for item in minima.values()):
        raise ValueError("INDEPENDENT_CLEARANCE_WINDOW_NOT_COVERED")
    return minima


def _continuous_good_intervals_independent(
    time_s: np.ndarray,
    left_gap_m: np.ndarray,
    right_gap_m: np.ndarray,
    left_gap_rate_m_s: np.ndarray,
    right_gap_rate_m_s: np.ndarray,
    ledger_interval_closed: np.ndarray,
    *,
    gap_threshold_m: float,
    rate_threshold_m_s: float,
) -> list[list[float]]:
    intervals: list[tuple[float, float]] = []
    for index in range(len(time_s) - 1):
        if not bool(ledger_interval_closed[index]):
            continue
        h = float(time_s[index + 1] - time_s[index])
        left = _hermite_coefficients_independent(
            left_gap_m[index], left_gap_m[index + 1],
            left_gap_rate_m_s[index], left_gap_rate_m_s[index + 1], h,
        )
        right = _hermite_coefficients_independent(
            right_gap_m[index], right_gap_m[index + 1],
            right_gap_rate_m_s[index], right_gap_rate_m_s[index + 1], h,
        )
        polynomials = [left.copy(), right.copy(), np.polyder(left) / h, np.polyder(right) / h]
        polynomials[0][-1] -= gap_threshold_m
        polynomials[1][-1] -= gap_threshold_m
        polynomials[2][-1] -= rate_threshold_m_s
        polynomials[3][-1] -= rate_threshold_m_s
        boundaries = [0.0, 1.0]
        for polynomial in polynomials:
            boundaries.extend(_real_unit_roots_independent(polynomial))
        boundaries = sorted(set(boundaries))
        for lower, upper in zip(boundaries[:-1], boundaries[1:]):
            if upper - lower <= 1.0e-14:
                continue
            midpoint = 0.5 * (lower + upper)
            if all(float(np.polyval(polynomial, midpoint)) >= 0.0 for polynomial in polynomials):
                intervals.append((
                    float(time_s[index] + h * lower),
                    float(time_s[index] + h * upper),
                ))
    merged: list[list[float]] = []
    for lower, upper in sorted(intervals):
        if not merged or lower - merged[-1][1] > 1.0e-12:
            merged.append([lower, upper])
        else:
            merged[-1][1] = max(merged[-1][1], upper)
    return merged


def main() -> int:
    clean_final()
    checks: list[dict[str, Any]] = []

    def add(identifier: str, passed: bool, detail: Any) -> None:
        checks.append({"id": identifier, "passed": bool(passed), "detail": detail})

    try:
        root = project_root()
        source_manifest = read_json(EVIDENCE / "SIM13_V4B4E_SOURCE_MANIFEST_V1.json")
        evidence_manifest = read_json(EVIDENCE_MANIFEST)
        source_snapshot = [(item["path"], item["bytes"], item["sha256"]) for item in source_manifest["sources"]]
        evidence_snapshot = [(item["path"], item["bytes"], item["sha256"]) for item in evidence_manifest["files"]]
        add("B4EA01_SOURCE_MANIFEST_SELF_EXCLUDED", source_manifest["self_excluded"] is True, source_manifest["source_count"])
        add("B4EA02_SOURCE_BYTES_SHA", verify_manifest_entries(source_manifest, root=root, key="sources"), source_manifest["source_count"])
        add("B4EA03_EVIDENCE_MANIFEST_SELF_EXCLUDED", evidence_manifest["self_excluded"] is True, evidence_manifest["file_count"])
        add("B4EA04_EVIDENCE_BYTES_SHA", verify_manifest_entries(evidence_manifest, root=PHASE_ROOT, key="files"), evidence_manifest["file_count"])

        validation = read_json(EVIDENCE / "SIM13_V4B4E_VALIDATION_V1.json")
        add("B4EA05_VALIDATION_48_OF_48", validation["status"] == "PASS" and validation["observed_checks"] == validation["passed_checks"] == 48, {"observed": validation["observed_checks"], "passed": validation["passed_checks"]})
        test_inventory = read_json(PHASE_ROOT / "contracts" / "PHASE_B4E_TEST_INVENTORY_V1.json")["pytest"]
        expected_pytest = int(test_inventory["expected_collected"])
        add("B4EA06_PYTEST_INVENTORY_CLEAN", validation["pytest"]["collected"] == validation["pytest"]["passed"] == expected_pytest and all(validation["pytest"][key] == 0 for key in ("failed", "errors", "skipped")), validation["pytest"])
        pre = read_json(PRE_AUDIT)
        add("B4EA07_PRE_AUDIT_NOT_FINAL", pre["final"] is False and pre["status"].startswith("PASS_PHASE_B4E_SOLVER_VALIDATION_PRE_AUDIT"), pre["status"])
        add("B4EA08_PRE_AUDIT_HASH_BINDINGS", pre["validation"]["sha256"] == sha256(EVIDENCE / "SIM13_V4B4E_VALIDATION_V1.json") and pre["evidence_manifest"]["sha256"] == sha256(EVIDENCE_MANIFEST), {"validation": pre["validation"]["sha256"], "manifest": pre["evidence_manifest"]["sha256"]})

        events = read_json(EVIDENCE / "SIM13_V4B4E_EVENT_INPUTS_V1.json")["runs"]
        primary_event = next(item for item in events if item["run_id"] == "rk4_reference")
        trace_binding = next(item for item in source_manifest["sources"] if item["id"] == "b3_reference_trace")
        upstream_trace = read_json(root / trace_binding["path"])
        first_index = None
        for index, item in enumerate(upstream_trace["reference_records"]):
            criteria = item["soft_capture_criteria"]
            if criteria["soft_capture_transient_qualifies"] and criteria["all_ledgers_closed"]:
                first_index = index; break
        add("B4EA09_TRIGGER_REBUILT_FIRST", first_index == primary_event["index"] == 205, first_index)
        add("B4EA10_TRIGGER_TIME_AND_LABEL", primary_event["time_s"] == 0.051250000000000004 and primary_event["state_label"] == "SOFT_CAPTURE_TRANSIENT_CANDIDATE", {"time": primary_event["time_s"], "label": primary_event["state_label"]})

        model = BranchedGripperServiceModel()
        service_data = primary_event["service"]; target_data = primary_event["target"]
        service = ServiceState(np.array(service_data["base_position_inertial_m"]), normalize_quaternion(service_data["base_quaternion_body_to_inertial_wxyz"], strict_unit=True), np.array(service_data["joint_coordinates_mixed"]), np.array(service_data["nu_s_mixed"]))
        target = TargetState(np.array(target_data["position_inertial_m"]), normalize_quaternion(target_data["quaternion_body_to_inertial_wxyz"], strict_unit=True), np.array(target_data["twist_inertial_mixed"]))
        palm, palm_rotation, jv, jw = model.palm_frame_and_jacobians(service)
        d_star = palm_rotation.T @ (target.position_inertial_m - palm)
        r_star = palm_rotation.T @ quat_to_rotation(target.quaternion_body_to_inertial_wxyz)
        acquisitions = read_json(EVIDENCE / "SIM13_V4B4E_ACQUISITION_LEDGER_V1.json")["runs"]
        primary = acquisitions["rk4_reference"]
        add("B4EA11_SNAPSHOT_TRANSLATION_REBUILT", np.linalg.norm(d_star - np.array(primary["snapshot"]["translation_palm_to_target_m"])) <= 1.0e-12, d_star.tolist())
        add("B4EA12_SNAPSHOT_ROTATION_REBUILT", np.linalg.norm(r_star - np.array(primary["snapshot"]["rotation_palm_to_target"]), ord=np.inf) <= 1.0e-12 and np.linalg.det(r_star) > 0.0, float(np.linalg.det(r_star)))

        offset = target.position_inertial_m - palm
        a = np.vstack((jv - skew(offset) @ jw, jw))
        embedding = np.vstack((np.eye(14), a))
        jc = np.hstack((-a, np.eye(6)))
        lref = 0.5 * np.linalg.norm(np.array(primary_event["right_common_contact_point_m"]) - np.array(primary_event["left_common_contact_point_m"]))
        d = np.diag(np.concatenate((np.ones(3), lref * np.ones(3))))
        s_eta = np.diag(np.concatenate((np.ones(3), lref * np.ones(3), lref * np.ones(6), np.ones(2))))
        s_z = block_diagonal(s_eta, np.diag(np.concatenate((np.ones(3), lref * np.ones(3)))))
        lhat = s_z @ embedding @ np.linalg.solve(s_eta, np.eye(14))
        jhat = d @ jc @ np.linalg.solve(s_z, np.eye(20))
        add("B4EA13_A_L_J_REBUILT", np.linalg.norm(a - np.array(primary["matrices"]["A"]), ord=np.inf) <= 1.0e-12 and np.linalg.norm(embedding - np.array(primary["matrices"]["L"]), ord=np.inf) <= 1.0e-12 and np.linalg.norm(jc - np.array(primary["matrices"]["J_c"]), ord=np.inf) <= 1.0e-12, float(np.linalg.norm(jc @ embedding, ord=np.inf)))
        add("B4EA14_SCALED_RANKS_REBUILT", (rank_relative(lhat), rank_relative(jhat)) == (14, 6), {"Lhat": rank_relative(lhat), "Jhat": rank_relative(jhat)})

        target_rotation = quat_to_rotation(target.quaternion_body_to_inertial_wxyz)
        mt = np.zeros((6, 6)); mt[:3, :3] = TARGET_MASS_KG * np.eye(3); mt[3:, 3:] = target_rotation @ TARGET_INERTIA_BODY_KG_M2 @ target_rotation.T
        mminus = block_diagonal(model.mass_matrix(service), mt)
        zminus = np.concatenate((service.nu_s_mixed, target.twist_inertial_mixed))
        mr = embedding.T @ mminus @ embedding
        eta = np.linalg.solve(mr, embedding.T @ mminus @ zminus)
        zreduced = embedding @ eta
        jbar = d @ jc
        kkt = np.block([[mminus, -jbar.T], [-jbar, np.zeros((6, 6))]])
        solution = np.linalg.solve(kkt, np.concatenate((mminus @ zminus, np.zeros(6))))
        zkkt = solution[:20]; lambda_bar = solution[20:]
        add("B4EA15_REDUCED_REBUILT", np.max(np.abs(zreduced - np.array(primary["z_plus_reduced"]))) <= 1.0e-12, float(np.max(np.abs(zreduced - np.array(primary["z_plus_reduced"])))))
        add("B4EA16_KKT_REBUILT_INDEPENDENT", np.max(np.abs(zkkt - np.array(primary["z_plus_kkt"]))) <= 1.0e-12 and np.max(np.abs(lambda_bar - np.array(primary["lambda_bar"]))) <= 1.0e-12, float(np.max(np.abs(zkkt - np.array(primary["z_plus_kkt"])))))
        add("B4EA17_POST_CONSTRAINT_REBUILT", np.max(np.abs(jc @ zkkt)) <= 1.0e-10, float(np.max(np.abs(jc @ zkkt))))

        wbar = jbar @ np.linalg.solve(mminus, jbar.T)
        eigenvalues = np.linalg.eigvalsh(0.5 * (wbar + wbar.T))
        add("B4EA18_WBAR_SPD_CONDITION", eigenvalues[0] > 0.0 and eigenvalues[-1] / eigenvalues[0] <= 1.0e10, {"min": float(eigenvalues[0]), "condition": float(eigenvalues[-1] / eigenvalues[0])})
        physical_lambda = d.T @ lambda_bar; impulse = physical_lambda[:3]; angular_impulse = physical_lambda[3:]
        add("B4EA19_PHYSICAL_IMPULSE_REBUILT", np.max(np.abs(impulse - np.array(primary["linear_impulse_N_s"]))) <= 1.0e-12 and np.max(np.abs(angular_impulse - np.array(primary["angular_impulse_N_m_s"]))) <= 1.0e-12, {"p": impulse.tolist(), "ell": angular_impulse.tolist()})

        pre_service = model.momentum_energy(service); pre_target = target_momentum_energy(target)
        post_service = ServiceState(service.base_position_inertial_m, service.base_quaternion_body_to_inertial_wxyz, service.joint_coordinates_mixed, zkkt[:14])
        post_target = TargetState(target.position_inertial_m, target.quaternion_body_to_inertial_wxyz, zkkt[14:])
        post_service_ledger = model.momentum_energy(post_service); post_target_ledger = target_momentum_energy(post_target)
        dp = (post_service_ledger.linear_momentum_n_s + post_target_ledger.linear_momentum_n_s) - (pre_service.linear_momentum_n_s + pre_target.linear_momentum_n_s)
        dh = (post_service_ledger.angular_momentum_about_inertial_origin_n_m_s + post_target_ledger.angular_momentum_about_inertial_origin_n_m_s) - (pre_service.angular_momentum_about_inertial_origin_n_m_s + pre_target.angular_momentum_about_inertial_origin_n_m_s)
        add("B4EA20_MOMENTUM_JUMPS_REBUILT", np.linalg.norm(dp) <= 1.0e-9 and np.linalg.norm(dh) <= 1.0e-9, {"linear": float(np.linalg.norm(dp)), "angular": float(np.linalg.norm(dh))})
        tminus = pre_service.kinetic_energy_j + pre_target.kinetic_energy_j; tplus = post_service_ledger.kinetic_energy_j + post_target_ledger.kinetic_energy_j
        dprojection = tminus - tplus
        add("B4EA21_ENERGY_PROJECTION_REBUILT", abs(dprojection - primary["energy_audit"]["D_projection_J"]) <= 1.0e-12 and dprojection >= -1.0e-12, dprojection)
        utotal = primary_event["left_contact_potential_J"] + primary_event["right_contact_potential_J"]
        add("B4EA22_SWITCH_ENERGY_ONCE", abs(primary["energy_audit"]["D_switch_J"] - dprojection - utotal) <= 1.0e-12, {"U": utotal, "Dswitch": primary["energy_audit"]["D_switch_J"]})
        chord = np.array(primary_event["right_common_contact_point_m"]) - np.array(primary_event["left_common_contact_point_m"]); chord /= np.linalg.norm(chord)
        rleft = np.array(primary_event["left_common_contact_point_m"]) - target.position_inertial_m
        chi = float(chord @ (angular_impulse - np.cross(rleft, impulse)))
        add("B4EA23_CHI_MISSING_FULL_FORMULA", abs(chi - primary["wrench_audit"]["rank5_unreachable_chi_missing_N_m_s"]) <= 1.0e-12, chi)

        active = read_json(EVIDENCE / "SIM13_V4B4E_ACTIVE_TRACES_V1.json")["runs"]
        primary_trace = active["rk4_reference"]["trace"]
        times = np.array(primary_trace["time_s"]); indices = range(len(times))
        snapshot_d = np.array(primary["snapshot"]["translation_palm_to_target_m"]); snapshot_r = np.array(primary["snapshot"]["rotation_palm_to_target"])
        pose_error = 0.0; twist_linear = 0.0; twist_angular = 0.0; gap_error = 0.0
        total_p: list[np.ndarray] = []; total_h: list[np.ndarray] = []; total_t: list[float] = []
        for index in indices:
            state = ServiceState(np.array(primary_trace["service_position_m"][index]), normalize_quaternion(primary_trace["service_quaternion_wxyz"][index], strict_unit=True), np.array(primary_trace["service_joint_coordinates_mixed"][index]), np.array(primary_trace["eta_mixed"][index]))
            target_state = TargetState(np.array(primary_trace["target_position_m"][index]), normalize_quaternion(primary_trace["target_quaternion_wxyz"][index], strict_unit=True), np.array(primary_trace["target_twist_mixed"][index]))
            pp, rp, pjv, pjw = model.palm_frame_and_jacobians(state); roffset = rp @ snapshot_d
            expected_position = pp + roffset; expected_rotation = rp @ snapshot_r
            aa = np.vstack((pjv - skew(roffset) @ pjw, pjw)); expected_twist = aa @ state.nu_s_mixed
            pose_error = max(pose_error, float(np.linalg.norm(expected_position - target_state.position_inertial_m)), quaternion_geodesic(target_state.quaternion_body_to_inertial_wxyz, _rotation_to_quaternion_independent(expected_rotation)))
            twist_linear = max(twist_linear, float(np.max(np.abs(expected_twist[:3] - target_state.twist_inertial_mixed[:3])))); twist_angular = max(twist_angular, float(np.max(np.abs(expected_twist[3:] - target_state.twist_inertial_mixed[3:]))))
            observations = evaluate_dual_contact(model, state, target_state, DualContactConfig(), enabled=False)
            gap_error = max(gap_error, abs(observations[0].gap_m - primary_trace["left_gap_m"][index]), abs(observations[1].gap_m - primary_trace["right_gap_m"][index]))
            sl = model.momentum_energy(state); tl = target_momentum_energy(target_state)
            total_p.append(sl.linear_momentum_n_s + tl.linear_momentum_n_s); total_h.append(sl.angular_momentum_about_inertial_origin_n_m_s + tl.angular_momentum_about_inertial_origin_n_m_s); total_t.append(sl.kinetic_energy_j + tl.kinetic_energy_j)
        add("B4EA24_ACTIVE_POSE_REBUILT_ALL_SAMPLES", pose_error <= 1.0e-9, pose_error)
        add("B4EA25_ACTIVE_TWIST_REBUILT_ALL_SAMPLES", twist_linear <= 1.0e-9 and twist_angular <= 1.0e-9, {"linear": twist_linear, "angular": twist_angular})
        add("B4EA26_ACTIVE_GAPS_REBUILT_ALL_SAMPLES", gap_error <= 1.0e-12, gap_error)
        pdrift = max(np.linalg.norm(value - total_p[0]) for value in total_p); hdrift = max(np.linalg.norm(value - total_h[0]) for value in total_h); tdrift = max(abs(value - total_t[0]) for value in total_t)
        add("B4EA27_ACTIVE_MOMENTUM_ENERGY_REBUILT", pdrift <= 1.0e-9 and hdrift <= 1.0e-9 and tdrift <= 1.0e-7, {"P": pdrift, "H": hdrift, "T": tdrift})

        no_removal = all(value["clearance"]["finite_event"] is False and value["synthetic_removal_executed"] is False for value in active.values())
        add("B4EA28_BOUNDED_NO_REMOVAL_OBSERVED", no_removal and all(abs(value["active_end_time_s"] - 0.08) <= 1.0e-14 for value in active.values()), "six bounded runs")
        cross = read_json(EVIDENCE / "SIM13_V4B4E_CROSS_INTEGRATOR_LEDGER_V1.json")
        add("B4EA29_CROSS_ACQUISITION_INDEPENDENT", cross["primary_acquisition_time_s"] != cross["independent_acquisition_time_s"] and cross["acquisition_event_time_difference_s"] <= 0.00025, cross["acquisition_event_time_difference_s"])
        add("B4EA30_NO_REMOVAL_TIME_GATE_PROMOTION", cross["removal_event_comparison"] == "NOT_EVALUATED_NO_FINITE_EVENT" and cross["both_horizon_exhausted_is_removal_capability_pass"] is False, cross["removal_event_comparison"])

        fixture = read_json(EVIDENCE / "SIM13_V4B4E_ABSTRACT_REMOVAL_FIXTURE_V1.json")
        fixture_event = fixture["fixture_event"]
        fixture_active = fixture["active_run"]
        fixture_trace = fixture_active["trace"]
        post = fixture["post_release"]
        mapping = post["mapping"]
        post_trace = post["trace"]
        acceptance = read_json(
            DIAGNOSTIC_ROOT
            / "phase_b4_synthetic_6d_constraint_acquisition_release"
            / "contracts"
            / "PHASE_B4_NUMERICAL_ACCEPTANCE_CONTRACT_V1.json"
        )
        removal_tolerances = acceptance["removal_and_event_tolerances"]
        gap_threshold = float(removal_tolerances["clearance_gap_min_m"])
        rate_threshold = -float(
            removal_tolerances["gap_reentry_closing_speed_tolerance_m_s"]
        )
        minimum_active_dwell = float(removal_tolerances["minimum_active_diagnostic_dwell_s"])
        clearance_dwell = float(removal_tolerances["clearance_dwell_s"])

        # Rebuild the fixture input from the hash-bound B3 event.  The only
        # allowed pre-acquisition changes are the two declared P coordinates
        # and their two declared rates; target and all other service channels
        # remain the frozen event values.
        fixture_service_data = fixture_event["service"]
        fixture_target_data = fixture_event["target"]
        fixture_service = ServiceState(
            np.array(fixture_service_data["base_position_inertial_m"]),
            normalize_quaternion(
                fixture_service_data["base_quaternion_body_to_inertial_wxyz"], strict_unit=True,
            ),
            np.array(fixture_service_data["joint_coordinates_mixed"]),
            np.array(fixture_service_data["nu_s_mixed"]),
        )
        fixture_target = TargetState(
            np.array(fixture_target_data["position_inertial_m"]),
            normalize_quaternion(
                fixture_target_data["quaternion_body_to_inertial_wxyz"], strict_unit=True,
            ),
            np.array(fixture_target_data["twist_inertial_mixed"]),
        )
        parent_service = primary_event["service"]
        parent_target = primary_event["target"]
        expected_coordinates = np.array(parent_service["joint_coordinates_mixed"], dtype=float)
        expected_coordinates[6:8] -= 2.0e-5
        expected_velocity = np.array(parent_service["nu_s_mixed"], dtype=float)
        expected_velocity[12:14] = 2.0e-2
        pre_acquisition_perturbation_exact = bool(
            np.max(np.abs(fixture_service.joint_coordinates_mixed - expected_coordinates)) <= 1.0e-15
            and np.max(np.abs(fixture_service.nu_s_mixed - expected_velocity)) <= 1.0e-15
            and np.max(np.abs(
                fixture_service.base_position_inertial_m
                - np.array(parent_service["base_position_inertial_m"])
            )) <= 1.0e-15
            and quaternion_geodesic(
                fixture_service.base_quaternion_body_to_inertial_wxyz,
                np.array(parent_service["base_quaternion_body_to_inertial_wxyz"]),
            ) <= 1.0e-15
            and np.max(np.abs(
                fixture_target.position_inertial_m
                - np.array(parent_target["position_inertial_m"])
            )) <= 1.0e-15
            and quaternion_geodesic(
                fixture_target.quaternion_body_to_inertial_wxyz,
                np.array(parent_target["quaternion_body_to_inertial_wxyz"]),
            ) <= 1.0e-15
            and np.max(np.abs(
                fixture_target.twist_inertial_mixed
                - np.array(parent_target["twist_inertial_mixed"])
            )) <= 1.0e-15
        )

        # This perturbed state is intentionally not a B3 trigger.  Recompute
        # its contact geometry and elastic storage with the contact kernel;
        # neither the common points nor the potentials may be inherited from
        # record 205.  Runtime evidence of a completed projection is accepted
        # only alongside an AST proof that the fixture call explicitly opted
        # into the narrowly scoped nontrigger allowance.
        fixture_observations_at_input = evaluate_dual_contact(
            model, fixture_service, fixture_target, DualContactConfig(), enabled=True,
        )
        fixture_criteria = fixture_event["criteria"]
        fixture_left_point = np.asarray(fixture_event["left_common_contact_point_m"], dtype=float)
        fixture_right_point = np.asarray(fixture_event["right_common_contact_point_m"], dtype=float)
        fixture_left_potential = float(fixture_event["left_contact_potential_J"])
        fixture_right_potential = float(fixture_event["right_contact_potential_J"])
        parent_left_point = np.asarray(primary_event["left_common_contact_point_m"], dtype=float)
        parent_right_point = np.asarray(primary_event["right_common_contact_point_m"], dtype=float)
        parent_left_potential = float(primary_event["left_contact_potential_J"])
        parent_right_potential = float(primary_event["right_contact_potential_J"])
        contact_point_errors = {
            "left_m": float(np.max(np.abs(
                fixture_left_point
                - fixture_observations_at_input[0].common_contact_point_inertial_m
            ))),
            "right_m": float(np.max(np.abs(
                fixture_right_point
                - fixture_observations_at_input[1].common_contact_point_inertial_m
            ))),
        }
        contact_potential_errors = {
            "left_J": abs(
                fixture_left_potential - fixture_observations_at_input[0].elastic_energy_j
            ),
            "right_J": abs(
                fixture_right_potential - fixture_observations_at_input[1].elastic_energy_j
            ),
        }
        contact_point_parent_deltas = {
            "left_m": float(np.max(np.abs(fixture_left_point - parent_left_point))),
            "right_m": float(np.max(np.abs(fixture_right_point - parent_right_point))),
        }
        contact_potential_parent_deltas = {
            "left_J": abs(fixture_left_potential - parent_left_potential),
            "right_J": abs(fixture_right_potential - parent_right_potential),
        }
        fixture_contact_recomputed_pass = bool(
            max(contact_point_errors.values()) <= 1.0e-12
            and max(contact_potential_errors.values()) <= 1.0e-12
            and min(contact_point_parent_deltas.values()) > 1.0e-12
            and min(contact_potential_parent_deltas.values()) > 1.0e-12
            and fixture_criteria["left_contact"]
            is bool(fixture_observations_at_input[0].penetration_m > 0.0)
            and fixture_criteria["right_contact"]
            is bool(fixture_observations_at_input[1].penetration_m > 0.0)
            and abs(
                float(fixture_criteria["left_gap_m"])
                - fixture_observations_at_input[0].gap_m
            ) <= 1.0e-12
            and abs(
                float(fixture_criteria["right_gap_m"])
                - fixture_observations_at_input[1].gap_m
            ) <= 1.0e-12
            and abs(
                float(fixture_criteria["left_relative_normal_speed_m_s"])
                - fixture_observations_at_input[0].relative_normal_speed_m_s
            ) <= 1.0e-12
            and abs(
                float(fixture_criteria["right_relative_normal_speed_m_s"])
                - fixture_observations_at_input[1].relative_normal_speed_m_s
            ) <= 1.0e-12
            and abs(float(fixture_criteria["left_finger_rate_m_s"]) - expected_velocity[12])
            <= 1.0e-15
            and abs(float(fixture_criteria["right_finger_rate_m_s"]) - expected_velocity[13])
            <= 1.0e-15
        )
        fixture_nontrigger_contract_pass = bool(
            fixture_event["run_id"] == "algorithm_only_consistent_offgrid_finite_event_fixture"
            and int(fixture_event["index"]) == -1
            and fixture_event["state_label"] == "ALGORITHM_ONLY_NONTRIGGER_INITIAL_STATE_FIXTURE"
            and fixture_event["source"]
            == "ALGORITHM_ONLY_NONTRIGGER_PRE_ACQUISITION_STATE_PERTURBED_FROM_HASH_BOUND_B3_EVENT__NOT_B3_MAIN_BRANCH"
            and float(fixture_event["b3_dissipation_J"]) == 0.0
            and fixture_criteria["algorithm_only_nontrigger_fixture"] is True
            and fixture_criteria["physical_or_main_trigger_credit"] is False
            and int(fixture_criteria["parent_hash_bound_b3_trigger_index"])
            == int(primary_event["index"])
            and fixture_criteria["all_ledgers_closed"] is False
            and fixture_criteria["soft_capture_transient_qualifies"] is False
            and fixture_criteria["qualification_reason"]
            == "NONTRIGGER_ALGORITHM_BRANCH_COVERAGE_ONLY"
        )
        solver_source_tree = ast.parse(
            (PHASE_ROOT / "b4_solver" / "constraint_solver.py").read_text(encoding="utf-8")
        )
        fixture_function = next(
            node for node in solver_source_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "_execute_consistent_finite_event_fixture"
        )
        allowance_calls = [
            node for node in ast.walk(fixture_function)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "acquisition_projection"
        ]
        explicit_nontrigger_allowance_call_present = bool(
            len(allowance_calls) == 1
            and any(
                keyword.arg == "allow_algorithm_only_nontrigger_fixture"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in allowance_calls[0].keywords
            )
        )

        fixture_palm, fixture_palm_rotation, fixture_jv, fixture_jw = model.palm_frame_and_jacobians(
            fixture_service
        )
        fixture_snapshot_d = fixture_palm_rotation.T @ (
            fixture_target.position_inertial_m - fixture_palm
        )
        fixture_snapshot_r = fixture_palm_rotation.T @ quat_to_rotation(
            fixture_target.quaternion_body_to_inertial_wxyz
        )
        fixture_offset = fixture_target.position_inertial_m - fixture_palm
        fixture_a = np.vstack((fixture_jv - skew(fixture_offset) @ fixture_jw, fixture_jw))
        fixture_target_mass = _target_spatial_mass_independent(fixture_target)
        fixture_mminus = block_diagonal(model.mass_matrix(fixture_service), fixture_target_mass)
        fixture_zminus = np.concatenate((
            fixture_service.nu_s_mixed, fixture_target.twist_inertial_mixed,
        ))
        fixture_jc = np.hstack((-fixture_a, np.eye(6)))
        fixture_reference_length = 0.5 * np.linalg.norm(
            np.array(fixture_event["right_common_contact_point_m"])
            - np.array(fixture_event["left_common_contact_point_m"])
        )
        fixture_d = np.diag(np.concatenate((np.ones(3), fixture_reference_length * np.ones(3))))
        fixture_jbar = fixture_d @ fixture_jc
        fixture_kkt = np.block([
            [fixture_mminus, -fixture_jbar.T],
            [-fixture_jbar, np.zeros((6, 6))],
        ])
        fixture_projection = np.linalg.solve(
            fixture_kkt,
            np.concatenate((fixture_mminus @ fixture_zminus, np.zeros(6))),
        )[:20]

        fixture_time = np.asarray(fixture_trace["time_s"], dtype=float)
        fixture_position = np.asarray(fixture_trace["service_position_m"], dtype=float)
        fixture_quaternion = np.asarray(fixture_trace["service_quaternion_wxyz"], dtype=float)
        fixture_coordinates = np.asarray(fixture_trace["service_joint_coordinates_mixed"], dtype=float)
        fixture_eta = np.asarray(fixture_trace["eta_mixed"], dtype=float)
        fixture_target_position = np.asarray(fixture_trace["target_position_m"], dtype=float)
        fixture_target_quaternion = np.asarray(fixture_trace["target_quaternion_wxyz"], dtype=float)
        fixture_target_twist = np.asarray(fixture_trace["target_twist_mixed"], dtype=float)
        fixture_left_gap_recorded = np.asarray(fixture_trace["left_gap_m"], dtype=float)
        fixture_right_gap_recorded = np.asarray(fixture_trace["right_gap_m"], dtype=float)
        fixture_left_rate_recorded = np.asarray(fixture_trace["left_gap_rate_m_s"], dtype=float)
        fixture_right_rate_recorded = np.asarray(fixture_trace["right_gap_rate_m_s"], dtype=float)
        fixture_count = len(fixture_time)
        fixture_shape_clean = bool(
            fixture_count >= 2
            and np.all(np.diff(fixture_time) > 0.0)
            and fixture_position.shape == (fixture_count, 3)
            and fixture_quaternion.shape == (fixture_count, 4)
            and fixture_coordinates.shape == (fixture_count, 8)
            and fixture_eta.shape == (fixture_count, 14)
            and fixture_target_position.shape == (fixture_count, 3)
            and fixture_target_quaternion.shape == (fixture_count, 4)
            and fixture_target_twist.shape == (fixture_count, 6)
        )
        first_target_expected, first_a_expected = _snapshot_target_independent(
            model,
            ServiceState(
                fixture_position[0], fixture_quaternion[0], fixture_coordinates[0], fixture_eta[0],
            ),
            fixture_snapshot_d,
            fixture_snapshot_r,
        )
        post_acquisition_first_state_exact = bool(
            abs(fixture_time[0] - float(fixture_event["time_s"])) <= 1.0e-15
            and np.max(np.abs(fixture_position[0] - fixture_service.base_position_inertial_m)) <= 1.0e-15
            and quaternion_geodesic(
                fixture_quaternion[0], fixture_service.base_quaternion_body_to_inertial_wxyz,
            ) <= 1.0e-15
            and np.max(np.abs(fixture_coordinates[0] - fixture_service.joint_coordinates_mixed)) <= 1.0e-15
            and np.max(np.abs(fixture_eta[0] - fixture_projection[:14])) <= 1.0e-10
            and np.max(np.abs(fixture_target_position[0] - first_target_expected.position_inertial_m)) <= 1.0e-12
            and quaternion_geodesic(
                fixture_target_quaternion[0], first_target_expected.quaternion_body_to_inertial_wxyz,
            ) <= 1.0e-12
            and np.max(np.abs(fixture_target_twist[0] - first_a_expected @ fixture_eta[0])) <= 1.0e-10
        )

        # Independently rebuild every active fixture sample used by the event
        # certifier.  These arrays, not the recorded pass boolean, drive the
        # continuous dwell audit below.
        fixture_left_gap = np.empty(fixture_count)
        fixture_right_gap = np.empty(fixture_count)
        fixture_left_rate = np.empty(fixture_count)
        fixture_right_rate = np.empty(fixture_count)
        fixture_linear = np.empty((fixture_count, 3))
        fixture_angular = np.empty((fixture_count, 3))
        fixture_energy = np.empty(fixture_count)
        fixture_pose_translation = np.empty(fixture_count)
        fixture_pose_rotation = np.empty(fixture_count)
        fixture_twist_linear = np.empty(fixture_count)
        fixture_twist_angular = np.empty(fixture_count)
        fixture_contact_force = np.empty(fixture_count)
        fixture_contact_torque = np.empty(fixture_count)
        for index in range(fixture_count):
            fixture_service_sample = ServiceState(
                fixture_position[index], fixture_quaternion[index],
                fixture_coordinates[index], fixture_eta[index],
            )
            fixture_target_sample = TargetState(
                fixture_target_position[index], fixture_target_quaternion[index],
                fixture_target_twist[index],
            )
            expected_target, expected_a = _snapshot_target_independent(
                model, fixture_service_sample, fixture_snapshot_d, fixture_snapshot_r,
            )
            fixture_pose_translation[index] = np.linalg.norm(
                fixture_target_sample.position_inertial_m - expected_target.position_inertial_m
            )
            fixture_pose_rotation[index] = quaternion_geodesic(
                fixture_target_sample.quaternion_body_to_inertial_wxyz,
                expected_target.quaternion_body_to_inertial_wxyz,
            )
            relative_twist = fixture_target_sample.twist_inertial_mixed - expected_a @ fixture_eta[index]
            fixture_twist_linear[index] = np.max(np.abs(relative_twist[:3]))
            fixture_twist_angular[index] = np.max(np.abs(relative_twist[3:]))
            fixture_observations = evaluate_dual_contact(
                model, fixture_service_sample, fixture_target_sample,
                DualContactConfig(), enabled=False,
            )
            fixture_left_gap[index] = fixture_observations[0].gap_m
            fixture_right_gap[index] = fixture_observations[1].gap_m
            fixture_left_rate[index] = fixture_observations[0].relative_normal_speed_m_s
            fixture_right_rate[index] = fixture_observations[1].relative_normal_speed_m_s
            fixture_contact_force[index] = max(
                np.linalg.norm(item.service_force_inertial_n) for item in fixture_observations
            )
            fixture_contact_torque[index] = max(
                np.linalg.norm(item.service_shift_torque_inertial_n_m) for item in fixture_observations
            )
            fixture_service_ledger = model.momentum_energy(fixture_service_sample)
            fixture_target_ledger = target_momentum_energy(fixture_target_sample)
            fixture_linear[index] = (
                fixture_service_ledger.linear_momentum_n_s
                + fixture_target_ledger.linear_momentum_n_s
            )
            fixture_angular[index] = (
                fixture_service_ledger.angular_momentum_about_inertial_origin_n_m_s
                + fixture_target_ledger.angular_momentum_about_inertial_origin_n_m_s
            )
            fixture_energy[index] = (
                fixture_service_ledger.kinetic_energy_j + fixture_target_ledger.kinetic_energy_j
            )
        fixture_linear_drift = np.linalg.norm(fixture_linear - fixture_linear[0], axis=1)
        fixture_angular_drift = np.linalg.norm(fixture_angular - fixture_angular[0], axis=1)
        fixture_energy_drift = np.abs(fixture_energy - fixture_energy[0])
        fixture_ledgers_recorded = fixture_trace["sample_ledgers"]
        fixture_observation_match = bool(
            np.max(np.abs(fixture_left_gap - fixture_left_gap_recorded)) <= 1.0e-12
            and np.max(np.abs(fixture_right_gap - fixture_right_gap_recorded)) <= 1.0e-12
            and np.max(np.abs(fixture_left_rate - fixture_left_rate_recorded)) <= 1.0e-12
            and np.max(np.abs(fixture_right_rate - fixture_right_rate_recorded)) <= 1.0e-12
            and np.max(np.abs(
                fixture_linear_drift
                - np.asarray(fixture_ledgers_recorded["linear_momentum_drift_N_s"])
            )) <= 1.0e-12
            and np.max(np.abs(
                fixture_angular_drift
                - np.asarray(fixture_ledgers_recorded["angular_momentum_drift_N_m_s"])
            )) <= 1.0e-12
            and np.max(np.abs(
                fixture_energy_drift
                - np.asarray(fixture_ledgers_recorded["energy_plus_dissipation_drift_J"])
            )) <= 1.0e-12
            and np.max(np.abs(
                fixture_pose_translation
                - np.asarray(fixture_ledgers_recorded["pose_translation_residual_m"])
            )) <= 1.0e-12
            and np.max(np.abs(
                fixture_pose_rotation
                - np.asarray(fixture_ledgers_recorded["pose_rotation_residual_rad"])
            )) <= 1.0e-12
            and np.max(np.abs(
                fixture_twist_linear
                - np.asarray(fixture_ledgers_recorded["relative_linear_twist_m_s"])
            )) <= 1.0e-12
            and np.max(np.abs(
                fixture_twist_angular
                - np.asarray(fixture_ledgers_recorded["relative_angular_twist_rad_s"])
            )) <= 1.0e-12
        )
        recorded_required_closed = (
            (np.asarray(fixture_ledgers_recorded["linear_momentum_drift_N_s"]) <= 1.0e-9)
            & (np.asarray(fixture_ledgers_recorded["angular_momentum_drift_N_m_s"]) <= 1.0e-9)
            & (np.asarray(fixture_ledgers_recorded["energy_plus_dissipation_drift_J"]) <= 1.0e-7)
            & (np.asarray(fixture_ledgers_recorded["pose_translation_residual_m"]) <= 1.0e-9)
            & (np.asarray(fixture_ledgers_recorded["pose_rotation_residual_rad"]) <= 1.0e-9)
            & (np.asarray(fixture_ledgers_recorded["relative_linear_twist_m_s"]) <= 1.0e-9)
            & (np.asarray(fixture_ledgers_recorded["relative_angular_twist_rad_s"]) <= 1.0e-9)
            & (np.abs(np.asarray(fixture_ledgers_recorded["ideal_constraint_power_W"])) <= 1.0e-10)
            & (np.asarray(fixture_ledgers_recorded["contact_force_while_active_N"]) <= 1.0e-12)
            & (np.asarray(fixture_ledgers_recorded["contact_torque_while_active_N_m"]) <= 1.0e-12)
        )
        independently_closed = (
            (fixture_linear_drift <= 1.0e-9)
            & (fixture_angular_drift <= 1.0e-9)
            & (fixture_energy_drift <= 1.0e-7)
            & (fixture_pose_translation <= 1.0e-9)
            & (fixture_pose_rotation <= 1.0e-9)
            & (fixture_twist_linear <= 1.0e-9)
            & (fixture_twist_angular <= 1.0e-9)
            & (fixture_contact_force <= 1.0e-12)
            & (fixture_contact_torque <= 1.0e-12)
        )
        fixture_sample_closed = recorded_required_closed & independently_closed
        fixture_good_intervals = _continuous_good_intervals_independent(
            fixture_time,
            fixture_left_gap,
            fixture_right_gap,
            fixture_left_rate,
            fixture_right_rate,
            fixture_sample_closed[:-1] & fixture_sample_closed[1:],
            gap_threshold_m=gap_threshold,
            rate_threshold_m_s=rate_threshold,
        )
        independent_tau = None
        independent_removal = None
        eligible_start = float(fixture_event["time_s"]) + minimum_active_dwell
        for interval_lower, interval_upper in fixture_good_intervals:
            candidate_tau = max(interval_lower, eligible_start)
            if interval_upper - candidate_tau >= clearance_dwell - 1.0e-12:
                independent_tau = candidate_tau
                independent_removal = candidate_tau + clearance_dwell
                break
        reported_clearance = fixture["clearance"]
        tau_c = float(reported_clearance["tau_c_s"])
        removal_time = float(reported_clearance["removal_time_s"])
        active_dwell_minima = _continuous_native_minima_independent(
            fixture_time,
            fixture_left_gap,
            fixture_right_gap,
            fixture_left_rate,
            fixture_right_rate,
            start_s=tau_c,
            end_s=removal_time,
        )
        active_interval_contains_dwell = any(
            lower <= tau_c + 1.0e-12 and upper >= removal_time - 1.0e-12
            for lower, upper in fixture_good_intervals
        )
        active_dwell_pass = bool(
            independent_tau is not None
            and independent_removal is not None
            and abs(tau_c - independent_tau) <= 1.0e-12
            and abs(removal_time - independent_removal) <= 1.0e-12
            and abs(removal_time - tau_c - clearance_dwell) <= 1.0e-12
            and active_interval_contains_dwell
        )

        # The removal time must be off the active sample grid.  Starting from
        # the accepted grid state immediately before it, independently replay
        # the accepted integrator over only the fractional remainder and bind
        # that exact state to the post-release 42D sample zero.
        fixture_step = float(fixture_event["step_s"])
        offgrid_index = (removal_time - float(fixture_event["time_s"])) / fixture_step
        offgrid_event = abs(offgrid_index - round(offgrid_index)) > 1.0e-6
        release_left_index = int(np.searchsorted(fixture_time, removal_time, side="right") - 1)
        release_left_index = max(0, min(release_left_index, fixture_count - 1))
        release_left_state = np.concatenate((
            fixture_position[release_left_index],
            fixture_quaternion[release_left_index],
            fixture_coordinates[release_left_index],
            fixture_eta[release_left_index],
        ))
        release_remainder = removal_time - float(fixture_time[release_left_index])
        release_state = _partial_active_step_independent(
            model,
            fixture_snapshot_d,
            fixture_snapshot_r,
            release_left_state,
            release_remainder,
            str(fixture_event["method"]),
        )
        release_service = _service_from_29(release_state)
        release_target, release_a = _snapshot_target_independent(
            model, release_service, fixture_snapshot_d, fixture_snapshot_r,
        )

        post_time = np.asarray(post_trace["time_s"], dtype=float)
        post_service_state = np.asarray(post_trace["service_state_29"], dtype=float)
        post_target_state = np.asarray(post_trace["target_state_13"], dtype=float)
        post_count = len(post_time)
        post_shape_clean = bool(
            post_count >= 2
            and post_service_state.shape == (post_count, 29)
            and post_target_state.shape == (post_count, 13)
            and np.all(np.diff(post_time) > 0.0)
        )
        post_service_zero = _service_from_29(post_service_state[0])
        post_target_zero = _target_from_13(post_target_state[0])
        release_configuration_errors = {
            "service_base_position_m": float(np.max(np.abs(
                post_service_state[0, :3] - release_state[:3]
            ))),
            "service_base_rotation_rad": quaternion_geodesic(
                post_service_state[0, 3:7], release_state[3:7],
            ),
            "service_R_joint_rad": float(np.max(np.abs(
                post_service_state[0, 7:13] - release_state[7:13]
            ))),
            "service_P_joint_m": float(np.max(np.abs(
                post_service_state[0, 13:15] - release_state[13:15]
            ))),
            "target_position_m": float(np.max(np.abs(
                post_target_state[0, :3] - release_target.position_inertial_m
            ))),
            "target_rotation_rad": quaternion_geodesic(
                post_target_state[0, 3:7], release_target.quaternion_body_to_inertial_wxyz,
            ),
        }
        native_slices = {
            "service_base_linear_m_s": slice(0, 3),
            "service_base_angular_rad_s": slice(3, 6),
            "service_R_joint_rad_s": slice(6, 12),
            "service_P_joint_m_s": slice(12, 14),
            "target_linear_m_s": slice(14, 17),
            "target_angular_rad_s": slice(17, 20),
        }
        z_before_fixture = np.asarray(mapping["z_before"], dtype=float)
        z_after_fixture = np.asarray(mapping["z_after"], dtype=float)
        post_zero_z = np.concatenate((post_service_state[0, 15:29], post_target_state[0, 7:13]))
        independent_release_z = np.concatenate((release_state[15:29], release_a @ release_state[15:29]))
        z_before_reconstruction_errors = {
            name: float(np.max(np.abs(z_before_fixture[indices] - independent_release_z[indices])))
            for name, indices in native_slices.items()
        }
        z_copy_errors = {
            name: float(np.max(np.abs(z_after_fixture[indices] - z_before_fixture[indices])))
            for name, indices in native_slices.items()
        }
        post_zero_binding_errors = {
            name: float(np.max(np.abs(post_zero_z[indices] - z_after_fixture[indices])))
            for name, indices in native_slices.items()
        }
        mapping_native_maxima_match = all(
            abs(float(mapping["native_velocity_jump_maxima"][name]) - z_copy_errors[name]) <= 1.0e-15
            for name in native_slices
        )
        exact_release_state_pass = bool(
            abs(post_time[0] - removal_time) <= 1.0e-15
            and release_remainder > 1.0e-12
            and release_remainder < fixture_step - 1.0e-12
            and max(release_configuration_errors.values()) <= 1.0e-10
            and max(z_before_reconstruction_errors.values()) <= 1.0e-10
            and max(z_copy_errors.values()) <= 1.0e-12
            and max(post_zero_binding_errors.values()) <= 1.0e-12
            and mapping_native_maxima_match
        )

        # Independently rebuild the zero-jump mapping ledgers from z_before and
        # z_after using the common release configuration.
        mapping_service_before = ServiceState(
            post_service_zero.base_position_inertial_m,
            post_service_zero.base_quaternion_body_to_inertial_wxyz,
            post_service_zero.joint_coordinates_mixed,
            z_before_fixture[:14],
        )
        mapping_target_before = TargetState(
            post_target_zero.position_inertial_m,
            post_target_zero.quaternion_body_to_inertial_wxyz,
            z_before_fixture[14:20],
        )
        mapping_service_after = ServiceState(
            post_service_zero.base_position_inertial_m,
            post_service_zero.base_quaternion_body_to_inertial_wxyz,
            post_service_zero.joint_coordinates_mixed,
            z_after_fixture[:14],
        )
        mapping_target_after = TargetState(
            post_target_zero.position_inertial_m,
            post_target_zero.quaternion_body_to_inertial_wxyz,
            z_after_fixture[14:20],
        )
        mapping_service_before_ledger = model.momentum_energy(mapping_service_before)
        mapping_target_before_ledger = target_momentum_energy(mapping_target_before)
        mapping_service_after_ledger = model.momentum_energy(mapping_service_after)
        mapping_target_after_ledger = target_momentum_energy(mapping_target_after)
        independent_mapping_linear = (
            mapping_service_after_ledger.linear_momentum_n_s
            + mapping_target_after_ledger.linear_momentum_n_s
            - mapping_service_before_ledger.linear_momentum_n_s
            - mapping_target_before_ledger.linear_momentum_n_s
        )
        independent_mapping_angular = (
            mapping_service_after_ledger.angular_momentum_about_inertial_origin_n_m_s
            + mapping_target_after_ledger.angular_momentum_about_inertial_origin_n_m_s
            - mapping_service_before_ledger.angular_momentum_about_inertial_origin_n_m_s
            - mapping_target_before_ledger.angular_momentum_about_inertial_origin_n_m_s
        )
        independent_mapping_energy = (
            mapping_service_after_ledger.kinetic_energy_j
            + mapping_target_after_ledger.kinetic_energy_j
            - mapping_service_before_ledger.kinetic_energy_j
            - mapping_target_before_ledger.kinetic_energy_j
        )
        mapping_ledger_pass = bool(
            np.linalg.norm(independent_mapping_linear) <= 1.0e-12
            and np.linalg.norm(independent_mapping_angular) <= 1.0e-12
            and abs(independent_mapping_energy) <= 1.0e-12
            and np.max(np.abs(
                independent_mapping_linear - np.asarray(mapping["linear_impulse_N_s"])
            )) <= 1.0e-12
            and np.max(np.abs(
                independent_mapping_angular - np.asarray(mapping["angular_impulse_N_m_s"])
            )) <= 1.0e-12
            and abs(independent_mapping_energy - float(mapping["kinetic_energy_jump_J"])) <= 1.0e-12
            and float(mapping["ideal_constraint_stored_energy_J"]) == 0.0
        )

        # Recompute contact observations and P/H/T at every post-release
        # sample.  The recorded post_release_passed flag is deliberately not
        # used as a premise for any of these checks.
        post_left_gap = np.empty(post_count)
        post_right_gap = np.empty(post_count)
        post_left_rate = np.empty(post_count)
        post_right_rate = np.empty(post_count)
        post_contact_force = np.empty(post_count)
        post_contact_torque = np.empty(post_count)
        post_linear = np.empty((post_count, 3))
        post_angular = np.empty((post_count, 3))
        post_energy = np.empty(post_count)
        post_snapshot_translation = np.empty(post_count)
        post_snapshot_rotation = np.empty(post_count)
        for index in range(post_count):
            service_sample = _service_from_29(post_service_state[index])
            target_sample = _target_from_13(post_target_state[index])
            post_observations = evaluate_dual_contact(
                model, service_sample, target_sample, DualContactConfig(), enabled=False,
            )
            post_left_gap[index] = post_observations[0].gap_m
            post_right_gap[index] = post_observations[1].gap_m
            post_left_rate[index] = post_observations[0].relative_normal_speed_m_s
            post_right_rate[index] = post_observations[1].relative_normal_speed_m_s
            post_contact_force[index] = max(
                np.linalg.norm(item.service_force_inertial_n) for item in post_observations
            )
            post_contact_torque[index] = max(
                np.linalg.norm(item.service_shift_torque_inertial_n_m) for item in post_observations
            )
            service_ledger = model.momentum_energy(service_sample)
            target_ledger = target_momentum_energy(target_sample)
            post_linear[index] = (
                service_ledger.linear_momentum_n_s + target_ledger.linear_momentum_n_s
            )
            post_angular[index] = (
                service_ledger.angular_momentum_about_inertial_origin_n_m_s
                + target_ledger.angular_momentum_about_inertial_origin_n_m_s
            )
            post_energy[index] = service_ledger.kinetic_energy_j + target_ledger.kinetic_energy_j
            snapshot_target, _ = _snapshot_target_independent(
                model, service_sample, fixture_snapshot_d, fixture_snapshot_r,
            )
            post_snapshot_translation[index] = np.linalg.norm(
                target_sample.position_inertial_m - snapshot_target.position_inertial_m
            )
            post_snapshot_rotation[index] = quaternion_geodesic(
                target_sample.quaternion_body_to_inertial_wxyz,
                snapshot_target.quaternion_body_to_inertial_wxyz,
            )
        post_linear_drift = np.linalg.norm(post_linear - post_linear[0], axis=1)
        post_angular_drift = np.linalg.norm(post_angular - post_angular[0], axis=1)
        post_energy_drift = np.abs(post_energy - post_energy[0])
        post_evidence_match = bool(
            np.max(np.abs(post_left_gap - np.asarray(post_trace["left_gap_m"]))) <= 1.0e-12
            and np.max(np.abs(post_right_gap - np.asarray(post_trace["right_gap_m"]))) <= 1.0e-12
            and np.max(np.abs(post_left_rate - np.asarray(post_trace["left_gap_rate_m_s"]))) <= 1.0e-12
            and np.max(np.abs(post_right_rate - np.asarray(post_trace["right_gap_rate_m_s"]))) <= 1.0e-12
            and np.max(np.abs(
                post_contact_force - np.asarray(post_trace["contact_force_N"])
            )) <= 1.0e-12
            and np.max(np.abs(
                post_contact_torque - np.asarray(post_trace["contact_torque_N_m"])
            )) <= 1.0e-12
            and np.max(np.abs(
                post_linear_drift - np.asarray(post_trace["linear_momentum_drift_N_s"])
            )) <= 1.0e-12
            and np.max(np.abs(
                post_angular_drift - np.asarray(post_trace["angular_momentum_drift_N_m_s"])
            )) <= 1.0e-12
            and np.max(np.abs(
                post_energy_drift - np.asarray(post_trace["energy_drift_J"])
            )) <= 1.0e-12
            and np.max(np.abs(
                post_snapshot_translation
                - np.asarray(post_trace["snapshot_translation_residual_m"])
            )) <= 1.0e-12
            and np.max(np.abs(
                post_snapshot_rotation
                - np.asarray(post_trace["snapshot_rotation_residual_rad"])
            )) <= 1.0e-12
        )
        post_duration = float(post_time[-1] - post_time[0])
        post_time_clean = bool(
            abs(post_duration - 0.005) <= 1.0e-12
            and abs(float(post["observation_duration_s"]) - 0.005) <= 1.0e-12
            and np.max(np.abs(np.diff(post_time) - float(post["step_s"]))) <= 1.0e-15
        )
        post_calls_clean = bool(
            len(post_trace["contact_calls"]) == post_count
            and all(
                item["phase"] == "POST_REMOVAL"
                and item["sample_index"] == index
                and item["enabled_argument"] is False
                for index, item in enumerate(post_trace["contact_calls"])
            )
            and np.max(post_contact_force) <= 1.0e-12
            and np.max(post_contact_torque) <= 1.0e-12
        )
        post_ledger_pass = bool(
            np.max(post_linear_drift) <= 1.0e-9
            and np.max(post_angular_drift) <= 1.0e-9
            and np.max(post_energy_drift) <= 1.0e-7
        )
        post_clearance_minima = _continuous_native_minima_independent(
            post_time,
            post_left_gap,
            post_right_gap,
            post_left_rate,
            post_right_rate,
        )
        post_clearance_pass = bool(
            post_clearance_minima["left_gap_m"] >= gap_threshold
            and post_clearance_minima["right_gap_m"] >= gap_threshold
            and post_clearance_minima["left_gap_rate_m_s"] >= rate_threshold
            and post_clearance_minima["right_gap_rate_m_s"] >= rate_threshold
        )
        post_target_independent = bool(
            np.max(post_snapshot_translation) > 0.0 or np.max(post_snapshot_rotation) > 0.0
        )
        reported_post_flags_consistent = bool(
            post["method"] == fixture_event["method"]
            and abs(float(post["release_time_s"]) - removal_time) <= 1.0e-15
            and post["target_state_source_after_removal"]
            == "INDEPENDENT_13D_ZERO_EXTERNAL_FREE_FLIGHT"
            and post["service_state_source_after_removal"]
            == "INDEPENDENT_29D_ZERO_EXTERNAL_FREE_FLIGHT"
            and post["mapping_pass"] is True
            and post["contact_kernel_disabled_pass"] is True
            and post["post_release_ledger_pass"] is True
            and post["observation_duration_pass"] is True
            and post["clearance"]["full_interval_certified"] is True
            and post["post_release_passed"] is True
            and post["terminal_status"]
            == "SYNTHETIC_CONSTRAINT_REMOVAL_AND_POST_RELEASE_OBSERVATION_COMPLETE"
            and post["physical_release_claimed"] is False
        )

        required_interval = np.asarray(fixture["same_active_trajectory_required_interval_s"])
        fixture_semantics_pass = bool(
            "PERTURBED_FROM_HASH_BOUND_B3_EVENT" in fixture["scope"]
            and "NOT_MAIN_B3_TRAJECTORY" in fixture["scope"]
            and fixture["fixture_inputs_are_hardware_specifications"] is False
            and fixture["fixture_satisfies_main_b3_soft_capture_trigger"] is False
            and fixture["fixture_receives_physical_or_main_trigger_credit"] is False
            and fixture["fixture_contact_points_and_potentials_recomputed_from_perturbed_state"]
            is True
            and fixture["no_state_mutation_after_acquisition"] is True
            and fixture["clearance_derived_from_same_active_state_trajectory"] is True
            and fixture["propagate_active_finite_event_branch_executed"] is True
            and fixture["exact_active_state_reconstructed_at_offgrid_removal_time"] is True
            and fixture["fixture_pass_does_not_set_main_synthetic_removal_executed"] is True
            and fixture_active["synthetic_removal_executed"] is True
            and fixture_active["clearance"] == reported_clearance
            and fixture_active["post_release"] == post
            and reported_clearance["finite_event"] is True
            and required_interval.shape == (2,)
            and np.max(np.abs(required_interval - np.array((fixture_time[0], removal_time)))) <= 1.0e-15
            and fixture["active_trace_semantics"]
            == "FULL_COUNTERFACTUAL_ATTACHED_SEARCH_TRACE_FOR_EARLIEST_EVENT_CERTIFICATION__EXECUTED_HYBRID_HISTORY_SWITCHES_AT_REMOVAL_TIME"
        )
        b4ea31_pass = all((
            pre_acquisition_perturbation_exact,
            fixture_contact_recomputed_pass,
            fixture_nontrigger_contract_pass,
            explicit_nontrigger_allowance_call_present,
            fixture_shape_clean,
            post_acquisition_first_state_exact,
            fixture_observation_match,
            bool(np.all(fixture_sample_closed)),
            active_dwell_pass,
            offgrid_event,
            exact_release_state_pass,
            post_shape_clean,
            mapping_ledger_pass,
            post_evidence_match,
            post_time_clean,
            post_calls_clean,
            post_ledger_pass,
            post_clearance_pass,
            post_target_independent,
            reported_post_flags_consistent,
            fixture_semantics_pass,
        ))
        add(
            "B4EA31_RELEASE_MAPPING_FIXTURE",
            b4ea31_pass,
            {
                "scope": fixture["scope"],
                "pre_acquisition_perturbation_exact": pre_acquisition_perturbation_exact,
                "nontrigger_contract_exact": fixture_nontrigger_contract_pass,
                "explicit_nontrigger_allowance_call_present": explicit_nontrigger_allowance_call_present,
                "contact_geometry_and_potential_recomputed": fixture_contact_recomputed_pass,
                "contact_point_recompute_errors_m": contact_point_errors,
                "contact_potential_recompute_errors_J": contact_potential_errors,
                "contact_point_deltas_from_parent_m": contact_point_parent_deltas,
                "contact_potential_deltas_from_parent_J": contact_potential_parent_deltas,
                "post_acquisition_first_state_exact": post_acquisition_first_state_exact,
                "same_active_trajectory_observations_rebuilt": fixture_observation_match,
                "active_tau_c_s": tau_c,
                "active_removal_time_s": removal_time,
                "active_dwell_minima": active_dwell_minima,
                "offgrid_fractional_index": offgrid_index,
                "release_remainder_s": release_remainder,
                "release_configuration_errors": release_configuration_errors,
                "z_before_reconstruction_errors_by_native_channel": z_before_reconstruction_errors,
                "z_copy_errors_by_native_channel": z_copy_errors,
                "post_zero_binding_errors_by_native_channel": post_zero_binding_errors,
                "post_duration_s": post_duration,
                "post_clearance_minima": post_clearance_minima,
                "post_P_H_T_drift": {
                    "linear_N_s": float(np.max(post_linear_drift)),
                    "angular_N_m_s": float(np.max(post_angular_drift)),
                    "energy_J": float(np.max(post_energy_drift)),
                },
                "post_contact_disabled_zero": post_calls_clean,
                "post_target_independent": post_target_independent,
                "reported_post_flags_only_consistency_checked": reported_post_flags_consistent,
            },
        )
        trap_min = hermite_minimum(2.0e-6, 2.0e-6, -0.01, 0.01, 0.001)
        add("B4EA32_CLEARANCE_INTERNAL_TRAP_REBUILT", trap_min < 1.0e-6 and fixture["internal_negative_gap_trap"]["certifier_returned_finite_event"] is False, trap_min)

        negative = read_json(EVIDENCE / "SIM13_V4B4E_NEGATIVE_CONTROLS_V1.json")
        expected_ids = read_json(DIAGNOSTIC_ROOT / "phase_b4_synthetic_6d_constraint_acquisition_release" / "contracts" / "PHASE_B4_NUMERICAL_ACCEPTANCE_CONTRACT_V1.json")["future_solver_required_negative_control_ids"]
        add("B4EA33_NEGATIVE_CONTROLS_EXACT", [item["id"] for item in negative["results"]] == expected_ids and negative["count"] == negative["passed"] == 22, negative["count"])
        nc21 = next(item for item in negative["results"] if item["id"] == "B4NC21_PHYSICAL_OR_FORMAL_AUTHORITY_TRUE")
        nc22 = next(item for item in negative["results"] if item["id"] == "B4NC22_NULL_PHYSICAL_INPUT_ZERO_FILLED")
        mutations_real = all(item["nominal_sha256"] != item["mutant_sha256"] and item["nominal_gate_output_sha256"] != item["mutant_gate_output_sha256"] and item["expected_failed_check"] in item["actual_failed_checks"] and item["affected_path_hit"] and item["killed"] and item["mutation_level"] in ("REAL_RAW_ARTIFACT_OR_EXECUTED_PATH", "EVERY_INDIVIDUAL_RAW_GOVERNANCE_FIELD") for item in negative["results"])
        add("B4EA34_NEGATIVE_MUTANTS_HASH_AND_GATE", mutations_real and nc21["subvariant_count"] == 8 and nc22["subvariant_count"] == 7 and all(item["killed"] for item in nc21["subvariants"] + nc22["subvariants"]), {"real_raw": mutations_real, "nc21": nc21["subvariant_count"], "nc22": nc22["subvariant_count"]})
        governance = read_json(PHASE_ROOT / "contracts" / "PHASE_B4E_GOVERNANCE_V1.json")
        runtime = read_json(EVIDENCE / "SIM13_V4B4E_RUNTIME_ENVIRONMENT_V1.json")
        memory_clean = runtime["memory_gate_applicable"] is False and runtime["memory_gate_passed"] is False and runtime["owner_override_used"] is False and runtime["unified_r2_generator_invoked"] is False and runtime["cad_or_com_write_invoked"] is False
        add("B4EA35_GOVERNANCE_AND_FORMAL_HOLDS", not any(governance["required_false"].values()) and governance["formal_sim13_v2_state_unchanged"] == {"passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"]} and memory_clean, {"formal": governance["formal_sim13_v2_state_unchanged"], "memory_clean": memory_clean})
        source_now = [(item["path"], item["bytes"], item["sha256"]) for item in source_manifest["sources"] if (root / item["path"]).is_file() and (root / item["path"]).stat().st_size == item["bytes"] and sha256(root / item["path"]) == item["sha256"]]
        evidence_now = [(item["path"], item["bytes"], item["sha256"]) for item in evidence_manifest["files"] if (PHASE_ROOT / item["path"]).is_file() and (PHASE_ROOT / item["path"]).stat().st_size == item["bytes"] and sha256(PHASE_ROOT / item["path"]) == item["sha256"]]
        add("B4EA36_TOCTOU_SOURCE_EVIDENCE_STABLE", source_now == source_snapshot and evidence_now == evidence_snapshot, {"sources": len(source_now), "evidence": len(evidence_now)})
    except Exception as error:
        add("B4EA_FATAL", False, f"{type(error).__name__}:{error}")

    passed = sum(item["passed"] for item in checks)
    if len(checks) != 36 or passed != 36:
        clean_final()
        failure = {"schema": "SIM13_V4B4E_INDEPENDENT_AUDIT_FAILURE_V1", "observed_checks": len(checks), "passed_checks": passed, "checks": checks}
        print(json.dumps(failure, indent=2, ensure_ascii=False))
        return 3

    receipt_payload = {
        "schema": "SIM13_V4B4E_INDEPENDENT_AUDIT_RECEIPT_V1",
        "status": "PASS",
        "audit_independence": "NO_IMPORT_OF_B4E_SOLVER_VALIDATOR_TESTS_OR_SHARED_HELPER",
        "expected_checks": 36, "observed_checks": 36, "passed_checks": 36,
        "pre_audit_gate": record(PRE_AUDIT, "PRE_AUDIT_GATE"),
        "evidence_manifest": record(EVIDENCE_MANIFEST, "EVIDENCE_DAG"),
        "checks": checks,
    }
    write_json(RECEIPT, receipt_payload)
    final_payload = {
        "schema": "SIM13_V4B4E_AUDITED_GATE_V1",
        "status": "PASS_PHASE_B4E_SOLVER_AUDIT__SYNTHETIC_ACQUISITION_ACTIVE_AND_ALGORITHM_ONLY_NONTRIGGER_HYBRID_BRANCH_VERIFIED__PRIMARY_BRANCH_HORIZON_EXHAUSTED_INCONCLUSIVE__NO_MAIN_REMOVAL__ALL_PHYSICAL_CURRENT_FORMAL_HOLDS",
        "final": True,
        "scope": "POST_FREEZE_SYNTHETIC_6DOF_CONSTRAINT_SOLVER_DIAGNOSTIC_ONLY",
        "pre_audit_gate": record(PRE_AUDIT, "PRE_AUDIT_GATE"),
        "independent_audit_receipt": record(RECEIPT, "INDEPENDENT_AUDIT_36_OF_36"),
        "evidence_manifest": record(EVIDENCE_MANIFEST, "EVIDENCE_DAG"),
        "capability_state": {
            "b4_contract_recursively_verified": True,
            "b4_acquisition_and_active_solver_implemented": True,
            "b4_clearance_eligibility_certifier_implemented": True,
            "b4_hybrid_removal_and_post_release_solver_implemented": True,
            "b4_solver_audited": True,
            "synthetic_acquisition_executed": True,
            "synthetic_active_constraint_propagated": True,
            "cross_integrator_checked": True,
            "solver_negative_controls_22_real_raw_mutations_killed": True,
            "algorithm_only_hybrid_removal_fixture_passed": True,
            "synthetic_removal_executed": False,
        },
        "nominal_branch": {
            "status": "DIAGNOSTIC_INCONCLUSIVE_HORIZON_EXHAUSTED_NO_REMOVAL_OBSERVED",
            "search_end_time_s": 0.08,
            "left_gap_at_end_m": float(primary_trace["left_gap_m"][-1]),
            "right_gap_at_end_m": float(primary_trace["right_gap_m"][-1]),
            "global_empty_eligibility_set_claimed": False,
            "removal_or_release_capability_pass": False,
        },
        "required_false": governance["required_false"],
        "required_null_physical_inputs": {name: None for name in governance["required_null_physical_inputs"]},
        "formal_sim13_v2_state_unchanged": governance["formal_sim13_v2_state_unchanged"],
        "mechanical_ruling": "the hash-bound B3 trigger branch verifies the ideal synthetic 6D acquisition projection and bounded active reduced dynamics but reaches no removal event; separately, an explicit algorithm-only nontrigger branch-coverage fixture verifies the finite-event orchestration and independent 5 ms post-release algorithm without B3-trigger, main-trajectory, physical, current-system or formal credit; the B3-derived branch closes fingers further and does not reach the preregistered clearance dwell by 0.08 s, so physical retention, lock, held capture, release, current-system binding and NC19 remain HOLD",
        "next_action": "change the synthetic finger command or add a separately preregistered active search/reachability study; do not extend the horizon after observing the result and do not alias the snapshot transform to a physical lock transform",
    }
    write_json(FINAL_GATE, final_payload)
    terminal_payload = {
        "schema": "SIM13_V4B4E_TERMINAL_SELF_EXCLUDED_MANIFEST_V1",
        "self_excluded": True,
        "entries": [
            record(PRE_AUDIT, "PRE_AUDIT_GATE"), record(EVIDENCE_MANIFEST, "EVIDENCE_DAG"),
            record(RECEIPT, "INDEPENDENT_AUDIT_RECEIPT"), record(FINAL_GATE, "AUDITED_FINAL_GATE"),
        ],
    }
    write_json(TERMINAL, terminal_payload)

    # Fresh recursive readback after signing.  Any discrepancy invalidates all
    # final artifacts, including a stale PASS from an earlier attempt.
    try:
        terminal_read = read_json(TERMINAL)
        for item in terminal_read["entries"]:
            path = PHASE_ROOT / item["path"]
            if path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"]:
                raise RuntimeError(f"TERMINAL_READBACK_DRIFT:{item['path']}")
        final_read = read_json(FINAL_GATE)
        if final_read != final_payload or read_json(RECEIPT) != receipt_payload:
            raise RuntimeError("SIGNED_PAYLOAD_READBACK_MISMATCH")
        if not verify_manifest_entries(source_manifest, root=root, key="sources"):
            raise RuntimeError("POST_SIGN_SOURCE_MANIFEST_DRIFT")
        if not verify_manifest_entries(evidence_manifest, root=PHASE_ROOT, key="files"):
            raise RuntimeError("POST_SIGN_EVIDENCE_MANIFEST_DRIFT")
    except Exception:
        clean_final()
        raise
    print(json.dumps(final_payload, indent=2, ensure_ascii=False))
    return 0


def _rotation_to_quaternion_independent(rotation: np.ndarray) -> np.ndarray:
    # Independent audit converter, wxyz output.
    r = np.asarray(rotation, dtype=float); trace = float(np.trace(r))
    if trace > 0.0:
        s = math.sqrt(trace + 1.0) * 2.0
        q = np.array((0.25 * s, (r[2, 1] - r[1, 2]) / s, (r[0, 2] - r[2, 0]) / s, (r[1, 0] - r[0, 1]) / s))
    else:
        index = int(np.argmax(np.diag(r)))
        if index == 0:
            s = math.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2]) * 2.0
            q = np.array(((r[2, 1] - r[1, 2]) / s, 0.25 * s, (r[0, 1] + r[1, 0]) / s, (r[0, 2] + r[2, 0]) / s))
        elif index == 1:
            s = math.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2]) * 2.0
            q = np.array(((r[0, 2] - r[2, 0]) / s, (r[0, 1] + r[1, 0]) / s, 0.25 * s, (r[1, 2] + r[2, 1]) / s))
        else:
            s = math.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1]) * 2.0
            q = np.array(((r[1, 0] - r[0, 1]) / s, (r[0, 2] + r[2, 0]) / s, (r[1, 2] + r[2, 1]) / s, 0.25 * s))
    q = normalize_quaternion(q)
    return -q if q[0] < 0.0 else q


if __name__ == "__main__":
    raise SystemExit(main())
