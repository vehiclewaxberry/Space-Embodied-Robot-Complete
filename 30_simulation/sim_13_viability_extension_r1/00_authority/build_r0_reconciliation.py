"""R0 权威调和：生成 SIM13_CURRENT_PARENT_CHILD_AUTHORITY_RECONCILIATION_V1.json。

只读审计 + 哈希绑定。不执行求解器，不改写任何既有 Gate。
所有 status 只允许 VERIFIED / PROVISIONAL / UNKNOWN / HOLD / ABSENT。

用法：python 30_simulation/sim_13_viability_extension_r1/00_authority/build_r0_reconciliation.py
"""
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "SIM13_CURRENT_PARENT_CHILD_AUTHORITY_RECONCILIATION_V1.json")


def pin(rel):
    """返回 {path,bytes,sha256} 或 ABSENT 记录（fail-closed：缺失即显式记录）。"""
    p = os.path.join(REPO, rel)
    if not os.path.isfile(p):
        return {"path": rel, "presence": "ABSENT_NOT_FOUND_IN_REPOSITORY"}
    b = open(p, "rb").read()
    return {"path": rel, "presence": "PRESENT", "bytes": len(b),
            "sha256": hashlib.sha256(b).hexdigest().upper()}


SIM13 = "30_simulation/sim_13_physics_gated_embodied_grasping"
V2 = f"{SIM13}/v2_system_rebind"
MECHREL = "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2"
V5R = "20_engineering/F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820"
M7 = "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1"

doc = {
    "schema": "SIM13_CURRENT_PARENT_CHILD_AUTHORITY_RECONCILIATION_V1",
    "program": "RESEARCH_COUPLED_CLOSURE_R1 / SIM13_VIABILITY_EXTENSION_R1",
    "generated_date_local": "2026-08-29",
    "artifact_class": "READ_ONLY_AUTHORITY_RECONCILIATION__NO_PARENT_MUTATION__NO_RELEASE_CREDIT",
    "review_status": "PENDING_OWNER_REVIEW",
    "decision_rule": "Authority > Evidence > Independent reproduction > Agent opinion",
    "fail_closed_invariants": [
        "UNKNOWN is never PASS",
        "a child/backend PASS is never a parent PASS",
        "a test PASS is not a scientific Gate PASS",
        "rigid-body FEASIBLE is never SAFE while FLEX is not evaluated",
        "an absent file is recorded as ABSENT, never inferred",
    ],

    # ---------------- 1. Sim13 父/子权威 ----------------
    "sim13_authority_chain": {
        "parent_gate": {
            "id": "SIM13_V2_PREBIND_SOURCE_GATE_V1",
            "pin": pin(f"{V2}/results/SIM13_V2_PREBIND_SOURCE_GATE_V1.json"),
            "generated_date_local": "2026-08-24",
            "score_package_validation": "25/25",
            "formal_negative_controls": "15/20 PASS, 0 FAIL, 5 DEPENDENCY_HOLD",
            "hold_ids": ["NC15", "NC16", "NC18", "NC19", "NC20"],
            "maximum_current_operational_state":
                "ABORT_ONLY_WITH_SOURCE_ONLY_ANALYTIC_PREBIND_DIAGNOSTICS",
            "system_urdf_available": False,
            "system_interface_instantiated": False,
            "owner_accepted": False,
            "next_stage_authorized": False,
            "release_credit": False,
            "status": "VERIFIED",
        },
        "child_backend_gate": {
            "id": "SIM13_20_OF_20_GATE_V1",
            "pin": pin(f"{V2}/runtime_fail_closed_backends_v2/results/SIM13_20_OF_20_GATE_V1.json"),
            "generated_date_local": "2026-08-25",
            "nc_score": "20/20",
            "score_semantics":
                "NEGATIVE_CONTROL_REGISTRY_NC01_NC20__NOT_A_20_CRITERION_MISSION_GATE",
            "scope": "BACKEND_SUBSCOPE_RUNTIME_FAIL_CLOSED_DYNAMICS_AND_CONTACT_GRASP_BACKENDS",
            "maximum_operational_state":
                "ABORT_ONLY_WITH_VALIDATED_FAIL_CLOSED_BACKENDS_20_OF_20_NC"
                "__PRODUCTION_NON_ABORT_STILL_MASKED_BY_12_GATE_AUTHORITY",
            "review_status": "PENDING_OWNER_REVIEW",
            "next_stage_authorized": False,
            "release_credit": False,
            "status": "VERIFIED",
        },
        "reconciling_addendum": {
            "id": "SIM13_POST_TERMINAL_HANDOFF_ADDENDUM_GATE_V1",
            "pin": pin(f"{MECHREL}/_work/loop_b/sim13_post_terminal_handoff_addendum_v1/"
                       "SIM13_POST_TERMINAL_HANDOFF_ADDENDUM_GATE_V1.json"),
            "authority": "APPEND_ONLY_LINEAGE_AND_BACKEND_SUBSCOPE_GATE__NO_PARENT_MUTATION",
            "frozen_parent_artifacts_modified": False,
            "historical_15_of_20_superseded": False,
            "post_terminal_relation": "APPEND_ONLY_BACKEND_SUBSCOPE_EVIDENCE",
            "full_tmg6_reissue_executed": False,
            "verdict": "SIM13_POST_TERMINAL_BACKEND_SUBSCOPE_20_OF_20_PASS"
                       "__FULL_TMG6_NOT_REISSUED__ABORT_ONLY__NO_RELEASE_CREDIT",
            "status": "VERIFIED",
        },
        "reconciliation_ruling": {
            "dual_authority_state_is_real": True,
            "resolution": "NO_CONFLICT__DIFFERENT_SCOPES__ADDENDUM_ALREADY_ADJUDICATES",
            "explanation": (
                "15/20 is the formal parent negative-control score of the Sim13 V2 prebind "
                "package. 20/20 is a later append-only backend-subscope negative-control "
                "registry that closed work orders WO-NC15/16/18/19/20 in the backend lane "
                "only. The addendum gate explicitly records historical_15_of_20_superseded="
                "false and full_tmg6_reissue_executed=false. Therefore the parent Sim13 "
                "status for this research program is 15/20, ABORT-only."),
            "current_parent_status_for_research": "PARENT_15_OF_20__ABORT_ONLY__NOT_REISSUED",
            "child_results_consumable_by_research_extension": True,
            "child_consumption_scope":
                "DIAGNOSTIC_AND_STRUCTURAL_ONLY__MAY_INFORM_MODEL_AND_SCHEMA_DESIGN",
            "child_results_may_generate_research_credit": False,
            "claims_that_remain_unauthorized": [
                "Sim13 parent PASS",
                "non-ABORT grasp action release",
                "contact/grasp physical authority",
                "current-system binding (SYSTEM_BINDING gate not passed)",
                "TMG-6 reissue",
                "Mechanical Release credit",
                "any RL/VLA training authorization",
            ],
            "status": "VERIFIED",
        },
    },

    # ---------------- 2. L0 机械权威 ----------------
    "l0_mechanical_authority": {
        "binding_ssot": {
            "id": "UNIFIED_R2_SYSTEM_INTERFACE_V1",
            "pin": pin(f"{MECHREL}/15_UNIFIED_R2_SYSTEM_INTERFACE.yaml"),
            "configuration": "C01_DEPLOYED_NOMINAL_FIXED_SOLAR_SNAPSHOT",
            "status": "VERIFIED",
        },
        "accepted_b601_urdf": {
            "pin": pin("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"),
            "classification_in_ssot": "CURRENT_HARDWARE_TRUTH",
            "ssot_note": "E_HW joint limits; modification FORBIDDEN",
            "topology_verified": {"links": 10, "joints": 9,
                                  "revolute": 6, "prismatic": 2, "fixed": 1},
            "topology_matches_expected_6R_1fixed_2P": True,
            "byte_identical_mirrors": [
                "20_engineering/cad/B5_1R1_B601_interface_native_rework_candidate/"
                "00_BASELINE/AUTHORITIES/accepted_urdf/arm_b601_v1.urdf",
                "20_engineering/cad/B5_1R1_B601_interface_native_rework_candidate/"
                "00_BASELINE/PARENT_LOCKED_INPUTS/ACCEPTED_URDF/arm_b601_v1.urdf",
                f"{V5R}/06_pack_and_go/V5R_NEUTRAL_OPERATIONAL_PACKAGE/urdf/arm_b601_v1.urdf",
            ],
            "status": "VERIFIED",
        },
        "system_urdf_candidate_19_link": {
            "pin": pin(f"{M7}/unified_r2_digital_prototype_prebind/generated_v2/"
                       "unified_r2_c01_no_route_c_sim_candidate_v2.urdf"),
            "topology_verified": {"links": 19, "joints": 18,
                                  "revolute": 6, "prismatic": 2, "fixed": 10},
            "classification_in_ssot": "EMITTED_THIS_CLOSURE / SOURCE_ONLY_BUILDER_EMISSION",
            "documented_defect": "TMC-F01 (see urdf_generation_receipt)",
            "status": "PROVISIONAL",
        },
        "system_frame_tree": {
            "pin": pin(f"{M7}/unified_r2_digital_prototype_prebind/source_only_v2/"
                       "UNIFIED_R2_SYSTEM_FRAME_TREE_V2.yaml"),
            "artifact_class": "SOURCE_ONLY_FRAME_AND_TOPOLOGY_LEDGER",
            "status_in_artifact": "PREBIND_STATIC_CANDIDATE_WITH_EXPLICIT_HOLDS",
            "covers": ["S_SPACECRAFT_BUS", "D_BUS_MATE_PHYSICAL", "M_DYNAMICS_NONPHYSICAL",
                       "D_BUS_M6_PATTERN", "M3R_ROOT", "B601_BASE_PHYSICAL",
                       "SOLAR_R2_ROOT_L", "SOLAR_R2_ROOT_R"],
            "does_not_cover": ["tool_flange_frame", "force_torque_sensor_frame",
                               "wrist_camera_frame", "active_grasp_frame",
                               "target_contact_frame"],
            "status": "PROVISIONAL",
        },
        "mass_inertia_authority": {
            "l0_authority": "accepted_b601_urdf (arm links)",
            "system_design_mass": {
                "pin": pin(f"{M7}/wp2_design_mass/SYSTEM_DESIGN_MASS_PROPERTIES_V3_R2.yaml"),
                "authority_class": "DESIGN_MODEL_R2__NOT_AS_BUILT_OR_FLIGHT",
                "coverage": "9/9 configurations mass+CG+full inertia",
            },
            "m4_released_mass_cg_inertia_count": "0/9",
            "runtime_c01_total_mass_kg": 31.022864807342987,
            "c08_22kg_target_composite_mass_kg": 53.022864807342984,
            "c09_150kg_debris_composite_mass_kg": 181.02286480734298,
            "cad_may_overwrite_l0": False,
            "status": "PROVISIONAL",
        },
        "base_interface_authority": {
            "pin": pin("20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/"
                       "03_native_cad/M3_interface_authority/M3R_INTERFACE_AUTHORITY_GATE.json"),
            "schema": "M3R_INTERFACE_AUTHORITY_GATE_V2",
            "current_competition_input": "4 x M4-class fastener stack on 64 x 64 mm square",
            "equivalent_pcd_mm": 90.509641772,
            "clocking_about_spacecraft_x_deg": 25.000014,
            "superseded_claim": "8 x M3 at approximately PCD 90.51 mm",
            "claim_scope": "AS_BUILT_MEASURED_COMPETITION_INTERFACE",
            "six_by_six_stiffness_or_compliance_present": False,
            "status": "PROVISIONAL_GEOMETRY_ONLY__NO_COMPLIANCE_DATA",
        },
    },

    # ---------------- 3. sim_12 来源与结构审计 ----------------
    "sim12_authority": {
        "gate": {
            "pin": pin("30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json"),
            "verdict": "SIM12_PHASE1_GATES_PASS",
            "n_cells": 16,
            "flex_status": "UNKNOWN_NOT_IN_CRITERIA",
            "best_per_case": {"A_low": "S1_passive", "B_anchor": "ABORT",
                              "C_transition": "S3a_wheel_bias", "D_extreme": "ABORT"},
            "status": "VERIFIED",
        },
        "results_csv": pin("30_simulation/sim_12_strategy_feasibility/results/strategy_results.csv"),
        "source": pin("30_simulation/sim_12_strategy_feasibility/src/strategy_eval.py"),
        "config": pin("20_engineering/config/strategy_feasibility/strategies_v0.yaml"),
        "inherited_threshold_config": pin("20_engineering/config/mission_feasibility/scan_v0.yaml"),
        "frozen_thresholds": {
            "post_capture_rate_max_dps": 2.0,
            "propellant_budget_max_g": 54.73476731425644,
            "t_detumble_max_s": 3600.0,
            "wheel_capacity_Nms": 0.3,
            "thruster_isp_s": 60.0,
            "thruster_force_N": 0.1,
            "lever_arm_m": 0.17,
            "g0_mps2": 9.80665,
        },
        "same_state_paired_table_v1": {
            **pin("SIM12_SAME_STATE_PAIRED_TABLE_V1.csv"),
            "repository_wide_search": "NO_FILE_MATCHING_*SAME_STATE* ANYWHERE IN REPOSITORY",
            "status": "ABSENT__EXTERNAL_CLAIM_NOT_REPRODUCIBLE_FROM_REPOSITORY",
        },
        "structural_audit_of_prompt_claims": {
            "claim_S1_S3a_S4_share_identical_capture_transition": {
                "verdict": "CONFIRMED",
                "method": "source-level (alpha=1.0 only for S2_velocity_matching) and "
                          "row-level byte equality of impulse_Ns, H_required_Nms, "
                          "post_capture_rate_dps across all 4 cases",
                "status": "VERIFIED",
            },
            "claim_correct_factorization_is_2x3": {
                "verdict": "CONFIRMED",
                "mapping": {"S1_passive": "alpha=0 x WHEEL_DIRECT",
                            "S3a_wheel_bias": "alpha=0 x WHEEL_BIAS",
                            "S4_post_capture_detumble": "alpha=0 x THRUSTER",
                            "S2_velocity_matching": "alpha=1 x WHEEL_DIRECT"},
                "missing_cells": ["alpha=1 x WHEEL_BIAS (4 cases)",
                                  "alpha=1 x THRUSTER (4 cases)"],
                "missing_cell_count": 8,
                "new_solver_run_required": False,
                "reason": "the alpha=1 physical transition (J, H, omega_plus) already exists "
                          "as the S2 row; only the post-capture allocation algebra differs",
                "status": "VERIFIED",
            },
            "claim_gate_set_changes_with_strategy": {
                "verdict": "CONFIRMED_DEFECT",
                "evidence": "strategy_eval.py: S4 uses feas = gate1 and gate3 and gate4 "
                            "(wheel gate deleted); S1/S2/S3a use feas = gate1 and gate2 "
                            "(thruster gates deleted)",
                "observable_symptom": "C_transition S4 is FEASIBLE with wheel_margin_Nms "
                                      "= -0.068886",
                "status": "VERIFIED",
            },
            "claim_24_cells_9_feasible_15_infeasible": {
                "verdict": "REPRODUCED_BY_ALGEBRAIC_RECONSTRUCTION",
                "reconstructed_feasible": 9,
                "reconstructed_infeasible": 15,
                "caveat": "reproduced under the CURRENT strategy-dependent gate subsets, "
                          "i.e. under the defect above; the R2 reissue uses one global "
                          "strategy-invariant gate vector and MAY CHANGE THIS SPLIT",
                "status": "PROVISIONAL",
            },
            "claim_alpha1_THRUSTER_C_transition_fuel_6_9980_g": {
                "verdict": "REPRODUCED_EXACTLY",
                "reconstruction": "fuel(S2 dv-match) 0.7696 g + 1e3*H/(lever*isp*g0) with "
                                  "H=0.6230150 -> 6.2284 g; total 6.9980 g",
                "status": "VERIFIED",
            },
            "claim_pareto_minimum_rigid_margins_M_0_013381_and_0_048817": {
                "verdict": "NOT_FOUND_IN_REPOSITORY",
                "note": "no normalized minimum-gate-margin scalar M is computed anywhere in "
                        "sim_12; wheel_margin_Nms for C_transition alpha=0 x WHEEL_BIAS is "
                        "0.231114 N*m*s, not 0.013381. M must be DEFINED by the R2 global "
                        "gate vector before any Pareto claim is made.",
                "status": "UNVERIFIED",
            },
            "wheel_bias_analytic_boundaries": {
                "verdict": "DERIVED_AND_VERIFIED_AGAINST_ROWS",
                "wheel_direct_feasible_iff": "H <= h_max (0.3 N*m*s)",
                "wheel_bias_feasible_iff": "H <= 2*h_max (0.6 N*m*s)",
                "wheel_bias_margin_exceeds_direct_iff": "H > h_max/2 (0.15 N*m*s)",
                "note": "the prompt's H > h_max/2 is the MARGIN-crossover boundary; "
                        "H > h_max is the distinct FEASIBILITY-crossover boundary. "
                        "Both are candidate binding-gate switches for Result B.",
                "row_check": "A_low: direct margin 0.297504 = h_max-H; bias margin 0.002496 "
                             "= H. C_transition: direct -0.068886; bias 0.231114. Both exact.",
                "status": "VERIFIED",
            },
        },
    },

    # ---------------- 4. 冻结物理锚点 ----------------
    "frozen_physics_anchors": {
        "sim_10": {"pin": pin("30_simulation/sim_10_mission_feasibility/results/sim_10_gate_check.json"),
                   "verdict": "SIM10_GATES_PASS", "status": "VERIFIED"},
        "sim_11": {"pin": pin("30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json"),
                   "verdict": "SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS",
                   "provisional_fields": ["panel modal parameters (placeholder)",
                                          "contact window T_c = 20 ms nominal"],
                   "status": "VERIFIED_WITH_PROVISIONAL_PARAMS"},
        "sim_12": {"verdict": "SIM12_PHASE1_GATES_PASS", "status": "VERIFIED"},
        "safe_00": {"pin": pin("30_simulation/safety_00_runtime_gate/results/safety_00_gate_check.json"),
                    "verdict": "PASS", "review_status": "PENDING_REVIEW",
                    "next_stage_authorized": False, "status": "VERIFIED"},
        "ctrl_01": {"pin": pin("30_simulation/control_01_end_effector_tracking/results/control_01_gate_check.json"),
                    "verdict": "REPEAT", "next_stage_authorized": False,
                    "disposition": "NEGATIVE_RESULT_CLOSED_BY_CP6_RULING", "status": "VERIFIED"},
        "ctrl_02": {"pin": pin("30_simulation/control_02_base_attitude/results/control_02_gate_check.json"),
                    "verdict": "PASS", "review_status": "PENDING_REVIEW",
                    "scope": "PROVISIONAL_ACTUATOR_AND_TIME_WINDOW_MODEL",
                    "status": "VERIFIED"},
        "mujoco_precontact": {
            "pin": pin("30_simulation/r2_mujoco_free_floating_precontact_v1/results/"
                       "R2_MUJOCO_FREE_FLOATING_PRECONTACT_GATE_V1.json"),
            "achieved_claim": "R2_MUJOCO_FREE_FLOATING_PRECONTACT_CROSS_SOLVER_DIAGNOSTIC_PASS"
                              "__PARENT_MECHANICAL_DYNAMICS_CONTROL_SAFE_SIM13_CONTACT_AND_"
                              "RELEASE_HOLD",
            "next_stage_authorized": False, "release_credit": False, "status": "VERIFIED"},
    },

    # ---------------- 5. e23 柔性证据映射 ----------------
    "e23_flex_authority": {
        "pin": pin("30_simulation/e23_r2_full_flex_coupled_recert/results/"
                   "E23_R2_FULL_FLEX_COUPLED_GATE_V1.json"),
        "technical_verdict": "PASS_WITH_DECLARED_PROVISIONAL_PHYSICS",
        "criteria": "18/18",
        "rom": "7 modes B1-B3 + T1-T4 (three bending modes preserved)",
        "hf_to_rom_seven_mode_max_relative": 0.0027143911284986865,
        "hf_to_rom_limit": 0.01,
        "minimum_passing_dimension": 6,
        "all_five_dimensional_subsets_fail_1pct": True,
        "cross_solver_max_relative": 1.8136532292893113e-05,
        "key_anchors": {
            "22kg_nominal_omega_plus_equiv_dps": 0.1603671648970606,
            "22kg_nominal_Hc_Nms": 0.011782323851997206,
            "150kg_nominal_omega_plus_equiv_dps": 3.042713056507504,
            "150kg_nominal_Hc_Nms": 3.6466119549031752,
        },
        "blocking_disposition": {
            "sim10_authority_inheritance": "NOT_INHERITED_THRESHOLD_HASH_DRIFT",
            "e15_current": "REPEAT_ANCF_CERTIFICATION",
            "e15_inheritance": "NOT_INHERITED",
            "diagnostic_gate_classification": "PROVISIONAL_E22_DIAGNOSTIC",
            "review_status": "PENDING_OWNER_REVIEW",
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "may_be_consumed_directly_as_sim13r_flex_evidence": False,
        "permitted_use": "LOW_FIDELITY_PRIOR_AND_ROM_STRUCTURE_DONOR_ONLY",
        "reason": "E23 explicitly records sim10_authority_inheritance="
                  "NOT_INHERITED_THRESHOLD_HASH_DRIFT; sim_12 thresholds are inherited from "
                  "the sim_10 frozen registry, so the E23 PASS cannot be inherited into the "
                  "sim_12/sim_13R gate lane without an explicit re-binding.",
        "open_discrepancy_for_R4_ledger": {
            "id": "DISC-001",
            "observation": "E23 150 kg nominal (omega_plus 3.042713 dps, Hc 3.6466 N*m*s) vs "
                           "sim_12 B_anchor alpha=0 (omega_plus 3.063330 dps, H 3.650993 "
                           "N*m*s): -0.67% and -0.12%.",
            "observation_2": "E23 22 kg nominal Hc 0.0117823 N*m*s is within 0.023% of "
                             "sim_12 A_low alpha=1 H 0.0117796 N*m*s, but 4.72x the "
                             "sim_12 A_low alpha=0 H 0.0024962 N*m*s.",
            "interpretation": "UNRESOLVED. Grasp geometry / lever arm / alpha convention "
                              "correspondence between E23 and sim_12 is NOT established. "
                              "Must be resolved before any FLEX row is written into the "
                              "24-cell table.",
            "status": "UNKNOWN",
        },
        "status": "VERIFIED_GATE__NOT_CONSUMABLE_AS_CURRENT_FLEX_EVIDENCE",
    },

    # ---------------- 6. 夹爪干涉台账 ----------------
    "gripper_interference_ledger": {
        "classification_table": pin(f"{V5R}/02_interfaces/INTERFERENCE_CLASSIFICATION.csv"),
        "geometry_validation": pin(f"{V5R}/04_validation/GRIPPER_R1_GEOMETRY_VALIDATION.json"),
        "mech_rl_interface": pin(f"{V5R}/02_interfaces/MECH_RL_INTERFACE_V1.yaml"),
        "class_1_donor_static_internal": {
            "rows": 81, "post_count": 81,
            "disposition": "ACCEPTED_EXCEPTION_OPTION_A_HISTORICAL_ONLY",
            "must_not_be_merged_with_class_2": True, "status": "HOLD"},
        "class_2_pose_induced": {
            "rows_native_v5": 36,
            "tallies": {"OPEN": {"rows": 24, "volume_mm3": 1266.933836},
                        "PREGRASP": {"rows": 12, "volume_mm3": 779.626476}},
            "target_palm_bodies": ["B51_REF_gripper_detail_LINKLOCAL050",
                                   "B51_REF_gripper_detail_LINKLOCAL054"],
            "status": "HOLD"},
        "derived_candidate_ALREADY_EXISTS": {
            "name": "B601_GRIPPER_PALM_RAIL_SLOT_R1",
            "step": pin(f"{V5R}/01_native_cad/gripper_r1/B601_GRIPPER_PALM_RAIL_SLOT_R1.step"),
            "stl": pin(f"{V5R}/01_native_cad/gripper_r1/B601_GRIPPER_PALM_RAIL_SLOT_R1.stl"),
            "status_in_artifact": "NEUTRAL_R1_CORRECTION_PASS_NATIVE_V5_REINTEGRATION_HOLD",
            "pose_induced_rail_palm_interference_rows": 0,
            "positive_overlap_volume_mm3": 0.0,
            "positive_overlap_basis":
                "ANALYTIC_CONSERVATIVE_ENVELOPE_PLUS_FOUR_POSE_BREP_BOOLEAN",
            "continuous_stroke": {"travel_domain_mm": [0.0, 71.5], "sample_step_mm": 0.5,
                                  "sample_count": 144, "analytic_pass": True,
                                  "four_pose_boolean_complete": True},
            "removed_volume_mm3": 19392.85747214633,
            "estimated_mass_delta_g": -54.674014864627416,
            "estimated_mass_delta_method":
                "ACCEPTED_URDF_GRIPPER_LINK_MASS_PRO_RATA_BY_V5_PALM_VOLUME",
            "donor_modified": False,
            "accepted_urdf_modified": False,
            "prompt_M_R2_exit_criteria_met_in_neutral_scope": True,
            "remaining_open_holds": [
                "NATIVE_V5_PALM_R1_REINTEGRATION_AND_36_ROW_NATIVE_REMEASUREMENT",
                "MANUFACTURING_ADDITIONAL_CLEARANCE_AUTHORITY",
                "MINIMUM_REMAINING_WALL_THICKNESS_DATUM",
                "STRUCTURAL_STRENGTH_AND_LOAD_CASE",
                "EXTERNAL_OBJECT_GRIPPER_CONTACT_GEOMETRY",
            ],
            "not_yet_produced_by_any_artifact": [
                "gripper aperture map as a function of q_p1, q_p2",
                "contact-point map r_g",
                "contact-normal map n_g",
                "minimum and maximum grasp radius",
                "candidate center-of-mass delta",
                "candidate inertia-tensor delta",
                "updated L2 collision mesh",
            ],
            "status": "PROVISIONAL__DO_NOT_RECREATE__RECONCILE_AND_EXTEND",
        },
        "class_3_composite_addenda": {
            "count": "UNKNOWN",
            "status": "HOLD_NOT_MONOLITHICALLY_PLACED_OR_NARROW_PHASE_VALIDATED",
            "rule": "UNKNOWN must fail closed in sim13"},
    },

    # ---------------- 7. R1 交付物存在性 ----------------
    "r1_deliverable_presence_audit": {
        "SIM13R_FRAME_GRAPH_V1.yaml": "ABSENT (partial upstream: UNIFIED_R2_SYSTEM_FRAME_TREE_V2)",
        "SIM13R_JOINT_ZERO_SIGN_LIMIT_REGISTER_V1.yaml": "ABSENT",
        "SIM13R_JOINT_CONTROL_ENVELOPE_V1.csv": "ABSENT",
        "SIM13R_SENSOR_AND_GRASP_FRAME_REGISTER_V1.yaml": "ABSENT",
        "SIM13R_BASE_INTERFACE_COMPLIANCE_LNH_V1.yaml": "ABSENT (no 6x6 K_b anywhere in repo)",
        "SIM13R_COLLISION_MODEL_MAPPING_V1.yaml": "ABSENT",
        "SIM13R_STOW_RELEASE_INTERLOCK_V1.yaml": "ABSENT",
        "FLEXIBLE_APPENDAGE_PARAMETER_CARD_SIM13R_V1.yaml": "ABSENT",
        "SIM12_FACTORIAL_GATE_VECTOR_V2.yaml": "ABSENT",
        "SIM12_SAME_STATE_PAIRED_TABLE_V2.csv": "ABSENT",
        "SIM12_PARETO_FRONT_V2.csv": "ABSENT",
        "SIM12_GS2_REISSUE_V2.json": "ABSENT",
        "SIM13R_CAPTURE_MAP_SCHEMA_V1.yaml": "ABSENT",
        "CTRL03_PROBLEM_FORMULATION_V1.md": "ABSENT",
        "MULTIFIDELITY_FLEXIBILITY_CONTRACT_V1.yaml": "ABSENT",
        "SIM13R_RESEARCH_MECHANICAL_BASELINE_MANIFEST_V1.json": "ABSENT",
        "SIM13R_MECH_DYNAMICS_HANDOFF_CONTRACT_V1.yaml": "ABSENT",
    },

    # ---------------- 8. R0 出口判定 ----------------
    "r0_exit_criteria": {
        "sim13_parent_status_identified": True,
        "sim13_child_backend_status_identified": True,
        "accepted_l0_urdf_identified_and_hashed": True,
        "current_frame_authority_identified": True,
        "current_e23_authority_identified": True,
        "sim12_source_and_gate_authority_identified": True,
        "all_six_met": True,
    },
    "verdict": "R0_AUTHORITY_RECONCILIATION_PASS__PARENT_SIM13_REMAINS_15_OF_20_ABORT_ONLY"
               "__CHILD_20_OF_20_IS_BACKEND_SUBSCOPE_NEGATIVE_CONTROL_ONLY"
               "__SIM12_FACTORIAL_DEFECT_CONFIRMED_AT_SOURCE_LEVEL"
               "__E23_NOT_DIRECTLY_CONSUMABLE__NO_RELEASE_CREDIT",
    "next_stage_authorized": False,
    "release_credit": False,
    "blocks_free_floating_simulation_until": [
        "SIM13R_FRAME_GRAPH_V1 complete (T_SB, tool flange, F/T, camera, grasp, target frames)",
        "SIM13R_JOINT_ZERO_SIGN_LIMIT_REGISTER_V1 complete (joint2 axis 0 0 -1 sign convention)",
        "SIM13R_JOINT_CONTROL_ENVELOPE_V1 complete (URDF 50/200 rad/s must not be used)",
    ],
}

with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(doc, f, indent=1, ensure_ascii=False)
    f.write("\n")
print("written:", os.path.relpath(OUT, REPO))
print("verdict:", doc["verdict"])
