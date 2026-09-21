"""Create the acyclic execution-source freeze chain for the B4G campaign.

This utility freezes source/test/contract bytes only.  It never executes a
registered slot, evaluates a scientific gate, or grants campaign credit.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
from typing import Any, Callable, Mapping, Sequence

from b4g_execution.io import (
    atomic_write_json,
    canonical_bytes,
    canonical_sha256,
    read_json,
    sha256_file,
)
from b4g_execution.source_guard import (
    EXECUTION_SOURCE_FREEZE_CLAIM_BOUNDARY,
    local_source_inventory,
    verify_execution_source_freeze,
)


PHASE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PHASE_ROOT.parents[3]
MANIFEST_RELATIVE_PATH = Path(
    "evidence/SIM13_V4B4G_EXECUTION_SOURCE_MANIFEST_V1.json"
)
GATE_RELATIVE_PATH = Path(
    "results/SIM13_V4B4G_EXECUTION_SOURCE_FREEZE_GATE_V1.json"
)
TERMINAL_RELATIVE_PATH = Path(
    "results/SIM13_V4B4G_EXECUTION_SOURCE_FREEZE_TERMINAL_"
    "SELF_EXCLUDED_MANIFEST_V1.json"
)
OUTPUT_ROOT_MARKER = ".sim13_v4b4g_execution_source_freeze_output_root.json"
CLAIM_BOUNDARY = EXECUTION_SOURCE_FREEZE_CLAIM_BOUNDARY
REQUIRED_FORMAL_ENTRYPOINTS = (
    "run_phase_b4g_solver.py",
    "run_phase_b4g_mutation_audit.py",
    "validate_phase_b4g_evidence.py",
    "publish_phase_b4g_preaudit.py",
    "independent_audit_phase_b4g.py",
)


class ExecutionSourceFreezeError(RuntimeError):
    """The source-freeze chain could not be published safely."""


def _require_complete_formal_workflow_sources(
    phase_root: Path,
    sources: Sequence[Mapping[str, Any]],
) -> None:
    """Reject a freeze that omits any later publication or audit entrypoint."""

    phase = Path(phase_root).resolve()
    missing: list[str] = []
    unbound: list[str] = []
    for name in REQUIRED_FORMAL_ENTRYPOINTS:
        path = (phase / name).resolve()
        if not path.is_file():
            missing.append(name)
            continue
        relative = path.relative_to(phase).as_posix()
        matching = [
            row for row in sources
            if Path(str(row.get("path", ""))).name == name
        ]
        if (
            len(matching) != 1
            or not str(matching[0].get("path", "")).replace("\\", "/").endswith(relative)
            or matching[0].get("bytes") != path.stat().st_size
            or matching[0].get("sha256") != sha256_file(path)
        ):
            unbound.append(name)
    if missing:
        raise ExecutionSourceFreezeError(
            "EXECUTION_SOURCE_FREEZE_REQUIRED_FORMAL_ENTRYPOINT_MISSING:"
            + ",".join(missing)
        )
    if unbound:
        raise ExecutionSourceFreezeError(
            "EXECUTION_SOURCE_FREEZE_REQUIRED_FORMAL_ENTRYPOINT_UNBOUND:"
            + ",".join(unbound)
        )


def _project_record(
    path: Path,
    *,
    project_root: Path,
    identifier: str,
    role: str,
) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        displayed = resolved.relative_to(project_root.resolve()).as_posix()
    except ValueError:
        displayed = resolved.as_posix()
    return {
        "id": identifier,
        "role": role,
        "path": displayed,
        "bytes": resolved.stat().st_size,
        "sha256": sha256_file(resolved),
    }


def _is_publication_link_or_reparse(path: Path) -> bool:
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


def _require_publication_root_chain_no_links(path: Path) -> Path:
    target = Path(os.path.abspath(path))
    current = Path(target.anchor)
    for part in target.parts[1:]:
        current = current / part
        if os.path.lexists(current) and _is_publication_link_or_reparse(current):
            raise ExecutionSourceFreezeError(
                f"EXECUTION_SOURCE_FREEZE_OUTPUT_ROOT_LINK_OR_REPARSE:{current}"
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


def _require_plain_publication_directory(path: Path, root: Path) -> Path:
    lexical_root = Path(os.path.abspath(root))
    target = Path(os.path.abspath(path))
    try:
        relative = target.relative_to(lexical_root)
    except ValueError as error:
        raise ExecutionSourceFreezeError(
            "EXECUTION_SOURCE_FREEZE_PATH_ESCAPES_ROOT"
        ) from error
    current = lexical_root
    for part in relative.parts:
        current = current / part
        if os.path.lexists(current):
            if _is_publication_link_or_reparse(current) or not current.is_dir():
                raise ExecutionSourceFreezeError(
                    "EXECUTION_SOURCE_FREEZE_PUBLICATION_PARENT_"
                    f"LINK_REPARSE_OR_NONDIR:{current}"
                )
        else:
            current.mkdir()
    try:
        target.resolve().relative_to(lexical_root.resolve())
    except ValueError as error:
        raise ExecutionSourceFreezeError(
            "EXECUTION_SOURCE_FREEZE_PATH_ESCAPES_ROOT"
        ) from error
    return target


def _safe_publication_paths(output_root: Path) -> tuple[Path, Path, Path]:
    root = Path(os.path.abspath(output_root))
    if (
        not os.path.lexists(root)
        or _is_publication_link_or_reparse(root)
        or not root.is_dir()
    ):
        raise ExecutionSourceFreezeError(
            "EXECUTION_SOURCE_FREEZE_PUBLICATION_ROOT_LINK_REPARSE_OR_NONDIR"
        )
    paths = tuple(root.joinpath(*relative.parts) for relative in (
        MANIFEST_RELATIVE_PATH, GATE_RELATIVE_PATH, TERMINAL_RELATIVE_PATH,
    ))
    for path, relative in zip(paths, (
        MANIFEST_RELATIVE_PATH, GATE_RELATIVE_PATH, TERMINAL_RELATIVE_PATH,
    )):
        if relative.is_absolute() or any(
            part in {"", ".", ".."} for part in relative.parts
        ):
            raise ExecutionSourceFreezeError("EXECUTION_SOURCE_FREEZE_PATH_ESCAPES_ROOT")
        _require_plain_publication_directory(path.parent, root)
    return paths  # type: ignore[return-value]


def _prepare_publication_root(
    project_root: Path,
    phase_root: Path,
    output_root: Path,
) -> tuple[Path, bool]:
    requested_lexical = _require_publication_root_chain_no_links(output_root)
    project = Path(project_root).resolve()
    phase = Path(phase_root).resolve()
    root = requested_lexical.resolve()
    formal = root == phase
    if root in {Path(root.anchor), project, project.parent}:
        raise ExecutionSourceFreezeError("EXECUTION_SOURCE_FREEZE_OUTPUT_ROOT_TOO_BROAD")
    if formal:
        root.mkdir(parents=True, exist_ok=True)
        return root, True
    if _paths_overlap(root, phase):
        raise ExecutionSourceFreezeError(
            "EXECUTION_SOURCE_FREEZE_CUSTOM_OUTPUT_OVERLAPS_PHASE_ROOT"
        )
    existed = root.exists()
    if existed and not root.is_dir():
        raise ExecutionSourceFreezeError("EXECUTION_SOURCE_FREEZE_OUTPUT_ROOT_NOT_DIRECTORY")
    marker = root / OUTPUT_ROOT_MARKER
    marker_payload = {
        "schema": "SIM13_V4B4G_DIAGNOSTIC_SOURCE_FREEZE_OUTPUT_ROOT_MARKER_V1",
        "phase_root": phase.as_posix(),
        "resolved_output_root": root.as_posix(),
        "diagnostic_only": True,
        "formal_publication_credit": False,
    }
    if existed and not os.path.lexists(marker):
        try:
            next(root.iterdir())
        except StopIteration:
            pass
        else:
            raise ExecutionSourceFreezeError(
                "EXECUTION_SOURCE_FREEZE_EXISTING_NONEMPTY_ROOT_REQUIRES_MARKER"
            )
    if os.path.lexists(marker):
        if _is_publication_link_or_reparse(marker) or not marker.is_file():
            raise ExecutionSourceFreezeError(
                "EXECUTION_SOURCE_FREEZE_OUTPUT_MARKER_NOT_PLAIN_FILE"
            )
        if (
            read_json(marker) != marker_payload
            or marker.read_bytes() != canonical_bytes(marker_payload) + b"\n"
        ):
            raise ExecutionSourceFreezeError(
                "EXECUTION_SOURCE_FREEZE_OUTPUT_MARKER_MISMATCH"
            )
    else:
        root.mkdir(parents=True, exist_ok=True)
        atomic_write_json(marker, marker_payload)
    return root, False


def _remove_incomplete_or_stale_chain(paths: Sequence[Path]) -> None:
    """Ensure no old or partially rewritten terminal chain remains usable."""

    # Delete in consumer-to-source order.  A terminal is never left pointing
    # at a stale gate while the earlier files are being replaced.
    manifest_path, gate_path, terminal_path = paths
    for path in (terminal_path, gate_path, manifest_path):
        if os.path.lexists(path):
            linked = _is_publication_link_or_reparse(path)
            if not linked and not path.is_file():
                raise ExecutionSourceFreezeError(
                    f"EXECUTION_SOURCE_FREEZE_STALE_PATH_NOT_FILE:{path}"
                )
            path.unlink()


def freeze_execution_sources(
    *,
    project_root: Path,
    phase_root: Path,
    output_root: Path | None = None,
    write_json_fn: Callable[[Path, Any], None] | None = None,
) -> dict[str, Any]:
    """Publish manifest -> final gate -> self-excluded terminal and self-verify."""

    project = Path(project_root).resolve()
    phase = Path(phase_root).resolve()
    requested_output = phase if output_root is None else Path(output_root)
    output, formal = _prepare_publication_root(
        project, phase, requested_output,
    )
    manifest_path, gate_path, terminal_path = _safe_publication_paths(output)
    chain_paths = (manifest_path, gate_path, terminal_path)
    _remove_incomplete_or_stale_chain(chain_paths)
    write_json = atomic_write_json if write_json_fn is None else write_json_fn
    try:
        sources = local_source_inventory(project, phase)
        if not sources:
            raise ExecutionSourceFreezeError("EXECUTION_SOURCE_INVENTORY_EMPTY")
        _require_complete_formal_workflow_sources(phase, sources)
        source_paths = [str(row.get("path", "")) for row in sources]
        if len(source_paths) != len(set(source_paths)):
            raise ExecutionSourceFreezeError("EXECUTION_SOURCE_INVENTORY_DUPLICATE_PATH")
        publication_paths = {
            manifest_path.name, gate_path.name, terminal_path.name,
        }
        if publication_paths & {Path(path).name for path in source_paths}:
            raise ExecutionSourceFreezeError("EXECUTION_SOURCE_FREEZE_SELF_REFERENCE")

        inventory_sha256 = canonical_sha256(sources)
        diagnostic_claim_boundary = (
            "custom diagnostic execution-source inventory only; no formal "
            "freeze, campaign invocation, scientific, publication, or audit credit"
        )
        chain_claim_boundary = (
            CLAIM_BOUNDARY if formal else diagnostic_claim_boundary
        )
        manifest = {
            "schema": (
                "SIM13_V4B4G_EXECUTION_SOURCE_MANIFEST_V1" if formal else
                "SIM13_V4B4G_DIAGNOSTIC_EXECUTION_SOURCE_MANIFEST_V1"
            ),
            "self_excluded": True,
            "source_count": len(sources),
            "sources": sources,
            "source_inventory_sha256": inventory_sha256,
            "claim_boundary": chain_claim_boundary,
        }
        if not formal:
            manifest.update({
                "diagnostic_only": True,
                "formal_publication_credit": False,
            })
        write_json(manifest_path, manifest)
        manifest_record = _project_record(
            manifest_path,
            project_root=project,
            identifier="b4g_execution_source_manifest",
            role="EXECUTION_SOURCE_MANIFEST",
        )
        gate = {
            "schema": (
                "SIM13_V4B4G_EXECUTION_SOURCE_FREEZE_GATE_V1" if formal else
                "SIM13_V4B4G_DIAGNOSTIC_EXECUTION_SOURCE_FREEZE_GATE_V1"
            ),
            "final": bool(formal),
            "execution_source_manifest": manifest_record,
            "source_count": len(sources),
            "source_inventory_sha256": inventory_sha256,
            "claim_boundary": chain_claim_boundary,
        }
        if not formal:
            gate.update({
                "diagnostic_only": True,
                "formal_publication_credit": False,
            })
        write_json(gate_path, gate)
        gate_record = _project_record(
            gate_path,
            project_root=project,
            identifier="b4g_execution_source_freeze_gate",
            role="EXECUTION_SOURCE_FREEZE_GATE",
        )
        terminal = {
            "schema": (
                "SIM13_V4B4G_EXECUTION_SOURCE_FREEZE_TERMINAL_"
                "SELF_EXCLUDED_MANIFEST_V1" if formal else
                "SIM13_V4B4G_DIAGNOSTIC_EXECUTION_SOURCE_FREEZE_TERMINAL_"
                "SELF_EXCLUDED_MANIFEST_V1"
            ),
            "self_excluded": True,
            "acyclic": True,
            "records": [gate_record],
            "source_count": len(sources),
            "source_inventory_sha256": inventory_sha256,
            "claim_boundary": chain_claim_boundary,
        }
        if not formal:
            terminal.update({
                "diagnostic_only": True,
                "formal_publication_credit": False,
            })
        write_json(terminal_path, terminal)
        terminal_sha256 = sha256_file(terminal_path)
        verification = (
            verify_execution_source_freeze(
                project, phase, terminal_path, terminal_sha256,
            )
            if formal else {
                "pass": (
                    read_json(manifest_path) == manifest
                    and read_json(gate_path) == gate
                    and read_json(terminal_path) == terminal
                    and local_source_inventory(project, phase) == sources
                ),
                "diagnostic_only": True,
                "formal_execution_source_freeze_eligible": False,
                "terminal_sha256": terminal_sha256,
            }
        )
        if verification.get("pass") is not True:
            raise ExecutionSourceFreezeError(
                "EXECUTION_SOURCE_FREEZE_SELF_VERIFY_FAILED"
            )
        return {
            "schema": "SIM13_V4B4G_EXECUTION_SOURCE_FREEZE_RECEIPT_V1",
            "manifest": _project_record(
                manifest_path, project_root=project,
                identifier="b4g_execution_source_manifest",
                role="EXECUTION_SOURCE_MANIFEST",
            ),
            "gate": _project_record(
                gate_path, project_root=project,
                identifier="b4g_execution_source_freeze_gate",
                role="EXECUTION_SOURCE_FREEZE_GATE",
            ),
            "terminal": _project_record(
                terminal_path, project_root=project,
                identifier="b4g_execution_source_freeze_terminal",
                role="EXECUTION_SOURCE_FREEZE_TERMINAL",
            ),
            "source_count": len(sources),
            "source_inventory_sha256": inventory_sha256,
            "verification": verification,
            "diagnostic_only": not formal,
            "formal_publication_credit": bool(formal),
            "claim_boundary": chain_claim_boundary,
        }
    except BaseException:
        _remove_incomplete_or_stale_chain(chain_paths)
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root", type=Path, default=PHASE_ROOT,
        help=(
            "canonical phase root for formal freeze; a custom root must be a "
            "new/empty or pre-marked owned diagnostic root and receives zero credit"
        ),
    )
    args = parser.parse_args(argv)
    receipt = freeze_execution_sources(
        project_root=PROJECT_ROOT,
        phase_root=PHASE_ROOT,
        output_root=args.output_root,
    )
    print(json.dumps(receipt, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
