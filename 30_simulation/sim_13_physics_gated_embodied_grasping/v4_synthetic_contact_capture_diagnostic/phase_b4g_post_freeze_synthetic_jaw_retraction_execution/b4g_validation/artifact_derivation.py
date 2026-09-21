"""Derive B4G mutation nominal payloads from byte-bound underlying artifacts.

This is deliberately an evidence-side implementation.  It imports neither the
solver, the campaign runner, nor the mutation executor.  A nominal mutation
bundle is accepted only when its payload can be rebuilt from independently
hash-verified files and the frozen contracts supplied by the caller.

The finite-event harness is treated as an untrusted raw interchange.  In
particular, its convenient top-level ``finite_event_harness_precondition`` is
never used as proof.  The event, work, removal mapping, post trace, contact
state, and mutation source payloads are rechecked from the raw histories.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .geometry_replay import (
    GeometryReplayError,
    centered_gap_jacobian,
    pad_kinematics,
    palm_kinematics,
    recompute_active_gap_rate,
    recompute_gap_rate,
    reconstruct_active_target_state_13,
)


class ArtifactDerivationError(ValueError):
    """Fail-closed malformed artifact or non-derivable nominal payload."""


@dataclass(frozen=True)
class ArtifactDerivationResult:
    """A successfully reconstructed nominal payload and its audit facts."""

    parent_id: str
    subvariant_index: int
    derived_payload: dict[str, Any]
    derived_mutant_payload: dict[str, Any]
    verified_roles: tuple[str, ...]
    verified_paths: tuple[str, ...]
    diagnostics: dict[str, Any]


_ALL_PARENTS = tuple(f"B4FNC{index:02d}" for index in range(1, 23))
_SOURCE_MANIFEST_ROLE = "EXECUTION_SOURCE_MANIFEST"
_FINITE_ROLE = "EXECUTED_FINITE_HARNESS_RAW_OUTPUT"
_DWELL_TRACE_ROLE = "MUTANT_DWELL_FORCE_TRACE"
_A2_DETECTOR_TRACE_ROLE = "A2_DETECTOR_SIX_LANE_TRACE"
_GEOMETRY_MUTANT_TRACE_ROLE = "GEOMETRY_CLIP_EXTRAPOLATE_TRACE"
_DEFAULT_CASE_PARENTS = {
    "B4FNC02", "B4FNC03", "B4FNC04", "B4FNC05", "B4FNC06",
}
_CASE_PARENTS = _DEFAULT_CASE_PARENTS | {"B4FNC21"}
_FINITE_PARENTS = {
    "B4FNC07", "B4FNC11", "B4FNC12", "B4FNC13", "B4FNC14",
}
_FINITE_DERIVATION_PARENTS = _FINITE_PARENTS | {"B4FNC08"}

_EXPECTED_ROLE_COUNTS: dict[str, Counter[str]] = {
    "B4FNC01": Counter({_SOURCE_MANIFEST_ROLE: 1, "BOUND_PARENT_SOURCE": 1, "MUTANT_RAW_BYTES": 1}),
    **{
        parent: Counter({_SOURCE_MANIFEST_ROLE: 1, "REGISTERED_CASE_METADATA": 1, "REGISTERED_CASE_RAW_NPZ": 1})
        for parent in _DEFAULT_CASE_PARENTS
    },
    **{
        parent: Counter({_SOURCE_MANIFEST_ROLE: 1, _FINITE_ROLE: 1})
        for parent in _FINITE_PARENTS
    },
    "B4FNC08": Counter({_SOURCE_MANIFEST_ROLE: 1, _FINITE_ROLE: 1, _DWELL_TRACE_ROLE: 1}),
    "B4FNC09": Counter({_SOURCE_MANIFEST_ROLE: 1, "FROZEN_CLASSIFIER_FIXTURE_CONTRACT": 1}),
    "B4FNC10": Counter({_SOURCE_MANIFEST_ROLE: 1, "FROZEN_CLASSIFIER_FIXTURE_CONTRACT": 1}),
    "B4FNC15": Counter({_SOURCE_MANIFEST_ROLE: 1, "RK4_REFERENCE_CASE_METADATA": 1, "MIDPOINT_REFERENCE_CASE_METADATA": 1}),
    "B4FNC16": Counter({_SOURCE_MANIFEST_ROLE: 1, "FROZEN_REGISTERED_SCHEDULE": 1}),
    "B4FNC18": Counter({_SOURCE_MANIFEST_ROLE: 1, "FROZEN_GOVERNANCE_CONTRACT": 1}),
    "B4FNC19": Counter({_SOURCE_MANIFEST_ROLE: 1, "FROZEN_GOVERNANCE_CONTRACT": 1}),
    "B4FNC20": Counter({_SOURCE_MANIFEST_ROLE: 1, "FROZEN_GOVERNANCE_CONTRACT": 1}),
    "B4FNC21": Counter({_SOURCE_MANIFEST_ROLE: 1, "REGISTERED_CASE_METADATA": 1, "REGISTERED_CASE_RAW_NPZ": 1, _GEOMETRY_MUTANT_TRACE_ROLE: 1}),
    "B4FNC22": Counter({_SOURCE_MANIFEST_ROLE: 1, "FROZEN_GOVERNANCE_CONTRACT": 1, "FROZEN_REGISTERED_SCHEDULE": 1}),
}

_FINITE_SOURCE_KEYS = {
    "REMOVAL_WORK_MAPPING",
    "REMOVAL_MAPPING",
    "ENERGY_MAPPING",
    "POST_RELEASE_TARGET_TRACE",
    "CONTACT_TRACE",
}

_FINITE_TOP_FIELDS = {
    "case_id", "method", "step_s", "event", "acquisition", "command", "raw",
    "clearance", "terminal_status", "geometry_domain_pass",
    "synthetic_removal_executed", "post_release", "failure", "search_endpoint",
    "physical_release_claimed", "minimum_required_force_or_work_claimed",
    "mutation_base_payload_sources", "schema", "harness_id",
    "finite_event_harness_contract", "Q_ref_N",
    "clearance_classifier_acquisition_time_s",
    "finite_event_harness_precondition", "claim_boundary",
}
_FINITE_RAW_FIELDS = {
    "time_s", "state_30_service_29_plus_signed_W_act_J",
    "applied_Q_P_left_right_N", "command_Q_14", "actuator_power_W",
    "left_gap_m", "right_gap_m", "left_gap_rate_m_s", "right_gap_rate_m_s",
    "target_position_m", "target_quaternion_wxyz", "target_twist_mixed",
    "total_linear_momentum_N_s", "total_angular_momentum_N_m_s",
    "total_kinetic_energy_J", "sample_ledgers", "stage_audits",
    "service_state_29", "signed_W_act_J", "ledger_interval_certified",
}
_EVENT_FIELDS = {
    "run_id", "method", "step_s", "index", "time_s", "source", "state_label",
    "criteria", "service", "target", "left_common_contact_point_m",
    "right_common_contact_point_m", "left_contact_potential_J",
    "right_contact_potential_J", "b3_dissipation_J",
}
_ACQUISITION_FIELDS = {
    "run_id", "acquisition_time_s", "snapshot", "reference_length_m", "z_minus",
    "z_plus_reduced", "z_plus_kkt", "z_plus_schur_audit", "eta_plus",
    "linear_impulse_N_s", "angular_impulse_N_m_s", "lambda_bar", "ranks",
    "metrics", "wrench_audit", "energy_audit", "momentum_audit",
    "backend_provenance",
}
_POST_FIELDS = {
    "release_time_s", "observation_duration_s", "method", "step_s", "mapping",
    "instrumented_trace", "maxima", "clearance", "geometry_domain_pass",
    "domain_failure", "post_release_stage_audit_count", "parent_b4e_crosscheck",
    "signed_W_act_carried_constant_J", "actuator_work_reset_on_removal",
    "post_release_generalized_force_14", "post_release_passed",
    "terminal_status", "physical_release_claimed",
}
_POST_TRACE_FIELDS = {
    "time_s", "state_42", "service_state_29", "target_state_13", "left_gap_m",
    "right_gap_m", "left_gap_rate_m_s", "right_gap_rate_m_s",
    "total_linear_momentum_N_s", "total_angular_momentum_N_m_s",
    "total_kinetic_energy_J", "contact_force_N", "contact_torque_N_m",
    "stage_audits",
}

_CLEARANCE_GAP_M = 1.0e-6
_CLEARANCE_RATE_M_S = -1.0e-6
_MINIMUM_ACTIVE_DWELL_S = 1.0e-3
_CLEARANCE_DWELL_S = 1.0e-3
_TIME_TOL_S = 1.0e-12
_PARENT_FIXTURE_RELATIVE_PATH = Path(
    "phase_b4_post_freeze_synthetic_6d_solver"
) / "evidence" / "SIM13_V4B4E_ABSTRACT_REMOVAL_FIXTURE_V1.json"
_PARENT_FIXTURE_BYTES = 167876
_PARENT_FIXTURE_SHA256 = "14DC9D22963D8F6930AF69FBFB0B0001DD4629DCFBDFFCFA3CE05FA1847C9FAB"
_MUTATION_CREDIT_BOUNDARY = (
    "mutation replay evidence only; no A1/A2 outcome, physical, current-system, "
    "formal NC19, Owner, production, release or next-stage credit"
)


def _fail(code: str, detail: Any | None = None) -> None:
    suffix = "" if detail is None else f":{detail}"
    raise ArtifactDerivationError(f"{code}{suffix}")


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, (bool, np.bool_)) and math.isfinite(float(value))


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ArtifactDerivationError("CANONICAL_JSON_INVALID") from error


def _canonical_sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest().upper()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _load_bound_parent_fixture(phase_root: Path) -> tuple[dict[str, Any], str]:
    """Load the one immutable B4E algorithm-only fixture allowed by B4G."""

    fixture_path = (phase_root.parent / _PARENT_FIXTURE_RELATIVE_PATH).resolve()
    if not fixture_path.is_file():
        _fail("FINITE_PARENT_FIXTURE_MISSING", fixture_path)
    fixture_bytes = fixture_path.stat().st_size
    fixture_sha = _sha256(fixture_path)
    if fixture_bytes != _PARENT_FIXTURE_BYTES or fixture_sha != _PARENT_FIXTURE_SHA256:
        _fail(
            "FINITE_PARENT_FIXTURE_BYTE_BINDING",
            {
                "expected_bytes": _PARENT_FIXTURE_BYTES,
                "observed_bytes": fixture_bytes,
                "expected_sha256": _PARENT_FIXTURE_SHA256,
                "observed_sha256": fixture_sha,
            },
        )
    fixture = _read_json(fixture_path)
    return fixture, fixture_sha


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("JSON_DUPLICATE_KEY", key)
        result[key] = value
    return result


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=lambda token: _fail("JSON_NONFINITE_CONSTANT", token),
        )
    except ArtifactDerivationError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ArtifactDerivationError(f"JSON_READ_FAILED:{path}") from error
    if not isinstance(value, dict):
        _fail("JSON_TOP_LEVEL_NOT_OBJECT", path)
    return value


def _inside(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _resolve_record_path(project_root: Path, declared: Any) -> Path:
    if not isinstance(declared, str) or not declared or "\x00" in declared:
        _fail("ARTIFACT_PATH_INVALID", declared)
    candidate = Path(declared)
    resolved = candidate.resolve() if candidate.is_absolute() else (project_root / candidate).resolve()
    if not _inside(project_root.resolve(), resolved):
        _fail("ARTIFACT_PATH_OUTSIDE_PROJECT", declared)
    if not resolved.is_file():
        _fail("ARTIFACT_FILE_MISSING", declared)
    return resolved


@dataclass(frozen=True)
class _VerifiedArtifact:
    role: str
    record: dict[str, Any]
    path: Path


def _verify_artifacts(
    parent_id: str,
    artifact_records: Sequence[Mapping[str, Any]],
    project_root: Path,
) -> tuple[list[_VerifiedArtifact], dict[str, list[_VerifiedArtifact]]]:
    if not isinstance(artifact_records, Sequence) or isinstance(artifact_records, (str, bytes, bytearray)):
        _fail("ARTIFACT_RECORDS_NOT_SEQUENCE")
    verified: list[_VerifiedArtifact] = []
    seen_paths: set[Path] = set()
    for index, row in enumerate(artifact_records):
        if not isinstance(row, Mapping) or set(row) != {"role", "path", "bytes", "sha256"}:
            _fail("ARTIFACT_RECORD_FIELDS", index)
        role = row.get("role")
        if not isinstance(role, str) or not role:
            _fail("ARTIFACT_ROLE_INVALID", index)
        expected_bytes = row.get("bytes")
        expected_sha = row.get("sha256")
        if not isinstance(expected_bytes, int) or isinstance(expected_bytes, bool) or expected_bytes < 0:
            _fail("ARTIFACT_BYTES_INVALID", role)
        if not isinstance(expected_sha, str) or len(expected_sha) != 64 or any(character not in "0123456789ABCDEF" for character in expected_sha):
            _fail("ARTIFACT_SHA256_INVALID", role)
        path = _resolve_record_path(project_root, row.get("path"))
        if path in seen_paths:
            _fail("ARTIFACT_PATH_DUPLICATED", path)
        seen_paths.add(path)
        if path.stat().st_size != expected_bytes:
            _fail("ARTIFACT_BYTE_COUNT_MISMATCH", role)
        if _sha256(path) != expected_sha:
            _fail("ARTIFACT_SHA256_MISMATCH", role)
        copied = {key: deepcopy(row[key]) for key in ("role", "path", "bytes", "sha256")}
        verified.append(_VerifiedArtifact(role, copied, path))

    roles = Counter(item.role for item in verified)
    if parent_id == "B4FNC17":
        fallback = Counter({_SOURCE_MANIFEST_ROLE: 1, "FROZEN_MUTATION_FALLBACK_CONTRACT": 1, "FROZEN_REGISTERED_SCHEDULE": 1, _A2_DETECTOR_TRACE_ROLE: 1})
        executed = Counter({_SOURCE_MANIFEST_ROLE: 1, "CAMPAIGN_SUMMARY": 1, "REGISTERED_A2_CASE_METADATA": 24})
        if roles not in (fallback, executed):
            _fail("ARTIFACT_ROLE_SET_MISMATCH", {"parent": parent_id, "actual": dict(roles)})
    else:
        expected = _EXPECTED_ROLE_COUNTS.get(parent_id)
        if expected is None or roles != expected:
            _fail("ARTIFACT_ROLE_SET_MISMATCH", {"parent": parent_id, "actual": dict(roles), "expected": None if expected is None else dict(expected)})
    by_role: dict[str, list[_VerifiedArtifact]] = defaultdict(list)
    for item in verified:
        by_role[item.role].append(item)
    return verified, by_role


def _one(by_role: Mapping[str, list[_VerifiedArtifact]], role: str) -> _VerifiedArtifact:
    rows = by_role.get(role, [])
    if len(rows) != 1:
        _fail("ARTIFACT_ROLE_NOT_SINGLETON", role)
    return rows[0]


def _record_without_role(item: _VerifiedArtifact) -> dict[str, Any]:
    return {key: deepcopy(item.record[key]) for key in ("path", "bytes", "sha256")}


def _load_npz_numeric(path: Path) -> dict[str, np.ndarray]:
    try:
        with np.load(path, allow_pickle=False) as archive:
            names = list(archive.files)
            if len(names) != len(set(names)):
                _fail("NPZ_DUPLICATE_MEMBER")
            arrays: dict[str, np.ndarray] = {}
            for name in names:
                value = np.asarray(archive[name])
                if value.dtype.kind not in "biuf":
                    _fail("NPZ_NONNUMERIC_DTYPE", {"name": name, "dtype": str(value.dtype)})
                if value.dtype.kind == "f" and not np.all(np.isfinite(value)):
                    _fail("NPZ_NONFINITE_ARRAY", name)
                arrays[name] = value
            return arrays
    except ArtifactDerivationError:
        raise
    except Exception as error:
        raise ArtifactDerivationError(f"NPZ_READ_FAILED:{path}") from error


def _array(arrays: Mapping[str, np.ndarray], name: str, *, shape_tail: tuple[int, ...] | None = None) -> np.ndarray:
    if name not in arrays:
        _fail("NPZ_REQUIRED_ARRAY_MISSING", name)
    value = np.asarray(arrays[name])
    if shape_tail is not None and (value.ndim < len(shape_tail) or tuple(value.shape[-len(shape_tail):]) != shape_tail):
        _fail("NPZ_ARRAY_SHAPE", {"name": name, "shape": list(value.shape)})
    return value


def _slot_for_case(schedule: Mapping[str, Any], case_id: str) -> dict[str, Any]:
    slots = schedule.get("slots")
    if not isinstance(slots, list):
        _fail("SCHEDULE_SLOTS_INVALID")
    matches = [row for row in slots if isinstance(row, dict) and row.get("case_id") == case_id]
    if len(matches) != 1:
        _fail("SCHEDULE_CASE_NOT_UNIQUE", case_id)
    return deepcopy(matches[0])


def _validate_registered_case_path(
    metadata: Mapping[str, Any], metadata_item: _VerifiedArtifact,
    npz_item: _VerifiedArtifact, project_root: Path, phase_root: Path,
    slot: Mapping[str, Any],
) -> None:
    safe = "".join(character if character.isalnum() else "_" for character in str(slot["case_id"]))
    stem = f"{int(slot['slot_index']):03d}__{safe}"
    raw_root = (phase_root / "evidence" / "raw_cases").resolve()
    if metadata_item.path != raw_root / f"{stem}.json" or npz_item.path != raw_root / f"{stem}.npz":
        _fail("CASE_ARTIFACT_NOT_OFFICIAL_RAW_SLOT_PATH", slot.get("case_id"))
    declared = metadata.get("npz_path")
    declared_path = _resolve_record_path(project_root, declared)
    if declared_path != npz_item.path:
        _fail("CASE_NPZ_PATH_MISMATCH", metadata.get("case_id"))


def _validate_official_metadata_path(
    item: _VerifiedArtifact, metadata: Mapping[str, Any],
    schedule: Mapping[str, Any], phase_root: Path,
) -> dict[str, Any]:
    slot = _slot_for_case(schedule, str(metadata.get("case_id")))
    safe = "".join(character if character.isalnum() else "_" for character in str(slot["case_id"]))
    expected = (phase_root / "evidence" / "raw_cases" / f"{int(slot['slot_index']):03d}__{safe}.json").resolve()
    if item.path != expected:
        _fail("CASE_METADATA_NOT_OFFICIAL_RAW_SLOT_PATH", metadata.get("case_id"))
    return slot


def _command_payload(
    parent_id: str,
    metadata: Mapping[str, Any],
    arrays: Mapping[str, np.ndarray],
    slot: Mapping[str, Any],
    mutation_spec: Mapping[str, Any],
    frozen_q_ref: float,
) -> dict[str, Any]:
    command = _array(arrays, "command_Q_14", shape_tail=(14,)).astype(float)
    time = _array(arrays, "time_s").astype(float)
    if command.ndim != 2 or time.ndim != 1 or len(command) != len(time) or len(time) == 0:
        _fail("COMMAND_TRACE_SHAPE")
    targets = mutation_spec.get("deterministic_targets_and_amplitudes", {})
    expected_case = targets.get("a0_slot") if parent_id == "B4FNC02" else targets.get("default_registered_forced_slot")
    if metadata.get("case_id") != expected_case:
        _fail("COMMAND_TRACE_WRONG_REGISTERED_CASE", metadata.get("case_id"))
    sample_index = 0 if parent_id == "B4FNC02" else int(np.argmax(np.sum(np.abs(command), axis=1)))
    command_parameters = metadata.get("command_parameters")
    if not isinstance(command_parameters, dict) or command_parameters.get("Q_ref_per_finger_N") != frozen_q_ref:
        _fail("COMMAND_QREF_NOT_FROZEN")
    event = metadata.get("event_provenance")
    if not isinstance(event, dict) or not _finite_number(event.get("acquisition_time_s")):
        _fail("COMMAND_ACQUISITION_TIME_INVALID")
    return {
        "trace_origin": "REGISTERED_CAMPAIGN_CASE",
        "harness_id": None,
        "harness_command": None,
        "arm": str(slot["arm"]),
        "slot": deepcopy(dict(slot)),
        "acquisition_time_s": float(event["acquisition_time_s"]),
        "sample_time_s": float(time[sample_index]),
        "Q_ref_N": float(frozen_q_ref),
        "command_parameters": deepcopy(command_parameters),
        "observed_Q_14": command[sample_index].tolist(),
        "clearance_dwell_active": False,
    }


def _geometry_payload(
    metadata: Mapping[str, Any], arrays: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    stage_service = _array(arrays, "stage_service_state_29", shape_tail=(29,)).astype(float)
    stage_p = _array(arrays, "stage_P_coordinates_m", shape_tail=(2,)).astype(float)
    stage_jac = _array(arrays, "stage_gap_jacobian_P", shape_tail=(2, 2)).astype(float)
    if stage_service.ndim != 2 or stage_p.ndim != 2 or stage_jac.ndim != 3 or not (len(stage_service) == len(stage_p) == len(stage_jac)) or len(stage_service) == 0:
        _fail("GEOMETRY_STAGE_SHAPE")
    if not np.array_equal(stage_p[0], stage_service[0, 13:15]):
        _fail("GEOMETRY_STAGE_P_NOT_BOUND_TO_SERVICE")
    acquisition = metadata.get("acquisition")
    snapshot = acquisition.get("snapshot") if isinstance(acquisition, dict) else None
    if not isinstance(snapshot, dict):
        _fail("GEOMETRY_ACQUISITION_SNAPSHOT_MISSING")
    try:
        replay = centered_gap_jacobian(stage_service[0], snapshot=snapshot, step_m=1.0e-7)
    except GeometryReplayError as error:
        raise ArtifactDerivationError(f"GEOMETRY_REPLAY_FAILED:{error}") from error
    if float(np.max(np.abs(replay.raw_gap_jacobian_p - stage_jac[0]))) > 1.0e-12:
        _fail("GEOMETRY_RAW_JACOBIAN_NOT_INDEPENDENTLY_REPLAYED")
    if replay.opening_signs != (1, 1):
        _fail("GEOMETRY_OPENING_SIGNS_NOT_REGISTERED")
    domain = metadata.get("geometry_domain")
    if not isinstance(domain, dict) or domain.get("clipping_or_extrapolation_used") is not False:
        _fail("GEOMETRY_CLIPPING_OR_EXTRAPOLATION")
    return {
        "P_coordinates_m": stage_p[0].tolist(),
        "centered_step_m": 1.0e-7,
        "raw_gap_jacobian_P": stage_jac[0].tolist(),
        "registered_signs": [1, 1],
        "consumed_signs": [1, 1],
        "clipping_used": False,
        "extrapolation_used": False,
        "terminal_status": metadata.get("terminal_status"),
    }


def _work_payload(arrays: Mapping[str, np.ndarray]) -> dict[str, Any]:
    time = _array(arrays, "time_s").astype(float)
    service = _array(arrays, "service_state_29", shape_tail=(29,)).astype(float)
    command = _array(arrays, "command_Q_14", shape_tail=(14,)).astype(float)
    work = _array(arrays, "signed_W_act_J").astype(float)
    residual = _array(arrays, "energy_minus_work_residual_J").astype(float)
    kinetic = _array(arrays, "total_kinetic_energy_J").astype(float)
    if any(value.ndim != expected for value, expected in ((time, 1), (service, 2), (command, 2), (work, 1), (residual, 1), (kinetic, 1))):
        _fail("WORK_TRACE_RANK")
    n = len(time)
    if n < 2 or any(len(value) != n for value in (service, command, work, residual, kinetic)) or np.any(np.diff(time) <= 0.0):
        _fail("WORK_TRACE_SHAPE_OR_TIME")
    if not np.all(command[:, :12] == 0.0):
        _fail("WORK_TRACE_NON_P_FORCE")
    if work[0] != 0.0:
        _fail("WORK_TRACE_INITIAL_NOT_ZERO")
    power = np.sum(command[:, 12:14] * service[:, 27:29], axis=1)
    trapezoid = np.zeros(n)
    trapezoid[1:] = np.cumsum(0.5 * (power[:-1] + power[1:]) * np.diff(time))
    if float(np.max(np.abs(work - trapezoid))) > 1.0e-7:
        _fail("WORK_TRACE_QUADRATURE_MISMATCH")
    independent_residual = np.abs((kinetic - work) - (kinetic[0] - work[0]))
    if float(np.max(np.abs(independent_residual - residual))) > 1.0e-12:
        _fail("WORK_TRACE_ENERGY_RESIDUAL_MISMATCH")
    return {
        "time_s": time.tolist(),
        "Q_P_N": command[:, 12:14].tolist(),
        "eta_P_m_s": service[:, 27:29].tolist(),
        "signed_W_act_J": work.tolist(),
        "energy_minus_work_residual_J": residual.tolist(),
    }


def _trim_poly(coefficients: Sequence[float]) -> np.ndarray:
    value = np.asarray(coefficients, dtype=float)
    scale = float(np.max(np.abs(value))) if len(value) else 0.0
    if scale == 0.0:
        return np.asarray([0.0])
    first = 0
    while first < len(value) - 1 and abs(float(value[first])) <= 1.0e-14 * scale:
        first += 1
    return value[first:]


def _roots_unit(coefficients: Sequence[float]) -> list[float]:
    value = _trim_poly(coefficients)
    if len(value) <= 1:
        return []
    roots = np.roots(value)
    result = [float(root.real) for root in roots if abs(float(root.imag)) <= 1.0e-10 and -1.0e-12 <= float(root.real) <= 1.0 + 1.0e-12]
    return sorted(set(round(min(1.0, max(0.0, item)), 14) for item in result))


def _hermite(y0: float, y1: float, d0: float, d1: float, dt: float) -> tuple[float, float, float, float]:
    return (2.0 * y0 - 2.0 * y1 + dt * (d0 + d1), -3.0 * y0 + 3.0 * y1 - dt * (2.0 * d0 + d1), dt * d0, y0)


def _clearance_all_root(
    time: np.ndarray, left_gap: np.ndarray, right_gap: np.ndarray,
    left_rate: np.ndarray, right_rate: np.ndarray, ledger: np.ndarray,
    acquisition_time: float,
) -> dict[str, Any]:
    if time.ndim != 1 or len(time) < 2 or np.any(np.diff(time) <= 0.0):
        _fail("CLEARANCE_TIME_INVALID")
    if any(value.shape != time.shape for value in (left_gap, right_gap, left_rate, right_rate)) or ledger.shape != (len(time) - 1,):
        _fail("CLEARANCE_SHAPE_INVALID")
    good: list[tuple[float, float]] = []
    for index in range(len(time) - 1):
        if not bool(ledger[index]):
            continue
        dt = float(time[index + 1] - time[index])
        polynomials = [_hermite(float(gap[index]), float(gap[index + 1]), float(rate[index]), float(rate[index + 1]), dt) for gap, rate in ((left_gap, left_rate), (right_gap, right_rate))]
        boundaries = {0.0, 1.0}
        for a, b, c, d in polynomials:
            boundaries.update(_roots_unit((a, b, c, d - _CLEARANCE_GAP_M)))
            boundaries.update(_roots_unit((3.0 * a / dt, 2.0 * b / dt, c / dt - _CLEARANCE_RATE_M_S)))
        ordered = sorted(boundaries)
        for lower, upper in zip(ordered[:-1], ordered[1:]):
            if upper - lower <= 1.0e-14:
                continue
            middle = 0.5 * (lower + upper)
            passed = True
            for a, b, c, d in polynomials:
                gap_value = ((a * middle + b) * middle + c) * middle + d
                rate_value = (3.0 * a * middle * middle + 2.0 * b * middle + c) / dt
                passed = passed and gap_value >= _CLEARANCE_GAP_M and rate_value >= _CLEARANCE_RATE_M_S
            if passed:
                good.append((float(time[index] + lower * dt), float(time[index] + upper * dt)))
    merged: list[list[float]] = []
    for lower, upper in sorted(good):
        if merged and lower <= merged[-1][1] + _TIME_TOL_S:
            merged[-1][1] = max(merged[-1][1], upper)
        else:
            merged.append([lower, upper])
    earliest = float(acquisition_time) + _MINIMUM_ACTIVE_DWELL_S
    for lower, upper in merged:
        tau = max(lower, earliest)
        if upper - tau >= _CLEARANCE_DWELL_S - _TIME_TOL_S:
            return {"finite_event": True, "tau_c_s": tau, "removal_time_s": tau + _CLEARANCE_DWELL_S, "certified_good_intervals_s": merged}
    return {"finite_event": False, "tau_c_s": None, "removal_time_s": None, "certified_good_intervals_s": merged}


def _as_real_array(value: Any, shape: tuple[int, ...] | None, name: str) -> np.ndarray:
    try:
        result = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as error:
        raise ArtifactDerivationError(f"RAW_ARRAY_INVALID:{name}") from error
    if shape is not None and result.shape != shape:
        _fail("RAW_ARRAY_SHAPE", {"name": name, "actual": list(result.shape), "expected": list(shape)})
    if not np.all(np.isfinite(result)):
        _fail("RAW_ARRAY_NONFINITE", name)
    return result


def _exact_or_close(actual: Any, expected: Any, name: str, tolerance: float = 0.0) -> None:
    left = _as_real_array(actual, None, name)
    right = _as_real_array(expected, left.shape, name)
    difference = float(np.max(np.abs(left - right))) if left.size else 0.0
    if difference > tolerance:
        _fail("RAW_NUMERIC_BINDING_MISMATCH", {"name": name, "max_abs": difference})


def _sin2(elapsed: float, duration: float) -> float:
    if duration == 0.0 or elapsed <= 0.0 or elapsed >= duration:
        return 0.0
    value = math.sin(math.pi * elapsed / duration)
    return value * value


def _expected_force(command: Mapping[str, Any], acquisition_time: float, q_ref: float, sample_time: float) -> np.ndarray:
    result = np.zeros(14)
    for column, side in ((12, "left"), (13, "right")):
        arm = command[side]
        start = acquisition_time + float(arm["delay_s"])
        result[column] = float(arm["alpha"]) * q_ref * _sin2(sample_time - start, float(arm["duration_s"]))
    return result


def _validate_active_stage_audits(
    records: Any,
    *,
    snapshot: Mapping[str, Any],
    command: Mapping[str, Any],
    acquisition_time: float,
    frozen_q_ref: float,
) -> int:
    if not isinstance(records, list) or not records:
        _fail("FINITE_RAW_ACTIVE_STAGE_AUDITS_MISSING")
    for index, row in enumerate(records):
        if not isinstance(row, dict) or row.get("accepted") is not True:
            _fail("FINITE_RAW_ACTIVE_STAGE_NOT_ACCEPTED", index)
        required = {
            "time_s", "stage_label", "P_coordinates_m_left_right",
            "raw_gap_jacobian_dimensionless", "diagonal_gap_derivatives_dimensionless",
            "opening_sign_left_right", "nominal_gap_m_left_right",
            "nominal_gap_rate_m_s_left_right", "contact_force_max_N",
            "contact_torque_max_N_m", "generalized_force_14",
            "consumed_opening_sign_left_right",
            "consumed_sigma_equals_raw_and_registered", "Q_base_and_R_exact_zero",
            "contact_kernel_enabled", "service_state_29", "stage_code",
            "mass_cholesky_min_diagonal", "actuator_power_W", "accepted",
        }
        if not required.issubset(row) or set(row) not in (required, required | {"mass_min_eigenvalue"}):
            _fail("FINITE_RAW_ACTIVE_STAGE_FIELD_SET", index)
        service = _as_real_array(row.get("service_state_29"), (29,), f"finite.stage.{index}.service")
        try:
            replay = centered_gap_jacobian(service, snapshot=snapshot, step_m=1.0e-7)
        except GeometryReplayError as error:
            raise ArtifactDerivationError(f"FINITE_RAW_ACTIVE_STAGE_GEOMETRY:{index}:{error}") from error
        if row.get("opening_sign_left_right") != [1, 1] or row.get("consumed_opening_sign_left_right") != [1, 1] or row.get("consumed_sigma_equals_raw_and_registered") is not True:
            _fail("FINITE_RAW_ACTIVE_STAGE_SIGN_BINDING", index)
        _exact_or_close(row.get("P_coordinates_m_left_right"), replay.p_coordinates_m, f"finite.stage.{index}.P")
        _exact_or_close(row.get("raw_gap_jacobian_dimensionless"), replay.raw_gap_jacobian_p, f"finite.stage.{index}.jacobian", 1.0e-12)
        _exact_or_close(row.get("diagonal_gap_derivatives_dimensionless"), replay.diagonal_derivatives, f"finite.stage.{index}.diagonal", 1.0e-12)
        _exact_or_close(row.get("nominal_gap_m_left_right"), replay.nominal_gaps_m, f"finite.stage.{index}.gaps", 1.0e-12)
        _exact_or_close(row.get("nominal_gap_rate_m_s_left_right"), replay.nominal_gap_rates_m_s, f"finite.stage.{index}.rates", 1.0e-12)
        force = _as_real_array(row.get("generalized_force_14"), (14,), f"finite.stage.{index}.force")
        expected_force = _expected_force(command, acquisition_time, frozen_q_ref, float(row["time_s"]))
        if float(np.max(np.abs(force - expected_force))) > 1.0e-15 or not np.all(force[:12] == 0.0):
            _fail("FINITE_RAW_ACTIVE_STAGE_FORCE", index)
        expected_power = float(force[12:14] @ service[27:29])
        if not _finite_number(row.get("actuator_power_W")) or abs(float(row["actuator_power_W"]) - expected_power) > 1.0e-12:
            _fail("FINITE_RAW_ACTIVE_STAGE_POWER", index)
        if row.get("Q_base_and_R_exact_zero") is not True or row.get("contact_kernel_enabled") is not False or abs(float(row.get("contact_force_max_N", math.inf))) > 1.0e-12 or abs(float(row.get("contact_torque_max_N_m", math.inf))) > 1.0e-12:
            _fail("FINITE_RAW_ACTIVE_STAGE_CONTACT_OR_CHANNEL", index)
        if not _finite_number(row.get("mass_cholesky_min_diagonal")) or float(row["mass_cholesky_min_diagonal"]) <= 0.0:
            _fail("FINITE_RAW_ACTIVE_STAGE_MASS", index)
    return len(records)


def _validate_post_stage_audits(records: Any) -> int:
    if not isinstance(records, list) or not records:
        _fail("FINITE_RAW_POST_STAGE_AUDITS_MISSING")
    required = {
        "time_s", "stage_label", "stage_code", "service_state_29",
        "target_state_13", "P_coordinates_m_left_right",
        "raw_gap_jacobian_dimensionless", "diagonal_gap_derivatives_dimensionless",
        "opening_sign_left_right", "nominal_gap_m_left_right",
        "nominal_gap_rate_m_s_left_right", "contact_force_max_N",
        "contact_torque_max_N_m", "consumed_opening_sign_left_right",
        "consumed_sigma_equals_raw_and_registered", "contact_kernel_enabled",
        "post_release_command_Q_14", "accepted", "post_release",
    }
    for index, row in enumerate(records):
        if not isinstance(row, dict) or set(row) != required or row.get("accepted") is not True or row.get("post_release") is not True:
            _fail("FINITE_RAW_POST_STAGE_FIELD_SET_OR_STATUS", index)
        service = _as_real_array(row.get("service_state_29"), (29,), f"finite.post_stage.{index}.service")
        target = _as_real_array(row.get("target_state_13"), (13,), f"finite.post_stage.{index}.target")
        try:
            replay = centered_gap_jacobian(service, independent_target_state_13=target, step_m=1.0e-7)
        except GeometryReplayError as error:
            raise ArtifactDerivationError(f"FINITE_RAW_POST_STAGE_GEOMETRY:{index}:{error}") from error
        if row.get("opening_sign_left_right") != [1, 1] or row.get("consumed_opening_sign_left_right") != [1, 1] or row.get("consumed_sigma_equals_raw_and_registered") is not True:
            _fail("FINITE_RAW_POST_STAGE_SIGN_BINDING", index)
        _exact_or_close(row.get("P_coordinates_m_left_right"), replay.p_coordinates_m, f"finite.post_stage.{index}.P")
        _exact_or_close(row.get("raw_gap_jacobian_dimensionless"), replay.raw_gap_jacobian_p, f"finite.post_stage.{index}.jacobian", 1.0e-12)
        _exact_or_close(row.get("diagonal_gap_derivatives_dimensionless"), replay.diagonal_derivatives, f"finite.post_stage.{index}.diagonal", 1.0e-12)
        _exact_or_close(row.get("nominal_gap_m_left_right"), replay.nominal_gaps_m, f"finite.post_stage.{index}.gaps", 1.0e-12)
        _exact_or_close(row.get("nominal_gap_rate_m_s_left_right"), replay.nominal_gap_rates_m_s, f"finite.post_stage.{index}.rates", 1.0e-12)
        if row.get("contact_kernel_enabled") is not False or row.get("post_release_command_Q_14") != [0.0] * 14 or abs(float(row.get("contact_force_max_N", math.inf))) > 1.0e-12 or abs(float(row.get("contact_torque_max_N_m", math.inf))) > 1.0e-12:
            _fail("FINITE_RAW_POST_STAGE_CONTACT_OR_COMMAND", index)
    return len(records)


def _finite_command_base(
    raw_payload: Mapping[str, Any], raw: Mapping[str, Any],
    mutation_spec: Mapping[str, Any], schedule: Mapping[str, Any], frozen_q_ref: float,
) -> dict[str, Any]:
    event = raw_payload.get("event")
    command = raw_payload.get("command")
    contract = mutation_spec.get("finite_event_harness")
    if not isinstance(event, dict) or not isinstance(command, dict) or not isinstance(contract, dict):
        _fail("FINITE_COMMAND_RECORD_MISSING")
    if set(command) != {"command_id", "left", "right"} or any(
        not isinstance(command.get(side), dict)
        or set(command[side]) != {"alpha", "delay_s", "duration_s"}
        for side in ("left", "right")
    ):
        _fail("FINITE_COMMAND_FIELD_SET")
    acquisition_time = event.get("time_s")
    if not _finite_number(acquisition_time):
        _fail("FINITE_COMMAND_ACQUISITION_INVALID")
    pulse = contract.get("force_pulse")
    if not isinstance(pulse, dict):
        _fail("FINITE_COMMAND_PULSE_INVALID")
    expected_command = {
        "command_id": contract.get("id"),
        "left": {"alpha": pulse.get("alpha_left"), "delay_s": 0.0, "duration_s": pulse.get("T_cmd_s")},
        "right": {"alpha": pulse.get("alpha_right"), "delay_s": 0.0, "duration_s": pulse.get("T_cmd_s")},
    }
    if command != expected_command:
        _fail("FINITE_COMMAND_NOT_FROZEN")
    time = _as_real_array(raw.get("time_s"), None, "finite.time_s")
    q = _as_real_array(raw.get("command_Q_14"), (len(time), 14), "finite.command_Q_14")
    expected_q = np.zeros_like(q)
    for row, sample_time in enumerate(time):
        for column, side in ((12, "left"), (13, "right")):
            arm = command[side]
            start = float(acquisition_time) + float(arm["delay_s"])
            expected_q[row, column] = float(arm["alpha"]) * frozen_q_ref * _sin2(float(sample_time) - start, float(arm["duration_s"]))
    if float(np.max(np.abs(q - expected_q))) > 1.0e-15:
        _fail("FINITE_COMMAND_RAW_PROFILE_MISMATCH")
    removal_time = raw_payload.get("clearance", {}).get("removal_time_s")
    if not _finite_number(removal_time) or abs(float(time[-1]) - float(removal_time)) > _TIME_TOL_S or not np.all(q[-1] == 0.0):
        _fail("FINITE_COMMAND_REMOVAL_SAMPLE_INVALID")
    targets = mutation_spec.get("deterministic_targets_and_amplitudes", {})
    slot = _slot_for_case(schedule, str(targets.get("default_registered_forced_slot")))
    command_parameters = {side: deepcopy(command[side]) for side in ("left", "right")}
    result = {
        "arm": "A1",
        "slot": slot,
        "acquisition_time_s": float(acquisition_time),
        "sample_time_s": float(removal_time),
        "Q_ref_N": float(frozen_q_ref),
        "command_parameters": command_parameters,
        "observed_Q_14": q[-1].tolist(),
        "clearance_dwell_active": True,
        "trace_origin": "FROZEN_FINITE_EVENT_HARNESS",
        "harness_id": contract.get("id"),
        "harness_command": {"force_pulse": deepcopy(pulse), "dwell_hold_N": {"left": 0.0, "right": 0.0}},
    }
    sources = raw_payload.get("mutation_base_payload_sources")
    if isinstance(sources, dict) and "COMMAND_TRACE" in sources and sources["COMMAND_TRACE"] != result:
        _fail("FINITE_COMMAND_SOURCE_PAYLOAD_MISMATCH")
    return result


def _validate_finite_raw(
    payload: Mapping[str, Any], mutation_spec: Mapping[str, Any],
    schedule: Mapping[str, Any], frozen_q_ref: float, phase_root: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    contract = mutation_spec.get("finite_event_harness")
    if payload.get("schema") != "SIM13_V4B4G_MUTATION_FINITE_HARNESS_RAW_V1" or not isinstance(contract, dict):
        _fail("FINITE_RAW_SCHEMA")
    if set(payload) != _FINITE_TOP_FIELDS:
        _fail("FINITE_RAW_TOP_FIELD_SET", {"missing": sorted(_FINITE_TOP_FIELDS - set(payload)), "extra": sorted(set(payload) - _FINITE_TOP_FIELDS)})
    if payload.get("harness_id") != contract.get("id") or payload.get("finite_event_harness_contract") != contract:
        _fail("FINITE_RAW_CONTRACT_BINDING")
    if payload.get("Q_ref_N") != frozen_q_ref:
        _fail("FINITE_RAW_QREF_BINDING")
    if payload.get("claim_boundary") != _MUTATION_CREDIT_BOUNDARY:
        _fail("FINITE_RAW_CLAIM_BOUNDARY")
    raw = payload.get("raw")
    if not isinstance(raw, dict):
        _fail("FINITE_RAW_HISTORY_MISSING")
    if set(raw) != _FINITE_RAW_FIELDS:
        _fail("FINITE_RAW_HISTORY_FIELD_SET", {"missing": sorted(_FINITE_RAW_FIELDS - set(raw)), "extra": sorted(set(raw) - _FINITE_RAW_FIELDS)})
    event = payload.get("event")
    acquisition = payload.get("acquisition")
    if not isinstance(event, dict) or set(event) != _EVENT_FIELDS:
        _fail("FINITE_RAW_EVENT_FIELD_SET")
    if not isinstance(acquisition, dict) or set(acquisition) != _ACQUISITION_FIELDS:
        _fail("FINITE_RAW_ACQUISITION_FIELD_SET")
    if event.get("run_id") != acquisition.get("run_id") or event.get("method") != payload.get("method") or event.get("step_s") != payload.get("step_s"):
        _fail("FINITE_RAW_EVENT_ACQUISITION_RUN_BINDING")
    if event.get("time_s") != acquisition.get("acquisition_time_s"):
        _fail("FINITE_RAW_EVENT_ACQUISITION_TIME_BINDING")
    if payload.get("method") not in {"rk4", "midpoint"} or not _finite_number(payload.get("step_s")) or float(payload["step_s"]) <= 0.0:
        _fail("FINITE_RAW_INTEGRATOR_INVALID")
    parent_fixture, parent_fixture_sha = _load_bound_parent_fixture(phase_root)
    if parent_fixture.get("schema") != "SIM13_V4B4E_ABSTRACT_REMOVAL_FIXTURE_V1":
        _fail("FINITE_PARENT_FIXTURE_SCHEMA")
    if parent_fixture.get("fixture_event") != event:
        _fail("FINITE_PARENT_FIXTURE_EVENT_MISMATCH")
    parent_active = parent_fixture.get("active_run")
    if not isinstance(parent_active, dict):
        _fail("FINITE_PARENT_FIXTURE_ACTIVE_RUN_MISSING")
    if (
        parent_active.get("run_id") != event.get("run_id")
        or parent_active.get("method") != payload.get("method")
        or parent_active.get("step_s") != payload.get("step_s")
        or parent_active.get("acquisition_time_s") != acquisition.get("acquisition_time_s")
    ):
        _fail("FINITE_PARENT_FIXTURE_ACTIVE_RUN_BINDING")
    parent_trace = parent_active.get("trace")
    if not isinstance(parent_trace, dict):
        _fail("FINITE_PARENT_FIXTURE_ACTIVE_TRACE_MISSING")
    if payload.get("physical_release_claimed") is not False or payload.get("minimum_required_force_or_work_claimed") is not False:
        _fail("FINITE_RAW_FORBIDDEN_CLAIM")
    time = _as_real_array(raw.get("time_s"), None, "finite.time_s")
    if time.ndim != 1 or len(time) < 2 or np.any(np.diff(time) <= 0.0):
        _fail("FINITE_RAW_TIME")
    n = len(time)
    state30 = _as_real_array(raw.get("state_30_service_29_plus_signed_W_act_J"), (n, 30), "finite.state_30")
    service = _as_real_array(raw.get("service_state_29"), (n, 29), "finite.service")
    work = _as_real_array(raw.get("signed_W_act_J"), (n,), "finite.work")
    if not np.array_equal(state30[:, :29], service) or not np.array_equal(state30[:, 29], work):
        _fail("FINITE_RAW_DUPLICATED_STATE_MISMATCH")
    event_service = event.get("service")
    if not isinstance(event_service, dict) or set(event_service) != {"base_position_inertial_m", "base_quaternion_body_to_inertial_wxyz", "joint_coordinates_mixed", "nu_s_mixed"}:
        _fail("FINITE_RAW_EVENT_SERVICE_FIELDS")
    expected_initial_configuration = np.concatenate((
        _as_real_array(event_service.get("base_position_inertial_m"), (3,), "finite.event.service.position"),
        _as_real_array(event_service.get("base_quaternion_body_to_inertial_wxyz"), (4,), "finite.event.service.quaternion"),
        _as_real_array(event_service.get("joint_coordinates_mixed"), (8,), "finite.event.service.coordinates"),
    ))
    eta_plus = _as_real_array(acquisition.get("eta_plus"), (14,), "finite.acquisition.eta_plus")
    z_plus = _as_real_array(acquisition.get("z_plus_reduced"), (20,), "finite.acquisition.z_plus")
    if not np.array_equal(service[0, :15], expected_initial_configuration) or not np.array_equal(service[0, 15:29], eta_plus) or not np.array_equal(eta_plus, z_plus[:14]):
        _fail("FINITE_RAW_INITIAL_SERVICE_PROVENANCE")
    snapshot = acquisition.get("snapshot")
    if not isinstance(snapshot, dict) or set(snapshot) != {"name", "translation_palm_to_target_m", "rotation_palm_to_target", "physical_lock_transform"} or snapshot.get("physical_lock_transform") is not False:
        _fail("FINITE_RAW_SNAPSHOT_FIELDS")
    target = np.column_stack((
        _as_real_array(raw.get("target_position_m"), (n, 3), "finite.target.position"),
        _as_real_array(raw.get("target_quaternion_wxyz"), (n, 4), "finite.target.quaternion"),
        _as_real_array(raw.get("target_twist_mixed"), (n, 6), "finite.target.twist"),
    ))
    parent_service_initial = np.concatenate((
        _as_real_array(parent_trace.get("service_position_m"), None, "parent_fixture.service_position")[0],
        _as_real_array(parent_trace.get("service_quaternion_wxyz"), None, "parent_fixture.service_quaternion")[0],
        _as_real_array(parent_trace.get("service_joint_coordinates_mixed"), None, "parent_fixture.service_joint_coordinates")[0],
        _as_real_array(parent_trace.get("eta_mixed"), None, "parent_fixture.eta")[0],
    ))
    parent_target_initial = np.concatenate((
        _as_real_array(parent_trace.get("target_position_m"), None, "parent_fixture.target_position")[0],
        _as_real_array(parent_trace.get("target_quaternion_wxyz"), None, "parent_fixture.target_quaternion")[0],
        _as_real_array(parent_trace.get("target_twist_mixed"), None, "parent_fixture.target_twist")[0],
    ))
    parent_eta_initial = _as_real_array(parent_trace.get("eta_mixed"), None, "parent_fixture.eta")[0]
    parent_time = _as_real_array(parent_trace.get("time_s"), None, "parent_fixture.time")
    if parent_time.ndim != 1 or not len(parent_time) or parent_time[0] != time[0] or parent_time[0] != float(acquisition["acquisition_time_s"]):
        _fail("FINITE_PARENT_FIXTURE_ACQUISITION_TIME_MISMATCH")
    if parent_service_initial.shape != (29,) or not np.array_equal(parent_service_initial, service[0]):
        _fail("FINITE_PARENT_FIXTURE_INITIAL_SERVICE_MISMATCH")
    if parent_target_initial.shape != (13,) or float(np.max(np.abs(parent_target_initial - target[0]))) > 1.0e-12:
        _fail("FINITE_PARENT_FIXTURE_INITIAL_TARGET_MISMATCH")
    if parent_eta_initial.shape != (14,) or float(np.max(np.abs(parent_eta_initial - eta_plus))) > 1.0e-12:
        _fail("FINITE_PARENT_FIXTURE_INITIAL_ETA_MISMATCH")
    if float(np.max(np.abs(target[0, 7:13] - z_plus[14:20]))) > 1.0e-12:
        _fail("FINITE_RAW_INITIAL_TARGET_TWIST_PROVENANCE")
    rebuilt_targets: list[np.ndarray] = []
    rebuilt_gaps: list[np.ndarray] = []
    rebuilt_rates: list[np.ndarray] = []
    try:
        for service_row in service:
            target_row = reconstruct_active_target_state_13(service_row, snapshot)
            observation = recompute_active_gap_rate(service_row, snapshot)
            rebuilt_targets.append(target_row)
            rebuilt_gaps.append(observation.gaps_m)
            rebuilt_rates.append(observation.gap_rates_m_s)
    except GeometryReplayError as error:
        raise ArtifactDerivationError(f"FINITE_RAW_ACTIVE_GEOMETRY_REPLAY_FAILED:{error}") from error
    if float(np.max(np.abs(np.asarray(rebuilt_targets) - target))) > 1.0e-12:
        _fail("FINITE_RAW_ACTIVE_TARGET_REPLAY")
    q = _as_real_array(raw.get("command_Q_14"), (n, 14), "finite.command")
    applied = _as_real_array(raw.get("applied_Q_P_left_right_N"), (n, 2), "finite.applied_P")
    if not np.array_equal(q[:, :12], np.zeros((n, 12))) or not np.array_equal(q[:, 12:14], applied):
        _fail("FINITE_RAW_COMMAND_DUPLICATION")
    power = _as_real_array(raw.get("actuator_power_W"), (n,), "finite.power")
    independent_power = np.sum(q[:, 12:14] * service[:, 27:29], axis=1)
    if float(np.max(np.abs(power - independent_power))) > 1.0e-12:
        _fail("FINITE_RAW_POWER_MISMATCH")
    if work[0] != 0.0:
        _fail("FINITE_RAW_INITIAL_WORK_NOT_ZERO")
    trapezoid = np.zeros(n)
    trapezoid[1:] = np.cumsum(0.5 * (power[:-1] + power[1:]) * np.diff(time))
    if float(np.max(np.abs(work - trapezoid))) > 1.0e-7:
        _fail("FINITE_RAW_WORK_QUADRATURE")
    if not math.isfinite(float(work[-1])) or abs(float(work[-1])) <= 1.0e-12:
        _fail("FINITE_RAW_NONZERO_WORK_PRECONDITION")
    kinetic = _as_real_array(raw.get("total_kinetic_energy_J"), (n,), "finite.kinetic")
    total_linear = _as_real_array(raw.get("total_linear_momentum_N_s"), (n, 3), "finite.linear_momentum")
    total_angular = _as_real_array(raw.get("total_angular_momentum_N_m_s"), (n, 3), "finite.angular_momentum")
    ledgers = raw.get("sample_ledgers")
    if not isinstance(ledgers, dict):
        _fail("FINITE_RAW_LEDGER_MISSING")
    required_ledgers = (
        "linear_momentum_drift_N_s", "angular_momentum_drift_N_m_s",
        "energy_minus_work_residual_J", "ideal_constraint_power_W",
        "active_contact_force_N", "active_contact_torque_N_m",
    )
    ledger_arrays = {name: _as_real_array(ledgers.get(name), (n,), f"finite.ledger.{name}") for name in required_ledgers}
    independent_linear_drift = np.linalg.norm(total_linear - total_linear[0], axis=1)
    independent_angular_drift = np.linalg.norm(total_angular - total_angular[0], axis=1)
    if float(np.max(np.abs(independent_linear_drift - ledger_arrays["linear_momentum_drift_N_s"]))) > 1.0e-12 or float(np.max(np.abs(independent_angular_drift - ledger_arrays["angular_momentum_drift_N_m_s"]))) > 1.0e-12:
        _fail("FINITE_RAW_MOMENTUM_LEDGER_MISMATCH")
    independent_energy = np.abs((kinetic - work) - (kinetic[0] - work[0]))
    if float(np.max(np.abs(independent_energy - ledger_arrays["energy_minus_work_residual_J"]))) > 1.0e-12:
        _fail("FINITE_RAW_ENERGY_MINUS_WORK_MISMATCH")
    closed = (
        (ledger_arrays["linear_momentum_drift_N_s"] <= 1.0e-9)
        & (ledger_arrays["angular_momentum_drift_N_m_s"] <= 1.0e-9)
        & (ledger_arrays["energy_minus_work_residual_J"] <= 1.0e-7)
        & (ledger_arrays["ideal_constraint_power_W"] <= 1.0e-10)
        & (ledger_arrays["active_contact_force_N"] <= 1.0e-12)
        & (ledger_arrays["active_contact_torque_N_m"] <= 1.0e-12)
    )
    command = payload.get("command")
    if not isinstance(command, dict) or not isinstance(event, dict):
        _fail("FINITE_RAW_COMMAND_EVENT_MISSING")
    command_end = max(
        float(event["time_s"]) + float(command[side]["delay_s"]) + float(command[side]["duration_s"])
        for side in ("left", "right")
    )
    active_stage_count = _validate_active_stage_audits(
        raw.get("stage_audits"), snapshot=snapshot, command=command,
        acquisition_time=float(event["time_s"]), frozen_q_ref=frozen_q_ref,
    )
    expected_interval = closed[:-1] & closed[1:] & (time[:-1] >= command_end - _TIME_TOL_S) & np.all(q[:-1] == 0.0, axis=1) & np.all(q[1:] == 0.0, axis=1)
    published_interval = np.asarray(raw.get("ledger_interval_certified"))
    if published_interval.dtype.kind != "b" or published_interval.shape != (n - 1,) or not np.array_equal(published_interval, expected_interval):
        _fail("FINITE_RAW_LEDGER_INTERVAL_MISMATCH")
    gaps = [_as_real_array(raw.get(name), (n,), f"finite.{name}") for name in ("left_gap_m", "right_gap_m", "left_gap_rate_m_s", "right_gap_rate_m_s")]
    if float(np.max(np.abs(np.asarray(rebuilt_gaps) - np.column_stack(gaps[:2])))) > 1.0e-12 or float(np.max(np.abs(np.asarray(rebuilt_rates) - np.column_stack(gaps[2:])))) > 1.0e-12:
        _fail("FINITE_RAW_ACTIVE_GAP_RATE_REPLAY")
    clearance_argument = payload.get("clearance_classifier_acquisition_time_s")
    if not _finite_number(clearance_argument):
        _fail("FINITE_RAW_CLEARANCE_ARGUMENT")
    independent_clearance = _clearance_all_root(time, gaps[0], gaps[1], gaps[2], gaps[3], expected_interval, float(clearance_argument))
    reported_clearance = payload.get("clearance")
    if not isinstance(reported_clearance, dict) or independent_clearance["finite_event"] is not True or reported_clearance.get("finite_event") is not True:
        _fail("FINITE_RAW_NO_INDEPENDENT_EVENT")
    for field in ("tau_c_s", "removal_time_s"):
        if not _finite_number(reported_clearance.get(field)) or abs(float(reported_clearance[field]) - float(independent_clearance[field])) > _TIME_TOL_S:
            _fail("FINITE_RAW_CLEARANCE_EVENT_MISMATCH", field)
    if abs(float(time[-1]) - float(independent_clearance["removal_time_s"])) > _TIME_TOL_S:
        _fail("FINITE_RAW_NOT_TRUNCATED_AT_REMOVAL")
    if payload.get("synthetic_removal_executed") is not True:
        _fail("FINITE_RAW_REMOVAL_NOT_EXECUTED")
    post = payload.get("post_release")
    if not isinstance(post, dict) or post.get("post_release_passed") is not True:
        _fail("FINITE_RAW_POST_RELEASE_NOT_PASS")
    if set(post) != _POST_FIELDS:
        _fail("FINITE_RAW_POST_FIELD_SET", {"missing": sorted(_POST_FIELDS - set(post)), "extra": sorted(set(post) - _POST_FIELDS)})
    if post.get("geometry_domain_pass") is not True or post.get("domain_failure") is not None or post.get("physical_release_claimed") is not False:
        _fail("FINITE_RAW_POST_GOVERNANCE_OR_DOMAIN")
    if post.get("actuator_work_reset_on_removal") is not False or post.get("signed_W_act_carried_constant_J") != float(work[-1]):
        _fail("FINITE_RAW_POST_WORK_CARRY")
    if post.get("post_release_generalized_force_14") != [0.0] * 14:
        _fail("FINITE_RAW_POST_FORCE_NOT_ZERO")
    mapping = post.get("mapping")
    if not isinstance(mapping, dict):
        _fail("FINITE_RAW_MAPPING_MISSING")
    mapping_fields = {"z_before", "z_after", "native_velocity_jump_maxima", "linear_impulse_N_s", "angular_impulse_N_m_s", "kinetic_energy_jump_J", "ideal_constraint_stored_energy_J", "mapping_name"}
    if set(mapping) != mapping_fields or mapping.get("mapping_name") != "EXPAND_L_ETA_THEN_COMPONENTWISE_COPY":
        _fail("FINITE_RAW_MAPPING_FIELD_SET_OR_NAME")
    z_before = _as_real_array(mapping.get("z_before"), (20,), "finite.mapping.z_before")
    z_after = _as_real_array(mapping.get("z_after"), (20,), "finite.mapping.z_after")
    if not np.array_equal(z_before, z_after):
        _fail("FINITE_RAW_MAPPING_Z_JUMP")
    mapping_linear_impulse = _as_real_array(mapping.get("linear_impulse_N_s"), (3,), "finite.mapping.linear_impulse")
    mapping_angular_impulse = _as_real_array(mapping.get("angular_impulse_N_m_s"), (3,), "finite.mapping.angular_impulse")
    if float(max(np.max(np.abs(mapping_linear_impulse)), np.max(np.abs(mapping_angular_impulse)))) > 1.0e-12:
        _fail("FINITE_RAW_MAPPING_IMPULSE_ABOVE_TOLERANCE")
    if mapping.get("kinetic_energy_jump_J") != 0.0 or mapping.get("ideal_constraint_stored_energy_J") != 0.0:
        _fail("FINITE_RAW_MAPPING_ENERGY_JUMP")
    trace = post.get("instrumented_trace")
    if not isinstance(trace, dict):
        _fail("FINITE_RAW_POST_TRACE_MISSING")
    if set(trace) != _POST_TRACE_FIELDS:
        _fail("FINITE_RAW_POST_TRACE_FIELD_SET", {"missing": sorted(_POST_TRACE_FIELDS - set(trace)), "extra": sorted(set(trace) - _POST_TRACE_FIELDS)})
    post_stage_count = _validate_post_stage_audits(trace.get("stage_audits"))
    if post.get("post_release_stage_audit_count") != post_stage_count:
        _fail("FINITE_RAW_POST_STAGE_COUNT")
    post_time = _as_real_array(trace.get("time_s"), None, "finite.post.time")
    m = len(post_time)
    if post_time.ndim != 1 or m < 2 or np.any(np.diff(post_time) <= 0.0) or abs(float(post_time[-1] - post_time[0]) - 0.005) > _TIME_TOL_S:
        _fail("FINITE_RAW_POST_TIME")
    state42 = _as_real_array(trace.get("state_42"), (m, 42), "finite.post.state42")
    post_service = _as_real_array(trace.get("service_state_29"), (m, 29), "finite.post.service")
    post_target = _as_real_array(trace.get("target_state_13"), (m, 13), "finite.post.target")
    if not np.array_equal(state42[:, :29], post_service) or not np.array_equal(state42[:, 29:42], post_target):
        _fail("FINITE_RAW_POST_STATE_DUPLICATION")
    if not np.array_equal(post_service[0], service[-1]):
        _fail("FINITE_RAW_POST_SERVICE_MAPPING")
    if not np.array_equal(z_before[:14], post_service[0, 15:29]) or not np.array_equal(z_before[14:20], post_target[0, 7:13]):
        _fail("FINITE_RAW_POST_NATIVE_Z_MAPPING")
    post_linear = _as_real_array(trace.get("total_linear_momentum_N_s"), (m, 3), "finite.post.linear_momentum")
    post_angular = _as_real_array(trace.get("total_angular_momentum_N_m_s"), (m, 3), "finite.post.angular_momentum")
    post_kinetic = _as_real_array(trace.get("total_kinetic_energy_J"), (m,), "finite.post.kinetic")
    if float(np.max(np.abs(mapping_linear_impulse - (post_linear[0] - total_linear[-1])))) > 1.0e-12 or float(np.max(np.abs(mapping_angular_impulse - (post_angular[0] - total_angular[-1])))) > 1.0e-12:
        _fail("FINITE_RAW_MAPPING_IMPULSE_NOT_RAW_DERIVED")
    if abs(float(mapping["kinetic_energy_jump_J"]) - float(post_kinetic[0] - kinetic[-1])) > 1.0e-12:
        _fail("FINITE_RAW_MAPPING_ENERGY_NOT_RAW_DERIVED")
    post_force = _as_real_array(trace.get("contact_force_N"), (m,), "finite.post.contact_force")
    post_torque = _as_real_array(trace.get("contact_torque_N_m"), (m,), "finite.post.contact_torque")
    if float(max(np.max(np.abs(post_force)), np.max(np.abs(post_torque)))) > 1.0e-12:
        _fail("FINITE_RAW_POST_CONTACT_NONZERO")
    post_gaps = [_as_real_array(trace.get(name), (m,), f"finite.post.{name}") for name in ("left_gap_m", "right_gap_m", "left_gap_rate_m_s", "right_gap_rate_m_s")]
    replay_post_gaps: list[np.ndarray] = []
    replay_post_rates: list[np.ndarray] = []
    try:
        for service_row, target_row in zip(post_service, post_target):
            observation = recompute_gap_rate(service_row, target_row)
            replay_post_gaps.append(observation.gaps_m)
            replay_post_rates.append(observation.gap_rates_m_s)
    except GeometryReplayError as error:
        raise ArtifactDerivationError(f"FINITE_RAW_POST_GEOMETRY_REPLAY_FAILED:{error}") from error
    if float(np.max(np.abs(np.asarray(replay_post_gaps) - np.column_stack(post_gaps[:2])))) > 1.0e-12 or float(np.max(np.abs(np.asarray(replay_post_rates) - np.column_stack(post_gaps[2:])))) > 1.0e-12:
        _fail("FINITE_RAW_POST_GAP_RATE_REPLAY")
    post_clearance = _clearance_all_root(
        post_time, post_gaps[0], post_gaps[1], post_gaps[2], post_gaps[3],
        np.ones(m - 1, dtype=bool), float(post_time[0]) - _MINIMUM_ACTIVE_DWELL_S,
    )
    # Full post-clearance is stricter than the dwell predicate: every interval
    # must belong to one continuous admissible component.
    intervals = post_clearance["certified_good_intervals_s"]
    if not intervals or len(intervals) != 1 or intervals[0][0] > float(post_time[0]) + _TIME_TOL_S or intervals[0][1] < float(post_time[-1]) - _TIME_TOL_S or post.get("clearance", {}).get("full_interval_certified") is not True:
        _fail("FINITE_RAW_POST_CLEARANCE_NOT_FULL")
    maxima = post.get("maxima")
    if not isinstance(maxima, dict):
        _fail("FINITE_RAW_POST_MAXIMA_MISSING")
    independent_post_linear_drift = np.linalg.norm(post_linear - post_linear[0], axis=1)
    independent_post_angular_drift = np.linalg.norm(post_angular - post_angular[0], axis=1)
    independent_post_energy_drift = np.abs(post_kinetic - post_kinetic[0])
    expected_maxima = {
        "linear_momentum_drift_N_s": float(np.max(independent_post_linear_drift)),
        "angular_momentum_drift_N_m_s": float(np.max(independent_post_angular_drift)),
        "energy_drift_J": float(np.max(independent_post_energy_drift)),
        "contact_force_N": float(np.max(post_force)),
        "contact_torque_N_m": float(np.max(post_torque)),
    }
    if set(maxima) != set(expected_maxima) or any(abs(float(maxima[key]) - value) > 1.0e-12 for key, value in expected_maxima.items()):
        _fail("FINITE_RAW_POST_MAXIMA_NOT_RAW_DERIVED")
    crosscheck = post.get("parent_b4e_crosscheck")
    if not isinstance(crosscheck, dict) or crosscheck.get("passed") is not True:
        _fail("FINITE_RAW_PARENT_CROSSCHECK")
    crosscheck_terminal = max(float(crosscheck.get("terminal_service_state_max_error", math.inf)), float(crosscheck.get("terminal_target_state_max_error", math.inf)))
    if not math.isfinite(crosscheck_terminal) or crosscheck_terminal > 1.0e-12 or float(crosscheck.get("mapping_z_before_max_error", math.inf)) > 1.0e-12:
        _fail("FINITE_RAW_PARENT_CROSSCHECK_ERROR")
    sources = payload.get("mutation_base_payload_sources")
    if not isinstance(sources, dict) or not _FINITE_SOURCE_KEYS.issubset(sources):
        _fail("FINITE_RAW_MUTATION_SOURCES_MISSING")
    if set(sources) not in (_FINITE_SOURCE_KEYS, _FINITE_SOURCE_KEYS | {"COMMAND_TRACE"}):
        _fail("FINITE_RAW_MUTATION_SOURCE_FIELD_SET", sorted(set(sources)))
    removal_work = sources["REMOVAL_WORK_MAPPING"]
    expected_work = {"finite_removal_event": True, "W_before_removal_J": float(work[-1]), "W_after_mapping_J": float(work[-1])}
    if removal_work != expected_work:
        _fail("FINITE_RAW_REMOVAL_WORK_SOURCE")
    removal_mapping = sources["REMOVAL_MAPPING"]
    if not isinstance(removal_mapping, dict) or removal_mapping != mapping:
        _fail("FINITE_RAW_REMOVAL_MAPPING_SOURCE")
    removal_base = {field: deepcopy(mapping[field]) for field in ("z_before", "z_after", "linear_impulse_N_s", "angular_impulse_N_m_s", "kinetic_energy_jump_J", "ideal_constraint_stored_energy_J")}
    energy = sources["ENERGY_MAPPING"]
    if not isinstance(energy, dict):
        _fail("FINITE_RAW_ENERGY_SOURCE")
    mass = _as_real_array(energy.get("mass_20x20"), (20, 20), "finite.energy.mass")
    if float(np.max(np.abs(mass - mass.T))) > 1.0e-12:
        _fail("FINITE_RAW_ENERGY_MASS_NOT_SYMMETRIC")
    try:
        np.linalg.cholesky(mass)
    except np.linalg.LinAlgError as error:
        raise ArtifactDerivationError("FINITE_RAW_ENERGY_MASS_NOT_POSITIVE_DEFINITE") from error
    acquisition = payload.get("acquisition")
    d_switch = acquisition.get("energy_audit", {}).get("D_switch_J") if isinstance(acquisition, dict) else None
    expected_energy = {"z_before": z_before.tolist(), "z_after": z_before.tolist(), "mass_20x20": mass.tolist(), "D_switch_J": d_switch, "reported_kinetic_increment_J": 0.0}
    if energy != expected_energy:
        _fail("FINITE_RAW_ENERGY_SOURCE_BINDING")
    post_source = sources["POST_RELEASE_TARGET_TRACE"]
    expected_post_source = {
        "time_s": post_time.tolist(),
        "independent_target_state_13": post_target.tolist(),
        "candidate_target_state_13": post_target.tolist(),
        "candidate_target_source": "INDEPENDENT_13D_POST_STATE",
        "parent_crosscheck_terminal_max_abs": crosscheck_terminal,
    }
    if post_source != expected_post_source:
        _fail("FINITE_RAW_POST_TARGET_SOURCE")
    contact_source = sources["CONTACT_TRACE"]
    expected_contact = {"contact_kernel_enabled": False, "contact_force_N": [[0.0, 0.0, 0.0]] * 2, "contact_torque_N_m": [[0.0, 0.0, 0.0]] * 2}
    if contact_source != expected_contact:
        _fail("FINITE_RAW_CONTACT_SOURCE")
    command_base = _finite_command_base(payload, raw, mutation_spec, schedule, frozen_q_ref)
    independently_derived_precondition = {
        "finite_removal_event": True,
        "synthetic_removal_executed": True,
        "removal_time_s": float(independent_clearance["removal_time_s"]),
        "W_act_at_removal_J": float(work[-1]),
        "abs_W_act_at_removal_J": abs(float(work[-1])),
        "post_release_passed": True,
    }
    published_precondition = payload.get("finite_event_harness_precondition")
    if not isinstance(published_precondition, dict):
        _fail("FINITE_RAW_PUBLISHED_PRECONDITION_MISSING")
    for field, expected in independently_derived_precondition.items():
        if published_precondition.get(field) != expected:
            _fail("FINITE_RAW_PUBLISHED_PRECONDITION_DISAGREES", field)
    bases = {
        "B4FNC07": expected_work,
        "B4FNC08": command_base,
        "B4FNC11": removal_base,
        "B4FNC12": expected_energy,
        "B4FNC13": expected_post_source,
        "B4FNC14": expected_contact,
    }
    return bases, {"finite_event_independently_recomputed": True, "parent_fixture_sha256": parent_fixture_sha, "abs_work_J": abs(float(work[-1])), "removal_time_s": float(independent_clearance["removal_time_s"]), "post_sample_count": m, "active_stage_count": active_stage_count, "post_stage_count": post_stage_count}


def _fixture_payload(parent_id: str, mutation_spec: Mapping[str, Any]) -> dict[str, Any]:
    targets = mutation_spec.get("deterministic_targets_and_amplitudes")
    if not isinstance(targets, dict):
        _fail("MUTATION_TARGETS_INVALID")
    key = "single_side_classifier_fixture" if parent_id == "B4FNC09" else "endpoint_only_classifier_fixture"
    fixture = targets.get(key)
    canonical = fixture.get("canonical_payload") if isinstance(fixture, dict) else None
    if not isinstance(canonical, dict) or _canonical_sha(canonical) != fixture.get("canonical_payload_sha256"):
        _fail("CLASSIFIER_FIXTURE_HASH_MISMATCH", key)
    time = _as_real_array(canonical.get("time_s"), None, "fixture.time")
    ledger = np.ones(len(time) - 1, dtype=bool)
    clearance = _clearance_all_root(
        time,
        _as_real_array(canonical.get("left_gap_m"), time.shape, "fixture.left_gap"),
        _as_real_array(canonical.get("right_gap_m"), time.shape, "fixture.right_gap"),
        _as_real_array(canonical.get("left_gap_rate_m_s"), time.shape, "fixture.left_rate"),
        _as_real_array(canonical.get("right_gap_rate_m_s"), time.shape, "fixture.right_rate"),
        ledger, float(canonical["acquisition_time_s"]),
    )
    if clearance["finite_event"] is not False:
        _fail("CLASSIFIER_FIXTURE_NOMINAL_NOT_NEGATIVE", key)
    return {
        **deepcopy(canonical),
        "ledger_interval_certified": [True] * (len(time) - 1),
        "observed_finite_event": False,
        "classifier_mode": "BILATERAL_HERMITE_ALL_ROOT_EARLIEST_DWELL",
    }


def _reference_row(metadata: Mapping[str, Any]) -> dict[str, Any]:
    event = metadata.get("event_provenance")
    responses = metadata.get("responses")
    if not isinstance(event, dict) or not isinstance(responses, dict):
        _fail("REFERENCE_METADATA_FIELDS")
    return {
        "lane_id": event.get("lane_id"),
        "fresh_b3_reconstruction": event.get("fresh_b3_reconstruction"),
        "acquisition_certificate_sha256": event.get("acquisition_certificate_sha256"),
        "clearance_certificate_sha256": event.get("clearance_certificate_sha256"),
        "acquisition_time_s": event.get("acquisition_time_s"),
        "removal_time_s": event.get("removal_time_s"),
        "signed_work_J": responses.get("signed_work_terminal_J"),
        "finite_removal_event": responses.get("finite_removal_event"),
        "post_release_passed": responses.get("post_release_passed"),
        "independent_integrity_pass": responses.get("selector_case_integrity_pass"),
    }


def _governance_candidate(governance: Mapping[str, Any], mutation_spec: Mapping[str, Any]) -> dict[str, Any]:
    required_false = governance.get("required_false")
    required_null = mutation_spec.get("deterministic_targets_and_amplitudes", {}).get("nc20_required_null_fields")
    if not isinstance(required_false, dict) or not all(value is False for value in required_false.values()) or not isinstance(required_null, list):
        _fail("GOVERNANCE_CONTRACT_INVALID")
    if required_null != governance.get("required_null_physical_inputs"):
        _fail("GOVERNANCE_NULL_LIST_MISMATCH")
    return {
        **{field: False for field in required_false},
        **{field: None for field in required_null},
        "reported_label": "lowest_tested_reachable_alpha_in_registered_discrete_grid",
    }


def _nc17_payload(
    by_role: Mapping[str, list[_VerifiedArtifact]], schedule: Mapping[str, Any],
    mutation_spec: Mapping[str, Any], frozen_q_ref: float, subvariant_index: int,
    phase_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if subvariant_index not in (1, 2):
        _fail("NC17_SUBVARIANT_INVALID", subvariant_index)
    fallback = "FROZEN_MUTATION_FALLBACK_CONTRACT" in by_role
    official_summary_path = (
        phase_root / "results" / "SIM13_V4B4G_CAMPAIGN_SUMMARY_V1.json"
    ).resolve()
    if not official_summary_path.is_file():
        _fail("NC17_CAMPAIGN_SUMMARY_BRANCH_AUTHORITY_MISSING")
    official_summary = _read_json(official_summary_path)
    authoritative_selected = official_summary.get("selector", {}).get(
        "selected_parent_level"
    )
    fallback_authorized = authoritative_selected is None
    if fallback != fallback_authorized:
        _fail(
            "NC17_BRANCH_NOT_AUTHORIZED_BY_CAMPAIGN_SELECTOR",
            {
                "fallback_artifacts": fallback,
                "selected_parent_level": authoritative_selected,
            },
        )
    if fallback:
        contract_artifact = _read_json(_one(by_role, "FROZEN_MUTATION_FALLBACK_CONTRACT").path)
        if contract_artifact != mutation_spec:
            _fail("NC17_FALLBACK_SPEC_ARTIFACT_MISMATCH")
        schedule_artifact = _read_json(_one(by_role, "FROZEN_REGISTERED_SCHEDULE").path)
        if schedule_artifact != schedule:
            _fail("NC17_FALLBACK_SCHEDULE_ARTIFACT_MISMATCH")
        fallback_contract = mutation_spec.get("deterministic_targets_and_amplitudes", {}).get("nc17_no_parent_harness")
        if not isinstance(fallback_contract, dict) or fallback_contract.get("all_six_lanes_required") is not True:
            _fail("NC17_FALLBACK_CONTRACT_INVALID")
        parent = {"alpha": float(fallback_contract["parent_alpha"]), "command_duration_s": float(fallback_contract["parent_T_cmd_s"]), "Q_ref_N": float(frozen_q_ref)}
    else:
        summary_item = _one(by_role, "CAMPAIGN_SUMMARY")
        if summary_item.path != official_summary_path:
            _fail("NC17_CAMPAIGN_SUMMARY_NOT_OFFICIAL_PATH")
        summary = _read_json(summary_item.path)
        if summary != official_summary:
            _fail("NC17_CAMPAIGN_SUMMARY_BRANCH_AUTHORITY_DRIFT")
        selected = summary.get("selector", {}).get("selected_parent_level")
        if not isinstance(selected, dict) or not _finite_number(selected.get("alpha")):
            _fail("NC17_SELECTED_PARENT_MISSING")
        duration = selected.get("command_duration_s", selected.get("tested_duration_s"))
        if not _finite_number(duration):
            _fail("NC17_SELECTED_DURATION_MISSING")
        parent = {"alpha": float(selected["alpha"]), "command_duration_s": float(duration), "Q_ref_N": float(frozen_q_ref)}
        items = by_role.get("REGISTERED_A2_CASE_METADATA", [])
        rows = [_read_json(item.path) for item in items]
        if len(rows) != 24 or len({row.get("case_id") for row in rows}) != 24:
            _fail("NC17_A2_METADATA_COUNT_OR_UNIQUENESS")
        expected_a2 = [slot for slot in schedule.get("slots", []) if isinstance(slot, dict) and slot.get("arm") == "A2"]
        if len(expected_a2) != 24 or {row.get("case_id") for row in rows} != {row.get("case_id") for row in expected_a2}:
            _fail("NC17_A2_METADATA_SCHEDULE_COVERAGE")
        expected_lane_variants = Counter((slot["lane_id"], slot["variant_id"]) for slot in expected_a2)
        if expected_lane_variants != Counter({(lane, variant): 1 for lane in schedule.get("lane_order", []) for variant in ("RIGHT_HALF_DELAY", "LEFT_HALF_DELAY_MIRROR", "RIGHT_COMMAND_OFF", "LEFT_COMMAND_OFF_MIRROR")}):
            _fail("NC17_A2_SCHEDULE_NOT_SIX_BY_FOUR")
        definitions = {
            "RIGHT_HALF_DELAY": ((1.0, 0.0), (0.5, 0.005)),
            "LEFT_HALF_DELAY_MIRROR": ((0.5, 0.005), (1.0, 0.0)),
            "RIGHT_COMMAND_OFF": ((1.0, 0.0), (0.0, 0.0)),
            "LEFT_COMMAND_OFF_MIRROR": ((0.0, 0.0), (1.0, 0.0)),
        }
        for item, row in zip(items, rows):
            official_slot = _validate_official_metadata_path(item, row, schedule, phase_root)
            if row.get("arm") != "A2" or row.get("execution_status") != "EXECUTED_FRESH_REGISTERED_SLOT" or row.get("registered_slot") != official_slot:
                _fail("NC17_A2_METADATA_NOT_FRESH_BOUND", row.get("case_id"))
            parameters = row.get("command_parameters")
            variant = str(official_slot.get("variant_id"))
            left_definition, right_definition = definitions[variant]
            expected_parameters = {
                "Q_ref_per_finger_N": frozen_q_ref,
                "only_nonzero_generalized_force_indices_zero_based": [12, 13],
                "left": {"alpha": float(selected["alpha"]) * left_definition[0], "delay_s": left_definition[1], "duration_s": float(duration)},
                "right": {"alpha": float(selected["alpha"]) * right_definition[0], "delay_s": right_definition[1], "duration_s": float(duration)},
                "physical_actuator_force_capacity_N": None,
                "selected_parent_level": deepcopy(selected),
            }
            if not isinstance(parameters, dict) or parameters != expected_parameters:
                _fail("NC17_A2_METADATA_QREF", row.get("case_id"))
    lanes = schedule.get("lane_order")
    if not isinstance(lanes, list) or len(lanes) != 6 or len(set(lanes)) != 6:
        _fail("NC17_SIX_LANE_ORDER_INVALID")
    alpha_force = parent["alpha"] * frozen_q_ref
    definitions = (
        ("HALF_DELAY", "RIGHT_HALF_DELAY", "LEFT_HALF_DELAY_MIRROR", 0.5),
        ("COMMAND_OFF", "RIGHT_COMMAND_OFF", "LEFT_COMMAND_OFF_MIRROR", 0.0),
    )
    pair, right, left, ratio = definitions[subvariant_index - 1]
    lane_rows = [
        {"lane_id": lane, "right_Q_2": [alpha_force, ratio * alpha_force], "left_mirror_Q_2": [ratio * alpha_force, alpha_force]}
        for lane in lanes
    ]
    return {
        "lanes": lane_rows,
        "pair_kind": pair,
        "parent_level": parent,
        "left_variant": left,
        "right_variant": right,
    }, {"fallback": fallback, "lane_count": 6}


def _subvariant_count(
    parent_id: str, mutation_spec: Mapping[str, Any], subvariant_index: int,
) -> int:
    parents = mutation_spec.get("required_parent_ids")
    counts = mutation_spec.get("subvariant_counts_by_parent")
    if parents != list(_ALL_PARENTS) or not isinstance(counts, list) or len(counts) != len(_ALL_PARENTS):
        _fail("MUTATION_SUBVARIANT_CONTRACT_INVALID")
    position = _ALL_PARENTS.index(parent_id)
    count = counts[position]
    if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
        _fail("MUTATION_SUBVARIANT_COUNT_INVALID", parent_id)
    if subvariant_index > count:
        _fail("SUBVARIANT_INDEX_OUT_OF_RANGE", {"parent": parent_id, "index": subvariant_index, "count": count})
    return count


def _enabled_post_contact_payload(
    service_state_29: Any, target_state_13: Any,
) -> dict[str, Any]:
    """Recompute the frozen enabled B3 contact mutation without solver imports."""

    service = _as_real_array(service_state_29, (29,), "mutant.contact.service")
    target = _as_real_array(target_state_13, (13,), "mutant.contact.target")
    forces: list[list[float]] = []
    torques: list[list[float]] = []
    for side in ("left", "right"):
        try:
            pad = pad_kinematics(service, side)
        except GeometryReplayError as error:
            raise ArtifactDerivationError(f"MUTANT_CONTACT_GEOMETRY_REPLAY_FAILED:{error}") from error
        radial = pad.position_inertial_m - target[:3]
        distance = float(np.linalg.norm(radial))
        if not math.isfinite(distance) or distance < 1.0e-12:
            _fail("MUTANT_CONTACT_DEGENERATE_RADIAL", side)
        normal = radial / distance
        gap = distance - 0.040
        penetration = max(-gap, 0.0)
        common = target[:3] + 0.040 * normal
        pad_velocity = pad.translational_jacobian_mixed @ service[15:29]
        finger_omega = pad.angular_jacobian_mixed @ service[15:29]
        service_common_velocity = pad_velocity + np.cross(
            finger_omega, common - pad.position_inertial_m,
        )
        target_common_velocity = target[7:10] + np.cross(
            target[10:13], common - target[:3],
        )
        relative = service_common_velocity - target_common_velocity
        normal_speed = float(relative @ normal)
        tangential = relative - normal_speed * normal
        tangential_speed = float(np.linalg.norm(tangential))
        if penetration > 0.0:
            closing = max(-normal_speed, 0.0)
            normal_magnitude = 8_000.0 * penetration + 12.0 * closing
            tangential_force = -0.25 * normal_magnitude * tangential / math.sqrt(
                tangential_speed**2 + (5.0e-3) ** 2
            )
        else:
            normal_magnitude = 0.0
            tangential_force = np.zeros(3)
        force = normal_magnitude * normal + tangential_force
        shift_torque = np.cross(common - pad.position_inertial_m, force)
        forces.append(force.tolist())
        torques.append(shift_torque.tolist())
    return {
        "contact_kernel_enabled": True,
        "contact_force_N": forces,
        "contact_torque_N_m": torques,
    }


def _reconstruct_attached_target_mutant(
    service_state_29: Any, snapshot: Mapping[str, Any],
) -> np.ndarray:
    """Match the frozen target-from-snapshot arithmetic and owned eta buffer."""

    try:
        target = reconstruct_active_target_state_13(service_state_29, snapshot)
        palm = palm_kinematics(service_state_29)
    except GeometryReplayError as error:
        raise ArtifactDerivationError(f"NC13_SNAPSHOT_TARGET_REPLAY_FAILED:{error}") from error
    translation = _as_real_array(
        snapshot.get("translation_palm_to_target_m"), (3,),
        "mutant.nc13.snapshot_translation",
    )
    offset = palm.rotation_body_to_inertial @ translation
    x, y, z = offset
    skew = np.array(((0.0, -z, y), (z, 0.0, -x), (-y, x, 0.0)))
    attachment = np.vstack((
        palm.translational_jacobian_mixed - skew @ palm.angular_jacobian_mixed,
        palm.angular_jacobian_mixed,
    ))
    # The frozen producer stores eta in an owned ServiceState array before the
    # matrix product.  Keeping that buffer ownership also fixes last-bit BLAS
    # reduction behavior for exact JSON payload equality.
    eta = _as_real_array(service_state_29, (29,), "mutant.nc13.service")[15:29].copy()
    target[7:13] = attachment @ eta
    return target


def _derive_mutant_payload(
    parent_id: str,
    subvariant_index: int,
    base_payload: Mapping[str, Any],
    by_role: Mapping[str, list[_VerifiedArtifact]],
    mutation_spec: Mapping[str, Any],
    frozen_q_ref: float,
    finite_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Rebuild the one frozen mutant payload for a parent/subvariant pair."""

    _subvariant_count(parent_id, mutation_spec, subvariant_index)
    targets = mutation_spec.get("deterministic_targets_and_amplitudes")
    if not isinstance(targets, dict):
        _fail("MUTATION_TARGETS_INVALID")
    mutant = deepcopy(dict(base_payload))

    if parent_id == "B4FNC01":
        source = _one(by_role, "BOUND_PARENT_SOURCE")
        candidate = _one(by_role, "MUTANT_RAW_BYTES")
        target = targets.get("source_byte_drift")
        if not isinstance(target, dict):
            _fail("NC01_TARGET_INVALID")
        offset = target.get("byte_offset_from_end")
        mask_hex = target.get("xor_mask_hex")
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 1 or not isinstance(mask_hex, str):
            _fail("NC01_MUTATION_TARGET_INVALID")
        try:
            mask = int(mask_hex, 16)
        except ValueError as error:
            raise ArtifactDerivationError("NC01_XOR_MASK_INVALID") from error
        source_bytes = source.path.read_bytes()
        candidate_bytes = candidate.path.read_bytes()
        if offset > len(source_bytes) or not 0 < mask <= 0xFF:
            _fail("NC01_XOR_TARGET_OUT_OF_RANGE")
        expected = bytearray(source_bytes)
        expected[len(expected) - offset] ^= mask
        if candidate_bytes != bytes(expected):
            _fail("NC01_MUTANT_BYTES_NOT_FROZEN_XOR")
        candidate_record = _record_without_role(candidate)
        mutant.update({
            "candidate_record": candidate_record,
            "candidate_bytes_path": candidate_record["path"],
            "xor_mutation": {
                "applied": True,
                "byte_offset_from_end": offset,
                "xor_mask_hex": mask_hex,
            },
        })
    elif parent_id in {"B4FNC02", "B4FNC03"}:
        q_index = 11 + subvariant_index if parent_id == "B4FNC02" else subvariant_index - 1
        injection = targets.get("force_injection_N")
        if not _finite_number(injection) or float(injection) != frozen_q_ref:
            _fail("COMMAND_MUTANT_FORCE_NOT_FROZEN_QREF")
        mutant["observed_Q_14"][q_index] += float(injection)
    elif parent_id == "B4FNC04":
        sign_mutants = targets.get("opening_sign_mutants_left_right")
        if not isinstance(sign_mutants, list) or len(sign_mutants) != 2:
            _fail("NC04_SIGN_MUTANTS_INVALID")
        signs = sign_mutants[subvariant_index - 1]
        if signs not in ([-1, 1], [1, -1]):
            _fail("NC04_SIGN_MUTANT_NOT_FROZEN", signs)
        mutant["consumed_signs"] = deepcopy(signs)
    elif parent_id in {"B4FNC05", "B4FNC06"}:
        multipliers = targets.get("work_multipliers")
        if not isinstance(multipliers, dict):
            _fail("WORK_MUTATION_MULTIPLIERS_INVALID")
        multiplier = multipliers.get("omitted" if parent_id == "B4FNC05" else "double_counted")
        expected_multiplier = 0.0 if parent_id == "B4FNC05" else 2.0
        if multiplier != expected_multiplier:
            _fail("WORK_MUTATION_MULTIPLIER_NOT_FROZEN")
        nominal_work = _as_real_array(base_payload.get("signed_W_act_J"), None, "mutant.nominal_work")
        mutant_work = float(multiplier) * nominal_work
        mutant["signed_W_act_J"] = mutant_work.tolist()
        if multiplier != 0.0:
            nominal_residual = _as_real_array(base_payload.get("energy_minus_work_residual_J"), nominal_work.shape, "mutant.nominal_residual")
            mutant["energy_minus_work_residual_J"] = np.abs(
                nominal_residual + (mutant_work - nominal_work)
            ).tolist()
    elif parent_id == "B4FNC07":
        mutant["W_after_mapping_J"] = 0.0
    elif parent_id == "B4FNC08":
        side = "left" if subvariant_index == 1 else "right"
        q_index = 12 if side == "left" else 13
        mutant["observed_Q_14"][q_index] = float(frozen_q_ref)
        mutant["harness_command"]["dwell_hold_N"][side] = float(frozen_q_ref)
    elif parent_id == "B4FNC09":
        mutant["observed_finite_event"] = True
        mutant["classifier_mode"] = "SINGLE_SIDE_LEFT" if subvariant_index == 1 else "SINGLE_SIDE_RIGHT"
    elif parent_id == "B4FNC10":
        mutant["observed_finite_event"] = True
        mutant["classifier_mode"] = "ENDPOINT_ONLY"
    elif parent_id in {"B4FNC11", "B4FNC12", "B4FNC13", "B4FNC14"}:
        if not isinstance(finite_payload, Mapping):
            _fail("FINITE_MUTANT_SOURCE_MISSING")
        acquisition = finite_payload.get("acquisition")
        post = finite_payload.get("post_release")
        sources = finite_payload.get("mutation_base_payload_sources")
        if not isinstance(acquisition, dict) or not isinstance(post, dict) or not isinstance(sources, dict):
            _fail("FINITE_MUTANT_SOURCE_FIELDS_MISSING")
        if parent_id == "B4FNC11":
            z = _as_real_array(base_payload.get("z_before"), (20,), "mutant.nc11.z")
            z_mutant = _as_real_array(acquisition.get("z_minus"), (20,), "mutant.nc11.z_minus")
            energy_source = sources.get("ENERGY_MAPPING")
            mass = _as_real_array(energy_source.get("mass_20x20") if isinstance(energy_source, dict) else None, (20, 20), "mutant.nc11.mass")
            momentum_jump = mass @ (z_mutant - z)
            kinetic_jump = 0.5 * float(z_mutant @ mass @ z_mutant - z @ mass @ z)
            mutant.update({
                "z_after": z_mutant.tolist(),
                "linear_impulse_N_s": momentum_jump[:3].tolist(),
                "angular_impulse_N_m_s": momentum_jump[3:6].tolist(),
                "kinetic_energy_jump_J": kinetic_jump,
            })
        elif parent_id == "B4FNC12":
            z = _as_real_array(base_payload.get("z_before"), (20,), "mutant.nc12.z")
            mass = _as_real_array(base_payload.get("mass_20x20"), (20, 20), "mutant.nc12.mass")
            d_switch = base_payload.get("D_switch_J")
            if not _finite_number(d_switch) or float(d_switch) <= 0.0:
                _fail("NC12_D_SWITCH_INVALID")
            direction = np.zeros(20)
            direction[12] = 1.0
            coefficient_a = 0.5 * float(direction @ mass @ direction)
            coefficient_b = float(z @ mass @ direction)
            discriminant = coefficient_b**2 + 4.0 * coefficient_a * float(d_switch)
            if coefficient_a <= 0.0 or discriminant < 0.0:
                _fail("NC12_MASS_METRIC_ROOT_NOT_REAL")
            roots = [
                (-coefficient_b - math.sqrt(discriminant)) / (2.0 * coefficient_a),
                (-coefficient_b + math.sqrt(discriminant)) / (2.0 * coefficient_a),
            ]
            beta = sorted(roots, key=lambda value: (abs(value), value < 0.0))[0]
            z_mutant = z + beta * direction
            increment = 0.5 * float(z_mutant @ mass @ z_mutant - z @ mass @ z)
            mutant.update({
                "z_after": z_mutant.tolist(),
                "reported_kinetic_increment_J": increment,
            })
        else:
            trace = post.get("instrumented_trace")
            if not isinstance(trace, dict):
                _fail("FINITE_MUTANT_POST_TRACE_MISSING")
            post_service = _as_real_array(trace.get("service_state_29"), None, "mutant.post.service")
            post_target = _as_real_array(trace.get("target_state_13"), None, "mutant.post.target")
            if post_service.ndim != 2 or post_service.shape[1:] != (29,) or post_target.shape != (len(post_service), 13):
                _fail("FINITE_MUTANT_POST_TRACE_SHAPE")
            if parent_id == "B4FNC13":
                snapshot = acquisition.get("snapshot")
                if not isinstance(snapshot, dict):
                    _fail("NC13_SNAPSHOT_MISSING")
                attached = np.asarray([
                    _reconstruct_attached_target_mutant(row, snapshot)
                    for row in post_service
                ])
                residual = float(np.max(np.abs(attached - post_target)))
                terminal = float(base_payload.get("parent_crosscheck_terminal_max_abs"))
                mutant.update({
                    "candidate_target_state_13": attached.tolist(),
                    "candidate_target_source": "ATTACHED_SNAPSHOT_RECONSTRUCTED_EVERY_SAMPLE",
                    "parent_crosscheck_terminal_max_abs": max(terminal, residual),
                })
            else:
                mutant = _enabled_post_contact_payload(post_service[0], post_target[0])
    elif parent_id == "B4FNC15":
        if subvariant_index == 1:
            mutant["rk4"] = deepcopy(base_payload["midpoint"])
        else:
            mutant["midpoint"] = deepcopy(base_payload["rk4"])
    elif parent_id == "B4FNC16":
        levels = targets.get("unregistered_levels")
        if not isinstance(levels, list) or len(levels) != 2:
            _fail("NC16_UNREGISTERED_LEVELS_INVALID")
        mutant["schedule"]["slots"].append(deepcopy(levels[subvariant_index - 1]))
    elif parent_id == "B4FNC17":
        breaks = targets.get("a2_command_breaks")
        if not isinstance(breaks, list) or len(breaks) != 2:
            _fail("NC17_COMMAND_BREAKS_INVALID")
        target = breaks[subvariant_index - 1]
        ratio_key = "mutated_ratio" if subvariant_index == 1 else "mutated_off_ratio"
        ratio = target.get(ratio_key) if isinstance(target, dict) else None
        expected_ratio = 0.75 if subvariant_index == 1 else 0.25
        if ratio != expected_ratio:
            _fail("NC17_MUTANT_RATIO_NOT_FROZEN")
        alpha_force = float(base_payload["parent_level"]["alpha"]) * frozen_q_ref
        for lane in mutant["lanes"]:
            lane["right_Q_2"][1] = float(ratio) * alpha_force
    elif parent_id == "B4FNC18":
        mutant["candidate"]["hardware_specification_released"] = True
    elif parent_id == "B4FNC19":
        fields = targets.get("nc19_required_false_fields")
        if not isinstance(fields, list) or len(fields) != 10:
            _fail("NC19_MUTANT_FIELDS_INVALID")
        mutant["candidate"][fields[subvariant_index - 1]] = True
    elif parent_id == "B4FNC20":
        fields = targets.get("nc20_required_null_fields")
        if not isinstance(fields, list) or len(fields) != 11:
            _fail("NC20_MUTANT_FIELDS_INVALID")
        mutant["candidate"][fields[subvariant_index - 1]] = 0.0
    elif parent_id == "B4FNC21":
        domain_mutants = targets.get("P_domain_mutants")
        if not isinstance(domain_mutants, list) or len(domain_mutants) != 6:
            _fail("NC21_DOMAIN_MUTANTS_INVALID")
        target = domain_mutants[subvariant_index - 1]
        if not isinstance(target, dict):
            _fail("NC21_DOMAIN_MUTANT_INVALID")
        if "side" in target:
            side = 0 if target.get("side") == "left" else 1 if target.get("side") == "right" else None
            if side is None or not _finite_number(target.get("value_m")):
                _fail("NC21_DOMAIN_COORDINATE_MUTANT_INVALID")
            mutant["P_coordinates_m"][side] = float(target["value_m"])
        elif target.get("path") == "CLIP_TO_UPPER_BOUND":
            mutant["clipping_used"] = True
        elif target.get("path") == "EXTRAPOLATE_AFTER_UPPER_BOUND":
            mutant["extrapolation_used"] = True
        else:
            _fail("NC21_DOMAIN_PATH_MUTANT_INVALID")
    elif parent_id == "B4FNC22":
        reporting = targets.get("reporting_mutants")
        if not isinstance(reporting, list) or len(reporting) != 2 or not isinstance(reporting[subvariant_index - 1], dict):
            _fail("NC22_REPORTING_MUTANTS_INVALID")
        mutant["report"].update(deepcopy(reporting[subvariant_index - 1]))
    else:  # pragma: no cover - exhaustive parent enumeration.
        _fail("MUTANT_DERIVATION_NOT_IMPLEMENTED", parent_id)

    if mutant == dict(base_payload):
        _fail("MUTANT_PAYLOAD_DOES_NOT_DIFFER", parent_id)
    return mutant


def derive_nominal_payload(
    parent_id: str,
    artifact_records: Sequence[Mapping[str, Any]],
    *,
    project_root: str | Path,
    phase_root: str | Path,
    source_bindings: Mapping[str, Any],
    mutation_spec: Mapping[str, Any],
    frozen_schedule: Mapping[str, Any],
    governance: Mapping[str, Any],
    frozen_q_ref: float,
    subvariant_index: int = 1,
) -> ArtifactDerivationResult:
    """Rebuild one nominal payload from hash-verified underlying artifacts."""

    if parent_id not in _ALL_PARENTS:
        _fail("PARENT_ID_INVALID", parent_id)
    if not isinstance(subvariant_index, int) or isinstance(subvariant_index, bool) or subvariant_index < 1:
        _fail("SUBVARIANT_INDEX_INVALID", subvariant_index)
    if not _finite_number(frozen_q_ref) or float(frozen_q_ref) <= 0.0:
        _fail("FROZEN_QREF_INVALID")
    root = Path(project_root).resolve()
    if not root.is_dir():
        _fail("PROJECT_ROOT_INVALID", root)
    phase = Path(phase_root).resolve()
    if not phase.is_dir() or not _inside(root, phase):
        _fail("PHASE_ROOT_INVALID", phase)
    verified, by_role = _verify_artifacts(parent_id, artifact_records, root)
    diagnostics: dict[str, Any] = {}
    finite_artifact: dict[str, Any] | None = None

    if parent_id == "B4FNC01":
        source = _one(by_role, "BOUND_PARENT_SOURCE")
        target = mutation_spec.get("deterministic_targets_and_amplitudes", {}).get("source_byte_drift")
        if not isinstance(target, dict):
            _fail("NC01_TARGET_INVALID")
        binding_rows = source_bindings.get("sources") if isinstance(source_bindings, Mapping) else None
        matches = [row for row in binding_rows if isinstance(row, dict) and row.get("id") == target.get("source_id")] if isinstance(binding_rows, list) else []
        if len(matches) != 1:
            _fail("NC01_BOUND_SOURCE_ID_NOT_UNIQUE")
        binding = matches[0]
        record = _record_without_role(source)
        if record != {key: binding.get(key) for key in ("path", "bytes", "sha256")} or source.path != _resolve_record_path(root, binding.get("path")):
            _fail("NC01_BOUND_PARENT_NOT_SOURCE_BINDING")
        payload = {
            "source_id": target.get("source_id"),
            "source_record": deepcopy(record),
            "candidate_record": deepcopy(record),
            "candidate_bytes_path": record["path"],
            "xor_mutation": {"applied": False, "byte_offset_from_end": int(target["byte_offset_from_end"]), "xor_mask_hex": "00"},
        }
    elif parent_id in _CASE_PARENTS:
        metadata_item = _one(by_role, "REGISTERED_CASE_METADATA")
        npz_item = _one(by_role, "REGISTERED_CASE_RAW_NPZ")
        metadata = _read_json(metadata_item.path)
        arrays = _load_npz_numeric(npz_item.path)
        case_id = metadata.get("case_id")
        slot = _slot_for_case(frozen_schedule, str(case_id))
        if metadata.get("registered_slot") != slot or metadata.get("execution_status") != "EXECUTED_FRESH_REGISTERED_SLOT":
            _fail("CASE_METADATA_SCHEDULE_OR_STATUS", case_id)
        _validate_registered_case_path(metadata, metadata_item, npz_item, root, phase, slot)
        if metadata.get("npz_bytes") != npz_item.record["bytes"] or metadata.get("npz_sha256") != npz_item.record["sha256"] or sorted(metadata.get("npz_arrays", [])) != sorted(arrays):
            _fail("CASE_NPZ_BINDING", case_id)
        if parent_id in {"B4FNC02", "B4FNC03"}:
            payload = _command_payload(parent_id, metadata, arrays, slot, mutation_spec, float(frozen_q_ref))
        elif parent_id in {"B4FNC04", "B4FNC21"}:
            targets = mutation_spec.get("deterministic_targets_and_amplitudes", {})
            if case_id != targets.get("default_registered_forced_slot"):
                _fail("GEOMETRY_WRONG_REGISTERED_CASE", case_id)
            payload = _geometry_payload(metadata, arrays)
        else:
            targets = mutation_spec.get("deterministic_targets_and_amplitudes", {})
            if case_id != targets.get("default_registered_forced_slot"):
                _fail("WORK_WRONG_REGISTERED_CASE", case_id)
            payload = _work_payload(arrays)
    elif parent_id in _FINITE_DERIVATION_PARENTS:
        finite_artifact = _read_json(_one(by_role, _FINITE_ROLE).path)
        bases, diagnostics = _validate_finite_raw(
            finite_artifact, mutation_spec, frozen_schedule, float(frozen_q_ref), phase,
        )
        payload = bases[parent_id]
    elif parent_id in {"B4FNC09", "B4FNC10"}:
        artifact_spec = _read_json(_one(by_role, "FROZEN_CLASSIFIER_FIXTURE_CONTRACT").path)
        if artifact_spec != mutation_spec:
            _fail("CLASSIFIER_SPEC_ARTIFACT_MISMATCH")
        payload = _fixture_payload(parent_id, mutation_spec)
    elif parent_id == "B4FNC15":
        rk_item = _one(by_role, "RK4_REFERENCE_CASE_METADATA")
        midpoint_item = _one(by_role, "MIDPOINT_REFERENCE_CASE_METADATA")
        rk = _read_json(rk_item.path)
        midpoint = _read_json(midpoint_item.path)
        expected_ids = ("RK4_REFERENCE__A1__ALPHA_2__TCMD_MS_10", "MIDPOINT_REFERENCE__A1__ALPHA_2__TCMD_MS_10")
        if (rk.get("case_id"), midpoint.get("case_id")) != expected_ids:
            _fail("NC15_REFERENCE_CASE_IDS")
        if _validate_official_metadata_path(rk_item, rk, frozen_schedule, phase) != rk.get("registered_slot") or _validate_official_metadata_path(midpoint_item, midpoint, frozen_schedule, phase) != midpoint.get("registered_slot"):
            _fail("NC15_REFERENCE_SCHEDULE_BINDING")
        payload = {"rk4": _reference_row(rk), "midpoint": _reference_row(midpoint), "event_time_tolerance_s": 0.00025, "work_relative_tolerance": 0.001, "work_absolute_floor_J": 1.0e-10}
    elif parent_id == "B4FNC16":
        artifact_schedule = _read_json(_one(by_role, "FROZEN_REGISTERED_SCHEDULE").path)
        if artifact_schedule != frozen_schedule:
            _fail("NC16_SCHEDULE_ARTIFACT_MISMATCH")
        payload = {"schedule": deepcopy(dict(frozen_schedule))}
    elif parent_id == "B4FNC17":
        payload, diagnostics = _nc17_payload(by_role, frozen_schedule, mutation_spec, float(frozen_q_ref), subvariant_index, phase)
    elif parent_id in {"B4FNC18", "B4FNC19", "B4FNC20", "B4FNC22"}:
        artifact_governance = _read_json(_one(by_role, "FROZEN_GOVERNANCE_CONTRACT").path)
        if artifact_governance != governance:
            _fail("GOVERNANCE_ARTIFACT_MISMATCH")
        candidate = _governance_candidate(governance, mutation_spec)
        if parent_id == "B4FNC22":
            artifact_schedule = _read_json(_one(by_role, "FROZEN_REGISTERED_SCHEDULE").path)
            if artifact_schedule != frozen_schedule:
                _fail("NC22_SCHEDULE_ARTIFACT_MISMATCH")
            payload = {"report": candidate}
        else:
            payload = {"candidate": candidate}
    else:  # pragma: no cover - parent enumeration above is exhaustive.
        _fail("PARENT_DERIVATION_NOT_IMPLEMENTED", parent_id)

    mutant_payload = _derive_mutant_payload(
        parent_id,
        subvariant_index,
        payload,
        by_role,
        mutation_spec,
        float(frozen_q_ref),
        finite_artifact,
    )

    return ArtifactDerivationResult(
        parent_id=parent_id,
        subvariant_index=subvariant_index,
        derived_payload=payload,
        derived_mutant_payload=mutant_payload,
        verified_roles=tuple(item.role for item in verified),
        verified_paths=tuple(str(item.path) for item in verified),
        diagnostics=diagnostics,
    )


def validate_nominal_payload_derivation(
    parent_id: str,
    base_payload: Mapping[str, Any],
    artifact_records: Sequence[Mapping[str, Any]],
    *,
    project_root: str | Path,
    phase_root: str | Path,
    source_bindings: Mapping[str, Any],
    mutation_spec: Mapping[str, Any],
    frozen_schedule: Mapping[str, Any],
    governance: Mapping[str, Any],
    frozen_q_ref: float,
    subvariant_index: int = 1,
) -> ArtifactDerivationResult:
    """Return the derivation only if the supplied nominal payload is exact."""

    if not isinstance(base_payload, Mapping):
        _fail("BASE_PAYLOAD_NOT_OBJECT")
    result = derive_nominal_payload(
        parent_id,
        artifact_records,
        project_root=project_root,
        phase_root=phase_root,
        source_bindings=source_bindings,
        mutation_spec=mutation_spec,
        frozen_schedule=frozen_schedule,
        governance=governance,
        frozen_q_ref=frozen_q_ref,
        subvariant_index=subvariant_index,
    )
    if _canonical_bytes(dict(base_payload)) != _canonical_bytes(result.derived_payload):
        _fail("BASE_PAYLOAD_NOT_ARTIFACT_DERIVED", parent_id)
    return result


__all__ = [
    "ArtifactDerivationError",
    "ArtifactDerivationResult",
    "derive_nominal_payload",
    "validate_nominal_payload_derivation",
]
