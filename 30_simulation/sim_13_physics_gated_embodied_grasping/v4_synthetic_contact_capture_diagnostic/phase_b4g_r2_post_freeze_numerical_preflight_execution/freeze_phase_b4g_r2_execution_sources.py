"""Publish the acyclic B4G-R2 execution-tooling source freeze.

Only source bytes, contracts, source-only mutation evidence, validation, and an
independent audit are frozen.  This entrypoint never imports a historical
numerical module and never starts a trajectory, physics case, or campaign.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from independent_audit_phase_b4g_r2_execution_source_freeze import audit
from r2_preflight.negative_controls import build_negative_control_evidence
from r2_preflight.rehydrator import load_donor_fixture
from r2_preflight.strict_json import atomic_write_json, canonical_sha256, file_sha256, load_path
from validate_phase_b4g_r2_execution_source_freeze import (
    local_source_inventory,
    negative_control_evidence_check,
    validate_source_freeze,
)


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[3]
MANIFEST = HERE / "evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_MANIFEST_V1.json"
VALIDATION = HERE / "evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_VALIDATION_V1.json"
AUDIT = HERE / "evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_INDEPENDENT_AUDIT_V1.json"
NC_EVIDENCE = HERE / "evidence/SIM13_V4B4G_R2_SOURCE_ONLY_NEGATIVE_CONTROLS_V1.json"
GATE = HERE / "results/SIM13_V4B4G_R2_EXECUTION_TOOLING_SOURCE_FREEZE_GATE_V1.json"
TERMINAL = HERE / "results/SIM13_V4B4G_R2_EXECUTION_SOURCE_FREEZE_TERMINAL_V1.json"
FREEZE_CONTRACT = HERE / "contracts/PHASE_B4G_R2_EXECUTION_TOOLING_FREEZE_CONTRACT_V1.json"
GOVERNANCE = HERE / "contracts/PHASE_B4G_R2_EXECUTION_GOVERNANCE_V1.json"
NC_CONTRACT = HERE / "contracts/PHASE_B4G_R2_SOURCE_ONLY_NEGATIVE_CONTROL_EVIDENCE_CONTRACT_V1.json"


class SourceFreezePublicationError(RuntimeError):
    pass


def _project_record(path: Path, identifier: str, role: str) -> dict[str, Any]:
    resolved = path.resolve()
    return {
        "id": identifier,
        "role": role,
        "path": resolved.relative_to(PROJECT_ROOT.resolve()).as_posix(),
        "bytes": resolved.stat().st_size,
        "sha256": file_sha256(resolved),
    }


def build_source_manifest(package_root: Path = HERE) -> dict[str, Any]:
    inventory = local_source_inventory(package_root)
    paths = [row["path"] for row in inventory]
    if any(path.startswith("evidence/") or path.startswith("results/") for path in paths):
        raise SourceFreezePublicationError("OUTPUT_PATH_PRESENT_IN_SOURCE_MANIFEST")
    return {
        "schema": "SIM13_V4B4G_R2_EXECUTION_SOURCE_MANIFEST_V1",
        "scope": "LOCAL_SOURCE_AND_CONTRACT_BYTES_ONLY_NO_EXECUTION",
        "self_excluded": True,
        "acyclic": True,
        "terminal_excluded": True,
        "excluded_path_prefixes": ["evidence/", "results/"],
        "terminal_exclusion_rule": "TERMINAL_GENERATED_LAST_AND_RECORDS_GATE_ONLY",
        "source_count": len(inventory),
        "sources": inventory,
        "source_inventory_sha256": canonical_sha256(inventory),
        "r2_numerical_preflight_executed": False,
        "trajectory_count": 0,
    }


def _safe_known_output(path: Path) -> Path:
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(HERE.resolve())
    except ValueError as exc:
        raise SourceFreezePublicationError("PUBLICATION_PATH_ESCAPES_PACKAGE") from exc
    if relative.as_posix() not in {
        "evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_MANIFEST_V1.json",
        "evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_VALIDATION_V1.json",
        "evidence/SIM13_V4B4G_R2_EXECUTION_SOURCE_INDEPENDENT_AUDIT_V1.json",
        "evidence/SIM13_V4B4G_R2_SOURCE_ONLY_NEGATIVE_CONTROLS_V1.json",
        "results/SIM13_V4B4G_R2_EXECUTION_TOOLING_SOURCE_FREEZE_GATE_V1.json",
        "results/SIM13_V4B4G_R2_EXECUTION_SOURCE_FREEZE_TERMINAL_V1.json",
    }:
        raise SourceFreezePublicationError("UNREGISTERED_PUBLICATION_PATH")
    return resolved


def _invalidate_old_chain() -> None:
    # Consumer-to-source order prevents a stale terminal from surviving a
    # partially refreshed chain.  Targets are exact, package-local filenames.
    for path in (TERMINAL, GATE, AUDIT, VALIDATION, NC_EVIDENCE, MANIFEST):
        target = _safe_known_output(path)
        if target.exists():
            if target.is_symlink() or not target.is_file():
                raise SourceFreezePublicationError(f"PUBLICATION_TARGET_NOT_PLAIN_FILE:{target}")
            target.unlink()


def _is_nc_only_partial(validation: dict[str, Any], independent: dict[str, Any]) -> bool:
    validator_failed = set(validation.get("score", {}).get("failed", []))
    audit_failed = set(independent.get("score", {}).get("failed", []))
    validator_allowed = {
        "R2SV09_SOURCE_ONLY_NEGATIVE_CONTROLS_EXACT_46",
        "R2SV10_LOCAL_JSON_STRICT_NO_NULL",
    }
    audit_allowed = {
        "R2SA09_SOURCE_ONLY_NEGATIVE_CONTROLS_EXACT_46",
        "R2SA10_VALIDATOR_RECEIPT_CONSISTENT_WITH_INDEPENDENT_RESULT",
        "R2SA11_LOCAL_JSON_STRICT_NO_NULL",
    }
    if not (
        "R2SV09_SOURCE_ONLY_NEGATIVE_CONTROLS_EXACT_46" in validator_failed
        and "R2SA09_SOURCE_ONLY_NEGATIVE_CONTROLS_EXACT_46" in audit_failed
        and "R2SA10_VALIDATOR_RECEIPT_CONSISTENT_WITH_INDEPENDENT_RESULT" in audit_failed
        and validator_failed <= validator_allowed
        and audit_failed <= audit_allowed
    ):
        return False

    nc_relative = NC_EVIDENCE.relative_to(HERE).as_posix()
    for result, check_id in (
        (validation, "R2SV10_LOCAL_JSON_STRICT_NO_NULL"),
        (independent, "R2SA11_LOCAL_JSON_STRICT_NO_NULL"),
    ):
        rows = [row for row in result.get("checks", []) if row.get("id") == check_id]
        if rows and rows[0].get("pass") is False:
            if rows[0].get("detail", {}).get("failures") != [nc_relative]:
                return False
    return True


def _source_only_nc_summary(nc_check: dict[str, Any]) -> dict[str, Any]:
    if nc_check.get("passed") is not True:
        return {
            "status": "MISSING_OR_INVALID_FAIL_CLOSED",
            "registered_count": 46,
            "implemented_count": 0,
            "source_only_executed_count": 0,
            "killed_count": 0,
            "source_only_negative_controls_implemented": False,
            "source_only_negative_controls_executed": False,
            "source_only_negative_controls_killed": False,
            "r2_execution_negative_controls_executed": False,
            "r2_runtime_trajectory_evaluated": False,
        }
    value = load_path(NC_EVIDENCE)
    return {
        "status": "PASS_EXACT_46_SOURCE_ONLY_MUTATIONS_KILLED",
        "registered_count": value["registered_count"],
        "implemented_count": value["implemented_count"],
        "source_only_executed_count": value["source_only_executed_count"],
        "killed_count": value["killed_count"],
        "source_only_negative_controls_implemented": value["source_only_negative_controls_implemented"],
        "source_only_negative_controls_executed": value["source_only_negative_controls_executed"],
        "source_only_negative_controls_killed": value["source_only_negative_controls_killed"],
        "r2_execution_negative_controls_executed": value["r2_execution_negative_controls_executed"],
        "r2_runtime_trajectory_evaluated": value["r2_runtime_trajectory_evaluated"],
    }


def _optional_file_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "bytes": 0, "sha256": "MISSING"}
    if path.is_symlink() or not path.is_file():
        raise SourceFreezePublicationError(f"SNAPSHOT_TARGET_NOT_PLAIN_FILE:{path}")
    return {"exists": True, "bytes": path.stat().st_size, "sha256": file_sha256(path)}


def _record_still_matches(record: dict[str, Any]) -> bool:
    path = PROJECT_ROOT / record["path"]
    return bool(
        path.is_file()
        and not path.is_symlink()
        and path.stat().st_size == record["bytes"]
        and file_sha256(path) == record["sha256"]
    )


def _require_final_stability(
    *,
    manifest: dict[str, Any],
    validation: dict[str, Any],
    independent: dict[str, Any],
    nc_snapshot: dict[str, Any],
    bound_records: list[dict[str, Any]],
) -> None:
    current_inventory = local_source_inventory(HERE)
    if current_inventory != manifest["sources"] or canonical_sha256(current_inventory) != manifest["source_inventory_sha256"]:
        raise SourceFreezePublicationError("LOCAL_SOURCE_CHANGED_AFTER_AUDIT")
    if _optional_file_snapshot(NC_EVIDENCE) != nc_snapshot:
        raise SourceFreezePublicationError("NEGATIVE_CONTROL_EVIDENCE_CHANGED_AFTER_AUDIT")
    if not all(_record_still_matches(record) for record in bound_records):
        raise SourceFreezePublicationError("BOUND_EVIDENCE_CHANGED_AFTER_AUDIT")
    final_validation = validate_source_freeze(
        project_root=PROJECT_ROOT,
        package_root=HERE,
        manifest_path=MANIFEST,
        negative_control_evidence_path=NC_EVIDENCE,
        output_path=VALIDATION,
        write_output=False,
    )
    if final_validation != validation:
        raise SourceFreezePublicationError("SOURCE_OR_EXTERNAL_BINDING_CHANGED_AFTER_AUDIT")
    final_independent = audit(write_output=False, output_path=AUDIT)
    if final_independent != independent:
        raise SourceFreezePublicationError("INDEPENDENT_AUDIT_REPLAY_CHANGED_AFTER_PUBLICATION")


def freeze_execution_sources() -> dict[str, Any]:
    """Write manifest -> validation -> audit -> Gate -> terminal, then verify."""

    if HERE.resolve() != Path(__file__).resolve().parent:
        raise SourceFreezePublicationError("PACKAGE_ROOT_IDENTITY_DRIFT")
    _invalidate_old_chain()
    manifest = build_source_manifest(HERE)
    atomic_write_json(MANIFEST, manifest)
    source_bindings = load_path(HERE / "contracts/PHASE_B4G_R2_EXECUTION_SOURCE_BINDINGS_V1.json")
    donor_rows = [row for row in source_bindings["sources"] if row["id"] == "common_prop_donor_raw_slot_052"]
    if len(donor_rows) != 1:
        raise SourceFreezePublicationError("DONOR_SOURCE_ID_CARDINALITY")
    donor = load_donor_fixture(PROJECT_ROOT / donor_rows[0]["path"])
    generated_nc_evidence = build_negative_control_evidence(
        project_root=PROJECT_ROOT,
        package_root=HERE,
        donor=donor,
        source_inventory_sha256=manifest["source_inventory_sha256"],
    )
    atomic_write_json(NC_EVIDENCE, generated_nc_evidence)
    validation = validate_source_freeze(
        project_root=PROJECT_ROOT,
        package_root=HERE,
        manifest_path=MANIFEST,
        negative_control_evidence_path=NC_EVIDENCE,
        output_path=VALIDATION,
        write_output=True,
    )
    independent = audit(write_output=True, output_path=AUDIT)
    nc_check = negative_control_evidence_check(NC_EVIDENCE, NC_CONTRACT)
    nc_snapshot = _optional_file_snapshot(NC_EVIDENCE)
    freeze_contract = load_path(FREEZE_CONTRACT)
    governance = load_path(GOVERNANCE)
    statuses = freeze_contract["exact_statuses"]
    pass_eligible = bool(
        validation.get("source_freeze_pass_eligible") is True
        and independent.get("independent_source_freeze_pass_eligible") is True
        and nc_check.get("passed") is True
    )
    if pass_eligible:
        status = statuses["pass"]
    elif _is_nc_only_partial(validation, independent):
        status = statuses["partial"]
    else:
        status = statuses["failure"]
    nc_summary = _source_only_nc_summary(nc_check)
    evidence = [
        _project_record(MANIFEST, "r2_execution_source_manifest", "SELF_EXCLUDED_LOCAL_SOURCE_MANIFEST"),
        _project_record(VALIDATION, "r2_execution_source_validation", "SOURCE_VALIDATOR_RECEIPT"),
        _project_record(AUDIT, "r2_execution_source_independent_audit", "INDEPENDENT_SOURCE_AUDIT_RECEIPT"),
    ]
    if nc_check.get("passed") is True:
        evidence.append(_project_record(NC_EVIDENCE, "r2_source_only_negative_controls", "EXACT_46_SOURCE_ONLY_MUTATION_EVIDENCE"))
    _require_final_stability(
        manifest=manifest,
        validation=validation,
        independent=independent,
        nc_snapshot=nc_snapshot,
        bound_records=evidence,
    )
    gate = {
        "schema": "SIM13_V4B4G_R2_EXECUTION_TOOLING_SOURCE_FREEZE_GATE_V1",
        "status": status,
        "scope": "EXECUTION_TOOLING_SOURCE_FREEZE_ONLY_NOT_NUMERICAL_OR_SCIENTIFIC_PASS",
        "tooling_source_freeze_pass": pass_eligible,
        "source_inventory_sha256": manifest["source_inventory_sha256"],
        "source_count": manifest["source_count"],
        "matrix_case_count": 78,
        "fresh_case_count": 60,
        "common_prop_case_count": 18,
        "source_only_negative_controls": nc_summary,
        "validation_status": validation["status"],
        "independent_audit_status": independent["status"],
        "evidence": evidence,
        "required_false": governance["required_false"],
        "required_zero": governance["required_zero"],
        "execution_readiness_status": statuses["execution_readiness"],
        "authorized_execution_path_status": statuses["authorized_execution_path_status"],
        "r2_numerical_preflight_executed": False,
        "r2_execution_negative_controls_executed": False,
        "full_campaign_executed": False,
        "full_campaign_authorized": False,
        "gate_implies_scientific_pass": False,
        "trajectory_count": 0,
    }
    atomic_write_json(GATE, gate)
    gate_record = _project_record(GATE, "r2_execution_tooling_source_freeze_gate", "SOURCE_FREEZE_GATE")
    _require_final_stability(
        manifest=manifest,
        validation=validation,
        independent=independent,
        nc_snapshot=nc_snapshot,
        bound_records=evidence + [gate_record],
    )
    terminal = {
        "schema": "SIM13_V4B4G_R2_EXECUTION_SOURCE_FREEZE_TERMINAL_V1",
        "status": status,
        "scope": "SELF_EXCLUDED_TERMINAL_FOR_SOURCE_ONLY_TOOLING_FREEZE",
        "self_excluded": True,
        "acyclic": True,
        "terminal_generated_last": True,
        "terminal_excluded_from_source_manifest": True,
        "records": [gate_record],
        "tooling_source_freeze_pass": pass_eligible,
        "source_inventory_sha256": manifest["source_inventory_sha256"],
        "source_count": manifest["source_count"],
        "source_only_negative_controls": nc_summary,
        "validation_status": validation["status"],
        "independent_audit_status": independent["status"],
        "required_false": governance["required_false"],
        "required_zero": governance["required_zero"],
        "execution_readiness_status": statuses["execution_readiness"],
        "authorized_execution_path_status": statuses["authorized_execution_path_status"],
        "r2_numerical_preflight_executed": False,
        "r2_execution_negative_controls_executed": False,
        "full_campaign_executed": False,
        "full_campaign_authorized": False,
        "owner_authorized": False,
        "production_ready": False,
        "release_ready": False,
        "next_stage_authorized": False,
        "trajectory_count": 0,
    }
    atomic_write_json(TERMINAL, terminal)
    reloaded = load_path(TERMINAL)
    if reloaded != terminal or file_sha256(GATE) != reloaded["records"][0]["sha256"]:
        raise SourceFreezePublicationError("TERMINAL_SELF_VERIFICATION_FAILED")
    if any(row["path"].startswith("evidence/") or row["path"].startswith("results/") for row in load_path(MANIFEST)["sources"]):
        raise SourceFreezePublicationError("TERMINAL_OR_OUTPUT_ENTERED_SOURCE_MANIFEST")
    _require_final_stability(
        manifest=manifest,
        validation=validation,
        independent=independent,
        nc_snapshot=nc_snapshot,
        bound_records=evidence + [gate_record],
    )
    return {
        "schema": "SIM13_V4B4G_R2_EXECUTION_TOOLING_SOURCE_FREEZE_RECEIPT_V1",
        "status": status,
        "source_freeze_pass": pass_eligible,
        "manifest": _project_record(MANIFEST, "r2_execution_source_manifest", "SELF_EXCLUDED_LOCAL_SOURCE_MANIFEST"),
        "gate": _project_record(GATE, "r2_execution_tooling_source_freeze_gate", "SOURCE_FREEZE_GATE"),
        "terminal": _project_record(TERMINAL, "r2_execution_source_freeze_terminal", "SELF_EXCLUDED_TERMINAL"),
        "r2_numerical_preflight_executed": False,
        "trajectory_count": 0,
        "authorized_execution_path_status": statuses["authorized_execution_path_status"],
    }


def main() -> int:
    try:
        receipt = freeze_execution_sources()
    except Exception as exc:
        print(json.dumps({"status": "FAIL_R2_EXECUTION_SOURCE_FREEZE_EXCEPTION", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0 if receipt["source_freeze_pass"] is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
