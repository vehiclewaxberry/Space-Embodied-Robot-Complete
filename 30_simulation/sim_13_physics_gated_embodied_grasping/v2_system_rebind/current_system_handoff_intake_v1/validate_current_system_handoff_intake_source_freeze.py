"""Read-only exact replay validator for the frozen intake bundle."""

from __future__ import annotations

from pathlib import Path
import hashlib
import sys


PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from current_handoff.freeze_support import (
    FROZEN_PACKAGE_FILE_ALLOWLIST,
    canonical_json_bytes,
    forbidden_package_entries,
    package_file_paths,
    source_inventory,
)
from current_handoff.schema import FROZEN_BINDING_DIGEST, MANDATORY_FALSE, REQUIRED_ABSENT_PATHS, validate_intake_document
from current_handoff.strict_io import IntakeError, strict_json_bytes
from freeze_current_system_handoff_intake import ARTIFACT_PATHS, build_bundle


PROJECT_ROOT = PACKAGE_ROOT.parents[3]


def _receipt_matches(record: object, expected_path: str | None = None) -> bool:
    if not isinstance(record, dict) or set(record) != {"path", "bytes", "sha256"}:
        return False
    path_text = record.get("path")
    if not isinstance(path_text, str) or (expected_path is not None and path_text != expected_path):
        return False
    path = PROJECT_ROOT / path_text
    if not path.is_file():
        return False
    payload = path.read_bytes()
    return (
        record.get("bytes") == len(payload)
        and record.get("sha256") == hashlib.sha256(payload).hexdigest().upper()
    )


def validate() -> dict:
    expected = build_bundle()
    checks: dict[str, bool] = {}
    loaded: dict[str, dict] = {}
    for name, relative in ARTIFACT_PATHS.items():
        path = PACKAGE_ROOT / relative
        exact = path.is_file() and path.read_bytes() == canonical_json_bytes(expected[name])
        checks[f"{name}_exact_replay"] = exact
        if path.is_file():
            parsed = strict_json_bytes(path.read_bytes())
            loaded[name] = parsed if isinstance(parsed, dict) else {}
    gate = loaded.get("gate", {})
    terminal = loaded.get("terminal", {})
    intake = loaded.get("intake", {})
    negative = loaded.get("negative_controls", {})
    audit = loaded.get("independent_audit", {})
    manifest = loaded.get("source_manifest", {})
    try:
        validate_intake_document(intake)
        checks["standalone_intake_schema_and_frozen_binding_exact"] = True
    except (IntakeError, KeyError, TypeError, ValueError):
        checks["standalone_intake_schema_and_frozen_binding_exact"] = False
    checks["gate_ceiling_and_actual_hold_exact"] = gate.get("overall_status") == "PASS_SOURCE_FREEZE_ONLY" and gate.get("current_intake_status") == "HOLD_INCOMPLETE"
    checks["mandatory_false_everywhere"] = all(
        gate.get("flags", {}).get(name) is False
        and terminal.get("flags", {}).get(name) is False
        and intake.get("flags", {}).get(name) is False
        and audit.get("flags", {}).get(name) is False
        for name in MANDATORY_FALSE
    )
    checks["negative_control_set_exact"] = (
        negative.get("controls_passed") == negative.get("controls_total") == 31
        and [item.get("id") for item in negative.get("controls", ())] == [f"NC{i:02d}" for i in range(1, 32)]
    )
    checks["source_and_audit_counts_exact"] = (
        gate.get("source_artifacts_bound") == 15
        and gate.get("source_validation_checks_passed") == gate.get("source_validation_checks_total") == 19
        and isinstance(gate.get("independent_audit_checks_total"), int)
        and gate.get("independent_audit_checks_total", 0) > 0
        and gate.get("independent_audit_checks_passed") == gate.get("independent_audit_checks_total")
    )
    checks["source_manifest_count_and_hashes_exact"] = (
        manifest.get("files") == source_inventory()
        and manifest.get("file_count") == len(manifest.get("files", ()))
        and manifest.get("file_count", 0) > 0
        and manifest.get("forbidden_package_entry_count") == 0
        and manifest.get("forbidden_package_entries") == []
        and all(_receipt_matches(record) for record in manifest.get("files", ()))
    )
    checks["complete_package_file_allowlist_exact"] = (
        manifest.get("frozen_package_file_allowlist") == list(FROZEN_PACKAGE_FILE_ALLOWLIST)
        and manifest.get("package_file_count") == len(FROZEN_PACKAGE_FILE_ALLOWLIST)
        and manifest.get("complete_package_file_allowlist_exact") is True
        and gate.get("complete_package_file_allowlist_exact") is True
        and gate.get("package_files_frozen") == len(FROZEN_PACKAGE_FILE_ALLOWLIST)
        and package_file_paths() == FROZEN_PACKAGE_FILE_ALLOWLIST
    )
    scope = gate.get("receipt_validation_scope", "")
    checks["receipt_preflight_explicitly_not_authority_or_persistent_replay"] = (
        "NO_PERSISTENT_OR_CROSS_PROCESS_CREDIT" in scope
        and "NO_SIGNATURE_OR_TRUST_ROOT__NO_OWNER_AUTHORITY" in scope
    )
    checks["hard_negatives_exact"] = (
        gate.get("preserved_hard_negatives", {}).get("e15", {}).get("max_cross_solver_relative_difference") == 0.05637349419858036
        and gate.get("preserved_hard_negatives", {}).get("harness", {}).get("handoff_g12") == "FAIL"
        and gate.get("preserved_hard_negatives", {}).get("route_c_physical_registry", {}).get("available") == 0
        and gate.get("preserved_hard_negatives", {}).get("route_c_physical_registry", {}).get("total") == 13
    )
    checks["required_absent_paths_exact_and_absent"] = (
        intake.get("required_absent_paths") == list(REQUIRED_ABSENT_PATHS)
        and all(not (PROJECT_ROOT / relative).exists() for relative in REQUIRED_ABSENT_PATHS)
    )
    evidence_paths = [f"{PACKAGE_ROOT.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()}/{ARTIFACT_PATHS[name]}" for name in ("intake", "negative_controls", "independent_audit", "source_manifest")]
    checks["gate_evidence_dag_receipts_exact"] = (
        gate.get("evidence_dag_complete") is True
        and isinstance(gate.get("evidence"), list)
        and [record.get("path") for record in gate.get("evidence", ()) if isinstance(record, dict)] == evidence_paths
        and all(_receipt_matches(record, expected_path) for record, expected_path in zip(gate.get("evidence", ()), evidence_paths))
    )
    checks["gate_contract_receipts_exact"] = (
        isinstance(gate.get("contracts"), list)
        and len(gate.get("contracts", ())) == 5
        and len({record.get("path") for record in gate.get("contracts", ()) if isinstance(record, dict)}) == 5
        and all(_receipt_matches(record) for record in gate.get("contracts", ()))
    )
    gate_path = f"{PACKAGE_ROOT.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()}/{ARTIFACT_PATHS['gate']}"
    checks["terminal_commits_exact_gate_receipt"] = (
        terminal.get("evidence_dag_terminal_commit") is True
        and _receipt_matches(terminal.get("gate"), gate_path)
    )
    checks["artifact_identity_and_binding_digest_exact"] = (
        all(document.get("artifact_id") == "SIM13_CURRENT_SYSTEM_HANDOFF_INTAKE_V1" for document in (intake, manifest, gate, terminal))
        and intake.get("frozen_binding_digest") == gate.get("frozen_binding_digest") == FROZEN_BINDING_DIGEST
    )
    checks["no_forbidden_generated_assets_or_cache_files_or_directories"] = forbidden_package_entries() == []
    passed = bool(checks) and all(checks.values())
    return {
        "schema": "CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_VALIDATOR_V1",
        "pass": passed,
        "status": "PASS_READ_ONLY_VALIDATION" if passed else "FAIL_READ_ONLY_VALIDATION",
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
    }


def main() -> int:
    try:
        result = validate()
    except (IntakeError, OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f"validator=FAIL error={exc}")
        return 1
    print(f"validator={result['status']} checks={result['checks_passed']}/{result['checks_total']}")
    if not result["pass"]:
        print("failed_checks=" + ",".join(name for name, passed in result["checks"].items() if not passed))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
