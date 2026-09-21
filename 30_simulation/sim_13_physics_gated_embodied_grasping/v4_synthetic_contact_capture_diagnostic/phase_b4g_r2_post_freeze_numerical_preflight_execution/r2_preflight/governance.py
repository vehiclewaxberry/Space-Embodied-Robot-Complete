"""Campaign-wide source contracts for the frozen 78-case R2 design.

The validators consume future evidence records but never run a case. They make
A0 bookends, certificate uniqueness, role overlap and blocked order explicit
production checks rather than test-local predicates.
"""

from __future__ import annotations

from copy import deepcopy
import math
from pathlib import PurePosixPath
from typing import Any

from .evaluator import validate_common_registry_structure
from .rehydrator import DONOR_PAYLOAD_SHA256, RehydrationError, rehydrate_payload
from .schedule import MATRIX_SHA256, SCHEDULE_SHA256, expand_matrix, generate_schedule
from .strict_json import StrictJSONError, canonical_bytes, canonical_sha256


HEX = set("0123456789ABCDEF")
MATRIX_BY_CASE = {row["case_id"]: row for row in expand_matrix()}


def _hex64(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(char in HEX for char in value)


def _evidence_path(value: Any, case_id: str) -> bool:
    if type(value) is not str or "\\" in value or ":" in value:
        return False
    path = PurePosixPath(value)
    return bool(
        not path.is_absolute()
        and ".." not in path.parts
        and len(path.parts) == 3
        and path.parts[:2] == ("evidence", "cases")
        and path.suffix == ".json"
        and path.stem == case_id
    )


def validate_matrix_and_schedule(matrix: Any, schedule: Any) -> dict[str, Any]:
    expected_matrix = expand_matrix()
    expected_schedule = generate_schedule()
    passed = bool(
        type(matrix) is list
        and type(schedule) is list
        and matrix == expected_matrix
        and schedule == expected_schedule
        and len(matrix) == len(schedule) == 78
        and len({row["case_id"] for row in matrix}) == 78
        and canonical_sha256(matrix) == MATRIX_SHA256
        and canonical_sha256(schedule) == SCHEDULE_SHA256
        and set(schedule) == {row["case_id"] for row in matrix}
    )
    return {
        "passed": passed,
        "status": "PASS_EXACT_78_MATRIX_AND_BLOCKED_ORDER" if passed else "FAIL_MATRIX_OR_SCHEDULE_DRIFT",
        "matrix_sha256": canonical_sha256(matrix) if isinstance(matrix, list) else "NOT_EVALUATED",
        "schedule_sha256": canonical_sha256(schedule) if isinstance(schedule, list) else "NOT_EVALUATED",
    }


FRESH_REGISTRY_KEYS = {
    "case_id", "execution_family", "roles", "lane_id", "method", "step_s",
    "arm", "sentinel", "alpha", "command_duration_s",
    "acquisition_certificate_payload", "acquisition_certificate_sha256",
    "evidence_path", "a0_numeric_payload", "a0_numeric_payload_sha256",
    "a0_generalized_force_Q_14", "a0_signed_W_act_J",
}
A0_NUMERIC_KEYS = {"schema", "case_id", "lane_id", "sentinel", "state_payload"}
A0_STATE_PAYLOAD_KEYS = {
    "time_grid_s", "service_state_29", "target_state_13",
    "generalized_force_Q_14", "signed_W_act_J",
}


def _finite_float(value: Any) -> bool:
    return type(value) is float and math.isfinite(value)


def _float_vector(value: Any, width: int | None = None) -> bool:
    return bool(
        type(value) is list
        and (width is None or len(value) == width)
        and all(_finite_float(item) for item in value)
    )


def _float_rows(value: Any, width: int, count: int) -> bool:
    return bool(
        type(value) is list
        and len(value) == count
        and all(_float_vector(row, width) for row in value)
    )


def _validate_a0_state_payload(value: Any) -> bool:
    if not isinstance(value, dict) or set(value) != A0_STATE_PAYLOAD_KEYS:
        return False
    time = value["time_grid_s"]
    if not _float_vector(time) or not time:
        return False
    if any(time[index] <= time[index - 1] for index in range(1, len(time))):
        return False
    count = len(time)
    return bool(
        _float_rows(value["service_state_29"], 29, count)
        and _float_rows(value["target_state_13"], 13, count)
        and _float_rows(value["generalized_force_Q_14"], 14, count)
        and _float_vector(value["signed_W_act_J"], count)
    )


def _project_a0_numeric(payload: Any) -> tuple[bytes, str] | None:
    try:
        if not isinstance(payload, dict) or set(payload) != A0_NUMERIC_KEYS:
            return None
        case_id = payload["case_id"]
        sentinel = payload["sentinel"]
        if (
            type(case_id) is not str
            or type(payload["lane_id"]) is not str
            or type(sentinel) is not str
            or sentinel not in {"PRE", "POST"}
            or not _validate_a0_state_payload(payload["state_payload"])
        ):
            return None
        projected = deepcopy(payload)
        projected["case_id"] = "CASE_IDENTITY_EXCLUDED_V1"
        projected["sentinel"] = "A0_BOOKEND_POSITION_EXCLUDED_V1"
        encoded = canonical_bytes(projected)
        return encoded, canonical_sha256(projected)
    except (StrictJSONError, TypeError, ValueError):
        return None


def _validate_fresh_registry_record(record: Any) -> tuple[bool, str]:
    if not isinstance(record, dict) or set(record) != FRESH_REGISTRY_KEYS:
        return False, "FRESH_REGISTRY_EXACT_RECORD_SCHEMA_REQUIRED"
    row = MATRIX_BY_CASE.get(record["case_id"])
    if row is None or row["execution_family"] != "FRESH":
        return False, "FRESH_REGISTRY_CASE_NOT_REGISTERED"
    for field in (
        "execution_family", "roles", "lane_id", "method", "step_s", "arm",
        "sentinel", "alpha", "command_duration_s",
    ):
        if record[field] != row[field] or type(record[field]) is not type(row[field]):
            return False, f"FRESH_REGISTRY_MATRIX_FIELD_DRIFT:{field}"
    certificate = record["acquisition_certificate_sha256"]
    if (
        not _hex64(certificate)
        or certificate == DONOR_PAYLOAD_SHA256
        or canonical_sha256(record["acquisition_certificate_payload"]) != certificate
        or not _evidence_path(record["evidence_path"], record["case_id"])
    ):
        return False, "FRESH_REGISTRY_CERTIFICATE_OR_PATH_INVALID"
    try:
        fixture = rehydrate_payload(record["acquisition_certificate_payload"], certificate)
    except (RehydrationError, StrictJSONError, TypeError, ValueError):
        return False, "FRESH_REGISTRY_CERTIFICATE_ROUNDTRIP_INVALID"
    if (
        fixture.case_id != record["case_id"]
        or fixture.lane_id != record["lane_id"]
        or fixture.event.method != record["method"]
        or fixture.event.step_s != record["step_s"]
    ):
        return False, "FRESH_REGISTRY_CERTIFICATE_METADATA_INVALID"
    if row["arm"] == "A0":
        projected = _project_a0_numeric(record["a0_numeric_payload"])
        state_payload = (
            record["a0_numeric_payload"].get("state_payload")
            if isinstance(record["a0_numeric_payload"], dict)
            else None
        )
        if (
            projected is None
            or record["a0_numeric_payload"]["schema"] != "B4G_R2_A0_BOOKEND_NUMERIC_PAYLOAD_V1"
            or record["a0_numeric_payload"]["case_id"] != record["case_id"]
            or record["a0_numeric_payload"]["lane_id"] != record["lane_id"]
            or record["a0_numeric_payload"]["sentinel"] != record["sentinel"]
            or not _hex64(record["a0_numeric_payload_sha256"])
            or canonical_sha256(record["a0_numeric_payload"]) != record["a0_numeric_payload_sha256"]
            or type(record["a0_generalized_force_Q_14"]) is not list
            or len(record["a0_generalized_force_Q_14"]) != 14
            or any(type(value) is not float or value != 0.0 for value in record["a0_generalized_force_Q_14"])
            or type(record["a0_signed_W_act_J"]) is not list
            or not record["a0_signed_W_act_J"]
            or any(type(value) is not float or value != 0.0 for value in record["a0_signed_W_act_J"])
            or not isinstance(state_payload, dict)
            or record["a0_signed_W_act_J"] != state_payload["signed_W_act_J"]
            or any(
                row_q != record["a0_generalized_force_Q_14"]
                for row_q in state_payload["generalized_force_Q_14"]
            )
            or len(record["a0_signed_W_act_J"]) != len(state_payload["time_grid_s"])
        ):
            return False, "A0_NUMERIC_PAYLOAD_Q_OR_W_INVALID"
    elif (
        record["a0_numeric_payload"] != "NOT_APPLICABLE_A1"
        or record["a0_numeric_payload_sha256"] != "NOT_APPLICABLE_A1"
        or record["a0_generalized_force_Q_14"] != "NOT_APPLICABLE_A1"
        or record["a0_signed_W_act_J"] != "NOT_APPLICABLE_A1"
    ):
        return False, "A1_A0_FIELDS_MUST_USE_EXPLICIT_ENUM"
    return True, "PASS"


def validate_a0_bookends(fresh_records: list[dict[str, Any]]) -> dict[str, Any]:
    records = [record for record in fresh_records if isinstance(record, dict) and record.get("arm") == "A0"]
    if len(records) != 12:
        return {"passed": False, "status": "A0_EXACT_TWELVE_RECORDS_REQUIRED"}
    by_lane: dict[str, dict[str, dict[str, Any]]] = {}
    for record in records:
        valid, status = _validate_fresh_registry_record(record)
        if not valid:
            return {"passed": False, "status": status}
        by_lane.setdefault(record["lane_id"], {})[record["sentinel"]] = record
    if len(by_lane) != 6 or any(set(pair) != {"PRE", "POST"} for pair in by_lane.values()):
        return {"passed": False, "status": "A0_PRE_POST_PAIR_MISSING_OR_DUPLICATE"}
    comparisons: dict[str, Any] = {}
    for lane, pair in by_lane.items():
        pre = _project_a0_numeric(pair["PRE"]["a0_numeric_payload"])
        post = _project_a0_numeric(pair["POST"]["a0_numeric_payload"])
        equal = pre is not None and post is not None and pre == post
        comparisons[lane] = {"projected_byte_and_sha_exact": equal}
        if not equal:
            return {"passed": False, "status": "A0_PRE_POST_NUMERIC_PROJECTION_MISMATCH", "comparisons": comparisons}
    return {"passed": True, "status": "PASS_A0_SIX_LANE_PRE_POST_BYTE_EXACT_Q_W_ZERO", "comparisons": comparisons}


def validate_fresh_registry(fresh_records: list[dict[str, Any]]) -> dict[str, Any]:
    expected_order = [case_id for case_id in generate_schedule() if MATRIX_BY_CASE[case_id]["execution_family"] == "FRESH"]
    if type(fresh_records) is not list or len(fresh_records) != 60:
        return {"passed": False, "status": "FRESH_EXACT_SIXTY_RECORDS_REQUIRED"}
    if [record.get("case_id") for record in fresh_records if isinstance(record, dict)] != expected_order:
        return {"passed": False, "status": "FRESH_BLOCKED_ORDER_MISMATCH"}
    for record in fresh_records:
        valid, status = _validate_fresh_registry_record(record)
        if not valid:
            return {"passed": False, "status": status}
    certificates = [record["acquisition_certificate_sha256"] for record in fresh_records]
    paths = [record["evidence_path"] for record in fresh_records]
    if len(set(certificates)) != 60 or len(set(paths)) != 60:
        return {"passed": False, "status": "FRESH_CERTIFICATE_OR_EVIDENCE_PATH_REUSED"}
    a0 = validate_a0_bookends(fresh_records)
    passed = a0["passed"] is True
    return {
        "passed": passed,
        "status": "PASS_FRESH_SIXTY_REGISTRY_AND_A0" if passed else a0["status"],
        "fresh_certificate_count": 60,
        "fresh_evidence_path_count": 60,
        "a0": a0,
    }


def validate_global_78_registry(
    fresh_records: list[dict[str, Any]], common_records: list[dict[str, Any]]
) -> dict[str, Any]:
    fresh = validate_fresh_registry(fresh_records)
    common_structure = validate_common_registry_structure(common_records)
    expected_common = [case_id for case_id in generate_schedule() if MATRIX_BY_CASE[case_id]["execution_family"] == "COMMON_PROP"]
    if fresh["passed"] is not True or common_structure["passed"] is not True:
        return {"passed": False, "status": "FRESH_OR_COMMON_REGISTRY_COUNT_INVALID"}
    if [record.get("case_id") for record in common_records if isinstance(record, dict)] != expected_common:
        return {"passed": False, "status": "COMMON_BLOCKED_ORDER_MISMATCH"}
    common_ids = [record.get("case_id") for record in common_records]
    common_paths = [record.get("evidence_path") for record in common_records]
    common_certs = [record.get("donor_certificate_sha256") for record in common_records]
    if (
        any(MATRIX_BY_CASE.get(case_id, {}).get("execution_family") != "COMMON_PROP" for case_id in common_ids)
        or any(not _evidence_path(path, case_id) for path, case_id in zip(common_paths, common_ids))
        or any(certificate != DONOR_PAYLOAD_SHA256 for certificate in common_certs)
        or len(set(common_ids)) != 18
        or len(set(common_paths)) != 18
    ):
        return {"passed": False, "status": "COMMON_REGISTRY_CASE_CERTIFICATE_OR_PATH_INVALID"}
    fresh_ids = [record["case_id"] for record in fresh_records]
    fresh_paths = [record["evidence_path"] for record in fresh_records]
    if (
        set(fresh_ids) & set(common_ids)
        or set(fresh_paths) & set(common_paths)
        or fresh_ids + common_ids != generate_schedule()
        or len(set(fresh_ids + common_ids)) != 78
        or len(set(fresh_paths + common_paths)) != 78
    ):
        return {"passed": False, "status": "FRESH_COMMON_OVERLAP_OR_GLOBAL_ORDER_INVALID"}
    return {
        "passed": True,
        "status": "PASS_EXACT_78_GLOBAL_REGISTRY_NO_UNDECLARED_OVERLAP",
        "fresh_count": 60,
        "common_count": 18,
        "common_registry_structure": common_structure,
        "trajectory_count": 0,
        "r2_numerical_preflight_executed": False,
    }


FALSE_FLAG_KEYS = {
    "r2_numerical_preflight_executed", "r2_execution_negative_controls_executed",
    "numerical_execution", "campaign_executed", "scientific_gate_pass", "current",
    "nc19_closed", "owner_execution_authorized", "production", "release",
    "next_stage_authorized", "formal_sim13_nc15", "formal_sim13_nc16",
    "formal_sim13_nc18", "formal_sim13_nc19", "formal_sim13_nc20",
    "memory_gate_applicable", "memory_gate_pass", "owner_memory_override",
}
GOVERNANCE_KEYS = FALSE_FLAG_KEYS | {
    "trajectory_count", "authorized_execution_path_status", "execution_readiness_status",
}


def validate_governance_flags(flags: Any) -> bool:
    return bool(
        isinstance(flags, dict)
        and set(flags) == GOVERNANCE_KEYS
        and all(flags[key] is False for key in FALSE_FLAG_KEYS)
        and type(flags["trajectory_count"]) is int
        and flags["trajectory_count"] == 0
        and flags["authorized_execution_path_status"] == "NOT_VALIDATED_NO_DIRECT_OWNER_SOURCE"
        and flags["execution_readiness_status"] == "HOLD_R2_NUMERICAL_PREFLIGHT_EXECUTION_NO_DIRECT_OWNER_SOURCE_AND_NO_IMPLEMENTED_AUTHORIZED_PATH"
    )


__all__ = [
    "A0_NUMERIC_KEYS", "A0_STATE_PAYLOAD_KEYS", "FALSE_FLAG_KEYS", "FRESH_REGISTRY_KEYS", "GOVERNANCE_KEYS",
    "validate_a0_bookends", "validate_fresh_registry", "validate_global_78_registry",
    "validate_governance_flags", "validate_matrix_and_schedule",
]
