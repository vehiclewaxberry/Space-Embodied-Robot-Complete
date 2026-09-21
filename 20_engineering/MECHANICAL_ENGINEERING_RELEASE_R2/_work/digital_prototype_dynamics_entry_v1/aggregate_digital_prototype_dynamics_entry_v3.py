"""Aggregate bounded R2 DG1--DG5 evidence without promoting parent Gates.

This evaluator is intentionally read-only with respect to every upstream file.
It reconciles newer owner/mount records with older intake ledgers, records only
the fields actually superseded, and leaves CAD, M01, Route-C, contact,
control, Sim13, mechanical release, and flight authority fail-closed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


PACKAGE = Path(__file__).resolve().parent


def workspace_root() -> Path:
    for candidate in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
        if (candidate / "PROJECT_MAP.md").is_file():
            return candidate
    raise RuntimeError("WORKSPACE_ROOT_NOT_FOUND")


ROOT = workspace_root()
OUTPUT = PACKAGE / "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V3.json"
MANIFEST = PACKAGE / "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_MANIFEST_V3.json"
SOURCE_PINS = {
    "entry_gate_v2": {
        "path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/digital_prototype_dynamics_entry_v1/CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V2.json",
        "bytes": 6259,
        "sha256": "551B291F4672ADB5B288C2718B6E46CCE76420216022896D24A49F1B1994ED4C",
    },
    "dg3_candidate_gate": {
        "path": "30_simulation/r2_dynamics_engineering_closure/dg3_arm_flex_coupling_candidate_v1/results/R2_DG3_ARM_FLEX_COUPLING_CANDIDATE_GATE_V1.json",
        "bytes": 2916,
        "sha256": "91BB7F3B424CF454DB5B2B4DFC27455AD46C4E6C5614F20D6A3C6EBB4714B7C3",
    },
    "dg4_candidate_gate": {
        "path": "30_simulation/r2_dynamics_engineering_closure/dg4_contact_hybrid_candidate_v1/results/DG4_CONTACT_HYBRID_GATE_V1.json",
        "bytes": 12193,
        "sha256": "1A77205ECED29D36C72F7C8A209001AC24EB11DF580FC4554C565FDB571EF08A",
    },
    "dg5_candidate_gate": {
        "path": "30_simulation/r2_dynamics_engineering_closure/dg5_uncertainty_candidate_v1/results/R2_DG5_DESIGN_UNCERTAINTY_CANDIDATE_GATE_V1.json",
        "bytes": 2161,
        "sha256": "6AF594F9C01F65B52B2D176EFE4366E29D8DD3EAD37C54C70EE5EC7002327DB5",
    },
    "parent_dynamics_gate": {
        "path": "30_simulation/r2_dynamics_engineering_closure/results/R2_DYNAMICS_ENGINEERING_GATE_V1.json",
        "bytes": 5694,
        "sha256": "C847DD680814864E8095223A42E4E4D53B903C6F6371E3DC47BAFEBAF478EB1A",
    },
    "odr60_option_a_execution_gate": {
        "path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/results/ODR60_OPTION_A_EXECUTION_CLOSURE_GATE_V1.json",
        "bytes": 4633,
        "sha256": "869A248050FD39347D5D502F6174E284943901BA9F3C40A2D4337B4B6FF5A01A",
    },
    "odr60_binding_intake_gate": {
        "path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_BINDING_INTAKE_V1/BINDING_INTAKE_GATE_V1.json",
        "bytes": 20629,
        "sha256": "509127D151BE7C60B74C54A12E629C0CC673126DEC5DF158177AED9E72009634",
    },
    "terminal_mechanical_release_gate": {
        "path": "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/00_RELEASE_GATE.json",
        "bytes": 5166,
        "sha256": "14D30FD40AC60253C0716A71BA46950E1DF6B8E69DCE3F12690319B970A48674",
    },
    "control_predevelopment_gate": {
        "path": "30_simulation/control_r2_integrated_candidate/results/CTRL_R2_PREDEVELOPMENT_GATE_V1.json",
        "bytes": 9552,
        "sha256": "ED4D8B7774C61317576DF03B8DDA1591BA1178B895DDC5FA7544EAD9A7E59ABE",
    },
    "parent_control_gate": {
        "path": "30_simulation/r2_control_engineering_closure/results/R2_CONTROL_ENGINEERING_GATE_V1.json",
        "bytes": 3966,
        "sha256": "2740B33E7958B4AF2232ED0A2A51CEA830470D1C98D5BA46C39C43279A02ADCE",
    },
    "joint_dynamics_control_gate": {
        "path": "30_simulation/r2_dynamics_control_system_closure/results/R2_DYNAMICS_CONTROL_SYSTEM_GATE_V1.json",
        "bytes": 4465,
        "sha256": "55490805D934A8806E58CDA25C398BD15AEF49F4624F1F8CC08FCB75F2634B03",
    },
}


class AggregateError(RuntimeError):
    """Raised for malformed or duplicate-key aggregate inputs."""


def _reject_duplicate_key(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AggregateError(f"DUPLICATE_JSON_KEY:{key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_key
    )
    if not isinstance(value, dict):
        raise AggregateError(f"EXPECTED_JSON_OBJECT:{path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def canonical_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def load_sources() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for source_id, pin in SOURCE_PINS.items():
        path = ROOT / pin["path"]
        exists = path.is_file()
        actual_bytes = path.stat().st_size if exists else None
        actual_sha = sha256(path) if exists else None
        match = bool(
            exists
            and actual_bytes == pin["bytes"]
            and actual_sha == pin["sha256"]
        )
        rows.append(
            {
                "id": source_id,
                "path": pin["path"],
                "expected_bytes": pin["bytes"],
                "actual_bytes": actual_bytes,
                "expected_sha256": pin["sha256"],
                "actual_sha256": actual_sha,
                "match": match,
            }
        )
        if match:
            documents[source_id] = load_json(path)
    return documents, {
        "pins": rows,
        "matched": sum(bool(row["match"]) for row in rows),
        "total": len(rows),
        "all_match": all(bool(row["match"]) for row in rows),
    }


def _criterion(gate: Mapping[str, Any], criterion_id: str) -> Mapping[str, Any]:
    rows = [row for row in gate.get("criteria", []) if row.get("id") == criterion_id]
    return rows[0] if len(rows) == 1 else {}


def _tmg(gate: Mapping[str, Any], gate_id: str) -> Mapping[str, Any]:
    rows = [row for row in gate.get("tmg", []) if row.get("id") == gate_id]
    return rows[0] if len(rows) == 1 else {}


def _artifact_record(path: Path, role: str) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "role": role,
    }


def build_manifest() -> dict[str, Any]:
    local = {
        Path(__file__).resolve(): "deterministic aggregate evaluator",
        PACKAGE / "tests" / "test_entry_gate_v3.py": "positive and fail-closed tests",
        PACKAGE / "README.md": "scope, authority boundary and reproduction",
        OUTPUT: "generated V3 aggregate Gate",
    }
    return {
        "schema": "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_MANIFEST_V3",
        "local_artifacts": [
            _artifact_record(path, role) for path, role in local.items()
        ],
        "external_source_pins": SOURCE_PINS,
        "summary": {
            "local_count": len(local),
            "external_pin_count": len(SOURCE_PINS),
            "all_exist": all(path.is_file() for path in local),
        },
        "parent_gates_mutated": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def build_gate() -> dict[str, Any]:
    docs, binding = load_sources()
    if not binding["all_match"]:
        return {
            "schema": "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V3",
            "technical_verdict": "SOURCE_HASH_DRIFT__FAIL_CLOSED",
            "source_binding": binding,
            "checks": {"V3-01_all_11_source_pins_exact": False},
            "summary": {
                "passed": 0,
                "total": 1,
                "failed": ["V3-01_all_11_source_pins_exact"],
            },
            "next_stage_authorized": False,
            "release_credit": False,
        }

    v2 = docs["entry_gate_v2"]
    dg3 = docs["dg3_candidate_gate"]
    dg4 = docs["dg4_candidate_gate"]
    dg5 = docs["dg5_candidate_gate"]
    parent_dynamics = docs["parent_dynamics_gate"]
    odr = docs["odr60_option_a_execution_gate"]
    intake = docs["odr60_binding_intake_gate"]
    mechanical = docs["terminal_mechanical_release_gate"]
    control_pre = docs["control_predevelopment_gate"]
    control = docs["parent_control_gate"]
    joint = docs["joint_dynamics_control_gate"]
    dg4_c08 = _criterion(dg4, "DG4-C08")
    dg4_c15 = _criterion(dg4, "DG4-C15")
    tmg4 = _tmg(mechanical, "TMG-4")
    tmg6 = _tmg(mechanical, "TMG-6")

    checks = {
        "V3-01_all_11_source_pins_exact": True,
        "V3-02_prior_V2_bounded_entry_10_of_10_retained": (
            v2.get("summary") == {"passed": 10, "total": 10, "failed": []}
            and v2.get("next_stage_authorized") is False
            and v2.get("release_credit") is False
        ),
        "V3-03_DG1_DG2_additive_candidates_retained": (
            v2.get("progress_delta", {}).get("dynamics", {}).get("DG1_reference_metric")
            == "PASS_CANDIDATE"
            and v2.get("progress_delta", {}).get("dynamics", {}).get(
                "DG2_nonzero_momentum_full_pose"
            )
            == "PASS_CANDIDATE"
            and v2.get("progress_delta", {}).get("dynamics", {}).get(
                "production_dynamics"
            )
            is False
        ),
        "V3-04_DG3_frozen_C0_candidate_30_of_30_no_parent_credit": (
            dg3.get("summary") == {"passed": 30, "total": 30, "failed": []}
            and dg3.get("candidate_package_complete") is True
            and dg3.get("mixed_28x28_spectral_credit") is False
            and dg3.get("E23_numerical_inheritance") is False
            and dg3.get("parent_DG3_satisfied") is False
            and dg3.get("parent_DG3_complete") is False
        ),
        "V3-05_DG4_two_body_impulse_candidate_15_of_15": (
            dg4.get("criteria_passed") == dg4.get("criteria_total") == 15
            and dg4.get("gate") == "PASS_CANDIDATE_WITH_PHYSICAL_HOLD"
            and dg4.get("design_diagnostic_candidate_complete") is True
            and dg4_c08.get("state") == "PASS"
            and dg4_c08.get("observed", {}).get("terminal_state")
            == "POST_IMPACT_DIAGNOSTIC"
        ),
        "V3-06_DG4_physical_attachment_and_non_abort_remain_false": (
            dg4.get("parent_DG4_satisfied") is False
            and dg4.get("real_attachment_ready") is False
            and dg4.get("physical_contact_ready") is False
            and dg4.get("non_abort_grasp_ready") is False
            and dg4.get("unknown_auto_allow_count") == 0
            and dg4_c15.get("state") == "PASS"
        ),
        "V3-07_DG5_design_screen_16_of_16_without_probability_or_physical_claim": (
            dg5.get("summary") == {"passed": 16, "total": 16, "failed": []}
            and dg5.get("design_uncertainty_candidate_satisfied") is True
            and dg5.get("mass_corner_audit", {}).get("evaluated") == 1024
            and dg5.get("mass_corner_audit", {}).get(
                "basic_rigid_body_constraints_not_falsified"
            )
            == 880
            and dg5.get("mass_corner_audit", {}).get("quarantined") == 144
            and dg5.get("parent_DG5_satisfied") is False
            and dg5.get("as_built_mass_properties") is None
            and dg5.get("contact_uncertainty") is None
            and dg5.get("actuator_uncertainty") is None
        ),
        "V3-08_parent_dynamics_gate_remains_unmodified_HOLD": (
            parent_dynamics.get("summary", {}).get("candidate_satisfied") == 1
            and parent_dynamics.get("summary", {}).get("total") == 6
            and parent_dynamics.get("dynamics_engineering_complete") is False
            and parent_dynamics.get("next_stage_authorized") is False
            and parent_dynamics.get("release_credit") is False
        ),
        "V3-09_owner_Option_A_selected_and_mount_frame_ledger_closed": (
            odr.get("owner_selection_recorded") is True
            and odr.get("owner_authority", {}).get("option_a_selected") is True
            and odr.get("owner_authority", {}).get("option_b_selected") is False
            and odr.get("actual_closures", {}).get(
                "execution_mount_full_precision_spelling_bound"
            )
            is True
            and odr.get("actual_closures", {}).get(
                "accepted_urdf_subtree_collision_frame_rows"
            )
            == 10
            and odr.get("actual_closures", {}).get(
                "accepted_urdf_subtree_collision_frame_rows_required"
            )
            == 10
        ),
        "V3-10_M01_zero_of_nine_fields_and_zero_of_three_instances_preserved": (
            intake.get("checks", {}).get("scene_bound_fields_zero_of_nine") is True
            and intake.get("current_readiness", {}).get(
                "scene_required_binding_count"
            )
            == 9
            and intake.get("current_readiness", {}).get(
                "scene_bound_required_binding_count"
            )
            == 0
            and odr.get("remaining_readiness", {}).get(
                "three_stage_scene_instances_bound"
            )
            == 0
            and odr.get("remaining_readiness", {}).get(
                "three_stage_scene_instances_required"
            )
            == 3
        ),
        "V3-11_collision_motion_oracle_edge_and_search_authority_remain_zero": (
            odr.get("remaining_readiness", {}).get(
                "complete_system_operational_collision_asset_set_bound"
            )
            is False
            and odr.get("remaining_readiness", {}).get("clearance_policy_rows_bound")
            == 0
            and odr.get("remaining_readiness", {}).get("motion_certificates_bound")
            == 0
            and odr.get("remaining_readiness", {}).get("pair_oracle_rows_executed")
            == 0
            and odr.get("execution_record", {}).get("edges_certified") == 0
            and odr.get("pair_evaluation_authorized") is False
            and odr.get("edge_evaluation_authorized") is False
            and odr.get("path_search_authorized") is False
            and odr.get("path_search_executed") is False
        ),
        "V3-12_runtime_memory_admission_and_low_memory_override_remain_false": (
            odr.get("authority", {}).get("runtime_memory_admission_pass") is False
            and odr.get("owner_authority", {}).get("low_memory_override_authorized")
            is False
        ),
        "V3-13_terminal_mechanical_release_remains_HOLD": (
            mechanical.get("gate_a_pass") is False
            and tmg4.get("state") == "HOLD"
            and tmg6.get("state") == "FAIL_15_OF_20"
            and mechanical.get("next_stage_authorized") is False
            and mechanical.get("release_credit") is False
        ),
        "V3-14_offline_control_predevelopment_only": (
            control_pre.get("candidate_package_complete") is True
            and control_pre.get("summary", {}).get(
                "candidate_packaging_criteria_satisfied"
            )
            == control_pre.get("summary", {}).get("total")
            == 9
            and control_pre.get("technical_predevelopment_complete") is False
            and control_pre.get("collision_aware_execution_credit") is False
            and control_pre.get("non_abort_execution_credit") is False
            and control_pre.get("integrated_control_ready") is False
        ),
        "V3-15_parent_control_safe_RL_VLA_and_execution_remain_HOLD": (
            control.get("predevelopment_source_technical_complete") is False
            and control.get("control_engineering_complete") is False
            and control.get("safe_review_pass") is False
            and control.get("rl_vla_execution_authorized") is False
            and control.get("collision_constrained_tracking_valid") is False
            and all(value is False for value in control.get("execution_guards", {}).values())
        ),
        "V3-16_joint_gate_remains_four_of_thirteen_ABORT_ONLY": (
            joint.get("required_condition_evaluation", {}).get("pass_count") == 4
            and joint.get("required_condition_evaluation", {}).get("total") == 13
            and joint.get("joint_system_ready") is False
            and joint.get("ready_for_physics_gated_embodied_intelligence") is False
            and joint.get("sim13_binding_pass") is False
            and joint.get("path_search_executed") is False
            and joint.get("unknown_auto_allow_count") == 0
        ),
        "V3-17_supersession_is_field_limited_not_gate_inheritance": (
            "ODR60_EXACT_OPTION_A_OWNER_TOKEN_ABSENT"
            in control_pre.get("remaining_holds", [])
            and "EXECUTION_MOUNT_NUMERIC_SPELLING_NOT_BOUND"
            in intake.get("blockers", [])
            and odr.get("owner_authority", {}).get("option_a_selected") is True
            and odr.get("actual_closures", {}).get(
                "execution_mount_full_precision_spelling_bound"
            )
            is True
            and odr.get("static_preflight_pass") is False
            and control_pre.get("technical_predevelopment_complete") is False
        ),
        "V3-18_all_candidate_and_parent_sources_deny_next_stage_and_release": all(
            document.get("next_stage_authorized") is False
            and document.get("release_credit") is False
            for document in (
                v2,
                dg3,
                dg4,
                dg5,
                parent_dynamics,
                odr,
                intake,
                mechanical,
                control_pre,
                control,
                joint,
            )
        ),
        "V3-19_CAD_M01_RouteC_nonabort_production_and_flight_credit_absent": (
            v2.get("authorized_now", {}).get("integrated_candidate_CAD_generation")
            is False
            and v2.get("authorized_now", {}).get("M01_collision_or_path_authority")
            is False
            and v2.get("authorized_now", {}).get(
                "physical_contact_or_non_abort_grasp"
            )
            is False
            and v2.get("authorized_now", {}).get("production_dynamics") is False
            and v2.get("authorized_now", {}).get("flight_release") is False
            and mechanical.get("harness_state", {}).get("terminal_gate")
            == "NOT_RELEASED"
        ),
    }
    all_pass = all(checks.values())
    failed = [name for name, value in checks.items() if not value]
    return {
        "schema": "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V3",
        "technical_verdict": (
            "PASS_ADDITIVE_DG1_TO_DG5_DESIGN_CANDIDATE_CONVERGENCE__PARENT_DYNAMICS_CAD_M01_ROUTE_C_PHYSICAL_CONTACT_NON_ABORT_CONTROL_AND_RELEASE_HOLD"
            if all_pass
            else "ADDITIVE_DG1_TO_DG5_CONVERGENCE_HOLD__SEE_FAILED_CHECKS"
        ),
        "decision_rule": "Authority > Evidence > Independent reproduction > Agent opinion",
        "source_binding": binding,
        "checks": checks,
        "summary": {
            "passed": sum(bool(value) for value in checks.values()),
            "total": len(checks),
            "failed": failed,
        },
        "dynamics_candidate_ledger": {
            "DG1": {
                "state": "PASS_ADDITIVE_CANDIDATE",
                "maximum_claim": "EXPLICIT_URDF_JOINT_SPAN_REFERENCE_METRIC_AND_COORDINATE_INVARIANCE",
                "forbidden_inference": "NO_CONDITIONING_OR_PARENT_DG1_COMPLETION_CLAIM",
            },
            "DG2": {
                "state": "PASS_ADDITIVE_CANDIDATE",
                "maximum_claim": "PRESCRIBED_JOINT_MOTION_WITH_NONZERO_LINEAR_AND_ANGULAR_MOMENTUM_CONSERVATION",
                "forbidden_inference": "NOT_TORQUE_DRIVEN_AND_NOT_A_COMPLETE_PLANT",
            },
            "DG3": {
                "state": "PASS_ADDITIVE_CANDIDATE_30_OF_30",
                "maximum_claim": dg3.get("maximum_claim"),
                "mixed_28x28_spectral_credit": False,
                "E23_numerical_inheritance": False,
                "parent_satisfied": False,
                "remaining_scope": dg3.get("remaining_DG3_scope"),
            },
            "DG4": {
                "state": "PASS_ADDITIVE_CANDIDATE_15_OF_15",
                "maximum_claim": "TWO_SEPARATE_RIGID_BODY_PRECONTACT_TO_POST_IMPACT_DIAGNOSTIC_AT_0P005_MPS",
                "terminal_state": "POST_IMPACT_DIAGNOSTIC",
                "real_attachment_ready": False,
                "physical_contact_ready": False,
                "parent_satisfied": False,
            },
            "DG5": {
                "state": "PASS_ADDITIVE_CANDIDATE_16_OF_16",
                "maximum_claim": "DETERMINISTIC_DESIGN_SCREEN_AND_THREE_DISCRETE_SOLAR_ROM_CORNERS",
                "corners_evaluated": 1024,
                "basic_rigid_body_constraints_not_falsified": 880,
                "quarantined_basic_constraint_failures": 144,
                "probability_or_as_built_credit": False,
                "parent_satisfied": False,
            },
            "parent_dynamics_engineering_complete": False,
        },
        "mechanical_and_M01_state": {
            "owner_option_a_selected": True,
            "execution_mount_full_precision_bound": True,
            "accepted_urdf_subtree_frame_ledger": "10_OF_10",
            "M01_required_scene_fields": "0_OF_9",
            "M01_instantiated_stage_scenes": "0_OF_3",
            "complete_collision_asset_set_bound": False,
            "clearance_policy": "0_OF_11166",
            "motion_certificates": "0_OF_150",
            "pair_oracle": "0_OF_11166",
            "continuous_edge_certificates": 0,
            "runtime_memory_admission_pass": False,
            "fresh_low_memory_owner_override_authorized": False,
            "terminal_mechanical_gate_a_pass": False,
        },
        "control_and_joint_state": {
            "offline_control_predevelopment_candidate_packaging": "9_OF_9",
            "offline_control_predevelopment_research_scope_available": all_pass,
            "technical_predevelopment_complete": False,
            "control_engineering_complete": False,
            "safe_current_tree_review_pass": False,
            "RL_or_VLA_execution_authorized": False,
            "joint_gate": "4_OF_13",
            "sim13_maximum_operational_state": "ABORT_ONLY",
            "ready_for_physics_gated_embodied_intelligence": False,
        },
        "supersession_ledger": [
            {
                "older_record": "CTRL_R2_PREDEVELOPMENT_GATE_V1.remaining_holds.ODR60_EXACT_OPTION_A_OWNER_TOKEN_ABSENT",
                "newer_record": "ODR60_OPTION_A_EXECUTION_CLOSURE_GATE_V1.owner_authority.option_a_selected=true",
                "superseded_field_only": "OWNER_OPTION_SELECTION",
                "broader_gate_inheritance": False,
            },
            {
                "older_record": "BINDING_INTAKE_GATE_V1 mount/frame blockers",
                "newer_record": "ODR60_OPTION_A_EXECUTION_CLOSURE_GATE_V1 mount spelling and 10/10 frame ledger",
                "superseded_fields_only": [
                    "EXECUTION_MOUNT_FULL_PRECISION_SPELLING",
                    "ACCEPTED_URDF_SUBTREE_COLLISION_FRAME_LEDGER",
                ],
                "M01_query_or_search_inheritance": False,
            },
        ],
        "bounded_research_actions_available": {
            "DG1_to_DG5_candidate_evidence_consumption": all_pass,
            "offline_control_contract_metric_and_negative_result_predevelopment": all_pass,
            "integrated_candidate_CAD_generation": False,
            "geometry_pair_or_edge_query": False,
            "M01_path_search": False,
            "physical_contact_or_target_attachment": False,
            "non_abort_grasp": False,
            "RL_or_VLA_execution": False,
            "hardware_or_flight_execution": False,
        },
        "exact_remaining_blockers": [
            "FRESH_NAMED_RUN_RUNTIME_MEMORY_ADMISSION_OR_FRESH_SINGLE_USE_LOW_MEMORY_OWNER_OVERRIDE_REQUIRED_FOR_CAD",
            "INTEGRATED_FULL_ARM_CANDIDATE_STEP_NOT_GENERATED_INSPECTED_OR_HASH_BOUND",
            "COMPLETE_SYSTEM_OPERATIONAL_COLLISION_ASSET_SET_NOT_BOUND",
            "M01_REQUIRED_SCENE_FIELDS_0_OF_9_AND_STAGE_INSTANCES_0_OF_3",
            "ACTIVE_OBJECT_AND_PAIR_UNIVERSE_NOT_REISSUED_PER_STAGE",
            "CLEARANCE_POLICY_0_OF_11166_MOTION_CERTIFICATES_0_OF_150_PAIR_ORACLE_0_OF_11166_CONTINUOUS_EDGES_0",
            "ROUTE_C_MANDATORY_HARNESS_STATES_AND_G12_NOT_CLOSED",
            "PHYSICAL_AS_BUILT_CONTACT_PATCH_CLOSING_TIME_FORCE_TORQUE_AND_UNCERTAINTY_PENDING",
            "DG3_TIME_VARYING_MASS_CORIOLIS_EULER_POINCARE_TORQUE_DRIVEN_AND_AS_BUILT_MODAL_SCOPE_OPEN",
            "POST_CAPTURE_ATTACHED_COMBINED_PLANT_AND_NON_ABORT_CONSUMER_AUTHORITY_ABSENT",
            "CONTROL_TASK_SPACE_METRIC_M01_TIME_HISTORY_ACTUATOR_WHEEL_FLEX_AND_SAFE_CURRENT_TREE_GATES_OPEN",
            "SIM13_SYSTEM_BINDING_AND_NON_ABORT_AUTHORITY_FALSE",
            "PARENT_DYNAMICS_CONTROL_JOINT_MECHANICAL_AND_RELEASE_GATES_NOT_REISSUED_AS_PASS",
        ],
        "maximum_claim": "HASH_BOUND_ADDITIVE_DG1_TO_DG5_BOUNDED_DESIGN_CANDIDATES_WITH_OFFLINE_CONTROL_PREDEVELOPMENT_SCOPE__NOT_COMPLETE_DYNAMICS_NOT_CAD_NOT_M01_NOT_ROUTE_C_NOT_PHYSICAL_CONTACT_NOT_NON_ABORT_NOT_CONTROL_RELEASE_NOT_FLIGHT_RELEASE",
        "review_status": "PENDING_OWNER_REVIEW",
        "next_stage_authorized": False,
        "release_credit": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    gate = build_gate()
    payload = canonical_bytes(gate)
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_bytes() != payload:
            print("FAIL_OUTPUT_MISSING_OR_NOT_BYTE_IDENTICAL")
            return 2
        manifest_payload = canonical_bytes(build_manifest())
        if not MANIFEST.is_file() or MANIFEST.read_bytes() != manifest_payload:
            print("FAIL_MANIFEST_MISSING_OR_NOT_BYTE_IDENTICAL")
            return 2
        print("PASS_BYTE_IDENTICAL")
    else:
        OUTPUT.write_bytes(payload)
        MANIFEST.write_bytes(canonical_bytes(build_manifest()))
        print(gate["technical_verdict"])
        print(f"checks={gate['summary']['passed']}/{gate['summary']['total']}")
        print(f"sha256={sha256(OUTPUT)}")
        print(f"manifest_sha256={sha256(MANIFEST)}")
    return 0 if gate["summary"]["passed"] == gate["summary"]["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
