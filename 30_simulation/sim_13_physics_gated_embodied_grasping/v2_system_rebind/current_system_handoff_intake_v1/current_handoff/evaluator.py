"""Reconstruct the current handoff intake without executing any model generator."""

from __future__ import annotations

import math
from typing import Any, Mapping

from .schema import (
    CLASSIFICATIONS,
    EXPECTED_DOMAIN_CLASSIFICATIONS,
    MANDATORY_FALSE,
    PROMOTION_STAGES,
    REQUIRED_ABSENT_PATHS,
    REQUIRED_DOMAINS,
    compute_frozen_binding_digest,
    validate_intake_document,
)
from .strict_io import IntakeError, SourceSnapshot, load_default_snapshot, require_exact_keys


GATE_CEILING = "PASS_SOURCE_FREEZE_ONLY"
CURRENT_STATUS = "HOLD_INCOMPLETE"
THEORETICAL_CEILING = "INTAKE_COMPLETE_PENDING_AUTHORIZED_EXECUTION"


def _doc(snapshot: SourceSnapshot, artifact_id: str) -> Mapping[str, Any]:
    artifact = snapshot.artifacts.get(artifact_id)
    if artifact is None or not isinstance(artifact.parsed, Mapping):
        raise IntakeError("MISSING", f"structured source absent: {artifact_id}")
    return artifact.parsed


def _close(value: Any, expected: float, tolerance: float = 1e-12) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and abs(float(value) - expected) <= tolerance
    )


def _quantity(
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


def _build_domains(snapshot: SourceSnapshot) -> dict[str, Any]:
    bindings = snapshot.crosswalk.get("domain_bindings")
    if not isinstance(bindings, (list, tuple)):
        raise IntakeError("MALFORMED", "domain_bindings must be a list")
    domains: dict[str, Any] = {}
    for raw in bindings:
        item = require_exact_keys(raw, {"domain", "artifact_ids", "classification", "reason"}, "domain binding")
        name = item["domain"]
        if name not in REQUIRED_DOMAINS or name in domains:
            raise IntakeError("MALFORMED", f"unknown or duplicate domain: {name}")
        artifact_ids = item["artifact_ids"]
        if not isinstance(artifact_ids, (list, tuple)) or not artifact_ids or not all(isinstance(value, str) for value in artifact_ids):
            raise IntakeError("MALFORMED", f"domain {name} artifact_ids invalid")
        classification = item["classification"]
        if classification not in CLASSIFICATIONS:
            raise IntakeError("MALFORMED", f"domain {name} classification invalid")
        if classification != EXPECTED_DOMAIN_CLASSIFICATIONS[name]:
            raise IntakeError("OWNER_REQUIRED", f"domain {name} crosswalk attempted classification promotion")
        presence = all(artifact_id in snapshot.artifacts for artifact_id in artifact_ids)
        domains[name] = {
            "classification": classification,
            "presence": presence,
            "eligible": False,
            "reason": item["reason"],
            "source_artifacts": list(artifact_ids),
        }
    if tuple(domains) != REQUIRED_DOMAINS:
        raise IntakeError("MALFORMED", "domain crosswalk order/completeness mismatch")
    return domains


def evaluate_snapshot(snapshot: SourceSnapshot) -> dict[str, Any]:
    frame = _doc(snapshot, "topology_frame_tree")
    collision = _doc(snapshot, "collision_gate")
    full_flex = _doc(snapshot, "full_flex_checkpoint")
    e22 = _doc(snapshot, "e22_gate")
    e15 = _doc(snapshot, "e15_gate")
    harness = _doc(snapshot, "harness_gate")
    handoff = _doc(snapshot, "handoff_gate")
    checkpoint_b = _doc(snapshot, "route_c_checkpoint_b")
    route_c_cad = _doc(snapshot, "route_c_cad_gate")
    current_binding = _doc(snapshot, "current_binding_gate")
    target = _doc(snapshot, "target_feasibility_gate")

    frame_text = frame.get("pinned_payload_text", "")
    mass_text = _doc(snapshot, "mass_model").get("pinned_payload_text", "")
    limits_text = _doc(snapshot, "limits_interface").get("pinned_payload_text", "")
    contact_text = _doc(snapshot, "contact_contract").get("pinned_payload_text", "")
    material_text = _doc(snapshot, "material_selection").get("pinned_payload_text", "")

    checks: dict[str, bool] = {
        "crosswalk_declares_one_read_bytes_sha_parser": snapshot.crosswalk.get("source_policy", {}).get("single_read_bytes_sha_parse") is True,
        "all_15_sources_bound_once": len(snapshot.artifacts) == 15 and all(item.read_count == 1 for item in snapshot.artifacts.values()),
        "nine_domains_exact": tuple(snapshot.crosswalk.get("required_domains", ())) == REQUIRED_DOMAINS,
        "topology_source_only_19_18_16_3_8": all(
            token in frame_text
            for token in (
                "urdf_emitted: false",
                "total_links: 19",
                "physical_links: 16",
                "frame_only_links: 3",
                "joints: 18",
                "actuated_dof: 8",
            )
        ),
        "mass_single_mode_and_c01_values_pinned": (
            "selected_mass_mode: EXPLICIT_STRUCTURE_PLUS_RESIDUAL" in frame_text
            and "m7_design_ledger_c01_kg: 31.022864807342987" in mass_text
            and "standard_uncertainty_kg: 4.594921657121637" in mass_text
        ),
        "limits_keep_model_and_hardware_separate": (
            "urdf_velocity_limit_literal_m_s: 15.0" in limits_text
            and "role: MODEL_LIMIT_ONLY" in limits_text
            and "rated_speed_m_s: null" in limits_text
        ),
        "collision_is_broadphase_only": collision.get("narrow_phase_available") is False and collision.get("system_collision_release") is False,
        "contact_unknowns_remain_null": (
            "normal_stiffness_N_per_m:" in contact_text
            and "estimate: null" in contact_text
            and "physical_contact_kernel_authorized: false" in contact_text
        ),
        "materials_are_design_only": (
            "DESIGN_SELECTIONS_MADE_6_FAMILIES_ZERO_FLIGHT_ALLOWABLES_ZERO_QUALIFICATION_CLAIMS" in material_text
            and "property_standard_uncertainty_unknown_value: null" in material_text
        ),
        "full_flex_checkpoint_6_of_12_hold": full_flex.get("checkpoint_outcome") == "HOLD" and full_flex.get("summary", {}).get("passed") == 6 and full_flex.get("summary", {}).get("total") == 12,
        "e22_16_of_18_g11_g17_fail": (
            e22.get("summary", {}).get("passed") == 16
            and e22.get("summary", {}).get("total") == 18
            and e22.get("summary", {}).get("failed") == ("G11", "G17")
        ),
        "e15_repeat_5p637349pct_gt_5pct": (
            e15.get("overall") == "REPEAT_ANCF_CERTIFICATION"
            and _close(e15.get("cross_solver_diagnostic", {}).get("max_relative_difference"), 0.05637349419858036)
            and e15.get("cross_solver_diagnostic", {}).get("all_lt_5pct") is False
        ),
        "harness_zero_of_ten_safe_zero_of_eight_released": (
            harness.get("mission_coverage") == "FAIL"
            and len(harness.get("required_states", ())) == 10
            and sum(item.get("pass") is True for item in harness.get("key_state_checks", ())) == 0
            and harness.get("required_trajectory_segments") == 8
            and harness.get("trajectory_segments_with_released_authority") == 0
        ),
        "handoff_g12_fail_11_of_12": (
            handoff.get("verdict") == "MECHANICAL_TO_EMBODIED_HANDOFF_FAIL"
            and handoff.get("checks_passed") == 11
            and handoff.get("checks_total") == 12
            and handoff.get("failing_checks") == ("G12",)
        ),
        "route_c_p01_p13_zero_of_13_available": (
            checkpoint_b.get("physical_registry", {}).get("entries_total") == 13
            and checkpoint_b.get("physical_registry", {}).get("value_non_null") == 0
            and checkpoint_b.get("physical_registry", {}).get("status_AVAILABLE") == 0
            and checkpoint_b.get("physical_registry", {}).get("status_HOLD") == 13
            and checkpoint_b.get("authority_guards", {}).get("route_b_seed_inheritance_allowed") is False
        ),
        "route_c_cad_and_owner_authority_absent": (
            route_c_cad.get("gate") == "HOLD"
            and route_c_cad.get("cad_artifacts_created_by_this_package") == 0
            and checkpoint_b.get("owner_accepted") is False
            and checkpoint_b.get("next_stage_authorized") is False
        ),
        "current_sim13_binding_invalidated": (
            current_binding.get("verdict") == "CURRENT_SIM13_PRODUCTION_MECHANICAL_BINDING_INVALIDATED_BY_NEWER_M7_EVIDENCE"
            and current_binding.get("current_authority", {}).get("mechanical_release") is False
            and current_binding.get("current_authority", {}).get("production_dynamics_ready") is False
        ),
        "target_rigid_feasibility_anchors_are_not_system_handoff": (
            target.get("verdict") == "SIM10_GATES_PASS"
            and all(gate.get("pass") is True for gate in target.get("gates", {}).values())
            and target.get("flex_status") == "UNKNOWN_NOT_IN_CRITERIA"
        ),
        "required_system_artifacts_absent": snapshot.required_absent_paths == REQUIRED_ABSENT_PATHS,
    }

    quantities = {
        "system_total_links": _quantity(19, "count", "NOT_APPLICABLE", "SYSTEM_GRAPH", 0, "EXACT_COUNT", "INFINITE", "NOT_APPLICABLE", "UNIFIED_R2_STATIC_SOURCE_LEDGER", "CANDIDATE_ONLY", "topology_frame_tree", "mode_topology.EXPLICIT_STRUCTURE_PLUS_RESIDUAL.total_links"),
        "system_total_joints": _quantity(18, "count", "NOT_APPLICABLE", "SYSTEM_GRAPH", 0, "EXACT_COUNT", "INFINITE", "NOT_APPLICABLE", "UNIFIED_R2_STATIC_SOURCE_LEDGER", "CANDIDATE_ONLY", "topology_frame_tree", "mode_topology.EXPLICIT_STRUCTURE_PLUS_RESIDUAL.joints"),
        "c01_design_mass": _quantity(31.022864807342987, "kg", "S", "SYSTEM_CENTER_OF_MASS", 4.594921657121637, "DECLARED_MODEL_STANDARD_UNCERTAINTY", None, "DECLARED_POLICY__NO_CORRELATION_INVENTED", "SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2__NOT_AS_BUILT", "CANDIDATE_ONLY", "mass_model", "configurations[C01].mass"),
        "gripper_urdf_model_velocity_literal": _quantity(15.0, "m/s", "GRIPPER_PARENT_JOINT_FRAME", "PRISMATIC_COORDINATE", None, None, None, None, "URDF_MODEL_LITERAL_ONLY__NOT_HARDWARE_RATING", "CANDIDATE_ONLY", "limits_interface", "model_layer.urdf_velocity_limit_literal_m_s"),
        "gripper_physical_rated_speed": _quantity(None, "m/s", "GRIPPER_PARENT_JOINT_FRAME", "PRISMATIC_COORDINATE", None, None, None, None, "HARDWARE_TEST_AUTHORITY_ABSENT", "TEST_REQUIRED", "limits_interface", "physical_actuator_layer.rated_speed_m_s"),
        "contact_normal_stiffness": _quantity(None, "N/m", "CONTACT_NORMAL_FRAME_UNAVAILABLE", "TARGET_CONTACT_POINT_UNAVAILABLE", None, None, None, None, "CT01_CT05_TEST_AUTHORITY_ABSENT", "TEST_REQUIRED", "contact_contract", "normal_contact.normal_stiffness_N_per_m.estimate"),
        "target_contact_effective_area": _quantity(None, "m^2", "TARGET_SURFACE_FRAME_UNAVAILABLE", "TARGET_CONTACT_PATCH_UNAVAILABLE", None, None, None, None, "AUTHORITATIVE_TARGET_GEOMETRY_ABSENT", "MISSING", "contact_contract", "contact_geometry.effective_area_m2.estimate"),
        "material_al7075_design_density": _quantity(2800.0, "kg/m^3", "MATERIAL_PROPERTY", "AL7075_T651_DESIGN_BASELINE", None, None, None, None, "DESIGN_SELECTION_TYPICAL_VALUE__ZERO_FLIGHT_ALLOWABLES", "CANDIDATE_ONLY", "material_selection", "component_families[M3R_PRIMARY_STRUCTURE_STAGE_A_B].selected_design_baseline.key_candidate_properties.density_kg_m3.value"),
        "full_flex_hf_to_rom_error": _quantity(3.5058706034330304, "percent", "R2_FLEX_RESPONSE_SPACE", "MAX_CURRENT_RESPONSE_METRIC", 0, "DETERMINISTIC_DIAGNOSTIC", "INFINITE", "NONE", "E22_DIAGNOSTIC__G11_FAILED", "TEST_REQUIRED", "e22_gate", "key_metrics.hf_to_rom_five_mode_max_relative*100"),
        "e15_cross_solver_difference": _quantity(5.637349419858036, "percent", "E15_CERTIFICATION_COMPARISON_SPACE", "MAX_OF_SIX_COMPARISONS", 0, "DETERMINISTIC_DIAGNOSTIC", "INFINITE", "NONE", "E15_REPEATED_CERTIFICATION_REQUIRED", "TEST_REQUIRED", "e15_gate", "cross_solver_diagnostic.max_relative_difference*100"),
        "harness_mandatory_safe_states": _quantity(0, "count", "B601_CONFIGURATION_SPACE", "TEN_MANDATORY_KEY_STATES", 0, "EXACT_GATE_COUNT", "INFINITE", "NOT_APPLICABLE", "B601_HARNESS_MISSION_COVERAGE_GATE_V1", "TEST_REQUIRED", "harness_gate", "key_state_checks[*].pass"),
        "route_c_available_physical_fields": _quantity(0, "count", "ROUTE_C_INPUT_SPACE", "P01_THROUGH_P13", 0, "EXACT_GATE_COUNT", "INFINITE", "NOT_APPLICABLE", "ROUTE_C_CHECKPOINT_B_GATE_V1", "MISSING", "route_c_checkpoint_b", "physical_registry.status_AVAILABLE"),
        "debris_anchor_post_capture_rate": _quantity(3.0633304945807067, "deg/s", "SIM10_INERTIAL_RATE_CONVENTION", "DEBRIS_SIM06_ANCHOR", None, None, None, None, "SIM10_RIGID_FEASIBILITY_ONLY__NOT_CURRENT_SYSTEM_BINDING", "CANDIDATE_ONLY", "target_feasibility_gate", "gates.X1_anchors_vs_sim06.checks[debris_sim06].w_plus_dps"),
        "satellite_anchor_post_capture_rate": _quantity(1.3872061825379134, "deg/s", "SIM10_INERTIAL_RATE_CONVENTION", "SATELLITE_SIM06_ANCHOR", None, None, None, None, "SIM10_RIGID_FEASIBILITY_ONLY__NOT_CURRENT_SYSTEM_BINDING", "CANDIDATE_ONLY", "target_feasibility_gate", "gates.X1_anchors_vs_sim06.checks[satellite_sim06].w_plus_dps"),
    }

    source_receipts = [
        {
            "artifact_id": artifact_id,
            "path": artifact.relative_path,
            "bytes": artifact.byte_count,
            "sha256": artifact.sha256,
            "read_count": artifact.read_count,
            "transport_classification": "PASS",
        }
        for artifact_id, artifact in snapshot.artifacts.items()
    ]
    promotion_sequence = [
        {"ordinal": index + 1, "stage": stage, "state": "HOLD_NOT_EXECUTED", "self_authorized": False}
        for index, stage in enumerate(PROMOTION_STAGES)
    ]
    hard_negatives = {
        "e15": {
            "status": "REPEAT_ANCF_CERTIFICATION",
            "max_cross_solver_relative_difference": 0.05637349419858036,
            "gate_limit": 0.05,
            "comparison": "5.637349419858036_PERCENT_GT_5_PERCENT",
        },
        "full_flex_checkpoint_a": {"status": "HOLD", "passed": 6, "total": 12},
        "e22": {"status": "HOLD_R2_HF_TO_ROM_DYNAMIC_VALIDATION_FAILED", "passed": 16, "total": 18, "failed": ["G11", "G17"]},
        "harness": {"handoff_g12": "FAIL", "handoff_passed": 11, "handoff_total": 12, "safe_key_states": 0, "required_key_states": 10, "released_trajectories": 0, "required_trajectories": 8},
        "route_c_physical_registry": {"available": 0, "non_null": 0, "hold": 13, "total": 13, "route_b_seed_inheritance_allowed": False},
        "current_binding": "INVALIDATED_BY_NEWER_M7_EVIDENCE",
    }
    document = {
        "schema": "CURRENT_SYSTEM_HANDOFF_INTAKE_V1",
        "artifact_id": "SIM13_CURRENT_SYSTEM_HANDOFF_INTAKE_V1",
        "scope": "SOURCE_ONLY_TRANSACTIONAL_INTAKE__NO_URDF_EXECUTION_NO_CAD_NO_PHYSICS",
        "current_intake_status": CURRENT_STATUS,
        "theoretical_ceiling": THEORETICAL_CEILING,
        "gate_ceiling": GATE_CEILING,
        "classification_enum": list(CLASSIFICATIONS),
        "mass_mode": "EXPLICIT_STRUCTURE_PLUS_RESIDUAL",
        "required_absent_paths": list(REQUIRED_ABSENT_PATHS),
        "source_receipts": source_receipts,
        "domains": _build_domains(snapshot),
        "physical_quantities": quantities,
        "route_c_disposition": {
            "selection": None,
            "allowed_values": ["INCLUDED", "EXCLUDED_RESEARCH_CANDIDATE"],
            "status": "OWNER_REQUIRED",
            "auto_accepted": False,
        },
        "promotion_sequence": promotion_sequence,
        "preserved_hard_negatives": hard_negatives,
        "checks": checks,
        "flags": {name: False for name in MANDATORY_FALSE},
        "source_only_validation_pass": bool(checks) and all(checks.values()),
    }
    document["frozen_binding_digest"] = compute_frozen_binding_digest(document)
    validate_intake_document(document)
    return document


def evaluate_default_snapshot() -> dict[str, Any]:
    return evaluate_snapshot(load_default_snapshot())
