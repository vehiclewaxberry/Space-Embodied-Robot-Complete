"""Build the deterministic source-freeze bundle; no model generator is imported."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from current_handoff.evaluator import evaluate_default_snapshot
from current_handoff.freeze_support import (
    FROZEN_PACKAGE_FILE_ALLOWLIST,
    canonical_json_bytes,
    document_receipt,
    file_receipt,
    forbidden_package_entries,
    package_file_paths,
    source_inventory,
    transactional_write_json_bundle,
)
from current_handoff.negative_controls import run_negative_controls
from current_handoff.schema import MANDATORY_FALSE
from current_handoff.strict_io import PROJECT_ROOT
from independent_audit_current_system_handoff_intake import build_audit


ARTIFACT_PATHS = {
    "intake": "evidence/CURRENT_SYSTEM_HANDOFF_INTAKE_V1.json",
    "negative_controls": "evidence/CURRENT_SYSTEM_HANDOFF_NEGATIVE_CONTROLS_V1.json",
    "independent_audit": "evidence/CURRENT_SYSTEM_HANDOFF_INDEPENDENT_AUDIT_V1.json",
    "source_manifest": "evidence/CURRENT_SYSTEM_HANDOFF_SOURCE_MANIFEST_V1.json",
    "gate": "results/CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_GATE_V1.json",
    "terminal": "results/CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_TERMINAL_V1.json",
}
CONTRACT_NAMES = (
    "CURRENT_SYSTEM_HANDOFF_INTAKE_SCHEMA_V1.json",
    "FIELD_SOURCE_CROSSWALK_V1.json",
    "ROUTE_C_DISPOSITION_CONTRACT_V1.json",
    "PROMOTION_SEQUENCE_CONTRACT_V1.json",
    "CURRENT_SYSTEM_HANDOFF_NEGATIVE_CONTROL_CONTRACT_V1.json",
)
PACKAGE_PROJECT_RELATIVE = PACKAGE_ROOT.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def _project_artifact_path(name: str) -> str:
    return f"{PACKAGE_PROJECT_RELATIVE}/{ARTIFACT_PATHS[name]}"


def build_source_manifest() -> dict:
    files = source_inventory()
    forbidden = forbidden_package_entries()
    complete_package_files = package_file_paths()
    return {
        "schema": "CURRENT_SYSTEM_HANDOFF_SOURCE_MANIFEST_V1",
        "artifact_id": "SIM13_CURRENT_SYSTEM_HANDOFF_INTAKE_V1",
        "inventory_scope": "SOURCE_HASH_MANIFEST_PLUS_COMPLETE_PACKAGE_FILE_ALLOWLIST__NO_UNLISTED_EVIDENCE_RESULTS_OR_OTHER_FILES",
        "files": files,
        "file_count": len(files),
        "frozen_package_file_allowlist": list(FROZEN_PACKAGE_FILE_ALLOWLIST),
        "package_file_count": len(complete_package_files),
        "complete_package_file_allowlist_exact": complete_package_files == FROZEN_PACKAGE_FILE_ALLOWLIST,
        "forbidden_package_entries": forbidden,
        "forbidden_package_entry_count": len(forbidden),
        "urdf_generator_source_imported": False,
        "generated_cad_step_mesh_urdf_or_physics_assets": False,
    }


def _contract_receipts() -> list[dict]:
    return [file_receipt(PACKAGE_ROOT / "contracts" / name) for name in CONTRACT_NAMES]


def build_bundle() -> dict[str, dict]:
    intake = evaluate_default_snapshot()
    negative = run_negative_controls()
    audit = build_audit()
    manifest = build_source_manifest()
    if (
        not intake["source_only_validation_pass"]
        or not negative["all_passed"]
        or not audit["independent_audit_pass"]
        or manifest["forbidden_package_entry_count"] != 0
        or not manifest["complete_package_file_allowlist_exact"]
    ):
        raise RuntimeError("source-freeze prerequisites did not pass")
    evidence_documents = {
        "intake": intake,
        "negative_controls": negative,
        "independent_audit": audit,
        "source_manifest": manifest,
    }
    evidence_receipts = [document_receipt(_project_artifact_path(name), document) for name, document in evidence_documents.items()]
    domain_counts: dict[str, int] = {}
    for domain in intake["domains"].values():
        classification = domain["classification"]
        domain_counts[classification] = domain_counts.get(classification, 0) + 1
    gate = {
        "schema": "CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_GATE_V1",
        "artifact_id": "SIM13_CURRENT_SYSTEM_HANDOFF_INTAKE_V1",
        "overall_status": "PASS_SOURCE_FREEZE_ONLY",
        "current_intake_status": "HOLD_INCOMPLETE",
        "highest_theoretical_status": "INTAKE_COMPLETE_PENDING_AUTHORIZED_EXECUTION",
        "source_freeze_tooling_pass": True,
        "source_artifacts_bound": len(intake["source_receipts"]),
        "source_validation_checks_passed": sum(intake["checks"].values()),
        "source_validation_checks_total": len(intake["checks"]),
        "negative_controls_passed": negative["controls_passed"],
        "negative_controls_total": negative["controls_total"],
        "independent_audit_checks_passed": audit["checks_passed"],
        "independent_audit_checks_total": audit["checks_total"],
        "domain_classification_counts": domain_counts,
        "frozen_binding_digest": intake["frozen_binding_digest"],
        "contracts": _contract_receipts(),
        "evidence": evidence_receipts,
        "receipt_validation_scope": "SCHEMA_FRESHNESS_BINDING_IN_MEMORY_REPLAY_PREFLIGHT_ONLY__NO_PERSISTENT_OR_CROSS_PROCESS_CREDIT__NO_SIGNATURE_OR_TRUST_ROOT__NO_OWNER_AUTHORITY",
        "evidence_dag_complete": True,
        "complete_package_file_allowlist_exact": manifest["complete_package_file_allowlist_exact"],
        "package_files_frozen": manifest["package_file_count"],
        "preserved_hard_negatives": intake["preserved_hard_negatives"],
        "flags": {name: False for name in MANDATORY_FALSE},
        "generated_cad_step_mesh_urdf_or_physics_assets": False,
        "urdf_generator_invoked": False,
        "legacy_unified_r2_validator_invoked": False,
        "release_credit": False,
        "ceiling_note": "PASS applies only to source contracts, one-read pinned intake, negative controls, independent audit, deterministic replay and validators. The actual intake remains HOLD_INCOMPLETE.",
    }
    terminal = {
        "schema": "CURRENT_SYSTEM_HANDOFF_INTAKE_SOURCE_FREEZE_TERMINAL_V1",
        "artifact_id": "SIM13_CURRENT_SYSTEM_HANDOFF_INTAKE_V1",
        "terminal_status": "PASS_SOURCE_FREEZE_ONLY",
        "current_intake_status": "HOLD_INCOMPLETE",
        "gate": document_receipt(_project_artifact_path("gate"), gate),
        "evidence_dag_terminal_commit": True,
        "flags": {name: False for name in MANDATORY_FALSE},
        "release_credit": False,
        "next_required_external_closure": "Complete eligible current-system intake evidence and obtain separate authorized execution; this package cannot issue that authority.",
    }
    return {**evidence_documents, "gate": gate, "terminal": terminal}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print", dest="print_name", choices=tuple(ARTIFACT_PATHS) + ("all",))
    parser.add_argument("--write", action="store_true", help="publish the deterministic bundle; terminal commit record is replaced last")
    args = parser.parse_args()
    bundle = build_bundle()
    if args.print_name:
        if args.print_name == "all":
            print(json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
        else:
            print(canonical_json_bytes(bundle[args.print_name]).decode("utf-8"), end="")
    if args.write:
        documents = {PACKAGE_ROOT / ARTIFACT_PATHS[name]: document for name, document in bundle.items()}
        transactional_write_json_bundle(documents, PACKAGE_ROOT / ARTIFACT_PATHS["terminal"])
    if not args.print_name and not args.write:
        gate = bundle["gate"]
        print(
            "freeze_preview={} intake={} checks={}/{} nc={}/{} audit={}/{}".format(
                gate["overall_status"],
                gate["current_intake_status"],
                gate["source_validation_checks_passed"],
                gate["source_validation_checks_total"],
                gate["negative_controls_passed"],
                gate["negative_controls_total"],
                gate["independent_audit_checks_passed"],
                gate["independent_audit_checks_total"],
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
