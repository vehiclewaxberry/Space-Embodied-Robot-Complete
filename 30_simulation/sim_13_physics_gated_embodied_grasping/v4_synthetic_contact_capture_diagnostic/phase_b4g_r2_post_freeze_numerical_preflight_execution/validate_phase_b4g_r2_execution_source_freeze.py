"""Validate the B4G-R2 execution-tooling source freeze without physics.

This validator does not import the independent audit, tests, historical solver
modules, or campaign entrypoints.  It validates source bytes, the frozen 78-case
identity, the typed donor roundtrip, governance false flags, and source-only
negative-control evidence.  Missing evidence fails closed.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import stat
from typing import Any, Iterable

from r2_preflight.negative_controls import build_negative_control_evidence
from r2_preflight.rehydrator import fixture_hashes, load_donor_fixture
from r2_preflight.schedule import (
    MATRIX_SHA256,
    SCHEDULE_SHA256,
    expand_matrix,
    generate_schedule,
)
from r2_preflight.strict_json import (
    atomic_write_json,
    canonical_sha256,
    contains_null,
    file_sha256,
    load_path,
)


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
SOURCE_BINDINGS = HERE / "contracts/PHASE_B4G_R2_EXECUTION_SOURCE_BINDINGS_V1.json"
FREEZE_CONTRACT = HERE / "contracts/PHASE_B4G_R2_EXECUTION_TOOLING_FREEZE_CONTRACT_V1.json"
GOVERNANCE = HERE / "contracts/PHASE_B4G_R2_EXECUTION_GOVERNANCE_V1.json"
NC_CONTRACT = HERE / "contracts/PHASE_B4G_R2_SOURCE_ONLY_NEGATIVE_CONTROL_EVIDENCE_CONTRACT_V1.json"
NC_EVIDENCE = HERE / "evidence/SIM13_V4B4G_R2_SOURCE_ONLY_NEGATIVE_CONTROLS_V1.json"
MANIFEST = HERE / "evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_MANIFEST_V1.json"
OUTPUT = HERE / "evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_VALIDATION_V1.json"
AUDIT_OUTPUT = HERE / "evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_INDEPENDENT_AUDIT_V1.json"
GATE_OUTPUT = HERE / "results/SIM13_V4B4G_R2_EXECUTION_TOOLING_SOURCE_FREEZE_GATE_V1.json"
TERMINAL_OUTPUT = HERE / "results/SIM13_V4B4G_R2_EXECUTION_SOURCE_FREEZE_TERMINAL_V1.json"

FORBIDDEN_SUFFIXES = {".npz", ".csv", ".urdf", ".step", ".stp", ".pyc", ".tmp"}
FORBIDDEN_DIRECTORIES = {"__pycache__", ".pytest_cache", "raw", "raw_cases"}
FORBIDDEN_FILENAME_SUBSTRINGS = {"solver"}
FORBIDDEN_IMPORT_TOKENS = {
    "b4g_solver",
    "b4_solver",
    "full_floating",
    "campaign",
    "forced_retraction",
}
OUTPUT_PREFIXES = ("evidence/", "results/")
EXPECTED_CRITICAL_ROOTS = {
    "r2_contract_gate": "8DB747F8C57F898B25B15273C691A1007F4E452EB688865EEFAE2BA81E4A0298",
    "r2_contract_terminal": "286088014FD4B84263C17521E24224B8338B42214440DF8ED1593BE29A666C07",
    "b4g_active_source_freeze_terminal": "B22C4D5B4C0E15FF58484D252A2316E6B42458423079E2324D6455CC09EF3464",
    "b4g_active_invalidation": "2743FBD314CCA3EAA6FB5F4985DF8F65697E5BD968DE6DEB2AD58F0521FAB1D9",
    "b4g_r1_failure_closure_gate": "AE7E81F66CF6A5EC218CBB8E3FC4A1EC923A49E2CF0CAFC6681EEC449D855C68",
    "b4g_r1_terminal": "A1B2BD2FC051DC3CB853B7B081E0B56DB5776A48DEB7318E656F396ABAA516EC",
}
HEX64 = set("0123456789ABCDEF")


class SourceFreezeValidationError(RuntimeError):
    """A source-only freeze invariant was not satisfied."""


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction) and is_junction():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _source_candidates(package_root: Path) -> Iterable[Path]:
    root = Path(package_root).resolve()
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.suffix.lower() in {".py", ".md", ".ini"}:
            yield path
    for subtree, suffixes in (
        ("r2_preflight", {".py"}),
        ("contracts", {".json"}),
        ("tests", {".py"}),
    ):
        base = root / subtree
        if not base.exists():
            continue
        for path in sorted(base.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_file() and path.suffix.lower() in suffixes:
                yield path


def local_source_inventory(package_root: Path) -> list[dict[str, Any]]:
    """Return the deterministic, phase-relative source inventory."""

    root = Path(package_root).resolve()
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in _source_candidates(root):
        if _is_link_or_reparse(path):
            raise SourceFreezeValidationError(f"LOCAL_SOURCE_LINK_OR_REPARSE:{path}")
        relative = path.resolve().relative_to(root).as_posix()
        if relative in seen:
            raise SourceFreezeValidationError(f"DUPLICATE_LOCAL_SOURCE_PATH:{relative}")
        seen.add(relative)
        rows.append({
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        })
    rows.sort(key=lambda row: row["path"])
    if not rows:
        raise SourceFreezeValidationError("LOCAL_SOURCE_INVENTORY_EMPTY")
    return rows


def artifact_guard(package_root: Path) -> dict[str, Any]:
    root = Path(package_root).resolve()
    violations: list[str] = []
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if _is_link_or_reparse(path):
            violations.append(f"LINK_OR_REPARSE:{relative}")
        if path.is_dir() and path.name.lower() in FORBIDDEN_DIRECTORIES:
            violations.append(f"FORBIDDEN_DIRECTORY:{relative}")
        if path.is_file():
            if path.suffix.lower() in FORBIDDEN_SUFFIXES:
                violations.append(f"FORBIDDEN_SUFFIX:{relative}")
            if any(token in path.name.lower() for token in FORBIDDEN_FILENAME_SUBSTRINGS):
                violations.append(f"FORBIDDEN_FILENAME:{relative}")
    imported: list[dict[str, str]] = []
    for path in _source_candidates(root):
        if path.suffix.lower() != ".py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            for module in modules:
                if any(token in module for token in FORBIDDEN_IMPORT_TOKENS):
                    imported.append({"path": path.relative_to(root).as_posix(), "module": module})
    return {"passed": not violations and not imported, "violations": sorted(violations), "forbidden_imports": imported}


def _record_matches(project_root: Path, row: dict[str, Any]) -> bool:
    if set(row) != {"id", "path", "role", "bytes", "sha256"}:
        return False
    root = Path(project_root).resolve()
    raw_path = Path(row["path"])
    if raw_path.is_absolute() or any(part in {"", ".", ".."} for part in raw_path.parts):
        return False
    path = (root / raw_path).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return bool(
        path.is_file()
        and not _is_link_or_reparse(path)
        and path.stat().st_size == row["bytes"]
        and file_sha256(path) == row["sha256"]
    )


def _source_bindings_check(project_root: Path, source_bindings: dict[str, Any]) -> dict[str, Any]:
    rows = source_bindings.get("sources", [])
    ids = [row.get("id") for row in rows if isinstance(row, dict)]
    row_pass = bool(
        isinstance(rows, list)
        and len(rows) == 22
        and len(ids) == len(set(ids))
        and all(isinstance(row, dict) and _record_matches(project_root, row) for row in rows)
    )
    policy = source_bindings.get("execution_authority_policy", {})
    policy_pass = bool(
        policy.get("direct_owner_source_required") is True
        and policy.get("external_nonworkspace_owner_source_required") is True
        and policy.get("bound_direct_owner_source_id") == "NOT_AVAILABLE_NO_EXECUTION_AUTHORITY"
        and policy.get("current_execution_authorized") is False
    )
    return {"passed": row_pass and policy_pass, "source_count": len(rows), "unique_ids": len(set(ids)), "authority_policy_pass": policy_pass}


def _critical_binding_roots_check(source_bindings: dict[str, Any], freeze_contract: dict[str, Any]) -> dict[str, Any]:
    roots = freeze_contract["frozen_parent_roots"]
    mapping = {
        "r2_contract_gate": "r2_contract_gate_sha256",
        "r2_contract_terminal": "r2_contract_terminal_sha256",
        "b4g_active_source_freeze_terminal": "b4g_active_source_freeze_terminal_sha256",
        "b4g_active_invalidation": "b4g_active_invalidation_sha256",
        "b4g_r1_failure_closure_gate": "b4g_r1_gate_sha256",
        "b4g_r1_terminal": "b4g_r1_terminal_sha256",
    }
    observed = {source_id: _row_by_id(source_bindings, source_id)["sha256"] for source_id in mapping}
    contract_roots = {source_id: roots[contract_key] for source_id, contract_key in mapping.items()}
    passed = observed == contract_roots == EXPECTED_CRITICAL_ROOTS
    donor = _row_by_id(source_bindings, "common_prop_donor_raw_slot_052")
    passed = bool(passed and donor["bytes"] == 69249 and donor["sha256"] == "5DF0C19A71180E1BD91816235AAD50108613C2BC0F99F950018D786119CF9D4F")
    return {"passed": passed, "critical_root_count": len(mapping), "observed": observed, "literal_expected": EXPECTED_CRITICAL_ROOTS}


def _raw_inventory_check(project_root: Path, source_bindings: dict[str, Any]) -> dict[str, Any]:
    spec = source_bindings["preserved_raw_inventory"]
    project = Path(project_root).resolve()
    raw_relative = Path(spec["path"])
    if raw_relative.is_absolute() or any(part in {"", ".", ".."} for part in raw_relative.parts):
        return {"passed": False, "reason": "RAW_ROOT_PATH_INVALID_OR_ESCAPING"}
    root = (project / raw_relative).resolve()
    try:
        root.relative_to(project)
    except ValueError:
        return {"passed": False, "reason": "RAW_ROOT_PATH_INVALID_OR_ESCAPING"}
    if not root.is_dir() or _is_link_or_reparse(root):
        return {"passed": False, "reason": "RAW_ROOT_MISSING_LINK_OR_NONDIR"}
    paths = sorted((path for path in root.iterdir() if path.is_file()), key=lambda path: path.name)
    rows = [{"path": path.name, "bytes": path.stat().st_size, "sha256": file_sha256(path)} for path in paths]
    observed = {
        "json_count": sum(path.suffix.lower() == ".json" for path in paths),
        "npz_count": sum(path.suffix.lower() == ".npz" for path in paths),
        "file_count": len(paths),
        "canonical_sha256": canonical_sha256(rows),
        "no_links": not any(_is_link_or_reparse(path) for path in paths),
    }
    expected = {
        "json_count": spec["json_count"],
        "npz_count": spec["npz_count"],
        "file_count": spec["file_count"],
        "canonical_sha256": spec["canonical_sha256"],
        "no_links": True,
    }
    return {"passed": observed == expected, "observed": observed, "expected": expected}


def _row_by_id(source_bindings: dict[str, Any], identifier: str) -> dict[str, Any]:
    rows = [row for row in source_bindings["sources"] if row["id"] == identifier]
    if len(rows) != 1:
        raise SourceFreezeValidationError(f"SOURCE_ID_CARDINALITY:{identifier}")
    return rows[0]


def _parent_semantics_check(project_root: Path, source_bindings: dict[str, Any]) -> dict[str, Any]:
    r2 = load_path(Path(project_root) / _row_by_id(source_bindings, "r2_contract_gate")["path"])
    # The raw-byte/hash-bound legacy R1 Gate contains one historical null in a
    # diagnostic field.  It is never copied into this package's new evidence.
    r1 = load_path(Path(project_root) / _row_by_id(source_bindings, "b4g_r1_failure_closure_gate")["path"], allow_null=True)
    invalidation = load_path(Path(project_root) / _row_by_id(source_bindings, "b4g_active_invalidation")["path"])
    r2_false = r2.get("required_false", {})
    r1_false = r1.get("required_false", {})
    passed = bool(
        r2.get("status") == "PASS_PHASE_B4G_R2_NUMERICAL_PREFLIGHT_CONTRACT_ONLY"
        and r2_false.get("r2_numerical_preflight_executed") is False
        and r2_false.get("next_stage_authorized") is False
        and r1.get("status") == "PASS_PHASE_B4G_R1_REGISTERED_FAILURE_CLOSURE_CONTRACT_ONLY"
        and r1.get("original_b4g_final_credit") is False
        and r1_false.get("current_system_bound") is False
        and invalidation.get("active") is True
        and invalidation.get("raw_case_and_diagnostic_evidence_preserved") is True
    )
    return {"passed": passed, "r2_status": r2.get("status", "MISSING"), "r1_status": r1.get("status", "MISSING"), "invalidation_active": invalidation.get("active", False)}


def _donor_check(project_root: Path, source_bindings: dict[str, Any]) -> dict[str, Any]:
    row = _row_by_id(source_bindings, "common_prop_donor_raw_slot_052")
    fixture = load_donor_fixture(Path(project_root) / row["path"])
    observed = fixture_hashes(fixture)
    binding = source_bindings["common_donor_binding"]
    expected = {
        "payload_canonical_bytes": binding["payload_canonical_bytes"],
        "payload_sha256": binding["payload_sha256"],
        "group_canonical_bytes": binding["group_canonical_bytes"],
        "group_sha256": binding["group_sha256"],
    }
    return {"passed": observed == expected, "observed": observed, "expected": expected}


def _matrix_schedule_check() -> dict[str, Any]:
    matrix = expand_matrix()
    schedule = generate_schedule()
    fresh = [row for row in matrix if row["execution_family"] == "FRESH"]
    common = [row for row in matrix if row["execution_family"] == "COMMON_PROP"]
    matrix_hash = canonical_sha256(matrix)
    schedule_hash = canonical_sha256(schedule)
    passed = bool(
        len(matrix) == len(schedule) == 78
        and len(fresh) == 60
        and len(common) == 18
        and len({row["case_id"] for row in matrix}) == 78
        and set(schedule) == {row["case_id"] for row in matrix}
        and matrix_hash == MATRIX_SHA256
        and schedule_hash == SCHEDULE_SHA256
        and all(row["g12_credit"] is False and row["selector_input"] is False for row in common)
    )
    return {"passed": passed, "matrix_sha256": matrix_hash, "schedule_sha256": schedule_hash, "case_count": len(matrix), "fresh_count": len(fresh), "common_count": len(common)}


def _hex64(value: Any) -> bool:
    return type(value) is str and len(value) == 64 and all(character in HEX64 for character in value)


def negative_control_value_check(
    evidence: Any,
    contract: dict[str, Any],
    *,
    expected_source_inventory_sha256: str | None = None,
    package_root: Path | None = None,
) -> dict[str, Any]:
    """Pure exact-schema check used without creating a temporary evidence file."""

    if not isinstance(evidence, dict):
        return {"passed": False, "reason": "NC_EVIDENCE_NOT_OBJECT"}
    registered = contract["registered_ids"]
    controls = evidence.get("controls", [])
    ids = [row.get("id") for row in controls if isinstance(row, dict)]
    ids_are_strings = all(isinstance(identifier, str) for identifier in ids)
    unique_id_count = len(set(ids)) if ids_are_strings else -1
    allowed = set(contract["allowed_statuses"])
    structural = set(contract["structural_source_signature_only_ids"])
    keys = set(contract["control_exact_keys"])
    per_control = contract["per_control_required"]
    rows_pass = bool(
        isinstance(controls, list)
        and len(controls) == 46
        and ids == registered
        and ids_are_strings
        and unique_id_count == 46
    )
    if rows_pass:
        for row in controls:
            status = row.get("status")
            rows_pass = bool(
                rows_pass
                and set(row) == keys
                and isinstance(status, str)
                and status in allowed
                and (status == "STRUCTURAL_SOURCE_SIGNATURE_KILLED") == (row["id"] in structural)
                and all(row.get(key) is value for key, value in per_control.items())
                and row.get("fixture_class") == contract["per_control_fixture_class_exact"]
                and type(row.get("witness")) is str
                and bool(row["witness"])
                and _hex64(row.get("implementation_sha256"))
            )
    top = contract["top_level_required"]
    implementation = evidence.get("implementation_files", [])
    binding = contract["implementation_binding"]
    implementation_rows_pass = bool(
        isinstance(implementation, list)
        and len(implementation) == binding["file_count"]
        and all(
            isinstance(row, dict)
            and set(row) == set(binding["record_exact_keys"])
            and type(row.get("path")) is str
            and type(row.get("bytes")) is int
            and row["bytes"] >= 0
            and _hex64(row.get("sha256"))
            for row in implementation
        )
        and _hex64(evidence.get("implementation_sha256"))
        and canonical_sha256(implementation) == evidence.get("implementation_sha256")
        and all(row.get("implementation_sha256") == evidence.get("implementation_sha256") for row in controls if isinstance(row, dict))
    )
    if implementation_rows_pass and package_root is not None:
        root = Path(package_root).resolve()
        for row in implementation:
            relative = Path(row["path"])
            path = (root / relative).resolve()
            try:
                path.relative_to(root)
                contained = not relative.is_absolute() and not any(part in {"", ".", ".."} for part in relative.parts)
            except ValueError:
                contained = False
            implementation_rows_pass = bool(
                implementation_rows_pass
                and contained
                and path.is_file()
                and not _is_link_or_reparse(path)
                and path.stat().st_size == row["bytes"]
                and file_sha256(path) == row["sha256"]
            )
    source_inventory_pass = bool(
        _hex64(evidence.get("source_inventory_sha256"))
        and (
            expected_source_inventory_sha256 is None
            or evidence.get("source_inventory_sha256") == expected_source_inventory_sha256
        )
    )
    top_pass = bool(
        set(evidence) == set(contract["evidence_exact_keys"])
        and evidence.get("schema") == contract["evidence_schema"]
        and evidence.get("scope") == contract["evidence_scope_exact"]
        and evidence.get("registered_count") == 46
        and all(evidence.get(key) == value and type(evidence.get(key)) is type(value) for key, value in top.items())
    )
    return {
        "passed": rows_pass and top_pass and implementation_rows_pass and source_inventory_pass,
        "row_count": len(controls) if isinstance(controls, list) else -1,
        "unique_id_count": unique_id_count,
        "rows_pass": rows_pass,
        "top_level_pass": top_pass,
        "implementation_binding_pass": implementation_rows_pass,
        "source_inventory_binding_pass": source_inventory_pass,
    }


def negative_control_evidence_check(
    evidence_path: Path,
    contract_path: Path = NC_CONTRACT,
    *,
    expected_source_inventory_sha256: str | None = None,
    package_root: Path | None = None,
) -> dict[str, Any]:
    """Validate exact 46/46 source-only mutation evidence, or fail closed."""

    if not evidence_path.is_file() or _is_link_or_reparse(evidence_path):
        return {"passed": False, "reason": "NC_EVIDENCE_MISSING_OR_LINK"}
    try:
        contract = load_path(contract_path)
        evidence = load_path(evidence_path)
    except Exception as exc:
        return {"passed": False, "reason": f"NC_EVIDENCE_STRICT_JSON_FAILURE:{type(exc).__name__}"}
    return negative_control_value_check(
        evidence,
        contract,
        expected_source_inventory_sha256=expected_source_inventory_sha256,
        package_root=package_root,
    )


def negative_control_replay_check(
    *,
    evidence_path: Path,
    manifest_path: Path,
    project_root: Path,
    package_root: Path,
) -> dict[str, Any]:
    """Actually rerun all 46 source-only mutations and compare exact evidence."""

    manifest = load_path(manifest_path)
    inventory_sha256 = manifest.get("source_inventory_sha256")
    structural = negative_control_evidence_check(
        evidence_path,
        Path(package_root) / "contracts/PHASE_B4G_R2_SOURCE_ONLY_NEGATIVE_CONTROL_EVIDENCE_CONTRACT_V1.json",
        expected_source_inventory_sha256=inventory_sha256,
        package_root=package_root,
    )
    if structural.get("passed") is not True:
        return {"passed": False, "replay_exact": False, "structural": structural}
    bindings = load_path(Path(package_root) / "contracts/PHASE_B4G_R2_EXECUTION_SOURCE_BINDINGS_V1.json")
    donor_row = _row_by_id(bindings, "common_prop_donor_raw_slot_052")
    donor = load_donor_fixture(Path(project_root) / donor_row["path"])
    expected = build_negative_control_evidence(
        project_root=Path(project_root),
        package_root=Path(package_root),
        donor=donor,
        source_inventory_sha256=inventory_sha256,
    )
    observed = load_path(evidence_path)
    replay_exact = canonical_sha256(expected) == canonical_sha256(observed) and expected == observed
    return {
        "passed": replay_exact,
        "replay_exact": replay_exact,
        "structural": structural,
        "expected_evidence_sha256": canonical_sha256(expected),
        "observed_evidence_sha256": canonical_sha256(observed),
        "actual_control_count": len(expected["controls"]),
        "actual_killed_count": expected["killed_count"],
    }


def _manifest_check(package_root: Path, manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.is_file() or _is_link_or_reparse(manifest_path):
        return {"passed": False, "reason": "MANIFEST_MISSING_OR_LINK"}
    manifest = load_path(manifest_path)
    observed = local_source_inventory(package_root)
    paths = [row["path"] for row in manifest.get("sources", []) if isinstance(row, dict)]
    excluded = all(not path.startswith(OUTPUT_PREFIXES) for path in paths)
    passed = bool(
        manifest.get("schema") == "SIM13_V4B4G_R2_EXECUTION_SOURCE_MANIFEST_V1"
        and manifest.get("self_excluded") is True
        and manifest.get("acyclic") is True
        and manifest.get("terminal_excluded") is True
        and manifest.get("sources") == observed
        and manifest.get("source_count") == len(observed)
        and manifest.get("source_inventory_sha256") == canonical_sha256(observed)
        and excluded
        and len(paths) == len(set(paths))
    )
    return {"passed": passed, "source_count": len(observed), "source_inventory_sha256": canonical_sha256(observed), "outputs_excluded": excluded}


def _governance_check(governance: dict[str, Any], freeze_contract: dict[str, Any]) -> dict[str, Any]:
    false = governance.get("required_false", {})
    zero = governance.get("required_zero", {})
    statuses = freeze_contract.get("exact_statuses", {})
    replay = freeze_contract.get("validator_and_audit_independence", {})
    passed = bool(
        false
        and all(value is False for value in false.values())
        and zero
        and all(type(value) is int and value == 0 for value in zero.values())
        and governance.get("gate_status_exact") == statuses.get("pass")
        and governance.get("partial_gate_status_exact") == statuses.get("partial")
        and governance.get("failure_gate_status_exact") == statuses.get("failure")
        and governance.get("execution_readiness_status_exact") == statuses.get("execution_readiness")
        and governance.get("authorized_execution_path_status_exact") == statuses.get("authorized_execution_path_status")
        and governance["authorization_boundary"]["bound_direct_owner_source_id"] == "NOT_AVAILABLE_NO_EXECUTION_AUTHORITY"
        and governance["authorization_boundary"]["successful_authorization_path_implemented_in_this_version"] is False
        and replay.get("standalone_default_mode") == "READ_ONLY_RECEIPT_VERIFY"
        and replay.get("receipt_write_requires_explicit_cli_flag") == "--write-receipt"
        and replay.get("receipt_write_flag_abbreviation_allowed") is False
        and replay.get("freeze_internal_receipt_generation_is_explicit") is True
        and replay.get("validator_audit_pytest_replay_must_preserve_all_package_bytes") is True
        and replay.get("read_only_replay_captures_after_delta_on_subcommand_failure") is True
        and replay.get("read_only_replay_revalidates_gate_and_terminal_hash_chain") is True
    )
    return {"passed": passed, "false_count": len(false), "zero_count": len(zero)}


def _execution_guard_hold_check(package_root: Path, governance: dict[str, Any]) -> dict[str, Any]:
    path = Path(package_root) / "r2_preflight/execution_guard.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    boundary = governance["authorization_boundary"]
    expected_names = boundary["no_success_path_function_names"]
    expected_error = boundary["required_fail_closed_exception"]
    details: dict[str, bool] = {}
    for name in expected_names:
        node = functions.get(name)
        body = [] if node is None else list(node.body)
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            body = body[1:]
        exact_raise = False
        if len(body) == 1 and isinstance(body[0], ast.Raise) and isinstance(body[0].exc, ast.Call):
            call = body[0].exc
            exact_raise = bool(
                isinstance(call.func, ast.Name)
                and call.func.id == "ExecutionAuthorizationError"
                and len(call.args) == 1
                and isinstance(call.args[0], ast.Constant)
                and call.args[0].value == expected_error
            )
        details[name] = exact_raise
    return {"passed": len(details) == 3 and all(details.values()), "functions": details, "required_exception": expected_error}


def _negative_control_registration_check(project_root: Path, source_bindings: dict[str, Any], local_contract: dict[str, Any]) -> dict[str, Any]:
    parent = load_path(Path(project_root) / _row_by_id(source_bindings, "r2_governance_negative_controls")["path"])
    registered = local_contract["registered_ids"]
    passed = bool(parent.get("negative_control_count") == 46 and parent.get("negative_controls") == registered and len(registered) == len(set(registered)) == 46)
    return {"passed": passed, "parent_count": parent.get("negative_control_count", -1), "local_count": len(registered)}


def _all_local_json_no_null(package_root: Path, output_path: Path) -> dict[str, Any]:
    checked = 0
    failures: list[str] = []
    # These downstream/self receipts do not exist yet when the validator
    # receipt is generated inside the freezer.  Excluding the exact fixed set
    # keeps a later standalone read-only replay byte-deterministic.
    excluded = {
        output_path.resolve(),
        AUDIT_OUTPUT.resolve(),
        GATE_OUTPUT.resolve(),
        TERMINAL_OUTPUT.resolve(),
    }
    for path in Path(package_root).rglob("*.json"):
        if path.resolve() in excluded:
            continue
        try:
            value = load_path(path)
            if contains_null(value):
                failures.append(path.relative_to(package_root).as_posix())
        except Exception:
            failures.append(path.relative_to(package_root).as_posix())
        checked += 1
    return {"passed": not failures, "checked": checked, "failures": sorted(failures)}


def validate_source_freeze(
    *,
    project_root: Path = PROJECT_ROOT,
    package_root: Path = HERE,
    manifest_path: Path = MANIFEST,
    negative_control_evidence_path: Path = NC_EVIDENCE,
    output_path: Path = OUTPUT,
    write_output: bool = False,
) -> dict[str, Any]:
    package = Path(package_root).resolve()
    project = Path(project_root).resolve()
    source_bindings = load_path(package / "contracts/PHASE_B4G_R2_EXECUTION_SOURCE_BINDINGS_V1.json")
    freeze_contract = load_path(package / "contracts/PHASE_B4G_R2_EXECUTION_TOOLING_FREEZE_CONTRACT_V1.json")
    governance = load_path(package / "contracts/PHASE_B4G_R2_EXECUTION_GOVERNANCE_V1.json")
    nc_contract = load_path(package / "contracts/PHASE_B4G_R2_SOURCE_ONLY_NEGATIVE_CONTROL_EVIDENCE_CONTRACT_V1.json")
    checks: list[dict[str, Any]] = []

    def add(check_id: str, detail: dict[str, Any]) -> None:
        checks.append({"id": check_id, "pass": detail.get("passed") is True, "detail": detail})

    add("R2SV01_LOCAL_MANIFEST_EXACT_AND_SELF_EXCLUDED", _manifest_check(package, manifest_path))
    add("R2SV02_RECURSIVE_ARTIFACT_AND_IMPORT_GUARD", artifact_guard(package))
    add("R2SV03_EXTERNAL_SOURCE_BINDINGS_EXACT", _source_bindings_check(project, source_bindings))
    add("R2SV04_PRESERVED_RAW_INVENTORY_EXACT", _raw_inventory_check(project, source_bindings))
    add("R2SV05_PARENT_CONTRACT_ONLY_AND_INVALIDATION_ACTIVE", _parent_semantics_check(project, source_bindings))
    add("R2SV06_DONOR_TYPED_ROUNDTRIP_AND_GROUP_EXACT", _donor_check(project, source_bindings))
    add("R2SV07_MATRIX_AND_BLOCKED_SCHEDULE_EXACT", _matrix_schedule_check())
    add("R2SV08_GOVERNANCE_FALSE_AND_ZERO_FLAGS_EXACT", _governance_check(governance, freeze_contract))
    add("R2SV09_SOURCE_ONLY_NEGATIVE_CONTROLS_EXACT_46", negative_control_replay_check(
        evidence_path=negative_control_evidence_path,
        manifest_path=manifest_path,
        project_root=project,
        package_root=package,
    ))
    add("R2SV10_LOCAL_JSON_STRICT_NO_NULL", _all_local_json_no_null(package, output_path))
    add("R2SV11_EXECUTION_GUARD_HAS_NO_SUCCESS_PATH", _execution_guard_hold_check(package, governance))
    add("R2SV12_NEGATIVE_CONTROL_REGISTRATION_MATCHES_PARENT", _negative_control_registration_check(project, source_bindings, nc_contract))
    add("R2SV13_CRITICAL_PARENT_ROOT_HASHES_LITERAL_MATCH", _critical_binding_roots_check(source_bindings, freeze_contract))
    failed = [row["id"] for row in checks if row["pass"] is not True]
    result = {
        "schema": "SIM13_V4B4G_R2_EXECUTION_SOURCE_VALIDATION_V1",
        "status": "PASS_R2_EXECUTION_SOURCE_VALIDATION" if not failed else "FAIL_R2_EXECUTION_SOURCE_VALIDATION",
        "scope": "SOURCE_ONLY_VALIDATION_NO_SOLVER_NO_PHYSICS_NO_TRAJECTORY",
        "score": {"pass": len(checks) - len(failed), "fail": len(failed), "total": len(checks), "failed": failed},
        "checks": checks,
        "source_freeze_pass_eligible": not failed,
        "r2_numerical_preflight_executed": False,
        "r2_execution_negative_controls_executed": False,
        "trajectory_count": 0,
        "authorized_execution_path_status": "NOT_VALIDATED_NO_DIRECT_OWNER_SOURCE",
    }
    if write_output:
        atomic_write_json(output_path, result)
    return result


def _existing_receipt_matches(result: dict[str, Any], output_path: Path = OUTPUT) -> bool:
    try:
        return bool(
            output_path.is_file()
            and not _is_link_or_reparse(output_path)
            and load_path(output_path) == result
        )
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only R2 source-freeze validator",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--write-receipt",
        action="store_true",
        help="explicitly generate the validator receipt; default only verifies the frozen receipt",
    )
    args = parser.parse_args(argv)
    try:
        result = validate_source_freeze(write_output=args.write_receipt)
    except Exception as exc:
        print({"status": "FAIL_R2_EXECUTION_SOURCE_VALIDATION_EXCEPTION", "error": str(exc)})
        return 1
    receipt_match = args.write_receipt or _existing_receipt_matches(result)
    status = result["status"] if receipt_match else "FAIL_R2_EXECUTION_SOURCE_VALIDATION_RECEIPT_DRIFT"
    print({"status": status, "score": result["score"], "mode": "WRITE_RECEIPT" if args.write_receipt else "READ_ONLY_RECEIPT_VERIFY", "receipt_match": receipt_match})
    return 0 if result["source_freeze_pass_eligible"] is True and receipt_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
