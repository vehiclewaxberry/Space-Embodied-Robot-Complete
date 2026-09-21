"""Synthetic 6-DOF constraint acquisition, propagation, and removal diagnostics.

The implementation follows the hash-bound B4 contract.  It intentionally
keeps linear and angular channels separate at every public boundary.  The
synthetic constraint is an ideal model mechanism; it is not a physical latch.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Callable, Iterable, Sequence

import numpy as np
from scipy import linalg as scipy_linalg


HERE = Path(__file__).resolve().parent
PHASE_ROOT = HERE.parent
DIAGNOSTIC_ROOT = PHASE_ROOT.parent
B3_ROOT = DIAGNOSTIC_ROOT / "phase_b3_branched_dual_contact_soft_capture"
B1_ROOT = DIAGNOSTIC_ROOT / "phase_b1_frictionless_single_contact"
for candidate in (DIAGNOSTIC_ROOT, B3_ROOT, B1_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from b3_contact.branched_model import BranchedGripperServiceModel  # noqa: E402
from b3_contact.dual_contact_kernel import (  # noqa: E402
    DualContactConfig,
    DualContactHistory,
    deterministic_dual_contact_scenario,
    evaluate_dual_contact,
    integrate_dual_contact,
)
from sim13_v4a.full_floating import (  # noqa: E402
    BodyKinematics,
    ChainKinematics,
    ServiceState,
    TargetState,
    TARGET_INERTIA_BODY_KG_M2,
    TARGET_MASS_KG,
    normalize_quaternion,
    quat_from_rotvec,
    quat_product,
    quat_to_rotation,
    quaternion_geodesic,
    skew,
    target_momentum_energy,
    validate_target_state,
)


SCOPE = "POST_FREEZE_SYNTHETIC_6DOF_CONSTRAINT_SOLVER_DIAGNOSTIC"
PHYSICAL_6D_CONTACT_CLOSURE = False
PHYSICAL_LOCK_IMPLEMENTED = False
PHYSICAL_RELEASE_IMPLEMENTED = False
HELD_CAPTURE_PASSED = False
GRASP_SUCCESS_CLAIMED = False
TARGET_ATTACHED_CLAIMED = False
CURRENT_SYSTEM_BOUND = False
FORMAL_NC19_CREDIT = False
OWNER_AUTHORIZED = False
PRODUCTION_READY = False
RELEASE_AUTHORIZED = False
NEXT_STAGE_AUTHORIZED = False

SV_REL_TOL = 1.0e-10
JHAT_LHAT_TOL = 1.0e-11
GAP_CLEARANCE_M = 1.0e-6
GAP_RATE_REENTRY_TOL_M_S = 1.0e-6
MINIMUM_ACTIVE_DWELL_S = 1.0e-3
CLEARANCE_DWELL_S = 1.0e-3
ACTIVE_END_TIME_S = 0.08
DIFFERENCE_STEP_S = 2.0e-6
POST_RELEASE_OBSERVATION_S = 5.0e-3

# Root finding operates on a normalized coefficient vector, so these two
# tolerances are dimensionless.  Gap and gap-rate classification remain in
# their native SI channels and are deliberately fail-closed at the threshold.
ROOT_COEFFICIENT_RELATIVE_TRIM = 1.0e-14
ROOT_IMAGINARY_TOLERANCE = 1.0e-10
ROOT_DOMAIN_TOLERANCE = 1.0e-12
GAP_CLASSIFICATION_MARGIN_M = 0.0
GAP_RATE_CLASSIFICATION_MARGIN_M_S = 0.0
TIME_INTERVAL_MERGE_TOLERANCE_S = 1.0e-12


class SolverError(RuntimeError):
    """Fail-closed solver or evidence error."""


@dataclass(frozen=True)
class SnapshotTransform:
    translation_palm_to_target_m: np.ndarray
    rotation_palm_to_target: np.ndarray
    acquisition_time_s: float


@dataclass(frozen=True)
class EventInput:
    run_id: str
    method: str
    step_s: float
    index: int
    time_s: float
    service: ServiceState
    target: TargetState
    left_common_contact_point_m: np.ndarray
    right_common_contact_point_m: np.ndarray
    left_contact_potential_j: float
    right_contact_potential_j: float
    b3_dissipation_j: float
    state_label: str
    criteria: dict[str, Any]
    source: str


@dataclass(frozen=True)
class AcquisitionResult:
    run_id: str
    acquisition_time_s: float
    snapshot: SnapshotTransform
    reference_length_m: float
    z_minus: np.ndarray
    z_plus_reduced: np.ndarray
    z_plus_kkt: np.ndarray
    z_plus_schur_audit: np.ndarray
    eta_plus: np.ndarray
    linear_impulse_n_s: np.ndarray
    angular_impulse_n_m_s: np.ndarray
    lambda_bar: np.ndarray
    matrices: dict[str, np.ndarray]
    ranks: dict[str, int]
    metrics: dict[str, float]
    wrench_audit: dict[str, Any]
    energy_audit: dict[str, float]
    momentum_audit: dict[str, Any]
    backend_provenance: dict[str, str]


@dataclass(frozen=True)
class ActiveRunResult:
    run_id: str
    method: str
    step_s: float
    acquisition: AcquisitionResult
    time_s: np.ndarray
    service_position_m: np.ndarray
    service_quaternion_wxyz: np.ndarray
    service_joint_coordinates_mixed: np.ndarray
    eta_mixed: np.ndarray
    target_position_m: np.ndarray
    target_quaternion_wxyz: np.ndarray
    target_twist_mixed: np.ndarray
    left_gap_m: np.ndarray
    right_gap_m: np.ndarray
    left_gap_rate_m_s: np.ndarray
    right_gap_rate_m_s: np.ndarray
    sample_ledgers: dict[str, np.ndarray]
    maxima: dict[str, float]
    clearance: dict[str, Any]
    terminal_status: str
    synthetic_removal_executed: bool
    post_release: dict[str, Any] | None


def _project_root() -> Path:
    for parent in (PHASE_ROOT, *PHASE_ROOT.parents):
        if (parent / "PROJECT_MAP.md").is_file() and (parent / "30_simulation").is_dir():
            return parent
    raise SolverError("PROJECT_ROOT_NOT_FOUND")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SolverError(f"JSON_READ_FAILED:{path}:{type(error).__name__}") from error
    if not isinstance(value, dict):
        raise SolverError(f"JSON_ROOT_NOT_OBJECT:{path}")
    return value


def _json_sha(value: Any) -> str:
    def canonical(item: Any) -> Any:
        if isinstance(item, np.ndarray):
            return item.tolist()
        if isinstance(item, np.generic):
            return item.item()
        if isinstance(item, bytes):
            return {"bytes": len(item), "sha256": hashlib.sha256(item).hexdigest().upper()}
        if isinstance(item, dict):
            return {str(key): canonical(value) for key, value in item.items()}
        if isinstance(item, (list, tuple)):
            return [canonical(value) for value in item]
        return item

    encoded = json.dumps(canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def verify_bound_sources(project_root: Path | None = None) -> list[dict[str, Any]]:
    """Verify every direct binding plus the complete transitive B4 binding list."""

    root = project_root or _project_root()
    binding_path = PHASE_ROOT / "contracts" / "PHASE_B4E_SOURCE_BINDINGS_V1.json"
    binding = _read_json(binding_path)
    verified: list[dict[str, Any]] = []
    for item in binding.get("sources", []):
        path = root / str(item["path"])
        if not path.is_file():
            raise SolverError(f"BOUND_SOURCE_MISSING:{item['id']}")
        size = path.stat().st_size
        digest = _sha256(path)
        if size != int(item["bytes"]) or digest != str(item["sha256"]).upper():
            raise SolverError(f"BOUND_SOURCE_DRIFT:{item['id']}")
        verified.append({"id": item["id"], "path": item["path"], "bytes": size, "sha256": digest, "role": item["role"]})

    b4_binding_item = next(item for item in binding["sources"] if item["id"] == "b4_source_contract")
    b4_binding = _read_json(root / b4_binding_item["path"])
    for item in b4_binding.get("sources", []):
        path = root / str(item["path"])
        if not path.is_file() or path.stat().st_size != int(item["bytes"]) or _sha256(path) != str(item["sha256"]).upper():
            raise SolverError(f"TRANSITIVE_B4_SOURCE_DRIFT:{item['id']}")
    return verified


def _vector(value: Sequence[float], size: int, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.shape != (size,) or not np.all(np.isfinite(array)):
        raise SolverError(f"INVALID_{name.upper().replace(' ', '_')}")
    return array.copy()


def _service_from_record(record: dict[str, Any]) -> ServiceState:
    service = record["service"]
    return ServiceState(
        _vector(service["base_position_inertial_m"], 3, "service position"),
        normalize_quaternion(_vector(service["base_quaternion_body_to_inertial_wxyz"], 4, "service quaternion"), strict_unit=True),
        _vector(service["joint_coordinates_mixed"], 8, "service q"),
        _vector(service["nu_s_mixed"], 14, "service nu"),
    )


def _target_from_record(record: dict[str, Any]) -> TargetState:
    target = record["target"]
    return validate_target_state(TargetState(
        _vector(target["position_inertial_m"], 3, "target position"),
        normalize_quaternion(_vector(target["quaternion_body_to_inertial_wxyz"], 4, "target quaternion"), strict_unit=True),
        _vector(target["twist_inertial_mixed"], 6, "target twist"),
    ))


def _first_qualifying_reference_record(trace: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    records = trace.get("reference_records")
    if not isinstance(records, list) or not records:
        raise SolverError("B3_REFERENCE_RECORDS_MISSING")
    for index, record in enumerate(records):
        if record.get("state_label") in ("ABORTED_SAFE", "DIAGNOSTIC_FAIL_CLOSED"):
            raise SolverError(f"B3_ABORT_BEFORE_TRIGGER:{index}")
        criteria = record.get("soft_capture_criteria", {})
        if criteria.get("soft_capture_transient_qualifies") is True and criteria.get("all_ledgers_closed") is True:
            return index, record
    raise SolverError("B3_FIRST_QUALIFYING_RECORD_NOT_FOUND")


def extract_frozen_primary_event(project_root: Path | None = None) -> EventInput:
    root = project_root or _project_root()
    verify_bound_sources(root)
    trace = _read_json(root / "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b3_branched_dual_contact_soft_capture/evidence/SIM13_V4B3_DUAL_CONTACT_TRACE_V1.json")
    index, record = _first_qualifying_reference_record(trace)
    if index != 205 or float(record["time_s"]) != 0.051250000000000004:
        raise SolverError("B3_FROZEN_TRIGGER_ANCHOR_MISMATCH")
    contacts = record["contacts"]
    b3_dissipation = 0.0
    for side in ("left", "right"):
        integrated = contacts[side]["integrated"]
        b3_dissipation += float(integrated["normal_dissipation_j"]) + float(integrated["friction_dissipation_j"])
    return EventInput(
        "rk4_reference", "rk4", 0.00025, index, float(record["time_s"]),
        _service_from_record(record), _target_from_record(record),
        _vector(contacts["left"]["common_contact_point_inertial_m"], 3, "left contact point"),
        _vector(contacts["right"]["common_contact_point_inertial_m"], 3, "right contact point"),
        float(contacts["left"]["elastic_energy_j"]), float(contacts["right"]["elastic_energy_j"]),
        b3_dissipation, str(record["state_label"]), deepcopy(record["soft_capture_criteria"]),
        "HASH_BOUND_B3_REFERENCE_RECORD_205",
    )


def _event_from_history(run_id: str, history: DualContactHistory) -> EventInput:
    if history.aborted_safe:
        raise SolverError(f"B3_RERUN_ABORTED:{run_id}:{'|'.join(history.abort_reasons)}")
    qualifying = [
        item for item in history.soft_capture_criteria_log
        if item.get("soft_capture_transient_qualifies") is True and item.get("all_ledgers_closed") is True
    ]
    if not qualifying:
        raise SolverError(f"B3_RERUN_NO_TRIGGER:{run_id}")
    criteria = qualifying[0]
    index = int(criteria["index"])
    if any(
        item.get("soft_capture_transient_qualifies") is True and int(item["index"]) < index
        for item in history.soft_capture_criteria_log
    ):
        raise SolverError(f"B3_RERUN_TRIGGER_NOT_FIRST:{run_id}")
    service = ServiceState(
        history.service_base_position_inertial_m[index].copy(),
        history.service_base_quaternion_body_to_inertial_wxyz[index].copy(),
        history.service_joint_coordinates_mixed[index].copy(),
        history.service_nu_s_mixed[index].copy(),
    )
    target = TargetState(
        history.target_position_inertial_m[index].copy(),
        history.target_quaternion_body_to_inertial_wxyz[index].copy(),
        history.target_twist_inertial_mixed[index].copy(),
    )
    b3_dissipation = float(
        history.left.cumulative_normal_dissipation_j[index]
        + history.left.cumulative_friction_dissipation_j[index]
        + history.right.cumulative_normal_dissipation_j[index]
        + history.right.cumulative_friction_dissipation_j[index]
    )
    return EventInput(
        run_id, history.method, float(history.step_s), index, float(history.time_s[index]),
        service, target,
        history.left.common_contact_point_inertial_m[index].copy(),
        history.right.common_contact_point_inertial_m[index].copy(),
        float(history.left.elastic_energy_j[index]), float(history.right.elastic_energy_j[index]),
        b3_dissipation, str(history.state_label[index]), deepcopy(criteria),
        "INDEPENDENT_B3_RERUN_FIRST_QUALIFYING_SAMPLE",
    )


def rerun_b3_to_event(run_id: str, method: str, step_s: float) -> EventInput:
    model, service, target, config = deterministic_dual_contact_scenario()
    history = integrate_dual_contact(
        model, service, target, config, step_s=step_s, duration_s=ACTIVE_END_TIME_S,
        method=method, contact_enabled=True, require_soft_capture=True,
    )
    return _event_from_history(run_id, history)


def _canonical_quaternion(quaternion: Sequence[float], tolerance: float = 1.0e-15) -> np.ndarray:
    q = normalize_quaternion(quaternion)
    if q[0] < -tolerance:
        q = -q
    elif abs(q[0]) <= tolerance:
        for component in q[1:]:
            if abs(component) > tolerance:
                if component < 0.0:
                    q = -q
                break
    return q


def _rotation_to_quaternion(rotation: np.ndarray) -> np.ndarray:
    r = np.asarray(rotation, dtype=float)
    if r.shape != (3, 3) or not np.all(np.isfinite(r)):
        raise SolverError("INVALID_ROTATION_MATRIX")
    trace = float(np.trace(r))
    if trace > 0.0:
        scale = math.sqrt(trace + 1.0) * 2.0
        q = np.array((0.25 * scale, (r[2, 1] - r[1, 2]) / scale, (r[0, 2] - r[2, 0]) / scale, (r[1, 0] - r[0, 1]) / scale))
    else:
        index = int(np.argmax(np.diag(r)))
        if index == 0:
            scale = math.sqrt(max(1.0 + r[0, 0] - r[1, 1] - r[2, 2], 0.0)) * 2.0
            q = np.array(((r[2, 1] - r[1, 2]) / scale, 0.25 * scale, (r[0, 1] + r[1, 0]) / scale, (r[0, 2] + r[2, 0]) / scale))
        elif index == 1:
            scale = math.sqrt(max(1.0 + r[1, 1] - r[0, 0] - r[2, 2], 0.0)) * 2.0
            q = np.array(((r[0, 2] - r[2, 0]) / scale, (r[0, 1] + r[1, 0]) / scale, 0.25 * scale, (r[1, 2] + r[2, 1]) / scale))
        else:
            scale = math.sqrt(max(1.0 + r[2, 2] - r[0, 0] - r[1, 1], 0.0)) * 2.0
            q = np.array(((r[1, 0] - r[0, 1]) / scale, (r[0, 2] + r[2, 0]) / scale, (r[1, 2] + r[2, 1]) / scale, 0.25 * scale))
    return _canonical_quaternion(q)


def _rotation_angle(rotation: np.ndarray) -> float:
    cosine = max(-1.0, min(1.0, 0.5 * (float(np.trace(rotation)) - 1.0)))
    return float(math.acos(cosine))


def build_snapshot(model: BranchedGripperServiceModel, event: EventInput) -> SnapshotTransform:
    service = model.validate_service_state(event.service)
    target = validate_target_state(event.target)
    palm, palm_rotation, _, _ = model.palm_frame_and_jacobians(service)
    target_rotation = quat_to_rotation(target.quaternion_body_to_inertial_wxyz)
    d_star = palm_rotation.T @ (target.position_inertial_m - palm)
    r_star = palm_rotation.T @ target_rotation
    orthogonality = float(np.linalg.norm(r_star.T @ r_star - np.eye(3), ord=np.inf))
    determinant_error = abs(float(np.linalg.det(r_star)) - 1.0)
    if orthogonality > 1.0e-12 or determinant_error > 1.0e-12 or np.linalg.det(r_star) <= 0.0:
        raise SolverError("SNAPSHOT_ROTATION_INVALID")
    if math.pi - _rotation_angle(r_star) <= 1.0e-8:
        raise SolverError("SNAPSHOT_SO3_PI_BRANCH_AMBIGUITY")
    return SnapshotTransform(d_star, r_star, event.time_s)


def target_from_snapshot(
    model: BranchedGripperServiceModel,
    service: ServiceState,
    snapshot: SnapshotTransform,
    velocity: np.ndarray | None = None,
) -> tuple[TargetState, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    service = model.validate_service_state(service)
    eta = service.nu_s_mixed if velocity is None else _vector(velocity, 14, "eta")
    palm, palm_rotation, palm_jv, palm_jw = model.palm_frame_and_jacobians(service)
    offset = palm_rotation @ snapshot.translation_palm_to_target_m
    target_position = palm + offset
    target_rotation = palm_rotation @ snapshot.rotation_palm_to_target
    a_v = palm_jv - skew(offset) @ palm_jw
    a = np.vstack((a_v, palm_jw))
    target = TargetState(target_position, _rotation_to_quaternion(target_rotation), a @ eta)
    return target, a, palm, palm_rotation, offset


class AttachedTargetModel(BranchedGripperServiceModel):
    """Independent fixed-child reconstruction used only as an audit path."""

    def __init__(self, snapshot: SnapshotTransform) -> None:
        super().__init__()
        self.snapshot = snapshot

    def kinematics(self, state: ServiceState) -> ChainKinematics:
        state = self.validate_service_state(state)
        service_frames = super().kinematics(state)
        target, a, _, _, _ = target_from_snapshot(self, state, self.snapshot)
        rotation = quat_to_rotation(target.quaternion_body_to_inertial_wxyz)
        target_body = BodyKinematics(
            "synthetic_target_fixed_child",
            TARGET_MASS_KG,
            rotation @ TARGET_INERTIA_BODY_KG_M2 @ rotation.T,
            target.position_inertial_m,
            rotation,
            a[:3].copy(),
            a[3:].copy(),
        )
        return ChainKinematics(
            tuple((*service_frames.bodies, target_body)),
            service_frames.joint_origins_inertial_m,
            service_frames.joint_axes_inertial,
            service_frames.link_origins_inertial_m,
            service_frames.link_rotations_body_to_inertial,
        )


def _target_spatial_mass(target: TargetState) -> np.ndarray:
    rotation = quat_to_rotation(target.quaternion_body_to_inertial_wxyz)
    inertia = rotation @ TARGET_INERTIA_BODY_KG_M2 @ rotation.T
    matrix = np.zeros((6, 6))
    matrix[:3, :3] = TARGET_MASS_KG * np.eye(3)
    matrix[3:, 3:] = inertia
    return matrix


def _target_bias(target: TargetState) -> np.ndarray:
    mass = _target_spatial_mass(target)
    omega = target.twist_inertial_mixed[3:]
    return np.concatenate((np.zeros(3), np.cross(omega, mass[3:, 3:] @ omega)))


def _cholesky_solve(matrix: np.ndarray, rhs: np.ndarray) -> np.ndarray:
    try:
        factor = np.linalg.cholesky(0.5 * (matrix + matrix.T))
        return scipy_linalg.solve_triangular(factor.T, scipy_linalg.solve_triangular(factor, rhs, lower=True), lower=False)
    except (np.linalg.LinAlgError, ValueError) as error:
        raise SolverError("SPD_CHOLESKY_SOLVE_FAILED") from error


def _rank(matrix: np.ndarray, relative_tolerance: float = SV_REL_TOL) -> int:
    singular = np.linalg.svd(matrix, compute_uv=False)
    if len(singular) == 0 or not np.all(np.isfinite(singular)) or singular[0] <= 0.0:
        return 0
    return int(np.count_nonzero(singular > relative_tolerance * singular[0]))


def _block_diagonal(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    result = np.zeros((left.shape[0] + right.shape[0], left.shape[1] + right.shape[1]))
    result[: left.shape[0], : left.shape[1]] = left
    result[left.shape[0] :, left.shape[1] :] = right
    return result


def _channel_maximum(vector: np.ndarray, indices: slice | Sequence[int]) -> float:
    return float(np.max(np.abs(vector[indices])))


def acquisition_projection(
    model: BranchedGripperServiceModel,
    event: EventInput,
    *,
    allow_algorithm_only_nontrigger_fixture: bool = False,
) -> AcquisitionResult:
    main_trigger = bool(
        event.state_label == "SOFT_CAPTURE_TRANSIENT_CANDIDATE"
        and event.criteria.get("all_ledgers_closed")
        and event.criteria.get("soft_capture_transient_qualifies")
    )
    fixture_trigger = bool(
        allow_algorithm_only_nontrigger_fixture
        and event.state_label == "ALGORITHM_ONLY_NONTRIGGER_INITIAL_STATE_FIXTURE"
        and event.criteria.get("algorithm_only_nontrigger_fixture") is True
        and event.criteria.get("physical_or_main_trigger_credit") is False
        and event.criteria.get("soft_capture_transient_qualifies") is False
    )
    if not (main_trigger or fixture_trigger):
        raise SolverError("ACQUISITION_TRIGGER_CONTRACT_NOT_SATISFIED")
    snapshot = build_snapshot(model, event)
    target_attached_minus, a, palm, palm_rotation, offset = target_from_snapshot(model, event.service, snapshot)
    snapshot_translation_error = float(np.linalg.norm(target_attached_minus.position_inertial_m - event.target.position_inertial_m))
    snapshot_rotation_error = quaternion_geodesic(target_attached_minus.quaternion_body_to_inertial_wxyz, event.target.quaternion_body_to_inertial_wxyz)
    if snapshot_translation_error > 1.0e-12 or snapshot_rotation_error > 1.0e-12:
        raise SolverError("SNAPSHOT_IDENTITY_RESIDUAL")

    chord = event.right_common_contact_point_m - event.left_common_contact_point_m
    chord_norm = float(np.linalg.norm(chord))
    reference_length = 0.5 * chord_norm
    if not math.isfinite(reference_length) or reference_length < 1.0e-3:
        raise SolverError("REFERENCE_LENGTH_INVALID")

    m_service = model.mass_matrix(event.service)
    m_target = _target_spatial_mass(event.target)
    m_minus = _block_diagonal(m_service, m_target)
    identity14 = np.eye(14)
    embedding = np.vstack((identity14, a))
    jc = np.hstack((-a, np.eye(6)))
    d = np.diag(np.concatenate((np.ones(3), reference_length * np.ones(3))))
    jbar = d @ jc
    s_eta = np.diag(np.concatenate((np.ones(3), reference_length * np.ones(3), reference_length * np.ones(6), np.ones(2))))
    s_z = _block_diagonal(s_eta, np.diag(np.concatenate((np.ones(3), reference_length * np.ones(3)))))
    l_hat = scipy_linalg.solve(s_eta.T, (s_z @ embedding).T, assume_a="gen").T
    j_hat = scipy_linalg.solve(s_z.T, (d @ jc).T, assume_a="gen").T
    ranks = {"L_hat": _rank(l_hat), "J_hat": _rank(j_hat)}
    if ranks != {"L_hat": 14, "J_hat": 6}:
        raise SolverError("SCALED_CONSTRAINT_RANK_FAILURE")
    jhat_lhat = float(np.linalg.norm(j_hat @ l_hat, ord=np.inf))
    if jhat_lhat > JHAT_LHAT_TOL:
        raise SolverError("SCALED_JL_IDENTITY_FAILURE")

    z_minus = np.concatenate((event.service.nu_s_mixed, event.target.twist_inertial_mixed))
    m_attached = embedding.T @ m_minus @ embedding
    eta_plus = _cholesky_solve(m_attached, embedding.T @ m_minus @ z_minus)
    z_plus_reduced = embedding @ eta_plus

    kkt_symmetric = np.block([[m_minus, -jbar.T], [-jbar, np.zeros((6, 6))]])
    rhs = np.concatenate((m_minus @ z_minus, np.zeros(6)))
    try:
        kkt_solution = scipy_linalg.solve(kkt_symmetric, rhs, assume_a="sym")
    except (np.linalg.LinAlgError, ValueError) as error:
        raise SolverError("PIVOTED_SYMMETRIC_KKT_SOLVE_FAILED") from error
    z_plus_kkt = kkt_solution[:20]
    lambda_bar_kkt = kkt_solution[20:]

    wbar = jbar @ _cholesky_solve(m_minus, jbar.T)
    wbar_symmetric = 0.5 * (wbar + wbar.T)
    eigenvalues = np.linalg.eigvalsh(wbar_symmetric)
    if eigenvalues[0] <= 0.0:
        raise SolverError("SCALED_EFFECTIVE_MASS_NOT_SPD")
    wbar_condition = float(eigenvalues[-1] / eigenvalues[0])
    if wbar_condition > 1.0e10:
        raise SolverError("SCALED_EFFECTIVE_MASS_CONDITION_EXCEEDED")
    gamma_minus = jbar @ z_minus
    lambda_bar_schur = -_cholesky_solve(wbar_symmetric, gamma_minus)
    z_plus_schur = z_minus + _cholesky_solve(m_minus, jbar.T @ lambda_bar_schur)
    physical_lambda = d.T @ lambda_bar_kkt
    linear_impulse = physical_lambda[:3]
    angular_impulse = physical_lambda[3:]

    component_difference = z_plus_reduced - z_plus_kkt
    kkt_original_residual = np.block([[m_minus, -jbar.T], [jbar, np.zeros((6, 6))]]) @ kkt_solution - rhs
    impulse_equation_residual = m_minus @ (z_plus_kkt - z_minus) - jbar.T @ lambda_bar_kkt
    native_constraint = jc @ z_plus_kkt
    scaled_constraint = jbar @ z_plus_kkt

    post_service = ServiceState(
        event.service.base_position_inertial_m.copy(), event.service.base_quaternion_body_to_inertial_wxyz.copy(),
        event.service.joint_coordinates_mixed.copy(), z_plus_kkt[:14].copy(),
    )
    post_target = TargetState(
        event.target.position_inertial_m.copy(), event.target.quaternion_body_to_inertial_wxyz.copy(), z_plus_kkt[14:].copy(),
    )
    pre_service_ledger = model.momentum_energy(event.service)
    pre_target_ledger = target_momentum_energy(event.target)
    post_service_ledger = model.momentum_energy(post_service)
    post_target_ledger = target_momentum_energy(post_target)
    service_dp = post_service_ledger.linear_momentum_n_s - pre_service_ledger.linear_momentum_n_s
    target_dp = post_target_ledger.linear_momentum_n_s - pre_target_ledger.linear_momentum_n_s
    service_dh = post_service_ledger.angular_momentum_about_inertial_origin_n_m_s - pre_service_ledger.angular_momentum_about_inertial_origin_n_m_s
    target_dh = post_target_ledger.angular_momentum_about_inertial_origin_n_m_s - pre_target_ledger.angular_momentum_about_inertial_origin_n_m_s
    expected_target_dh = np.cross(event.target.position_inertial_m, linear_impulse) + angular_impulse

    t_minus = pre_service_ledger.kinetic_energy_j + pre_target_ledger.kinetic_energy_j
    t_plus = post_service_ledger.kinetic_energy_j + post_target_ledger.kinetic_energy_j
    d_projection = t_minus - t_plus
    d_projection_schur = 0.5 * float(gamma_minus @ _cholesky_solve(wbar_symmetric, gamma_minus))
    u_left = float(event.left_contact_potential_j)
    u_right = float(event.right_contact_potential_j)
    u_total = u_left + u_right
    d_switch = d_projection + u_total

    chord_axis = chord / chord_norm
    r_left = event.left_common_contact_point_m - event.target.position_inertial_m
    ordinary_axis = float(chord_axis @ angular_impulse)
    chi_missing = float(chord_axis @ (angular_impulse - np.cross(r_left, linear_impulse)))
    grasp_map = np.block([[np.eye(3), np.eye(3)], [skew(r_left), skew(event.right_common_contact_point_m - event.target.position_inertial_m)]])
    gbar_scale = np.diag(np.concatenate((np.ones(3), np.ones(3) / reference_length)))
    gbar = gbar_scale @ grasp_map
    rank_gbar = _rank(gbar)
    if rank_gbar != 5:
        raise SolverError("B3_TWO_POINT_GRASP_MAP_RANK_NOT_FIVE")
    lambda_normalized = np.concatenate((linear_impulse, angular_impulse / reference_length))
    # This pseudoinverse is strictly isolated to the contract-whitelisted rank-5
    # unreachable-wrench audit.  It never enters the acquisition solve.
    unreachable = (np.eye(6) - gbar @ np.linalg.pinv(gbar, rcond=SV_REL_TOL)) @ lambda_normalized
    ranks["G_bar"] = rank_gbar

    fixed_child = AttachedTargetModel(snapshot)
    fixed_mass = fixed_child.mass_matrix(post_service)
    metrics = {
        "snapshot_translation_identity_m": snapshot_translation_error,
        "snapshot_rotation_geodesic_rad": snapshot_rotation_error,
        "rotation_orthogonality_inf": float(np.linalg.norm(snapshot.rotation_palm_to_target.T @ snapshot.rotation_palm_to_target - np.eye(3), ord=np.inf)),
        "rotation_determinant_error_abs": abs(float(np.linalg.det(snapshot.rotation_palm_to_target)) - 1.0),
        "quaternion_unit_norm_error_abs": abs(float(np.linalg.norm(post_target.quaternion_body_to_inertial_wxyz)) - 1.0),
        "Jhat_Lhat_operator_inf_dimensionless": jhat_lhat,
        "W_bar_scaled_min_eigenvalue": float(eigenvalues[0]),
        "W_bar_scaled_condition_number": wbar_condition,
        "reduced_kkt_service_base_linear_component_m_s": _channel_maximum(component_difference, slice(0, 3)),
        "reduced_kkt_service_base_angular_component_rad_s": _channel_maximum(component_difference, slice(3, 6)),
        "reduced_kkt_R_joint_component_rad_s": _channel_maximum(component_difference, slice(6, 12)),
        "reduced_kkt_P_joint_component_m_s": _channel_maximum(component_difference, slice(12, 14)),
        "reduced_kkt_target_linear_component_m_s": _channel_maximum(component_difference, slice(14, 17)),
        "reduced_kkt_target_angular_component_rad_s": _channel_maximum(component_difference, slice(17, 20)),
        "post_constraint_linear_twist_m_s": _channel_maximum(native_constraint, slice(0, 3)),
        "post_constraint_angular_twist_rad_s": _channel_maximum(native_constraint, slice(3, 6)),
        "scaled_post_constraint_inf": float(np.max(np.abs(scaled_constraint))),
        "kkt_original_contract_residual_inf": float(np.max(np.abs(kkt_original_residual))),
        "combined_impulse_equation_service_base_linear_N_s": _channel_maximum(impulse_equation_residual, slice(0, 3)),
        "combined_impulse_equation_service_base_angular_N_m_s": _channel_maximum(impulse_equation_residual, slice(3, 6)),
        "combined_impulse_equation_R_joint_N_m_s": _channel_maximum(impulse_equation_residual, slice(6, 12)),
        "combined_impulse_equation_P_joint_N_s": _channel_maximum(impulse_equation_residual, slice(12, 14)),
        "combined_impulse_equation_target_linear_N_s": _channel_maximum(impulse_equation_residual, slice(14, 17)),
        "combined_impulse_equation_target_angular_N_m_s": _channel_maximum(impulse_equation_residual, slice(17, 20)),
        "total_linear_momentum_jump_N_s": float(np.linalg.norm(service_dp + target_dp)),
        "total_angular_momentum_jump_about_fixed_inertial_origin_N_m_s": float(np.linalg.norm(service_dh + target_dh)),
        "projection_energy_identity_J": abs(d_projection - d_projection_schur),
        "switch_energy_identity_J": abs((t_plus + event.b3_dissipation_j + d_switch) - (t_minus + u_total + event.b3_dissipation_j)),
        "contact_potential_sum_identity_J": abs(u_total - u_left - u_right),
        "attached_mass_fixed_child_inf": float(np.linalg.norm(fixed_mass - m_attached, ord=np.inf)),
        "schur_kkt_velocity_inf_audit_only": float(np.max(np.abs(z_plus_schur - z_plus_kkt))),
    }
    if d_projection < -1.0e-12:
        raise SolverError("NEGATIVE_ACQUISITION_DISSIPATION")

    return AcquisitionResult(
        event.run_id, event.time_s, snapshot, reference_length, z_minus, z_plus_reduced,
        z_plus_kkt, z_plus_schur, eta_plus, linear_impulse, angular_impulse,
        lambda_bar_kkt,
        {"M_minus": m_minus, "M_attached": m_attached, "A": a, "L": embedding, "J_c": jc, "D": d, "J_bar": jbar, "S_eta": s_eta, "S_z": s_z, "L_hat": l_hat, "J_hat": j_hat, "W_bar": wbar_symmetric, "G_bar": gbar},
        ranks, metrics,
        {
            "contact_chord_unit_vector": chord_axis.tolist(),
            "ordinary_axis_projected_angular_impulse_N_m_s": ordinary_axis,
            "rank5_unreachable_chi_missing_N_m_s": chi_missing,
            "normalized_rank5_unreachable_projection_N_s": unreachable.tolist(),
            "normalized_rank5_unreachable_projection_norm_N_s": float(np.linalg.norm(unreachable)),
            "transverse_angular_impulse_N_m_s": (angular_impulse - ordinary_axis * chord_axis).tolist(),
            "rank5_contact_capability_attributed": False,
            "synthetic_sixth_constraint_attributed": True,
        },
        {
            "T_minus_J": t_minus, "T_plus_J": t_plus,
            "D_projection_J": d_projection, "D_projection_schur_J": d_projection_schur,
            "U_left_minus_J": u_left, "U_right_minus_J": u_right, "U_contact_minus_J": u_total,
            "D_B3_minus_J": event.b3_dissipation_j, "D_switch_J": d_switch,
        },
        {
            "service_linear_momentum_jump_N_s": service_dp.tolist(),
            "target_linear_momentum_jump_N_s": target_dp.tolist(),
            "service_angular_momentum_jump_N_m_s": service_dh.tolist(),
            "target_angular_momentum_jump_N_m_s": target_dh.tolist(),
            "expected_target_linear_jump_N_s": linear_impulse.tolist(),
            "expected_target_angular_jump_N_m_s": expected_target_dh.tolist(),
            "service_equivalent_wrench_about_palm_origin": {
                "linear_impulse_N_s": (-linear_impulse).tolist(),
                "angular_impulse_N_m_s": (-(angular_impulse + np.cross(offset, linear_impulse))).tolist(),
                "r_cross_p_count": 1,
            },
        },
        {
            "reduced_spd": "numpy_cholesky_plus_triangular_solve",
            "direct_kkt": "scipy_symmetric_indefinite_pivoted_direct_solve",
            "schur_audit_only": "numpy_cholesky_plus_triangular_solve",
            "acquisition_pinv_or_lstsq": "FORBIDDEN_NOT_USED",
            "pinv_whitelist": "G_BAR_RANK5_UNREACHABLE_PROJECTION_AUDIT_ONLY",
        },
    )


def _service_to_active_vector(service: ServiceState) -> np.ndarray:
    return np.concatenate((service.base_position_inertial_m, service.base_quaternion_body_to_inertial_wxyz, service.joint_coordinates_mixed, service.nu_s_mixed))


def _service_from_active_vector(vector: np.ndarray) -> ServiceState:
    value = np.asarray(vector, dtype=float)
    if value.shape != (29,) or not np.all(np.isfinite(value)):
        raise SolverError("INVALID_ACTIVE_STATE_VECTOR")
    return ServiceState(value[:3].copy(), normalize_quaternion(value[3:7]), value[7:15].copy(), value[15:29].copy())


def _active_formula_terms(
    model: BranchedGripperServiceModel,
    service: ServiceState,
    snapshot: SnapshotTransform,
    difference_step_s: float = DIFFERENCE_STEP_S,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, TargetState, np.ndarray, np.ndarray]:
    target, a, _, _, _ = target_from_snapshot(model, service, snapshot)
    plus = model._shift_state_along_velocity(service, service.nu_s_mixed, difference_step_s)
    minus = model._shift_state_along_velocity(service, service.nu_s_mixed, -difference_step_s)
    _, a_plus, _, _, _ = target_from_snapshot(model, plus, snapshot)
    _, a_minus, _, _, _ = target_from_snapshot(model, minus, snapshot)
    adot_eta = ((a_plus - a_minus) / (2.0 * difference_step_s)) @ service.nu_s_mixed
    m_service = model.mass_matrix(service)
    h_service = model.bias_effort(service, difference_step_s=difference_step_s)
    m_target = _target_spatial_mass(target)
    h_target = _target_bias(target)
    m_attached = m_service + a.T @ m_target @ a
    h_attached = h_service + a.T @ (h_target + m_target @ adot_eta)
    return m_attached, h_attached, a, target, adot_eta, m_target


def _active_rhs(model: BranchedGripperServiceModel, snapshot: SnapshotTransform, vector: np.ndarray) -> np.ndarray:
    service = _service_from_active_vector(vector)
    mass, bias, _, _, _, _ = _active_formula_terms(model, service, snapshot)
    eta_dot = _cholesky_solve(mass, -bias)
    quaternion_rate = 0.5 * quat_product(np.array((0.0, *service.nu_s_mixed[3:6])), service.base_quaternion_body_to_inertial_wxyz)
    return np.concatenate((service.nu_s_mixed[:3], quaternion_rate, service.nu_s_mixed[6:], eta_dot))


def _rk4_step(rhs: Callable[[np.ndarray], np.ndarray], state: np.ndarray, step_s: float) -> np.ndarray:
    k1 = rhs(state)
    k2 = rhs(state + 0.5 * step_s * k1)
    k3 = rhs(state + 0.5 * step_s * k2)
    k4 = rhs(state + step_s * k3)
    return state + (step_s / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def _midpoint_step(rhs: Callable[[np.ndarray], np.ndarray], state: np.ndarray, step_s: float) -> np.ndarray:
    first = rhs(state)
    midpoint = state + 0.5 * step_s * first
    return state + step_s * rhs(midpoint)


def _poly_real_roots(coefficients: Sequence[float]) -> list[float]:
    """Return real roots in the normalized segment coordinate ``s in [0, 1]``.

    Coefficients may carry metres or metres per second.  They are normalized
    before the dimensionless root tolerances are applied; no SI-channel
    absolute tolerance is used to trim the polynomial degree.
    """

    coeff = np.asarray(coefficients, dtype=float)
    if coeff.ndim != 1 or len(coeff) == 0 or not np.all(np.isfinite(coeff)):
        raise SolverError("INVALID_CLEARANCE_POLYNOMIAL")
    scale = float(np.max(np.abs(coeff)))
    if scale == 0.0:
        return []
    coeff = coeff / scale
    first = 0
    while first < len(coeff) - 1 and abs(coeff[first]) <= ROOT_COEFFICIENT_RELATIVE_TRIM:
        first += 1
    coeff = coeff[first:]
    if len(coeff) <= 1:
        return []
    roots = np.roots(coeff)
    result: list[float] = []
    for root in roots:
        if abs(float(np.imag(root))) <= ROOT_IMAGINARY_TOLERANCE:
            value = float(np.real(root))
            if -ROOT_DOMAIN_TOLERANCE <= value <= 1.0 + ROOT_DOMAIN_TOLERANCE:
                result.append(min(1.0, max(0.0, value)))
    return sorted(set(round(value, 14) for value in result))


def _hermite_coefficients(g0: float, g1: float, v0: float, v1: float, step_s: float) -> np.ndarray:
    return np.array((
        2.0 * g0 - 2.0 * g1 + step_s * (v0 + v1),
        -3.0 * g0 + 3.0 * g1 - step_s * (2.0 * v0 + v1),
        step_s * v0,
        g0,
    ))


def _poly_value(coefficients: np.ndarray, s: float) -> float:
    return float(np.polyval(coefficients, s))


def _segment_good_intervals(
    t_left: float,
    t_right: float,
    left_coeff: np.ndarray,
    right_coeff: np.ndarray,
    *,
    ledger_interval_certified: bool,
) -> list[tuple[float, float]]:
    if not ledger_interval_certified:
        return []
    h = t_right - t_left
    left_gap = left_coeff.copy(); left_gap[-1] -= GAP_CLEARANCE_M + GAP_CLASSIFICATION_MARGIN_M
    right_gap = right_coeff.copy(); right_gap[-1] -= GAP_CLEARANCE_M + GAP_CLASSIFICATION_MARGIN_M
    left_rate = np.polyder(left_coeff) / h
    left_rate[-1] += GAP_RATE_REENTRY_TOL_M_S - GAP_RATE_CLASSIFICATION_MARGIN_M_S
    right_rate = np.polyder(right_coeff) / h
    right_rate[-1] += GAP_RATE_REENTRY_TOL_M_S - GAP_RATE_CLASSIFICATION_MARGIN_M_S
    native_polynomials = (
        (left_gap, "gap_m"), (right_gap, "gap_m"),
        (left_rate, "gap_rate_m_s"), (right_rate, "gap_rate_m_s"),
    )
    boundaries = [0.0, 1.0]
    for polynomial, _ in native_polynomials:
        boundaries.extend(_poly_real_roots(polynomial))
    boundaries = sorted(set(min(1.0, max(0.0, value)) for value in boundaries))
    intervals: list[tuple[float, float]] = []
    for lower, upper in zip(boundaries[:-1], boundaries[1:]):
        if upper - lower <= 1.0e-14:
            continue
        midpoint = 0.5 * (lower + upper)
        # Zero is an admissible threshold equality.  Any negative value in
        # either native channel is rejected; there is no shared unitless slack.
        if all(_poly_value(polynomial, midpoint) >= 0.0 for polynomial, _ in native_polynomials):
            intervals.append((t_left + h * lower, t_left + h * upper))
    return intervals


def _merge_intervals(intervals: Sequence[tuple[float, float]]) -> list[list[float]]:
    merged: list[list[float]] = []
    for lower, upper in sorted(intervals):
        if not merged or lower - merged[-1][1] > TIME_INTERVAL_MERGE_TOLERANCE_S:
            merged.append([float(lower), float(upper)])
        else:
            merged[-1][1] = max(merged[-1][1], float(upper))
    return merged


def _continuous_clearance_coverage(
    time_s: Sequence[float],
    left_gap_m: Sequence[float],
    right_gap_m: Sequence[float],
    left_gap_rate_m_s: Sequence[float],
    right_gap_rate_m_s: Sequence[float],
) -> dict[str, Any]:
    """Certify that both clearance channels stay admissible for a whole trace."""

    time = np.asarray(time_s, dtype=float)
    arrays = [np.asarray(value, dtype=float) for value in (left_gap_m, right_gap_m, left_gap_rate_m_s, right_gap_rate_m_s)]
    if time.ndim != 1 or len(time) < 2 or any(value.shape != time.shape for value in arrays):
        raise SolverError("POST_RELEASE_CLEARANCE_HISTORY_SHAPE_INVALID")
    if np.any(np.diff(time) <= 0.0) or not all(np.all(np.isfinite(value)) for value in (time, *arrays)):
        raise SolverError("POST_RELEASE_CLEARANCE_HISTORY_NONFINITE_OR_NONMONOTONIC")
    good: list[tuple[float, float]] = []
    for index in range(len(time) - 1):
        h = float(time[index + 1] - time[index])
        left_coeff = _hermite_coefficients(arrays[0][index], arrays[0][index + 1], arrays[2][index], arrays[2][index + 1], h)
        right_coeff = _hermite_coefficients(arrays[1][index], arrays[1][index + 1], arrays[3][index], arrays[3][index + 1], h)
        good.extend(_segment_good_intervals(float(time[index]), float(time[index + 1]), left_coeff, right_coeff, ledger_interval_certified=True))
    merged = _merge_intervals(good)
    full = bool(
        merged
        and merged[0][0] <= float(time[0]) + TIME_INTERVAL_MERGE_TOLERANCE_S
        and merged[-1][1] >= float(time[-1]) - TIME_INTERVAL_MERGE_TOLERANCE_S
        and len(merged) == 1
    )
    return {
        "full_interval_certified": full,
        "certified_good_intervals_s": merged,
        "gap_threshold_m": GAP_CLEARANCE_M,
        "gap_rate_threshold_m_s": -GAP_RATE_REENTRY_TOL_M_S,
        "gap_classification_margin_m": GAP_CLASSIFICATION_MARGIN_M,
        "gap_rate_classification_margin_m_s": GAP_RATE_CLASSIFICATION_MARGIN_M_S,
        "root_coefficient_relative_trim_dimensionless": ROOT_COEFFICIENT_RELATIVE_TRIM,
        "root_imaginary_tolerance_dimensionless": ROOT_IMAGINARY_TOLERANCE,
    }


def certify_earliest_clearance(
    time_s: Sequence[float],
    left_gap_m: Sequence[float],
    right_gap_m: Sequence[float],
    left_gap_rate_m_s: Sequence[float],
    right_gap_rate_m_s: Sequence[float],
    *,
    acquisition_time_s: float,
    ledger_interval_certified: Sequence[bool] | None = None,
) -> dict[str, Any]:
    time = np.asarray(time_s, dtype=float)
    arrays = [np.asarray(value, dtype=float) for value in (left_gap_m, right_gap_m, left_gap_rate_m_s, right_gap_rate_m_s)]
    if time.ndim != 1 or len(time) < 2 or any(value.shape != time.shape for value in arrays):
        raise SolverError("CLEARANCE_HISTORY_SHAPE_INVALID")
    if np.any(np.diff(time) <= 0.0) or not all(np.all(np.isfinite(value)) for value in (time, *arrays)):
        raise SolverError("CLEARANCE_HISTORY_NONFINITE_OR_NONMONOTONIC")
    certified = np.ones(len(time) - 1, dtype=bool) if ledger_interval_certified is None else np.asarray(ledger_interval_certified, dtype=bool)
    if certified.shape != (len(time) - 1,):
        raise SolverError("CLEARANCE_LEDGER_INTERVAL_SHAPE_INVALID")
    good: list[tuple[float, float]] = []
    for index in range(len(time) - 1):
        h = float(time[index + 1] - time[index])
        left_coeff = _hermite_coefficients(arrays[0][index], arrays[0][index + 1], arrays[2][index], arrays[2][index + 1], h)
        right_coeff = _hermite_coefficients(arrays[1][index], arrays[1][index + 1], arrays[3][index], arrays[3][index + 1], h)
        good.extend(_segment_good_intervals(float(time[index]), float(time[index + 1]), left_coeff, right_coeff, ledger_interval_certified=bool(certified[index])))
    merged = _merge_intervals(good)
    eligible_start = acquisition_time_s + MINIMUM_ACTIVE_DWELL_S
    for lower, upper in merged:
        tau_c = max(lower, eligible_start)
        if upper - tau_c >= CLEARANCE_DWELL_S - TIME_INTERVAL_MERGE_TOLERANCE_S:
            removal = tau_c + CLEARANCE_DWELL_S
            return {
                "finite_event": True,
                "tau_c_s": tau_c,
                "removal_time_s": removal,
                "certified_good_interval_s": [lower, upper],
                "algorithm": "PIECEWISE_CUBIC_HERMITE_ALL_ROOT_PARTITION_EARLIEST_DWELL",
                "endpoint_only": False,
                "native_tolerance_channels": {
                    "gap_classification_margin_m": GAP_CLASSIFICATION_MARGIN_M,
                    "gap_rate_classification_margin_m_s": GAP_RATE_CLASSIFICATION_MARGIN_M_S,
                    "root_imaginary_tolerance_dimensionless": ROOT_IMAGINARY_TOLERANCE,
                },
            }
    return {
        "finite_event": False,
        "tau_c_s": None,
        "removal_time_s": None,
        "certified_good_intervals_s": merged,
        "algorithm": "PIECEWISE_CUBIC_HERMITE_ALL_ROOT_PARTITION_EARLIEST_DWELL",
        "endpoint_only": False,
        "native_tolerance_channels": {
            "gap_classification_margin_m": GAP_CLASSIFICATION_MARGIN_M,
            "gap_rate_classification_margin_m_s": GAP_RATE_CLASSIFICATION_MARGIN_M_S,
            "root_imaginary_tolerance_dimensionless": ROOT_IMAGINARY_TOLERANCE,
        },
        "status": "DIAGNOSTIC_INCONCLUSIVE_HORIZON_EXHAUSTED_NO_REMOVAL_OBSERVED",
        "global_empty_eligibility_set_claimed": False,
    }


def _active_sample(
    model: BranchedGripperServiceModel,
    attached_model: AttachedTargetModel,
    snapshot: SnapshotTransform,
    service: ServiceState,
    initial_linear_momentum: np.ndarray,
    initial_angular_momentum: np.ndarray,
    initial_energy_plus_dissipation_j: float,
    fixed_dissipation_j: float,
) -> dict[str, Any]:
    mass_formula, bias_formula, a, target, adot_eta, m_target = _active_formula_terms(model, service, snapshot)
    mass_fixed = attached_model.mass_matrix(service)
    bias_fixed = attached_model.bias_effort(service, difference_step_s=DIFFERENCE_STEP_S)
    service_ledger = model.momentum_energy(service)
    target_ledger = target_momentum_energy(target)
    observations = evaluate_dual_contact(model, service, target, DualContactConfig(), enabled=False)
    eta_dot = _cholesky_solve(mass_formula, -bias_formula)
    combined_acceleration = np.concatenate((eta_dot, a @ eta_dot + adot_eta))
    combined_mass = _block_diagonal(model.mass_matrix(service), m_target)
    combined_bias = np.concatenate((model.bias_effort(service), _target_bias(target)))
    embedding = np.vstack((np.eye(14), a))
    full_residual = combined_mass @ combined_acceleration + combined_bias
    ideal_power = float(np.concatenate((service.nu_s_mixed, target.twist_inertial_mixed)) @ full_residual)
    total_linear = service_ledger.linear_momentum_n_s + target_ledger.linear_momentum_n_s
    total_angular = service_ledger.angular_momentum_about_inertial_origin_n_m_s + target_ledger.angular_momentum_about_inertial_origin_n_m_s
    energy_plus = service_ledger.kinetic_energy_j + target_ledger.kinetic_energy_j + fixed_dissipation_j
    relative = target.twist_inertial_mixed - a @ service.nu_s_mixed
    return {
        "target": target,
        "left_gap_m": float(observations[0].gap_m),
        "right_gap_m": float(observations[1].gap_m),
        "left_gap_rate_m_s": float(observations[0].relative_normal_speed_m_s),
        "right_gap_rate_m_s": float(observations[1].relative_normal_speed_m_s),
        "linear_momentum_drift_N_s": float(np.linalg.norm(total_linear - initial_linear_momentum)),
        "angular_momentum_drift_N_m_s": float(np.linalg.norm(total_angular - initial_angular_momentum)),
        "energy_plus_dissipation_drift_J": abs(energy_plus - initial_energy_plus_dissipation_j),
        "pose_translation_residual_m": 0.0,
        "pose_rotation_residual_rad": 0.0,
        "relative_linear_twist_m_s": float(np.max(np.abs(relative[:3]))),
        "relative_angular_twist_rad_s": float(np.max(np.abs(relative[3:]))),
        "ideal_constraint_power_W": abs(ideal_power),
        "contact_force_while_active_N": max(float(np.linalg.norm(observations[0].service_force_inertial_n)), float(np.linalg.norm(observations[1].service_force_inertial_n))),
        "contact_torque_while_active_N_m": max(float(np.linalg.norm(observations[0].service_shift_torque_inertial_n_m)), float(np.linalg.norm(observations[1].service_shift_torque_inertial_n_m))),
        "mass_formula_fixed_child_inf": float(np.linalg.norm(mass_formula - mass_fixed, ord=np.inf)),
        "bias_formula_fixed_child_base_linear_N": _channel_maximum(bias_formula - bias_fixed, slice(0, 3)),
        "bias_formula_fixed_child_base_angular_N_m": _channel_maximum(bias_formula - bias_fixed, slice(3, 6)),
        "bias_formula_fixed_child_R_joint_N_m": _channel_maximum(bias_formula - bias_fixed, slice(6, 12)),
        "bias_formula_fixed_child_P_joint_N": _channel_maximum(bias_formula - bias_fixed, slice(12, 14)),
        "reduced_full_residual_power_W": abs(float(service.nu_s_mixed @ (embedding.T @ full_residual))),
    }


def _target_to_post_vector(target: TargetState) -> np.ndarray:
    return np.concatenate((
        target.position_inertial_m,
        target.quaternion_body_to_inertial_wxyz,
        target.twist_inertial_mixed,
    ))


def _target_from_post_vector(vector: Sequence[float]) -> TargetState:
    value = np.asarray(vector, dtype=float)
    if value.shape != (13,) or not np.all(np.isfinite(value)):
        raise SolverError("INVALID_POST_RELEASE_TARGET_VECTOR")
    return validate_target_state(TargetState(
        value[:3].copy(), normalize_quaternion(value[3:7]), value[7:13].copy(),
    ))


def _post_release_rhs(model: BranchedGripperServiceModel, vector: np.ndarray) -> np.ndarray:
    """Independent 29D service plus 13D target zero-external free flight."""

    value = np.asarray(vector, dtype=float)
    if value.shape != (42,) or not np.all(np.isfinite(value)):
        raise SolverError("INVALID_POST_RELEASE_COMBINED_STATE")
    service = _service_from_active_vector(value[:29])
    target = _target_from_post_vector(value[29:42])
    service_acceleration = _cholesky_solve(model.mass_matrix(service), -model.bias_effort(service))
    service_quaternion_rate = 0.5 * quat_product(
        np.array((0.0, *service.nu_s_mixed[3:6])),
        service.base_quaternion_body_to_inertial_wxyz,
    )
    rotation = quat_to_rotation(target.quaternion_body_to_inertial_wxyz)
    inertia_world = rotation @ TARGET_INERTIA_BODY_KG_M2 @ rotation.T
    target_velocity = target.twist_inertial_mixed[:3]
    target_omega = target.twist_inertial_mixed[3:]
    target_omega_dot = np.linalg.solve(
        inertia_world,
        -np.cross(target_omega, inertia_world @ target_omega),
    )
    target_quaternion_rate = 0.5 * quat_product(
        np.array((0.0, *target_omega)),
        target.quaternion_body_to_inertial_wxyz,
    )
    return np.concatenate((
        service.nu_s_mixed[:3], service_quaternion_rate,
        service.nu_s_mixed[6:], service_acceleration,
        target_velocity, target_quaternion_rate, np.zeros(3), target_omega_dot,
    ))


def _active_service_at_time(
    model: BranchedGripperServiceModel,
    active: ActiveRunResult,
    time_s: float,
) -> ServiceState:
    """Reconstruct the active state at an exact event time without sample rounding."""

    requested = float(time_s)
    if requested < float(active.time_s[0]) - TIME_INTERVAL_MERGE_TOLERANCE_S or requested > float(active.time_s[-1]) + TIME_INTERVAL_MERGE_TOLERANCE_S:
        raise SolverError("ACTIVE_EVENT_TIME_OUTSIDE_TRACE")
    index = int(np.searchsorted(active.time_s, requested, side="right") - 1)
    index = max(0, min(index, len(active.time_s) - 1))
    service = ServiceState(
        active.service_position_m[index].copy(),
        active.service_quaternion_wxyz[index].copy(),
        active.service_joint_coordinates_mixed[index].copy(),
        active.eta_mixed[index].copy(),
    )
    remainder = requested - float(active.time_s[index])
    if abs(remainder) <= TIME_INTERVAL_MERGE_TOLERANCE_S:
        return model.validate_service_state(service)
    if remainder < 0.0 or remainder > active.step_s + TIME_INTERVAL_MERGE_TOLERANCE_S:
        raise SolverError("ACTIVE_EVENT_RECONSTRUCTION_INTERVAL_INVALID")
    rhs = lambda state: _active_rhs(model, active.acquisition.snapshot, state)
    stepper = _rk4_step if active.method == "rk4" else _midpoint_step if active.method == "midpoint" else None
    if stepper is None:
        raise SolverError("ACTIVE_EVENT_RECONSTRUCTION_METHOD_INVALID")
    state = stepper(rhs, _service_to_active_vector(service), remainder)
    state[3:7] = _canonical_quaternion(state[3:7])
    return _service_from_active_vector(state)


def execute_post_release(
    model: BranchedGripperServiceModel,
    acquisition: AcquisitionResult,
    service_at_release: ServiceState,
    *,
    release_time_s: float,
    method: str,
    step_s: float,
    observation_s: float = POST_RELEASE_OBSERVATION_S,
    z_after_override: Sequence[float] | None = None,
    contact_enabled: bool = False,
) -> dict[str, Any]:
    """Execute the complete synthetic removal mapping and 5 ms free-flight audit.

    The contact evaluator remains an observation-only call after removal.  Its
    ``enabled`` argument is recorded sample by sample so NC20 can mutate the
    real call path and the Gate can reject that call independently of force.
    """

    if observation_s <= 0.0 or step_s <= 0.0:
        raise SolverError("POST_RELEASE_TIME_CONFIGURATION_INVALID")
    steps_float = observation_s / step_s
    steps = int(round(steps_float))
    if steps < 1 or abs(steps_float - steps) > 1.0e-9:
        raise SolverError("POST_RELEASE_OBSERVATION_NOT_INTEGER_MULTIPLE")
    service_before = model.validate_service_state(service_at_release)
    target_before, a_release, _, _, _ = target_from_snapshot(model, service_before, acquisition.snapshot)
    z_before = np.concatenate((service_before.nu_s_mixed, a_release @ service_before.nu_s_mixed))
    z_after = z_before.copy() if z_after_override is None else _vector(z_after_override, 20, "post release z after override")
    service_after = ServiceState(
        service_before.base_position_inertial_m.copy(),
        service_before.base_quaternion_body_to_inertial_wxyz.copy(),
        service_before.joint_coordinates_mixed.copy(),
        z_after[:14].copy(),
    )
    target_after = TargetState(
        target_before.position_inertial_m.copy(),
        target_before.quaternion_body_to_inertial_wxyz.copy(),
        z_after[14:20].copy(),
    )

    channel_slices = {
        "service_base_linear_m_s": slice(0, 3),
        "service_base_angular_rad_s": slice(3, 6),
        "service_R_joint_rad_s": slice(6, 12),
        "service_P_joint_m_s": slice(12, 14),
        "target_linear_m_s": slice(14, 17),
        "target_angular_rad_s": slice(17, 20),
    }
    native_velocity_jump = {
        name: float(np.max(np.abs(z_after[indices] - z_before[indices])))
        for name, indices in channel_slices.items()
    }
    before_service_ledger = model.momentum_energy(service_before)
    before_target_ledger = target_momentum_energy(target_before)
    after_service_ledger = model.momentum_energy(service_after)
    after_target_ledger = target_momentum_energy(target_after)
    linear_impulse = (
        after_service_ledger.linear_momentum_n_s + after_target_ledger.linear_momentum_n_s
        - before_service_ledger.linear_momentum_n_s - before_target_ledger.linear_momentum_n_s
    )
    angular_impulse = (
        after_service_ledger.angular_momentum_about_inertial_origin_n_m_s
        + after_target_ledger.angular_momentum_about_inertial_origin_n_m_s
        - before_service_ledger.angular_momentum_about_inertial_origin_n_m_s
        - before_target_ledger.angular_momentum_about_inertial_origin_n_m_s
    )
    energy_before = before_service_ledger.kinetic_energy_j + before_target_ledger.kinetic_energy_j
    energy_after = after_service_ledger.kinetic_energy_j + after_target_ledger.kinetic_energy_j

    count = steps + 1
    time = float(release_time_s) + np.arange(count, dtype=float) * step_s
    service_state = np.empty((count, 29))
    target_state = np.empty((count, 13))
    left_gap = np.empty(count); right_gap = np.empty(count)
    left_rate = np.empty(count); right_rate = np.empty(count)
    contact_force = np.empty(count); contact_torque = np.empty(count)
    linear_drift = np.empty(count); angular_drift = np.empty(count); energy_drift = np.empty(count)
    snapshot_translation_residual = np.empty(count); snapshot_rotation_residual = np.empty(count)
    contact_calls: list[dict[str, Any]] = []
    initial_linear = after_service_ledger.linear_momentum_n_s + after_target_ledger.linear_momentum_n_s
    initial_angular = after_service_ledger.angular_momentum_about_inertial_origin_n_m_s + after_target_ledger.angular_momentum_about_inertial_origin_n_m_s
    initial_energy = energy_after
    state = np.concatenate((_service_to_active_vector(service_after), _target_to_post_vector(target_after)))
    rhs = lambda value: _post_release_rhs(model, value)
    stepper = _rk4_step if method == "rk4" else _midpoint_step if method == "midpoint" else None
    if stepper is None:
        raise SolverError("POST_RELEASE_INTEGRATOR_INVALID")

    for index in range(count):
        service = _service_from_active_vector(state[:29])
        target = _target_from_post_vector(state[29:42])
        service_state[index] = state[:29]
        target_state[index] = state[29:42]
        observations = evaluate_dual_contact(model, service, target, DualContactConfig(), enabled=contact_enabled)
        contact_calls.append({"phase": "POST_REMOVAL", "sample_index": index, "enabled_argument": bool(contact_enabled)})
        left_gap[index] = float(observations[0].gap_m); right_gap[index] = float(observations[1].gap_m)
        left_rate[index] = float(observations[0].relative_normal_speed_m_s); right_rate[index] = float(observations[1].relative_normal_speed_m_s)
        contact_force[index] = max(float(np.linalg.norm(item.service_force_inertial_n)) for item in observations)
        contact_torque[index] = max(float(np.linalg.norm(item.service_shift_torque_inertial_n_m)) for item in observations)
        service_ledger = model.momentum_energy(service); target_ledger = target_momentum_energy(target)
        linear_drift[index] = float(np.linalg.norm(service_ledger.linear_momentum_n_s + target_ledger.linear_momentum_n_s - initial_linear))
        angular_drift[index] = float(np.linalg.norm(service_ledger.angular_momentum_about_inertial_origin_n_m_s + target_ledger.angular_momentum_about_inertial_origin_n_m_s - initial_angular))
        energy_drift[index] = abs(service_ledger.kinetic_energy_j + target_ledger.kinetic_energy_j - initial_energy)
        snapshot_target, _, _, _, _ = target_from_snapshot(model, service, acquisition.snapshot)
        snapshot_translation_residual[index] = float(np.linalg.norm(target.position_inertial_m - snapshot_target.position_inertial_m))
        snapshot_rotation_residual[index] = quaternion_geodesic(target.quaternion_body_to_inertial_wxyz, snapshot_target.quaternion_body_to_inertial_wxyz)
        if index < steps:
            state = stepper(rhs, state, step_s)
            if not np.all(np.isfinite(state)):
                raise SolverError("POST_RELEASE_NONFINITE_STATE")
            state[3:7] = _canonical_quaternion(state[3:7])
            state[32:36] = _canonical_quaternion(state[32:36])

    clearance = _continuous_clearance_coverage(time, left_gap, right_gap, left_rate, right_rate)
    mapping_pass = bool(
        max(native_velocity_jump.values()) <= 1.0e-12
        and float(np.linalg.norm(linear_impulse)) <= 1.0e-12
        and float(np.linalg.norm(angular_impulse)) <= 1.0e-12
        and abs(energy_after - energy_before) <= 1.0e-12
    )
    contact_pass = bool(
        not any(call["enabled_argument"] for call in contact_calls)
        and float(np.max(contact_force)) <= 1.0e-12
        and float(np.max(contact_torque)) <= 1.0e-12
    )
    ledger_pass = bool(
        float(np.max(linear_drift)) <= 1.0e-9
        and float(np.max(angular_drift)) <= 1.0e-9
        and float(np.max(energy_drift)) <= 1.0e-7
    )
    duration_pass = abs(float(time[-1] - time[0]) - POST_RELEASE_OBSERVATION_S) <= TIME_INTERVAL_MERGE_TOLERANCE_S
    passed = mapping_pass and contact_pass and ledger_pass and duration_pass and bool(clearance["full_interval_certified"])
    if not mapping_pass:
        terminal = "DIAGNOSTIC_FAIL_CLOSED_REMOVAL_MAPPING"
    elif not contact_pass:
        terminal = "DIAGNOSTIC_FAIL_CLOSED_POST_REMOVAL_CONTACT_REACTIVATED"
    elif not clearance["full_interval_certified"]:
        terminal = "DIAGNOSTIC_FAIL_CLOSED_POST_REMOVAL_CLEARANCE_REENTRY"
    elif not ledger_pass:
        terminal = "DIAGNOSTIC_FAIL_CLOSED_POST_REMOVAL_LEDGER"
    elif not duration_pass:
        terminal = "DIAGNOSTIC_FAIL_CLOSED_POST_REMOVAL_DURATION"
    else:
        terminal = "SYNTHETIC_CONSTRAINT_REMOVAL_AND_POST_RELEASE_OBSERVATION_COMPLETE"
    return {
        "release_time_s": float(release_time_s),
        "observation_duration_s": float(time[-1] - time[0]),
        "method": method,
        "step_s": float(step_s),
        "target_state_source_after_removal": "INDEPENDENT_13D_ZERO_EXTERNAL_FREE_FLIGHT",
        "service_state_source_after_removal": "INDEPENDENT_29D_ZERO_EXTERNAL_FREE_FLIGHT",
        "mapping": {
            "z_before": z_before.tolist(), "z_after": z_after.tolist(),
            "native_velocity_jump_maxima": native_velocity_jump,
            "linear_impulse_N_s": linear_impulse.tolist(),
            "angular_impulse_N_m_s": angular_impulse.tolist(),
            "kinetic_energy_jump_J": float(energy_after - energy_before),
            "ideal_constraint_stored_energy_J": 0.0,
            "mapping_name": "EXPAND_L_ETA_THEN_COMPONENTWISE_COPY",
        },
        "trace": {
            "time_s": time.tolist(),
            "service_state_29": service_state.tolist(),
            "target_state_13": target_state.tolist(),
            "left_gap_m": left_gap.tolist(), "right_gap_m": right_gap.tolist(),
            "left_gap_rate_m_s": left_rate.tolist(), "right_gap_rate_m_s": right_rate.tolist(),
            "contact_force_N": contact_force.tolist(), "contact_torque_N_m": contact_torque.tolist(),
            "linear_momentum_drift_N_s": linear_drift.tolist(),
            "angular_momentum_drift_N_m_s": angular_drift.tolist(),
            "energy_drift_J": energy_drift.tolist(),
            "snapshot_translation_residual_m": snapshot_translation_residual.tolist(),
            "snapshot_rotation_residual_rad": snapshot_rotation_residual.tolist(),
            "contact_calls": contact_calls,
        },
        "maxima": {
            "contact_force_N": float(np.max(contact_force)),
            "contact_torque_N_m": float(np.max(contact_torque)),
            "linear_momentum_drift_N_s": float(np.max(linear_drift)),
            "angular_momentum_drift_N_m_s": float(np.max(angular_drift)),
            "energy_drift_J": float(np.max(energy_drift)),
            "snapshot_translation_residual_m": float(np.max(snapshot_translation_residual)),
            "snapshot_rotation_residual_rad": float(np.max(snapshot_rotation_residual)),
        },
        "clearance": clearance,
        "mapping_pass": mapping_pass,
        "contact_kernel_disabled_pass": contact_pass,
        "post_release_ledger_pass": ledger_pass,
        "observation_duration_pass": duration_pass,
        "post_release_passed": passed,
        "terminal_status": terminal,
        "physical_release_claimed": False,
    }


def propagate_active(
    model: BranchedGripperServiceModel,
    event: EventInput,
    acquisition: AcquisitionResult,
    *,
    method: str,
    step_s: float,
    end_time_s: float = ACTIVE_END_TIME_S,
) -> ActiveRunResult:
    duration = end_time_s - event.time_s
    steps_float = duration / step_s
    steps = int(round(steps_float))
    if steps < 2 or abs(steps_float - steps) > 1.0e-9:
        raise SolverError(f"ACTIVE_HORIZON_NOT_INTEGER_MULTIPLE:{event.run_id}")
    post_service = ServiceState(
        event.service.base_position_inertial_m.copy(), event.service.base_quaternion_body_to_inertial_wxyz.copy(),
        event.service.joint_coordinates_mixed.copy(), acquisition.eta_plus.copy(),
    )
    state = _service_to_active_vector(post_service)
    count = steps + 1
    time = event.time_s + np.arange(count, dtype=float) * step_s
    position = np.empty((count, 3)); quaternion = np.empty((count, 4)); q = np.empty((count, 8)); eta = np.empty((count, 14))
    target_position = np.empty((count, 3)); target_quaternion = np.empty((count, 4)); target_twist = np.empty((count, 6))
    left_gap = np.empty(count); right_gap = np.empty(count); left_rate = np.empty(count); right_rate = np.empty(count)
    ledger_names = (
        "linear_momentum_drift_N_s", "angular_momentum_drift_N_m_s", "energy_plus_dissipation_drift_J",
        "pose_translation_residual_m", "pose_rotation_residual_rad", "relative_linear_twist_m_s", "relative_angular_twist_rad_s",
        "ideal_constraint_power_W", "contact_force_while_active_N", "contact_torque_while_active_N_m",
        "mass_formula_fixed_child_inf", "bias_formula_fixed_child_base_linear_N", "bias_formula_fixed_child_base_angular_N_m",
        "bias_formula_fixed_child_R_joint_N_m", "bias_formula_fixed_child_P_joint_N", "reduced_full_residual_power_W",
    )
    ledgers = {name: np.empty(count) for name in ledger_names}
    attached_model = AttachedTargetModel(acquisition.snapshot)
    first_service_ledger = model.momentum_energy(post_service)
    first_target, _, _, _, _ = target_from_snapshot(model, post_service, acquisition.snapshot)
    first_target_ledger = target_momentum_energy(first_target)
    initial_linear = first_service_ledger.linear_momentum_n_s + first_target_ledger.linear_momentum_n_s
    initial_angular = first_service_ledger.angular_momentum_about_inertial_origin_n_m_s + first_target_ledger.angular_momentum_about_inertial_origin_n_m_s
    fixed_dissipation = event.b3_dissipation_j + acquisition.energy_audit["D_switch_J"]
    initial_energy = first_service_ledger.kinetic_energy_j + first_target_ledger.kinetic_energy_j + fixed_dissipation
    rhs = lambda value: _active_rhs(model, acquisition.snapshot, value)
    stepper = _rk4_step if method == "rk4" else _midpoint_step if method == "midpoint" else None
    if stepper is None:
        raise SolverError(f"UNKNOWN_ACTIVE_INTEGRATOR:{method}")
    for index in range(count):
        service = _service_from_active_vector(state)
        sample = _active_sample(model, attached_model, acquisition.snapshot, service, initial_linear, initial_angular, initial_energy, fixed_dissipation)
        position[index] = service.base_position_inertial_m; quaternion[index] = service.base_quaternion_body_to_inertial_wxyz
        q[index] = service.joint_coordinates_mixed; eta[index] = service.nu_s_mixed
        target = sample.pop("target")
        target_position[index] = target.position_inertial_m; target_quaternion[index] = target.quaternion_body_to_inertial_wxyz; target_twist[index] = target.twist_inertial_mixed
        left_gap[index] = sample.pop("left_gap_m"); right_gap[index] = sample.pop("right_gap_m")
        left_rate[index] = sample.pop("left_gap_rate_m_s"); right_rate[index] = sample.pop("right_gap_rate_m_s")
        for name in ledger_names:
            ledgers[name][index] = float(sample[name])
        if index < steps:
            state = stepper(rhs, state, step_s)
            if not np.all(np.isfinite(state)):
                raise SolverError(f"ACTIVE_NONFINITE_STATE:{event.run_id}:{index}")
            state[3:7] = _canonical_quaternion(state[3:7])

    maxima = {name: float(np.max(np.abs(values))) for name, values in ledgers.items()}
    ledger_closed_sample = (
        (ledgers["linear_momentum_drift_N_s"] <= 1.0e-9)
        & (ledgers["angular_momentum_drift_N_m_s"] <= 1.0e-9)
        & (ledgers["energy_plus_dissipation_drift_J"] <= 1.0e-7)
        & (ledgers["pose_translation_residual_m"] <= 1.0e-9)
        & (ledgers["pose_rotation_residual_rad"] <= 1.0e-9)
        & (ledgers["relative_linear_twist_m_s"] <= 1.0e-9)
        & (ledgers["relative_angular_twist_rad_s"] <= 1.0e-9)
        & (ledgers["ideal_constraint_power_W"] <= 1.0e-10)
        & (ledgers["contact_force_while_active_N"] <= 1.0e-12)
        & (ledgers["contact_torque_while_active_N_m"] <= 1.0e-12)
    )
    interval_certified = ledger_closed_sample[:-1] & ledger_closed_sample[1:]
    clearance = certify_earliest_clearance(
        time, left_gap, right_gap, left_rate, right_rate,
        acquisition_time_s=event.time_s, ledger_interval_certified=interval_certified,
    )
    if not bool(np.all(ledger_closed_sample)):
        provisional_terminal = "DIAGNOSTIC_FAIL_CLOSED_ACTIVE_LEDGER"
    elif clearance["finite_event"]:
        provisional_terminal = "SYNTHETIC_CONSTRAINT_REMOVAL_ELIGIBLE_PENDING_TRANSITION"
    else:
        provisional_terminal = "DIAGNOSTIC_INCONCLUSIVE_HORIZON_EXHAUSTED_NO_REMOVAL_OBSERVED"
    provisional = ActiveRunResult(
        event.run_id, method, step_s, acquisition, time, position, quaternion, q, eta,
        target_position, target_quaternion, target_twist, left_gap, right_gap, left_rate,
        right_rate, ledgers, maxima, clearance, provisional_terminal, False, None,
    )
    post_release: dict[str, Any] | None = None
    if bool(np.all(ledger_closed_sample)) and clearance["finite_event"]:
        release_time = float(clearance["removal_time_s"])
        service_at_release = _active_service_at_time(model, provisional, release_time)
        post_release = execute_post_release(
            model, acquisition, service_at_release,
            release_time_s=release_time, method=method, step_s=step_s,
        )
        removal_executed = bool(post_release["post_release_passed"])
        terminal = str(post_release["terminal_status"])
    else:
        removal_executed = False
        terminal = provisional_terminal
    return ActiveRunResult(
        event.run_id, method, step_s, acquisition, time, position, quaternion, q, eta,
        target_position, target_quaternion, target_twist, left_gap, right_gap, left_rate,
        right_rate, ledgers, maxima, clearance, terminal, removal_executed, post_release,
    )


def release_mapping(acquisition: AcquisitionResult, service: ServiceState) -> dict[str, Any]:
    _, a, _, _, _ = target_from_snapshot(BranchedGripperServiceModel(), service, acquisition.snapshot)
    z_before = np.concatenate((service.nu_s_mixed, a @ service.nu_s_mixed))
    z_after = z_before.copy()
    return {
        "z_before": z_before,
        "z_after": z_after,
        "linear_impulse_N_s": np.zeros(3),
        "angular_impulse_N_m_s": np.zeros(3),
        "ideal_constraint_stored_energy_J": 0.0,
        "mapping": "EXPAND_L_ETA_THEN_COMPONENTWISE_COPY",
    }


def _execute_consistent_finite_event_fixture(active: ActiveRunResult) -> tuple[EventInput, ActiveRunResult]:
    """Run the finite-event orchestration branch from a self-consistent nontrigger fixture.

    The B3 record is copied before acquisition, then its two P coordinates are
    offset by -20 micrometres and both P rates are set to +20 mm/s.  No state is
    altered after acquisition.  Consequently every active gap/rate sample, the
    off-grid clearance event and the 42D post-release state come from one and the
    same propagated trajectory.  The perturbed state is deliberately not a B3
    soft-capture trigger and receives no trigger or physical credit; contact
    points and elastic potentials are recomputed before the diagnostic
    acquisition projection so no stale B3 contact data are inherited.
    """

    base = extract_frozen_primary_event()
    if abs(base.time_s - active.acquisition.acquisition_time_s) > 1.0e-15:
        raise SolverError("FINITE_FIXTURE_PARENT_ACQUISITION_ANCHOR_MISMATCH")
    coordinates = base.service.joint_coordinates_mixed.copy(); coordinates[6:8] -= 2.0e-5
    velocity = base.service.nu_s_mixed.copy(); velocity[12:14] = 2.0e-2
    fixture_service = ServiceState(
        base.service.base_position_inertial_m.copy(),
        base.service.base_quaternion_body_to_inertial_wxyz.copy(),
        coordinates, velocity,
    )
    fixture_observations = evaluate_dual_contact(
        BranchedGripperServiceModel(), fixture_service, base.target,
        DualContactConfig(), enabled=True,
    )
    fixture_criteria = {
        "algorithm_only_nontrigger_fixture": True,
        "physical_or_main_trigger_credit": False,
        "parent_hash_bound_b3_trigger_index": int(base.index),
        "left_contact": bool(fixture_observations[0].penetration_m > 0.0),
        "right_contact": bool(fixture_observations[1].penetration_m > 0.0),
        "left_gap_m": float(fixture_observations[0].gap_m),
        "right_gap_m": float(fixture_observations[1].gap_m),
        "left_relative_normal_speed_m_s": float(fixture_observations[0].relative_normal_speed_m_s),
        "right_relative_normal_speed_m_s": float(fixture_observations[1].relative_normal_speed_m_s),
        "left_finger_rate_m_s": float(velocity[12]),
        "right_finger_rate_m_s": float(velocity[13]),
        "all_ledgers_closed": False,
        "soft_capture_transient_qualifies": False,
        "qualification_reason": "NONTRIGGER_ALGORITHM_BRANCH_COVERAGE_ONLY",
    }
    fixture_event = replace(
        base,
        run_id="algorithm_only_consistent_offgrid_finite_event_fixture",
        index=-1,
        service=fixture_service,
        left_common_contact_point_m=fixture_observations[0].common_contact_point_inertial_m.copy(),
        right_common_contact_point_m=fixture_observations[1].common_contact_point_inertial_m.copy(),
        left_contact_potential_j=float(fixture_observations[0].elastic_energy_j),
        right_contact_potential_j=float(fixture_observations[1].elastic_energy_j),
        b3_dissipation_j=0.0,
        state_label="ALGORITHM_ONLY_NONTRIGGER_INITIAL_STATE_FIXTURE",
        criteria=fixture_criteria,
        source="ALGORITHM_ONLY_NONTRIGGER_PRE_ACQUISITION_STATE_PERTURBED_FROM_HASH_BOUND_B3_EVENT__NOT_B3_MAIN_BRANCH",
    )
    model = BranchedGripperServiceModel()
    acquisition = acquisition_projection(
        model, fixture_event, allow_algorithm_only_nontrigger_fixture=True,
    )
    fixture_run = propagate_active(
        model, fixture_event, acquisition,
        method=fixture_event.method, step_s=fixture_event.step_s, end_time_s=0.06,
    )
    if not fixture_run.clearance["finite_event"] or not fixture_run.synthetic_removal_executed or fixture_run.post_release is None:
        raise SolverError("CONSISTENT_FINITE_EVENT_FIXTURE_DID_NOT_COMPLETE_HYBRID_BRANCH")
    relative_index = (float(fixture_run.clearance["removal_time_s"]) - fixture_event.time_s) / fixture_event.step_s
    if abs(relative_index - round(relative_index)) <= 1.0e-6:
        raise SolverError("CONSISTENT_FINITE_EVENT_FIXTURE_NOT_OFF_GRID")
    return fixture_event, fixture_run


def execute_abstract_removal_fixture(active: ActiveRunResult) -> dict[str, Any]:
    """Publish the consistent algorithm-only finite-event branch evidence."""

    fixture_event, fixture_run = _execute_consistent_finite_event_fixture(active)
    ta = fixture_event.time_s
    post = fixture_run.post_release
    assert post is not None
    trap_time = np.array((ta + 1.0e-3, ta + 2.0e-3))
    trap_gap = np.array((2.0e-6, 2.0e-6)); trap_rate = np.array((-1.0e-2, 1.0e-2))
    trap = certify_earliest_clearance(
        trap_time, trap_gap, trap_gap, trap_rate, trap_rate,
        acquisition_time_s=ta, ledger_interval_certified=np.ones(1, dtype=bool),
    )
    return {
        "scope": "ALGORITHM_ONLY_CONSISTENT_OFFGRID_FINITE_EVENT_HYBRID_FIXTURE__PERTURBED_FROM_HASH_BOUND_B3_EVENT__NOT_MAIN_B3_TRAJECTORY",
        "synthetic_pre_acquisition_P_coordinate_offset_m": -2.0e-5,
        "synthetic_pre_acquisition_P_velocity_m_s": 2.0e-2,
        "fixture_inputs_are_hardware_specifications": False,
        "fixture_satisfies_main_b3_soft_capture_trigger": False,
        "fixture_receives_physical_or_main_trigger_credit": False,
        "fixture_contact_points_and_potentials_recomputed_from_perturbed_state": True,
        "no_state_mutation_after_acquisition": True,
        "clearance_derived_from_same_active_state_trajectory": True,
        "same_active_trajectory_required_interval_s": [ta, float(fixture_run.clearance["removal_time_s"])],
        "active_trace_semantics": "FULL_COUNTERFACTUAL_ATTACHED_SEARCH_TRACE_FOR_EARLIEST_EVENT_CERTIFICATION__EXECUTED_HYBRID_HISTORY_SWITCHES_AT_REMOVAL_TIME",
        "propagate_active_finite_event_branch_executed": True,
        "exact_active_state_reconstructed_at_offgrid_removal_time": True,
        "fixture_event": event_to_json(fixture_event),
        "active_run": active_to_json(fixture_run, full_trace=True),
        "clearance": fixture_run.clearance,
        "post_release": post,
        "internal_negative_gap_trap": {
            "endpoint_gaps_above_threshold": True,
            "certifier_returned_finite_event": bool(trap["finite_event"]),
            "certifier": trap,
        },
        "fixture_pass_does_not_set_main_synthetic_removal_executed": True,
    }


def execute_run(event: EventInput) -> ActiveRunResult:
    model = BranchedGripperServiceModel()
    acquisition = acquisition_projection(model, event)
    return propagate_active(model, event, acquisition, method=event.method, step_s=event.step_s)


def _negative_control_release_service(active: ActiveRunResult) -> ServiceState:
    """Deterministic algorithm-only state with genuine positive opening rate."""

    coordinates = active.service_joint_coordinates_mixed[0].copy()
    coordinates[6:8] += 1.0e-3
    velocity = active.eta_mixed[0].copy()
    velocity[12:14] = 2.0e-2
    return ServiceState(
        active.service_position_m[0].copy(), active.service_quaternion_wxyz[0].copy(),
        coordinates, velocity,
    )


def _negative_control_base(
    acquisition: AcquisitionResult,
    active: ActiveRunResult,
    finite_fixture: ActiveRunResult,
) -> dict[str, Any]:
    """Build a raw-artifact bundle; no self-reported pass flags are included."""

    project = _project_root()
    bindings = _read_json(PHASE_ROOT / "contracts" / "PHASE_B4E_SOURCE_BINDINGS_V1.json")
    kernel_binding = next(item for item in bindings["sources"] if item["id"] == "b3_contact_kernel")
    kernel_bytes = (project / kernel_binding["path"]).read_bytes()
    trace_binding = next(item for item in bindings["sources"] if item["id"] == "b3_reference_trace")
    trace = _read_json(project / trace_binding["path"])
    trigger_records = [
        {
            "index": index,
            "aborted": record.get("state_label") in ("ABORTED_SAFE", "DIAGNOSTIC_FAIL_CLOSED"),
            "qualifies": record.get("soft_capture_criteria", {}).get("soft_capture_transient_qualifies") is True,
            "all_ledgers_closed": record.get("soft_capture_criteria", {}).get("all_ledgers_closed") is True,
        }
        for index, record in enumerate(trace["reference_records"])
    ]
    selected_record = trace["reference_records"][205]
    left_point = np.asarray(selected_record["contacts"]["left"]["common_contact_point_inertial_m"], dtype=float)
    right_point = np.asarray(selected_record["contacts"]["right"]["common_contact_point_inertial_m"], dtype=float)
    target_position = np.asarray(selected_record["target"]["position_inertial_m"], dtype=float)
    target_quaternion = np.asarray(selected_record["target"]["quaternion_body_to_inertial_wxyz"], dtype=float)

    service_state = np.hstack((
        active.service_position_m, active.service_quaternion_wxyz,
        active.service_joint_coordinates_mixed, active.eta_mixed,
    ))
    target_state = np.hstack((
        active.target_position_m, active.target_quaternion_wxyz, active.target_twist_mixed,
    ))
    post_release = finite_fixture.post_release
    if post_release is None or not post_release["post_release_passed"]:
        raise SolverError("NEGATIVE_CONTROL_RELEASE_FIXTURE_NOT_CLEAN")
    release_time = float(post_release["release_time_s"])
    release_service = _service_from_active_vector(np.asarray(post_release["trace"]["service_state_29"][0], dtype=float))
    mapping = post_release["mapping"]
    release_target, _, _, _, _ = target_from_snapshot(
        BranchedGripperServiceModel(), release_service, finite_fixture.acquisition.snapshot,
    )
    release_mass = _block_diagonal(
        BranchedGripperServiceModel().mass_matrix(release_service),
        _target_spatial_mass(release_target),
    )
    clearance_acquisition_time = float(finite_fixture.acquisition.acquisition_time_s)
    clearance_time = finite_fixture.time_s.copy()
    clearance_left_gap = finite_fixture.left_gap_m.copy()
    clearance_right_gap = finite_fixture.right_gap_m.copy()
    clearance_left_rate = finite_fixture.left_gap_rate_m_s.copy()
    clearance_right_rate = finite_fixture.right_gap_rate_m_s.copy()
    clearance_report = deepcopy(finite_fixture.clearance)
    return {
        "source": {
            "payload": kernel_bytes,
            "expected_bytes": int(kernel_binding["bytes"]),
            "expected_sha256": str(kernel_binding["sha256"]).upper(),
        },
        "trigger": {"records": trigger_records, "selected_index": 205},
        "acquisition": {
            "M_minus": acquisition.matrices["M_minus"].copy(),
            "M_service": acquisition.matrices["M_minus"][:14, :14].copy(),
            "M_target": acquisition.matrices["M_minus"][14:, 14:].copy(),
            "M_attached": acquisition.matrices["M_attached"].copy(),
            "A": acquisition.matrices["A"].copy(),
            "L": acquisition.matrices["L"].copy(),
            "J_c": acquisition.matrices["J_c"].copy(),
            "D": acquisition.matrices["D"].copy(),
            "S_eta": acquisition.matrices["S_eta"].copy(),
            "S_z": acquisition.matrices["S_z"].copy(),
            "z_minus": acquisition.z_minus.copy(),
            "z_plus": acquisition.z_plus_kkt.copy(),
            "reference_length_m": acquisition.reference_length_m,
            "target_quaternion_wxyz": target_quaternion,
            "backend_calls": [
                {"phase": "ACQUISITION_REDUCED", "callable_fqn": "numpy.linalg.cholesky"},
                {"phase": "ACQUISITION_KKT", "callable_fqn": "scipy.linalg.solve[assume_a=sym]"},
            ],
            "condition_records": [
                {"matrix_id": "W_BAR_SCALED_DIMENSIONLESS", "value": acquisition.metrics["W_bar_scaled_condition_number"]},
            ],
            "wrench": {
                "linear_impulse_N_s": acquisition.linear_impulse_n_s.copy(),
                "angular_impulse_N_m_s": acquisition.angular_impulse_n_m_s.copy(),
                "left_moment_arm_m": left_point - target_position,
                "contact_chord_unit_vector": (right_point - left_point) / np.linalg.norm(right_point - left_point),
                "chi_reported_N_m_s": acquisition.wrench_audit["rank5_unreachable_chi_missing_N_m_s"],
            },
            "energy": {
                "U_left_J": acquisition.energy_audit["U_left_minus_J"],
                "U_right_J": acquisition.energy_audit["U_right_minus_J"],
                "D_projection_reported_J": acquisition.energy_audit["D_projection_J"],
                "D_switch_reported_J": acquisition.energy_audit["D_switch_J"],
            },
        },
        "active": {
            "service_state_29": service_state,
            "target_state_13": target_state,
            "reported_linear_momentum_drift_N_s": active.sample_ledgers["linear_momentum_drift_N_s"].copy(),
            "reported_angular_momentum_drift_N_m_s": active.sample_ledgers["angular_momentum_drift_N_m_s"].copy(),
            "reported_energy_drift_J": active.sample_ledgers["energy_plus_dissipation_drift_J"].copy(),
            "contact_force_N": active.sample_ledgers["contact_force_while_active_N"].copy(),
            "contact_torque_N_m": active.sample_ledgers["contact_torque_while_active_N_m"].copy(),
            "contact_calls": [
                {"phase": "ACTIVE", "sample_index": index, "enabled_argument": False}
                for index in range(len(active.time_s))
            ],
            "terminal_status": active.terminal_status,
        },
        "release": {
            "service_at_release": _service_to_active_vector(release_service),
            "release_time_s": release_time,
            "release_mass": release_mass,
            "z_before": np.asarray(mapping["z_before"], dtype=float),
            "z_after": np.asarray(mapping["z_after"], dtype=float),
            "post_release": post_release,
        },
        "clearance_fixture": {
            "acquisition_time_s": clearance_acquisition_time,
            "time_s": clearance_time,
            "left_gap_m": clearance_left_gap, "right_gap_m": clearance_right_gap,
            "left_gap_rate_m_s": clearance_left_rate, "right_gap_rate_m_s": clearance_right_rate,
            "reported": clearance_report,
        },
        "governance": {
            "physical_lock": False, "held_capture": False, "current_system": False,
            "formal_nc19": False, "owner": False, "production": False,
            "release": False, "next_stage": False,
        },
        "physical_inputs": {
            "left_contact_frame": None, "right_contact_frame": None,
            "lock_transform": None, "stiffness": None, "damping": None,
            "retention": None, "release_energy": None,
        },
    }


def _gate_candidate(candidate: dict[str, Any]) -> list[str]:
    """Independently recompute the Gate from raw bytes, matrices and traces."""

    failures: list[str] = []

    def add(check_id: str) -> None:
        if check_id not in failures:
            failures.append(check_id)

    source = candidate["source"]
    payload = bytes(source["payload"])
    if len(payload) != int(source["expected_bytes"]) or hashlib.sha256(payload).hexdigest().upper() != str(source["expected_sha256"]).upper():
        add("B4E-SRC-01")

    first_trigger: int | None = None
    for record in candidate["trigger"]["records"]:
        if record["aborted"] and first_trigger is None:
            break
        if record["qualifies"] and record["all_ledgers_closed"]:
            first_trigger = int(record["index"])
            break
    if first_trigger is None or int(candidate["trigger"]["selected_index"]) != first_trigger:
        add("B4E-TRG-01")

    raw = candidate["acquisition"]
    j_c = np.asarray(raw["J_c"], dtype=float); embedding = np.asarray(raw["L"], dtype=float)
    d = np.asarray(raw["D"], dtype=float); s_eta = np.asarray(raw["S_eta"], dtype=float); s_z = np.asarray(raw["S_z"], dtype=float)
    try:
        j_hat = scipy_linalg.solve(s_z.T, (d @ j_c).T, assume_a="gen").T
        l_hat = scipy_linalg.solve(s_eta.T, (s_z @ embedding).T, assume_a="gen").T
        if _rank(j_hat) != 6:
            add("B4E-RANK-J")
        if _rank(l_hat) != 14 or float(np.linalg.norm(j_c @ embedding, ord=np.inf)) > JHAT_LHAT_TOL:
            add("B4E-RANK-L")
    except (ValueError, np.linalg.LinAlgError):
        add("B4E-RANK-J"); add("B4E-RANK-L")
    if any(
        forbidden in str(call["callable_fqn"]).lower()
        for call in raw["backend_calls"] for forbidden in ("pinv", "lstsq")
    ):
        add("B4E-SOLVE-FORBIDDEN")
    expected_d = np.diag(np.concatenate((np.ones(3), float(raw["reference_length_m"]) * np.ones(3))))
    if d.shape != (6, 6) or not np.allclose(d, expected_d, rtol=0.0, atol=1.0e-15):
        add("B4E-UNIT-SCALE")
    if any(record["matrix_id"] != "W_BAR_SCALED_DIMENSIONLESS" for record in raw["condition_records"]):
        add("B4E-UNIT-COND")

    wrench = raw["wrench"]
    p = np.asarray(wrench["linear_impulse_N_s"], dtype=float)
    ell = np.asarray(wrench["angular_impulse_N_m_s"], dtype=float)
    r_left = np.asarray(wrench["left_moment_arm_m"], dtype=float)
    chord_axis = np.asarray(wrench["contact_chord_unit_vector"], dtype=float)
    chi_expected = float(chord_axis @ (ell - np.cross(r_left, p)))
    if abs(float(wrench["chi_reported_N_m_s"]) - chi_expected) > 1.0e-12:
        add("B4E-WRENCH-CHI")

    active_raw = candidate["active"]
    if any(call["enabled_argument"] for call in active_raw["contact_calls"]):
        add("B4E-DOUBLE-ACTIVITY")
    if float(np.max(np.abs(np.asarray(active_raw["contact_force_N"], dtype=float)))) > 1.0e-12 or float(np.max(np.abs(np.asarray(active_raw["contact_torque_N_m"], dtype=float)))) > 1.0e-12:
        add("B4E-DOUBLE-ACTIVITY")

    m_minus = np.asarray(raw["M_minus"], dtype=float)
    z_minus = np.asarray(raw["z_minus"], dtype=float); z_plus = np.asarray(raw["z_plus"], dtype=float)
    t_minus = 0.5 * float(z_minus @ m_minus @ z_minus)
    t_plus = 0.5 * float(z_plus @ m_minus @ z_plus)
    d_projection = t_minus - t_plus
    energy = raw["energy"]
    u_total = float(energy["U_left_J"]) + float(energy["U_right_J"])
    if abs(float(energy["D_switch_reported_J"]) - (d_projection + u_total)) > 1.0e-12:
        add("B4E-SWITCH-U")
    if d_projection < -1.0e-12 or abs(float(energy["D_projection_reported_J"]) - d_projection) > 1.0e-12:
        add("B4E-DISSIPATION-SIGN")

    target_state_for_mass = TargetState(
        np.zeros(3), normalize_quaternion(raw["target_quaternion_wxyz"]), np.zeros(6),
    )
    expected_target_mass = _target_spatial_mass(target_state_for_mass)
    actual_target_mass = np.asarray(raw["M_target"], dtype=float)
    expected_m_minus = _block_diagonal(np.asarray(raw["M_service"], dtype=float), expected_target_mass)
    expected_attached = np.asarray(raw["M_service"], dtype=float) + np.asarray(raw["A"], dtype=float).T @ expected_target_mass @ np.asarray(raw["A"], dtype=float)
    if (
        not np.allclose(actual_target_mass, expected_target_mass, rtol=0.0, atol=1.0e-12)
        or not np.allclose(m_minus, expected_m_minus, rtol=0.0, atol=1.0e-12)
        or not np.allclose(np.asarray(raw["M_attached"], dtype=float), expected_attached, rtol=0.0, atol=1.0e-10)
    ):
        add("B4E-TARGET-MASS")

    service_states = np.asarray(active_raw["service_state_29"], dtype=float)
    target_states = np.asarray(active_raw["target_state_13"], dtype=float)
    reported_linear = np.asarray(active_raw["reported_linear_momentum_drift_N_s"], dtype=float)
    reported_angular = np.asarray(active_raw["reported_angular_momentum_drift_N_m_s"], dtype=float)
    reported_energy = np.asarray(active_raw["reported_energy_drift_J"], dtype=float)
    recomputed_linear: list[float] = []; recomputed_angular: list[float] = []; recomputed_energy: list[float] = []
    model = BranchedGripperServiceModel()
    initial_p: np.ndarray | None = None; initial_h: np.ndarray | None = None; initial_t: float | None = None
    for service_vector, target_vector in zip(service_states, target_states):
        service_state_i = _service_from_active_vector(service_vector)
        target_state_i = _target_from_post_vector(target_vector)
        service_ledger = model.momentum_energy(service_state_i); target_ledger = target_momentum_energy(target_state_i)
        total_p = service_ledger.linear_momentum_n_s + target_ledger.linear_momentum_n_s
        total_h = service_ledger.angular_momentum_about_inertial_origin_n_m_s + target_ledger.angular_momentum_about_inertial_origin_n_m_s
        total_t = service_ledger.kinetic_energy_j + target_ledger.kinetic_energy_j
        if initial_p is None:
            initial_p = total_p.copy(); initial_h = total_h.copy(); initial_t = total_t
        recomputed_linear.append(float(np.linalg.norm(total_p - initial_p)))
        recomputed_angular.append(float(np.linalg.norm(total_h - initial_h)))
        recomputed_energy.append(abs(total_t - float(initial_t)))
    if (
        reported_linear.shape != (len(recomputed_linear),)
        or reported_angular.shape != (len(recomputed_angular),)
        or reported_energy.shape != (len(recomputed_energy),)
        or not np.allclose(reported_linear, recomputed_linear, rtol=0.0, atol=1.0e-12)
        or not np.allclose(reported_angular, recomputed_angular, rtol=0.0, atol=1.0e-12)
        or not np.allclose(reported_energy, recomputed_energy, rtol=0.0, atol=1.0e-12)
        or float(np.max(reported_linear)) > 1.0e-9
        or float(np.max(reported_angular)) > 1.0e-9
        or float(np.max(reported_energy)) > 1.0e-7
    ):
        add("B4E-ACTIVE-LEDGER")

    release = candidate["release"]
    z_before = np.asarray(release["z_before"], dtype=float); z_after = np.asarray(release["z_after"], dtype=float)
    channel_slices = {
        "service_base_linear_m_s": slice(0, 3),
        "service_base_angular_rad_s": slice(3, 6),
        "service_R_joint_rad_s": slice(6, 12),
        "service_P_joint_m_s": slice(12, 14),
        "target_linear_m_s": slice(14, 17),
        "target_angular_rad_s": slice(17, 20),
    }
    native_mapping_mismatch = z_before.shape != (20,) or z_after.shape != (20,)
    if not native_mapping_mismatch:
        native_mapping_mismatch = any(
            float(np.max(np.abs(z_after[indices] - z_before[indices]))) > 1.0e-12
            for indices in channel_slices.values()
        )
    if native_mapping_mismatch:
        add("B4E-REMOVAL-JUMP")
    release_mass = np.asarray(release["release_mass"], dtype=float)
    release_energy_jump = 0.5 * float(z_after @ release_mass @ z_after - z_before @ release_mass @ z_before)
    if abs(release_energy_jump) > 1.0e-12:
        add("B4E-REMOVAL-ENERGY")

    clearance_raw = candidate["clearance_fixture"]
    recomputed_clearance = certify_earliest_clearance(
        clearance_raw["time_s"], clearance_raw["left_gap_m"], clearance_raw["right_gap_m"],
        clearance_raw["left_gap_rate_m_s"], clearance_raw["right_gap_rate_m_s"],
        acquisition_time_s=acquisition_time_from_candidate(candidate),
    )
    reported_clearance = clearance_raw["reported"]
    clearance_agrees = bool(recomputed_clearance["finite_event"]) == bool(reported_clearance["finite_event"])
    if clearance_agrees and recomputed_clearance["finite_event"]:
        clearance_agrees = (
            abs(float(recomputed_clearance["tau_c_s"]) - float(reported_clearance["tau_c_s"])) <= TIME_INTERVAL_MERGE_TOLERANCE_S
            and abs(float(recomputed_clearance["removal_time_s"]) - float(reported_clearance["removal_time_s"])) <= TIME_INTERVAL_MERGE_TOLERANCE_S
        )
    if not clearance_agrees:
        add("B4E-CLEARANCE-CONTINUITY")

    post = release["post_release"]
    post_trace = post["trace"]
    post_mapping = post["mapping"]
    post_z_before = np.asarray(post_mapping["z_before"], dtype=float)
    post_z_after = np.asarray(post_mapping["z_after"], dtype=float)
    post_service_zero = np.asarray(post_trace["service_state_29"][0], dtype=float)
    post_target_zero = np.asarray(post_trace["target_state_13"][0], dtype=float)
    post_z_zero = np.concatenate((post_service_zero[15:29], post_target_zero[7:13]))
    if (
        post_z_before.shape != (20,)
        or post_z_after.shape != (20,)
        or post_z_zero.shape != (20,)
        or any(
            float(np.max(np.abs(post_z_before[indices] - z_before[indices]))) > 1.0e-12
            or float(np.max(np.abs(post_z_after[indices] - z_after[indices]))) > 1.0e-12
            or float(np.max(np.abs(post_z_zero[indices] - z_after[indices]))) > 1.0e-12
            for indices in channel_slices.values()
        )
    ):
        add("B4E-REMOVAL-JUMP")
    if (
        any(call["enabled_argument"] for call in post_trace["contact_calls"])
        or float(np.max(np.abs(np.asarray(post_trace["contact_force_N"], dtype=float)))) > 1.0e-12
        or float(np.max(np.abs(np.asarray(post_trace["contact_torque_N_m"], dtype=float)))) > 1.0e-12
    ):
        add("B4E-POST-CONTACT")
    post_coverage = _continuous_clearance_coverage(
        post_trace["time_s"], post_trace["left_gap_m"], post_trace["right_gap_m"],
        post_trace["left_gap_rate_m_s"], post_trace["right_gap_rate_m_s"],
    )
    if not post_coverage["full_interval_certified"]:
        add("B4E-POST-REENTRY")
    if abs(float(post_trace["time_s"][-1]) - float(post_trace["time_s"][0]) - POST_RELEASE_OBSERVATION_S) > TIME_INTERVAL_MERGE_TOLERANCE_S:
        add("B4E-POST-DURATION")

    if any(bool(value) for value in candidate["governance"].values()):
        add("B4E-AUTHORITY")
    if any(value is not None for value in candidate["physical_inputs"].values()):
        add("B4E-NULL-ZEROFILL")
    return failures


def acquisition_time_from_candidate(candidate: dict[str, Any]) -> float:
    return float(candidate["clearance_fixture"]["acquisition_time_s"])


def run_negative_controls(acquisition: AcquisitionResult, active: ActiveRunResult) -> list[dict[str, Any]]:
    """Run 22 real raw-artifact mutations and bind both inputs and Gate outputs."""

    _, finite_fixture = _execute_consistent_finite_event_fixture(active)
    base = _negative_control_base(acquisition, active, finite_fixture)
    nominal_failures = _gate_candidate(base)
    if nominal_failures:
        raise SolverError(f"NEGATIVE_CONTROL_NOMINAL_NOT_CLEAN:{'|'.join(nominal_failures)}")
    nominal_hash = _json_sha(base)
    nominal_output_sha = _json_sha({"failures": nominal_failures})

    def mutated_acquisition_kkt(value: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
        raw = value["acquisition"]
        m_minus = np.asarray(raw["M_minus"], dtype=float)
        j_bar = np.asarray(raw["D"], dtype=float) @ np.asarray(raw["J_c"], dtype=float)
        kkt = np.block([[m_minus, -j_bar.T], [-j_bar, np.zeros((6, 6))]])
        rhs = np.concatenate((m_minus @ np.asarray(raw["z_minus"], dtype=float), np.zeros(6)))
        return kkt, rhs

    def rerun_mutated_post_release(value: dict[str, Any], z_after: np.ndarray) -> None:
        release = value["release"]
        service = _service_from_active_vector(np.asarray(release["service_at_release"], dtype=float))
        post = execute_post_release(
            BranchedGripperServiceModel(), finite_fixture.acquisition, service,
            release_time_s=float(release["release_time_s"]),
            method=str(release["post_release"]["method"]),
            step_s=float(release["post_release"]["step_s"]),
            z_after_override=z_after,
        )
        release["z_after"] = np.asarray(z_after, dtype=float)
        release["post_release"] = post

    def mutate_nc01(value: dict[str, Any]) -> None:
        payload = bytearray(value["source"]["payload"]); payload[len(payload) // 2] ^= 0x01
        value["source"]["payload"] = bytes(payload)

    def mutate_nc02(value: dict[str, Any]) -> None:
        qualifying = [item["index"] for item in value["trigger"]["records"] if item["qualifies"] and item["all_ledgers_closed"]]
        value["trigger"]["selected_index"] = int(qualifying[1])

    def mutate_nc03(value: dict[str, Any]) -> None:
        value["acquisition"]["J_c"][5, :] = value["acquisition"]["J_c"][4, :]
        kkt, rhs = mutated_acquisition_kkt(value)
        value["acquisition"]["z_plus"] = (np.linalg.pinv(kkt) @ rhs)[:20]
        value["acquisition"]["backend_calls"].append({"phase": "ACQUISITION_MUTANT", "callable_fqn": "numpy.linalg.pinv"})

    def mutate_nc04(value: dict[str, Any]) -> None:
        value["acquisition"]["L"][:, 13] = 0.0

    def mutate_nc05(value: dict[str, Any]) -> None:
        kkt, rhs = mutated_acquisition_kkt(value)
        value["acquisition"]["z_plus"] = np.linalg.lstsq(kkt, rhs, rcond=None)[0][:20]
        value["acquisition"]["backend_calls"].append({"phase": "ACQUISITION_MUTANT", "callable_fqn": "numpy.linalg.lstsq"})

    def mutate_nc06(value: dict[str, Any]) -> None:
        value["acquisition"]["D"] = np.eye(6)

    def mutate_nc07(value: dict[str, Any]) -> None:
        value["acquisition"]["condition_records"].append({
            "matrix_id": "M_MINUS_NATIVE_MIXED_UNITS_FORBIDDEN",
            "value": float(np.linalg.cond(value["acquisition"]["M_minus"])),
        })

    def mutate_nc08(value: dict[str, Any]) -> None:
        wrench = value["acquisition"]["wrench"]
        wrench["chi_reported_N_m_s"] = float(np.asarray(wrench["contact_chord_unit_vector"]) @ np.asarray(wrench["angular_impulse_N_m_s"]))

    def mutate_nc09(value: dict[str, Any]) -> None:
        service = _service_from_active_vector(value["active"]["service_state_29"][0])
        target = _target_from_post_vector(value["active"]["target_state_13"][0])
        observations = evaluate_dual_contact(BranchedGripperServiceModel(), service, target, DualContactConfig(), enabled=True)
        value["active"]["contact_calls"][0]["enabled_argument"] = True
        value["active"]["contact_force_N"][0] = max(float(np.linalg.norm(item.service_force_inertial_n)) for item in observations)
        value["active"]["contact_torque_N_m"][0] = max(float(np.linalg.norm(item.service_shift_torque_inertial_n_m)) for item in observations)

    def mutate_nc10(value: dict[str, Any]) -> None:
        value["acquisition"]["energy"]["D_switch_reported_J"] = value["acquisition"]["energy"]["D_projection_reported_J"]

    def mutate_nc11(value: dict[str, Any]) -> None:
        energy = value["acquisition"]["energy"]
        energy["D_switch_reported_J"] = energy["D_projection_reported_J"] + 2.0 * (energy["U_left_J"] + energy["U_right_J"])

    def mutate_nc12(value: dict[str, Any]) -> None:
        energy = value["acquisition"]["energy"]
        energy["D_projection_reported_J"] = -abs(float(energy["D_projection_reported_J"]))

    def mutate_target_mass(value: dict[str, Any], multiplier: float) -> None:
        raw = value["acquisition"]
        expected = raw["M_target"].copy()
        mutated = multiplier * expected
        raw["M_target"] = mutated
        raw["M_minus"] = _block_diagonal(raw["M_service"], mutated)
        raw["M_attached"] = raw["M_service"] + raw["A"].T @ mutated @ raw["A"]

    def mutate_nc15(value: dict[str, Any]) -> None:
        middle = len(value["active"]["reported_linear_momentum_drift_N_s"]) // 2
        value["active"]["reported_linear_momentum_drift_N_s"][middle] += 1.0e-5
        value["active"]["terminal_status"] = "NOMINAL_LABEL_ILLEGALLY_RETAINED"

    def mutate_nc16(value: dict[str, Any]) -> None:
        rerun_mutated_post_release(value, finite_fixture.acquisition.z_minus.copy())

    def mutate_nc17(value: dict[str, Any]) -> None:
        z_after = np.asarray(value["release"]["z_after"], dtype=float).copy()
        z_after[14:20] = 0.0
        rerun_mutated_post_release(value, z_after)

    def mutate_nc18(value: dict[str, Any]) -> None:
        release = value["release"]
        z = release["z_before"]
        mass = release["release_mass"]
        kinetic = 0.5 * float(z @ mass @ z)
        returned = float(value["acquisition"]["energy"]["D_switch_reported_J"])
        rerun_mutated_post_release(value, math.sqrt((kinetic + returned) / kinetic) * z)

    def mutate_nc19(value: dict[str, Any]) -> None:
        ta = acquisition_time_from_candidate(value)
        value["clearance_fixture"]["time_s"] = np.array((ta + 1.0e-3, ta + 2.0e-3))
        value["clearance_fixture"]["left_gap_m"] = np.array((2.0e-6, 2.0e-6))
        value["clearance_fixture"]["right_gap_m"] = np.array((2.0e-6, 2.0e-6))
        value["clearance_fixture"]["left_gap_rate_m_s"] = np.array((-1.0e-2, 1.0e-2))
        value["clearance_fixture"]["right_gap_rate_m_s"] = np.array((-1.0e-2, 1.0e-2))

    def mutate_nc20(value: dict[str, Any]) -> None:
        service = _service_from_active_vector(value["release"]["service_at_release"])
        q = service.joint_coordinates_mixed.copy(); q[6:8] -= 2.0e-3
        penetrating = ServiceState(
            service.base_position_inertial_m, service.base_quaternion_body_to_inertial_wxyz,
            q, service.nu_s_mixed,
        )
        value["release"]["post_release"] = execute_post_release(
            BranchedGripperServiceModel(), finite_fixture.acquisition, penetrating,
            release_time_s=float(value["release"]["release_time_s"]),
            method="rk4", step_s=2.5e-4, contact_enabled=True,
        )

    definitions: list[tuple[str, str, str, Callable[[dict[str, Any]], None]]] = [
        ("B4NC01_SOURCE_BYTE_SHA_DRIFT", "source.payload(actual bytes)", "B4E-SRC-01", mutate_nc01),
        ("B4NC02_TRIGGER_INDEX_CHERRY_PICK", "trigger.selected_index(actual records)", "B4E-TRG-01", mutate_nc02),
        ("B4NC03_DUPLICATE_JC_ROW_RANK5_WITH_PINV_ATTEMPT", "acquisition.J_c+z_plus+backend_calls(actual full-KKT pinv)", "B4E-RANK-J", mutate_nc03),
        ("B4NC04_L_COLUMN_RANK_LOSS", "acquisition.L[:,13]", "B4E-RANK-L", mutate_nc04),
        ("B4NC05_ACQUISITION_PINV_OR_LSTSQ_CALL", "acquisition.z_plus+backend_calls(actual full-KKT lstsq)", "B4E-SOLVE-FORBIDDEN", mutate_nc05),
        ("B4NC06_REMOVE_LENGTH_SCALING_D_EQUALS_I", "acquisition.D", "B4E-UNIT-SCALE", mutate_nc06),
        ("B4NC07_MIXED_UNIT_CONDITION_NUMBER_REPORTED", "acquisition.condition_records(actual cond)", "B4E-UNIT-COND", mutate_nc07),
        ("B4NC08_AXIAL_MISSING_WRENCH_MISFORMULA", "acquisition.wrench.chi_reported_N_m_s", "B4E-WRENCH-CHI", mutate_nc08),
        ("B4NC09_CONTACT_AND_CONSTRAINT_SIMULTANEOUSLY_ACTIVE", "active.contact_calls+actual kernel force", "B4E-DOUBLE-ACTIVITY", mutate_nc09),
        ("B4NC10_CONTACT_POTENTIAL_OMITTED", "acquisition.energy.D_switch_reported_J", "B4E-SWITCH-U", mutate_nc10),
        ("B4NC11_CONTACT_POTENTIAL_DOUBLE_COUNTED", "acquisition.energy.D_switch_reported_J", "B4E-SWITCH-U", mutate_nc11),
        ("B4NC12_PROJECTION_DISSIPATION_SIGN_FLIP", "acquisition.energy.D_projection_reported_J", "B4E-DISSIPATION-SIGN", mutate_nc12),
        ("B4NC13_TARGET_CHILD_MASS_OMITTED", "acquisition.M_target/M_minus/M_attached", "B4E-TARGET-MASS", lambda value: mutate_target_mass(value, 0.0)),
        ("B4NC14_TARGET_CHILD_MASS_DOUBLE_COUNTED", "acquisition.M_target/M_minus/M_attached", "B4E-TARGET-MASS", lambda value: mutate_target_mass(value, 2.0)),
        ("B4NC15_ACTIVE_INTERMEDIATE_LEDGER_MUTATION_WITH_GOOD_TERMINAL_LABEL", "active.reported_linear_momentum_drift_N_s[mid]", "B4E-ACTIVE-LEDGER", mutate_nc15),
        ("B4NC16_REMOVAL_RESTORES_PRE_ACQUISITION_TWIST", "release.z_after+post_release(actual 42D rerun from pre-acquisition z)", "B4E-REMOVAL-JUMP", mutate_nc16),
        ("B4NC17_REMOVAL_ZEROES_TARGET_TWIST", "release.z_after+post_release(actual 42D rerun with target twist zero)", "B4E-REMOVAL-JUMP", mutate_nc17),
        ("B4NC18_REMOVAL_RETURNS_DISSIPATED_ENERGY", "release.z_after+post_release(actual 42D energy-scaled rerun)", "B4E-REMOVAL-ENERGY", mutate_nc18),
        ("B4NC19_CLEARANCE_DWELL_NEGATIVE_GAP_INSERTION", "clearance_fixture.actual Hermite history", "B4E-CLEARANCE-CONTINUITY", mutate_nc19),
        ("B4NC20_POST_REMOVAL_CONTACT_KERNEL_REACTIVATION", "release.post_release actual enabled=True calls", "B4E-POST-CONTACT", mutate_nc20),
    ]
    results: list[dict[str, Any]] = []
    for control_id, path, expected, mutation in definitions:
        mutant = deepcopy(base); mutation(mutant)
        failures = _gate_candidate(mutant)
        mutant_hash = _json_sha(mutant)
        results.append({
            "id": control_id, "mutation_level": "REAL_RAW_ARTIFACT_OR_EXECUTED_PATH",
            "mutated_path": path, "expected_failed_check": expected,
            "actual_failed_checks": failures, "affected_path_hit": expected in failures,
            "killed": expected in failures, "nominal_sha256": nominal_hash,
            "mutant_sha256": mutant_hash, "nominal_gate_output_sha256": nominal_output_sha,
            "mutant_gate_output_sha256": _json_sha({"failures": failures}),
            "subvariant_count": 1,
        })

    for control_id, path, expected, group in (
        ("B4NC21_PHYSICAL_OR_FORMAL_AUTHORITY_TRUE", "governance.<each-required-false>", "B4E-AUTHORITY", "governance"),
        ("B4NC22_NULL_PHYSICAL_INPUT_ZERO_FILLED", "physical_inputs.<each-required-null>", "B4E-NULL-ZEROFILL", "physical_inputs"),
    ):
        subvariants: list[dict[str, Any]] = []
        for key in base[group]:
            mutant = deepcopy(base)
            mutant[group][key] = True if group == "governance" else 0.0
            failures = _gate_candidate(mutant)
            subvariants.append({
                "field": key, "actual_failed_checks": failures,
                "killed": expected in failures,
                "mutant_input_sha256": _json_sha(mutant),
                "mutant_gate_output_sha256": _json_sha({"failures": failures}),
            })
        results.append({
            "id": control_id, "mutation_level": "EVERY_INDIVIDUAL_RAW_GOVERNANCE_FIELD",
            "mutated_path": path, "expected_failed_check": expected,
            "actual_failed_checks": sorted(set(check for item in subvariants for check in item["actual_failed_checks"])),
            "affected_path_hit": all(item["killed"] for item in subvariants),
            "killed": all(item["killed"] for item in subvariants),
            "nominal_sha256": nominal_hash,
            "mutant_sha256": _json_sha(subvariants),
            "nominal_gate_output_sha256": nominal_output_sha,
            "mutant_gate_output_sha256": _json_sha([item["mutant_gate_output_sha256"] for item in subvariants]),
            "subvariant_count": len(subvariants), "subvariants": subvariants,
        })
    if len(results) != 22 or not all(result["killed"] for result in results):
        raise SolverError("NOT_ALL_22_REAL_RAW_NEGATIVE_CONTROLS_KILLED")
    return results


def event_to_json(event: EventInput) -> dict[str, Any]:
    return {
        "run_id": event.run_id, "method": event.method, "step_s": event.step_s,
        "index": event.index, "time_s": event.time_s, "source": event.source,
        "state_label": event.state_label, "criteria": event.criteria,
        "service": {
            "base_position_inertial_m": event.service.base_position_inertial_m.tolist(),
            "base_quaternion_body_to_inertial_wxyz": event.service.base_quaternion_body_to_inertial_wxyz.tolist(),
            "joint_coordinates_mixed": event.service.joint_coordinates_mixed.tolist(),
            "nu_s_mixed": event.service.nu_s_mixed.tolist(),
        },
        "target": {
            "position_inertial_m": event.target.position_inertial_m.tolist(),
            "quaternion_body_to_inertial_wxyz": event.target.quaternion_body_to_inertial_wxyz.tolist(),
            "twist_inertial_mixed": event.target.twist_inertial_mixed.tolist(),
        },
        "left_common_contact_point_m": event.left_common_contact_point_m.tolist(),
        "right_common_contact_point_m": event.right_common_contact_point_m.tolist(),
        "left_contact_potential_J": event.left_contact_potential_j,
        "right_contact_potential_J": event.right_contact_potential_j,
        "b3_dissipation_J": event.b3_dissipation_j,
    }


def acquisition_to_json(value: AcquisitionResult, *, include_matrices: bool = True) -> dict[str, Any]:
    result = {
        "run_id": value.run_id, "acquisition_time_s": value.acquisition_time_s,
        "snapshot": {
            "name": "T_PALM_TARGET_SNAPSHOT_SYNTHETIC",
            "translation_palm_to_target_m": value.snapshot.translation_palm_to_target_m.tolist(),
            "rotation_palm_to_target": value.snapshot.rotation_palm_to_target.tolist(),
            "physical_lock_transform": False,
        },
        "reference_length_m": value.reference_length_m,
        "z_minus": value.z_minus.tolist(), "z_plus_reduced": value.z_plus_reduced.tolist(),
        "z_plus_kkt": value.z_plus_kkt.tolist(), "z_plus_schur_audit": value.z_plus_schur_audit.tolist(),
        "eta_plus": value.eta_plus.tolist(),
        "linear_impulse_N_s": value.linear_impulse_n_s.tolist(),
        "angular_impulse_N_m_s": value.angular_impulse_n_m_s.tolist(),
        "lambda_bar": value.lambda_bar.tolist(), "ranks": value.ranks,
        "metrics": value.metrics, "wrench_audit": value.wrench_audit,
        "energy_audit": value.energy_audit, "momentum_audit": value.momentum_audit,
        "backend_provenance": value.backend_provenance,
    }
    if include_matrices:
        result["matrices"] = {name: matrix.tolist() for name, matrix in value.matrices.items()}
    return result


def active_to_json(value: ActiveRunResult, *, full_trace: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {
        "run_id": value.run_id, "method": value.method, "step_s": value.step_s,
        "acquisition_time_s": value.acquisition.acquisition_time_s,
        "active_end_time_s": float(value.time_s[-1]), "sample_count": len(value.time_s),
        "maxima": value.maxima, "clearance": value.clearance,
        "terminal_status": value.terminal_status,
        "synthetic_removal_executed": value.synthetic_removal_executed,
        "post_release": value.post_release,
    }
    if full_trace:
        result["trace"] = {
            "time_s": value.time_s.tolist(), "service_position_m": value.service_position_m.tolist(),
            "service_quaternion_wxyz": value.service_quaternion_wxyz.tolist(),
            "service_joint_coordinates_mixed": value.service_joint_coordinates_mixed.tolist(),
            "eta_mixed": value.eta_mixed.tolist(), "target_position_m": value.target_position_m.tolist(),
            "target_quaternion_wxyz": value.target_quaternion_wxyz.tolist(),
            "target_twist_mixed": value.target_twist_mixed.tolist(),
            "left_gap_m": value.left_gap_m.tolist(), "right_gap_m": value.right_gap_m.tolist(),
            "left_gap_rate_m_s": value.left_gap_rate_m_s.tolist(), "right_gap_rate_m_s": value.right_gap_rate_m_s.tolist(),
            "sample_ledgers": {name: array.tolist() for name, array in value.sample_ledgers.items()},
        }
    return result
