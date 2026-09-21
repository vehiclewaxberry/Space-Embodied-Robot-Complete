#!/usr/bin/env python3
"""Independent raw-byte audit of the readiness package.

This script intentionally does not import the primary readiness module.
"""

from __future__ import annotations

import ast
import hashlib
import json
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from safe_io import EVIDENCE_ROOT, PROJECT_ROOT, secure_read_bytes, write_fixed_json


TOOL_DIR = Path(__file__).resolve().parent
CURRENT = EVIDENCE_ROOT / "PREAUTHORIZATION_READINESS_CURRENT_V1.json"
OUTPUT_NAME = "PREAUTHORIZATION_READINESS_INDEPENDENT_AUDIT_V1.json"
MAIN_SOURCE = TOOL_DIR / "preauthorization_readiness.py"
SOURCE_DIR = (
    PROJECT_ROOT
    / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
    / "unified_r2_digital_prototype_prebind/source_only_v2"
)
TARGETS = {
    "authorization_target": SOURCE_DIR / "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json",
    "run_consumption": SOURCE_DIR / ".unified_r2_v2_run_consumption",
    "override_consumption": SOURCE_DIR / ".unified_r2_v2_override_consumption",
    "active_lock": SOURCE_DIR / ".unified_r2_v2_active_run.lock",
    "interface_instance": (
        PROJECT_ROOT
        / "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind"
        / "interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml"
    ),
}
PINS = {
    "ODR07": (
        PROJECT_ROOT
        / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/terminal_decision_pack"
        / "P2_ROM_DIMENSION_AND_VALIDITY_DECISION_REQUEST_V1.yaml",
        23043,
        "679DC5D2BA2B814F584379C28E47A9F487D03277F0F1EAA45DFB85D150367D25",
    ),
    "ODR08": (
        PROJECT_ROOT
        / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/terminal_decision_pack"
        / "LEGACY_R1_COMPARATOR_SEMANTICS_DECISION_REQUEST_V1.yaml",
        46441,
        "5ED037AE057F7119678DECF890C9C0E64740C1443E5E9B9682FC09B8610046F6",
    ),
    "SOURCE": (SOURCE_DIR / "unified_r2_urdf_source_v2.py", 24599, "64AF651E928986F3492607CA74CE40F15B385357C53DD435C1A66AE6BB7A8E40"),
    "INPUT": (SOURCE_DIR / "UNIFIED_R2_URDF_SOURCE_INPUTS_V2.yaml", 17945, "8DC401FF86F6642DDD47585AD7ECE74F58831E7D3848F3B002BBF2B5952C56F3"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def snapshot_targets() -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, path in TARGETS.items():
        if not path.exists() and not path.is_symlink():
            result[name] = {"state": "ABSENT"}
        elif is_reparse(path):
            result[name] = {"state": "REPARSE_POINT_FAIL_CLOSED"}
        elif path.is_file():
            result[name] = {"state": "FILE", "bytes": path.stat().st_size, "sha256": sha256(path)}
        elif path.is_dir():
            entries = []
            for item in sorted(path.rglob("*"), key=lambda value: value.as_posix()):
                if item.is_file() and not is_reparse(item):
                    entries.append(
                        {
                            "path": item.relative_to(path).as_posix(),
                            "bytes": item.stat().st_size,
                            "sha256": sha256(item),
                        }
                    )
                else:
                    entries.append({"path": item.relative_to(path).as_posix(), "state": "NONFILE_OR_REPARSE"})
            digest = hashlib.sha256(json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()).hexdigest().upper()
            result[name] = {"state": "DIRECTORY", "tree_sha256": digest, "entry_count": len(entries)}
        else:
            result[name] = {"state": "OTHER_FAIL_CLOSED"}
    return result


def add(checks: list[dict[str, Any]], check_id: str, passed: bool, observed: Any) -> None:
    checks.append({"id": check_id, "pass": bool(passed), "observed": observed})


def matches_minimum_frozen_v2_authorization_shape(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    flags = record.get("authority_flags")
    required_true = {
        "rebase_execution_authorized",
        "unified_r2_v2_generation_authorized",
        "system_urdf_generation_authorized",
        "route_c_exclusion_accepted_for_this_sim_candidate",
        "memory_admitted_for_this_execution",
    }
    return (
        record.get("schema") == "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2"
        and record.get("owner_accepted") is True
        and isinstance(flags, dict)
        and all(flags.get(key) is True for key in required_true)
        and flags.get("route_c_cad_authorized") is False
        and all(
            isinstance(record.get(key), str) and bool(record.get(key))
            for key in (
                "run_id",
                "issued_utc",
                "expires_utc",
                "source_sha256",
                "input_sha256",
                "runtime_code_sha256",
            )
        )
    )


def audit() -> dict[str, Any]:
    before = snapshot_targets()
    checks: list[dict[str, Any]] = []
    raw, current_read_meta = secure_read_bytes(CURRENT, allowed_roots=[EVIDENCE_ROOT])
    report = json.loads(raw.decode("utf-8-sig"))
    add(checks, "I01_CURRENT_RAW_BYTES", len(raw) > 0 and sha256(CURRENT) == hashlib.sha256(raw).hexdigest().upper(), {"bytes": len(raw), "sha256": sha256(CURRENT)})
    add(checks, "I02_READINESS_CLASS", report.get("artifact_class") == "READ_ONLY_PREAUTHORIZATION_READINESS__NOT_AUTHORIZATION", report.get("artifact_class"))
    summary = report.get("summary", {})
    add(checks, "I03_CURRENT_DENIAL", summary.get("state") == "DENY_NO_DIRECT_OWNER_SOURCE", summary.get("state"))
    add(checks, "I04_AUTHORITY_NONE", summary.get("authority_effect") == "NONE", summary.get("authority_effect"))
    add(checks, "I05_ALL_RELEASE_FLAGS_FALSE", all(summary.get(key) is False for key in ("execution_authorized", "target_authorization_written", "owner_accepted", "next_stage_authorized", "release_credit")), summary)
    add(checks, "I05A_IDENTITY_UNVERIFIED", summary.get("owner_identity_verified") is False, summary.get("owner_identity_verified"))
    add(checks, "I06_NO_TOP_OWNER_ACCEPTED", "owner_accepted" not in report, sorted(report))
    provenance = report.get("owner_source_provenance", {})
    add(checks, "I07_NO_DIRECT_OWNER_SOURCE", provenance.get("present") is False and provenance.get("raw_bytes_parsed") is False, provenance.get("status"))
    decisions = report.get("decision_readiness", {})
    add(checks, "I08_THREE_INDEPENDENT_DECISIONS", set(decisions) == {"odr_gpt_07", "odr_gpt_08", "c01_unified_r2_research_candidate"}, sorted(decisions))
    add(
        checks,
        "I09_C01_NOT_DERIVED",
        decisions.get("c01_unified_r2_research_candidate", {}).get("source_section_present") is False
        and report.get("checks", {}).get("odr_07_and_08_do_not_imply_c01") is True,
        report.get("checks", {}).get("odr_07_and_08_do_not_imply_c01"),
    )
    for offset, (name, (path, expected_bytes, expected_sha)) in enumerate(PINS.items(), start=10):
        actual_sha = sha256(path) if path.is_file() else None
        add(checks, f"I{offset:02d}_{name}_RAW_PIN", path.is_file() and path.stat().st_size == expected_bytes and actual_sha == expected_sha, {"bytes": path.stat().st_size if path.is_file() else None, "sha256": actual_sha})
    memory = report.get("memory_preview", {})
    add(checks, "I14_MEMORY_GATE_FALSE", memory.get("memory_gate_passed") is False, memory)
    add(checks, "I15_MEMORY_FUTURE_REMEASURE", memory.get("future_execution_must_remeasure") is True, memory.get("future_execution_must_remeasure"))
    runtime = report.get("ephemeral_preview", {}).get("runtime_hash", {})
    add(
        checks,
        "I16_RUNTIME_NOT_COMPUTED_AND_NONREUSABLE",
        runtime.get("preview_only") is True
        and runtime.get("runtime_code_sha256_preview") is None
        and runtime.get("status") == "NOT_COMPUTED_BY_DESIGN_NONAUTHORITATIVE"
        and runtime.get("reusable_by_future_issuer") is False,
        runtime,
    )
    add(checks, "I17_RUNTIME_SAME_INSTANCE_RULE", runtime.get("future_issuer_must_recompute_with_generator_in_same_loaded_instance_and_process") is True, runtime.get("future_issuer_must_recompute_with_generator_in_same_loaded_instance_and_process"))
    add(checks, "I18_NO_FORMAL_SCHEMA_MATCH", report.get("formal_authorization_incompatibility", {}).get("formal_schema_match") is False, report.get("formal_authorization_incompatibility"))
    add(checks, "I19_COPY_CANNOT_SATISFY_TOP_OWNER", report.get("owner_accepted") is not True and summary.get("owner_accepted") is False, {"top": report.get("owner_accepted"), "nested": summary.get("owner_accepted")})
    add(checks, "I20_NO_AUTHORITY_FLAGS_OBJECT", "authority_flags" not in report, "authority_flags" in report)
    source_text = MAIN_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source_text)
    forbidden_call_names = {"gen_" + "urdf", "_" + "build_robot"}
    calls = []
    parser_literals = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.append(node.func.attr)
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            parser_literals.append(node.value)
    add(checks, "I21_AST_NO_GENERATOR_OR_BUILDER_CALL", not forbidden_call_names.intersection(calls), sorted(forbidden_call_names.intersection(calls)))
    allowed_commands = {"audit-current", "assess-owner", "verify-readiness", "self-test"}
    registered_commands = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_parser"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            registered_commands.add(node.args[0].value)
    add(checks, "I22_ONLY_FOUR_CLI_COMMANDS", registered_commands == allowed_commands, sorted(registered_commands))
    add(checks, "I23_NO_FORCE_OR_OUTPUT_OPTION", "--force" not in parser_literals and "--output" not in parser_literals, [value for value in parser_literals if value.startswith("--")])
    output_names = report.get("checks", {})
    add(checks, "I24_REPORT_SAYS_NO_TARGET_WRITE", output_names.get("formal_authorization_target_written") is False and output_names.get("urdf_or_interface_written") is False, output_names)
    add(
        checks,
        "I25_REPORT_ENDPOINTS_OBSERVED_UNCHANGED_WITH_CLAIM_LIMIT",
        report.get("protected_state", {}).get("before") == report.get("protected_state", {}).get("after")
        and report.get("protected_state", {}).get("observed_before_after_unchanged") is True
        and "not proof" in report.get("protected_state", {}).get("claim_limit", ""),
        report.get("protected_state", {}).get("observed_before_after_unchanged"),
    )
    add(checks, "I26_ACTUAL_TARGETS_ABSENT", all(item["state"] == "ABSENT" for item in before.values()), before)
    unwanted = [
        path.relative_to(TOOL_DIR).as_posix()
        for path in TOOL_DIR.rglob("*")
        if path.is_file() and (path.suffix.lower() in {".urdf", ".pyc"} or path.name == ".pytest_cache")
    ]
    add(checks, "I27_NO_URDF_OR_PYC", not unwanted, unwanted)
    after = snapshot_targets()
    add(
        checks,
        "I28_INDEPENDENT_AUDIT_ENDPOINTS_OBSERVED_BEFORE_AFTER_UNCHANGED",
        before == after,
        {"before": before, "after": after, "claim": "observation_not_proof_of_no_transient_write"},
    )
    runtime_nodes = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_runtime_hash_preview"
    ]
    runtime_calls = [node for node in ast.walk(runtime_nodes[0]) if isinstance(node, ast.Call)] if len(runtime_nodes) == 1 else ["MISSING"]
    imported = {
        alias.name.split(".")[0]
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    add(
        checks,
        "I29_RUNTIME_PREVIEW_AST_HAS_NO_IMPORT_COMPILE_OR_EXECUTION_PATH",
        len(runtime_nodes) == 1 and not runtime_calls and not {"importlib", "runpy"}.intersection(imported),
        {"runtime_call_count": len(runtime_calls), "imports": sorted(imported)},
    )
    add(
        checks,
        "I30_CURRENT_SECURE_HANDLE_IDENTITY_STABLE",
        current_read_meta.get("handle_identity_stable") is True
        and current_read_meta.get("parent_directory_handle_stable") is True,
        current_read_meta,
    )
    writer_files = [
        "preauthorization_readiness.py",
        "validate_release.py",
        "independent_audit.py",
        "build_release.py",
    ]
    safe_imports = {}
    for filename in writer_files:
        source_tree = ast.parse((TOOL_DIR / filename).read_text(encoding="utf-8"))
        safe_imports[filename] = any(
            isinstance(node, ast.ImportFrom) and node.module == "safe_io"
            for node in source_tree.body
        )
    add(checks, "I31_ALL_FOUR_WRITERS_IMPORT_COMMON_SAFE_IO", all(safe_imports.values()), safe_imports)
    verification_path = EVIDENCE_ROOT / "PREAUTHORIZATION_READINESS_VERIFICATION_V1.json"
    if verification_path.is_file():
        verification_raw, _ = secure_read_bytes(verification_path, allowed_roots=[EVIDENCE_ROOT])
        verification = json.loads(verification_raw.decode("utf-8-sig"))
    else:
        verification = {}
    add(
        checks,
        "I32_VERIFY_REPORT_STRUCTURAL_AND_LIVE_SPLIT",
        verification.get("structural_passed") is True
        and verification.get("live_readiness_passed") is True
        and verification.get("owner_intents_ready") is False
        and verification.get("owner_identity_verified") is False,
        {
            "structural": verification.get("structural_passed"),
            "live": verification.get("live_readiness_passed"),
            "identity": verification.get("owner_identity_verified"),
            "owner_intents_ready": verification.get("owner_intents_ready"),
        },
    )
    pytest_path = EVIDENCE_ROOT / "PREAUTHORIZATION_READINESS_PYTEST_V1.json"
    if pytest_path.is_file():
        pytest_raw, pytest_meta = secure_read_bytes(pytest_path, allowed_roots=[EVIDENCE_ROOT])
        pytest_evidence = json.loads(pytest_raw.decode("utf-8-sig"))
    else:
        pytest_meta = None
        pytest_evidence = {}
    critical_fragments = {
        "drifted_generator_with_top_level_side_effect",
        "pin_then_source_swap",
        "verify_duplicate_key_raw_bytes",
        "owner_decision_keyset_must_be_exact",
        "actual_junction_or_symlink_root_has_zero_write",
        "readiness_bytes_copied_to_target_name",
        "exact_ready_string_forged_onto_no_source",
        "ready_nested_boolean_drift",
        "ready_decision_state_drift",
        "ready_provenance_required_field_missing",
        "ready_cross_field_hash_drift",
        "deny_no_source_requires_matching_negative_evidence",
    }
    negative_nodeids = pytest_evidence.get("negative_control_nodeids", [])
    add(
        checks,
        "I33_PYTEST_EVIDENCE_INCLUDES_CRITICAL_NEGATIVE_CONTROLS",
        pytest_evidence.get("all_collected_passed") is True
        and pytest_evidence.get("passed_count") == pytest_evidence.get("collected_count")
        and all(any(fragment in nodeid for nodeid in negative_nodeids) for fragment in critical_fragments)
        and isinstance(pytest_meta, dict)
        and pytest_meta.get("handle_identity_stable") is True
        and pytest_meta.get("parent_directory_handle_stable") is True,
        {
            "critical_fragments": sorted(critical_fragments),
            "negative_control_count": len(negative_nodeids),
            "secure_read": pytest_meta,
        },
    )
    schema = json.loads((TOOL_DIR / "PREAUTHORIZATION_READINESS_SCHEMA_V1.json").read_text(encoding="utf-8"))
    object_nodes: list[dict[str, Any]] = []

    def collect_schema_objects(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") == "object":
                object_nodes.append(value)
            for child in value.values():
                collect_schema_objects(child)
        elif isinstance(value, list):
            for child in value:
                collect_schema_objects(child)

    collect_schema_objects(schema)
    add(
        checks,
        "I34_ALL_SCHEMA_OBJECTS_ADDITIONAL_PROPERTIES_FALSE",
        bool(object_nodes) and all(node.get("additionalProperties") is False for node in object_nodes),
        {"object_schema_count": len(object_nodes)},
    )
    report_keys: set[str] = set()

    def collect_report_keys(value: Any) -> None:
        if isinstance(value, dict):
            report_keys.update(str(key) for key in value)
            for child in value.values():
                collect_report_keys(child)
        elif isinstance(value, list):
            for child in value:
                collect_report_keys(child)

    collect_report_keys(report)
    add(
        checks,
        "I35_NO_RUN_OR_OVERRIDE_IDENTIFIER_CREATED",
        "run_id" not in report_keys and "override_id" not in report_keys,
        sorted(key for key in report_keys if key in {"run_id", "override_id"}),
    )
    add(
        checks,
        "I36_READINESS_COPY_CANNOT_MATCH_MINIMUM_FROZEN_V2_AUTHORIZATION_SHAPE",
        not matches_minimum_frozen_v2_authorization_shape(report),
        {
            "readiness_schema": report.get("schema"),
            "formal_shape_match": matches_minimum_frozen_v2_authorization_shape(report),
        },
    )
    add(
        checks,
        "I37_READY_AND_DENY_CROSS_FIELD_SCHEMA_CONDITIONALS_PRESENT",
        isinstance(schema.get("allOf"), list)
        and len(schema.get("allOf")) >= 2
        and {
            "readyProvenanceEvidence",
            "readyOdrEvidence",
            "readyC01Evidence",
            "denyNoSourceProvenanceEvidence",
            "denyNoSourceReportChecksEvidence",
        }.issubset(schema.get("$defs", {})),
        {
            "conditional_count": len(schema.get("allOf", [])),
            "defs_count": len(schema.get("$defs", {})),
        },
    )
    verification_evidence = verification.get("owner_intent_evidence_checks", {})
    add(
        checks,
        "I38_CURRENT_DENY_LIVE_SCOPE_SEPARATED_FROM_OWNER_INTENTS",
        verification.get("structural_passed") is True
        and verification.get("live_readiness_passed") is True
        and verification.get("owner_intents_ready") is False
        and verification.get("owner_identity_verified") is False
        and verification.get("signing_or_execution_ready") is False
        and verification.get("live_readiness_scope")
        == "ARTIFACT_TIME_WINDOW_ONLY__NOT_ISSUER_OR_EXECUTION_READINESS"
        and isinstance(verification_evidence, dict)
        and bool(verification_evidence)
        and not all(verification_evidence.values()),
        {
            "verification_state": verification.get("verification_state"),
            "live_scope": verification.get("live_readiness_scope"),
            "owner_intents_ready": verification.get("owner_intents_ready"),
            "signing_or_execution_ready": verification.get("signing_or_execution_ready"),
        },
    )
    return {
        "schema": "PREAUTHORIZATION_READINESS_INDEPENDENT_AUDIT_V1",
        "artifact_class": "INDEPENDENT_RAW_BYTE_AUDIT__TOOLING_CREDIT_ONLY",
        "independence": {
            "imports_primary_module": False,
            "recomputes_request_and_source_hashes_from_raw_bytes": True,
            "parses_primary_source_ast": True,
        },
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "checks": checks,
        "summary": {
            "passed": all(item["pass"] for item in checks),
            "passed_count": sum(item["pass"] for item in checks),
            "total_count": len(checks),
        },
        "protected_state_before": before,
        "protected_state_after": after,
        "authority_effect": "NONE",
        "execution_authorized": False,
        "target_authorization_written": False,
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


if __name__ == "__main__":
    target_before = snapshot_targets()
    result = audit()
    write_fixed_json(OUTPUT_NAME, result)
    target_after = snapshot_targets()
    if target_before != target_after:
        raise SystemExit("INDEPENDENT_AUDIT_CHANGED_PROTECTED_STATE")
    print(json.dumps(result["summary"], sort_keys=True))
    raise SystemExit(0 if result["summary"]["passed"] else 2)
