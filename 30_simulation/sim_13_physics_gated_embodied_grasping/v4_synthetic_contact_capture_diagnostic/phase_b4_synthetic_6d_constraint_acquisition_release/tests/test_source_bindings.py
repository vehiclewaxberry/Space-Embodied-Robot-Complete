from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from conftest import ROOT


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


def _record(source_bindings: dict, source_id: str) -> dict:
    return next(row for row in source_bindings["sources"] if row["id"] == source_id)


def test_source_ids_paths_and_roles_are_unique(source_bindings: dict) -> None:
    rows = source_bindings["sources"]
    actual = {row["id"]: (row["path"], row["role"]) for row in rows}
    assert actual == EXPECTED_SOURCE_BINDINGS
    assert len(rows) == len(EXPECTED_SOURCE_BINDINGS)
    assert len({row["path"] for row in rows}) == len(rows)
    assert len({row["role"] for row in rows}) == len(rows)


def test_every_bound_source_matches_bytes_and_sha256(source_bindings: dict) -> None:
    for row in source_bindings["sources"]:
        path = (ROOT / row["path"]).resolve()
        assert path.is_relative_to(ROOT.resolve())
        data = path.read_bytes()
        assert len(data) == row["bytes"]
        assert hashlib.sha256(data).hexdigest().upper() == row["sha256"]


def test_b3_audited_gate_preserves_rank5_and_all_holds(source_bindings: dict) -> None:
    gate = json.loads((ROOT / _record(source_bindings, "b3_audited_gate")["path"]).read_text(encoding="utf-8"))
    assert gate["final_gate"] is True
    assert gate["audited_metrics"]["all_qualifying_grasp_map_rank"] == 5
    assert gate["audited_metrics"]["full_6d_wrench_span"] is False
    assert gate["audited_metrics"]["full_6d_force_closure"] is False
    for key in (
        "lock_implemented",
        "grasp_success",
        "current_system_bound",
        "formal_nc19_closed",
        "owner_authorized",
        "production_ready",
        "release_authorized",
        "next_stage_authorized",
    ):
        assert gate["authorizations"][key] is False


def test_first_qualifying_b3_record_is_exactly_frozen_trigger(source_bindings: dict, model_contract: dict) -> None:
    trace = json.loads((ROOT / _record(source_bindings, "b3_reference_trace")["path"]).read_text(encoding="utf-8"))
    records = trace["reference_records"]
    qualifying = [
        index
        for index, row in enumerate(records)
        if row["soft_capture_criteria"]["soft_capture_transient_qualifies"]
        and row["soft_capture_criteria"]["all_ledgers_closed"]
    ]
    trigger = model_contract["trigger_contract"]
    assert qualifying[0] == trigger["reference_record_index"] == 205
    assert records[qualifying[0]]["time_s"] == trigger["reference_time_s"]
    assert sum(index <= qualifying[0] for index in qualifying) == trigger["required_upstream_candidate_count_at_or_before_trigger"]


def test_trigger_is_proved_by_raw_predicates_not_label_only(source_bindings: dict) -> None:
    trace = json.loads((ROOT / _record(source_bindings, "b3_reference_trace")["path"]).read_text(encoding="utf-8"))
    row = trace["reference_records"][205]
    criteria = row["soft_capture_criteria"]
    assert row["state_label"] == "SOFT_CAPTURE_TRANSIENT_CANDIDATE"
    assert criteria["left_contact"] is True
    assert criteria["right_contact"] is True
    assert criteria["all_ledgers_closed"] is True
    assert criteria["soft_capture_transient_qualifies"] is True
    assert criteria["dual_contact_dwell_s"] >= 0.001


def test_no_prior_upstream_abort_exists_before_frozen_trigger(source_bindings: dict) -> None:
    trace = json.loads((ROOT / _record(source_bindings, "b3_reference_trace")["path"]).read_text(encoding="utf-8"))
    labels = [row["state_label"] for row in trace["reference_records"][:206]]
    assert not any("ABORT" in label or "FAIL_CLOSED" in label for label in labels)


def test_lref_and_contact_potential_anchors_are_independently_recomputed(source_bindings: dict, numerical_contract: dict) -> None:
    trace = json.loads((ROOT / _record(source_bindings, "b3_reference_trace")["path"]).read_text(encoding="utf-8"))
    row = trace["reference_records"][205]
    p_left = row["contacts"]["left"]["common_contact_point_inertial_m"]
    p_right = row["contacts"]["right"]["common_contact_point_inertial_m"]
    l_ref = 0.5 * math.sqrt(sum((right - left) ** 2 for left, right in zip(p_left, p_right)))
    u_left = row["contacts"]["left"]["elastic_energy_j"]
    u_right = row["contacts"]["right"]["elastic_energy_j"]
    anchors = numerical_contract["frozen_reference_anchors"]
    assert l_ref == anchors["reference_length_m"]
    assert u_left == anchors["left_contact_elastic_energy_j"]
    assert u_right == anchors["right_contact_elastic_energy_j"]
    assert u_left + u_right == anchors["total_contact_elastic_energy_j"]


def test_m06_physical_contact_and_lock_remain_null_hold(source_bindings: dict) -> None:
    text = (ROOT / _record(source_bindings, "m06_contact_lock_contract")["path"]).read_text(encoding="utf-8")
    assert "status: HOLD_NO_PHYSICAL_CONTACT_ACTUATOR_OR_LOCK_AUTHORITY" in text
    assert "lock_confirmed: null" in text
    assert "lock_retention_force_N: null" in text
    assert "released_for_mission_gate: false" in text
    assert "next_stage_authorized: false" in text


def test_m07_attached_target_recovery_inputs_remain_null_hold(source_bindings: dict) -> None:
    text = (ROOT / _record(source_bindings, "m07_attached_target_recovery_contract")["path"]).read_text(encoding="utf-8")
    for token in (
        "selected_post_capture_model_branch: null",
        "T_gripper_target_locked: null",
        "lock_stiffness: null",
        "lock_retention_force_N: null",
        "lock_confirmation_predicate: null",
    ):
        assert token in text
    assert "ATTACHED_TARGET_RECOVERY_HOLD" in text


def test_contact_parameter_zero_fill_is_forbidden(source_bindings: dict) -> None:
    text = (ROOT / _record(source_bindings, "m5_contact_parameter_contract")["path"]).read_text(encoding="utf-8")
    assert "zero_fill_forbidden: true" in text
    assert "left_contact_frame_T_gripper_link: null" in text
    assert "right_contact_frame_T_gripper_link: null" in text
    assert "physical_contact_kernel_authorized: false" in text


def test_formal_sim13_v2_and_nc19_remain_dependency_hold(source_bindings: dict) -> None:
    gate = json.loads((ROOT / _record(source_bindings, "formal_sim13_v2_gate")["path"]).read_text(encoding="utf-8"))
    assert gate["formal_negative_controls_passed"] == 15
    assert gate["formal_negative_controls_declared"] == 20
    assert gate["formal_negative_controls_hold_ids"] == ["NC15", "NC16", "NC18", "NC19", "NC20"]
    assert gate["contact_grasp_gate_passed"] is False
    assert gate["system_urdf_available"] is False
    assert gate["system_interface_instantiated"] is False


def test_current_production_mechanical_binding_is_invalidated(source_bindings: dict) -> None:
    gate = json.loads((ROOT / _record(source_bindings, "current_mechanical_binding_audit")["path"]).read_text(encoding="utf-8"))
    payload = json.dumps(gate, ensure_ascii=False, sort_keys=True)
    assert "INVALIDATED" in payload
    assert gate.get("next_stage_authorized", False) is False
