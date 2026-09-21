"""Exact intake, metrology, authority-receipt, and promotion schemas."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any, Mapping, MutableSet

from .strict_io import IntakeError, deep_freeze, reject_nonfinite, require_exact_keys, validate_project_relative_path


CLASSIFICATIONS = (
    "MISSING",
    "MALFORMED",
    "HASH_DRIFT",
    "CANDIDATE_ONLY",
    "TEST_REQUIRED",
    "OWNER_REQUIRED",
    "PASS",
)
REQUIRED_DOMAINS = (
    "topology",
    "mass",
    "limits",
    "collision",
    "contact",
    "material",
    "flex",
    "harness",
    "targets",
)
MANDATORY_FALSE = (
    "intake_complete",
    "current_system_bound",
    "urdf_emitted",
    "system_urdf_available",
    "interface_instantiated",
    "runtime_ready",
    "dynamics_ready",
    "contact_ready",
    "full_flex_ready",
    "sim13_ready",
    "next_stage_authorized",
    "release",
)
PROMOTION_STAGES = (
    "OWNER_AUTHORIZED_URDF_EXECUTION",
    "CURRENT_SYSTEM_BINDING",
    "RUNTIME_FAIL_CLOSED_INTEGRATION",
    "DYNAMICS_BACKEND_INTEGRATION",
    "CONTACT_AND_GRASP_VALIDATION",
    "E15_RERUN_IF_FULL_FLEX",
)
QUANTITY_KEYS = {
    "value",
    "unit",
    "frame",
    "reference_point",
    "uncertainty",
    "authority",
    "status",
    "source_artifact",
    "source_field",
}
UNCERTAINTY_KEYS = {
    "standard_uncertainty",
    "distribution",
    "degrees_of_freedom",
    "correlation",
}
ZERO_FILL_FORBIDDEN_IDS = {
    "gripper_physical_rated_speed",
    "contact_normal_stiffness",
    "target_contact_effective_area",
}
EXPECTED_UNITS = {
    "system_total_links": "count",
    "system_total_joints": "count",
    "c01_design_mass": "kg",
    "gripper_urdf_model_velocity_literal": "m/s",
    "gripper_physical_rated_speed": "m/s",
    "contact_normal_stiffness": "N/m",
    "target_contact_effective_area": "m^2",
    "material_al7075_design_density": "kg/m^3",
    "full_flex_hf_to_rom_error": "percent",
    "e15_cross_solver_difference": "percent",
    "harness_mandatory_safe_states": "count",
    "route_c_available_physical_fields": "count",
    "debris_anchor_post_capture_rate": "deg/s",
    "satellite_anchor_post_capture_rate": "deg/s",
}
EXPECTED_SOURCE_IDS = (
    "topology_frame_tree",
    "mass_model",
    "limits_interface",
    "collision_gate",
    "contact_contract",
    "material_selection",
    "full_flex_checkpoint",
    "e22_gate",
    "e15_gate",
    "harness_gate",
    "handoff_gate",
    "route_c_checkpoint_b",
    "route_c_cad_gate",
    "current_binding_gate",
    "target_feasibility_gate",
)
PROMOTION_RECEIPT_ARTIFACT_ID = "SIM13_CURRENT_SYSTEM_PROMOTION_AUTHORITY_RECEIPT_V1"
REQUIRED_ABSENT_PATHS = (
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/generated_v2/unified_r2_c01_no_route_c_sim_candidate_v2.urdf",
    "30_simulation/sim_13_physics_gated_embodied_grasping/v2_system_rebind/interfaces/MECH_RL_SYSTEM_INTERFACE_V2.yaml",
)


def _source_receipt(artifact_id: str, path: str, byte_count: int, sha256: str) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "path": path,
        "bytes": byte_count,
        "sha256": sha256,
        "read_count": 1,
        "transport_classification": "PASS",
    }


# Standalone validation must not trust bindings copied from the candidate document
# or a mutable crosswalk.  These ID -> path/bytes/SHA tuples are source constants.
EXPECTED_SOURCE_RECEIPTS = deep_freeze(
    [
        _source_receipt("topology_frame_tree", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/unified_r2_digital_prototype_prebind/source_only_v2/UNIFIED_R2_SYSTEM_FRAME_TREE_V2.yaml", 11828, "5F8B19DC5BF14EFBB3C6A781C6816D52FE80804DAB328821623E165239999756"),
        _source_receipt("mass_model", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml", 223714, "3FD2557318E98748A37927977FA2925C18803668FE16391D824C184F646486BB"),
        _source_receipt("limits_interface", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_gripper_velocity_unit_authority/01_interface/GRIPPER_ACTUATION_INTERFACE_CANDIDATE_V1.yaml", 2126, "364D7F2C54B6A77CC80B105EC24F3B7DDEA5FD5648FD7F01E7A2F96BE21A5F51"),
        _source_receipt("collision_gate", "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/02_configurations/M5_BROADPHASE_COLLISION_AUDIT_V1.json", 17130, "DB9029C8626B135F531E5467F1293CA65EDFED7BCB5BAB469CBDAA717AE71BF8"),
        _source_receipt("contact_contract", "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/05_contact_identification/CONTACT_MODEL_PARAMETER_CONTRACT_V1.yaml", 5199, "1BF741A508AA6F263D81458184840F2AD6608652250256CE84D7F2656BD04B6B"),
        _source_receipt("material_selection", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp6_material_selection/DESIGN_MATERIAL_SELECTION_V1.yaml", 25619, "B2973F2A0A95CAF21FE551C5E82388FEEEDCAACE79140A5339DACD5884723220"),
        _source_receipt("full_flex_checkpoint", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/checkpoint_a/R2_FULL_FLEX_GATE_V1.json", 24848, "FC8C9D7BEABF58D19B25CF4A238F12AC255F664F756E7950A942E7E6D3FC1C13"),
        _source_receipt("e22_gate", "30_simulation/e22_r2_full_flex_coupled_diagnostics/results/E22_R2_FULL_FLEX_COUPLED_GATE_V1.json", 9374, "472ADA4A7ABF98BBD5F72B0459400704A86FAF2B13DACCD562025C0CC356AA5E"),
        _source_receipt("e15_gate", "30_simulation/e15_ancf_certification/results/gate_summary.json", 1585, "AAB4D609E219279C2563C8A38743AC1784BBF16DE399D5B8798439B0AC2DCA80"),
        _source_receipt("harness_gate", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/04_mission/B601_HARNESS_MISSION_COVERAGE_GATE.json", 7324, "F3B444222E87509B66F712E623A4903748C7309C6396708EC02A0C1A54CDAA5C"),
        _source_receipt("handoff_gate", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/07_release/MECHANICAL_TO_EMBODIED_HANDOFF_GATE_V2.json", 54345, "13722965D5C558D3439A7CB1E77ABBF3C2094B88E9D62F80D664D0C4C90D4E21"),
        _source_receipt("route_c_checkpoint_b", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/checkpoint_b/ROUTE_C_CHECKPOINT_B_GATE_V1.json", 14887, "C9E7526D790E1FB7F5522A113EDF41F5913207C15A68E12468FD9EBA157349D1"),
        _source_receipt("route_c_cad_gate", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/08_route_c/ROUTE_C_CAD_ENTRY_GATE_V1.json", 2624, "5524EFB209C792DCFECA022C613030E35EAB86ADFFDB8F3CA4D244D6C73E98AE"),
        _source_receipt("current_binding_gate", "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_b601_harness_rated_envelope/09_downstream_rebind/SIM13_CURRENT_MECHANICAL_BINDING_AUDIT_GATE_V1.json", 6345, "7FD3C63AF46BE4BA3055CCF87EFD1A71C13517EC872B1F3EDC52304B070D9153"),
        _source_receipt("target_feasibility_gate", "30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json", 5951, "4DBD8C91FF3455D5E5997A995AC385F02BBC1D2E379BBFE5C0563D41834DFC67"),
    ]
)
EXPECTED_DOMAIN_CLASSIFICATIONS = {
    "topology": "OWNER_REQUIRED",
    "mass": "CANDIDATE_ONLY",
    "limits": "TEST_REQUIRED",
    "collision": "TEST_REQUIRED",
    "contact": "TEST_REQUIRED",
    "material": "CANDIDATE_ONLY",
    "flex": "TEST_REQUIRED",
    "harness": "MISSING",
    "targets": "MISSING",
}
EXPECTED_DOMAINS = deep_freeze(
    {
        "topology": {
            "classification": "OWNER_REQUIRED",
            "presence": True,
            "eligible": False,
            "reason": "The 19-link/18-joint source ledger is present, but no current system URDF or authorized binding exists.",
            "source_artifacts": ["topology_frame_tree", "current_binding_gate"],
        },
        "mass": {
            "classification": "CANDIDATE_ONLY",
            "presence": True,
            "eligible": False,
            "reason": "C01 and nine-configuration values are design-model properties, not as-built metrology or an executed current system model.",
            "source_artifacts": ["mass_model", "topology_frame_tree"],
        },
        "limits": {
            "classification": "TEST_REQUIRED",
            "presence": True,
            "eligible": False,
            "reason": "Kinematic/model limits exist, while physical speed, timing, acceleration, force and latency authority remain null.",
            "source_artifacts": ["limits_interface"],
        },
        "collision": {
            "classification": "TEST_REQUIRED",
            "presence": True,
            "eligible": False,
            "reason": "Only conservative broad-phase evidence exists; authoritative narrow-phase and system collision release are false.",
            "source_artifacts": ["collision_gate"],
        },
        "contact": {
            "classification": "TEST_REQUIRED",
            "presence": True,
            "eligible": False,
            "reason": "Physical contact coefficients, actuator capability, target frames, normals and patch authority remain null/HOLD.",
            "source_artifacts": ["contact_contract", "limits_interface"],
        },
        "material": {
            "classification": "CANDIDATE_ONLY",
            "presence": True,
            "eligible": False,
            "reason": "Six design families are selected with zero flight allowables and zero qualification claims.",
            "source_artifacts": ["material_selection"],
        },
        "flex": {
            "classification": "TEST_REQUIRED",
            "presence": True,
            "eligible": False,
            "reason": "Checkpoint A is 6/12 HOLD, E22 is 16/18 with G11/G17 failed, and e15 requires repeat certification.",
            "source_artifacts": ["full_flex_checkpoint", "e22_gate", "e15_gate"],
        },
        "harness": {
            "classification": "MISSING",
            "presence": True,
            "eligible": False,
            "reason": "G12 fails, zero of ten mandatory states are SAFE, zero of eight trajectories are released, and P01-P13 are zero of thirteen available.",
            "source_artifacts": ["harness_gate", "handoff_gate", "route_c_checkpoint_b", "route_c_cad_gate"],
        },
        "targets": {
            "classification": "MISSING",
            "presence": True,
            "eligible": False,
            "reason": "Rigid feasibility anchors exist, but target contact frames, surface normal, patch/area and current-system full-flex authority are absent.",
            "source_artifacts": ["target_feasibility_gate", "contact_contract"],
        },
    }
)


def _frozen_quantity(
    value: int | float | None,
    unit: str,
    frame: str,
    reference_point: str,
    standard_uncertainty: int | float | None,
    distribution: str | None,
    degrees_of_freedom: int | float | str | None,
    correlation: str | None,
    authority: str,
    status: str,
    source_artifact: str,
    source_field: str,
) -> dict[str, Any]:
    return {
        "value": value,
        "unit": unit,
        "frame": frame,
        "reference_point": reference_point,
        "uncertainty": {
            "standard_uncertainty": standard_uncertainty,
            "distribution": distribution,
            "degrees_of_freedom": degrees_of_freedom,
            "correlation": correlation,
        },
        "authority": authority,
        "status": status,
        "source_artifact": source_artifact,
        "source_field": source_field,
    }


EXPECTED_QUANTITY_CONTRACTS = deep_freeze(
    {
        "system_total_links": _frozen_quantity(19, "count", "NOT_APPLICABLE", "SYSTEM_GRAPH", 0, "EXACT_COUNT", "INFINITE", "NOT_APPLICABLE", "UNIFIED_R2_STATIC_SOURCE_LEDGER", "CANDIDATE_ONLY", "topology_frame_tree", "mode_topology.EXPLICIT_STRUCTURE_PLUS_RESIDUAL.total_links"),
        "system_total_joints": _frozen_quantity(18, "count", "NOT_APPLICABLE", "SYSTEM_GRAPH", 0, "EXACT_COUNT", "INFINITE", "NOT_APPLICABLE", "UNIFIED_R2_STATIC_SOURCE_LEDGER", "CANDIDATE_ONLY", "topology_frame_tree", "mode_topology.EXPLICIT_STRUCTURE_PLUS_RESIDUAL.joints"),
        "c01_design_mass": _frozen_quantity(31.022864807342987, "kg", "S", "SYSTEM_CENTER_OF_MASS", 4.594921657121637, "DECLARED_MODEL_STANDARD_UNCERTAINTY", None, "DECLARED_POLICY__NO_CORRELATION_INVENTED", "SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2__NOT_AS_BUILT", "CANDIDATE_ONLY", "mass_model", "configurations[C01].mass"),
        "gripper_urdf_model_velocity_literal": _frozen_quantity(15.0, "m/s", "GRIPPER_PARENT_JOINT_FRAME", "PRISMATIC_COORDINATE", None, None, None, None, "URDF_MODEL_LITERAL_ONLY__NOT_HARDWARE_RATING", "CANDIDATE_ONLY", "limits_interface", "model_layer.urdf_velocity_limit_literal_m_s"),
        "gripper_physical_rated_speed": _frozen_quantity(None, "m/s", "GRIPPER_PARENT_JOINT_FRAME", "PRISMATIC_COORDINATE", None, None, None, None, "HARDWARE_TEST_AUTHORITY_ABSENT", "TEST_REQUIRED", "limits_interface", "physical_actuator_layer.rated_speed_m_s"),
        "contact_normal_stiffness": _frozen_quantity(None, "N/m", "CONTACT_NORMAL_FRAME_UNAVAILABLE", "TARGET_CONTACT_POINT_UNAVAILABLE", None, None, None, None, "CT01_CT05_TEST_AUTHORITY_ABSENT", "TEST_REQUIRED", "contact_contract", "normal_contact.normal_stiffness_N_per_m.estimate"),
        "target_contact_effective_area": _frozen_quantity(None, "m^2", "TARGET_SURFACE_FRAME_UNAVAILABLE", "TARGET_CONTACT_PATCH_UNAVAILABLE", None, None, None, None, "AUTHORITATIVE_TARGET_GEOMETRY_ABSENT", "MISSING", "contact_contract", "contact_geometry.effective_area_m2.estimate"),
        "material_al7075_design_density": _frozen_quantity(2800.0, "kg/m^3", "MATERIAL_PROPERTY", "AL7075_T651_DESIGN_BASELINE", None, None, None, None, "DESIGN_SELECTION_TYPICAL_VALUE__ZERO_FLIGHT_ALLOWABLES", "CANDIDATE_ONLY", "material_selection", "component_families[M3R_PRIMARY_STRUCTURE_STAGE_A_B].selected_design_baseline.key_candidate_properties.density_kg_m3.value"),
        "full_flex_hf_to_rom_error": _frozen_quantity(3.5058706034330304, "percent", "R2_FLEX_RESPONSE_SPACE", "MAX_CURRENT_RESPONSE_METRIC", 0, "DETERMINISTIC_DIAGNOSTIC", "INFINITE", "NONE", "E22_DIAGNOSTIC__G11_FAILED", "TEST_REQUIRED", "e22_gate", "key_metrics.hf_to_rom_five_mode_max_relative*100"),
        "e15_cross_solver_difference": _frozen_quantity(5.637349419858036, "percent", "E15_CERTIFICATION_COMPARISON_SPACE", "MAX_OF_SIX_COMPARISONS", 0, "DETERMINISTIC_DIAGNOSTIC", "INFINITE", "NONE", "E15_REPEATED_CERTIFICATION_REQUIRED", "TEST_REQUIRED", "e15_gate", "cross_solver_diagnostic.max_relative_difference*100"),
        "harness_mandatory_safe_states": _frozen_quantity(0, "count", "B601_CONFIGURATION_SPACE", "TEN_MANDATORY_KEY_STATES", 0, "EXACT_GATE_COUNT", "INFINITE", "NOT_APPLICABLE", "B601_HARNESS_MISSION_COVERAGE_GATE_V1", "TEST_REQUIRED", "harness_gate", "key_state_checks[*].pass"),
        "route_c_available_physical_fields": _frozen_quantity(0, "count", "ROUTE_C_INPUT_SPACE", "P01_THROUGH_P13", 0, "EXACT_GATE_COUNT", "INFINITE", "NOT_APPLICABLE", "ROUTE_C_CHECKPOINT_B_GATE_V1", "MISSING", "route_c_checkpoint_b", "physical_registry.status_AVAILABLE"),
        "debris_anchor_post_capture_rate": _frozen_quantity(3.0633304945807067, "deg/s", "SIM10_INERTIAL_RATE_CONVENTION", "DEBRIS_SIM06_ANCHOR", None, None, None, None, "SIM10_RIGID_FEASIBILITY_ONLY__NOT_CURRENT_SYSTEM_BINDING", "CANDIDATE_ONLY", "target_feasibility_gate", "gates.X1_anchors_vs_sim06.checks[debris_sim06].w_plus_dps"),
        "satellite_anchor_post_capture_rate": _frozen_quantity(1.3872061825379134, "deg/s", "SIM10_INERTIAL_RATE_CONVENTION", "SATELLITE_SIM06_ANCHOR", None, None, None, None, "SIM10_RIGID_FEASIBILITY_ONLY__NOT_CURRENT_SYSTEM_BINDING", "CANDIDATE_ONLY", "target_feasibility_gate", "gates.X1_anchors_vs_sim06.checks[satellite_sim06].w_plus_dps"),
    }
)
EXPECTED_CHECKS = {
    "crosswalk_declares_one_read_bytes_sha_parser",
    "all_15_sources_bound_once",
    "nine_domains_exact",
    "topology_source_only_19_18_16_3_8",
    "mass_single_mode_and_c01_values_pinned",
    "limits_keep_model_and_hardware_separate",
    "collision_is_broadphase_only",
    "contact_unknowns_remain_null",
    "materials_are_design_only",
    "full_flex_checkpoint_6_of_12_hold",
    "e22_16_of_18_g11_g17_fail",
    "e15_repeat_5p637349pct_gt_5pct",
    "harness_zero_of_ten_safe_zero_of_eight_released",
    "handoff_g12_fail_11_of_12",
    "route_c_p01_p13_zero_of_13_available",
    "route_c_cad_and_owner_authority_absent",
    "current_sim13_binding_invalidated",
    "target_rigid_feasibility_anchors_are_not_system_handoff",
    "required_system_artifacts_absent",
}
EXPECTED_ROUTE_C_DISPOSITION = deep_freeze(
    {
        "selection": None,
        "allowed_values": ["INCLUDED", "EXCLUDED_RESEARCH_CANDIDATE"],
        "status": "OWNER_REQUIRED",
        "auto_accepted": False,
    }
)
EXPECTED_PROMOTION_SEQUENCE = deep_freeze(
    [
        {"ordinal": index + 1, "stage": stage, "state": "HOLD_NOT_EXECUTED", "self_authorized": False}
        for index, stage in enumerate(PROMOTION_STAGES)
    ]
)
EXPECTED_HARD_NEGATIVES = deep_freeze(
    {
        "e15": {
            "status": "REPEAT_ANCF_CERTIFICATION",
            "max_cross_solver_relative_difference": 0.05637349419858036,
            "gate_limit": 0.05,
            "comparison": "5.637349419858036_PERCENT_GT_5_PERCENT",
        },
        "full_flex_checkpoint_a": {"status": "HOLD", "passed": 6, "total": 12},
        "e22": {"status": "HOLD_R2_HF_TO_ROM_DYNAMIC_VALIDATION_FAILED", "passed": 16, "total": 18, "failed": ["G11", "G17"]},
        "harness": {
            "handoff_g12": "FAIL",
            "handoff_passed": 11,
            "handoff_total": 12,
            "safe_key_states": 0,
            "required_key_states": 10,
            "released_trajectories": 0,
            "required_trajectories": 8,
        },
        "route_c_physical_registry": {
            "available": 0,
            "non_null": 0,
            "hold": 13,
            "total": 13,
            "route_b_seed_inheritance_allowed": False,
        },
        "current_binding": "INVALIDATED_BY_NEWER_M7_EVIDENCE",
    }
)
# This literal is replaced only when the source-owned canonical intake binding is
# deliberately revised and all evidence is re-frozen.  Recomputing a digest inside
# an attacker-controlled document cannot change this source constant.
FROZEN_BINDING_DIGEST = "D6CC48E6EEF2112AC9CA4E1C2F0D97D59D9FF2B64880DC44DF95109CD6A01F33"
HEX64 = re.compile(r"^[0-9A-F]{64}$")
NONCE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{15,127}$")


def _finite_number(value: Any, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise IntakeError("MALFORMED", f"{context} must be finite numeric and not bool")
    return float(value)


def validate_quantity(quantity_id: str, value: Any) -> None:
    item = require_exact_keys(value, QUANTITY_KEYS, f"quantity {quantity_id}")
    for key in ("unit", "frame", "reference_point", "authority", "status", "source_artifact", "source_field"):
        if not isinstance(item[key], str) or not item[key]:
            raise IntakeError("MALFORMED", f"quantity {quantity_id}.{key} must be non-empty")
    if item["status"] not in CLASSIFICATIONS:
        raise IntakeError("MALFORMED", f"quantity {quantity_id} has invalid status")
    if quantity_id not in EXPECTED_UNITS or item["unit"] != EXPECTED_UNITS[quantity_id]:
        raise IntakeError("MALFORMED", f"quantity {quantity_id} unit is not the frozen SI/display contract")
    uncertainty = require_exact_keys(item["uncertainty"], UNCERTAINTY_KEYS, f"quantity {quantity_id}.uncertainty")
    estimate = item["value"]
    standard = uncertainty["standard_uncertainty"]
    if estimate is None:
        if standard is not None:
            raise IntakeError("MALFORMED", f"unknown quantity {quantity_id} cannot have numeric uncertainty")
        if item["status"] == "PASS":
            raise IntakeError("MISSING", f"unknown quantity {quantity_id} cannot be PASS")
    else:
        _finite_number(estimate, f"quantity {quantity_id}.value")
        if standard is not None and _finite_number(standard, f"quantity {quantity_id}.standard_uncertainty") < 0:
            raise IntakeError("MALFORMED", "standard uncertainty cannot be negative")
    for key in ("distribution", "correlation"):
        if uncertainty[key] is not None and (not isinstance(uncertainty[key], str) or not uncertainty[key]):
            raise IntakeError("MALFORMED", f"quantity {quantity_id}.{key} invalid")
    dof = uncertainty["degrees_of_freedom"]
    if dof is not None and dof != "INFINITE":
        if _finite_number(dof, f"quantity {quantity_id}.degrees_of_freedom") < 1:
            raise IntakeError("MALFORMED", "degrees of freedom must be >=1 or INFINITE")
    if item["status"] == "PASS" and (
        standard is None
        or uncertainty["distribution"] is None
        or dof is None
        or uncertainty["correlation"] is None
    ):
        raise IntakeError("MALFORMED", f"PASS quantity {quantity_id} lacks full uncertainty semantics")
    if quantity_id in ZERO_FILL_FORBIDDEN_IDS and estimate is not None:
        raise IntakeError("TEST_REQUIRED", f"unknown physical field {quantity_id} may not be zero-filled or estimated")
    if quantity_id == "gripper_urdf_model_velocity_literal":
        if item["authority"] != "URDF_MODEL_LITERAL_ONLY__NOT_HARDWARE_RATING" or item["status"] == "PASS":
            raise IntakeError("TEST_REQUIRED", "URDF velocity literal cannot become physical speed authority")


_RECEIPT_KEYS = {
    "schema",
    "artifact_id",
    "action_digest",
    "context_digest",
    "issued_at_utc",
    "expires_at_utc",
    "nonce",
    "generation",
    "authority",
    "decision",
}


def _utc_z(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise IntakeError("MALFORMED", f"{label} must use UTC Z notation")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise IntakeError("MALFORMED", f"invalid {label}") from exc
    if parsed.tzinfo != timezone.utc:
        raise IntakeError("MALFORMED", f"{label} must be UTC")
    return parsed


def validate_promotion_receipt(
    receipt: Any,
    *,
    now: datetime,
    expected_action_digest: str,
    expected_context_digest: str,
    replay_ledger: MutableSet[str],
) -> None:
    """Validate freshness/binding syntax only; this is not signature verification.

    A successful return is merely an in-memory preflight result. This source-freeze
    has no persistent or cross-process replay ledger, trust root, signature verifier,
    or authority to turn it into Owner approval.
    """
    item = require_exact_keys(receipt, _RECEIPT_KEYS, "promotion receipt")
    if item["schema"] != "CURRENT_SYSTEM_PROMOTION_AUTHORITY_RECEIPT_V1":
        raise IntakeError("MALFORMED", "promotion receipt schema mismatch")
    if item["artifact_id"] != PROMOTION_RECEIPT_ARTIFACT_ID:
        raise IntakeError("OWNER_REQUIRED", "promotion receipt artifact_id mismatch")
    if item["authority"] != "OWNER_EXTERNAL_AUTHORITY" or item["decision"] != "ALLOW_SINGLE_USE":
        raise IntakeError("OWNER_REQUIRED", "receipt does not carry external Owner authority")
    for field, expected in (("action_digest", expected_action_digest), ("context_digest", expected_context_digest)):
        if not isinstance(item[field], str) or HEX64.fullmatch(item[field]) is None or item[field] != expected:
            raise IntakeError("OWNER_REQUIRED", f"receipt {field} mismatch")
    if isinstance(item["generation"], bool) or not isinstance(item["generation"], int) or item["generation"] < 1:
        raise IntakeError("MALFORMED", "receipt generation must be a positive integer")
    nonce = item["nonce"]
    if not isinstance(nonce, str) or NONCE_RE.fullmatch(nonce) is None:
        raise IntakeError("MALFORMED", "receipt nonce format invalid")
    issued = _utc_z(item["issued_at_utc"], "issued_at_utc")
    expires = _utc_z(item["expires_at_utc"], "expires_at_utc")
    if now.tzinfo is None:
        raise IntakeError("MALFORMED", "validation clock must be timezone-aware")
    now_utc = now.astimezone(timezone.utc)
    if expires <= issued or (expires - issued).total_seconds() > 900:
        raise IntakeError("MALFORMED", "receipt lifetime must be (0,900] seconds")
    if now_utc < issued or now_utc > expires:
        raise IntakeError("OWNER_REQUIRED", "receipt is not currently valid")
    if nonce in replay_ledger:
        raise IntakeError("OWNER_REQUIRED", "receipt nonce replay detected")
    replay_ledger.add(nonce)


def route_c_auto_accept(disposition: Any) -> bool:
    item = require_exact_keys(
        disposition,
        {"schema", "disposition", "owner_receipt_digest", "auto_accepted"},
        "Route-C disposition",
    )
    if item["schema"] != "ROUTE_C_DISPOSITION_V1":
        raise IntakeError("MALFORMED", "Route-C disposition schema mismatch")
    if item["disposition"] not in ("INCLUDED", "EXCLUDED_RESEARCH_CANDIDATE"):
        raise IntakeError("MALFORMED", "Route-C disposition must use the exact binary enum")
    if item["auto_accepted"] is not False:
        raise IntakeError("OWNER_REQUIRED", "neither Route-C disposition may be auto-accepted")
    digest = item["owner_receipt_digest"]
    if digest is not None and (not isinstance(digest, str) or HEX64.fullmatch(digest) is None):
        raise IntakeError("MALFORMED", "Route-C receipt digest invalid")
    raise IntakeError("OWNER_REQUIRED", "Route-C disposition requires a separate current external receipt")


def validate_mass_mode(mode: Any) -> None:
    if mode != "EXPLICIT_STRUCTURE_PLUS_RESIDUAL":
        raise IntakeError("MALFORMED", "exactly one selected mass mode is required; aggregate or dual mode rejected")


def validate_promotion_sequence(sequence: Any) -> None:
    if not isinstance(sequence, list) or [item.get("stage") for item in sequence if isinstance(item, Mapping)] != list(PROMOTION_STAGES):
        raise IntakeError("MALFORMED", "promotion sequence order differs from frozen contract")
    for index, raw in enumerate(sequence):
        item = require_exact_keys(raw, {"ordinal", "stage", "state", "self_authorized"}, "promotion stage")
        if item["ordinal"] != index + 1 or item["state"] != "HOLD_NOT_EXECUTED" or item["self_authorized"] is not False:
            raise IntakeError("OWNER_REQUIRED", "source-freeze may not execute or self-authorize promotion stages")


_INTAKE_KEYS = {
    "schema",
    "artifact_id",
    "scope",
    "current_intake_status",
    "theoretical_ceiling",
    "gate_ceiling",
    "classification_enum",
    "mass_mode",
    "required_absent_paths",
    "source_receipts",
    "domains",
    "physical_quantities",
    "route_c_disposition",
    "promotion_sequence",
    "preserved_hard_negatives",
    "checks",
    "flags",
    "source_only_validation_pass",
    "frozen_binding_digest",
}


def compute_frozen_binding_digest(document: Mapping[str, Any]) -> str:
    """Digest every frozen intake field except the digest field itself."""

    projection = {key: value for key, value in document.items() if key != "frozen_binding_digest"}
    if set(projection) != _INTAKE_KEYS - {"frozen_binding_digest"}:
        raise IntakeError("MALFORMED", "binding digest projection key set differs")
    reject_nonfinite(projection)
    payload = json.dumps(
        projection,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def validate_intake_document(document: Any) -> None:
    item = require_exact_keys(document, _INTAKE_KEYS, "CURRENT_SYSTEM_HANDOFF_INTAKE_V1")
    if item["schema"] != "CURRENT_SYSTEM_HANDOFF_INTAKE_V1":
        raise IntakeError("MALFORMED", "intake schema mismatch")
    if item["artifact_id"] != "SIM13_CURRENT_SYSTEM_HANDOFF_INTAKE_V1":
        raise IntakeError("MALFORMED", "intake artifact_id mismatch")
    if item["scope"] != "SOURCE_ONLY_TRANSACTIONAL_INTAKE__NO_URDF_EXECUTION_NO_CAD_NO_PHYSICS":
        raise IntakeError("OWNER_REQUIRED", "intake scope was broadened")
    if item["current_intake_status"] != "HOLD_INCOMPLETE":
        raise IntakeError("OWNER_REQUIRED", "current intake must remain HOLD_INCOMPLETE")
    if item["theoretical_ceiling"] != "INTAKE_COMPLETE_PENDING_AUTHORIZED_EXECUTION":
        raise IntakeError("MALFORMED", "theoretical ceiling mismatch")
    if item["gate_ceiling"] != "PASS_SOURCE_FREEZE_ONLY":
        raise IntakeError("OWNER_REQUIRED", "gate ceiling exceeds source freeze")
    if tuple(item["classification_enum"]) != CLASSIFICATIONS:
        raise IntakeError("MALFORMED", "classification enum mismatch")
    validate_mass_mode(item["mass_mode"])
    absent_paths = item["required_absent_paths"]
    if not isinstance(absent_paths, list) or tuple(absent_paths) != REQUIRED_ABSENT_PATHS:
        raise IntakeError("OWNER_REQUIRED", "required absent paths differ from the exact system URDF/interface contract")
    for relative_path in absent_paths:
        validate_project_relative_path(relative_path)
    domains = require_exact_keys(item["domains"], set(REQUIRED_DOMAINS), "domains")
    for name in REQUIRED_DOMAINS:
        domain = require_exact_keys(
            domains[name],
            {"classification", "presence", "eligible", "reason", "source_artifacts"},
            f"domain {name}",
        )
        if domain["classification"] not in CLASSIFICATIONS:
            raise IntakeError("MALFORMED", f"domain {name} classification invalid")
        if domain["classification"] != EXPECTED_DOMAIN_CLASSIFICATIONS[name]:
            raise IntakeError("OWNER_REQUIRED", f"domain {name} frozen classification was promoted")
        if not isinstance(domain["presence"], bool) or not isinstance(domain["eligible"], bool):
            raise IntakeError("MALFORMED", f"domain {name} booleans invalid")
        if domain["eligible"] is True and domain["classification"] != "PASS":
            raise IntakeError("MALFORMED", f"domain {name}: eligibility requires PASS")
        if domain["eligible"] is not False:
            raise IntakeError("OWNER_REQUIRED", f"source-only current domain {name} cannot be eligible")
        if not isinstance(domain["reason"], str) or not domain["reason"]:
            raise IntakeError("MALFORMED", f"domain {name} reason missing")
        if not isinstance(domain["source_artifacts"], list) or not domain["source_artifacts"]:
            raise IntakeError("MALFORMED", f"domain {name} source binding missing")
        if len(domain["source_artifacts"]) != len(set(domain["source_artifacts"])):
            raise IntakeError("MALFORMED", f"domain {name} repeats a source binding")
    if not any(domain["presence"] is True and domain["eligible"] is False for domain in domains.values()):
        raise IntakeError("MALFORMED", "presence-versus-eligibility separation is not demonstrated")
    if deep_freeze(dict(domains)) != EXPECTED_DOMAINS:
        raise IntakeError("OWNER_REQUIRED", "domain presence/reason/source lineage differs from the frozen binding")
    quantities = item["physical_quantities"]
    if not isinstance(quantities, Mapping) or not quantities:
        raise IntakeError("MALFORMED", "physical_quantities must be non-empty")
    for quantity_id, quantity in quantities.items():
        validate_quantity(str(quantity_id), quantity)
    if set(quantities) != set(EXPECTED_UNITS):
        raise IntakeError("MALFORMED", "physical quantity set differs from frozen schema")
    if deep_freeze(dict(quantities)) != EXPECTED_QUANTITY_CONTRACTS:
        raise IntakeError("OWNER_REQUIRED", "physical quantity value/authority/status/source binding differs from the frozen contract")
    route_c = require_exact_keys(
        item["route_c_disposition"],
        {"selection", "allowed_values", "status", "auto_accepted"},
        "current Route-C disposition",
    )
    if deep_freeze(dict(route_c)) != EXPECTED_ROUTE_C_DISPOSITION:
        raise IntakeError("OWNER_REQUIRED", "current Route-C state was promoted or altered")
    validate_promotion_sequence(item["promotion_sequence"])
    if deep_freeze(item["promotion_sequence"]) != EXPECTED_PROMOTION_SEQUENCE:
        raise IntakeError("OWNER_REQUIRED", "promotion sequence differs from its canonical source binding")
    hard = require_exact_keys(
        item["preserved_hard_negatives"],
        {"e15", "full_flex_checkpoint_a", "e22", "harness", "route_c_physical_registry", "current_binding"},
        "preserved hard negatives",
    )
    if hard["e15"] != {
        "status": "REPEAT_ANCF_CERTIFICATION",
        "max_cross_solver_relative_difference": 0.05637349419858036,
        "gate_limit": 0.05,
        "comparison": "5.637349419858036_PERCENT_GT_5_PERCENT",
    }:
        raise IntakeError("MALFORMED", "e15 hard negative changed")
    if hard["full_flex_checkpoint_a"] != {"status": "HOLD", "passed": 6, "total": 12}:
        raise IntakeError("MALFORMED", "Checkpoint-A hard negative changed")
    if hard["e22"] != {"status": "HOLD_R2_HF_TO_ROM_DYNAMIC_VALIDATION_FAILED", "passed": 16, "total": 18, "failed": ["G11", "G17"]}:
        raise IntakeError("MALFORMED", "E22 hard negative changed")
    if hard["harness"] != {
        "handoff_g12": "FAIL",
        "handoff_passed": 11,
        "handoff_total": 12,
        "safe_key_states": 0,
        "required_key_states": 10,
        "released_trajectories": 0,
        "required_trajectories": 8,
    }:
        raise IntakeError("MALFORMED", "harness G12 hard negative changed")
    if hard["route_c_physical_registry"] != {
        "available": 0,
        "non_null": 0,
        "hold": 13,
        "total": 13,
        "route_b_seed_inheritance_allowed": False,
    }:
        raise IntakeError("MALFORMED", "Route-C P01-P13 hard negative changed")
    if hard["current_binding"] != "INVALIDATED_BY_NEWER_M7_EVIDENCE":
        raise IntakeError("OWNER_REQUIRED", "current binding invalidation was removed")
    if deep_freeze(dict(hard)) != EXPECTED_HARD_NEGATIVES:
        raise IntakeError("OWNER_REQUIRED", "preserved hard-negative bundle differs from the frozen source binding")
    receipts = item["source_receipts"]
    if not isinstance(receipts, list) or len(receipts) != 15:
        raise IntakeError("MALFORMED", "exactly 15 source receipts are required")
    receipt_ids: list[str] = []
    receipt_paths: list[str] = []
    for receipt in receipts:
        source = require_exact_keys(
            receipt,
            {"artifact_id", "path", "bytes", "sha256", "read_count", "transport_classification"},
            "source receipt",
        )
        if source["read_count"] != 1 or source["transport_classification"] != "PASS":
            raise IntakeError("MALFORMED", "source receipt does not prove one-read PASS")
        if not isinstance(source["artifact_id"], str) or not source["artifact_id"]:
            raise IntakeError("MALFORMED", "source receipt artifact_id invalid")
        validate_project_relative_path(source["path"])
        if isinstance(source["bytes"], bool) or not isinstance(source["bytes"], int) or source["bytes"] <= 0:
            raise IntakeError("MALFORMED", "source receipt byte count invalid")
        if not isinstance(source["sha256"], str) or HEX64.fullmatch(source["sha256"]) is None:
            raise IntakeError("MALFORMED", "source receipt SHA-256 invalid")
        receipt_ids.append(source["artifact_id"])
        receipt_paths.append(source["path"])
    if tuple(receipt_ids) != EXPECTED_SOURCE_IDS or len(set(receipt_ids)) != 15 or len(set(receipt_paths)) != 15:
        raise IntakeError("MALFORMED", "source receipt ID/path set or order differs from the frozen crosswalk")
    if deep_freeze(receipts) != EXPECTED_SOURCE_RECEIPTS:
        raise IntakeError("HASH_DRIFT", "source receipt ID-to-path/bytes/SHA binding differs from source constants")
    source_id_set = set(receipt_ids)
    for name, domain in domains.items():
        if any(source_id not in source_id_set for source_id in domain["source_artifacts"]):
            raise IntakeError("MALFORMED", f"domain {name} cross-references an unreceipted source")
    for quantity_id, quantity in quantities.items():
        if quantity["source_artifact"] not in source_id_set:
            raise IntakeError("MALFORMED", f"quantity {quantity_id} cross-references an unreceipted source")
    checks = require_exact_keys(item["checks"], EXPECTED_CHECKS, "intake checks")
    if any(value is not True for value in checks.values()):
        raise IntakeError("MALFORMED", "all frozen intake checks must be exact true")
    flags = require_exact_keys(item["flags"], set(MANDATORY_FALSE), "mandatory flags")
    if any(flags[name] is not False for name in MANDATORY_FALSE):
        raise IntakeError("OWNER_REQUIRED", "one or more mandatory-false flags were promoted")
    if item["source_only_validation_pass"] is not True:
        raise IntakeError("MALFORMED", "source-only validation must be exact true")
    digest = item["frozen_binding_digest"]
    calculated_digest = compute_frozen_binding_digest(item)
    if not isinstance(digest, str) or HEX64.fullmatch(digest) is None:
        raise IntakeError("MALFORMED", "frozen binding digest must be uppercase SHA-256")
    if digest != calculated_digest or digest != FROZEN_BINDING_DIGEST:
        raise IntakeError("HASH_DRIFT", "canonical frozen binding digest mismatch")
