#!/usr/bin/env python3
"""Validate the fixed Unified-R2 V2 readiness evidence without promotion."""

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
OUTPUT_NAME = "PREAUTHORIZATION_READINESS_VALIDATION_V1.json"
SCHEMA_PATH = TOOL_DIR / "PREAUTHORIZATION_READINESS_SCHEMA_V1.json"
SOURCE_DIR = (
    PROJECT_ROOT
    / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
    / "unified_r2_digital_prototype_prebind/source_only_v2"
)
TARGET = SOURCE_DIR / "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json"
PROTECTED = [
    TARGET,
    SOURCE_DIR / ".unified_r2_v2_run_consumption",
    SOURCE_DIR / ".unified_r2_v2_override_consumption",
    SOURCE_DIR / ".unified_r2_v2_active_run.lock",
    PROJECT_ROOT
    / "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind"
    / "interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml",
]
EXPECTED_REQUESTS = {
    "ODR-GPT-07": (
        PROJECT_ROOT
        / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/terminal_decision_pack"
        / "P2_ROM_DIMENSION_AND_VALIDITY_DECISION_REQUEST_V1.yaml",
        23043,
        "679DC5D2BA2B814F584379C28E47A9F487D03277F0F1EAA45DFB85D150367D25",
    ),
    "ODR-GPT-08": (
        PROJECT_ROOT
        / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/terminal_decision_pack"
        / "LEGACY_R1_COMPARATOR_SEMANTICS_DECISION_REQUEST_V1.yaml",
        46441,
        "5ED037AE057F7119678DECF890C9C0E64740C1443E5E9B9682FC09B8610046F6",
    ),
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


def add(checks: list[dict[str, Any]], check_id: str, passed: bool, observed: Any) -> None:
    checks.append({"id": check_id, "pass": bool(passed), "observed": observed})


def nested_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(str(key) for key in value)
        for child in value.values():
            keys.update(nested_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(nested_keys(child))
    return keys


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


def validate() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    current_raw, current_read_meta = secure_read_bytes(CURRENT, allowed_roots=[EVIDENCE_ROOT])
    data = json.loads(current_raw.decode("utf-8-sig"))
    add(checks, "V01_CURRENT_EXISTS", CURRENT.is_file() and not is_reparse(CURRENT), str(CURRENT))
    add(checks, "V02_SCHEMA", data.get("schema") == "PREAUTHORIZATION_READINESS_REPORT_V1", data.get("schema"))
    add(
        checks,
        "V03_ARTIFACT_CLASS",
        data.get("artifact_class") == "READ_ONLY_PREAUTHORIZATION_READINESS__NOT_AUTHORIZATION",
        data.get("artifact_class"),
    )
    summary = data.get("summary", {})
    add(checks, "V04_CURRENT_DENY", summary.get("state") == "DENY_NO_DIRECT_OWNER_SOURCE", summary.get("state"))
    add(checks, "V05_AUTHORITY_NONE", summary.get("authority_effect") == "NONE", summary.get("authority_effect"))
    add(checks, "V05A_IDENTITY_UNVERIFIED", summary.get("owner_identity_verified") is False, summary.get("owner_identity_verified"))
    add(checks, "V06_EXECUTION_FALSE", summary.get("execution_authorized") is False, summary.get("execution_authorized"))
    add(
        checks,
        "V07_TARGET_WRITE_FALSE",
        summary.get("target_authorization_written") is False,
        summary.get("target_authorization_written"),
    )
    add(checks, "V08_OWNER_FALSE", summary.get("owner_accepted") is False, summary.get("owner_accepted"))
    add(checks, "V09_NEXT_STAGE_FALSE", summary.get("next_stage_authorized") is False, summary.get("next_stage_authorized"))
    add(checks, "V10_RELEASE_FALSE", summary.get("release_credit") is False, summary.get("release_credit"))
    provenance = data.get("owner_source_provenance", {})
    add(checks, "V11_NO_OWNER_SOURCE", provenance.get("present") is False, provenance.get("present"))
    add(
        checks,
        "V12_NO_OPERATOR_DECISIONS",
        provenance.get("operator_supplied_decisions") is False,
        provenance.get("operator_supplied_decisions"),
    )
    decisions = data.get("decision_readiness", {})
    add(
        checks,
        "V13_ODR07_NOT_READY",
        decisions.get("odr_gpt_07", {}).get("source_section_present") is False,
        decisions.get("odr_gpt_07", {}).get("state"),
    )
    add(
        checks,
        "V14_ODR08_NOT_READY",
        decisions.get("odr_gpt_08", {}).get("source_section_present") is False,
        decisions.get("odr_gpt_08", {}).get("state"),
    )
    add(
        checks,
        "V15_C01_NOT_READY",
        decisions.get("c01_unified_r2_research_candidate", {}).get("source_section_present") is False,
        decisions.get("c01_unified_r2_research_candidate", {}).get("state"),
    )
    add(
        checks,
        "V16_INDEPENDENCE_RULE",
        set(decisions)
        == {"odr_gpt_07", "odr_gpt_08", "c01_unified_r2_research_candidate"}
        and data.get("checks", {}).get("odr_07_and_08_do_not_imply_c01") is True,
        {
            "decision_keys": sorted(decisions),
            "odr_07_and_08_do_not_imply_c01": data.get("checks", {}).get(
                "odr_07_and_08_do_not_imply_c01"
            ),
        },
    )
    for index, (decision_id, (path, expected_bytes, expected_sha)) in enumerate(EXPECTED_REQUESTS.items(), start=17):
        actual = sha256(path) if path.is_file() else None
        passed = path.is_file() and path.stat().st_size == expected_bytes and actual == expected_sha
        add(checks, f"V{index:02d}_{decision_id}_PIN", passed, {"bytes": path.stat().st_size if path.is_file() else None, "sha256": actual})
    pins = data.get("request_bindings", {})
    add(
        checks,
        "V19_REPORT_REQUEST_PINS",
        all(pins.get(key, {}).get("pass") is True for key in EXPECTED_REQUESTS),
        {key: pins.get(key, {}).get("pass") for key in EXPECTED_REQUESTS},
    )
    add(
        checks,
        "V20_SOURCE_PINS",
        all(item.get("pass") is True for item in data.get("frozen_source_bindings", {}).values()),
        data.get("frozen_source_bindings"),
    )
    c01 = data.get("c01_fixed_candidate_contract", {})
    add(checks, "V21_C01_CONFIGURATION", c01.get("configuration") == "C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT", c01.get("configuration"))
    add(checks, "V22_C01_MODE", c01.get("selected_bus_mass_mode") == "EXPLICIT_STRUCTURE_PLUS_RESIDUAL", c01.get("selected_bus_mass_mode"))
    add(checks, "V23_C01_MASS", c01.get("total_design_mass_kg") == 31.022864807342987, c01.get("total_design_mass_kg"))
    add(checks, "V24_ROUTE_C_EXCLUDED", c01.get("route_c_excluded") is True and c01.get("route_c_cad_authorized") is False, {"excluded": c01.get("route_c_excluded"), "cad_authorized": c01.get("route_c_cad_authorized")})
    add(
        checks,
        "V25_PRODUCTION_PERMISSIONS_FALSE",
        all(
            c01.get(key) is False
            for key in (
                "execution_authorized",
                "urdf_write_authorized",
                "sim13_rebind_authorized",
                "production_dynamics_ready",
                "physical_contact_ready",
                "next_stage_authorized",
                "release_credit",
            )
        ),
        {key: c01.get(key) for key in c01 if key.endswith("authorized") or key.endswith("ready") or key == "release_credit"},
    )
    runtime = data.get("ephemeral_preview", {}).get("runtime_hash", {})
    add(
        checks,
        "V26_RUNTIME_NOT_COMPUTED_BY_DESIGN",
        runtime.get("preview_only") is True
        and runtime.get("runtime_code_sha256_preview") is None
        and runtime.get("status") == "NOT_COMPUTED_BY_DESIGN_NONAUTHORITATIVE",
        runtime,
    )
    add(checks, "V27_RUNTIME_NONREUSABLE", runtime.get("reusable_by_future_issuer") is False, runtime.get("reusable_by_future_issuer"))
    add(
        checks,
        "V28_RUNTIME_SAME_INSTANCE_RECOMPUTE",
        runtime.get("future_issuer_must_recompute_with_generator_in_same_loaded_instance_and_process") is True,
        runtime.get("future_issuer_must_recompute_with_generator_in_same_loaded_instance_and_process"),
    )
    memory = data.get("memory_preview", {})
    add(checks, "V29_MEMORY_PREVIEW_ONLY", memory.get("preview_only") is True, memory.get("preview_only"))
    add(checks, "V30_MEMORY_GATE_NOT_PASS", memory.get("memory_gate_passed") is False, memory.get("memory_gate_passed"))
    add(checks, "V31_NO_OVERRIDE_EFFECT", memory.get("owner_override_effect_created") is False, memory.get("owner_override_effect_created"))
    add(checks, "V32_MEMORY_REMEASURE", memory.get("future_execution_must_remeasure") is True, memory.get("future_execution_must_remeasure"))
    protected = data.get("protected_state", {})
    add(
        checks,
        "V33_PROTECTED_REPORT_ENDPOINTS_OBSERVED_UNCHANGED",
        protected.get("observed_before_after_unchanged") is True
        and protected.get("before") == protected.get("after")
        and "not proof" in protected.get("claim_limit", ""),
        protected.get("observed_before_after_unchanged"),
    )
    add(checks, "V34_PROTECTED_ACTUAL_ABSENT", all(not path.exists() and not path.is_symlink() for path in PROTECTED), [str(path) for path in PROTECTED if path.exists() or path.is_symlink()])
    incompatibility = data.get("formal_authorization_incompatibility", {})
    add(checks, "V35_FORMAL_SCHEMA_FALSE", incompatibility.get("formal_schema_match") is False, incompatibility.get("formal_schema_match"))
    add(
        checks,
        "V36_COPY_PROHIBITED",
        incompatibility.get("readiness_report_may_not_be_renamed_or_copied_as_authorization") is True,
        incompatibility.get("readiness_report_may_not_be_renamed_or_copied_as_authorization"),
    )
    forbidden_a = "gen_" + "urdf" + "("
    forbidden_b = "_" + "build_robot" + "("
    python_sources = sorted(TOOL_DIR.rglob("*.py"))
    static_ok = all(forbidden_a not in path.read_text(encoding="utf-8") and forbidden_b not in path.read_text(encoding="utf-8") for path in python_sources)
    add(checks, "V37_NO_GENERATOR_OR_BUILDER_CALL_TOKENS", static_ok, [path.relative_to(TOOL_DIR).as_posix() for path in python_sources])
    main_source = (TOOL_DIR / "preauthorization_readiness.py").read_text(encoding="utf-8")
    add(checks, "V38_NO_FROZEN_AUTH_PATH_SYMBOL", "AUTHORITY" + "_PATH" not in main_source, "static scan")
    add(checks, "V39_NO_FORCE_OR_OUTPUT_OPTION", "--force" not in main_source and "--output" not in main_source, "static scan")
    add(checks, "V40_NO_URDF_IN_TOOL_OR_EVIDENCE", not any(TOOL_DIR.rglob("*.urdf")) and not any(EVIDENCE_ROOT.rglob("*.urdf")), "zero expected")
    try:
        import jsonschema

        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(data)
        schema_valid = True
        schema_error = None
    except Exception as exc:
        schema_valid = False
        schema_error = f"{type(exc).__name__}:{exc}"
    add(checks, "V41_JSON_SCHEMA", schema_valid, schema_error)
    main_tree = ast.parse(main_source)
    runtime_functions = [
        node
        for node in main_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "_runtime_hash_preview"
    ]
    runtime_calls = [node for node in ast.walk(runtime_functions[0]) if isinstance(node, ast.Call)] if len(runtime_functions) == 1 else ["MISSING"]
    imported_modules = {
        alias.name.split(".")[0]
        for node in main_tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    add(
        checks,
        "V42_RUNTIME_PREVIEW_HAS_NO_CODE_EXECUTION_PATH",
        len(runtime_functions) == 1
        and not runtime_calls
        and "importlib" not in imported_modules
        and "runpy" not in imported_modules,
        {"runtime_call_count": len(runtime_calls), "imports": sorted(imported_modules)},
    )
    add(
        checks,
        "V43_SECURE_SINGLE_HANDLE_CURRENT_READ",
        current_read_meta.get("handle_identity_stable") is True
        and current_read_meta.get("parent_directory_handle_stable") is True,
        current_read_meta,
    )
    verification_path = EVIDENCE_ROOT / "PREAUTHORIZATION_READINESS_VERIFICATION_V1.json"
    if verification_path.is_file():
        verification_raw, _ = secure_read_bytes(verification_path, allowed_roots=[EVIDENCE_ROOT])
        verification = json.loads(verification_raw.decode("utf-8-sig"))
    else:
        verification = {}
    add(
        checks,
        "V44_VERIFICATION_STRUCTURAL_AND_LIVE",
        verification.get("structural_passed") is True
        and verification.get("live_readiness_passed") is True
        and verification.get("owner_intents_ready") is False
        and verification.get("owner_identity_verified") is False
        and verification.get("signing_or_execution_ready") is False
        and verification.get("live_readiness_scope")
        == "ARTIFACT_TIME_WINDOW_ONLY__NOT_ISSUER_OR_EXECUTION_READINESS",
        {
            "structural_passed": verification.get("structural_passed"),
            "live_readiness_passed": verification.get("live_readiness_passed"),
            "owner_intents_ready": verification.get("owner_intents_ready"),
            "owner_identity_verified": verification.get("owner_identity_verified"),
            "signing_or_execution_ready": verification.get("signing_or_execution_ready"),
            "live_readiness_scope": verification.get("live_readiness_scope"),
        },
    )
    safe_source = (TOOL_DIR / "safe_io.py").read_text(encoding="utf-8")
    add(
        checks,
        "V45_COMMON_SAFE_IO_FIXED_ROOT",
        "FIXED_OUTPUT_NAMES" in safe_source
        and "EVIDENCE_ROOT_MUST_PREEXIST" in safe_source
        and "OUTPUT_FILENAME_NOT_FIXED_ALLOWLISTED" in safe_source,
        "static safe_io contract",
    )
    pytest_path = EVIDENCE_ROOT / "PREAUTHORIZATION_READINESS_PYTEST_V1.json"
    if pytest_path.is_file():
        pytest_raw, pytest_meta = secure_read_bytes(pytest_path, allowed_roots=[EVIDENCE_ROOT])
        pytest_evidence = json.loads(pytest_raw.decode("utf-8-sig"))
    else:
        pytest_meta = None
        pytest_evidence = {}
    add(
        checks,
        "V46_PYTEST_EVIDENCE_ALL_COLLECTED_PASS_AND_NONAUTHORITATIVE",
        pytest_evidence.get("all_collected_passed") is True
        and pytest_evidence.get("passed_count") == pytest_evidence.get("collected_count")
        and pytest_evidence.get("passed_count", 0) > 0
        and pytest_evidence.get("authority_effect") == "NONE"
        and all(
            pytest_evidence.get(key) is False
            for key in (
                "execution_authorized",
                "target_authorization_written",
                "owner_accepted",
                "next_stage_authorized",
                "release_credit",
            )
        )
        and isinstance(pytest_meta, dict)
        and pytest_meta.get("handle_identity_stable") is True
        and pytest_meta.get("parent_directory_handle_stable") is True,
        {
            "passed_count": pytest_evidence.get("passed_count"),
            "collected_count": pytest_evidence.get("collected_count"),
            "negative_control_count": len(pytest_evidence.get("negative_control_nodeids", [])),
            "secure_read": pytest_meta,
        },
    )
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

    collect_schema_objects(schema if "schema" in locals() else {})
    add(
        checks,
        "V47_ALL_JSON_SCHEMA_OBJECTS_CLOSE_ADDITIONAL_PROPERTIES",
        bool(object_nodes) and all(node.get("additionalProperties") is False for node in object_nodes),
        {"object_schema_count": len(object_nodes)},
    )
    report_keys = nested_keys(data)
    add(
        checks,
        "V48_NO_RUN_OR_OVERRIDE_IDENTIFIER_CREATED",
        "run_id" not in report_keys and "override_id" not in report_keys,
        sorted(key for key in report_keys if key in {"run_id", "override_id"}),
    )
    add(
        checks,
        "V49_READINESS_BYTES_CANNOT_MATCH_MINIMUM_FROZEN_V2_AUTHORIZATION_SHAPE",
        not matches_minimum_frozen_v2_authorization_shape(data),
        {
            "readiness_schema": data.get("schema"),
            "formal_schema_match": matches_minimum_frozen_v2_authorization_shape(data),
        },
    )
    add(
        checks,
        "V50_SCHEMA_HAS_READY_AND_DENY_NO_SOURCE_CROSS_FIELD_CONDITIONALS",
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
            "cross_field_defs_present": sorted(
                key
                for key in schema.get("$defs", {})
                if key.startswith("ready") or key.startswith("denyNoSource")
            ),
        },
    )
    verification_evidence = verification.get("owner_intent_evidence_checks", {})
    add(
        checks,
        "V51_CURRENT_DENY_OWNER_EVIDENCE_CONJUNCTION_FALSE",
        isinstance(verification_evidence, dict)
        and bool(verification_evidence)
        and not all(verification_evidence.values())
        and verification.get("owner_intents_ready") is False,
        {
            "false_owner_evidence_checks": sorted(
                key for key, value in verification_evidence.items() if value is not True
            ),
            "owner_intents_ready": verification.get("owner_intents_ready"),
        },
    )
    return {
        "schema": "PREAUTHORIZATION_READINESS_VALIDATION_V1",
        "artifact_class": "READ_ONLY_VALIDATION__TOOLING_CREDIT_ONLY",
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "input": {
            "path": CURRENT.relative_to(PROJECT_ROOT).as_posix(),
            "bytes": CURRENT.stat().st_size,
            "sha256": sha256(CURRENT),
        },
        "checks": checks,
        "summary": {
            "passed": all(item["pass"] for item in checks),
            "passed_count": sum(item["pass"] for item in checks),
            "total_count": len(checks),
            "gate_credit": "PREAUTHORIZATION_READINESS_TOOLING_ONLY",
        },
        "authority_effect": "NONE",
        "execution_authorized": False,
        "target_authorization_written": False,
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


if __name__ == "__main__":
    result = validate()
    write_fixed_json(OUTPUT_NAME, result)
    print(json.dumps(result["summary"], sort_keys=True))
    raise SystemExit(0 if result["summary"]["passed"] else 2)
