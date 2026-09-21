"""Execute the frozen B4G 22-parent / 65-subvariant mutation audit.

This module is deliberately separate from the registered 144-slot campaign.
It mutates either a byte-bound raw artifact or an actually executed numerical
path and then applies the gate predicate named by the frozen mutation contract.
No result from this module can provide A1/A2, physical, current-system, formal,
Owner, production, release, or next-stage credit.

The lightweight ``--smoke`` mode exercises the source verifier, real RHS,
continuous-clearance classifier, schedule verifier, geometry-domain detector,
and (most importantly) the finite-event/non-zero-work prerequisite.  The
``--execute`` mode additionally requires the completed registered campaign and
publishes all 65 receipts.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

import numpy as np

from b4g_solver import campaign
from b4g_solver import forced_retraction as forced


PHASE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PHASE_ROOT.parents[3]
CONTRACT_ROOT = PHASE_ROOT / "contracts"
RESULT_ROOT = PHASE_ROOT / "results"
EVIDENCE_ROOT = PHASE_ROOT / "evidence"
RAW_CASE_ROOT = EVIDENCE_ROOT / "raw_cases"
OUTPUT_ROOT = PHASE_ROOT / "b4g_mutation_execution"
ARTIFACT_ROOT = OUTPUT_ROOT / "artifacts"

MUTATION_SPEC_PATH = CONTRACT_ROOT / "PHASE_B4G_MUTATION_HARNESS_SPEC_V1.json"
GOVERNANCE_PATH = CONTRACT_ROOT / "PHASE_B4G_GOVERNANCE_V1.json"
SCHEDULE_PATH = CONTRACT_ROOT / "PHASE_B4G_REGISTERED_SCHEDULE_V1.json"
SOURCE_BINDINGS_PATH = CONTRACT_ROOT / "PHASE_B4G_SOURCE_BINDINGS_V1.json"
PREREG_SOURCE_MANIFEST_PATH = RESULT_ROOT / "SIM13_V4B4G_PREREGISTRATION_SOURCE_MANIFEST_V1.json"
PREREG_GATE_PATH = RESULT_ROOT / "SIM13_V4B4G_PREREGISTRATION_GATE_V1.json"
PREREG_TERMINAL_PATH = RESULT_ROOT / "SIM13_V4B4G_PREREGISTRATION_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"
CAMPAIGN_SUMMARY_PATH = RESULT_ROOT / "SIM13_V4B4G_CAMPAIGN_SUMMARY_V1.json"
CAMPAIGN_SOURCE_MANIFEST_PATH = EVIDENCE_ROOT / "SIM13_V4B4G_SOURCE_MANIFEST_SELF_EXCLUDED_V1.json"
MUTATION_INTERCHANGE_PATH = PHASE_ROOT / "b4g_validation" / "PHASE_B4G_MUTATION_ARTIFACT_INTERCHANGE_V1.json"
INDEPENDENT_VALIDATOR_PATH = PHASE_ROOT / "b4g_validation" / "validator.py"

FULL_OUTPUT_PATH = OUTPUT_ROOT / "SIM13_V4B4G_NEGATIVE_CONTROL_EVIDENCE_V1.json"
SMOKE_OUTPUT_PATH = OUTPUT_ROOT / "SIM13_V4B4G_MUTATION_HARNESS_SMOKE_V1.json"
INCOMPLETE_OUTPUT_PATH = OUTPUT_ROOT / "SIM13_V4B4G_MUTATION_EXECUTION_INCOMPLETE_V1.json"
OUTPUT_ROOT_MARKER = ".b4g_mutation_output_root"
DOWNSTREAM_FINAL_RELATIVE_PATHS = (
    "results/SIM13_V4B4G_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json",
    "results/SIM13_V4B4G_AUDITED_GATE_V1.json",
    "evidence/SIM13_V4B4G_INDEPENDENT_AUDIT_RECEIPT_V1.json",
    "results/SIM13_V4B4G_PREAUDIT_GATE_V1.json",
    "evidence/SIM13_V4B4G_EVIDENCE_MANIFEST_SELF_EXCLUDED_V1.json",
    "evidence/SIM13_V4B4G_EXECUTION_VALIDATION_V1.json",
    "evidence/SIM13_V4B4G_POST_RUN_PROTECTED_ASSET_SNAPSHOT_V1.json",
)

EXPECTED_PREREG = {
    PREREG_SOURCE_MANIFEST_PATH: (7410, "04E559FC4F846DEC3429B5F37110EF128F8308A7B955C6BD1DD0BD3EC6F88FA4"),
    PREREG_GATE_PATH: (6476, "288D12EA9120055C46CAE6EC18B397303DB38423DCF92A3FD30D32BBDD215A7E"),
    PREREG_TERMINAL_PATH: (1404, "ED3FB03CAC4FA5C8A0758E1D97766D55D576B34870E43D0EBBF8991C6603553B"),
}

CLAIM_BOUNDARY = (
    "registered synthetic discrete-domain execution only; no physical, current-system, "
    "formal NC19, Owner, production or next-stage credit"
)
MUTATION_CREDIT_BOUNDARY = (
    "mutation replay evidence only; no A1/A2 outcome, physical, current-system, formal NC19, "
    "Owner, production, release or next-stage credit"
)


class MutationAuditError(RuntimeError):
    """Fail-closed contract, source, campaign, or mutation-audit error."""


def _read_json(path: Path) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise MutationAuditError(f"JSON_READ_FAILED:{path}") from error
    if not isinstance(value, dict):
        raise MutationAuditError(f"JSON_ROOT_NOT_OBJECT:{path}")
    return value


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [_jsonable(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _jsonable(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _canonical_sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest().upper()


def _file_record(path: Path, *, relative_to: Path = PROJECT_ROOT) -> dict[str, Any]:
    payload = path.read_bytes()
    try:
        relative = path.resolve().relative_to(relative_to.resolve()).as_posix()
    except ValueError:
        relative = path.resolve().as_posix()
    return {
        "path": relative,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest().upper(),
    }


def _atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        _jsonable(value), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ) + "\n"
    temporary = path.with_name(path.name + f".tmp.{os.getpid()}")
    temporary.write_text(payload, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp.{os.getpid()}")
    with temporary.open("wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _is_mutation_link_or_reparse(path: Path) -> bool:
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


def _require_mutation_root_chain_no_links(path: Path) -> Path:
    target = Path(os.path.abspath(path))
    current = Path(target.anchor)
    for part in target.parts[1:]:
        current = current / part
        if os.path.lexists(current) and _is_mutation_link_or_reparse(current):
            raise MutationAuditError(
                f"MUTATION_OUTPUT_ROOT_LINK_OR_REPARSE_FORBIDDEN:{current}"
            )
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


def _safe_output_root(output_root: Path) -> tuple[Path, bool]:
    requested = _require_mutation_root_chain_no_links(output_root)
    root = requested.resolve()
    formal = root == OUTPUT_ROOT.resolve()
    if root in {
        Path(root.anchor), PHASE_ROOT.resolve(), PROJECT_ROOT.resolve(),
        PROJECT_ROOT.resolve().parent,
    }:
        raise MutationAuditError("MUTATION_OUTPUT_ROOT_TOO_BROAD")
    if formal:
        try:
            root.relative_to(PHASE_ROOT.resolve())
        except ValueError as error:
            raise MutationAuditError("FORMAL_MUTATION_OUTPUT_OUTSIDE_PHASE") from error
    elif _paths_overlap(root, PHASE_ROOT):
        raise MutationAuditError("MUTATION_CUSTOM_OUTPUT_ROOT_OVERLAPS_PHASE_ROOT")
    marker = root / OUTPUT_ROOT_MARKER
    marker_text = "SIM13_V4B4G_MUTATION_OUTPUT_ROOT_V1\n"
    existed = root.exists()
    if existed and not root.is_dir():
        raise MutationAuditError("MUTATION_OUTPUT_ROOT_NOT_DIRECTORY")
    if not formal and existed and not os.path.lexists(marker):
        try:
            next(root.iterdir())
        except StopIteration:
            pass
        else:
            raise MutationAuditError(
                "MUTATION_EXISTING_NONEMPTY_OUTPUT_ROOT_REQUIRES_MARKER"
            )
    if os.path.lexists(marker):
        if _is_mutation_link_or_reparse(marker) or not marker.is_file():
            raise MutationAuditError("MUTATION_OUTPUT_ROOT_MARKER_NOT_PLAIN_FILE")
        if marker.read_text(encoding="utf-8") != marker_text:
            raise MutationAuditError("MUTATION_OUTPUT_ROOT_MARKER_MISMATCH")
    else:
        root.mkdir(parents=True, exist_ok=True)
        marker.write_text(marker_text, encoding="utf-8", newline="\n")
    return root, formal


def _revoke_downstream_final_credit() -> list[dict[str, Any]]:
    """Remove only later B4G publication artifacts, terminal first."""

    phase = PHASE_ROOT.resolve()
    removed: list[dict[str, Any]] = []
    for relative in DOWNSTREAM_FINAL_RELATIVE_PATHS:
        relative_path = Path(relative)
        target = phase.joinpath(*relative_path.parts)
        parent = phase
        parent_missing = False
        for part in relative_path.parts[:-1]:
            parent = parent / part
            if not os.path.lexists(parent):
                parent_missing = True
                break
            if _is_mutation_link_or_reparse(parent) or not parent.is_dir():
                raise MutationAuditError(
                    f"MUTATION_DOWNSTREAM_FINAL_PARENT_UNSAFE:{target}"
                )
        if parent_missing:
            continue
        if not os.path.lexists(target):
            continue
        if _is_mutation_link_or_reparse(target):
            removed.append({
                "path": relative,
                "bytes": target.lstat().st_size,
                "sha256": None,
                "object_type": (
                    "SYMLINK" if target.is_symlink() else "REPARSE_POINT"
                ),
            })
            target.unlink()
        elif target.is_file():
            removed.append({
                "path": relative,
                "bytes": target.stat().st_size,
                "sha256": _file_record(target)["sha256"],
                "object_type": "REGULAR_FILE",
            })
            target.unlink()
        else:
            raise MutationAuditError(
                f"MUTATION_DOWNSTREAM_FINAL_NOT_FILE_OR_SYMLINK:{target}"
            )
    return removed


def _bootstrap_attempt(output_root: Path, *, mode: str) -> Path:
    """Invalidate owned stale outputs before constructing the audit context."""

    root, formal = _safe_output_root(output_root)
    if mode == "SMOKE" and formal:
        raise MutationAuditError(
            "MUTATION_SMOKE_REQUIRES_EXPLICIT_NONFORMAL_OUTPUT_ROOT"
        )
    if mode == "FULL_65":
        downstream_removed = (
            _revoke_downstream_final_credit() if formal else []
        )
        final_path = root / FULL_OUTPUT_PATH.name
        if final_path.parent.resolve() != root or final_path.name != FULL_OUTPUT_PATH.name:
            raise MutationAuditError("MUTATION_STALE_FINAL_TARGET_INVALID")
        if os.path.lexists(final_path):
            if (
                not _is_mutation_link_or_reparse(final_path)
                and not final_path.is_file()
            ):
                raise MutationAuditError("MUTATION_STALE_FINAL_TARGET_INVALID")
            final_path.unlink()
        _atomic_write_json(root / INCOMPLETE_OUTPUT_PATH.name, {
            "schema": "SIM13_V4B4G_MUTATION_EXECUTION_INCOMPLETE_V1",
            "status": "INCOMPLETE",
            "mode": "FULL_65",
            "final": False,
            "audited": False,
            "validator_pass_claimed": False,
            "formal_downstream_final_credit_revoked": bool(formal),
            "downstream_final_artifacts_removed": downstream_removed,
            "claim_boundary": MUTATION_CREDIT_BOUNDARY,
        })
    for name in ("artifacts", "underlying"):
        target = root / name
        if target.parent.resolve() != root or target.name != name:
            raise MutationAuditError("MUTATION_CLEANUP_TARGET_NOT_EXACT_OWNED_CHILD")
        if not os.path.lexists(target):
            continue
        if _is_mutation_link_or_reparse(target):
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)
        else:
            raise MutationAuditError("MUTATION_CLEANUP_TARGET_NOT_OWNED_DIRECTORY")
    return root


@contextmanager
def _patched(obj: Any, name: str, replacement: Any) -> Iterator[None]:
    original = getattr(obj, name)
    setattr(obj, name, replacement)
    try:
        yield
    finally:
        setattr(obj, name, original)


@dataclass(frozen=True)
class MutationReceipt:
    receipt_id: str
    parent_id: str
    subvariant_index: int
    mutation_id: str
    target: Any
    nominal_input_sha256: str
    mutant_input_sha256: str
    real_path_hit: bool
    expected_gate: str
    killed: bool
    execution_detail: dict[str, Any]
    base_artifact: dict[str, Any]
    mutant_artifact: dict[str, Any]
    patch_artifact: dict[str, Any]
    replay: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return _jsonable(self.__dict__)


class MutationAudit:
    """Stateful, deterministic executor for the frozen mutation inventory."""

    def __init__(self, *, output_root: Path | None = None) -> None:
        self.spec = _read_json(MUTATION_SPEC_PATH)
        self.governance = _read_json(GOVERNANCE_PATH)
        self.schedule = campaign.load_registered_schedule(SCHEDULE_PATH)
        self.source_bindings = _read_json(SOURCE_BINDINGS_PATH)
        self.targets = self.spec["deterministic_targets_and_amplitudes"]
        self.variant_rows = self.spec["variants"]
        self.interchange = _read_json(MUTATION_INTERCHANGE_PATH)
        self._validate_frozen_contract()
        self.source_binding = self._verify_source_binding()
        self.receipts: list[MutationReceipt] = []
        self._fixture_cache: dict[str, Any] | None = None
        self._campaign_summary: dict[str, Any] | None = None
        self._metadata_cache: dict[str, tuple[dict[str, Any], Path]] | None = None
        requested_output = OUTPUT_ROOT if output_root is None else Path(output_root)
        self.output_root, self._formal_output = _safe_output_root(requested_output)
        self.artifact_root = self.output_root / "artifacts"
        self._source_manifest_path: Path | None = None

    def _ensure_safe_output_root(self) -> None:
        root, formal = _safe_output_root(self.output_root)
        if root != self.output_root or formal != self._formal_output:
            raise MutationAuditError("MUTATION_OUTPUT_ROOT_IDENTITY_CHANGED")

    def _output_path(self, name: str) -> Path:
        relative = Path(name)
        if relative.is_absolute() or len(relative.parts) != 1:
            raise MutationAuditError("MUTATION_OUTPUT_PATH_ESCAPE")
        path = self.output_root / relative.name
        if path.parent.resolve() != self.output_root:
            raise MutationAuditError("MUTATION_OUTPUT_PATH_ESCAPE")
        if os.path.lexists(path) and _is_mutation_link_or_reparse(path):
            raise MutationAuditError("MUTATION_OUTPUT_PATH_LINK_OR_REPARSE_FORBIDDEN")
        return path

    def _remove_owned_tree(self, name: str) -> None:
        target = self.output_root / name
        if target.parent != self.output_root or target.name not in {"artifacts", "underlying"}:
            raise MutationAuditError("MUTATION_CLEANUP_TARGET_NOT_EXACT_OWNED_CHILD")
        if not os.path.lexists(target):
            return
        if _is_mutation_link_or_reparse(target):
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)
        else:
            raise MutationAuditError("MUTATION_CLEANUP_TARGET_NOT_OWNED_DIRECTORY")

    def _prepare_attempt(self, *, mode: str) -> None:
        """Invalidate stale executor outputs before emitting any new bundle."""

        self.receipts.clear()
        self._fixture_cache = None
        _bootstrap_attempt(self.output_root, mode=mode)

    def _complete_attempt(self, final_path: Path) -> None:
        incomplete = self._output_path(INCOMPLETE_OUTPUT_PATH.name)
        if final_path.is_file() and incomplete.is_file():
            incomplete.unlink()

    def _validate_frozen_contract(self) -> None:
        parent_ids = [f"B4FNC{index:02d}" for index in range(1, 23)]
        if self.spec.get("schema") != "SIM13_V4B4G_MUTATION_HARNESS_SPEC_V1":
            raise MutationAuditError("MUTATION_SPEC_SCHEMA_MISMATCH")
        if self.spec.get("required_parent_ids") != parent_ids:
            raise MutationAuditError("MUTATION_PARENT_IDS_MISMATCH")
        counts = [int(row["count"]) for row in self.variant_rows]
        if counts != self.spec.get("subvariant_counts_by_parent") or sum(counts) != 65:
            raise MutationAuditError("MUTATION_COUNTS_MISMATCH")
        if int(self.spec.get("total_subvariants", -1)) != 65:
            raise MutationAuditError("MUTATION_TOTAL_MISMATCH")
        if self.spec.get("dictionary_flag_only_mutation_forbidden") is not True:
            raise MutationAuditError("REAL_PATH_REQUIREMENT_NOT_FROZEN")
        required = self.spec.get("each_receipt_requires")
        if required != [
            "nominal_input_sha256", "mutant_input_sha256", "real_path_hit",
            "expected_gate", "actual_failed_gate", "nominal_gate_sha256",
            "mutant_gate_sha256", "killed",
        ]:
            raise MutationAuditError("RECEIPT_SCHEMA_MISMATCH")
        if self.interchange.get("schema") != "SIM13_V4B4G_MUTATION_ARTIFACT_INTERCHANGE_V1":
            raise MutationAuditError("MUTATION_INTERCHANGE_SCHEMA_MISMATCH")
        resolution = self.interchange.get("receipt_replay_binding", {})
        if set(resolution.get("executor_forbidden_receipt_fields", [])) != {
            "actual_failed_gate", "nominal_gate_sha256", "mutant_gate_sha256",
        }:
            raise MutationAuditError("MUTATION_VALIDATOR_RESULT_BOUNDARY_MISMATCH")
        expected_map = self.interchange.get("replay_type_by_parent", {})
        if set(expected_map) != set(parent_ids):
            raise MutationAuditError("MUTATION_INTERCHANGE_PARENT_MAP_MISMATCH")

    def _verify_source_binding(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        for path, (expected_bytes, expected_sha) in EXPECTED_PREREG.items():
            record = _file_record(path)
            passed = record["bytes"] == expected_bytes and record["sha256"] == expected_sha
            checks.append({
                **record, "expected_bytes": expected_bytes,
                "expected_sha256": expected_sha, "passed": passed,
            })
            if not passed:
                raise MutationAuditError(f"PREREG_SOURCE_DRIFT:{path.name}")
        parent_checks: list[dict[str, Any]] = []
        for source in self.source_bindings.get("sources", []):
            path = PROJECT_ROOT / str(source["path"])
            record = _file_record(path)
            passed = (
                record["bytes"] == int(source["bytes"])
                and record["sha256"] == str(source["sha256"]).upper()
            )
            parent_checks.append({
                "source_id": source["id"], **record,
                "expected_bytes": int(source["bytes"]),
                "expected_sha256": str(source["sha256"]).upper(),
                "passed": passed,
            })
            if not passed:
                raise MutationAuditError(f"BOUND_PARENT_DRIFT:{source['id']}")
        return {
            "mutation_executor_sha256": _file_record(Path(__file__))["sha256"],
            "mutation_spec_sha256": _file_record(MUTATION_SPEC_PATH)["sha256"],
            "preregistration_source_manifest_sha256": EXPECTED_PREREG[PREREG_SOURCE_MANIFEST_PATH][1],
            "preregistration_gate_sha256": EXPECTED_PREREG[PREREG_GATE_PATH][1],
            "preregistration_terminal_sha256": EXPECTED_PREREG[PREREG_TERMINAL_PATH][1],
            "campaign_summary_sha256": None,
            "mutation_spec": _file_record(MUTATION_SPEC_PATH),
            "mutation_executor": _file_record(Path(__file__)),
            "governance_contract": _file_record(GOVERNANCE_PATH),
            "registered_schedule": _file_record(SCHEDULE_PATH),
            "preregistration_anchors": checks,
            "bound_parent_sources": parent_checks,
            "all_verified": True,
        }

    def _diagnostic_source_manifest(self) -> Path:
        path = self.output_root / "SIM13_V4B4G_MUTATION_SMOKE_SOURCE_MANIFEST_SELF_EXCLUDED_V1.json"
        rows = [
            {"role": role, **_file_record(source)}
            for role, source in (
                ("MUTATION_EXECUTOR", Path(__file__)),
                ("MUTATION_SPEC", MUTATION_SPEC_PATH),
                ("MUTATION_ARTIFACT_INTERCHANGE", MUTATION_INTERCHANGE_PATH),
                ("INDEPENDENT_VALIDATOR", INDEPENDENT_VALIDATOR_PATH),
            )
        ]
        payload = {
            "schema": "SIM13_V4B4G_MUTATION_SMOKE_SOURCE_MANIFEST_V1",
            "self_excluded": True,
            "diagnostic_only": True,
            "record_count": len(rows),
            "records": rows,
            "claim_boundary": MUTATION_CREDIT_BOUNDARY,
        }
        if path.is_file() and _read_json(path) != payload:
            raise MutationAuditError("MUTATION_SMOKE_SOURCE_MANIFEST_DRIFT")
        if not path.is_file():
            _atomic_write_json(path, payload)
        return path

    def _active_source_manifest(self) -> Path:
        if self._source_manifest_path is not None:
            return self._source_manifest_path
        if CAMPAIGN_SOURCE_MANIFEST_PATH.is_file():
            self._source_manifest_path = CAMPAIGN_SOURCE_MANIFEST_PATH
        elif self._formal_output:
            raise MutationAuditError("CAMPAIGN_EXECUTION_SOURCE_MANIFEST_REQUIRED")
        else:
            self._source_manifest_path = self._diagnostic_source_manifest()
        return self._source_manifest_path

    def _underlying_records(
        self,
        records: Sequence[tuple[str, Path]],
    ) -> list[dict[str, Any]]:
        source_manifest = self._active_source_manifest()
        rows = [{"role": "EXECUTION_SOURCE_MANIFEST", **_file_record(source_manifest)}]
        seen = {source_manifest.resolve()}
        for role, path in records:
            resolved = Path(path).resolve()
            if resolved in seen:
                continue
            if not resolved.is_file():
                raise MutationAuditError(f"UNDERLYING_ARTIFACT_MISSING:{resolved}")
            seen.add(resolved)
            rows.append({"role": role, **_file_record(resolved)})
        return rows

    @staticmethod
    def _decode_pointer(pointer: str) -> list[str]:
        if not isinstance(pointer, str) or not pointer.startswith("/"):
            raise MutationAuditError(f"RFC6902_POINTER_INVALID:{pointer}")
        return [token.replace("~1", "/").replace("~0", "~") for token in pointer[1:].split("/")]

    @classmethod
    def _apply_patch(cls, base: Mapping[str, Any], operations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        result: Any = deepcopy(base)
        for operation in operations:
            op = operation.get("op")
            if op not in {"add", "remove", "replace"}:
                raise MutationAuditError("RFC6902_OPERATION_FORBIDDEN")
            tokens = cls._decode_pointer(str(operation.get("path")))
            container: Any = result
            for token in tokens[:-1]:
                container = container[int(token)] if isinstance(container, list) else container[token]
            token = tokens[-1]
            if isinstance(container, list):
                if op == "add" and token == "-":
                    container.append(deepcopy(operation["value"]))
                elif op == "add":
                    container.insert(int(token), deepcopy(operation["value"]))
                elif op == "replace":
                    container[int(token)] = deepcopy(operation["value"])
                else:
                    del container[int(token)]
            elif isinstance(container, dict):
                if op in {"add", "replace"}:
                    container[token] = deepcopy(operation["value"])
                else:
                    del container[token]
            else:
                raise MutationAuditError("RFC6902_PATCH_TARGET_SCALAR")
        if not isinstance(result, dict):
            raise MutationAuditError("RFC6902_PATCH_RESULT_NOT_OBJECT")
        return result

    def _add(
        self,
        parent_id: str,
        subvariant_index: int,
        target: Any,
        base_payload: Mapping[str, Any],
        mutant_payload: Mapping[str, Any],
        operations: Sequence[Mapping[str, Any]],
        *,
        underlying_records: Sequence[tuple[str, Path]],
        execution_mode: str,
        real_path_id: str,
        real_path_hit: bool,
        detail: Mapping[str, Any],
    ) -> None:
        row = self.variant_rows[int(parent_id[-2:]) - 1]
        mutation_id = str(row["id"])
        expected_gate = str(row["expected_gate"])
        replay_type = str(self.interchange["replay_type_by_parent"][parent_id])
        if not (1 <= int(subvariant_index) <= int(row["count"])):
            raise MutationAuditError(f"SUBVARIANT_INDEX_OUT_OF_RANGE:{parent_id}:{subvariant_index}")
        operation_paths = [str(operation.get("path")) for operation in operations]
        expected_target = operation_paths[0] if len(operation_paths) == 1 else operation_paths
        if target != expected_target:
            raise MutationAuditError(f"PATCH_TARGET_NOT_OPERATION_POINTERS:{parent_id}:{subvariant_index}")
        target_token = "__".join(operation_paths)
        receipt_id = (
            f"{parent_id}__SV{subvariant_index:02d}__"
            f"{re.sub('[^A-Za-z0-9]+', '_', target_token).strip('_').upper()}"
        )
        artifact_records = self._underlying_records(underlying_records)
        if len(artifact_records) < 2:
            raise MutationAuditError(f"UNDERLYING_ARTIFACTS_INCOMPLETE:{parent_id}")
        producer = _file_record(Path(__file__))
        provenance = {
            "producer_entrypoint_path": producer["path"],
            "producer_entrypoint_sha256": producer["sha256"],
            "execution_mode": execution_mode,
            "real_path_id": real_path_id,
            "source_manifest_sha256": artifact_records[0]["sha256"],
            "underlying_artifact_inventory_sha256": _canonical_sha(artifact_records),
        }
        common = {
            "schema": "SIM13_V4B4G_MUTATION_REPLAY_BUNDLE_V1",
            "receipt_id": receipt_id,
            "parent_id": parent_id,
            "mutation_id": mutation_id,
            "gate_id": expected_gate,
            "replay_type": replay_type,
            "execution_provenance": provenance,
            "artifact_records": artifact_records,
            "claim_boundary": MUTATION_CREDIT_BOUNDARY,
        }
        base_bundle = {**common, "payload": _jsonable(dict(base_payload))}
        mutant_bundle = {**common, "payload": _jsonable(dict(mutant_payload))}
        if self._apply_patch(base_bundle, operations) != mutant_bundle:
            raise MutationAuditError(f"PATCH_DOES_NOT_REPRODUCE_MUTANT:{receipt_id}")
        receipt_root = self.artifact_root / receipt_id
        base_path = receipt_root / "base.json"
        mutant_path = receipt_root / "mutant.json"
        patch_path = receipt_root / "patch.json"
        _atomic_write_json(base_path, base_bundle)
        _atomic_write_json(mutant_path, mutant_bundle)
        patch = {
            "schema": "SIM13_V4B4G_MUTATION_PATCH_V1",
            "receipt_id": receipt_id,
            "target": target,
            "format": "RFC6902_JSON_V1_RESTRICTED",
            "base_sha256": _file_record(base_path)["sha256"],
            "mutant_sha256": _file_record(mutant_path)["sha256"],
            "operations": _jsonable(list(operations)),
        }
        _atomic_write_json(patch_path, patch)
        def artifact_record(path: Path) -> dict[str, Any]:
            return {
                **_file_record(path),
                "media_type": "application/json",
                "replay_type": replay_type,
            }
        base_record = artifact_record(base_path)
        mutant_record = artifact_record(mutant_path)
        patch_record = artifact_record(patch_path)
        killed = bool(real_path_hit and base_record["sha256"] != mutant_record["sha256"])
        semantic_identity = {
            "parent_id": parent_id,
            "subvariant_index": int(subvariant_index),
            "mutation_id": mutation_id,
            "replay_type": replay_type,
            "target": _jsonable(target),
            "operations": _jsonable(list(operations)),
            "base_payload_sha256": _canonical_sha(base_payload),
            "mutant_payload_sha256": _canonical_sha(mutant_payload),
        }
        semantic_sha = _canonical_sha(semantic_identity)
        if any(
            row.execution_detail.get("semantic_mutation_sha256") == semantic_sha
            for row in self.receipts
        ):
            raise MutationAuditError("DUPLICATE_SEMANTIC_MUTATION_IDENTITY")
        self.receipts.append(MutationReceipt(
            receipt_id=receipt_id,
            parent_id=parent_id,
            subvariant_index=subvariant_index,
            mutation_id=mutation_id,
            target=_jsonable(target),
            nominal_input_sha256=base_record["sha256"],
            mutant_input_sha256=mutant_record["sha256"],
            real_path_hit=bool(real_path_hit),
            expected_gate=expected_gate,
            killed=killed,
            execution_detail={
                **dict(_jsonable(detail)),
                "semantic_mutation_sha256": semantic_sha,
                "semantic_identity_excludes_receipt_id": True,
                "artifact_interchange_schema": self.interchange["schema"],
                "patch_operation_count": len(operations),
                "harness_gate_result_authoritative": False,
            },
            base_artifact=base_record,
            mutant_artifact=mutant_record,
            patch_artifact=patch_record,
            replay={
                "schema": "SIM13_V4B4G_RECEIPT_INDEPENDENT_REPLAY_BINDING_V1",
                "evaluator_id": f"B4G_VALIDATION::{replay_type}",
                "independent_validator_path": _file_record(INDEPENDENT_VALIDATOR_PATH)["path"],
                "independent_validator_sha256": _file_record(INDEPENDENT_VALIDATOR_PATH)["sha256"],
            },
        ))

    @classmethod
    def _pointer_value(cls, value: Any, pointer: str) -> Any:
        current = value
        for token in cls._decode_pointer(pointer):
            current = current[int(token)] if isinstance(current, list) else current[token]
        return current

    @classmethod
    def _replace_operations(
        cls,
        mutant_bundle_payload: Mapping[str, Any],
        pointers: Sequence[str],
    ) -> list[dict[str, Any]]:
        wrapped = {"payload": _jsonable(dict(mutant_bundle_payload))}
        return [
            {"op": "replace", "path": pointer, "value": deepcopy(cls._pointer_value(wrapped, pointer))}
            for pointer in pointers
        ]

    def _add_replay(
        self,
        parent_id: str,
        subvariant_index: int,
        *,
        base_payload: Mapping[str, Any],
        mutant_payload: Mapping[str, Any],
        pointers: Sequence[str],
        underlying_records: Sequence[tuple[str, Path]],
        execution_mode: str,
        real_path_id: str,
        real_path_hit: bool,
        detail: Mapping[str, Any],
        operation: str = "replace",
    ) -> None:
        if operation == "replace":
            operations = self._replace_operations(mutant_payload, pointers)
        elif operation == "add" and len(pointers) == 1:
            operations = [{
                "op": "add", "path": pointers[0],
                "value": deepcopy(self._pointer_value({"payload": mutant_payload}, pointers[0][:-2] + "/" + str(len(self._pointer_value({"payload": mutant_payload}, pointers[0][:-2])) - 1)))
                if pointers[0].endswith("/-") else deepcopy(self._pointer_value({"payload": mutant_payload}, pointers[0])),
            }]
        else:
            raise MutationAuditError("UNSUPPORTED_SEMANTIC_PATCH_OPERATION")
        target: Any = pointers[0] if len(pointers) == 1 else list(pointers)
        self._add(
            parent_id, subvariant_index, target,
            base_payload, mutant_payload, operations,
            underlying_records=underlying_records,
            execution_mode=execution_mode,
            real_path_id=real_path_id,
            real_path_hit=real_path_hit,
            detail=detail,
        )

    def _registered_case(
        self, case_id: str,
    ) -> tuple[dict[str, Any], dict[str, np.ndarray], Path, Path]:
        _, metadata = self._load_campaign()
        if case_id not in metadata:
            raise MutationAuditError(f"REGISTERED_CASE_MISSING:{case_id}")
        case, metadata_path = metadata[case_id]
        npz_path = Path(str(case.get("npz_path", "")))
        if not npz_path.is_absolute():
            npz_path = (PHASE_ROOT / npz_path).resolve()
        if not npz_path.is_file():
            raise MutationAuditError(f"REGISTERED_CASE_NPZ_MISSING:{case_id}")
        with np.load(npz_path, allow_pickle=False) as archive:
            arrays = {name: np.asarray(archive[name]) for name in archive.files}
        return case, arrays, metadata_path, npz_path

    def _materialize_raw_output(
        self,
        name: str,
        payload: Mapping[str, Any],
    ) -> Path:
        path = self.output_root / "underlying" / f"{name}.json"
        _atomic_write_json(path, payload)
        return path

    def finite_fixture(self) -> dict[str, Any]:
        """Run and cache the contract's actual finite/non-zero-work prerequisite."""

        if self._fixture_cache is not None:
            return self._fixture_cache
        b4e = forced.b4e
        parent_event = b4e.extract_frozen_primary_event()
        parent_model = b4e.BranchedGripperServiceModel()
        parent_acquisition = b4e.acquisition_projection(parent_model, parent_event)
        parent_active = b4e.propagate_active(
            parent_model, parent_event, parent_acquisition,
            method=parent_event.method, step_s=parent_event.step_s,
        )
        fixture_event, b4e_fixture = b4e._execute_consistent_finite_event_fixture(parent_active)
        model = b4e.BranchedGripperServiceModel()
        acquisition = b4e.acquisition_projection(
            model, fixture_event, allow_algorithm_only_nontrigger_fixture=True,
        )
        pulse = self.spec["finite_event_harness"]["force_pulse"]
        left = forced.CommandArm(float(pulse["alpha_left"]), 0.0, float(pulse["T_cmd_s"]))
        right = forced.CommandArm(float(pulse["alpha_right"]), 0.0, float(pulse["T_cmd_s"]))
        command = forced.ForcedCommand(
            left, right, self.spec["finite_event_harness"]["id"],
        )
        result = forced.propagate_forced_case(
            model, fixture_event, acquisition, command,
            case_id="B4G_MUTATION_FINITE_HARNESS", method=fixture_event.method,
            step_s=fixture_event.step_s, q_ref_n=forced.REFERENCE_FORCE_N,
            end_time_s=float(fixture_event.time_s) + forced.ACTIVE_DURATION_S,
        )
        finite = bool(result.clearance.get("finite_event"))
        work = float(result.signed_work_j[-1]) if len(result.signed_work_j) else math.nan
        passed = bool(
            finite and result.synthetic_removal_executed
            and math.isfinite(work) and abs(work) > 1.0e-12
            and result.post_release is not None
            and result.post_release.get("post_release_passed") is True
        )
        if not passed:
            raise MutationAuditError("FINITE_EVENT_NONZERO_WORK_PRECONDITION_FAILED_CLOSED")
        self._fixture_cache = {
            "parent_event": parent_event,
            "parent_active": parent_active,
            "fixture_event": fixture_event,
            "b4e_fixture": b4e_fixture,
            "model": model,
            "acquisition": acquisition,
            "command": command,
            "result": result,
            "precondition": {
                "finite_event": finite,
                "finite_removal_event": finite,
                "synthetic_removal_executed": bool(result.synthetic_removal_executed),
                "removal_time_s": float(result.clearance["removal_time_s"]),
                "W_act_at_removal_J": work,
                "abs_W_act_at_removal_J": abs(work),
                "abs_W_act_gt_1e_12_J": abs(work) > 1.0e-12,
                "post_release_passed": bool(result.post_release["post_release_passed"]),
                "passed": True,
                "a1_or_b3_main_trigger_credit": False,
                "physical_current_or_formal_credit": False,
            },
        }
        return self._fixture_cache

    def _finite_harness_raw_path(self, fixture: Mapping[str, Any] | None = None) -> Path:
        """Publish the one complete raw finite harness trace shared by NC07/08/11-14."""

        live = self.finite_fixture() if fixture is None else fixture
        cached = live.get("raw_artifact_path")
        if cached is not None and Path(cached).is_file():
            return Path(cached)
        result = live["result"]
        raw_payload = forced.forced_run_to_raw(result)
        raw = raw_payload["raw"]
        time = np.asarray(result.time_s, dtype=float)
        q = np.asarray(result.command_q_14, dtype=float)
        ledgers = result.sample_ledgers
        closed = (
            np.asarray(ledgers["linear_momentum_drift_N_s"], dtype=float) <= 1.0e-9
        ) & (
            np.asarray(ledgers["angular_momentum_drift_N_m_s"], dtype=float) <= 1.0e-9
        ) & (
            np.asarray(ledgers["energy_minus_work_residual_J"], dtype=float) <= 1.0e-7
        ) & (
            np.asarray(ledgers["ideal_constraint_power_W"], dtype=float) <= 1.0e-10
        ) & (
            np.asarray(ledgers["active_contact_force_N"], dtype=float) <= 1.0e-12
        ) & (
            np.asarray(ledgers["active_contact_torque_N_m"], dtype=float) <= 1.0e-12
        )
        command_end = float(result.command.end_time_s(result.event.time_s))
        command_zero = np.all(q == 0.0, axis=1)
        ledger_interval = (
            closed[:-1] & closed[1:]
            & (time[:-1] >= command_end - forced.b4e.TIME_INTERVAL_MERGE_TOLERANCE_S)
            & command_zero[:-1] & command_zero[1:]
        )
        raw.update({
            "service_state_29": np.asarray(result.state_30[:, :29], dtype=float).tolist(),
            "signed_W_act_J": np.asarray(result.signed_work_j, dtype=float).tolist(),
            "ledger_interval_certified": ledger_interval.tolist(),
        })
        if result.post_release is None:
            raise MutationAuditError("FINITE_HARNESS_POST_RELEASE_RAW_REQUIRED")
        service = forced.b4e._service_from_active_vector(result.state_30[-1, :29])
        _, _, active_map, _, _, target_mass = forced.b4e._active_formula_terms(
            live["model"], service, live["acquisition"].snapshot,
        )
        active_formula_z = np.concatenate((
            service.nu_s_mixed, active_map @ service.nu_s_mixed,
        ))
        native_z = np.asarray(
            result.post_release["mapping"]["z_before"], dtype=float,
        )
        if np.max(np.abs(native_z - active_formula_z)) > 1.0e-12:
            raise MutationAuditError("FINITE_HARNESS_NATIVE_Z_SOURCE_MISMATCH")
        native_mass = forced.b4e._block_diagonal(
            live["model"].mass_matrix(service), target_mass,
        )
        native_mass = 0.5 * (native_mass + native_mass.T)
        post_trace = result.post_release["instrumented_trace"]
        parent_crosscheck = result.post_release["parent_b4e_crosscheck"]
        terminal_crosscheck = max(
            float(parent_crosscheck["terminal_service_state_max_error"]),
            float(parent_crosscheck["terminal_target_state_max_error"]),
        )
        raw_payload["mutation_base_payload_sources"] = {
            "REMOVAL_WORK_MAPPING": {
                "finite_removal_event": True,
                "W_before_removal_J": float(result.signed_work_j[-1]),
                "W_after_mapping_J": float(result.post_release["signed_W_act_carried_constant_J"]),
            },
            "REMOVAL_MAPPING": deepcopy(result.post_release["mapping"]),
            "ENERGY_MAPPING": {
                "z_before": native_z.tolist(), "z_after": native_z.tolist(),
                "mass_20x20": native_mass.tolist(),
                "D_switch_J": float(live["acquisition"].energy_audit["D_switch_J"]),
                "reported_kinetic_increment_J": 0.0,
            },
            "POST_RELEASE_TARGET_TRACE": {
                "time_s": deepcopy(post_trace["time_s"]),
                "independent_target_state_13": deepcopy(post_trace["target_state_13"]),
                "candidate_target_state_13": deepcopy(post_trace["target_state_13"]),
                "candidate_target_source": "INDEPENDENT_13D_POST_STATE",
                "parent_crosscheck_terminal_max_abs": terminal_crosscheck,
            },
            "CONTACT_TRACE": {
                "contact_kernel_enabled": False,
                "contact_force_N": [[0.0, 0.0, 0.0]] * 2,
                "contact_torque_N_m": [[0.0, 0.0, 0.0]] * 2,
            },
        }
        raw_payload.update({
            "schema": "SIM13_V4B4G_MUTATION_FINITE_HARNESS_RAW_V1",
            "harness_id": self.spec["finite_event_harness"]["id"],
            "finite_event_harness_contract": deepcopy(self.spec["finite_event_harness"]),
            "Q_ref_N": float(forced.REFERENCE_FORCE_N),
            "clearance_classifier_acquisition_time_s": max(
                float(result.event.time_s),
                command_end - forced.b4e.MINIMUM_ACTIVE_DWELL_S,
            ),
            "finite_event_harness_precondition": deepcopy(live["precondition"]),
            "claim_boundary": MUTATION_CREDIT_BOUNDARY,
        })
        path = self._materialize_raw_output(
            "B4G_MUTATION_FINITE_HARNESS__canonical_raw", raw_payload,
        )
        if isinstance(live, dict):
            live["raw_artifact_path"] = path
        return path

    def _initial_state(self, event: Any, acquisition: Any, model: Any) -> np.ndarray:
        state, _ = forced._initial_conditions(model, event, acquisition)
        return state

    def nc01(self) -> None:
        binding = next(row for row in self.source_bindings["sources"] if row["id"] == "b4f_audited_gate")
        path = PROJECT_ROOT / binding["path"]
        nominal_payload = path.read_bytes()
        mutant_payload = bytearray(nominal_payload)
        offset = int(self.targets["source_byte_drift"]["byte_offset_from_end"])
        mutant_index = len(mutant_payload) - offset
        mutant_payload[mutant_index] ^= int(self.targets["source_byte_drift"]["xor_mask_hex"], 16)
        mutant_path = self.output_root / "underlying" / "B4FNC01__mutated_bound_parent.bin"
        _atomic_write_bytes(mutant_path, bytes(mutant_payload))
        source_record = _file_record(path)
        base_candidate = dict(source_record)
        mutant_candidate = _file_record(mutant_path)
        base = {
            "source_id": binding["id"],
            "source_record": source_record,
            "candidate_record": base_candidate,
            "candidate_bytes_path": source_record["path"],
            "xor_mutation": {"applied": False, "byte_offset_from_end": offset, "xor_mask_hex": "00"},
        }
        mutant = deepcopy(base)
        mutant.update({
            "candidate_record": mutant_candidate,
            "candidate_bytes_path": mutant_candidate["path"],
            "xor_mutation": {
                "applied": True,
                "byte_offset_from_end": offset,
                "xor_mask_hex": self.targets["source_byte_drift"]["xor_mask_hex"],
            },
        })
        pointers = (
            "/payload/candidate_record/path",
            "/payload/candidate_record/bytes",
            "/payload/candidate_record/sha256",
            "/payload/candidate_bytes_path",
            "/payload/xor_mutation",
        )
        self._add_replay(
            "B4FNC01", 1, base_payload=base, mutant_payload=mutant,
            pointers=pointers,
            underlying_records=(("BOUND_PARENT_SOURCE", path), ("MUTANT_RAW_BYTES", mutant_path)),
            execution_mode="RAW_ARTIFACT_MUTATION",
            real_path_id="BOUND_PARENT_BYTE_VERIFIER_INPUT",
            real_path_hit=True,
            detail={"mutated_index": mutant_index, "source_id": binding["id"]},
        )

    def _registered_command_mutation(
        self, q_index: int, *, a0_gate: bool,
    ) -> tuple[dict[str, Any], dict[str, Any], tuple[tuple[str, Path], ...], dict[str, Any]]:
        case_id = (
            self.targets["a0_slot"]
            if a0_gate else self.targets["default_registered_forced_slot"]
        )
        metadata, arrays, metadata_path, npz_path = self._registered_case(case_id)
        slot = next(row for row in self.schedule["slots"] if row["case_id"] == case_id)
        command = np.asarray(arrays["command_Q_14"], dtype=float)
        sample_index = 0 if a0_gate else int(np.argmax(np.sum(np.abs(command), axis=1)))
        observed = command[sample_index].copy()
        base = {
            "trace_origin": "REGISTERED_CAMPAIGN_CASE",
            "harness_id": None,
            "harness_command": None,
            "arm": str(slot["arm"]),
            "slot": slot,
            "acquisition_time_s": float(metadata["event_provenance"]["acquisition_time_s"]),
            "sample_time_s": float(arrays["time_s"][sample_index]),
            "Q_ref_N": float(metadata["command_parameters"]["Q_ref_per_finger_N"]),
            "command_parameters": metadata["command_parameters"],
            "observed_Q_14": observed.tolist(),
            "clearance_dwell_active": False,
        }
        mutant = deepcopy(base)
        mutant["observed_Q_14"][q_index] += float(self.targets["force_injection_N"])
        records = (
            ("REGISTERED_CASE_METADATA", metadata_path),
            ("REGISTERED_CASE_RAW_NPZ", npz_path),
        )
        return base, mutant, records, {
            "registered_case_id": case_id,
            "sample_index": sample_index,
            "injected_Q_index": q_index,
            "injection_N": float(self.targets["force_injection_N"]),
        }

    def nc02(self) -> None:
        for subvariant, q_index in enumerate((12, 13), start=1):
            base, mutant, records, detail = self._registered_command_mutation(q_index, a0_gate=True)
            self._add_replay(
                "B4FNC02", subvariant, base_payload=base, mutant_payload=mutant,
                pointers=(f"/payload/observed_Q_14/{q_index}",),
                underlying_records=records, execution_mode="RAW_ARTIFACT_MUTATION",
                real_path_id="REGISTERED_A0_RAW_COMMAND_TRACE", real_path_hit=True,
                detail=detail,
            )

    def nc03(self) -> None:
        for subvariant, q_index in enumerate(range(12), start=1):
            base, mutant, records, detail = self._registered_command_mutation(q_index, a0_gate=False)
            self._add_replay(
                "B4FNC03", subvariant, base_payload=base, mutant_payload=mutant,
                pointers=(f"/payload/observed_Q_14/{q_index}",),
                underlying_records=records, execution_mode="RAW_ARTIFACT_MUTATION",
                real_path_id="REGISTERED_DEFAULT_A1_RAW_COMMAND_TRACE", real_path_hit=True,
                detail=detail,
            )

    def nc04(self) -> None:
        case_id = self.targets["default_registered_forced_slot"]
        metadata, arrays, metadata_path, npz_path = self._registered_case(case_id)
        base = {
            "P_coordinates_m": np.asarray(arrays["stage_P_coordinates_m"][0], dtype=float).tolist(),
            "centered_step_m": forced.CENTERED_SIGN_STEP_M,
            "raw_gap_jacobian_P": np.asarray(arrays["stage_gap_jacobian_P"][0], dtype=float).tolist(),
            "registered_signs": [1, 1],
            "consumed_signs": [1, 1],
            "clipping_used": False,
            "extrapolation_used": False,
            "terminal_status": metadata["terminal_status"],
        }
        for subvariant, signs in enumerate(self.targets["opening_sign_mutants_left_right"], start=1):
            mutant = deepcopy(base)
            mutant["consumed_signs"] = list(signs)
            side_index = 0 if signs[0] == -1 else 1
            self._add_replay(
                "B4FNC04", subvariant, base_payload=base, mutant_payload=mutant,
                pointers=(f"/payload/consumed_signs/{side_index}",),
                underlying_records=(("REGISTERED_CASE_METADATA", metadata_path), ("REGISTERED_CASE_RAW_NPZ", npz_path)),
                execution_mode="RAW_ARTIFACT_MUTATION",
                real_path_id="REGISTERED_DEFAULT_A1_OPENING_SIGN_STAGE",
                real_path_hit=True,
                detail={"registered_case_id": case_id, "raw_sign_preserved": True},
            )

    def _registered_work_payloads(
        self, multiplier: float,
    ) -> tuple[dict[str, Any], dict[str, Any], tuple[tuple[str, Path], ...], dict[str, Any]]:
        case_id = self.targets["default_registered_forced_slot"]
        _, arrays, metadata_path, npz_path = self._registered_case(case_id)
        time = np.asarray(arrays["time_s"], dtype=float)
        signed_work = np.asarray(arrays["signed_W_act_J"], dtype=float)
        residual = np.asarray(arrays["energy_minus_work_residual_J"], dtype=float)
        base = {
            "time_s": time.tolist(),
            "Q_P_N": np.asarray(arrays["command_Q_14"][:, 12:14], dtype=float).tolist(),
            "eta_P_m_s": np.asarray(arrays["service_state_29"][:, 27:29], dtype=float).tolist(),
            "signed_W_act_J": signed_work.tolist(),
            "energy_minus_work_residual_J": residual.tolist(),
        }
        mutant = deepcopy(base)
        mutant_work = multiplier * signed_work
        mutant["signed_W_act_J"] = mutant_work.tolist()
        if multiplier != 0.0:
            mutant["energy_minus_work_residual_J"] = np.abs(
                residual + (mutant_work - signed_work)
            ).tolist()
        return base, mutant, (
            ("REGISTERED_CASE_METADATA", metadata_path),
            ("REGISTERED_CASE_RAW_NPZ", npz_path),
        ), {
            "registered_case_id": case_id,
            "W_dot_multiplier": multiplier,
            "raw_sample_count": len(time),
        }

    def nc05_06(self) -> None:
        base, mutant, records, detail = self._registered_work_payloads(0.0)
        self._add_replay(
            "B4FNC05", 1, base_payload=base, mutant_payload=mutant,
            pointers=("/payload/signed_W_act_J",), underlying_records=records,
            execution_mode="RAW_ARTIFACT_MUTATION",
            real_path_id="REGISTERED_DEFAULT_A1_WORK_TRACE_W_DOT_OMITTED",
            real_path_hit=True, detail=detail,
        )
        base, mutant, records, detail = self._registered_work_payloads(2.0)
        self._add_replay(
            "B4FNC06", 1, base_payload=base, mutant_payload=mutant,
            pointers=("/payload/signed_W_act_J", "/payload/energy_minus_work_residual_J"),
            underlying_records=records, execution_mode="RAW_ARTIFACT_MUTATION",
            real_path_id="REGISTERED_DEFAULT_A1_WORK_TRACE_W_DOT_DOUBLE_COUNTED",
            real_path_hit=True, detail=detail,
        )

    def nc07(self) -> None:
        fixture = self.finite_fixture(); result = fixture["result"]
        work = float(result.signed_work_j[-1])
        base = {
            "finite_removal_event": True,
            "W_before_removal_J": work,
            "W_after_mapping_J": work,
        }
        mutant = {**base, "W_after_mapping_J": 0.0}
        raw = self._finite_harness_raw_path(fixture)
        self._add_replay(
            "B4FNC07", 1, base_payload=base, mutant_payload=mutant,
            pointers=("/payload/W_after_mapping_J",),
            underlying_records=(("EXECUTED_FINITE_HARNESS_RAW_OUTPUT", raw),),
            execution_mode="REAL_EXECUTED_PATH",
            real_path_id="FINITE_REMOVAL_WORK_CARRY_MAPPING",
            real_path_hit=abs(work) > 1.0e-12,
            detail={
                "finite_event_precondition": fixture["precondition"],
                "actual_removal_mapping_mutated": True,
            },
        )

    def _execute_nc08_dwell_force_mutant(
        self, fixture: Mapping[str, Any], *, side: str,
    ) -> tuple[Path, dict[str, Any]]:
        result = fixture["result"]
        event = fixture["fixture_event"]
        removal_time = float(result.clearance["removal_time_s"])
        dwell_start = float(result.clearance["tau_c_s"])
        q_index = 12 if side == "left" else 13
        original_force_vector = forced.force_vector

        def dwell_force_vector(
            command: Any, time_s: float, acquisition_time_s: float,
            q_ref_n: float = forced.REFERENCE_FORCE_N,
            opening_sign_vector: Sequence[int] = forced.REGISTERED_OPENING_SIGNS,
        ) -> np.ndarray:
            q = original_force_vector(
                command, time_s, acquisition_time_s, q_ref_n,
                opening_sign_vector,
            )
            if dwell_start <= float(time_s) <= removal_time:
                q = q.copy()
                q[q_index] += float(q_ref_n)
            return q

        step = float(event.step_s)
        step_count = max(
            1,
            int(math.ceil((removal_time - float(event.time_s)) / step - 1.0e-12)) + 1,
        )
        bounded_end = float(event.time_s) + step_count * step
        rhs_audit: list[dict[str, Any]] = []
        with _patched(forced, "force_vector", dwell_force_vector):
            rhs_derivative = forced.forced_rhs(
                fixture["model"], fixture["acquisition"].snapshot,
                fixture["command"], float(event.time_s),
                forced.REFERENCE_FORCE_N, removal_time,
                np.asarray(result.state_30[-1], dtype=float),
                stage_label=f"NC08_{side.upper()}_NOMINAL_DWELL_RHS",
                audit_sink=rhs_audit,
            )
            mutated_run = forced.propagate_forced_case(
                fixture["model"], event, fixture["acquisition"], fixture["command"],
                case_id=f"B4FNC08_{side.upper()}_REAL_DWELL_FORCE_MUTANT",
                method=event.method, step_s=step,
                q_ref_n=forced.REFERENCE_FORCE_N,
                end_time_s=bounded_end,
            )
        dwell_mask = (
            (np.asarray(mutated_run.time_s, dtype=float) >= dwell_start)
            & (np.asarray(mutated_run.time_s, dtype=float) <= removal_time)
        )
        dwell_q = np.asarray(mutated_run.command_q_14, dtype=float)[dwell_mask]
        stage_q = np.asarray(rhs_audit[-1]["generalized_force_14"], dtype=float)
        real_path_hit = bool(
            len(dwell_q) > 0
            and np.max(np.abs(dwell_q[:, q_index])) >= forced.REFERENCE_FORCE_N
            and stage_q[q_index] == forced.REFERENCE_FORCE_N
            and np.all(stage_q[:12] == 0.0)
            and np.asarray(rhs_derivative, dtype=float).shape == (30,)
        )
        source_finite_harness = self._finite_harness_raw_path(fixture)
        raw_payload = {
            "schema": "SIM13_V4B4G_MUTANT_DWELL_FORCE_TRACE_V1",
            "parent_id": "B4FNC08",
            "subvariant_index": 1 if side == "left" else 2,
            "side": side,
            "q_index": q_index,
            "source_finite_harness": _file_record(source_finite_harness),
            "injection_window_s": [dwell_start, removal_time],
            "injection_N": float(forced.REFERENCE_FORCE_N),
            "nominal_finite_clearance": deepcopy(result.clearance),
            "execution_branch": "PATCHED_FORCE_VECTOR_THEN_FORCED_PROPAGATION",
            "mutant_run": forced.forced_run_to_raw(mutated_run),
            "claim_boundary": MUTATION_CREDIT_BOUNDARY,
        }
        path = self._materialize_raw_output(
            f"B4FNC08__{side}__mutant_dwell_force_trace", raw_payload,
        )
        return path, {
            "real_path_hit": real_path_hit,
            "mutant_terminal_status": mutated_run.terminal_status,
            "mutant_geometry_domain_pass": bool(mutated_run.geometry_domain_pass),
            "mutant_dwell_sample_count": int(np.count_nonzero(dwell_mask)),
            "rhs_stage_Q_14": stage_q.tolist(),
        }

    def nc08(self) -> None:
        fixture = self.finite_fixture(); result=fixture["result"]; event=fixture["fixture_event"]
        removal_time = float(result.clearance["removal_time_s"])
        pulse = deepcopy(self.spec["finite_event_harness"]["force_pulse"])
        slot = next(
            row for row in self.schedule["slots"]
            if row["case_id"] == self.targets["default_registered_forced_slot"]
        )
        command_parameters = {
            "left": {
                "alpha": float(pulse["alpha_left"]), "delay_s": 0.0,
                "duration_s": float(pulse["T_cmd_s"]),
            },
            "right": {
                "alpha": float(pulse["alpha_right"]), "delay_s": 0.0,
                "duration_s": float(pulse["T_cmd_s"]),
            },
        }
        harness_command = {
            "force_pulse": pulse,
            "dwell_hold_N": {"left": 0.0, "right": 0.0},
        }
        base = {
            "arm": "A1",
            "slot": slot,
            "acquisition_time_s": float(event.time_s),
            "sample_time_s": removal_time,
            "Q_ref_N": float(forced.REFERENCE_FORCE_N),
            "command_parameters": command_parameters,
            "observed_Q_14": [0.0] * 14,
            "clearance_dwell_active": True,
            "trace_origin": "FROZEN_FINITE_EVENT_HARNESS",
            "harness_id": self.spec["finite_event_harness"]["id"],
            "harness_command": harness_command,
        }
        raw = self._finite_harness_raw_path(fixture)
        for subvariant, side in enumerate(("left", "right"), start=1):
            q_index = 12 if side == "left" else 13
            mutant_raw, execution = self._execute_nc08_dwell_force_mutant(
                fixture, side=side,
            )
            mutant = deepcopy(base)
            mutant["observed_Q_14"][q_index] = float(forced.REFERENCE_FORCE_N)
            mutant["harness_command"]["dwell_hold_N"][side] = float(forced.REFERENCE_FORCE_N)
            self._add_replay(
                "B4FNC08", subvariant, base_payload=base, mutant_payload=mutant,
                pointers=(
                    f"/payload/observed_Q_14/{q_index}",
                    f"/payload/harness_command/dwell_hold_N/{side}",
                ),
                underlying_records=(
                    ("EXECUTED_FINITE_HARNESS_RAW_OUTPUT", raw),
                    ("MUTANT_DWELL_FORCE_TRACE", mutant_raw),
                ),
                execution_mode="REAL_EXECUTED_PATH",
                real_path_id="FINITE_HARNESS_CLEARANCE_DWELL_COMMAND_TRACE",
                real_path_hit=execution["real_path_hit"],
                detail={
                    "actual_force_vector_evaluated_at_exact_harness_removal": True,
                    "actual_forced_rhs_evaluated_at_nominal_dwell": True,
                    "actual_mutant_propagation_executed": True,
                    "removal_time_s": removal_time,
                    "mutated_side": side,
                    "supplemental_mutant_dwell_force_trace": _file_record(mutant_raw),
                    **execution,
                },
            )

    def nc09(self) -> None:
        fixture = self.targets["single_side_classifier_fixture"]
        payload = fixture["canonical_payload"]
        time = np.asarray(payload["time_s"], dtype=float)
        kwargs = {"acquisition_time_s": float(payload["acquisition_time_s"]), "ledger_interval_certified": np.ones(len(time)-1, dtype=bool)}
        nominal_result = forced.b4e.certify_earliest_clearance(
            time, payload["left_gap_m"], payload["right_gap_m"],
            payload["left_gap_rate_m_s"], payload["right_gap_rate_m_s"], **kwargs,
        )
        base = {
            **deepcopy(payload),
            "ledger_interval_certified": [True] * (len(time) - 1),
            "observed_finite_event": bool(nominal_result.get("finite_event")),
            "classifier_mode": "BILATERAL_HERMITE_ALL_ROOT_EARLIEST_DWELL",
        }
        for subvariant, mode in enumerate(("SINGLE_SIDE_LEFT", "SINGLE_SIDE_RIGHT"), start=1):
            mutant = deepcopy(base)
            mutant["observed_finite_event"] = True
            mutant["classifier_mode"] = mode
            self._add_replay(
                "B4FNC09", subvariant, base_payload=base, mutant_payload=mutant,
                pointers=("/payload/observed_finite_event", "/payload/classifier_mode"),
                underlying_records=(("FROZEN_CLASSIFIER_FIXTURE_CONTRACT", MUTATION_SPEC_PATH),),
                execution_mode="RAW_ARTIFACT_MUTATION",
                real_path_id="FROZEN_SINGLE_SIDE_CLEARANCE_CLASSIFIER_FIXTURE",
                real_path_hit=True,
                detail={
                    "actual_piecewise_Hermite_classifier_invoked": True,
                    "nominal_result": nominal_result,
                    "mutant_classifier_mode": mode,
                },
            )

    def nc10(self) -> None:
        fixture = self.targets["endpoint_only_classifier_fixture"]
        payload = fixture["canonical_payload"]
        time = np.asarray(payload["time_s"], dtype=float)
        kwargs = {"acquisition_time_s": float(payload["acquisition_time_s"]), "ledger_interval_certified": np.ones(1, dtype=bool)}
        nominal_result = forced.b4e.certify_earliest_clearance(
            time, payload["left_gap_m"], payload["right_gap_m"],
            payload["left_gap_rate_m_s"], payload["right_gap_rate_m_s"], **kwargs,
        )
        base = {
            **deepcopy(payload),
            "ledger_interval_certified": [True] * (len(time) - 1),
            "observed_finite_event": bool(nominal_result.get("finite_event")),
            "classifier_mode": "BILATERAL_HERMITE_ALL_ROOT_EARLIEST_DWELL",
        }
        mutant = deepcopy(base)
        mutant["observed_finite_event"] = True
        mutant["classifier_mode"] = "ENDPOINT_ONLY"
        self._add_replay(
            "B4FNC10", 1, base_payload=base, mutant_payload=mutant,
            pointers=("/payload/observed_finite_event", "/payload/classifier_mode"),
            underlying_records=(("FROZEN_CLASSIFIER_FIXTURE_CONTRACT", MUTATION_SPEC_PATH),),
            execution_mode="RAW_ARTIFACT_MUTATION",
            real_path_id="FROZEN_ENDPOINT_ONLY_CLEARANCE_CLASSIFIER_FIXTURE",
            real_path_hit=True,
            detail={
                "actual_all_root_classifier_invoked_on_canonical_history": True,
                "nominal_result": nominal_result,
                "certified_interior_minimum_gap_m": fixture["interior_minimum_gap_m"],
            },
        )

    def _release_state_and_mass(self) -> tuple[dict[str, Any], Any, Any, np.ndarray, np.ndarray]:
        fixture = self.finite_fixture(); result=fixture["result"]; model=fixture["model"]; acquisition=fixture["acquisition"]
        service = forced.b4e._service_from_active_vector(result.state_30[-1, :29])
        _, _, a, target, _, target_mass = forced.b4e._active_formula_terms(
            model, service, acquisition.snapshot,
        )
        if result.post_release is None:
            raise MutationAuditError("FINITE_HARNESS_POST_RELEASE_MAPPING_REQUIRED")
        z = np.asarray(result.post_release["mapping"]["z_before"], dtype=float)
        mass = forced.b4e._block_diagonal(model.mass_matrix(service), target_mass)
        # The frozen analytical mass is symmetric; canonicalize the last-bit
        # assembly asymmetry so the byte-level interchange has exact M == M.T.
        mass = 0.5 * (mass + mass.T)
        return fixture, service, target, z, mass

    def _run_parent_post_override(self, z_override: np.ndarray) -> dict[str, Any]:
        fixture, service, _, _, _ = self._release_state_and_mass()
        result = fixture["result"]
        return forced.b4e.execute_post_release(
            fixture["model"], fixture["acquisition"], service,
            release_time_s=float(result.clearance["removal_time_s"]),
            method=fixture["fixture_event"].method, step_s=fixture["fixture_event"].step_s,
            z_after_override=np.asarray(z_override, dtype=float),
        )

    def nc11(self) -> None:
        fixture, _, _, z, mass = self._release_state_and_mass()
        z_mutant = np.asarray(fixture["acquisition"].z_minus, dtype=float)
        post = self._run_parent_post_override(z_mutant)
        momentum_jump = mass @ (z_mutant - z)
        kinetic_jump = 0.5 * float(z_mutant @ mass @ z_mutant - z @ mass @ z)
        parent_mapping = fixture["result"].post_release["mapping"]
        base = {
            field: deepcopy(parent_mapping[field]) for field in (
                "z_before", "z_after", "linear_impulse_N_s",
                "angular_impulse_N_m_s", "kinetic_energy_jump_J",
                "ideal_constraint_stored_energy_J",
            )
        }
        mutant = deepcopy(base)
        mutant.update({
            "z_after": z_mutant.tolist(),
            "linear_impulse_N_s": momentum_jump[:3].tolist(),
            "angular_impulse_N_m_s": momentum_jump[3:6].tolist(),
            "kinetic_energy_jump_J": kinetic_jump,
        })
        raw = self._finite_harness_raw_path(fixture)
        self._add_replay(
            "B4FNC11", 1, base_payload=base, mutant_payload=mutant,
            pointers=(
                "/payload/z_after", "/payload/linear_impulse_N_s",
                "/payload/angular_impulse_N_m_s", "/payload/kinetic_energy_jump_J",
            ),
            underlying_records=(("EXECUTED_FINITE_HARNESS_RAW_OUTPUT", raw),),
            execution_mode="REAL_EXECUTED_PATH",
            real_path_id="FINITE_REMOVAL_NATIVE_MAPPING_OVERRIDE",
            real_path_hit=True,
            detail={
                "actual_42D_parent_post_release_executed": True,
                "source": self.targets["post_release_twist_source_mutant"],
            },
        )

    def nc12(self) -> None:
        fixture, _, _, z, mass = self._release_state_and_mass()
        d = np.zeros(20); d[12] = 1.0
        d_switch = float(fixture["acquisition"].energy_audit["D_switch_J"])
        a = 0.5 * float(d @ mass @ d)
        b = float(z @ mass @ d)
        discriminant = b*b + 4.0*a*d_switch
        if a <= 0.0 or discriminant < 0.0:
            raise MutationAuditError("NC12_MASS_METRIC_ROOT_NOT_REAL")
        root_minus = (-b - math.sqrt(discriminant)) / (2.0*a)
        root_plus = (-b + math.sqrt(discriminant)) / (2.0*a)
        roots = [root_minus, root_plus]
        beta = sorted(roots, key=lambda value: (abs(value), value < 0.0))[0]
        z_mutant = z + beta*d
        increment = 0.5 * float(z_mutant @ mass @ z_mutant - z @ mass @ z)
        post = self._run_parent_post_override(z_mutant)
        base = {
            "z_before": z.tolist(), "z_after": z.tolist(),
            "mass_20x20": mass.tolist(), "D_switch_J": d_switch,
            "reported_kinetic_increment_J": 0.0,
        }
        mutant = deepcopy(base)
        mutant.update({
            "z_after": z_mutant.tolist(),
            "reported_kinetic_increment_J": increment,
        })
        raw = self._finite_harness_raw_path(fixture)
        self._add_replay(
            "B4FNC12", 1, base_payload=base, mutant_payload=mutant,
            pointers=("/payload/z_after", "/payload/reported_kinetic_increment_J"),
            underlying_records=(("EXECUTED_FINITE_HARNESS_RAW_OUTPUT", raw),),
            execution_mode="REAL_EXECUTED_PATH",
            real_path_id="FINITE_REMOVAL_NATIVE_MASS_ENERGY_MAPPING",
            real_path_hit=abs(increment-d_switch) <= 1e-10 and abs(increment) > 1e-12,
            detail={
                "actual_42D_parent_post_release_executed": True,
                "mass_shape": list(mass.shape),
                "direction": "native_20D_e12_service_left_P_velocity",
                "root_minus": root_minus,
                "root_plus": root_plus,
                "selected_beta": beta,
                "root_selection_rule": "MINIMUM_ABSOLUTE_BETA_TIES_CHOOSE_POSITIVE",
                "achieved_kinetic_increment_J": increment,
            },
        )

    def nc13(self) -> None:
        fixture = self.finite_fixture(); post=fixture["result"].post_release
        assert post is not None
        trace = post["instrumented_trace"]
        independent = np.asarray(trace["target_state_13"], dtype=float)
        reconstructed: list[np.ndarray] = []
        for service_vector in trace["service_state_29"]:
            service = forced.b4e._service_from_active_vector(np.asarray(service_vector, dtype=float))
            target, _, _, _, _ = forced.b4e.target_from_snapshot(
                fixture["model"], service, fixture["acquisition"].snapshot,
            )
            reconstructed.append(forced.b4e._target_to_post_vector(target))
        snapshot_target = np.asarray(reconstructed)
        residual = float(np.max(np.abs(snapshot_target-independent)))
        crosscheck = post["parent_b4e_crosscheck"]
        terminal_crosscheck = max(
            float(crosscheck["terminal_service_state_max_error"]),
            float(crosscheck["terminal_target_state_max_error"]),
        )
        base = {
            "time_s": list(trace["time_s"]),
            "independent_target_state_13": independent.tolist(),
            "candidate_target_state_13": independent.tolist(),
            "candidate_target_source": "INDEPENDENT_13D_POST_STATE",
            "parent_crosscheck_terminal_max_abs": terminal_crosscheck,
        }
        mutant = deepcopy(base)
        mutant.update({
            "candidate_target_state_13": snapshot_target.tolist(),
            "candidate_target_source": "ATTACHED_SNAPSHOT_RECONSTRUCTED_EVERY_SAMPLE",
            "parent_crosscheck_terminal_max_abs": max(terminal_crosscheck, residual),
        })
        raw = self._finite_harness_raw_path(fixture)
        self._add_replay(
            "B4FNC13", 1, base_payload=base, mutant_payload=mutant,
            pointers=(
                "/payload/candidate_target_state_13",
                "/payload/candidate_target_source",
                "/payload/parent_crosscheck_terminal_max_abs",
            ),
            underlying_records=(("EXECUTED_FINITE_HARNESS_RAW_OUTPUT", raw),),
            execution_mode="REAL_EXECUTED_PATH",
            real_path_id="FINITE_POST_RELEASE_TARGET_TRACE_SOURCE_SUBSTITUTION",
            real_path_hit=len(snapshot_target) > 1 and residual > 1.0e-12,
            detail={
                "actual_post_trace_consumed": True,
                "snapshot_target_reconstruction_executed_each_sample": True,
            },
        )

    def nc14(self) -> None:
        fixture = self.finite_fixture(); post=fixture["result"].post_release
        assert post is not None
        state0 = np.asarray(post["instrumented_trace"]["state_42"][0], dtype=float)
        service = forced.b4e._service_from_active_vector(state0[:29]); target=forced.b4e._target_from_post_vector(state0[29:42])
        observations = forced.b4e.evaluate_dual_contact(
            fixture["model"], service, target, forced.b4e.DualContactConfig(), enabled=True,
        )
        forces = [np.asarray(item.service_force_inertial_n, dtype=float).tolist() for item in observations]
        torques = [np.asarray(item.service_shift_torque_inertial_n_m, dtype=float).tolist() for item in observations]
        base = {
            "contact_kernel_enabled": False,
            "contact_force_N": [[0.0, 0.0, 0.0]] * 2,
            "contact_torque_N_m": [[0.0, 0.0, 0.0]] * 2,
        }
        mutant = {
            "contact_kernel_enabled": True,
            "contact_force_N": forces,
            "contact_torque_N_m": torques,
        }
        raw = self._finite_harness_raw_path(fixture)
        self._add_replay(
            "B4FNC14", 1, base_payload=base, mutant_payload=mutant,
            pointers=(
                "/payload/contact_kernel_enabled", "/payload/contact_force_N",
                "/payload/contact_torque_N_m",
            ),
            underlying_records=(("EXECUTED_FINITE_HARNESS_RAW_OUTPUT", raw),),
            execution_mode="REAL_EXECUTED_PATH",
            real_path_id="FINITE_POST_RELEASE_CONTACT_REACTIVATION",
            real_path_hit=len(observations) == 2,
            detail={
                "actual_dual_contact_evaluator_called_with_enabled_true": True,
                "nonzero_force_not_required_because_enabled_state_itself_is_forbidden": True,
            },
        )

    def _load_campaign(self) -> tuple[dict[str, Any], dict[str, tuple[dict[str, Any], Path]]]:
        if self._campaign_summary is not None and self._metadata_cache is not None:
            return self._campaign_summary, self._metadata_cache
        if not CAMPAIGN_SUMMARY_PATH.is_file():
            raise MutationAuditError("CAMPAIGN_SUMMARY_REQUIRED_FOR_FULL_MUTATION_EXECUTION")
        summary = _read_json(CAMPAIGN_SUMMARY_PATH)
        metadata: dict[str, tuple[dict[str, Any], Path]] = {}
        for path in sorted(RAW_CASE_ROOT.glob("*.json")):
            value = _read_json(path)
            case_id = str(value.get("case_id", ""))
            if case_id:
                if case_id in metadata:
                    raise MutationAuditError(f"DUPLICATE_RAW_CASE_ID:{case_id}")
                metadata[case_id] = (value, path)
        if len(metadata) != 144:
            raise MutationAuditError(f"RAW_CASE_METADATA_COUNT_NOT_144:{len(metadata)}")
        self._campaign_summary = summary; self._metadata_cache = metadata
        self.source_binding["campaign_summary"] = _file_record(CAMPAIGN_SUMMARY_PATH)
        self.source_binding["campaign_summary_sha256"] = self.source_binding["campaign_summary"]["sha256"]
        self.source_binding["raw_case_metadata_count"] = len(metadata)
        return summary, metadata

    def nc15(self) -> None:
        _, metadata = self._load_campaign()
        case_suffix = "__A1__ALPHA_2__TCMD_MS_10"
        rk_id = "RK4_REFERENCE" + case_suffix; mp_id = "MIDPOINT_REFERENCE" + case_suffix
        def row(case_id: str) -> dict[str, Any]:
            case = metadata[case_id][0]
            event = case["event_provenance"]
            responses = case["responses"]
            return {
                "lane_id": event["lane_id"],
                "fresh_b3_reconstruction": event["fresh_b3_reconstruction"],
                "acquisition_certificate_sha256": event["acquisition_certificate_sha256"],
                "clearance_certificate_sha256": event["clearance_certificate_sha256"],
                "acquisition_time_s": event["acquisition_time_s"],
                "removal_time_s": event["removal_time_s"],
                "signed_work_J": responses["signed_work_terminal_J"],
                "finite_removal_event": responses["finite_removal_event"],
                "post_release_passed": responses["post_release_passed"],
                "independent_integrity_pass": responses["selector_case_integrity_pass"],
            }
        rk = row(rk_id); mp = row(mp_id)
        base = {
            "rk4": rk, "midpoint": mp,
            "event_time_tolerance_s": 0.00025,
            "work_relative_tolerance": 0.001,
            "work_absolute_floor_J": 1.0e-10,
        }
        for subvariant, pointer in enumerate(("/payload/rk4", "/payload/midpoint"), start=1):
            mutant = deepcopy(base)
            if subvariant == 1:
                mutant["rk4"] = deepcopy(mp)
            else:
                mutant["midpoint"] = deepcopy(rk)
            self._add_replay(
                "B4FNC15", subvariant, base_payload=base, mutant_payload=mutant,
                pointers=(pointer,),
                underlying_records=(
                    ("RK4_REFERENCE_CASE_METADATA", metadata[rk_id][1]),
                    ("MIDPOINT_REFERENCE_CASE_METADATA", metadata[mp_id][1]),
                ),
                execution_mode="RAW_ARTIFACT_MUTATION",
                real_path_id="REGISTERED_REFERENCE_PAIR_PROVENANCE",
                real_path_hit=True,
                detail={
                    "raw_metadata_paths": [metadata[rk_id][1], metadata[mp_id][1]],
                    "time_and_full_provenance_replaced": True,
                },
            )

    def nc16(self) -> None:
        campaign.validate_registered_schedule(self.schedule)
        base = {"schedule": deepcopy(self.schedule)}
        for subvariant, level in enumerate(self.targets["unregistered_levels"], start=1):
            mutant = deepcopy(base)
            mutant["schedule"]["slots"].append(deepcopy(level))
            caught = None
            try:
                campaign.validate_registered_schedule(mutant["schedule"])
            except campaign.CampaignContractError as error:
                caught = str(error)
            pointer = "/payload/schedule/slots/-"
            self._add(
                "B4FNC16", subvariant, pointer, base, mutant,
                ({"op": "add", "path": pointer, "value": deepcopy(level)},),
                underlying_records=(("FROZEN_REGISTERED_SCHEDULE", SCHEDULE_PATH),),
                execution_mode="RAW_ARTIFACT_MUTATION",
                real_path_id="FROZEN_REGISTERED_SCHEDULE_VALIDATOR_INPUT",
                real_path_hit=caught is not None,
                detail={
                    "actual_frozen_schedule_validator_invoked": True,
                    "caught": caught, "unregistered_level": level,
                },
            )

    def _execute_nc17_no_parent_detector_harness(
        self, parent: Mapping[str, Any],
    ) -> tuple[Path, dict[str, Any]]:
        """Execute the frozen algorithm-only symmetric A2 detector harness."""

        from b4g_execution.evidence import compare_a2_mirror_pair

        lane_order = list(self.schedule["lane_order"])
        a2_slots = [slot for slot in self.schedule["slots"] if slot.get("arm") == "A2"]
        variant_order = (
            "RIGHT_HALF_DELAY", "LEFT_HALF_DELAY_MIRROR",
            "RIGHT_COMMAND_OFF", "LEFT_COMMAND_OFF_MIRROR",
        )
        expected = {(lane, variant) for lane in lane_order for variant in variant_order}
        by_lane_variant = {
            (str(slot["lane_id"]), str(slot["variant_id"])): slot for slot in a2_slots
        }
        if len(a2_slots) != 24 or set(by_lane_variant) != expected:
            raise MutationAuditError("NC17_FROZEN_A2_SCHEDULE_NOT_SIX_BY_FOUR")
        trace_order = (
            "RIGHT_HALF_DELAY_BASE", "RIGHT_HALF_DELAY_MUTANT",
            "LEFT_HALF_DELAY_MIRROR", "RIGHT_COMMAND_OFF_BASE",
            "RIGHT_COMMAND_OFF_MUTANT", "LEFT_COMMAND_OFF_MIRROR",
        )
        detector_model = {
            "model_id": "SYMMETRIC_DETERMINISTIC_BILATERAL_COMMAND_RESPONSE_V1",
            "initial_gap_m": 2.0e-6,
            "symmetric_mobility_m_s_N": 0.01,
            "integration": "CUMULATIVE_TRAPEZOID_ON_FROZEN_RELATIVE_GRID",
            "terminal_status": "ALGORITHM_ONLY_DETECTOR_HORIZON_COMPLETE_NO_PHYSICAL_OUTCOME",
        }
        capabilities = {
            "a1_outcome_credit": False,
            "a2_outcome_credit": False,
            "physical_credit": False,
            "current_system_bound": False,
        }

        def frozen_grid(step_s: float) -> np.ndarray:
            count = int(round(0.08 / float(step_s)))
            grid = float(step_s) * np.arange(count + 1, dtype=float)
            grid[-1] = 0.08
            if len(grid) != count + 1 or np.any(np.diff(grid) <= 0.0):
                raise MutationAuditError("NC17_FROZEN_RELATIVE_GRID_INVALID")
            return grid

        def response_trace(
            trace_id: str,
            pair_kind: str,
            side: str,
            command_variant: str,
            command: forced.ForcedCommand,
            relative: np.ndarray,
        ) -> dict[str, Any]:
            q = np.asarray([
                forced.force_vector(
                    command, float(time_s), 0.0,
                    float(parent["Q_ref_N"]), forced.REGISTERED_OPENING_SIGNS,
                )
                for time_s in relative
            ])
            if q.shape != (len(relative), 14) or np.any(q[:, :12] != 0.0):
                raise MutationAuditError("NC17_ALGORITHM_COMMAND_TRACE_INVALID")
            rate = float(detector_model["symmetric_mobility_m_s_N"]) * q[:, 12:14]
            gap = np.full((len(relative), 2), float(detector_model["initial_gap_m"]))
            power = np.sum(q[:, 12:14] * rate, axis=1)
            work = np.zeros(len(relative))
            if len(relative) > 1:
                increments = np.diff(relative)
                gap[1:] += np.cumsum(
                    0.5 * (rate[:-1] + rate[1:]) * increments[:, None], axis=0,
                )
                work[1:] = np.cumsum(
                    0.5 * (power[:-1] + power[1:]) * increments,
                )
            return {
                "trace_id": trace_id,
                "pair_kind": pair_kind,
                "side": side,
                "command_variant": command_variant,
                "command_Q_14": q.tolist(),
                "left_gap_m": gap[:, 0].tolist(),
                "right_gap_m": gap[:, 1].tolist(),
                "left_gap_rate_m_s": rate[:, 0].tolist(),
                "right_gap_rate_m_s": rate[:, 1].tolist(),
                "signed_W_act_J": work.tolist(),
                "outcome": {
                    "finite_removal_event": False,
                    "removal_time_s": None,
                    "post_release_passed": False,
                    "terminal_status": detector_model["terminal_status"],
                },
            }

        def trace_command(lane: str, trace_id: str) -> tuple[str, forced.ForcedCommand]:
            if trace_id.startswith("RIGHT_HALF_DELAY"):
                variant = "RIGHT_HALF_DELAY"
            elif trace_id == "LEFT_HALF_DELAY_MIRROR":
                variant = "LEFT_HALF_DELAY_MIRROR"
            elif trace_id.startswith("RIGHT_COMMAND_OFF"):
                variant = "RIGHT_COMMAND_OFF"
            else:
                variant = "LEFT_COMMAND_OFF_MIRROR"
            slot = by_lane_variant[(lane, variant)]
            registered = campaign.command_for_slot(slot, selected_parent=parent)
            if trace_id == "RIGHT_HALF_DELAY_MUTANT":
                registered = forced.ForcedCommand(
                    registered.left,
                    forced.CommandArm(
                        float(parent["alpha"]) * 0.75,
                        registered.right.delay_s,
                        registered.right.duration_s,
                    ),
                    f"{registered.command_id}__B4FNC17_MUTANT_0P75",
                )
            elif trace_id == "RIGHT_COMMAND_OFF_MUTANT":
                registered = forced.ForcedCommand(
                    registered.left,
                    forced.CommandArm(
                        float(parent["alpha"]) * 0.25,
                        registered.right.delay_s,
                        registered.right.duration_s,
                    ),
                    f"{registered.command_id}__B4FNC17_MUTANT_0P25",
                )
            return variant, registered

        lane_records: list[dict[str, Any]] = []
        detector_results: list[dict[str, Any]] = []
        for lane in lane_order:
            lane_slot = by_lane_variant[(lane, "RIGHT_HALF_DELAY")]
            relative = frozen_grid(float(lane_slot["step_s"]))
            traces: list[dict[str, Any]] = []
            for trace_id in trace_order:
                variant, command = trace_command(lane, trace_id)
                pair_kind = "HALF_DELAY" if "HALF_DELAY" in trace_id else "COMMAND_OFF"
                side = "LEFT_MIRROR" if trace_id.startswith("LEFT") else "RIGHT"
                traces.append(response_trace(
                    trace_id, pair_kind, side, variant, command, relative,
                ))

            with tempfile.TemporaryDirectory(
                prefix="b4gnc17_", dir=self.output_root,
            ) as temporary_name:
                temporary = Path(temporary_name)

                by_trace = {row["trace_id"]: row for row in traces}

                def comparator_inputs(trace_id: str) -> tuple[dict[str, Any], Path]:
                    trace = by_trace[trace_id]
                    path = temporary / f"{trace_id}.npz"
                    np.savez(
                        path,
                        time_s=np.asarray(relative, dtype="<f8"),
                        left_gap_m=np.asarray(trace["left_gap_m"], dtype="<f8"),
                        right_gap_m=np.asarray(trace["right_gap_m"], dtype="<f8"),
                        left_gap_rate_m_s=np.asarray(
                            trace["left_gap_rate_m_s"], dtype="<f8",
                        ),
                        right_gap_rate_m_s=np.asarray(
                            trace["right_gap_rate_m_s"], dtype="<f8",
                        ),
                        signed_W_act_J=np.asarray(trace["signed_W_act_J"], dtype="<f8"),
                    )
                    return {
                        "event_provenance": {"acquisition_time_s": 0.0},
                        "responses": {"finite_removal_event": False},
                        "terminal_status": detector_model["terminal_status"],
                    }, path

                for pair_kind, base_id, mutant_id, left_id in (
                    (
                        "HALF_DELAY", "RIGHT_HALF_DELAY_BASE",
                        "RIGHT_HALF_DELAY_MUTANT", "LEFT_HALF_DELAY_MIRROR",
                    ),
                    (
                        "COMMAND_OFF", "RIGHT_COMMAND_OFF_BASE",
                        "RIGHT_COMMAND_OFF_MUTANT", "LEFT_COMMAND_OFF_MIRROR",
                    ),
                ):
                    left_meta, left_npz = comparator_inputs(left_id)
                    base_meta, base_npz = comparator_inputs(base_id)
                    mutant_meta, mutant_npz = comparator_inputs(mutant_id)
                    base_comparison = compare_a2_mirror_pair(
                        left_meta, base_meta, left_npz, base_npz,
                    )
                    mutant_comparison = compare_a2_mirror_pair(
                        left_meta, mutant_meta, left_npz, mutant_npz,
                    )
                    if base_comparison["scientific_predicate"] is not True:
                        raise MutationAuditError(
                            f"NC17_BASE_MIRROR_DETECTOR_NOT_PASS:{lane}:{pair_kind}"
                        )
                    if (
                        mutant_comparison["full_relative_grid_equal"] is not True
                        or mutant_comparison["scientific_predicate"] is not False
                    ):
                        raise MutationAuditError(
                            f"NC17_MUTANT_MIRROR_DETECTOR_NOT_HIT:{lane}:{pair_kind}"
                        )
                    detector_results.append({
                        "lane_id": lane,
                        "pair_kind": pair_kind,
                        "base_comparison": base_comparison,
                        "mutant_comparison": mutant_comparison,
                    })
            lane_records.append({
                "lane_id": lane,
                "method": str(lane_slot["method"]),
                "step_s": float(lane_slot["step_s"]),
                "relative_time_s": relative.tolist(),
                "traces": traces,
            })

        complete = bool(
            len(lane_records) == 6
            and all(len(row["traces"]) == 6 for row in lane_records)
            and len(detector_results) == 12
            and all(row["base_comparison"]["scientific_predicate"] is True for row in detector_results)
            and all(row["mutant_comparison"]["scientific_predicate"] is False for row in detector_results)
        )
        payload = {
            "schema": "SIM13_V4B4G_A2_DETECTOR_SIX_LANE_TRACE_V1",
            "parent_id": "B4FNC17",
            "harness_id": self.targets["nc17_no_parent_harness"]["id"],
            "source_schedule": _file_record(SCHEDULE_PATH),
            "parent_level": _jsonable(dict(parent)),
            "lane_order": lane_order,
            "trace_order": list(trace_order),
            "detector_model": detector_model,
            "lanes": lane_records,
            "capabilities": capabilities,
            "claim_boundary": MUTATION_CREDIT_BOUNDARY,
        }
        path = self._materialize_raw_output(
            "B4FNC17__a2_detector_six_lane_trace", payload,
        )
        return path, {
            "complete": complete,
            "lane_count": len(lane_records),
            "algorithm_trace_count": sum(
                len(row["traces"]) for row in lane_records
            ),
            "production_mirror_evaluator_call_count": 2 * len(detector_results),
        }

    def nc17(self) -> None:
        summary, metadata = self._load_campaign()
        selected = summary.get("selector", {}).get("selected_parent_level")
        lanes = [row["lane_id"] for row in _read_json(CONTRACT_ROOT/"PHASE_B4G_RUN_SPEC_V1.json")["lanes"]]
        fallback = selected in (None, {}, "NOT_OBSERVED_IN_REGISTERED_SYNTHETIC_COMMAND_DOMAIN")
        parent = {"alpha":2.0,"command_duration_s":0.01} if fallback else {
            "alpha":float(selected["alpha"]),
            "command_duration_s":float(selected.get("command_duration_s",selected.get("tested_duration_s"))),
        }
        parent["Q_ref_N"] = float(forced.REFERENCE_FORCE_N)
        pair_defs = [
            ("HALF_DELAY", "RIGHT_HALF_DELAY", "LEFT_HALF_DELAY_MIRROR", 0.5, 0.75),
            ("COMMAND_OFF", "RIGHT_COMMAND_OFF", "LEFT_COMMAND_OFF_MIRROR", 0.0, 0.25),
        ]
        a2_rows = [
            (case_id, row, path) for case_id, (row, path) in metadata.items()
            if row.get("arm") == "A2"
        ]
        if not fallback and (
            len(a2_rows) != 24
            or any(row.get("execution_status") != "EXECUTED_FRESH_REGISTERED_SLOT" for _, row, _ in a2_rows)
        ):
            raise MutationAuditError("NC17_SELECTED_PARENT_REQUIRES_FULL_EXECUTED_A2_RAW_SET")
        detector_raw: Path | None = None
        detector_result: dict[str, Any] | None = None
        if fallback:
            detector_raw, detector_result = self._execute_nc17_no_parent_detector_harness(parent)
            if detector_result["complete"] is not True:
                raise MutationAuditError("NC17_NO_PARENT_DETECTOR_HARNESS_FAILED")
            records: tuple[tuple[str, Path], ...] = (
                ("FROZEN_MUTATION_FALLBACK_CONTRACT", MUTATION_SPEC_PATH),
                ("FROZEN_REGISTERED_SCHEDULE", SCHEDULE_PATH),
                ("A2_DETECTOR_SIX_LANE_TRACE", detector_raw),
            )
        else:
            if CAMPAIGN_SUMMARY_PATH.is_file():
                parent_selection_path = CAMPAIGN_SUMMARY_PATH
            elif not self._formal_output:
                parent_selection_path = self._materialize_raw_output(
                    "B4FNC17__diagnostic_parent_selection", summary,
                )
            else:
                raise MutationAuditError("NC17_CAMPAIGN_SUMMARY_BINDING_MISSING")
            records = tuple(
                [("CAMPAIGN_SUMMARY", parent_selection_path)]
                + [("REGISTERED_A2_CASE_METADATA", path) for _, _, path in a2_rows]
            )
        alpha_force = float(parent["alpha"]) * float(parent["Q_ref_N"])
        for subvariant, (pair_name, right_variant, left_variant, base_ratio, mutant_ratio) in enumerate(pair_defs,start=1):
            base_lanes = [
                {
                    "lane_id": lane,
                    "right_Q_2": [alpha_force, base_ratio * alpha_force],
                    "left_mirror_Q_2": [base_ratio * alpha_force, alpha_force],
                }
                for lane in lanes
            ]
            base = {
                "lanes": base_lanes,
                "pair_kind": pair_name,
                "parent_level": parent,
                "left_variant": left_variant,
                "right_variant": right_variant,
            }
            mutant = deepcopy(base)
            for lane_row in mutant["lanes"]:
                lane_row["right_Q_2"][1] = mutant_ratio * alpha_force
            pointers = tuple(f"/payload/lanes/{index}/right_Q_2/1" for index in range(6))
            self._add_replay(
                "B4FNC17", subvariant, base_payload=base, mutant_payload=mutant,
                pointers=pointers, underlying_records=records,
                execution_mode=("REAL_EXECUTED_PATH" if not fallback else "RAW_ARTIFACT_MUTATION"),
                real_path_id=(
                    "FULL_REGISTERED_A2_SIX_LANE_PAIR"
                    if not fallback else "FROZEN_SIX_LANE_A2_NO_PARENT_FALLBACK"
                ),
                real_path_hit=(True if not fallback else bool(detector_result["complete"])),
                detail={
                    "actual_command_pair_built_for_all_six_lanes": True,
                    "fallback_no_parent_harness_used": fallback,
                    "fallback_a1_a2_or_physical_credit": False,
                    "campaign_A2_metadata_available": len(a2_rows) == 24,
                    "supplemental_detector_raw": (
                        None if detector_raw is None else _file_record(detector_raw)
                    ),
                    "detector_execution": detector_result,
                },
            )

    def _governance_candidate(self) -> dict[str, Any]:
        return {
            **{field: False for field in self.governance["required_false"]},
            **{field: None for field in self.targets["nc20_required_null_fields"]},
            "reported_label": "lowest_tested_reachable_alpha_in_registered_discrete_grid",
        }

    def _governance_failures(self, value: Mapping[str, Any]) -> list[str]:
        failures=[]
        required_false=self.governance["required_false"]
        for field, expected in required_false.items():
            if field in value and value[field] is not expected:
                failures.append(field)
        for field in self.governance["required_null_physical_inputs"]:
            if value.get(field,"MISSING") is not None:
                failures.append(field)
        if value.get("hardware_specification_released") is not False:
            failures.append("hardware_specification_released")
        return failures

    def nc18_20(self) -> None:
        candidate=self._governance_candidate()
        if self._governance_failures(candidate):
            raise MutationAuditError("NOMINAL_GOVERNANCE_CANDIDATE_NOT_CLEAN")
        base={"candidate":candidate}
        mutant=deepcopy(base); mutant["candidate"]["hardware_specification_released"]=True
        failures=self._governance_failures(mutant["candidate"])
        self._add_replay(
            "B4FNC18", 1, base_payload=base, mutant_payload=mutant,
            pointers=("/payload/candidate/hardware_specification_released",),
            underlying_records=(("FROZEN_GOVERNANCE_CONTRACT", GOVERNANCE_PATH),),
            execution_mode="RAW_ARTIFACT_MUTATION",
            real_path_id="FROZEN_GOVERNANCE_CANDIDATE",
            real_path_hit="hardware_specification_released" in failures,
            detail={"actual_governance_candidate_verifier_invoked":True,"failures":failures,
                    "synthetic_Q_ref_N_not_hardware_specification":forced.REFERENCE_FORCE_N},
        )
        for index,field in enumerate(self.targets["nc19_required_false_fields"],start=1):
            mutant=deepcopy(base); mutant["candidate"][field]=True
            failures=self._governance_failures(mutant["candidate"])
            self._add_replay(
                "B4FNC19", index, base_payload=base, mutant_payload=mutant,
                pointers=(f"/payload/candidate/{field}",),
                underlying_records=(("FROZEN_GOVERNANCE_CONTRACT", GOVERNANCE_PATH),),
                execution_mode="RAW_ARTIFACT_MUTATION",
                real_path_id="FROZEN_GOVERNANCE_CANDIDATE",
                real_path_hit=field in failures,
                detail={"actual_governance_candidate_verifier_invoked":True,"failures":failures},
            )
        for index,field in enumerate(self.targets["nc20_required_null_fields"],start=1):
            mutant=deepcopy(base); mutant["candidate"][field]=0.0
            failures=self._governance_failures(mutant["candidate"])
            self._add_replay(
                "B4FNC20", index, base_payload=base, mutant_payload=mutant,
                pointers=(f"/payload/candidate/{field}",),
                underlying_records=(("FROZEN_GOVERNANCE_CONTRACT", GOVERNANCE_PATH),),
                execution_mode="RAW_ARTIFACT_MUTATION",
                real_path_id="FROZEN_GOVERNANCE_CANDIDATE",
                real_path_hit=field in failures,
                detail={"actual_governance_candidate_verifier_invoked":True,"failures":failures},
            )

    @staticmethod
    def _nc21_no_domain_guard_evaluation(
        model: Any,
        service: Any,
        snapshot: Any,
        *,
        step_m: float = forced.CENTERED_SIGN_STEP_M,
    ) -> dict[str, Any]:
        """Execute the mutation-only active FK with the P-domain guard bypassed."""

        difference = float(step_m)
        if difference != forced.CENTERED_SIGN_STEP_M:
            raise MutationAuditError("NC21_CENTERED_STEP_DRIFT")
        service_vector = np.asarray(
            forced.b4e._service_to_active_vector(service), dtype=float,
        )
        target, nominal = forced._raw_contact_observations(model, service, snapshot)
        nominal_gaps = np.asarray([float(item.gap_m) for item in nominal], dtype=float)
        nominal_rates = np.asarray(
            [float(item.relative_normal_speed_m_s) for item in nominal], dtype=float,
        )
        pad_positions = np.vstack([
            np.asarray(item.pad_point_inertial_m, dtype=float) for item in nominal
        ])
        target_state = np.asarray(
            forced.b4e._target_to_post_vector(target), dtype=float,
        )
        p_coordinates = service_vector[13:15].copy()
        minus_p = np.tile(p_coordinates, (2, 1))
        plus_p = np.tile(p_coordinates, (2, 1))
        minus_gaps = np.empty((2, 2), dtype=float)
        plus_gaps = np.empty((2, 2), dtype=float)
        jacobian = np.empty((2, 2), dtype=float)
        for column, coordinate_index in enumerate(forced.P_COORDINATE_INDICES):
            plus = forced._service_with_coordinate(
                service, coordinate_index,
                float(p_coordinates[column]) + difference,
            )
            minus = forced._service_with_coordinate(
                service, coordinate_index,
                float(p_coordinates[column]) - difference,
            )
            plus_p[column] = np.asarray(plus.joint_coordinates_mixed[6:8], dtype=float)
            minus_p[column] = np.asarray(minus.joint_coordinates_mixed[6:8], dtype=float)
            _, plus_observations = forced._raw_contact_observations(
                model, plus, snapshot,
            )
            _, minus_observations = forced._raw_contact_observations(
                model, minus, snapshot,
            )
            plus_gaps[column] = np.asarray(
                [float(item.gap_m) for item in plus_observations], dtype=float,
            )
            minus_gaps[column] = np.asarray(
                [float(item.gap_m) for item in minus_observations], dtype=float,
            )
            jacobian[:, column] = (
                plus_gaps[column] - minus_gaps[column]
            ) / (2.0 * difference)
        values = (
            service_vector, pad_positions, target_state, nominal_gaps,
            nominal_rates, minus_p, plus_p, minus_gaps, plus_gaps, jacobian,
        )
        if any(not np.all(np.isfinite(value)) for value in values):
            raise MutationAuditError("NC21_NO_DOMAIN_GUARD_FK_NONFINITE")
        return {
            "schema": "SIM13_V4B4G_MUTATION_ONLY_NO_DOMAIN_GUARD_FK_V1",
            "evaluator_id": (
                "INDEPENDENT_B601_6R2P_ACTIVE_GEOMETRY_NO_P_DOMAIN_GUARD_V1"
            ),
            "mutation_audit_only": True,
            "domain_guard_bypassed": True,
            "selector_or_scientific_credit": False,
            "service_state_29": service_vector.tolist(),
            "P_coordinates_m": p_coordinates.tolist(),
            "pad_positions_inertial_m_left_right": pad_positions.tolist(),
            "target_state_13": target_state.tolist(),
            "nominal_gap_m_left_right": nominal_gaps.tolist(),
            "nominal_gap_rate_m_s_left_right": nominal_rates.tolist(),
            "centered_step_m": difference,
            "centered_minus_P_coordinates_m_by_column": minus_p.tolist(),
            "centered_plus_P_coordinates_m_by_column": plus_p.tolist(),
            "centered_minus_gap_m_by_column": minus_gaps.tolist(),
            "centered_plus_gap_m_by_column": plus_gaps.tolist(),
            "raw_gap_jacobian_P": jacobian.tolist(),
        }

    def _nc21_execution_context(
        self,
        case_id: str,
        metadata: Mapping[str, Any],
        arrays: Mapping[str, np.ndarray],
    ) -> dict[str, Any]:
        slot = next(
            row for row in self.schedule["slots"] if row["case_id"] == case_id
        )
        event = forced.b4e.rerun_b3_to_event(
            case_id, str(slot["method"]), float(slot["step_s"]),
        )
        model = forced.b4e.BranchedGripperServiceModel()
        acquisition = forced.b4e.acquisition_projection(model, event)
        if "stage_service_state_29" in arrays and len(arrays["stage_service_state_29"]):
            service_vector = np.asarray(arrays["stage_service_state_29"][0], dtype=float)
        else:
            service = forced.b4e.ServiceState(
                event.service.base_position_inertial_m.copy(),
                event.service.base_quaternion_body_to_inertial_wxyz.copy(),
                event.service.joint_coordinates_mixed.copy(),
                acquisition.eta_plus.copy(),
            )
            service_vector = forced.b4e._service_to_active_vector(service)
        service = forced.b4e._service_from_active_vector(service_vector)
        stage_time = (
            float(np.asarray(arrays["stage_time_s"], dtype=float)[0])
            if "stage_time_s" in arrays and len(arrays["stage_time_s"])
            else float(metadata["event_provenance"]["acquisition_time_s"])
        )
        nominal = forced.opening_signs(
            model, service, acquisition.snapshot,
            time_s=stage_time, stage_label="NC21_REGISTERED_BASE_STAGE_REPLAY",
        )
        stored_p = np.asarray(arrays["stage_P_coordinates_m"][0], dtype=float)
        stored_jacobian = np.asarray(arrays["stage_gap_jacobian_P"][0], dtype=float)
        base_matches = bool(
            np.max(np.abs(nominal.p_coordinates_m - stored_p)) <= 1.0e-12
            and np.max(np.abs(nominal.raw_gap_jacobian - stored_jacobian)) <= 1.0e-12
            and nominal.signs == forced.REGISTERED_OPENING_SIGNS
        )
        return {
            "slot": slot,
            "event": event,
            "model": model,
            "acquisition": acquisition,
            "service": service,
            "service_vector_29": np.asarray(service_vector, dtype=float),
            "stage_time_s": stage_time,
            "base_replay": nominal,
            "base_matches_registered_stage": base_matches,
        }

    def _execute_nc21_mutant_branch(
        self,
        context: Mapping[str, Any],
        target: Mapping[str, Any],
        *,
        subvariant_index: int,
        metadata_path: Path,
        npz_path: Path,
    ) -> tuple[Path, bool, dict[str, Any]]:
        model = context["model"]
        acquisition = context["acquisition"]
        service = context["service"]
        stage_time = float(context["stage_time_s"])
        branch = str(target.get("path", "DIRECT_DOMAIN_REJECT_NO_TRANSFORM"))
        if "side" in target:
            side_index = 0 if target["side"] == "left" else 1
            coordinate_index = forced.P_COORDINATE_INDICES[side_index]
            raw_service = forced._service_with_coordinate(
                service, coordinate_index, float(target["value_m"]),
            )
        else:
            side_index = 0
            coordinate_index = forced.P_COORDINATE_INDICES[side_index]
            raw_service = forced._service_with_coordinate(
                service, coordinate_index,
                float(forced.P_DOMAIN_M[side_index][1]) + 1.0e-9,
            )
        domain_failure: dict[str, Any] | None = None
        try:
            forced.opening_signs(
                model, raw_service, acquisition.snapshot,
                time_s=stage_time,
                stage_label=f"B4FNC21_SUPPLEMENTAL_SV{subvariant_index:02d}",
            )
        except forced.DomainExit as error:
            domain_failure = deepcopy(error.record)
        if domain_failure is None:
            raise MutationAuditError(
                f"NC21_NOMINAL_MUTANT_DID_NOT_DOMAIN_EXIT:{subvariant_index}"
            )
        raw_p = np.asarray(raw_service.joint_coordinates_mixed[6:8], dtype=float)
        transformed_service: Any | None = None
        if branch == "DIRECT_DOMAIN_REJECT_NO_TRANSFORM":
            transformed_p: list[float] | None = None
            policy_outcome = "G16_FAIL_DIRECT_OUT_OF_DOMAIN"
        elif branch == "CLIP_TO_UPPER_BOUND":
            transformed_service = forced._service_with_coordinate(
                raw_service, coordinate_index,
                float(forced.P_DOMAIN_M[side_index][1]),
            )
            transformed_p = np.asarray(
                transformed_service.joint_coordinates_mixed[6:8], dtype=float,
            ).tolist()
            policy_outcome = "G16_FAIL_CLIPPING_USED"
        else:
            if branch != "EXTRAPOLATE_AFTER_UPPER_BOUND":
                raise MutationAuditError("NC21_UNKNOWN_MUTANT_GEOMETRY_BRANCH")
            transformed_service = raw_service
            transformed_p = raw_p.tolist()
            policy_outcome = "G16_FAIL_EXTRAPOLATION_USED"
        no_domain_evaluation = (
            None
            if transformed_service is None
            else self._nc21_no_domain_guard_evaluation(
                model, transformed_service, acquisition.snapshot,
            )
        )
        branch_trace = [
            {
                "ordinal": 0,
                "operation": "APPLY_RAW_REGISTERED_MUTANT_P",
                "P_coordinates_m": raw_p.tolist(),
                "outcome": "APPLIED",
            },
            {
                "ordinal": 1,
                "operation": "FROZEN_P_DOMAIN_GUARD",
                "P_coordinates_m": raw_p.tolist(),
                "outcome": "DOMAIN_EXIT",
            },
        ]
        if transformed_p is None:
            branch_trace.extend((
                {
                    "ordinal": 2, "operation": "NO_TRANSFORM",
                    "P_coordinates_m": None, "outcome": "NOT_EXECUTED",
                },
                {
                    "ordinal": 3, "operation": "G16_POLICY",
                    "P_coordinates_m": raw_p.tolist(),
                    "outcome": policy_outcome,
                },
            ))
        else:
            branch_trace.extend((
                {
                    "ordinal": 2,
                    "operation": (
                        "CLIP_TO_UPPER_BOUND"
                        if branch == "CLIP_TO_UPPER_BOUND"
                        else "EXTRAPOLATE_IDENTITY_OUTSIDE_DOMAIN"
                    ),
                    "P_coordinates_m": transformed_p,
                    "outcome": "TRANSFORMED",
                },
                {
                    "ordinal": 3,
                    "operation": "MUTATION_ONLY_NO_DOMAIN_GUARD_FK",
                    "P_coordinates_m": transformed_p,
                    "outcome": "EXECUTED",
                },
                {
                    "ordinal": 4, "operation": "G16_POLICY",
                    "P_coordinates_m": transformed_p,
                    "outcome": policy_outcome,
                },
            ))
        branch_executed = bool(
            domain_failure is not None
            and (
                transformed_p is None
                or no_domain_evaluation is not None
            )
        )
        raw_payload = {
            "schema": "SIM13_V4B4G_GEOMETRY_CLIP_EXTRAPOLATE_TRACE_V1",
            "parent_id": "B4FNC21",
            "subvariant_index": int(subvariant_index),
            "source_case_metadata": _file_record(metadata_path),
            "source_case_npz": _file_record(npz_path),
            "stage_index": 0,
            "mutation_target": deepcopy(dict(target)),
            "nominal_service_state_29": np.asarray(
                context["service_vector_29"], dtype=float,
            ).tolist(),
            "acquisition_snapshot": forced.b4e.acquisition_to_json(
                acquisition, include_matrices=False,
            )["snapshot"],
            "raw_P_coordinates_m": raw_p.tolist(),
            "transformed_P_coordinates_m": transformed_p,
            "branch": branch,
            "domain_exit_record": domain_failure,
            "branch_trace": branch_trace,
            "no_domain_guard_evaluation": no_domain_evaluation,
            "claim_boundary": MUTATION_CREDIT_BOUNDARY,
        }
        path = self._materialize_raw_output(
            f"B4FNC21__SV{subvariant_index:02d}__geometry_clip_extrapolate_trace",
            raw_payload,
        )
        return path, branch_executed, {
            "branch": branch,
            "nominal_domain_failure": domain_failure,
            "branch_trace": branch_trace,
            "no_domain_guard_fk_executed": no_domain_evaluation is not None,
            "registered_base_stage_replayed": True,
            "registered_base_stage_exact_match": bool(
                context["base_matches_registered_stage"]
            ),
        }

    def nc21(self) -> None:
        case_id = self.targets["default_registered_forced_slot"]
        metadata, arrays, metadata_path, npz_path = self._registered_case(case_id)
        if len(arrays["stage_P_coordinates_m"]) == 0:
            raise MutationAuditError("NC21_REGISTERED_STAGE_TRACE_EMPTY")
        base={
            "P_coordinates_m":np.asarray(arrays["stage_P_coordinates_m"][0],dtype=float).tolist(),
            "centered_step_m":forced.CENTERED_SIGN_STEP_M,
            "raw_gap_jacobian_P":np.asarray(arrays["stage_gap_jacobian_P"][0],dtype=float).tolist(),
            "registered_signs":[1,1], "consumed_signs":[1,1],
            "clipping_used":False, "extrapolation_used":False,
            "terminal_status":metadata["terminal_status"],
        }
        context = self._nc21_execution_context(case_id, metadata, arrays)
        for index,target in enumerate(self.targets["P_domain_mutants"],start=1):
            mutant=deepcopy(base); detail={"target":target,"registered_case_id":case_id}
            if "side" in target:
                side=0 if target["side"]=="left" else 1
                mutant["P_coordinates_m"][side]=float(target["value_m"])
                pointer=f"/payload/P_coordinates_m/{side}"
            elif target["path"]=="CLIP_TO_UPPER_BOUND":
                mutant["clipping_used"]=True
                pointer="/payload/clipping_used"
            else:
                mutant["extrapolation_used"]=True
                pointer="/payload/extrapolation_used"
            mutant_raw, real_path_hit, execution = self._execute_nc21_mutant_branch(
                context, target, subvariant_index=index,
                metadata_path=metadata_path, npz_path=npz_path,
            )
            self._add_replay(
                "B4FNC21", index, base_payload=base, mutant_payload=mutant,
                pointers=(pointer,),
                underlying_records=(
                    ("REGISTERED_CASE_METADATA",metadata_path),
                    ("REGISTERED_CASE_RAW_NPZ",npz_path),
                    ("GEOMETRY_CLIP_EXTRAPOLATE_TRACE",mutant_raw),
                ),
                execution_mode="REAL_EXECUTED_PATH",
                real_path_id="EXECUTED_REGISTERED_A1_GEOMETRY_DOMAIN_MUTANT_PATH",
                real_path_hit=real_path_hit,
                detail={
                    **detail,
                    **execution,
                    "actual_registered_raw_geometry_stage_consumed":True,
                    "supplemental_geometry_mutant_raw": _file_record(mutant_raw),
                },
            )

    def nc22(self) -> None:
        report=self._governance_candidate()
        base={"report":report}
        expected_label="lowest_tested_reachable_alpha_in_registered_discrete_grid"
        for index,target in enumerate(self.targets["reporting_mutants"],start=1):
            mutant=deepcopy(base); mutant["report"].update(target)
            pointer=(
                "/payload/report/reported_label" if index==1
                else "/payload/report/minimum_required_force_or_work_claimed"
            )
            self._add_replay(
                "B4FNC22", index, base_payload=base, mutant_payload=mutant,
                pointers=(pointer,),
                underlying_records=(
                    ("FROZEN_GOVERNANCE_CONTRACT",GOVERNANCE_PATH),
                    ("FROZEN_REGISTERED_SCHEDULE",SCHEDULE_PATH),
                ),
                execution_mode="RAW_ARTIFACT_MUTATION",
                real_path_id="REGISTERED_SELECTOR_REPORT_BOUNDARY",
                real_path_hit=True,
                detail={"actual_selector_report_candidate_verifier_invoked":True,
                        "expected_reported_label":expected_label},
            )

    def _structured_source_binding(self) -> dict[str, Any]:
        summary, _ = self._load_campaign()
        manifest = self._active_source_manifest()
        freeze = summary.get("execution_source_freeze")
        if not isinstance(freeze, dict) or freeze.get("pass") is not True:
            raise MutationAuditError("CAMPAIGN_EXECUTION_SOURCE_FREEZE_BINDING_REQUIRED")
        terminal_path = Path(str(freeze.get("terminal_path", ""))).resolve()
        if not terminal_path.is_file():
            raise MutationAuditError("CAMPAIGN_EXECUTION_SOURCE_FREEZE_TERMINAL_MISSING")
        terminal = _file_record(terminal_path)
        expected_terminal = str(freeze.get(
            "expected_terminal_sha256",
            summary.get("expected_execution_source_freeze_terminal_sha256", ""),
        )).upper()
        if terminal["sha256"] != expected_terminal:
            raise MutationAuditError("CAMPAIGN_EXECUTION_SOURCE_FREEZE_TERMINAL_DRIFT")
        try:
            from b4g_execution.source_guard import verify_execution_source_freeze

            verified_freeze = verify_execution_source_freeze(
                PROJECT_ROOT, PHASE_ROOT, terminal_path, expected_terminal,
            )
        except Exception as error:
            raise MutationAuditError(
                "MUTATION_EXECUTION_SOURCE_FREEZE_REVERIFICATION_FAILED"
            ) from error
        if verified_freeze.get("pass") is not True:
            raise MutationAuditError("MUTATION_EXECUTION_SOURCE_FREEZE_NOT_PASS")
        supplemental_roles = {
            "MUTANT_DWELL_FORCE_TRACE",
            "A2_DETECTOR_SIX_LANE_TRACE",
            "GEOMETRY_CLIP_EXTRAPOLATE_TRACE",
        }
        supplemental_role_records: list[dict[str, Any]] = []
        for receipt in self.receipts:
            base_path = Path(str(receipt.base_artifact["path"]))
            if not base_path.is_absolute():
                base_path = (PROJECT_ROOT / base_path).resolve()
            bundle = _read_json(base_path)
            for record in bundle.get("artifact_records", []):
                if record.get("role") in supplemental_roles:
                    supplemental_role_records.append({
                        "receipt_id": receipt.receipt_id,
                        "role": str(record["role"]),
                        "path": str(record["path"]),
                        "bytes": int(record["bytes"]),
                        "sha256": str(record["sha256"]),
                    })
        supplemental_role_records.sort(
            key=lambda row: (row["receipt_id"], row["role"]),
        )
        selector = (self._campaign_summary or {}).get("selector", {})
        selected_parent = (
            selector.get("selected_parent_level")
            if isinstance(selector, Mapping) else None
        )
        expected_supplemental_count = 10 if selected_parent is None else 8
        if len(supplemental_role_records) != expected_supplemental_count:
            raise MutationAuditError(
                "SUPPLEMENTAL_ROLE_INVENTORY_COUNT_MISMATCH:"
                f"expected={expected_supplemental_count}:"
                f"actual={len(supplemental_role_records)}"
            )
        inventory_core = {
            "receipt_count": len(self.receipts),
            "base_sha256s": sorted(row.nominal_input_sha256 for row in self.receipts),
            "mutant_sha256s": sorted(row.mutant_input_sha256 for row in self.receipts),
            "patch_sha256s": sorted(row.patch_artifact["sha256"] for row in self.receipts),
            "supplemental_role_records": supplemental_role_records,
        }
        return {
            "mutation_spec": _file_record(MUTATION_SPEC_PATH),
            "preregistration_gate": _file_record(PREREG_GATE_PATH),
            "preregistration_terminal": _file_record(PREREG_TERMINAL_PATH),
            "preregistration_source_manifest": _file_record(PREREG_SOURCE_MANIFEST_PATH),
            "campaign_summary": _file_record(CAMPAIGN_SUMMARY_PATH),
            "execution_source_manifest": _file_record(manifest),
            "execution_source_freeze_terminal": terminal,
            "execution_source_freeze_expected_terminal_sha256": expected_terminal,
            "mutation_executor": _file_record(Path(__file__)),
            "independent_validator": _file_record(INDEPENDENT_VALIDATOR_PATH),
            "artifact_inventory": {
                **inventory_core,
                "inventory_sha256": _canonical_sha(inventory_core),
            },
            "all_required_files_byte_bound": True,
        }

    def run_smoke(self, *, attempt_prepared: bool = False) -> dict[str, Any]:
        if attempt_prepared:
            self.receipts.clear(); self._fixture_cache = None
        else:
            self._prepare_attempt(mode="SMOKE")
        fixture=self.finite_fixture()
        self._finite_harness_raw_path(fixture)
        self.nc01()
        self.nc07()
        self.nc09(); self.nc10(); self.nc16(); self.nc18_20(); self.nc22()
        payload={
            "schema":"SIM13_V4B4G_MUTATION_HARNESS_SMOKE_V1",
            "scope":"BOUNDED_SMOKE_ONLY_NOT_THE_65_SUBVARIANT_AUDIT",
            "source_binding":self.source_binding,
            "finite_event_harness_precondition":fixture["precondition"],
            "smoke_receipts":[row.as_dict() for row in self.receipts],
            "smoke_receipt_count":len(self.receipts),
            "all_smoke_mutations_killed":all(row.killed for row in self.receipts),
            "full_65_executed":False,
            "final":False, "audited":False, "validator_pass_claimed":False,
            "dictionary_flag_only_mutation_used":False,
            "campaign_or_scientific_credit_from_mutations":False,
            "claim_boundary":CLAIM_BOUNDARY,
            "mutation_credit_boundary":MUTATION_CREDIT_BOUNDARY,
            "memory":{"memory_gate_applicable":False,"memory_gate_passed":False,"owner_override_used":False,"classification":"DIAGNOSTIC_ONLY"},
        }
        if not payload["all_smoke_mutations_killed"]:
            raise MutationAuditError("SMOKE_MUTATION_NOT_KILLED")
        return payload

    def run_full(self, *, attempt_prepared: bool = False) -> dict[str, Any]:
        if attempt_prepared:
            self.receipts.clear(); self._fixture_cache = None
        else:
            self._prepare_attempt(mode="FULL_65")
        self._load_campaign()
        self._active_source_manifest()
        fixture=self.finite_fixture()
        self._finite_harness_raw_path(fixture)
        self.nc01(); self.nc02(); self.nc03(); self.nc04(); self.nc05_06(); self.nc07(); self.nc08(); self.nc09(); self.nc10()
        self.nc11(); self.nc12(); self.nc13(); self.nc14(); self.nc15(); self.nc16(); self.nc17(); self.nc18_20(); self.nc21(); self.nc22()
        expected_counts={f"B4FNC{i:02d}":int(row["count"]) for i,row in enumerate(self.variant_rows,start=1)}
        parent_summaries=[]
        for parent_id,expected_count in expected_counts.items():
            rows=[row for row in self.receipts if row.parent_id==parent_id]
            expected_gate=self.variant_rows[int(parent_id[-2:])-1]["expected_gate"]
            parent_summaries.append({
                "parent_id":parent_id,"expected_gate":expected_gate,"expected_count":expected_count,
                "executed_count":len(rows),"killed_count":sum(row.killed for row in rows),
                "passed":len(rows)==expected_count and all(row.killed for row in rows),
            })
        receipt_ids=[row.receipt_id for row in self.receipts]
        mutant_input_hashes=[row.mutant_input_sha256 for row in self.receipts]
        semantic_hashes=[
            str(row.execution_detail.get("semantic_mutation_sha256", ""))
            for row in self.receipts
        ]
        unique=(
            len(receipt_ids)==len(set(receipt_ids))==65
            and len(mutant_input_hashes)==len(set(mutant_input_hashes))==65
            and len(semantic_hashes)==len(set(semantic_hashes))==65
            and all(re.fullmatch(r"[0-9A-F]{64}", value) for value in semantic_hashes)
        )
        all_killed=len(self.receipts)==65 and all(row.killed for row in self.receipts)
        source_binding = self._structured_source_binding()
        payload={
            "schema":"SIM13_V4B4G_NEGATIVE_CONTROL_EVIDENCE_V1",
            "scope":"REAL_RAW_ARTIFACT_OR_EXECUTED_PATH_MUTATIONS_ONLY",
            "required_parent_ids":self.spec["required_parent_ids"],
            "subvariant_counts_by_parent":self.spec["subvariant_counts_by_parent"],
            "source_binding":source_binding,
            "finite_event_harness_precondition":fixture["precondition"],
            "counts":{"required_parent_count":22,"total_subvariants":65,
                      "executed_subvariants":len(self.receipts),
                      "killed_subvariants":sum(row.killed for row in self.receipts),
                      "unique_subvariants":min(
                          len(set(receipt_ids)), len(set(mutant_input_hashes)),
                          len(set(semantic_hashes)),
                      ),
                      "executed":len(self.receipts),"killed":sum(row.killed for row in self.receipts),
                      "unique":len(set(receipt_ids))},
            "parent_summaries":parent_summaries,
            "receipts":[row.as_dict() for row in self.receipts],
            "all_65_subvariants_unique_hit_and_killed":bool(unique and all_killed and all(row["passed"] for row in parent_summaries)),
            "final":False,
            "audited":False,
            "validator_pass_claimed":False,
            "dictionary_flag_only_mutation_used":False,
            "campaign_or_scientific_credit_from_mutations":False,
            "campaign_negative_control_hook_closed":False,
            "executor_bundle_generation_complete":True,
            "claim_boundary":CLAIM_BOUNDARY,
            "mutation_credit_boundary":MUTATION_CREDIT_BOUNDARY,
            "capabilities":{"registered_negative_controls_executed":True,"physical_release_implemented":False,
                            "current_system_bound":False,"formal_nc19_credit":False,"owner_authorized":False,
                            "production_ready":False,"release_authorized":False,"next_stage_authorized":False},
            "memory":{"memory_gate_applicable":False,"memory_gate_passed":False,"owner_override_used":False,"classification":"DIAGNOSTIC_ONLY"},
        }
        if not payload["all_65_subvariants_unique_hit_and_killed"]:
            raise MutationAuditError("FULL_MUTATION_AUDIT_FAILED_CLOSED")
        return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke",action="store_true",help="run bounded pre-campaign mutation smoke")
    mode.add_argument("--execute",action="store_true",help="execute and publish all 65 frozen subvariants")
    parser.add_argument(
        "--no-write",
        action="store_true",
        help=(
            "diagnostic execution without the final JSON; requires an explicit "
            "nonformal --output-root and may clean/write attempt artifacts only "
            "inside that diagnostic root"
        ),
    )
    parser.add_argument(
        "--output-root", type=Path, default=None,
        help="explicit mutation output root; nondefault roots remain diagnostic only",
    )
    args=parser.parse_args(argv)
    requested_root = OUTPUT_ROOT if args.output_root is None else args.output_root
    requested_is_formal = Path(requested_root).resolve() == OUTPUT_ROOT.resolve()
    if args.no_write and requested_is_formal:
        raise MutationAuditError(
            "MUTATION_NO_WRITE_REQUIRES_EXPLICIT_NONFORMAL_OUTPUT_ROOT"
        )
    if args.smoke and requested_is_formal:
        raise MutationAuditError(
            "MUTATION_SMOKE_REQUIRES_EXPLICIT_NONFORMAL_OUTPUT_ROOT"
        )
    prepared_root = _bootstrap_attempt(
        requested_root, mode="SMOKE" if args.smoke else "FULL_65",
    )
    audit=MutationAudit(output_root=prepared_root)
    payload=(
        audit.run_smoke(attempt_prepared=True)
        if args.smoke else audit.run_full(attempt_prepared=True)
    )
    output=audit._output_path(SMOKE_OUTPUT_PATH.name if args.smoke else FULL_OUTPUT_PATH.name)
    if not args.no_write:
        _atomic_write_json(output,payload)
        record=_file_record(output)
        if args.execute:
            audit._complete_attempt(output)
    else:
        record={"path":str(output),"bytes":None,"sha256":None}
    print(json.dumps({
        "mode":"SMOKE" if args.smoke else "FULL_65",
        "passed":payload.get("all_smoke_mutations_killed",payload.get("all_65_subvariants_unique_hit_and_killed",False)),
        "receipt_count":payload.get("smoke_receipt_count",payload.get("counts",{}).get("executed")),
        "output":record,
        "claim_boundary":CLAIM_BOUNDARY,
    },sort_keys=True,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
