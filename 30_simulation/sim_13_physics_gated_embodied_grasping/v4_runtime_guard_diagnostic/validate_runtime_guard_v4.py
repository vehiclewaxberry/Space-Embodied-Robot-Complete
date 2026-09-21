#!/usr/bin/env python3
"""Validate V4 evidence, then write a truth-preserving machine Gate."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Mapping


HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[2]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import generate_runtime_guard_evidence as generator
import independent_audit_runtime_guard as independent


VALIDATION_PATH = HERE / "evidence/SIM13_V4_VALIDATION_V1.json"
GATE_PATH = HERE / "results/SIM13_V4_RUNTIME_GUARD_DIAGNOSTIC_GATE_V1.json"
EVIDENCE_MANIFEST_PATH = HERE / "results/SIM13_V4_SELF_EXCLUDED_EVIDENCE_MANIFEST_V1.json"


def _write_json(path: Path, document: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_bytes(payload.encode("utf-8"))


def _record(path: Path) -> dict[str, object]:
    return generator.file_record(path, PROJECT_ROOT)


def _run_tests() -> dict[str, object]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    command = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "-q",
        "-p",
        "no:cacheprovider",
    ]
    completed = subprocess.run(
        command,
        cwd=HERE,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = (completed.stdout + "\n" + completed.stderr).strip()
    match = re.search(r"(\d+) passed", output)
    passed = int(match.group(1)) if match else 0
    return {
        "command": "python -B -m pytest -q -p no:cacheprovider",
        "returncode": completed.returncode,
        "passed": passed,
        "expected_passed": 40,
        "all_passed": completed.returncode == 0 and passed == 40,
        "cache_provider_disabled": True,
    }


def _forbidden_assets() -> dict[str, object]:
    urdf = [path.relative_to(HERE).as_posix() for path in HERE.rglob("*.urdf")]
    cache = [
        path.relative_to(HERE).as_posix()
        for path in HERE.rglob("*")
        if path.name in {"__pycache__", ".pytest_cache"}
    ]
    compiled = [
        path.relative_to(HERE).as_posix()
        for pattern in ("*.pyc", "*.pyo")
        for path in HERE.rglob(pattern)
    ]
    forbidden_names = {
        "MECH_RL_SYSTEM_INTERFACE_V2.yaml",
        "OWNER_AUTHORIZATION.json",
        "RUN_AUTHORIZATION.json",
        "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json",
    }
    authority_files = [
        path.relative_to(HERE).as_posix()
        for path in HERE.rglob("*")
        if path.name in forbidden_names
    ]
    private_calls: list[str] = []
    for path in HERE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            else:
                continue
            if name in {"_build_robot", "gen_urdf"}:
                private_calls.append(f"{path.name}:{name}")
    return {
        "urdf_files": urdf,
        "cache_directories": cache,
        "compiled_python_files": compiled,
        "interface_or_authorization_files": authority_files,
        "private_unified_generator_calls": private_calls,
        "clean": not (urdf or cache or compiled or authority_files or private_calls),
    }


def build_validation(test_result: Mapping[str, object]) -> dict[str, Any]:
    source_manifest_current = (
        generator.SOURCE_MANIFEST_PATH.read_bytes()
        == generator.build_source_manifest_bytes()
    )
    stored_ledger = json.loads(generator.LEDGER_PATH.read_text(encoding="utf-8"))
    fresh_ledger = generator.build_ledger()
    ledger_reproduced = stored_ledger == fresh_ledger
    stored_audit = json.loads(independent.AUDIT_PATH.read_text(encoding="utf-8"))
    fresh_audit = independent.build_audit()
    audit_reproduced = stored_audit == fresh_audit
    assets = _forbidden_assets()
    authority_false = all(
        value is False for value in stored_ledger["authority_flags"].values()
    )
    v2_formal_unchanged = stored_ledger["formal_v2_negative_control_state"] == {
        "passed": 15,
        "declared": 20,
        "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"],
        "unchanged_by_v4": True,
    }
    diagnostic_controls = stored_ledger["diagnostic_controls"]
    four_diagnostics = all(
        diagnostic_controls[name]["passed_diagnostic"] is True
        for name in ("NC15", "NC16", "NC18", "NC20")
    )
    nc15 = diagnostic_controls["NC15"]
    nc16 = diagnostic_controls["NC16"]
    nc18 = diagnostic_controls["NC18"]
    nc20 = diagnostic_controls["NC20"]
    nc15_module_instance_boundary_exact = nc15["persistence_boundary"] == (
        "SINGLE_CANONICAL_MODULE_INSTANCE_LIFETIME_SHARED_THREAD_SAFE_ONLY__"
        "NO_IMPORTLIB_RELOAD_DUPLICATE_MODULE_INSTANCE_CROSS_PROCESS_OR_RESTART_"
        "PERSISTENCE_CLAIM"
    )
    nc15_shared_race = (
        nc15["cases"]["cross_shield_new_ledger_replay"]["decision"]["reason_code"]
        == "CAPABILITY_NONCE_REPLAY"
        and nc15["cases"]["cross_shield_new_ledger_replay"][
            "new_ledger_view_reconsume_allowed"
        ]
        is False
        and nc15["cases"]["thread_safe_cross_shield_race"]["allowed"] == 1
        and nc15["cases"]["thread_safe_cross_shield_race"]["replay_rejections"]
        == 15
    )
    opaque = nc16["opaque_invocation_negative_controls"]
    opaque_exact = (
        opaque["passed"] is True
        and opaque["object_new_accepted"] is False
        and opaque["copy_constructor_rejected"] is True
        and opaque["manual_clone_accepted"] is False
        and opaque["registered_original_accepted_once"] is True
        and opaque["replay_accepted"] is False
        and opaque["module_private_forge_primitives"] == []
        and nc16["direct_bypass_reason"]
        == "BACKEND_DIRECT_CALL_FORBIDDEN_USE_COORDINATOR"
    )
    sim10_artifacts = nc20["sim10_artifacts"]
    receipt_payload = nc20["receipt"]["payload"]
    four_sim10_sha_bound = (
        set(sim10_artifacts) == {"gate", "summary", "parameter_card", "anchor_source"}
        and receipt_payload["sim10_gate_sha256"]
        == sim10_artifacts["gate"]["sha256"]
        and receipt_payload["sim10_summary_sha256"]
        == sim10_artifacts["summary"]["sha256"]
        and receipt_payload["sim10_parameter_card_sha256"]
        == sim10_artifacts["parameter_card"]["sha256"]
        and receipt_payload["sim10_anchor_source_sha256"]
        == sim10_artifacts["anchor_source"]["sha256"]
    )
    distributed_anchor_fields_bound = (
        receipt_payload["anchor_region"] == "INFEASIBLE_RATE"
        and receipt_payload["anchor_w_plus_dps"] == 3.0633304945807067
        and receipt_payload["mass_speed_source_proof"]
        == {
            "parameter_card_calibration_mass_kg": 150.0,
            "anchor_source_target_mass_kg": 150.0,
            "anchor_source_tumble_rate_dps": 3.0,
        }
    )
    expected_coordinator_cases = {
        "missing_receipt",
        "valid_infeasible_veto",
        "action_drift",
        "snapshot_drift",
        "target_drift",
        "anchor_drift",
        "hash_drift",
        "malformed_numeric",
    }
    coordinator_cases = nc20["coordinator_prebackend_veto_cases"]
    prebackend_zero = set(coordinator_cases) == expected_coordinator_cases and all(
        item["executed_action"]["strategy_id"] == "ABORT"
        and item["capability_consumed"] is False
        and item["backend_invocation_delta"] == 0
        and item["backend_invocation_count_before"] == 0
        and item["backend_invocation_count_after"] == 0
        and item["state_byte_semantic_unchanged"] is True
        and item["before_state_sha256"] == item["after_state_sha256"]
        for item in coordinator_cases.values()
    )
    prebackend_zero = prebackend_zero and (
        nc20["coordinator_backend_invocation_count_final"] == 0
        and nc20["coordinator_capability_nonce_consumed"] is False
        and nc20["veto_precedes_capability_consumption_and_backend"] is True
    )
    checks = {
        "V01_TESTS_40_OF_40": test_result["all_passed"] is True,
        "V02_PYTEST_CACHE_DISABLED": test_result["cache_provider_disabled"] is True,
        "V03_SOURCE_MANIFEST_REPRODUCES": source_manifest_current,
        "V04_LEDGER_REPRODUCES": ledger_reproduced,
        "V05_INDEPENDENT_AUDIT_REPRODUCES": audit_reproduced,
        "V06_INDEPENDENT_AUDIT_20_OF_20": stored_audit["score"] == {
            "pass": 20,
            "total": 20,
            "failed": [],
        },
        "V07_NC15_DIAGNOSTIC": nc15["passed_diagnostic"] is True,
        "V08_NC16_DIAGNOSTIC": nc16["passed_diagnostic"] is True,
        "V09_NC18_DIAGNOSTIC": nc18["passed_diagnostic"] is True,
        "V10_NC20_DIAGNOSTIC": nc20["passed_diagnostic"] is True,
        "V11_FOUR_DIAGNOSTICS_ARE_NOT_FORMAL_CREDIT": four_diagnostics
        and stored_ledger["diagnostic_summary"]["formal_production_nc_credit"]
        is False,
        "V12_V2_FORMAL_REMAINS_15_OF_20": v2_formal_unchanged,
        "V13_NC19_HOLD": stored_ledger["nc19"]["executed"] is False
        and stored_ledger["nc19"]["passed"] is False,
        "V14_ALL_AUTHORITY_AND_RELEASE_FLAGS_FALSE": authority_false,
        "V15_NO_URDF_INTERFACE_AUTH_PRIVATE_CALL_OR_CACHE": assets["clean"] is True,
        "V16_UNIT_LEDGER_SEPARATED": nc18["unit_contract"]
        == {
            "coordinate_units": ["rad"] * 6 + ["m"] * 2,
            "rate_units": ["rad/s"] * 6 + ["m/s"] * 2,
            "effort_units": ["N*m"] * 6 + ["N"] * 2,
            "heterogeneous_global_norm_used": False,
            "base_linear_and_angular_twist_audited_separately": True,
        },
        "V17_SIM10_NOT_INHERITED_TO_CURRENT_R2": nc20["cases"][
            "valid_infeasible_rate_veto"
        ]["historical_sim10_pass_inherited_to_current_system"]
        is False,
        "V18_PHASE_ONLY_NEGATIVE_DETECTED": nc18["phase_only_negative_control"][
            "assessment"
        ]["reason_code"]
        == "DYNAMICS_STATE_UPDATE_FAILURE_PHASE_ONLY",
        "V19_NC15_SHARED_THREAD_SAFE_CANONICAL_MODULE_NONCE": nc15_shared_race,
        "V20_NC15_RELOAD_DUPLICATE_MODULE_PROCESS_RESTART_NOT_CLAIMED": (
            nc15_module_instance_boundary_exact
        ),
        "V21_NC16_OPAQUE_ONE_USE_AND_DIRECT_BYPASS_REJECTION": opaque_exact,
        "V22_NC16_COOPERATIVE_API_BOUNDARY_DECLARED": (
            "MALICIOUS_MONKEYPATCH_OR_CLOSURE_INTROSPECTION_OUT_OF_SCOPE"
            in nc16["security_boundary"]
        ),
        "V23_NC20_FOUR_SHA_PLUS_DISTRIBUTED_ANCHOR_FIELDS": (
            four_sim10_sha_bound
            and distributed_anchor_fields_bound
            and stored_audit["checks"][
                "A20_SIM10_FOUR_SHA_PLUS_DISTRIBUTED_ANCHOR_FIELDS"
            ]
            is True
        ),
        "V24_NC20_PREBACKEND_ABORT_ZERO_INVOCATION_STATE_UNCHANGED": prebackend_zero,
        "V25_NC20_RESIGNED_MALFORMED_TYPE_FAILS_CLOSED": nc20["cases"][
            "resigned_malformed_numeric"
        ]["reason_code"]
        == "SIM10_VETO_RECEIPT_MALFORMED_TYPE",
    }
    pass_count = sum(int(value) for value in checks.values())
    return {
        "schema": "SIM13_V4_RUNTIME_GUARD_VALIDATION_V1",
        "generated_date_local": "2026-08-24",
        "scope": "SYNTHETIC_PREBIND_DIAGNOSTIC_ONLY",
        "verdict": (
            "PASS_V4_SYNTHETIC_DIAGNOSTIC_VALIDATION"
            if pass_count == len(checks)
            else "FAIL_V4_SYNTHETIC_DIAGNOSTIC_VALIDATION"
        ),
        "score": {
            "pass": pass_count,
            "total": len(checks),
            "failed": [name for name, value in checks.items() if not value],
        },
        "checks": checks,
        "tests": dict(test_result),
        "forbidden_asset_scan": assets,
        "inputs": {
            "source_manifest": _record(generator.SOURCE_MANIFEST_PATH),
            "ledger": _record(generator.LEDGER_PATH),
            "independent_audit": _record(independent.AUDIT_PATH),
        },
        "owner_accepted": False,
        "current_system_passed": False,
        "current_system_binding_passed": False,
        "system_binding_passed": False,
        "runtime_fail_closed_gate_passed": False,
        "runtime_production_gate_passed": False,
        "production_dynamics_gate_passed": False,
        "contact_grasp_gate_passed": False,
        "system_urdf_available": False,
        "system_interface_instantiated": False,
        "release_credit": False,
        "next_stage_authorized": False,
    }


def build_gate(validation: Mapping[str, Any]) -> dict[str, Any]:
    diagnostics_pass = validation["score"]["failed"] == []
    return {
        "schema": "SIM13_V4_RUNTIME_GUARD_DIAGNOSTIC_GATE_V1",
        "generated_date_local": "2026-08-24",
        "scope": "SYNTHETIC_PREBIND_DIAGNOSTIC_ONLY",
        "technical_verdict": (
            "PASS_SYNTHETIC_PREBIND_RUNTIME_GUARD_DIAGNOSTIC_ONLY__CURRENT_V2_FORMAL_NC_REMAINS_15_OF_20__NC19_HOLD__NO_PRODUCTION_OR_RELEASE_CREDIT"
            if diagnostics_pass
            else "FAIL_SYNTHETIC_PREBIND_RUNTIME_GUARD_DIAGNOSTIC"
        ),
        "diagnostic_gate_passed": diagnostics_pass,
        "diagnostic_negative_controls": {
            "NC15": "PASS_DIAGNOSTIC_LOGIC_ONLY" if diagnostics_pass else "FAIL",
            "NC16": "PASS_DIAGNOSTIC_LOGIC_ONLY" if diagnostics_pass else "FAIL",
            "NC18": "PASS_DIAGNOSTIC_LOGIC_ONLY" if diagnostics_pass else "FAIL",
            "NC20": "PASS_DIAGNOSTIC_LOGIC_ONLY" if diagnostics_pass else "FAIL",
            "formal_production_nc_credit": False,
        },
        "formal_v2_negative_controls": {
            "passed": 15,
            "declared": 20,
            "all_passed": False,
            "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"],
            "unchanged_by_v4": True,
        },
        "diagnostic_claim_boundaries": {
            "NC15": (
                "SINGLE_CANONICAL_MODULE_INSTANCE_LIFETIME_SHARED_THREAD_SAFE_"
                "NONCE_ONLY__NO_IMPORTLIB_RELOAD_DUPLICATE_MODULE_INSTANCE_"
                "CROSS_PROCESS_OR_RESTART_PERSISTENCE_CLAIM__FORMAL_HOLD"
            ),
            "NC16": (
                "COOPERATIVE_PYTHON_API_DIAGNOSTIC_ONLY__OPAQUE_INVOCATION_"
                "ONE_USE__MALICIOUS_IN_PROCESS_MONKEYPATCH_OR_CLOSURE_"
                "INTROSPECTION_OUT_OF_SCOPE__FORMAL_HOLD"
            ),
            "NC18": (
                "V3_PUBLIC_SYNTHETIC_6R2P_REDUCED_DYNAMICS_VIA_UNIQUE_"
                "COORDINATOR__NOT_CURRENT_SYSTEM_OR_CONTACT__FORMAL_HOLD"
            ),
            "NC20": (
                "FOUR_SIM10_ARTIFACT_SHA_BINDINGS__GATE_SUMMARY_REGION_AND_W_"
                "PLUS__PARAMETER_CARD_CALIBRATION_MASS__ANCHOR_SOURCE_MASS_AND_"
                "TUMBLE__150KG_3DPS_PREBACKEND_VETO__NO_SIM10_PASS_INHERITANCE__"
                "FORMAL_HOLD"
            ),
            "NC19": "NOT_EXECUTED__FORMAL_HOLD",
        },
        "nc19_status": "HOLD_AUTHORITATIVE_NARROW_PHASE_CONTACT_AND_RELEASED_GEOMETRY_ABSENT",
        "score": validation["score"],
        "evidence": {
            "source_manifest": _record(generator.SOURCE_MANIFEST_PATH),
            "ledger": _record(generator.LEDGER_PATH),
            "independent_audit": _record(independent.AUDIT_PATH),
            "validation": _record(VALIDATION_PATH),
        },
        "owner_accepted": False,
        "current_system_passed": False,
        "current_system_binding_passed": False,
        "system_binding_passed": False,
        "runtime_fail_closed_gate_passed": False,
        "runtime_production_gate_passed": False,
        "production_dynamics_gate_passed": False,
        "contact_grasp_gate_passed": False,
        "system_urdf_available": False,
        "system_interface_instantiated": False,
        "historical_sim10_pass_inherited_to_current_system": False,
        "release_credit": False,
        "next_stage_authorized": False,
    }


def build_evidence_manifest() -> dict[str, Any]:
    return {
        "schema": "SIM13_V4_SELF_EXCLUDED_EVIDENCE_MANIFEST_V1",
        "generated_date_local": "2026-08-24",
        "manifest_policy": (
            "DAG_ONLY: source_manifest -> ledger -> independent_audit -> validation -> gate; "
            "this outer manifest hashes all prior nodes and explicitly excludes itself"
        ),
        "self_excluded": True,
        "contains_manifest_own_hash": False,
        "artifacts": [
            _record(generator.SOURCE_MANIFEST_PATH),
            _record(generator.LEDGER_PATH),
            _record(independent.AUDIT_PATH),
            _record(VALIDATION_PATH),
            _record(GATE_PATH),
        ],
        "owner_accepted": False,
        "current_system_passed": False,
        "current_system_binding_passed": False,
        "system_binding_passed": False,
        "runtime_fail_closed_gate_passed": False,
        "runtime_production_gate_passed": False,
        "production_dynamics_gate_passed": False,
        "contact_grasp_gate_passed": False,
        "system_urdf_available": False,
        "system_interface_instantiated": False,
        "release_credit": False,
        "next_stage_authorized": False,
    }


def main() -> int:
    test_result = _run_tests()
    validation = build_validation(test_result)
    _write_json(VALIDATION_PATH, validation)
    gate = build_gate(validation)
    _write_json(GATE_PATH, gate)
    manifest = build_evidence_manifest()
    _write_json(EVIDENCE_MANIFEST_PATH, manifest)
    print(
        json.dumps(
            {
                "tests": test_result,
                "validation_score": validation["score"],
                "gate": gate["technical_verdict"],
                "next_stage_authorized": gate["next_stage_authorized"],
            },
            sort_keys=True,
        )
    )
    return 0 if not validation["score"]["failed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
