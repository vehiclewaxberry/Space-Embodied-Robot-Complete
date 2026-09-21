#!/usr/bin/env python3
"""Validate the definition-only Sim13 V2 mechanical rebind boundary.

This validator is deliberately non-operative: it does not create a URDF, an
interface instance, a Sim13 V2 package, or any simulator/runtime state.
"""

from __future__ import annotations

import csv
import hashlib
import json
import tempfile
from pathlib import Path

import yaml


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
BOUNDARY_PATH = HERE / "SIM13_VERSIONED_REBIND_BOUNDARY_V2.yaml"
SCHEMA_PATH = HERE / "MECH_RL_SYSTEM_INTERFACE_V2_SCHEMA_DEFINITION.yaml"
VALIDATOR_PATH = HERE / "validate_sim13_versioned_rebind_boundary_v2.py"
VALIDATION_PATH = HERE / "SIM13_VERSIONED_REBIND_BOUNDARY_VALIDATION_V2.json"
GATE_PATH = HERE / "SIM13_VERSIONED_REBIND_BOUNDARY_GATE_V2.json"
RECEIPT_PATH = HERE / "SIM13_VERSIONED_REBIND_BOUNDARY_RECEIPT_V2.md"
HASH_PATH = HERE / "SIM13_VERSIONED_REBIND_BOUNDARY_SHA256_V2.csv"

SOURCE_DIR = HERE.parent / "source_only_v2"
SIM13_V1_DIR = ROOT / "30_simulation/sim_13_physics_gated_embodied_grasping"
SIM13_V2_RUNTIME_DIR = SIM13_V1_DIR / "v2_system_rebind"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def check(identifier: str, name: str, passed: bool, evidence) -> dict[str, object]:
    return {"id": identifier, "name": name, "pass": bool(passed), "evidence": evidence}


def pin_audit(pins: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    for pin_id, pin in pins.items():
        path = ROOT / str(pin["path"])
        actual_bytes = path.stat().st_size if path.is_file() else None
        actual_hash = sha256(path) if path.is_file() else None
        rows.append(
            {
                "id": pin_id,
                "path": pin["path"],
                "expected_bytes": pin["bytes"],
                "actual_bytes": actual_bytes,
                "expected_sha256": pin["sha256"],
                "actual_sha256": actual_hash,
                "pass": actual_bytes == int(pin["bytes"]) and actual_hash == pin["sha256"],
            }
        )
    return rows


def source_manifest_audit(path: Path) -> list[dict[str, object]]:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for record in csv.DictReader(stream):
            candidate = ROOT / record["path"]
            actual_bytes = candidate.stat().st_size if candidate.is_file() else None
            actual_hash = sha256(candidate) if candidate.is_file() else None
            rows.append(
                {
                    "path": record["path"],
                    "expected_bytes": int(record["bytes"]),
                    "actual_bytes": actual_bytes,
                    "expected_sha256": record["sha256"],
                    "actual_sha256": actual_hash,
                    "pass": actual_bytes == int(record["bytes"]) and actual_hash == record["sha256"],
                }
            )
    return rows


def sim13_v1_manifest_audit(manifest: dict[str, object]) -> list[dict[str, object]]:
    rows = []
    for group in ("required_modules", "supporting_source"):
        for relative_path, expected_hash in manifest[group].items():
            path = SIM13_V1_DIR / relative_path
            actual_hash = sha256(path) if path.is_file() else None
            rows.append(
                {
                    "group": group,
                    "path": relative_path,
                    "expected_sha256": expected_hash,
                    "actual_sha256": actual_hash,
                    "pass": actual_hash == expected_hash,
                }
            )
    return rows


def forbidden_instance_scan(unified_root: Path, sim13_root: Path) -> dict[str, object]:
    urdf_files = sorted(path.relative_to(unified_root).as_posix() for path in unified_root.rglob("*.urdf"))
    authority_files = sorted(
        path.relative_to(unified_root).as_posix()
        for path in unified_root.rglob("UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json")
    )
    interface_instances = sorted(
        path.relative_to(sim13_root).as_posix()
        for path in sim13_root.rglob("MECH_RL_SYSTEM_INTERFACE_V2.yaml")
    )
    runtime_namespace_files = []
    if (sim13_root / "v2_system_rebind").exists():
        runtime_namespace_files = sorted(
            path.relative_to(sim13_root).as_posix()
            for path in (sim13_root / "v2_system_rebind").rglob("*")
            if path.is_file()
        )
    embedded_interface_schema = []
    for path in sim13_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".py", ".yaml", ".yml", ".json"}:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (UnicodeDecodeError, OSError):
            continue
        if "MECH_RL_SYSTEM_INTERFACE_V2" in text:
            embedded_interface_schema.append(path.relative_to(sim13_root).as_posix())
    return {
        "urdf_files": urdf_files,
        "authority_files": authority_files,
        "interface_instances": interface_instances,
        "runtime_namespace_files": runtime_namespace_files,
        "embedded_interface_schema": sorted(embedded_interface_schema),
        "clean": not any((urdf_files, authority_files, interface_instances, runtime_namespace_files, embedded_interface_schema)),
    }


def forbidden_scan_negative_control() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="sim13_rebind_boundary_scan_") as temp_name:
        root = Path(temp_name)
        unified = root / "unified"
        sim13 = root / "sim13"
        (unified / "nested").mkdir(parents=True)
        (sim13 / "alternate").mkdir(parents=True)
        (sim13 / "v2_system_rebind").mkdir(parents=True)
        (unified / "nested" / "candidate.urdf").write_text("<robot/>", encoding="utf-8")
        (unified / "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json").write_text("{}", encoding="utf-8")
        (sim13 / "alternate" / "MECH_RL_SYSTEM_INTERFACE_V2.yaml").write_text("schema: MECH_RL_SYSTEM_INTERFACE_V2", encoding="utf-8")
        (sim13 / "v2_system_rebind" / "loader.py").write_text("# injected", encoding="utf-8")
        result = forbidden_instance_scan(unified, sim13)
        detected = {
            "recursive_urdf": result["urdf_files"] == ["nested/candidate.urdf"],
            "authority_record": result["authority_files"] == ["UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json"],
            "interface_by_name": result["interface_instances"] == ["alternate/MECH_RL_SYSTEM_INTERFACE_V2.yaml"],
            "interface_by_content": result["embedded_interface_schema"] == ["alternate/MECH_RL_SYSTEM_INTERFACE_V2.yaml"],
            "runtime_namespace": result["runtime_namespace_files"] == ["v2_system_rebind/loader.py"],
        }
        return {"all_detected": all(detected.values()), "detections": detected}


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    boundary = yaml.safe_load(BOUNDARY_PATH.read_text(encoding="utf-8-sig"))
    schema = yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8-sig"))
    pins = pin_audit(boundary["source_pins"])

    v2_gate_pin = boundary["source_pins"]["unified_r2_source_gate_v2"]
    v2_validation_pin = boundary["source_pins"]["unified_r2_static_validation_v2"]
    v2_manifest_pin = boundary["source_pins"]["unified_r2_sha_manifest_v2"]
    current_audit_pin = boundary["source_pins"]["sim13_current_binding_audit_v1"]
    sim13_manifest_pin = boundary["source_pins"]["sim13_source_manifest_v1"]
    v2_gate = json.loads((ROOT / v2_gate_pin["path"]).read_text(encoding="utf-8-sig"))
    v2_validation = json.loads((ROOT / v2_validation_pin["path"]).read_text(encoding="utf-8-sig"))
    current_audit = json.loads((ROOT / current_audit_pin["path"]).read_text(encoding="utf-8-sig"))
    sim13_source_manifest = json.loads((ROOT / sim13_manifest_pin["path"]).read_text(encoding="utf-8-sig"))
    v2_manifest_rows = source_manifest_audit(ROOT / v2_manifest_pin["path"])
    sim13_manifest_rows = sim13_v1_manifest_audit(sim13_source_manifest)

    loader_text = (ROOT / boundary["source_pins"]["sim13_v1_loader"]["path"]).read_text(encoding="utf-8-sig")
    backend_text = (ROOT / boundary["source_pins"]["sim13_v1_physics_backend"]["path"]).read_text(encoding="utf-8-sig")
    action_mask_text = (ROOT / boundary["source_pins"]["sim13_v1_action_mask"]["path"]).read_text(encoding="utf-8-sig")

    current = boundary["current_state"]
    system = boundary["selected_system_contract"]
    b601 = boundary["accepted_b601_subtree_contract"]
    frame = boundary["frame_and_load_path_contract"]
    future_interface = boundary["future_interface_schema"]
    future_artifacts = boundary["future_artifact_contract"]
    runtime = boundary["future_runtime_gate_contract"]
    authority_join = boundary["future_authority_join"]
    negative_contract = boundary["required_negative_controls"]
    negatives = negative_contract["controls"]
    sequence = boundary["future_gate_sequence"]
    route_c = boundary["route_c_scope_rule"]
    actual_forbidden_scan = forbidden_instance_scan(HERE.parent, SIM13_V1_DIR)
    scan_negative_control = forbidden_scan_negative_control()

    absent_source_state = {
        "urdf_files": sorted(path.name for path in SOURCE_DIR.glob("*.urdf")),
        "authorization_present": (SOURCE_DIR / "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json").exists(),
        "run_consumption_present": (SOURCE_DIR / ".unified_r2_v2_run_consumption").exists(),
        "override_consumption_present": (SOURCE_DIR / ".unified_r2_v2_override_consumption").exists(),
        "active_writer_lock_present": (SOURCE_DIR / ".unified_r2_v2_active_run.lock").exists(),
    }
    all_current_flags_false = all(
        current[name] is False
        for name in (
            "system_interface_instantiated",
            "system_urdf_available",
            "unified_r2_generation_authorized",
            "route_c_exclusion_accepted_for_this_sim_candidate",
            "sim13_v2_package_created",
            "sim13_rebind_authorized",
            "runtime_fail_closed_gate_passed",
            "dynamics_backend_gate_passed",
            "contact_grasp_gate_passed",
            "dynamics_capture_entry_authorized",
            "production_dynamics_ready",
            "next_stage_authorized",
            "release_credit",
        )
    )

    expected_inherited_v1_gates = {
        "ik_reachable",
        "external_collision_clear",
        "keep_out_clear",
        "sim10_gate",
        "safe00_state",
        "post_grasp_stability_gate",
        "gripper_configuration_accepted",
        "target_surface_normal_valid",
    }
    expected_new_v2_gates = {
        "mechanical_system_binding",
        "harness_rated_envelope",
        "contact_physics_ready",
        "route_c_scope_disposition",
    }
    expected_runtime_gates = expected_inherited_v1_gates | expected_new_v2_gates
    expected_negative_controls = [
        ("NC01", "V1_SCHEMA_OR_FILENAME_AS_V2_BINDING", "binding_denied", "REJECT_BINDING", "SIM13_SYSTEM_BINDING_GATE_V2", False),
        ("NC02", "ARTIFACT_BYTES_OR_SHA256_DRIFT", "binding_denied", "REJECT_BINDING", "SIM13_SYSTEM_BINDING_GATE_V2", False),
        ("NC03", "AGGREGATE_18_LINK_MODE_MASQUERADES_AS_SELECTED_19_LINK_MODE", "topology_mismatch", "REJECT_BINDING", "SIM13_SYSTEM_BINDING_GATE_V2", False),
        ("NC04", "EXPLICIT_STRUCTURE_DOUBLE_COUNT_TOTAL_37P05784541499227_KG", "mass_recomposition_mismatch", "REJECT_BINDING", "SIM13_SYSTEM_BINDING_GATE_V2", False),
        ("NC05", "ACCEPTED_B601_EXACT_FIELD_DRIFT", "subtree_mismatch", "REJECT_BINDING", "SIM13_SYSTEM_BINDING_GATE_V2", False),
        ("NC06", "FRAME_ONLY_LINK_HAS_INERTIAL_VISUAL_OR_COLLISION", "frame_contract_mismatch", "REJECT_BINDING", "SIM13_SYSTEM_BINDING_GATE_V2", False),
        ("NC07", "D_M_ALIAS_OR_PHYSICAL_PATH_TRAVERSES_M", "load_path_mismatch", "REJECT_BINDING", "SIM13_SYSTEM_BINDING_GATE_V2", False),
        ("NC08", "MECHANICAL_SYSTEM_BINDING_UNKNOWN_OR_FAIL_WITH_NON_ABORT_REQUEST", "shield_executes_abort", "MASK_TO_ABORT_ONLY", "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", False),
        ("NC09", "HARNESS_RATED_ENVELOPE_UNKNOWN_OR_FAIL_WITH_NON_ABORT_REQUEST", "shield_executes_abort", "MASK_TO_ABORT_ONLY", "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", False),
        ("NC10", "CONTACT_PHYSICS_READY_UNKNOWN_OR_FAIL_WITH_GRASP_REQUEST", "shield_executes_abort", "MASK_TO_ABORT_ONLY", "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", False),
        ("NC11", "KINEMATIC_BOOTSTRAP_OFFERED_AS_CONTACT_OR_TRAINING_PHYSICS", "backend_scope_rejected", "FAIL_GATE", "SIM13_DYNAMICS_BACKEND_GATE_V2", False),
        ("NC12", "URDF_ABSENT_OR_ROUTE_C_SCOPE_UNACCEPTED_OR_REBIND_UNAUTHORIZED", "consumer_load_denied", "REJECT_BINDING", "SIM13_SYSTEM_BINDING_GATE_V2", False),
        ("NC13", "ANY_INHERITED_V1_GATE_UNKNOWN_OR_FAIL_WITH_NON_ABORT_REQUEST", "shield_executes_abort", "MASK_TO_ABORT_ONLY", "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", False),
        ("NC14", "CALLER_FORGES_PASS_WITHOUT_HASH_BOUND_EVALUATOR_RECEIPT", "authority_join_denied", "REJECT_BINDING", "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", False),
        ("NC15", "STALE_OR_REPLAYED_GATE_SNAPSHOT", "snapshot_rejected", "MASK_TO_ABORT_ONLY", "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", False),
        ("NC16", "DIRECT_BACKEND_CALL_BYPASSES_SAFETY_SHIELD", "backend_rejects_unshielded_non_abort", "MASK_TO_ABORT_ONLY", "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", False),
        ("NC17", "MASS_OR_INERTIA_PERTURBED_BUT_TRAJECTORY_UNCHANGED", "physics_sensitivity_failure", "FAIL_GATE", "SIM13_DYNAMICS_BACKEND_GATE_V2", False),
        ("NC18", "NON_ABORT_STEP_CHANGES_TASK_PHASE_ONLY_WITHOUT_JOINT_BASE_OR_EE_STATE", "dynamics_state_update_failure", "FAIL_GATE", "SIM13_DYNAMICS_BACKEND_GATE_V2", False),
        ("NC19", "OVERLAPPING_GEOMETRY_DOES_NOT_UPDATE_COLLISION_OR_CONTACT_STATE", "contact_detection_failure", "FAIL_GATE", "SIM13_CONTACT_GRASP_GATE_V2", False),
        ("NC20", "DEBRIS_150KG_3DPS_REQUESTS_NON_ABORT_WITHOUT_FEASIBILITY_AND_POST_GRASP_PASS", "shield_executes_abort", "MASK_TO_ABORT_ONLY", "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2", False),
    ]
    expected_gate_names = [
        "UNIFIED_R2_URDF_EXECUTION_GATE_V2",
        "SIM13_SYSTEM_BINDING_GATE_V2",
        "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2",
        "SIM13_DYNAMICS_BACKEND_GATE_V2",
        "SIM13_CONTACT_GRASP_GATE_V2",
        "E15_RECERTIFICATION_IF_FLEXIBLE_FULL_COUPLING_CLAIMED",
    ]
    expected_artifacts = {
        "system_urdf",
        "system_frame_tree",
        "accepted_b601_urdf",
        "urdf_generation_receipt",
        "unified_r2_source_gate",
        "sim_candidate_contract",
    }
    expected_stage_artifacts = {
        "SIM13_SYSTEM_BINDING_GATE_V2": ["v2_loader_source", "v2_loader_validation_receipt"],
        "SIM13_RUNTIME_FAIL_CLOSED_GATE_V2": ["runtime_gate_adapter_source", "runtime_evaluator_source", "runtime_evaluator_receipt"],
        "SIM13_DYNAMICS_BACKEND_GATE_V2": ["dynamics_backend_source", "dynamics_backend_validation_receipt"],
        "SIM13_CONTACT_GRASP_GATE_V2": ["contact_backend_source", "contact_backend_validation_receipt"],
    }
    expected_consumer_join = [
        "owner_accepted",
        "route_c_exclusion_accepted_for_this_sim_candidate",
        "route_c_scope_disposition_pass",
        "system_urdf_generated_and_validated",
        "urdf_generation_receipt_hash_valid",
        "sim13_system_binding_gate_passed",
        "v2_loader_validation_receipt_hash_valid",
        "runtime_fail_closed_gate_passed",
        "runtime_evaluator_receipt_hash_valid",
        "dynamics_backend_gate_passed",
        "dynamics_backend_validation_receipt_hash_valid",
    ]
    expected_contact_join = [
        "consumer_load_all_of_passed",
        "contact_grasp_gate_passed",
        "contact_backend_validation_receipt_hash_valid",
    ]
    expected_interface_path = "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml"
    expected_runtime_namespace = "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind"
    expected_urdf_path = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/unified_r2_c01_no_route_c_sim_candidate_v2.urdf"

    checks = [
        check("SRB2-01", "boundary and schema are definition-only artifacts", boundary["artifact_class"] == "ENGINEERING_DEFINITION_ONLY__NOT_A_SIMULATOR_BINDING" and current["boundary_definition_only"] is True and schema["artifact_class"] == "SCHEMA_DEFINITION_ONLY__NOT_AN_INTERFACE_INSTANCE" and schema["definition_only"] is True and schema["instantiated"] is False, {"boundary_class": boundary["artifact_class"], "schema_class": schema["artifact_class"], "definition_only": schema["definition_only"], "instantiated": schema["instantiated"]}),
        check("SRB2-02", "all twenty current source pins match bytes and SHA-256", len(pins) == 20 and all(row["pass"] for row in pins), pins),
        check("SRB2-03", "Unified R2 internal nine-row SHA manifest remains exact", len(v2_manifest_rows) == 9 and all(row["pass"] for row in v2_manifest_rows), v2_manifest_rows),
        check("SRB2-04", "Unified R2 source Gate is 24 of 24 source-static only", v2_gate["static_validation"] == {"pass": 24, "total": 24, "failed": []} and v2_gate["technical_outcome"] == "PASS_SOURCE_STATIC_ONLY" and v2_gate["urdf_emitted"] is False and v2_gate["sim13_rebind_authorized"] is False and v2_gate["next_stage_authorized"] is False, v2_gate),
        check("SRB2-05", "Unified R2 cross-file field audit is 401 of 401", v2_validation["cross_file_field_audit"]["row_count"] == 401 and v2_validation["cross_file_field_audit"]["passed_rows"] == 401 and v2_validation["cross_file_field_audit"]["all_passed"] is True and not v2_validation["cross_file_field_audit"]["failed_rows"], {key: v2_validation["cross_file_field_audit"][key] for key in ("row_count", "passed_rows", "failed_rows", "all_passed")}),
        check("SRB2-06", "no URDF authorization consumption marker or writer lock exists", not any(absent_source_state.values()), absent_source_state),
        check("SRB2-07", "current Sim13 production binding remains invalidated and diagnostic-only", current_audit["verdict"] == "CURRENT_SIM13_PRODUCTION_MECHANICAL_BINDING_INVALIDATED_BY_NEWER_M7_EVIDENCE" and current_audit["current_authority"]["diagnostic_kinematic_bootstrap_only"] is True and current_audit["current_authority"]["physical_contact_ready"] is False and current_audit["next_stage_authorized"] is False, {"verdict": current_audit["verdict"], "current_authority": current_audit["current_authority"], "next_stage_authorized": current_audit["next_stage_authorized"]}),
        check("SRB2-08", "complete Sim13 V1 source semantics are hash-pinned and V1 remains incompatible with V2", "MECH_RL_INTERFACE_V1" in loader_text and "KINEMATIC_BOOTSTRAP_NOT_CONTACT_OR_TRAINING_PHYSICS" in backend_text and all(name in action_mask_text for name in expected_inherited_v1_gates) and all(name not in action_mask_text for name in expected_new_v2_gates) and len([row for row in pins if row["id"].startswith("sim13_v1_")]) == 15, {"loader_v1_literal": "MECH_RL_INTERFACE_V1" in loader_text, "backend_kinematic_literal": "KINEMATIC_BOOTSTRAP_NOT_CONTACT_OR_TRAINING_PHYSICS" in backend_text, "inherited_v1_gates_present": sorted(name for name in expected_inherited_v1_gates if name in action_mask_text), "new_v2_gates_absent": sorted(name for name in expected_new_v2_gates if name not in action_mask_text), "pinned_sim13_v1_assets": len([row for row in pins if row["id"].startswith("sim13_v1_")])}),
        check("SRB2-09", "selected whole-system topology and mass are exact", (system["root_link"], system["total_links"], system["physical_links"], system["frame_only_links"], system["joints"], system["fixed_joints"], system["revolute_joints"], system["prismatic_joints"], system["actuated_dof"], float(system["total_mass_kg"])) == ("spacecraft_bus", 19, 16, 3, 18, 10, 6, 2, 8, 31.022864807342987), system),
        check("SRB2-10", "mass authorities are separate and double counting is explicit", abs(float(system["mass_authority_separation"]["residual_bus_mass_kg"]) + float(system["mass_authority_separation"]["explicit_structure_mass_kg"]) - float(system["mass_authority_separation"]["recomposed_bus_mass_kg"])) <= 1.0e-12 and abs(float(system["mass_authority_separation"]["prohibited_double_count_total_kg"]) - (23.3032134 + 6.034980607649281 + 0.702195458 + 0.7619 + 4.695555949342986 + 1.56)) <= 1.0e-12 and future_artifacts["system_and_b601_mass_authorities_must_remain_separate"] is True, system["mass_authority_separation"]),
        check("SRB2-11", "accepted B601 subtree and eight actuated joints are exact", (b601["root_link"], b601["links"], b601["joints"], b601["fixed_joints"], b601["revolute_joints"], b601["prismatic_joints"], float(b601["mass_kg"])) == ("base_link", 10, 9, 1, 6, 2, 4.695555949342986) and b601["actuated_joints"] == ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "gripper_joint1", "gripper_joint2"] and b601["fixed_joint_excluded_from_state"] == ["gripper_joint"] and len(b601["exact_fields"]) == 7, b601),
        check("SRB2-12", "three frame-only identities and physical load path are explicit", frame["frame_only_links"] == ["D_BUS_MATE_PHYSICAL", "D_BUS_M6_PATTERN", "M_DYNAMICS_NONPHYSICAL"] and set(frame["frame_only_required_omissions"]) == {"inertial", "visual", "collision"} and frame["D_and_M_semantic_relation"] == "DISTINCT_IDENTITIES__NEVER_ALIAS" and frame["physical_path"] == ["spacecraft_bus", "D_BUS_MATE_PHYSICAL", "D_BUS_M6_PATTERN", "load_bridge_candidate", "m3r_lumped_link", "base_link"] and frame["physical_path_must_not_traverse"] not in frame["physical_path"], frame),
        check("SRB2-13", "future interface schema requires six core hash-bound artifacts and freezes its only namespaces", set(future_artifacts["core_binding_artifacts"]) == expected_artifacts and future_artifacts["every_artifact_fields"] == ["path", "bytes", "sha256"] and future_artifacts["current_artifact_instances"] == 0 and schema["field_schema"]["artifacts"]["required_entries"] == future_artifacts["core_binding_artifacts"] and future_interface["future_instance_path"] == schema["future_instance_path"] == expected_interface_path and future_interface["future_runtime_namespace"] == schema["future_runtime_namespace"] == expected_runtime_namespace and future_interface["future_generated_urdf_path"] == schema["future_generated_urdf_path"] == expected_urdf_path and future_interface["alternate_instance_or_runtime_namespaces_permitted"] is False and schema["current_boundary"]["interface_instance_path"] is None and schema["current_boundary"]["system_urdf_path"] is None, {"future_interface": future_interface, "future_artifacts": future_artifacts, "schema_current_boundary": schema["current_boundary"]}),
        check("SRB2-14", "eight inherited and four new runtime gates are UNKNOWN and fail closed to ABORT", set(runtime["inherited_v1_safety_gates"]) == expected_inherited_v1_gates and set(runtime["new_v2_mechanical_gates"]) == expected_new_v2_gates and all(value == "UNKNOWN" for value in runtime["inherited_v1_safety_gates"].values()) and all(value == "UNKNOWN" for value in runtime["new_v2_mechanical_gates"].values()) and runtime["combined_required_gate_count"] == 12 and set(schema["field_schema"]["runtime_gate_contract"]["combined_required_fields"]) == expected_runtime_gates and schema["field_schema"]["runtime_gate_contract"]["combined_required_gate_count"] == 12 and runtime["fail_closed_rule"] == "any UNKNOWN or FAIL masks every non-ABORT action" and runtime["abort_always_available"] is True and runtime["current_runtime_adapter_exists"] is False, runtime),
        check("SRB2-15", "twenty negative-control requirements have exact non-executed semantics", [(row["id"], row["stimulus"], row["required_observation"], row["canonical_outcome"], row["future_gate"], row["executed_now"]) for row in negatives] == expected_negative_controls and negative_contract["execution_status_now"] == "REQUIREMENTS_DECLARED_NOT_EXECUTED" and negative_contract["executed_count_now"] == 0, negative_contract),
        check("SRB2-16", "future Gate sequence is complete ordered and conditional e15 is preserved", [row["order"] for row in sequence] == list(range(1, 7)) and [row["gate"] for row in sequence] == expected_gate_names and "5.64 percent above 5 percent" in sequence[-1]["purpose"], sequence),
        check("SRB2-17", "Route-C exclusion acceptance cannot grant harness contact production flight or release authority", route_c["current_route_c_status"] == "HOLD_ABSENT" and set(route_c["never_implied_by_route_c_exclusion_acceptance"]) == {"Route-C CAD", "harness physical envelope", "contact grasp", "production dynamics", "flight qualification", "release"}, route_c),
        check("SRB2-18", "recursive forbidden-artifact scan is clean and detects injected bypass locations", all_current_flags_false and actual_forbidden_scan["clean"] and scan_negative_control["all_detected"] and schema["instance_creation_authorized_now"] is False and schema["consumer_loaded"] is False and boundary["current_machine_decision"]["maximum_current_operational_state"] == "ABORT_OR_DIAGNOSTIC_KINEMATIC_BOOTSTRAP_ONLY" and boundary["current_machine_decision"]["next_stage_authorized"] is False, {"all_current_flags_false": all_current_flags_false, "actual_forbidden_scan": actual_forbidden_scan, "scan_negative_control": scan_negative_control, "schema_boundary": schema["current_boundary"], "machine_decision": boundary["current_machine_decision"]}),
        check("SRB2-19", "consumer-load and contact authority are single all-of joins from hash-bound receipts", authority_join["evaluation"] == "ALL_OF_EXACT_TRUE_FROM_HASH_BOUND_RECEIPTS" and authority_join["caller_supplied_gate_state_is_authority"] is False and authority_join["consumer_load_all_of"] == expected_consumer_join and authority_join["contact_grasp_all_of"] == expected_contact_join and authority_join["current_consumer_load_authorized"] is False and authority_join["current_contact_grasp_authorized"] is False and schema["field_schema"]["authority"]["required_exact_true_before_consumer_load"] == expected_consumer_join and schema["field_schema"]["authority"]["required_exact_true_before_contact_grasp"] == expected_contact_join and schema["field_schema"]["authority"]["caller_supplied_gate_state_is_authority"] is False, {"boundary_join": authority_join, "schema_join": schema["field_schema"]["authority"]}),
        check("SRB2-20", "future loader evaluator dynamics and contact artifacts are pre-registered with hashes", future_artifacts["gate_stage_artifacts"] == expected_stage_artifacts and future_artifacts["every_gate_stage_artifact_fields"] == ["path", "bytes", "sha256"] and future_artifacts["pass_evidence_source"] == "hash-bound evaluator receipt only" and future_artifacts["caller_supplied_pass_is_authority"] is False and schema["field_schema"]["artifacts"]["gate_stage_required_entries"] == expected_stage_artifacts and schema["field_schema"]["artifacts"]["every_gate_stage_entry_required_fields"] == ["path", "bytes", "sha256"], future_artifacts),
        check("SRB2-21", "Sim13 V1 source manifest independently binds all ten runtime modules and four supporting assets", sim13_source_manifest["schema_version"] == "SIM13_SOURCE_MANIFEST_V1" and sim13_source_manifest["required_module_count"] == 10 and len(sim13_manifest_rows) == 14 and all(row["pass"] for row in sim13_manifest_rows), sim13_manifest_rows),
    ]

    failed = [row["id"] for row in checks if not row["pass"]]
    validation = {
        "schema": "SIM13_VERSIONED_REBIND_BOUNDARY_VALIDATION_V2",
        "generated_date_local": "2026-08-24",
        "authority_scope": "DEFINITION_ONLY__NO_SIMULATOR_MUTATION",
        "checks": checks,
        "summary": {"pass": len(checks) - len(failed), "total": len(checks), "failed": failed},
        "source_pin_audit": pins,
        "unified_r2_internal_sha_manifest_audit": v2_manifest_rows,
        "sim13_v1_source_manifest_audit": sim13_manifest_rows,
        "forbidden_artifact_scan": actual_forbidden_scan,
        "forbidden_artifact_scan_negative_control": scan_negative_control,
        "negative_control_requirements_declared": len(negatives),
        "negative_controls_executed": 0,
        "boundary_defined": not failed,
        "system_interface_instantiated": False,
        "urdf_available": False,
        "sim13_rebind_authorized": False,
        "dynamics_capture_entry_authorized": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": "PASS_VERSIONED_REBIND_BOUNDARY_DEFINITION_ONLY" if not failed else "HOLD_REBIND_BOUNDARY_DEFINITION_DEFECT",
    }
    write_json(VALIDATION_PATH, validation)

    gate = {
        "schema": "SIM13_VERSIONED_REBIND_BOUNDARY_GATE_V2",
        "generated_date_local": "2026-08-24",
        "package_validation": "PASS" if not failed else "FAIL",
        "technical_outcome": validation["verdict"],
        "score": validation["summary"],
        "boundary_defined": not failed,
        "system_interface_instantiated": False,
        "urdf_available": False,
        "route_c_exclusion_accepted_for_this_sim_candidate": False,
        "sim13_v2_package_created": False,
        "sim13_rebind_authorized": False,
        "runtime_fail_closed_gate_passed": False,
        "dynamics_backend_gate_passed": False,
        "contact_grasp_gate_passed": False,
        "dynamics_capture_entry_authorized": False,
        "negative_control_requirements_declared": len(negatives),
        "negative_controls_executed": 0,
        "maximum_current_operational_state": "ABORT_OR_DIAGNOSTIC_KINEMATIC_BOOTSTRAP_ONLY",
        "next_required_gate": "UNIFIED_R2_URDF_EXECUTION_GATE_V2_AFTER_OWNER_SCOPE_ACCEPTANCE",
        "review_status": "PENDING_OWNER_REVIEW",
        "owner_accepted": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "technical_verdict": "BOUNDARY_SCHEMA_AUTHORITY_JOIN_AND_NEGATIVE_CONTROL_REQUIREMENTS_DECLARED__NEGATIVE_CONTROLS_NOT_EXECUTED__URDF_INTERFACE_LOADER_RUNTIME_DYNAMICS_CONTACT_AND_RELEASE_HOLD",
    }
    write_json(GATE_PATH, gate)

    receipt = (
        "# Sim13 V2 版本化机械重绑定边界回执\n\n"
        f"- 机器检查：`{validation['summary']['pass']}/{validation['summary']['total']}`；裁决：`{validation['verdict']}`。\n"
        "- 本包只冻结未来接口字段、19-link/18-joint 系统不变量、八个继承安全门＋四个新增机械门、20 项负对照要求和六级 Gate 顺序。\n"
        "- 20 项负对照本轮仅完成机器可判定的需求声明，`executed_count=0`；将在对应系统绑定、运行时、动力学与接触 Gate 中执行。\n"
        "- 未生成 `.urdf`，未实例化 `MECH_RL_SYSTEM_INTERFACE_V2.yaml`，未建立或修改 Sim13 V2/V1 运行时代码。\n"
        "- 当前只允许 `ABORT` 或历史诊断性运动学 bootstrap；不得宣称已进入动力学抓取。\n"
        "- 下一有效动作：Owner 接受无 Route-C 研究候选范围后，签发独立、单次、哈希绑定的 Unified R2 URDF 生成授权。\n"
        "- `next_stage_authorized=false`；无接触、生产动力学、飞行或发布信用。\n"
    )
    RECEIPT_PATH.write_text(receipt, encoding="utf-8")

    rows = []
    for artifact_class, path in (
        ("BOUNDARY_SOURCE", BOUNDARY_PATH),
        ("BOUNDARY_SOURCE", SCHEMA_PATH),
        ("BOUNDARY_SOURCE", VALIDATOR_PATH),
        ("BOUNDARY_DERIVED", VALIDATION_PATH),
        ("BOUNDARY_DERIVED", GATE_PATH),
        ("BOUNDARY_DERIVED", RECEIPT_PATH),
    ):
        rows.append(
            {
                "class": artifact_class,
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    for pin in pins:
        rows.append(
            {
                "class": "PINNED_INPUT",
                "path": pin["path"],
                "bytes": pin["actual_bytes"],
                "sha256": pin["actual_sha256"],
            }
        )
    with HASH_PATH.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=("class", "path", "bytes", "sha256"))
        writer.writeheader()
        writer.writerows(rows)

    print(json.dumps({"score": validation["summary"], "verdict": validation["verdict"], "urdf_available": False, "sim13_rebind_authorized": False}))


if __name__ == "__main__":
    main()
