"""Fail-closed authorization boundary for any future R2 numerical execution.

Authorization is checked before importing any historical physics module and
before creating an output directory.  Source-freeze tests exercise only the
denial path; this file never grants or manufactures authorization.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

from .schedule import MATRIX_SHA256, SCHEDULE_SHA256
from .strict_json import canonical_sha256, file_sha256, load_path


AUTHORIZATION_KEYS = {
    "schema", "status", "authorization_id", "authorization_scope", "authorized_once",
    "already_consumed", "owner_execution_authorized", "matrix_sha256", "schedule_sha256",
    "case_count", "trajectory_budget", "execution_source_freeze_terminal_sha256",
    "direct_owner_source_id", "direct_owner_source_sha256", "issued_utc", "expires_utc",
    "single_use_nonce", "persistent_consumption_ledger_path", "persistent_consumption_ledger_sha256",
}
MANIFEST_KEYS = {
    "schema", "scope", "self_excluded", "acyclic", "terminal_excluded",
    "excluded_path_prefixes", "terminal_exclusion_rule", "source_count", "sources",
    "source_inventory_sha256", "r2_numerical_preflight_executed", "trajectory_count",
}
LEGACY_MODULE_TOKENS = ("b4_solver", "b4g_solver", "constraint_solver", "forced_retraction", "b4g_solver.campaign")


class ExecutionAuthorizationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthorizationReceipt:
    authorization_id: str
    execution_source_freeze_terminal_sha256: str
    source_binding_count: int
    preserved_raw_inventory_sha256: str
    single_use_nonce: str
    persistent_consumption_ledger_path: str
    persistent_consumption_ledger_sha256: str


@dataclass(frozen=True)
class ConsumedAuthorizationReceipt:
    validated: AuthorizationReceipt
    ledger_sha256_after_consumption: str


def legacy_modules_loaded() -> list[str]:
    return sorted(name for name in sys.modules if any(token in name for token in LEGACY_MODULE_TOKENS))


def _project_root_from(package_root: Path) -> Path:
    for candidate in (package_root, *package_root.parents):
        if (candidate / "PROJECT_MAP.md").is_file() and (candidate / "30_simulation").is_dir():
            return candidate
    raise ExecutionAuthorizationError("PROJECT_ROOT_NOT_FOUND")


def _verify_sources(project_root: Path, source_contract: dict[str, Any]) -> int:
    sources = source_contract.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ExecutionAuthorizationError("SOURCE_BINDINGS_MISSING")
    for row in sources:
        if not isinstance(row, dict) or set(("id", "path", "bytes", "sha256")) - set(row):
            raise ExecutionAuthorizationError("SOURCE_BINDING_SCHEMA_INVALID")
        path = project_root / row["path"]
        if path.is_symlink() or not path.is_file() or path.stat().st_size != row["bytes"] or file_sha256(path) != row["sha256"]:
            raise ExecutionAuthorizationError(f"BOUND_SOURCE_DRIFT:{row.get('id', 'UNKNOWN')}")
    return len(sources)


def _current_local_source_inventory(package_root: Path) -> list[dict[str, Any]]:
    """Independently rebuild the manifest's complete local source inventory."""

    root = package_root.resolve()
    candidates: list[Path] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.suffix.lower() in {".py", ".md", ".ini"}:
            candidates.append(path)
    for subtree, suffixes in (
        ("r2_preflight", {".py"}),
        ("contracts", {".json"}),
        ("tests", {".py"}),
    ):
        base = root / subtree
        if not base.exists() or base.is_symlink() or not base.is_dir():
            raise ExecutionAuthorizationError(f"LOCAL_SOURCE_SUBTREE_INVALID:{subtree}")
        candidates.extend(
            path
            for path in sorted(base.rglob("*"), key=lambda item: item.as_posix())
            if path.is_file() and path.suffix.lower() in suffixes
        )
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.is_symlink() or not candidate.is_file():
            raise ExecutionAuthorizationError("LOCAL_SOURCE_LINK_OR_NONFILE")
        try:
            relative = candidate.resolve().relative_to(root).as_posix()
        except ValueError as exc:
            raise ExecutionAuthorizationError("LOCAL_SOURCE_ESCAPES_PACKAGE") from exc
        if relative in seen:
            raise ExecutionAuthorizationError(f"DUPLICATE_LOCAL_SOURCE_PATH:{relative}")
        seen.add(relative)
        rows.append({
            "path": relative,
            "bytes": candidate.stat().st_size,
            "sha256": file_sha256(candidate),
        })
    rows.sort(key=lambda row: row["path"])
    if not rows:
        raise ExecutionAuthorizationError("LOCAL_SOURCE_INVENTORY_EMPTY")
    return rows


def _verify_local_source_manifest(package_root: Path, manifest: Any) -> list[dict[str, Any]]:
    if not isinstance(manifest, dict) or set(manifest) != MANIFEST_KEYS:
        raise ExecutionAuthorizationError("EXECUTION_SOURCE_MANIFEST_SCHEMA_INVALID")
    if not (
        manifest["schema"] == "SIM13_V4B4G_R2_EXECUTION_SOURCE_MANIFEST_V1"
        and manifest["scope"] == "LOCAL_SOURCE_AND_CONTRACT_BYTES_ONLY_NO_EXECUTION"
        and manifest["self_excluded"] is True
        and manifest["acyclic"] is True
        and manifest["terminal_excluded"] is True
        and manifest["excluded_path_prefixes"] == ["evidence/", "results/"]
        and manifest["terminal_exclusion_rule"] == "TERMINAL_GENERATED_LAST_AND_RECORDS_GATE_ONLY"
        and manifest["r2_numerical_preflight_executed"] is False
        and type(manifest["trajectory_count"]) is int
        and manifest["trajectory_count"] == 0
        and type(manifest["source_count"]) is int
    ):
        raise ExecutionAuthorizationError("EXECUTION_SOURCE_MANIFEST_SEMANTICS_INVALID")
    sources = manifest["sources"]
    if not isinstance(sources, list) or not sources or manifest["source_count"] != len(sources):
        raise ExecutionAuthorizationError("EXECUTION_SOURCE_MANIFEST_COUNT_INVALID")
    previous = ""
    for row in sources:
        if not isinstance(row, dict) or set(row) != {"path", "bytes", "sha256"}:
            raise ExecutionAuthorizationError("EXECUTION_SOURCE_MANIFEST_ROW_SCHEMA_INVALID")
        relative = row["path"]
        if (
            type(relative) is not str
            or not relative
            or "\\" in relative
            or relative.startswith(("/", "evidence/", "results/"))
            or any(part in {"", ".", ".."} for part in relative.split("/"))
            or relative <= previous
            or type(row["bytes"]) is not int
            or row["bytes"] < 0
            or type(row["sha256"]) is not str
            or len(row["sha256"]) != 64
            or any(char not in "0123456789ABCDEF" for char in row["sha256"])
        ):
            raise ExecutionAuthorizationError("EXECUTION_SOURCE_MANIFEST_ROW_INVALID")
        previous = relative
    inventory_sha = canonical_sha256(sources)
    if manifest["source_inventory_sha256"] != inventory_sha:
        raise ExecutionAuthorizationError("EXECUTION_SOURCE_MANIFEST_SEMANTIC_HASH_INVALID")
    current = _current_local_source_inventory(package_root)
    if current != sources:
        raise ExecutionAuthorizationError("EXECUTION_SOURCE_MANIFEST_CURRENT_INVENTORY_DRIFT")
    return sources


def validate_invalidation_semantics(invalidation: Any) -> bool:
    required_cases = {
        "MIDPOINT_COARSE__A1__ALPHA_16__TCMD_MS_5",
        "MIDPOINT_COARSE__A1__ALPHA_16__TCMD_MS_10",
        "MIDPOINT_COARSE__A1__ALPHA_16__TCMD_MS_20",
    }
    failure = invalidation.get("failure", "") if isinstance(invalidation, dict) else ""
    return bool(
        isinstance(invalidation, dict)
        and invalidation.get("active") is True
        and invalidation.get("raw_case_and_diagnostic_evidence_preserved") is True
        and all(case in failure for case in required_cases)
        and "B4F-G06-ENERGY-MINUS-WORK-IDENTITY" in failure
    )


def validate_failure_slots(slots: Any) -> bool:
    if not isinstance(slots, list) or len(slots) != 144:
        return False
    observed = {
        row["slot_index"]: row["case_id"]
        for row in slots
        if isinstance(row, dict) and row.get("slot_index") in (82, 84, 88)
    }
    return observed == {
        82: "MIDPOINT_COARSE__A1__ALPHA_16__TCMD_MS_10",
        84: "MIDPOINT_COARSE__A1__ALPHA_16__TCMD_MS_5",
        88: "MIDPOINT_COARSE__A1__ALPHA_16__TCMD_MS_20",
    }


def validate_preserved_raw_inventory(inventory: Any, records: Any) -> bool:
    if not isinstance(inventory, dict) or not isinstance(records, list):
        return False
    observed = {
        "json_count": sum(row.get("path", "").lower().endswith(".json") for row in records if isinstance(row, dict)),
        "npz_count": sum(row.get("path", "").lower().endswith(".npz") for row in records if isinstance(row, dict)),
        "file_count": len(records),
        "canonical_sha256": canonical_sha256(records),
    }
    return all(inventory.get(key) == value for key, value in observed.items())


def validate_r1_contract_semantics(gate: Any) -> bool:
    required_false = gate.get("required_false", {}) if isinstance(gate, dict) else {}
    return bool(
        isinstance(gate, dict)
        and gate.get("status") == "PASS_PHASE_B4G_R1_REGISTERED_FAILURE_CLOSURE_CONTRACT_ONLY"
        and gate.get("original_b4g_final_credit") is False
        and gate.get("b4g_scientific_gate_pass") is False
        and required_false.get("current_system_bound") is False
        and required_false.get("next_stage_authorized") is False
    )


def _source_by_id(source_contract: dict[str, Any], source_id: str) -> dict[str, Any]:
    matches = [row for row in source_contract["sources"] if row.get("id") == source_id]
    if len(matches) != 1:
        raise ExecutionAuthorizationError(f"SOURCE_ID_CARDINALITY:{source_id}:{len(matches)}")
    return matches[0]


def _verify_failed_baseline(project_root: Path, source_contract: dict[str, Any]) -> str:
    invalidation_row = _source_by_id(source_contract, "b4g_active_invalidation")
    invalidation = load_path(project_root / invalidation_row["path"])
    if not validate_invalidation_semantics(invalidation):
        raise ExecutionAuthorizationError("B4G_ACTIVE_INVALIDATION_SEMANTICS_DRIFT")
    schedule_row = _source_by_id(source_contract, "b4g_registered_schedule")
    schedule = load_path(project_root / schedule_row["path"])
    slots = schedule.get("slots") if isinstance(schedule, dict) else "INVALID"
    if not validate_failure_slots(slots):
        raise ExecutionAuthorizationError("B4G_REGISTERED_FAILURE_SLOT_DRIFT")

    inventory = source_contract.get("preserved_raw_inventory")
    if not isinstance(inventory, dict):
        raise ExecutionAuthorizationError("RAW_INVENTORY_CONTRACT_MISSING")
    raw_root = project_root / inventory["path"]
    files = sorted((path for path in raw_root.iterdir() if path.is_file()), key=lambda path: path.name)
    if raw_root.is_symlink() or any(path.is_symlink() for path in files):
        raise ExecutionAuthorizationError("RAW_INVENTORY_SYMLINK_FORBIDDEN")
    records = [{"path": path.name, "bytes": path.stat().st_size, "sha256": file_sha256(path)} for path in files]
    if not validate_preserved_raw_inventory(inventory, records):
        raise ExecutionAuthorizationError("RAW_INVENTORY_DRIFT")
    return canonical_sha256(records)


def _verify_r1_contract_only(project_root: Path, source_contract: dict[str, Any]) -> None:
    row = _source_by_id(source_contract, "b4g_r1_failure_closure_gate")
    # This bound legacy gate contains historical null diagnostics.  The file is
    # already byte/hash verified by _verify_sources; allow null only for this
    # narrow outer read, then validate the non-null governance leaves below.
    gate = load_path(project_root / row["path"], allow_null=True)
    if not validate_r1_contract_semantics(gate):
        raise ExecutionAuthorizationError("R1_CONTRACT_ONLY_BOUNDARY_DRIFT")


def require_single_execution_authorization(
    authorization_path: Path | None,
    *,
    package_root: Path,
    source_bindings_path: Path,
    source_freeze_terminal_path: Path,
) -> AuthorizationReceipt:
    """Return only after every authority and source condition is satisfied."""

    if legacy_modules_loaded():
        raise ExecutionAuthorizationError("LEGACY_MODULE_ALREADY_LOADED_BEFORE_GUARD")
    fixed_package_root = Path(__file__).resolve().parents[1]
    if package_root.resolve() != fixed_package_root:
        raise ExecutionAuthorizationError("CALLER_SUPPLIED_PACKAGE_ROOT_FORBIDDEN")
    # This is deliberately the first filesystem decision.  No output path is
    # accepted or created here, and no historical module has been imported.
    if authorization_path is None or not authorization_path.is_file() or authorization_path.is_symlink():
        raise ExecutionAuthorizationError("MISSING_SINGLE_EXECUTION_AUTHORIZATION")
    authorization = load_path(authorization_path)
    if not isinstance(authorization, dict) or set(authorization) != AUTHORIZATION_KEYS:
        raise ExecutionAuthorizationError("EXECUTION_AUTHORIZATION_SCHEMA_INVALID")
    if not (
        authorization["schema"] == "SIM13_V4B4G_R2_SINGLE_EXECUTION_AUTHORIZATION_V1"
        and authorization["status"] == "AUTHORIZED_SINGLE_R2_NUMERICAL_PREFLIGHT_EXECUTION"
        and isinstance(authorization["authorization_id"], str) and authorization["authorization_id"]
        and authorization["authorization_scope"] == "EXACT_FROZEN_78_CASE_R2_NUMERICAL_PREFLIGHT_ONCE"
        and authorization["authorized_once"] is True
        and authorization["already_consumed"] is False
        and authorization["owner_execution_authorized"] is True
        and authorization["matrix_sha256"] == MATRIX_SHA256
        and authorization["schedule_sha256"] == SCHEDULE_SHA256
        and authorization["case_count"] == 78
        and authorization["trajectory_budget"] == 78
    ):
        raise ExecutionAuthorizationError("EXECUTION_AUTHORIZATION_CONTENT_INVALID")
    try:
        issued = datetime.fromisoformat(authorization["issued_utc"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(authorization["expires_utc"].replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ExecutionAuthorizationError("AUTHORIZATION_TIME_WINDOW_INVALID") from exc
    now = datetime.now(timezone.utc)
    if issued.tzinfo is None or expires.tzinfo is None or not (issued <= now <= expires) or not (0.0 < (expires - issued).total_seconds() <= 7200.0):
        raise ExecutionAuthorizationError("AUTHORIZATION_NOT_FRESH_OR_WINDOW_OVER_2H")
    nonce = authorization["single_use_nonce"]
    if not isinstance(nonce, str) or len(nonce) != 64 or any(char not in "0123456789ABCDEF" for char in nonce):
        raise ExecutionAuthorizationError("AUTHORIZATION_NONCE_INVALID")
    if source_freeze_terminal_path.is_symlink() or not source_freeze_terminal_path.is_file():
        raise ExecutionAuthorizationError("EXECUTION_SOURCE_FREEZE_TERMINAL_MISSING")
    terminal_hash = file_sha256(source_freeze_terminal_path)
    if terminal_hash != authorization["execution_source_freeze_terminal_sha256"]:
        raise ExecutionAuthorizationError("EXECUTION_SOURCE_FREEZE_TERMINAL_HASH_MISMATCH")
    terminal = load_path(source_freeze_terminal_path)
    if not (
        terminal.get("status") == "PASS_PHASE_B4G_R2_EXECUTION_TOOLING_SOURCE_FREEZE_ONLY"
        and terminal.get("self_excluded") is True and terminal.get("acyclic") is True
        and terminal.get("r2_numerical_preflight_executed") is False
        and terminal.get("trajectory_count") == 0
    ):
        raise ExecutionAuthorizationError("EXECUTION_SOURCE_FREEZE_TERMINAL_SEMANTICS_INVALID")
    expected_bindings = (fixed_package_root / "contracts/PHASE_B4G_R2_EXECUTION_SOURCE_BINDINGS_V1.json").resolve()
    expected_terminal = (fixed_package_root / "results/SIM13_V4B4G_R2_EXECUTION_SOURCE_FREEZE_TERMINAL_V1.json").resolve()
    if source_bindings_path.resolve() != expected_bindings or source_freeze_terminal_path.resolve() != expected_terminal:
        raise ExecutionAuthorizationError("CALLER_SUPPLIED_AUTHORITY_OR_SOURCE_PATH_FORBIDDEN")
    source_contract = load_path(expected_bindings)
    manifest_path = fixed_package_root / "evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_MANIFEST_V1.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ExecutionAuthorizationError("EXECUTION_SOURCE_MANIFEST_MISSING")
    manifest = load_path(manifest_path)
    manifest_sources = _verify_local_source_manifest(fixed_package_root, manifest)
    binding_rows = [
        row for row in manifest_sources
        if row.get("path") == "contracts/PHASE_B4G_R2_EXECUTION_SOURCE_BINDINGS_V1.json"
    ]
    if (
        terminal.get("source_inventory_sha256") != manifest.get("source_inventory_sha256")
        or len(binding_rows) != 1
        or binding_rows[0].get("sha256") != file_sha256(expected_bindings)
        or binding_rows[0].get("bytes") != expected_bindings.stat().st_size
    ):
        raise ExecutionAuthorizationError("TERMINAL_MANIFEST_SOURCE_BINDING_CHAIN_INVALID")
    project_root = _project_root_from(fixed_package_root)
    binding_count = _verify_sources(project_root, source_contract)
    policy = source_contract.get("execution_authority_policy", {})
    bound_owner_id = policy.get("bound_direct_owner_source_id")
    if bound_owner_id == "NOT_AVAILABLE_NO_EXECUTION_AUTHORITY" or bound_owner_id != authorization["direct_owner_source_id"]:
        raise ExecutionAuthorizationError("DIRECT_OWNER_SOURCE_NOT_BOUND_IN_THIS_FREEZE")
    owner_row = _source_by_id(source_contract, bound_owner_id)
    if owner_row["sha256"] != authorization["direct_owner_source_sha256"]:
        raise ExecutionAuthorizationError("DIRECT_OWNER_SOURCE_HASH_MISMATCH")
    ledger = project_root / authorization["persistent_consumption_ledger_path"]
    if ledger.is_symlink() or not ledger.is_file() or file_sha256(ledger) != authorization["persistent_consumption_ledger_sha256"]:
        raise ExecutionAuthorizationError("PERSISTENT_CONSUMPTION_LEDGER_MISSING_OR_DRIFTED")
    ledger_value = load_path(ledger)
    if ledger_value.get("schema") != "SIM13_V4B4G_R2_AUTHORIZATION_CONSUMPTION_LEDGER_V1" or nonce in ledger_value.get("consumed_nonces", []):
        raise ExecutionAuthorizationError("AUTHORIZATION_NONCE_ALREADY_CONSUMED_OR_LEDGER_INVALID")
    inventory_hash = _verify_failed_baseline(project_root, source_contract)
    _verify_r1_contract_only(project_root, source_contract)
    return AuthorizationReceipt(
        authorization["authorization_id"], terminal_hash, binding_count, inventory_hash,
        nonce, authorization["persistent_consumption_ledger_path"], authorization["persistent_consumption_ledger_sha256"],
    )


def consume_authorization(receipt: AuthorizationReceipt, *, package_root: Path) -> ConsumedAuthorizationReceipt:
    """This freeze cannot consume authority; a new version must add locked CAS."""

    raise ExecutionAuthorizationError("EXECUTION_PATH_NOT_IMPLEMENTED_NO_DIRECT_OWNER_SOURCE_IN_THIS_FREEZE")


def authorized_lazy_imports(receipt: ConsumedAuthorizationReceipt, *, package_root: Path) -> dict[str, Any]:
    """Import bound legacy modules only after the caller obtained a receipt."""

    raise ExecutionAuthorizationError("EXECUTION_PATH_NOT_IMPLEMENTED_NO_DIRECT_OWNER_SOURCE_IN_THIS_FREEZE")


def create_output_root_after_authorization(receipt: ConsumedAuthorizationReceipt, output_root: Path) -> Path:
    raise ExecutionAuthorizationError("EXECUTION_PATH_NOT_IMPLEMENTED_NO_DIRECT_OWNER_SOURCE_IN_THIS_FREEZE")


def _cli() -> int:
    parser = argparse.ArgumentParser(description="R2 authorization guard; does not execute physics")
    parser.add_argument("--authorization")
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parents[1]
    try:
        require_single_execution_authorization(
            Path(args.authorization) if args.authorization else None,
            package_root=here,
            source_bindings_path=here / "contracts/PHASE_B4G_R2_EXECUTION_SOURCE_BINDINGS_V1.json",
            source_freeze_terminal_path=here / "results/SIM13_V4B4G_R2_EXECUTION_SOURCE_FREEZE_TERMINAL_V1.json",
        )
    except ExecutionAuthorizationError as exc:
        # stdout is the subprocess proof channel; it is not an evidence file.
        print({"status": str(exc), "legacy_modules_loaded": legacy_modules_loaded(), "output_tree_exists": Path(args.output_root).exists()})
        return 23
    print({"status": "AUTHORIZATION_VALIDATED_ONLY_NO_EXECUTION_STARTED"})
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
