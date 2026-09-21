"""Strict source-only integrity context and independent parent-trace binding."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np

from .source_api import load_raw_modules


CONTEXT_SCHEMA = "SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_CONTEXT_V1"
EVIDENCE_CLASS = "SOURCE_ONLY_TECHNICAL_FIXTURE"
AUTHORIZATION_SENTINEL = "NOT_AVAILABLE_SOURCE_FREEZE_ONLY_NO_DIRECT_OWNER_SOURCE"
PROVENANCE_SCOPE = "CASE_INTERNAL_CERTIFICATE_AND_RAW_INITIAL_STATE_ONLY_NO_FIXED_TEMPLATE_CREDIT"
CLAIM_BOUNDARY = (
    "source-only technical predicate recomputation; no trajectory, current-system, "
    "formal NC19, scientific, Owner, production, release or next-stage credit"
)
CONTEXT_KEYS = {
    "schema", "case_id", "lane_id", "method", "step_s", "raw_binding",
    "execution_evidence_class", "authorization_terminal_binding",
    "acquisition_certificate_payload", "acquisition_certificate_sha256",
    "acquisition_provenance_scope", "parent_trace_binding", "claim_boundary",
}
PARENT_BINDING_KEYS = {"schema", "path", "bytes", "sha256"}
PARENT_TRACE_KEYS = {
    "schema", "case_id", "lane_id", "method", "step_s", "producer_id",
    "parent_source_bindings", "input_projection", "mapping_z_before_20",
    "terminal_service_state_29", "terminal_target_state_13",
    "post_release_passed", "terminal_status", "claim_boundary",
}
PARENT_INPUT_KEYS = {
    "raw_npz_sha256", "acquisition_certificate_sha256", "removal_index",
    "removal_time_s", "active_service_state_29_sha256",
}
PARENT_SOURCE_KIND = "SOURCE_ONLY_TECHNICAL_PARENT_FIXTURE"
PARENT_CLAIM_BOUNDARY = (
    "source-only compact parent crosscheck fixture; not an independent B4E "
    "execution and no G11 execution credit"
)


class ContextError(ValueError):
    pass


@dataclass(frozen=True)
class BoundIntegrityContext:
    relative_path: str
    byte_count: int
    sha256: str
    payload: Mapping[str, Any]
    acquisition_payload: Mapping[str, Any]
    snapshot: Mapping[str, Any]
    parent_binding: Mapping[str, Any]
    parent_trace: Mapping[str, Any]

    @property
    def execution_credit_allowed(self) -> bool:
        return False


def _canonical_sha256(value: Any) -> str:
    modules = load_raw_modules()
    return modules["strict_json"].canonical_sha256(value)


def _hex64(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(char in "0123456789ABCDEF" for char in value)


def _finite_float(value: Any) -> bool:
    return type(value) is float and math.isfinite(value)


def _deep_freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    return value


def _acquisition_binding(context: dict[str, Any], case: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = context["acquisition_certificate_payload"]
    if not isinstance(payload, dict) or set(payload) != {"lane_id", "case_id", "event", "acquisition"}:
        raise ContextError("ACQUISITION_PAYLOAD_EXACT_TOP_LEVEL_SCHEMA_REQUIRED")
    if (
        payload.get("lane_id") != case.sidecar["lane_id"]
        or payload.get("case_id") != case.sidecar["case_id"]
        or _canonical_sha256(payload) != context["acquisition_certificate_sha256"]
    ):
        raise ContextError("ACQUISITION_PAYLOAD_ID_OR_SHA256_MISMATCH")
    event = payload.get("event")
    acquisition = payload.get("acquisition")
    if not isinstance(event, dict) or not isinstance(acquisition, dict):
        raise ContextError("ACQUISITION_EVENT_AND_ACQUISITION_OBJECTS_REQUIRED")
    required_event = {"run_id", "method", "step_s", "index", "time_s", "source", "b3_dissipation_J", "service", "target"}
    required_acquisition = {"run_id", "acquisition_time_s", "z_plus_reduced", "eta_plus", "snapshot", "energy_audit"}
    if not required_event.issubset(event) or not required_acquisition.issubset(acquisition):
        raise ContextError("ACQUISITION_REQUIRED_NESTED_FIELDS_MISSING")
    if (
        event["run_id"] != case.sidecar["case_id"]
        or acquisition["run_id"] != case.sidecar["case_id"]
        or event["method"] != case.sidecar["method"]
        or event["step_s"] != case.sidecar["step_s"]
        or type(event["index"]) is not int or event["index"] < 0
        or event["source"] != "INDEPENDENT_B3_RERUN_FIRST_QUALIFYING_SAMPLE"
        or not _finite_float(event["time_s"])
        or not _finite_float(acquisition["acquisition_time_s"])
        or event["time_s"] != acquisition["acquisition_time_s"]
        or event["time_s"] != float(case.arrays["time_s"][0])
    ):
        raise ContextError("ACQUISITION_CASE_METHOD_STEP_TIME_OR_SOURCE_BINDING_INVALID")
    service = event["service"]
    target = event["target"]
    energy = acquisition["energy_audit"]
    snapshot = acquisition["snapshot"]
    if not isinstance(service, dict) or not isinstance(target, dict) or not isinstance(energy, dict) or not isinstance(snapshot, dict):
        raise ContextError("ACQUISITION_STATE_ENERGY_OR_SNAPSHOT_OBJECT_REQUIRED")
    try:
        position = np.asarray(service["base_position_inertial_m"], dtype="<f8")
        quaternion = np.asarray(service["base_quaternion_body_to_inertial_wxyz"], dtype="<f8")
        joints = np.asarray(service["joint_coordinates_mixed"], dtype="<f8")
        target_position = np.asarray(target["position_inertial_m"], dtype="<f8")
        target_quaternion = np.asarray(target["quaternion_body_to_inertial_wxyz"], dtype="<f8")
        z_plus = np.asarray(acquisition["z_plus_reduced"], dtype="<f8")
        eta_plus = np.asarray(acquisition["eta_plus"], dtype="<f8")
    except (KeyError, TypeError, ValueError) as exc:
        raise ContextError("ACQUISITION_STATE_NUMERIC_FIELDS_INVALID") from exc
    values = (position, quaternion, joints, target_position, target_quaternion, z_plus, eta_plus)
    shapes = ((3,), (4,), (8,), (3,), (4,), (20,), (14,))
    if any(value.shape != shape or not np.all(np.isfinite(value)) for value, shape in zip(values, shapes)):
        raise ContextError("ACQUISITION_STATE_SHAPE_OR_FINITE_INVALID")
    if not np.array_equal(eta_plus, z_plus[:14]):
        raise ContextError("ACQUISITION_ETA_PLUS_NOT_EXACT_Z_PLUS_PREFIX")
    event_d = event["b3_dissipation_J"]
    acquisition_d = energy.get("D_B3_minus_J")
    if (
        not _finite_float(event_d) or not _finite_float(acquisition_d)
        or event_d < 0.0 or acquisition_d < 0.0
        or np.asarray(event_d, dtype="<f8").view("<u8").item()
        != np.asarray(acquisition_d, dtype="<f8").view("<u8").item()
    ):
        raise ContextError("ACQUISITION_DISSIPATION_NOT_NONNEGATIVE_BIT_EXACT")
    expected_service = np.concatenate((position, quaternion, joints, z_plus[:14]))
    expected_target = np.concatenate((target_position, target_quaternion, z_plus[14:20]))
    if not np.array_equal(expected_service, case.arrays["service_state_29"][0]):
        raise ContextError("RAW_ACTIVE_INITIAL_SERVICE_NOT_EXACT_ACQUISITION_PAYLOAD")
    if not np.array_equal(expected_target, case.arrays["target_state_13"][0]):
        raise ContextError("RAW_ACTIVE_INITIAL_TARGET_NOT_EXACT_ACQUISITION_PAYLOAD")
    return payload, snapshot


def _numeric_vector(value: Any, width: int, name: str) -> np.ndarray:
    try:
        array = np.asarray(value, dtype="<f8")
    except (TypeError, ValueError) as exc:
        raise ContextError(f"PARENT_{name}_NOT_NUMERIC") from exc
    if array.shape != (width,) or not np.all(np.isfinite(array)):
        raise ContextError(f"PARENT_{name}_SHAPE_OR_FINITE")
    return array


def _load_parent_binding(root: Path, value: Any, case: Any, acquisition_sha256: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != PARENT_BINDING_KEYS:
        raise ContextError("FINITE_PARENT_TRACE_EXACT_BINDING_REQUIRED")
    if (
        value.get("schema") != "SIM13_V4B4G_R2_PARENT_POST_RELEASE_TRACE_FILE_BINDING_V1"
        or type(value.get("path")) is not str
        or type(value.get("bytes")) is not int or value["bytes"] <= 0
        or not _hex64(value.get("sha256"))
    ):
        raise ContextError("PARENT_TRACE_BINDING_IDENTITY_INVALID")
    modules = load_raw_modules()
    try:
        bound = modules["path_binding"].single_read_project_file(
            root, value["path"], suffix=".json",
        )
        trace = modules["strict_json"].loads_bytes(bound.payload)
    except Exception as exc:
        raise ContextError("PARENT_TRACE_PATH_BINDING_FAILED") from exc
    digest = hashlib.sha256(bound.payload).hexdigest().upper()
    if bound.byte_count != value["bytes"] or digest != value["sha256"]:
        raise ContextError("PARENT_TRACE_BYTES_OR_SHA256_MISMATCH")
    if not isinstance(trace, dict) or set(trace) != PARENT_TRACE_KEYS:
        raise ContextError("PARENT_TRACE_EXACT_SCHEMA_REQUIRED")
    if (
        trace.get("schema") != "SIM13_V4B4G_R2_B4E_PARENT_POST_TRACE_COMPACT_V1"
        or trace.get("case_id") != case.sidecar["case_id"]
        or trace.get("lane_id") != case.sidecar["lane_id"]
        or trace.get("method") != case.sidecar["method"]
        or trace.get("step_s") != case.sidecar["step_s"]
        or trace.get("producer_id") != PARENT_SOURCE_KIND
        or trace.get("post_release_passed") is not True
        or trace.get("terminal_status") != "SOURCE_ONLY_TECHNICAL_PARENT_TRACE_COMPLETE"
        or trace.get("claim_boundary") != PARENT_CLAIM_BOUNDARY
        or not isinstance(trace.get("parent_source_bindings"), list)
        or not trace["parent_source_bindings"]
        or not isinstance(trace.get("input_projection"), dict)
        or set(trace["input_projection"]) != PARENT_INPUT_KEYS
    ):
        raise ContextError("PARENT_TRACE_IDENTITY_OR_SCOPE_INVALID")
    for record in trace["parent_source_bindings"]:
        if (
            not isinstance(record, dict) or set(record) != {"source_id", "path", "bytes", "sha256"}
            or type(record["source_id"]) is not str or not record["source_id"]
            or type(record["path"]) is not str or not record["path"]
            or type(record["bytes"]) is not int or record["bytes"] <= 0
            or not _hex64(record["sha256"])
        ):
            raise ContextError("PARENT_SOURCE_BINDING_RECORD_INVALID")
    projection = trace["input_projection"]
    removal_index = int(case.arrays["bilateral_removal_active_sample_index"][0])
    removal_time = float(case.arrays["bilateral_removal_event_time_s"][0])
    service_sha = _canonical_sha256(case.arrays["service_state_29"][removal_index].tolist())
    if (
        projection.get("raw_npz_sha256") != case.npz_sha256
        or projection.get("acquisition_certificate_sha256") != acquisition_sha256
        or type(projection.get("removal_index")) is not int
        or projection.get("removal_index") != removal_index
        or not _finite_float(projection.get("removal_time_s"))
        or projection.get("removal_time_s") != removal_time
        or projection.get("active_service_state_29_sha256") != service_sha
    ):
        raise ContextError("PARENT_INPUT_PROJECTION_NOT_BOUND_TO_RAW_EVENT")
    _numeric_vector(trace["mapping_z_before_20"], 20, "MAPPING_Z_BEFORE_20")
    _numeric_vector(trace["terminal_service_state_29"], 29, "TERMINAL_SERVICE_STATE_29")
    _numeric_vector(trace["terminal_target_state_13"], 13, "TERMINAL_TARGET_STATE_13")
    return value, trace


def load_integrity_context(project_root: Path, relative_path: str, case: Any) -> BoundIntegrityContext:
    modules = load_raw_modules()
    try:
        bound = modules["path_binding"].single_read_project_file(project_root, relative_path, suffix=".json")
        context = modules["strict_json"].loads_bytes(bound.payload)
    except Exception as exc:
        raise ContextError("CONTEXT_STRICT_PATH_OR_JSON_BINDING_FAILED") from exc
    if not isinstance(context, dict) or set(context) != CONTEXT_KEYS:
        raise ContextError("CONTEXT_EXACT_SCHEMA_REQUIRED")
    if (
        context.get("schema") != CONTEXT_SCHEMA
        or context.get("case_id") != case.sidecar["case_id"]
        or context.get("lane_id") != case.sidecar["lane_id"]
        or context.get("method") != case.sidecar["method"]
        or context.get("step_s") != case.sidecar["step_s"]
        or context.get("raw_binding") != case.raw_binding()
        or context.get("execution_evidence_class") != EVIDENCE_CLASS
        or context.get("authorization_terminal_binding") != AUTHORIZATION_SENTINEL
        or context.get("acquisition_provenance_scope") != PROVENANCE_SCOPE
        or context.get("claim_boundary") != CLAIM_BOUNDARY
        or not _hex64(context.get("acquisition_certificate_sha256"))
    ):
        raise ContextError("CONTEXT_IDENTITY_SCOPE_OR_RAW_BINDING_INVALID")
    acquisition_payload, snapshot = _acquisition_binding(context, case)
    finite = case.sidecar["outcome"] == "FINITE_BILATERAL_REMOVAL_OBSERVED"
    if not finite:
        raise ContextError("FULL_INTEGRITY_CONTEXT_REQUIRES_RAW_FINITE_REMOVAL_CASE")
    parent_binding, parent_trace = _load_parent_binding(
        project_root, context["parent_trace_binding"], case,
        context["acquisition_certificate_sha256"],
    )
    return BoundIntegrityContext(
        relative_path=bound.relative_path,
        byte_count=bound.byte_count,
        sha256=hashlib.sha256(bound.payload).hexdigest().upper(),
        payload=_deep_freeze(context),
        acquisition_payload=_deep_freeze(acquisition_payload),
        snapshot=_deep_freeze(snapshot),
        parent_binding=_deep_freeze(parent_binding),
        parent_trace=_deep_freeze(parent_trace),
    )


__all__ = [
    "AUTHORIZATION_SENTINEL", "BoundIntegrityContext", "CLAIM_BOUNDARY",
    "CONTEXT_SCHEMA", "ContextError", "EVIDENCE_CLASS", "PARENT_CLAIM_BOUNDARY",
    "PARENT_SOURCE_KIND", "PROVENANCE_SCOPE", "load_integrity_context",
]
