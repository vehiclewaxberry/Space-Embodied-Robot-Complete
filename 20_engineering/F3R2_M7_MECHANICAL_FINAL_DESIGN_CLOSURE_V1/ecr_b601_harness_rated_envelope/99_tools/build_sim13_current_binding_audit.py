#!/usr/bin/env python3
"""Build a read-only, fail-closed audit of the current Sim13 mechanical binding.

The audit does not modify Sim13 or any M7/Route-B baseline.  It binds the
newer M7 terminal evidence to the exact Sim13 configuration and source files
that are currently present in the repository.
"""
from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
PACKAGE = SCRIPT.parents[1]
ROOT = SCRIPT.parents[4]
OUT = PACKAGE / "09_downstream_rebind"

PATHS = {
    "m7_terminal_gate": PACKAGE / "07_release/B601_HARNESS_TERMINAL_GATE_V1.json",
    "m7_handoff_v2": PACKAGE / "07_release/MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2.json",
    "m7_mission_coverage": PACKAGE / "04_mission/B601_HARNESS_MISSION_COVERAGE_GATE.json",
    "handoff_builder_source": PACKAGE / "99_tools/build_route_b_terminal_closure.py",
    "sim13_config": ROOT / "30_simulation/sim_13_physics_gated_embodied_grasping/config/sim13_bootstrap.json",
    "sim13_historical_receipt": ROOT / "30_simulation/sim_13_physics_gated_embodied_grasping/evidence/SIM13_PRODUCTION_BINDING_RECEIPT.json",
    "sim13_historical_bootstrap_gate": ROOT / "30_simulation/sim_13_physics_gated_embodied_grasping/evidence/SIM13_ENVIRONMENT_BOOTSTRAP_GATE.json",
    "sim13_loader_source": ROOT / "30_simulation/sim_13_physics_gated_embodied_grasping/src/mechanical_asset_loader.py",
    "sim13_action_mask_source": ROOT / "30_simulation/sim_13_physics_gated_embodied_grasping/src/action_mask.py",
    "sim13_backend_source": ROOT / "30_simulation/sim_13_physics_gated_embodied_grasping/src/physics_backend.py",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def assigned_string(tree: ast.AST, name: str) -> str | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    return node.value.value
    return None


def safety_gate_fields(tree: ast.AST) -> list[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "SafetyGateSnapshot":
            return [
                item.target.id
                for item in node.body
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
            ]
    return []


def backend_facts(tree: ast.AST) -> dict[str, Any]:
    scope = None
    reset_collision_false = False
    step_replace_keywords: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "DeterministicPhysicsBackend":
            for item in node.body:
                if isinstance(item, ast.Assign):
                    if any(isinstance(target, ast.Name) and target.id == "scope" for target in item.targets):
                        if isinstance(item.value, ast.Constant):
                            scope = item.value.value
                if isinstance(item, ast.FunctionDef) and item.name == "reset":
                    for descendant in ast.walk(item):
                        if isinstance(descendant, ast.Call):
                            for keyword in descendant.keywords:
                                if keyword.arg == "collision_detected":
                                    reset_collision_false = (
                                        isinstance(keyword.value, ast.Constant)
                                        and keyword.value.value is False
                                    )
                if isinstance(item, ast.FunctionDef) and item.name == "step":
                    for descendant in ast.walk(item):
                        if isinstance(descendant, ast.Call) and isinstance(descendant.func, ast.Name):
                            if descendant.func.id == "replace":
                                step_replace_keywords.extend(
                                    keyword.arg for keyword in descendant.keywords if keyword.arg
                                )
    dynamic_state_terms = {
        "base_quaternion_xyzw",
        "base_angular_velocity_radps",
        "joint_position_rad_or_m",
        "joint_velocity_radps_or_mps",
        "end_effector_position_m",
        "end_effector_quaternion_xyzw",
        "end_effector_linear_velocity_mps",
        "end_effector_angular_velocity_radps",
        "collision_detected",
    }
    return {
        "scope": scope,
        "reset_collision_detected_false": reset_collision_false,
        "step_replace_keywords": sorted(set(step_replace_keywords)),
        "step_updates_any_robot_or_collision_state": bool(
            dynamic_state_terms.intersection(step_replace_keywords)
        ),
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    missing = [rel(path) for path in PATHS.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"required audit inputs missing: {missing}")

    terminal = load_json(PATHS["m7_terminal_gate"])
    handoff = load_json(PATHS["m7_handoff_v2"])
    mission = load_json(PATHS["m7_mission_coverage"])
    config = load_json(PATHS["sim13_config"])
    receipt = load_json(PATHS["sim13_historical_receipt"])
    bootstrap = load_json(PATHS["sim13_historical_bootstrap_gate"])

    loader_text = PATHS["sim13_loader_source"].read_text(encoding="utf-8-sig")
    action_text = PATHS["sim13_action_mask_source"].read_text(encoding="utf-8-sig")
    backend_text = PATHS["sim13_backend_source"].read_text(encoding="utf-8-sig")
    handoff_builder_text = PATHS["handoff_builder_source"].read_text(encoding="utf-8-sig")
    loader_tree = ast.parse(loader_text)
    action_tree = ast.parse(action_text)
    backend_tree = ast.parse(backend_text)

    loader_schema = assigned_string(loader_tree, "INTERFACE_SCHEMA_VERSION")
    loader_filename_locked = "MECH_RL_INTERFACE_V1.yaml" in loader_text
    fields = safety_gate_fields(action_tree)
    harness_fields = [field for field in fields if "harness" in field.lower()]
    backend = backend_facts(backend_tree)

    terminal_time = parse_time(terminal["generated_local"])
    receipt_time = parse_time(receipt["validated_at"])
    bootstrap_time = parse_time(bootstrap["generated_at"])
    terminal_newer_than_history = terminal_time > max(receipt_time, bootstrap_time)

    configured_interface_path = str(config["mechanical_interface_path"])
    configured_interface_is_v1 = configured_interface_path.endswith("MECH_RL_INTERFACE_V1.yaml")
    historical_interface_same = (
        receipt.get("production_interface_path") == configured_interface_path
        and receipt.get("interface_schema_version") == "MECH_RL_INTERFACE_V1"
    )

    g12 = next(item for item in handoff["checks"] if item.get("id") == "G12")
    g12_terms = g12["evidence"]["terms"]
    handoff_string_heuristic = (
        '"rl_action_mask_binds_harness": "harness" in contract["rl_action_mask"].lower()'
        in handoff_builder_text
    )

    observations = [
        {
            "id": "A01",
            "name": "INPUTS_HASH_BOUND",
            "observed": True,
            "evidence": {"input_count": len(PATHS)},
        },
        {
            "id": "A02",
            "name": "M7_TERMINAL_EVIDENCE_NEWER_THAN_SIM13_HISTORY",
            "observed": terminal_newer_than_history,
            "evidence": {
                "m7_terminal_generated_local": terminal["generated_local"],
                "sim13_receipt_validated_at": receipt["validated_at"],
                "sim13_bootstrap_generated_at": bootstrap["generated_at"],
            },
        },
        {
            "id": "A03",
            "name": "M7_ROUTE_B_REJECTED",
            "observed": terminal.get("route_b") == "REJECTED",
            "evidence": {"route_b": terminal.get("route_b")},
        },
        {
            "id": "A04",
            "name": "M7_MECHANICAL_DESIGN_NOT_RELEASED",
            "observed": terminal.get("mechanical_design") == "NOT_RELEASED",
            "evidence": {"mechanical_design": terminal.get("mechanical_design")},
        },
        {
            "id": "A05",
            "name": "M7_NEXT_STAGE_NOT_AUTHORIZED",
            "observed": terminal.get("next_stage_authorized") is False,
            "evidence": {"next_stage_authorized": terminal.get("next_stage_authorized")},
        },
        {
            "id": "A06",
            "name": "M7_MISSION_COVERAGE_FAILED",
            "observed": mission.get("mission_coverage") == "FAIL",
            "evidence": {
                "mandatory_states": len(mission.get("key_state_checks", [])),
                "mandatory_states_safe": sum(
                    item.get("harness_status") == "SAFE"
                    for item in mission.get("key_state_checks", [])
                ),
                "released_trajectories": mission.get("trajectory_segments_with_released_authority"),
                "required_trajectories": mission.get("required_trajectory_segments"),
            },
        },
        {
            "id": "A07",
            "name": "M7_HANDOFF_FAILED_AT_G12",
            "observed": (
                handoff.get("verdict") == "MECHANICAL_TO_EMBODIED_HANDOFF_FAIL"
                and handoff.get("failing_checks") == ["G12"]
                and g12.get("pass") is False
            ),
            "evidence": {
                "passed": handoff.get("checks_passed"),
                "total": handoff.get("checks_total"),
                "failing_checks": handoff.get("failing_checks"),
            },
        },
        {
            "id": "A08",
            "name": "SIM13_CONFIG_STILL_BINDS_V1",
            "observed": configured_interface_is_v1,
            "evidence": {"mechanical_interface_path": configured_interface_path},
        },
        {
            "id": "A09",
            "name": "SIM13_HISTORICAL_RECEIPT_BINDS_SAME_V1",
            "observed": historical_interface_same,
            "evidence": {
                "production_interface_path": receipt.get("production_interface_path"),
                "interface_schema_version": receipt.get("interface_schema_version"),
                "historical_production_binding_passed": receipt.get("production_binding_passed"),
            },
        },
        {
            "id": "A10",
            "name": "SIM13_LOADER_HARD_CODES_V1_SCHEMA_AND_FILENAME",
            "observed": loader_schema == "MECH_RL_INTERFACE_V1" and loader_filename_locked,
            "evidence": {
                "loader_schema_constant": loader_schema,
                "required_filename_literal_present": loader_filename_locked,
            },
        },
        {
            "id": "A11",
            "name": "SIM13_RUNTIME_SAFETY_SNAPSHOT_HAS_NO_HARNESS_GATE",
            "observed": bool(fields) and not harness_fields,
            "evidence": {
                "runtime_gate_count": len(fields),
                "runtime_gate_fields": fields,
                "harness_gate_fields": harness_fields,
            },
        },
        {
            "id": "A12",
            "name": "SIM13_BACKEND_IS_KINEMATIC_AND_DOES_NOT_UPDATE_COLLISION",
            "observed": (
                backend["scope"] == "KINEMATIC_BOOTSTRAP_NOT_CONTACT_OR_TRAINING_PHYSICS"
                and backend["reset_collision_detected_false"]
                and not backend["step_updates_any_robot_or_collision_state"]
            ),
            "evidence": backend,
        },
        {
            "id": "A13",
            "name": "M7_G12_RUNTIME_BINDING_TERM_IS_ONLY_STRING_HEURISTIC",
            "observed": handoff_string_heuristic and g12_terms.get("rl_action_mask_binds_harness") is True,
            "evidence": {
                "g12_reported_term": g12_terms.get("rl_action_mask_binds_harness"),
                "builder_expression": '"harness" in contract["rl_action_mask"].lower()',
                "runtime_action_mask_source_was_not_consumed_by_g12": True,
            },
        },
        {
            "id": "A14",
            "name": "HISTORICAL_BOOTSTRAP_ALREADY_LIMITED_TO_KINEMATIC_SCOPE",
            "observed": (
                bootstrap.get("environment_scope")
                == "DETERMINISTIC_KINEMATIC_BOOTSTRAP_NOT_CONTACT_PHYSICS_OR_TRAINING"
                and bootstrap.get("next_stage_authorized") is False
            ),
            "evidence": {
                "gate_status": bootstrap.get("gate_status"),
                "scope": bootstrap.get("environment_scope"),
                "next_stage_authorized": bootstrap.get("next_stage_authorized"),
            },
        },
    ]

    all_observed = all(item["observed"] for item in observations)
    input_manifest = {
        "schema": "SIM13_CURRENT_BINDING_AUDIT_INPUT_MANIFEST_V1",
        "purpose": "immutable byte-level binding for a read-only downstream authority audit",
        "inputs": [
            {
                "role": role,
                "path": rel(path),
                "sha256": sha256(path),
                "size_bytes": path.stat().st_size,
            }
            for role, path in PATHS.items()
        ],
        "input_count": len(PATHS),
        "all_inputs_present": True,
    }
    input_manifest_path = OUT / "SIM13_CURRENT_BINDING_AUDIT_INPUT_MANIFEST_V1.json"
    write_json(input_manifest_path, input_manifest)

    gate = {
        "schema": "SIM13_CURRENT_MECHANICAL_BINDING_AUDIT_GATE_V1",
        "generated_from_latest_bound_evidence": terminal["generated_local"],
        "authority_scope": "READ_ONLY_DOWNSTREAM_REBIND_AUDIT",
        "baseline_mutation_authorized": False,
        "input_manifest": {
            "path": rel(input_manifest_path),
            "sha256": sha256(input_manifest_path),
            "input_count": len(PATHS),
        },
        "observations": observations,
        "observation_count": len(observations),
        "observations_confirmed": sum(item["observed"] for item in observations),
        "observations_unconfirmed": [
            item["id"] for item in observations if not item["observed"]
        ],
        "historical_evidence_disposition": {
            "sim13_production_binding_receipt_preserved": True,
            "sim13_environment_bootstrap_gate_preserved": True,
            "historical_bootstrap_result": bootstrap.get("gate_status"),
            "historical_scope_remains_valid": "KINEMATIC_BOOTSTRAP_ONLY",
            "historical_evidence_not_rewritten": True,
        },
        "current_authority": {
            "mechanical_release": False,
            "production_dynamics_ready": False,
            "physical_contact_ready": False,
            "physics_gated_rl_ready": False,
            "hardware_motion_ready": False,
            "diagnostic_kinematic_bootstrap_only": True,
            "abort_always_available": True,
        },
        "verdict": (
            "CURRENT_SIM13_PRODUCTION_MECHANICAL_BINDING_INVALIDATED_BY_NEWER_M7_EVIDENCE"
            if all_observed
            else "AUDIT_INCOMPLETE_FAIL_CLOSED_CURRENT_SIM13_PRODUCTION_BINDING_NOT_AUTHORIZED"
        ),
        "verdict_issued": all_observed,
        "required_action": "ABORT_OR_DIAGNOSTIC_KINEMATIC_BOOTSTRAP_ONLY_UNTIL_ROUTE_C_AND_RUNTIME_REBIND_PASS",
        "reentry_requirements": [
            "Route C detailed design is authorized, realized and passes its exact harness predicate",
            "mandatory mission states and complete trajectories obtain released harness authority",
            "a new interface version is hash-bound and consumed by the Sim13 loader",
            "SafetyGateSnapshot contains a fail-closed runtime harness state",
            "runtime negative controls prove harness FAIL and UNKNOWN mask every non-ABORT action",
            "a separate contact-physics/production-dynamics gate is passed",
        ],
        "next_stage_authorized": False,
        "prohibition": "do not use the historical V1 receipt as current production/contact/RL mechanical authority",
    }
    gate_path = OUT / "SIM13_CURRENT_MECHANICAL_BINDING_AUDIT_GATE_V1.json"
    write_json(gate_path, gate)

    validator = PACKAGE / "99_tools/validate_sim13_current_binding_audit.py"
    output_manifest = {
        "schema": "SIM13_CURRENT_BINDING_AUDIT_OUTPUT_MANIFEST_V1",
        "hash_algorithm": "SHA-256",
        "outputs": [
            {"path": rel(input_manifest_path), "sha256": sha256(input_manifest_path)},
            {"path": rel(gate_path), "sha256": sha256(gate_path)},
        ],
        "sources": [
            {"path": rel(SCRIPT), "sha256": sha256(SCRIPT)},
            {"path": rel(validator), "sha256": sha256(validator)},
        ],
        "output_count": 2,
        "source_count": 2,
        "self_excluded_to_avoid_recursive_hash": True,
    }
    write_json(OUT / "SIM13_CURRENT_BINDING_AUDIT_OUTPUT_MANIFEST_V1.json", output_manifest)
    print(json.dumps({
        "verdict": gate["verdict"],
        "observations": f"{gate['observations_confirmed']}/{gate['observation_count']}",
        "gate_sha256": sha256(gate_path),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
