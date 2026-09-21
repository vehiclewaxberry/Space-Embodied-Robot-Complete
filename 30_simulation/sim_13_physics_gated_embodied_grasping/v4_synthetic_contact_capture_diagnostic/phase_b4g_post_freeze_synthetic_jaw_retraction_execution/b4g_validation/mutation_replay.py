"""Independent replay of byte-bound B4G mutation artifacts.

No solver, campaign runner, or mutation-executor module is imported here.  The
module verifies real files, replays a restricted JSON patch, and evaluates the
named Gate directly from the replay bundle payload.
"""

from __future__ import annotations

from copy import deepcopy
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .core import (
    ValidationReport,
    canonical_bytes,
    canonical_sha256,
    finite_number,
    is_sha256,
    read_json_strict,
    resolve_declared,
    sha256_file,
    verify_file_record,
)


REPLAY_TYPE_BY_PARENT = {
    "B4FNC01": "BOUND_SOURCE_BYTES", "B4FNC02": "COMMAND_TRACE",
    "B4FNC03": "COMMAND_TRACE", "B4FNC04": "GEOMETRY_SIGN_TRACE",
    "B4FNC05": "WORK_TRACE", "B4FNC06": "WORK_TRACE",
    "B4FNC07": "REMOVAL_WORK_MAPPING", "B4FNC08": "COMMAND_TRACE",
    "B4FNC09": "CLEARANCE_TRACE", "B4FNC10": "CLEARANCE_TRACE",
    "B4FNC11": "REMOVAL_MAPPING", "B4FNC12": "ENERGY_MAPPING",
    "B4FNC13": "POST_RELEASE_TARGET_TRACE", "B4FNC14": "CONTACT_TRACE",
    "B4FNC15": "REFERENCE_PAIR", "B4FNC16": "REGISTERED_SCHEDULE",
    "B4FNC17": "A2_COMMAND_OR_TRACE_PAIR", "B4FNC18": "GOVERNANCE_CANDIDATE",
    "B4FNC19": "GOVERNANCE_CANDIDATE", "B4FNC20": "GOVERNANCE_CANDIDATE",
    "B4FNC21": "GEOMETRY_SIGN_TRACE", "B4FNC22": "SELECTOR_REPORT",
}

PAYLOAD_FIELDS = {
    "BOUND_SOURCE_BYTES": {"source_id", "source_record", "candidate_record", "candidate_bytes_path", "xor_mutation"},
    "COMMAND_TRACE": {"arm", "slot", "acquisition_time_s", "sample_time_s", "Q_ref_N", "command_parameters", "observed_Q_14", "clearance_dwell_active", "trace_origin", "harness_id", "harness_command"},
    "GEOMETRY_SIGN_TRACE": {"P_coordinates_m", "centered_step_m", "raw_gap_jacobian_P", "registered_signs", "consumed_signs", "clipping_used", "extrapolation_used", "terminal_status"},
    "WORK_TRACE": {"time_s", "Q_P_N", "eta_P_m_s", "signed_W_act_J", "energy_minus_work_residual_J"},
    "REMOVAL_WORK_MAPPING": {"finite_removal_event", "W_before_removal_J", "W_after_mapping_J"},
    "CLEARANCE_TRACE": {"time_s", "acquisition_time_s", "left_gap_m", "right_gap_m", "left_gap_rate_m_s", "right_gap_rate_m_s", "ledger_interval_certified", "observed_finite_event", "classifier_mode"},
    "REMOVAL_MAPPING": {"z_before", "z_after", "linear_impulse_N_s", "angular_impulse_N_m_s", "kinetic_energy_jump_J", "ideal_constraint_stored_energy_J"},
    "ENERGY_MAPPING": {"z_before", "z_after", "mass_20x20", "D_switch_J", "reported_kinetic_increment_J"},
    "POST_RELEASE_TARGET_TRACE": {"time_s", "independent_target_state_13", "candidate_target_state_13", "candidate_target_source", "parent_crosscheck_terminal_max_abs"},
    "CONTACT_TRACE": {"contact_kernel_enabled", "contact_force_N", "contact_torque_N_m"},
    "REFERENCE_PAIR": {"rk4", "midpoint", "event_time_tolerance_s", "work_relative_tolerance", "work_absolute_floor_J"},
    "REGISTERED_SCHEDULE": {"schedule"},
    "A2_COMMAND_OR_TRACE_PAIR": {"lanes", "pair_kind", "parent_level", "left_variant", "right_variant"},
    "GOVERNANCE_CANDIDATE": {"candidate"},
    "SELECTOR_REPORT": {"report"},
}

CLAIM_BOUNDARY = (
    "mutation replay evidence only; no A1/A2 outcome, physical, current-system, "
    "formal NC19, Owner, production, release or next-stage credit"
)


def expected_patch_target(
    parent_id: str,
    subvariant_index: int,
    mutation_spec: Mapping[str, Any],
) -> str | list[str] | None:
    """Rebuild the frozen semantic target; executor-provided labels are not truth."""

    targets = mutation_spec.get("deterministic_targets_and_amplitudes", {})
    if parent_id == "B4FNC01":
        return [
            "/payload/candidate_record/path", "/payload/candidate_record/bytes",
            "/payload/candidate_record/sha256", "/payload/candidate_bytes_path",
            "/payload/xor_mutation",
        ]
    if parent_id == "B4FNC02" and subvariant_index in (1, 2):
        return f"/payload/observed_Q_14/{11 + subvariant_index}"
    if parent_id == "B4FNC03" and 1 <= subvariant_index <= 12:
        return f"/payload/observed_Q_14/{subvariant_index - 1}"
    if parent_id == "B4FNC04" and subvariant_index in (1, 2):
        return f"/payload/consumed_signs/{subvariant_index - 1}"
    fixed: dict[str, str | list[str]] = {
        "B4FNC05": "/payload/signed_W_act_J",
        "B4FNC06": ["/payload/signed_W_act_J", "/payload/energy_minus_work_residual_J"],
        "B4FNC07": "/payload/W_after_mapping_J",
        "B4FNC10": ["/payload/observed_finite_event", "/payload/classifier_mode"],
        "B4FNC11": [
            "/payload/z_after", "/payload/linear_impulse_N_s",
            "/payload/angular_impulse_N_m_s", "/payload/kinetic_energy_jump_J",
        ],
        "B4FNC12": ["/payload/z_after", "/payload/reported_kinetic_increment_J"],
        "B4FNC13": [
            "/payload/candidate_target_state_13", "/payload/candidate_target_source",
            "/payload/parent_crosscheck_terminal_max_abs",
        ],
        "B4FNC14": [
            "/payload/contact_kernel_enabled", "/payload/contact_force_N",
            "/payload/contact_torque_N_m",
        ],
        "B4FNC16": "/payload/schedule/slots/-",
        "B4FNC18": "/payload/candidate/hardware_specification_released",
    }
    if parent_id in fixed:
        return fixed[parent_id]
    if parent_id == "B4FNC08" and subvariant_index in (1, 2):
        side = "left" if subvariant_index == 1 else "right"
        return [
            f"/payload/observed_Q_14/{11 + subvariant_index}",
            f"/payload/harness_command/dwell_hold_N/{side}",
        ]
    if parent_id == "B4FNC09" and subvariant_index in (1, 2):
        return ["/payload/observed_finite_event", "/payload/classifier_mode"]
    if parent_id == "B4FNC15" and subvariant_index in (1, 2):
        return "/payload/rk4" if subvariant_index == 1 else "/payload/midpoint"
    if parent_id == "B4FNC17" and subvariant_index in (1, 2):
        # One registered pair member is mutated in every frozen lane.
        return [f"/payload/lanes/{index}/right_Q_2/1" for index in range(6)]
    if parent_id == "B4FNC19":
        fields = targets.get("nc19_required_false_fields", [])
        if isinstance(fields, list) and 1 <= subvariant_index <= len(fields):
            return f"/payload/candidate/{fields[subvariant_index - 1]}"
    if parent_id == "B4FNC20":
        fields = targets.get("nc20_required_null_fields", [])
        if isinstance(fields, list) and 1 <= subvariant_index <= len(fields):
            return f"/payload/candidate/{fields[subvariant_index - 1]}"
    if parent_id == "B4FNC21" and 1 <= subvariant_index <= 6:
        return (
            f"/payload/P_coordinates_m/{0 if subvariant_index <= 2 else 1}"
            if subvariant_index <= 4
            else "/payload/clipping_used" if subvariant_index == 5
            else "/payload/extrapolation_used"
        )
    if parent_id == "B4FNC22" and subvariant_index in (1, 2):
        return (
            "/payload/report/reported_label" if subvariant_index == 1
            else "/payload/report/minimum_required_force_or_work_claimed"
        )
    return None


def validate_patch_semantics(
    *,
    parent_id: str,
    subvariant_index: int,
    target: Any,
    patch: Mapping[str, Any],
    base_payload: Mapping[str, Any],
    mutation_spec: Mapping[str, Any],
    frozen_q_ref: float,
) -> bool:
    """Reject gate-killing but preregistration-inconsistent or duplicate mutations."""

    expected = expected_patch_target(parent_id, subvariant_index, mutation_spec)
    operations = patch.get("operations")
    if expected is None or target != expected or patch.get("target") != expected:
        return False
    expected_paths = expected if isinstance(expected, list) else [expected]
    if not isinstance(operations, list) or [row.get("path") for row in operations if isinstance(row, dict)] != expected_paths:
        return False
    expected_op = "add" if parent_id == "B4FNC16" else "replace"
    if any(not isinstance(row, dict) or row.get("op") != expected_op for row in operations):
        return False
    values = [row.get("value") for row in operations]
    targets = mutation_spec.get("deterministic_targets_and_amplitudes", {})
    if parent_id in {"B4FNC02", "B4FNC03"}:
        return len(values) == 1 and finite_number(values[0]) and float(values[0]) == float(frozen_q_ref)
    if parent_id == "B4FNC04":
        return values == [-1]
    if parent_id == "B4FNC07":
        return values == [0.0]
    if parent_id == "B4FNC08":
        return len(values) == 2 and all(finite_number(value) and float(value) == float(frozen_q_ref) for value in values)
    if parent_id == "B4FNC09":
        expected_mode = "SINGLE_SIDE_LEFT" if subvariant_index == 1 else "SINGLE_SIDE_RIGHT"
        return values == [True, expected_mode]
    if parent_id == "B4FNC10":
        return values == [True, "ENDPOINT_ONLY"]
    if parent_id == "B4FNC14":
        return bool(values and values[0] is True)
    if parent_id == "B4FNC16":
        levels = targets.get("unregistered_levels", [])
        return isinstance(levels, list) and 1 <= subvariant_index <= len(levels) and values == [levels[subvariant_index - 1]]
    if parent_id == "B4FNC18":
        return values == [True]
    if parent_id == "B4FNC17":
        parent = base_payload.get("parent_level")
        if not isinstance(parent, dict):
            return False
        alpha = parent.get("alpha")
        qref = parent.get("Q_ref_N")
        if not finite_number(alpha) or not finite_number(qref) or float(qref) != float(frozen_q_ref):
            return False
        ratio = 0.75 if subvariant_index == 1 else 0.25
        expected_value = ratio * float(alpha) * float(frozen_q_ref)
        return len(values) == 6 and all(
            finite_number(value) and float(value) == expected_value for value in values
        )
    if parent_id == "B4FNC19":
        return values == [True]
    if parent_id == "B4FNC20":
        return values == [0.0]
    if parent_id == "B4FNC21":
        domain_mutants = targets.get("P_domain_mutants", [])
        if not isinstance(domain_mutants, list) or not (1 <= subvariant_index <= len(domain_mutants)):
            return False
        registered = domain_mutants[subvariant_index - 1]
        if subvariant_index <= 4:
            return values == [registered.get("value_m")]
        return values == [True]
    if parent_id == "B4FNC22":
        return values == (["minimum_required_force"] if subvariant_index == 1 else [True])
    # The remaining mutations use trajectory- or matrix-derived values.  Their
    # exact paths/op count are frozen here; the independent Gate evaluator
    # validates the resulting numerical relation.
    return True


def independent_gate_record(gate_id: str, replay_type: str, passed: bool) -> dict[str, Any]:
    return {
        "schema": "SIM13_V4B4G_INDEPENDENT_MUTATION_GATE_REPLAY_V1",
        "gate_id": gate_id,
        "evaluation_status": "PASS" if passed else "FAIL",
        "scientific_predicate": bool(passed),
        "failed_gate_ids": [] if passed else [gate_id],
        "replay_type": replay_type,
    }


def _decode_pointer(path: str) -> list[str]:
    if not isinstance(path, str) or not path.startswith("/") or path == "/":
        raise ValueError("PATCH_POINTER_INVALID_OR_ROOT")
    decoded: list[str] = []
    for encoded in path[1:].split("/"):
        token: list[str] = []
        index = 0
        while index < len(encoded):
            character = encoded[index]
            if character != "~":
                token.append(character)
                index += 1
                continue
            if index + 1 >= len(encoded) or encoded[index + 1] not in {"0", "1"}:
                raise ValueError("PATCH_POINTER_INVALID_ESCAPE")
            token.append("~" if encoded[index + 1] == "0" else "/")
            index += 2
        decoded.append("".join(token))
    return decoded


def _list_index(token: str, *, length: int, allow_end: bool) -> int:
    if not isinstance(token, str) or not token:
        raise ValueError("PATCH_LIST_INDEX_INVALID")
    if token != "0" and (not token.isascii() or not token.isdigit() or token.startswith("0")):
        raise ValueError("PATCH_LIST_INDEX_NONCANONICAL")
    if token == "0":
        index = 0
    else:
        index = int(token)
    upper = length if allow_end else length - 1
    if index < 0 or index > upper:
        raise ValueError("PATCH_LIST_INDEX_OUT_OF_RANGE")
    return index


def _container_and_token(document: Any, tokens: Sequence[str]) -> tuple[Any, str]:
    cursor = document
    for token in tokens[:-1]:
        if isinstance(cursor, list):
            cursor = cursor[_list_index(token, length=len(cursor), allow_end=False)]
        elif isinstance(cursor, dict):
            cursor = cursor[token]
        else:
            raise ValueError("PATCH_PATH_TRAVERSES_SCALAR")
    return cursor, tokens[-1]


def apply_restricted_patch(base: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    if set(patch) != {
        "schema", "receipt_id", "target", "format", "base_sha256",
        "mutant_sha256", "operations",
    }:
        raise ValueError("PATCH_FIELDS_NOT_EXACT")
    if patch.get("schema") != "SIM13_V4B4G_MUTATION_PATCH_V1" or patch.get("format") != "RFC6902_JSON_V1_RESTRICTED":
        raise ValueError("PATCH_SCHEMA_OR_FORMAT")
    operations = patch.get("operations")
    if not isinstance(operations, list) or not operations:
        raise ValueError("PATCH_OPERATIONS_EMPTY")
    result: Any = deepcopy(base)
    for operation in operations:
        if not isinstance(operation, dict) or operation.get("op") not in {"add", "remove", "replace"}:
            raise ValueError("PATCH_OPERATION_FORBIDDEN")
        op = operation["op"]
        expected_fields = {"op", "path"} if op == "remove" else {"op", "path", "value"}
        if set(operation) != expected_fields:
            raise ValueError("PATCH_OPERATION_FIELDS_NOT_EXACT")
        tokens = _decode_pointer(operation.get("path"))
        container, token = _container_and_token(result, tokens)
        if isinstance(container, list):
            if op == "add" and token == "-":
                container.append(deepcopy(operation["value"]))
                continue
            if token == "-":
                raise ValueError("PATCH_LIST_DASH_ONLY_VALID_FOR_ADD")
            index = _list_index(
                token, length=len(container), allow_end=(op == "add"),
            )
            if op == "add":
                container.insert(index, deepcopy(operation["value"]))
            elif op == "replace":
                container[index] = deepcopy(operation["value"])
            else:
                del container[index]
        elif isinstance(container, dict):
            if op == "add":
                container[token] = deepcopy(operation["value"])
            elif op == "replace":
                if token not in container:
                    raise ValueError("PATCH_REPLACE_KEY_MISSING")
                container[token] = deepcopy(operation["value"])
            else:
                if token not in container:
                    raise ValueError("PATCH_REMOVE_KEY_MISSING")
                del container[token]
        else:
            raise ValueError("PATCH_TARGET_SCALAR")
    if not isinstance(result, dict):
        raise ValueError("PATCH_RESULT_NOT_OBJECT")
    return result


def _inside_project(path: Path, project_root: Path) -> bool:
    try:
        path.resolve().relative_to(project_root.resolve())
        return True
    except ValueError:
        return False


def load_artifact_record(
    report: ValidationReport,
    record: Mapping[str, Any],
    *,
    project_root: Path,
    phase_root: Path,
    code: str,
) -> tuple[Path, dict[str, Any]] | None:
    required = {"path", "bytes", "sha256", "media_type", "replay_type"}
    if not report.require(
        set(record) == required,
        f"{code}_FIELDS",
        {
            "missing": sorted(required - set(record)),
            "extra": sorted(set(record) - required),
        },
    ):
        return None
    path = resolve_declared(project_root, phase_root, record["path"])
    if not report.require(
        _inside_project(path, project_root), f"{code}_OUTSIDE_PROJECT",
        path.as_posix(),
    ):
        return None
    if not verify_file_record(report, path=path, expected_bytes=record["bytes"], expected_sha256=record["sha256"], code=code):
        return None
    value = report.guard(f"{code}_JSON", lambda: read_json_strict(path))
    if value is None:
        return None
    report.require(path.read_bytes() == canonical_bytes(value) + b"\n", f"{code}_NOT_CANONICAL")
    return path, value


def validate_bundle(
    report: ValidationReport,
    bundle: Mapping[str, Any],
    *,
    bundle_path: Path,
    receipt_id: str,
    parent_id: str,
    gate_id: str,
    replay_type: str,
    project_root: Path,
    phase_root: Path,
) -> bool:
    required = {"schema", "receipt_id", "parent_id", "mutation_id", "gate_id", "replay_type", "execution_provenance", "artifact_records", "payload", "claim_boundary"}
    ok = report.require(
        set(bundle) == required,
        "REPLAY_BUNDLE_FIELDS",
        {
            "receipt": receipt_id,
            "missing": sorted(required - set(bundle)),
            "extra": sorted(set(bundle) - required),
        },
    )
    ok &= report.require(bundle.get("schema") == "SIM13_V4B4G_MUTATION_REPLAY_BUNDLE_V1", "REPLAY_BUNDLE_SCHEMA", receipt_id)
    ok &= report.require(bundle.get("receipt_id") == receipt_id and bundle.get("parent_id") == parent_id, "REPLAY_BUNDLE_RECEIPT_PARENT", receipt_id)
    ok &= report.require(bundle.get("gate_id") == gate_id and bundle.get("replay_type") == replay_type, "REPLAY_BUNDLE_GATE_TYPE", receipt_id)
    ok &= report.require(bundle.get("claim_boundary") == CLAIM_BOUNDARY, "REPLAY_BUNDLE_CLAIM_BOUNDARY", receipt_id)
    payload = bundle.get("payload", {})
    ok &= report.require(
        isinstance(payload, dict) and set(payload) == PAYLOAD_FIELDS[replay_type],
        "REPLAY_PAYLOAD_FIELDS",
        {
            "receipt": receipt_id,
            "missing": sorted(
                PAYLOAD_FIELDS[replay_type] - set(payload)
                if isinstance(payload, dict) else PAYLOAD_FIELDS[replay_type]
            ),
            "extra": sorted(
                set(payload) - PAYLOAD_FIELDS[replay_type]
                if isinstance(payload, dict) else []
            ),
        },
    )
    provenance = bundle.get("execution_provenance", {})
    provenance_fields = {"producer_entrypoint_path", "producer_entrypoint_sha256", "execution_mode", "real_path_id", "source_manifest_sha256", "underlying_artifact_inventory_sha256"}
    ok &= report.require(
        isinstance(provenance, dict) and set(provenance) == provenance_fields,
        "REPLAY_PROVENANCE_FIELDS", receipt_id,
    )
    if isinstance(provenance, dict):
        producer = resolve_declared(project_root, phase_root, provenance.get("producer_entrypoint_path"))
        ok &= report.require(_inside_project(producer, project_root) and producer.is_file(), "REPLAY_PRODUCER_MISSING", receipt_id)
        if producer.is_file():
            ok &= report.require(sha256_file(producer) == provenance.get("producer_entrypoint_sha256"), "REPLAY_PRODUCER_HASH", receipt_id)
        ok &= report.require(provenance.get("execution_mode") in {"REAL_EXECUTED_PATH", "RAW_ARTIFACT_MUTATION"}, "REPLAY_EXECUTION_MODE", receipt_id)
        ok &= report.require(isinstance(provenance.get("real_path_id"), str) and bool(provenance.get("real_path_id")), "REPLAY_REAL_PATH_ID", receipt_id)
        ok &= report.require(is_sha256(provenance.get("source_manifest_sha256")), "REPLAY_SOURCE_MANIFEST_SHA", receipt_id)
    rows = bundle.get("artifact_records", [])
    ok &= report.require(isinstance(rows, list) and len(rows) >= 2, "REPLAY_UNDERLYING_ARTIFACTS_INCOMPLETE", receipt_id)
    if isinstance(rows, list):
        ok &= report.require(
            bool(rows) and isinstance(rows[0], dict)
            and rows[0].get("role") == "EXECUTION_SOURCE_MANIFEST",
            "REPLAY_SOURCE_MANIFEST_NOT_FIRST_ARTIFACT",
            receipt_id,
        )
        inventory_sha256 = report.guard(
            "REPLAY_UNDERLYING_ARTIFACT_INVENTORY_CANONICALIZATION",
            lambda: canonical_sha256(rows),
        )
        ok &= report.require(
            inventory_sha256 is not None
            and provenance.get("underlying_artifact_inventory_sha256") == inventory_sha256,
            "REPLAY_UNDERLYING_ARTIFACT_INVENTORY_HASH",
            receipt_id,
        )
    source_manifest_bound = False
    substantive_artifact_bound = False
    resolved_artifact_paths: list[Path] = []
    for index, row in enumerate(rows if isinstance(rows, list) else []):
        if not isinstance(row, dict):
            ok &= report.require(False, "REPLAY_UNDERLYING_RECORD_NOT_OBJECT", {"receipt": receipt_id, "index": index})
            continue
        fields = {"role", "path", "bytes", "sha256"}
        ok &= report.require(
            set(row) == fields,
            "REPLAY_UNDERLYING_RECORD_FIELDS",
            {"receipt": receipt_id, "index": index},
        )
        path = resolve_declared(project_root, phase_root, row.get("path"))
        resolved_artifact_paths.append(path)
        row_inside = report.require(
            _inside_project(path, project_root),
            "REPLAY_UNDERLYING_OUTSIDE_PROJECT", path.as_posix(),
        )
        ok &= row_inside
        if row_inside:
            ok &= verify_file_record(report, path=path, expected_bytes=row.get("bytes"), expected_sha256=row.get("sha256"), code=f"REPLAY_UNDERLYING_{receipt_id}_{index:02d}")
        ok &= report.require(path.resolve() != bundle_path.resolve(), "REPLAY_BUNDLE_SELF_REFERENCE", receipt_id)
        if row.get("role") == "EXECUTION_SOURCE_MANIFEST" and row.get("sha256") == provenance.get("source_manifest_sha256"):
            source_manifest_bound = True
        elif row.get("role") != "EXECUTION_SOURCE_MANIFEST":
            substantive_artifact_bound = True
    ok &= report.require(source_manifest_bound, "REPLAY_SOURCE_MANIFEST_NOT_ARTIFACT_BOUND", receipt_id)
    ok &= report.require(substantive_artifact_bound, "REPLAY_SUBSTANTIVE_BASE_SOURCE_NOT_BOUND", receipt_id)
    ok &= report.require(len(set(resolved_artifact_paths)) == len(resolved_artifact_paths), "REPLAY_UNDERLYING_ARTIFACT_PATH_DUPLICATE", receipt_id)
    return bool(ok)


def _profile(sample_time: float, acquisition: float, arm: Mapping[str, Any], qref: float) -> float:
    alpha = float(arm["alpha"]); delay = float(arm["delay_s"]); duration = float(arm["duration_s"])
    start = acquisition + delay; end = start + duration
    if duration <= 0.0 or alpha == 0.0 or sample_time <= start or sample_time >= end:
        return 0.0
    return alpha * qref * math.sin(math.pi * (sample_time - start) / duration) ** 2


def _registered_slot(
    candidate: Any,
    frozen_schedule: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    """Return the one byte-semantically registered slot, never a label-only match."""

    if not isinstance(candidate, dict):
        return None
    slots = frozen_schedule.get("slots")
    if not isinstance(slots, list):
        return None
    matches = [slot for slot in slots if isinstance(slot, dict) and slot == candidate]
    return matches[0] if len(matches) == 1 else None


def _expected_command_sides(
    slot: Mapping[str, Any],
    command: Mapping[str, Any],
) -> tuple[dict[str, float], dict[str, float]] | None:
    zero = {"alpha": 0.0, "delay_s": 0.0, "duration_s": 0.0}
    arm = slot.get("arm")
    if arm == "A0":
        return dict(zero), dict(zero)
    if arm == "A1":
        side = {
            "alpha": float(slot["alpha"]), "delay_s": 0.0,
            "duration_s": float(slot["command_duration_s"]),
        }
        return dict(side), dict(side)
    if arm != "A2":
        return None
    parent = command.get("selected_parent_level")
    if not isinstance(parent, dict):
        return None
    alpha = float(parent["alpha"])
    duration = float(parent["command_duration_s"])
    full = {"alpha": alpha, "delay_s": 0.0, "duration_s": duration}
    off = {"alpha": 0.0, "delay_s": 0.0, "duration_s": duration}
    half = {"alpha": 0.5 * alpha, "delay_s": 0.005, "duration_s": duration}
    return {
        "RIGHT_HALF_DELAY": (dict(full), dict(half)),
        "LEFT_HALF_DELAY_MIRROR": (dict(half), dict(full)),
        "RIGHT_COMMAND_OFF": (dict(full), dict(off)),
        "LEFT_COMMAND_OFF_MIRROR": (dict(off), dict(full)),
    }.get(str(slot.get("variant_id")))


def _command_trace_matches_registered_slot(
    payload: Mapping[str, Any],
    *,
    frozen_schedule: Mapping[str, Any],
    frozen_q_ref: float,
    mutation_spec: Mapping[str, Any],
    parent_id: str,
) -> bool:
    slot = _registered_slot(payload.get("slot"), frozen_schedule)
    command = payload.get("command_parameters")
    if slot is None or not isinstance(command, dict) or payload.get("arm") != slot.get("arm"):
        return False
    acquisition = payload.get("acquisition_time_s")
    sample_time = payload.get("sample_time_s")
    qref = payload.get("Q_ref_N")
    if not all(finite_number(value) for value in (acquisition, sample_time, qref)):
        return False
    if float(qref) != float(frozen_q_ref):
        return False
    origin = payload.get("trace_origin")
    if origin == "REGISTERED_CAMPAIGN_CASE":
        if parent_id not in {"B4FNC02", "B4FNC03"}:
            return False
        if payload.get("harness_id") is not None or payload.get("harness_command") is not None:
            return False
        expected_sides = _expected_command_sides(slot, command)
        dwell_hold = {"left": 0.0, "right": 0.0}
    elif origin == "FROZEN_FINITE_EVENT_HARNESS":
        if parent_id != "B4FNC08":
            return False
        finite_harness = mutation_spec.get("finite_event_harness", {})
        targets = mutation_spec.get("deterministic_targets_and_amplitudes", {})
        if (
            payload.get("harness_id") != finite_harness.get("id")
            or slot.get("case_id") != targets.get("default_registered_forced_slot")
        ):
            return False
        force_pulse = finite_harness.get("force_pulse")
        harness_command = payload.get("harness_command")
        if not isinstance(force_pulse, dict) or not isinstance(harness_command, dict):
            return False
        if harness_command.get("force_pulse") != force_pulse:
            return False
        dwell_hold = harness_command.get("dwell_hold_N")
        if not isinstance(dwell_hold, dict) or set(dwell_hold) != {"left", "right"}:
            return False
        if not all(finite_number(dwell_hold.get(side)) for side in ("left", "right")):
            return False
        expected_sides = (
            {
                "alpha": float(force_pulse["alpha_left"]), "delay_s": 0.0,
                "duration_s": float(force_pulse["T_cmd_s"]),
            },
            {
                "alpha": float(force_pulse["alpha_right"]), "delay_s": 0.0,
                "duration_s": float(force_pulse["T_cmd_s"]),
            },
        )
    else:
        return False
    if expected_sides is None:
        return False
    for side_name, expected_side in zip(("left", "right"), expected_sides):
        side = command.get(side_name)
        if not isinstance(side, dict):
            return False
        for field, expected in expected_side.items():
            value = side.get(field)
            if not finite_number(value) or float(value) != expected:
                return False
    q = np.asarray(payload.get("observed_Q_14"), dtype=float)
    if q.shape != (14,) or not np.all(np.isfinite(q)):
        return False
    expected_q = np.zeros(14, dtype=float)
    expected_q[12] = _profile(float(sample_time), float(acquisition), expected_sides[0], float(frozen_q_ref))
    expected_q[13] = _profile(float(sample_time), float(acquisition), expected_sides[1], float(frozen_q_ref))
    if origin == "FROZEN_FINITE_EVENT_HARNESS" and payload.get("clearance_dwell_active") is True:
        expected_q[12] += float(dwell_hold["left"])
        expected_q[13] += float(dwell_hold["right"])
    return bool(np.array_equal(q, expected_q))


def _real_roots_unit(coefficients: Sequence[float]) -> list[float]:
    coefficients_array = np.asarray(coefficients, dtype=float)
    scale = float(np.max(np.abs(coefficients_array))) if len(coefficients_array) else 0.0
    if not math.isfinite(scale) or scale == 0.0:
        return []
    coefficients_array = coefficients_array / scale
    first = 0
    while first < len(coefficients_array) - 1 and abs(float(coefficients_array[first])) <= 1.0e-14:
        first += 1
    coefficients_array = coefficients_array[first:]
    if len(coefficients_array) <= 1:
        return []
    roots = np.roots(coefficients_array)
    result = [float(root.real) for root in roots if abs(float(root.imag)) <= 1.0e-10 and -1.0e-12 <= float(root.real) <= 1.0 + 1.0e-12]
    return sorted(set(round(min(1.0, max(0.0, value)), 14) for value in result))


def _hermite_coefficients(y0: float, y1: float, d0: float, d1: float, dt: float) -> tuple[float, float, float, float]:
    # a*s^3+b*s^2+c*s+d on s in [0,1]
    return (2*y0 - 2*y1 + dt*(d0+d1), -3*y0 + 3*y1 - dt*(2*d0+d1), dt*d0, y0)


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
    if not (time.ndim == 1 and len(time) >= 2 and np.all(np.diff(time) > 0.0)):
        raise ValueError("CLEARANCE_TIME_INVALID")
    if any(array.shape != time.shape for array in (left_gap, right_gap, left_rate, right_rate)) or ledger.shape != (len(time)-1,):
        raise ValueError("CLEARANCE_SHAPE_INVALID")
    if not all(np.all(np.isfinite(value)) for value in (time,left_gap,right_gap,left_rate,right_rate)):
        raise ValueError("CLEARANCE_NONFINITE")
    eligible_segments: list[tuple[float, float]] = []
    for index in range(len(time)-1):
        if not ledger[index]:
            continue
        dt = float(time[index+1] - time[index])
        polys: list[tuple[float, float, float, float]] = []
        for gap, rate in ((left_gap, left_rate), (right_gap, right_rate)):
            a, b, c, d = _hermite_coefficients(float(gap[index]), float(gap[index+1]), float(rate[index]), float(rate[index+1]), dt)
            polys.append((a, b, c, d))
        boundaries = {0.0, 1.0}
        for a, b, c, d in polys:
            boundaries.update(_real_roots_unit((a, b, c, d - 1.0e-6)))
            boundaries.update(_real_roots_unit((3*a/dt, 2*b/dt, c/dt + 1.0e-6)))
        ordered = sorted(boundaries)
        for lo, hi in zip(ordered[:-1], ordered[1:]):
            if hi - lo <= 1.0e-13:
                continue
            middle = 0.5*(lo+hi)
            passed = True
            for a, b, c, d in polys:
                gap_value = ((a*middle+b)*middle+c)*middle+d
                rate_value = (3*a*middle*middle+2*b*middle+c)/dt
                passed &= gap_value >= 1.0e-6 and rate_value >= -1.0e-6
            if passed:
                eligible_segments.append((float(time[index]+lo*dt), float(time[index]+hi*dt)))
    merged: list[list[float]] = []
    for start, end in sorted(eligible_segments):
        if merged and start <= merged[-1][1] + 1.0e-12:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
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


def _clearance_expected(payload: Mapping[str, Any]) -> bool:
    result = certify_clearance_independent(
        payload["time_s"], payload["left_gap_m"], payload["right_gap_m"],
        payload["left_gap_rate_m_s"], payload["right_gap_rate_m_s"],
        acquisition_time_s=float(payload["acquisition_time_s"]),
        ledger_interval_certified=payload["ledger_interval_certified"],
    )
    return bool(result["finite_event"])


def _clearance_history_is_frozen_fixture(
    payload: Mapping[str, Any],
    *,
    parent_id: str,
    mutation_spec: Mapping[str, Any],
) -> bool:
    targets = mutation_spec.get("deterministic_targets_and_amplitudes", {})
    fixture_name = {
        "B4FNC09": "single_side_classifier_fixture",
        "B4FNC10": "endpoint_only_classifier_fixture",
    }.get(parent_id)
    if fixture_name is None:
        return False
    fixture = targets.get(fixture_name)
    if not isinstance(fixture, dict):
        return False
    canonical = fixture.get("canonical_payload")
    if not isinstance(canonical, dict) or canonical_sha256(canonical) != fixture.get("canonical_payload_sha256"):
        return False
    fields = {
        "time_s", "acquisition_time_s", "left_gap_m", "right_gap_m",
        "left_gap_rate_m_s", "right_gap_rate_m_s",
    }
    if any(payload.get(field) != canonical.get(field) for field in fields):
        return False
    time = canonical.get("time_s")
    return bool(
        isinstance(time, list)
        and payload.get("ledger_interval_certified") == [True] * (len(time) - 1)
    )


def evaluate_payload(
    replay_type: str,
    gate_id: str,
    payload: Mapping[str, Any],
    *,
    parent_id: str,
    frozen_schedule: Mapping[str, Any],
    frozen_q_ref: float,
    mutation_spec: Mapping[str, Any],
    required_false: Mapping[str, Any],
    required_null_names: Sequence[str],
    project_root: Path,
    phase_root: Path,
) -> bool:
    try:
        if replay_type == "BOUND_SOURCE_BYTES":
            source = payload["source_record"]; candidate = payload["candidate_record"]
            path = resolve_declared(project_root, phase_root, payload["candidate_bytes_path"])
            registered_source = mutation_spec.get("deterministic_targets_and_amplitudes", {}).get("source_byte_drift", {}).get("source_id")
            return bool(payload.get("source_id") == registered_source and isinstance(source,dict) and isinstance(candidate,dict) and finite_number(source.get("bytes")) and finite_number(candidate.get("bytes")) and is_sha256(source.get("sha256")) and is_sha256(candidate.get("sha256")) and path.is_file() and path.stat().st_size == int(candidate["bytes"]) and sha256_file(path) == candidate["sha256"] and candidate["bytes"] == source["bytes"] and candidate["sha256"] == source["sha256"])
        if replay_type == "COMMAND_TRACE":
            q = np.asarray(payload["observed_Q_14"], dtype=float)
            if q.shape != (14,) or not np.all(np.isfinite(q)):
                return False
            registered_trace = _command_trace_matches_registered_slot(
                payload,
                frozen_schedule=frozen_schedule,
                frozen_q_ref=frozen_q_ref,
                mutation_spec=mutation_spec,
                parent_id=parent_id,
            )
            if gate_id.startswith("B4F-G02"):
                command = payload["command_parameters"]
                return bool(registered_trace and payload["arm"] == "A0" and np.all(q == 0.0) and all(float(command[side][field]) == 0.0 for side in ("left", "right") for field in ("alpha", "delay_s", "duration_s")))
            if gate_id.startswith("B4F-G03"):
                return bool(registered_trace and np.all(q[:12] == 0.0))
            if gate_id.startswith("B4F-G08"):
                return bool(registered_trace and payload["clearance_dwell_active"] is True and np.all(q == 0.0))
            return False
        if replay_type == "GEOMETRY_SIGN_TRACE":
            p = np.asarray(payload["P_coordinates_m"], dtype=float)
            jac = np.asarray(payload["raw_gap_jacobian_P"], dtype=float)
            step = float(payload["centered_step_m"])
            return bool(p.shape == (2,) and jac.shape == (2,2) and np.all(np.isfinite(p)) and np.all(np.isfinite(jac)) and step == 1.0e-7 and np.all(p-step >= 0.0) and np.all(p+step <= 0.0715) and jac[0,0] > 0.0 and jac[1,1] > 0.0 and payload["registered_signs"] == [1,1] and payload["consumed_signs"] == [1,1] and not payload["clipping_used"] and not payload["extrapolation_used"])
        if replay_type == "WORK_TRACE":
            time = np.asarray(payload["time_s"], dtype=float); q = np.asarray(payload["Q_P_N"], dtype=float); eta = np.asarray(payload["eta_P_m_s"], dtype=float); work = np.asarray(payload["signed_W_act_J"], dtype=float); residual = np.asarray(payload["energy_minus_work_residual_J"], dtype=float)
            if len(time) < 2 or q.shape != (len(time),2) or eta.shape != (len(time),2) or work.shape != time.shape or residual.shape != time.shape:
                return False
            if not all(np.all(np.isfinite(array)) for array in (time, q, eta, work, residual)) or not np.all(np.diff(time) > 0.0):
                return False
            power = np.sum(q*eta, axis=1)
            trapezoid = getattr(np, "trapezoid", None)
            trap = float(trapezoid(power, time)) if trapezoid is not None else float(np.trapz(power, time))
            cumulative = np.concatenate((
                np.asarray([float(work[0])]),
                float(work[0]) + np.cumsum(0.5 * (power[:-1] + power[1:]) * np.diff(time)),
            ))
            if gate_id.startswith("B4F-G04"):
                return abs(trap-float(work[-1]-work[0])) <= 1.0e-7 and float(np.max(np.abs(cumulative-work))) <= 1.0e-7
            return float(np.max(np.abs(residual))) <= 1.0e-7
        if replay_type == "REMOVAL_WORK_MAPPING":
            return bool(payload["finite_removal_event"] is True and finite_number(payload["W_before_removal_J"]) and finite_number(payload["W_after_mapping_J"]) and abs(float(payload["W_before_removal_J"])) > 1.0e-12 and abs(float(payload["W_after_mapping_J"])-float(payload["W_before_removal_J"])) <= 1.0e-15)
        if replay_type == "CLEARANCE_TRACE":
            return bool(
                _clearance_history_is_frozen_fixture(
                    payload, parent_id=parent_id, mutation_spec=mutation_spec,
                )
                and
                payload.get("classifier_mode")
                == "BILATERAL_HERMITE_ALL_ROOT_EARLIEST_DWELL"
                and payload["observed_finite_event"] is _clearance_expected(payload)
            )
        if replay_type == "REMOVAL_MAPPING":
            before=np.asarray(payload["z_before"],float); after=np.asarray(payload["z_after"],float)
            linear=np.asarray(payload["linear_impulse_N_s"],float); angular=np.asarray(payload["angular_impulse_N_m_s"],float)
            return bool(before.shape==(20,) and after.shape==(20,) and linear.shape==(3,) and angular.shape==(3,) and all(np.all(np.isfinite(array)) for array in (before,after,linear,angular)) and np.max(np.abs(after-before))<=1.0e-12 and np.max(np.abs(linear))<=1.0e-12 and np.max(np.abs(angular))<=1.0e-12 and finite_number(payload["kinetic_energy_jump_J"]) and finite_number(payload["ideal_constraint_stored_energy_J"]) and abs(float(payload["kinetic_energy_jump_J"]))<=1.0e-12 and float(payload["ideal_constraint_stored_energy_J"])==0.0)
        if replay_type == "ENERGY_MAPPING":
            before=np.asarray(payload["z_before"],float); after=np.asarray(payload["z_after"],float); mass=np.asarray(payload["mass_20x20"],float)
            if before.shape!=(20,) or after.shape!=(20,) or mass.shape!=(20,20) or not all(np.all(np.isfinite(array)) for array in (before,after,mass)) or not np.array_equal(mass,mass.T): return False
            np.linalg.cholesky(mass)
            increment=0.5*float(after@mass@after-before@mass@before)
            return finite_number(payload["reported_kinetic_increment_J"]) and abs(increment-float(payload["reported_kinetic_increment_J"]))<=1.0e-10 and abs(increment)<=1.0e-12
        if replay_type == "POST_RELEASE_TARGET_TRACE":
            independent=np.asarray(payload["independent_target_state_13"],float); candidate=np.asarray(payload["candidate_target_state_13"],float)
            time=np.asarray(payload["time_s"],float)
            return bool(independent.ndim==2 and independent.shape[1:]==(13,) and len(independent)>=2 and candidate.shape==independent.shape and time.shape==(len(independent),) and np.all(np.diff(time)>0.0) and all(np.all(np.isfinite(array)) for array in (time,independent,candidate)) and payload["candidate_target_source"]=="INDEPENDENT_13D_POST_STATE" and np.max(np.abs(candidate-independent))<=1.0e-12 and finite_number(payload["parent_crosscheck_terminal_max_abs"]) and float(payload["parent_crosscheck_terminal_max_abs"])<=1.0e-12)
        if replay_type == "CONTACT_TRACE":
            force=np.asarray(payload["contact_force_N"],float); torque=np.asarray(payload["contact_torque_N_m"],float)
            return bool(payload["contact_kernel_enabled"] is False and force.size>0 and torque.size>0 and np.all(np.isfinite(force)) and np.all(np.isfinite(torque)) and np.max(np.abs(force))<=1.0e-12 and np.max(np.abs(torque))<=1.0e-12)
        if replay_type == "REFERENCE_PAIR":
            rk=payload["rk4"]; mid=payload["midpoint"]
            provenance=bool(rk["lane_id"]=="RK4_REFERENCE" and mid["lane_id"]=="MIDPOINT_REFERENCE" and rk["fresh_b3_reconstruction"] is True and mid["fresh_b3_reconstruction"] is True and is_sha256(rk["acquisition_certificate_sha256"]) and is_sha256(mid["acquisition_certificate_sha256"]) and is_sha256(rk["clearance_certificate_sha256"]) and is_sha256(mid["clearance_certificate_sha256"]) and rk["acquisition_certificate_sha256"]!=mid["acquisition_certificate_sha256"] and rk["clearance_certificate_sha256"]!=mid["clearance_certificate_sha256"])
            tolerance=max(float(payload["work_absolute_floor_J"]),float(payload["work_relative_tolerance"])*max(abs(float(rk["signed_work_J"])),abs(float(mid["signed_work_J"]))))
            numeric=[payload["event_time_tolerance_s"],payload["work_relative_tolerance"],payload["work_absolute_floor_J"]]+[row[field] for row in (rk,mid) for field in ("acquisition_time_s","removal_time_s","signed_work_J")]
            return bool(all(finite_number(value) for value in numeric) and provenance and rk["finite_removal_event"] is True and mid["finite_removal_event"] is True and rk["post_release_passed"] is True and mid["post_release_passed"] is True and rk["independent_integrity_pass"] is True and mid["independent_integrity_pass"] is True and abs(float(rk["acquisition_time_s"])-float(mid["acquisition_time_s"]))<=float(payload["event_time_tolerance_s"]) and abs(float(rk["removal_time_s"])-float(mid["removal_time_s"]))<=float(payload["event_time_tolerance_s"]) and abs(float(rk["signed_work_J"])-float(mid["signed_work_J"]))<=tolerance)
        if replay_type == "REGISTERED_SCHEDULE":
            return payload["schedule"] == frozen_schedule
        if replay_type == "A2_COMMAND_OR_TRACE_PAIR":
            lanes=payload["lanes"]
            lane_order=["RK4_COARSE","RK4_FINE","RK4_REFERENCE","MIDPOINT_COARSE","MIDPOINT_FINE","MIDPOINT_REFERENCE"]
            parent=payload["parent_level"]
            if not isinstance(parent,dict) or not all(finite_number(parent.get(field)) for field in ("alpha","command_duration_s","Q_ref_N")):
                return False
            alpha=float(parent["alpha"]); duration=float(parent["command_duration_s"]); qref=float(parent["Q_ref_N"])
            registered_levels={(float(row["alpha"]),float(row["command_duration_s"])) for row in frozen_schedule.get("slots",[]) if isinstance(row,dict) and row.get("arm")=="A1"}
            pair=payload["pair_kind"]
            if pair=="HALF_DELAY":
                ratio=0.5; expected_variants=("RIGHT_HALF_DELAY","LEFT_HALF_DELAY_MIRROR")
            elif pair=="COMMAND_OFF":
                ratio=0.0; expected_variants=("RIGHT_COMMAND_OFF","LEFT_COMMAND_OFF_MIRROR")
            else:
                return False
            expected_right=np.asarray([alpha*qref,ratio*alpha*qref],dtype=float)
            expected_left=expected_right[::-1]
            return bool(qref==float(frozen_q_ref) and (alpha,duration) in registered_levels and payload["right_variant"]==expected_variants[0] and payload["left_variant"]==expected_variants[1] and isinstance(lanes,list) and len(lanes)==6 and [row.get("lane_id") for row in lanes if isinstance(row,dict)]==lane_order and all(np.array_equal(np.asarray(row["right_Q_2"],float),expected_right) and np.array_equal(np.asarray(row["left_mirror_Q_2"],float),expected_left) for row in lanes))
        if replay_type == "GOVERNANCE_CANDIDATE":
            candidate=payload["candidate"]
            return bool(all(candidate.get(field) is expected for field,expected in required_false.items()) and all(candidate.get(field,"MISSING") is None for field in required_null_names))
        if replay_type == "SELECTOR_REPORT":
            candidate=payload["report"]
            return bool(candidate.get("reported_label")=="lowest_tested_reachable_alpha_in_registered_discrete_grid" and candidate.get("minimum_required_force_or_work_claimed") is False and candidate.get("continuous_threshold_or_interpolation_claimed") is False and candidate.get("global_unreachability_claimed") is False)
    except (
        KeyError, TypeError, ValueError, IndexError, OverflowError,
        ZeroDivisionError, np.linalg.LinAlgError,
    ):
        return False
    return False
