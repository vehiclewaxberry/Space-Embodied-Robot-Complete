#!/usr/bin/env python3
"""Recompute the source-freeze claims without writing any artifact."""

from __future__ import annotations

import hashlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any

from freeze_preexecution_security_sources import (
    build_manifest,
    package_asset_cache_findings,
    package_inventory_findings,
)
from independent_audit_preexecution_security import build_audit
from preexec_security.evidence_dag import (
    FALSE_FIELDS,
    build_gate,
    build_terminal,
    document_receipt,
    frozen_json_bytes,
)
from preexec_security.interface_contract import parse_interface_candidate, synthetic_interface_candidate
from preexec_security.negative_controls import (
    ACTION_ABORT,
    ACTION_S1,
    CONTEXT,
    NOW,
    SYNTHETIC_KEY,
    parent_baseline_hashes,
    run_security_negative_controls,
)
from preexec_security.receipts import (
    ReceiptError,
    ReplayStore,
    admit_backend_request,
    evaluate_receipt_bound_join,
    issue_synthetic_receipt,
    verify_receipt,
)
from preexec_security.strict_json import (
    MAX_JSON_BYTES,
    MAX_JSON_COMPLEXITY_UNITS,
    MAX_JSON_DEPTH,
    MAX_JSON_NODES,
    MAX_JSON_NUMBER_CHARS,
    MAX_JSON_STRING_CHARS,
    MAX_JSON_TOTAL_STRING_CHARS,
    StrictJSONError,
    canonical_json_bytes,
    loads_strict,
)
from preexec_security.transaction_contract import validate_transaction_contract
from preexec_security.urdf_contract import build_synthetic_parser_fixture_bytes, validate_system_urdf_bytes


HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
INTERFACE_PATH = PROJECT / "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml"
SYSTEM_URDF_PATH = PROJECT / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/unified_r2_c01_no_route_c_sim_candidate_v2.urdf"

MANIFEST_PATH = HERE / "manifest/PREEXECUTION_BINDING_SECURITY_SOURCE_SHA256_V1.json"
NEGATIVE_PATH = HERE / "evidence/PREEXECUTION_SECURITY_NEGATIVE_CONTROLS_V1.json"
PYTEST_PATH = HERE / "evidence/PREEXECUTION_SECURITY_PYTEST_RECEIPT_V1.json"
VALIDATION_PATH = HERE / "evidence/PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_VALIDATION_V1.json"
AUDIT_PATH = HERE / "evidence/PREEXECUTION_BINDING_SECURITY_INDEPENDENT_AUDIT_V1.json"
GATE_PATH = HERE / "results/UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_GATE_V1.json"
TERMINAL_PATH = HERE / "results/UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_TERMINAL_V1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _check(checks: list[dict[str, Any]], identifier: str, statement: str, passed: bool, observed: Any) -> None:
    checks.append({"id": identifier, "statement": statement, "passed": bool(passed), "observed": observed})


def build_validation() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    committed_manifest = loads_strict(MANIFEST_PATH.read_bytes())
    current_manifest = build_manifest()
    _check(checks, "PSF-01", "source manifest hashes and byte counts are current", committed_manifest == current_manifest, {"committed_files": committed_manifest.get("file_count"), "current_files": current_manifest["file_count"]})
    _check(checks, "PSF-02", "source AST contains no dormant generator import or generation call", current_manifest["source_static_pass"] is True, current_manifest["source_static_findings"])
    interface = parse_interface_candidate(canonical_json_bytes(synthetic_interface_candidate()))
    _check(checks, "PSF-03", "strict V2 interface candidate parser accepts only the synthetic exact fixture", interface["schema"] == "MECH_RL_SYSTEM_INTERFACE_V2" and interface["authority"]["contact_grasp_authorized"] is False, {"schema": interface["schema"], "scope": interface["authority"]["current_scope"]})
    urdf = validate_system_urdf_bytes(build_synthetic_parser_fixture_bytes())
    _check(checks, "PSF-04", "exact source-static broadphase 19-link 18-joint URDF contract passes only the in-memory fixture", urdf["fixture_only"] is True and urdf["mesh_references"] == 0 and urdf["total_mass_kg"] == 31.022864807342987 and urdf["geometry_contract"].startswith("EXACT_SOURCE_STATIC_PRIMITIVE_BROADPHASE_ONLY") and urdf["numeric_comparison"] == "EXACT_PARSED_FLOAT_NO_TOLERANCE", urdf)
    transaction = validate_transaction_contract((HERE / "contracts/UNIFIED_R2_ATOMIC_GENERATION_TRANSACTION_CONTRACT_V1.json").read_bytes())
    _check(checks, "PSF-05", "fixed-path atomic transaction is declaration-only", transaction["mode"] == "DECLARATION_ONLY_NO_EXECUTOR" and not any(transaction["source_freeze_execution_state"].values()), transaction["source_freeze_execution_state"])
    negative = run_security_negative_controls()
    _check(checks, "PSF-06", "NC15 NC16 NC20 pass exact deterministic source-only probes", negative["all_requested_controls_passed"] is True and negative["controls_passed"] == ["NC15", "NC16", "NC20"], negative["controls_passed"])
    _check(checks, "PSF-07", "parent formal NC credit remains 15 of 20 with zero promotion", negative["parent_formal_nc_passed"] == 15 and negative["formal_nc_promotion"] == 0, {"formal": negative["parent_formal_nc_passed"], "promotion": negative["formal_nc_promotion"]})
    _check(checks, "PSF-08", "additive source-only frontier is 18 of 20", negative["additive_effective_source_only_frontier_passed"] == 18 and negative["remaining_dependency_holds"] == ["NC18", "NC19"], {"effective": negative["additive_effective_source_only_frontier_passed"], "holds": negative["remaining_dependency_holds"]})
    hashes, hash_pass = parent_baseline_hashes()
    _check(checks, "PSF-09", "parent frozen hashes remain unchanged", hash_pass, hashes)
    _check(checks, "PSF-10", "actual V2 interface instance remains absent", not INTERFACE_PATH.exists(), INTERFACE_PATH.relative_to(PROJECT).as_posix())
    _check(checks, "PSF-11", "actual system URDF remains absent", not SYSTEM_URDF_PATH.exists(), SYSTEM_URDF_PATH.relative_to(PROJECT).as_posix())
    prohibited = package_asset_cache_findings() + package_inventory_findings()
    _check(checks, "PSF-12", "full package matches the exact source-plus-fixed-DAG allowlist and contains no prohibited asset or cache", not prohibited, prohibited)
    stored_nc = loads_strict(NEGATIVE_PATH.read_bytes())
    _check(checks, "PSF-13", "stored negative-control evidence matches recomputation", stored_nc == negative, {"stored_sha256": _sha256(NEGATIVE_PATH)})
    pytest_receipt = loads_strict(PYTEST_PATH.read_bytes())
    pytest_ok = (
        pytest_receipt.get("schema") == "PREEXECUTION_SECURITY_PYTEST_RECEIPT_V1"
        and isinstance(pytest_receipt.get("collected"), int)
        and pytest_receipt.get("collected") > 0
        and pytest_receipt.get("passed") == pytest_receipt.get("collected")
        and pytest_receipt.get("failed") == 0
        and isinstance(pytest_receipt.get("duration_seconds"), (int, float))
        and pytest_receipt.get("duration_seconds") > 0
        and pytest_receipt.get("cacheprovider_disabled") is True
        and pytest_receipt.get("bytecode_write_disabled") is True
    )
    _check(checks, "PSF-14", "pytest receipt records complete no-cache execution", pytest_ok, pytest_receipt)
    action_context_exact = (
        tuple(ACTION_S1) == ("grasp_candidate_id", "capture_timing_id", "strategy_id")
        and ACTION_ABORT == {"grasp_candidate_id": "__ABORT__", "capture_timing_id": "__ABORT__", "strategy_id": "ABORT"}
        and tuple(CONTEXT) == ("episode_id", "configuration_id", "authority_epoch", "target_class")
        and "consume_nonce" not in inspect.signature(verify_receipt).parameters
    )
    _check(checks, "PSF-15", "exact high-level action/context schema and read-only public verify API are frozen", action_context_exact, {"action_fields": list(ACTION_S1), "context_fields": list(CONTEXT), "verify_parameters": list(inspect.signature(verify_receipt).parameters)})
    overflow_rejected = False
    try:
        issue_synthetic_receipt(
            kind="SYSTEM_BINDING_V2",
            action=ACTION_S1,
            context=CONTEXT,
            payload={"status": "PASS", "system_urdf_sha256": "A" * 64},
            issued_at_unix_s=10**399,
            expires_at_unix_s=NOW + 30.0,
            nonce="VALIDATION_OVERFLOW_NONCE_01",
            evidence_sha256="B" * 64,
            key=SYNTHETIC_KEY,
        )
    except ReceiptError as exc:
        overflow_rejected = str(exc) == "INVALID_NUMBER:/body/issued_at_unix_s"
    direct_store = ReplayStore()
    direct_invalid = admit_backend_request(
        "S1",
        shield_receipt_bytes={},
        action=ACTION_S1,
        context=CONTEXT,
        trusted_now_unix_s=NOW,
        replay_store=direct_store,
        key=SYNTHETIC_KEY,
    )
    join_store = ReplayStore()
    join_invalid = evaluate_receipt_bound_join(
        "S1",
        receipt_bytes_by_kind={"SHIELD_ATTESTATION_V2": None},
        action=ACTION_S1,
        context=CONTEXT,
        trusted_now_unix_s=NOW,
        replay_store=join_store,
        key=SYNTHETIC_KEY,
    )
    boundary_totality = (
        overflow_rejected
        and direct_invalid.allowed is False
        and direct_invalid.executed_strategy == "ABORT"
        and direct_invalid.reason_codes == ("RECEIPT_BYTES_REQUIRED",)
        and direct_store.seen_count == 0
        and join_invalid.allowed is False
        and join_invalid.executed_strategy == "ABORT"
        and join_invalid.reason_codes == ("RECEIPT_BYTES_REQUIRED",)
        and join_store.seen_count == 0
    )
    _check(
        checks,
        "PSF-16",
        "overflowing JSON-domain integers and non-bytes receipts fail closed without nonce consumption",
        boundary_totality,
        {
            "overflow_rejected": overflow_rejected,
            "direct_reason": list(direct_invalid.reason_codes),
            "join_reason": list(join_invalid.reason_codes),
            "direct_nonce_count": direct_store.seen_count,
            "join_nonce_count": join_store.seen_count,
        },
    )
    malformed_records = {
        "deep_array_1200": b"[" * 1200 + b"0" + b"]" * 1200,
        "deep_object_1200": b'{"x":' * 1200 + b"0" + b"}" * 1200,
        "integer_5000_digits": b"9" * 5000,
        "oversize_bytes": b" " * (MAX_JSON_BYTES + 1),
        "invalid_utf8": b'"\xff"',
        "escaped_lone_surrogate": b'"\\ud800"',
        "overlong_string": ('"' + "x" * (MAX_JSON_STRING_CHARS + 1) + '"').encode("ascii"),
    }
    parser_reasons: dict[str, str] = {}
    public_boundary_pass = True
    for label, malformed in malformed_records.items():
        try:
            verify_receipt(
                malformed,
                expected_kind="SYSTEM_BINDING_V2",
                action=ACTION_S1,
                context=CONTEXT,
                trusted_now_unix_s=NOW,
                replay_store=ReplayStore(),
                key=SYNTHETIC_KEY,
            )
            public_boundary_pass = False
            parser_reasons[label] = "UNEXPECTED_VERIFY_ACCEPT"
        except ReceiptError as exc:
            parser_reasons[label] = str(exc)
        direct_limit_store = ReplayStore()
        direct_limit = admit_backend_request(
            "S1",
            shield_receipt_bytes=malformed,
            action=ACTION_S1,
            context=CONTEXT,
            trusted_now_unix_s=NOW,
            replay_store=direct_limit_store,
            key=SYNTHETIC_KEY,
        )
        join_limit_store = ReplayStore()
        join_limit = evaluate_receipt_bound_join(
            "S1",
            receipt_bytes_by_kind={"SHIELD_ATTESTATION_V2": malformed},
            action=ACTION_S1,
            context=CONTEXT,
            trusted_now_unix_s=NOW,
            replay_store=join_limit_store,
            key=SYNTHETIC_KEY,
        )
        public_boundary_pass = public_boundary_pass and (
            direct_limit.allowed is False
            and direct_limit.executed_strategy == "ABORT"
            and direct_limit_store.seen_count == 0
            and join_limit.allowed is False
            and join_limit.executed_strategy == "ABORT"
            and join_limit_store.seen_count == 0
        )

    deep_payload: object = 0
    for _ in range(1200):
        deep_payload = [deep_payload]
    issue_inputs = (
        ({"nested": deep_payload}, NOW - 1.0),
        ({"nodes": [0] * (MAX_JSON_NODES + 1)}, NOW - 1.0),
        ({"text": "x" * (MAX_JSON_STRING_CHARS + 1)}, NOW - 1.0),
        ({"text": "\ud800"}, NOW - 1.0),
        ({"status": "PASS", "system_urdf_sha256": "A" * 64}, 10**4999),
    )
    issue_reasons: list[str] = []
    for index, (payload, issued_at) in enumerate(issue_inputs):
        try:
            issue_synthetic_receipt(
                kind="SYSTEM_BINDING_V2",
                action=ACTION_S1,
                context=CONTEXT,
                payload=payload,
                issued_at_unix_s=issued_at,
                expires_at_unix_s=NOW + 30.0,
                nonce=f"VALIDATION_LIMIT_NONCE_{index:02d}",
                evidence_sha256="C" * 64,
                key=SYNTHETIC_KEY,
            )
            public_boundary_pass = False
            issue_reasons.append("UNEXPECTED_ISSUE_ACCEPT")
        except ReceiptError as exc:
            issue_reasons.append(str(exc))

    valid_system_receipt = issue_synthetic_receipt(
        kind="SYSTEM_BINDING_V2",
        action=ACTION_S1,
        context=CONTEXT,
        payload={"status": "PASS", "system_urdf_sha256": "A" * 64},
        issued_at_unix_s=NOW - 1.0,
        expires_at_unix_s=NOW + 30.0,
        nonce="VALIDATION_SURROGATE_BASE_NONCE",
        evidence_sha256="D" * 64,
        key=SYNTHETIC_KEY,
    )
    bad_surrogate_action = dict(ACTION_S1, grasp_candidate_id="\ud800")
    bad_surrogate_context = dict(CONTEXT, target_class="\ud800")
    surrogate_verify_reason = "UNEXPECTED_VERIFY_ACCEPT"
    try:
        verify_receipt(
            valid_system_receipt,
            expected_kind="SYSTEM_BINDING_V2",
            action=ACTION_S1,
            context=bad_surrogate_context,
            trusted_now_unix_s=NOW,
            replay_store=ReplayStore(),
            key=SYNTHETIC_KEY,
        )
        public_boundary_pass = False
    except ReceiptError as exc:
        surrogate_verify_reason = str(exc)
    surrogate_direct_store = ReplayStore()
    surrogate_direct = admit_backend_request(
        "S1",
        shield_receipt_bytes=None,
        action=bad_surrogate_action,
        context=CONTEXT,
        trusted_now_unix_s=NOW,
        replay_store=surrogate_direct_store,
        key=SYNTHETIC_KEY,
    )
    surrogate_join_store = ReplayStore()
    surrogate_join = evaluate_receipt_bound_join(
        "S1",
        receipt_bytes_by_kind={},
        action=ACTION_S1,
        context=bad_surrogate_context,
        trusted_now_unix_s=NOW,
        replay_store=surrogate_join_store,
        key=SYNTHETIC_KEY,
    )
    surrogate_boundaries_pass = (
        surrogate_verify_reason.startswith("INVALID_UTF8_STRING")
        and surrogate_direct.allowed is False
        and surrogate_direct.executed_strategy == "ABORT"
        and surrogate_direct.reason_codes[0].startswith("INVALID_UTF8_STRING")
        and surrogate_direct_store.seen_count == 0
        and surrogate_join.allowed is False
        and surrogate_join.executed_strategy == "ABORT"
        and surrogate_join.reason_codes[0].startswith("INVALID_UTF8_STRING")
        and surrogate_join_store.seen_count == 0
    )
    public_boundary_pass = public_boundary_pass and surrogate_boundaries_pass

    adjacent_pass = (
        loads_strict(b"[" * MAX_JSON_DEPTH + b"0" + b"]" * MAX_JSON_DEPTH) is not None
        and loads_strict(("9" * MAX_JSON_NUMBER_CHARS).encode("ascii")) > 0
        and loads_strict(b"null" + b" " * (MAX_JSON_BYTES - 4)) is None
        and len(loads_strict(b"[" + b",".join([b"0"] * MAX_JSON_COMPLEXITY_UNITS) + b"]"))
        == MAX_JSON_COMPLEXITY_UNITS
        and len(loads_strict(('"' + "a" * MAX_JSON_STRING_CHARS + '"').encode("ascii")))
        == MAX_JSON_STRING_CHARS
        and sum(
            len(item)
            for item in loads_strict(
                ("[" + ",".join(
                    '"' + "a" * MAX_JSON_STRING_CHARS + '"'
                    for _ in range(MAX_JSON_TOTAL_STRING_CHARS // MAX_JSON_STRING_CHARS)
                ) + "]").encode("ascii")
            )
        ) == MAX_JSON_TOTAL_STRING_CHARS
    )
    adjacent_reject_reasons: list[str] = []
    for malformed in (
        b"[" * (MAX_JSON_DEPTH + 1) + b"0" + b"]" * (MAX_JSON_DEPTH + 1),
        ("9" * (MAX_JSON_NUMBER_CHARS + 1)).encode("ascii"),
        b"null" + b" " * (MAX_JSON_BYTES - 3),
        b"[" + b",".join([b"0"] * (MAX_JSON_COMPLEXITY_UNITS + 1)) + b"]",
        ('"' + "a" * (MAX_JSON_STRING_CHARS + 1) + '"').encode("ascii"),
        (
            "["
            + ",".join(
                ['"' + "a" * MAX_JSON_STRING_CHARS + '"']
                * (MAX_JSON_TOTAL_STRING_CHARS // MAX_JSON_STRING_CHARS)
                + ['"b"']
            )
            + "]"
        ).encode("ascii"),
    ):
        try:
            loads_strict(malformed)
            adjacent_pass = False
            adjacent_reject_reasons.append("UNEXPECTED_LIMIT_ACCEPT")
        except StrictJSONError as exc:
            adjacent_reject_reasons.append(str(exc))
    public_boundary_pass = public_boundary_pass and adjacent_pass
    _check(
        checks,
        "PSF-17",
        "bounded strict JSON totality rejects hostile depth, digits, bytes, strings, nodes and UTF-8 at issue/verify/admit/join while adjacent limits pass",
        public_boundary_pass,
        {
            "limits": {
                "bytes": MAX_JSON_BYTES,
                "depth": MAX_JSON_DEPTH,
                "complexity_units": MAX_JSON_COMPLEXITY_UNITS,
                "nodes": MAX_JSON_NODES,
                "string_chars": MAX_JSON_STRING_CHARS,
                "total_string_chars": MAX_JSON_TOTAL_STRING_CHARS,
                "number_chars": MAX_JSON_NUMBER_CHARS,
            },
            "parser_reasons": parser_reasons,
            "issue_reasons": issue_reasons,
            "in_memory_surrogate_action_context_pass": surrogate_boundaries_pass,
            "in_memory_surrogate_verify_reason": surrogate_verify_reason,
            "adjacent_limits_pass": adjacent_pass,
            "adjacent_reject_reasons": adjacent_reject_reasons,
            "denial_nonce_consumption": 0,
        },
    )
    required_false = {field: False for field in FALSE_FIELDS}
    all_pass = all(check["passed"] for check in checks)
    return {
        "schema": "UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_VALIDATION_V1",
        "status": "PASS_SOURCE_FREEZE_ONLY" if all_pass else "FAIL_SOURCE_FREEZE",
        "gate_ceiling": "PASS_SOURCE_FREEZE_ONLY",
        "checks_passed": sum(check["passed"] for check in checks),
        "checks_total": len(checks),
        "checks": checks,
        "dag_inputs": {
            "source_manifest": document_receipt("manifest/PREEXECUTION_BINDING_SECURITY_SOURCE_SHA256_V1.json", committed_manifest),
            "negative_controls": document_receipt("evidence/PREEXECUTION_SECURITY_NEGATIVE_CONTROLS_V1.json", stored_nc),
            "pytest": document_receipt("evidence/PREEXECUTION_SECURITY_PYTEST_RECEIPT_V1.json", pytest_receipt),
        },
        "parent_formal_nc": {"passed": 15, "total": 20, "promoted": 0},
        "additive_effective_source_only_nc": {"passed": 18 if all_pass else 15, "total": 20, "added": ["NC15", "NC16", "NC20"], "holds": ["NC18", "NC19"]},
        "production_credit": False,
        "replay_store_scope": "IN_PROCESS_SYNTHETIC_NONPERSISTENT__NO_PRODUCTION_CREDIT",
        **required_false,
    }


def verify_committed_dag() -> dict[str, Any]:
    """Recompute and bind every committed node without introducing a DAG cycle."""

    manifest = loads_strict(MANIFEST_PATH.read_bytes())
    negative = loads_strict(NEGATIVE_PATH.read_bytes())
    pytest_receipt = loads_strict(PYTEST_PATH.read_bytes())
    committed_validation = loads_strict(VALIDATION_PATH.read_bytes())
    committed_audit = loads_strict(AUDIT_PATH.read_bytes())
    committed_gate = loads_strict(GATE_PATH.read_bytes())
    committed_terminal = loads_strict(TERMINAL_PATH.read_bytes())

    expected_validation = build_validation()
    expected_audit = build_audit()
    expected_gate = build_gate(
        manifest=manifest,
        negative_controls=negative,
        pytest_receipt=pytest_receipt,
        validation=committed_validation,
        independent_audit=committed_audit,
    )
    expected_terminal = build_terminal(expected_gate)
    nodes = {
        "source_manifest": (MANIFEST_PATH, manifest),
        "negative_controls": (NEGATIVE_PATH, negative),
        "pytest": (PYTEST_PATH, pytest_receipt),
        "validation": (VALIDATION_PATH, committed_validation),
        "independent_audit": (AUDIT_PATH, committed_audit),
        "gate": (GATE_PATH, committed_gate),
        "terminal": (TERMINAL_PATH, committed_terminal),
    }
    canonical_nodes = {
        name: path.read_bytes() == frozen_json_bytes(document)
        for name, (path, document) in nodes.items()
    }
    checks = {
        "validation_recomputed_exact": committed_validation == expected_validation,
        "independent_audit_recomputed_exact": committed_audit == expected_audit,
        "gate_recomputed_exact": committed_gate == expected_gate,
        "terminal_recomputed_exact": committed_terminal == expected_terminal,
        "terminal_binds_exact_gate_document": committed_terminal.get("gate")
        == document_receipt(
            "results/UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_SOURCE_FREEZE_GATE_V1.json",
            committed_gate,
        ),
        "all_nodes_canonical_bytes": all(canonical_nodes.values()),
        "gate_ceiling_exact": committed_gate.get("status") == "PASS_SOURCE_FREEZE_ONLY"
        and committed_gate.get("gate_ceiling") == "PASS_SOURCE_FREEZE_ONLY",
        "mandatory_false_in_gate_and_terminal": all(
            committed_gate.get(field) is False and committed_terminal.get(field) is False
            for field in FALSE_FIELDS
        ),
        "formal_credit_and_holds_unchanged": committed_gate.get("parent_formal_nc")
        == {"passed": 15, "total": 20, "promoted": 0}
        and committed_gate.get("additive_effective_source_only_nc", {}).get("passed") == 18
        and committed_gate.get("additive_effective_source_only_nc", {}).get("holds") == ["NC18", "NC19"],
    }
    passed = all(checks.values())
    return {
        "schema": "UNIFIED_R2_SIM13_PREEXECUTION_BINDING_SECURITY_COMMITTED_DAG_VALIDATION_V1",
        "status": "PASS_SOURCE_FREEZE_ONLY" if passed else "FAIL_SOURCE_FREEZE",
        "gate_ceiling": "PASS_SOURCE_FREEZE_ONLY",
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "canonical_nodes": canonical_nodes,
        "terminal_gate_receipt": committed_terminal.get("gate"),
        "production_credit": False,
        **{field: False for field in FALSE_FIELDS},
    }


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments == ["--evidence-node"]:
        output = build_validation()
    elif not arguments:
        output = verify_committed_dag()
    else:
        print("usage: validate_preexecution_security_source_freeze.py [--evidence-node]", file=sys.stderr)
        return 2
    print(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if output["status"] == "PASS_SOURCE_FREEZE_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
