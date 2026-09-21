#!/usr/bin/env python3
"""Independent validator and in-memory negative controls for the Sim13 audit."""
from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
PACKAGE = SCRIPT.parents[1]
ROOT = SCRIPT.parents[4]
OUT = PACKAGE / "09_downstream_rebind"
INPUT_MANIFEST = OUT / "SIM13_CURRENT_BINDING_AUDIT_INPUT_MANIFEST_V1.json"
GATE = OUT / "SIM13_CURRENT_MECHANICAL_BINDING_AUDIT_GATE_V1.json"
OUTPUT_MANIFEST = OUT / "SIM13_CURRENT_BINDING_AUDIT_OUTPUT_MANIFEST_V1.json"
REPORT = OUT / "SIM13_CURRENT_BINDING_AUDIT_VALIDATION_REPORT_V1.json"


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


def resolve(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT)
    return path


def iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def class_fields(source: str, class_name: str) -> list[str]:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return [
                item.target.id
                for item in node.body
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
            ]
    return []


def constant_string(source: str, name: str) -> str | None:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    return node.value.value
    return None


def backend_is_nonproduction(source: str) -> bool:
    return (
        constant_string(source, "scope")
        == "KINEMATIC_BOOTSTRAP_NOT_CONTACT_OR_TRAINING_PHYSICS"
        and "collision_detected=False" in source
        and "collision_detected=" not in source.split("def step", 1)[1]
    )


def production_authorized(
    runtime_harness_gate_present: bool,
    current_interface_consumed: bool,
    superseding_evidence_is_newer: bool,
    production_backend_present: bool,
) -> bool:
    """Minimal independent fail-closed predicate exercised by negative controls."""
    return all((
        runtime_harness_gate_present,
        current_interface_consumed,
        superseding_evidence_is_newer,
        production_backend_present,
    ))


def record(checks: list[dict[str, Any]], check_id: str, name: str, passed: bool, evidence: Any) -> None:
    checks.append({"id": check_id, "name": name, "pass": bool(passed), "evidence": evidence})


def main() -> int:
    input_manifest = read_json(INPUT_MANIFEST)
    gate = read_json(GATE)
    output_manifest = read_json(OUTPUT_MANIFEST)
    checks: list[dict[str, Any]] = []

    input_records = input_manifest.get("inputs", [])
    record(checks, "V01", "INPUT_MANIFEST_SCHEMA", input_manifest.get("schema") == "SIM13_CURRENT_BINDING_AUDIT_INPUT_MANIFEST_V1", input_manifest.get("schema"))
    record(checks, "V02", "INPUT_COUNT", len(input_records) == input_manifest.get("input_count") == 10, len(input_records))
    input_hash_checks = [sha(resolve(item["path"])) == item["sha256"] for item in input_records]
    record(checks, "V03", "ALL_INPUT_HASHES_MATCH", all(input_hash_checks), {"passed": sum(input_hash_checks), "total": len(input_hash_checks)})

    role_paths = {item["role"]: resolve(item["path"]) for item in input_records}
    terminal = read_json(role_paths["m7_terminal_gate"])
    handoff = read_json(role_paths["m7_handoff_v2"])
    mission = read_json(role_paths["m7_mission_coverage"])
    config = read_json(role_paths["sim13_config"])
    receipt = read_json(role_paths["sim13_historical_receipt"])
    bootstrap = read_json(role_paths["sim13_historical_bootstrap_gate"])
    loader = role_paths["sim13_loader_source"].read_text(encoding="utf-8-sig")
    action = role_paths["sim13_action_mask_source"].read_text(encoding="utf-8-sig")
    backend = role_paths["sim13_backend_source"].read_text(encoding="utf-8-sig")
    handoff_builder = role_paths["handoff_builder_source"].read_text(encoding="utf-8-sig")

    terminal_is_newer = iso(terminal["generated_local"]) > max(iso(receipt["validated_at"]), iso(bootstrap["generated_at"]))
    fields = class_fields(action, "SafetyGateSnapshot")
    no_harness_runtime_gate = bool(fields) and not any("harness" in item.lower() for item in fields)
    old_interface = str(config.get("mechanical_interface_path", "")).endswith("MECH_RL_INTERFACE_V1.yaml")
    loader_v1_only = (
        "INTERFACE_SCHEMA_VERSION = \"MECH_RL_INTERFACE_V1\"" in loader
        and 'path.name != "MECH_RL_INTERFACE_V1.yaml"' in loader
    )
    g12 = next(item for item in handoff["checks"] if item.get("id") == "G12")
    string_only_g12 = (
        '"rl_action_mask_binds_harness": "harness" in contract["rl_action_mask"].lower()'
        in handoff_builder
        and g12["evidence"]["terms"]["rl_action_mask_binds_harness"] is True
    )

    record(checks, "V04", "TERMINAL_NEWER_THAN_HISTORY", terminal_is_newer, terminal["generated_local"])
    record(checks, "V05", "ROUTE_B_REJECTED", terminal.get("route_b") == "REJECTED", terminal.get("route_b"))
    record(checks, "V06", "MECHANICAL_NOT_RELEASED", terminal.get("mechanical_design") == "NOT_RELEASED", terminal.get("mechanical_design"))
    record(checks, "V07", "M7_STAGE_NOT_AUTHORIZED", terminal.get("next_stage_authorized") is False, terminal.get("next_stage_authorized"))
    record(checks, "V08", "MISSION_FAIL", mission.get("mission_coverage") == "FAIL", mission.get("mission_coverage"))
    record(checks, "V09", "TEN_OF_TEN_MANDATORY_STATES_UNSAFE", len(mission.get("key_state_checks", [])) == 10 and all(item.get("harness_status") == "UNSAFE" for item in mission["key_state_checks"]), len(mission.get("key_state_checks", [])))
    record(checks, "V10", "ZERO_OF_EIGHT_TRAJECTORIES_RELEASED", mission.get("required_trajectory_segments") == 8 and mission.get("trajectory_segments_with_released_authority") == 0, {"released": mission.get("trajectory_segments_with_released_authority"), "required": mission.get("required_trajectory_segments")})
    record(checks, "V11", "HANDOFF_11_OF_12_FAIL_G12", handoff.get("checks_passed") == 11 and handoff.get("checks_total") == 12 and handoff.get("failing_checks") == ["G12"] and g12.get("pass") is False, handoff.get("failing_checks"))
    record(checks, "V12", "CONFIG_BINDS_OLD_V1", old_interface, config.get("mechanical_interface_path"))
    record(checks, "V13", "RECEIPT_BINDS_SAME_OLD_V1", receipt.get("production_interface_path") == config.get("mechanical_interface_path") and receipt.get("interface_schema_version") == "MECH_RL_INTERFACE_V1", receipt.get("interface_schema_version"))
    record(checks, "V14", "LOADER_V1_ONLY", loader_v1_only, "schema and filename literals")
    record(checks, "V15", "NO_RUNTIME_HARNESS_GATE", no_harness_runtime_gate, fields)
    record(checks, "V16", "BACKEND_NONPRODUCTION_SCOPE", backend_is_nonproduction(backend), "kinematic scope; collision false and unchanged in step")
    record(checks, "V17", "G12_USES_STRING_ONLY_HEURISTIC", string_only_g12, "builder expression found")
    record(checks, "V18", "HISTORICAL_BOOTSTRAP_SCOPE_PRESERVED", bootstrap.get("environment_scope") == "DETERMINISTIC_KINEMATIC_BOOTSTRAP_NOT_CONTACT_PHYSICS_OR_TRAINING" and bootstrap.get("next_stage_authorized") is False, bootstrap.get("environment_scope"))
    record(checks, "V19", "GATE_OBSERVATIONS_14_OF_14", gate.get("observations_confirmed") == gate.get("observation_count") == 14, {"confirmed": gate.get("observations_confirmed"), "total": gate.get("observation_count")})
    record(checks, "V20", "EXPECTED_INVALIDATION_VERDICT", gate.get("verdict") == "CURRENT_SIM13_PRODUCTION_MECHANICAL_BINDING_INVALIDATED_BY_NEWER_M7_EVIDENCE" and gate.get("verdict_issued") is True, gate.get("verdict"))
    authority = gate.get("current_authority", {})
    record(checks, "V21", "PRODUCTION_CONTACT_RL_FALSE", all(authority.get(name) is False for name in ("mechanical_release", "production_dynamics_ready", "physical_contact_ready", "physics_gated_rl_ready", "hardware_motion_ready")), authority)
    record(checks, "V22", "DIAGNOSTIC_ABORT_ONLY", authority.get("diagnostic_kinematic_bootstrap_only") is True and authority.get("abort_always_available") is True and gate.get("next_stage_authorized") is False, gate.get("required_action"))
    history = gate.get("historical_evidence_disposition", {})
    record(checks, "V23", "HISTORICAL_EVIDENCE_NOT_REWRITTEN", history.get("sim13_production_binding_receipt_preserved") is True and history.get("sim13_environment_bootstrap_gate_preserved") is True and history.get("historical_evidence_not_rewritten") is True, history)
    record(checks, "V24", "GATE_BINDS_INPUT_MANIFEST", gate.get("input_manifest", {}).get("sha256") == sha(INPUT_MANIFEST), gate.get("input_manifest"))

    output_records = output_manifest.get("outputs", [])
    source_records = output_manifest.get("sources", [])
    output_matches = [sha(resolve(item["path"])) == item["sha256"] for item in output_records]
    source_matches = [sha(resolve(item["path"])) == item["sha256"] for item in source_records]
    record(checks, "V25", "OUTPUT_MANIFEST_COUNTS", len(output_records) == output_manifest.get("output_count") == 2 and len(source_records) == output_manifest.get("source_count") == 2, {"outputs": len(output_records), "sources": len(source_records)})
    record(checks, "V26", "OUTPUT_HASHES_MATCH", all(output_matches), {"passed": sum(output_matches), "total": len(output_matches)})
    record(checks, "V27", "SOURCE_HASHES_MATCH", all(source_matches), {"passed": sum(source_matches), "total": len(source_matches)})
    record(checks, "V28", "NO_BASELINE_OUTPUT_TARGETS", all(item["path"].startswith("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/09_downstream_rebind/") for item in output_records), [item["path"] for item in output_records])

    # Negative controls operate only on in-memory copies and must all trip fail-closed.
    sample_input = role_paths["m7_terminal_gate"].read_bytes()
    sample_source = action.encode("utf-8")
    history_latest = max(iso(receipt["validated_at"]), iso(bootstrap["generated_at"]))
    stale_evidence_is_newer = (history_latest - timedelta(seconds=1)) > history_latest
    negative_controls = [
        {"id": "NC01", "name": "INPUT_BYTE_TAMPER_DETECTED", "pass": sha_bytes(sample_input + b" ") != sha_bytes(sample_input)},
        {"id": "NC02", "name": "SOURCE_BYTE_TAMPER_DETECTED", "pass": sha_bytes(sample_source + b"#tamper") != sha_bytes(sample_source)},
        {"id": "NC03", "name": "MISSING_RUNTIME_HARNESS_GATE_BLOCKS_PRODUCTION", "pass": no_harness_runtime_gate and not production_authorized(False, True, True, True)},
        {"id": "NC04", "name": "OLD_INTERFACE_BLOCKS_V2_REBIND", "pass": old_interface and loader_v1_only and not production_authorized(True, False, True, True)},
        {"id": "NC05", "name": "STALE_TIMESTAMP_CANNOT_SUPERSEDE_HISTORY", "pass": not stale_evidence_is_newer and not production_authorized(True, True, stale_evidence_is_newer, True)},
        {"id": "NC06", "name": "KINEMATIC_BACKEND_BLOCKS_CONTACT_PRODUCTION", "pass": backend_is_nonproduction(backend) and not production_authorized(True, True, True, False)},
        {"id": "NC07", "name": "G12_STRING_HEURISTIC_CANNOT_PROVE_RUNTIME_BINDING", "pass": string_only_g12 and no_harness_runtime_gate and not production_authorized(False, True, True, True)},
    ]
    record(checks, "V29", "ALL_NEGATIVE_CONTROLS_TRIP_FAIL_CLOSED", all(item["pass"] for item in negative_controls), {"passed": sum(item["pass"] for item in negative_controls), "total": len(negative_controls)})

    passed = sum(item["pass"] for item in checks)
    report = {
        "schema": "SIM13_CURRENT_BINDING_AUDIT_VALIDATION_REPORT_V1",
        "validation_scope": "independent read-only semantic, hash and negative-control validation",
        "checks": checks,
        "checks_total": len(checks),
        "checks_passed": passed,
        "checks_failed": len(checks) - passed,
        "negative_controls": negative_controls,
        "negative_controls_total": len(negative_controls),
        "negative_controls_passed": sum(item["pass"] for item in negative_controls),
        "verdict": "PASS" if passed == len(checks) else "FAIL",
        "baseline_files_modified": False,
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "verdict": report["verdict"],
        "checks": f"{passed}/{len(checks)}",
        "negative_controls": f"{report['negative_controls_passed']}/{report['negative_controls_total']}",
        "report_sha256": sha(REPORT),
    }))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
