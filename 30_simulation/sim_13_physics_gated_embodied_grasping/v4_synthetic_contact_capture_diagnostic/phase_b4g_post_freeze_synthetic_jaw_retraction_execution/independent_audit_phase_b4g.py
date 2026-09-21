"""Independent B4G evidence audit and terminal signer.

The audit is deliberately a consumer of frozen files.  It does not import the
B4G solver, campaign runner, mutation executor, read-only validator, shared
evidence helpers, or tests.  Only the Python standard library and NumPy are
used.  All paths in signed records are resolved beneath the project root.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


PHASE_ROOT = Path(os.path.abspath(__file__)).parent
FILE_ATTRIBUTE_REPARSE_POINT = getattr(
    stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x00000400,
)
EVIDENCE_REL = Path("evidence")
RESULTS_REL = Path("results")
MANIFEST_REL = EVIDENCE_REL / "SIM13_V4B4G_EVIDENCE_MANIFEST_SELF_EXCLUDED_V1.json"
VALIDATION_REL = EVIDENCE_REL / "SIM13_V4B4G_EXECUTION_VALIDATION_V1.json"
PREAUDIT_REL = RESULTS_REL / "SIM13_V4B4G_PREAUDIT_GATE_V1.json"
RECEIPT_REL = EVIDENCE_REL / "SIM13_V4B4G_INDEPENDENT_AUDIT_RECEIPT_V1.json"
AUDITED_GATE_REL = RESULTS_REL / "SIM13_V4B4G_AUDITED_GATE_V1.json"
TERMINAL_REL = RESULTS_REL / "SIM13_V4B4G_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"
SUMMARY_REL = RESULTS_REL / "SIM13_V4B4G_CAMPAIGN_SUMMARY_V1.json"
NEGATIVE_REL = Path("b4g_mutation_execution") / "SIM13_V4B4G_NEGATIVE_CONTROL_EVIDENCE_V1.json"
POST_REL = EVIDENCE_REL / "SIM13_V4B4G_POST_RUN_PROTECTED_ASSET_SNAPSHOT_V1.json"
FINAL_CONSUMER_FIRST_RELATIVES = (TERMINAL_REL, AUDITED_GATE_REL, RECEIPT_REL)

CLAIM_BOUNDARY = (
    "registered synthetic discrete-domain execution only; no physical, current-system, "
    "formal NC19, Owner, production or next-stage credit"
)
SCOPE = "SYNTHETIC_REGISTERED_DOMAIN_EXECUTION_AND_AUDIT_ONLY"
MEMORY = {
    "memory_gate_applicable": False,
    "memory_gate_passed": False,
    "owner_override_used": False,
    "classification": "DIAGNOSTIC_ONLY",
}
FORMAL_STATE = {
    "passed": 15,
    "declared": 20,
    "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"],
}
LANES = (
    "RK4_COARSE", "RK4_FINE", "RK4_REFERENCE",
    "MIDPOINT_COARSE", "MIDPOINT_FINE", "MIDPOINT_REFERENCE",
)

ACTIVE_ARRAYS = (
    "time_s", "service_state_29", "target_state_13", "command_Q_14",
    "signed_W_act_J", "left_gap_m", "right_gap_m", "left_gap_rate_m_s",
    "right_gap_rate_m_s", "total_linear_momentum_N_s",
    "total_angular_momentum_N_m_s", "total_kinetic_energy_J",
    "energy_minus_work_residual_J", "ideal_constraint_power_W",
    "contact_force_N", "contact_torque_N_m", "stage_time_s", "stage_code",
    "stage_service_state_29", "stage_command_Q_14", "stage_power_W",
    "stage_P_coordinates_m", "stage_gap_jacobian_P",
    "stage_mass_cholesky_min_diagonal", "stage_domain_and_sign_pass",
)
POST_ARRAYS = (
    "post_time_s", "post_service_state_29", "post_target_state_13",
    "post_left_gap_m", "post_right_gap_m", "post_left_gap_rate_m_s",
    "post_right_gap_rate_m_s", "post_total_linear_momentum_N_s",
    "post_total_angular_momentum_N_m_s", "post_total_kinetic_energy_J",
    "post_contact_force_N", "post_contact_torque_N_m", "post_stage_time_s",
    "post_stage_code", "post_stage_service_state_29",
    "post_stage_target_state_13", "post_stage_P_coordinates_m",
    "post_stage_gap_jacobian_P", "post_stage_domain_and_sign_pass",
)
A0_PARENT_ARRAYS = (
    "time_s", "service_position_m", "service_quaternion_wxyz",
    "R_joint_coordinates_rad", "P_joint_coordinates_m", "base_linear_m_s",
    "base_angular_rad_s", "R_joint_rad_s", "P_joint_m_s", "left_gap_m",
    "right_gap_m", "left_gap_rate_m_s", "right_gap_rate_m_s",
)
INTEGER_ARRAYS = {"stage_code", "post_stage_code"}
BOOLEAN_ARRAYS = {"stage_domain_and_sign_pass", "post_stage_domain_and_sign_pass"}

DIRECT_ROLE_COUNTS = {
    "PRE_RUN_PROTECTED_ASSET_SNAPSHOT": 1,
    "SOURCE_MANIFEST_SELF_EXCLUDED": 1,
    "REFERENCE_FORCE_AND_ACQUISITION": 1,
    "REGISTERED_SCHEDULE": 1,
    "RUNTIME_ENVIRONMENT": 1,
    "PRE_RUN_EXECUTION_LEDGER": 1,
    "A0_PARENT_TRACE_MANIFEST": 1,
    "A0_PARENT_TRACE_NPZ": 6,
    "A2_SELECTION_LEDGER": 1,
    "REGISTERED_CASE_METADATA": 144,
    "CAMPAIGN_SUMMARY": 1,
    "NEGATIVE_CONTROL_EVIDENCE": 1,
    "PROVISIONAL_POST_CAMPAIGN_SNAPSHOT": 1,
    "POST_RUN_PROTECTED_ASSET_SNAPSHOT": 1,
    "EXECUTION_VALIDATION_FULL": 1,
    "EXECUTION_SOURCE_FREEZE_TERMINAL": 1,
    "MUTATION_BASE_BUNDLE": 65,
    "MUTATION_MUTANT_BUNDLE": 65,
    "MUTATION_PATCH_BUNDLE": 65,
}
VARIABLE_ROLES = {"EXECUTED_CASE_NPZ", "MUTATION_ARTIFACT_DEPENDENCY"}
ALLOWED_ROLES = set(DIRECT_ROLE_COUNTS) | VARIABLE_ROLES

MANIFEST_KEYS = {
    "schema", "scope", "self_excluded", "acyclic", "source_freeze_terminal",
    "execution_validation", "records", "record_count",
    "records_canonical_sha256", "excluded_future_outputs", "claim_boundary",
}
PREAUDIT_KEYS = {
    "schema", "scope", "status", "ready_for_independent_audit", "final",
    "audited", "inputs", "checks", "governance", "claim_boundary",
}
PREAUDIT_INPUT_KEYS = {
    "execution_validation", "evidence_manifest", "post_run_snapshot",
    "campaign_summary", "negative_control_evidence",
    "execution_source_freeze_terminal",
}
PREAUDIT_CHECK_KEYS = {
    "validation_full_pass", "manifest_self_excluded_and_acyclic",
    "publication_prefix_complete", "source_freeze_reverified",
    "protected_assets_reverified", "a0_pre_post_reverified",
    "registered_144_complete", "mutation_65_complete",
    "governance_holds_reverified",
}
PREAUDIT_GOVERNANCE_KEYS = {
    "required_false", "required_null_physical_inputs",
    "formal_sim13_v2_state_unchanged", "memory",
    "physical_current_formal_owner_production_release_next_stage_hold",
}

MUTATION_REPLAY_TYPE_BY_PARENT = {
    "B4FNC01": "BOUND_SOURCE_BYTES",
    "B4FNC02": "COMMAND_TRACE",
    "B4FNC03": "COMMAND_TRACE",
    "B4FNC04": "GEOMETRY_SIGN_TRACE",
    "B4FNC05": "WORK_TRACE",
    "B4FNC06": "WORK_TRACE",
    "B4FNC07": "REMOVAL_WORK_MAPPING",
    "B4FNC08": "COMMAND_TRACE",
    "B4FNC09": "CLEARANCE_TRACE",
    "B4FNC10": "CLEARANCE_TRACE",
    "B4FNC11": "REMOVAL_MAPPING",
    "B4FNC12": "ENERGY_MAPPING",
    "B4FNC13": "POST_RELEASE_TARGET_TRACE",
    "B4FNC14": "CONTACT_TRACE",
    "B4FNC15": "REFERENCE_PAIR",
    "B4FNC16": "REGISTERED_SCHEDULE",
    "B4FNC17": "A2_COMMAND_OR_TRACE_PAIR",
    "B4FNC18": "GOVERNANCE_CANDIDATE",
    "B4FNC19": "GOVERNANCE_CANDIDATE",
    "B4FNC20": "GOVERNANCE_CANDIDATE",
    "B4FNC21": "GEOMETRY_SIGN_TRACE",
    "B4FNC22": "SELECTOR_REPORT",
}

MUTATION_PAYLOAD_FIELDS = {
    "BOUND_SOURCE_BYTES": {
        "source_id", "source_record", "candidate_record",
        "candidate_bytes_path", "xor_mutation",
    },
    "COMMAND_TRACE": {
        "arm", "slot", "acquisition_time_s", "sample_time_s", "Q_ref_N",
        "command_parameters", "observed_Q_14", "clearance_dwell_active",
        "trace_origin", "harness_id", "harness_command",
    },
    "GEOMETRY_SIGN_TRACE": {
        "P_coordinates_m", "centered_step_m", "raw_gap_jacobian_P",
        "registered_signs", "consumed_signs", "clipping_used",
        "extrapolation_used", "terminal_status",
    },
    "WORK_TRACE": {
        "time_s", "Q_P_N", "eta_P_m_s", "signed_W_act_J",
        "energy_minus_work_residual_J",
    },
    "REMOVAL_WORK_MAPPING": {
        "finite_removal_event", "W_before_removal_J", "W_after_mapping_J",
    },
    "CLEARANCE_TRACE": {
        "time_s", "acquisition_time_s", "left_gap_m", "right_gap_m",
        "left_gap_rate_m_s", "right_gap_rate_m_s",
        "ledger_interval_certified", "observed_finite_event", "classifier_mode",
    },
    "REMOVAL_MAPPING": {
        "z_before", "z_after", "linear_impulse_N_s", "angular_impulse_N_m_s",
        "kinetic_energy_jump_J", "ideal_constraint_stored_energy_J",
    },
    "ENERGY_MAPPING": {
        "z_before", "z_after", "mass_20x20", "D_switch_J",
        "reported_kinetic_increment_J",
    },
    "POST_RELEASE_TARGET_TRACE": {
        "time_s", "independent_target_state_13", "candidate_target_state_13",
        "candidate_target_source", "parent_crosscheck_terminal_max_abs",
    },
    "CONTACT_TRACE": {
        "contact_kernel_enabled", "contact_force_N", "contact_torque_N_m",
    },
    "REFERENCE_PAIR": {
        "rk4", "midpoint", "event_time_tolerance_s", "work_relative_tolerance",
        "work_absolute_floor_J",
    },
    "REGISTERED_SCHEDULE": {"schedule"},
    "A2_COMMAND_OR_TRACE_PAIR": {
        "lanes", "pair_kind", "parent_level", "left_variant", "right_variant",
    },
    "GOVERNANCE_CANDIDATE": {"candidate"},
    "SELECTOR_REPORT": {"report"},
}

MUTATION_CREDIT_BOUNDARY = (
    "mutation replay evidence only; no A1/A2 outcome, physical, current-system, "
    "formal NC19, Owner, production, release or next-stage credit"
)
NEGATIVE_CONTROL_KEYS = {
    "schema", "scope", "required_parent_ids", "subvariant_counts_by_parent",
    "source_binding", "finite_event_harness_precondition", "counts",
    "parent_summaries", "receipts", "all_65_subvariants_unique_hit_and_killed",
    "final", "audited", "validator_pass_claimed",
    "dictionary_flag_only_mutation_used", "campaign_or_scientific_credit_from_mutations",
    "campaign_negative_control_hook_closed", "executor_bundle_generation_complete",
    "claim_boundary", "mutation_credit_boundary", "capabilities", "memory",
}


class B4GIndependentAuditError(RuntimeError):
    """A strict independent audit predicate failed."""


def _fail(code: str, detail: Any = None) -> None:
    suffix = "" if detail is None else f":{detail}"
    raise B4GIndependentAuditError(f"{code}{suffix}")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    _fail("NONFINITE_JSON_CONSTANT", value)


def read_json(path: Path, *, canonical: bool = False) -> dict[str, Any]:
    try:
        payload = path.read_bytes()
        value = json.loads(
            payload.decode("utf-8"), object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_constant,
        )
    except B4GIndependentAuditError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise B4GIndependentAuditError(f"JSON_READ_FAILED:{path}") from error
    if not isinstance(value, dict):
        _fail("JSON_ROOT_NOT_OBJECT", path)
    if canonical and payload != canonical_bytes(value) + b"\n":
        _fail("JSON_NOT_CANONICAL_SORTED_COMPACT_LF", path)
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_bytes(value) + b"\n"
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _absolute_lexical(path: Path | str) -> Path:
    """Return an absolute normalized path without resolving reparse points."""

    return Path(os.path.abspath(os.fspath(path)))


def _path_reports_junction(path: Path) -> bool:
    checker = getattr(path, "is_junction", None)
    if not callable(checker):
        return False
    try:
        return bool(checker())
    except OSError as error:
        raise B4GIndependentAuditError(
            f"LEXICAL_JUNCTION_QUERY_FAILED:{path}"
        ) from error


def _status_is_reparse(path: Path, status: os.stat_result) -> bool:
    attributes = int(getattr(status, "st_file_attributes", 0))
    return bool(
        stat.S_ISLNK(status.st_mode)
        or attributes & FILE_ATTRIBUTE_REPARSE_POINT
        or _path_reports_junction(path)
    )


def _assert_no_reparse_lexical_chain(
    path: Path | str, *, require_leaf_exists: bool, code: str,
) -> Path:
    """lstat every lexical component before any caller may resolve the path."""

    absolute = _absolute_lexical(path)
    if not absolute.is_absolute() or not absolute.anchor:
        _fail(f"{code}_NOT_ABSOLUTE", absolute)
    parts = absolute.parts
    current = Path(parts[0])
    components = [current]
    for part in parts[1:]:
        current = current / part
        components.append(current)
    for index, component in enumerate(components):
        if not os.path.lexists(component):
            if require_leaf_exists or index < len(components) - 1:
                _fail(f"{code}_LEXICAL_COMPONENT_MISSING", component)
            return absolute
        try:
            status = component.lstat()
        except OSError as error:
            raise B4GIndependentAuditError(
                f"{code}_LSTAT_FAILED:{component}"
            ) from error
        if _status_is_reparse(component, status):
            _fail(f"{code}_REPARSE_POINT_FORBIDDEN", component)
    return absolute


def find_project_root(phase_root: Path) -> Path:
    phase = _absolute_lexical(phase_root)
    for candidate in (phase, *phase.parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    _fail("PROJECT_ROOT_NOT_FOUND", phase)
    raise AssertionError


def _project_relative(path: Path, project_root: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        _fail("PATH_OUTSIDE_PROJECT", path)
    raise AssertionError


def _safe_record_path(raw: Any, project_root: Path) -> Path:
    if not isinstance(raw, str) or not raw or "\\" in raw:
        _fail("RECORD_PATH_NOT_PROJECT_RELATIVE_POSIX", raw)
    pure = PurePosixPath(raw)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        _fail("RECORD_PATH_UNSAFE", raw)
    root_lexical = _absolute_lexical(project_root)
    candidate_lexical = root_lexical / Path(*pure.parts)
    _assert_no_reparse_lexical_chain(
        candidate_lexical,
        require_leaf_exists=False,
        code="RECORD_PATH_LEXICAL_CHAIN",
    )
    # Resolution is permitted only after every existing lexical component has
    # been proven non-symlink, non-junction and non-reparse by lstat.
    root_resolved = root_lexical.resolve(strict=True)
    candidate = candidate_lexical.resolve(strict=False)
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        _fail("RECORD_PATH_ESCAPES_PROJECT", raw)
    return candidate


def file_record(path: Path, role: str, project_root: Path) -> dict[str, Any]:
    return {
        "path": _project_relative(path, project_root),
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def verify_record(
    record: Mapping[str, Any], project_root: Path, *, exact_keys: bool = True,
) -> Path:
    required = {"path", "role", "bytes", "sha256"}
    if (set(record) != required) if exact_keys else not required.issubset(record):
        _fail("FILE_RECORD_KEY_SET", sorted(record))
    path = _safe_record_path(record.get("path"), project_root)
    if not path.is_file():
        _fail("FILE_RECORD_MISSING", record.get("path"))
    if type(record.get("bytes")) is not int or record["bytes"] < 0:
        _fail("FILE_RECORD_BYTES_INVALID", record.get("path"))
    if path.stat().st_size != record["bytes"]:
        _fail("FILE_RECORD_SIZE_DRIFT", record.get("path"))
    digest = record.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9A-F]{64}", digest):
        _fail("FILE_RECORD_SHA_FORMAT", record.get("path"))
    if sha256_file(path) != digest:
        _fail("FILE_RECORD_SHA_DRIFT", record.get("path"))
    return path


def _resolve_embedded_record_path(record: Mapping[str, Any], project_root: Path) -> Path:
    """Resolve producer records which may omit role/media fields."""

    if not {"path", "bytes", "sha256"}.issubset(record):
        _fail("EMBEDDED_FILE_RECORD_INCOMPLETE")
    path = _safe_record_path(record["path"], project_root)
    if (
        not path.is_file()
        or path.stat().st_size != record["bytes"]
        or sha256_file(path) != record["sha256"]
    ):
        _fail("EMBEDDED_FILE_RECORD_DRIFT", record.get("path"))
    return path


def clean_final(phase_root: Path) -> None:
    """Remove the terminal chain consumer-first without following any symlink.

    Every target is attempted even after a BaseException.  A second bounded
    pass removes nodes left by a transient interrupt, after which any observed
    cleanup error or surviving node is reported fail-closed.
    """

    root = _assert_no_reparse_lexical_chain(
        phase_root,
        require_leaf_exists=True,
        code="STALE_FINAL_FORMAL_PHASE_CHAIN",
    )
    errors: list[dict[str, Any]] = []

    def remove_one(relative: Path, attempt: int) -> None:
        parent = root / relative.parent
        target = root / relative
        if target.parent != parent or target.name != relative.name:
            _fail("STALE_FINAL_TARGET_LEXICALLY_UNSAFE", relative)
        _assert_no_reparse_lexical_chain(
            parent,
            require_leaf_exists=False,
            code="STALE_FINAL_PARENT_CHAIN",
        )
        if not os.path.lexists(parent):
            return
        parent_status = parent.lstat()
        if _status_is_reparse(parent, parent_status):
            _fail("STALE_FINAL_PARENT_REPARSE_FORBIDDEN", relative.parent)
        if not stat.S_ISDIR(parent_status.st_mode):
            _fail("STALE_FINAL_PARENT_NOT_DIRECTORY", relative.parent)
        if not os.path.lexists(target):
            return
        target_status = target.lstat()
        if stat.S_ISLNK(target_status.st_mode):
            target.unlink()
            return
        if _status_is_reparse(target, target_status):
            _fail("STALE_FINAL_TARGET_NON_SYMLINK_REPARSE_FORBIDDEN", relative)
        if stat.S_ISREG(target_status.st_mode):
            target.unlink()
            return
        _fail("STALE_FINAL_NOT_PLAIN_FILE_OR_SYMLINK", relative)

    for attempt in (1, 2):
        for relative in FINAL_CONSUMER_FIRST_RELATIVES:
            target = root / relative
            if attempt == 2 and not os.path.lexists(target):
                continue
            try:
                remove_one(relative, attempt)
            except BaseException as error:
                errors.append({
                    "attempt": attempt,
                    "path": relative.as_posix(),
                    "error": f"{type(error).__name__}:{error}",
                })
    remaining = [
        relative.as_posix() for relative in FINAL_CONSUMER_FIRST_RELATIVES
        if os.path.lexists(root / relative)
    ]
    if errors or remaining:
        _fail("STALE_FINAL_CLEANUP_FAILED_CLOSED", {
            "errors": errors,
            "remaining": remaining,
        })


def _cleanup_final_then_reraise(
    phase_root: Path, original_error: BaseException,
) -> None:
    """Guarantee a best-effort terminal-chain rollback before re-raising."""

    try:
        clean_final(phase_root)
    except BaseException as cleanup_error:
        raise B4GIndependentAuditError(
            "FINAL_CHAIN_ROLLBACK_FAILED_AFTER_"
            f"{type(original_error).__name__}:{cleanup_error}"
        ) from original_error
    raise original_error.with_traceback(original_error.__traceback__)


def _assert_final_publication_parents_safe(phase_root: Path) -> None:
    """Recheck the formal phase and both publication parents before writes."""

    root = _assert_no_reparse_lexical_chain(
        phase_root,
        require_leaf_exists=True,
        code="FINAL_PUBLICATION_PHASE_CHAIN",
    )
    for relative_parent in (EVIDENCE_REL, RESULTS_REL):
        _assert_no_reparse_lexical_chain(
            root / relative_parent,
            require_leaf_exists=True,
            code="FINAL_PUBLICATION_PARENT_CHAIN",
        )


def _assert_exact_keys(value: Mapping[str, Any], expected: set[str], code: str) -> None:
    if set(value) != expected:
        _fail(code, {"missing": sorted(expected - set(value)), "extra": sorted(set(value) - expected)})


def _assert_import_independence(source_path: Path) -> None:
    allowed = {
        "__future__", "argparse", "ast", "collections", "copy", "hashlib",
        "json", "math", "os", "pathlib", "re", "stat", "sys", "tempfile", "typing",
        "numpy",
    }
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                _fail("AUDIT_RELATIVE_IMPORT_FORBIDDEN", node.module)
            imported.add((node.module or "").split(".")[0])
    if imported - allowed:
        _fail("AUDIT_FORBIDDEN_IMPORT", sorted(imported - allowed))


def _array_payload_sha256(arrays: Mapping[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for name in sorted(arrays):
        array = np.ascontiguousarray(arrays[name])
        header = canonical_bytes({
            "name": name, "dtype": array.dtype.str, "shape": list(array.shape),
        })
        digest.update(len(header).to_bytes(8, "big"))
        digest.update(header)
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest().upper()


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    try:
        with np.load(path, allow_pickle=False) as archive:
            arrays = {name: np.asarray(archive[name]) for name in archive.files}
    except (OSError, ValueError) as error:
        raise B4GIndependentAuditError(f"NPZ_ALLOW_PICKLE_FALSE_READ_FAILED:{path}") from error
    for name, value in arrays.items():
        if value.dtype.kind in "OUSVc":
            _fail("NPZ_FORBIDDEN_DTYPE", f"{path}:{name}:{value.dtype}")
        expected = (
            np.dtype(np.bool_).str if name in BOOLEAN_ARRAYS
            else np.dtype("<i8").str if name in INTEGER_ARRAYS
            else np.dtype("<f8").str
        )
        if value.dtype.str != expected:
            _fail("NPZ_DTYPE", f"{path}:{name}:{value.dtype.str}:{expected}")
        if value.dtype.kind == "f" and not np.all(np.isfinite(value)):
            _fail("NPZ_NONFINITE", f"{path}:{name}")
    return arrays


def _shape(value: np.ndarray, expected: tuple[int, ...], code: str) -> None:
    if value.shape != expected:
        _fail(code, {"actual": value.shape, "expected": expected})


def _max_abs(value: np.ndarray) -> float:
    return 0.0 if value.size == 0 else float(np.max(np.abs(value)))


def _quaternion_rows_pass(values: np.ndarray, tolerance: float = 1.0e-10) -> bool:
    return bool(values.ndim == 2 and values.shape[1] == 4 and np.all(
        np.abs(np.linalg.norm(values, axis=1) - 1.0) <= tolerance
    ))


def _a0_quaternion_geodesic_rows(
    raw_wxyz: np.ndarray,
    parent_wxyz: np.ndarray,
) -> np.ndarray:
    """Return stable A0-only SO(3) geodesics for paired quaternion rows.

    A0 replay has a stricter contract than the general raw-trace quaternion
    shape/unit check above.  Reject non-unit inputs before normalization, align
    the double-cover sign, and use the chord/atan2 form rather than acos(dot),
    which is unstable near identical rotations and can receive a one-ULP dot
    outside its mathematical domain.
    """

    try:
        raw = np.asarray(raw_wxyz, dtype=np.float64)
        parent = np.asarray(parent_wxyz, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as error:
        raise B4GIndependentAuditError(
            "A0_QUATERNION_GEODESIC_NOT_REAL_NUMERIC"
        ) from error
    if (
        raw.ndim != 2
        or parent.ndim != 2
        or raw.shape[1:] != (4,)
        or parent.shape != raw.shape
        or raw.shape[0] == 0
    ):
        _fail("A0_QUATERNION_GEODESIC_SHAPE_MISMATCH", {
            "raw": raw.shape, "parent": parent.shape,
        })
    if not np.all(np.isfinite(raw)) or not np.all(np.isfinite(parent)):
        _fail("A0_QUATERNION_GEODESIC_NONFINITE")

    raw_norm = np.linalg.norm(raw, axis=1)
    parent_norm = np.linalg.norm(parent, axis=1)
    if (
        not np.all(np.isfinite(raw_norm))
        or not np.all(np.isfinite(parent_norm))
        or np.any(np.abs(raw_norm - 1.0) > 1.0e-12)
        or np.any(np.abs(parent_norm - 1.0) > 1.0e-12)
    ):
        _fail("A0_QUATERNION_GEODESIC_NONUNIT")

    raw_unit = raw / raw_norm[:, None]
    parent_unit = parent / parent_norm[:, None]
    dot = np.sum(raw_unit * parent_unit, axis=1)
    parent_aligned = np.where(dot[:, None] < 0.0, -parent_unit, parent_unit)
    geodesic_rad = 4.0 * np.arctan2(
        np.linalg.norm(raw_unit - parent_aligned, axis=1),
        np.linalg.norm(raw_unit + parent_aligned, axis=1),
    )
    if not np.all(np.isfinite(geodesic_rad)):
        _fail("A0_QUATERNION_GEODESIC_NONFINITE_RESULT")
    return geodesic_rad


def _verify_a0_quaternion_replay(
    raw_wxyz: np.ndarray,
    parent_wxyz: np.ndarray,
    lane: str,
) -> float:
    geodesic_rad = _a0_quaternion_geodesic_rows(raw_wxyz, parent_wxyz)
    maximum_rad = float(np.max(geodesic_rad))
    if maximum_rad > 1.0e-12:
        _fail(
            "A0_RAW_PARENT_REPLAY",
            f"{lane}:service_quaternion_wxyz:{maximum_rad:.17g}",
        )
    return maximum_rad


def _sin2_profile(time_s: float, start_s: float, duration_s: float) -> float:
    elapsed = float(time_s) - float(start_s)
    if duration_s == 0.0 or elapsed <= 0.0 or elapsed >= duration_s:
        return 0.0
    value = math.sin(math.pi * elapsed / duration_s)
    return value * value


def _expected_command(metadata: Mapping[str, Any], times: np.ndarray) -> np.ndarray:
    parameters = metadata["command_parameters"]
    q_ref = float(parameters["Q_ref_per_finger_N"])
    acquisition = float(metadata["event_provenance"]["acquisition_time_s"])
    result = np.zeros((len(times), 14), dtype="<f8")
    for column, side in ((12, "left"), (13, "right")):
        arm = parameters[side]
        alpha = float(arm["alpha"])
        delay = float(arm["delay_s"])
        duration = float(arm["duration_s"])
        for index, time_s in enumerate(times):
            result[index, column] = alpha * q_ref * _sin2_profile(
                float(time_s), acquisition + delay, duration,
            )
    return result


def _validate_npz_arrays(metadata: Mapping[str, Any], arrays: Mapping[str, np.ndarray]) -> None:
    names = set(arrays)
    finite_event = bool(metadata["responses"].get("finite_removal_event"))
    expected = set(ACTIVE_ARRAYS) | (set(POST_ARRAYS) if finite_event else set())
    if names != expected:
        _fail("CASE_NPZ_ARRAY_SET", metadata["case_id"])
    n = arrays["time_s"].shape[0]
    s = arrays["stage_time_s"].shape[0]
    if n < 1 or s < 1:
        _fail("CASE_NPZ_EMPTY_ACTIVE_TRACE", metadata["case_id"])
    active_shapes = {
        "time_s": (n,), "service_state_29": (n, 29), "target_state_13": (n, 13),
        "command_Q_14": (n, 14), "signed_W_act_J": (n,), "left_gap_m": (n,),
        "right_gap_m": (n,), "left_gap_rate_m_s": (n,), "right_gap_rate_m_s": (n,),
        "total_linear_momentum_N_s": (n, 3), "total_angular_momentum_N_m_s": (n, 3),
        "total_kinetic_energy_J": (n,), "energy_minus_work_residual_J": (n,),
        "ideal_constraint_power_W": (n,), "contact_force_N": (n,),
        "contact_torque_N_m": (n,), "stage_time_s": (s,), "stage_code": (s,),
        "stage_service_state_29": (s, 29), "stage_command_Q_14": (s, 14),
        "stage_power_W": (s,), "stage_P_coordinates_m": (s, 2),
        "stage_gap_jacobian_P": (s, 2, 2),
        "stage_mass_cholesky_min_diagonal": (s,),
        "stage_domain_and_sign_pass": (s,),
    }
    for name, shape in active_shapes.items():
        _shape(arrays[name], shape, f"CASE_SHAPE_{name}")
    if n > 1 and not np.all(np.diff(arrays["time_s"]) > 0.0):
        _fail("CASE_TIME_NOT_STRICT", metadata["case_id"])
    if not _quaternion_rows_pass(arrays["service_state_29"][:, 3:7]):
        _fail("CASE_SERVICE_QUATERNION_NOT_UNIT", metadata["case_id"])
    if not _quaternion_rows_pass(arrays["target_state_13"][:, 3:7]):
        _fail("CASE_TARGET_QUATERNION_NOT_UNIT", metadata["case_id"])
    if not np.all((arrays["service_state_29"][:, 13:15] >= 0.0) & (arrays["service_state_29"][:, 13:15] <= 0.0715)):
        _fail("CASE_P_DOMAIN_ACTIVE", metadata["case_id"])
    if not np.all((arrays["stage_P_coordinates_m"] >= 0.0) & (arrays["stage_P_coordinates_m"] <= 0.0715)):
        _fail("CASE_P_DOMAIN_STAGE", metadata["case_id"])
    if not np.all(arrays["stage_domain_and_sign_pass"]):
        _fail("CASE_STAGE_DOMAIN_SIGN_FALSE", metadata["case_id"])
    if np.any(arrays["command_Q_14"][:, :12] != 0.0) or np.any(arrays["stage_command_Q_14"][:, :12] != 0.0):
        _fail("CASE_NON_P_GENERALIZED_FORCE", metadata["case_id"])
    expected_command = _expected_command(metadata, arrays["time_s"])
    if not np.array_equal(arrays["command_Q_14"], expected_command):
        _fail("CASE_COMMAND_PROFILE_MISMATCH", metadata["case_id"])
    expected_stage_command = _expected_command(metadata, arrays["stage_time_s"])
    if not np.array_equal(arrays["stage_command_Q_14"], expected_stage_command):
        _fail("CASE_STAGE_COMMAND_PROFILE_MISMATCH", metadata["case_id"])
    stage_power = np.sum(
        arrays["stage_command_Q_14"][:, 12:14]
        * arrays["stage_service_state_29"][:, 27:29], axis=1,
    )
    if _max_abs(stage_power - arrays["stage_power_W"]) > 1.0e-12:
        _fail("CASE_STAGE_POWER_NOT_Q_DOT_PDOT", metadata["case_id"])
    if _max_abs(arrays["energy_minus_work_residual_J"]) > 1.0e-7:
        _fail("CASE_ENERGY_WORK_RESIDUAL", metadata["case_id"])
    if _max_abs(arrays["total_linear_momentum_N_s"] - arrays["total_linear_momentum_N_s"][0]) > 1.0e-9:
        _fail("CASE_LINEAR_MOMENTUM_DRIFT", metadata["case_id"])
    if _max_abs(arrays["total_angular_momentum_N_m_s"] - arrays["total_angular_momentum_N_m_s"][0]) > 1.0e-9:
        _fail("CASE_ANGULAR_MOMENTUM_DRIFT", metadata["case_id"])
    if _max_abs(arrays["contact_force_N"]) > 1.0e-12 or _max_abs(arrays["contact_torque_N_m"]) > 1.0e-12:
        _fail("CASE_ACTIVE_CONTACT_NOT_ZERO", metadata["case_id"])
    if float(arrays["signed_W_act_J"][-1]) != float(metadata["responses"]["signed_work_terminal_J"]):
        _fail("CASE_TERMINAL_WORK_METADATA_MISMATCH", metadata["case_id"])
    if metadata["arm"] == "A0":
        if np.any(arrays["command_Q_14"] != 0.0) or np.any(arrays["stage_command_Q_14"] != 0.0):
            _fail("A0_COMMAND_NOT_EXACT_ZERO", metadata["case_id"])
        if np.any(arrays["signed_W_act_J"] != 0.0):
            _fail("A0_WORK_NOT_EXACT_ZERO", metadata["case_id"])
    if finite_event:
        m = arrays["post_time_s"].shape[0]
        u = arrays["post_stage_time_s"].shape[0]
        post_shapes = {
            "post_time_s": (m,), "post_service_state_29": (m, 29),
            "post_target_state_13": (m, 13), "post_left_gap_m": (m,),
            "post_right_gap_m": (m,), "post_left_gap_rate_m_s": (m,),
            "post_right_gap_rate_m_s": (m,), "post_total_linear_momentum_N_s": (m, 3),
            "post_total_angular_momentum_N_m_s": (m, 3),
            "post_total_kinetic_energy_J": (m,), "post_contact_force_N": (m,),
            "post_contact_torque_N_m": (m,), "post_stage_time_s": (u,),
            "post_stage_code": (u,), "post_stage_service_state_29": (u, 29),
            "post_stage_target_state_13": (u, 13), "post_stage_P_coordinates_m": (u, 2),
            "post_stage_gap_jacobian_P": (u, 2, 2),
            "post_stage_domain_and_sign_pass": (u,),
        }
        if m < 2 or u < 1:
            _fail("POST_RELEASE_TRACE_TOO_SHORT", metadata["case_id"])
        for name, shape in post_shapes.items():
            _shape(arrays[name], shape, f"CASE_SHAPE_{name}")
        if abs(float(arrays["post_time_s"][-1] - arrays["post_time_s"][0]) - 0.005) > 1.0e-12:
            _fail("POST_RELEASE_DURATION_NOT_5MS", metadata["case_id"])
        if not np.array_equal(arrays["service_state_29"][-1, 15:29], arrays["post_service_state_29"][0, 15:29]):
            _fail("G10_SERVICE_VELOCITY_JUMP", metadata["case_id"])
        if not np.array_equal(arrays["target_state_13"][-1, 7:13], arrays["post_target_state_13"][0, 7:13]):
            _fail("G10_TARGET_VELOCITY_JUMP", metadata["case_id"])
        linear_impulse = arrays["post_total_linear_momentum_N_s"][0] - arrays["total_linear_momentum_N_s"][-1]
        angular_impulse = arrays["post_total_angular_momentum_N_m_s"][0] - arrays["total_angular_momentum_N_m_s"][-1]
        energy_jump = float(arrays["post_total_kinetic_energy_J"][0] - arrays["total_kinetic_energy_J"][-1])
        if np.linalg.norm(linear_impulse) > 1.0e-12 or np.linalg.norm(angular_impulse) > 1.0e-12 or abs(energy_jump) > 1.0e-12:
            _fail("G10_ZERO_IMPULSE_OR_ENERGY_JUMP", metadata["case_id"])
        g10 = next((row for row in metadata["gate_records"] if row.get("gate_id") == "B4F-G10-EXACT-ZERO-JUMP-REMOVAL"), None)
        if not isinstance(g10, dict) or g10.get("evaluation_status") != "PASS" or g10.get("scientific_predicate") is not True:
            _fail("G10_GATE_NOT_PASS", metadata["case_id"])
        detail = g10.get("detail", {})
        if (
            np.linalg.norm(np.asarray(detail.get("linear_impulse_N_s"), dtype=float)) > 1.0e-12
            or np.linalg.norm(np.asarray(detail.get("angular_impulse_N_m_s"), dtype=float)) > 1.0e-12
            or abs(float(detail.get("kinetic_energy_jump_J"))) > 1.0e-12
            or float(detail.get("ideal_constraint_stored_energy_J")) != 0.0
        ):
            _fail("G10_REPORTED_MAPPING_METRICS", metadata["case_id"])
        if _max_abs(arrays["post_contact_force_N"]) > 1.0e-12 or _max_abs(arrays["post_contact_torque_N_m"]) > 1.0e-12:
            _fail("POST_RELEASE_CONTACT_NOT_ZERO", metadata["case_id"])
        if _max_abs(arrays["post_total_linear_momentum_N_s"] - arrays["post_total_linear_momentum_N_s"][0]) > 1.0e-9:
            _fail("POST_LINEAR_MOMENTUM_DRIFT", metadata["case_id"])
        if _max_abs(arrays["post_total_angular_momentum_N_m_s"] - arrays["post_total_angular_momentum_N_m_s"][0]) > 1.0e-9:
            _fail("POST_ANGULAR_MOMENTUM_DRIFT", metadata["case_id"])
        if _max_abs(arrays["post_total_kinetic_energy_J"] - arrays["post_total_kinetic_energy_J"][0]) > 1.0e-7:
            _fail("POST_ENERGY_DRIFT", metadata["case_id"])
    else:
        g10 = next((row for row in metadata["gate_records"] if row.get("gate_id") == "B4F-G10-EXACT-ZERO-JUMP-REMOVAL"), None)
        if not isinstance(g10, dict) or g10.get("evaluation_status") != "NOT_APPLICABLE" or g10.get("scientific_predicate") is not None:
            _fail("G10_NO_EVENT_NOT_EXACT_NA", metadata["case_id"])


def _verify_validation(payload: Mapping[str, Any]) -> None:
    expected_keys = {
        "schema", "mode", "status", "passed", "final", "audited",
        "validator_pass_claimed", "campaign_or_scientific_credit", "check_count",
        "failure_count", "failures", "observations", "writes_performed",
        "solver_runner_mutation_modules_imported",
    }
    _assert_exact_keys(payload, expected_keys, "VALIDATION_KEY_SET")
    if not (
        payload["schema"] == "SIM13_V4B4G_READ_ONLY_VALIDATION_REPORT_V1"
        and payload["mode"] == "full" and payload["status"] == "PASS"
        and payload["passed"] is True and payload["final"] is False
        and payload["audited"] is False and payload["validator_pass_claimed"] is False
        and payload["campaign_or_scientific_credit"] is False
        and type(payload["check_count"]) is int and payload["check_count"] > 0
        and payload["failure_count"] == 0 and payload["failures"] == []
        and isinstance(payload["observations"], dict)
        and payload["writes_performed"] is False
        and payload["solver_runner_mutation_modules_imported"] is False
    ):
        _fail("VALIDATION_NOT_FULL_READ_ONLY_PASS")


def _verify_source_freeze(terminal_path: Path, project_root: Path, phase_root: Path) -> dict[str, Any]:
    expected_terminal_path = (
        phase_root / "results"
        / "SIM13_V4B4G_EXECUTION_SOURCE_FREEZE_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"
    ).resolve()
    if terminal_path.resolve() != expected_terminal_path:
        _fail("EXECUTION_SOURCE_FREEZE_TERMINAL_NONCANONICAL_PATH", terminal_path)
    terminal = read_json(terminal_path, canonical=True)
    if not (
        terminal.get("schema") == "SIM13_V4B4G_EXECUTION_SOURCE_FREEZE_TERMINAL_SELF_EXCLUDED_MANIFEST_V1"
        and terminal.get("self_excluded") is True and terminal.get("acyclic") is True
        and isinstance(terminal.get("records"), list) and len(terminal["records"]) == 1
    ):
        _fail("EXECUTION_SOURCE_FREEZE_TERMINAL_INVALID")
    gate_record = terminal["records"][0]
    gate_path = _resolve_embedded_record_path(gate_record, project_root)
    if gate_path != (
        phase_root / "results" / "SIM13_V4B4G_EXECUTION_SOURCE_FREEZE_GATE_V1.json"
    ).resolve():
        _fail("EXECUTION_SOURCE_FREEZE_GATE_NONCANONICAL_PATH", gate_path)
    gate = read_json(gate_path, canonical=True)
    if gate.get("schema") != "SIM13_V4B4G_EXECUTION_SOURCE_FREEZE_GATE_V1" or gate.get("final") is not True:
        _fail("EXECUTION_SOURCE_FREEZE_GATE_INVALID")
    manifest_record = gate.get("execution_source_manifest")
    if not isinstance(manifest_record, dict):
        _fail("EXECUTION_SOURCE_FREEZE_MANIFEST_RECORD_MISSING")
    source_manifest_path = _resolve_embedded_record_path(manifest_record, project_root)
    if source_manifest_path != (
        phase_root / "evidence" / "SIM13_V4B4G_EXECUTION_SOURCE_MANIFEST_V1.json"
    ).resolve():
        _fail("EXECUTION_SOURCE_FREEZE_MANIFEST_NONCANONICAL_PATH", source_manifest_path)
    source_manifest = read_json(source_manifest_path, canonical=True)
    sources = source_manifest.get("sources")
    if not (
        source_manifest.get("schema") == "SIM13_V4B4G_EXECUTION_SOURCE_MANIFEST_V1"
        and source_manifest.get("self_excluded") is True
        and isinstance(sources, list) and source_manifest.get("source_count") == len(sources)
        and source_manifest.get("source_inventory_sha256") == canonical_sha256(sources)
        and gate.get("source_count") == len(sources)
        and gate.get("source_inventory_sha256") == source_manifest["source_inventory_sha256"]
        and terminal.get("source_count") == len(sources)
        and terminal.get("source_inventory_sha256") == source_manifest["source_inventory_sha256"]
    ):
        _fail("EXECUTION_SOURCE_FREEZE_CHAIN_MISMATCH")
    paths: list[str] = []
    for record in sources:
        path = _resolve_embedded_record_path(record, project_root)
        paths.append(_project_relative(path, project_root))
    if len(paths) != len(set(item.casefold() for item in paths)):
        _fail("EXECUTION_SOURCE_FREEZE_DUPLICATE_PATH")
    current = _current_source_inventory(project_root, phase_root)
    if sources != current:
        _fail("EXECUTION_SOURCE_FREEZE_NOT_EXACT_CURRENT_ALLOWLIST")
    required_entrypoints = {
        "run_phase_b4g_solver.py", "run_phase_b4g_mutation_audit.py",
        "validate_phase_b4g_evidence.py", "publish_phase_b4g_preaudit.py",
        "independent_audit_phase_b4g.py",
    }
    if not required_entrypoints.issubset({Path(path).name for path in paths}):
        _fail("EXECUTION_SOURCE_FREEZE_FORMAL_ENTRYPOINT_OMISSION")
    test_prefix = _project_relative(phase_root / "tests_execution_audit", project_root).rstrip("/") + "/"
    if not any(path.startswith(test_prefix) and path.endswith(".py") for path in paths):
        _fail("EXECUTION_SOURCE_FREEZE_OMITS_AUDIT_TESTS")
    return {
        "terminal_sha256": sha256_file(terminal_path),
        "source_count": len(sources),
        "source_inventory_sha256": source_manifest["source_inventory_sha256"],
    }


def _current_source_inventory(project_root: Path, phase_root: Path) -> list[dict[str, Any]]:
    excluded = {"evidence", "results", "__pycache__", ".pytest_cache", ".smoke", "raw_cases"}

    def excluded_part(name: str) -> bool:
        return name in excluded or name.startswith(".pytest") or name.startswith(".smoke")

    candidates: list[Path] = []
    for current, directory_names, file_names in os.walk(phase_root):
        directory_names[:] = sorted(name for name in directory_names if not excluded_part(name))
        current_path = Path(current)
        candidates.extend(current_path / name for name in sorted(file_names))
    records: list[dict[str, Any]] = []
    interchange_names = {
        "PHASE_B4G_A0_PARENT_TRACE_INTERCHANGE_V1.json",
        "PHASE_B4G_MUTATION_ARTIFACT_INTERCHANGE_V1.json",
        "PHASE_B4G_VALIDATOR_RAW_INTERFACE_V1.json",
    }
    for path in sorted(candidates, key=lambda value: value.relative_to(phase_root).as_posix()):
        relative = path.relative_to(phase_root)
        if not path.is_file() or any(excluded_part(part) for part in relative.parts):
            continue
        permitted = (
            path.suffix.lower() == ".py"
            or (len(relative.parts) >= 2 and relative.parts[0] == "contracts" and path.suffix.lower() == ".json")
            or (len(relative.parts) == 2 and relative.parts[0] == "b4g_validation" and relative.name in interchange_names)
            or relative.as_posix() == "pytest.ini"
        )
        if not permitted:
            continue
        displayed = _project_relative(path, project_root)
        records.append({
            "id": f"local::{relative.as_posix()}",
            "role": "B4G_FROZEN_CONTRACT_SOURCE_TEST_OR_WORKFLOW",
            "path": displayed,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })
    return records


def _expected_future_outputs(phase_root: Path, project_root: Path) -> list[str]:
    return [
        _project_relative(phase_root / relative, project_root)
        for relative in (
            MANIFEST_REL, PREAUDIT_REL, RECEIPT_REL, AUDITED_GATE_REL, TERMINAL_REL,
        )
    ]


def _verify_manifest(
    manifest_path: Path, project_root: Path, phase_root: Path,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, Path]]:
    manifest = read_json(manifest_path, canonical=True)
    _assert_exact_keys(manifest, MANIFEST_KEYS, "EVIDENCE_MANIFEST_KEY_SET")
    records = manifest.get("records")
    if not (
        manifest["schema"] == "SIM13_V4B4G_EVIDENCE_MANIFEST_SELF_EXCLUDED_V1"
        and manifest["scope"] == SCOPE
        and manifest["self_excluded"] is True and manifest["acyclic"] is True
        and isinstance(records, list) and manifest["record_count"] == len(records)
        and manifest["records_canonical_sha256"] == canonical_sha256(records)
        and manifest["excluded_future_outputs"] == _expected_future_outputs(phase_root, project_root)
        and manifest["claim_boundary"] == CLAIM_BOUNDARY
    ):
        _fail("EVIDENCE_MANIFEST_HEADER_INVALID")
    if any(not isinstance(row, dict) for row in records):
        _fail("EVIDENCE_MANIFEST_RECORD_NOT_OBJECT")
    if records != sorted(
        records, key=lambda row: (str(row.get("path", "")).casefold(), str(row.get("path", ""))),
    ):
        _fail("EVIDENCE_MANIFEST_RECORDS_NOT_CANONICALLY_SORTED")
    by_role: dict[str, list[dict[str, Any]]] = {}
    paths: dict[str, Path] = {}
    seen_casefold: set[str] = set()
    manifest_relative = _project_relative(manifest_path, project_root)
    for record in records:
        path = verify_record(record, project_root)
        role = record["role"]
        if role not in ALLOWED_ROLES:
            _fail("EVIDENCE_MANIFEST_UNREGISTERED_ROLE", role)
        relative = record["path"]
        if relative.casefold() in seen_casefold:
            _fail("EVIDENCE_MANIFEST_DUPLICATE_CASEFOLD_PATH", relative)
        seen_casefold.add(relative.casefold())
        if relative == manifest_relative or relative in manifest["excluded_future_outputs"]:
            _fail("EVIDENCE_MANIFEST_SELF_OR_FUTURE_REFERENCE", relative)
        if any(part.startswith(".pytest") or part.startswith(".smoke") or ".tmp" in part for part in PurePosixPath(relative).parts):
            _fail("EVIDENCE_MANIFEST_TEMP_PATH", relative)
        by_role.setdefault(role, []).append(record)
        paths[relative] = path
    counts = Counter(record["role"] for record in records)
    for role, expected in DIRECT_ROLE_COUNTS.items():
        if counts[role] != expected:
            _fail("EVIDENCE_MANIFEST_ROLE_COUNT", f"{role}:{counts[role]}:{expected}")
    if counts["EXECUTED_CASE_NPZ"] < 120 or counts["EXECUTED_CASE_NPZ"] > 144:
        _fail("EVIDENCE_MANIFEST_EXECUTED_NPZ_COUNT", counts["EXECUTED_CASE_NPZ"])
    if counts["MUTATION_ARTIFACT_DEPENDENCY"] < 1:
        _fail("EVIDENCE_MANIFEST_MUTATION_DEPENDENCIES_EMPTY")
    if manifest["source_freeze_terminal"] != by_role["EXECUTION_SOURCE_FREEZE_TERMINAL"][0]:
        _fail("EVIDENCE_MANIFEST_SOURCE_FREEZE_TOP_RECORD_MISMATCH")
    if manifest["execution_validation"] != by_role["EXECUTION_VALIDATION_FULL"][0]:
        _fail("EVIDENCE_MANIFEST_VALIDATION_TOP_RECORD_MISMATCH")
    return manifest, by_role, paths


def _record_for_path(
    records_by_role: Mapping[str, list[dict[str, Any]]], role: str,
    path: Path, project_root: Path,
) -> dict[str, Any]:
    relative = _project_relative(path, project_root)
    matches = [row for row in records_by_role.get(role, []) if row["path"] == relative]
    if len(matches) != 1:
        _fail("MANIFEST_EXPECTED_PATH_ROLE_NOT_UNIQUE", f"{role}:{relative}")
    return matches[0]


def _gate_map(metadata: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    records = metadata.get("gate_records")
    if not isinstance(records, list):
        _fail("CASE_GATE_RECORDS_NOT_LIST", metadata.get("case_id"))
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or set(record) != {
            "gate_id", "evaluation_status", "scientific_predicate",
            "applicability_reason", "detail",
        }:
            _fail("CASE_GATE_RECORD_SCHEMA", metadata.get("case_id"))
        gate_id = record["gate_id"]
        if gate_id in result:
            _fail("CASE_DUPLICATE_GATE_ID", f"{metadata.get('case_id')}:{gate_id}")
        if record["evaluation_status"] not in {"PASS", "FAIL", "NOT_APPLICABLE"}:
            _fail("CASE_GATE_STATUS", gate_id)
        if record["evaluation_status"] == "NOT_APPLICABLE" and record["scientific_predicate"] is not None:
            _fail("CASE_GATE_NA_PREDICATE_NOT_NULL", gate_id)
        result[gate_id] = record
    return result


def _validate_case_metadata_header(metadata: Mapping[str, Any], slot: Mapping[str, Any]) -> None:
    required = {
        "schema", "slot_index", "case_id", "lane_id", "arm", "execution_status",
        "terminal_status", "source_hashes", "acquisition", "event_provenance",
        "command_parameters", "geometry_domain", "opening_sign", "responses",
        "gate_records", "npz_path", "npz_bytes", "npz_sha256", "claim_boundary",
    }
    if not required.issubset(metadata):
        _fail("CASE_METADATA_REQUIRED_FIELD_MISSING", metadata.get("case_id"))
    if not (
        metadata["schema"] == "SIM13_V4B4G_CASE_METADATA_V1"
        and metadata["slot_index"] == slot["slot_index"]
        and metadata.get("registered_slot") == dict(slot)
        and metadata["case_id"] == slot["case_id"]
        and metadata["lane_id"] == slot["lane_id"]
        and metadata["arm"] == slot["arm"]
        and metadata["claim_boundary"] == CLAIM_BOUNDARY
    ):
        _fail("CASE_METADATA_SCHEDULE_BINDING", slot["case_id"])
    provenance = metadata["event_provenance"]
    if not isinstance(provenance, dict) or not {
        "lane_id", "fresh_b3_reconstruction", "first_qualifying_event_index",
        "acquisition_time_s", "acquisition_certificate_sha256",
        "clearance_certificate_sha256", "removal_time_s",
    }.issubset(provenance):
        _fail("CASE_EVENT_PROVENANCE_FIELDS", slot["case_id"])
    if provenance["lane_id"] != slot["lane_id"]:
        _fail("CASE_EVENT_PROVENANCE_LANE", slot["case_id"])
    gates = _gate_map(metadata)
    required_gate_ids = {
        "B4F-G03-P-ONLY-INTERNAL-GENERALIZED-FORCE",
        "B4F-G04-ACTUATOR-WORK-LEDGER", "B4F-G05-P-H-CONSERVATION",
        "B4F-G06-ENERGY-MINUS-WORK-IDENTITY",
        "B4F-G07-CONTACT-CONSTRAINT-MUTUAL-EXCLUSION",
        "B4F-G08-COMMAND-ZERO-BEFORE-REMOVAL",
        "B4F-G09-CONTINUOUS-BILATERAL-CLEARANCE",
        "B4F-G10-EXACT-ZERO-JUMP-REMOVAL",
        "B4F-G11-INDEPENDENT-POST-RELEASE-5MS",
        "B4F-G16-SYNTHETIC-GEOMETRY-DOMAIN",
    }
    if slot["arm"] == "A0":
        required_gate_ids.add("B4F-G02-A0-EXACT-REPLAY")
    if set(gates) != required_gate_ids:
        _fail("CASE_GATE_ID_SET", slot["case_id"])
    if any(row["evaluation_status"] == "FAIL" for row in gates.values()):
        _fail("CASE_INTEGRITY_GATE_FAIL", slot["case_id"])


def _load_cases(
    phase_root: Path, project_root: Path, schedule: Mapping[str, Any],
    by_role: Mapping[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[int, dict[str, np.ndarray]]]:
    slots = schedule.get("slots")
    if not (
        schedule.get("schema") == "SIM13_V4B4G_REGISTERED_SCHEDULE_V1"
        and schedule.get("slot_count") == 144 and isinstance(slots, list)
        and len(slots) == 144
        and [slot.get("slot_index") for slot in slots] == list(range(144))
    ):
        _fail("FROZEN_SCHEDULE_INVALID")
    if schedule.get("slots_sha256") != canonical_sha256(slots):
        _fail("FROZEN_SCHEDULE_SLOTS_SHA256")
    metadata_records = {row["path"]: row for row in by_role["REGISTERED_CASE_METADATA"]}
    npz_records = {row["path"]: row for row in by_role["EXECUTED_CASE_NPZ"]}
    metadata_rows: list[dict[str, Any]] = []
    arrays_by_slot: dict[int, dict[str, np.ndarray]] = {}
    expected_raw_names: set[str] = set()
    expected_npz_relatives: set[str] = set()
    raw_root = (phase_root / "evidence" / "raw_cases").resolve()
    for slot in slots:
        stem = str(slot["case_id"])
        if not re.fullmatch(r"[A-Za-z0-9_]+", stem):
            _fail("SCHEDULE_CASE_ID_UNSAFE", stem)
        metadata_path = raw_root / f"{slot['slot_index']:03d}__{stem}.json"
        metadata_relative = _project_relative(metadata_path, project_root)
        expected_raw_names.add(metadata_path.name)
        if metadata_relative not in metadata_records:
            _fail("RAW_CASE_METADATA_NOT_MANIFESTED", slot["case_id"])
        metadata = read_json(metadata_path, canonical=True)
        _validate_case_metadata_header(metadata, slot)
        status = metadata["execution_status"]
        if status == "NOT_EVALUATED_NO_A1_SUCCESS":
            if slot["arm"] != "A2" or any(metadata.get(key) is not None for key in ("npz_path", "npz_bytes", "npz_sha256")):
                _fail("A2_NA_RECORD_INVALID", slot["case_id"])
            if metadata.get("npz_arrays") != [] or metadata["event_provenance"].get("acquisition_certificate_sha256") is not None:
                _fail("A2_NA_NUMERIC_OR_CERTIFICATE_PRESENT", slot["case_id"])
        elif status == "EXECUTED_FRESH_REGISTERED_SLOT":
            if metadata["event_provenance"].get("fresh_b3_reconstruction") is not True:
                _fail("EXECUTED_CASE_NOT_FRESH_B3", slot["case_id"])
            npz_raw = metadata.get("npz_path")
            npz_path = _safe_record_path(npz_raw, project_root)
            expected_path = metadata_path.with_suffix(".npz").resolve()
            if npz_path != expected_path:
                _fail("CASE_NPZ_NONCANONICAL_PATH", slot["case_id"])
            npz_relative = _project_relative(npz_path, project_root)
            expected_raw_names.add(npz_path.name)
            expected_npz_relatives.add(npz_relative)
            if npz_relative not in npz_records:
                _fail("CASE_NPZ_NOT_MANIFESTED", slot["case_id"])
            if metadata["npz_bytes"] != npz_path.stat().st_size or metadata["npz_sha256"] != sha256_file(npz_path):
                _fail("CASE_NPZ_METADATA_HASH_DRIFT", slot["case_id"])
            arrays = _load_npz(npz_path)
            if metadata.get("npz_arrays") != sorted(arrays):
                _fail("CASE_NPZ_ARRAY_INVENTORY_METADATA", slot["case_id"])
            if metadata.get("numeric_payload_sha256") != _array_payload_sha256(arrays):
                _fail("CASE_NUMERIC_PAYLOAD_SHA", slot["case_id"])
            _validate_npz_arrays(metadata, arrays)
            arrays_by_slot[int(slot["slot_index"])] = arrays
        else:
            _fail("CASE_EXECUTION_STATUS", f"{slot['case_id']}:{status}")
        metadata_rows.append(metadata)
    if set(npz_records) != expected_npz_relatives:
        _fail("MANIFEST_EXECUTED_NPZ_SET_NOT_EXACT")
    _assert_exact_raw_entries(raw_root, expected_raw_names)
    return metadata_rows, arrays_by_slot


def _assert_exact_raw_entries(raw_root: Path, expected_names: set[str]) -> None:
    actual_entries = list(raw_root.iterdir())
    if any(not item.is_file() or item.is_symlink() for item in actual_entries):
        _fail("RAW_CASE_DIRECTORY_NONPLAIN_ENTRY")
    actual_names = {item.name for item in actual_entries}
    if actual_names != expected_names:
        _fail("RAW_CASE_DIRECTORY_INVENTORY", {
            "missing": sorted(expected_names - actual_names),
            "extra": sorted(actual_names - expected_names),
        })


def _validate_a0_parent_npz(arrays: Mapping[str, np.ndarray], lane: str) -> None:
    if set(arrays) != set(A0_PARENT_ARRAYS):
        _fail("A0_PARENT_ARRAY_SET", lane)
    n = arrays["time_s"].shape[0]
    shapes = {
        "time_s": (n,), "service_position_m": (n, 3),
        "service_quaternion_wxyz": (n, 4), "R_joint_coordinates_rad": (n, 6),
        "P_joint_coordinates_m": (n, 2), "base_linear_m_s": (n, 3),
        "base_angular_rad_s": (n, 3), "R_joint_rad_s": (n, 6),
        "P_joint_m_s": (n, 2), "left_gap_m": (n,), "right_gap_m": (n,),
        "left_gap_rate_m_s": (n,), "right_gap_rate_m_s": (n,),
    }
    if n < 2:
        _fail("A0_PARENT_TOO_SHORT", lane)
    for name, shape in shapes.items():
        _shape(arrays[name], shape, f"A0_PARENT_SHAPE_{name}")
    if not np.all(np.diff(arrays["time_s"]) > 0.0) or abs(float(arrays["time_s"][-1]) - 0.08) > 1.0e-12:
        _fail("A0_PARENT_TIME_GRID", lane)
    if not _quaternion_rows_pass(arrays["service_quaternion_wxyz"]):
        _fail("A0_PARENT_QUATERNION", lane)


def _verify_a0(
    phase_root: Path, project_root: Path, metadata: Sequence[Mapping[str, Any]],
    arrays_by_slot: Mapping[int, Mapping[str, np.ndarray]],
    by_role: Mapping[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    manifest_path = verify_record(by_role["A0_PARENT_TRACE_MANIFEST"][0], project_root)
    parent_manifest = read_json(manifest_path, canonical=True)
    traces = parent_manifest.get("traces")
    if not (
        parent_manifest.get("schema") == "SIM13_V4B4G_A0_PARENT_REFERENCE_TRACES_V1"
        and parent_manifest.get("fresh_generation") is True
        and parent_manifest.get("trace_count") == 6
        and isinstance(traces, list) and len(traces) == 6
        and [row.get("lane_id") for row in traces] == list(LANES)
    ):
        _fail("A0_PARENT_MANIFEST_INVALID")
    parent_by_lane: dict[str, dict[str, np.ndarray]] = {}
    manifested_npz = {row["path"] for row in by_role["A0_PARENT_TRACE_NPZ"]}
    for trace in traces:
        lane = trace["lane_id"]
        npz_path = _safe_record_path(trace.get("npz_path"), project_root)
        relative = _project_relative(npz_path, project_root)
        if relative not in manifested_npz:
            _fail("A0_PARENT_NPZ_NOT_MANIFESTED", lane)
        if trace.get("npz_bytes") != npz_path.stat().st_size or trace.get("npz_sha256") != sha256_file(npz_path):
            _fail("A0_PARENT_NPZ_HASH", lane)
        arrays = _load_npz(npz_path)
        _validate_a0_parent_npz(arrays, lane)
        if trace.get("numeric_payload_sha256") != _array_payload_sha256(arrays):
            _fail("A0_PARENT_NUMERIC_SHA", lane)
        parent_by_lane[lane] = arrays
    maximum_quaternion_geodesic_rad = 0.0
    for lane in LANES:
        rows = [row for row in metadata if row["lane_id"] == lane and row["arm"] == "A0"]
        if len(rows) != 2:
            _fail("A0_PRE_POST_COUNT", lane)
        pre = next(row for row in rows if row["case_id"].endswith("__PRE"))
        post = next(row for row in rows if row["case_id"].endswith("__POST"))
        pre_arrays = arrays_by_slot[int(pre["slot_index"])]
        post_arrays = arrays_by_slot[int(post["slot_index"])]
        if set(pre_arrays) != set(post_arrays) or any(
            not np.array_equal(pre_arrays[name], post_arrays[name]) for name in pre_arrays
        ):
            _fail("A0_PRE_POST_NUMERIC_NOT_EXACT", lane)
        parent = parent_by_lane[lane]
        raw_channels = {
            "time_s": pre_arrays["time_s"],
            "service_position_m": pre_arrays["service_state_29"][:, 0:3],
            "service_quaternion_wxyz": pre_arrays["service_state_29"][:, 3:7],
            "R_joint_coordinates_rad": pre_arrays["service_state_29"][:, 7:13],
            "P_joint_coordinates_m": pre_arrays["service_state_29"][:, 13:15],
            "base_linear_m_s": pre_arrays["service_state_29"][:, 15:18],
            "base_angular_rad_s": pre_arrays["service_state_29"][:, 18:21],
            "R_joint_rad_s": pre_arrays["service_state_29"][:, 21:27],
            "P_joint_m_s": pre_arrays["service_state_29"][:, 27:29],
            "left_gap_m": pre_arrays["left_gap_m"],
            "right_gap_m": pre_arrays["right_gap_m"],
            "left_gap_rate_m_s": pre_arrays["left_gap_rate_m_s"],
            "right_gap_rate_m_s": pre_arrays["right_gap_rate_m_s"],
        }
        for name in A0_PARENT_ARRAYS:
            if raw_channels[name].shape != parent[name].shape:
                _fail("A0_RAW_PARENT_REPLAY", f"{lane}:{name}:shape")
            if name == "service_quaternion_wxyz":
                maximum_quaternion_geodesic_rad = max(
                    maximum_quaternion_geodesic_rad,
                    _verify_a0_quaternion_replay(
                        raw_channels[name], parent[name], lane,
                    ),
                )
            elif _max_abs(raw_channels[name] - parent[name]) > 1.0e-12:
                _fail("A0_RAW_PARENT_REPLAY", f"{lane}:{name}")
    return {
        "lane_count": 6,
        "sentinel_count": 12,
        "all_exact": True,
        "maximum_service_quaternion_geodesic_rad": (
            maximum_quaternion_geodesic_rad
        ),
        "service_quaternion_geodesic_tolerance_rad": 1.0e-12,
    }


def _gate_record(
    gate_id: str, status: str, predicate: bool | None, reason: str, detail: Any,
) -> dict[str, Any]:
    return {
        "gate_id": gate_id, "evaluation_status": status,
        "scientific_predicate": predicate, "applicability_reason": reason,
        "detail": detail,
    }


def _alpha_token(alpha: float) -> str:
    return "0P5" if alpha == 0.5 else str(int(alpha))


def _reference_eligibility(
    metadata: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_key: dict[tuple[str, float, float], Mapping[str, Any]] = {}
    for row in metadata:
        if row["arm"] != "A1":
            continue
        command = row["command_parameters"]["left"]
        key = (row["lane_id"], float(command["alpha"]), float(command["duration_s"]))
        if key in by_key:
            _fail("REFERENCE_LEVEL_DUPLICATE", key)
        by_key[key] = row
    records: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for alpha in (0.5, 1.0, 2.0, 4.0, 8.0, 16.0):
        for duration in (0.005, 0.01, 0.02):
            try:
                rk = by_key[("RK4_REFERENCE", alpha, duration)]
                mid = by_key[("MIDPOINT_REFERENCE", alpha, duration)]
            except KeyError as error:
                raise B4GIndependentAuditError(f"REFERENCE_LEVEL_MISSING:{error}") from error
            level_id = f"ALPHA_{_alpha_token(alpha)}__TCMD_MS_{round(duration * 1000)}"
            geometry = bool(rk["geometry_domain"]["passed"] and mid["geometry_domain"]["passed"])
            rk_finite = bool(rk["responses"]["finite_removal_event"])
            mid_finite = bool(mid["responses"]["finite_removal_event"])
            both_finite = rk_finite and mid_finite
            if not geometry:
                record = _gate_record(
                    "B4F-G12-CROSS-INTEGRATOR-CONVERGENCE", "NOT_APPLICABLE", None,
                    "REFERENCE_CASE_GEOMETRY_DOMAIN_EXIT",
                    {"level_id": level_id, "alpha": alpha, "T_cmd_s": duration},
                )
            elif not rk_finite and not mid_finite:
                record = _gate_record(
                    "B4F-G12-CROSS-INTEGRATOR-CONVERGENCE", "NOT_APPLICABLE", None,
                    "NO_PAIRED_FINITE_REFERENCE_EVENT",
                    {
                        "level_id": level_id, "alpha": alpha, "T_cmd_s": duration,
                        "rk4_finite": False, "midpoint_finite": False,
                    },
                )
            elif not both_finite:
                record = _gate_record(
                    "B4F-G12-CROSS-INTEGRATOR-CONVERGENCE", "PASS", False,
                    "EXACTLY_ONE_REFERENCE_FINITE_EVENT_EVALUATED_NEGATIVE_OUTCOME",
                    {
                        "level_id": level_id, "alpha": alpha, "T_cmd_s": duration,
                        "rk4_finite": rk_finite, "midpoint_finite": mid_finite,
                        "eligible": False, "one_reference_success_only_rule_applied": True,
                    },
                )
            else:
                acquisition_delta = abs(
                    float(rk["event_provenance"]["acquisition_time_s"])
                    - float(mid["event_provenance"]["acquisition_time_s"])
                )
                removal_delta = abs(
                    float(rk["event_provenance"]["removal_time_s"])
                    - float(mid["event_provenance"]["removal_time_s"])
                )
                rk_work = float(rk["responses"]["signed_work_terminal_J"])
                mid_work = float(mid["responses"]["signed_work_terminal_J"])
                work_tolerance = max(1.0e-10, 0.001 * max(abs(rk_work), abs(mid_work)))
                work_delta = abs(rk_work - mid_work)
                provenance = bool(
                    rk["event_provenance"]["fresh_b3_reconstruction"]
                    and mid["event_provenance"]["fresh_b3_reconstruction"]
                    and rk["event_provenance"]["lane_id"] != mid["event_provenance"]["lane_id"]
                    and rk["event_provenance"]["acquisition_certificate_sha256"]
                    != mid["event_provenance"]["acquisition_certificate_sha256"]
                    and rk["event_provenance"]["clearance_certificate_sha256"]
                    != mid["event_provenance"]["clearance_certificate_sha256"]
                )
                predicate = bool(
                    acquisition_delta <= 0.00025 and removal_delta <= 0.00025
                    and work_delta <= work_tolerance and provenance
                    and rk["responses"]["post_release_passed"]
                    and mid["responses"]["post_release_passed"]
                    and rk["responses"]["selector_case_integrity_pass"]
                    and mid["responses"]["selector_case_integrity_pass"]
                )
                detail = {
                    "level_id": level_id, "alpha": alpha, "T_cmd_s": duration,
                    "acquisition_time_difference_s": acquisition_delta,
                    "removal_time_difference_s": removal_delta,
                    "event_time_tolerance_s": 0.00025,
                    "signed_work_difference_J": work_delta,
                    "signed_work_tolerance_J": work_tolerance,
                    "lane_specific_fresh_provenance_pass": provenance,
                    "rk4_reference_case_id": rk["case_id"],
                    "midpoint_reference_case_id": mid["case_id"],
                }
                record = _gate_record(
                    "B4F-G12-CROSS-INTEGRATOR-CONVERGENCE", "PASS", predicate,
                    "PAIRED_FINITE_REFERENCE_EVENTS_EVALUATED", detail,
                )
                if predicate:
                    eligible.append({
                        "level_id": level_id, "alpha": alpha,
                        "command_duration_s": duration,
                        "case_abs_work_J": max(abs(rk_work), abs(mid_work)),
                        "rk4_reference_case_id": rk["case_id"],
                        "midpoint_reference_case_id": mid["case_id"],
                    })
            records.append(record)
    eligible.sort(key=lambda row: (
        row["alpha"], row["command_duration_s"], row["case_abs_work_J"], row["level_id"],
    ))
    return records, eligible


def _verify_summary_selector(
    summary: Mapping[str, Any], metadata: Sequence[Mapping[str, Any]],
    schedule: Mapping[str, Any], reference_force: Mapping[str, Any],
) -> dict[str, Any]:
    executed = sum(row["execution_status"] == "EXECUTED_FRESH_REGISTERED_SLOT" for row in metadata)
    a2_na = sum(row["execution_status"] == "NOT_EVALUATED_NO_A1_SUCCESS" for row in metadata)
    if not (
        summary.get("schema") == "SIM13_V4B4G_CAMPAIGN_SUMMARY_V1"
        and summary.get("final") is False
        and summary.get("scope") == "REGISTERED_SYNTHETIC_DISCRETE_DOMAIN_ONLY"
        and summary.get("logical_slot_count") == 144
        and summary.get("executed_slot_count") == executed
        and summary.get("a2_not_evaluated_slot_count") == a2_na
        and summary.get("case_integrity_failures") == []
        and summary.get("global_integrity_failures") == []
        and summary.get("registered_domain_execution_integrity_pass") is True
        and summary.get("claim_boundary") == CLAIM_BOUNDARY
    ):
        _fail("CAMPAIGN_SUMMARY_HEADER_OR_COUNTS")
    index = summary.get("case_metadata_index")
    if not isinstance(index, list) or len(index) != 144:
        _fail("CAMPAIGN_SUMMARY_CASE_INDEX")
    for slot, row, meta in zip(schedule["slots"], index, metadata):
        if not (
            row.get("slot_index") == slot["slot_index"]
            and row.get("case_id") == slot["case_id"]
            and row.get("execution_status") == meta["execution_status"]
        ):
            _fail("CAMPAIGN_SUMMARY_CASE_INDEX_ROW", slot["case_id"])
    q_ref = float(reference_force["individual_finger_reference_force_N"])
    if float(summary.get("one_common_Q_ref_per_finger_N")) != q_ref:
        _fail("SUMMARY_REFERENCE_FORCE_DRIFT")
    for row in metadata:
        if row["execution_status"] == "EXECUTED_FRESH_REGISTERED_SLOT" and float(row["command_parameters"]["Q_ref_per_finger_N"]) != q_ref:
            _fail("CASE_REFERENCE_FORCE_DRIFT", row["case_id"])
    g12, eligible = _reference_eligibility(metadata)
    if summary.get("cross_reference_gate_records_18") != g12:
        _fail("SUMMARY_G12_NOT_INDEPENDENT_RECOMPUTATION")
    if summary.get("reference_eligible_levels") != eligible:
        _fail("SUMMARY_ELIGIBLE_LEVELS_NOT_RECOMPUTATION")
    selected = eligible[0] if eligible else None
    selector = {
        "status": (
            "REACHABLE_IN_REGISTERED_SYNTHETIC_COMMAND_DOMAIN"
            if selected is not None else "NOT_OBSERVED_IN_REGISTERED_SYNTHETIC_COMMAND_DOMAIN"
        ),
        "eligible_level_count": len(eligible),
        "eligible_levels_in_frozen_sort_order": eligible,
        "reported_label": "lowest_tested_reachable_alpha_in_registered_discrete_grid",
        "lowest_tested_reachable_alpha_in_registered_discrete_grid": None if selected is None else selected["alpha"],
        "selected_tested_duration_s": None if selected is None else selected["command_duration_s"],
        "selected_parent_level": selected,
        "minimum_required_force_or_work_claimed": False,
        "continuous_threshold_or_interpolation_claimed": False,
        "global_unreachability_claimed": False,
    }
    if summary.get("selector") != selector:
        _fail("SUMMARY_SELECTOR_NOT_INDEPENDENT_RECOMPUTATION")
    a2_rows = [row for row in metadata if row["arm"] == "A2"]
    if selected is None:
        if len(a2_rows) != 24 or any(row["execution_status"] != "NOT_EVALUATED_NO_A1_SUCCESS" for row in a2_rows):
            _fail("A2_NO_PARENT_NOT_24_NA")
    elif len(a2_rows) != 24 or any(row["execution_status"] != "EXECUTED_FRESH_REGISTERED_SLOT" for row in a2_rows):
        _fail("A2_SELECTED_PARENT_NOT_24_EXECUTED")
    global_gates = summary.get("global_gate_records")
    if not isinstance(global_gates, list):
        _fail("SUMMARY_GLOBAL_GATES_NOT_LIST")
    g17 = next((row for row in global_gates if row.get("gate_id") == "B4F-G17-DISCRETE-GRID-REPORTING-BOUNDARY"), None)
    if not isinstance(g17, dict) or g17.get("evaluation_status") != "PASS" or g17.get("scientific_predicate") is not True or g17.get("detail") != selector:
        _fail("SUMMARY_G17_SELECTOR_BINDING")
    return {"eligible": eligible, "selected": selected, "selector": selector}


def _decode_pointer(pointer: str) -> list[str]:
    if not isinstance(pointer, str) or not pointer.startswith("/") or pointer == "/":
        _fail("MUTATION_PATCH_POINTER_INVALID", pointer)
    decoded: list[str] = []
    for encoded in pointer[1:].split("/"):
        token: list[str] = []
        index = 0
        while index < len(encoded):
            character = encoded[index]
            if character != "~":
                token.append(character)
                index += 1
                continue
            if index + 1 >= len(encoded) or encoded[index + 1] not in {"0", "1"}:
                _fail("MUTATION_PATCH_POINTER_ESCAPE", pointer)
            token.append("~" if encoded[index + 1] == "0" else "/")
            index += 2
        decoded.append("".join(token))
    return decoded


def _patch_list_index(token: str, length: int, *, allow_end: bool) -> int:
    if (
        not isinstance(token, str) or not token
        or (token != "0" and (not token.isascii() or not token.isdigit() or token.startswith("0")))
    ):
        _fail("MUTATION_PATCH_LIST_INDEX_NONCANONICAL", token)
    index = int(token)
    upper = length if allow_end else length - 1
    if index < 0 or index > upper:
        _fail("MUTATION_PATCH_LIST_INDEX", token)
    return index


def _apply_patch(base: Mapping[str, Any], operations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    result: Any = deepcopy(dict(base))
    for operation in operations:
        if not isinstance(operation, Mapping) or operation.get("op") not in {"add", "remove", "replace"}:
            _fail("MUTATION_PATCH_OPERATION_SCHEMA")
        op = operation["op"]
        expected_fields = {"op", "path"} if op == "remove" else {"op", "path", "value"}
        if set(operation) != expected_fields:
            _fail("MUTATION_PATCH_OPERATION_FIELDS")
        tokens = _decode_pointer(operation["path"])
        current = result
        for token in tokens[:-1]:
            try:
                current = (
                    current[_patch_list_index(token, len(current), allow_end=False)]
                    if isinstance(current, list) else current[token]
                )
            except (KeyError, IndexError, ValueError, TypeError) as error:
                raise B4GIndependentAuditError(f"MUTATION_PATCH_POINTER_MISSING:{operation['path']}") from error
        last = tokens[-1]
        if isinstance(current, list):
            if op == "add" and last == "-":
                current.append(deepcopy(operation["value"]))
                continue
            if last == "-":
                _fail("MUTATION_PATCH_DASH_ONLY_ADD", operation["path"])
            index = _patch_list_index(last, len(current), allow_end=(op == "add"))
            if op == "add":
                current.insert(index, deepcopy(operation["value"]))
            elif op == "replace":
                current[index] = deepcopy(operation["value"])
            else:
                del current[index]
        elif isinstance(current, dict):
            if op == "add":
                current[last] = deepcopy(operation["value"])
            elif last not in current:
                _fail("MUTATION_PATCH_KEY_MISSING", operation["path"])
            elif op == "replace":
                current[last] = deepcopy(operation["value"])
            else:
                del current[last]
        else:
            _fail("MUTATION_PATCH_TARGET_SCALAR", operation["path"])
    if not isinstance(result, dict):
        _fail("MUTATION_PATCH_RESULT_NOT_OBJECT")
    return result


def _expected_mutation_target(
    parent_id: str, subvariant_index: int, mutation_spec: Mapping[str, Any],
) -> str | list[str] | None:
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
        "B4FNC06": [
            "/payload/signed_W_act_J", "/payload/energy_minus_work_residual_J",
        ],
        "B4FNC07": "/payload/W_after_mapping_J",
        "B4FNC10": [
            "/payload/observed_finite_event", "/payload/classifier_mode",
        ],
        "B4FNC11": [
            "/payload/z_after", "/payload/linear_impulse_N_s",
            "/payload/angular_impulse_N_m_s", "/payload/kinetic_energy_jump_J",
        ],
        "B4FNC12": [
            "/payload/z_after", "/payload/reported_kinetic_increment_J",
        ],
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
        if subvariant_index <= 4:
            return f"/payload/P_coordinates_m/{0 if subvariant_index <= 2 else 1}"
        return "/payload/clipping_used" if subvariant_index == 5 else "/payload/extrapolation_used"
    if parent_id == "B4FNC22" and subvariant_index in (1, 2):
        return (
            "/payload/report/reported_label" if subvariant_index == 1
            else "/payload/report/minimum_required_force_or_work_claimed"
        )
    return None


def _verify_mutation_patch_semantics(
    parent_id: str, subvariant_index: int, target: Any,
    patch: Mapping[str, Any], base_payload: Mapping[str, Any],
    mutation_spec: Mapping[str, Any], frozen_q_ref: float,
) -> None:
    expected = _expected_mutation_target(parent_id, subvariant_index, mutation_spec)
    operations = patch.get("operations")
    if expected is None or target != expected or patch.get("target") != expected:
        _fail("MUTATION_FROZEN_TARGET_DRIFT", f"{parent_id}:{subvariant_index}")
    expected_paths = expected if isinstance(expected, list) else [expected]
    if not isinstance(operations, list) or [row.get("path") for row in operations] != expected_paths:
        _fail("MUTATION_FROZEN_PATCH_PATH_DRIFT", f"{parent_id}:{subvariant_index}")
    expected_op = "add" if parent_id == "B4FNC16" else "replace"
    if any(row.get("op") != expected_op for row in operations):
        _fail("MUTATION_FROZEN_PATCH_OPERATION_DRIFT", f"{parent_id}:{subvariant_index}")
    values = [row.get("value") for row in operations]
    targets = mutation_spec.get("deterministic_targets_and_amplitudes", {})
    exact = True
    if parent_id in {"B4FNC02", "B4FNC03"}:
        exact = values == [frozen_q_ref]
    elif parent_id == "B4FNC04":
        exact = values == [-1]
    elif parent_id == "B4FNC07":
        exact = values == [0.0]
    elif parent_id == "B4FNC08":
        exact = values == [frozen_q_ref, frozen_q_ref]
    elif parent_id == "B4FNC09":
        mode = "SINGLE_SIDE_LEFT" if subvariant_index == 1 else "SINGLE_SIDE_RIGHT"
        exact = values == [True, mode]
    elif parent_id == "B4FNC10":
        exact = values == [True, "ENDPOINT_ONLY"]
    elif parent_id == "B4FNC14":
        exact = bool(values and values[0] is True)
    elif parent_id == "B4FNC16":
        levels = targets.get("unregistered_levels", [])
        exact = (
            isinstance(levels, list) and 1 <= subvariant_index <= len(levels)
            and values == [levels[subvariant_index - 1]]
        )
    elif parent_id == "B4FNC17":
        parent = base_payload.get("parent_level")
        if not isinstance(parent, dict):
            exact = False
        else:
            alpha = parent.get("alpha")
            qref = parent.get("Q_ref_N")
            ratio = 0.75 if subvariant_index == 1 else 0.25
            exact = (
                _finite_number(alpha) and _finite_number(qref)
                and float(qref) == frozen_q_ref
                and values == [ratio * float(alpha) * frozen_q_ref] * 6
            )
    elif parent_id in {"B4FNC18", "B4FNC19"}:
        exact = values == [True]
    elif parent_id == "B4FNC20":
        exact = values == [0.0]
    elif parent_id == "B4FNC21":
        mutants = targets.get("P_domain_mutants", [])
        exact = bool(
            isinstance(mutants, list) and 1 <= subvariant_index <= len(mutants)
            and values == (
                [mutants[subvariant_index - 1].get("value_m")]
                if subvariant_index <= 4 else [True]
            )
        )
    elif parent_id == "B4FNC22":
        exact = values == (
            ["minimum_required_force"] if subvariant_index == 1 else [True]
        )
    if not exact:
        _fail("MUTATION_FROZEN_PATCH_VALUE_DRIFT", f"{parent_id}:{subvariant_index}")


def _finite_number(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(float(value))


def _sha256_string(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9A-F]{64}", value) is not None


def _mutation_profile(
    sample_time: float, acquisition: float, side: Mapping[str, Any], q_ref: float,
) -> float:
    alpha = float(side["alpha"])
    delay = float(side["delay_s"])
    duration = float(side["duration_s"])
    start = acquisition + delay
    end = start + duration
    if duration <= 0.0 or alpha == 0.0 or sample_time <= start or sample_time >= end:
        return 0.0
    return alpha * q_ref * math.sin(math.pi * (sample_time - start) / duration) ** 2


def _registered_mutation_slot(
    candidate: Any, frozen_schedule: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    slots = frozen_schedule.get("slots")
    if not isinstance(candidate, dict) or not isinstance(slots, list):
        return None
    matches = [slot for slot in slots if isinstance(slot, dict) and slot == candidate]
    return matches[0] if len(matches) == 1 else None


def _expected_mutation_command_sides(
    slot: Mapping[str, Any], command: Mapping[str, Any],
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


def _mutation_command_trace_is_registered(
    payload: Mapping[str, Any], *, frozen_schedule: Mapping[str, Any],
    frozen_q_ref: float, mutation_spec: Mapping[str, Any], parent_id: str,
) -> bool:
    slot = _registered_mutation_slot(payload.get("slot"), frozen_schedule)
    command = payload.get("command_parameters")
    if slot is None or not isinstance(command, dict) or payload.get("arm") != slot.get("arm"):
        return False
    acquisition = payload.get("acquisition_time_s")
    sample_time = payload.get("sample_time_s")
    q_ref = payload.get("Q_ref_N")
    if not all(_finite_number(value) for value in (acquisition, sample_time, q_ref)):
        return False
    if float(q_ref) != frozen_q_ref:
        return False
    origin = payload.get("trace_origin")
    if origin == "REGISTERED_CAMPAIGN_CASE":
        if parent_id not in {"B4FNC02", "B4FNC03"}:
            return False
        if payload.get("harness_id") is not None or payload.get("harness_command") is not None:
            return False
        expected_sides = _expected_mutation_command_sides(slot, command)
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
        if (
            not isinstance(dwell_hold, dict) or set(dwell_hold) != {"left", "right"}
            or not all(_finite_number(dwell_hold.get(side)) for side in ("left", "right"))
        ):
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
            if not _finite_number(value) or float(value) != expected:
                return False
    q = np.asarray(payload.get("observed_Q_14"), dtype=float)
    if q.shape != (14,) or not np.all(np.isfinite(q)):
        return False
    expected_q = np.zeros(14, dtype=float)
    expected_q[12] = _mutation_profile(
        float(sample_time), float(acquisition), expected_sides[0], frozen_q_ref,
    )
    expected_q[13] = _mutation_profile(
        float(sample_time), float(acquisition), expected_sides[1], frozen_q_ref,
    )
    if origin == "FROZEN_FINITE_EVENT_HARNESS" and payload.get("clearance_dwell_active") is True:
        expected_q[12] += float(dwell_hold["left"])
        expected_q[13] += float(dwell_hold["right"])
    return bool(np.array_equal(q, expected_q))


def _unit_interval_real_roots(coefficients: Sequence[float]) -> list[float]:
    values = np.asarray(coefficients, dtype=float)
    scale = float(np.max(np.abs(values))) if len(values) else 0.0
    if not math.isfinite(scale) or scale == 0.0:
        return []
    values = values / scale
    first = 0
    while first < len(values) - 1 and abs(float(values[first])) <= 1.0e-14:
        first += 1
    values = values[first:]
    if len(values) <= 1:
        return []
    roots = np.roots(values)
    result = [
        float(root.real) for root in roots
        if abs(float(root.imag)) <= 1.0e-10
        and -1.0e-12 <= float(root.real) <= 1.0 + 1.0e-12
    ]
    return sorted(set(round(min(1.0, max(0.0, value)), 14) for value in result))


def _hermite_coefficients(
    y0: float, y1: float, d0: float, d1: float, delta_t: float,
) -> tuple[float, float, float, float]:
    return (
        2.0 * y0 - 2.0 * y1 + delta_t * (d0 + d1),
        -3.0 * y0 + 3.0 * y1 - delta_t * (2.0 * d0 + d1),
        delta_t * d0,
        y0,
    )


def _independent_clearance_event(payload: Mapping[str, Any]) -> bool:
    time = np.asarray(payload["time_s"], dtype=float)
    left_gap = np.asarray(payload["left_gap_m"], dtype=float)
    right_gap = np.asarray(payload["right_gap_m"], dtype=float)
    left_rate = np.asarray(payload["left_gap_rate_m_s"], dtype=float)
    right_rate = np.asarray(payload["right_gap_rate_m_s"], dtype=float)
    ledger = np.asarray(payload["ledger_interval_certified"], dtype=bool)
    acquisition = float(payload["acquisition_time_s"])
    if not (time.ndim == 1 and len(time) >= 2 and np.all(np.diff(time) > 0.0)):
        return False
    if (
        any(array.shape != time.shape for array in (left_gap, right_gap, left_rate, right_rate))
        or ledger.shape != (len(time) - 1,)
        or not all(np.all(np.isfinite(array)) for array in (time, left_gap, right_gap, left_rate, right_rate))
        or not math.isfinite(acquisition)
    ):
        return False
    eligible: list[tuple[float, float]] = []
    for index in range(len(time) - 1):
        if not ledger[index]:
            continue
        delta_t = float(time[index + 1] - time[index])
        polynomials = [
            _hermite_coefficients(
                float(gap[index]), float(gap[index + 1]),
                float(rate[index]), float(rate[index + 1]), delta_t,
            )
            for gap, rate in ((left_gap, left_rate), (right_gap, right_rate))
        ]
        boundaries = {0.0, 1.0}
        for a, b, c, d in polynomials:
            boundaries.update(_unit_interval_real_roots((a, b, c, d - 1.0e-6)))
            boundaries.update(_unit_interval_real_roots((3.0 * a / delta_t, 2.0 * b / delta_t, c / delta_t + 1.0e-6)))
        ordered = sorted(boundaries)
        for lower, upper in zip(ordered[:-1], ordered[1:]):
            if upper - lower <= 1.0e-13:
                continue
            middle = 0.5 * (lower + upper)
            passed = True
            for a, b, c, d in polynomials:
                gap_value = ((a * middle + b) * middle + c) * middle + d
                rate_value = (3.0 * a * middle * middle + 2.0 * b * middle + c) / delta_t
                passed &= gap_value >= 1.0e-6 and rate_value >= -1.0e-6
            if passed:
                eligible.append((
                    float(time[index] + lower * delta_t),
                    float(time[index] + upper * delta_t),
                ))
    merged: list[list[float]] = []
    for start, end in sorted(eligible):
        if merged and start <= merged[-1][1] + 1.0e-12:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    earliest = acquisition + 0.001
    return any(
        upper - max(lower, earliest) >= 0.001 - 1.0e-12
        for lower, upper in merged
    )


def _clearance_payload_is_frozen_fixture(
    payload: Mapping[str, Any], parent_id: str, mutation_spec: Mapping[str, Any],
) -> bool:
    fixture_name = {
        "B4FNC09": "single_side_classifier_fixture",
        "B4FNC10": "endpoint_only_classifier_fixture",
    }.get(parent_id)
    targets = mutation_spec.get("deterministic_targets_and_amplitudes", {})
    fixture = targets.get(fixture_name) if fixture_name is not None else None
    if not isinstance(fixture, dict):
        return False
    canonical = fixture.get("canonical_payload")
    if (
        not isinstance(canonical, dict)
        or canonical_sha256(canonical) != fixture.get("canonical_payload_sha256")
    ):
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


def _independent_mutation_gate_pass(
    replay_type: str, gate_id: str, payload: Mapping[str, Any], *,
    parent_id: str, frozen_schedule: Mapping[str, Any], frozen_q_ref: float,
    mutation_spec: Mapping[str, Any], required_false: Mapping[str, Any],
    required_null_names: Sequence[str], project_root: Path,
) -> bool:
    """Recompute the named mutation Gate without validator or executor code."""

    try:
        if set(payload) != MUTATION_PAYLOAD_FIELDS[replay_type]:
            return False
        if replay_type == "BOUND_SOURCE_BYTES":
            source = payload["source_record"]
            candidate = payload["candidate_record"]
            path = _safe_record_path(payload["candidate_bytes_path"], project_root)
            registered_source = (
                mutation_spec.get("deterministic_targets_and_amplitudes", {})
                .get("source_byte_drift", {}).get("source_id")
            )
            return bool(
                payload.get("source_id") == registered_source
                and isinstance(source, dict) and isinstance(candidate, dict)
                and _finite_number(source.get("bytes")) and _finite_number(candidate.get("bytes"))
                and _sha256_string(source.get("sha256")) and _sha256_string(candidate.get("sha256"))
                and candidate.get("path") == payload["candidate_bytes_path"]
                and path.is_file() and path.stat().st_size == int(candidate["bytes"])
                and sha256_file(path) == candidate["sha256"]
                and candidate["bytes"] == source["bytes"]
                and candidate["sha256"] == source["sha256"]
            )
        if replay_type == "COMMAND_TRACE":
            q = np.asarray(payload["observed_Q_14"], dtype=float)
            if q.shape != (14,) or not np.all(np.isfinite(q)):
                return False
            registered = _mutation_command_trace_is_registered(
                payload, frozen_schedule=frozen_schedule, frozen_q_ref=frozen_q_ref,
                mutation_spec=mutation_spec, parent_id=parent_id,
            )
            if gate_id.startswith("B4F-G02"):
                command = payload["command_parameters"]
                return bool(
                    registered and payload["arm"] == "A0" and np.all(q == 0.0)
                    and all(
                        float(command[side][field]) == 0.0
                        for side in ("left", "right")
                        for field in ("alpha", "delay_s", "duration_s")
                    )
                )
            if gate_id.startswith("B4F-G03"):
                return bool(registered and np.all(q[:12] == 0.0))
            if gate_id.startswith("B4F-G08"):
                return bool(
                    registered and payload["clearance_dwell_active"] is True
                    and np.all(q == 0.0)
                )
            return False
        if replay_type == "GEOMETRY_SIGN_TRACE":
            p = np.asarray(payload["P_coordinates_m"], dtype=float)
            jacobian = np.asarray(payload["raw_gap_jacobian_P"], dtype=float)
            step = float(payload["centered_step_m"])
            return bool(
                p.shape == (2,) and jacobian.shape == (2, 2)
                and np.all(np.isfinite(p)) and np.all(np.isfinite(jacobian))
                and step == 1.0e-7 and np.all(p - step >= 0.0)
                and np.all(p + step <= 0.0715)
                and jacobian[0, 0] > 0.0 and jacobian[1, 1] > 0.0
                and payload["registered_signs"] == [1, 1]
                and payload["consumed_signs"] == [1, 1]
                and payload["clipping_used"] is False
                and payload["extrapolation_used"] is False
            )
        if replay_type == "WORK_TRACE":
            time = np.asarray(payload["time_s"], dtype=float)
            q = np.asarray(payload["Q_P_N"], dtype=float)
            eta = np.asarray(payload["eta_P_m_s"], dtype=float)
            work = np.asarray(payload["signed_W_act_J"], dtype=float)
            residual = np.asarray(payload["energy_minus_work_residual_J"], dtype=float)
            if (
                len(time) < 2 or q.shape != (len(time), 2)
                or eta.shape != (len(time), 2) or work.shape != time.shape
                or residual.shape != time.shape
                or not all(np.all(np.isfinite(array)) for array in (time, q, eta, work, residual))
                or not np.all(np.diff(time) > 0.0)
            ):
                return False
            power = np.sum(q * eta, axis=1)
            trapezoid = getattr(np, "trapezoid", None)
            integrated = (
                float(trapezoid(power, time))
                if trapezoid is not None else float(np.trapz(power, time))
            )
            cumulative = np.concatenate((
                np.asarray([float(work[0])]),
                float(work[0]) + np.cumsum(
                    0.5 * (power[:-1] + power[1:]) * np.diff(time)
                ),
            ))
            if gate_id.startswith("B4F-G04"):
                return bool(
                    abs(integrated - float(work[-1] - work[0])) <= 1.0e-7
                    and float(np.max(np.abs(cumulative - work))) <= 1.0e-7
                )
            return float(np.max(np.abs(residual))) <= 1.0e-7
        if replay_type == "REMOVAL_WORK_MAPPING":
            return bool(
                payload["finite_removal_event"] is True
                and _finite_number(payload["W_before_removal_J"])
                and _finite_number(payload["W_after_mapping_J"])
                and abs(float(payload["W_before_removal_J"])) > 1.0e-12
                and abs(
                    float(payload["W_after_mapping_J"])
                    - float(payload["W_before_removal_J"])
                ) <= 1.0e-15
            )
        if replay_type == "CLEARANCE_TRACE":
            return bool(
                _clearance_payload_is_frozen_fixture(payload, parent_id, mutation_spec)
                and payload.get("classifier_mode")
                == "BILATERAL_HERMITE_ALL_ROOT_EARLIEST_DWELL"
                and payload["observed_finite_event"] is _independent_clearance_event(payload)
            )
        if replay_type == "REMOVAL_MAPPING":
            before = np.asarray(payload["z_before"], dtype=float)
            after = np.asarray(payload["z_after"], dtype=float)
            linear = np.asarray(payload["linear_impulse_N_s"], dtype=float)
            angular = np.asarray(payload["angular_impulse_N_m_s"], dtype=float)
            return bool(
                before.shape == (20,) and after.shape == (20,)
                and linear.shape == (3,) and angular.shape == (3,)
                and all(np.all(np.isfinite(array)) for array in (before, after, linear, angular))
                and np.max(np.abs(after - before)) <= 1.0e-12
                and np.max(np.abs(linear)) <= 1.0e-12
                and np.max(np.abs(angular)) <= 1.0e-12
                and _finite_number(payload["kinetic_energy_jump_J"])
                and _finite_number(payload["ideal_constraint_stored_energy_J"])
                and abs(float(payload["kinetic_energy_jump_J"])) <= 1.0e-12
                and float(payload["ideal_constraint_stored_energy_J"]) == 0.0
            )
        if replay_type == "ENERGY_MAPPING":
            before = np.asarray(payload["z_before"], dtype=float)
            after = np.asarray(payload["z_after"], dtype=float)
            mass = np.asarray(payload["mass_20x20"], dtype=float)
            if (
                before.shape != (20,) or after.shape != (20,) or mass.shape != (20, 20)
                or not all(np.all(np.isfinite(array)) for array in (before, after, mass))
                or not np.array_equal(mass, mass.T)
            ):
                return False
            np.linalg.cholesky(mass)
            increment = 0.5 * float(after @ mass @ after - before @ mass @ before)
            return bool(
                _finite_number(payload["reported_kinetic_increment_J"])
                and abs(increment - float(payload["reported_kinetic_increment_J"])) <= 1.0e-10
                and abs(increment) <= 1.0e-12
            )
        if replay_type == "POST_RELEASE_TARGET_TRACE":
            independent = np.asarray(payload["independent_target_state_13"], dtype=float)
            candidate = np.asarray(payload["candidate_target_state_13"], dtype=float)
            time = np.asarray(payload["time_s"], dtype=float)
            return bool(
                independent.ndim == 2 and independent.shape[1:] == (13,)
                and len(independent) >= 2 and candidate.shape == independent.shape
                and time.shape == (len(independent),) and np.all(np.diff(time) > 0.0)
                and all(np.all(np.isfinite(array)) for array in (time, independent, candidate))
                and payload["candidate_target_source"] == "INDEPENDENT_13D_POST_STATE"
                and np.max(np.abs(candidate - independent)) <= 1.0e-12
                and _finite_number(payload["parent_crosscheck_terminal_max_abs"])
                and float(payload["parent_crosscheck_terminal_max_abs"]) <= 1.0e-12
            )
        if replay_type == "CONTACT_TRACE":
            force = np.asarray(payload["contact_force_N"], dtype=float)
            torque = np.asarray(payload["contact_torque_N_m"], dtype=float)
            return bool(
                payload["contact_kernel_enabled"] is False
                and force.size > 0 and torque.size > 0
                and np.all(np.isfinite(force)) and np.all(np.isfinite(torque))
                and np.max(np.abs(force)) <= 1.0e-12
                and np.max(np.abs(torque)) <= 1.0e-12
            )
        if replay_type == "REFERENCE_PAIR":
            rk4 = payload["rk4"]
            midpoint = payload["midpoint"]
            provenance = bool(
                rk4["lane_id"] == "RK4_REFERENCE"
                and midpoint["lane_id"] == "MIDPOINT_REFERENCE"
                and rk4["fresh_b3_reconstruction"] is True
                and midpoint["fresh_b3_reconstruction"] is True
                and _sha256_string(rk4["acquisition_certificate_sha256"])
                and _sha256_string(midpoint["acquisition_certificate_sha256"])
                and _sha256_string(rk4["clearance_certificate_sha256"])
                and _sha256_string(midpoint["clearance_certificate_sha256"])
                and rk4["acquisition_certificate_sha256"]
                != midpoint["acquisition_certificate_sha256"]
                and rk4["clearance_certificate_sha256"]
                != midpoint["clearance_certificate_sha256"]
            )
            tolerance = max(
                float(payload["work_absolute_floor_J"]),
                float(payload["work_relative_tolerance"]) * max(
                    abs(float(rk4["signed_work_J"])),
                    abs(float(midpoint["signed_work_J"])),
                ),
            )
            numeric = [
                payload["event_time_tolerance_s"], payload["work_relative_tolerance"],
                payload["work_absolute_floor_J"],
                *[
                    row[field] for row in (rk4, midpoint)
                    for field in ("acquisition_time_s", "removal_time_s", "signed_work_J")
                ],
            ]
            return bool(
                all(_finite_number(value) for value in numeric) and provenance
                and rk4["finite_removal_event"] is True
                and midpoint["finite_removal_event"] is True
                and rk4["post_release_passed"] is True
                and midpoint["post_release_passed"] is True
                and rk4["independent_integrity_pass"] is True
                and midpoint["independent_integrity_pass"] is True
                and abs(float(rk4["acquisition_time_s"]) - float(midpoint["acquisition_time_s"]))
                <= float(payload["event_time_tolerance_s"])
                and abs(float(rk4["removal_time_s"]) - float(midpoint["removal_time_s"]))
                <= float(payload["event_time_tolerance_s"])
                and abs(float(rk4["signed_work_J"]) - float(midpoint["signed_work_J"]))
                <= tolerance
            )
        if replay_type == "REGISTERED_SCHEDULE":
            return payload["schedule"] == frozen_schedule
        if replay_type == "A2_COMMAND_OR_TRACE_PAIR":
            lanes = payload["lanes"]
            parent = payload["parent_level"]
            if (
                not isinstance(parent, dict)
                or not all(_finite_number(parent.get(field)) for field in ("alpha", "command_duration_s", "Q_ref_N"))
            ):
                return False
            alpha = float(parent["alpha"])
            duration = float(parent["command_duration_s"])
            q_ref = float(parent["Q_ref_N"])
            registered_levels = {
                (float(row["alpha"]), float(row["command_duration_s"]))
                for row in frozen_schedule.get("slots", [])
                if isinstance(row, dict) and row.get("arm") == "A1"
            }
            pair = payload["pair_kind"]
            if pair == "HALF_DELAY":
                ratio = 0.5
                expected_variants = ("RIGHT_HALF_DELAY", "LEFT_HALF_DELAY_MIRROR")
            elif pair == "COMMAND_OFF":
                ratio = 0.0
                expected_variants = ("RIGHT_COMMAND_OFF", "LEFT_COMMAND_OFF_MIRROR")
            else:
                return False
            expected_right = np.asarray([alpha * q_ref, ratio * alpha * q_ref], dtype=float)
            expected_left = expected_right[::-1]
            return bool(
                q_ref == frozen_q_ref and (alpha, duration) in registered_levels
                and payload["right_variant"] == expected_variants[0]
                and payload["left_variant"] == expected_variants[1]
                and isinstance(lanes, list) and len(lanes) == 6
                and [row.get("lane_id") for row in lanes if isinstance(row, dict)] == list(LANES)
                and all(
                    np.array_equal(np.asarray(row["right_Q_2"], dtype=float), expected_right)
                    and np.array_equal(np.asarray(row["left_mirror_Q_2"], dtype=float), expected_left)
                    for row in lanes
                )
            )
        if replay_type == "GOVERNANCE_CANDIDATE":
            candidate = payload["candidate"]
            return bool(
                isinstance(candidate, dict)
                and all(candidate.get(field) is expected for field, expected in required_false.items())
                and all(candidate.get(field, "MISSING") is None for field in required_null_names)
            )
        if replay_type == "SELECTOR_REPORT":
            report = payload["report"]
            return bool(
                isinstance(report, dict)
                and report.get("reported_label")
                == "lowest_tested_reachable_alpha_in_registered_discrete_grid"
                and report.get("minimum_required_force_or_work_claimed") is False
                and report.get("continuous_threshold_or_interpolation_claimed") is False
                and report.get("global_unreachability_claimed") is False
            )
    except (
        KeyError, TypeError, ValueError, IndexError, OverflowError, OSError,
        ZeroDivisionError, np.linalg.LinAlgError, B4GIndependentAuditError,
    ):
        return False
    return False


def _independent_mutation_gate_record(
    gate_id: str, replay_type: str, passed: bool,
) -> dict[str, Any]:
    return {
        "schema": "SIM13_V4B4G_INDEPENDENT_MUTATION_GATE_REPLAY_V1",
        "gate_id": gate_id,
        "evaluation_status": "PASS" if passed else "FAIL",
        "scientific_predicate": bool(passed),
        "failed_gate_ids": [] if passed else [gate_id],
        "replay_type": replay_type,
    }


def _verify_independent_mutation_kill(
    *, parent_id: str, gate_id: str, base: Mapping[str, Any],
    mutant: Mapping[str, Any], frozen_schedule: Mapping[str, Any],
    frozen_q_ref: float, mutation_spec: Mapping[str, Any],
    governance: Mapping[str, Any], project_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    replay_type = MUTATION_REPLAY_TYPE_BY_PARENT.get(parent_id)
    if replay_type is None or base.get("replay_type") != replay_type or mutant.get("replay_type") != replay_type:
        _fail("MUTATION_REPLAY_TYPE_BINDING", parent_id)
    base_payload = base.get("payload")
    mutant_payload = mutant.get("payload")
    if not isinstance(base_payload, dict) or not isinstance(mutant_payload, dict):
        _fail("MUTATION_PAYLOAD_NOT_OBJECT", parent_id)
    arguments = {
        "parent_id": parent_id,
        "frozen_schedule": frozen_schedule,
        "frozen_q_ref": frozen_q_ref,
        "mutation_spec": mutation_spec,
        "required_false": governance["required_false"],
        "required_null_names": governance["required_null_physical_inputs"],
        "project_root": project_root,
    }
    nominal_pass = _independent_mutation_gate_pass(
        replay_type, gate_id, base_payload, **arguments,
    )
    mutant_pass = _independent_mutation_gate_pass(
        replay_type, gate_id, mutant_payload, **arguments,
    )
    nominal_record = _independent_mutation_gate_record(gate_id, replay_type, nominal_pass)
    mutant_record = _independent_mutation_gate_record(gate_id, replay_type, mutant_pass)
    if not nominal_pass or mutant_pass or mutant_record["failed_gate_ids"] != [gate_id]:
        _fail("MUTATION_NOT_INDEPENDENTLY_GATE_KILLED", parent_id)
    return nominal_record, mutant_record


def _verify_mutations(
    negative: Mapping[str, Any], mutation_spec: Mapping[str, Any],
    summary: Mapping[str, Any], project_root: Path, phase_root: Path,
    frozen_schedule: Mapping[str, Any], reference: Mapping[str, Any],
    governance: Mapping[str, Any],
    by_role: Mapping[str, list[dict[str, Any]]], validation: Mapping[str, Any],
) -> dict[str, Any]:
    parents = mutation_spec["required_parent_ids"]
    counts = mutation_spec["subvariant_counts_by_parent"]
    variants = mutation_spec["variants"]
    expected_counts = dict(zip(parents, counts))
    receipts = negative.get("receipts")
    count_payload = negative.get("counts", {})
    if not (
        set(negative) == NEGATIVE_CONTROL_KEYS
        and negative.get("schema") == "SIM13_V4B4G_NEGATIVE_CONTROL_EVIDENCE_V1"
        and negative.get("scope") == "REAL_RAW_ARTIFACT_OR_EXECUTED_PATH_MUTATIONS_ONLY"
        and parents == [f"B4FNC{index:02d}" for index in range(1, 23)]
        and negative.get("required_parent_ids") == parents
        and negative.get("subvariant_counts_by_parent") == counts
        and len(counts) == 22 and sum(counts) == 65
        and [row.get("count") for row in variants] == counts
        and isinstance(receipts, list) and len(receipts) == 65
        and set(count_payload) == {
            "required_parent_count", "total_subvariants", "executed_subvariants",
            "killed_subvariants", "unique_subvariants", "executed", "killed", "unique",
        }
        and count_payload.get("required_parent_count") == 22
        and count_payload.get("total_subvariants") == 65
        and count_payload.get("executed_subvariants") == 65
        and count_payload.get("killed_subvariants") == 65
        and count_payload.get("unique_subvariants") == 65
        and count_payload.get("executed") == 65
        and count_payload.get("killed") == 65
        and count_payload.get("unique") == 65
        and negative.get("all_65_subvariants_unique_hit_and_killed") is True
        and negative.get("final") is False and negative.get("audited") is False
        and negative.get("validator_pass_claimed") is False
        and negative.get("dictionary_flag_only_mutation_used") is False
        and negative.get("campaign_or_scientific_credit_from_mutations") is False
        and negative.get("campaign_negative_control_hook_closed") is False
        and negative.get("executor_bundle_generation_complete") is True
        and negative.get("claim_boundary") == CLAIM_BOUNDARY
        and negative.get("mutation_credit_boundary") == MUTATION_CREDIT_BOUNDARY
        and negative.get("memory") == MEMORY
    ):
        _fail("NEGATIVE_CONTROL_HEADER_OR_COUNTS")
    base_manifest = {row["path"]: row for row in by_role["MUTATION_BASE_BUNDLE"]}
    mutant_manifest = {row["path"]: row for row in by_role["MUTATION_MUTANT_BUNDLE"]}
    patch_manifest = {row["path"]: row for row in by_role["MUTATION_PATCH_BUNDLE"]}
    all_manifested_paths = {
        row["path"] for rows in by_role.values() for row in rows
    }
    receipt_ids: list[str] = []
    mutant_hashes: list[str] = []
    semantic_hashes: list[str] = []
    independent_gate_records: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    observed_counts: Counter[str] = Counter()
    indices_by_parent: dict[str, set[int]] = {parent: set() for parent in parents}
    supplemental_by_parent_index: dict[tuple[str, int], set[str]] = {}
    receipt_keys = {
        "receipt_id", "parent_id", "subvariant_index", "mutation_id", "target",
        "nominal_input_sha256", "mutant_input_sha256", "real_path_hit",
        "expected_gate", "killed", "execution_detail", "base_artifact",
        "mutant_artifact", "patch_artifact", "replay",
    }
    variant_by_parent = {parent: variant for parent, variant in zip(parents, variants)}
    for receipt in receipts:
        if not isinstance(receipt, dict) or set(receipt) != receipt_keys:
            _fail("MUTATION_RECEIPT_KEY_SET")
        parent = receipt["parent_id"]
        if parent not in expected_counts:
            _fail("MUTATION_RECEIPT_PARENT", parent)
        observed_counts[parent] += 1
        index = receipt["subvariant_index"]
        if type(index) is not int or not 1 <= index <= expected_counts[parent]:
            _fail("MUTATION_SUBVARIANT_INDEX", f"{parent}:{index}")
        if index in indices_by_parent[parent]:
            _fail("MUTATION_DUPLICATE_SUBVARIANT_INDEX", f"{parent}:{index}")
        indices_by_parent[parent].add(index)
        variant = variant_by_parent[parent]
        if receipt["mutation_id"] != variant["id"] or receipt["expected_gate"] != variant["expected_gate"]:
            _fail("MUTATION_VARIANT_OR_GATE_BINDING", receipt["receipt_id"])
        if receipt["real_path_hit"] is not True or receipt["killed"] is not True:
            _fail("MUTATION_NOT_REAL_PATH_KILLED", receipt["receipt_id"])
        artifacts: dict[str, tuple[Path, dict[str, Any]]] = {}
        for field, manifest_rows in (
            ("base_artifact", base_manifest), ("mutant_artifact", mutant_manifest),
            ("patch_artifact", patch_manifest),
        ):
            embedded = receipt[field]
            if not isinstance(embedded, dict):
                _fail("MUTATION_ARTIFACT_RECORD_NOT_OBJECT", receipt["receipt_id"])
            path = _resolve_embedded_record_path(embedded, project_root)
            relative = _project_relative(path, project_root)
            if relative not in manifest_rows:
                _fail("MUTATION_BUNDLE_NOT_MANIFESTED", f"{receipt['receipt_id']}:{field}")
            artifacts[field] = (path, read_json(path, canonical=True))
        base_path, base = artifacts["base_artifact"]
        mutant_path, mutant = artifacts["mutant_artifact"]
        patch_path, patch = artifacts["patch_artifact"]
        if receipt["nominal_input_sha256"] != sha256_file(base_path) or receipt["mutant_input_sha256"] != sha256_file(mutant_path):
            _fail("MUTATION_RECEIPT_INPUT_SHA", receipt["receipt_id"])
        if sha256_file(base_path) == sha256_file(mutant_path):
            _fail("MUTATION_BASE_MUTANT_IDENTICAL", receipt["receipt_id"])
        if not (
            set(patch) == {
                "schema", "receipt_id", "target", "format", "base_sha256",
                "mutant_sha256", "operations",
            }
            and
            patch.get("schema") == "SIM13_V4B4G_MUTATION_PATCH_V1"
            and patch.get("receipt_id") == receipt["receipt_id"]
            and patch.get("target") == receipt["target"]
            and patch.get("format") == "RFC6902_JSON_V1_RESTRICTED"
            and patch.get("base_sha256") == sha256_file(base_path)
            and patch.get("mutant_sha256") == sha256_file(mutant_path)
            and isinstance(patch.get("operations"), list) and patch["operations"]
        ):
            _fail("MUTATION_PATCH_HEADER", receipt["receipt_id"])
        frozen_q_ref = reference.get("individual_finger_reference_force_N")
        if not _finite_number(frozen_q_ref):
            _fail("MUTATION_REFERENCE_FORCE_INVALID")
        _verify_mutation_patch_semantics(
            parent, index, receipt["target"], patch, base.get("payload", {}),
            mutation_spec, float(frozen_q_ref),
        )
        if _apply_patch(base, patch["operations"]) != mutant:
            _fail("MUTATION_PATCH_DOES_NOT_REPRODUCE_MUTANT", receipt["receipt_id"])
        expected_bundle_keys = {
            "schema", "receipt_id", "parent_id", "mutation_id", "gate_id",
            "replay_type", "execution_provenance", "artifact_records", "payload",
            "claim_boundary",
        }
        if set(base) != expected_bundle_keys or set(mutant) != expected_bundle_keys:
            _fail("MUTATION_BUNDLE_KEY_SET", receipt["receipt_id"])
        common_keys = set(base) - {"payload"}
        if set(mutant) - {"payload"} != common_keys or any(base[key] != mutant[key] for key in common_keys):
            _fail("MUTATION_BUNDLE_COMMON_PROVENANCE_DRIFT", receipt["receipt_id"])
        if not (
            base.get("schema") == "SIM13_V4B4G_MUTATION_REPLAY_BUNDLE_V1"
            and base.get("receipt_id") == receipt["receipt_id"]
            and base.get("parent_id") == parent
            and base.get("mutation_id") == receipt["mutation_id"]
            and base.get("gate_id") == receipt["expected_gate"]
            and base.get("claim_boundary") == MUTATION_CREDIT_BOUNDARY
            and isinstance(base.get("artifact_records"), list)
            and len(base["artifact_records"]) >= 2
        ):
            _fail("MUTATION_BUNDLE_HEADER", receipt["receipt_id"])
        replay_type = MUTATION_REPLAY_TYPE_BY_PARENT.get(parent)
        replay_binding = receipt["replay"]
        expected_validator = (phase_root / "b4g_validation" / "mutation_replay.py").resolve()
        if not (
            replay_type is not None
            and isinstance(replay_binding, dict)
            and set(replay_binding) == {
                "schema", "evaluator_id", "independent_validator_path",
                "independent_validator_sha256",
            }
            and replay_binding.get("schema")
            == "SIM13_V4B4G_RECEIPT_INDEPENDENT_REPLAY_BINDING_V1"
            and replay_binding.get("evaluator_id") == f"B4G_VALIDATION::{replay_type}"
            and replay_binding.get("independent_validator_path")
            == _project_relative(expected_validator, project_root)
            and expected_validator.is_file()
            and replay_binding.get("independent_validator_sha256")
            == sha256_file(expected_validator)
        ):
            _fail("MUTATION_VALIDATOR_SOURCE_BINDING", receipt["receipt_id"])
        artifact_roles: set[str] = set()
        artifact_paths: list[str] = []
        for artifact in base["artifact_records"]:
            if not isinstance(artifact, dict) or set(artifact) != {"role", "path", "bytes", "sha256"}:
                _fail("MUTATION_UNDERLYING_RECORD_KEY_SET", receipt["receipt_id"])
            dependency_path = _resolve_embedded_record_path(artifact, project_root)
            relative = _project_relative(dependency_path, project_root)
            artifact_paths.append(relative)
            if relative not in all_manifested_paths:
                _fail("MUTATION_UNMANIFESTED_UNDERLYING", f"{receipt['receipt_id']}:{relative}")
            if isinstance(artifact.get("role"), str):
                artifact_roles.add(artifact["role"])
        if (
            len(artifact_paths) != len(set(path.casefold() for path in artifact_paths))
            or "EXECUTION_SOURCE_MANIFEST" not in artifact_roles
            or len(artifact_roles - {"EXECUTION_SOURCE_MANIFEST"}) < 1
        ):
            _fail("MUTATION_UNDERLYING_INVENTORY_NOT_SUBSTANTIVE_UNIQUE", receipt["receipt_id"])
        supplemental_by_parent_index[(parent, index)] = artifact_roles
        detail = receipt["execution_detail"]
        semantic = {
            "parent_id": parent,
            "subvariant_index": index,
            "mutation_id": receipt["mutation_id"],
            "replay_type": base["replay_type"],
            "target": receipt["target"],
            "operations": patch["operations"],
            "base_payload_sha256": canonical_sha256(base["payload"]),
            "mutant_payload_sha256": canonical_sha256(mutant["payload"]),
        }
        semantic_sha = canonical_sha256(semantic)
        if not (
            isinstance(detail, dict)
            and detail.get("semantic_mutation_sha256") == semantic_sha
            and detail.get("semantic_identity_excludes_receipt_id") is True
            and detail.get("harness_gate_result_authoritative") is False
            and detail.get("patch_operation_count") == len(patch["operations"])
        ):
            _fail("MUTATION_SEMANTIC_IDENTITY", receipt["receipt_id"])
        independent_gate_records[receipt["receipt_id"]] = _verify_independent_mutation_kill(
            parent_id=parent, gate_id=receipt["expected_gate"], base=base,
            mutant=mutant, frozen_schedule=frozen_schedule,
            frozen_q_ref=float(frozen_q_ref), mutation_spec=mutation_spec,
            governance=governance, project_root=project_root,
        )
        receipt_ids.append(receipt["receipt_id"])
        mutant_hashes.append(receipt["mutant_input_sha256"])
        semantic_hashes.append(semantic_sha)
    if observed_counts != Counter(expected_counts):
        _fail("MUTATION_PARENT_SUBVARIANT_COUNTS", dict(observed_counts))
    for parent, count in expected_counts.items():
        if indices_by_parent[parent] != set(range(1, count + 1)):
            _fail("MUTATION_SUBVARIANT_INDEX_COVERAGE", f"{parent}:{sorted(indices_by_parent[parent])}")
    if len(set(receipt_ids)) != 65 or len(set(mutant_hashes)) != 65 or len(set(semantic_hashes)) != 65:
        _fail("MUTATION_65_NOT_UNIQUE")
    for index in range(1, 3):
        roles = supplemental_by_parent_index[("B4FNC08", index)]
        if "MUTANT_DWELL_FORCE_TRACE" not in roles:
            _fail("NC08_SUPPLEMENTAL_TRACE_MISSING")
    if summary["selector"]["selected_parent_level"] is None:
        for index in range(1, 3):
            roles = supplemental_by_parent_index[("B4FNC17", index)]
            if "A2_DETECTOR_SIX_LANE_TRACE" not in roles:
                _fail("NC17_FALLBACK_SIX_LANE_TRACE_MISSING")
    if any(
        "GEOMETRY_CLIP_EXTRAPOLATE_TRACE"
        not in supplemental_by_parent_index[("B4FNC21", index)]
        for index in (5, 6)
    ):
        _fail("NC21_CLIP_EXTRAPOLATE_TRACE_MISSING")
    parent_summaries = negative.get("parent_summaries")
    if not isinstance(parent_summaries, list) or len(parent_summaries) != 22:
        _fail("MUTATION_PARENT_SUMMARIES")
    for row, parent, count, variant in zip(parent_summaries, parents, counts, variants):
        if row != {
            "parent_id": parent, "expected_gate": variant["expected_gate"],
            "expected_count": count, "executed_count": count,
            "killed_count": count, "passed": True,
        }:
            _fail("MUTATION_PARENT_SUMMARY_ROW", parent)
    observation = validation.get("observations", {}).get("negative_controls")
    if not isinstance(observation, dict):
        _fail("VALIDATOR_GENERATED_REPLAY_OBSERVATION_MISSING")
    replays = observation.get("validator_generated_replays")
    if not (
        observation.get("parent_count") == 22
        and observation.get("subvariant_count") == 65
        and observation.get("executed") == 65
        and observation.get("killed") == 65
        and observation.get("unique") == 65
        and observation.get("validator_generated_replay_count") == 65
        and isinstance(replays, list) and len(replays) == 65
        and observation.get("validator_generated_replays_sha256") == canonical_sha256(replays)
    ):
        _fail("VALIDATOR_GENERATED_REPLAY_HEADER")
    replay_by_id: dict[str, Mapping[str, Any]] = {}
    for replay in replays:
        receipt_id = replay.get("receipt_id")
        if not isinstance(receipt_id, str) or receipt_id in replay_by_id:
            _fail("VALIDATOR_GENERATED_REPLAY_ID_DUPLICATE")
        replay_by_id[receipt_id] = replay
    if set(replay_by_id) != set(receipt_ids):
        _fail("VALIDATOR_GENERATED_REPLAY_RECEIPT_SET")
    receipt_by_id = {row["receipt_id"]: row for row in receipts}
    for receipt_id, replay in replay_by_id.items():
        receipt = receipt_by_id[receipt_id]
        nominal_record, mutant_record = independent_gate_records[receipt_id]
        if not (
            replay.get("parent_id") == receipt["parent_id"]
            and replay.get("subvariant_index") == receipt["subvariant_index"]
            and replay.get("nominal_input_sha256") == receipt["nominal_input_sha256"]
            and replay.get("mutant_input_sha256") == receipt["mutant_input_sha256"]
            and replay.get("real_path_hit") is True
            and replay.get("expected_gate") == receipt["expected_gate"]
            and replay.get("actual_failed_gate") == receipt["expected_gate"]
            and replay.get("killed") is True
            and replay.get("independently_killed") is True
            and replay.get("nominal_gate_record") == nominal_record
            and replay.get("mutant_gate_record") == mutant_record
            and replay.get("nominal_gate_sha256") == canonical_sha256(nominal_record)
            and replay.get("mutant_gate_sha256") == canonical_sha256(mutant_record)
        ):
            _fail("VALIDATOR_GENERATED_REPLAY_BINDING", receipt_id)
    return {
        "parent_count": 22,
        "receipt_count": 65,
        "all_unique_and_independently_gate_recomputed_killed": True,
    }


def _verify_no_active_attempt_or_invalidation(phase_root: Path) -> None:
    incomplete = phase_root / "b4g_mutation_execution" / "SIM13_V4B4G_MUTATION_EXECUTION_INCOMPLETE_V1.json"
    if os.path.lexists(incomplete):
        _fail("MUTATION_EXECUTION_INCOMPLETE_MARKER_PRESENT", incomplete)
    for relative, schema in (
        ("results/SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json", "SIM13_V4B4G_EXECUTION_INVALIDATED_V1"),
        ("results/SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1.json", "SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1"),
    ):
        path = phase_root / relative
        if not os.path.lexists(path):
            continue
        if path.is_symlink():
            _fail("INVALIDATION_MARKER_SYMLINK_FORBIDDEN", relative)
        if not path.is_file():
            _fail("INVALIDATION_MARKER_NOT_REGULAR_FILE", relative)
        payload = read_json(path, canonical=True)
        if payload.get("schema") != schema:
            _fail("INVALIDATION_MARKER_SCHEMA", relative)
        if payload.get("active") is not False:
            _fail("ACTIVE_INVALIDATION_OR_SUPERSESSION_MARKER", relative)


def _verify_runtime_and_protected(
    phase_root: Path, project_root: Path, governance: Mapping[str, Any],
    by_role: Mapping[str, list[dict[str, Any]]], post: Mapping[str, Any],
) -> dict[str, Any]:
    runtime_path = verify_record(by_role["RUNTIME_ENVIRONMENT"][0], project_root)
    runtime = read_json(runtime_path, canonical=True)
    identity = runtime.get("runtime_identity")
    if not (
        runtime.get("schema") == "SIM13_V4B4G_RUNTIME_ENVIRONMENT_V1"
        and isinstance(identity, dict)
        and runtime.get("runtime_identity_sha256") == canonical_sha256(identity)
        and {key: identity.get(key) for key in MEMORY} == MEMORY
    ):
        _fail("RUNTIME_MEMORY_OR_IDENTITY_INVALID")
    pre_path = verify_record(by_role["PRE_RUN_PROTECTED_ASSET_SNAPSHOT"][0], project_root)
    pre = read_json(pre_path, canonical=True)
    protected_keys = {
        "bound_parent_count", "bound_parents", "local_forbidden_artifacts",
        "protected_scope", "preregistration_source_verification",
    }
    for payload, label in ((pre, "PRE"), (post, "POST")):
        if payload.get("bound_parent_count") != 11 or payload.get("local_forbidden_artifacts") != [] or payload.get("pass") is not True:
            _fail(f"{label}_PROTECTED_SNAPSHOT_STATUS")
        if payload.get("protected_scope") != governance["protected_asset_snapshot_scope"]:
            _fail(f"{label}_PROTECTED_SCOPE")
        bound = payload.get("bound_parents")
        if not isinstance(bound, list) or len(bound) != 11:
            _fail(f"{label}_BOUND_PARENT_COUNT")
        for record in bound:
            _resolve_embedded_record_path(record, project_root)
        core = {key: payload[key] for key in protected_keys}
        if payload.get("snapshot_payload_sha256") != canonical_sha256(core):
            _fail(f"{label}_PROTECTED_PAYLOAD_SHA")
    if any(
        pre.get(key) != post.get(key)
        for key in protected_keys | {"snapshot_payload_sha256", "pass"}
    ):
        _fail("PRE_POST_PROTECTED_SNAPSHOT_DRIFT")
    _scan_forbidden_local_artifacts(phase_root, governance)
    return {"runtime_identity_sha256": runtime["runtime_identity_sha256"], "bound_parent_count": 11}


def _scan_forbidden_local_artifacts(
    phase_root: Path, governance: Mapping[str, Any],
) -> None:
    forbidden_literals = set(governance["forbidden_local_artifacts"][1:])
    def generated_directory(name: str) -> bool:
        return bool(
            name == "__pycache__" or name == ".pytest_cache"
            or name.startswith(".pytest") or name.startswith(".smoke")
        )
    for current, directory_names, file_names in os.walk(
        phase_root, topdown=True, followlinks=False,
    ):
        directory_names[:] = sorted(
            name for name in directory_names if not generated_directory(name)
        )
        current_path = Path(current)
        for name in sorted(file_names):
            path = current_path / name
            if path.is_symlink():
                _fail("B4G_SYMLINK_DURING_FORBIDDEN_SCAN", path.relative_to(phase_root).as_posix())
            if path.suffix.lower() == ".urdf" or path.name in forbidden_literals:
                _fail("B4G_FORBIDDEN_LOCAL_ARTIFACT", path.relative_to(phase_root).as_posix())


def _verify_post_run(
    post: Mapping[str, Any], evidence_schema: Mapping[str, Any],
    summary_path: Path, negative_path: Path, project_root: Path,
) -> None:
    protected_keys = {
        "bound_parent_count", "bound_parents", "local_forbidden_artifacts",
        "protected_scope", "preregistration_source_verification",
        "snapshot_payload_sha256", "pass",
    }
    expected = protected_keys | {
        "schema", "classification", "final_post_run", "negative_controls_completed",
        "final_signing_authorized", "publication_order", "campaign_summary_dependency",
        "negative_control_dependency", "source_identity_reverification",
        "source_identity_sha256", "recursive_parent_post_verification",
        "recursive_parent_post_identity_sha256", "runtime_identity",
        "runtime_identity_sha256", "a0_parent_reference_trace_post_verification",
        "a0_parent_reference_trace_manifest_sha256", "reference_force_reverification",
        "raw_case_inventory_post_run", "reverification_checks", "claim_boundary",
    }
    _assert_exact_keys(post, expected, "POST_RUN_KEY_SET")
    order = evidence_schema["publication_order"]
    post_name = POST_REL.name
    prefix = order[: order.index(post_name) + 1]
    if not (
        post["schema"] == "SIM13_V4B4G_POST_RUN_PROTECTED_ASSET_SNAPSHOT_V1"
        and post["classification"] == "FINAL_POST_RUN_BEFORE_READ_ONLY_VALIDATOR"
        and post["final_post_run"] is True
        and post["negative_controls_completed"] is True
        and post["final_signing_authorized"] is False
        and post["publication_order"] == prefix
        and post["claim_boundary"] == CLAIM_BOUNDARY
        and isinstance(post["reverification_checks"], dict)
        and post["reverification_checks"]
        and all(value is True for value in post["reverification_checks"].values())
        and post["source_identity_sha256"] == canonical_sha256(post["source_identity_reverification"])
        and post["recursive_parent_post_identity_sha256"] == canonical_sha256(post["recursive_parent_post_verification"])
        and post["runtime_identity_sha256"] == canonical_sha256(post["runtime_identity"])
    ):
        _fail("POST_RUN_STATUS_OR_REVERIFICATION")
    for record, expected_path, expected_role in (
        (post["campaign_summary_dependency"], summary_path, "CAMPAIGN_SUMMARY"),
        (post["negative_control_dependency"], negative_path, "NEGATIVE_CONTROL_EVIDENCE"),
    ):
        if record.get("role") != expected_role or verify_record(record, project_root) != expected_path.resolve():
            _fail("POST_RUN_DEPENDENCY_RECORD", expected_role)


def _verify_governance(
    governance: Mapping[str, Any], run_spec: Mapping[str, Any],
    summary: Mapping[str, Any], negative: Mapping[str, Any], post: Mapping[str, Any],
) -> dict[str, Any]:
    required_false = governance["required_false"]
    required_null = {name: None for name in governance["required_null_physical_inputs"]}
    if any(value is not False for value in required_false.values()):
        _fail("GOVERNANCE_CONTRACT_REQUIRED_FALSE_NOT_FALSE")
    if governance["formal_sim13_v2_state_unchanged"] != FORMAL_STATE:
        _fail("GOVERNANCE_FORMAL_STATE_DRIFT")
    if governance["memory_record_required"] != MEMORY or run_spec["memory"] != MEMORY:
        _fail("GOVERNANCE_MEMORY_DRIFT")
    if summary.get("governance") != {
        "required_false": required_false,
        "required_null_physical_inputs": required_null,
        "formal_sim13_v2_state_unchanged": FORMAL_STATE,
        "memory": MEMORY,
    }:
        _fail("SUMMARY_GOVERNANCE_DRIFT")
    expected_capabilities = {
        "registered_negative_controls_executed": True,
        "physical_release_implemented": False,
        "current_system_bound": False,
        "formal_nc19_credit": False,
        "owner_authorized": False,
        "production_ready": False,
        "release_authorized": False,
        "next_stage_authorized": False,
    }
    capabilities = negative.get("capabilities")
    if capabilities != expected_capabilities:
        _fail("NEGATIVE_CONTROL_GOVERNANCE_PROMOTION_OR_KEY_DRIFT")
    if negative.get("memory") != MEMORY:
        _fail("NEGATIVE_CONTROL_MEMORY_DRIFT")
    if {key: post["runtime_identity"].get(key) for key in MEMORY} != MEMORY:
        _fail("POST_RUN_MEMORY_DRIFT")
    return {
        "required_false": required_false,
        "required_null_physical_inputs": required_null,
        "formal_sim13_v2_state_unchanged": FORMAL_STATE,
        "memory": MEMORY,
    }


def _verify_preaudit(
    preaudit: Mapping[str, Any], governance_state: Mapping[str, Any],
    project_root: Path, expected_paths: Mapping[str, Path],
) -> None:
    _assert_exact_keys(preaudit, PREAUDIT_KEYS, "PREAUDIT_KEY_SET")
    _assert_exact_keys(preaudit["inputs"], PREAUDIT_INPUT_KEYS, "PREAUDIT_INPUT_KEY_SET")
    _assert_exact_keys(preaudit["checks"], PREAUDIT_CHECK_KEYS, "PREAUDIT_CHECK_KEY_SET")
    _assert_exact_keys(preaudit["governance"], PREAUDIT_GOVERNANCE_KEYS, "PREAUDIT_GOVERNANCE_KEY_SET")
    if not (
        preaudit["schema"] == "SIM13_V4B4G_PREAUDIT_GATE_V1"
        and preaudit["scope"] == SCOPE
        and preaudit["status"] == "PASS_READY_FOR_INDEPENDENT_AUDIT"
        and preaudit["ready_for_independent_audit"] is True
        and preaudit["final"] is False and preaudit["audited"] is False
        and all(value is True for value in preaudit["checks"].values())
        and preaudit["claim_boundary"] == CLAIM_BOUNDARY
    ):
        _fail("PREAUDIT_NOT_EXACT_READY")
    expected_roles = {
        "execution_validation": "EXECUTION_VALIDATION_FULL",
        "evidence_manifest": "EVIDENCE_MANIFEST_SELF_EXCLUDED",
        "post_run_snapshot": "POST_RUN_PROTECTED_ASSET_SNAPSHOT",
        "campaign_summary": "CAMPAIGN_SUMMARY",
        "negative_control_evidence": "NEGATIVE_CONTROL_EVIDENCE",
        "execution_source_freeze_terminal": "EXECUTION_SOURCE_FREEZE_TERMINAL",
    }
    for name, record in preaudit["inputs"].items():
        if record.get("role") != expected_roles[name] or verify_record(record, project_root) != expected_paths[name].resolve():
            _fail("PREAUDIT_INPUT_RECORD", name)
    expected_governance = {
        **governance_state,
        "physical_current_formal_owner_production_release_next_stage_hold": True,
    }
    if preaudit["governance"] != expected_governance:
        _fail("PREAUDIT_GOVERNANCE_DRIFT")


def _rehash_manifest_records(manifest: Mapping[str, Any], project_root: Path) -> str:
    for record in manifest["records"]:
        verify_record(record, project_root)
    return canonical_sha256(manifest["records"])


def _verify_terminal_payload(
    terminal: Mapping[str, Any], terminal_path: Path, project_root: Path,
) -> None:
    expected_keys = {
        "schema", "self_excluded", "acyclic", "records", "record_count",
        "excluded_self_path", "claim_boundary",
    }
    _assert_exact_keys(terminal, expected_keys, "TERMINAL_KEY_SET")
    records = terminal.get("records")
    self_path = _project_relative(terminal_path, project_root)
    if not (
        terminal["schema"] == "SIM13_V4B4G_TERMINAL_SELF_EXCLUDED_MANIFEST_V1"
        and terminal["self_excluded"] is True and terminal["acyclic"] is True
        and isinstance(records, list) and terminal["record_count"] == len(records) == 4
        and terminal["excluded_self_path"] == self_path
        and terminal["claim_boundary"] == CLAIM_BOUNDARY
        and self_path not in {row.get("path") for row in records if isinstance(row, dict)}
    ):
        _fail("TERMINAL_SELF_EXCLUSION_OR_HEADER")
    if [row.get("role") for row in records] != [
        "PREAUDIT_GATE", "EVIDENCE_MANIFEST_SELF_EXCLUDED",
        "INDEPENDENT_AUDIT_RECEIPT", "AUDITED_FINAL_GATE",
    ]:
        _fail("TERMINAL_RECORD_ORDER")
    for record in records:
        verify_record(record, project_root)


def _verify_campaign_prefix_auxiliary(
    phase_root: Path, project_root: Path, by_role: Mapping[str, list[dict[str, Any]]],
    schedule_contract: Mapping[str, Any], reference_contract: Mapping[str, Any],
    source_freeze: Mapping[str, Any], selector_state: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> None:
    schedule_path = verify_record(by_role["REGISTERED_SCHEDULE"][0], project_root)
    if read_json(schedule_path, canonical=True) != schedule_contract:
        _fail("PUBLISHED_SCHEDULE_NOT_FROZEN_CONTRACT")
    reference_path = verify_record(by_role["REFERENCE_FORCE_AND_ACQUISITION"][0], project_root)
    reference = read_json(reference_path, canonical=True)
    if not (
        reference.get("schema") == "SIM13_V4B4G_REFERENCE_FORCE_AND_ACQUISITION_V1"
        and reference.get("one_common_Q_ref_per_finger_N") == reference_contract["individual_finger_reference_force_N"]
        and reference.get("per_lane_or_treatment_rescaling_used") is False
        and reference.get("explicit_matrix_inverse_used") is False
        and reference.get("expected_execution_source_freeze_terminal_sha256") == source_freeze["terminal_sha256"]
        and reference.get("claim_boundary") == CLAIM_BOUNDARY
    ):
        _fail("REFERENCE_FORCE_EVIDENCE_INVALID")
    source_path = verify_record(by_role["SOURCE_MANIFEST_SELF_EXCLUDED"][0], project_root)
    source = read_json(source_path, canonical=True)
    identity = source.get("identity", {})
    if not (
        source.get("schema") == "SIM13_V4B4G_SOURCE_MANIFEST_SELF_EXCLUDED_V1"
        and source.get("self_excluded") is True and source.get("acyclic") is True
        and source.get("claim_boundary") == CLAIM_BOUNDARY
        and isinstance(identity, dict)
        and identity.get("local_sources") == _current_source_inventory(project_root, phase_root)
        and identity.get("local_source_inventory_sha256") == canonical_sha256(identity["local_sources"])
        and identity.get("expected_execution_source_freeze_terminal_sha256") == source_freeze["terminal_sha256"]
        and identity.get("execution_source_freeze", {}).get("pass") is True
    ):
        _fail("CAMPAIGN_SOURCE_MANIFEST_INVALID")
    a2_path = verify_record(by_role["A2_SELECTION_LEDGER"][0], project_root)
    ledger = read_json(a2_path, canonical=True)
    core = {key: value for key, value in ledger.items() if key != "ledger_payload_sha256"}
    if not (
        ledger.get("schema") == "SIM13_V4B4G_A2_SELECTION_LEDGER_V1"
        and ledger.get("self_excluded") is True
        and ledger.get("cross_reference_gate_records_18") == summary["cross_reference_gate_records_18"]
        and ledger.get("eligible_levels_in_frozen_sort_order") == selector_state["eligible"]
        and ledger.get("selected_parent_level") == selector_state["selected"]
        and ledger.get("selection_sort") == [
            "alpha_ascending", "T_cmd_s_ascending", "case_abs_work_J_ascending",
            "canonical_level_id_ascending",
        ]
        and ledger.get("a2_not_evaluated_if_selected_parent_is_null") is True
        and ledger.get("ledger_payload_sha256") == canonical_sha256(core)
    ):
        _fail("A2_SELECTION_LEDGER_INVALID")


def _load_contracts(phase_root: Path) -> dict[str, dict[str, Any]]:
    files = {
        "schema": "PHASE_B4G_EVIDENCE_SCHEMA_V1.json",
        "governance": "PHASE_B4G_GOVERNANCE_V1.json",
        "schedule": "PHASE_B4G_REGISTERED_SCHEDULE_V1.json",
        "run_spec": "PHASE_B4G_RUN_SPEC_V1.json",
        "mutation": "PHASE_B4G_MUTATION_HARNESS_SPEC_V1.json",
        "reference": "PHASE_B4G_REFERENCE_FORCE_V1.json",
    }
    result = {
        name: read_json(phase_root / "contracts" / filename)
        for name, filename in files.items()
    }
    if result["schema"].get("schema") != "SIM13_V4B4G_EVIDENCE_SCHEMA_V1":
        _fail("EVIDENCE_SCHEMA_CONTRACT_INVALID")
    if result["governance"].get("schema") != "SIM13_V4B4G_GOVERNANCE_V1":
        _fail("GOVERNANCE_CONTRACT_INVALID")
    if result["mutation"].get("total_subvariants") != 65:
        _fail("MUTATION_CONTRACT_INVALID")
    return result


def audit_phase(
    phase_root: Path = PHASE_ROOT, *, project_root: Path | None = None,
    sign: bool = True,
) -> dict[str, Any]:
    phase = _absolute_lexical(phase_root)
    formal_phase = _absolute_lexical(PHASE_ROOT)
    if sign and os.path.normcase(os.fspath(phase)) != os.path.normcase(os.fspath(formal_phase)):
        _fail("FORMAL_SIGNING_REQUIRES_MODULE_PHASE_ROOT", phase)
    if sign:
        _assert_no_reparse_lexical_chain(
            formal_phase,
            require_leaf_exists=True,
            code="FORMAL_SIGNING_PHASE_CHAIN",
        )
    project = (
        find_project_root(phase)
        if project_root is None else _absolute_lexical(project_root)
    )
    formal_project = find_project_root(formal_phase)
    if sign and os.path.normcase(os.fspath(project)) != os.path.normcase(os.fspath(formal_project)):
        _fail("FORMAL_SIGNING_REQUIRES_FORMAL_PROJECT_ROOT", project)
    if sign:
        _assert_no_reparse_lexical_chain(
            formal_project,
            require_leaf_exists=True,
            code="FORMAL_SIGNING_PROJECT_CHAIN",
        )
    if sign:
        clean_final(phase)
    checks: list[dict[str, Any]] = []

    def passed(identifier: str, detail: Any) -> None:
        checks.append({"id": identifier, "passed": True, "detail": detail})

    try:
        _assert_import_independence(Path(__file__).resolve())
        passed("B4GA01_IMPORT_INDEPENDENCE", "STDLIB_AND_NUMPY_ONLY")
        _verify_no_active_attempt_or_invalidation(phase)
        passed("B4GA02_NO_ACTIVE_INCOMPLETE_OR_INVALIDATION", True)
        contracts = _load_contracts(phase)
        if contracts["schema"].get("claim_boundary") != CLAIM_BOUNDARY:
            _fail("EVIDENCE_SCHEMA_CLAIM_BOUNDARY")
        passed("B4GA03_FROZEN_CONTRACTS", 6)

        manifest_path = phase / MANIFEST_REL
        validation_path = phase / VALIDATION_REL
        preaudit_path = phase / PREAUDIT_REL
        summary_path = phase / SUMMARY_REL
        negative_path = phase / NEGATIVE_REL
        post_path = phase / POST_REL
        initial_files = {
            path: (path.stat().st_size, sha256_file(path))
            for path in (
                manifest_path, validation_path, preaudit_path, summary_path,
                negative_path, post_path,
            )
            if path.is_file()
        }
        if len(initial_files) != 6:
            _fail("AUDIT_INPUT_PREFIX_INCOMPLETE", len(initial_files))

        manifest, by_role, _ = _verify_manifest(manifest_path, project, phase)
        passed("B4GA04_EVIDENCE_MANIFEST_DAG", manifest["record_count"])
        validation_record_path = verify_record(by_role["EXECUTION_VALIDATION_FULL"][0], project)
        if validation_record_path != validation_path:
            _fail("VALIDATION_CANONICAL_PATH")
        validation = read_json(validation_path, canonical=True)
        _verify_validation(validation)
        passed("B4GA05_FULL_READ_ONLY_VALIDATION_BOUND", validation["check_count"])

        source_terminal_path = verify_record(by_role["EXECUTION_SOURCE_FREEZE_TERMINAL"][0], project)
        source_freeze = _verify_source_freeze(source_terminal_path, project, phase)
        passed("B4GA06_EXECUTION_SOURCE_FREEZE_EXACT_CURRENT", source_freeze)

        summary_manifest_path = verify_record(by_role["CAMPAIGN_SUMMARY"][0], project)
        negative_manifest_path = verify_record(by_role["NEGATIVE_CONTROL_EVIDENCE"][0], project)
        post_manifest_path = verify_record(by_role["POST_RUN_PROTECTED_ASSET_SNAPSHOT"][0], project)
        if (summary_manifest_path, negative_manifest_path, post_manifest_path) != (
            summary_path, negative_path, post_path,
        ):
            _fail("CANONICAL_PRIMARY_EVIDENCE_PATH")
        summary = read_json(summary_path, canonical=True)
        negative = read_json(negative_path, canonical=True)
        post = read_json(post_path, canonical=True)
        _verify_post_run(post, contracts["schema"], summary_path, negative_path, project)
        passed("B4GA07_FINAL_POST_RUN_PREFIX", len(post["publication_order"]))
        runtime_protected = _verify_runtime_and_protected(
            phase, project, contracts["governance"], by_role, post,
        )
        passed("B4GA08_RUNTIME_AND_PROTECTED_ASSETS", runtime_protected)

        metadata, arrays_by_slot = _load_cases(
            phase, project, contracts["schedule"], by_role,
        )
        passed("B4GA09_REGISTERED_144_RAW_CASES", {
            "metadata": len(metadata), "npz": len(arrays_by_slot),
        })
        a0_state = _verify_a0(phase, project, metadata, arrays_by_slot, by_role)
        passed("B4GA10_A0_PARENT_AND_PRE_POST", a0_state)
        selector_state = _verify_summary_selector(
            summary, metadata, contracts["schedule"], contracts["reference"],
        )
        passed("B4GA11_G12_SELECTOR_G17", {
            "eligible_count": len(selector_state["eligible"]),
            "selected": selector_state["selected"],
        })
        finite_count = sum(row["responses"].get("finite_removal_event") is True for row in metadata)
        passed("B4GA12_G10_ALL_EVENT_OR_EXACT_NA", {"finite_event_cases": finite_count})
        _verify_campaign_prefix_auxiliary(
            phase, project, by_role, contracts["schedule"], contracts["reference"],
            source_freeze, selector_state, summary,
        )
        passed("B4GA13_AUXILIARY_PREFIX_BINDINGS", True)

        mutation_state = _verify_mutations(
            negative, contracts["mutation"], summary, project, phase,
            contracts["schedule"], contracts["reference"], contracts["governance"],
            by_role, validation,
        )
        passed("B4GA14_MUTATION_65_INDEPENDENT_GATE_RECOMPUTATION", mutation_state)
        governance_state = _verify_governance(
            contracts["governance"], contracts["run_spec"], summary, negative, post,
        )
        passed("B4GA15_GOVERNANCE_HOLDS", True)

        preaudit = read_json(preaudit_path, canonical=True)
        expected_paths = {
            "execution_validation": validation_path,
            "evidence_manifest": manifest_path,
            "post_run_snapshot": post_path,
            "campaign_summary": summary_path,
            "negative_control_evidence": negative_path,
            "execution_source_freeze_terminal": source_terminal_path,
        }
        _verify_preaudit(preaudit, governance_state, project, expected_paths)
        passed("B4GA16_PREAUDIT_NOT_FINAL_AND_BOUND", True)
        if _rehash_manifest_records(manifest, project) != manifest["records_canonical_sha256"]:
            _fail("MANIFEST_RECORDS_TOCTOU_BEFORE_SIGN")
        for path, identity in initial_files.items():
            if not path.is_file() or (path.stat().st_size, sha256_file(path)) != identity:
                _fail("PRIMARY_INPUT_TOCTOU_BEFORE_SIGN", path)
        _verify_no_active_attempt_or_invalidation(phase)
        passed("B4GA17_PRE_SIGN_TOCTOU", manifest["record_count"])
    except BaseException as error:
        if sign:
            _cleanup_final_then_reraise(phase, error)
        raise

    result = {
        "schema": "SIM13_V4B4G_INDEPENDENT_AUDIT_RESULT_V1",
        "status": "PASS",
        "expected_checks": 17,
        "observed_checks": len(checks),
        "passed_checks": sum(row["passed"] for row in checks),
        "checks": checks,
        "selector": selector_state["selector"],
        "finite_removal_case_count": finite_count,
        "manifest_record_count": manifest["record_count"],
    }
    if len(checks) != 17:
        if sign:
            clean_final(phase)
        _fail("AUDIT_CHECK_COUNT_INTERNAL", len(checks))
    if not sign:
        return result

    receipt_path = phase / RECEIPT_REL
    final_path = phase / AUDITED_GATE_REL
    terminal_path = phase / TERMINAL_REL
    try:
        # Last mutable-boundary recheck before the first signing write.
        _verify_no_active_attempt_or_invalidation(phase)
        _verify_source_freeze(source_terminal_path, project, phase)
        if _rehash_manifest_records(manifest, project) != manifest["records_canonical_sha256"]:
            _fail("MANIFEST_RECORDS_FINAL_PREWRITE_TOCTOU")
        for path, identity in initial_files.items():
            if not path.is_file() or (path.stat().st_size, sha256_file(path)) != identity:
                _fail("PRIMARY_INPUT_FINAL_PREWRITE_TOCTOU", path)
        receipt = {
            "schema": "SIM13_V4B4G_INDEPENDENT_AUDIT_RECEIPT_V1",
            "status": "PASS",
            "audit_independence": "NO_IMPORT_OF_SOLVER_RUNNER_MUTATION_EXECUTOR_VALIDATOR_OR_TESTS__STDLIB_AND_NUMPY_ONLY",
            "scope": SCOPE,
            "expected_checks": 17,
            "observed_checks": 17,
            "passed_checks": 17,
            "preaudit_gate": file_record(preaudit_path, "PREAUDIT_GATE", project),
            "evidence_manifest": file_record(manifest_path, "EVIDENCE_MANIFEST_SELF_EXCLUDED", project),
            "execution_validation": file_record(validation_path, "EXECUTION_VALIDATION_FULL", project),
            "checks": checks,
            "claim_boundary": CLAIM_BOUNDARY,
        }
        _assert_final_publication_parents_safe(phase)
        atomic_write_json(receipt_path, receipt)
        selected = selector_state["selected"]
        a2_evaluated = any(
            row["arm"] == "A2" and row["execution_status"] == "EXECUTED_FRESH_REGISTERED_SLOT"
            for row in metadata
        )
        capability_state = {
            "b4g_workflow_authorized": True,
            "b4g_execution_spec_frozen": True,
            "b4g_solver_implemented": True,
            "b4g_campaign_executed": True,
            "parent_b4f_recursively_verified": True,
            "registered_domain_evaluated": True,
            "a0_replay_verified": True,
            "registered_negative_controls_executed": True,
            "b4g_execution_audited": True,
            "synthetic_reachability_observed": selected is not None,
            "lowest_tested_reachable_alpha_reported": selected is not None,
            "algorithm_only_case_removal_executed": finite_count > 0,
            "a2_stress_lane_evaluated": a2_evaluated,
        }
        _assert_final_publication_parents_safe(phase)
        final = {
            "schema": "SIM13_V4B4G_AUDITED_GATE_V1",
            "status": "PASS_PHASE_B4G_INDEPENDENT_AUDIT__REGISTERED_SYNTHETIC_DISCRETE_DOMAIN_ONLY__ALL_PHYSICAL_CURRENT_FORMAL_OWNER_PRODUCTION_RELEASE_NEXT_STAGE_HOLDS",
            "final": True,
            "scope": SCOPE,
            "preaudit_gate": file_record(preaudit_path, "PREAUDIT_GATE", project),
            "independent_audit_receipt": file_record(receipt_path, "INDEPENDENT_AUDIT_RECEIPT_17_OF_17", project),
            "evidence_manifest": file_record(manifest_path, "EVIDENCE_MANIFEST_SELF_EXCLUDED", project),
            "execution_validation": file_record(validation_path, "EXECUTION_VALIDATION_FULL", project),
            "capability_state": capability_state,
            "selector": selector_state["selector"],
            "required_false": governance_state["required_false"],
            "required_null_physical_inputs": governance_state["required_null_physical_inputs"],
            "formal_sim13_v2_state_unchanged": FORMAL_STATE,
            "memory": MEMORY,
            "physical_current_formal_nc19_owner_production_release_next_stage": "HOLD",
            "mechanical_ruling": (
                "Only the preregistered synthetic discrete 6R+2P command domain is audited. "
                "Any observed removal is algorithm-only; no physical actuator, lock, retention, "
                "release, current-system, NC19, Owner, production, or next-stage credit follows."
            ),
            "claim_boundary": CLAIM_BOUNDARY,
        }
        atomic_write_json(final_path, final)
        _assert_final_publication_parents_safe(phase)
        terminal = {
            "schema": "SIM13_V4B4G_TERMINAL_SELF_EXCLUDED_MANIFEST_V1",
            "self_excluded": True,
            "acyclic": True,
            "records": [
                file_record(preaudit_path, "PREAUDIT_GATE", project),
                file_record(manifest_path, "EVIDENCE_MANIFEST_SELF_EXCLUDED", project),
                file_record(receipt_path, "INDEPENDENT_AUDIT_RECEIPT", project),
                file_record(final_path, "AUDITED_FINAL_GATE", project),
            ],
            "record_count": 4,
            "excluded_self_path": _project_relative(terminal_path, project),
            "claim_boundary": CLAIM_BOUNDARY,
        }
        atomic_write_json(terminal_path, terminal)
        terminal_read = read_json(terminal_path, canonical=True)
        if terminal_read != terminal:
            _fail("TERMINAL_READBACK_MISMATCH")
        _verify_terminal_payload(terminal_read, terminal_path, project)
        if read_json(receipt_path, canonical=True) != receipt or read_json(final_path, canonical=True) != final:
            _fail("SIGNED_PAYLOAD_READBACK")
        if _rehash_manifest_records(manifest, project) != manifest["records_canonical_sha256"]:
            _fail("MANIFEST_RECORDS_TOCTOU_AFTER_SIGN")
        for path, identity in initial_files.items():
            if (path.stat().st_size, sha256_file(path)) != identity:
                _fail("PRIMARY_INPUT_TOCTOU_AFTER_SIGN", path)
        _verify_source_freeze(source_terminal_path, project, phase)
        _verify_no_active_attempt_or_invalidation(phase)
    except BaseException as error:
        _cleanup_final_then_reraise(phase, error)
    return {
        **result,
        "independent_audit_receipt": file_record(receipt_path, "INDEPENDENT_AUDIT_RECEIPT", project),
        "audited_gate": file_record(final_path, "AUDITED_FINAL_GATE", project),
        "terminal": file_record(terminal_path, "TERMINAL_SELF_EXCLUDED_MANIFEST", project),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase-root", type=Path, default=PHASE_ROOT,
        help="B4G publication root; the formal default is this module's directory",
    )
    parser.add_argument(
        "--preflight", action="store_true",
        help="perform the full read-only audit without cleanup or terminal signing",
    )
    arguments = parser.parse_args(argv)
    try:
        result = audit_phase(arguments.phase_root, sign=not arguments.preflight)
    except Exception as error:
        print(json.dumps({
            "schema": "SIM13_V4B4G_INDEPENDENT_AUDIT_FAILURE_V1",
            "status": "DIAGNOSTIC_FAIL_CLOSED",
            "error": f"{type(error).__name__}:{error}",
            "final_signed": False,
            "claim_boundary": CLAIM_BOUNDARY,
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
        return 3
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
