"""Publish the acyclic full raw-integrity backend source-only freeze chain."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from independent_audit_phase_b4g_r2_full_integrity_source_freeze import audit
from r2_full_integrity.freeze_support import (
    file_sha256, project_record, record_valid, seal, seal_valid,
    source_inventory, strict_load,
)
from r2_full_integrity.negative_controls import run_negative_controls
from r2_full_integrity.source_api import load_raw_modules
from validate_phase_b4g_r2_full_integrity_source_freeze import validate_source_freeze


HERE = Path(__file__).resolve().parent
CONTRACT = HERE / "contracts/PHASE_B4G_R2_FULL_RAW_INTEGRITY_SOURCE_FREEZE_CONTRACT_V1.json"
MANIFEST = HERE / "evidence/SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_SOURCE_MANIFEST_V1.json"
NEGATIVE = HERE / "evidence/SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_NEGATIVE_CONTROLS_V1.json"
VALIDATION = HERE / "evidence/SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_SOURCE_VALIDATION_V1.json"
AUDIT = HERE / "evidence/SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_INDEPENDENT_AUDIT_V1.json"
GATE = HERE / "results/SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_SOURCE_FREEZE_GATE_V1.json"
TERMINAL = HERE / "results/SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_SOURCE_FREEZE_TERMINAL_V1.json"

REQUIRED_FALSE = {
    "r2_numerical_preflight_executed": False,
    "current_system_bound": False,
    "formal_nc19_credit": False,
    "scientific_credit": False,
    "owner_authorized": False,
    "production_credit": False,
    "release_authorized": False,
    "next_stage_authorized": False,
}


class PublicationError(RuntimeError):
    pass


def _write(path: Path, value: dict[str, Any]) -> None:
    load_raw_modules()["strict_json"].atomic_write_json(path, value)


def _manifest() -> dict[str, Any]:
    sources = source_inventory(HERE)
    canonical = load_raw_modules()["strict_json"].canonical_sha256
    return seal({
        "schema": "SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_SOURCE_MANIFEST_V1",
        "scope": "LOCAL_SOURCE_AND_CONTRACT_BYTES_SELF_EXCLUDED_OUTPUTS",
        "self_excluded": True,
        "acyclic": True,
        "excluded_output_prefixes": ["evidence/", "results/"],
        "source_count": len(sources),
        "sources": sources,
        "source_inventory_sha256": canonical(sources),
        "trajectory_count": 0,
        "actual_case_full_raw_integrity_recomputed": False,
    })


def _gate(manifest: dict[str, Any], negative: dict[str, Any], validation: dict[str, Any], independent: dict[str, Any]) -> dict[str, Any]:
    contract = strict_load(CONTRACT)
    if not (
        negative["result"]["passed"] is True
        and negative["result"]["control_count"] == negative["result"]["killed_count"] == 14
        and validation["source_freeze_pass_eligible"] is True
        and validation["pytest_passed_count"] == 18
        and independent["independent_source_freeze_pass_eligible"] is True
    ):
        raise PublicationError("UPSTREAM_RECEIPT_NOT_PASS_ELIGIBLE")
    records = [
        project_record(MANIFEST, "full_integrity_source_manifest", "SELF_EXCLUDED_SOURCE_MANIFEST"),
        project_record(NEGATIVE, "full_integrity_negative_controls", "14_OF_14_MUTATION_CONTROLS"),
        project_record(VALIDATION, "full_integrity_source_validation", "SOURCE_VALIDATOR_RECEIPT"),
        project_record(AUDIT, "full_integrity_independent_audit", "INDEPENDENT_AUDIT_RECEIPT"),
    ]
    return seal({
        "schema": "SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_SOURCE_FREEZE_GATE_V1",
        "status": contract["highest_permitted_gate_status"],
        "scope": "FULL_RAW_INTEGRITY_BACKEND_SOURCE_FREEZE_ONLY_NOT_R2_EXECUTION_OR_SCIENTIFIC_PASS",
        "tool_id": "SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_BACKEND_V1",
        "tooling_source_freeze_pass": True,
        "full_raw_integrity_backend_implemented": True,
        "technical_fixture_full_gate_set_recomputed": True,
        "technical_fixture_all_gate_predicates_true": True,
        "required_gate_count": 10,
        "source_count": manifest["source_count"],
        "source_inventory_sha256": manifest["source_inventory_sha256"],
        "pytest_passed_count": 18,
        "negative_control_count": 14,
        "negative_controls_all_killed": True,
        "evidence": records,
        "required_false": REQUIRED_FALSE,
        "actual_raw_case_count": 0,
        "trajectory_count": 0,
        "full_raw_integrity_recomputed": False,
        "actual_case_full_raw_integrity_recomputed": False,
        "source_only_candidate_predicate_pass": False,
        "r2_numerical_preflight_executed": False,
        "current_system_bound": False,
        "formal_nc19_credit": False,
        "scientific_credit": False,
        "owner_authorized": False,
        "production_credit": False,
        "release_authorized": False,
        "next_stage_authorized": False,
        "claim_boundary": "BACKEND_P1_CLOSED_IN_SOURCE_ONLY_FORM_NO_ACTUAL_RAW_OR_EXECUTION_CREDIT",
    })


def freeze_sources() -> dict[str, Any]:
    for path in (TERMINAL, GATE):
        if path.exists():
            if path.is_symlink() or not path.is_file():
                raise PublicationError("OLD_GATE_OR_TERMINAL_NOT_REGULAR_FILE")
            path.unlink()
    manifest = _manifest()
    _write(MANIFEST, manifest)
    negative_result = run_negative_controls(HERE)
    negative = seal({
        "schema": "SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_NEGATIVE_CONTROLS_EVIDENCE_V1",
        "status": "PASS_14_OF_14_KILLED" if negative_result["passed"] else "FAIL_NEGATIVE_CONTROLS",
        "source_inventory_sha256": manifest["source_inventory_sha256"],
        "result": negative_result,
        "trajectory_count": 0,
        "execution_credit": False,
    })
    _write(NEGATIVE, negative)
    validation = validate_source_freeze(write_output=True)
    if validation["source_freeze_pass_eligible"] is not True:
        raise PublicationError(f"VALIDATION_FAILED:{validation['score']['failed']}")
    independent = audit(write_output=True)
    if independent["independent_source_freeze_pass_eligible"] is not True:
        raise PublicationError(f"AUDIT_FAILED:{independent['score']['failed']}")
    if source_inventory(HERE) != manifest["sources"]:
        raise PublicationError("SOURCE_CHANGED_DURING_PUBLICATION")
    gate = _gate(manifest, negative, validation, independent)
    _write(GATE, gate)
    if not all(record_valid(record) for record in gate["evidence"]):
        raise PublicationError("GATE_RECORD_SELF_CHECK_FAILED")
    terminal = seal({
        "schema": "SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_SOURCE_FREEZE_TERMINAL_V1",
        "status": gate["status"],
        "scope": "SELF_EXCLUDED_TERMINAL_FOR_FULL_RAW_INTEGRITY_BACKEND_SOURCE_FREEZE",
        "self_excluded": True,
        "acyclic": True,
        "terminal_generated_last": True,
        "records": [project_record(GATE, "full_integrity_source_freeze_gate", "SOURCE_FREEZE_GATE")],
        "source_inventory_sha256": gate["source_inventory_sha256"],
        "source_count": gate["source_count"],
        "technical_fixture_full_gate_set_recomputed": True,
        "technical_fixture_all_gate_predicates_true": True,
        "required_false": REQUIRED_FALSE,
        "actual_raw_case_count": 0,
        "trajectory_count": 0,
        "full_raw_integrity_recomputed": False,
        "actual_case_full_raw_integrity_recomputed": False,
        "r2_numerical_preflight_executed": False,
        "current_system_bound": False,
        "formal_nc19_credit": False,
        "scientific_credit": False,
        "owner_authorized": False,
        "production_credit": False,
        "release_authorized": False,
        "next_stage_authorized": False,
        "claim_boundary": gate["claim_boundary"],
    })
    _write(TERMINAL, terminal)
    reloaded = strict_load(TERMINAL)
    if (
        reloaded != terminal or not seal_valid(reloaded)
        or not record_valid(reloaded["records"][0])
        or source_inventory(HERE) != manifest["sources"]
    ):
        raise PublicationError("TERMINAL_FINAL_SELF_CHECK_FAILED")
    return {
        "schema": "SIM13_V4B4G_R2_FULL_RAW_INTEGRITY_SOURCE_FREEZE_PUBLICATION_RECEIPT_V1",
        "status": gate["status"],
        "source_freeze_pass": True,
        "source_manifest_sha256": file_sha256(MANIFEST),
        "gate_sha256": file_sha256(GATE),
        "terminal_sha256": file_sha256(TERMINAL),
        "trajectory_count": 0,
        "actual_case_full_raw_integrity_recomputed": False,
        "next_stage_authorized": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--write-receipts", action="store_true")
    args = parser.parse_args(argv)
    if not args.write_receipts:
        print(json.dumps({
            "status": "HOLD_EXPLICIT_WRITE_RECEIPTS_FLAG_REQUIRED",
            "write_performed": False,
            "trajectory_count": 0,
            "next_stage_authorized": False,
        }, sort_keys=True))
        return 2
    try:
        result = freeze_sources()
    except Exception as exc:
        print(json.dumps({"status": "FAIL_SOURCE_FREEZE_EXCEPTION", "error": f"{type(exc).__name__}:{exc}"}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
