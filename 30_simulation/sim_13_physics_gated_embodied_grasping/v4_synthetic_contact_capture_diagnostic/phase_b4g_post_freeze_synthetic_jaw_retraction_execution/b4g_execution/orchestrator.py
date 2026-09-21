"""Full 144-slot, resumable and source-bound B4G execution workflow."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import stat
from typing import Any, Callable, Iterable, Mapping

import numpy as np

from b4g_solver import campaign
from b4g_solver import forced_retraction as forced

from .evidence import (
    _B4E_PROVENANCE_FILES,
    _FRESH_B3_EVENT_SOURCE,
    _compare_fresh_b4e_to_frozen_template,
    CLAIM_BOUNDARY,
    compare_a2_mirror_pair,
    executed_case_payload,
    gate_record,
    not_evaluated_a2_payload,
    validate_acquisition_certificate_binding,
    validate_case_npz_schema,
)
from .io import (
    EvidenceIOError,
    array_payload_sha256,
    atomic_write_json,
    atomic_write_npz,
    canonical_bytes,
    canonical_sha256,
    display_path,
    read_json,
    sha256_file,
    verify_npz,
)
from .source_guard import (
    SourceGuardError,
    execution_identity,
    protected_snapshot,
    require_plain_file_under_root,
    verify_recursive_parents,
)


PHASE_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = forced.b4e._project_root().resolve()
CONTRACT_ROOT = PHASE_ROOT / "contracts"
A0_PARENT_INTERCHANGE_PATH = (
    PHASE_ROOT / "b4g_validation" / "PHASE_B4G_A0_PARENT_TRACE_INTERCHANGE_V1.json"
)

A0_PARENT_TRACE_ARRAYS = (
    "time_s",
    "service_position_m",
    "service_quaternion_wxyz",
    "R_joint_coordinates_rad",
    "P_joint_coordinates_m",
    "base_linear_m_s",
    "base_angular_rad_s",
    "R_joint_rad_s",
    "P_joint_m_s",
    "left_gap_m",
    "right_gap_m",
    "left_gap_rate_m_s",
    "right_gap_rate_m_s",
)

_OUTPUT_MARKER = ".sim13_v4b4g_execution_output_root.json"
_STALE_FINAL_RELATIVE_PATHS = (
    "results/SIM13_V4B4G_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json",
    "results/SIM13_V4B4G_AUDITED_GATE_V1.json",
    "evidence/SIM13_V4B4G_INDEPENDENT_AUDIT_RECEIPT_V1.json",
    "results/SIM13_V4B4G_PREAUDIT_GATE_V1.json",
    "evidence/SIM13_V4B4G_EVIDENCE_MANIFEST_SELF_EXCLUDED_V1.json",
    "evidence/SIM13_V4B4G_EXECUTION_VALIDATION_V1.json",
    "evidence/SIM13_V4B4G_POST_RUN_PROTECTED_ASSET_SNAPSHOT_V1.json",
    "evidence/SIM13_V4B4G_PROVISIONAL_POST_CAMPAIGN_PROTECTED_ASSET_SNAPSHOT_V1.json",
    "results/SIM13_V4B4G_CAMPAIGN_SUMMARY_V1.json",
)

_A0_LANE_DEFINITION = {
    "RK4_COARSE": ("rk4", 0.001),
    "RK4_FINE": ("rk4", 0.0005),
    "RK4_REFERENCE": ("rk4", 0.00025),
    "MIDPOINT_COARSE": ("midpoint", 0.0005),
    "MIDPOINT_FINE": ("midpoint", 0.00025),
    "MIDPOINT_REFERENCE": ("midpoint", 0.000125),
}

_INTEGRITY_CASE_GATE_IDS = {
    "B4F-G02-A0-EXACT-REPLAY",
    "B4F-G03-P-ONLY-INTERNAL-GENERALIZED-FORCE",
    "B4F-G04-ACTUATOR-WORK-LEDGER",
    "B4F-G05-P-H-CONSERVATION",
    "B4F-G06-ENERGY-MINUS-WORK-IDENTITY",
    "B4F-G07-CONTACT-CONSTRAINT-MUTUAL-EXCLUSION",
    "B4F-G08-COMMAND-ZERO-BEFORE-REMOVAL",
    "B4F-G10-EXACT-ZERO-JUMP-REMOVAL",
    "B4F-G11-INDEPENDENT-POST-RELEASE-5MS",
}

_INTEGRITY_GLOBAL_GATE_IDS = {
    "B4F-G01-SOURCE-AND-PARENT-RECURSIVE",
    "B4F-G02-A0-EXACT-REPLAY",
    "B4F-G14-REGISTERED-DOMAIN-NO-POST-HOC-EXTENSION",
    "B4F-G15-GOVERNANCE-AND-NULL-PHYSICAL-INPUTS",
    "B4F-G17-DISCRETE-GRID-REPORTING-BOUNDARY",
}

_SUPERSESSION_RECEIPT_RELATIVE_PATH = (
    "results/SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1.json"
)

_FORMAL_EXECUTION_SOURCE_FREEZE_TERMINAL_RELATIVE_PATH = Path(
    "results/SIM13_V4B4G_EXECUTION_SOURCE_FREEZE_TERMINAL_"
    "SELF_EXCLUDED_MANIFEST_V1.json"
)
_FORMAL_EXECUTION_SOURCE_FREEZE_GATE_RELATIVE_PATH = Path(
    "results/SIM13_V4B4G_EXECUTION_SOURCE_FREEZE_GATE_V1.json"
)
_FORMAL_EXECUTION_SOURCE_MANIFEST_RELATIVE_PATH = Path(
    "evidence/SIM13_V4B4G_EXECUTION_SOURCE_MANIFEST_V1.json"
)

_B4E_ACTIVE_TRACES_BINDING = (
    PHASE_ROOT.parent
    / "phase_b4_post_freeze_synthetic_6d_solver"
    / "evidence"
    / "SIM13_V4B4E_ACTIVE_TRACES_V1.json",
    1_341_400,
    "956BB62D1BED86738158A416B2EE6FDB6963F6D6B2E78F1ECA9D347430BC2CAD",
)

_B4E_EVIDENCE_MANIFEST_BINDING = (
    PHASE_ROOT.parent
    / "phase_b4_post_freeze_synthetic_6d_solver"
    / "evidence"
    / "SIM13_V4B4E_EVIDENCE_MANIFEST_V1.json",
    2_876,
    "58B5A33B294FDD3DD486A5A3BC653793299D2CD365F7661E690B15557C8A4E27",
)


class B4GExecutionError(RuntimeError):
    """The registered campaign could not continue without violating its contract."""


def _load_contracts() -> dict[str, dict[str, Any]]:
    names = {
        "bindings": "PHASE_B4G_SOURCE_BINDINGS_V1.json",
        "run_spec": "PHASE_B4G_RUN_SPEC_V1.json",
        "schedule": "PHASE_B4G_REGISTERED_SCHEDULE_V1.json",
        "reference": "PHASE_B4G_REFERENCE_FORCE_V1.json",
        "governance": "PHASE_B4G_GOVERNANCE_V1.json",
        "schema": "PHASE_B4G_EVIDENCE_SCHEMA_V1.json",
        "authorization": "PHASE_B4G_POST_FREEZE_WORK_AUTHORIZATION_V1.json",
    }
    contracts = {key: read_json(CONTRACT_ROOT / name) for key, name in names.items()}
    campaign.validate_registered_schedule(contracts["schedule"])
    if contracts["authorization"]["authorized"]["execute_registered_a0_a1_and_conditional_a2_campaign"] is not True:
        raise B4GExecutionError("B4G_CAMPAIGN_NOT_AUTHORIZED")
    if contracts["authorization"]["authorized"]["modify_b4_b4e_or_b4f"] is not False:
        raise B4GExecutionError("PARENT_READ_ONLY_AUTHORITY_DRIFT")
    return contracts


def _runtime_identity() -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "python_executable": os.path.realpath(os.sys.executable),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": __import__("scipy").__version__,
        "memory_gate_applicable": False,
        "memory_gate_passed": False,
        "owner_override_used": False,
        "classification": "DIAGNOSTIC_ONLY",
    }


def _runtime_record(identity: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": "SIM13_V4B4G_RUNTIME_ENVIRONMENT_V1",
        "sampled_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "runtime_identity": dict(identity),
        "runtime_identity_sha256": canonical_sha256(identity),
    }


def _prepare_output_root(output_root: Path) -> Path:
    requested = _require_lexical_output_root_no_links(output_root)
    root = requested.resolve()
    if root == Path(root.anchor) or root == PROJECT_ROOT or root == PROJECT_ROOT.parent:
        raise B4GExecutionError(f"UNSAFE_B4G_OUTPUT_ROOT:{root}")
    if root != PHASE_ROOT:
        if _paths_overlap(root, PHASE_ROOT):
            raise B4GExecutionError(f"CUSTOM_OUTPUT_ROOT_OVERLAPS_PHASE_ROOT:{root}")
        existed = root.exists()
        if existed and not root.is_dir():
            raise B4GExecutionError(f"CUSTOM_OUTPUT_ROOT_NOT_DIRECTORY:{root}")
        marker = root / _OUTPUT_MARKER
        payload = {
            "schema": "SIM13_V4B4G_EXECUTION_OUTPUT_ROOT_MARKER_V1",
            "phase_root": PHASE_ROOT.as_posix(),
            "resolved_output_root": root.as_posix(),
        }
        if existed and not os.path.lexists(marker):
            try:
                next(root.iterdir())
            except StopIteration:
                pass
            else:
                raise B4GExecutionError(
                    "CUSTOM_OUTPUT_ROOT_EXISTING_NONEMPTY_REQUIRES_MARKER"
                )
        if os.path.lexists(marker):
            if _is_managed_link_or_reparse(marker) or not marker.is_file():
                raise B4GExecutionError("CUSTOM_OUTPUT_ROOT_MARKER_NOT_PLAIN_FILE")
            if (
                read_json(marker) != payload
                or marker.read_bytes() != canonical_bytes(payload) + b"\n"
            ):
                raise B4GExecutionError("CUSTOM_OUTPUT_ROOT_MARKER_MISMATCH")
        else:
            root.mkdir(parents=True, exist_ok=True)
            atomic_write_json(marker, payload)
    else:
        root.mkdir(parents=True, exist_ok=True)
    return root


def _is_managed_link_or_reparse(path: Path) -> bool:
    candidate = Path(path)
    if candidate.is_symlink():
        return True
    is_junction = getattr(candidate, "is_junction", None)
    if callable(is_junction) and is_junction():
        return True
    try:
        attributes = getattr(candidate.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _require_lexical_output_root_no_links(path: Path) -> Path:
    target = Path(os.path.abspath(path))
    current = Path(target.anchor)
    for part in target.parts[1:]:
        current = current / part
        if os.path.lexists(current) and _is_managed_link_or_reparse(current):
            raise B4GExecutionError(f"B4G_OUTPUT_ROOT_LINK_OR_REPARSE_FORBIDDEN:{current}")
    return target


def _paths_overlap(first: Path, second: Path) -> bool:
    left = Path(first).resolve()
    right = Path(second).resolve()
    try:
        left.relative_to(right)
        return True
    except ValueError:
        pass
    try:
        right.relative_to(left)
        return True
    except ValueError:
        return False


def _require_managed_output_directory(
    path: Path,
    output_root: Path,
    *,
    create: bool,
) -> Path:
    root = Path(os.path.abspath(output_root))
    target = Path(os.path.abspath(path))
    try:
        relative = target.relative_to(root)
    except ValueError as error:
        raise B4GExecutionError(f"MANAGED_OUTPUT_DIRECTORY_ESCAPED:{target}") from error
    current = root
    for part in relative.parts:
        current = current / part
        if os.path.lexists(current):
            if _is_managed_link_or_reparse(current) or not current.is_dir():
                raise B4GExecutionError(
                    f"MANAGED_OUTPUT_DIRECTORY_LINK_REPARSE_OR_NONDIR:{current}"
                )
        elif create:
            current.mkdir()
        else:
            raise B4GExecutionError(f"MANAGED_OUTPUT_DIRECTORY_MISSING:{current}")
    try:
        target.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise B4GExecutionError(f"MANAGED_OUTPUT_DIRECTORY_RESOLVED_ESCAPE:{target}") from error
    return target


def _prepare_campaign_managed_directories(output_root: Path) -> None:
    for relative in (
        "evidence",
        "evidence/raw_cases",
        "evidence/a0_parent_reference_traces",
        "evidence/recovery_receipts",
        "results",
    ):
        _require_managed_output_directory(
            output_root / relative, output_root, create=True,
        )


def _preflight_existing_campaign_managed_directories(output_root: Path) -> None:
    for relative in (
        "evidence",
        "evidence/raw_cases",
        "evidence/a0_parent_reference_traces",
        "evidence/recovery_receipts",
        "results",
    ):
        path = output_root / relative
        if os.path.lexists(path):
            _require_managed_output_directory(
                path, output_root, create=False,
            )


def _validated_output_root(output_root: Path) -> Path:
    root = Path(output_root).resolve()
    if root == PHASE_ROOT:
        return root
    marker = root / _OUTPUT_MARKER
    if (
        not os.path.lexists(marker)
        or _is_managed_link_or_reparse(marker)
        or not marker.is_file()
    ):
        raise B4GExecutionError("CUSTOM_OUTPUT_ROOT_MARKER_MISSING")
    payload = read_json(marker)
    if (
        payload.get("schema") != "SIM13_V4B4G_EXECUTION_OUTPUT_ROOT_MARKER_V1"
        or payload.get("phase_root") != PHASE_ROOT.as_posix()
        or payload.get("resolved_output_root") != root.as_posix()
        or marker.read_bytes() != canonical_bytes(payload) + b"\n"
    ):
        raise B4GExecutionError("CUSTOM_OUTPUT_ROOT_MARKER_INVALID")
    return root


def _require_formal_execution_source_freeze_paths(
    output_root: Path,
    terminal_path: Path,
) -> None:
    """For formal credit, bind the source-freeze chain to its fixed local paths."""

    root = Path(output_root).resolve()
    if root != PHASE_ROOT.resolve():
        return
    expected_terminal = (
        PHASE_ROOT / _FORMAL_EXECUTION_SOURCE_FREEZE_TERMINAL_RELATIVE_PATH
    )
    expected_gate = (
        PHASE_ROOT / _FORMAL_EXECUTION_SOURCE_FREEZE_GATE_RELATIVE_PATH
    )
    expected_manifest = (
        PHASE_ROOT / _FORMAL_EXECUTION_SOURCE_MANIFEST_RELATIVE_PATH
    )
    terminal_nominal = Path(os.path.abspath(terminal_path))
    expected_terminal_nominal = Path(os.path.abspath(expected_terminal))
    if terminal_nominal != expected_terminal_nominal:
        raise B4GExecutionError(
            "FORMAL_CAMPAIGN_EXECUTION_SOURCE_FREEZE_TERMINAL_PATH_NOT_FIXED"
        )
    try:
        terminal = require_plain_file_under_root(
            terminal_nominal, PROJECT_ROOT,
            label="FORMAL_CAMPAIGN_EXECUTION_SOURCE_FREEZE_TERMINAL",
        )
    except SourceGuardError as error:
        raise B4GExecutionError(str(error)) from error

    def resolved_record_path(row: Mapping[str, Any], local_root: Path) -> Path:
        declared = Path(str(row.get("path", "")))
        if declared.is_absolute():
            return declared.resolve()
        project_candidate = (PROJECT_ROOT / declared).resolve()
        if project_candidate.is_file():
            return project_candidate
        return (local_root / declared).resolve()

    terminal_payload = read_json(terminal)
    terminal_rows = terminal_payload.get("records", [])
    if not isinstance(terminal_rows, list) or len(terminal_rows) != 1:
        raise B4GExecutionError(
            "FORMAL_CAMPAIGN_EXECUTION_SOURCE_FREEZE_TERMINAL_RECORD_SET"
        )
    gate_nominal = resolved_record_path(terminal_rows[0], terminal.parent)
    if Path(os.path.abspath(gate_nominal)) != Path(os.path.abspath(expected_gate)):
        raise B4GExecutionError(
            "FORMAL_CAMPAIGN_EXECUTION_SOURCE_FREEZE_GATE_PATH_NOT_FIXED"
        )
    try:
        gate = require_plain_file_under_root(
            expected_gate, PROJECT_ROOT,
            label="FORMAL_CAMPAIGN_EXECUTION_SOURCE_FREEZE_GATE",
        )
    except SourceGuardError as error:
        raise B4GExecutionError(str(error)) from error
    gate_payload = read_json(gate)
    manifest_record = gate_payload.get("execution_source_manifest")
    if not isinstance(manifest_record, Mapping):
        raise B4GExecutionError(
            "FORMAL_CAMPAIGN_EXECUTION_SOURCE_FREEZE_MANIFEST_RECORD_MISSING"
        )
    manifest_nominal = resolved_record_path(manifest_record, gate.parent)
    if Path(os.path.abspath(manifest_nominal)) != Path(os.path.abspath(expected_manifest)):
        raise B4GExecutionError(
            "FORMAL_CAMPAIGN_EXECUTION_SOURCE_MANIFEST_PATH_NOT_FIXED"
        )
    try:
        manifest = require_plain_file_under_root(
            expected_manifest, PROJECT_ROOT,
            label="FORMAL_CAMPAIGN_EXECUTION_SOURCE_MANIFEST",
        )
    except SourceGuardError as error:
        raise B4GExecutionError(str(error)) from error
    for path in (terminal, gate, manifest):
        try:
            path.relative_to(PROJECT_ROOT)
        except ValueError as error:
            raise B4GExecutionError(
                f"FORMAL_CAMPAIGN_EXECUTION_SOURCE_FREEZE_OUTSIDE_PROJECT:{path}"
            ) from error


def _remove_stale_final_allowlist(
    root: Path,
    *,
    unlink_fn: Callable[[Path], None] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Attempt the consumer-first allowlist completely, unlinking links only."""

    removed: list[dict[str, Any]] = []
    failures: list[str] = []
    unlink = (lambda path: path.unlink()) if unlink_fn is None else unlink_fn
    for relative in _STALE_FINAL_RELATIVE_PATHS:
        try:
            relative_path = Path(relative)
            if relative_path.is_absolute() or any(
                part in {"", ".", ".."} for part in relative_path.parts
            ):
                raise B4GExecutionError(
                    f"STALE_FINAL_RELATIVE_PATH_INVALID:{relative}"
                )
            target = root.joinpath(*relative_path.parts)
            parent = root
            parent_missing = False
            for part in relative_path.parts[:-1]:
                parent = parent / part
                if not os.path.lexists(parent):
                    parent_missing = True
                    break
                if _is_managed_link_or_reparse(parent) or not parent.is_dir():
                    raise B4GExecutionError(
                        f"STALE_FINAL_PARENT_LINK_REPARSE_OR_NONDIR:{relative}"
                    )
            if parent_missing:
                continue
            if not os.path.lexists(target):
                continue
            if _is_managed_link_or_reparse(target):
                record = {
                    "path": relative,
                    "bytes": target.lstat().st_size,
                    "sha256": None,
                    "object_type": (
                        "SYMLINK" if target.is_symlink() else "REPARSE_POINT"
                    ),
                }
            elif target.is_file():
                record = {
                    "path": relative,
                    "bytes": target.stat().st_size,
                    "sha256": sha256_file(target),
                    "object_type": "REGULAR_FILE",
                }
            else:
                raise B4GExecutionError(
                    f"STALE_FINAL_NOT_FILE_OR_SYMLINK:{relative}"
                )
            unlink(target)
            removed.append(record)
        except BaseException as error:
            failures.append(f"{relative}:{type(error).__name__}:{error}")
    return removed, failures


def invalidate_output_root(
    output_root: Path,
    failure: BaseException,
    *,
    _unlink_fn: Callable[[Path], None] | None = None,
) -> dict[str, Any]:
    """Remove only exact stale final artifacts under a validated output root."""

    root = _validated_output_root(output_root)
    _require_managed_output_directory(
        root / "results", root, create=True,
    )
    removed, cleanup_failures = _remove_stale_final_allowlist(
        root, unlink_fn=_unlink_fn,
    )
    receipt = {
        "schema": "SIM13_V4B4G_EXECUTION_INVALIDATED_V1",
        "active": True,
        "failure_type": type(failure).__name__,
        "failure": str(failure),
        "stale_final_artifacts_removed": removed,
        "stale_final_cleanup_failures": cleanup_failures,
        "raw_case_and_diagnostic_evidence_preserved": True,
        "cleanup_scope": "EXACT_ALLOWLIST_UNDER_VALIDATED_OUTPUT_ROOT_ONLY",
    }
    atomic_write_json(root / "results" / "SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json", receipt)
    if cleanup_failures:
        raise B4GExecutionError(
            "STALE_FINAL_CLEANUP_INCOMPLETE:" + "|".join(cleanup_failures)
        )
    return receipt


def _supersede_prior_final_credit(
    output_root: Path,
    *,
    _unlink_fn: Callable[[Path], None] | None = None,
) -> dict[str, Any]:
    """Invalidate only the exact prior final/audited allowlist before slot writes."""

    root = _validated_output_root(output_root)
    _require_managed_output_directory(
        root / "results", root, create=True,
    )
    removed, cleanup_failures = _remove_stale_final_allowlist(
        root, unlink_fn=_unlink_fn,
    )
    receipt = {
        "schema": "SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1",
        "active": True,
        "preflight_complete": True,
        "before_first_campaign_shard": True,
        "exact_allowlist": list(_STALE_FINAL_RELATIVE_PATHS),
        "prior_final_artifacts_removed": removed,
        "prior_final_cleanup_failures": cleanup_failures,
        "raw_case_and_diagnostic_evidence_preserved": True,
        "cleanup_scope": "EXACT_ALLOWLIST_UNDER_VALIDATED_OUTPUT_ROOT_ONLY",
        "replacement_campaign_summary": None,
    }
    atomic_write_json(root / _SUPERSESSION_RECEIPT_RELATIVE_PATH, receipt)
    if cleanup_failures:
        raise B4GExecutionError(
            "SUPERSESSION_STALE_FINAL_CLEANUP_INCOMPLETE:"
            + "|".join(cleanup_failures)
        )
    return receipt


def _mark_supersession_resolved(
    output_root: Path,
    campaign_summary_path: Path,
) -> None:
    path = output_root / _SUPERSESSION_RECEIPT_RELATIVE_PATH
    if not path.is_file():
        raise B4GExecutionError("SUPERSESSION_RECEIPT_MISSING_AT_SUCCESS")
    payload = read_json(path)
    if (
        payload.get("schema")
        != "SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1"
        or payload.get("active") is not True
    ):
        raise B4GExecutionError("SUPERSESSION_RECEIPT_INVALID_AT_SUCCESS")
    payload.update({
        "active": False,
        "replacement_campaign_summary": {
            "path": display_path(campaign_summary_path, PROJECT_ROOT),
            "bytes": campaign_summary_path.stat().st_size,
            "sha256": sha256_file(campaign_summary_path),
        },
    })
    atomic_write_json(path, payload)


def _case_stem(slot: Mapping[str, Any]) -> str:
    safe = "".join(character if character.isalnum() else "_" for character in str(slot["case_id"]))
    return f"{int(slot['slot_index']):03d}__{safe}"


def _case_paths(raw_root: Path, slot: Mapping[str, Any]) -> tuple[Path, Path]:
    stem = _case_stem(slot)
    return raw_root / f"{stem}.json", raw_root / f"{stem}.npz"


def _require_plain_resume_shard_file(path: Path) -> bool:
    """Return whether a lexical shard exists, rejecting every link/reparse form."""

    candidate = Path(os.path.abspath(path))
    if not os.path.lexists(candidate):
        return False
    if _is_managed_link_or_reparse(candidate) or not candidate.is_file():
        raise B4GExecutionError(
            f"RESUME_SHARD_NOT_PLAIN_REGULAR_FILE:{candidate}"
        )
    return True


def _verify_raw_case_inventory(
    raw_root: Path,
    schedule: Mapping[str, Any],
    ordered_metadata: Iterable[Mapping[str, Any]],
    *,
    phase: str,
) -> dict[str, Any]:
    """Require the raw directory to contain exactly 144 JSONs plus executed NPZs."""

    slots = list(schedule["slots"])
    records = list(ordered_metadata)
    if len(slots) != 144 or len(records) != 144:
        raise B4GExecutionError(f"RAW_CASE_INVENTORY_NOT_144:{phase}")
    expected_json: set[str] = set()
    expected_npz: set[str] = set()
    for index, (slot, metadata) in enumerate(zip(slots, records, strict=True)):
        metadata_path, npz_path = _case_paths(raw_root, slot)
        expected_json.add(metadata_path.name)
        if (
            metadata.get("slot_index") != index
            or metadata.get("case_id") != slot.get("case_id")
            or metadata.get("registered_slot") != slot
        ):
            raise B4GExecutionError(f"RAW_CASE_INVENTORY_METADATA_SLOT_MISMATCH:{phase}:{index}")
        status = metadata.get("execution_status")
        if status == "EXECUTED_FRESH_REGISTERED_SLOT":
            expected_npz.add(npz_path.name)
        elif status != "NOT_EVALUATED_NO_A1_SUCCESS":
            raise B4GExecutionError(f"RAW_CASE_INVENTORY_STATUS_INVALID:{phase}:{index}")
    expected = expected_json | expected_npz
    entries = list(raw_root.iterdir())
    for entry in entries:
        if _is_managed_link_or_reparse(entry) or not entry.is_file():
            raise B4GExecutionError(
                f"RAW_CASE_INVENTORY_NON_PLAIN_FILE:{phase}:{entry.name}"
            )
    actual = {entry.name for entry in entries}
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise B4GExecutionError(
            f"RAW_CASE_INVENTORY_EXACT_SET_MISMATCH:{phase}:"
            f"MISSING={missing}:EXTRA={extra}"
        )
    payload = {
        "phase": phase,
        "registered_json_count": len(expected_json),
        "executed_npz_count": len(expected_npz),
        "exact_file_count": len(expected),
        "filenames": sorted(expected),
    }
    payload["inventory_sha256"] = canonical_sha256(payload)
    return payload


def _binding(path: Path) -> dict[str, Any]:
    target = Path(path).resolve()
    return {
        "path": display_path(target, PROJECT_ROOT),
        "bytes": target.stat().st_size,
        "sha256": sha256_file(target),
    }


def _resolve_published_path(declared: str) -> Path:
    value = Path(str(declared))
    return value.resolve() if value.is_absolute() else (PROJECT_ROOT / value).resolve()


def _a0_parent_trace_arrays(active: Any) -> dict[str, np.ndarray]:
    coordinates = np.asarray(active.service_joint_coordinates_mixed, dtype="<f8")
    eta = np.asarray(active.eta_mixed, dtype="<f8")
    return {
        "time_s": np.asarray(active.time_s, dtype="<f8"),
        "service_position_m": np.asarray(active.service_position_m, dtype="<f8"),
        "service_quaternion_wxyz": np.asarray(active.service_quaternion_wxyz, dtype="<f8"),
        "R_joint_coordinates_rad": coordinates[:, 0:6],
        "P_joint_coordinates_m": coordinates[:, 6:8],
        "base_linear_m_s": eta[:, 0:3],
        "base_angular_rad_s": eta[:, 3:6],
        "R_joint_rad_s": eta[:, 6:12],
        "P_joint_m_s": eta[:, 12:14],
        "left_gap_m": np.asarray(active.left_gap_m, dtype="<f8"),
        "right_gap_m": np.asarray(active.right_gap_m, dtype="<f8"),
        "left_gap_rate_m_s": np.asarray(active.left_gap_rate_m_s, dtype="<f8"),
        "right_gap_rate_m_s": np.asarray(active.right_gap_rate_m_s, dtype="<f8"),
    }


def _validate_a0_parent_trace_arrays(
    arrays: Mapping[str, np.ndarray],
    *,
    expected_payload_sha256: str | None = None,
) -> dict[str, Any]:
    if set(arrays) != set(A0_PARENT_TRACE_ARRAYS):
        raise B4GExecutionError("A0_PARENT_TRACE_EXACT_ARRAY_SET_MISMATCH")
    normalized = {name: np.asarray(value) for name, value in arrays.items()}
    for name, value in normalized.items():
        if value.dtype.str != "<f8":
            raise B4GExecutionError(f"A0_PARENT_TRACE_DTYPE_MISMATCH:{name}:{value.dtype.str}")
        if not np.all(np.isfinite(value)):
            raise B4GExecutionError(f"A0_PARENT_TRACE_NONFINITE:{name}")
    n = normalized["time_s"].shape[0]
    if n < 2:
        raise B4GExecutionError("A0_PARENT_TRACE_TOO_SHORT")
    shapes = {
        "time_s": (n,),
        "service_position_m": (n, 3),
        "service_quaternion_wxyz": (n, 4),
        "R_joint_coordinates_rad": (n, 6),
        "P_joint_coordinates_m": (n, 2),
        "base_linear_m_s": (n, 3),
        "base_angular_rad_s": (n, 3),
        "R_joint_rad_s": (n, 6),
        "P_joint_m_s": (n, 2),
        "left_gap_m": (n,),
        "right_gap_m": (n,),
        "left_gap_rate_m_s": (n,),
        "right_gap_rate_m_s": (n,),
    }
    for name, expected_shape in shapes.items():
        if normalized[name].shape != expected_shape:
            raise B4GExecutionError(
                f"A0_PARENT_TRACE_NATIVE_SHAPE_MISMATCH:{name}:"
                f"{normalized[name].shape}:{expected_shape}"
            )
    time_s = normalized["time_s"]
    if not np.all(np.diff(time_s) > 0.0):
        raise B4GExecutionError("A0_PARENT_TRACE_TIME_NOT_STRICTLY_INCREASING")
    tolerance = float(forced.b4e.TIME_INTERVAL_MERGE_TOLERANCE_S)
    if float(time_s[-1]) > 0.08 + tolerance or abs(float(time_s[-1]) - 0.08) > tolerance:
        raise B4GExecutionError("A0_PARENT_TRACE_NOT_ABSOLUTE_T_LE_0P08_GRID")
    payload_sha = array_payload_sha256(normalized)
    if expected_payload_sha256 is not None and payload_sha != str(expected_payload_sha256):
        raise B4GExecutionError("A0_PARENT_TRACE_NUMERIC_PAYLOAD_SHA256_MISMATCH")
    return {
        "pass": True,
        "sample_count": n,
        "numeric_payload_sha256": payload_sha,
        "absolute_end_time_s": float(time_s[-1]),
    }


def _load_b4e_active_trace_oracle() -> tuple[dict[str, Any], dict[str, Any]]:
    path, expected_bytes, expected_sha256 = _B4E_ACTIVE_TRACES_BINDING
    manifest_path, manifest_bytes, manifest_sha256 = _B4E_EVIDENCE_MANIFEST_BINDING
    if (
        not manifest_path.is_file()
        or manifest_path.stat().st_size != manifest_bytes
        or sha256_file(manifest_path) != manifest_sha256
    ):
        raise B4GExecutionError("A0_PARENT_B4E_EVIDENCE_MANIFEST_DRIFT")
    parent_manifest = read_json(manifest_path)
    records = [
        record for record in parent_manifest.get("files", [])
        if record.get("path") == "evidence/SIM13_V4B4E_ACTIVE_TRACES_V1.json"
    ]
    if (
        parent_manifest.get("schema") != "SIM13_V4B4E_EVIDENCE_MANIFEST_V1"
        or parent_manifest.get("self_excluded") is not True
        or len(records) != 1
        or records[0].get("bytes") != expected_bytes
        or records[0].get("sha256") != expected_sha256
        or Path(str(records[0].get("path"))).name != path.name
    ):
        raise B4GExecutionError("A0_PARENT_B4E_ACTIVE_TRACES_MANIFEST_RECORD_DRIFT")
    if (
        not path.is_file()
        or path.stat().st_size != expected_bytes
        or sha256_file(path) != expected_sha256
    ):
        raise B4GExecutionError("A0_PARENT_B4E_ACTIVE_TRACES_ORACLE_DRIFT")
    payload = read_json(path)
    expected_runs = [lane.lower() for lane in _A0_LANE_DEFINITION]
    if (
        payload.get("schema") != "SIM13_V4B4E_ACTIVE_TRACES_V1"
        or not isinstance(payload.get("runs"), dict)
        or list(payload["runs"]) != expected_runs
    ):
        raise B4GExecutionError("A0_PARENT_B4E_ACTIVE_TRACES_ORACLE_SCHEMA_MISMATCH")
    return payload, _binding(path)


def _a0_parent_oracle_arrays(
    lane_id: str,
    active_oracle: Mapping[str, Any],
) -> dict[str, np.ndarray]:
    row = active_oracle["runs"].get(str(lane_id).lower())
    if not isinstance(row, dict):
        raise B4GExecutionError(f"A0_PARENT_B4E_ACTIVE_TRACE_LANE_MISSING:{lane_id}")
    expected_method, expected_step_s = _A0_LANE_DEFINITION[lane_id]
    trace = row.get("trace")
    if (
        row.get("run_id") != str(lane_id).lower()
        or row.get("method") != expected_method
        or row.get("step_s") != expected_step_s
        or row.get("active_end_time_s") != 0.08
        or not isinstance(trace, dict)
    ):
        raise B4GExecutionError(f"A0_PARENT_B4E_ACTIVE_TRACE_IDENTITY_MISMATCH:{lane_id}")
    coordinates = np.asarray(trace["service_joint_coordinates_mixed"], dtype="<f8")
    eta = np.asarray(trace["eta_mixed"], dtype="<f8")
    arrays = {
        "time_s": np.asarray(trace["time_s"], dtype="<f8"),
        "service_position_m": np.asarray(trace["service_position_m"], dtype="<f8"),
        "service_quaternion_wxyz": np.asarray(
            trace["service_quaternion_wxyz"], dtype="<f8",
        ),
        "R_joint_coordinates_rad": coordinates[:, 0:6],
        "P_joint_coordinates_m": coordinates[:, 6:8],
        "base_linear_m_s": eta[:, 0:3],
        "base_angular_rad_s": eta[:, 3:6],
        "R_joint_rad_s": eta[:, 6:12],
        "P_joint_m_s": eta[:, 12:14],
        "left_gap_m": np.asarray(trace["left_gap_m"], dtype="<f8"),
        "right_gap_m": np.asarray(trace["right_gap_m"], dtype="<f8"),
        "left_gap_rate_m_s": np.asarray(trace["left_gap_rate_m_s"], dtype="<f8"),
        "right_gap_rate_m_s": np.asarray(trace["right_gap_rate_m_s"], dtype="<f8"),
    }
    _validate_a0_parent_trace_arrays(arrays)
    return arrays


def _assert_a0_parent_matches_oracle(
    lane_id: str,
    arrays: Mapping[str, np.ndarray],
    oracle_arrays: Mapping[str, np.ndarray],
) -> None:
    if set(arrays) != set(oracle_arrays):
        raise B4GExecutionError(f"A0_PARENT_ORACLE_ARRAY_SET_MISMATCH:{lane_id}")
    for name in sorted(oracle_arrays):
        actual = np.asarray(arrays[name])
        expected = np.asarray(oracle_arrays[name])
        if (
            actual.dtype.str != expected.dtype.str
            or actual.shape != expected.shape
            or not np.array_equal(actual, expected)
        ):
            raise B4GExecutionError(
                f"A0_PARENT_ORACLE_ARRAY_NOT_EXACT:{lane_id}:{name}"
            )


def _a0_parent_source_bindings(
    contracts: Mapping[str, Mapping[str, Any]],
    interchange: Mapping[str, Any],
) -> dict[str, str]:
    by_id = {row["id"]: row for row in contracts["bindings"]["sources"]}
    actual = {
        "b4e_solver_sha256": str(by_id["b4e_solver"]["sha256"]),
        "b4e_run_spec_sha256": str(by_id["b4e_run_spec"]["sha256"]),
        "b4e_audited_gate_sha256": str(by_id["b4e_audited_gate"]["sha256"]),
        "b4e_terminal_sha256": str(by_id["b4e_terminal"]["sha256"]),
    }
    if actual != interchange.get("source_bindings_required"):
        raise B4GExecutionError("A0_PARENT_TRACE_SOURCE_BINDING_CONTRACT_MISMATCH")
    return actual


def _load_fixed_b4e_parent_provenance() -> dict[str, dict[str, Any]]:
    """Read the two frozen B4E provenance objects under their exact bindings."""

    loaded: dict[str, dict[str, Any]] = {}
    for name, (path, expected_bytes, expected_sha256) in _B4E_PROVENANCE_FILES.items():
        if (
            not path.is_file()
            or path.stat().st_size != int(expected_bytes)
            or sha256_file(path) != str(expected_sha256)
        ):
            raise B4GExecutionError(f"A0_PARENT_B4E_{name.upper()}_PROVENANCE_DRIFT")
        loaded[name] = read_json(path)
    return loaded


def _expected_a0_parent_event_provenance(
    lane_id: str,
    method: str,
    step_s: float,
    *,
    fixed: Mapping[str, Mapping[str, Any]] | None = None,
    event: Mapping[str, Any] | None = None,
    acquisition: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate and bind one fresh A0 event/acquisition to the fixed ledgers."""

    expected_lane = _A0_LANE_DEFINITION.get(str(lane_id))
    if expected_lane != (str(method), float(step_s)):
        raise B4GExecutionError(f"A0_PARENT_TRACE_LANE_METHOD_STEP_MISMATCH:{lane_id}")
    provenance = _load_fixed_b4e_parent_provenance() if fixed is None else fixed
    candidates = [
        row for row in provenance["events"].get("runs", [])
        if row.get("method") == method and row.get("step_s") == step_s
    ]
    if len(candidates) != 1:
        raise B4GExecutionError(f"A0_PARENT_B4E_EVENT_TEMPLATE_NOT_UNIQUE:{lane_id}")
    event_template = candidates[0]
    template_run_id = str(event_template.get("run_id"))
    if template_run_id.upper() != str(lane_id).upper():
        raise B4GExecutionError(f"A0_PARENT_B4E_EVENT_TEMPLATE_LANE_MISMATCH:{lane_id}")
    acquisition_template = provenance["acquisitions"].get("runs", {}).get(
        template_run_id,
    )
    if not isinstance(acquisition_template, dict):
        raise B4GExecutionError(f"A0_PARENT_B4E_ACQUISITION_TEMPLATE_MISSING:{lane_id}")
    if acquisition_template.get("acquisition_time_s") != event_template.get("time_s"):
        raise B4GExecutionError(f"A0_PARENT_B4E_ACQUISITION_TIME_MISMATCH:{lane_id}")
    parent_case_id = f"B4G_A0_PARENT_REFERENCE__{lane_id}"
    if (event is None) != (acquisition is None):
        raise B4GExecutionError(
            f"A0_PARENT_EVENT_ACQUISITION_PAIR_REQUIRED:{lane_id}"
        )
    if event is None:
        fresh_event = dict(event_template)
        fresh_event.update({
            "run_id": parent_case_id,
            "source": _FRESH_B3_EVENT_SOURCE,
        })
        fresh_acquisition = {
            key: value for key, value in acquisition_template.items()
            if key != "matrices"
        }
        fresh_acquisition["run_id"] = parent_case_id
    else:
        fresh_event = dict(event)
        fresh_event["run_id"] = parent_case_id
        fresh_acquisition = dict(acquisition)
        fresh_acquisition["run_id"] = parent_case_id
    try:
        comparison_audit = _compare_fresh_b4e_to_frozen_template(
            lane_id=lane_id,
            case_id=parent_case_id,
            event=fresh_event,
            acquisition=fresh_acquisition,
            loaded=provenance,
        )
    except ValueError as error:
        raise B4GExecutionError(
            f"A0_PARENT_FRESH_TEMPLATE_COMPARISON_FAILED:{lane_id}:{error}"
        ) from error
    certificate_payload = {
        "lane_id": lane_id,
        "case_id": parent_case_id,
        "event": fresh_event,
        "acquisition": fresh_acquisition,
    }
    return {
        "acquisition_time_s": float(fresh_event["time_s"]),
        "acquisition_certificate_payload": certificate_payload,
        "event_certificate_sha256": canonical_sha256(certificate_payload),
        "fixed_template_comparison_audit": comparison_audit,
    }


def _write_fresh_a0_parent_reference_traces(
    *,
    output_root: Path,
    contracts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Recompute six independent B3->B4E A0 reference traces and publish raw NPZs."""

    interchange = read_json(A0_PARENT_INTERCHANGE_PATH)
    if interchange.get("schema") != "SIM13_V4B4G_A0_PARENT_TRACE_INTERCHANGE_V1":
        raise B4GExecutionError("A0_PARENT_TRACE_INTERCHANGE_SCHEMA_MISMATCH")
    if set(interchange.get("npz_arrays", {})) != set(A0_PARENT_TRACE_ARRAYS):
        raise B4GExecutionError("A0_PARENT_TRACE_INTERCHANGE_ARRAY_SET_MISMATCH")
    source_bindings = _a0_parent_source_bindings(contracts, interchange)
    active_oracle, active_oracle_binding = _load_b4e_active_trace_oracle()
    trace_root = output_root / "evidence" / "a0_parent_reference_traces"
    trace_root.mkdir(parents=True, exist_ok=True)
    traces: list[dict[str, Any]] = []
    schedule = contracts["schedule"]
    fixed_b4e = _load_fixed_b4e_parent_provenance()
    for lane_id in schedule["lane_order"]:
        lane_slot = next(
            slot for slot in schedule["slots"]
            if slot["lane_id"] == lane_id and slot["arm"] == "A0"
            and slot["case_id"].endswith("__PRE")
        )
        method = str(lane_slot["method"])
        step_s = float(lane_slot["step_s"])
        event = forced.b4e.rerun_b3_to_event(
            f"B4G_A0_PARENT_REFERENCE__{lane_id}", method, step_s,
        )
        model = forced.b4e.BranchedGripperServiceModel()
        acquisition = forced.b4e.acquisition_projection(model, event)
        active = forced.b4e.propagate_active(
            model,
            event,
            acquisition,
            method=method,
            step_s=step_s,
            end_time_s=0.08,
        )
        arrays = _a0_parent_trace_arrays(active)
        audit = _validate_a0_parent_trace_arrays(arrays)
        _assert_a0_parent_matches_oracle(
            lane_id, arrays, _a0_parent_oracle_arrays(lane_id, active_oracle),
        )
        npz_path = trace_root / f"{lane_id}.npz"
        receipt = atomic_write_npz(npz_path, arrays)
        event_json = forced.b4e.event_to_json(event)
        acquisition_json = forced.b4e.acquisition_to_json(
            acquisition, include_matrices=False,
        )
        expected_event_provenance = _expected_a0_parent_event_provenance(
            lane_id, method, step_s, fixed=fixed_b4e,
            event=event_json, acquisition=acquisition_json,
        )
        event_certificate = expected_event_provenance[
            "event_certificate_sha256"
        ]
        if float(event.time_s) != expected_event_provenance["acquisition_time_s"]:
            raise B4GExecutionError(
                f"A0_PARENT_FRESH_EVENT_OR_ACQUISITION_CERTIFICATE_MISMATCH:{lane_id}"
            )
        traces.append({
            "lane_id": lane_id,
            "method": method,
            "step_s": step_s,
            "fresh_b3_reconstruction": True,
            "fresh_b4e_reference_propagation": True,
            "acquisition_time_s": float(event.time_s),
            "common_absolute_end_time_s": 0.08,
            "acquisition_certificate_payload": expected_event_provenance[
                "acquisition_certificate_payload"
            ],
            "event_certificate_sha256": event_certificate,
            "fixed_template_comparison_audit": expected_event_provenance[
                "fixed_template_comparison_audit"
            ],
            "npz_path": display_path(npz_path, PROJECT_ROOT),
            "npz_bytes": receipt["bytes"],
            "npz_sha256": receipt["sha256"],
            "numeric_payload_sha256": audit["numeric_payload_sha256"],
        })
    manifest = {
        "schema": "SIM13_V4B4G_A0_PARENT_REFERENCE_TRACES_V1",
        "fresh_generation": True,
        "source_bindings": source_bindings,
        "b4e_active_traces_binding": active_oracle_binding,
        "interchange_contract": _binding(A0_PARENT_INTERCHANGE_PATH),
        "trace_count": len(traces),
        "traces": traces,
        "claim_boundary": interchange["claim_boundary"],
    }
    manifest_path = output_root / str(interchange["manifest_path"])
    atomic_write_json(manifest_path, manifest)
    return _verify_a0_parent_trace_bundle(_binding(manifest_path))


def _verify_a0_parent_trace_bundle(manifest_binding: Mapping[str, Any]) -> dict[str, Any]:
    manifest_path = _resolve_published_path(str(manifest_binding["path"]))
    if (
        not manifest_path.is_file()
        or manifest_path.stat().st_size != int(manifest_binding["bytes"])
        or sha256_file(manifest_path) != str(manifest_binding["sha256"])
    ):
        raise B4GExecutionError("A0_PARENT_TRACE_MANIFEST_BINDING_DRIFT")
    manifest = read_json(manifest_path)
    interchange = read_json(A0_PARENT_INTERCHANGE_PATH)
    active_oracle, active_oracle_binding = _load_b4e_active_trace_oracle()
    required_manifest_fields = set(interchange.get("manifest_required_fields", []))
    if (
        manifest.get("schema") != "SIM13_V4B4G_A0_PARENT_REFERENCE_TRACES_V1"
        or manifest.get("fresh_generation") is not True
        or manifest.get("trace_count") != 6
        or len(manifest.get("traces", [])) != 6
        or not required_manifest_fields.issubset(manifest)
        or manifest.get("source_bindings") != interchange.get("source_bindings_required")
        or manifest.get("b4e_active_traces_binding") != active_oracle_binding
        or manifest.get("claim_boundary") != interchange.get("claim_boundary")
        or manifest.get("interchange_contract") != _binding(A0_PARENT_INTERCHANGE_PATH)
    ):
        raise B4GExecutionError("A0_PARENT_TRACE_MANIFEST_SCHEMA_OR_COUNT_MISMATCH")
    required_trace_fields = set(interchange.get("trace_required_fields", [])) | {
        "acquisition_certificate_payload",
        "fixed_template_comparison_audit",
    }
    observed_lanes: list[str] = []
    trace_bindings: list[dict[str, Any]] = []
    fixed_b4e = _load_fixed_b4e_parent_provenance()
    for trace in manifest["traces"]:
        if set(trace) != required_trace_fields:
            raise B4GExecutionError("A0_PARENT_TRACE_REQUIRED_FIELD_MISSING")
        observed_lanes.append(str(trace.get("lane_id")))
        lane_id = str(trace.get("lane_id"))
        if lane_id not in _A0_LANE_DEFINITION:
            raise B4GExecutionError(f"A0_PARENT_TRACE_UNKNOWN_LANE:{lane_id}")
        expected_method, expected_step_s = _A0_LANE_DEFINITION[lane_id]
        expected_event_provenance = _expected_a0_parent_event_provenance(
            lane_id, expected_method, expected_step_s, fixed=fixed_b4e,
            event=trace.get("acquisition_certificate_payload", {}).get("event"),
            acquisition=trace.get("acquisition_certificate_payload", {}).get(
                "acquisition"
            ),
        )
        if (
            trace.get("method") != expected_method
            or trace.get("step_s") != expected_step_s
            or trace.get("acquisition_time_s")
            != expected_event_provenance["acquisition_time_s"]
            or trace.get("event_certificate_sha256")
            != expected_event_provenance["event_certificate_sha256"]
            or trace.get("acquisition_certificate_payload")
            != expected_event_provenance["acquisition_certificate_payload"]
            or trace.get("fixed_template_comparison_audit")
            != expected_event_provenance["fixed_template_comparison_audit"]
            or trace.get("fresh_b3_reconstruction") is not True
            or trace.get("fresh_b4e_reference_propagation") is not True
            or float(trace.get("common_absolute_end_time_s", -1.0)) != 0.08
        ):
            raise B4GExecutionError("A0_PARENT_TRACE_PROVENANCE_OR_ARRAY_INVENTORY_MISMATCH")
        npz_path = _resolve_published_path(str(trace["npz_path"]))
        verify_npz(
            npz_path,
            size=int(trace["npz_bytes"]),
            sha256=str(trace["npz_sha256"]),
            arrays=list(A0_PARENT_TRACE_ARRAYS),
        )
        with np.load(npz_path, allow_pickle=False) as archive:
            arrays = {name: np.asarray(archive[name]) for name in archive.files}
        audit = _validate_a0_parent_trace_arrays(
            arrays,
            expected_payload_sha256=str(trace["numeric_payload_sha256"]),
        )
        _assert_a0_parent_matches_oracle(
            lane_id, arrays, _a0_parent_oracle_arrays(lane_id, active_oracle),
        )
        trace_bindings.append({
            "lane_id": trace["lane_id"],
            "npz_path": trace["npz_path"],
            "npz_bytes": trace["npz_bytes"],
            "npz_sha256": trace["npz_sha256"],
            "numeric_payload_sha256": trace["numeric_payload_sha256"],
        })
    expected_lanes = list(_A0_LANE_DEFINITION)
    if observed_lanes != expected_lanes:
        raise B4GExecutionError("A0_PARENT_TRACE_LANE_ORDER_MISMATCH")
    return {
        "pass": True,
        "manifest": dict(manifest_binding),
        "manifest_path": manifest_path.resolve().as_posix(),
        "trace_count": 6,
        "b4e_active_traces_binding": active_oracle_binding,
        "trace_bindings": trace_bindings,
        "trace_bindings_sha256": canonical_sha256(trace_bindings),
    }


def _source_hashes(
    identity: Mapping[str, Any],
    schedule: Mapping[str, Any],
    slot: Mapping[str, Any],
    pre_run: Mapping[str, Any],
    *,
    a2_selection_ledger_sha256: str | None = None,
) -> dict[str, Any]:
    return {
        "local_source_inventory_sha256": identity["local_source_inventory_sha256"],
        "contract_bundle_sha256": identity["contract_bundle_sha256"],
        "signed_preregistration_anchor_set_sha256": identity["signed_preregistration_anchor_set_sha256"],
        "registered_slots_sha256": schedule["slots_sha256"],
        "slot_canonical_sha256": canonical_sha256(slot),
        "pre_run_execution_ledger_sha256": pre_run["pre_run_execution_ledger_sha256"],
        "pre_run_protected_snapshot_sha256": pre_run["pre_run_protected_snapshot_sha256"],
        "a0_parent_reference_trace_manifest_sha256": pre_run[
            "a0_parent_reference_trace_manifest_sha256"
        ],
        "runtime_identity_sha256": pre_run["runtime_identity_sha256"],
        "recursive_parent_identity_sha256": pre_run["recursive_parent_identity_sha256"],
        "expected_execution_source_freeze_terminal_sha256": identity[
            "expected_execution_source_freeze_terminal_sha256"
        ],
        "a2_selection_ledger_sha256": a2_selection_ledger_sha256,
    }


def _ensure_exact_json(path: Path, payload: Mapping[str, Any], mismatch: str) -> None:
    if path.exists() and read_json(path) != dict(payload):
        raise B4GExecutionError(mismatch)
    atomic_write_json(path, payload)


def _ensure_runtime_evidence(path: Path, runtime_identity: Mapping[str, Any]) -> dict[str, Any]:
    identity_sha = canonical_sha256(runtime_identity)
    if path.exists():
        existing = read_json(path)
        if (
            existing.get("schema") != "SIM13_V4B4G_RUNTIME_ENVIRONMENT_V1"
            or existing.get("runtime_identity") != dict(runtime_identity)
            or existing.get("runtime_identity_sha256") != identity_sha
        ):
            raise B4GExecutionError("RESUME_RUNTIME_IDENTITY_MISMATCH")
        return existing
    payload = _runtime_record(runtime_identity)
    atomic_write_json(path, payload)
    return payload


def _build_pre_run_execution_ledger(
    contracts: Mapping[str, Mapping[str, Any]],
    identity: Mapping[str, Any],
    recursive: Mapping[str, Any],
    runtime_identity: Mapping[str, Any],
    protected: Mapping[str, Any],
    a0_parent_traces: Mapping[str, Any],
) -> dict[str, Any]:
    discovery, conditional = _registered_execution_plan(contracts["schedule"])
    ordered_execution = discovery + conditional
    slots = [
        {
            "execution_ordinal": index,
            "slot_index": int(slot["slot_index"]),
            "case_id": slot["case_id"],
            "registered_slot": dict(slot),
            "slot_canonical_sha256": canonical_sha256(slot),
            "a2_parent_binding": (
                "BIND_TO_SEPARATE_POST_A1_SELECTION_LEDGER"
                if slot["arm"] == "A2" else "NOT_APPLICABLE"
            ),
        }
        for index, slot in enumerate(ordered_execution)
    ]
    core = {
        "schema": "SIM13_V4B4G_PRE_RUN_EXECUTION_LEDGER_V1",
        "self_excluded": True,
        "local_source_inventory_sha256": identity["local_source_inventory_sha256"],
        "contract_bundle_sha256": identity["contract_bundle_sha256"],
        "signed_preregistration_anchor_set_sha256": identity["signed_preregistration_anchor_set_sha256"],
        "preregistration_source_records_sha256": identity["preregistration_source_records_sha256"],
        "expected_execution_source_freeze_terminal_sha256": identity[
            "expected_execution_source_freeze_terminal_sha256"
        ],
        "recursive_parent_identity_sha256": canonical_sha256(recursive),
        "runtime_identity": dict(runtime_identity),
        "runtime_identity_sha256": canonical_sha256(runtime_identity),
        "protected_snapshot_payload_sha256": protected["snapshot_payload_sha256"],
        "a0_parent_reference_trace_manifest": dict(a0_parent_traces["manifest"]),
        "a0_parent_reference_trace_bindings_sha256": a0_parent_traces[
            "trace_bindings_sha256"
        ],
        "registered_slots_sha256": contracts["schedule"]["slots_sha256"],
        "logical_slot_count": 144,
        "execution_slots": slots,
        "selection_rule": contracts["run_spec"]["selector"],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {**core, "ledger_payload_sha256": canonical_sha256(core)}


def _resolve_metadata_npz(metadata: Mapping[str, Any], expected: Path) -> Path:
    declared = metadata.get("npz_path")
    if declared is None:
        return expected
    path = Path(str(declared))
    return path if path.is_absolute() else PROJECT_ROOT / path


def _safe_orphan_recovery(path: Path, raw_root: Path, reason: str) -> None:
    root = Path(os.path.abspath(raw_root))
    if root.name != "raw_cases" or root.parent.name != "evidence":
        raise B4GExecutionError(f"ORPHAN_RAW_ROOT_NOT_EXACT_MANAGED_PATH:{root}")
    output_root = root.parent.parent
    _require_managed_output_directory(root, output_root, create=False)
    target = Path(os.path.abspath(path))
    if target.parent != root:
        raise B4GExecutionError(f"ORPHAN_PATH_ESCAPED_RAW_ROOT:{target}")
    if not os.path.lexists(target):
        return
    if _is_managed_link_or_reparse(target):
        orphan_bytes = target.lstat().st_size
        orphan_sha256 = None
        object_type = "SYMLINK" if target.is_symlink() else "REPARSE_POINT"
    elif target.is_file():
        orphan_bytes = target.stat().st_size
        orphan_sha256 = sha256_file(target)
        object_type = "REGULAR_FILE"
    else:
        raise B4GExecutionError(f"ORPHAN_TARGET_NOT_FILE_OR_SYMLINK:{target}")
    recovery_root = root.parent / "recovery_receipts"
    _require_managed_output_directory(
        recovery_root, output_root, create=True,
    )
    receipt = {
        "schema": "SIM13_V4B4G_ORPHAN_RECOVERY_RECEIPT_V1",
        "orphan_path": target.name,
        "orphan_bytes": orphan_bytes,
        "orphan_sha256": orphan_sha256,
        "orphan_object_type": object_type,
        "reason": reason,
        "action": "REMOVE_EXACT_ORPHAN_AND_REBUILD_BOTH_SHARD_FILES",
    }
    recovery = recovery_root / f"{target.stem}__{target.suffix[1:]}_orphan.json"
    atomic_write_json(recovery, receipt)
    target.unlink()


def _verify_pre_run_context(pre_run: Mapping[str, Any]) -> None:
    for prefix in ("pre_run_execution_ledger", "pre_run_protected_snapshot"):
        path = Path(str(pre_run[f"{prefix}_path"]))
        if (
            not path.is_file()
            or path.stat().st_size != int(pre_run[f"{prefix}_bytes"])
            or sha256_file(path) != str(pre_run[f"{prefix}_sha256"])
        ):
            raise B4GExecutionError(f"{prefix.upper()}_DRIFT")
    ledger = read_json(Path(str(pre_run["pre_run_execution_ledger_path"])))
    core = {key: value for key, value in ledger.items() if key != "ledger_payload_sha256"}
    if ledger.get("ledger_payload_sha256") != canonical_sha256(core):
        raise B4GExecutionError("PRE_RUN_EXECUTION_LEDGER_SELF_HASH_MISMATCH")
    parent = _verify_a0_parent_trace_bundle({
        "path": pre_run["a0_parent_reference_trace_manifest_path"],
        "bytes": pre_run["a0_parent_reference_trace_manifest_bytes"],
        "sha256": pre_run["a0_parent_reference_trace_manifest_sha256"],
    })
    if (
        parent["trace_bindings_sha256"]
        != pre_run["a0_parent_reference_trace_bindings_sha256"]
    ):
        raise B4GExecutionError("PRE_RUN_A0_PARENT_REFERENCE_TRACE_BINDINGS_DRIFT")


def _load_resumable_case(
    metadata_path: Path,
    npz_path: Path,
    *,
    slot: Mapping[str, Any],
    execution_ordinal: int,
    source_hashes: Mapping[str, Any],
    pre_run: Mapping[str, Any],
    selected_parent: Mapping[str, Any] | None,
    q_ref_n: float | None,
) -> dict[str, Any] | None:
    _verify_pre_run_context(pre_run)
    metadata_lexical = Path(os.path.abspath(metadata_path))
    npz_lexical = Path(os.path.abspath(npz_path))
    if metadata_lexical.parent != npz_lexical.parent:
        raise B4GExecutionError(f"RESUME_SHARD_PARENT_MISMATCH:{slot['case_id']}")
    raw_root = metadata_lexical.parent
    if raw_root.name != "raw_cases" or raw_root.parent.name != "evidence":
        raise B4GExecutionError(f"RESUME_SHARD_PARENT_NOT_MANAGED_RAW_ROOT:{slot['case_id']}")
    _require_managed_output_directory(
        raw_root, raw_root.parent.parent, create=False,
    )
    metadata_exists = _require_plain_resume_shard_file(metadata_lexical)
    npz_exists = _require_plain_resume_shard_file(npz_lexical)
    if not metadata_exists and not npz_exists:
        return None
    if not metadata_exists and npz_exists:
        _safe_orphan_recovery(npz_path, metadata_path.parent, "NPZ_PUBLISHED_BEFORE_METADATA_CRASH")
        return None
    if metadata_exists and not npz_exists:
        try:
            possible_na = read_json(metadata_path)
        except EvidenceIOError:
            possible_na = {}
        if (
            slot["arm"] == "A2"
            and selected_parent is None
            and possible_na.get("execution_status") == "NOT_EVALUATED_NO_A1_SUCCESS"
        ):
            metadata = possible_na
        else:
            _safe_orphan_recovery(metadata_path, metadata_path.parent, "METADATA_PUBLISHED_WITHOUT_NPZ_CRASH")
            return None
    else:
        metadata = read_json(metadata_path)
    exact = bool(
        metadata.get("schema") == "SIM13_V4B4G_CASE_METADATA_V1"
        and metadata.get("slot_index") == slot["slot_index"]
        and metadata.get("case_id") == slot["case_id"]
        and metadata.get("lane_id") == slot["lane_id"]
        and metadata.get("arm") == slot["arm"]
        and metadata.get("execution_ordinal") == execution_ordinal
        and metadata.get("source_hashes") == dict(source_hashes)
        and metadata.get("registered_slot") == dict(slot)
        and metadata.get("event_provenance", {}).get("lane_id") == slot["lane_id"]
    )
    if not exact:
        raise B4GExecutionError(f"RESUME_SLOT_OR_SOURCE_IDENTITY_MISMATCH:{slot['case_id']}")
    try:
        validate_acquisition_certificate_binding(metadata)
    except ValueError as error:
        raise B4GExecutionError(
            f"RESUME_ACQUISITION_CERTIFICATE_INVALID:{slot['case_id']}:{error}"
        ) from error
    if metadata.get("execution_status") == "EXECUTED_FRESH_REGISTERED_SLOT":
        if q_ref_n is None:
            raise B4GExecutionError(f"RESUME_EXECUTED_CASE_QREF_MISSING:{slot['case_id']}")
        actual_npz = _resolve_metadata_npz(metadata, npz_lexical)
        if Path(os.path.abspath(actual_npz)) != npz_lexical:
            raise B4GExecutionError(f"RESUME_NPZ_PATH_MISMATCH:{slot['case_id']}")
        if not _require_plain_resume_shard_file(actual_npz):
            raise B4GExecutionError(f"RESUME_NPZ_MISSING:{slot['case_id']}")
        verify_npz(
            actual_npz,
            size=int(metadata["npz_bytes"]),
            sha256=str(metadata["npz_sha256"]),
            arrays=list(metadata["npz_arrays"]),
        )
        try:
            validate_case_npz_schema(actual_npz, metadata)
        except ValueError as error:
            raise B4GExecutionError(f"RESUME_NPZ_SCHEMA_INVALID:{slot['case_id']}:{error}") from error
        if slot["arm"] == "A2" and selected_parent is None:
            raise B4GExecutionError(f"RESUME_A2_SELECTED_PARENT_MISMATCH:{slot['case_id']}")
        if (
            slot["arm"] == "A2"
            and metadata.get("command_parameters", {}).get("selected_parent_level")
            != dict(selected_parent or {})
        ):
            raise B4GExecutionError(f"RESUME_A2_SELECTED_PARENT_MISMATCH:{slot['case_id']}")
        expected_command = campaign.command_for_slot(
            slot,
            selected_parent=selected_parent if slot["arm"] == "A2" else None,
        )
        expected_parameters: dict[str, Any] = {
            "Q_ref_per_finger_N": float(q_ref_n),
            "only_nonzero_generalized_force_indices_zero_based": [12, 13],
            "left": {
                "alpha": expected_command.left.alpha,
                "delay_s": expected_command.left.delay_s,
                "duration_s": expected_command.left.duration_s,
            },
            "right": {
                "alpha": expected_command.right.alpha,
                "delay_s": expected_command.right.delay_s,
                "duration_s": expected_command.right.duration_s,
            },
            "physical_actuator_force_capacity_N": None,
        }
        if selected_parent is not None:
            expected_parameters["selected_parent_level"] = dict(selected_parent)
        if metadata.get("command_parameters") != expected_parameters:
            raise B4GExecutionError(f"RESUME_REGISTERED_COMMAND_MISMATCH:{slot['case_id']}")
    elif metadata.get("execution_status") == "NOT_EVALUATED_NO_A1_SUCCESS":
        if slot["arm"] != "A2" or selected_parent is not None:
            raise B4GExecutionError(f"RESUME_A2_NA_SELECTED_PARENT_MISMATCH:{slot['case_id']}")
        if metadata.get("command_parameters") != {
            "selected_parent": None,
            "variant_id": slot["variant_id"],
        }:
            raise B4GExecutionError(f"RESUME_A2_NA_COMMAND_MISMATCH:{slot['case_id']}")
        if npz_path.exists() or any(metadata.get(key) is not None for key in ("npz_path", "npz_bytes", "npz_sha256")):
            raise B4GExecutionError(f"NA_A2_HAS_RAW_NPZ:{slot['case_id']}")
    else:
        raise B4GExecutionError(f"RESUME_EXECUTION_STATUS_INVALID:{slot['case_id']}")
    return metadata


def _verify_resumed_case_against_fresh_replay(
    *,
    resumed: Mapping[str, Any],
    npz_path: Path,
    fresh_metadata: Mapping[str, Any],
    fresh_arrays: Mapping[str, np.ndarray],
) -> None:
    """Reject a coordinated JSON/NPZ mutation by replaying the frozen slot."""

    try:
        with np.load(npz_path, allow_pickle=False) as archive:
            if set(archive.files) != set(fresh_arrays):
                raise B4GExecutionError(
                    f"RESUME_FRESH_REPLAY_ARRAY_SET_MISMATCH:{resumed.get('case_id')}"
                )
            for name in sorted(fresh_arrays):
                actual = np.asarray(archive[name])
                expected = np.asarray(fresh_arrays[name])
                if actual.dtype.str != expected.dtype.str:
                    raise B4GExecutionError(
                        f"RESUME_FRESH_REPLAY_DTYPE_MISMATCH:"
                        f"{resumed.get('case_id')}:{name}"
                    )
                if actual.shape != expected.shape:
                    raise B4GExecutionError(
                        f"RESUME_FRESH_REPLAY_SHAPE_MISMATCH:"
                        f"{resumed.get('case_id')}:{name}"
                    )
                if not np.array_equal(actual, expected):
                    raise B4GExecutionError(
                        f"RESUME_FRESH_REPLAY_NUMERIC_MISMATCH:"
                        f"{resumed.get('case_id')}:{name}"
                    )
    except (OSError, ValueError) as error:
        raise B4GExecutionError(
            f"RESUME_FRESH_REPLAY_NPZ_READ_FAILED:{resumed.get('case_id')}"
        ) from error
    expected_metadata = dict(fresh_metadata)
    expected_metadata.update({
        "npz_path": display_path(npz_path, PROJECT_ROOT),
        "npz_bytes": npz_path.stat().st_size,
        "npz_sha256": sha256_file(npz_path),
        "npz_arrays": sorted(fresh_arrays),
    })
    if dict(resumed) != expected_metadata:
        raise B4GExecutionError(
            f"RESUME_FRESH_REPLAY_METADATA_MISMATCH:{resumed.get('case_id')}"
        )


def _fresh_executed_case_candidate(
    *,
    slot: Mapping[str, Any],
    execution_ordinal: int,
    source_hashes: Mapping[str, Any],
    q_ref_n: float,
    selected_parent: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Run one registered slot from a fresh B3 event and derive all evidence."""

    result = campaign.run_registered_slot(
        slot, selected_parent=selected_parent, q_ref_n=q_ref_n,
    )
    comparison = _a0_comparison(result) if slot["arm"] == "A0" else None
    metadata, arrays = executed_case_payload(
        result, slot=slot, execution_ordinal=execution_ordinal,
        q_ref_n=q_ref_n, source_hashes=source_hashes,
        a0_comparison=comparison,
    )
    if selected_parent is not None:
        metadata["command_parameters"]["selected_parent_level"] = dict(
            selected_parent,
        )
    return metadata, arrays


def _sign_aligned_unit_quaternion_geodesic_rows(
    left_wxyz: np.ndarray,
    right_wxyz: np.ndarray,
) -> np.ndarray:
    """Return stable SO(3) geodesics for paired unit-quaternion rows."""

    try:
        left = np.asarray(left_wxyz, dtype=np.float64)
        right = np.asarray(right_wxyz, dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as error:
        raise B4GExecutionError(
            "A0_QUATERNION_GEODESIC_NOT_REAL_NUMERIC"
        ) from error
    if (
        left.ndim != 2
        or right.ndim != 2
        or left.shape[1:] != (4,)
        or right.shape != left.shape
        or left.shape[0] == 0
    ):
        raise B4GExecutionError(
            f"A0_QUATERNION_GEODESIC_SHAPE_MISMATCH:{left.shape}:{right.shape}"
        )
    if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
        raise B4GExecutionError("A0_QUATERNION_GEODESIC_NONFINITE")

    left_norm = np.linalg.norm(left, axis=1)
    right_norm = np.linalg.norm(right, axis=1)
    if (
        np.any(np.abs(left_norm - 1.0) > 1.0e-12)
        or np.any(np.abs(right_norm - 1.0) > 1.0e-12)
    ):
        raise B4GExecutionError("A0_QUATERNION_GEODESIC_NONUNIT")

    left_unit = left / left_norm[:, None]
    right_unit = right / right_norm[:, None]
    dot = np.sum(left_unit * right_unit, axis=1)
    sign = np.where(dot < 0.0, -1.0, 1.0)
    right_aligned = sign[:, None] * right_unit
    theta = 4.0 * np.arctan2(
        np.linalg.norm(left_unit - right_aligned, axis=1),
        np.linalg.norm(left_unit + right_aligned, axis=1),
    )
    if not np.all(np.isfinite(theta)):
        raise B4GExecutionError("A0_QUATERNION_GEODESIC_NONFINITE_RESULT")
    return theta


def _a0_comparison(result: forced.ForcedRunResult) -> dict[str, Any]:
    model = forced.b4e.BranchedGripperServiceModel()
    reference = forced.b4e.propagate_active(
        model, result.event, result.acquisition,
        method=result.method, step_s=result.step_s, end_time_s=0.08,
    )
    # Preserve the parent solver's own fail-closed time-grid and zero-input audit,
    # then publish only the ten frozen interchange channels.  The validator
    # independently recomputes these values from the two raw NPZs.
    native = campaign.a0_replay_comparison(
        result, reference, common_end_time_s=0.08,
    )
    mask = result.time_s <= 0.08 + 1.0e-12
    state = result.state_30[mask]
    quaternion_geodesic_rad = _sign_aligned_unit_quaternion_geodesic_rows(
        state[:, 3:7], reference.service_quaternion_wxyz,
    )
    maxima = {
        "service_position_m": float(np.max(np.abs(
            state[:, 0:3] - reference.service_position_m,
        ))),
        "service_quaternion_geodesic_rad": float(np.max(
            quaternion_geodesic_rad,
        )),
        "R_joint_coordinates_rad": float(np.max(np.abs(
            state[:, 7:13] - reference.service_joint_coordinates_mixed[:, 0:6],
        ))),
        "P_joint_coordinates_m": float(np.max(np.abs(
            state[:, 13:15] - reference.service_joint_coordinates_mixed[:, 6:8],
        ))),
        "base_linear_m_s": float(np.max(np.abs(
            state[:, 15:18] - reference.eta_mixed[:, 0:3],
        ))),
        "base_angular_rad_s": float(np.max(np.abs(
            state[:, 18:21] - reference.eta_mixed[:, 3:6],
        ))),
        "R_joint_rad_s": float(np.max(np.abs(
            state[:, 21:27] - reference.eta_mixed[:, 6:12],
        ))),
        "P_joint_m_s": float(np.max(np.abs(
            state[:, 27:29] - reference.eta_mixed[:, 12:14],
        ))),
        "left_right_gap_m": float(max(
            np.max(np.abs(result.left_gap_m[mask] - reference.left_gap_m)),
            np.max(np.abs(result.right_gap_m[mask] - reference.right_gap_m)),
        )),
        "left_right_gap_rate_m_s": float(max(
            np.max(np.abs(result.left_gap_rate_m_s[mask] - reference.left_gap_rate_m_s)),
            np.max(np.abs(result.right_gap_rate_m_s[mask] - reference.right_gap_rate_m_s)),
        )),
    }
    tolerances = {name: 1.0e-12 for name in maxima}
    per_channel = {
        name: value <= tolerances[name] for name, value in maxima.items()
    }
    q_and_w = bool(native["Q_and_W_exact_zero"])
    return {
        "common_end_time_s": 0.08,
        "sample_count": int(len(state)),
        "channel_maxima": maxima,
        "native_absolute_tolerances": tolerances,
        "per_channel_pass": per_channel,
        "Q_and_W_exact_zero": q_and_w,
        "passed": bool(q_and_w and all(per_channel.values())),
        "fresh_b4e_reference_propagation": True,
        "b4e_reference_terminal_status": reference.terminal_status,
    }


def _publish_executed_case(
    *,
    slot: Mapping[str, Any],
    execution_ordinal: int,
    raw_root: Path,
    source_hashes: Mapping[str, Any],
    q_ref_n: float,
    selected_parent: Mapping[str, Any] | None,
    pre_run: Mapping[str, Any],
) -> dict[str, Any]:
    metadata_path, npz_path = _case_paths(raw_root, slot)
    resumed = _load_resumable_case(
        metadata_path, npz_path, slot=slot, execution_ordinal=execution_ordinal,
        source_hashes=source_hashes, pre_run=pre_run, selected_parent=selected_parent,
        q_ref_n=q_ref_n,
    )
    metadata, arrays = _fresh_executed_case_candidate(
        slot=slot,
        execution_ordinal=execution_ordinal,
        source_hashes=source_hashes,
        q_ref_n=q_ref_n,
        selected_parent=selected_parent,
    )
    if resumed is not None:
        _verify_resumed_case_against_fresh_replay(
            resumed=resumed,
            npz_path=npz_path,
            fresh_metadata=metadata,
            fresh_arrays=arrays,
        )
        return resumed
    receipt = atomic_write_npz(npz_path, arrays)
    metadata.update({
        "npz_path": display_path(npz_path, PROJECT_ROOT),
        "npz_bytes": receipt["bytes"],
        "npz_sha256": receipt["sha256"],
        "npz_arrays": receipt["arrays"],
    })
    atomic_write_json(metadata_path, metadata)
    try:
        validate_case_npz_schema(npz_path, metadata)
    except ValueError as error:
        raise B4GExecutionError(f"PUBLISHED_NPZ_SCHEMA_INVALID:{slot['case_id']}:{error}") from error
    return metadata


def _publish_na_a2(
    *,
    slot: Mapping[str, Any],
    execution_ordinal: int,
    raw_root: Path,
    source_hashes: Mapping[str, Any],
    pre_run: Mapping[str, Any],
) -> dict[str, Any]:
    metadata_path, npz_path = _case_paths(raw_root, slot)
    expected_metadata = not_evaluated_a2_payload(
        slot=slot, execution_ordinal=execution_ordinal, source_hashes=source_hashes,
    )
    resumed = _load_resumable_case(
        metadata_path, npz_path, slot=slot, execution_ordinal=execution_ordinal,
        source_hashes=source_hashes, pre_run=pre_run, selected_parent=None,
        q_ref_n=None,
    )
    if resumed is not None:
        if resumed != expected_metadata:
            raise B4GExecutionError(
                f"RESUME_A2_NA_FRESH_REGENERATION_MISMATCH:{slot['case_id']}"
            )
        return resumed
    atomic_write_json(metadata_path, expected_metadata)
    return expected_metadata


def _registered_execution_plan(schedule: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    slots = list(schedule["slots"])
    lanes = list(schedule["lane_order"])
    discovery: list[dict[str, Any]] = []
    conditional_and_post: list[dict[str, Any]] = []
    for lane in lanes:
        lane_slots = [slot for slot in slots if slot["lane_id"] == lane]
        discovery.extend(lane_slots[:19])
    for lane in lanes:
        lane_slots = [slot for slot in slots if slot["lane_id"] == lane]
        conditional_and_post.extend(lane_slots[19:24])
    if len(discovery) != 114 or len(conditional_and_post) != 30:
        raise B4GExecutionError("REGISTERED_TWO_WAVE_PLAN_COUNT_MISMATCH")
    return discovery, conditional_and_post


def _metadata_by_lane_level(metadata: Iterable[Mapping[str, Any]]) -> dict[tuple[str, float, float], Mapping[str, Any]]:
    records: dict[tuple[str, float, float], Mapping[str, Any]] = {}
    for item in metadata:
        if item.get("arm") != "A1":
            continue
        command = item["command_parameters"]["left"]
        records[(str(item["lane_id"]), float(command["alpha"]), float(command["duration_s"]))] = item
    return records


def _alpha_token(alpha: float) -> str:
    return "0P5" if float(alpha) == 0.5 else str(int(alpha))


def _reference_eligibility(
    metadata: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_key = _metadata_by_lane_level(metadata)
    records: list[dict[str, Any]] = []
    eligible: list[dict[str, Any]] = []
    for alpha in (0.5, 1.0, 2.0, 4.0, 8.0, 16.0):
        for duration in (0.005, 0.01, 0.02):
            rk = by_key[("RK4_REFERENCE", alpha, duration)]
            mid = by_key[("MIDPOINT_REFERENCE", alpha, duration)]
            level_id = f"ALPHA_{_alpha_token(alpha)}__TCMD_MS_{round(duration * 1000)}"
            geometry = bool(rk["geometry_domain"]["passed"] and mid["geometry_domain"]["passed"])
            both_finite = bool(
                rk["responses"]["finite_removal_event"]
                and mid["responses"]["finite_removal_event"]
            )
            if not geometry:
                record = gate_record(
                    "B4F-G12-CROSS-INTEGRATOR-CONVERGENCE", "NOT_APPLICABLE", None,
                    "REFERENCE_CASE_GEOMETRY_DOMAIN_EXIT",
                    {"level_id": level_id, "alpha": alpha, "T_cmd_s": duration},
                )
            elif not rk["responses"]["finite_removal_event"] and not mid["responses"]["finite_removal_event"]:
                record = gate_record(
                    "B4F-G12-CROSS-INTEGRATOR-CONVERGENCE", "NOT_APPLICABLE", None,
                    "NO_PAIRED_FINITE_REFERENCE_EVENT",
                    {
                        "level_id": level_id, "alpha": alpha, "T_cmd_s": duration,
                        "rk4_finite": rk["responses"]["finite_removal_event"],
                        "midpoint_finite": mid["responses"]["finite_removal_event"],
                    },
                )
            elif not both_finite:
                record = gate_record(
                    "B4F-G12-CROSS-INTEGRATOR-CONVERGENCE", "PASS", False,
                    "EXACTLY_ONE_REFERENCE_FINITE_EVENT_EVALUATED_NEGATIVE_OUTCOME",
                    {
                        "level_id": level_id, "alpha": alpha, "T_cmd_s": duration,
                        "rk4_finite": rk["responses"]["finite_removal_event"],
                        "midpoint_finite": mid["responses"]["finite_removal_event"],
                        "eligible": False,
                        "one_reference_success_only_rule_applied": True,
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
                provenance_pass = bool(
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
                    and work_delta <= work_tolerance and provenance_pass
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
                    "lane_specific_fresh_provenance_pass": provenance_pass,
                    "rk4_reference_case_id": rk["case_id"],
                    "midpoint_reference_case_id": mid["case_id"],
                }
                record = gate_record(
                    "B4F-G12-CROSS-INTEGRATOR-CONVERGENCE", "PASS", predicate,
                    "PAIRED_FINITE_REFERENCE_EVENTS_EVALUATED", detail,
                )
                if predicate:
                    eligible.append({
                        "level_id": level_id,
                        "alpha": alpha,
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


def _write_a2_selection_ledger(
    evidence_root: Path,
    pre_run: Mapping[str, Any],
    g12_records: list[dict[str, Any]],
    eligible: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    selected = eligible[0] if eligible else None
    core = {
        "schema": "SIM13_V4B4G_A2_SELECTION_LEDGER_V1",
        "self_excluded": True,
        "pre_run_execution_ledger_sha256": pre_run["pre_run_execution_ledger_sha256"],
        "cross_reference_gate_records_18": g12_records,
        "eligible_levels_in_frozen_sort_order": eligible,
        "selected_parent_level": selected,
        "selection_sort": [
            "alpha_ascending", "T_cmd_s_ascending", "case_abs_work_J_ascending",
            "canonical_level_id_ascending",
        ],
        "a2_not_evaluated_if_selected_parent_is_null": True,
    }
    payload = {**core, "ledger_payload_sha256": canonical_sha256(core)}
    path = evidence_root / "SIM13_V4B4G_A2_SELECTION_LEDGER_V1.json"
    _ensure_exact_json(path, payload, "RESUME_A2_SELECTION_LEDGER_MISMATCH")
    binding = {
        "path": path.resolve().as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "ledger_payload_sha256": payload["ledger_payload_sha256"],
    }
    return payload, binding


def _a0_aggregate(
    metadata: Iterable[Mapping[str, Any]],
    a0_parent_traces: Mapping[str, Any],
) -> dict[str, Any]:
    a0 = [item for item in metadata if item.get("arm") == "A0"]
    parent_by_lane = {
        row["lane_id"]: row for row in a0_parent_traces["trace_bindings"]
    }
    lanes: list[dict[str, Any]] = []
    for lane in ("RK4_COARSE", "RK4_FINE", "RK4_REFERENCE", "MIDPOINT_COARSE", "MIDPOINT_FINE", "MIDPOINT_REFERENCE"):
        records = [item for item in a0 if item["lane_id"] == lane]
        if len(records) != 2:
            raise B4GExecutionError(f"A0_SENTINEL_COUNT_MISMATCH:{lane}")
        pre = next(item for item in records if item["case_id"].endswith("__PRE"))
        post = next(item for item in records if item["case_id"].endswith("__POST"))
        pair_pass = bool(
            pre["numeric_payload_sha256"] == post["numeric_payload_sha256"]
            and pre["responses"]["a0_replay_comparison"]["passed"]
            and post["responses"]["a0_replay_comparison"]["passed"]
            and not pre["responses"]["finite_removal_event"]
            and not post["responses"]["finite_removal_event"]
        )
        lanes.append({
            "lane_id": lane,
            "pre_case_id": pre["case_id"],
            "post_case_id": post["case_id"],
            "pre_numeric_payload_sha256": pre["numeric_payload_sha256"],
            "post_numeric_payload_sha256": post["numeric_payload_sha256"],
            "parent_trace_sha256": parent_by_lane[lane]["npz_sha256"],
            "passed": pair_pass,
        })
    return {
        "a0_slot_count": len(a0),
        "lane_pairs": lanes,
        "all_exact_replay_and_pre_post_payload_pairs_pass": all(row["passed"] for row in lanes),
    }


def _a2_mirror_records(
    metadata: Iterable[Mapping[str, Any]], raw_root: Path, *, parent_exists: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records: list[dict[str, Any]] = []
    a2 = [item for item in metadata if item.get("arm") == "A2"]
    pairs = (("RIGHT_HALF_DELAY", "LEFT_HALF_DELAY_MIRROR"), ("RIGHT_COMMAND_OFF", "LEFT_COMMAND_OFF_MIRROR"))
    for lane in ("RK4_COARSE", "RK4_FINE", "RK4_REFERENCE", "MIDPOINT_COARSE", "MIDPOINT_FINE", "MIDPOINT_REFERENCE"):
        lane_items = [item for item in a2 if item["lane_id"] == lane]
        for right_variant, left_variant in pairs:
            right = next(item for item in lane_items if right_variant in item["case_id"])
            left = next(item for item in lane_items if left_variant in item["case_id"])
            if not parent_exists:
                records.append(gate_record(
                    "B4F-G13-A2-MIRROR-AND-BILATERAL-LOGIC", "NOT_APPLICABLE", None,
                    "NO_REFERENCE_ELIGIBLE_A1_PARENT",
                    {"lane_id": lane, "pair": [right_variant, left_variant]},
                ))
                continue
            left_slot = {"slot_index": left["slot_index"], "case_id": left["case_id"]}
            right_slot = {"slot_index": right["slot_index"], "case_id": right["case_id"]}
            left_npz = _case_paths(raw_root, left_slot)[1]
            right_npz = _case_paths(raw_root, right_slot)[1]
            detail = compare_a2_mirror_pair(left, right, left_npz, right_npz)
            records.append(gate_record(
                "B4F-G13-A2-MIRROR-AND-BILATERAL-LOGIC", "PASS",
                bool(detail["scientific_predicate"]), "A2_MIRROR_PAIR_EXECUTED",
                {"lane_id": lane, "pair": [right_variant, left_variant], **detail},
            ))
    if parent_exists:
        global_predicate = all(record["scientific_predicate"] is True for record in records)
        global_record = gate_record(
            "B4F-G13-A2-MIRROR-AND-BILATERAL-LOGIC", "PASS", global_predicate,
            "GLOBAL_A2_MIRROR_AGGREGATE", {"pair_record_count": len(records)},
        )
    else:
        global_record = gate_record(
            "B4F-G13-A2-MIRROR-AND-BILATERAL-LOGIC", "NOT_APPLICABLE", None,
            "NO_REFERENCE_ELIGIBLE_A1_PARENT",
            {"pair_record_count": len(records), "a2_na_slot_count": len(a2)},
        )
    return records, global_record


def _write_prerun_bundle(
    output_root: Path,
    contracts: Mapping[str, Mapping[str, Any]],
    identity: Mapping[str, Any],
    recursive: Mapping[str, Any],
    reference: campaign.ReferenceForceAudit,
    runtime_identity: Mapping[str, Any],
    a0_parent_traces: Mapping[str, Any],
) -> tuple[Path, Path, dict[str, Any], dict[str, Any]]:
    evidence_root = output_root / "evidence"
    results_root = output_root / "results"
    raw_root = evidence_root / "raw_cases"
    raw_root.mkdir(parents=True, exist_ok=True)
    results_root.mkdir(parents=True, exist_ok=True)
    snapshot = protected_snapshot(
        PROJECT_ROOT, PHASE_ROOT, contracts["bindings"], contracts["governance"],
    )
    snapshot_payload = {
        "schema": "SIM13_V4B4G_PRE_RUN_PROTECTED_ASSET_SNAPSHOT_V1",
        **snapshot,
        "a0_parent_reference_trace_manifest": dict(a0_parent_traces["manifest"]),
        "a0_parent_reference_trace_bindings_sha256": a0_parent_traces[
            "trace_bindings_sha256"
        ],
    }
    pre_path = evidence_root / "SIM13_V4B4G_PRE_RUN_PROTECTED_ASSET_SNAPSHOT_V1.json"
    if pre_path.exists():
        existing = read_json(pre_path)
        if existing != snapshot_payload:
            raise B4GExecutionError("RESUME_PRE_RUN_PROTECTED_SNAPSHOT_MISMATCH")
    else:
        atomic_write_json(pre_path, snapshot_payload)
    runtime_path = evidence_root / "SIM13_V4B4G_RUNTIME_ENVIRONMENT_V1.json"
    _ensure_runtime_evidence(runtime_path, runtime_identity)
    pre_run_ledger = _build_pre_run_execution_ledger(
        contracts,
        identity,
        recursive,
        runtime_identity,
        snapshot,
        a0_parent_traces,
    )
    ledger_path = evidence_root / "SIM13_V4B4G_PRE_RUN_EXECUTION_LEDGER_V1.json"
    _ensure_exact_json(
        ledger_path, pre_run_ledger, "RESUME_PRE_RUN_EXECUTION_LEDGER_MISMATCH",
    )
    pre_run = {
        "pre_run_execution_ledger_path": ledger_path.resolve().as_posix(),
        "pre_run_execution_ledger_bytes": ledger_path.stat().st_size,
        "pre_run_execution_ledger_sha256": sha256_file(ledger_path),
        "pre_run_protected_snapshot_path": pre_path.resolve().as_posix(),
        "pre_run_protected_snapshot_bytes": pre_path.stat().st_size,
        "pre_run_protected_snapshot_sha256": sha256_file(pre_path),
        "a0_parent_reference_trace_manifest_path": a0_parent_traces[
            "manifest_path"
        ],
        "a0_parent_reference_trace_manifest_bytes": a0_parent_traces[
            "manifest"
        ]["bytes"],
        "a0_parent_reference_trace_manifest_sha256": a0_parent_traces[
            "manifest"
        ]["sha256"],
        "a0_parent_reference_trace_bindings_sha256": a0_parent_traces[
            "trace_bindings_sha256"
        ],
        "runtime_identity_sha256": canonical_sha256(runtime_identity),
        "recursive_parent_identity_sha256": canonical_sha256(recursive),
    }
    source_manifest = {
        "schema": "SIM13_V4B4G_SOURCE_MANIFEST_SELF_EXCLUDED_V1",
        "self_excluded": True,
        "acyclic": True,
        "identity": identity,
        "recursive_parent_verification": recursive,
        "pre_run_execution_ledger": {
            "path": display_path(ledger_path, PROJECT_ROOT),
            "bytes": ledger_path.stat().st_size,
            "sha256": sha256_file(ledger_path),
            "ledger_payload_sha256": pre_run_ledger["ledger_payload_sha256"],
        },
        "a0_parent_reference_traces": dict(a0_parent_traces),
        "runtime_identity_sha256": canonical_sha256(runtime_identity),
        "claim_boundary": CLAIM_BOUNDARY,
    }
    source_path = evidence_root / "SIM13_V4B4G_SOURCE_MANIFEST_SELF_EXCLUDED_V1.json"
    if source_path.exists() and read_json(source_path) != source_manifest:
        raise B4GExecutionError("RESUME_SOURCE_MANIFEST_IDENTITY_MISMATCH")
    atomic_write_json(source_path, source_manifest)
    reference_payload = {
        "schema": "SIM13_V4B4G_REFERENCE_FORCE_AND_ACQUISITION_V1",
        "native_recomputation": reference.as_dict(),
        "one_common_Q_ref_per_finger_N": reference.individual_finger_reference_force_n,
        "per_lane_or_treatment_rescaling_used": False,
        "explicit_matrix_inverse_used": False,
        "signed_preregistration_anchors": identity["signed_preregistration_anchors"],
        "expected_execution_source_freeze_terminal_sha256": identity[
            "expected_execution_source_freeze_terminal_sha256"
        ],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    reference_path = evidence_root / "SIM13_V4B4G_REFERENCE_FORCE_AND_ACQUISITION_V1.json"
    if reference_path.exists() and read_json(reference_path) != reference_payload:
        raise B4GExecutionError("RESUME_REFERENCE_FORCE_EVIDENCE_MISMATCH")
    atomic_write_json(reference_path, reference_payload)
    schedule_path = evidence_root / "SIM13_V4B4G_REGISTERED_SCHEDULE_V1.json"
    if schedule_path.exists() and read_json(schedule_path) != contracts["schedule"]:
        raise B4GExecutionError("RESUME_REGISTERED_SCHEDULE_EVIDENCE_MISMATCH")
    atomic_write_json(schedule_path, contracts["schedule"])
    return evidence_root, raw_root, snapshot_payload, pre_run


def _negative_control_hook() -> dict[str, Any]:
    return {
        "status": "NOT_EXECUTED_BY_CAMPAIGN_ORCHESTRATOR",
        "registered_parent_count": 22,
        "registered_subvariant_count": 65,
        "required_next_module": "dedicated real-path mutation harness and final signer",
        "campaign_execution_credit_from_this_hook": False,
    }


def _mark_prior_invalidation_resolved(
    output_root: Path,
    campaign_summary_path: Path,
) -> None:
    """Retain a prior diagnostic receipt while marking the new attempt successful."""

    path = output_root / "results" / "SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json"
    if not path.is_file():
        return
    payload = read_json(path)
    if payload.get("schema") != "SIM13_V4B4G_EXECUTION_INVALIDATED_V1":
        raise B4GExecutionError("INVALIDATION_RECEIPT_SCHEMA_MISMATCH")
    payload.update({
        "active": False,
        "resolved_by": {
            "path": display_path(campaign_summary_path, PROJECT_ROOT),
            "bytes": campaign_summary_path.stat().st_size,
            "sha256": sha256_file(campaign_summary_path),
        },
        "diagnostic_receipt_retained": True,
    })
    atomic_write_json(path, payload)


def _write_provisional_post_campaign_snapshot(
    *,
    evidence_root: Path,
    post_snapshot: Mapping[str, Any],
    recursive_after: Mapping[str, Any],
    runtime_identity: Mapping[str, Any],
    campaign_summary_path: Path,
    a0_parent_trace_post_verification: Mapping[str, Any],
) -> dict[str, Any]:
    """Publish campaign-only post evidence after the summary, never final POST_RUN."""

    summary_binding = {
        "path": display_path(campaign_summary_path, PROJECT_ROOT),
        "bytes": campaign_summary_path.stat().st_size,
        "sha256": sha256_file(campaign_summary_path),
    }
    payload = {
        "schema": "SIM13_V4B4G_PROVISIONAL_POST_CAMPAIGN_PROTECTED_ASSET_SNAPSHOT_V1",
        "classification": "PROVISIONAL_POST_CAMPAIGN_ONLY",
        "final_post_run": False,
        "negative_controls_completed": False,
        "final_signing_authorized": False,
        "publication_order": [
            "CAMPAIGN_SUMMARY",
            "PROVISIONAL_POST_CAMPAIGN",
            "NEGATIVE_CONTROL_REQUIRED_LATER",
            "FINAL_POST_RUN_REVERIFY_REQUIRED_LATER",
        ],
        "campaign_summary_dependency": summary_binding,
        "protected_snapshot": dict(post_snapshot),
        "protected_snapshot_payload_sha256": post_snapshot["snapshot_payload_sha256"],
        "recursive_parent_post_verification": dict(recursive_after),
        "recursive_parent_post_identity_sha256": canonical_sha256(recursive_after),
        "runtime_identity": dict(runtime_identity),
        "runtime_identity_sha256": canonical_sha256(runtime_identity),
        "a0_parent_reference_trace_post_verification": dict(
            a0_parent_trace_post_verification
        ),
        "a0_parent_reference_trace_manifest_sha256": (
            a0_parent_trace_post_verification["manifest"]["sha256"]
        ),
        "required_finalizer_actions": [
            "execute_registered_negative_controls",
            "repeat_local_source_identity_verification",
            "repeat_direct_and_recursive_parent_DAG_verification",
            "repeat_protected_asset_snapshot",
            "publish_final_POST_RUN_only_after_all_preceding_dependencies",
        ],
        "claim_boundary": CLAIM_BOUNDARY,
    }
    atomic_write_json(
        evidence_root / "SIM13_V4B4G_PROVISIONAL_POST_CAMPAIGN_PROTECTED_ASSET_SNAPSHOT_V1.json",
        payload,
    )
    return payload


def _enforce_integrity_before_publication(
    ordered: Iterable[Mapping[str, Any]],
    global_gates: Iterable[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Separate execution integrity from legitimate negative scientific outcomes."""

    integrity_failures = [
        {"case_id": item["case_id"], "gate_id": record["gate_id"]}
        for item in ordered for record in item["gate_records"]
        if record["evaluation_status"] == "FAIL"
        and record["gate_id"] in _INTEGRITY_CASE_GATE_IDS
    ]
    global_integrity_failures = [
        {"gate_id": record["gate_id"]}
        for record in global_gates
        if record["evaluation_status"] == "FAIL"
        and record["gate_id"] in _INTEGRITY_GLOBAL_GATE_IDS
    ]
    if integrity_failures or global_integrity_failures:
        raise B4GExecutionError(
            "REGISTERED_CAMPAIGN_INTEGRITY_FAILURES:"
            f"CASE={integrity_failures}:GLOBAL={global_integrity_failures}"
        )
    return integrity_failures, global_integrity_failures


def _execute_campaign_impl(
    *,
    target_root: Path,
    execution_source_freeze_terminal: Path,
    expected_execution_source_freeze_terminal_sha256: str,
) -> dict[str, Any]:
    """Internal full campaign implementation; public wrapper owns invalidation."""

    _require_formal_execution_source_freeze_paths(
        target_root, execution_source_freeze_terminal,
    )
    _preflight_existing_campaign_managed_directories(target_root)
    # Revoke every prior campaign/final credit and publish the active attempt
    # marker before A0 parent traces, pre-run ledgers, or any other phase
    # evidence can be written by this attempt.
    _supersede_prior_final_credit(target_root)
    _prepare_campaign_managed_directories(target_root)
    contracts = _load_contracts()
    runtime_before = _runtime_identity()
    identity_before = execution_identity(
        PROJECT_ROOT,
        PHASE_ROOT,
        execution_source_freeze_terminal=execution_source_freeze_terminal,
        expected_execution_source_freeze_terminal_sha256=(
            expected_execution_source_freeze_terminal_sha256
        ),
    )
    if identity_before["execution_source_freeze"] is None:
        raise B4GExecutionError("FORMAL_CAMPAIGN_EXECUTION_SOURCE_FREEZE_REQUIRED")
    recursive_before = verify_recursive_parents(
        PROJECT_ROOT, PHASE_ROOT, contracts["bindings"],
    )
    a0_parent_traces_before = _write_fresh_a0_parent_reference_traces(
        output_root=target_root,
        contracts=contracts,
    )
    reference = campaign.recompute_reference_force()
    evidence_root, raw_root, pre_snapshot, pre_run = _write_prerun_bundle(
        target_root,
        contracts,
        identity_before,
        recursive_before,
        reference,
        runtime_before,
        a0_parent_traces_before,
    )
    schedule = contracts["schedule"]
    discovery, conditional = _registered_execution_plan(schedule)
    ordinal = {slot["case_id"]: index for index, slot in enumerate(discovery + conditional)}
    metadata: dict[int, dict[str, Any]] = {}

    for slot in discovery:
        hashes = _source_hashes(identity_before, schedule, slot, pre_run)
        item = _publish_executed_case(
            slot=slot, execution_ordinal=ordinal[slot["case_id"]], raw_root=raw_root,
            source_hashes=hashes,
            q_ref_n=reference.individual_finger_reference_force_n,
            selected_parent=None,
            pre_run=pre_run,
        )
        metadata[int(slot["slot_index"])] = item

    g12_records, eligible = _reference_eligibility(metadata.values())
    selection_ledger, selection_binding = _write_a2_selection_ledger(
        evidence_root, pre_run, g12_records, eligible,
    )
    selected = selection_ledger["selected_parent_level"]
    for slot in conditional:
        hashes = _source_hashes(
            identity_before,
            schedule,
            slot,
            pre_run,
            a2_selection_ledger_sha256=selection_binding["sha256"],
        )
        if slot["arm"] == "A2" and selected is None:
            item = _publish_na_a2(
                slot=slot, execution_ordinal=ordinal[slot["case_id"]], raw_root=raw_root,
                source_hashes=hashes,
                pre_run=pre_run,
            )
        else:
            item = _publish_executed_case(
                slot=slot, execution_ordinal=ordinal[slot["case_id"]], raw_root=raw_root,
                source_hashes=hashes,
                q_ref_n=reference.individual_finger_reference_force_n,
                selected_parent=selected if slot["arm"] == "A2" else None,
                pre_run=pre_run,
            )
        metadata[int(slot["slot_index"])] = item

    if sorted(metadata) != list(range(144)):
        raise B4GExecutionError("CAMPAIGN_DID_NOT_PRODUCE_EXACT_144_SLOT_RECORDS")
    ordered = [metadata[index] for index in range(144)]
    raw_inventory_pre_publication = _verify_raw_case_inventory(
        raw_root, schedule, ordered, phase="PRE_PUBLICATION",
    )
    a0 = _a0_aggregate(ordered, a0_parent_traces_before)
    pair_records, global_g13 = _a2_mirror_records(
        ordered, raw_root, parent_exists=selected is not None,
    )
    runtime_after = _runtime_identity()
    if runtime_after != runtime_before:
        raise B4GExecutionError("TOCTOU_RUNTIME_IDENTITY_CHANGED_DURING_CAMPAIGN")
    identity_after = execution_identity(
        PROJECT_ROOT,
        PHASE_ROOT,
        execution_source_freeze_terminal=execution_source_freeze_terminal,
        expected_execution_source_freeze_terminal_sha256=(
            expected_execution_source_freeze_terminal_sha256
        ),
    )
    if identity_after != identity_before:
        raise B4GExecutionError("TOCTOU_LOCAL_SOURCE_OR_CONTRACT_CHANGED_DURING_CAMPAIGN")
    recursive_after = verify_recursive_parents(
        PROJECT_ROOT, PHASE_ROOT, contracts["bindings"],
    )
    recursive_before_sha = canonical_sha256(recursive_before)
    recursive_after_sha = canonical_sha256(recursive_after)
    if recursive_after_sha != recursive_before_sha:
        raise B4GExecutionError("TOCTOU_RECURSIVE_PARENT_DAG_CHANGED_DURING_CAMPAIGN")
    post_snapshot = protected_snapshot(
        PROJECT_ROOT, PHASE_ROOT, contracts["bindings"], contracts["governance"],
    )
    if post_snapshot["snapshot_payload_sha256"] != pre_snapshot["snapshot_payload_sha256"]:
        raise B4GExecutionError("PROTECTED_PARENT_OR_FORBIDDEN_ASSET_CHANGED_DURING_CAMPAIGN")
    a0_parent_traces_after = _verify_a0_parent_trace_bundle(
        a0_parent_traces_before["manifest"],
    )
    if a0_parent_traces_after != a0_parent_traces_before:
        raise B4GExecutionError("A0_PARENT_REFERENCE_TRACE_BUNDLE_CHANGED_DURING_CAMPAIGN")
    raw_inventory_post_toctou = _verify_raw_case_inventory(
        raw_root, schedule, ordered, phase="POST_TOCTOU",
    )
    if (
        raw_inventory_post_toctou["filenames"]
        != raw_inventory_pre_publication["filenames"]
        or raw_inventory_post_toctou["registered_json_count"]
        != raw_inventory_pre_publication["registered_json_count"]
        or raw_inventory_post_toctou["executed_npz_count"]
        != raw_inventory_pre_publication["executed_npz_count"]
    ):
        raise B4GExecutionError("RAW_CASE_INVENTORY_CHANGED_DURING_POST_CHECKS")

    a2_na_count = sum(item["execution_status"] == "NOT_EVALUATED_NO_A1_SUCCESS" for item in ordered)
    executed_count = 144 - a2_na_count
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
    global_gates = [
        gate_record(
            "B4F-G01-SOURCE-AND-PARENT-RECURSIVE", "PASS", True,
            "GLOBAL_PRE_AND_PROVISIONAL_POST_CAMPAIGN_FULL_RECURSIVE_REVERIFY",
            {
                "direct_binding_count": recursive_before["direct_binding_count"],
                "pre_recursive_parent_identity_sha256": recursive_before_sha,
                "post_recursive_parent_identity_sha256": recursive_after_sha,
                "recursive_parent_exact_match": True,
                "pre_protected_snapshot_payload_sha256": pre_snapshot["snapshot_payload_sha256"],
                "post_protected_snapshot_payload_sha256": post_snapshot["snapshot_payload_sha256"],
                "protected_snapshot_exact_match": True,
                "pre_preregistration_source_record_count": pre_snapshot[
                    "preregistration_source_verification"
                ]["record_count"],
                "post_preregistration_source_record_count": post_snapshot[
                    "preregistration_source_verification"
                ]["record_count"],
                "pre_and_post_preregistration_19_of_19_verified": True,
                "execution_source_freeze_terminal_sha256": identity_before[
                    "expected_execution_source_freeze_terminal_sha256"
                ],
                "runtime_identity_exact_match": True,
                "pre_a0_parent_reference_trace_manifest_sha256": (
                    a0_parent_traces_before["manifest"]["sha256"]
                ),
                "post_a0_parent_reference_trace_manifest_sha256": (
                    a0_parent_traces_after["manifest"]["sha256"]
                ),
                "a0_parent_reference_trace_bundle_exact_match": True,
                "final_post_run_not_claimed": True,
            },
        ),
        gate_record(
            "B4F-G02-A0-EXACT-REPLAY",
            "PASS" if a0["all_exact_replay_and_pre_post_payload_pairs_pass"] else "FAIL",
            bool(a0["all_exact_replay_and_pre_post_payload_pairs_pass"]),
            "GLOBAL_12_A0_AGGREGATE", a0,
        ),
        global_g13,
        gate_record(
            "B4F-G14-REGISTERED-DOMAIN-NO-POST-HOC-EXTENSION", "PASS", True,
            "GLOBAL_SCHEDULE_AND_ALL_144_SLOTS",
            {"slot_count": 144, "schedule_sha256": schedule["slots_sha256"], "post_result_extension_used": False},
        ),
        gate_record(
            "B4F-G15-GOVERNANCE-AND-NULL-PHYSICAL-INPUTS", "PASS", True,
            "GLOBAL_PRE_RUN_AND_PROVISIONAL_POST_CAMPAIGN",
            {
                "required_false": contracts["governance"]["required_false"],
                "required_null_physical_inputs": {name: None for name in contracts["governance"]["required_null_physical_inputs"]},
                "memory": contracts["run_spec"]["memory"],
                "formal_sim13_v2_state_unchanged": contracts["governance"]["formal_sim13_v2_state_unchanged"],
            },
        ),
        gate_record(
            "B4F-G17-DISCRETE-GRID-REPORTING-BOUNDARY", "PASS", True,
            "GLOBAL_SELECTOR_AND_REPORT", selector,
        ),
    ]
    integrity_failures, global_integrity_failures = (
        _enforce_integrity_before_publication(ordered, global_gates)
    )
    campaign_summary = {
        "schema": "SIM13_V4B4G_CAMPAIGN_SUMMARY_V1",
        "status": "CAMPAIGN_EXECUTION_COMPLETE_PENDING_NEGATIVE_CONTROLS_VALIDATOR_AND_INDEPENDENT_AUDIT",
        "final": False,
        "scope": "REGISTERED_SYNTHETIC_DISCRETE_DOMAIN_ONLY",
        "logical_slot_count": 144,
        "executed_slot_count": executed_count,
        "a2_not_evaluated_slot_count": a2_na_count,
        "orchestration": {
            "discovery_wave_count": len(discovery),
            "conditional_a2_and_post_wave_count": len(conditional),
            "reason": "A2 requires global paired-reference parent selection before execution",
            "slot_index_semantics_unchanged": True,
            "within_lane_registered_order_preserved": True,
            "hidden_mutable_state_or_event_cache_between_cases": False,
        },
        "signed_preregistration_anchors": identity_before["signed_preregistration_anchors"],
        "execution_source_freeze": identity_before["execution_source_freeze"],
        "expected_execution_source_freeze_terminal_sha256": identity_before[
            "expected_execution_source_freeze_terminal_sha256"
        ],
        "pre_run_identity": dict(pre_run),
        "pre_recursive_parent_identity_sha256": recursive_before_sha,
        "post_recursive_parent_identity_sha256": recursive_after_sha,
        "runtime_identity": runtime_before,
        "runtime_identity_sha256": canonical_sha256(runtime_before),
        "a0_parent_reference_traces": a0_parent_traces_before,
        "one_common_Q_ref_per_finger_N": reference.individual_finger_reference_force_n,
        "a0": a0,
        "cross_reference_gate_records_18": g12_records,
        "reference_eligible_levels": eligible,
        "selector": selector,
        "a2_selection_ledger": selection_binding,
        "a2_mirror_pair_gate_records_12": pair_records,
        "global_gate_records": global_gates,
        "case_integrity_failures": integrity_failures,
        "global_integrity_failures": global_integrity_failures,
        "registered_domain_execution_integrity_pass": True,
        "raw_case_inventory_pre_publication": raw_inventory_pre_publication,
        "raw_case_inventory_post_toctou": raw_inventory_post_toctou,
        "negative_control_hook": _negative_control_hook(),
        "governance": {
            "required_false": contracts["governance"]["required_false"],
            "required_null_physical_inputs": {name: None for name in contracts["governance"]["required_null_physical_inputs"]},
            "formal_sim13_v2_state_unchanged": contracts["governance"]["formal_sim13_v2_state_unchanged"],
            "memory": contracts["run_spec"]["memory"],
        },
        "claim_boundary": CLAIM_BOUNDARY,
        "case_metadata_index": [
            {
                "slot_index": item["slot_index"], "case_id": item["case_id"],
                "execution_status": item["execution_status"],
                "metadata_path": display_path(_case_paths(raw_root, schedule["slots"][item["slot_index"]])[0], PROJECT_ROOT),
                "metadata_sha256": sha256_file(_case_paths(raw_root, schedule["slots"][item["slot_index"]])[0]),
            }
            for item in ordered
        ],
    }
    campaign_summary_path = (
        target_root / "results" / "SIM13_V4B4G_CAMPAIGN_SUMMARY_V1.json"
    )
    atomic_write_json(campaign_summary_path, campaign_summary)
    _write_provisional_post_campaign_snapshot(
        evidence_root=evidence_root,
        post_snapshot=post_snapshot,
        recursive_after=recursive_after,
        runtime_identity=runtime_after,
        campaign_summary_path=campaign_summary_path,
        a0_parent_trace_post_verification=a0_parent_traces_after,
    )
    _mark_supersession_resolved(target_root, campaign_summary_path)
    _mark_prior_invalidation_resolved(target_root, campaign_summary_path)
    return campaign_summary


def execute_campaign(
    *,
    output_root: Path | None = None,
    execution_source_freeze_terminal: Path | None = None,
    expected_execution_source_freeze_terminal_sha256: str | None = None,
) -> dict[str, Any]:
    """Execute/resume 144 slots, fail closed, and stop before negative controls."""

    requested_root = PHASE_ROOT if output_root is None else Path(output_root)
    requested_lexical = _require_lexical_output_root_no_links(requested_root)
    formal_lexical = Path(os.path.abspath(PHASE_ROOT))
    if (
        requested_lexical != formal_lexical
        or requested_lexical.resolve() != PHASE_ROOT.resolve()
    ):
        raise B4GExecutionError("FULL_CAMPAIGN_REQUIRES_FORMAL_PHASE_ROOT")
    target_root = _prepare_output_root(requested_lexical)
    try:
        if (
            execution_source_freeze_terminal is None
            or expected_execution_source_freeze_terminal_sha256 is None
        ):
            raise B4GExecutionError(
                "FULL_CAMPAIGN_REQUIRES_EXTERNAL_EXECUTION_SOURCE_FREEZE_TERMINAL_AND_SHA256"
            )
        return _execute_campaign_impl(
            target_root=target_root,
            execution_source_freeze_terminal=Path(execution_source_freeze_terminal),
            expected_execution_source_freeze_terminal_sha256=(
                expected_execution_source_freeze_terminal_sha256
            ),
        )
    except BaseException as failure:
        try:
            invalidate_output_root(target_root, failure)
        except BaseException as cleanup_failure:
            if hasattr(failure, "add_note"):
                failure.add_note(f"B4G stale-final invalidation also failed: {cleanup_failure}")
        raise


def _execute_smoke_impl(*, slot_index: int, target_root: Path) -> dict[str, Any]:
    """Run one non-publication unconditional slot through the complete shard writer."""

    contracts = _load_contracts()
    if not 0 <= int(slot_index) < 144:
        raise B4GExecutionError("SMOKE_SLOT_INDEX_OUTSIDE_0_143")
    slot = contracts["schedule"]["slots"][int(slot_index)]
    if slot["arm"] == "A2":
        raise B4GExecutionError("SMOKE_A2_REQUIRES_FULL_GLOBAL_PARENT_SELECTION")
    runtime_before = _runtime_identity()
    identity = execution_identity(PROJECT_ROOT, PHASE_ROOT)
    recursive_before = verify_recursive_parents(
        PROJECT_ROOT, PHASE_ROOT, contracts["bindings"],
    )
    a0_parent_traces_before = _write_fresh_a0_parent_reference_traces(
        output_root=target_root,
        contracts=contracts,
    )
    reference = campaign.recompute_reference_force()
    evidence_root, raw_root, pre, pre_run = _write_prerun_bundle(
        target_root,
        contracts,
        identity,
        recursive_before,
        reference,
        runtime_before,
        a0_parent_traces_before,
    )
    discovery, conditional = _registered_execution_plan(contracts["schedule"])
    ordinal = {
        candidate["case_id"]: index
        for index, candidate in enumerate(discovery + conditional)
    }[slot["case_id"]]
    item = _publish_executed_case(
        slot=slot, execution_ordinal=ordinal, raw_root=raw_root,
        source_hashes=_source_hashes(
            identity, contracts["schedule"], slot, pre_run,
        ),
        q_ref_n=reference.individual_finger_reference_force_n,
        selected_parent=None,
        pre_run=pre_run,
    )
    runtime_after = _runtime_identity()
    identity_after = execution_identity(PROJECT_ROOT, PHASE_ROOT)
    recursive_after = verify_recursive_parents(
        PROJECT_ROOT, PHASE_ROOT, contracts["bindings"],
    )
    post = protected_snapshot(PROJECT_ROOT, PHASE_ROOT, contracts["bindings"], contracts["governance"])
    a0_parent_traces_after = _verify_a0_parent_trace_bundle(
        a0_parent_traces_before["manifest"],
    )
    if (
        identity_after != identity
        or runtime_after != runtime_before
        or canonical_sha256(recursive_after) != canonical_sha256(recursive_before)
        or post["snapshot_payload_sha256"] != pre["snapshot_payload_sha256"]
        or a0_parent_traces_after != a0_parent_traces_before
    ):
        raise B4GExecutionError("SMOKE_TOCTOU_SOURCE_OR_PROTECTED_ASSET_DRIFT")
    summary = {
        "schema": "SIM13_V4B4G_BOUNDED_SMOKE_RESULT_V1",
        "publication_credit": False,
        "slot_index": slot["slot_index"],
        "case_id": slot["case_id"],
        "execution_status": item["execution_status"],
        "terminal_status": item["terminal_status"],
        "npz_sha256": item["npz_sha256"],
        "all_case_integrity_gates_nonfail": all(
            record["evaluation_status"] != "FAIL" for record in item["gate_records"]
        ),
        "signed_preregistration_anchor_set_sha256": identity["signed_preregistration_anchor_set_sha256"],
        "execution_source_freeze_terminal_sha256": None,
        "recursive_parent_pre_post_exact_match": True,
        "runtime_identity_sha256": canonical_sha256(runtime_before),
        "a0_parent_reference_traces": a0_parent_traces_before,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    summary_path = target_root / "results" / "SIM13_V4B4G_BOUNDED_SMOKE_RESULT_V1.json"
    atomic_write_json(summary_path, summary)
    _write_provisional_post_campaign_snapshot(
        evidence_root=evidence_root,
        post_snapshot=post,
        recursive_after=recursive_after,
        runtime_identity=runtime_after,
        campaign_summary_path=summary_path,
        a0_parent_trace_post_verification=a0_parent_traces_after,
    )
    return summary


def execute_smoke(*, slot_index: int, output_root: Path) -> dict[str, Any]:
    """Run a bounded diagnostic shard and invalidate stale finals on any failure."""

    requested_root = _require_lexical_output_root_no_links(Path(output_root))
    if requested_root.resolve() == PHASE_ROOT.resolve():
        raise B4GExecutionError("SMOKE_REQUIRES_CUSTOM_DIAGNOSTIC_OUTPUT_ROOT")
    target_root = _prepare_output_root(requested_root)
    _prepare_campaign_managed_directories(target_root)
    try:
        return _execute_smoke_impl(slot_index=slot_index, target_root=target_root)
    except BaseException as failure:
        try:
            invalidate_output_root(target_root, failure)
        except BaseException as cleanup_failure:
            if hasattr(failure, "add_note"):
                failure.add_note(f"B4G stale-final invalidation also failed: {cleanup_failure}")
        raise
