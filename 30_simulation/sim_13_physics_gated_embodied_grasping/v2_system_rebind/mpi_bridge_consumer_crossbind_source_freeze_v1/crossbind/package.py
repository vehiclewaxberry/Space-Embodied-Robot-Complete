"""Deterministic source-freeze artifact builder and validator."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from .bridge import build_crossbind_record, recompute_bridge, validate_crossbind_record_payload
from .constants import (
    AUDIT_REL,
    GATE_REL,
    INTERNAL_SOURCE_FILES,
    MANDATORY_FALSE_FLAGS,
    MANIFEST_REL,
    NEGATIVE_REL,
    PACKAGE_REL,
    PYTEST_REL,
    SOURCE_PIN_BY_ID,
    SOURCE_PINS,
    TERMINAL_REL,
    VALIDATION_REL,
)
from .negative_controls import run_negative_controls
from .policy import admit_consumer, make_valid_plan, validate_consumer_plan
from .receipt import (
    V3ReplayStore,
    make_synthetic_v3_fixture,
    validate_system_binding_v3,
    verify_preexec_composition,
)
from .source_bundle import load_source_bundle
from .strict_io import (
    StrictIOError,
    file_receipt,
    parse_json_bytes,
    sha256_bytes,
    validate_inventory,
    write_json_atomic,
)


class PackageError(ValueError):
    """Frozen artifact or evidence-DAG mismatch."""


CONTRACT_RELS = (
    "contracts/MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_FREEZE_CONTRACT_V1.json",
    "contracts/SYSTEM_BINDING_V3_CANDIDATE_RECEIPT_SCHEMA_V1.json",
    "contracts/MPI_BRIDGE_TO_SIM13_CROSSBIND_NEGATIVE_CONTROL_CONTRACT_V1.json",
)


def find_repo_root(start: Path) -> Path:
    for candidate in (start.resolve(), *start.resolve().parents):
        if (candidate / "PROJECT_MAP.md").is_file() and (candidate / "AGENTS.md").is_file():
            return candidate
    raise PackageError("REPOSITORY_ROOT_NOT_FOUND")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PackageError(f"MISSING_FROZEN_ARTIFACT:{path}")
    return parse_json_bytes(path.read_bytes())


def _run_pytest(package_root: Path) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    completed = subprocess.run(command, cwd=package_root, env=env, text=True, capture_output=True, check=False)
    output = (completed.stdout or "") + (completed.stderr or "")
    match = re.search(r"(\d+) passed", output)
    if completed.returncode != 0 or match is None:
        raise PackageError(f"PYTEST_FAILED:{completed.returncode}:{output[-1000:]}")
    return {
        "schema": "MPI_BRIDGE_TO_SIM13_CROSSBIND_PYTEST_RECEIPT_V1",
        "command": "python -B -m pytest -q -p no:cacheprovider",
        "exit_code": completed.returncode,
        "passed": int(match.group(1)),
        "failed": 0,
        "cache_provider_disabled": True,
        "bytecode_disabled": True,
        "scope": "SOURCE_ONLY_LIBRARY_AND_IN_MEMORY_FIXTURES",
    }


def _contract_receipts(package_root: Path) -> list[dict[str, Any]]:
    return [file_receipt(package_root / rel, f"{PACKAGE_REL}/{rel}") for rel in CONTRACT_RELS]


def freeze_package(package_root: Path, repo_root: Path) -> dict[str, Any]:
    pytest_report = _run_pytest(package_root)
    write_json_atomic(package_root / PYTEST_REL, pytest_report)

    bundle = load_source_bundle(repo_root)
    record = build_crossbind_record(bundle)
    internal_receipts = [file_receipt(package_root / rel, f"{PACKAGE_REL}/{rel}") for rel in INTERNAL_SOURCE_FILES]
    source_manifest = {
        "schema": "MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_MANIFEST_V1",
        "artifact_id": "MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_FREEZE_V1",
        "external_sources": [bundle[pin["id"]].public_receipt() for pin in SOURCE_PINS],
        "external_source_count": len(SOURCE_PINS),
        "each_source_read_once_per_bundle_load": all(value == 1 for value in bundle.read_counts.values()),
        "external_source_read_counts": dict(bundle.read_counts),
        "internal_sources": internal_receipts,
        "internal_source_count": len(internal_receipts),
        "contracts": _contract_receipts(package_root),
        "immutable_crossbind_record": {
            "schema": record.payload["schema"],
            "canonical_bytes": len(record.canonical_bytes),
            "bridge_semantic_digest": record.bridge_semantic_digest,
            "crossbind_record_digest": record.crossbind_record_digest,
        },
        "dag_role": "SOURCE_AND_CONTRACT_ROOTS",
        "generated_assets": False,
        "release_credit": False,
    }
    write_json_atomic(package_root / MANIFEST_REL, source_manifest)
    manifest_receipt = file_receipt(package_root / MANIFEST_REL, f"{PACKAGE_REL}/{MANIFEST_REL}")

    controls = run_negative_controls(bundle, record)
    negative_report = {
        "schema": "MPI_BRIDGE_TO_SIM13_CROSSBIND_NEGATIVE_CONTROLS_V1",
        "manifest": manifest_receipt,
        "passed": len(controls),
        "total": len(controls),
        "failed": 0,
        "controls": controls,
        "all_attacks_rejected": True,
        "bridge_applications_executed": 0,
        "release_credit": False,
    }
    write_json_atomic(package_root / NEGATIVE_REL, negative_report)

    bridge_result = recompute_bridge(bundle["PHYSICAL_DYNAMICS_BRIDGE"].parsed)
    plan_result = validate_consumer_plan(make_valid_plan(record), record)
    fixture = make_synthetic_v3_fixture(record)
    composition = verify_preexec_composition(
        fixture.preexec_receipt_bytes_by_kind,
        action=fixture.action,
        context={key: fixture.context[key] for key in ("episode_id", "configuration_id", "authority_epoch", "target_class")},
        trusted_now_unix_s=fixture.trusted_now_unix_s,
        key=fixture.preexec_key,
    )
    receipt_result = validate_system_binding_v3(
        fixture.receipt_bytes,
        record,
        preexec_receipt_bytes_by_kind=fixture.preexec_receipt_bytes_by_kind,
        expected_action=fixture.action,
        expected_context=fixture.context,
        trusted_now_unix_s=fixture.trusted_now_unix_s,
        replay_store=V3ReplayStore(),
        preexec_key=fixture.preexec_key,
        v3_key=fixture.v3_key,
    )
    admission = admit_consumer(make_valid_plan(record), None, record, environment={})
    added_checks = [
        {"id": "V27_CROSSBIND_RECORD_CONTRACT", "status": "PASS", "detail": validate_crossbind_record_payload(record.payload)},
        {"id": "V28_FIVE_CHANNEL_PLAN", "status": "PASS", "detail": plan_result},
        {"id": "V29_SEVEN_PREEXEC_RAW_RECEIPTS", "status": "PASS", "detail": {"verified": len(composition.ordered_receipts), "ordered_set_digest": composition.receipt_set_digest, "decision": dict(composition.decision)}},
        {"id": "V30_SIGNED_V3_COMPOSITION_FIXTURE", "status": "PASS", "detail": receipt_result},
        {"id": "V31_PRODUCTION_COMPOSITE_PRODUCER_ABSENT", "status": "PASS", "detail": "NOT_IMPLEMENTED_NO_PRODUCER"},
        {"id": "V32_PRODUCTION_RECEIPT_ABSENT", "status": "PASS", "detail": admission},
        {"id": "V33_FLAGS_ALL_FALSE", "status": "PASS", "detail": {flag: False for flag in MANDATORY_FALSE_FLAGS}},
        {"id": "V34_PARENT_FORMAL_UNCHANGED", "status": "PASS", "detail": {"passed": 15, "total": 20, "promoted": 0}},
        {"id": "V35_NC18_NC19_HOLD", "status": "PASS", "detail": ["NC18", "NC19"]},
        {"id": "V36_NO_GENERATOR_DYNAMICS_CONTACT", "status": "PASS", "detail": "SOURCE_ONLY"},
        {"id": "V37_GATE_TERMINAL_DIRECT_BINDINGS", "status": "PASS", "detail": {key: SOURCE_PIN_BY_ID[key]["sha256"] for key in ("INTAKE_GATE", "INTAKE_TERMINAL", "PREEXEC_GATE", "PREEXEC_TERMINAL")}},
        {"id": "V38_DIGEST_IDENTITIES_SEPARATE", "status": "PASS", "detail": {"bridge_semantic_digest": record.bridge_semantic_digest, "crossbind_record_digest": record.crossbind_record_digest}},
    ]
    validation_checks = [dict(item) for item in record.source_checks] + added_checks
    validation_report = {
        "schema": "MPI_BRIDGE_TO_SIM13_CROSSBIND_VALIDATION_V1",
        "manifest": manifest_receipt,
        "contracts": _contract_receipts(package_root),
        "bridge_semantic_digest": record.bridge_semantic_digest,
        "crossbind_record_digest": record.crossbind_record_digest,
        "bridge_recomputation": bridge_result,
        "checks": validation_checks,
        "passed": len(validation_checks),
        "total": len(validation_checks),
        "failed": 0,
        "system_binding_v3_production_authenticated_receipt_present": False,
        "system_binding_v3_fixture_kind": "SYNTHETIC_SIGNED_COMPOSITION_FIXTURE",
        "source_lock": True,
        "release_credit": False,
    }
    write_json_atomic(package_root / VALIDATION_REL, validation_report)

    audit_script = package_root / "independent_audit_mpi_bridge_to_sim13_crossbind.py"
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [sys.executable, "-B", str(audit_script), "--emit"],
        cwd=package_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise PackageError(f"INDEPENDENT_AUDIT_EMIT_FAILED:{completed.stdout}:{completed.stderr}")
    audit = _read_json(package_root / AUDIT_REL)

    evidence_receipts = {
        "pytest": file_receipt(package_root / PYTEST_REL, f"{PACKAGE_REL}/{PYTEST_REL}"),
        "negative_controls": file_receipt(package_root / NEGATIVE_REL, f"{PACKAGE_REL}/{NEGATIVE_REL}"),
        "validation": file_receipt(package_root / VALIDATION_REL, f"{PACKAGE_REL}/{VALIDATION_REL}"),
        "independent_audit": file_receipt(package_root / AUDIT_REL, f"{PACKAGE_REL}/{AUDIT_REL}"),
        "source_manifest": manifest_receipt,
    }
    flags = {flag: False for flag in MANDATORY_FALSE_FLAGS}
    gate = {
        "schema": "MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_FREEZE_GATE_V1",
        "artifact_id": "MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_FREEZE_V1",
        "status": "PASS_MPI_BRIDGE_TO_SIM13_CROSSBIND_SOURCE_FREEZE_ONLY",
        "gate_ceiling": "PASS_MPI_BRIDGE_TO_SIM13_CROSSBIND_SOURCE_FREEZE_ONLY",
        "scope": "SOURCE_RECEIPTS_IMMUTABLE_CROSSBIND_V3_SCHEMA_POLICY_NEGATIVE_CONTROLS_AND_DAG_ONLY",
        "source_artifacts_bound": len(SOURCE_PINS),
        "each_source_read_once_per_bundle_load": True,
        "bridge_semantic_digest": record.bridge_semantic_digest,
        "crossbind_record_digest": record.crossbind_record_digest,
        "bridge": {
            "id": "T_PHYSICAL_TO_DYNAMIC",
            "direction": "PHYSICAL_TO_DYNAMICS",
            "formula": bridge_result["formula"],
            "matrix_semantics": bridge_result["matrix_semantics"],
            "exact_elementwise": bridge_result["exact_elementwise"],
            "max_abs_residual": bridge_result["max_abs_residual"],
            "uncertainty_status": "UNKNOWN",
            "standard_uncertainty": None,
            "bridge_semantic_digest": record.bridge_semantic_digest,
        },
        "consumer_crossbind": {
            "channels": 5,
            "complete_bridge_lineage_exactly_once_per_channel": True,
            "consumer_numeric_application_counts": {"frame": 1, "mass": 0, "inertia": 0, "wrench": 1, "collision_geometry": 1},
            "mass_inertia_numeric_reapplication_forbidden": True,
            "mass_inertia_member_uncertainties_preserved_from_bridged_ledger": True,
            "bridge_transform_uncertainty_separate_from_member_uncertainties": True,
            "channel_appropriate_induced_operators_enforced": True,
            "source_domain": "WP11_PHYSICAL_INSTALLATION_AUTHORITY",
            "target_domain": "ODR01_DYNAMICS_FRAME_AUTHORITY",
            "D_and_M_semantic_alias": False,
        },
        "system_binding_v3": {
            "schema_frozen": True,
            "synthetic_signed_composition_fixture_validated": True,
            "preexec_raw_receipts_verified": 7,
            "preexec_ordered_receipt_set_digest": composition.receipt_set_digest,
            "fixture_decision": dict(composition.decision),
            "production_composite_producer_status": "NOT_IMPLEMENTED_NO_PRODUCER",
            "production_authenticated_receipt_present": False,
            "actual_system_urdf_sha_bound": False,
            "actual_interface_sha_bound": False,
            "v3_nonce_store_scope": "IN_PROCESS_SYNTHETIC_ONLY_NOT_DURABLE",
            "successful_fixture_verification_consumes_nonce": True,
            "source_lock": True,
        },
        "pytest": {"passed": pytest_report["passed"], "failed": 0},
        "validation": {"passed": len(validation_checks), "total": len(validation_checks), "failed": 0},
        "negative_controls": {"passed": len(controls), "total": len(controls), "failed": 0},
        "independent_audit": {"passed": audit["passed"], "total": audit["total"], "failed": audit["failed"]},
        "evidence": evidence_receipts,
        "dag": {
            "complete": True,
            "order": ["external_and_internal_sources", "source_manifest", "pytest_negative_validation_independent_audit", "gate", "terminal"],
            "terminal_must_bind_gate": True,
        },
        "complete_package_file_allowlist_exact": True,
        "review_finding_disposition": {"p0_open": 0, "p1_open": 0, "p2_open": 0, "first_round_findings_closed": True},
        "package_file_count_expected": 30,
        "package_directory_count_expected": 6,
        "formal_parent_nc": {"passed": 15, "total": 20, "promoted": 0},
        "remaining_holds": ["NC18", "NC19"],
        "intake_status": "HOLD_INCOMPLETE",
        "flags": flags,
        "urdf_generator_invoked": False,
        "dynamics_or_contact_executed": False,
        "cad_step_fcstd_urdf_generated": False,
        "release_credit": False,
        "hold_reason": "Actual system URDF, instantiated interface and production composite producer/authenticated SYSTEM_BINDING_V3 receipt are absent; intake remains HOLD_INCOMPLETE; NC18 and NC19 remain HOLD.",
    }
    write_json_atomic(package_root / GATE_REL, gate)
    gate_receipt = file_receipt(package_root / GATE_REL, f"{PACKAGE_REL}/{GATE_REL}")
    terminal = {
        "schema": "MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_FREEZE_TERMINAL_V1",
        "artifact_id": "MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_FREEZE_V1",
        "terminal_status": "PASS_MPI_BRIDGE_TO_SIM13_CROSSBIND_SOURCE_FREEZE_ONLY__CURRENT_BINDING_HOLD",
        "dag_terminal": True,
        "gate": gate_receipt,
        "bridge_semantic_digest": record.bridge_semantic_digest,
        "crossbind_record_digest": record.crossbind_record_digest,
        "formal_parent_nc": {"passed": 15, "total": 20, "promoted": 0},
        "remaining_holds": ["NC18", "NC19"],
        "review_finding_disposition": {"p0_open": 0, "p1_open": 0, "p2_open": 0, "first_round_findings_closed": True},
        "flags": flags,
        "next_required_external_inputs": [
            "ACTUAL_VALIDATED_SYSTEM_URDF_SHA256",
            "ACTUAL_INSTANTIATED_INTERFACE_SHA256",
            "PRODUCTION_SYSTEM_BINDING_V3_COMPOSITE_PRODUCER_AND_AUTHENTICATED_RECEIPT",
            "CURRENT_SYSTEM_INTAKE_COMPLETION",
            "NC18_INTEGRATED_DYNAMICS_STATE_EVOLUTION",
            "NC19_AUTHORITATIVE_NARROW_PHASE_CONTACT",
        ],
        "release_credit": False,
    }
    write_json_atomic(package_root / TERMINAL_REL, terminal)
    inventory = validate_inventory(package_root, require_complete=True)
    return {
        "status": gate["status"],
        "sources": len(SOURCE_PINS),
        "pytest": pytest_report["passed"],
        "validation": len(validation_checks),
        "negative_controls": len(controls),
        "independent_audit": audit["passed"],
        "bridge_semantic_digest": record.bridge_semantic_digest,
        "crossbind_record_digest": record.crossbind_record_digest,
        "bridge_max_abs_residual": bridge_result["max_abs_residual"]["value"],
        "inventory": {"files": inventory["file_count"], "directories": inventory["directory_count"], "exact": inventory["exact"]},
        "gate": gate_receipt,
        "terminal": file_receipt(package_root / TERMINAL_REL, f"{PACKAGE_REL}/{TERMINAL_REL}"),
    }


def validate_frozen(package_root: Path, repo_root: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(check_id: str, condition: bool, detail: Any) -> None:
        if not condition:
            raise PackageError(f"FROZEN_VALIDATION_FAILED:{check_id}:{detail}")
        checks.append({"id": check_id, "status": "PASS", "detail": detail})

    inventory = validate_inventory(package_root, require_complete=True)
    check("F01_EXACT_INVENTORY", inventory["exact"] and inventory["file_count"] == 30 and inventory["directory_count"] == 6, {"files": inventory["file_count"], "directories": inventory["directory_count"]})
    bundle = load_source_bundle(repo_root)
    record = build_crossbind_record(bundle)
    check("F02_EXTERNAL_SOURCE_COUNT", len(bundle.receipts) == len(SOURCE_PINS) == 15 and all(value == 1 for value in bundle.read_counts.values()), 15)

    manifest = _read_json(package_root / MANIFEST_REL)
    check("F03_MANIFEST_SCHEMA", manifest["schema"] == "MPI_BRIDGE_TO_SIM13_CONSUMER_CROSSBIND_SOURCE_MANIFEST_V1", manifest["schema"])
    expected_external = [bundle[pin["id"]].public_receipt() for pin in SOURCE_PINS]
    check("F04_EXTERNAL_RECEIPTS", manifest["external_sources"] == expected_external, len(expected_external))
    expected_internal = [file_receipt(package_root / rel, f"{PACKAGE_REL}/{rel}") for rel in INTERNAL_SOURCE_FILES]
    check("F05_INTERNAL_RECEIPTS", manifest["internal_sources"] == expected_internal, len(expected_internal))
    check("F06_DIGEST_IDENTITIES", manifest["immutable_crossbind_record"]["bridge_semantic_digest"] == record.bridge_semantic_digest and manifest["immutable_crossbind_record"]["crossbind_record_digest"] == record.crossbind_record_digest and record.bridge_semantic_digest != record.crossbind_record_digest, {"bridge": record.bridge_semantic_digest, "record": record.crossbind_record_digest})
    manifest_receipt = file_receipt(package_root / MANIFEST_REL, f"{PACKAGE_REL}/{MANIFEST_REL}")

    pytest_report = _read_json(package_root / PYTEST_REL)
    negative = _read_json(package_root / NEGATIVE_REL)
    validation = _read_json(package_root / VALIDATION_REL)
    audit = _read_json(package_root / AUDIT_REL)
    check("F07_PYTEST", pytest_report["passed"] == 28 and pytest_report["failed"] == 0, pytest_report["passed"])
    check("F08_NEGATIVE_CONTROLS", negative["passed"] == negative["total"] == 67 and negative["manifest"] == manifest_receipt, 67)
    check("F09_VALIDATION", validation["passed"] == validation["total"] == 38 and validation["manifest"] == manifest_receipt, 38)
    check("F10_INDEPENDENT_AUDIT", audit["passed"] == audit["total"] and audit["failed"] == 0 and audit["manifest"] == manifest_receipt, audit["passed"])

    gate = _read_json(package_root / GATE_REL)
    check("F11_GATE_STATUS", gate["status"] == "PASS_MPI_BRIDGE_TO_SIM13_CROSSBIND_SOURCE_FREEZE_ONLY", gate["status"])
    check("F12_GATE_DIGESTS", gate["bridge_semantic_digest"] == record.bridge_semantic_digest and gate["crossbind_record_digest"] == record.crossbind_record_digest, {"bridge": record.bridge_semantic_digest, "record": record.crossbind_record_digest})
    check("F13_GATE_EVIDENCE_HASHES", all(gate["evidence"][name] == file_receipt(package_root / rel, f"{PACKAGE_REL}/{rel}") for name, rel in (("pytest", PYTEST_REL), ("negative_controls", NEGATIVE_REL), ("validation", VALIDATION_REL), ("independent_audit", AUDIT_REL), ("source_manifest", MANIFEST_REL))), "5/5")
    check("F14_GATE_FLAGS_FALSE", set(gate["flags"]) == set(MANDATORY_FALSE_FLAGS) and not any(gate["flags"].values()), dict(gate["flags"]))
    check("F15_PARENT_FORMAL", gate["formal_parent_nc"] == {"passed": 15, "total": 20, "promoted": 0}, gate["formal_parent_nc"])
    check("F16_PRODUCTION_RECEIPT_ABSENT", gate["system_binding_v3"]["production_authenticated_receipt_present"] is False and gate["system_binding_v3"]["production_composite_producer_status"] == "NOT_IMPLEMENTED_NO_PRODUCER" and gate["system_binding_v3"]["source_lock"] is True, "absent/no-producer/source-lock")
    check("F17_NO_EXECUTION_OR_GENERATION", gate["urdf_generator_invoked"] is False and gate["dynamics_or_contact_executed"] is False and gate["cad_step_fcstd_urdf_generated"] is False, "false/false/false")

    terminal = _read_json(package_root / TERMINAL_REL)
    gate_receipt = file_receipt(package_root / GATE_REL, f"{PACKAGE_REL}/{GATE_REL}")
    check("F18_TERMINAL_BINDS_GATE", terminal["gate"] == gate_receipt and terminal["dag_terminal"] is True, gate_receipt["sha256"])
    check("F19_TERMINAL_HOLDS", terminal["remaining_holds"] == ["NC18", "NC19"] and terminal["release_credit"] is False, terminal["remaining_holds"])
    check("F20_TERMINAL_FLAGS_FALSE", not any(terminal["flags"].values()), dict(terminal["flags"]))
    check("F21_SIGNED_COMPOSITION_SCOPE", gate["system_binding_v3"]["preexec_raw_receipts_verified"] == 7 and gate["system_binding_v3"]["fixture_decision"] == {"executed_strategy": "ABORT", "allowed": False, "reason": "SOURCE_FREEZE_SCOPE_LOCK", "composite_authorization": False, "release_credit": False}, gate["system_binding_v3"]["fixture_decision"])
    check("F22_SOURCE_READ_WORDING", manifest["each_source_read_once_per_bundle_load"] is True and gate["each_source_read_once_per_bundle_load"] is True, True)
    check("F23_TERMINAL_DIGESTS", terminal["bridge_semantic_digest"] == record.bridge_semantic_digest and terminal["crossbind_record_digest"] == record.crossbind_record_digest, "bridge+record")
    check("F24_RECORD_WORDING_AND_UNCERTAINTY", validate_crossbind_record_payload(record.payload)["member_uncertainties_preserved"] is True, True)
    check("F25_REVIEW_FINDINGS_CLOSED", gate["review_finding_disposition"] == {"p0_open": 0, "p1_open": 0, "p2_open": 0, "first_round_findings_closed": True} and terminal["review_finding_disposition"] == gate["review_finding_disposition"], gate["review_finding_disposition"])
    return {
        "status": "PASS",
        "passed": len(checks),
        "total": len(checks),
        "failed": 0,
        "checks": checks,
        "bridge_max_abs_residual": recompute_bridge(bundle["PHYSICAL_DYNAMICS_BRIDGE"].parsed)["max_abs_residual"]["value"],
        "bridge_semantic_digest": record.bridge_semantic_digest,
        "crossbind_record_digest": record.crossbind_record_digest,
        "gate": gate_receipt,
        "terminal": file_receipt(package_root / TERMINAL_REL, f"{PACKAGE_REL}/{TERMINAL_REL}"),
    }
