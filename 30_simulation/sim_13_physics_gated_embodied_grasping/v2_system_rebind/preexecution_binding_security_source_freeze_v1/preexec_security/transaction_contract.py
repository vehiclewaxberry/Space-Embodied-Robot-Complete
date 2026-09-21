"""Static fixed-path atomic publication transaction contract.

Only contract objects and synthetic state traces are validated.  There is no
executor, lock acquisition, generator import, temporary-file write or rename in
this module.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import Any, Mapping

from .strict_json import StrictJSONError, loads_strict, require_exact_keys


TARGET_PATH = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "unified_r2_digital_prototype_prebind/generated_v2/"
    "unified_r2_c01_no_route_c_sim_candidate_v2.urdf"
)
AUTHORITY_PATH = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "unified_r2_digital_prototype_prebind/source_only_v2/"
    "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json"
)
LOCK_PATH = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "unified_r2_digital_prototype_prebind/source_only_v2/"
    ".unified_r2_v2_active_run.lock"
)
EVENTS = (
    "AUTHORITY_VERIFIED",
    "RUN_ID_CONSUMED",
    "LOCK_ACQUIRED",
    "INPUT_SNAPSHOTS_HASH_VERIFIED",
    "BUILT_IN_MEMORY",
    "VALIDATED_IN_MEMORY",
    "TEMP_FILE_OPENED_EXCLUSIVE_SAME_DIRECTORY",
    "TEMP_FILE_FLUSHED_AND_FSYNCED",
    "ATOMIC_REPLACE_COMMITTED",
    "OUTPUT_BYTES_REHASHED",
    "RECEIPT_COMMITTED",
    "LOCK_RELEASED",
)
_RUN_ID = re.compile(r"^[A-Z0-9][A-Z0-9_-]{15,63}$")


class TransactionContractError(ValueError):
    pass


def canonical_transaction_contract() -> dict[str, Any]:
    return {
        "schema": "UNIFIED_R2_ATOMIC_GENERATION_TRANSACTION_CONTRACT_V1",
        "mode": "DECLARATION_ONLY_NO_EXECUTOR",
        "target_path": TARGET_PATH,
        "authority_path": AUTHORITY_PATH,
        "lock_path": LOCK_PATH,
        "temporary_path_rule": "TARGET_PLUS_DOT_TMP_DOT_RUN_ID_IN_SAME_DIRECTORY",
        "ordered_events": list(EVENTS),
        "failure_rule": "ANY_ERROR_BEFORE_RECEIPT_COMMIT_REMOVES_TEMP_AND_DENIES_RECEIPT",
        "authority_rules": {
            "strict_json_duplicate_keys_rejected": True,
            "strict_json_extra_fields_rejected": True,
            "stable_owner_handle_required": True,
            "fresh_time_window_required": True,
            "single_use_run_id_required": True,
        },
        "source_freeze_execution_state": {
            "generator_invoked": False,
            "artifact_emitted": False,
            "receipt_emitted": False,
        },
    }


def _safe_exact_path(path: Any, expected: str, label: str) -> None:
    if path != expected:
        raise TransactionContractError(f"{label}_PATH_MISMATCH")
    pure = PurePosixPath(path)
    if path.startswith("/") or "\\" in path or ":" in path or ".." in pure.parts:
        raise TransactionContractError(f"{label}_PATH_UNSAFE")


def validate_transaction_contract(payload: bytes | str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(payload, (bytes, str)):
        try:
            data = loads_strict(payload)
        except StrictJSONError as exc:
            raise TransactionContractError(str(exc)) from exc
    else:
        data = dict(payload)
    expected = canonical_transaction_contract()
    require_exact_keys(data, expected, path="/")
    require_exact_keys(data["authority_rules"], expected["authority_rules"], path="/authority_rules")
    require_exact_keys(data["source_freeze_execution_state"], expected["source_freeze_execution_state"], path="/source_freeze_execution_state")
    for key, exact in expected.items():
        if data[key] != exact:
            raise TransactionContractError(f"TRANSACTION_CONTRACT_MISMATCH:{key}")
    _safe_exact_path(data["target_path"], TARGET_PATH, "TARGET")
    _safe_exact_path(data["authority_path"], AUTHORITY_PATH, "AUTHORITY")
    _safe_exact_path(data["lock_path"], LOCK_PATH, "LOCK")
    return dict(data)


def validate_transition_trace(record: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a synthetic state-machine trace without performing any event."""

    require_exact_keys(
        record,
        (
            "schema",
            "mode",
            "run_id",
            "target_path",
            "temporary_path",
            "events",
            "generator_invoked",
            "artifact_emitted",
        ),
        path="/",
    )
    if record["schema"] != "UNIFIED_R2_ATOMIC_GENERATION_SYNTHETIC_TRACE_V1":
        raise TransactionContractError("TRACE_SCHEMA_MISMATCH")
    if record["mode"] != "SYNTHETIC_STATE_MACHINE_TEST_ONLY":
        raise TransactionContractError("TRACE_MODE_MISMATCH")
    run_id = record["run_id"]
    if not isinstance(run_id, str) or not _RUN_ID.fullmatch(run_id):
        raise TransactionContractError("TRACE_RUN_ID_INVALID")
    _safe_exact_path(record["target_path"], TARGET_PATH, "TRACE_TARGET")
    expected_temp = f"{TARGET_PATH}.tmp.{run_id}"
    if record["temporary_path"] != expected_temp:
        raise TransactionContractError("TRACE_TEMP_PATH_MISMATCH")
    if record["events"] != list(EVENTS):
        raise TransactionContractError("TRACE_EVENT_ORDER_MISMATCH")
    if record["generator_invoked"] is not False or record["artifact_emitted"] is not False:
        raise TransactionContractError("SOURCE_FREEZE_EXECUTION_FORBIDDEN")
    return {
        "valid": True,
        "events_checked": len(EVENTS),
        "fixed_target": True,
        "atomic_replace_precedes_receipt": EVENTS.index("ATOMIC_REPLACE_COMMITTED")
        < EVENTS.index("RECEIPT_COMMITTED"),
        "lock_release_is_terminal": EVENTS[-1] == "LOCK_RELEASED",
        "source_only": True,
    }


def synthetic_transition_trace() -> dict[str, Any]:
    run_id = "SYNTHETIC_RUN_0001"
    return {
        "schema": "UNIFIED_R2_ATOMIC_GENERATION_SYNTHETIC_TRACE_V1",
        "mode": "SYNTHETIC_STATE_MACHINE_TEST_ONLY",
        "run_id": run_id,
        "target_path": TARGET_PATH,
        "temporary_path": f"{TARGET_PATH}.tmp.{run_id}",
        "events": list(EVENTS),
        "generator_invoked": False,
        "artifact_emitted": False,
    }


__all__ = [
    "AUTHORITY_PATH",
    "EVENTS",
    "LOCK_PATH",
    "TARGET_PATH",
    "TransactionContractError",
    "canonical_transaction_contract",
    "synthetic_transition_trace",
    "validate_transaction_contract",
    "validate_transition_trace",
]
