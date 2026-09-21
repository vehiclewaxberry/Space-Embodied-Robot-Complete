"""Publish the deterministic B4G post-run and pre-audit evidence prefix.

This entrypoint is a publisher, not the independent auditor.  It can run only
after the registered campaign and all 65 mutation receipts exist.  It repeats
the frozen-source, recursive-parent, protected-asset, runtime, A0-parent and
raw-case checks, publishes the final POST_RUN snapshot, invokes the read-only
validator in ``full`` mode, and only then publishes validation, the acyclic
self-excluded evidence manifest, and the non-final PREAUDIT gate.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Callable, Iterable, Mapping, Sequence

from b4g_execution.io import (
    atomic_write_json,
    canonical_bytes,
    canonical_sha256,
    read_json,
    sha256_file,
)
from b4g_execution.orchestrator import (
    B4GExecutionError,
    CLAIM_BOUNDARY,
    PHASE_ROOT,
    PROJECT_ROOT,
    _load_contracts,
    _require_formal_execution_source_freeze_paths,
    _runtime_identity,
    _verify_a0_parent_trace_bundle,
    _verify_raw_case_inventory,
    campaign,
)
from b4g_execution.source_guard import (
    execution_identity,
    protected_snapshot,
    verify_recursive_parents,
)


POST_RELATIVE_PATH = Path(
    "evidence/SIM13_V4B4G_POST_RUN_PROTECTED_ASSET_SNAPSHOT_V1.json"
)
VALIDATION_RELATIVE_PATH = Path(
    "evidence/SIM13_V4B4G_EXECUTION_VALIDATION_V1.json"
)
MANIFEST_RELATIVE_PATH = Path(
    "evidence/SIM13_V4B4G_EVIDENCE_MANIFEST_SELF_EXCLUDED_V1.json"
)
PREAUDIT_RELATIVE_PATH = Path(
    "results/SIM13_V4B4G_PREAUDIT_GATE_V1.json"
)

_STALE_AUDIT_AND_FINAL_RELATIVE_PATHS = (
    Path("results/SIM13_V4B4G_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"),
    Path("results/SIM13_V4B4G_AUDITED_GATE_V1.json"),
    Path("evidence/SIM13_V4B4G_INDEPENDENT_AUDIT_RECEIPT_V1.json"),
    PREAUDIT_RELATIVE_PATH,
    MANIFEST_RELATIVE_PATH,
    VALIDATION_RELATIVE_PATH,
    POST_RELATIVE_PATH,
)

_PHASE_PROJECT_RELATIVE = PHASE_ROOT.resolve().relative_to(
    PROJECT_ROOT.resolve()
).as_posix()
_EXCLUDED_FUTURE_OUTPUTS = [
    f"{_PHASE_PROJECT_RELATIVE}/evidence/"
    "SIM13_V4B4G_EVIDENCE_MANIFEST_SELF_EXCLUDED_V1.json",
    f"{_PHASE_PROJECT_RELATIVE}/results/SIM13_V4B4G_PREAUDIT_GATE_V1.json",
    f"{_PHASE_PROJECT_RELATIVE}/evidence/"
    "SIM13_V4B4G_INDEPENDENT_AUDIT_RECEIPT_V1.json",
    f"{_PHASE_PROJECT_RELATIVE}/results/SIM13_V4B4G_AUDITED_GATE_V1.json",
    f"{_PHASE_PROJECT_RELATIVE}/results/"
    "SIM13_V4B4G_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json",
]

_DIRECT_RECORDS = (
    ("evidence/SIM13_V4B4G_PRE_RUN_PROTECTED_ASSET_SNAPSHOT_V1.json",
     "PRE_RUN_PROTECTED_ASSET_SNAPSHOT"),
    ("evidence/SIM13_V4B4G_SOURCE_MANIFEST_SELF_EXCLUDED_V1.json",
     "SOURCE_MANIFEST_SELF_EXCLUDED"),
    ("evidence/SIM13_V4B4G_REFERENCE_FORCE_AND_ACQUISITION_V1.json",
     "REFERENCE_FORCE_AND_ACQUISITION"),
    ("evidence/SIM13_V4B4G_REGISTERED_SCHEDULE_V1.json",
     "REGISTERED_SCHEDULE"),
    ("evidence/SIM13_V4B4G_RUNTIME_ENVIRONMENT_V1.json",
     "RUNTIME_ENVIRONMENT"),
    ("evidence/SIM13_V4B4G_PRE_RUN_EXECUTION_LEDGER_V1.json",
     "PRE_RUN_EXECUTION_LEDGER"),
    ("evidence/SIM13_V4B4G_A2_SELECTION_LEDGER_V1.json",
     "A2_SELECTION_LEDGER"),
    ("evidence/SIM13_V4B4G_A0_PARENT_REFERENCE_TRACES_V1.json",
     "A0_PARENT_TRACE_MANIFEST"),
    ("evidence/SIM13_V4B4G_PROVISIONAL_POST_CAMPAIGN_PROTECTED_ASSET_SNAPSHOT_V1.json",
     "PROVISIONAL_POST_CAMPAIGN_SNAPSHOT"),
    ("results/SIM13_V4B4G_CAMPAIGN_SUMMARY_V1.json", "CAMPAIGN_SUMMARY"),
    ("b4g_mutation_execution/SIM13_V4B4G_NEGATIVE_CONTROL_EVIDENCE_V1.json",
     "NEGATIVE_CONTROL_EVIDENCE"),
)

_FIXED_ROLE_COUNTS = {
    "PRE_RUN_PROTECTED_ASSET_SNAPSHOT": 1,
    "SOURCE_MANIFEST_SELF_EXCLUDED": 1,
    "REFERENCE_FORCE_AND_ACQUISITION": 1,
    "REGISTERED_SCHEDULE": 1,
    "RUNTIME_ENVIRONMENT": 1,
    "PRE_RUN_EXECUTION_LEDGER": 1,
    "A2_SELECTION_LEDGER": 1,
    "A0_PARENT_TRACE_MANIFEST": 1,
    "PROVISIONAL_POST_CAMPAIGN_SNAPSHOT": 1,
    "REGISTERED_CASE_METADATA": 144,
    "CAMPAIGN_SUMMARY": 1,
    "NEGATIVE_CONTROL_EVIDENCE": 1,
    "POST_RUN_PROTECTED_ASSET_SNAPSHOT": 1,
    "EXECUTION_VALIDATION_FULL": 1,
    "EXECUTION_SOURCE_FREEZE_TERMINAL": 1,
    "A0_PARENT_TRACE_NPZ": 6,
    "MUTATION_BASE_BUNDLE": 65,
    "MUTATION_MUTANT_BUNDLE": 65,
    "MUTATION_PATCH_BUNDLE": 65,
}


class B4GPreauditPublicationError(RuntimeError):
    """The non-final publication prefix could not be created safely."""


def _strict_json_object(payload: bytes, *, label: str) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"DUPLICATE_KEY:{key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=lambda token: (_ for _ in ()).throw(
                ValueError(f"NONFINITE:{token}")
            ),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise B4GPreauditPublicationError(
            f"{label}_STRICT_JSON_PARSE_FAILED"
        ) from error
    if not isinstance(value, dict):
        raise B4GPreauditPublicationError(f"{label}_ROOT_NOT_OBJECT")
    return value


def _run_full_validator_subprocess(*, mode: str) -> dict[str, Any]:
    """Run the independent validator in a clean interpreter process."""

    if mode != "full":
        raise B4GPreauditPublicationError("PREAUDIT_VALIDATOR_MODE_NOT_FULL")
    entrypoint = PHASE_ROOT / "validate_phase_b4g_evidence.py"
    process = subprocess.run(
        [sys.executable, str(entrypoint), "--mode", "full"],
        cwd=PHASE_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", errors="replace")[-2000:]
        raise B4GPreauditPublicationError(
            f"FULL_VALIDATOR_SUBPROCESS_FAILED:{process.returncode}:{detail}"
        )
    if process.stderr:
        raise B4GPreauditPublicationError(
            "FULL_VALIDATOR_SUBPROCESS_STDERR_NOT_EMPTY"
        )
    payload = _strict_json_object(
        process.stdout.rstrip(b"\r\n"), label="FULL_VALIDATOR_STDOUT",
    )
    if process.stdout != canonical_bytes(payload) + b"\n":
        raise B4GPreauditPublicationError(
            "FULL_VALIDATOR_STDOUT_NOT_ONE_CANONICAL_LF_LINE"
        )
    return payload


def _safe_root(root: Path) -> Path:
    resolved = Path(root).resolve()
    if (
        resolved == Path(resolved.anchor)
        or resolved == PROJECT_ROOT
        or resolved == PROJECT_ROOT.parent
    ):
        raise B4GPreauditPublicationError(f"UNSAFE_PREAUDIT_OUTPUT_ROOT:{resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _owned_lexical_target(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or any(
        part in {"", ".", ".."} for part in relative.parts
    ):
        raise B4GPreauditPublicationError(
            f"PREAUDIT_TARGET_RELATIVE_PATH_INVALID:{relative}"
        )
    target = root.joinpath(*relative.parts)
    try:
        target.parent.resolve().relative_to(root)
    except ValueError as error:
        raise B4GPreauditPublicationError(
            f"PREAUDIT_TARGET_ESCAPES_OUTPUT_ROOT:{target}"
        ) from error
    return target


def _safe_target(root: Path, relative: Path) -> Path:
    target = _owned_lexical_target(root, relative)
    if os.path.lexists(target) and target.is_symlink():
        raise B4GPreauditPublicationError(
            f"PREAUDIT_SYMLINK_PUBLICATION_TARGET:{target}"
        )
    return target


def _cleanup_stale_audit_and_final_outputs(
    root: Path,
    *,
    unlink_fn: Callable[[Path], None] | None = None,
) -> list[dict[str, Any]]:
    """Best-effort consumer-first removal of the exact final allowlist."""

    removed: list[dict[str, Any]] = []
    failures: list[str] = []
    unlink = (lambda path: path.unlink()) if unlink_fn is None else unlink_fn
    for relative in _STALE_AUDIT_AND_FINAL_RELATIVE_PATHS:
        try:
            path = _owned_lexical_target(root, relative)
            if not os.path.lexists(path):
                continue
            if path.is_symlink():
                record = {
                    "path": relative.as_posix(),
                    "bytes": path.lstat().st_size,
                    "sha256": None,
                    "object_type": "SYMLINK",
                }
            elif path.is_file():
                record = {
                    "path": relative.as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "object_type": "REGULAR_FILE",
                }
            else:
                raise B4GPreauditPublicationError(
                    f"PREAUDIT_STALE_FINAL_NOT_FILE_OR_SYMLINK:{relative.as_posix()}"
                )
            unlink(path)
            removed.append(record)
        except BaseException as error:
            failures.append(
                f"{relative.as_posix()}:{type(error).__name__}:{error}"
            )
    if failures:
        raise B4GPreauditPublicationError(
            "PREAUDIT_STALE_FINAL_CLEANUP_INCOMPLETE:" + "|".join(failures)
        )
    return removed


def _canonical_json(path: Path, expected_schema: str | None = None) -> dict[str, Any]:
    if not path.is_file():
        raise B4GPreauditPublicationError(f"PREAUDIT_DEPENDENCY_MISSING:{path}")
    value = read_json(path)
    if path.read_bytes() != canonical_bytes(value) + b"\n":
        raise B4GPreauditPublicationError(
            f"PREAUDIT_DEPENDENCY_NOT_CANONICAL_JSON:{path.name}"
        )
    if expected_schema is not None and value.get("schema") != expected_schema:
        raise B4GPreauditPublicationError(
            f"PREAUDIT_DEPENDENCY_SCHEMA_MISMATCH:{path.name}"
        )
    return value


def _project_relative(path: Path, project_root: Path) -> str:
    resolved = Path(path).resolve()
    try:
        relative = resolved.relative_to(project_root.resolve())
    except ValueError as error:
        raise B4GPreauditPublicationError(
            f"MANIFEST_DEPENDENCY_OUTSIDE_PROJECT_ROOT:{resolved}"
        ) from error
    value = relative.as_posix()
    parts = value.split("/")
    if (
        not value
        or "\\" in value
        or any(part in {"", ".", ".."} for part in parts)
        or any(part.startswith(".") for part in parts)
    ):
        raise B4GPreauditPublicationError(
            f"MANIFEST_DEPENDENCY_PATH_INVALID:{value}"
        )
    return value


def _record(path: Path, role: str, *, project_root: Path) -> dict[str, Any]:
    resolved = Path(path).resolve()
    if not resolved.is_file():
        raise B4GPreauditPublicationError(
            f"MANIFEST_DEPENDENCY_MISSING:{resolved}"
        )
    return {
        "path": _project_relative(resolved, project_root),
        "role": role,
        "bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def _resolve_declared(
    declared: Any,
    *,
    project_root: Path,
    publication_root: Path,
) -> Path:
    value = Path(str(declared))
    if value.is_absolute():
        return value.resolve()
    project_candidate = (project_root / value).resolve()
    if project_candidate.is_file():
        return project_candidate
    return (publication_root / value).resolve()


def _verify_record_points_to(
    row: Mapping[str, Any],
    expected: Path,
    *,
    project_root: Path,
    publication_root: Path,
    label: str,
) -> None:
    actual = _resolve_declared(
        row.get("path"), project_root=project_root,
        publication_root=publication_root,
    )
    target = Path(expected).resolve()
    if (
        actual != target
        or not target.is_file()
        or row.get("bytes") != target.stat().st_size
        or str(row.get("sha256", "")).upper() != sha256_file(target)
    ):
        raise B4GPreauditPublicationError(f"{label}_RECORD_MISMATCH")


def _require_no_active_attempt_markers(root: Path) -> None:
    mutation_incomplete = (
        root / "b4g_mutation_execution"
        / "SIM13_V4B4G_MUTATION_EXECUTION_INCOMPLETE_V1.json"
    )
    if os.path.lexists(mutation_incomplete):
        raise B4GPreauditPublicationError(
            "POST_RUN_MUTATION_INCOMPLETE_MARKER_PRESENT"
        )
    for receipt_path, expected_schema in (
        (
            root / "results/SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json",
            "SIM13_V4B4G_EXECUTION_INVALIDATED_V1",
        ),
        (
            root / "results/SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1.json",
            "SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1",
        ),
    ):
        if not os.path.lexists(receipt_path):
            continue
        if receipt_path.is_symlink() or not receipt_path.is_file():
            raise B4GPreauditPublicationError(
                f"POST_RUN_CAMPAIGN_RECEIPT_NOT_PLAIN_FILE:{receipt_path.name}"
            )
        try:
            receipt = _canonical_json(receipt_path, expected_schema)
        except BaseException as error:
            raise B4GPreauditPublicationError(
                f"POST_RUN_CAMPAIGN_RECEIPT_INVALID:{receipt_path.name}"
            ) from error
        if receipt.get("active") is not False:
            raise B4GPreauditPublicationError(
                f"POST_RUN_ACTIVE_CAMPAIGN_RECEIPT:{receipt_path.name}"
            )


def _formal_reverification(
    *,
    output_root: Path,
    execution_source_freeze_terminal: Path,
    expected_execution_source_freeze_terminal_sha256: str,
) -> dict[str, Any]:
    """Repeat every mutable-boundary check before final POST_RUN publication."""

    root = Path(output_root).resolve()
    if root != PHASE_ROOT.resolve():
        raise B4GPreauditPublicationError(
            "FORMAL_PREAUDIT_PUBLISHER_REQUIRES_PHASE_ROOT"
        )
    try:
        _require_formal_execution_source_freeze_paths(
            root, Path(execution_source_freeze_terminal),
        )
    except B4GExecutionError as error:
        raise B4GPreauditPublicationError(
            f"POST_RUN_EXECUTION_SOURCE_FREEZE_FIXED_PATH_FAILED:{error}"
        ) from error
    contracts = _load_contracts()
    paths = {
        "pre": root / "evidence/SIM13_V4B4G_PRE_RUN_PROTECTED_ASSET_SNAPSHOT_V1.json",
        "source": root / "evidence/SIM13_V4B4G_SOURCE_MANIFEST_SELF_EXCLUDED_V1.json",
        "reference": root / "evidence/SIM13_V4B4G_REFERENCE_FORCE_AND_ACQUISITION_V1.json",
        "schedule": root / "evidence/SIM13_V4B4G_REGISTERED_SCHEDULE_V1.json",
        "runtime": root / "evidence/SIM13_V4B4G_RUNTIME_ENVIRONMENT_V1.json",
        "a0_parent": root / "evidence/SIM13_V4B4G_A0_PARENT_REFERENCE_TRACES_V1.json",
        "provisional": root / "evidence/SIM13_V4B4G_PROVISIONAL_POST_CAMPAIGN_PROTECTED_ASSET_SNAPSHOT_V1.json",
        "summary": root / "results/SIM13_V4B4G_CAMPAIGN_SUMMARY_V1.json",
        "negative": root / "b4g_mutation_execution/SIM13_V4B4G_NEGATIVE_CONTROL_EVIDENCE_V1.json",
    }
    schemas = {
        "pre": "SIM13_V4B4G_PRE_RUN_PROTECTED_ASSET_SNAPSHOT_V1",
        "source": "SIM13_V4B4G_SOURCE_MANIFEST_SELF_EXCLUDED_V1",
        "reference": "SIM13_V4B4G_REFERENCE_FORCE_AND_ACQUISITION_V1",
        "schedule": "SIM13_V4B4G_REGISTERED_SCHEDULE_V1",
        "runtime": "SIM13_V4B4G_RUNTIME_ENVIRONMENT_V1",
        "a0_parent": "SIM13_V4B4G_A0_PARENT_REFERENCE_TRACES_V1",
        "provisional": (
            "SIM13_V4B4G_PROVISIONAL_POST_CAMPAIGN_"
            "PROTECTED_ASSET_SNAPSHOT_V1"
        ),
        "summary": "SIM13_V4B4G_CAMPAIGN_SUMMARY_V1",
        "negative": "SIM13_V4B4G_NEGATIVE_CONTROL_EVIDENCE_V1",
    }
    values = {
        name: _canonical_json(path, schemas[name])
        for name, path in paths.items()
    }
    _require_no_active_attempt_markers(root)
    if values["schedule"] != contracts["schedule"]:
        raise B4GPreauditPublicationError("POST_RUN_REGISTERED_SCHEDULE_DRIFT")
    if values["summary"].get("logical_slot_count") != 144:
        raise B4GPreauditPublicationError("POST_RUN_CAMPAIGN_NOT_EXACT_144")
    if (
        values["summary"].get("registered_domain_execution_integrity_pass") is not True
        or values["summary"].get("case_integrity_failures") != []
        or values["summary"].get("global_integrity_failures") != []
    ):
        raise B4GPreauditPublicationError("POST_RUN_CAMPAIGN_INTEGRITY_NOT_PASS")
    negative = values["negative"]
    negative_counts = negative.get("counts", {})
    if (
        negative.get("schema") != "SIM13_V4B4G_NEGATIVE_CONTROL_EVIDENCE_V1"
        or negative.get("all_65_subvariants_unique_hit_and_killed") is not True
        or negative_counts.get("executed_subvariants") != 65
        or negative_counts.get("killed_subvariants") != 65
        or negative_counts.get("unique_subvariants") != 65
        or len(negative.get("receipts", [])) != 65
    ):
        raise B4GPreauditPublicationError("POST_RUN_MUTATION_65_NOT_COMPLETE")

    terminal = Path(execution_source_freeze_terminal).resolve()
    expected_terminal_sha = str(
        expected_execution_source_freeze_terminal_sha256
    ).upper()
    identity = execution_identity(
        PROJECT_ROOT,
        PHASE_ROOT,
        execution_source_freeze_terminal=terminal,
        expected_execution_source_freeze_terminal_sha256=expected_terminal_sha,
    )
    if identity.get("execution_source_freeze", {}).get("pass") is not True:
        raise B4GPreauditPublicationError("POST_RUN_EXECUTION_SOURCE_FREEZE_NOT_PASS")
    source = values["source"]
    if source.get("identity") != identity:
        raise B4GPreauditPublicationError("POST_RUN_SOURCE_IDENTITY_DRIFT")
    if (
        values["summary"].get("expected_execution_source_freeze_terminal_sha256")
        != expected_terminal_sha
    ):
        raise B4GPreauditPublicationError("POST_RUN_SUMMARY_SOURCE_FREEZE_DRIFT")
    negative_binding = negative.get("source_binding", {})
    _verify_record_points_to(
        negative_binding.get("campaign_summary", {}), paths["summary"],
        project_root=PROJECT_ROOT, publication_root=root,
        label="POST_RUN_MUTATION_CAMPAIGN_SUMMARY",
    )
    _verify_record_points_to(
        negative_binding.get("execution_source_manifest", {}), paths["source"],
        project_root=PROJECT_ROOT, publication_root=root,
        label="POST_RUN_MUTATION_CAMPAIGN_SOURCE_MANIFEST",
    )
    _verify_record_points_to(
        negative_binding.get("execution_source_freeze_terminal", {}), terminal,
        project_root=PROJECT_ROOT, publication_root=root,
        label="POST_RUN_MUTATION_SOURCE_FREEZE",
    )
    if (
        negative_binding.get("execution_source_freeze_expected_terminal_sha256")
        != expected_terminal_sha
    ):
        raise B4GPreauditPublicationError(
            "POST_RUN_MUTATION_SOURCE_FREEZE_EXPECTED_SHA_DRIFT"
        )

    recursive = verify_recursive_parents(
        PROJECT_ROOT, PHASE_ROOT, contracts["bindings"],
    )
    recursive_sha = canonical_sha256(recursive)
    if (
        source.get("recursive_parent_verification") != recursive
        or values["summary"].get("pre_recursive_parent_identity_sha256")
        != recursive_sha
        or values["summary"].get("post_recursive_parent_identity_sha256")
        != recursive_sha
        or values["provisional"].get("recursive_parent_post_verification")
        != recursive
    ):
        raise B4GPreauditPublicationError("POST_RUN_RECURSIVE_PARENT_DAG_DRIFT")

    runtime = _runtime_identity()
    runtime_sha = canonical_sha256(runtime)
    if (
        values["runtime"].get("runtime_identity") != runtime
        or values["runtime"].get("runtime_identity_sha256") != runtime_sha
        or values["summary"].get("runtime_identity") != runtime
        or values["summary"].get("runtime_identity_sha256") != runtime_sha
        or values["provisional"].get("runtime_identity") != runtime
        or values["provisional"].get("runtime_identity_sha256") != runtime_sha
    ):
        raise B4GPreauditPublicationError("POST_RUN_RUNTIME_IDENTITY_DRIFT")

    protected = protected_snapshot(
        PROJECT_ROOT, PHASE_ROOT, contracts["bindings"], contracts["governance"],
    )
    for key, value in protected.items():
        if values["pre"].get(key) != value:
            raise B4GPreauditPublicationError(
                f"POST_RUN_PRE_PROTECTED_SNAPSHOT_DRIFT:{key}"
            )
    if values["provisional"].get("protected_snapshot") != protected:
        raise B4GPreauditPublicationError(
            "POST_RUN_PROVISIONAL_PROTECTED_SNAPSHOT_DRIFT"
        )

    a0_binding = values["summary"].get("a0_parent_reference_traces", {})
    if not isinstance(a0_binding, Mapping) or not isinstance(
        a0_binding.get("manifest"), Mapping,
    ):
        raise B4GPreauditPublicationError("POST_RUN_A0_PARENT_BINDING_MISSING")
    a0 = _verify_a0_parent_trace_bundle(a0_binding["manifest"])
    if (
        a0 != a0_binding
        or source.get("a0_parent_reference_traces") != a0
        or values["pre"].get("a0_parent_reference_trace_manifest")
        != a0["manifest"]
        or values["pre"].get("a0_parent_reference_trace_bindings_sha256")
        != a0["trace_bindings_sha256"]
        or values["provisional"].get(
            "a0_parent_reference_trace_post_verification"
        ) != a0
    ):
        raise B4GPreauditPublicationError("POST_RUN_A0_PARENT_TRACE_DRIFT")

    reference = campaign.recompute_reference_force()
    reference_dict = reference.as_dict()
    if (
        values["reference"].get("native_recomputation") != reference_dict
        or values["reference"].get("one_common_Q_ref_per_finger_N")
        != reference.individual_finger_reference_force_n
        or values["summary"].get("one_common_Q_ref_per_finger_N")
        != reference.individual_finger_reference_force_n
    ):
        raise B4GPreauditPublicationError("POST_RUN_REFERENCE_FORCE_DRIFT")

    metadata_index = values["summary"].get("case_metadata_index", [])
    if not isinstance(metadata_index, list) or len(metadata_index) != 144:
        raise B4GPreauditPublicationError("POST_RUN_CASE_METADATA_INDEX_NOT_144")
    metadata: list[dict[str, Any]] = []
    executed_npz_count = 0
    for expected_slot, index_row in enumerate(metadata_index):
        metadata_path = _resolve_declared(
            index_row.get("metadata_path"), project_root=PROJECT_ROOT,
            publication_root=root,
        )
        item = _canonical_json(metadata_path)
        if (
            index_row.get("slot_index") != expected_slot
            or item.get("slot_index") != expected_slot
            or index_row.get("case_id") != item.get("case_id")
            or index_row.get("metadata_sha256") != sha256_file(metadata_path)
        ):
            raise B4GPreauditPublicationError(
                f"POST_RUN_CASE_METADATA_INDEX_DRIFT:{expected_slot}"
            )
        metadata.append(item)
        if item.get("npz_path") is not None:
            executed_npz_count += 1
    raw_inventory = _verify_raw_case_inventory(
        root / "evidence/raw_cases", contracts["schedule"], metadata,
        phase="FINAL_POST_RUN",
    )

    publication_order = contracts["schema"].get("publication_order", [])
    post_name = POST_RELATIVE_PATH.name
    if post_name not in publication_order:
        raise B4GPreauditPublicationError("POST_RUN_PUBLICATION_ORDER_CONTRACT_DRIFT")
    post_prefix = publication_order[:publication_order.index(post_name) + 1]
    campaign_record = _record(
        paths["summary"], "CAMPAIGN_SUMMARY", project_root=PROJECT_ROOT,
    )
    negative_record = _record(
        paths["negative"], "NEGATIVE_CONTROL_EVIDENCE", project_root=PROJECT_ROOT,
    )
    checks = {
        "execution_source_freeze_reverified": True,
        "local_source_identity_reverified": True,
        "recursive_parent_dag_reverified": True,
        "protected_assets_reverified": True,
        "runtime_identity_reverified": True,
        "a0_parent_traces_reverified": True,
        "reference_force_recomputed": True,
        "registered_144_raw_inventory_reverified": True,
        "mutation_65_completion_reverified": True,
        "no_active_invalidation_supersession_or_incomplete_marker": True,
    }
    post = {
        "schema": "SIM13_V4B4G_POST_RUN_PROTECTED_ASSET_SNAPSHOT_V1",
        "classification": "FINAL_POST_RUN_BEFORE_READ_ONLY_VALIDATOR",
        "final_post_run": True,
        "negative_controls_completed": True,
        "final_signing_authorized": False,
        "publication_order": post_prefix,
        "campaign_summary_dependency": campaign_record,
        "negative_control_dependency": negative_record,
        "source_identity_reverification": identity,
        "source_identity_sha256": canonical_sha256(identity),
        "recursive_parent_post_verification": recursive,
        "recursive_parent_post_identity_sha256": recursive_sha,
        "runtime_identity": runtime,
        "runtime_identity_sha256": runtime_sha,
        "a0_parent_reference_trace_post_verification": a0,
        "a0_parent_reference_trace_manifest_sha256": a0["manifest"]["sha256"],
        "reference_force_reverification": reference_dict,
        "raw_case_inventory_post_run": raw_inventory,
        "reverification_checks": checks,
        **protected,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    return {
        "post_run_snapshot": post,
        "paths": paths,
        "values": values,
        "metadata": metadata,
        "executed_npz_count": executed_npz_count,
        "a0_parent_manifest": values["a0_parent"],
        "source_freeze_terminal": terminal,
        "expected_source_freeze_terminal_sha256": expected_terminal_sha,
        "contracts": contracts,
    }


def _validated_report_payload(report: Any) -> dict[str, Any]:
    payload = report.as_dict() if hasattr(report, "as_dict") else dict(report)
    required = {
        "schema", "mode", "status", "passed", "final", "audited",
        "validator_pass_claimed", "campaign_or_scientific_credit",
        "check_count", "failure_count", "failures", "observations",
        "writes_performed", "solver_runner_mutation_modules_imported",
    }
    if set(payload) != required:
        raise B4GPreauditPublicationError("FULL_VALIDATION_REPORT_FIELD_SET_MISMATCH")
    if not (
        payload["schema"] == "SIM13_V4B4G_READ_ONLY_VALIDATION_REPORT_V1"
        and payload["mode"] == "full"
        and payload["status"] == "PASS"
        and payload["passed"] is True
        and payload["final"] is False
        and payload["audited"] is False
        and payload["validator_pass_claimed"] is False
        and payload["campaign_or_scientific_credit"] is False
        and isinstance(payload["check_count"], int)
        and not isinstance(payload["check_count"], bool)
        and payload["check_count"] > 0
        and payload["failure_count"] == 0
        and payload["failures"] == []
        and isinstance(payload["observations"], dict)
        and payload["writes_performed"] is False
        and payload["solver_runner_mutation_modules_imported"] is False
    ):
        raise B4GPreauditPublicationError("FULL_VALIDATION_NOT_EXACT_PASS")
    return payload


def _add_unique_record(
    records: list[dict[str, Any]],
    by_casefold_path: dict[str, dict[str, Any]],
    path: Path,
    role: str,
    *,
    project_root: Path,
) -> None:
    row = _record(path, role, project_root=project_root)
    key = row["path"].casefold()
    existing = by_casefold_path.get(key)
    if existing is not None:
        if (
            existing["path"] != row["path"]
            or existing["bytes"] != row["bytes"]
            or existing["sha256"] != row["sha256"]
        ):
            raise B4GPreauditPublicationError(
                f"EVIDENCE_MANIFEST_CASEFOLD_OR_IDENTITY_COLLISION:{row['path']}"
            )
        return
    records.append(row)
    by_casefold_path[key] = row


def _build_evidence_records(
    *,
    output_root: Path,
    project_root: Path,
    reverified: Mapping[str, Any],
    post_path: Path,
    validation_path: Path | None,
) -> list[dict[str, Any]]:
    root = Path(output_root).resolve()
    records: list[dict[str, Any]] = []
    by_path: dict[str, dict[str, Any]] = {}
    for relative, role in _DIRECT_RECORDS:
        _add_unique_record(
            records, by_path, root / relative, role, project_root=project_root,
        )
    _add_unique_record(
        records, by_path, post_path, "POST_RUN_PROTECTED_ASSET_SNAPSHOT",
        project_root=project_root,
    )
    if validation_path is not None:
        _add_unique_record(
            records, by_path, validation_path, "EXECUTION_VALIDATION_FULL",
            project_root=project_root,
        )
    terminal = Path(reverified["source_freeze_terminal"])
    _add_unique_record(
        records, by_path, terminal, "EXECUTION_SOURCE_FREEZE_TERMINAL",
        project_root=project_root,
    )

    summary = reverified["values"]["summary"]
    expected_executed_npz_count = int(reverified["executed_npz_count"])
    for row in summary["case_metadata_index"]:
        metadata_path = _resolve_declared(
            row["metadata_path"], project_root=project_root,
            publication_root=root,
        )
        metadata = _canonical_json(metadata_path)
        _add_unique_record(
            records, by_path, metadata_path, "REGISTERED_CASE_METADATA",
            project_root=project_root,
        )
        if metadata.get("npz_path") is not None:
            npz_path = _resolve_declared(
                metadata["npz_path"], project_root=project_root,
                publication_root=root,
            )
            if (
                metadata.get("npz_bytes") != npz_path.stat().st_size
                or metadata.get("npz_sha256") != sha256_file(npz_path)
            ):
                raise B4GPreauditPublicationError(
                    f"MANIFEST_EXECUTED_CASE_NPZ_BINDING_DRIFT:{metadata.get('case_id')}"
                )
            _add_unique_record(
                records, by_path, npz_path, "EXECUTED_CASE_NPZ",
                project_root=project_root,
            )

    a0_parent = reverified["a0_parent_manifest"]
    for trace in a0_parent["traces"]:
        npz_path = _resolve_declared(
            trace["npz_path"], project_root=project_root,
            publication_root=root,
        )
        if (
            trace.get("npz_bytes") != npz_path.stat().st_size
            or trace.get("npz_sha256") != sha256_file(npz_path)
        ):
            raise B4GPreauditPublicationError(
                f"MANIFEST_A0_PARENT_NPZ_BINDING_DRIFT:{trace.get('lane_id')}"
            )
        _add_unique_record(
            records, by_path, npz_path, "A0_PARENT_TRACE_NPZ",
            project_root=project_root,
        )

    negative = reverified["values"]["negative"]
    receipts = negative.get("receipts", [])
    if len(receipts) != 65:
        raise B4GPreauditPublicationError("MANIFEST_MUTATION_RECEIPT_COUNT_NOT_65")
    bundle_paths: list[Path] = []
    for receipt in receipts:
        for field, role in (
            ("base_artifact", "MUTATION_BASE_BUNDLE"),
            ("mutant_artifact", "MUTATION_MUTANT_BUNDLE"),
            ("patch_artifact", "MUTATION_PATCH_BUNDLE"),
        ):
            artifact = receipt.get(field, {})
            path = _resolve_declared(
                artifact.get("path"), project_root=project_root,
                publication_root=root,
            )
            if (
                artifact.get("bytes") != path.stat().st_size
                or artifact.get("sha256") != sha256_file(path)
            ):
                raise B4GPreauditPublicationError(
                    f"MANIFEST_MUTATION_BUNDLE_BINDING_DRIFT:{receipt.get('receipt_id')}:{field}"
                )
            _canonical_json(path)
            _add_unique_record(
                records, by_path, path, role, project_root=project_root,
            )
            if field != "patch_artifact":
                bundle_paths.append(path)
    if len(bundle_paths) != 130:
        raise B4GPreauditPublicationError("MANIFEST_BASE_MUTANT_BUNDLE_COUNT_NOT_130")
    for bundle_path in bundle_paths:
        bundle = _canonical_json(bundle_path)
        artifact_records = bundle.get("artifact_records", [])
        if not isinstance(artifact_records, list) or len(artifact_records) < 2:
            raise B4GPreauditPublicationError(
                f"MANIFEST_MUTATION_ARTIFACT_RECORDS_INCOMPLETE:{bundle_path.name}"
            )
        for artifact in artifact_records:
            dependency = _resolve_declared(
                artifact.get("path"), project_root=project_root,
                publication_root=root,
            )
            if (
                artifact.get("bytes") != dependency.stat().st_size
                or artifact.get("sha256") != sha256_file(dependency)
            ):
                raise B4GPreauditPublicationError(
                    f"MANIFEST_MUTATION_ARTIFACT_DEPENDENCY_DRIFT:{dependency}"
                )
            _add_unique_record(
                records, by_path, dependency, "MUTATION_ARTIFACT_DEPENDENCY",
                project_root=project_root,
            )

    records.sort(key=lambda row: (row["path"].casefold(), row["path"]))
    if Counter(row["role"] for row in records).get(
        "EXECUTED_CASE_NPZ", 0,
    ) != expected_executed_npz_count:
        raise B4GPreauditPublicationError(
            "EVIDENCE_MANIFEST_EXECUTED_CASE_NPZ_NOT_EXACT_METADATA_SET"
        )
    paths = [row["path"] for row in records]
    if len(paths) != len(set(paths)) or len(paths) != len({value.casefold() for value in paths}):
        raise B4GPreauditPublicationError("EVIDENCE_MANIFEST_DUPLICATE_PATH")
    return records


def _evidence_manifest_payload(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = [dict(row) for row in records]
    expected_record_fields = {"path", "role", "bytes", "sha256"}
    for index, row in enumerate(rows):
        if set(row) != expected_record_fields:
            raise B4GPreauditPublicationError(
                f"EVIDENCE_MANIFEST_RECORD_FIELDS:{index}"
            )
        if (
            not isinstance(row["path"], str)
            or not isinstance(row["role"], str)
            or not row["role"]
            or not isinstance(row["bytes"], int)
            or isinstance(row["bytes"], bool)
            or row["bytes"] < 0
            or not isinstance(row["sha256"], str)
            or len(row["sha256"]) != 64
            or row["sha256"] != row["sha256"].upper()
            or any(character not in "0123456789ABCDEF" for character in row["sha256"])
        ):
            raise B4GPreauditPublicationError(
                f"EVIDENCE_MANIFEST_RECORD_IDENTITY:{index}"
            )
    role_counts = Counter(row.get("role") for row in rows)
    for role, count in _FIXED_ROLE_COUNTS.items():
        if role_counts.get(role, 0) != count:
            raise B4GPreauditPublicationError(
                f"EVIDENCE_MANIFEST_ROLE_COUNT:{role}:"
                f"expected={count}:actual={role_counts.get(role, 0)}"
            )
    allowed_roles = set(_FIXED_ROLE_COUNTS) | {
        "EXECUTED_CASE_NPZ", "MUTATION_ARTIFACT_DEPENDENCY",
    }
    unknown = sorted(set(role_counts) - allowed_roles)
    if unknown:
        raise B4GPreauditPublicationError(
            f"EVIDENCE_MANIFEST_UNKNOWN_ROLE:{unknown[0]}"
        )
    if role_counts.get("EXECUTED_CASE_NPZ", 0) < 120:
        raise B4GPreauditPublicationError(
            "EVIDENCE_MANIFEST_EXECUTED_CASE_NPZ_COUNT_TOO_SMALL"
        )
    if role_counts.get("MUTATION_ARTIFACT_DEPENDENCY", 0) < 1:
        raise B4GPreauditPublicationError(
            "EVIDENCE_MANIFEST_MUTATION_DEPENDENCY_SET_EMPTY"
        )
    paths = [str(row.get("path", "")) for row in rows]
    if (
        len(paths) != len(set(paths))
        or len(paths) != len({path.casefold() for path in paths})
        or any(Path(path).is_absolute() or "\\" in path for path in paths)
        or any(part in {"", ".", ".."} for path in paths for part in path.split("/"))
    ):
        raise B4GPreauditPublicationError("EVIDENCE_MANIFEST_PATH_SET_INVALID")
    if rows != sorted(
        rows, key=lambda row: (row["path"].casefold(), row["path"]),
    ):
        raise B4GPreauditPublicationError("EVIDENCE_MANIFEST_RECORDS_NOT_SORTED")
    forbidden_names = {Path(value).name.casefold() for value in _EXCLUDED_FUTURE_OUTPUTS}
    if any(Path(path).name.casefold() in forbidden_names for path in paths):
        raise B4GPreauditPublicationError("EVIDENCE_MANIFEST_NOT_SELF_EXCLUDED")
    transient_names = {
        name.casefold()
        for name in (
            "SIM13_V4B4G_MUTATION_HARNESS_SMOKE_V1.json",
            "SIM13_V4B4G_MUTATION_EXECUTION_INCOMPLETE_V1.json",
            "SIM13_V4B4G_EXECUTION_INVALIDATED_V1.json",
            "SIM13_V4B4G_PRIOR_FINAL_CREDIT_SUPERSEDED_V1.json",
        )
    }
    if any(
        Path(path).name.casefold() in transient_names
        or any(part.casefold().startswith(".pytest") for part in path.split("/"))
        for path in paths
    ):
        raise B4GPreauditPublicationError(
            "EVIDENCE_MANIFEST_TRANSIENT_DEPENDENCY_FORBIDDEN"
        )
    source = next(
        row for row in rows if row["role"] == "EXECUTION_SOURCE_FREEZE_TERMINAL"
    )
    validation = next(
        row for row in rows if row["role"] == "EXECUTION_VALIDATION_FULL"
    )
    return {
        "schema": "SIM13_V4B4G_EVIDENCE_MANIFEST_SELF_EXCLUDED_V1",
        "scope": "SYNTHETIC_REGISTERED_DOMAIN_EXECUTION_AND_AUDIT_ONLY",
        "self_excluded": True,
        "acyclic": True,
        "source_freeze_terminal": dict(source),
        "execution_validation": dict(validation),
        "records": rows,
        "record_count": len(rows),
        "records_canonical_sha256": canonical_sha256(rows),
        "excluded_future_outputs": list(_EXCLUDED_FUTURE_OUTPUTS),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _preaudit_payload(
    *,
    output_root: Path,
    project_root: Path,
    reverified: Mapping[str, Any],
    validation_path: Path,
    manifest_path: Path,
    post_path: Path,
) -> dict[str, Any]:
    root = Path(output_root).resolve()
    contracts = reverified["contracts"]
    inputs = {
        "execution_validation": _record(
            validation_path, "EXECUTION_VALIDATION_FULL", project_root=project_root,
        ),
        "evidence_manifest": _record(
            manifest_path, "EVIDENCE_MANIFEST_SELF_EXCLUDED",
            project_root=project_root,
        ),
        "post_run_snapshot": _record(
            post_path, "POST_RUN_PROTECTED_ASSET_SNAPSHOT",
            project_root=project_root,
        ),
        "campaign_summary": _record(
            root / "results/SIM13_V4B4G_CAMPAIGN_SUMMARY_V1.json",
            "CAMPAIGN_SUMMARY", project_root=project_root,
        ),
        "negative_control_evidence": _record(
            root / "b4g_mutation_execution/SIM13_V4B4G_NEGATIVE_CONTROL_EVIDENCE_V1.json",
            "NEGATIVE_CONTROL_EVIDENCE", project_root=project_root,
        ),
        "execution_source_freeze_terminal": _record(
            Path(reverified["source_freeze_terminal"]),
            "EXECUTION_SOURCE_FREEZE_TERMINAL", project_root=project_root,
        ),
    }
    governance = {
        "required_false": contracts["governance"]["required_false"],
        "required_null_physical_inputs": {
            name: None
            for name in contracts["governance"]["required_null_physical_inputs"]
        },
        "formal_sim13_v2_state_unchanged": contracts["governance"][
            "formal_sim13_v2_state_unchanged"
        ],
        "memory": contracts["run_spec"]["memory"],
        "physical_current_formal_owner_production_release_next_stage_hold": True,
    }
    checks = {
        "validation_full_pass": True,
        "manifest_self_excluded_and_acyclic": True,
        "publication_prefix_complete": True,
        "source_freeze_reverified": True,
        "protected_assets_reverified": True,
        "a0_pre_post_reverified": True,
        "registered_144_complete": True,
        "mutation_65_complete": True,
        "governance_holds_reverified": True,
    }
    return {
        "schema": "SIM13_V4B4G_PREAUDIT_GATE_V1",
        "scope": "SYNTHETIC_REGISTERED_DOMAIN_EXECUTION_AND_AUDIT_ONLY",
        "status": "PASS_READY_FOR_INDEPENDENT_AUDIT",
        "ready_for_independent_audit": True,
        "final": False,
        "audited": False,
        "inputs": inputs,
        "checks": checks,
        "governance": governance,
        "claim_boundary": contracts["schema"]["claim_boundary"],
    }


def publish_preaudit(
    *,
    execution_source_freeze_terminal: Path,
    expected_execution_source_freeze_terminal_sha256: str,
    output_root: Path = PHASE_ROOT,
    reverify_fn: Callable[..., Mapping[str, Any]] | None = None,
    validator_fn: Callable[..., Any] | None = None,
    record_builder_fn: Callable[..., list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Publish POST_RUN -> validation -> manifest -> PREAUDIT, or no stale finals."""

    requested_root = Path(output_root).resolve()
    if requested_root != PHASE_ROOT.resolve():
        raise B4GPreauditPublicationError(
            "FORMAL_PREAUDIT_PUBLISHER_REQUIRES_PHASE_ROOT"
        )
    root = _safe_root(requested_root)
    initial_removed = _cleanup_stale_audit_and_final_outputs(root)
    post_path = _safe_target(root, POST_RELATIVE_PATH)
    validation_path = _safe_target(root, VALIDATION_RELATIVE_PATH)
    manifest_path = _safe_target(root, MANIFEST_RELATIVE_PATH)
    preaudit_path = _safe_target(root, PREAUDIT_RELATIVE_PATH)
    reverify = _formal_reverification if reverify_fn is None else reverify_fn
    validator = (
        _run_full_validator_subprocess if validator_fn is None else validator_fn
    )
    record_builder = (
        _build_evidence_records if record_builder_fn is None else record_builder_fn
    )
    try:
        reverified = dict(reverify(
            output_root=root,
            execution_source_freeze_terminal=Path(
                execution_source_freeze_terminal
            ),
            expected_execution_source_freeze_terminal_sha256=(
                expected_execution_source_freeze_terminal_sha256
            ),
        ))
        post = dict(reverified["post_run_snapshot"])
        atomic_write_json(post_path, post)
        if _canonical_json(post_path) != post:
            raise B4GPreauditPublicationError("POST_RUN_ATOMIC_PUBLICATION_MISMATCH")

        pre_validator_records = record_builder(
            output_root=root,
            project_root=PROJECT_ROOT,
            reverified=reverified,
            post_path=post_path,
            validation_path=None,
        )

        validation = _validated_report_payload(validator(mode="full"))
        post_validator_reverified = dict(reverify(
            output_root=root,
            execution_source_freeze_terminal=Path(
                execution_source_freeze_terminal
            ),
            expected_execution_source_freeze_terminal_sha256=(
                expected_execution_source_freeze_terminal_sha256
            ),
        ))
        post_validator_records = record_builder(
            output_root=root,
            project_root=PROJECT_ROOT,
            reverified=post_validator_reverified,
            post_path=post_path,
            validation_path=None,
        )
        if (
            post_validator_reverified != reverified
            or post_validator_records != pre_validator_records
            or _canonical_json(post_path) != post
        ):
            raise B4GPreauditPublicationError(
                "POST_VALIDATOR_AUTHORITATIVE_EVIDENCE_IDENTITY_DRIFT"
            )
        atomic_write_json(validation_path, validation)
        if _canonical_json(validation_path) != validation:
            raise B4GPreauditPublicationError(
                "EXECUTION_VALIDATION_ATOMIC_PUBLICATION_MISMATCH"
            )

        records = record_builder(
            output_root=root,
            project_root=PROJECT_ROOT,
            reverified=reverified,
            post_path=post_path,
            validation_path=validation_path,
        )
        if [
            row for row in records
            if row.get("role") != "EXECUTION_VALIDATION_FULL"
        ] != pre_validator_records:
            raise B4GPreauditPublicationError(
                "PRE_MANIFEST_AUTHORITATIVE_EVIDENCE_IDENTITY_DRIFT"
            )
        manifest = _evidence_manifest_payload(records)
        atomic_write_json(manifest_path, manifest)
        if _canonical_json(manifest_path) != manifest:
            raise B4GPreauditPublicationError(
                "EVIDENCE_MANIFEST_ATOMIC_PUBLICATION_MISMATCH"
            )
        manifest_record = _record(
            manifest_path, "EVIDENCE_MANIFEST_SELF_EXCLUDED",
            project_root=PROJECT_ROOT,
        )

        pre_preaudit_reverified = dict(reverify(
            output_root=root,
            execution_source_freeze_terminal=Path(
                execution_source_freeze_terminal
            ),
            expected_execution_source_freeze_terminal_sha256=(
                expected_execution_source_freeze_terminal_sha256
            ),
        ))
        pre_preaudit_records = record_builder(
            output_root=root,
            project_root=PROJECT_ROOT,
            reverified=pre_preaudit_reverified,
            post_path=post_path,
            validation_path=validation_path,
        )
        if (
            pre_preaudit_reverified != reverified
            or pre_preaudit_records != records
            or _canonical_json(post_path) != post
            or _canonical_json(validation_path) != validation
            or _canonical_json(manifest_path) != manifest
        ):
            raise B4GPreauditPublicationError(
                "PRE_PREAUDIT_AUTHORITATIVE_EVIDENCE_IDENTITY_DRIFT"
            )

        preaudit = _preaudit_payload(
            output_root=root,
            project_root=PROJECT_ROOT,
            reverified=reverified,
            validation_path=validation_path,
            manifest_path=manifest_path,
            post_path=post_path,
        )
        def unique_record(role: str) -> dict[str, Any]:
            matching = [row for row in records if row.get("role") == role]
            if len(matching) != 1:
                raise B4GPreauditPublicationError(
                    f"PREAUDIT_INPUT_ROLE_NOT_UNIQUE:{role}"
                )
            return dict(matching[0])

        expected_preaudit_inputs = {
            "execution_validation": unique_record("EXECUTION_VALIDATION_FULL"),
            "evidence_manifest": manifest_record,
            "post_run_snapshot": unique_record(
                "POST_RUN_PROTECTED_ASSET_SNAPSHOT"
            ),
            "campaign_summary": unique_record("CAMPAIGN_SUMMARY"),
            "negative_control_evidence": unique_record(
                "NEGATIVE_CONTROL_EVIDENCE"
            ),
            "execution_source_freeze_terminal": unique_record(
                "EXECUTION_SOURCE_FREEZE_TERMINAL"
            ),
        }
        if preaudit.get("inputs") != expected_preaudit_inputs:
            raise B4GPreauditPublicationError(
                "PREAUDIT_INPUTS_NOT_EXACT_VERIFIED_IDENTITIES"
            )
        final_reverified = dict(reverify(
            output_root=root,
            execution_source_freeze_terminal=Path(
                execution_source_freeze_terminal
            ),
            expected_execution_source_freeze_terminal_sha256=(
                expected_execution_source_freeze_terminal_sha256
            ),
        ))
        final_records = record_builder(
            output_root=root,
            project_root=PROJECT_ROOT,
            reverified=final_reverified,
            post_path=post_path,
            validation_path=validation_path,
        )
        if (
            final_reverified != reverified
            or final_records != records
            or _record(
                manifest_path, "EVIDENCE_MANIFEST_SELF_EXCLUDED",
                project_root=PROJECT_ROOT,
            ) != manifest_record
            or _canonical_json(post_path) != post
            or _canonical_json(validation_path) != validation
            or _canonical_json(manifest_path) != manifest
        ):
            raise B4GPreauditPublicationError(
                "FINAL_PREAUDIT_INPUT_IDENTITY_DRIFT"
            )
        atomic_write_json(preaudit_path, preaudit)
        if _canonical_json(preaudit_path) != preaudit:
            raise B4GPreauditPublicationError(
                "PREAUDIT_GATE_ATOMIC_PUBLICATION_MISMATCH"
            )
        post_write_reverified = dict(reverify(
            output_root=root,
            execution_source_freeze_terminal=Path(
                execution_source_freeze_terminal
            ),
            expected_execution_source_freeze_terminal_sha256=(
                expected_execution_source_freeze_terminal_sha256
            ),
        ))
        post_write_records = record_builder(
            output_root=root,
            project_root=PROJECT_ROOT,
            reverified=post_write_reverified,
            post_path=post_path,
            validation_path=validation_path,
        )
        if (
            post_write_reverified != reverified
            or post_write_records != records
            or _record(
                manifest_path, "EVIDENCE_MANIFEST_SELF_EXCLUDED",
                project_root=PROJECT_ROOT,
            ) != manifest_record
            or _canonical_json(post_path) != post
            or _canonical_json(validation_path) != validation
            or _canonical_json(manifest_path) != manifest
            or _canonical_json(preaudit_path) != preaudit
        ):
            raise B4GPreauditPublicationError(
                "POST_PREAUDIT_PUBLICATION_INPUT_IDENTITY_DRIFT"
            )
        return {
            "schema": "SIM13_V4B4G_PREAUDIT_PUBLICATION_RECEIPT_V1",
            "status": "PASS_READY_FOR_INDEPENDENT_AUDIT",
            "post_run_snapshot": _record(
                post_path, "POST_RUN_PROTECTED_ASSET_SNAPSHOT",
                project_root=PROJECT_ROOT,
            ),
            "execution_validation": _record(
                validation_path, "EXECUTION_VALIDATION_FULL",
                project_root=PROJECT_ROOT,
            ),
            "evidence_manifest": _record(
                manifest_path, "EVIDENCE_MANIFEST_SELF_EXCLUDED",
                project_root=PROJECT_ROOT,
            ),
            "preaudit_gate": _record(
                preaudit_path, "PREAUDIT_GATE", project_root=PROJECT_ROOT,
            ),
            "initial_stale_final_artifacts_removed": initial_removed,
            "independent_audit_executed": False,
            "final_or_audited_credit": False,
            "claim_boundary": CLAIM_BOUNDARY,
        }
    except BaseException as failure:
        try:
            _cleanup_stale_audit_and_final_outputs(root)
        except BaseException as cleanup_failure:
            if hasattr(failure, "add_note"):
                failure.add_note(
                    f"B4G preaudit final cleanup also failed: {cleanup_failure}"
                )
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execution-source-freeze-terminal", type=Path, required=True,
    )
    parser.add_argument(
        "--expected-execution-source-freeze-terminal-sha256", required=True,
    )
    args = parser.parse_args(argv)
    receipt = publish_preaudit(
        execution_source_freeze_terminal=args.execution_source_freeze_terminal,
        expected_execution_source_freeze_terminal_sha256=(
            args.expected_execution_source_freeze_terminal_sha256
        ),
    )
    print(json.dumps(
        receipt, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
