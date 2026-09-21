"""Issue the scoped M4 gate from independently validated evidence."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


M4_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = M4_ROOT.parents[1]
SIM14_ROOT = PROJECT_ROOT / "30_simulation" / "sim_14_m4_digital_prototype_grasping"
OUTPUT = M4_ROOT / "12_release" / "MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_GATE_V1.json"


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def main() -> int:
    validation = read_json(
        M4_ROOT / "11_validation" / "M4_INDEPENDENT_VALIDATION_RECEIPT_V1.json"
    )
    inputs = read_json(
        M4_ROOT / "00_authority" / "M4_FROZEN_INPUT_MANIFEST_V1.json"
    )
    build = read_json(
        M4_ROOT / "02_parameterized_cad" / "DIGITAL_PROTOTYPE_BUILD_RECEIPT_V1.json"
    )
    mass_audit = read_json(
        M4_ROOT
        / "03_mass_properties"
        / "M4_MASS_MATERIAL_TOLERANCE_MECHANISM_AUDIT_V1.json"
    )
    structural = read_json(
        M4_ROOT / "07_structural_model" / "STRUCTURAL_ANALYSIS_ENTRY_GATE.json"
    )
    sim_gate = read_json(SIM14_ROOT / "evidence" / "SIM14_DYNAMICS_GRASPING_GATE.json")
    sim_binding = read_json(
        SIM14_ROOT / "evidence" / "SIM14_PRODUCTION_BINDING_RECEIPT.json"
    )
    sim_tests = read_json(SIM14_ROOT / "evidence" / "SIM14_TEST_RESULTS.json")

    preconditions = {
        "frozen_inputs_pass": inputs.get("status") == "PASS",
        "root_independent_validation_pass": validation.get("status")
        == "PASS_EXPECTED_HOLDS_PRESERVED",
        "master_build_pass": build.get("verdict")
        == "M4_MASTER_DIGITAL_PROTOTYPE_BUILD_PASS_WITH_RELEASE_HOLDS",
        "mass_material_tolerance_mechanism_integrity_pass": mass_audit.get("status")
        == "PASS_FAIL_CLOSED_PACKAGE_INTEGRITY_M4_RELEASE_STILL_HOLD",
        "structural_gate_remains_hold": structural.get("gate_status") == "HOLD",
        "formal_fea_run_count_zero": structural.get("formal_fea_run_count") == 0,
        "sim14_diagnostic_kernel_pass": sim_gate.get("overall_status")
        == "PASS_DIAGNOSTIC_KERNEL_HOLD_PRODUCTION_DYNAMICS",
        "sim14_all_required_assets_hash_bound": sim_binding.get(
            "unresolved_required_artifacts"
        )
        == []
        and len(sim_binding.get("resolved_hash_bound_artifacts", [])) == 14,
        "sim14_cross_domain_audit_hash_bound": (
            "mass_material_tolerance_mechanism_audit"
            in sim_binding.get("resolved_hash_bound_artifacts", [])
        )
        and sim_binding.get("closure_audit", {}).get(
            "nested_artifact_hashes_verified"
        )
        == 13,
        "sim14_production_dynamics_not_ready": sim_binding.get(
            "production_dynamics_ready"
        )
        is False,
        "sim14_tests_pass": sim_tests.get("tests_failed") == 0
        and sim_tests.get("exit_code") == 0,
        "memory_gate_truth_preserved": build.get("memory_gate", {}).get(
            "memory_gate_passed"
        )
        is False
        and build.get("memory_gate", {}).get("owner_override_used") is True,
    }
    all_preconditions = all(preconditions.values())

    payload = {
        "schema": "MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_GATE_V1",
        "generated_local": datetime.now().astimezone().isoformat(),
        "phase": "M4_SPACECRAFT_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE",
        "baseline_out": "V7_SPACECRAFT_MECHANICAL_DIGITAL_PROTOTYPE_WORKING",
        "release_claim_ceiling": "COMPETITION_ENGINEERING_DIGITAL_PROTOTYPE_ONLY",
        "preconditions": preconditions,
        "release_tokens": {
            "digital_prototype": {
                "token": "M4_DIGITAL_PROTOTYPE_RELEASED",
                "issued": all_preconditions,
                "status": "PASS_SCOPED_WORKING_RELEASE" if all_preconditions else "HOLD",
                "scope": [
                    "hash_bound_FreeCAD_master_and_neutral_STEP",
                    "default_configuration_static_geometry",
                    "explicit_frame_and_unresolved_slot_architecture",
                    "nine_configuration_data_contract",
                    "prototype_drawing_and_nonprocurement_BOM_package",
                ],
                "exclusions": [
                    "complete_physical_B601_geometry_and_collision",
                    "spacecraft_to_M3R_load_bridge",
                    "system_mass_center_of_mass_and_inertia_release",
                    "continuous_motion_collision",
                    "manufacturing_qualification_and_flight_release",
                ],
            },
            "structural_entry": {
                "token": "STRUCTURAL_ANALYSIS_READY",
                "issued": False,
                "status": "HOLD",
                "formal_fea_authorized": False,
                "formal_fea_run_count": structural.get("formal_fea_run_count"),
            },
            "bounded_diagnostic_dynamics": {
                "token": "SIM14_BOUNDED_DYNAMICS_READY",
                "issued": all_preconditions,
                "status": "PASS_DIAGNOSTIC_ONLY" if all_preconditions else "HOLD",
                "scope": [
                    "hash_and_schema_validation",
                    "fail_closed_action_mask",
                    "ideal_two_body_rigid_lock_momentum_closure",
                    "grasp_event_state_machine",
                ],
                "engineering_prediction": False,
            },
            "production_contact_rl": {
                "token": "PHYSICS_GATED_CONTACT_RL_READY",
                "issued": False,
                "status": "HOLD",
            },
        },
        "quantitative_receipt": {
            "frozen_input_file_count": inputs.get("file_count"),
            "frozen_input_total_size_bytes": inputs.get("total_size_bytes"),
            "root_validation_checks_passed": validation.get("pass_count"),
            "root_validation_checks_failed": validation.get("fail_count"),
            "freecad_objects": build.get("fcstd_cold_reopen", {}).get("object_count"),
            "freecad_internal_links": build.get("fcstd_cold_reopen", {}).get(
                "app_link_count"
            ),
            "step_solids": build.get("step_cold_reopen", {}).get("solids"),
            "required_configurations": 9,
            "released_system_mass_count": 0,
            "released_system_center_of_mass_count": 0,
            "released_system_inertia_count": 0,
            "sim14_required_asset_bindings_resolved": len(
                sim_binding.get("resolved_hash_bound_artifacts", [])
            ),
            "sim14_required_asset_binding_count": 14,
            "sim14_cross_domain_audited_artifact_count": sim_binding.get(
                "closure_audit", {}
            ).get("nested_artifact_hashes_verified"),
            "sim14_tests_passed": sim_tests.get("tests_passed"),
            "sim14_tests_failed": sim_tests.get("tests_failed"),
            "diagnostic_branch_B_service_mass_kg": 29.081436764691,
            "diagnostic_22kg_composite_mass_kg": 51.081436764691,
            "diagnostic_150kg_composite_mass_kg": 179.081436764691,
            "diagnostic_momentum_residual_limit": 1.0e-12,
            "diagnostic_momentum_residual_limit_role": "software numerical closure threshold not physical tolerance",
        },
        "mandatory_holds": [
            "SPACECRAFT_TO_M3R_LOAD_BRIDGE_AND_LOAD_PATH_CONTINUITY_HOLD",
            "M_DYNAMICS_VS_PHYSICAL_ARM_BASE_FRAME_ALIAS_RECONCILIATION_HOLD",
            "B601_PHYSICAL_LINK_GEOMETRY_AND_COLLISION_HOLD",
            "SOLAR_ARRAY_STOWED_FAILED_STATE_AND_HINGE_SWEEP_HOLD",
            "GRIPPER_FINGERS_CONTACT_ACTUATOR_RETENTION_AND_LIFE_HOLD",
            "ARM_HDRM_ARCHITECTURE_INTERFACE_AND_RELIABILITY_HOLD",
            "TARGET_IDENTITY_CAPTURE_TRANSFORM_AND_CONTACT_SURFACE_HOLD",
            "NINE_CONFIGURATION_SYSTEM_MASS_COM_INERTIA_UNCERTAINTY_HOLD",
            "MATERIAL_PROCESS_TOLERANCE_LOADS_AND_STRUCTURAL_ENTRY_HOLD",
            "CONTACT_FLEXIBLE_BODY_PRODUCTION_DYNAMICS_AND_RL_HOLD",
            "MANUFACTURING_LAUNCHER_QUALIFICATION_AND_FLIGHT_HOLD",
        ],
        "next_authorized_loop": {
            "id": "M5_PHYSICAL_AUTHORITY_AND_DYNAMICS_CLOSURE",
            "register": "12_release/M4_NEXT_LOOP_ACTION_REGISTER_V1.yaml",
            "authorized_now": [
                "physical_input_acquisition_and_measurement_planning",
                "controlled_geometry_and_collision_asset_completion",
                "mass_material_tolerance_and_mechanism_closure",
                "bounded_Sim14_diagnostic_research",
            ],
            "not_authorized_now": [
                "formal_FEA",
                "production_contact_dynamics",
                "RL_training_performance_claims",
                "manufacturing_procurement_qualification_or_flight_release",
            ],
        },
        "memory_execution_record": build.get("memory_gate"),
        "overall_status": (
            "PASS_SCOPED_M4_DIGITAL_PROTOTYPE_AND_SIM14_DIAGNOSTIC_WITH_MANDATORY_PHYSICAL_HOLDS"
            if all_preconditions
            else "HOLD_M4_RELEASE_PRECONDITION_FAILURE"
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "all_preconditions": all_preconditions,
                "digital_prototype_token_issued": payload["release_tokens"][
                    "digital_prototype"
                ]["issued"],
                "bounded_dynamics_token_issued": payload["release_tokens"][
                    "bounded_diagnostic_dynamics"
                ]["issued"],
                "structural_token_issued": payload["release_tokens"][
                    "structural_entry"
                ]["issued"],
                "production_contact_rl_token_issued": payload["release_tokens"][
                    "production_contact_rl"
                ]["issued"],
                "overall_status": payload["overall_status"],
            },
            indent=2,
        )
    )
    return 0 if all_preconditions else 2


if __name__ == "__main__":
    raise SystemExit(main())
