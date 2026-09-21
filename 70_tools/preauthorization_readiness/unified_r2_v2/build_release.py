#!/usr/bin/env python3
"""Build the acyclic evidence manifest and tooling-only readiness Gate."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from safe_io import EVIDENCE_ROOT, PROJECT_ROOT, secure_read_bytes, sha256_bytes, write_fixed_json


TOOL_DIR = Path(__file__).resolve().parent
MANIFEST_NAME = "PREAUTHORIZATION_READINESS_ACYCLIC_MANIFEST_V1.json"
GATE_NAME = "PREAUTHORIZATION_READINESS_GATE_V1.json"
PYTEST_NAME = "PREAUTHORIZATION_READINESS_PYTEST_V1.json"
MANIFEST = EVIDENCE_ROOT / MANIFEST_NAME
GATE = EVIDENCE_ROOT / GATE_NAME
SOURCE_DIR = (
    PROJECT_ROOT
    / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"
    / "unified_r2_digital_prototype_prebind/source_only_v2"
)
PROTECTED = [
    SOURCE_DIR / "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json",
    SOURCE_DIR / ".unified_r2_v2_run_consumption",
    SOURCE_DIR / ".unified_r2_v2_override_consumption",
    SOURCE_DIR / ".unified_r2_v2_active_run.lock",
    PROJECT_ROOT
    / "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind"
    / "interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml",
]
REQUESTS_RAW = [
    PROJECT_ROOT
    / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/terminal_decision_pack"
    / "P2_ROM_DIMENSION_AND_VALIDITY_DECISION_REQUEST_V1.yaml",
    PROJECT_ROOT
    / "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/terminal_decision_pack"
    / "LEGACY_R1_COMPARATOR_SEMANTICS_DECISION_REQUEST_V1.yaml",
]


def sha256(path: Path) -> str:
    return sha256_bytes(read_stable(path))


def read_stable(path: Path) -> bytes:
    root = EVIDENCE_ROOT if path.absolute().is_relative_to(EVIDENCE_ROOT.absolute()) else PROJECT_ROOT
    payload, _ = secure_read_bytes(path, allowed_roots=[root], max_bytes=2 * 1024 * 1024)
    return payload


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def run(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return {"args": args, "returncode": completed.returncode, "output": completed.stdout.strip()}


def load(name: str) -> dict[str, Any]:
    return json.loads(read_stable(EVIDENCE_ROOT / name).decode("utf-8-sig"))


def manifest_entry(path: Path, role: str) -> dict[str, Any]:
    raw = read_stable(path)
    return {
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "role": role,
        "bytes": len(raw),
        "sha256": sha256_bytes(raw),
    }


def graph_is_acyclic(edges: list[dict[str, str]]) -> tuple[bool, list[str]]:
    nodes = set()
    outgoing: dict[str, set[str]] = {}
    indegree: dict[str, int] = {}
    for edge in edges:
        source = edge["source"]
        consumer = edge["consumer"]
        nodes.update((source, consumer))
        outgoing.setdefault(source, set()).add(consumer)
    for node in nodes:
        indegree[node] = 0
    for destinations in outgoing.values():
        for destination in destinations:
            indegree[destination] += 1
    queue = sorted(node for node, degree in indegree.items() if degree == 0)
    order: list[str] = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for destination in sorted(outgoing.get(node, set())):
            indegree[destination] -= 1
            if indegree[destination] == 0:
                queue.append(destination)
                queue.sort()
    return len(order) == len(nodes), order


def main() -> int:
    protected_before = {str(path): path.exists() or path.is_symlink() for path in PROTECTED}
    python = sys.executable
    commands = {
        "audit_current": run([python, "-B", str(TOOL_DIR / "preauthorization_readiness.py"), "audit-current"]),
        "self_test": run([python, "-B", str(TOOL_DIR / "preauthorization_readiness.py"), "self-test"]),
        "pytest": run(
            [
                python,
                "-B",
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                str(TOOL_DIR / "tests"),
            ]
        ),
        "pytest_collect": run(
            [
                python,
                "-B",
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                "-p",
                "no:cacheprovider",
                str(TOOL_DIR / "tests"),
            ]
        ),
    }
    collected_nodeids = [
        line.strip()
        for line in commands["pytest_collect"]["output"].splitlines()
        if "::test_" in line
    ]
    match = re.search(r"(\d+) passed", commands["pytest"]["output"])
    test_count = int(match.group(1)) if match else 0
    negative_keywords = (
        "reject",
        "deny",
        "fail",
        "drift",
        "mismatch",
        "missing",
        "duplicate",
        "stale",
        "future",
        "expired",
        "reparse",
        "symlink",
        "swap",
        "prohibited",
        "cannot_match",
        "cannot",
        "conflict",
        "must_be_exact",
        "requires",
        "absent",
        "not_",
        "no_",
        "zero_write",
    )
    negative_nodeids = [
        nodeid for nodeid in collected_nodeids if any(keyword in nodeid.lower() for keyword in negative_keywords)
    ]
    pytest_evidence = {
        "schema": "PREAUTHORIZATION_READINESS_PYTEST_V1",
        "artifact_class": "INDEPENDENT_PYTEST_EXECUTION_EVIDENCE__TOOLING_ONLY",
        "generated_utc": utc_now(),
        "command": commands["pytest"]["args"],
        "collect_command": commands["pytest_collect"]["args"],
        "returncode": commands["pytest"]["returncode"],
        "collect_returncode": commands["pytest_collect"]["returncode"],
        "passed_count": test_count,
        "collected_count": len(collected_nodeids),
        "all_collected_passed": commands["pytest"]["returncode"] == 0
        and commands["pytest_collect"]["returncode"] == 0
        and test_count == len(collected_nodeids)
        and test_count > 0,
        "collected_nodeids": collected_nodeids,
        "negative_control_nodeids": negative_nodeids,
        "negative_control_count": len(negative_nodeids),
        "pytest_output": commands["pytest"]["output"],
        "pytest_output_sha256": sha256_bytes(commands["pytest"]["output"].encode("utf-8")),
        "authority_effect": "NONE",
        "execution_authorized": False,
        "target_authorization_written": False,
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    write_fixed_json(PYTEST_NAME, pytest_evidence)
    commands["verify"] = run(
        [
            python,
            "-B",
            str(TOOL_DIR / "preauthorization_readiness.py"),
            "verify-readiness",
            str(EVIDENCE_ROOT / "PREAUTHORIZATION_READINESS_CURRENT_V1.json"),
        ]
    )
    commands["validator"] = run([python, "-B", str(TOOL_DIR / "validate_release.py")])
    commands["independent_audit"] = run([python, "-B", str(TOOL_DIR / "independent_audit.py")])

    current = load("PREAUTHORIZATION_READINESS_CURRENT_V1.json")
    self_test = load("PREAUTHORIZATION_READINESS_SELF_TEST_V1.json")
    verification = load("PREAUTHORIZATION_READINESS_VERIFICATION_V1.json")
    validation = load("PREAUTHORIZATION_READINESS_VALIDATION_V1.json")
    independent = load("PREAUTHORIZATION_READINESS_INDEPENDENT_AUDIT_V1.json")
    protected_after_commands = {str(path): path.exists() or path.is_symlink() for path in PROTECTED}

    artifact_paths = [
        (TOOL_DIR / "preauthorization_readiness.py", "PRIMARY_READ_ONLY_TOOL"),
        (TOOL_DIR / "safe_io.py", "COMMON_FIXED_BOUNDARY_SAFE_IO"),
        (TOOL_DIR / "PREAUTHORIZATION_READINESS_SCHEMA_V1.json", "READINESS_SCHEMA_NOT_AUTHORIZATION_SCHEMA"),
        (TOOL_DIR / "README.md", "BOUNDARY_AND_REPRODUCTION_GUIDE"),
        (TOOL_DIR / "validate_release.py", "PRIMARY_VALIDATOR"),
        (TOOL_DIR / "independent_audit.py", "INDEPENDENT_RAW_BYTE_AUDITOR"),
        (TOOL_DIR / "build_release.py", "ACYCLIC_RELEASE_BUILDER"),
        (TOOL_DIR / "tests/test_readiness.py", "NEGATIVE_AND_POSITIVE_READINESS_TESTS"),
        (REQUESTS_RAW[0], "ODR07_REQUEST_RAW_PIN"),
        (REQUESTS_RAW[1], "ODR08_REQUEST_RAW_PIN"),
        (SOURCE_DIR / "unified_r2_urdf_source_v2.py", "FROZEN_GENERATOR_SOURCE_RAW_PIN_NOT_EXECUTED"),
        (SOURCE_DIR / "UNIFIED_R2_URDF_SOURCE_INPUTS_V2.yaml", "FROZEN_GENERATOR_INPUT_RAW_PIN"),
        (EVIDENCE_ROOT / "PREAUTHORIZATION_READINESS_CURRENT_V1.json", "CANONICAL_CURRENT_DENIAL"),
        (EVIDENCE_ROOT / "PREAUTHORIZATION_READINESS_SELF_TEST_V1.json", "BOUNDED_SELF_TEST"),
        (EVIDENCE_ROOT / "PREAUTHORIZATION_READINESS_VERIFICATION_V1.json", "READINESS_REPORT_VERIFICATION"),
        (EVIDENCE_ROOT / "PREAUTHORIZATION_READINESS_VALIDATION_V1.json", "PRIMARY_VALIDATION"),
        (EVIDENCE_ROOT / "PREAUTHORIZATION_READINESS_INDEPENDENT_AUDIT_V1.json", "INDEPENDENT_AUDIT"),
        (EVIDENCE_ROOT / PYTEST_NAME, "PYTEST_AND_NEGATIVE_CONTROL_EVIDENCE"),
    ]
    entries = [manifest_entry(path, role) for path, role in artifact_paths]
    edges = [
        {"source": "ODR07_REQUEST_RAW_BYTES", "consumer": "CURRENT_REPORT"},
        {"source": "ODR08_REQUEST_RAW_BYTES", "consumer": "CURRENT_REPORT"},
        {"source": "FROZEN_GENERATOR_SOURCE_RAW_BYTES", "consumer": "CURRENT_REPORT"},
        {"source": "FROZEN_GENERATOR_INPUT_RAW_BYTES", "consumer": "CURRENT_REPORT"},
        {"source": "PRIMARY_TOOL", "consumer": "CURRENT_REPORT"},
        {"source": "CURRENT_REPORT", "consumer": "VERIFICATION"},
        {"source": "CURRENT_REPORT", "consumer": "PRIMARY_VALIDATION"},
        {"source": "READINESS_SCHEMA", "consumer": "PRIMARY_VALIDATION"},
        {"source": "CURRENT_REPORT", "consumer": "INDEPENDENT_AUDIT"},
        {"source": "PRIMARY_TOOL", "consumer": "INDEPENDENT_AUDIT"},
        {"source": "TEST_SOURCE_RAW_BYTES", "consumer": "PYTEST_RESULT"},
        {"source": "PYTEST_RESULT", "consumer": "ACYCLIC_MANIFEST"},
        {"source": "CURRENT_REPORT", "consumer": "ACYCLIC_MANIFEST"},
        {"source": "SELF_TEST", "consumer": "ACYCLIC_MANIFEST"},
        {"source": "VERIFICATION", "consumer": "ACYCLIC_MANIFEST"},
        {"source": "PRIMARY_VALIDATION", "consumer": "ACYCLIC_MANIFEST"},
        {"source": "INDEPENDENT_AUDIT", "consumer": "ACYCLIC_MANIFEST"},
        {"source": "ACYCLIC_MANIFEST", "consumer": "TOOLING_GATE"},
    ]
    edges.extend(
        {"source": f"PYTEST_CASE::{nodeid}", "consumer": "PYTEST_RESULT"}
        for nodeid in collected_nodeids
    )
    acyclic, topological_order = graph_is_acyclic(edges)
    manifest = {
        "schema": "PREAUTHORIZATION_READINESS_ACYCLIC_MANIFEST_V1",
        "artifact_class": "ACYCLIC_SHA256_MANIFEST__TOOLING_ONLY",
        "generated_utc": utc_now(),
        "hash_algorithm": "SHA-256",
        "self_reference_policy": "MANIFEST_SELF_EXCLUDED",
        "gate_reference_policy": "GATE_EXCLUDED_AND_GENERATED_AFTER_MANIFEST",
        "entries": entries,
        "dependency_graph": {
            "edge_semantics": "source_to_consumer",
            "edges": edges,
            "acyclic": acyclic,
            "topological_order": topological_order,
        },
        "authority_effect": "NONE",
        "execution_authorized": False,
        "target_authorization_written": False,
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    write_fixed_json(MANIFEST_NAME, manifest)

    no_unwanted = not any(
        path.is_file() and path.suffix.lower() in {".urdf", ".pyc"}
        for root in (TOOL_DIR, EVIDENCE_ROOT)
        for path in root.rglob("*")
    ) and not any(path.name in {"__pycache__", ".pytest_cache"} for path in TOOL_DIR.rglob("*"))
    critical_negative_fragments = {
        "drifted_generator_with_top_level_side_effect",
        "pin_then_source_swap",
        "verify_duplicate_key_raw_bytes",
        "owner_decision_keyset_must_be_exact",
        "actual_junction_or_symlink_root_has_zero_write",
        "low_memory_requires_exact_ack",
        "readiness_bytes_copied_to_target_name",
        "exact_ready_string_forged_onto_no_source",
        "ready_nested_boolean_drift",
        "ready_decision_state_drift",
        "ready_provenance_required_field_missing",
        "ready_cross_field_hash_drift",
        "deny_no_source_requires_matching_negative_evidence",
    }
    runtime = current.get("ephemeral_preview", {}).get("runtime_hash", {})
    checks = {
        "all_subprocesses_return_zero": all(item["returncode"] == 0 for item in commands.values()),
        "pytest_all_collected_pass": pytest_evidence["all_collected_passed"],
        "pytest_negative_controls_registered": len(negative_nodeids) >= 20,
        "pytest_critical_negative_controls_registered": all(
            any(fragment in nodeid for nodeid in negative_nodeids)
            for fragment in critical_negative_fragments
        ),
        "current_state_exact_denial": current.get("summary", {}).get("state") == "DENY_NO_DIRECT_OWNER_SOURCE",
        "current_authority_effect_none": current.get("summary", {}).get("authority_effect") == "NONE",
        "all_current_release_and_execution_flags_false": all(
            current.get("summary", {}).get(key) is False
            for key in (
                "execution_authorized",
                "target_authorization_written",
                "owner_accepted",
                "next_stage_authorized",
                "release_credit",
            )
        ),
        "current_owner_identity_unverified": current.get("summary", {}).get("owner_identity_verified")
        is False,
        "self_test_pass": self_test.get("summary", {}).get("passed") is True,
        "current_deny_artifact_structural_and_time_window_valid_but_owner_intents_not_ready": verification.get("structural_passed") is True
        and verification.get("live_readiness_passed") is True
        and verification.get("owner_intents_ready") is False
        and verification.get("owner_identity_verified") is False
        and verification.get("signing_or_execution_ready") is False
        and verification.get("live_readiness_scope")
        == "ARTIFACT_TIME_WINDOW_ONLY__NOT_ISSUER_OR_EXECUTION_READINESS",
        "primary_validation_all_pass": validation.get("summary", {}).get("passed") is True
        and validation.get("summary", {}).get("passed_count") == validation.get("summary", {}).get("total_count"),
        "independent_audit_all_pass": independent.get("summary", {}).get("passed") is True
        and independent.get("summary", {}).get("passed_count") == independent.get("summary", {}).get("total_count"),
        "protected_endpoints_observed_absent_before_and_after": not any(protected_before.values())
        and protected_before == protected_after_commands,
        "no_urdf_pyc_or_cache": no_unwanted,
        "manifest_is_acyclic": acyclic,
        "manifest_self_excluded": all(entry["path"] != MANIFEST.relative_to(PROJECT_ROOT).as_posix() for entry in entries),
        "gate_excluded_from_manifest": all(entry["path"] != GATE.relative_to(PROJECT_ROOT).as_posix() for entry in entries),
        "memory_gate_not_claimed_pass": current.get("memory_preview", {}).get("memory_gate_passed") is False,
        "runtime_hash_not_computed_and_generator_never_loaded": runtime.get("runtime_code_sha256_preview") is None
        and runtime.get("status") == "NOT_COMPUTED_BY_DESIGN_NONAUTHORITATIVE"
        and runtime.get("reusable_by_future_issuer") is False
        and all(
            runtime.get(key) is False
            for key in (
                "generator_source_loaded",
                "generator_source_imported",
                "generator_source_compiled",
                "generator_source_executed",
            )
        ),
        "no_run_or_override_identifier_created": "run_id" not in current.get("ephemeral_preview", {})
        and "override_id" not in current.get("memory_preview", {}),
        "formal_authorization_schema_match_false": current.get("formal_authorization_incompatibility", {}).get("formal_schema_match")
        is False,
    }
    passed = all(checks.values())
    gate = {
        "schema": "PREAUTHORIZATION_READINESS_GATE_V1",
        "artifact_class": "TOOLING_READINESS_GATE__NOT_EXECUTION_AUTHORIZATION",
        "generated_utc": utc_now(),
        "gate": (
            "PASS_PREAUTHORIZATION_READINESS_TOOLING_WITH_EXECUTION_DENIED"
            if passed
            else "FAIL_PREAUTHORIZATION_READINESS_TOOLING__EXECUTION_DENIED"
        ),
        "checks": checks,
        "test_result": {
            "passed": pytest_evidence["all_collected_passed"],
            "passed_count": test_count,
            "total_count": len(collected_nodeids),
            "negative_control_count": len(negative_nodeids),
            "evidence_path": (EVIDENCE_ROOT / PYTEST_NAME).relative_to(PROJECT_ROOT).as_posix(),
            "evidence_sha256": sha256(EVIDENCE_ROOT / PYTEST_NAME),
            "all_test_case_nodes_bound_into_manifest_dag": len(collected_nodeids) == test_count,
        },
        "primary_validation": validation["summary"],
        "independent_audit": independent["summary"],
        "manifest": {
            "path": MANIFEST.relative_to(PROJECT_ROOT).as_posix(),
            "bytes": MANIFEST.stat().st_size,
            "sha256": sha256(MANIFEST),
            "acyclic": acyclic,
        },
        "current_audit_state": current["summary"]["state"],
        "verification": {
            "structural_passed": verification.get("structural_passed"),
            "live_readiness_passed": verification.get("live_readiness_passed"),
            "owner_intents_ready": verification.get("owner_intents_ready"),
            "owner_identity_verified": verification.get("owner_identity_verified"),
            "signing_or_execution_ready": verification.get("signing_or_execution_ready"),
            "live_readiness_scope": verification.get("live_readiness_scope"),
        },
        "protected_endpoint_observation_limit": (
            "Before/after equality is an observation, not proof of no transient write; no-generation credit also "
            "depends on the absent generator execution path, static call audit, and side-effect negative controls."
        ),
        "credit": {
            "tooling_readiness": passed,
            "owner_decision_credit": False,
            "engineering_or_scientific_gate_credit": False,
            "execution_credit": False,
            "release_credit": False,
        },
        "authority_effect": "NONE",
        "execution_authorized": False,
        "target_authorization_written": False,
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "unchanged_holds": [
            "UNIFIED_R2_V2_EXECUTION_AUTHORIZATION_ABSENT",
            "OWNER_DIRECT_SOURCE_ABSENT",
            "SYSTEM_URDF_NOT_GENERATED",
            "MECH_RL_SYSTEM_INTERFACE_V2_NOT_INSTANTIATED",
            "SIM13_REBIND_NOT_AUTHORIZED",
            "PRODUCTION_DYNAMICS_AND_CONTACT_HOLD",
        ],
    }
    write_fixed_json(GATE_NAME, gate)
    protected_final = {str(path): path.exists() or path.is_symlink() for path in PROTECTED}
    if protected_final != protected_before:
        raise RuntimeError("BUILD_CHANGED_PROTECTED_TARGET_OR_RUNTIME_STATE")
    print(
        json.dumps(
            {
                "gate": gate["gate"],
                "tests": f"{test_count}/{len(collected_nodeids)}",
                "validation": f"{validation['summary']['passed_count']}/{validation['summary']['total_count']}",
                "independent_audit": f"{independent['summary']['passed_count']}/{independent['summary']['total_count']}",
                "current_state": current["summary"]["state"],
            },
            sort_keys=True,
        )
    )
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
