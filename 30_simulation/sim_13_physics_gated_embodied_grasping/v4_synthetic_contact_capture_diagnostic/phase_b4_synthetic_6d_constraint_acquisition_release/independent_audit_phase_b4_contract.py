from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np


# This audit deliberately does not import the validator, its tests, or any B4 solver.
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

EXPECTED_STATUS = (
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
    "b4_solver_implemented", "physical_dual_contact_identified", "physical_friction_identified",
    "physical_actuator_timing_identified", "physical_lock_implemented", "physical_release_implemented",
    "held_capture_passed", "grasp_success_claimed", "target_attached_claimed", "current_system_bound",
    "formal_nc19_credit", "owner_authorized", "production_ready", "release_authorized",
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
    "pose_translation_m": 1e-9, "pose_rotation_geodesic_rad": 1e-9,
    "relative_linear_twist_m_s": 1e-9, "relative_angular_twist_rad_s": 1e-9,
    "total_linear_momentum_drift_N_s": 1e-9,
    "total_angular_momentum_drift_about_fixed_inertial_origin_N_m_s": 1e-9,
    "mechanical_energy_plus_all_dissipation_drift_J": 1e-7, "ideal_constraint_power_W": 1e-10,
    "contact_force_while_constraint_active_N": 1e-12,
    "contact_torque_while_constraint_active_N_m": 1e-12,
}
EXPECTED_CONTRACT_CANONICAL_SHA256 = {
    "model": "CE39890A558901DFE97922534CC15FEF42B9DA527C089D308CA7BBC2CFD2F0AF",
    "governance": "2533588DC8C4FB807BC0DE3CBC8069748593D0AF08E077D5D1CD2D5503ECDFE1",
    "units": "63E7F07FB9B84CAC469176A4F3BFFAA2F48DF6446C620D629BFDDDBE51E660A4",
    "numerical": "80D8AC949B4F28074E04DF092890038DA339734499AE12111E6DF48ED7915BDB",
    "source_bindings": "F731260C0D318BC3A0CB3D3206E0F488D19254286498A9D0CD3A0757D3E18BAC",
}
EXPECTED_LOCAL_SOURCE_RELATIVE_PATHS = [
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
EXPECTED_VALIDATOR_CHECK_IDS = {f"B4C-{index:02d}" for index in range(1, 36)} | {"B4C-06A", "B4C-06B"}
EXPECTED_AUDIT_PREDECESSOR_IDS = {f"B4IA-{index:02d}" for index in range(1, 22)}
EXPECTED_AUDIT_CHECK_IDS = {f"B4IA-{index:02d}" for index in range(1, 23)}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _canonical_payload_sha(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return _sha(data)


def _record(path: Path, role: str) -> dict[str, Any]:
    data = path.read_bytes()
    return {"role": role, "path": path.relative_to(ROOT).as_posix(), "bytes": len(data), "sha256": _sha(data)}


def _write(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _inside_root(path: Path) -> bool:
    return path.resolve().is_relative_to(ROOT.resolve())


def _verify_record(record: dict[str, Any]) -> bool:
    try:
        path = (ROOT / record["path"]).resolve()
        if not _inside_root(path):
            return False
        data = path.read_bytes()
        return len(data) == record["bytes"] and _sha(data) == record["sha256"]
    except Exception:
        return False


def _record_matches(record: dict[str, Any], path: Path, role: str) -> bool:
    return (
        record.get("path") == path.relative_to(ROOT).as_posix()
        and record.get("role") == role
        and _verify_record(record)
    )


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


def _binding(source_bindings: dict[str, Any], source_id: str) -> dict[str, Any]:
    return next(row for row in source_bindings["sources"] if row["id"] == source_id)


def _bound_path(source_bindings: dict[str, Any], source_id: str) -> Path:
    return ROOT / _binding(source_bindings, source_id)["path"]


def _bindings_exact(source_bindings: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    rows = source_bindings.get("sources", [])
    reports: list[dict[str, Any]] = []
    for row in rows:
        try:
            path = (ROOT / row["path"]).resolve()
            data = path.read_bytes() if _inside_root(path) else b""
            passed = _inside_root(path) and len(data) == row["bytes"] and _sha(data) == row["sha256"]
            reports.append({"id": row.get("id"), "pass": passed, "bytes": len(data), "sha256": _sha(data) if data else None})
        except Exception as exc:
            reports.append({"id": row.get("id"), "pass": False, "error": type(exc).__name__})
    actual_mapping = {
        row.get("id"): (row.get("path"), row.get("role"))
        for row in rows
        if isinstance(row, dict)
    }
    exact_set = len(rows) == len(EXPECTED_SOURCE_BINDINGS) and actual_mapping == EXPECTED_SOURCE_BINDINGS and source_bindings.get("scope") == "READ_ONLY_HASH_PINNED_PREREGISTRATION_INPUTS" and source_bindings.get("source_mutation_authorized") is False and source_bindings.get("formal_state_inheritance_authorized") is False and _canonical_payload_sha(source_bindings) == EXPECTED_CONTRACT_CANONICAL_SHA256["source_bindings"]
    unique = len({row.get("path") for row in rows}) == 13 and len({row.get("role") for row in rows}) == 13
    return exact_set and unique and all(row["pass"] for row in reports), reports


def _skew(vector: np.ndarray) -> np.ndarray:
    x, y, z = vector
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]], dtype=float)


def _independent_trigger_rank_anchors(
    source_bindings: dict[str, Any], numerical: dict[str, Any]
) -> tuple[bool, dict[str, Any]]:
    trace = _load(_bound_path(source_bindings, "b3_reference_trace"))
    records = trace.get("reference_records", [])
    qualifying = [
        index
        for index, row in enumerate(records)
        if row.get("soft_capture_criteria", {}).get("soft_capture_transient_qualifies") is True
        and row.get("soft_capture_criteria", {}).get("all_ledgers_closed") is True
    ]
    if not qualifying:
        return False, {"error": "NO_QUALIFYING_SAMPLE"}
    index = qualifying[0]
    row = records[index]
    prior_abort = any(
        "ABORT" in item.get("state_label", "") or "FAIL_CLOSED" in item.get("state_label", "")
        for item in records[: index + 1]
    )
    target = np.asarray(row["target"]["position_inertial_m"], dtype=float)
    p_left = np.asarray(row["contacts"]["left"]["common_contact_point_inertial_m"], dtype=float)
    p_right = np.asarray(row["contacts"]["right"]["common_contact_point_inertial_m"], dtype=float)
    r_left = p_left - target
    r_right = p_right - target
    length_reference = 0.5 * np.linalg.norm(p_right - p_left)
    grasp = np.block([[np.eye(3), np.eye(3)], [_skew(r_left), _skew(r_right)]])
    grasp_scaled = np.diag([1.0, 1.0, 1.0, 1.0 / length_reference, 1.0 / length_reference, 1.0 / length_reference]) @ grasp
    singular = np.linalg.svd(grasp_scaled, compute_uv=False)
    rank_tolerance = numerical["rank_and_linear_solve"]["svd_relative_rank_tolerance"] * singular[0]
    rank = int(np.sum(singular > rank_tolerance))
    u_left = float(row["contacts"]["left"]["elastic_energy_j"])
    u_right = float(row["contacts"]["right"]["elastic_energy_j"])
    anchors = numerical["frozen_reference_anchors"]

    force_left = np.array([0.017, -0.011, 0.009])
    force_right = np.array([-0.013, 0.019, -0.007])
    resultant_force = force_left + force_right
    resultant_couple = np.cross(r_left, force_left) + np.cross(r_right, force_right)
    chord = (p_right - p_left) / np.linalg.norm(p_right - p_left)
    chi_contact = float(chord @ (resultant_couple - np.cross(r_left, resultant_force)))
    axial_only_couple = chord * 0.003
    chi_axial = float(chord @ (axial_only_couple - np.cross(r_left, np.zeros(3))))
    metrics = {
        "record_count": len(records),
        "qualifying_count": len(qualifying),
        "first_qualifying_index": index,
        "first_qualifying_time_s": row["time_s"],
        "prior_abort": prior_abort,
        "reference_length_m": float(length_reference),
        "left_contact_elastic_energy_j": u_left,
        "right_contact_elastic_energy_j": u_right,
        "total_contact_elastic_energy_j": u_left + u_right,
        "grasp_scaled_singular_values": singular.tolist(),
        "grasp_scaled_rank": rank,
        "rank_tolerance_absolute": float(rank_tolerance),
        "two_point_contact_chi_missing_N_m_s": chi_contact,
        "synthetic_axial_only_chi_missing_N_m_s": chi_axial,
    }
    passed = (
        len(records) == 321
        and len(qualifying) == 7
        and index == anchors["b3_reference_record_index"] == 205
        and row["time_s"] == anchors["b3_reference_time_s"]
        and not prior_abort
        and float(length_reference) == anchors["reference_length_m"]
        and u_left == anchors["left_contact_elastic_energy_j"]
        and u_right == anchors["right_contact_elastic_energy_j"]
        and u_left + u_right == anchors["total_contact_elastic_energy_j"]
        and rank == 5
        and abs(chi_contact) < 1e-15
        and abs(chi_axial - 0.003) < 1e-15
    )
    return passed, metrics


def _independent_projection_proof(numerical: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    row = np.arange(6, dtype=float)[:, None]
    col = np.arange(14, dtype=float)[None, :]
    a_map = 0.03 * np.cos(0.19 * (row + 2.0) * (col + 1.0))
    a_map[:, :6] += np.array(
        [
            [1.0, 0.0, 0.0, 0.0, 0.08, -0.05],
            [0.0, 1.0, 0.0, -0.08, 0.0, 0.06],
            [0.0, 0.0, 1.0, 0.05, -0.06, 0.0],
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        ]
    )
    embedding = np.vstack((np.eye(14), a_map))
    constraint = np.hstack((-a_map, np.eye(6)))
    seed = np.arange(400, dtype=float).reshape(20, 20)
    base = np.cos(0.013 * (seed + 3.0))
    mass = base.T @ base + np.diag(np.linspace(0.8, 4.1, 20))
    z_minus = 0.008 * np.sin(np.arange(20, dtype=float) * 0.37 + 0.4)
    reference_length = 0.23
    scale = np.diag([1.0, 1.0, 1.0, reference_length, reference_length, reference_length])
    j_bar = scale @ constraint
    s_eta_diag = np.array([1.0] * 3 + [reference_length] * 3 + [reference_length] * 6 + [1.0] * 2)
    s_z_diag = np.concatenate((s_eta_diag, np.ones(3), np.full(3, reference_length)))
    l_hat = np.diag(s_z_diag) @ embedding @ np.diag(1.0 / s_eta_diag)
    j_hat = j_bar @ np.diag(1.0 / s_z_diag)

    reduced_mass = embedding.T @ mass @ embedding
    eta = np.linalg.solve(reduced_mass, embedding.T @ mass @ z_minus)
    z_reduced = embedding @ eta
    block = np.block([[mass, -j_bar.T], [j_bar, np.zeros((6, 6))]])
    solution = np.linalg.solve(block, np.concatenate((mass @ z_minus, np.zeros(6))))
    z_kkt = solution[:20]
    effective = j_bar @ np.linalg.solve(mass, j_bar.T)
    gamma = j_bar @ z_minus
    loss_formula = 0.5 * gamma @ np.linalg.solve(effective, gamma)
    loss_direct = 0.5 * z_minus @ mass @ z_minus - 0.5 * z_kkt @ mass @ z_kkt
    singular = np.linalg.svd(effective, compute_uv=False)
    condition = float(singular[0] / singular[-1])
    metrics = {
        "rank_L_hat": int(np.linalg.matrix_rank(l_hat)),
        "rank_J_hat": int(np.linalg.matrix_rank(j_hat)),
        "Jhat_Lhat_operator_inf_dimensionless": float(np.linalg.norm(j_hat @ l_hat, ord=np.inf)),
        "reduced_kkt_inf_difference": float(np.linalg.norm(z_reduced - z_kkt, ord=np.inf)),
        "native_constraint_inf": float(np.linalg.norm(constraint @ z_kkt, ord=np.inf)),
        "scaled_constraint_inf": float(np.linalg.norm(j_bar @ z_kkt, ord=np.inf)),
        "scaled_effective_min_eigenvalue": float(np.min(np.linalg.eigvalsh(0.5 * (effective + effective.T)))),
        "scaled_effective_condition_number": condition,
        "energy_loss_formula_j": float(loss_formula),
        "energy_loss_direct_j": float(loss_direct),
        "energy_identity_error_j": float(abs(loss_formula - loss_direct)),
    }
    rank_contract = numerical["rank_and_linear_solve"]
    passed = (
        metrics["rank_L_hat"] == 14
        and metrics["rank_J_hat"] == 6
        and metrics["Jhat_Lhat_operator_inf_dimensionless"] < numerical["event_local_native_unit_tolerances"]["Jhat_Lhat_operator_inf_dimensionless"]
        and metrics["reduced_kkt_inf_difference"] < 1e-12
        and metrics["native_constraint_inf"] < 1e-12
        and metrics["scaled_constraint_inf"] < 1e-12
        and metrics["scaled_effective_min_eigenvalue"] > 0.0
        and condition < rank_contract["scaled_effective_mass_condition_number_max"]
        and loss_formula >= 0.0
        and metrics["energy_identity_error_j"] < numerical["event_local_native_unit_tolerances"]["projection_energy_identity_J"]
    )
    return passed, metrics


def _semantic_checks(
    model: dict[str, Any], governance: dict[str, Any], units: dict[str, Any], numerical: dict[str, Any]
) -> dict[str, bool]:
    projection = model.get("acquisition_impulse_projection", {})
    wrench = model.get("wrench_and_momentum_semantics", {})
    switch = model.get("contact_to_constraint_switch", {})
    active = model.get("active_constraint_propagation", {})
    removal = model.get("release_contract", {})
    physical = [row for row in units.get("quantities", []) if str(row.get("id", "")).startswith("physical_")]
    rank = numerical.get("rank_and_linear_solve", {})
    solver_allowed = rank.get("acquisition_solve_allowed", {})
    trigger = model.get("trigger_contract", {})
    upstream = model.get("upstream_ruling", {})
    required_false = governance.get("required_false", {})
    contract_hashes = {
        "model": _canonical_payload_sha(model),
        "governance": _canonical_payload_sha(governance),
        "units": _canonical_payload_sha(units),
        "numerical": _canonical_payload_sha(numerical),
    }
    return {
        "contract_payloads_canonical": contract_hashes == {key: EXPECTED_CONTRACT_CANONICAL_SHA256[key] for key in contract_hashes},
        "trigger_exact": trigger.get("reference_record_index") == 205 and trigger.get("reference_time_s") == 0.051250000000000004 and trigger.get("required_upstream_candidate_count_at_or_before_trigger") == 1 and trigger.get("interpolation_rule_for_future_solver") == "locate the earliest predicate transition independently for each integrator; never force the frozen reference timestamp into another integrator" and trigger.get("cherry_pick_forbidden") is True,
        "upstream_rank5_only": upstream.get("b3_grasp_map_rank") == 5 and upstream.get("full_6d_wrench_span") is False and upstream.get("full_6d_force_closure") is False,
        "dimensions_and_snapshot": model.get("scope") == "CONTRACT_PREREGISTRATION_ONLY__SYNTHETIC_DIAGNOSTIC" and model.get("pre_event_state", {}).get("dimension") == 20 and model.get("pre_event_state", {}).get("external_impulse") == "zero" and model.get("attached_subspace", {}).get("embedding_shape") == [20, 14] and model.get("attached_subspace", {}).get("constraint_shape") == [6, 20] and "d_star=" in model.get("synthetic_snapshot_transform", {}).get("translation_snapshot", "") and "R_star=" in model.get("synthetic_snapshot_transform", {}).get("rotation_snapshot", ""),
        "direct_solvers_no_acquisition_pinv": "directly solve block system" in projection.get("independent_kkt_solution", "") and "without forming a Schur complement" in projection.get("independent_kkt_solution", "") and {"explicit_matrix_inverse", "pinv", "lstsq"}.issubset(set(rank.get("acquisition_solve_forbidden", []))) and rank.get("pinv_whitelist") == ["rank5_grasp_wrench_unreachable_projection_audit_only_after_rank_Gbar_equals_5"] and "cholesky_solve" not in solver_allowed.get("direct_symmetric_indefinite_kkt", []) and "pivoted_symmetric_ldlt_solve" in solver_allowed.get("direct_symmetric_indefinite_kkt", []),
        "scaled_units_and_condition": "D=diag(I_3,L_ref*I_3)" in projection.get("scaling", "") and rank.get("condition_number_whitelist") == ["W_bar_scaled"] and "lambda_max(W_bar)/lambda_min(W_bar)" in rank.get("scaled_effective_mass_condition_number_definition", "") and projection.get("unscaled_mixed_unit_condition_number_forbidden") is True and numerical.get("constraint_basis_scaling", {}).get("identity") == "J_hat*L_hat=0" and "audit-only coordinate scalings" in numerical.get("constraint_basis_scaling", {}).get("use_boundary", ""),
        "correct_missing_wrench": "ell-r_left cross p" in wrench.get("synthetic_missing_sixth_wrench_scalar", "") and "chi_missing=0" in wrench.get("rank5_identity", "") and "not generally the rank5-unreachable scalar" in wrench.get("ordinary_angular_impulse_projection", ""),
        "equivalent_service_wrench_once": "ell+r_cross_p" in wrench.get("service_equivalent_wrench_about_palm_origin", "") and "shall not be added a second time" in wrench.get("service_equivalent_wrench_about_palm_origin", ""),
        "switch_energy_complete": switch.get("b3_contact_force_after_acquisition") == "disabled while synthetic constraint is active" and switch.get("double_counting_contact_and_constraint") == "forbidden" and switch.get("reference_left_contact_potential_at_t_a_minus_j") == 3.3837573393085704e-7 and switch.get("reference_right_contact_potential_at_t_a_minus_j") == 4.6759575924213813e-7 and switch.get("reference_total_contact_potential_at_t_a_minus_j") == 8.059714931729952e-7 and switch.get("contact_potential_sum") == "U_contact_minus=U_left_minus+U_right_minus with each side counted exactly once" and switch.get("projection_dissipation") == "D_projection=T_minus-T_plus" and switch.get("switch_dissipation") == "D_switch=D_projection+U_left_minus+U_right_minus" and switch.get("full_event_energy_identity") == "T_plus+D_B3_minus+D_switch=T_minus+U_left_minus+U_right_minus+D_B3_minus" and switch.get("energy_deletion") == "forbidden" and switch.get("actuator_work") == "zero; no actuator model exists",
        "active_bias_complete": "M_combined*L_dot*eta" in active.get("bias", "") and "independently agrees" in active.get("bias", "") and active.get("external_force_and_torque") == "zero" and active.get("required_ledgers") == ["total_linear_momentum_N_s", "total_angular_momentum_about_fixed_inertial_origin_N_m_s", "mechanical_energy_plus_all_dissipation_J", "pose_residual_translation_m", "pose_residual_rotation_rad", "relative_twist_linear_m_s", "relative_twist_angular_rad_s"] and len(wrench.get("required_reports", [])) == 10,
        "removal_and_clearance": "L(q_r)*eta_minus" in removal.get("release_mapping", "") and removal.get("release_impulse_linear_N_s") == 0.0 and removal.get("release_impulse_angular_N_m_s") == 0.0 and removal.get("clearance_gap_min_m", 0.0) > 0.0 and "sample endpoints alone are insufficient" in removal.get("clearance_continuity", "") and "tau_c=inf" in removal.get("earliest_eligible_event_rule", "") and "unique earliest finite t_r" in removal.get("event_selection", "") and removal.get("empty_eligibility_set") == "DIAGNOSTIC_FAIL_CLOSED_NO_REMOVAL_EVENT" and "remain disabled" in removal.get("contact_kernel_after_removal", ""),
        "trajectory_not_label": model.get("state_machine", {}).get("nominal_sequence") == ["B3_SOFT_CAPTURE_TRANSIENT_CANDIDATE", "SYNTHETIC_CONSTRAINT_ACQUISITION_REQUEST", "SYNTHETIC_CONSTRAINT_ACTIVE_DIAGNOSTIC", "SYNTHETIC_CONSTRAINT_REMOVAL_ELIGIBLE", "SYNTHETIC_CONSTRAINT_REMOVED_FREE_FLIGHT_DIAGNOSTIC"] and model.get("state_machine", {}).get("success_label") == "none" and model.get("state_machine", {}).get("failure_terminal") == "DIAGNOSTIC_FAIL_CLOSED" and "terminal label alone has zero Gate value" in model.get("state_machine", {}).get("qualification_rule", ""),
        "physical_holds": {row.get("id") for row in physical} == {"physical_lock_transform", "physical_constraint_stiffness", "physical_constraint_damping", "physical_retention_capacity", "physical_release_energy"} and all(row.get("estimate") is None and row.get("standard_uncertainty") is None and row.get("distribution") is None and row.get("degrees_of_freedom") is None and row.get("source") is None and str(row.get("status", "")).startswith("HOLD_") for row in physical) and units.get("physical_measurement_model_available") is False and units.get("gum_or_monte_carlo_uncertainty_propagation_authorized") is False,
        "governance_holds": set(required_false) == EXPECTED_REQUIRED_FALSE_KEYS and not any(required_false.values()) and governance.get("authorized_scope") == EXPECTED_AUTHORIZED_SCOPE and governance.get("current_status") == "CONTRACT_FROZEN_FOR_VALIDATION__FINAL_CREDIT_REQUIRES_INDEPENDENT_AUDIT__NO_IMPLEMENTATION" and governance.get("formal_sim13_v2_state_unchanged") == {"passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"]} and set(governance.get("forbidden_actions", [])) == {"CALL_UNIFIED_PRIVATE_BUILDER", "CALL_UNIFIED_GENERATOR", "CREATE_FORMAL_INTERFACE_INSTANCE", "CLAIM_ACTUAL_B601_BINDING", "CLAIM_PHYSICAL_LOCK_OR_HELD_CAPTURE", "CLAIM_GRASP_SUCCESS", "CLAIM_RELEASED_ATTACHED_TARGET", "CREDIT_THIS_PACKAGE_TO_FORMAL_NC19", "AUTHORIZE_PRODUCTION_RELEASE_OR_NEXT_STAGE"} and governance.get("forbidden_artifacts") == ["*.urdf", "MECH_RL_SYSTEM_INTERFACE_V2.yaml", "UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json", "T_gripper_target_locked", "execution.lock", "release.marker"],
        "numeric_inventory": numerical.get("contract_freeze_mutation_ids") == EXPECTED_CONTRACT_FREEZE_MUTATION_IDS and numerical.get("future_solver_required_negative_control_ids") == EXPECTED_FUTURE_SOLVER_NEGATIVE_CONTROL_IDS and len(numerical.get("event_local_native_unit_tolerances", {})) == 26 and numerical.get("active_trajectory_native_unit_tolerances") == EXPECTED_ACTIVE_TOLERANCES and numerical.get("future_solver_gate_rule") == "all tolerances apply per native-unit channel and over the full trajectory where stated; no terminal label, summary maximum, or aggregate mixed-unit norm can replace the underlying samplewise evidence",
    }


def _independent_mutations(
    source_bindings: dict[str, Any], model: dict[str, Any], governance: dict[str, Any], units: dict[str, Any], numerical: dict[str, Any]
) -> tuple[bool, dict[str, bool]]:
    mutations: dict[str, bool] = {}

    bad_sources = copy.deepcopy(source_bindings)
    bad_sources["sources"][0]["sha256"] = "0" * 64
    mutations["B4CFNC01_SOURCE_SHA_DRIFT"] = not _bindings_exact(bad_sources)[0]

    bad_trigger = copy.deepcopy(model)
    bad_trigger["trigger_contract"]["reference_record_index"] = 206
    bad_trigger["trigger_contract"]["cherry_pick_forbidden"] = False
    mutations["B4CFNC02_TRIGGER_CHERRY_PICK"] = not _semantic_checks(bad_trigger, governance, units, numerical)["trigger_exact"]

    bad_upstream = copy.deepcopy(model)
    bad_upstream["upstream_ruling"]["b3_grasp_map_rank"] = 6
    bad_upstream["upstream_ruling"]["full_6d_wrench_span"] = True
    mutations["B4CFNC03_B3_RANK6_REWRITE"] = not _semantic_checks(bad_upstream, governance, units, numerical)["upstream_rank5_only"]

    bad_wrench = copy.deepcopy(model)
    bad_wrench["wrench_and_momentum_semantics"]["synthetic_missing_sixth_wrench_scalar"] = "chi_missing=a_chord dot ell"
    mutations["B4CFNC04_AXIAL_MISSING_WRENCH_MISFORMULA"] = not _semantic_checks(bad_wrench, governance, units, numerical)["correct_missing_wrench"]

    bad_solver = copy.deepcopy(numerical)
    bad_solver["rank_and_linear_solve"]["condition_number_whitelist"] = ["M_minus_unscaled"]
    mutations["B4CFNC05_UNSCALED_MIXED_CONDITION"] = not _semantic_checks(model, governance, units, bad_solver)["scaled_units_and_condition"]

    bad_switch = copy.deepcopy(model)
    bad_switch["contact_to_constraint_switch"]["b3_contact_force_after_acquisition"] = "active"
    bad_switch["contact_to_constraint_switch"]["double_counting_contact_and_constraint"] = "allowed"
    mutations["B4CFNC06_CONTACT_CONSTRAINT_DOUBLE_ACTIVITY"] = not _semantic_checks(bad_switch, governance, units, numerical)["switch_energy_complete"]

    bad_energy = copy.deepcopy(model)
    bad_energy["contact_to_constraint_switch"]["switch_dissipation"] = "D_switch=1+2"
    bad_energy["contact_to_constraint_switch"]["full_event_energy_identity"] = "D_B3_minus token only"
    mutations["B4CFNC07_CONTACT_POTENTIAL_OMISSION"] = not _semantic_checks(bad_energy, governance, units, numerical)["switch_energy_complete"]

    bad_removal = copy.deepcopy(model)
    bad_removal["release_contract"]["release_impulse_linear_N_s"] = 0.001
    mutations["B4CFNC08_NONZERO_REMOVAL_IMPULSE"] = not _semantic_checks(bad_removal, governance, units, numerical)["removal_and_clearance"]

    bad_recontact = copy.deepcopy(model)
    bad_recontact["release_contract"]["contact_kernel_after_removal"] = "re-enabled"
    mutations["B4CFNC09_POST_REMOVAL_CONTACT_REACTIVATION"] = not _semantic_checks(bad_recontact, governance, units, numerical)["removal_and_clearance"]

    bad_governance = copy.deepcopy(governance)
    bad_governance["required_false"]["formal_nc19_credit"] = True
    bad_governance["authorized_scope"]["invoke_unified_private_builder_or_generator"] = True
    mutations["B4CFNC10_CURRENT_OR_FORMAL_AUTHORITY_TRUE"] = not _semantic_checks(model, bad_governance, units, numerical)["governance_holds"]

    bad_units = copy.deepcopy(units)
    physical_lock = next(row for row in bad_units["quantities"] if row["id"] == "physical_lock_transform")
    physical_lock["estimate"] = 0.0
    physical_lock["source"] = "zero_fill"
    mutations["B4CFNC11_NULL_PHYSICAL_INPUT_ZERO_FILL"] = not _semantic_checks(model, governance, bad_units, numerical)["physical_holds"]

    bad_terminal = copy.deepcopy(model)
    bad_terminal["state_machine"]["success_label"] = "GRASP_SUCCESS"
    bad_terminal["state_machine"]["failure_terminal"] = "ALLOW"
    mutations["B4CFNC12_SUCCESS_TERMINAL_ALIAS"] = not _semantic_checks(bad_terminal, governance, units, numerical)["trajectory_not_label"]
    return list(mutations) == EXPECTED_CONTRACT_FREEZE_MUTATION_IDS and all(mutations.values()), mutations


def _expected_source_manifest_path_roles() -> dict[str, str]:
    here_relative = HERE.relative_to(ROOT).as_posix()
    expected = {
        path: f"BOUND_{source_id.upper()}"
        for source_id, (path, _role) in EXPECTED_SOURCE_BINDINGS.items()
    }
    expected.update(
        {
            f"{here_relative}/{relative}": f"B4_LOCAL_SOURCE_{Path(relative).name.upper()}"
            for relative in EXPECTED_LOCAL_SOURCE_RELATIVE_PATHS
        }
    )
    return expected


def _unexpected_b4_artifacts() -> tuple[list[Path], list[Path]]:
    forbidden = (
        list(HERE.rglob("*.urdf"))
        + list(HERE.rglob("MECH_RL_SYSTEM_INTERFACE_V2.yaml"))
        + list(HERE.rglob("UNIFIED_R2_URDF_EXECUTION_AUTHORIZATION_V2.json"))
        + list(HERE.rglob("T_gripper_target_locked"))
        + list(HERE.rglob("execution.lock"))
        + list(HERE.rglob("release.marker"))
    )
    allowed_code = {
        (HERE / relative).resolve()
        for relative in EXPECTED_LOCAL_SOURCE_RELATIVE_PATHS
        if Path(relative).suffix.lower() == ".py"
    }
    executable_suffixes = {
        ".py", ".pyw", ".m", ".mlx", ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp",
        ".jl", ".ipynb", ".ps1", ".bat", ".cmd", ".sh", ".exe", ".dll",
    }
    unexpected_code = [
        path
        for path in HERE.rglob("*")
        if path.is_file() and path.suffix.lower() in executable_suffixes and path.resolve() not in allowed_code
    ]
    return forbidden, unexpected_code


def _unexpected_tree_files(allowed_outputs: list[Path]) -> list[Path]:
    allowed = {(HERE / relative).resolve() for relative in EXPECTED_LOCAL_SOURCE_RELATIVE_PATHS}
    allowed.update(path.resolve() for path in allowed_outputs)
    return [path for path in HERE.rglob("*") if path.is_file() and path.resolve() not in allowed]


def _validation_payload_exact(validation: dict[str, Any]) -> bool:
    validation_checks = validation.get("checks", {})
    pytest_payload = validation.get("pytest", {})
    exact_outcomes = {
        "passed": 62,
        "failed": 0,
        "skipped": 0,
        "xfailed": 0,
        "xpassed": 0,
        "deselected": 0,
        "errors": 0,
    }
    parsed_outcomes = _parse_pytest_outcomes(
        f"{pytest_payload.get('run_stdout', '')}\n{pytest_payload.get('run_stderr', '')}"
    )
    exact_implementation = {
        "b4_dynamics_solver_implemented": False,
        "physical_lock_implemented": False,
        "held_capture_passed": False,
        "current_system_bound": False,
        "formal_nc19_credit": False,
        "release_authorized": False,
        "next_stage_authorized": False,
    }
    return (
        validation.get("schema") == "SIM13_V4B4_CONTRACT_VALIDATION_V1"
        and validation.get("status") == "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT"
        and validation.get("score") == {"pass": 37, "fail": 0, "total": 37, "failed": []}
        and set(validation_checks) == EXPECTED_VALIDATOR_CHECK_IDS
        and all(row.get("pass") is True for row in validation_checks.values())
        and validation.get("expected_test_count") == 62
        and pytest_payload.get("collect_returncode") == 0
        and pytest_payload.get("collected") == 62
        and pytest_payload.get("run_returncode") == 0
        and pytest_payload.get("outcomes") == exact_outcomes
        and parsed_outcomes == exact_outcomes
        and validation.get("implementation_state") == exact_implementation
    )


def verify_existing_bundle() -> dict[str, Any]:
    required = [
        SOURCE_BINDINGS_PATH, MODEL_CONTRACT_PATH, GOVERNANCE_CONTRACT_PATH, UNITS_LEDGER_PATH,
        NUMERICAL_CONTRACT_PATH, SOURCE_MANIFEST_PATH, VALIDATION_PATH, EVIDENCE_MANIFEST_PATH,
        PRE_AUDIT_GATE_PATH, AUDIT_RECEIPT_PATH, FINAL_GATE_PATH, TERMINAL_MANIFEST_PATH,
    ]
    missing = [path.relative_to(ROOT).as_posix() for path in required if not path.is_file()]
    if missing:
        return {"pass": False, "failed": ["MISSING_REQUIRED_ARTIFACT"], "missing": missing}

    source_bindings = _load(SOURCE_BINDINGS_PATH)
    model = _load(MODEL_CONTRACT_PATH)
    governance = _load(GOVERNANCE_CONTRACT_PATH)
    units = _load(UNITS_LEDGER_PATH)
    numerical = _load(NUMERICAL_CONTRACT_PATH)
    source_manifest = _load(SOURCE_MANIFEST_PATH)
    validation = _load(VALIDATION_PATH)
    evidence_manifest = _load(EVIDENCE_MANIFEST_PATH)
    pre_audit = _load(PRE_AUDIT_GATE_PATH)
    receipt = _load(AUDIT_RECEIPT_PATH)
    final_gate = _load(FINAL_GATE_PATH)
    terminal = _load(TERMINAL_MANIFEST_PATH)

    checks: dict[str, bool] = {}
    semantic = _semantic_checks(model, governance, units, numerical)
    bindings_ok, _reports = _bindings_exact(source_bindings)
    checks["contracts_and_bindings"] = bindings_ok and all(semantic.values())

    source_records = source_manifest.get("records", [])
    actual_source_mapping = {
        row.get("path"): row.get("role") for row in source_records if isinstance(row, dict)
    }
    checks["source_manifest_recursive"] = (
        source_manifest.get("schema") == "SIM13_V4B4_CONTRACT_SOURCE_MANIFEST_V1"
        and source_manifest.get("scope") == "B4_CONTRACT_FREEZE_ONLY"
        and source_manifest.get("self_excluded") is True
        and len(source_records) == 29
        and actual_source_mapping == _expected_source_manifest_path_roles()
        and all(_verify_record(row) for row in source_records)
        and SOURCE_MANIFEST_PATH.relative_to(ROOT).as_posix() not in actual_source_mapping
    )
    checks["validation_exact"] = _validation_payload_exact(validation)

    evidence_records = evidence_manifest.get("records", [])
    evidence_by_role = {row.get("role"): row for row in evidence_records if isinstance(row, dict)}
    checks["evidence_manifest_exact"] = (
        evidence_manifest.get("schema") == "SIM13_V4B4_CONTRACT_EVIDENCE_MANIFEST_V1"
        and evidence_manifest.get("self_excluded") is True
        and set(evidence_by_role) == {"B4_CONTRACT_SOURCE_MANIFEST", "B4_CONTRACT_VALIDATION"}
        and len(evidence_records) == 2
        and _record_matches(evidence_by_role.get("B4_CONTRACT_SOURCE_MANIFEST", {}), SOURCE_MANIFEST_PATH, "B4_CONTRACT_SOURCE_MANIFEST")
        and _record_matches(evidence_by_role.get("B4_CONTRACT_VALIDATION", {}), VALIDATION_PATH, "B4_CONTRACT_VALIDATION")
    )

    pre_chain = pre_audit.get("hash_chain", {})
    expected_pre_scope = {
        "contract_preregistered": True,
        "implementation_started": False,
        "synthetic_constraint_executed": False,
        "physical_lock_or_held_capture": False,
        "current_system_or_formal_nc19_credit": False,
        "release_or_next_stage_authorized": False,
    }
    checks["pre_audit_exact"] = (
        pre_audit.get("schema") == "SIM13_V4B4_CONTRACT_PRE_AUDIT_GATE_V1"
        and pre_audit.get("overall_status") == "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT"
        and pre_audit.get("final_gate") is False
        and pre_audit.get("score") == validation.get("score")
        and set(pre_chain) == {"source_manifest", "validation", "evidence_manifest"}
        and _record_matches(pre_chain.get("source_manifest", {}), SOURCE_MANIFEST_PATH, "UPSTREAM_SOURCE_MANIFEST")
        and _record_matches(pre_chain.get("validation", {}), VALIDATION_PATH, "UPSTREAM_VALIDATION")
        and _record_matches(pre_chain.get("evidence_manifest", {}), EVIDENCE_MANIFEST_PATH, "UPSTREAM_EVIDENCE_MANIFEST")
        and pre_audit.get("scope_ruling") == expected_pre_scope
        and pre_audit.get("final_gate_issuer") == "independent_audit_phase_b4_contract.py"
    )

    receipt_checks = receipt.get("checks", {})
    receipt_upstream = receipt.get("upstream", {})
    expected_independence = {
        "imports_validator": False,
        "imports_b4_solver": False,
        "uses_validator_trigger_summary": False,
        "recomputes_raw_b3_trigger_rank_anchors": True,
        "uses_different_projection_fixture": True,
    }
    checks["audit_receipt_exact"] = (
        set(receipt) == {"schema", "status", "independence", "upstream", "score", "checks"}
        and receipt.get("schema") == "SIM13_V4B4_CONTRACT_INDEPENDENT_AUDIT_RECEIPT_V1"
        and receipt.get("status") == "PASS_INDEPENDENT_CONTRACT_AUDIT"
        and receipt.get("independence") == expected_independence
        and receipt.get("score") == {"pass": 22, "fail": 0, "total": 22, "failed": []}
        and set(receipt_checks) == EXPECTED_AUDIT_CHECK_IDS
        and all(row.get("pass") is True for row in receipt_checks.values())
        and set(receipt_upstream) == {"source_manifest", "validation", "evidence_manifest", "pre_audit_gate"}
        and _record_matches(receipt_upstream.get("source_manifest", {}), SOURCE_MANIFEST_PATH, "UPSTREAM_SOURCE_MANIFEST")
        and _record_matches(receipt_upstream.get("validation", {}), VALIDATION_PATH, "UPSTREAM_VALIDATION")
        and _record_matches(receipt_upstream.get("evidence_manifest", {}), EVIDENCE_MANIFEST_PATH, "UPSTREAM_EVIDENCE_MANIFEST")
        and _record_matches(receipt_upstream.get("pre_audit_gate", {}), PRE_AUDIT_GATE_PATH, "UPSTREAM_PRE_AUDIT_GATE")
    )

    expected_gates = [
        {"id": "V4B4-CFG01", "name": "synthetic 6DOF acquisition removal contract preregistration", "status": "PASS_AUDITED", "pass": True},
        {"id": "V4B4-CFG02", "name": "B4 dynamics solver implementation", "status": "HOLD_IMPLEMENTATION_NOT_STARTED", "pass": False},
        {"id": "V4B4-CFG03", "name": "synthetic constraint execution", "status": "HOLD_NOT_EXECUTED", "pass": False},
        {"id": "V4B4-CFG04", "name": "physical lock held capture grasp success", "status": "HOLD_NO_PHYSICAL_AUTHORITY", "pass": False},
        {"id": "V4B4-CFG05", "name": "current system and formal NC19", "status": "HOLD_FORMAL_V2_15_OF_20", "pass": False},
        {"id": "V4B4-CFG06", "name": "Owner production release next stage", "status": "HOLD_NOT_AUTHORIZED", "pass": False},
    ]
    expected_authorizations = {
        "b4_contract_freeze_audited": True,
        "b4_dynamics_solver_implemented": False,
        "synthetic_constraint_executed": False,
        "physical_lock_implemented": False,
        "held_capture_passed": False,
        "grasp_success": False,
        "target_attached_claimed": False,
        "current_system_bound": False,
        "formal_nc19_closed": False,
        "owner_authorized": False,
        "production_ready": False,
        "release_authorized": False,
        "next_stage_authorized": False,
    }
    anchors_ok, expected_anchors = _independent_trigger_rank_anchors(source_bindings, numerical)
    projection_ok, expected_projection_metrics = _independent_projection_proof(numerical)
    expected_final_gate = {
        "schema": "SIM13_V4B4_CONTRACT_AUDITED_GATE_V1",
        "overall_status": EXPECTED_STATUS,
        "final_gate": True,
        "scope": "CONTRACT_FREEZE_ONLY",
        "hash_chain": {
            "source_manifest": _record(SOURCE_MANIFEST_PATH, "UPSTREAM_SOURCE_MANIFEST"),
            "evidence_manifest": _record(EVIDENCE_MANIFEST_PATH, "UPSTREAM_EVIDENCE_MANIFEST"),
            "pre_audit_gate": _record(PRE_AUDIT_GATE_PATH, "UPSTREAM_PRE_AUDIT_GATE"),
            "independent_audit_receipt": _record(AUDIT_RECEIPT_PATH, "UPSTREAM_INDEPENDENT_AUDIT_RECEIPT"),
        },
        "validator_score": {"pass": 37, "fail": 0, "total": 37, "failed": []},
        "independent_audit_score": {"pass": 22, "fail": 0, "total": 22, "failed": []},
        "audited_contract_anchors": expected_anchors,
        "projection_identity_fixture": {
            "scope": "ABSTRACT_INDEPENDENT_ALGEBRA_FIXTURE__NOT_B3_EVENT_OR_B4_SOLVER",
            "metrics": expected_projection_metrics,
        },
        "gates": expected_gates,
        "authorizations": expected_authorizations,
        "formal_sim13_v2_state": {"passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"], "changed_by_this_package": False},
    }
    checks["final_gate_exact"] = anchors_ok and projection_ok and final_gate == expected_final_gate

    terminal_records = terminal.get("records", [])
    terminal_by_role = {row.get("role"): row for row in terminal_records if isinstance(row, dict)}
    expected_terminal = {
        "schema": "SIM13_V4B4_CONTRACT_TERMINAL_SELF_EXCLUDED_MANIFEST_V1",
        "self_excluded": True,
        "acyclic": True,
        "records": [
            _record(AUDIT_RECEIPT_PATH, "B4_CONTRACT_INDEPENDENT_AUDIT_RECEIPT"),
            _record(FINAL_GATE_PATH, "B4_CONTRACT_FINAL_AUDITED_GATE"),
        ],
    }
    checks["terminal_manifest_exact"] = terminal == expected_terminal and TERMINAL_MANIFEST_PATH.relative_to(ROOT).as_posix() not in {row.get("path") for row in terminal_records}
    forbidden, unexpected_code = _unexpected_b4_artifacts()
    unexpected_tree = _unexpected_tree_files([
        SOURCE_MANIFEST_PATH, VALIDATION_PATH, EVIDENCE_MANIFEST_PATH, PRE_AUDIT_GATE_PATH,
        AUDIT_RECEIPT_PATH, FINAL_GATE_PATH, TERMINAL_MANIFEST_PATH,
    ])
    checks["tree_has_no_authority_or_solver_artifact"] = not forbidden and not unexpected_code and not unexpected_tree
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "pass": not failed,
        "score": {"pass": len(checks) - len(failed), "fail": len(failed), "total": len(checks)},
        "failed": failed,
        "checks": checks,
        "forbidden": [path.relative_to(HERE).as_posix() for path in forbidden],
        "unexpected_code": [path.relative_to(HERE).as_posix() for path in unexpected_code],
        "unexpected_tree": [path.relative_to(HERE).as_posix() for path in unexpected_tree],
    }


def run_audit() -> dict[str, Any]:
    for path in (AUDIT_RECEIPT_PATH, FINAL_GATE_PATH, TERMINAL_MANIFEST_PATH):
        if path.exists():
            path.unlink()

    required_inputs = [SOURCE_MANIFEST_PATH, VALIDATION_PATH, EVIDENCE_MANIFEST_PATH, PRE_AUDIT_GATE_PATH]
    if not all(path.is_file() for path in required_inputs):
        raise RuntimeError("RUN_VALIDATOR_BEFORE_INDEPENDENT_AUDIT")

    source_bindings = _load(SOURCE_BINDINGS_PATH)
    model = _load(MODEL_CONTRACT_PATH)
    governance = _load(GOVERNANCE_CONTRACT_PATH)
    units = _load(UNITS_LEDGER_PATH)
    numerical = _load(NUMERICAL_CONTRACT_PATH)
    source_manifest = _load(SOURCE_MANIFEST_PATH)
    validation = _load(VALIDATION_PATH)
    evidence_manifest = _load(EVIDENCE_MANIFEST_PATH)
    pre_audit = _load(PRE_AUDIT_GATE_PATH)

    checks: dict[str, dict[str, Any]] = {}

    def add(check_id: str, name: str, passed: bool, evidence: Any) -> None:
        checks[check_id] = {"name": name, "pass": bool(passed), "evidence": evidence}

    semantic = _semantic_checks(model, governance, units, numerical)

    manifest_records = source_manifest.get("records", [])
    here_relative = HERE.relative_to(ROOT).as_posix()
    expected_manifest_path_roles = {
        path: f"BOUND_{source_id.upper()}"
        for source_id, (path, _role) in EXPECTED_SOURCE_BINDINGS.items()
    }
    expected_manifest_path_roles.update(
        {
            f"{here_relative}/{relative}": f"B4_LOCAL_SOURCE_{Path(relative).name.upper()}"
            for relative in EXPECTED_LOCAL_SOURCE_RELATIVE_PATHS
        }
    )
    actual_manifest_path_roles = {
        row.get("path"): row.get("role")
        for row in manifest_records
        if isinstance(row, dict)
    }
    source_manifest_ok = (
        source_manifest.get("schema") == "SIM13_V4B4_CONTRACT_SOURCE_MANIFEST_V1"
        and source_manifest.get("scope") == "B4_CONTRACT_FREEZE_ONLY"
        and source_manifest.get("self_excluded") is True
        and len(manifest_records) == 29
        and len({row.get("path") for row in manifest_records}) == 29
        and len({row.get("role") for row in manifest_records}) == 29
        and actual_manifest_path_roles == expected_manifest_path_roles
        and all(_verify_record(row) for row in manifest_records)
        and SOURCE_MANIFEST_PATH.relative_to(ROOT).as_posix() not in {row.get("path") for row in manifest_records}
    )
    add("B4IA-01", "source manifest is exact self-excluded and byte-hash valid", source_manifest_ok, {"records": len(manifest_records)})

    bindings_ok, binding_reports = _bindings_exact(source_bindings)
    add("B4IA-02", "all 13 upstream source bindings independently match exact set path bytes SHA role", bindings_ok, binding_reports)

    trigger_ok, trigger_metrics = _independent_trigger_rank_anchors(source_bindings, numerical)
    add("B4IA-03", "raw B3 trace independently yields first trigger no prior abort and exact frozen trigger contract", trigger_ok and semantic["trigger_exact"], trigger_metrics)
    add("B4IA-04", "independent normalized grasp map is rank5 and missing-wrench functional is correct", trigger_ok and semantic["upstream_rank5_only"] and trigger_metrics.get("grasp_scaled_rank") == 5 and abs(trigger_metrics.get("two_point_contact_chi_missing_N_m_s", 1.0)) < 1e-15 and abs(trigger_metrics.get("synthetic_axial_only_chi_missing_N_m_s", 0.0)) > 0.0, trigger_metrics)

    b3_gate = _load(_bound_path(source_bindings, "b3_audited_gate"))
    b3_hold_ok = b3_gate.get("final_gate") is True and b3_gate.get("audited_metrics", {}).get("all_qualifying_grasp_map_rank") == 5 and b3_gate.get("audited_metrics", {}).get("full_6d_wrench_span") is False and not any(b3_gate.get("authorizations", {}).get(key) for key in ("lock_implemented", "grasp_success", "current_system_bound", "formal_nc19_closed", "release_authorized", "next_stage_authorized"))
    add("B4IA-05", "upstream B3 remains rank5 transient-only with all lock current formal holds", b3_hold_ok, {"status": b3_gate.get("overall_status")})

    add("B4IA-06", "all four local contract payloads are canonical and snapshot dimensions are explicit", semantic["contract_payloads_canonical"] and semantic["dimensions_and_snapshot"], {})
    add("B4IA-07", "direct reduced and block-KKT solver contracts forbid acquisition pseudoinverse", semantic["direct_solvers_no_acquisition_pinv"], {})
    add("B4IA-08", "rank and condition are scaled with native-unit separation", semantic["scaled_units_and_condition"], {})
    add("B4IA-09", "rank5 missing wrench scalar and equivalent palm wrench signs are exact", semantic["correct_missing_wrench"] and semantic["equivalent_service_wrench_once"], {})
    add("B4IA-10", "switch energy identity carries both potentials and prior B3 dissipation once", semantic["switch_energy_complete"], {})
    add("B4IA-11", "active attached bias contains M Ldot eta and full-trajectory requirement", semantic["active_bias_complete"] and semantic["trajectory_not_label"], {})
    add("B4IA-12", "removal is continuous zero impulse positive-clearance and contact-kernel-off", semantic["removal_and_clearance"], {})
    add("B4IA-13", "physical quantities and formal governance remain null false HOLD", semantic["physical_holds"] and semantic["governance_holds"], {})
    add("B4IA-14", "numeric tolerance and negative-control inventories are frozen", semantic["numeric_inventory"], {})

    projection_ok, projection_metrics = _independent_projection_proof(numerical)
    add("B4IA-15", "independent abstract fixture proves reduced versus direct block-KKT projection and energy identity without B4 execution", projection_ok, {"scope": "ABSTRACT_INDEPENDENT_ALGEBRA_FIXTURE__NOT_B3_EVENT_OR_B4_SOLVER", "metrics": projection_metrics})

    mutations_ok, mutation_results = _independent_mutations(source_bindings, model, governance, units, numerical)
    add("B4IA-16", "independent real in-memory mutations are rejected", mutations_ok, mutation_results)

    formal = _load(_bound_path(source_bindings, "formal_sim13_v2_gate"))
    nc = _load(_bound_path(source_bindings, "formal_sim13_v2_negative_controls"))
    formal_ok = formal.get("formal_negative_controls_passed") == 15 and formal.get("formal_negative_controls_declared") == 20 and formal.get("formal_negative_controls_hold_ids") == ["NC15", "NC16", "NC18", "NC19", "NC20"] and "NC19" in json.dumps(nc) and formal.get("contact_grasp_gate_passed") is False
    add("B4IA-17", "formal Sim13 stays 15 of 20 and NC19 dependency HOLD", formal_ok, {"passed": formal.get("formal_negative_controls_passed"), "hold_ids": formal.get("formal_negative_controls_hold_ids")})

    forbidden_files, solver_files = _unexpected_b4_artifacts()
    shadow_files = _unexpected_tree_files([SOURCE_MANIFEST_PATH, VALIDATION_PATH, EVIDENCE_MANIFEST_PATH, PRE_AUDIT_GATE_PATH])
    add("B4IA-18", "no solver source authority artifact or unmanifested shadow file exists", not forbidden_files and not solver_files and not shadow_files, {"forbidden": [str(path) for path in forbidden_files], "solver": [str(path) for path in solver_files], "shadow": [str(path) for path in shadow_files]})

    evidence_records = evidence_manifest.get("records", [])
    evidence_by_role = {row.get("role"): row for row in evidence_records if isinstance(row, dict)}
    evidence_ok = evidence_manifest.get("schema") == "SIM13_V4B4_CONTRACT_EVIDENCE_MANIFEST_V1" and evidence_manifest.get("self_excluded") is True and set(evidence_by_role) == {"B4_CONTRACT_SOURCE_MANIFEST", "B4_CONTRACT_VALIDATION"} and len(evidence_records) == 2 and _record_matches(evidence_by_role.get("B4_CONTRACT_SOURCE_MANIFEST", {}), SOURCE_MANIFEST_PATH, "B4_CONTRACT_SOURCE_MANIFEST") and _record_matches(evidence_by_role.get("B4_CONTRACT_VALIDATION", {}), VALIDATION_PATH, "B4_CONTRACT_VALIDATION") and EVIDENCE_MANIFEST_PATH.relative_to(ROOT).as_posix() not in {row.get("path") for row in evidence_records}
    pre_chain = pre_audit.get("hash_chain", {})
    pre_scope_expected = {"contract_preregistered": True, "implementation_started": False, "synthetic_constraint_executed": False, "physical_lock_or_held_capture": False, "current_system_or_formal_nc19_credit": False, "release_or_next_stage_authorized": False}
    pre_ok = pre_audit.get("schema") == "SIM13_V4B4_CONTRACT_PRE_AUDIT_GATE_V1" and pre_audit.get("overall_status") == "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT" and pre_audit.get("final_gate") is False and pre_audit.get("score") == validation.get("score") and set(pre_chain) == {"source_manifest", "validation", "evidence_manifest"} and _record_matches(pre_chain.get("source_manifest", {}), SOURCE_MANIFEST_PATH, "UPSTREAM_SOURCE_MANIFEST") and _record_matches(pre_chain.get("validation", {}), VALIDATION_PATH, "UPSTREAM_VALIDATION") and _record_matches(pre_chain.get("evidence_manifest", {}), EVIDENCE_MANIFEST_PATH, "UPSTREAM_EVIDENCE_MANIFEST") and pre_audit.get("scope_ruling") == pre_scope_expected and pre_audit.get("final_gate_issuer") == "independent_audit_phase_b4_contract.py"
    add("B4IA-19", "validator evidence DAG and pre-audit Gate are acyclic and byte-hash valid", evidence_ok and pre_ok, {"evidence_records": len(evidence_records), "pre_chain_records": len(pre_chain)})

    validation_checks = validation.get("checks", {})
    expected_implementation_state = {"b4_dynamics_solver_implemented": False, "physical_lock_implemented": False, "held_capture_passed": False, "current_system_bound": False, "formal_nc19_credit": False, "release_authorized": False, "next_stage_authorized": False}
    pytest_payload = validation.get("pytest", {})
    independently_parsed_outcomes = _parse_pytest_outcomes(f"{pytest_payload.get('run_stdout', '')}\n{pytest_payload.get('run_stderr', '')}")
    exact_pytest_outcomes = {"passed": 62, "failed": 0, "skipped": 0, "xfailed": 0, "xpassed": 0, "deselected": 0, "errors": 0}
    validation_ok = validation.get("schema") == "SIM13_V4B4_CONTRACT_VALIDATION_V1" and validation.get("status") == "PASS_VALIDATOR_PENDING_INDEPENDENT_AUDIT" and validation.get("score") == {"pass": 37, "fail": 0, "total": 37, "failed": []} and set(validation_checks) == EXPECTED_VALIDATOR_CHECK_IDS and all(row.get("pass") is True for row in validation_checks.values()) and validation.get("expected_test_count") == 62 and pytest_payload.get("collect_returncode") == 0 and pytest_payload.get("collected") == 62 and pytest_payload.get("run_returncode") == 0 and pytest_payload.get("outcomes") == exact_pytest_outcomes and independently_parsed_outcomes == exact_pytest_outcomes and validation.get("implementation_state") == expected_implementation_state
    add("B4IA-20", "validator passed exact 62-test inventory without implementation credit", validation_ok, {"score": validation.get("score"), "tests": validation.get("pytest", {}).get("collected")})

    gate_rule_ok = governance.get("current_status") == "CONTRACT_FROZEN_FOR_VALIDATION__FINAL_CREDIT_REQUIRES_INDEPENDENT_AUDIT__NO_IMPLEMENTATION" and governance.get("required_contract_gate_status") == EXPECTED_STATUS and "implementation_not_started" in governance.get("contract_gate_rule", "") and governance.get("authorized_scope") == EXPECTED_AUTHORIZED_SCOPE
    add("B4IA-21", "only exact contract-freeze status is issuable and solver authority remains false", gate_rule_ok, governance.get("required_contract_gate_status"))

    predecessor_ids_exact = set(checks) == EXPECTED_AUDIT_PREDECESSOR_IDS
    forbidden_now, unexpected_code_now = _unexpected_b4_artifacts()
    shadow_now = _unexpected_tree_files([SOURCE_MANIFEST_PATH, VALIDATION_PATH, EVIDENCE_MANIFEST_PATH, PRE_AUDIT_GATE_PATH])
    signing_inputs_fresh = (
        _load(SOURCE_BINDINGS_PATH) == source_bindings
        and _load(MODEL_CONTRACT_PATH) == model
        and _load(GOVERNANCE_CONTRACT_PATH) == governance
        and _load(UNITS_LEDGER_PATH) == units
        and _load(NUMERICAL_CONTRACT_PATH) == numerical
        and _load(SOURCE_MANIFEST_PATH) == source_manifest
        and _load(VALIDATION_PATH) == validation
        and _load(EVIDENCE_MANIFEST_PATH) == evidence_manifest
        and _load(PRE_AUDIT_GATE_PATH) == pre_audit
        and all(_verify_record(row) for row in source_manifest.get("records", []))
        and _bindings_exact(source_bindings)[0]
        and all(semantic.values())
        and not forbidden_now
        and not unexpected_code_now
        and not shadow_now
    )
    all_checks_pass = predecessor_ids_exact and all(row["pass"] for row in checks.values()) and signing_inputs_fresh
    add("B4IA-22", "all exact independent audit predecessors and signing inputs pass fresh revalidation", all_checks_pass, {"predecessor_count": len(checks), "predecessor_ids_exact": predecessor_ids_exact, "signing_inputs_fresh": signing_inputs_fresh})
    passed = sum(1 for row in checks.values() if row["pass"])
    failed = [check_id for check_id, row in checks.items() if not row["pass"]]

    audit_receipt = {
        "schema": "SIM13_V4B4_CONTRACT_INDEPENDENT_AUDIT_RECEIPT_V1",
        "status": "PASS_INDEPENDENT_CONTRACT_AUDIT" if not failed else "FAIL_INDEPENDENT_CONTRACT_AUDIT",
        "independence": {
            "imports_validator": False,
            "imports_b4_solver": False,
            "uses_validator_trigger_summary": False,
            "recomputes_raw_b3_trigger_rank_anchors": True,
            "uses_different_projection_fixture": True,
        },
        "upstream": {
            "source_manifest": _record(SOURCE_MANIFEST_PATH, "UPSTREAM_SOURCE_MANIFEST"),
            "validation": _record(VALIDATION_PATH, "UPSTREAM_VALIDATION"),
            "evidence_manifest": _record(EVIDENCE_MANIFEST_PATH, "UPSTREAM_EVIDENCE_MANIFEST"),
            "pre_audit_gate": _record(PRE_AUDIT_GATE_PATH, "UPSTREAM_PRE_AUDIT_GATE"),
        },
        "score": {"pass": passed, "fail": len(failed), "total": len(checks), "failed": failed},
        "checks": checks,
    }
    try:
        _write(AUDIT_RECEIPT_PATH, audit_receipt)

        final_status = EXPECTED_STATUS if not failed else "FAIL_PHASE_B4_CONTRACT_FREEZE_AUDIT"
        final_gate = {
            "schema": "SIM13_V4B4_CONTRACT_AUDITED_GATE_V1",
            "overall_status": final_status,
            "final_gate": not failed,
            "scope": "CONTRACT_FREEZE_ONLY",
            "hash_chain": {
                "source_manifest": _record(SOURCE_MANIFEST_PATH, "UPSTREAM_SOURCE_MANIFEST"),
                "evidence_manifest": _record(EVIDENCE_MANIFEST_PATH, "UPSTREAM_EVIDENCE_MANIFEST"),
                "pre_audit_gate": _record(PRE_AUDIT_GATE_PATH, "UPSTREAM_PRE_AUDIT_GATE"),
                "independent_audit_receipt": _record(AUDIT_RECEIPT_PATH, "UPSTREAM_INDEPENDENT_AUDIT_RECEIPT"),
            },
            "validator_score": validation.get("score"),
            "independent_audit_score": audit_receipt["score"],
            "audited_contract_anchors": trigger_metrics,
            "projection_identity_fixture": {
                "scope": "ABSTRACT_INDEPENDENT_ALGEBRA_FIXTURE__NOT_B3_EVENT_OR_B4_SOLVER",
                "metrics": projection_metrics,
            },
            "gates": [
                {"id": "V4B4-CFG01", "name": "synthetic 6DOF acquisition removal contract preregistration", "status": "PASS_AUDITED" if not failed else "FAIL", "pass": not failed},
                {"id": "V4B4-CFG02", "name": "B4 dynamics solver implementation", "status": "HOLD_IMPLEMENTATION_NOT_STARTED", "pass": False},
                {"id": "V4B4-CFG03", "name": "synthetic constraint execution", "status": "HOLD_NOT_EXECUTED", "pass": False},
                {"id": "V4B4-CFG04", "name": "physical lock held capture grasp success", "status": "HOLD_NO_PHYSICAL_AUTHORITY", "pass": False},
                {"id": "V4B4-CFG05", "name": "current system and formal NC19", "status": "HOLD_FORMAL_V2_15_OF_20", "pass": False},
                {"id": "V4B4-CFG06", "name": "Owner production release next stage", "status": "HOLD_NOT_AUTHORIZED", "pass": False},
            ],
            "authorizations": {
                "b4_contract_freeze_audited": not failed,
                "b4_dynamics_solver_implemented": False,
                "synthetic_constraint_executed": False,
                "physical_lock_implemented": False,
                "held_capture_passed": False,
                "grasp_success": False,
                "target_attached_claimed": False,
                "current_system_bound": False,
                "formal_nc19_closed": False,
                "owner_authorized": False,
                "production_ready": False,
                "release_authorized": False,
                "next_stage_authorized": False,
            },
            "formal_sim13_v2_state": {"passed": 15, "declared": 20, "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"], "changed_by_this_package": False},
        }
        _write(FINAL_GATE_PATH, final_gate)

        terminal = {
            "schema": "SIM13_V4B4_CONTRACT_TERMINAL_SELF_EXCLUDED_MANIFEST_V1",
            "self_excluded": True,
            "acyclic": True,
            "records": [
                _record(AUDIT_RECEIPT_PATH, "B4_CONTRACT_INDEPENDENT_AUDIT_RECEIPT"),
                _record(FINAL_GATE_PATH, "B4_CONTRACT_FINAL_AUDITED_GATE"),
            ],
        }
        _write(TERMINAL_MANIFEST_PATH, terminal)
        if not failed:
            readback_exact = (
                _load(AUDIT_RECEIPT_PATH) == audit_receipt
                and _load(FINAL_GATE_PATH) == final_gate
                and _load(TERMINAL_MANIFEST_PATH) == terminal
            )
            recursive_verification = verify_existing_bundle()
            if not readback_exact or not recursive_verification.get("pass"):
                raise RuntimeError(
                    "POST_WRITE_RECURSIVE_READBACK_FAILED__PASS_ARTIFACTS_REMOVED__"
                    + json.dumps({"readback_exact": readback_exact, "verification": recursive_verification}, ensure_ascii=False)
                )
        return final_gate
    except Exception:
        for path in (AUDIT_RECEIPT_PATH, FINAL_GATE_PATH, TERMINAL_MANIFEST_PATH):
            if path.exists():
                path.unlink()
        raise


if __name__ == "__main__":
    gate = run_audit()
    try:
        recursive_verification = verify_existing_bundle() if gate["final_gate"] else {"pass": False, "reason": "FINAL_GATE_FALSE"}
    except Exception as exc:
        recursive_verification = {"pass": False, "failed": ["SECOND_READBACK_EXCEPTION"], "exception": type(exc).__name__}
    exit_pass = gate["final_gate"] and recursive_verification.get("pass") is True
    if not exit_pass and gate["final_gate"]:
        for path in (AUDIT_RECEIPT_PATH, FINAL_GATE_PATH, TERMINAL_MANIFEST_PATH):
            if path.exists():
                path.unlink()
    final_sha = _record(FINAL_GATE_PATH, "FINAL_GATE")["sha256"] if FINAL_GATE_PATH.is_file() else None
    terminal_sha = _record(TERMINAL_MANIFEST_PATH, "TERMINAL_MANIFEST")["sha256"] if TERMINAL_MANIFEST_PATH.is_file() else None
    print(
        json.dumps(
            {
                "status": gate["overall_status"],
                "validator_score": gate["validator_score"],
                "independent_audit_score": gate["independent_audit_score"],
                "final_gate_sha256": final_sha,
                "terminal_manifest_sha256": terminal_sha,
                "recursive_bundle_verification": recursive_verification,
            },
            indent=2,
        )
    )
    raise SystemExit(0 if exit_pass else 1)
