"""Publish the acyclic R2 raw-adapter source-only freeze chain.

This command never creates or consumes runtime NPZ/CSV, never imports a solver,
and never starts a physics case, trajectory, or campaign.  Publication requires
the exact ``--write-receipts`` flag; all ordinary verification commands are
read-only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from independent_audit_phase_b4g_r2_raw_adapter_source_freeze import audit
from r2_raw_adapter.array_contract import ARRAY_CONTRACT_DOCUMENT_SHA256
from r2_raw_adapter.freeze_support import (
    build_source_manifest,
    document_seal_valid,
    local_source_inventory,
    project_record,
    record_matches,
    seal_document,
    strict_load,
)
from r2_raw_adapter.strict_json import atomic_write_json, canonical_sha256, file_sha256
from validate_phase_b4g_r2_raw_adapter_source_freeze import (
    build_negative_control_evidence,
    validate_source_freeze,
)


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
MANIFEST = HERE / "evidence/SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_MANIFEST_V1.json"
NC_EVIDENCE = HERE / "evidence/SIM13_V4B4G_R2_RAW_ADAPTER_NEGATIVE_CONTROLS_V1.json"
VALIDATION = HERE / "evidence/SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_VALIDATION_V1.json"
AUDIT = HERE / "evidence/SIM13_V4B4G_R2_RAW_ADAPTER_INDEPENDENT_SOURCE_AUDIT_V1.json"
GATE = HERE / "results/SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_FREEZE_GATE_V1.json"
TERMINAL = HERE / "results/SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_FREEZE_TERMINAL_V1.json"
GOVERNANCE = HERE / "contracts/PHASE_B4G_R2_RAW_ADAPTER_GOVERNANCE_V1.json"
FREEZE_CONTRACT = HERE / "contracts/PHASE_B4G_R2_RAW_ADAPTER_SOURCE_FREEZE_CONTRACT_V1.json"


class RawAdapterFreezeError(RuntimeError):
    pass


REQUIRED_FALSE = {
    "r2_numerical_preflight_executed": False,
    "current_system_bound": False,
    "formal_nc19_credit": False,
    "science_credit": False,
    "full_campaign_authorized": False,
    "owner_authorized": False,
    "production_ready": False,
    "release_ready": False,
    "next_stage_authorized": False,
}


def _known_output(path: Path) -> Path:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(HERE.resolve()).as_posix()
    except ValueError as exc:
        raise RawAdapterFreezeError("PUBLICATION_PATH_ESCAPES_PACKAGE") from exc
    expected = set(strict_load(FREEZE_CONTRACT)["output_files"].values())
    if relative not in expected:
        raise RawAdapterFreezeError(f"UNREGISTERED_PUBLICATION_PATH:{relative}")
    return resolved


def _clear_downstream_terminal_and_gate() -> None:
    for path in (TERMINAL, GATE):
        target = _known_output(path)
        if target.exists():
            if target.is_symlink() or not target.is_file():
                raise RawAdapterFreezeError("OLD_OUTPUT_NOT_REGULAR_FILE")
            target.unlink()


def _evidence_records() -> list[dict[str, Any]]:
    return [
        project_record(MANIFEST, HERE, "raw_adapter_source_manifest", "SELF_EXCLUDED_SOURCE_MANIFEST"),
        project_record(NC_EVIDENCE, HERE, "raw_adapter_negative_controls", "EXACT_86_SOURCE_ONLY_MUTATION_RECEIPT"),
        project_record(VALIDATION, HERE, "raw_adapter_source_validation", "SOURCE_VALIDATOR_RECEIPT"),
        project_record(AUDIT, HERE, "raw_adapter_independent_source_audit", "STDLIB_INDEPENDENT_AUDIT_RECEIPT"),
    ]


def _gate_document(
    manifest: dict[str, Any], negative: dict[str, Any], validation: dict[str, Any], independent: dict[str, Any],
) -> dict[str, Any]:
    contract = strict_load(FREEZE_CONTRACT)
    pass_eligible = bool(
        validation["source_freeze_pass_eligible"] is True
        and independent["independent_source_freeze_pass_eligible"] is True
        and negative["result"]["all_killed"] is True
        and negative["result"]["killed_count"] == 86
    )
    if not pass_eligible:
        raise RawAdapterFreezeError("SOURCE_FREEZE_INPUT_RECEIPT_NOT_PASS_ELIGIBLE")
    return seal_document({
        "schema": "SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_FREEZE_GATE_V1",
        "status": contract["highest_permitted_gate_status"],
        "scope": "RAW_EVIDENCE_ADAPTER_SOURCE_FREEZE_ONLY_NOT_NUMERICAL_CURRENT_NC19_OR_SCIENTIFIC_PASS",
        "tool_id": "SIM13_V4B4G_R2_RAW_EVIDENCE_ADAPTER_V1",
        "tooling_source_freeze_pass": True,
        "source_inventory_sha256": manifest["source_inventory_sha256"],
        "source_count": manifest["source_count"],
        "array_contract_document_sha256": ARRAY_CONTRACT_DOCUMENT_SHA256,
        "frozen_registry_case_count": 78,
        "source_only_negative_control_count": 86,
        "source_only_negative_controls_all_killed": True,
        "negative_control_result_sha256": negative["result_sha256"],
        "validation_status": validation["status"],
        "independent_audit_status": independent["status"],
        "evidence": _evidence_records(),
        "required_false": REQUIRED_FALSE,
        "trajectory_count": 0,
        "r2_numerical_preflight_executed": False,
        "current_system_bound": False,
        "formal_nc19_credit": False,
        "science_credit": False,
        "full_campaign_authorized": False,
        "owner_authorized": False,
        "production_ready": False,
        "release_ready": False,
        "next_stage_authorized": False,
        "full_raw_integrity_recomputed": False,
        "g12_source_only_candidate_predicate_pass": False,
        "claim_boundary": "RAW_P1_NARROWED_NOT_ELIMINATED_NO_NUMERICAL_OR_SCIENTIFIC_CREDIT",
    })


def _terminal_document(gate: dict[str, Any]) -> dict[str, Any]:
    gate_record = project_record(GATE, HERE, "raw_adapter_source_freeze_gate", "SOURCE_FREEZE_GATE")
    return seal_document({
        "schema": "SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_FREEZE_TERMINAL_V1",
        "status": gate["status"],
        "scope": "SELF_EXCLUDED_TERMINAL_FOR_RAW_ADAPTER_SOURCE_ONLY_FREEZE",
        "self_excluded": True,
        "acyclic": True,
        "terminal_generated_last": True,
        "terminal_excluded_from_source_manifest": True,
        "records": [gate_record],
        "gate_evidence_sha256": canonical_sha256(gate["evidence"]),
        "source_inventory_sha256": gate["source_inventory_sha256"],
        "source_count": gate["source_count"],
        "array_contract_document_sha256": gate["array_contract_document_sha256"],
        "source_only_negative_control_count": 86,
        "source_only_negative_controls_all_killed": True,
        "required_false": REQUIRED_FALSE,
        "trajectory_count": 0,
        "r2_numerical_preflight_executed": False,
        "current_system_bound": False,
        "formal_nc19_credit": False,
        "science_credit": False,
        "full_campaign_authorized": False,
        "owner_authorized": False,
        "production_ready": False,
        "release_ready": False,
        "next_stage_authorized": False,
        "full_raw_integrity_recomputed": False,
        "claim_boundary": gate["claim_boundary"],
    })


def freeze_sources() -> dict[str, Any]:
    _clear_downstream_terminal_and_gate()
    manifest = build_source_manifest(HERE)
    atomic_write_json(MANIFEST, manifest)
    negative = build_negative_control_evidence(HERE, manifest["source_inventory_sha256"])
    atomic_write_json(NC_EVIDENCE, negative)
    validation = validate_source_freeze(write_output=True)
    if validation["source_freeze_pass_eligible"] is not True:
        raise RawAdapterFreezeError(f"VALIDATION_FAILED:{validation['score']['failed']}")
    independent = audit(write_output=True)
    if independent["independent_source_freeze_pass_eligible"] is not True:
        raise RawAdapterFreezeError(f"INDEPENDENT_AUDIT_FAILED:{independent['score']['failed']}")
    if local_source_inventory(HERE) != manifest["sources"]:
        raise RawAdapterFreezeError("SOURCE_CHANGED_DURING_PUBLICATION")
    gate = _gate_document(manifest, negative, validation, independent)
    atomic_write_json(GATE, gate)
    if not all(record_matches(row, PROJECT_ROOT) for row in gate["evidence"]):
        raise RawAdapterFreezeError("GATE_EVIDENCE_RECORD_SELF_CHECK_FAILED")
    terminal = _terminal_document(gate)
    atomic_write_json(TERMINAL, terminal)
    reloaded = strict_load(TERMINAL)
    if (
        reloaded != terminal or not document_seal_valid(reloaded)
        or not record_matches(reloaded["records"][0], PROJECT_ROOT)
        or reloaded["gate_evidence_sha256"] != canonical_sha256(strict_load(GATE)["evidence"])
        or local_source_inventory(HERE) != manifest["sources"]
    ):
        raise RawAdapterFreezeError("TERMINAL_OR_FINAL_SOURCE_SELF_CHECK_FAILED")
    return {
        "schema": "SIM13_V4B4G_R2_RAW_ADAPTER_SOURCE_FREEZE_PUBLICATION_RECEIPT_V1",
        "status": gate["status"],
        "source_freeze_pass": True,
        "manifest_sha256": file_sha256(MANIFEST),
        "gate_sha256": file_sha256(GATE),
        "terminal_sha256": file_sha256(TERMINAL),
        "trajectory_count": 0,
        "r2_numerical_preflight_executed": False,
        "next_stage_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish R2 raw-adapter source freeze", allow_abbrev=False)
    parser.add_argument("--write-receipts", action="store_true", help="required exact flag for publication writes")
    args = parser.parse_args(argv)
    if not args.write_receipts:
        print(json.dumps({
            "status": "HOLD_EXPLICIT_WRITE_RECEIPTS_FLAG_REQUIRED",
            "write_performed": False, "trajectory_count": 0,
            "r2_numerical_preflight_executed": False,
        }, sort_keys=True))
        return 2
    try:
        receipt = freeze_sources()
    except Exception as exc:
        print(json.dumps({"status": "FAIL_R2_RAW_ADAPTER_SOURCE_FREEZE_EXCEPTION", "error": f"{type(exc).__name__}:{exc}"}, sort_keys=True))
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
