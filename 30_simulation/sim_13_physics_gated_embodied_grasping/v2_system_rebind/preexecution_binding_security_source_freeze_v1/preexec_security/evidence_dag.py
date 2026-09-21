"""Deterministic source-freeze evidence DAG builders.

The DAG is deliberately acyclic:

    source/contracts -> manifest, negative controls, pytest receipt
    manifest + negative controls + pytest -> validation
    manifest + negative controls + pytest + validation -> independent audit
    all preceding nodes + contracts -> Gate
    Gate -> terminal

No function writes a file or touches a production path.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parents[3]
PACKAGE_RELATIVE = PACKAGE_ROOT.relative_to(PROJECT_ROOT).as_posix()
FALSE_FIELDS = (
    "system_urdf_available",
    "current_system_bound",
    "interface_instantiated",
    "physical_contact_ready",
    "dynamics_backend_ready",
    "contact_execution_authorized",
    "grasp_training_authorized",
    "next_stage_authorized",
    "release",
)
CONTRACT_FILES = (
    "MECH_RL_SYSTEM_INTERFACE_V2_STRICT_JSON_CANDIDATE_CONTRACT_V1.json",
    "PARENT_BASELINE_HASH_PINS_V1.json",
    "PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_CONTRACT_V1.json",
    "PREEXECUTION_SECURITY_NEGATIVE_CONTROL_CONTRACT_V1.json",
    "UNIFIED_R2_ATOMIC_GENERATION_TRANSACTION_CONTRACT_V1.json",
)


def frozen_json_bytes(document: Any) -> bytes:
    return (
        json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _receipt(path: str, payload: bytes) -> dict[str, Any]:
    return {
        "path": path,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest().upper(),
    }


def document_receipt(relative: str, document: Any) -> dict[str, Any]:
    return _receipt(f"{PACKAGE_RELATIVE}/{relative}", frozen_json_bytes(document))


def file_receipt(path: Path) -> dict[str, Any]:
    payload = path.read_bytes()
    return _receipt(path.relative_to(PROJECT_ROOT).as_posix(), payload)


def contract_receipts() -> dict[str, dict[str, Any]]:
    return {
        name: file_receipt(PACKAGE_ROOT / "contracts" / name)
        for name in CONTRACT_FILES
    }


def build_gate(
    *,
    manifest: Mapping[str, Any],
    negative_controls: Mapping[str, Any],
    pytest_receipt: Mapping[str, Any],
    validation: Mapping[str, Any],
    independent_audit: Mapping[str, Any],
) -> dict[str, Any]:
    prerequisites = (
        manifest.get("source_static_pass") is True
        and manifest.get("source_static_findings") == []
        and manifest.get("package_inventory_findings") == []
        and negative_controls.get("all_requested_controls_passed") is True
        and negative_controls.get("controls_passed") == ["NC15", "NC16", "NC20"]
        and negative_controls.get("parent_formal_nc_passed") == 15
        and negative_controls.get("parent_formal_nc_total") == 20
        and negative_controls.get("formal_nc_promotion") == 0
        and negative_controls.get("additive_effective_source_only_frontier_passed") == 18
        and negative_controls.get("remaining_dependency_holds") == ["NC18", "NC19"]
        and validation.get("status") == "PASS_SOURCE_FREEZE_ONLY"
        and validation.get("checks_passed") == validation.get("checks_total")
        and all(validation.get(field) is False for field in FALSE_FIELDS)
        and independent_audit.get("status") == "PASS_INDEPENDENT_SOURCE_FREEZE_AUDIT"
        and independent_audit.get("checks_passed") == independent_audit.get("checks_total")
        and all(independent_audit.get(field) is False for field in FALSE_FIELDS)
        and pytest_receipt.get("schema") == "PREEXECUTION_SECURITY_PYTEST_RECEIPT_V1"
        and pytest_receipt.get("failed") == 0
        and pytest_receipt.get("passed") == pytest_receipt.get("collected")
        and pytest_receipt.get("cacheprovider_disabled") is True
        and pytest_receipt.get("bytecode_write_disabled") is True
    )
    status = "PASS_SOURCE_FREEZE_ONLY" if prerequisites else "FAIL_SOURCE_FREEZE"
    return {
        "schema": "UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_GATE_V1",
        "status": status,
        "gate_ceiling": "PASS_SOURCE_FREEZE_ONLY",
        "scope": "PREEXECUTION_BINDING_SECURITY_CONTRACTS_AND_SYNTHETIC_FIXTURES_ONLY",
        "criteria": {
            "strict_json_and_canonical_digest": "PASS" if prerequisites else "FAIL",
            "full_package_exact_allowlist": "PASS_SOURCE_MANIFEST_PLUS_FIXED_DAG_OUTPUTS" if prerequisites else "FAIL",
            "public_boundary_totality": "PASS_BOUNDED_JSON_ABORT_NO_NONCE_ON_DEPTH_DIGITS_BYTES_STRINGS_NODES_UTF8_SURROGATES_OVERFLOW_OR_NON_BYTES" if prerequisites else "FAIL",
            "strict_interface_candidate_parser": "PASS_SYNTHETIC_FIXTURE_ONLY" if prerequisites else "FAIL",
            "receipt_bound_authority_join": "PASS_SOURCE_KERNEL_ONLY" if prerequisites else "FAIL",
            "atomic_bundle_nonce_commit": "DECLARED_FUTURE_ALLOW_COMMIT_ONLY__CURRENT_SOURCE_FREEZE_CONSUMES_ZERO_NONCES",
            "replay_store": "IN_PROCESS_SYNTHETIC_NONPERSISTENT__NO_PRODUCTION_CREDIT",
            "direct_backend_public_api": "ABORT_ONLY_SOURCE_FREEZE_SCOPE_LOCK",
            "system_urdf_bytes_contract": "PASS_EXACT_SOURCE_STATIC_BROADPHASE_SYNTHETIC_FIXTURE_ONLY" if prerequisites else "FAIL",
            "atomic_generation_transaction": "PASS_DECLARATION_ONLY_NO_EXECUTOR" if prerequisites else "FAIL",
            "NC15": "PASS_NEGATIVE_CONTROL_DETECTED_SOURCE_ONLY" if prerequisites else "FAIL",
            "NC16": "PASS_NEGATIVE_CONTROL_DETECTED_SOURCE_ONLY" if prerequisites else "FAIL",
            "NC20": "PASS_NEGATIVE_CONTROL_DETECTED_SOURCE_ONLY" if prerequisites else "FAIL",
            "NC18": "HOLD_NO_INTEGRATED_STATE_EVOLUTION",
            "NC19": "HOLD_NO_AUTHORITATIVE_NARROW_PHASE_CONTACT",
        },
        "parent_formal_nc": {"passed": 15, "total": 20, "promoted": 0},
        "additive_effective_source_only_nc": {
            "passed": 18 if prerequisites else 15,
            "total": 20,
            "added": ["NC15", "NC16", "NC20"] if prerequisites else [],
            "holds": ["NC18", "NC19"],
        },
        "dag": {
            "order": [
                "contracts_and_sources",
                "source_manifest_negative_controls_pytest",
                "validation",
                "independent_audit",
                "gate",
                "terminal",
            ],
            "terminal_must_bind_gate": True,
        },
        "contracts": contract_receipts(),
        "evidence": {
            "source_manifest": document_receipt("manifest/PREEXECUTION_BINDING_SECURITY_SOURCE_SHA256_V1.json", manifest),
            "negative_controls": document_receipt("evidence/PREEXECUTION_SECURITY_NEGATIVE_CONTROLS_V1.json", negative_controls),
            "pytest": document_receipt("evidence/PREEXECUTION_SECURITY_PYTEST_RECEIPT_V1.json", pytest_receipt),
            "validation": document_receipt("evidence/PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_VALIDATION_V1.json", validation),
            "independent_audit": document_receipt("evidence/PREEXECUTION_BINDING_SECURITY_INDEPENDENT_AUDIT_V1.json", independent_audit),
        },
        "production_credit": False,
        **{field: False for field in FALSE_FIELDS},
        "maximum_runtime_state": "ABORT_ONLY",
        "hold_reason": "Actual V2 interface and system URDF are absent; NC18/NC19 remain HOLD; synthetic HMAC, in-process replay state and fixtures carry no production authority.",
    }


def build_terminal(gate: Mapping[str, Any]) -> dict[str, Any]:
    gate_pass = gate.get("status") == "PASS_SOURCE_FREEZE_ONLY"
    return {
        "schema": "UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_TERMINAL_V1",
        "terminal_state": (
            "PASS_SOURCE_FREEZE_ONLY__PRODUCTION_BINDING_HOLD"
            if gate_pass
            else "FAIL_SOURCE_FREEZE__PRODUCTION_BINDING_HOLD"
        ),
        "source_freeze_complete": gate_pass,
        "gate": document_receipt(
            "results/UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_GATE_V1.json",
            gate,
        ),
        "dag_terminal": True,
        "formal_parent_nc_passed": 15,
        "formal_parent_nc_total": 20,
        "formal_nc_promotion": 0,
        "effective_source_only_nc_passed": 18 if gate_pass else 15,
        "effective_source_only_nc_total": 20,
        "remaining_holds": ["NC18", "NC19"],
        "next_required_external_or_future_version_inputs": [
            "DIRECT_OWNER_EXECUTION_AUTHORIZATION",
            "ACTUAL_MECH_RL_SYSTEM_INTERFACE_V2_INSTANCE",
            "ACTUAL_VALIDATED_SYSTEM_URDF_AND_RECEIPT",
            "PRODUCTION_KEY_TRUSTED_CLOCK_AND_DURABLE_REPLAY_STORE",
            "INTEGRATED_DYNAMICS_STATE_EVOLUTION_FOR_NC18",
            "AUTHORITATIVE_NARROW_PHASE_CONTACT_AND_RELEASED_GEOMETRY_FOR_NC19",
        ],
        "production_credit": False,
        **{field: False for field in FALSE_FIELDS},
    }


__all__ = [
    "CONTRACT_FILES",
    "FALSE_FIELDS",
    "PACKAGE_RELATIVE",
    "build_gate",
    "build_terminal",
    "contract_receipts",
    "document_receipt",
    "file_receipt",
    "frozen_json_bytes",
]
