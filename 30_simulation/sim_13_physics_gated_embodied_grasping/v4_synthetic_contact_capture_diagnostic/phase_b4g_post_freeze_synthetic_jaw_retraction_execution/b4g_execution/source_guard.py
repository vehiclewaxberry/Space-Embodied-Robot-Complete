"""Byte binding, recursive parent DAG and protected-asset guards."""

from __future__ import annotations

import os
from pathlib import Path
import stat
from typing import Any, Iterable, Mapping

from .io import canonical_sha256, read_json, sha256_file


class SourceGuardError(RuntimeError):
    """A frozen source, recursive record, or protected asset drifted."""


EXECUTION_SOURCE_FREEZE_CLAIM_BOUNDARY = (
    "execution source bytes frozen for later B4G campaign invocation only; "
    "no slot executed, scientific gate evaluated, or campaign credit granted"
)


PREREGISTRATION_ANCHORS = (
    {
        "id": "b4g_preregistration_gate",
        "path": "results/SIM13_V4B4G_PREREGISTRATION_GATE_V1.json",
        "bytes": 6476,
        "sha256": "288D12EA9120055C46CAE6EC18B397303DB38423DCF92A3FD30D32BBDD215A7E",
        "role": "SIGNED_B4G_PREREGISTRATION_GATE",
    },
    {
        "id": "b4g_preregistration_terminal",
        "path": "results/SIM13_V4B4G_PREREGISTRATION_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json",
        "bytes": 1404,
        "sha256": "ED3FB03CAC4FA5C8A0758E1D97766D55D576B34870E43D0EBBF8991C6603553B",
        "role": "SIGNED_B4G_PREREGISTRATION_TERMINAL",
    },
    {
        "id": "b4g_preregistration_source_manifest",
        "path": "results/SIM13_V4B4G_PREREGISTRATION_SOURCE_MANIFEST_V1.json",
        "bytes": 7410,
        "sha256": "04E559FC4F846DEC3429B5F37110EF128F8308A7B955C6BD1DD0BD3EC6F88FA4",
        "role": "SIGNED_B4G_PREREGISTRATION_SOURCE_MANIFEST",
    },
)


def _project_record(project_root: Path, path: Path, *, identifier: str, role: str) -> dict[str, Any]:
    if not path.is_file():
        raise SourceGuardError(f"SOURCE_MISSING:{identifier}:{path}")
    return {
        "id": identifier,
        "path": path.resolve().relative_to(project_root.resolve()).as_posix(),
        "role": role,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _resolve_declared(project_root: Path, local_root: Path, declared: str) -> Path:
    value = Path(str(declared).replace("/", str(Path('/'))))
    if value.is_absolute():
        return value
    project_candidate = project_root / value
    if project_candidate.is_file():
        return project_candidate
    return local_root / value


def _verify_rows(
    rows: Iterable[Mapping[str, Any]],
    *,
    project_root: Path,
    local_root: Path,
    label: str,
) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        declared = str(row.get("path", ""))
        path = _resolve_declared(project_root, local_root, declared)
        identifier = str(row.get("id", row.get("role", f"ROW_{index}")))
        actual_bytes = path.stat().st_size if path.is_file() else None
        actual_sha = sha256_file(path) if path.is_file() else None
        passed = bool(
            path.is_file()
            and actual_bytes == int(row.get("bytes", -1))
            and actual_sha == str(row.get("sha256", "")).upper()
        )
        record = {
            "id": identifier,
            "role": row.get("role"),
            "declared_path": declared,
            "resolved_path": path.resolve().as_posix(),
            "declared_bytes": row.get("bytes"),
            "actual_bytes": actual_bytes,
            "declared_sha256": str(row.get("sha256", "")).upper(),
            "actual_sha256": actual_sha,
            "pass": passed,
        }
        verified.append(record)
        if not passed:
            raise SourceGuardError(f"{label}_RECORD_MISMATCH:{identifier}")
    return verified


def verify_recursive_parents(
    project_root: Path,
    phase_root: Path,
    bindings: Mapping[str, Any],
) -> dict[str, Any]:
    """Independently walk B4F terminal/evidence, B4E terminal/evidence/source and B4 terminal."""

    sources = list(bindings.get("sources", []))
    if len(sources) != 11:
        raise SourceGuardError("B4G_DIRECT_BINDING_COUNT_NOT_11")
    direct = _verify_rows(
        sources, project_root=project_root, local_root=project_root,
        label="B4G_DIRECT_BINDING",
    )
    by_id = {str(row["id"]): row for row in sources}

    b4f_terminal_path = project_root / by_id["b4f_terminal"]["path"]
    b4f_terminal = read_json(b4f_terminal_path)
    if b4f_terminal.get("self_excluded") is not True or b4f_terminal.get("acyclic") is not True:
        raise SourceGuardError("B4F_TERMINAL_NOT_SELF_EXCLUDED_ACYCLIC")
    b4f_rows = list(b4f_terminal.get("records", []))
    if b4f_terminal_path.name in {Path(str(row.get("path", ""))).name for row in b4f_rows}:
        raise SourceGuardError("B4F_TERMINAL_SELF_REFERENCE")
    b4f_records = _verify_rows(
        b4f_rows, project_root=project_root, local_root=b4f_terminal_path.parent.parent,
        label="B4F_TERMINAL",
    )
    b4f_evidence_row = next(
        (row for row in b4f_rows if row.get("role") == "B4F_CONTRACT_EVIDENCE_DAG"), None,
    )
    if b4f_evidence_row is None:
        raise SourceGuardError("B4F_EVIDENCE_DAG_RECORD_MISSING")
    b4f_evidence_path = _resolve_declared(
        project_root, b4f_terminal_path.parent.parent, str(b4f_evidence_row["path"]),
    )
    b4f_evidence = read_json(b4f_evidence_path)
    if b4f_evidence.get("self_excluded") is not True or b4f_evidence.get("acyclic") is not True:
        raise SourceGuardError("B4F_EVIDENCE_NOT_SELF_EXCLUDED_ACYCLIC")
    b4f_evidence_records = _verify_rows(
        b4f_evidence.get("records", []), project_root=project_root,
        local_root=b4f_evidence_path.parent, label="B4F_EVIDENCE",
    )

    b4e_terminal_path = project_root / by_id["b4e_terminal"]["path"]
    b4e_root = b4e_terminal_path.parent.parent
    b4e_terminal = read_json(b4e_terminal_path)
    if b4e_terminal.get("self_excluded") is not True:
        raise SourceGuardError("B4E_TERMINAL_NOT_SELF_EXCLUDED")
    b4e_rows = list(b4e_terminal.get("entries", []))
    if b4e_terminal_path.name in {Path(str(row.get("path", ""))).name for row in b4e_rows}:
        raise SourceGuardError("B4E_TERMINAL_SELF_REFERENCE")
    b4e_terminal_records = _verify_rows(
        b4e_rows, project_root=project_root, local_root=b4e_root,
        label="B4E_TERMINAL",
    )
    b4e_evidence_row = next(
        (row for row in b4e_rows if row.get("role") == "EVIDENCE_DAG"), None,
    )
    if b4e_evidence_row is None:
        raise SourceGuardError("B4E_EVIDENCE_DAG_RECORD_MISSING")
    b4e_evidence_path = _resolve_declared(project_root, b4e_root, str(b4e_evidence_row["path"]))
    b4e_evidence = read_json(b4e_evidence_path)
    if b4e_evidence.get("self_excluded") is not True:
        raise SourceGuardError("B4E_EVIDENCE_NOT_SELF_EXCLUDED")
    b4e_evidence_rows = list(b4e_evidence.get("files", []))
    b4e_evidence_records = _verify_rows(
        b4e_evidence_rows, project_root=project_root, local_root=b4e_root,
        label="B4E_EVIDENCE",
    )
    b4e_source_row = next(
        (row for row in b4e_evidence_rows if row.get("role") == "SOURCE_DAG_ROOT"), None,
    )
    if b4e_source_row is None:
        raise SourceGuardError("B4E_SOURCE_DAG_RECORD_MISSING")
    b4e_source_path = _resolve_declared(project_root, b4e_root, str(b4e_source_row["path"]))
    b4e_source = read_json(b4e_source_path)
    if b4e_source.get("self_excluded") is not True:
        raise SourceGuardError("B4E_SOURCE_NOT_SELF_EXCLUDED")
    b4e_source_rows = list(b4e_source.get("sources", []))
    b4e_source_records = _verify_rows(
        b4e_source_rows, project_root=project_root, local_root=project_root,
        label="B4E_SOURCE",
    )
    b4_terminal_row = next(
        (row for row in b4e_source_rows if row.get("id") == "b4_contract_terminal_manifest"), None,
    )
    b4_gate_row = next(
        (row for row in b4e_source_rows if row.get("id") == "b4_contract_audited_gate"), None,
    )
    if b4_terminal_row is None or b4_gate_row is None:
        raise SourceGuardError("B4_TERMINAL_OR_GATE_NOT_RECURSIVELY_BOUND")
    b4_terminal_path = _resolve_declared(project_root, project_root, str(b4_terminal_row["path"]))
    b4_terminal = read_json(b4_terminal_path)
    if b4_terminal.get("self_excluded") is not True or b4_terminal.get("acyclic") is not True:
        raise SourceGuardError("B4_TERMINAL_NOT_SELF_EXCLUDED_ACYCLIC")
    b4_rows = list(b4_terminal.get("records", []))
    b4_records = _verify_rows(
        b4_rows, project_root=project_root, local_root=b4_terminal_path.parent.parent,
        label="B4_TERMINAL",
    )
    if str(b4_gate_row["sha256"]).upper() != "55441DFF42C92235B14DF9C810B013ADC2E59D5607D7697A5D85795149431D92":
        raise SourceGuardError("FROZEN_B4_GATE_HASH_CHANGED")
    if str(b4_terminal_row["sha256"]).upper() != "09D26114D50358FD488BF51912C68FDB3993AB0035201B22478D7CD9A9B7B76E":
        raise SourceGuardError("FROZEN_B4_TERMINAL_HASH_CHANGED")

    return {
        "pass": True,
        "direct_binding_count": len(direct),
        "direct_bindings": direct,
        "b4f_terminal_records": b4f_records,
        "b4f_evidence_records": b4f_evidence_records,
        "b4e_terminal_records": b4e_terminal_records,
        "b4e_evidence_records": b4e_evidence_records,
        "b4e_source_records": b4e_source_records,
        "b4_terminal_records": b4_records,
        "frozen_b4_gate_sha256": str(b4_gate_row["sha256"]).upper(),
        "frozen_b4_terminal_sha256": str(b4_terminal_row["sha256"]).upper(),
    }


def verify_preregistration_source_manifest(
    project_root: Path,
    phase_root: Path,
) -> dict[str, Any]:
    """Expand and verify all 19 records in the signed preregistration manifest."""

    anchor = next(
        row for row in PREREGISTRATION_ANCHORS
        if row["id"] == "b4g_preregistration_source_manifest"
    )
    manifest_path = phase_root / anchor["path"]
    if (
        not manifest_path.is_file()
        or manifest_path.stat().st_size != anchor["bytes"]
        or sha256_file(manifest_path) != anchor["sha256"]
    ):
        raise SourceGuardError("B4G_PREREGISTRATION_SOURCE_MANIFEST_ANCHOR_MISMATCH")
    manifest = read_json(manifest_path)
    rows = list(manifest.get("records", []))
    if manifest.get("schema") != "SIM13_V4B4G_PREREGISTRATION_SOURCE_MANIFEST_V1":
        raise SourceGuardError("B4G_PREREGISTRATION_SOURCE_MANIFEST_SCHEMA_MISMATCH")
    if manifest.get("self_excluded") is not True:
        raise SourceGuardError("B4G_PREREGISTRATION_SOURCE_MANIFEST_NOT_SELF_EXCLUDED")
    if int(manifest.get("record_count", -1)) != 19 or len(rows) != 19:
        raise SourceGuardError("B4G_PREREGISTRATION_SOURCE_RECORD_COUNT_NOT_19")
    paths = [str(row.get("path", "")) for row in rows]
    if len(paths) != len(set(paths)) or manifest_path.name in {Path(path).name for path in paths}:
        raise SourceGuardError("B4G_PREREGISTRATION_SOURCE_RECORD_DUPLICATE_OR_SELF_REFERENCE")
    verified = _verify_rows(
        rows, project_root=project_root, local_root=project_root,
        label="B4G_PREREGISTRATION_SOURCE",
    )
    return {
        "pass": True,
        "schema": manifest["schema"],
        "self_excluded": True,
        "record_count": 19,
        "manifest_bytes": manifest_path.stat().st_size,
        "manifest_sha256": sha256_file(manifest_path),
        "records": verified,
        "records_canonical_sha256": canonical_sha256(verified),
    }


def verify_execution_source_freeze(
    project_root: Path,
    phase_root: Path,
    terminal_path: Path,
    expected_terminal_sha256: str,
) -> dict[str, Any]:
    """Verify the externally signed terminal -> gate -> source manifest chain."""

    expected = str(expected_terminal_sha256).upper()
    if len(expected) != 64 or any(character not in "0123456789ABCDEF" for character in expected):
        raise SourceGuardError("EXECUTION_SOURCE_FREEZE_EXPECTED_SHA256_INVALID")
    terminal_file = require_plain_file_under_root(
        terminal_path, project_root, label="EXECUTION_SOURCE_FREEZE_TERMINAL",
    )
    if sha256_file(terminal_file) != expected:
        raise SourceGuardError("EXECUTION_SOURCE_FREEZE_TERMINAL_SHA256_MISMATCH")
    terminal = read_json(terminal_file)
    terminal_fields = {
        "schema", "self_excluded", "acyclic", "records", "source_count",
        "source_inventory_sha256", "claim_boundary",
    }
    record_fields = {"id", "role", "path", "bytes", "sha256"}
    if set(terminal) != terminal_fields or terminal.get("schema") != (
        "SIM13_V4B4G_EXECUTION_SOURCE_FREEZE_TERMINAL_"
        "SELF_EXCLUDED_MANIFEST_V1"
    ):
        raise SourceGuardError("EXECUTION_SOURCE_FREEZE_TERMINAL_SCHEMA_OR_FIELDS")
    if terminal.get("self_excluded") is not True or terminal.get("acyclic") is not True:
        raise SourceGuardError("EXECUTION_SOURCE_FREEZE_TERMINAL_NOT_SELF_EXCLUDED_ACYCLIC")
    terminal_rows = terminal.get("records")
    if (
        not isinstance(terminal_rows, list)
        or len(terminal_rows) != 1
        or not isinstance(terminal_rows[0], Mapping)
        or set(terminal_rows[0]) != record_fields
        or terminal_rows[0].get("id") != "b4g_execution_source_freeze_gate"
        or terminal_rows[0].get("role") != "EXECUTION_SOURCE_FREEZE_GATE"
        or terminal_file.name in {
        Path(str(row.get("path", ""))).name for row in terminal_rows
        }
    ):
        raise SourceGuardError("EXECUTION_SOURCE_FREEZE_TERMINAL_RECORDS_INVALID")
    terminal_records = _verify_rows(
        terminal_rows, project_root=project_root, local_root=terminal_file.parent,
        label="EXECUTION_SOURCE_FREEZE_TERMINAL",
    )
    gate_row = terminal_rows[0]
    gate_path = require_plain_file_under_root(
        _resolve_declared(
            project_root, terminal_file.parent, str(gate_row["path"]),
        ),
        project_root,
        label="EXECUTION_SOURCE_FREEZE_GATE",
    )
    gate = read_json(gate_path)
    gate_fields = {
        "schema", "final", "execution_source_manifest", "source_count",
        "source_inventory_sha256", "claim_boundary",
    }
    if set(gate) != gate_fields or gate.get("schema") != (
        "SIM13_V4B4G_EXECUTION_SOURCE_FREEZE_GATE_V1"
    ):
        raise SourceGuardError("EXECUTION_SOURCE_FREEZE_GATE_SCHEMA_OR_FIELDS")
    if gate.get("final") is not True:
        raise SourceGuardError("EXECUTION_SOURCE_FREEZE_GATE_NOT_FINAL")
    manifest_row = gate.get("execution_source_manifest")
    if (
        not isinstance(manifest_row, Mapping)
        or set(manifest_row) != record_fields
        or manifest_row.get("id") != "b4g_execution_source_manifest"
        or manifest_row.get("role") != "EXECUTION_SOURCE_MANIFEST"
    ):
        raise SourceGuardError("EXECUTION_SOURCE_FREEZE_MANIFEST_RECORD_MISSING")
    manifest_verified = _verify_rows(
        [manifest_row], project_root=project_root, local_root=gate_path.parent,
        label="EXECUTION_SOURCE_FREEZE_GATE",
    )[0]
    manifest_path = require_plain_file_under_root(
        _resolve_declared(
            project_root, gate_path.parent, str(manifest_row["path"]),
        ),
        project_root,
        label="EXECUTION_SOURCE_MANIFEST",
    )
    manifest = read_json(manifest_path)
    manifest_fields = {
        "schema", "self_excluded", "source_count", "sources",
        "source_inventory_sha256", "claim_boundary",
    }
    if set(manifest) != manifest_fields or manifest.get("schema") != (
        "SIM13_V4B4G_EXECUTION_SOURCE_MANIFEST_V1"
    ):
        raise SourceGuardError("EXECUTION_SOURCE_MANIFEST_SCHEMA_OR_FIELDS")
    if manifest.get("self_excluded") is not True:
        raise SourceGuardError("EXECUTION_SOURCE_MANIFEST_NOT_SELF_EXCLUDED")
    raw_sources = manifest.get("sources")
    if not isinstance(raw_sources, list) or any(
        not isinstance(row, Mapping) or set(row) != record_fields
        for row in raw_sources
    ):
        raise SourceGuardError("EXECUTION_SOURCE_MANIFEST_SOURCE_RECORD_FIELDS")
    source_rows = list(raw_sources)
    declared_count = int(manifest.get("source_count", -1))
    if declared_count != len(source_rows) or not source_rows:
        raise SourceGuardError("EXECUTION_SOURCE_MANIFEST_RECORD_COUNT_MISMATCH")
    paths = [str(row.get("path", "")) for row in source_rows]
    if len(paths) != len(set(paths)) or manifest_path.name in {Path(path).name for path in paths}:
        raise SourceGuardError("EXECUTION_SOURCE_MANIFEST_DUPLICATE_OR_SELF_REFERENCE")
    verified_sources = _verify_rows(
        source_rows, project_root=project_root, local_root=project_root,
        label="EXECUTION_SOURCE_MANIFEST",
    )
    current = local_source_inventory(project_root, phase_root)
    if source_rows != current:
        raise SourceGuardError("EXECUTION_SOURCE_MANIFEST_NOT_EXACT_CURRENT_ALLOWLIST_INVENTORY")
    inventory_sha256 = canonical_sha256(source_rows)
    if (
        manifest.get("source_inventory_sha256") != inventory_sha256
        or gate.get("source_inventory_sha256") != inventory_sha256
        or terminal.get("source_inventory_sha256") != inventory_sha256
        or manifest.get("source_count") != len(source_rows)
        or gate.get("source_count") != len(source_rows)
        or terminal.get("source_count") != len(source_rows)
    ):
        raise SourceGuardError(
            "EXECUTION_SOURCE_FREEZE_COUNT_OR_INVENTORY_SHA256_INCONSISTENT"
        )
    if not (
        manifest.get("claim_boundary")
        == gate.get("claim_boundary")
        == terminal.get("claim_boundary")
        == EXECUTION_SOURCE_FREEZE_CLAIM_BOUNDARY
    ):
        raise SourceGuardError("EXECUTION_SOURCE_FREEZE_CLAIM_BOUNDARY_MISMATCH")
    return {
        "pass": True,
        "terminal_path": terminal_file.as_posix(),
        "expected_terminal_sha256": expected,
        "terminal_bytes": terminal_file.stat().st_size,
        "terminal_records": terminal_records,
        "gate_path": gate_path.as_posix(),
        "gate_sha256": sha256_file(gate_path),
        "manifest_path": manifest_path.as_posix(),
        "manifest_sha256": sha256_file(manifest_path),
        "source_count": len(verified_sources),
        "sources": verified_sources,
        "sources_canonical_sha256": canonical_sha256(verified_sources),
    }


def _is_directory_link_or_reparse(path: Path) -> bool:
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


def _assert_walk_root_chain(
    project_root: Path,
    phase_root: Path,
    *,
    label: str,
) -> None:
    project = Path(os.path.abspath(project_root))
    phase = Path(os.path.abspath(phase_root))
    try:
        relative = phase.relative_to(project)
    except ValueError as error:
        raise SourceGuardError(f"{label}_PHASE_OUTSIDE_PROJECT") from error
    current = project
    for part in (Path(), *relative.parts):
        if part != Path():
            current = current / part
        if os.path.lexists(current) and _is_directory_link_or_reparse(current):
            raise SourceGuardError(
                f"{label}_ROOT_CHAIN_LINK_OR_REPARSE:{current.as_posix()}"
            )


def require_plain_file_under_root(
    path: Path,
    root: Path,
    *,
    label: str,
) -> Path:
    nominal = Path(os.path.abspath(path))
    root_absolute = Path(os.path.abspath(root))
    try:
        nominal.parent.relative_to(root_absolute)
    except ValueError as error:
        raise SourceGuardError(f"{label}_OUTSIDE_CONTROLLED_ROOT:{nominal}") from error
    _assert_walk_root_chain(
        root_absolute, nominal.parent, label=f"{label}_PARENT",
    )
    if (
        not os.path.lexists(nominal)
        or _is_directory_link_or_reparse(nominal)
        or not nominal.is_file()
    ):
        raise SourceGuardError(f"{label}_NOT_PLAIN_REGULAR_FILE:{nominal}")
    return nominal


def local_source_inventory(project_root: Path, phase_root: Path) -> list[dict[str, Any]]:
    """Inventory only source/test/contract allowlisted files, never derived JSON evidence."""

    excluded_dirs = {
        "evidence", "results", "__pycache__", ".pytest_cache", ".smoke", "raw_cases",
    }
    def excluded_part(part: str) -> bool:
        return bool(
            part in excluded_dirs
            or part.startswith(".pytest")
            or part.startswith(".smoke")
        )

    _assert_walk_root_chain(project_root, phase_root, label="LOCAL_SOURCE_INVENTORY")

    # Prune generated trees before descent.  Filtering only after ``rglob``
    # still walks arbitrarily deep pytest basetemps and can hit Windows path
    # limits before the derived file is rejected.
    candidates: list[Path] = []
    def walk_error(error: OSError) -> None:
        raise SourceGuardError(
            f"LOCAL_SOURCE_INVENTORY_WALK_ERROR:{error}"
        ) from error

    for current, directory_names, file_names in os.walk(
        phase_root, topdown=True, onerror=walk_error, followlinks=False,
    ):
        current_path = Path(current)
        for name in directory_names:
            if not excluded_part(name) and _is_directory_link_or_reparse(
                current_path / name
            ):
                raise SourceGuardError(
                    "LOCAL_SOURCE_INVENTORY_DIRECTORY_LINK_OR_REPARSE:"
                    f"{(current_path / name).as_posix()}"
                )
        for name in file_names:
            if not excluded_part(name) and _is_directory_link_or_reparse(
                current_path / name
            ):
                raise SourceGuardError(
                    "LOCAL_SOURCE_INVENTORY_FILE_LINK_OR_REPARSE:"
                    f"{(current_path / name).as_posix()}"
                )
        directory_names[:] = sorted(
            name for name in directory_names if not excluded_part(name)
        )
        candidates.extend(current_path / name for name in sorted(file_names))
    records: list[dict[str, Any]] = []
    for path in sorted(candidates, key=lambda item: item.relative_to(phase_root).as_posix()):
        relative = path.relative_to(phase_root)
        if not path.is_file() or any(
            excluded_part(part)
            for part in relative.parts
        ):
            continue
        is_python_source = path.suffix.lower() == ".py"
        is_frozen_contract = (
            len(relative.parts) >= 2
            and relative.parts[0] == "contracts"
            and path.suffix.lower() == ".json"
        )
        is_validator_interchange_contract = (
            len(relative.parts) == 2
            and relative.parts[0] == "b4g_validation"
            and relative.name in {
                "PHASE_B4G_A0_PARENT_TRACE_INTERCHANGE_V1.json",
                "PHASE_B4G_MUTATION_ARTIFACT_INTERCHANGE_V1.json",
                "PHASE_B4G_VALIDATOR_RAW_INTERFACE_V1.json",
            }
        )
        is_test_configuration = relative.as_posix() == "pytest.ini"
        if not (
            is_python_source
            or is_frozen_contract
            or is_validator_interchange_contract
            or is_test_configuration
        ):
            continue
        records.append(_project_record(
            project_root, path,
            identifier=f"local::{path.relative_to(phase_root).as_posix()}",
            role="B4G_FROZEN_CONTRACT_SOURCE_TEST_OR_WORKFLOW",
        ))
    return records


def execution_identity(
    project_root: Path,
    phase_root: Path,
    *,
    execution_source_freeze_terminal: Path | None = None,
    expected_execution_source_freeze_terminal_sha256: str | None = None,
) -> dict[str, Any]:
    local = local_source_inventory(project_root, phase_root)
    contracts = [row for row in local if "/contracts/" in f"/{row['path']}"]
    preregistration = _verify_rows(
        PREREGISTRATION_ANCHORS,
        project_root=project_root,
        local_root=phase_root,
        label="B4G_SIGNED_PREREGISTRATION",
    )
    preregistration_sources = verify_preregistration_source_manifest(
        project_root, phase_root,
    )
    freeze: dict[str, Any] | None = None
    if execution_source_freeze_terminal is not None or expected_execution_source_freeze_terminal_sha256 is not None:
        if execution_source_freeze_terminal is None or expected_execution_source_freeze_terminal_sha256 is None:
            raise SourceGuardError("EXECUTION_SOURCE_FREEZE_PATH_AND_SHA256_BOTH_REQUIRED")
        freeze = verify_execution_source_freeze(
            project_root, phase_root, execution_source_freeze_terminal,
            expected_execution_source_freeze_terminal_sha256,
        )
    return {
        "local_source_count": len(local),
        "local_sources": local,
        "local_source_inventory_sha256": canonical_sha256(local),
        "contract_bundle_sha256": canonical_sha256(contracts),
        "signed_preregistration_anchors": preregistration,
        "signed_preregistration_anchor_set_sha256": canonical_sha256(preregistration),
        "preregistration_source_verification": preregistration_sources,
        "preregistration_source_records_sha256": preregistration_sources["records_canonical_sha256"],
        "execution_source_freeze": freeze,
        "expected_execution_source_freeze_terminal_sha256": (
            None if freeze is None else freeze["expected_terminal_sha256"]
        ),
    }


def forbidden_local_artifacts(phase_root: Path, governance: Mapping[str, Any]) -> list[str]:
    forbidden = list(governance.get("forbidden_local_artifacts", []))
    literal_names = set(forbidden[1:])
    found: list[str] = []
    root = Path(phase_root).resolve()
    _assert_walk_root_chain(root, root, label="FORBIDDEN_LOCAL_ARTIFACTS")

    def generated_directory(name: str) -> bool:
        return bool(
            name == "__pycache__"
            or name.startswith(".pytest")
            or name.startswith(".smoke")
        )

    # Preserve the complete business evidence/results scan, but prune pytest
    # and smoke basetemps before descent so arbitrarily deep generated trees
    # cannot trigger WinError 206 ahead of the forbidden-asset check.
    def walk_error(error: OSError) -> None:
        raise SourceGuardError(
            f"FORBIDDEN_LOCAL_ARTIFACTS_WALK_ERROR:{error}"
        ) from error

    for current, directory_names, file_names in os.walk(
        root, topdown=True, onerror=walk_error, followlinks=False,
    ):
        current_path = Path(current)
        for name in directory_names:
            if not generated_directory(name) and _is_directory_link_or_reparse(
                current_path / name
            ):
                raise SourceGuardError(
                    "FORBIDDEN_LOCAL_ARTIFACTS_DIRECTORY_LINK_OR_REPARSE:"
                    f"{(current_path / name).as_posix()}"
                )
        for name in file_names:
            if not generated_directory(name) and _is_directory_link_or_reparse(
                current_path / name
            ):
                raise SourceGuardError(
                    "FORBIDDEN_LOCAL_ARTIFACTS_FILE_LINK_OR_REPARSE:"
                    f"{(current_path / name).as_posix()}"
                )
        directory_names[:] = sorted(
            name for name in directory_names if not generated_directory(name)
        )
        for name in sorted(file_names):
            path = current_path / name
            if path.suffix.lower() == ".urdf" or path.name in literal_names:
                found.append(path.relative_to(root).as_posix())
    return sorted(found)


def protected_snapshot(
    project_root: Path,
    phase_root: Path,
    bindings: Mapping[str, Any],
    governance: Mapping[str, Any],
) -> dict[str, Any]:
    direct = _verify_rows(
        bindings.get("sources", []), project_root=project_root,
        local_root=project_root, label="PROTECTED_PARENT",
    )
    forbidden = forbidden_local_artifacts(phase_root, governance)
    if forbidden:
        raise SourceGuardError(f"FORBIDDEN_LOCAL_ARTIFACT_PRESENT:{forbidden[0]}")
    preregistration_sources = verify_preregistration_source_manifest(project_root, phase_root)
    payload = {
        "bound_parent_count": len(direct),
        "bound_parents": direct,
        "local_forbidden_artifacts": forbidden,
        "protected_scope": governance.get("protected_asset_snapshot_scope"),
        "preregistration_source_verification": preregistration_sources,
    }
    return {**payload, "snapshot_payload_sha256": canonical_sha256(payload), "pass": True}
