from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CONTRACTS = HERE / "contracts"
EVIDENCE = HERE / "evidence"
RESULTS = HERE / "results"

SOURCE_BINDINGS_PATH = CONTRACTS / "PHASE_B4_SOURCE_BINDINGS_V1.json"
MODEL_CONTRACT_PATH = CONTRACTS / "PHASE_B4_MODEL_CONTRACT_V1.json"
GOVERNANCE_CONTRACT_PATH = CONTRACTS / "PHASE_B4_GOVERNANCE_CONTRACT_V1.json"
UNITS_LEDGER_PATH = CONTRACTS / "PHASE_B4_UNCERTAINTY_AND_UNITS_LEDGER_V1.json"
NUMERICAL_CONTRACT_PATH = CONTRACTS / "PHASE_B4_NUMERICAL_ACCEPTANCE_CONTRACT_V1.json"

SOURCE_MANIFEST_PATH = EVIDENCE / "SIM13_V4B4_CONTRACT_SOURCE_MANIFEST_V1.json"
VALIDATION_PATH = EVIDENCE / "SIM13_V4B4_CONTRACT_VALIDATION_V1.json"
EVIDENCE_MANIFEST_PATH = EVIDENCE / "SIM13_V4B4_CONTRACT_EVIDENCE_MANIFEST_V1.json"
PRE_AUDIT_GATE_PATH = RESULTS / "SIM13_V4B4_CONTRACT_PRE_AUDIT_GATE_V1.json"
AUDIT_RECEIPT_PATH = EVIDENCE / "SIM13_V4B4_CONTRACT_INDEPENDENT_AUDIT_RECEIPT_V1.json"
FINAL_GATE_PATH = RESULTS / "SIM13_V4B4_CONTRACT_AUDITED_GATE_V1.json"
TERMINAL_MANIFEST_PATH = RESULTS / "SIM13_V4B4_CONTRACT_TERMINAL_SELF_EXCLUDED_MANIFEST_V1.json"

EXPECTED_TEST_COUNT = 62
EXPECTED_CONTRACT_GATE_STATUS = (
    "PASS_PHASE_B4_CONTRACT_FREEZE_ONLY__SYNTHETIC_6DOF_CONSTRAINT_ACQUISITION_RELEASE_"
    "PREREGISTERED__IMPLEMENTATION_NOT_STARTED__ALL_PHYSICAL_CURRENT_LOCK_HELD_RELEASE_NC19_HOLDS"
)
EXPECTED_SOURCE_BINDINGS = {
    "b3_audited_gate": (
        "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b3_branched_dual_contact_soft_capture/results/SIM13_V4B3_AUDITED_GATE_V1.json",
        "UPSTREAM_AUDITED_SCOPE_AND_HOLD_RULING",
    ),
    "b3_reference_trace": (
        "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b3_branched_dual_contact_soft_capture/evidence/SIM13_V4B3_DUAL_CONTACT_TRACE_V1.json",
        "FIRST_QUALIFYING_SAMPLE_AND_PRE_SWITCH_STATE",
    ),
    "b3_ledger": (
        "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b3_branched_dual_contact_soft_capture/evidence/SIM13_V4B3_DUAL_CONTACT_LEDGER_V1.json",
        "UPSTREAM_DIMENSIONED_LEDGER",
    ),
    "b3_model_contract": (
        "30_simulation/sim_13_physics_gated_embodied_grasping/v4_synthetic_contact_capture_diagnostic/phase_b3_branched_dual_contact_soft_capture/contracts/PHASE_B3_MODEL_CONTRACT_V1.json",
        "UPSTREAM_CONTACT_AND_RANK5_CONTRACT",
    ),
    "m06_contact_lock_contract": (
        "30_simulation/e18_b601_mission_input_branches/01_contracts/M06_22_CONTACT_AND_LOCK_V1.yaml",
        "PHYSICAL_CONTACT_AND_LOCK_HOLD",
    ),
    "m07_attached_target_recovery_contract": (
        "30_simulation/e18_b601_mission_input_branches/01_contracts/M07_22_ATTACHED_TARGET_RECOVERY_V1.yaml",
        "NULL_LOCK_TRANSFORM_STIFFNESS_RETENTION_AND_RECOVERY_INPUTS",
    ),
    "m5_contact_parameter_contract": (
        "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/05_contact_identification/CONTACT_MODEL_PARAMETER_CONTRACT_V1.yaml",
        "NULL_PHYSICAL_CONTACT_PARAMETERS_AND_FRAMES",
    ),
    "gripper_engineering_pack_v2": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp5_mechanisms/GRIPPER_ENGINEERING_PACK_V2.yaml",
        "DESIGN_CANDIDATE_AND_ACTUATOR_CONTACT_HOLDS",
    ),
    "formal_sim13_v2_gate": (
        "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/results/SIM13_V2_PREBIND_SOURCE_GATE_V1.json",
        "FORMAL_15_OF_20_AND_NC19_HOLD",
    ),
    "formal_sim13_v2_negative_controls": (
        "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/evidence/SIM13_V2_NEGATIVE_CONTROLS_PREBIND_V1.json",
        "NC19_DEFINITION_AND_DEPENDENCY_HOLD",
    ),
    "current_mechanical_binding_audit": (
        "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/09_downstream_rebind/SIM13_CURRENT_MECHANICAL_BINDING_AUDIT_GATE_V1.json",
        "CURRENT_PRODUCTION_BINDING_INVALIDATED",
    ),
    "digital_prototype_frame_tree": (
        "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/01_system_architecture/DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml",
        "CHILD_TO_PARENT_TRANSFORM_CONVENTION_AND_UNKNOWN_MASK_RULE",
    ),
    "accepted_arm_urdf_read_only": (
        "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf",
        "READ_ONLY_TOPOLOGY_ONLY_NO_GENERATION",
    ),
}
EXPECTED_AUTHORIZED_SCOPE = {
    "read_existing_sources": True,
    "freeze_synthetic_model_contract": True,
    "implement_contract_validator_and_independent_contract_audit": True,
    "implement_dynamics_solver": False,
    "modify_upstream_b3": False,
    "modify_or_generate_urdf": False,
    "instantiate_system_interface": False,
    "invoke_unified_private_builder_or_generator": False,
}
EXPECTED_REQUIRED_FALSE_KEYS = {
    "b4_solver_implemented",
    "physical_dual_contact_identified",
    "physical_friction_identified",
    "physical_actuator_timing_identified",
    "physical_lock_implemented",
    "physical_release_implemented",
    "held_capture_passed",
    "grasp_success_claimed",
    "target_attached_claimed",
    "current_system_bound",
    "formal_nc19_credit",
    "owner_authorized",
    "production_ready",
    "release_authorized",
    "next_stage_authorized",
}
EXPECTED_CONTRACT_FREEZE_MUTATION_IDS = [
    "B4CFNC01_SOURCE_SHA_DRIFT", "B4CFNC02_TRIGGER_CHERRY_PICK", "B4CFNC03_B3_RANK6_REWRITE",
    "B4CFNC04_AXIAL_MISSING_WRENCH_MISFORMULA", "B4CFNC05_UNSCALED_MIXED_CONDITION",
    "B4CFNC06_CONTACT_CONSTRAINT_DOUBLE_ACTIVITY", "B4CFNC07_CONTACT_POTENTIAL_OMISSION",
    "B4CFNC08_NONZERO_REMOVAL_IMPULSE", "B4CFNC09_POST_REMOVAL_CONTACT_REACTIVATION",
    "B4CFNC10_CURRENT_OR_FORMAL_AUTHORITY_TRUE", "B4CFNC11_NULL_PHYSICAL_INPUT_ZERO_FILL",
    "B4CFNC12_SUCCESS_TERMINAL_ALIAS",
]
EXPECTED_FUTURE_SOLVER_NEGATIVE_CONTROL_IDS = [
    "B4NC01_SOURCE_BYTE_SHA_DRIFT", "B4NC02_TRIGGER_INDEX_CHERRY_PICK",
    "B4NC03_DUPLICATE_JC_ROW_RANK5_WITH_PINV_ATTEMPT", "B4NC04_L_COLUMN_RANK_LOSS",
    "B4NC05_ACQUISITION_PINV_OR_LSTSQ_CALL", "B4NC06_REMOVE_LENGTH_SCALING_D_EQUALS_I",
    "B4NC07_MIXED_UNIT_CONDITION_NUMBER_REPORTED", "B4NC08_AXIAL_MISSING_WRENCH_MISFORMULA",
    "B4NC09_CONTACT_AND_CONSTRAINT_SIMULTANEOUSLY_ACTIVE", "B4NC10_CONTACT_POTENTIAL_OMITTED",
    "B4NC11_CONTACT_POTENTIAL_DOUBLE_COUNTED", "B4NC12_PROJECTION_DISSIPATION_SIGN_FLIP",
    "B4NC13_TARGET_CHILD_MASS_OMITTED", "B4NC14_TARGET_CHILD_MASS_DOUBLE_COUNTED",
    "B4NC15_ACTIVE_INTERMEDIATE_LEDGER_MUTATION_WITH_GOOD_TERMINAL_LABEL",
    "B4NC16_REMOVAL_RESTORES_PRE_ACQUISITION_TWIST", "B4NC17_REMOVAL_ZEROES_TARGET_TWIST",
    "B4NC18_REMOVAL_RETURNS_DISSIPATED_ENERGY", "B4NC19_CLEARANCE_DWELL_NEGATIVE_GAP_INSERTION",
    "B4NC20_POST_REMOVAL_CONTACT_KERNEL_REACTIVATION", "B4NC21_PHYSICAL_OR_FORMAL_AUTHORITY_TRUE",
    "B4NC22_NULL_PHYSICAL_INPUT_ZERO_FILLED",
]
EXPECTED_ACTIVE_TOLERANCES = {
    "pose_translation_m": 1e-9,
    "pose_rotation_geodesic_rad": 1e-9,
    "relative_linear_twist_m_s": 1e-9,
    "relative_angular_twist_rad_s": 1e-9,
    "total_linear_momentum_drift_N_s": 1e-9,
    "total_angular_momentum_drift_about_fixed_inertial_origin_N_m_s": 1e-9,
    "mechanical_energy_plus_all_dissipation_drift_J": 1e-7,
    "ideal_constraint_power_W": 1e-10,
    "contact_force_while_constraint_active_N": 1e-12,
    "contact_torque_while_constraint_active_N_m": 1e-12,
}
EXPECTED_EVENT_TOLERANCES = {
    "snapshot_translation_identity_m": 1e-12,
    "snapshot_rotation_geodesic_rad": 1e-12,
    "rotation_orthogonality_inf": 1e-12,
    "rotation_determinant_error_abs": 1e-12,
    "quaternion_unit_norm_error_abs": 1e-12,
    "Jhat_Lhat_operator_inf_dimensionless": 1e-11,
    "post_constraint_linear_twist_m_s": 1e-10,
    "post_constraint_angular_twist_rad_s": 1e-10,
    "reduced_kkt_service_base_linear_component_m_s": 1e-10,
    "reduced_kkt_service_base_angular_component_rad_s": 1e-10,
    "reduced_kkt_R_joint_component_rad_s": 1e-10,
    "reduced_kkt_P_joint_component_m_s": 1e-10,
    "reduced_kkt_target_linear_component_m_s": 1e-10,
    "reduced_kkt_target_angular_component_rad_s": 1e-10,
    "combined_impulse_equation_service_base_linear_N_s": 1e-9,
    "combined_impulse_equation_service_base_angular_N_m_s": 1e-9,
    "combined_impulse_equation_R_joint_N_m_s": 1e-9,
    "combined_impulse_equation_P_joint_N_s": 1e-9,
    "combined_impulse_equation_target_linear_N_s": 1e-9,
    "combined_impulse_equation_target_angular_N_m_s": 1e-9,
    "total_linear_momentum_jump_N_s": 1e-9,
    "total_angular_momentum_jump_about_fixed_inertial_origin_N_m_s": 1e-9,
    "projection_energy_identity_J": 1e-9,
    "switch_energy_identity_J": 1e-9,
    "contact_potential_sum_identity_J": 1e-12,
    "negative_dissipation_allowance_J": 1e-12,
}
EXPECTED_REMOVAL_TOLERANCES = {
    "clearance_gap_min_m": 1e-6,
    "gap_reentry_closing_speed_tolerance_m_s": 1e-6,
    "minimum_active_diagnostic_dwell_s": 0.001,
    "clearance_dwell_s": 0.001,
    "clearance_continuity_rule": "event-interpolated gaps and gap rates must satisfy both inequalities throughout the complete dwell; sample endpoints alone are insufficient",
    "removal_service_base_linear_velocity_jump_m_s": 1e-12,
    "removal_service_base_angular_velocity_jump_rad_s": 1e-12,
    "removal_R_joint_velocity_jump_rad_s": 1e-12,
    "removal_P_joint_velocity_jump_m_s": 1e-12,
    "removal_target_linear_velocity_jump_m_s": 1e-12,
    "removal_target_angular_velocity_jump_rad_s": 1e-12,
    "removal_linear_impulse_N_s": 1e-12,
    "removal_angular_impulse_N_m_s": 1e-12,
    "ideal_constraint_stored_energy_J": 1e-12,
    "cross_integrator_acquisition_event_time_s": 0.00025,
    "cross_integrator_removal_event_time_s": 0.00025,
    "post_removal_observation_s": 0.005,
}
EXPECTED_CONTRACT_CANONICAL_SHA256 = {
    "model": "CE39890A558901DFE97922534CC15FEF42B9DA527C089D308CA7BBC2CFD2F0AF",
    "governance": "2533588DC8C4FB807BC0DE3CBC8069748593D0AF08E077D5D1CD2D5503ECDFE1",
    "units": "63E7F07FB9B84CAC469176A4F3BFFAA2F48DF6446C620D629BFDDDBE51E660A4",
    "numerical": "80D8AC949B4F28074E04DF092890038DA339734499AE12111E6DF48ED7915BDB",
    "source_bindings": "F731260C0D318BC3A0CB3D3206E0F488D19254286498A9D0CD3A0757D3E18BAC",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _canonical_payload_sha256(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return _sha256_bytes(data)


def _record(path: Path, role: str) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "role": role,
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": len(data),
        "sha256": _sha256_bytes(data),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _bound_record(source_bindings: dict[str, Any], source_id: str) -> dict[str, Any]:
    return next(row for row in source_bindings["sources"] if row["id"] == source_id)


def _read_bound_text(source_bindings: dict[str, Any], source_id: str) -> str:
    return (ROOT / _bound_record(source_bindings, source_id)["path"]).read_text(encoding="utf-8")


def _read_bound_json(source_bindings: dict[str, Any], source_id: str) -> dict[str, Any]:
    return json.loads(_read_bound_text(source_bindings, source_id))


def _projection_fixture() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rows = np.arange(6, dtype=float)[:, None]
    cols = np.arange(14, dtype=float)[None, :]
    a_map = 0.02 * np.sin(0.31 * (rows + 1.0) * (cols + 1.0))
    a_map[:, :6] += np.array(
        [
            [1.0, 0.0, 0.0, 0.0, 0.12, -0.08],
            [0.0, 1.0, 0.0, -0.12, 0.0, 0.09],
            [0.0, 0.0, 1.0, 0.08, -0.09, 0.0],
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        ]
    )
    embedding = np.vstack((np.eye(14), a_map))
    constraint = np.hstack((-a_map, np.eye(6)))
    seed = np.arange(400, dtype=float).reshape(20, 20)
    base = np.sin(0.017 * (seed + 1.0))
    mass = base.T @ base + np.diag(np.linspace(1.0, 3.0, 20))
    velocity = 0.01 * np.cos(np.arange(20, dtype=float) + 0.2)
    scale = np.diag([1.0, 1.0, 1.0, 0.17, 0.17, 0.17])
    return mass, embedding, constraint, velocity, scale


def projection_identity_metrics() -> dict[str, float | int]:
    mass, embedding, constraint, velocity, scale = _projection_fixture()
    attached_mass = embedding.T @ mass @ embedding
    eta_plus = np.linalg.solve(attached_mass, embedding.T @ mass @ velocity)
    reduced = embedding @ eta_plus
    scaled_constraint = scale @ constraint
    reference_length = float(scale[3, 3])
    s_eta_diag = np.array([1.0] * 3 + [reference_length] * 3 + [reference_length] * 6 + [1.0] * 2)
    s_z_diag = np.concatenate((s_eta_diag, np.ones(3), np.full(3, reference_length)))
    l_hat = np.diag(s_z_diag) @ embedding @ np.diag(1.0 / s_eta_diag)
    j_hat = scaled_constraint @ np.diag(1.0 / s_z_diag)
    effective = scaled_constraint @ np.linalg.solve(mass, scaled_constraint.T)
    relative = scaled_constraint @ velocity
    block = np.block(
        [
            [mass, -scaled_constraint.T],
            [scaled_constraint, np.zeros((6, 6))],
        ]
    )
    block_solution = np.linalg.solve(block, np.concatenate((mass @ velocity, np.zeros(6))))
    kkt = block_solution[:20]
    impulse = block_solution[20:]
    loss_formula = 0.5 * relative @ np.linalg.solve(effective, relative)
    loss_direct = 0.5 * velocity @ mass @ velocity - 0.5 * kkt @ mass @ kkt
    return {
        "L_hat_rank": int(np.linalg.matrix_rank(l_hat)),
        "J_hat_rank": int(np.linalg.matrix_rank(j_hat)),
        "Jhat_Lhat_operator_inf_dimensionless": float(np.linalg.norm(j_hat @ l_hat, ord=np.inf)),
        "attached_mass_min_eigenvalue": float(np.min(np.linalg.eigvalsh(0.5 * (attached_mass + attached_mass.T)))),
        "scaled_effective_mass_min_eigenvalue": float(np.min(np.linalg.eigvalsh(0.5 * (effective + effective.T)))),
        "reduced_kkt_inf_difference": float(np.linalg.norm(reduced - kkt, ord=np.inf)),
        "post_constraint_inf_residual": float(np.linalg.norm(scaled_constraint @ kkt, ord=np.inf)),
        "energy_loss_formula_j": float(loss_formula),
        "energy_loss_direct_j": float(loss_direct),
        "energy_loss_identity_error_j": float(abs(loss_formula - loss_direct)),
    }


def evaluate_contract_payloads(
    model: dict[str, Any],
    governance: dict[str, Any],
    units: dict[str, Any],
    numerical: dict[str, Any],
    source_bindings: dict[str, Any],
    *,
    verify_files: bool = True,
) -> dict[str, dict[str, Any]]:
    checks: dict[str, dict[str, Any]] = {}

    def add(check_id: str, name: str, passed: bool, evidence: Any) -> None:
        checks[check_id] = {"name": name, "pass": bool(passed), "evidence": evidence}

    actual_contract_hashes = {
        "model": _canonical_payload_sha256(model),
        "governance": _canonical_payload_sha256(governance),
        "units": _canonical_payload_sha256(units),
        "numerical": _canonical_payload_sha256(numerical),
        "source_bindings": _canonical_payload_sha256(source_bindings),
    }
    schemas_ok = (
        model.get("schema") == "SIM13_V4B4_SYNTHETIC_6DOF_CONSTRAINT_ACQUISITION_RELEASE_MODEL_CONTRACT_V1"
        and model.get("scope") == "CONTRACT_PREREGISTRATION_ONLY__SYNTHETIC_DIAGNOSTIC"
        and governance.get("schema") == "SIM13_V4B4_GOVERNANCE_CONTRACT_V1"
        and units.get("schema") == "SIM13_V4B4_UNCERTAINTY_AND_UNITS_LEDGER_V1"
        and numerical.get("schema") == "SIM13_V4B4_NUMERICAL_ACCEPTANCE_CONTRACT_V1"
        and source_bindings.get("schema") == "SIM13_V4B4_SOURCE_BINDINGS_V1"
        and actual_contract_hashes == EXPECTED_CONTRACT_CANONICAL_SHA256
    )
    add("B4C-01", "five contract schemas and canonical payloads are exact", schemas_ok, {"schemas": [model.get("schema"), governance.get("schema"), units.get("schema"), numerical.get("schema"), source_bindings.get("schema")], "canonical_sha256": actual_contract_hashes})

    rows = source_bindings.get("sources", [])
    actual_source_bindings = {
        row.get("id"): (row.get("path"), row.get("role"))
        for row in rows
        if isinstance(row, dict)
    }
    source_unique = (
        len(rows) == len(EXPECTED_SOURCE_BINDINGS)
        and actual_source_bindings == EXPECTED_SOURCE_BINDINGS
        and len({row.get("id") for row in rows}) == len(rows)
        and len({row.get("path") for row in rows}) == len(rows)
        and len({row.get("role") for row in rows}) == len(rows)
        and source_bindings.get("scope") == "READ_ONLY_HASH_PINNED_PREREGISTRATION_INPUTS"
        and source_bindings.get("source_mutation_authorized") is False
        and source_bindings.get("formal_state_inheritance_authorized") is False
    )
    add("B4C-02", "source ids map to the exact frozen paths and roles", source_unique, {"count": len(rows), "actual": actual_source_bindings})

    source_file_checks: list[dict[str, Any]] = []
    if verify_files:
        for row in rows:
            try:
                path = (ROOT / row["path"]).resolve()
                inside = path.is_relative_to(ROOT.resolve())
                data = path.read_bytes() if inside else b""
                passed = inside and len(data) == row["bytes"] and _sha256_bytes(data) == row["sha256"]
                source_file_checks.append({"id": row.get("id"), "pass": passed, "inside_root": inside, "bytes": len(data), "sha256": _sha256_bytes(data) if data else None})
            except Exception as exc:  # fail closed diagnostic
                source_file_checks.append({"id": row.get("id"), "pass": False, "error": type(exc).__name__})
        source_files_ok = len(source_file_checks) == len(rows) and all(row["pass"] for row in source_file_checks)
    else:
        source_files_ok = all(isinstance(row.get("sha256"), str) and len(row["sha256"]) == 64 and row.get("bytes", 0) > 0 for row in rows)
        source_file_checks = [{"verification": "structure_only_for_mutation_test", "pass": source_files_ok}]
    add("B4C-03", "all bound sources remain inside root with exact bytes and SHA256", source_files_ok, source_file_checks)

    if verify_files and source_files_ok:
        b3_gate = _read_bound_json(source_bindings, "b3_audited_gate")
        b3_ok = (
            b3_gate.get("final_gate") is True
            and b3_gate.get("audited_metrics", {}).get("all_qualifying_grasp_map_rank") == 5
            and b3_gate.get("audited_metrics", {}).get("full_6d_wrench_span") is False
            and b3_gate.get("audited_metrics", {}).get("full_6d_force_closure") is False
            and not any(b3_gate.get("authorizations", {}).get(key) for key in ("lock_implemented", "grasp_success", "current_system_bound", "formal_nc19_closed", "release_authorized", "next_stage_authorized"))
        )
    else:
        b3_ok = model.get("upstream_ruling", {}).get("b3_grasp_map_rank") == 5 and model.get("upstream_ruling", {}).get("full_6d_wrench_span") is False
        b3_gate = {"verification": "contract_side_for_mutation_test"}
    add("B4C-04", "B3 remains audited rank5 non6D with lock/current/formal holds", b3_ok, b3_gate if not verify_files else {"status": b3_gate.get("overall_status")})

    trigger = model.get("trigger_contract", {})
    if verify_files and source_files_ok:
        trace = _read_bound_json(source_bindings, "b3_reference_trace")
        records = trace.get("reference_records", [])
        qualifying = [index for index, row in enumerate(records) if row.get("soft_capture_criteria", {}).get("soft_capture_transient_qualifies") is True and row.get("soft_capture_criteria", {}).get("all_ledgers_closed") is True]
        trigger_ok = (
            bool(qualifying)
            and qualifying[0] == trigger.get("reference_record_index") == 205
            and records[qualifying[0]].get("time_s") == trigger.get("reference_time_s")
            and sum(index <= qualifying[0] for index in qualifying) == trigger.get("required_upstream_candidate_count_at_or_before_trigger") == 1
            and trigger.get("interpolation_rule_for_future_solver") == "locate the earliest predicate transition independently for each integrator; never force the frozen reference timestamp into another integrator"
            and trigger.get("cherry_pick_forbidden") is True
        )
        trigger_row = records[205] if len(records) > 205 else {}
    else:
        trigger_ok = trigger.get("reference_record_index") == 205 and trigger.get("reference_time_s") == 0.051250000000000004 and trigger.get("required_upstream_candidate_count_at_or_before_trigger") == 1 and trigger.get("interpolation_rule_for_future_solver") == "locate the earliest predicate transition independently for each integrator; never force the frozen reference timestamp into another integrator" and trigger.get("cherry_pick_forbidden") is True
        trigger_row = {}
    add("B4C-05", "first all-predicate B3 candidate is frozen without cherry picking", trigger_ok, {"trigger": trigger, "source_row_time": trigger_row.get("time_s")})

    if verify_files and source_files_ok and trigger_row:
        criteria = trigger_row.get("soft_capture_criteria", {})
        raw_predicates_ok = (
            trigger_row.get("state_label") == "SOFT_CAPTURE_TRANSIENT_CANDIDATE"
            and criteria.get("left_contact") is True
            and criteria.get("right_contact") is True
            and criteria.get("all_ledgers_closed") is True
            and criteria.get("soft_capture_transient_qualifies") is True
            and criteria.get("dual_contact_dwell_s", 0.0) >= 0.001
        )
    else:
        raw_predicates_ok = trigger.get("required_state_label") == "SOFT_CAPTURE_TRANSIENT_CANDIDATE" and trigger.get("required_left_contact") is True and trigger.get("required_right_contact") is True
        criteria = {"verification": "contract_side_for_mutation_test"}
    add("B4C-06", "trigger requires raw B3 predicates and ledgers not label alone", raw_predicates_ok, criteria)

    if verify_files and source_files_ok and trigger_row:
        prior_labels = [row.get("state_label", "") for row in records[:206]]
        no_prior_abort = not any("ABORT" in label or "FAIL_CLOSED" in label for label in prior_labels)
        p_left = np.asarray(trigger_row["contacts"]["left"]["common_contact_point_inertial_m"], dtype=float)
        p_right = np.asarray(trigger_row["contacts"]["right"]["common_contact_point_inertial_m"], dtype=float)
        source_anchor_metrics = {
            "reference_length_m": float(0.5 * np.linalg.norm(p_right - p_left)),
            "left_contact_elastic_energy_j": float(trigger_row["contacts"]["left"]["elastic_energy_j"]),
            "right_contact_elastic_energy_j": float(trigger_row["contacts"]["right"]["elastic_energy_j"]),
        }
        source_anchor_metrics["total_contact_elastic_energy_j"] = source_anchor_metrics["left_contact_elastic_energy_j"] + source_anchor_metrics["right_contact_elastic_energy_j"]
        frozen_anchors = numerical.get("frozen_reference_anchors", {})
        anchor_ok = all(source_anchor_metrics[key] == frozen_anchors.get(key) for key in source_anchor_metrics)
    else:
        no_prior_abort = "no prior DIAGNOSTIC_FAIL_CLOSED or upstream ABORTED_SAFE" in trigger.get("selection_rule", "")
        source_anchor_metrics = numerical.get("frozen_reference_anchors", {})
        anchor_ok = source_anchor_metrics.get("reference_length_m") == 0.03999999992105392 and source_anchor_metrics.get("total_contact_elastic_energy_j") == 8.059714931729952e-7
    add("B4C-06A", "no upstream abort precedes the frozen trigger", no_prior_abort, {})
    add("B4C-06B", "L_ref and both contact potentials are independently recomputed from raw B3 trace", anchor_ok, source_anchor_metrics)

    if verify_files and source_files_ok:
        m06 = _read_bound_text(source_bindings, "m06_contact_lock_contract")
        m06_ok = all(token in m06 for token in ("HOLD_NO_PHYSICAL_CONTACT_ACTUATOR_OR_LOCK_AUTHORITY", "lock_confirmed: null", "lock_retention_force_N: null", "released_for_mission_gate: false", "next_stage_authorized: false"))
        m07 = _read_bound_text(source_bindings, "m07_attached_target_recovery_contract")
        m07_ok = all(token in m07 for token in ("T_gripper_target_locked: null", "lock_stiffness: null", "lock_retention_force_N: null", "lock_confirmation_predicate: null", "ATTACHED_TARGET_RECOVERY_HOLD"))
        m5 = _read_bound_text(source_bindings, "m5_contact_parameter_contract")
        m5_ok = all(token in m5 for token in ("zero_fill_forbidden: true", "left_contact_frame_T_gripper_link: null", "right_contact_frame_T_gripper_link: null", "physical_contact_kernel_authorized: false"))
    else:
        holds = governance.get("required_upstream_holds", {})
        m06_ok = holds.get("physical_contact_and_lock") == "HOLD_NO_PHYSICAL_CONTACT_ACTUATOR_OR_LOCK_AUTHORITY"
        m07_ok = holds.get("physical_lock_transform") is None and holds.get("physical_retention_force") is None
        m5_ok = holds.get("physical_contact_kernel_authorized") is False and holds.get("left_contact_frame_T_gripper_link") is None and holds.get("right_contact_frame_T_gripper_link") is None
    add("B4C-07", "M06 physical contact actuator lock authority remains HOLD", m06_ok, {})
    add("B4C-08", "M07 lock transform stiffness retention recovery remain null HOLD", m07_ok, {})
    add("B4C-09", "M5 physical contact frames and kernel remain null HOLD with no zero fill", m5_ok, {})

    if verify_files and source_files_ok:
        formal_gate = _read_bound_json(source_bindings, "formal_sim13_v2_gate")
        formal_source_ok = formal_gate.get("formal_negative_controls_passed") == 15 and formal_gate.get("formal_negative_controls_declared") == 20 and formal_gate.get("formal_negative_controls_hold_ids") == ["NC15", "NC16", "NC18", "NC19", "NC20"] and formal_gate.get("contact_grasp_gate_passed") is False and formal_gate.get("system_urdf_available") is False
        binding_text = _read_bound_text(source_bindings, "current_mechanical_binding_audit")
        binding_invalid = "INVALIDATED" in binding_text
    else:
        formal = governance.get("formal_sim13_v2_state_unchanged", {})
        formal_source_ok = formal == {"passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"]}
        binding_invalid = governance.get("required_false", {}).get("current_system_bound") is False
    add("B4C-10", "formal Sim13 stays 15 of 20 with NC19 and four peers HOLD", formal_source_ok, {})
    add("B4C-11", "current production mechanical binding remains invalidated", binding_invalid, {})

    snapshot = model.get("synthetic_snapshot_transform", {})
    snapshot_ok = snapshot.get("name") == "T_PALM_TARGET_SNAPSHOT_SYNTHETIC" and snapshot.get("frozen_at_event") is True and snapshot.get("physical_lock_transform") is False and "T_gripper_target_locked" in snapshot.get("forbidden_aliases", [])
    add("B4C-12", "synthetic snapshot transform is event frozen and cannot alias physical lock", snapshot_ok, snapshot)

    attached = model.get("attached_subspace", {})
    attached_ok = model.get("pre_event_state", {}).get("external_impulse") == "zero" and attached.get("embedding_shape") == [20, 14] and attached.get("constraint_shape") == [6, 20] and attached.get("required_rank") == 6 and attached.get("required_identity") == "J_c*L=0" and "omega_palm cross" in attached.get("target_twist_mapping", "")
    add("B4C-13", "20D independent state projects to 14D full-rank attached subspace with offset kinematics", attached_ok, attached)

    projection = model.get("acquisition_impulse_projection", {})
    plastic_ok = projection.get("impact_type") == "perfectly_inelastic_ideal_constraint_acquisition" and projection.get("restitution") == 0.0 and "eta_plus=" in projection.get("primary_reduced_solution", "") and "[z_plus_kkt;lambda_bar]" in projection.get("independent_kkt_solution", "") and "without forming a Schur complement" in projection.get("independent_kkt_solution", "") and projection.get("required_dissipation_nonnegative") is True
    add("B4C-14", "acquisition is plastic with reduced and independent KKT solutions", plastic_ok, projection)
    rank_numeric = numerical.get("rank_and_linear_solve", {})
    coordinate_scaling = numerical.get("constraint_basis_scaling", {})
    solver_allowed = rank_numeric.get("acquisition_solve_allowed", {})
    scaling_ok = "D=diag(I_3,L_ref*I_3)" in projection.get("scaling", "") and projection.get("six_vector_raw_norm_forbidden") is True and projection.get("unscaled_mixed_unit_condition_number_forbidden") is True and projection.get("pseudoinverse_to_hide_rank_loss") == "forbidden" and rank_numeric.get("svd_relative_rank_tolerance") == 1e-10 and rank_numeric.get("expected_rank_L_hat") == 14 and rank_numeric.get("expected_rank_J_hat") == 6 and rank_numeric.get("expected_rank_Gbar") == 5 and rank_numeric.get("minimum_reference_length_m") == 0.001 and rank_numeric.get("scaled_effective_mass_condition_number_max") == 1e10 and rank_numeric.get("condition_number_whitelist") == ["W_bar_scaled"] and rank_numeric.get("condition_number_forbidden") == ["M_minus_unscaled", "M_attached_unscaled", "J_c_unscaled", "G_unscaled"] and rank_numeric.get("scaled_effective_mass_condition_number_definition") == "kappa_2(W_bar)=lambda_max(W_bar)/lambda_min(W_bar) after proving W_bar symmetric positive definite" and {"explicit_matrix_inverse", "pinv", "lstsq"}.issubset(set(rank_numeric.get("acquisition_solve_forbidden", []))) and "cholesky_solve" not in solver_allowed.get("direct_symmetric_indefinite_kkt", []) and "pivoted_symmetric_ldlt_solve" in solver_allowed.get("direct_symmetric_indefinite_kkt", []) and "diag(I3,L_ref*I3,L_ref*I6,I2)" in coordinate_scaling.get("S_eta", "") and "block_diag(S_eta,I3,L_ref*I3)" in coordinate_scaling.get("S_z", "") and coordinate_scaling.get("identity") == "J_hat*L_hat=0" and "audit-only coordinate scalings" in coordinate_scaling.get("use_boundary", "")
    add("B4C-15", "scaled rank conditioning keeps linear and angular units separate", scaling_ok, {})

    ruling = model.get("upstream_ruling", {})
    wrench = model.get("wrench_and_momentum_semantics", {})
    sixth_ok = ruling.get("b3_grasp_map_rank") == 5 and ruling.get("full_6d_wrench_span") is False and "ell-r_left cross p" in wrench.get("synthetic_missing_sixth_wrench_scalar", "") and "chi_missing=0" in wrench.get("rank5_identity", "") and "synthetic sixth constraint" in wrench.get("attribution", "") and "audit decomposition only" in wrench.get("normalized_rank5_unreachable_projection", "")
    add("B4C-16", "sixth axial couple is explicit synthetic mechanism demand not B3 contact", sixth_ok, {"ruling": ruling, "attribution": wrench.get("attribution")})
    wrench_ok = "ell+r_cross_p" in wrench.get("service_equivalent_wrench_about_palm_origin", "") and "shall not be added a second time" in wrench.get("service_equivalent_wrench_about_palm_origin", "") and wrench.get("linear_impulse_pair_sum") == "zero N*s" and wrench.get("angular_impulse_pair_about_same_inertial_origin") == "zero N*m*s" and "r_target_com_about_O cross p+ell" in wrench.get("target_angular_momentum_jump_about_fixed_inertial_origin", "") and wrench.get("required_reports") == ["linear_impulse_vector_N_s", "angular_impulse_vector_N_m_s", "ordinary_axis_projected_angular_impulse_N_m_s", "rank5_unreachable_chi_missing_N_m_s", "normalized_rank5_unreachable_projection_N_s", "transverse_angular_impulse_N_m_s", "service_linear_momentum_jump_N_s", "target_linear_momentum_jump_N_s", "service_angular_momentum_jump_N_m_s", "target_angular_momentum_jump_N_m_s"]
    add("B4C-17", "service impulse includes offset moment and total P H jump identities", wrench_ok, {})

    switch = model.get("contact_to_constraint_switch", {})
    switch_ok = switch.get("b3_contact_force_after_acquisition") == "disabled while synthetic constraint is active" and switch.get("double_counting_contact_and_constraint") == "forbidden" and switch.get("reference_left_contact_potential_at_t_a_minus_j") == 3.3837573393085704e-7 and switch.get("reference_right_contact_potential_at_t_a_minus_j") == 4.6759575924213813e-7 and switch.get("reference_total_contact_potential_at_t_a_minus_j") == 8.059714931729952e-7 and switch.get("contact_potential_sum") == "U_contact_minus=U_left_minus+U_right_minus with each side counted exactly once" and switch.get("projection_dissipation") == "D_projection=T_minus-T_plus" and switch.get("switch_dissipation") == "D_switch=D_projection+U_left_minus+U_right_minus" and switch.get("full_event_energy_identity") == "T_plus+D_B3_minus+D_switch=T_minus+U_left_minus+U_right_minus+D_B3_minus" and switch.get("energy_deletion") == "forbidden" and switch.get("actuator_work") == "zero; no actuator model exists"
    add("B4C-18", "contact-to-constraint switch avoids double counting and absorbs stored contact energy", switch_ok, switch)

    active = model.get("active_constraint_propagation", {})
    active_ok = active.get("state_dimension") == 14 and "target child body" in active.get("mass_matrix", "") and "M_combined*L_dot*eta" in active.get("bias", "") and "independently agrees" in active.get("bias", "") and active.get("ideal_constraint_power") == "zero" and active.get("external_force_and_torque") == "zero" and active.get("required_ledgers") == ["total_linear_momentum_N_s", "total_angular_momentum_about_fixed_inertial_origin_N_m_s", "mechanical_energy_plus_all_dissipation_J", "pose_residual_translation_m", "pose_residual_rotation_rad", "relative_twist_linear_m_s", "relative_twist_angular_rad_s"]
    add("B4C-19", "active reduced model includes target inertia and recomputed bias", active_ok, active)

    removal = model.get("release_contract", {})
    removal_ok = "z_after=z_before" in removal.get("release_mapping", "") and removal.get("release_impulse_linear_N_s") == 0.0 and removal.get("release_impulse_angular_N_m_s") == 0.0 and removal.get("ideal_constraint_stored_energy_J") == 0.0
    add("B4C-20", "constraint removal is state continuous with zero impulse and no energy return", removal_ok, removal)
    recontact_ok = "remain disabled" in removal.get("contact_kernel_after_removal", "") and "g_clearance_min" in removal.get("recontact_rule", "") and removal.get("clearance_gap_min_m", 0.0) > 0.0 and removal.get("gap_reentry_closing_speed_tolerance_m_s", 0.0) > 0.0 and "sample endpoints alone are insufficient" in removal.get("clearance_continuity", "") and "tau_c=inf" in removal.get("earliest_eligible_event_rule", "") and "t_r=tau_c+clearance_dwell_s" in removal.get("earliest_eligible_event_rule", "") and "unique earliest finite t_r" in removal.get("event_selection", "") and removal.get("empty_eligibility_set") == "DIAGNOSTIC_FAIL_CLOSED_NO_REMOVAL_EVENT" and "independently located earliest t_r" in removal.get("cross_integrator_removal_event_definition", "") and "separate preregistered re-contact" in removal.get("future_contact_reactivation", "")
    add("B4C-21", "B4 main branch keeps contact kernel off and fails closed on raw-gap reentry", recontact_ok, {})

    machine = model.get("state_machine", {})
    machine_ok = machine.get("nominal_sequence") == ["B3_SOFT_CAPTURE_TRANSIENT_CANDIDATE", "SYNTHETIC_CONSTRAINT_ACQUISITION_REQUEST", "SYNTHETIC_CONSTRAINT_ACTIVE_DIAGNOSTIC", "SYNTHETIC_CONSTRAINT_REMOVAL_ELIGIBLE", "SYNTHETIC_CONSTRAINT_REMOVED_FREE_FLIGHT_DIAGNOSTIC"] and machine.get("success_label") == "none" and machine.get("failure_terminal") == "DIAGNOSTIC_FAIL_CLOSED" and "terminal label alone has zero Gate value" in machine.get("qualification_rule", "") and set(machine.get("forbidden_states", [])) == {"LOCKED", "HELD_CAPTURE", "GRASP_SUCCESS", "TARGET_ATTACHED", "RELEASED_ATTACHED_TARGET", "CURRENT_SYSTEM_CONTACT_PASS", "NC19_PASS"}
    add("B4C-22", "state machine has no success alias and labels cannot replace trajectory proof", machine_ok, machine)

    fail_text = "\n".join(model.get("fail_closed_conditions", []))
    fail_tokens = ("rank(L_hat) not 14", "rank(J_hat) not 6", "J_hat*L_hat residual above tolerance", "scaled effective mass W_bar", "reduced and KKT projections disagree", "contact elastic potential omitted", "simultaneously active", "nonzero release impulse", "contact-kernel reactivation", "forbidden state authorization")
    fail_inventory_ok = all(token in fail_text for token in fail_tokens)
    add("B4C-23", "fail-closed inventory covers rank impulse energy switch removal and authority faults", fail_inventory_ok, {"required_tokens": fail_tokens})

    physical_rows = [row for row in units.get("quantities", []) if str(row.get("id", "")).startswith("physical_")]
    physical_ids = {row.get("id") for row in physical_rows}
    physical_units_ok = physical_ids == {"physical_lock_transform", "physical_constraint_stiffness", "physical_constraint_damping", "physical_retention_capacity", "physical_release_energy"} and all(row.get("estimate") is None and row.get("standard_uncertainty") is None and row.get("distribution") is None and row.get("degrees_of_freedom") is None and row.get("source") is None and str(row.get("status", "")).startswith("HOLD_") for row in physical_rows) and units.get("physical_measurement_model_available") is False and units.get("gum_or_monte_carlo_uncertainty_propagation_authorized") is False
    add("B4C-24", "all physical B4 quantities remain null HOLD with uncertainty fields unfilled", physical_units_ok, physical_rows)
    unit_channels = units.get("required_native_unit_channels", {})
    timing_rows = {row.get("id"): row for row in units.get("quantities", [])}
    anchors = numerical.get("frozen_reference_anchors", {})
    event_tolerances = numerical.get("event_local_native_unit_tolerances", {})
    active_tolerances = numerical.get("active_trajectory_native_unit_tolerances", {})
    removal_tolerances = numerical.get("removal_and_event_tolerances", {})
    numeric_complete = anchors == {
        "b3_reference_record_index": 205,
        "b3_reference_time_s": 0.051250000000000004,
        "reference_length_m": 0.03999999992105392,
        "left_contact_elastic_energy_j": 3.3837573393085704e-7,
        "right_contact_elastic_energy_j": 4.6759575924213813e-7,
        "total_contact_elastic_energy_j": 8.059714931729952e-7,
        "classification": "HASH_BOUND_B3_SYNTHETIC_REFERENCE_ANCHORS__FUTURE_INTEGRATORS_RECOMPUTE_THEIR_OWN_EVENT_VALUES",
    } and event_tolerances == EXPECTED_EVENT_TOLERANCES and active_tolerances == EXPECTED_ACTIVE_TOLERANCES and removal_tolerances == EXPECTED_REMOVAL_TOLERANCES and numerical.get("contract_freeze_mutation_ids") == EXPECTED_CONTRACT_FREEZE_MUTATION_IDS and numerical.get("future_solver_required_negative_control_ids") == EXPECTED_FUTURE_SOLVER_NEGATIVE_CONTROL_IDS
    units_ok = units.get("units_policy") == "SI_AT_ALL_MODEL_AND_EVIDENCE_BOUNDARIES" and "never combine linear and angular quantities" in units.get("mixed_dimension_policy", "") and unit_channels.get("linear_impulse") == "N*s" and unit_channels.get("angular_impulse") == "N*m*s" and all(timing_rows[key].get("distribution") == "exact algorithmic registration" and "NOT_" in timing_rows[key].get("status", "") for key in ("minimum_active_diagnostic_dwell", "clearance_dwell", "post_release_observation_horizon")) and numerical.get("future_solver_gate_rule") == "all tolerances apply per native-unit channel and over the full trajectory where stated; no terminal label, summary maximum, or aggregate mixed-unit norm can replace the underlying samplewise evidence" and numeric_complete
    add("B4C-25", "SI native channels and synthetic timing classifications are explicit", units_ok, unit_channels)

    required_false = governance.get("required_false", {})
    governance_false_ok = set(required_false) == EXPECTED_REQUIRED_FALSE_KEYS and not any(required_false.values()) and governance.get("authorized_scope") == EXPECTED_AUTHORIZED_SCOPE and governance.get("forbidden_artifacts") == ["*.urdf", "MECH_RL_SYSTEM_INTERFACE_V2.yaml", "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json", "T_gripper_target_locked", "execution.lock", "release.marker"] and set(governance.get("forbidden_actions", [])) == {"CALL_UNIFIED_PRIVATE_BUILDER", "CALL_UNIFIED_GENERATOR", "CREATE_FORMAL_INTERFACE_INSTANCE", "CLAIM_ACTUAL_B601_BINDING", "CLAIM_PHYSICAL_LOCK_OR_HELD_CAPTURE", "CLAIM_GRASP_SUCCESS", "CLAIM_RELEASED_ATTACHED_TARGET", "CREDIT_THIS_PACKAGE_TO_FORMAL_NC19", "AUTHORIZE_PRODUCTION_RELEASE_OR_NEXT_STAGE"}
    add("B4C-26", "solver physical current formal production release next stage remain false", governance_false_ok, required_false)
    formal_contract_ok = governance.get("formal_sim13_v2_state_unchanged") == {"passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"]}
    add("B4C-27", "governance freezes formal Sim13 V2 state", formal_contract_ok, governance.get("formal_sim13_v2_state_unchanged"))

    forbidden_tree = list(HERE.rglob("*.urdf")) + list(HERE.rglob("MECH_RL_SYSTEM_INTERFACE_V2.yaml")) + list(HERE.rglob("UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json")) + list(HERE.rglob("T_gripper_target_locked")) + list(HERE.rglob("execution.lock")) + list(HERE.rglob("release.marker"))
    add("B4C-28", "B4 tree contains no URDF formal interface or execution authorization", not forbidden_tree, [path.relative_to(HERE).as_posix() for path in forbidden_tree])

    metrics = projection_identity_metrics()
    math_ok = metrics["L_hat_rank"] == 14 and metrics["J_hat_rank"] == 6 and metrics["Jhat_Lhat_operator_inf_dimensionless"] < numerical["event_local_native_unit_tolerances"]["Jhat_Lhat_operator_inf_dimensionless"] and metrics["attached_mass_min_eigenvalue"] > 0.0 and metrics["scaled_effective_mass_min_eigenvalue"] > 0.0 and metrics["reduced_kkt_inf_difference"] < 1e-12 and metrics["post_constraint_inf_residual"] < 1e-12 and metrics["energy_loss_formula_j"] >= 0.0 and metrics["energy_loss_identity_error_j"] < 1e-12
    add("B4C-29", "abstract deterministic algebra fixture proves the preregistered projection identity without executing B4 dynamics", math_ok, {"scope": "ABSTRACT_CONTRACT_MATH_FIXTURE__NOT_B3_EVENT_OR_B4_SOLVER", "metrics": metrics})

    solver_markers = [path for path in HERE.rglob("*.py") if path.name not in {"validate_phase_b4_contract.py", "independent_audit_phase_b4_contract.py"} and "tests" not in path.parts and ("solver" in path.name.lower() or "dynamics" in path.name.lower())]
    allowed_source_files = {path.resolve() for path in _local_source_paths()}
    unexpected_tree_files = [path for path in HERE.rglob("*") if path.is_file() and path.resolve() not in allowed_source_files]
    add("B4C-30", "no B4 solver or unmanifested shadow source exists", not solver_markers and not unexpected_tree_files, {"solver": [path.relative_to(HERE).as_posix() for path in solver_markers], "unexpected": [path.relative_to(HERE).as_posix() for path in unexpected_tree_files]})

    status_ok = governance.get("current_status") == "CONTRACT_FROZEN_FOR_VALIDATION__FINAL_CREDIT_REQUIRES_INDEPENDENT_AUDIT__NO_IMPLEMENTATION"
    add("B4C-31", "contract status is exactly frozen-for-validation before independent audit", status_ok, governance.get("current_status"))
    gate_rule_ok = governance.get("required_contract_gate_status") == EXPECTED_CONTRACT_GATE_STATUS and "implementation_not_started" in governance.get("contract_gate_rule", "")
    add("B4C-32", "only exact contract-freeze status may be issued", gate_rule_ok, governance.get("required_contract_gate_status"))
    return checks


def _parse_pytest_outcomes(output: str) -> dict[str, int]:
    patterns = {
        "passed": r"(\d+)\s+passed\b",
        "failed": r"(\d+)\s+failed\b",
        "skipped": r"(\d+)\s+skipped\b",
        "xfailed": r"(\d+)\s+xfailed\b",
        "xpassed": r"(\d+)\s+xpassed\b",
        "deselected": r"(\d+)\s+deselected\b",
        "errors": r"(\d+)\s+errors?\b",
    }
    return {
        name: sum(int(match) for match in re.findall(pattern, output))
        for name, pattern in patterns.items()
    }


def _run_pytest() -> dict[str, Any]:
    env = os.environ.copy()
    env.pop("PYTEST_ADDOPTS", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    collect = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=HERE,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    match = re.search(r"(\d+) tests collected", collect.stdout)
    collected = int(match.group(1)) if match else -1
    run = subprocess.run(
        [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=HERE,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    outcomes = _parse_pytest_outcomes(f"{run.stdout}\n{run.stderr}")
    return {
        "collect_returncode": collect.returncode,
        "collected": collected,
        "collect_stdout": collect.stdout.strip(),
        "collect_stderr": collect.stderr.strip(),
        "run_returncode": run.returncode,
        "run_stdout": run.stdout.strip(),
        "run_stderr": run.stderr.strip(),
        "outcomes": outcomes,
    }


def _local_source_paths() -> list[Path]:
    relative = [
        "README.md",
        "pytest.ini",
        "validate_phase_b4_contract.py",
        "independent_audit_phase_b4_contract.py",
        "contracts/PHASE_B4_SOURCE_BINDINGS_V1.json",
        "contracts/PHASE_B4_MODEL_CONTRACT_V1.json",
        "contracts/PHASE_B4_GOVERNANCE_CONTRACT_V1.json",
        "contracts/PHASE_B4_UNCERTAINTY_AND_UNITS_LEDGER_V1.json",
        "contracts/PHASE_B4_NUMERICAL_ACCEPTANCE_CONTRACT_V1.json",
        "tests/conftest.py",
        "tests/test_source_bindings.py",
        "tests/test_model_contract.py",
        "tests/test_governance_units.py",
        "tests/test_projection_identity.py",
        "tests/test_numerical_acceptance.py",
        "tests/test_negative_controls.py",
    ]
    return [HERE / path for path in relative]


def _candidate_source_records(source_bindings: dict[str, Any]) -> list[dict[str, Any]]:
    upstream = [
        _record(ROOT / row["path"], f"BOUND_{row['id'].upper()}")
        for row in source_bindings["sources"]
    ]
    local = [
        _record(path, f"B4_LOCAL_SOURCE_{path.name.upper()}")
        for path in _local_source_paths()
    ]
    return upstream + local


def _clean_downstream_outputs() -> None:
    for path in (SOURCE_MANIFEST_PATH, VALIDATION_PATH, EVIDENCE_MANIFEST_PATH, PRE_AUDIT_GATE_PATH, AUDIT_RECEIPT_PATH, FINAL_GATE_PATH, TERMINAL_MANIFEST_PATH):
        if path.exists():
            path.unlink()


def run_validation() -> dict[str, Any]:
    _clean_downstream_outputs()
    model = _load(MODEL_CONTRACT_PATH)
    governance = _load(GOVERNANCE_CONTRACT_PATH)
    units = _load(UNITS_LEDGER_PATH)
    numerical = _load(NUMERICAL_CONTRACT_PATH)
    source_bindings = _load(SOURCE_BINDINGS_PATH)
    source_records_before_tests = _candidate_source_records(source_bindings)
    pytest_result = _run_pytest()
    checks = evaluate_contract_payloads(model, governance, units, numerical, source_bindings, verify_files=True)
    checks["B4C-33"] = {
        "name": "fixed pytest inventory exact",
        "pass": pytest_result["collect_returncode"] == 0 and pytest_result["collected"] == EXPECTED_TEST_COUNT,
        "evidence": {"expected": EXPECTED_TEST_COUNT, "collected": pytest_result["collected"]},
    }
    checks["B4C-34"] = {
        "name": "all 62 fixed tests pass with no skip xfail xpass deselection or error",
        "pass": pytest_result["run_returncode"] == 0 and pytest_result["outcomes"] == {"passed": EXPECTED_TEST_COUNT, "failed": 0, "skipped": 0, "xfailed": 0, "xpassed": 0, "deselected": 0, "errors": 0},
        "evidence": {"returncode": pytest_result["run_returncode"], "outcomes": pytest_result["outcomes"], "stdout": pytest_result["run_stdout"], "stderr": pytest_result["run_stderr"]},
    }

    all_records = _candidate_source_records(source_bindings)
    source_snapshot_stable = source_records_before_tests == all_records
    paths_unique = len({row["path"] for row in all_records}) == len(all_records)
    roles_unique = len({row["role"] for row in all_records}) == len(all_records)
    expected_upstream_path_roles = {
        path: f"BOUND_{source_id.upper()}"
        for source_id, (path, _role) in EXPECTED_SOURCE_BINDINGS.items()
    }
    expected_local_path_roles = {
        path.relative_to(ROOT).as_posix(): f"B4_LOCAL_SOURCE_{path.name.upper()}"
        for path in _local_source_paths()
    }
    actual_path_roles = {row["path"]: row["role"] for row in all_records}
    exact_manifest_mapping = actual_path_roles == (expected_upstream_path_roles | expected_local_path_roles)
    checks["B4C-35"] = {
        "name": "source manifest candidate is the exact stable 13-upstream plus 16-local snapshot",
        "pass": len(all_records) == 29 and paths_unique and roles_unique and exact_manifest_mapping and source_snapshot_stable,
        "evidence": {"records": len(all_records), "paths_unique": paths_unique, "roles_unique": roles_unique, "exact_mapping": exact_manifest_mapping, "pre_post_test_snapshot_stable": source_snapshot_stable},
    }

    source_manifest = {
        "schema": "SIM13_V4B4_CONTRACT_SOURCE_MANIFEST_V1",
        "scope": "B4_CONTRACT_FREEZE_ONLY",
        "self_excluded": True,
        "records": all_records,
    }
    _write_json(SOURCE_MANIFEST_PATH, source_manifest)
    manifest_records_fresh = all(_record(ROOT / row["path"], row["role"]) == row for row in all_records)
    checks["B4C-35"]["pass"] = checks["B4C-35"]["pass"] and manifest_records_fresh
    checks["B4C-35"]["evidence"]["post_write_records_fresh"] = manifest_records_fresh

    passed = sum(1 for row in checks.values() if row["pass"])
    total = len(checks)
    failed = [check_id for check_id, row in checks.items() if not row["pass"]]
    status = "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT" if not failed else "FAIL_CONTRACT_VALIDATION"

    validation = {
        "schema": "SIM13_V4B4_CONTRACT_VALIDATION_V1",
        "status": status,
        "score": {"pass": passed, "fail": len(failed), "total": total, "failed": failed},
        "expected_test_count": EXPECTED_TEST_COUNT,
        "pytest": pytest_result,
        "checks": checks,
        "implementation_state": {
            "b4_dynamics_solver_implemented": False,
            "physical_lock_implemented": False,
            "held_capture_passed": False,
            "current_system_bound": False,
            "formal_nc19_credit": False,
            "release_authorized": False,
            "next_stage_authorized": False,
        },
    }
    _write_json(VALIDATION_PATH, validation)

    evidence_manifest = {
        "schema": "SIM13_V4B4_CONTRACT_EVIDENCE_MANIFEST_V1",
        "self_excluded": True,
        "records": [
            _record(SOURCE_MANIFEST_PATH, "B4_CONTRACT_SOURCE_MANIFEST"),
            _record(VALIDATION_PATH, "B4_CONTRACT_VALIDATION"),
        ],
    }
    _write_json(EVIDENCE_MANIFEST_PATH, evidence_manifest)

    pre_audit_gate = {
        "schema": "SIM13_V4B4_CONTRACT_PRE_AUDIT_GATE_V1",
        "overall_status": status,
        "final_gate": False,
        "score": validation["score"],
        "hash_chain": {
            "source_manifest": _record(SOURCE_MANIFEST_PATH, "UPSTREAM_SOURCE_MANIFEST"),
            "validation": _record(VALIDATION_PATH, "UPSTREAM_VALIDATION"),
            "evidence_manifest": _record(EVIDENCE_MANIFEST_PATH, "UPSTREAM_EVIDENCE_MANIFEST"),
        },
        "scope_ruling": {
            "contract_preregistered": not failed,
            "implementation_started": False,
            "synthetic_constraint_executed": False,
            "physical_lock_or_held_capture": False,
            "current_system_or_formal_nc19_credit": False,
            "release_or_next_stage_authorized": False,
        },
        "final_gate_issuer": "independent_audit_phase_b4_contract.py",
    }
    _write_json(PRE_AUDIT_GATE_PATH, pre_audit_gate)
    return pre_audit_gate


if __name__ == "__main__":
    result = run_validation()
    print(json.dumps({"status": result["overall_status"], "score": result["score"], "pre_audit_gate_sha256": _record(PRE_AUDIT_GATE_PATH, "PRE_AUDIT_GATE")["sha256"]}, indent=2))
    raise SystemExit(0 if result["overall_status"] == "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT" else 1)
