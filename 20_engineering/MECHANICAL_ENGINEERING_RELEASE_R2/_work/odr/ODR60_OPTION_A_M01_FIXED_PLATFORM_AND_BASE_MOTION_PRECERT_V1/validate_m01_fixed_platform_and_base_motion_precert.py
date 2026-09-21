#!/usr/bin/env python3
"""Standalone fail-closed validator for the M01 fixed-platform package.

The validator intentionally does not import, execute, or introspect the
builder module. Source locks, contracts, recomputations, manifest rules, and
mutation controls are independently frozen here.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import math
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

import numpy as np
import yaml


HERE = Path(__file__).resolve().parent
POSE_NAME = "M01_FIXED_PLATFORM_POSE_BINDING_V1.json"
RECOMPUTE_NAME = "INDEPENDENT_BASE_LINK_ZERO_MOTION_RECOMPUTE_V1.json"
CERT_NAME = "A_BASE_LINK_GLOBAL_MOTION_CERTIFICATE_V1.json"
QUARANTINE_NAME = "ROUTE_C_NEGATIVE_WITNESS_QUARANTINE_V1.json"
NEGATIVE_NAME = "M01_FIXED_PLATFORM_AND_BASE_MOTION_NEGATIVE_CONTROLS_V1.json"
GATE_NAME = "M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_GATE_V1.json"
MANIFEST_NAME = "M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_SHA256_V1.csv"
JSON_ARTIFACT_NAMES = (POSE_NAME, RECOMPUTE_NAME, CERT_NAME, QUARANTINE_NAME, NEGATIVE_NAME, GATE_NAME)
PACKAGE_PAYLOAD_FILES = frozenset({
    "README.md",
    "build_m01_fixed_platform_and_base_motion_precert.py",
    "validate_m01_fixed_platform_and_base_motion_precert.py",
    "test_m01_fixed_platform_and_base_motion_precert.py",
    *JSON_ARTIFACT_NAMES,
})

Q_ORDER = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6"]
Q_LOWER = [-2.8, -3.14, -3.14, -1.87, -1.57, -3.14]
Q_UPPER = [2.8, 0.0, 0.0, 1.57, 1.57, 3.14]
IDENTITY_4 = [
    [1.0, 0.0, 0.0, 0.0],
    [0.0, 1.0, 0.0, 0.0],
    [0.0, 0.0, 1.0, 0.0],
    [0.0, 0.0, 0.0, 1.0],
]
M3R_S_ROWS = [
    [0.0, 0.0, 1.0, 208.0],
    [0.422618483193, 0.906307683772, 0.0, 0.015994151],
    [-0.906307683772, 0.422618483193, 0.0, -0.086366070],
    [0.0, 0.0, 0.0, 1.0],
]
MOUNT_DECIMAL_ROWS = [
    ["0.000000000000", "0.000000000000", "1.000000000000", "0.208000000000"],
    ["0.422618483193", "0.906307683772", "0.000000000000", "0.000000000000"],
    ["-0.906307683772", "0.422618483193", "0.000000000000", "0.000000000000"],
    ["0.000000000000", "0.000000000000", "0.000000000000", "1.000000000000"],
]
PAIR_DERATE_FIELDS = [
    "centerline_hausdorff_bound_mm",
    "radius_uncertainty_bound_mm",
    "model_uncertainty_bound_mm",
    "numeric_uncertainty_bound_mm",
]
EXPECTED_COUNTERS = {
    "authoritative_scene_values_bound": 0,
    "authoritative_scene_values_required": 30,
    "stage_instances_bound": 0,
    "stage_instances_required": 3,
    "fixed_platform_design_pose_bindings": 3,
    "fixed_platform_asset_level_operational_promotions": 0,
    "active_object_count": 150,
    "asset_level_operational_count": 1,
    "system_motion_certificates_bound": 1,
    "system_motion_certificates_required": 150,
    "remaining_objects_without_system_motion_certificate": 149,
    "clearance_policy_rows_bound": 0,
    "clearance_policy_rows_required": 11166,
    "pair_queries_executed": 0,
    "pair_queries_required": 11166,
    "system_safe_pairs_certified": 0,
    "edges_certified": 0,
    "path_search_authorized": False,
    "path_search_executed": False,
    "next_stage_authorized": False,
    "release_credit": False,
}
RECOMPUTE_CHECK_IDS = frozenset({
    "R01_accepted_urdf_raw_and_lf_hashes_recomputed",
    "R02_base_link_is_unique_urdf_root_without_parent_joint",
    "R03_six_joint_q_domain_recomputed_exactly",
    "R04_full_precision_mount_decimal_spelling_consumed",
    "R05_mount_is_proper_rigid_transform",
    "R06_base_proxy_registration_is_identity_in_base_link",
    "R07_base_proxy_npz_frame_units_and_vertex_count_recomputed",
    "R08_base_proxy_mesh_bbox_matches_receipt",
    "R09_geometry_reference_radius_covers_mesh_and_brep",
    "R10_base_pose_is_q_independent_by_urdf_root_structure",
    "R11_base_pose_is_scene_independent_by_registration_and_schema",
    "R12_fifteen_boundary_samples_replay_identically",
    "R13_m3r_full_precision_frame_matches_frozen_rows",
    "R14_load_bridge_step_reopens_in_S_station_range",
})
GATE_CHECK_IDS = frozenset({
    "G01_all_28_dependency_hash_pins_match",
    "G02_option_a_consumed_without_query_authority",
    "G03_all_30_authoritative_scene_values_remain_null",
    "G04_scene_instances_remain_zero_of_three",
    "G05_current_150_object_and_11166_query_universe_not_reissued",
    "G06_fixed_platform_pose_ledger_is_three_of_three",
    "G07_load_bridge_runtime_transform_is_identity",
    "G08_load_bridge_double_transform_explicitly_forbidden",
    "G09_m3r_stage_a_uses_local_identity_then_exact_M3R_frame",
    "G10_m3r_stage_b_uses_local_identity_then_exact_M3R_frame",
    "G11_all_fixed_platform_entries_are_design_level_only",
    "G12_no_fixed_platform_operational_promotion",
    "G13_no_fixed_platform_pair_or_motion_credit",
    "G14_urdf_raw_and_lf_hashes_recomputed",
    "G15_base_link_unique_root_without_parent_joint",
    "G16_q_order_and_full_limits_recomputed_exactly",
    "G17_full_precision_execution_mount_recomputed",
    "G18_base_asset_registration_is_identity_and_operational",
    "G19_base_proxy_bbox_recomputed_from_npz",
    "G20_geometry_reference_radius_is_conservative",
    "G21_full_q_domain_zero_motion_proven_structurally",
    "G22_full_scene_schema_domain_independence_proven_without_values",
    "G23_base_global_motion_coefficients_are_exactly_six_zeroes",
    "G24_motion_certificate_contains_every_pinned_contract_output_field",
    "G25_system_motion_authority_is_exactly_one_of_150",
    "G26_pair_derate_unknowns_remain_null_and_pair_ineligible",
    "G27_clearance_and_pair_query_counts_remain_zero_of_11166",
    "G28_edge_path_search_next_and_release_remain_false_zero",
    "G29_route_c_negative_witness_is_quarantined_not_imported",
    "G30_standalone_independent_mutation_suite_is_mandatory",
})

TOP_LEVEL_KEYS = {
    POSE_NAME: frozenset({
        "accounting", "authority", "coordinate_contract", "edge_evaluation_authorized",
        "entries", "explicit_nonclaims", "generated_utc", "next_stage_authorized",
        "pair_evaluation_authorized", "path_search_authorized", "release_credit", "schema",
        "source_pins", "verdict",
    }),
    RECOMPUTE_NAME: frozenset({
        "authority", "checks", "checks_passed", "checks_total",
        "collision_registration_recompute", "edge_evaluation_authorized",
        "execution_mount_recompute", "fixed_platform_transform_recompute",
        "full_domain_zero_motion_proof", "generated_utc", "geometry_recompute",
        "next_stage_authorized", "pair_evaluation_authorized", "parent_truth_snapshot",
        "path_search_authorized", "release_credit", "schema", "source_pins",
        "urdf_graph_recompute", "verdict",
    }),
    CERT_NAME: frozenset({
        "all_values_finite_nonnegative", "all_values_finite_nonnegative_scope", "authority",
        "centerline_hausdorff_bound_mm", "contract_sha256", "deterministic_replay_payload",
        "deterministic_replay_sha256", "edge_evaluation_authorized", "evidence_sha256",
        "generated_utc", "geometry_reference_radius_mm", "global_L_mm_per_rad",
        "hidden_law_parameters", "independent_review_status", "input_binding",
        "input_binding_sha256", "maximum_claim", "model_uncertainty_bound_mm", "motion_class",
        "next_stage_authorized", "numeric_uncertainty_bound_mm", "object_id",
        "pair_derate_nullability", "pair_derating_authority_bound", "pair_eligible",
        "pair_evaluation_authorized", "path_search_authorized", "proof_domain_complete",
        "proof_method", "q_domain_lower_rad", "q_domain_upper_rad", "q_order",
        "radius_uncertainty_bound_mm", "reason_codes", "release_credit",
        "runtime_object_pose_bound", "schema", "status", "system_motion_authority_credit",
        "verdict",
    }),
    QUARANTINE_NAME: frozenset({
        "authority", "current_binding", "edge_evaluation_authorized", "generated_utc",
        "legacy_witness", "next_stage_authorized", "pair_evaluation_authorized",
        "path_search_authorized", "release_credit", "schema", "scope_controls",
        "source_pin", "verdict",
    }),
    NEGATIVE_NAME: frozenset({
        "accounting", "authority", "cases", "generated_utc", "next_stage_authorized",
        "release_credit", "schema", "verdict",
    }),
    GATE_NAME: frozenset({
        "append_only_package_complete", "authority", "base_link_motion_precert_pass", "checks",
        "checks_passed", "checks_total", "counters", "decision_rule",
        "edge_evaluation_authorized", "fixed_platform_pose_prebind_pass", "generated_utc",
        "local_artifact_pins", "manifest_policy", "maximum_claim", "next_stage_authorized",
        "pair_evaluation_authorized", "path_search_authorized", "release_credit",
        "retained_holds", "review_status", "schema", "source_pins",
        "system_collision_gate_pass", "system_path_gate_pass", "verdict",
    }),
}

CERT_FROZEN_FIELDS = {
    "authority": "ONE_REGISTERED_ASSET_GLOBAL_MOTION_BOUND_ONLY__NO_PAIR_EDGE_PATH_OR_RELEASE_AUTHORITY",
    "maximum_claim": "A_BASE_LINK_GLOBAL_ZERO_MOTION_BOUND_OVER_FULL_ACCEPTED_Q_AND_SCENE_SCHEMA_DOMAIN",
    "verdict": "A_BASE_LINK_GLOBAL_ZERO_MOTION_CERTIFIED_AS_ONE_OF_150_REGISTERED_OBJECTS__PAIR_INELIGIBLE_AND_SYSTEM_HOLD",
    "independent_review_status": "INDEPENDENT_RECOMPUTE_PASS",
    "hidden_law_parameters": None,
    "proof_method": (
        "A::base_link is the unique accepted-URDF root; its registered collision asset is rigid "
        "and identity in base_link; the full-precision spacecraft mount is constant; no "
        "scene-schema field acts on base_link. Therefore for all q in the accepted six-joint "
        "domain and all s admitted by the schema, G_base(q,s) is the same closed registered set."
    ),
    "all_values_finite_nonnegative": True,
    "all_values_finite_nonnegative_scope": "GLOBAL_L_AND_GEOMETRY_REFERENCE_RADIUS_ONLY__NULL_PAIR_DERATES_EXCLUDED",
    "reason_codes": [
        "UNIQUE_ACCEPTED_URDF_ROOT_WITH_NO_PARENT_JOINT",
        "IDENTITY_ASSET_TO_BASE_LINK_REGISTRATION",
        "CONSTANT_FULL_PRECISION_T_S_BASE_LINK_MOUNT",
        "NO_SCENE_SCHEMA_FIELD_ACTS_ON_BASE_LINK",
        "PAIR_DERATES_AND_CLEARANCE_POLICY_REMAIN_UNBOUND",
    ],
}

GATE_FROZEN_FIELDS = {
    "authority": "APPEND_ONLY_FIXED_POSE_AND_ONE_OBJECT_MOTION_PRECREDIT_ONLY__NO_PARENT_GATE_REISSUE",
    "maximum_claim": "THREE_DESIGN_LEVEL_FIXED_PLATFORM_POSES_BOUND_AND_A_BASE_LINK_GLOBAL_ZERO_MOTION_CERTIFIED_AS_EXACTLY_ONE_OF_150__NO_SCENE_PAIR_EDGE_PATH_OR_RELEASE_CREDIT",
    "review_status": "PENDING_OWNER_REVIEW",
    "decision_rule": "Authority > evidence > independent reproduction > agent opinion",
    "manifest_policy": {
        "path": MANIFEST_NAME,
        "self_excluded": True,
        "manifest_hash_not_embedded_to_avoid_circularity": True,
    },
    "retained_holds": [
        "ALL_30_OWNER_SCENE_VALUES_AND_ALL_3_SCENE_INSTANCES_UNBOUND",
        "149_OF_150_SYSTEM_OBJECT_MOTION_CERTIFICATES_UNBOUND",
        "FIXED_PLATFORM_GEOMETRY_NOT_OPERATIONALLY_PROMOTED",
        "11166_EXPLICIT_CLEARANCE_POLICY_ROWS_ABSENT",
        "11166_PAIR_QUERIES_UNEXECUTED",
        "ZERO_CONTINUOUS_EDGE_CERTIFICATES",
        "NO_PATH_SEARCH_AUTHORITY_OR_EXECUTION",
        "V9F_NEGATIVE_WITNESS_NOT_A_CURRENT_SYSTEM_PAIR_RESULT",
    ],
    "verdict": (
        "M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_30_OF_30_PASS__"
        "FIXED_PLATFORM_POSES_3_OF_3_DESIGN_LEVEL__BASE_MOTION_1_OF_150__"
        "SCENE_PAIR_EDGE_PATH_AND_RELEASE_HOLD"
    ),
}

# Independent frozen source lock: path, bytes, SHA-256, role.
SOURCE_PINS: dict[str, tuple[str, int, str, str]] = {
    "owner_selection": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/OWNER_SELECTION_RECORD_V1.json", 3318, "A88E2301B36D330D9B15AFC73C03D19838E05CD20BBC47406C39B1BF465FF2BF", "OPTION_A_BRANCH_SELECTION_ONLY"),
    "scene_schema_v2": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/M01_THREE_STAGE_SCENE_SCHEMA_V2.json", 6733, "67252BCE1259414876103EE3B6AF25ACC4A33E5A36B73AF974BD4004C285141C", "SCENE_SCHEMA_DOMAIN_WITH_ZERO_INSTANCES"),
    "scene_decision_intake": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_SCENE_DECISION_INTAKE_V1.yaml", 9508, "A75295F677FFAB8BA33D73EAADF2E596891659CDD7EE23160BDE70A0FE5EE65E", "THIRTY_EXPLICIT_NULL_OWNER_FIELDS"),
    "scene_prebind_gate": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_SCENE_AND_COLLISION_PREBIND_GATE_V1.json", 7677, "CDFADB08C3C93F9E380C41B232727E7D08750B2955411DF9E4AF894C550B7FC4", "CURRENT_ZERO_SCENE_ZERO_QUERY_HOLD"),
    "operational_asset_readiness": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_M01_SCENE_AND_COLLISION_PREBIND_V1/M01_OPERATIONAL_ASSET_READINESS_V1.csv", 113527, "974D50C1786003ED70F8494F67DFEF20ABF64F1DE103A224E9ACA34DE83A5D09", "ONE_OF_150_ASSET_LEVEL_OPERATIONAL_LEDGER"),
    "system_registry": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_SYSTEM_COLLISION_REGISTRY_V1.json", 247325, "AC975D11CC4715277E34FCFF7ABF049BC57334FD8F03AAB223BBED0877B1694F", "CURRENT_150_OBJECT_REGISTRY"),
    "pair_coverage": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_PAIR_COVERAGE_V1.csv", 1416771, "C1F64FB26D4E563EEF6BF798EE163645FE16766CC3C510552769DB7FDF97306C", "CURRENT_11166_QUERY_REQUIRED_PAIR_LEDGER"),
    "registry_gate": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/M01_SYSTEM_COLLISION_REGISTRY_GATE_V1.json", 2872, "F5E91371648756D43FF7CF6C03028FA95174428D088BAAC08254FAD8D5DCC3FF", "CURRENT_PAIR_UNIVERSE_HOLD"),
    "object_motion_contract": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/OBJECT_MOTION_BOUND_CONTRACT_V1.json", 15414, "CA1A741576A90301D77FD684DFA07882FB1AB88A00E927C1381D8709C715A5CD", "MOTION_CERTIFICATE_FIELD_AND_BOUND_CONTRACT"),
    "pair_oracle_contract": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/SYSTEM_PAIR_ORACLE_CONTRACT_V1.json", 13175, "D8B9CEE66BBD1793732F08F8E52C070B91CC5A6FCAAE56820E09E3C13BC81417", "UNSIGNED_SYSTEM_PAIR_ORACLE_CONTRACT"),
    "clearance_policy_intake": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_BINDING_INTAKE_V1/CLEARANCE_POLICY_INTAKE_V1.json", 4845, "51BF794D0DFFE8B877048EF367B7CCE54EAF3FF37BD1E5F79CB595DCC5AFFAB1", "ZERO_OF_11166_NUMERIC_CLEARANCE_ROWS"),
    "query_infrastructure_gate": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_QUERY_INFRASTRUCTURE_V1/QUERY_INFRASTRUCTURE_GATE_V1.json", 8258, "6F8E3BAF38CB69312017B76BAEAB304A84E7B956DE528356831AE378A28A6221", "ZERO_QUERY_EDGE_PATH_EXECUTION_HOLD"),
    "execution_mount": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/EXECUTION_MOUNT_BINDING_V1.json", 3477, "B7758F751E273CE21CCD5132C23F2514524DE7613E31B33646E027603B0F6653", "FULL_PRECISION_PHYSICAL_ARM_MOUNT"),
    "collision_frame_registration": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_EXECUTION_CLOSURE_V1/COLLISION_FRAME_REGISTRATION_V1.json", 28801, "3C60DBFFB2C62AB0C71482D78C8CEC63EC3AF042ABF550A324627771C9D3EA4D", "B601_COLLISION_ASSET_TO_URDF_FRAME_LEDGER"),
    "base_proxy_receipt": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/base_link_proxy_v2/BASE_LINK_OPERATIONAL_COLLISION_RECEIPT_V2.json", 7325, "5871D0AF4F9E31BF19240E4C8E885CB4715DA8936FF74BBB34F2367655BBACDA", "BASE_LINK_OPERATIONAL_PROXY_RECEIPT"),
    "base_proxy_npz": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/ODR60_OPTION_A_COLLISION_AUTHORITY_V1/base_link_proxy_v2/BASE_LINK_OPERATIONAL_COLLISION_V2.npz", 5398490, "A0C5F9FAB58A748F2F89DC7CE398684B5A8C1205426C153C6752C56226250428", "BASE_LINK_OPERATIONAL_PROXY_GEOMETRY"),
    "accepted_urdf": ("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf", 11321, "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164", "ACCEPTED_B601_KINEMATIC_TREE_RAW_BYTES"),
    "urdf_line_ending_receipt": ("20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/11_validation/URDF_LINE_ENDING_HASH_EQUIVALENCE_RECEIPT.json", 950, "DF8D4624B2E33E7DDC93613DE86C663AC230C7F76A06D875ED08037FFE37E7AF", "RAW_AND_LF_NORMALIZED_URDF_IDENTITY"),
    "physical_dynamics_bridge": ("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml", 12145, "0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C", "CONFIRMED_PHYSICAL_TO_DYNAMICS_BRIDGE_PIN_ONLY"),
    "digital_frame_tree": ("20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/01_system_architecture/DIGITAL_PROTOTYPE_FRAME_TREE_V1.yaml", 6236, "67293323A45237FB9B415871A4160732EFB156DE74776C9E11ABA9C4202134CA", "M3R_LOCAL_FULL_PRECISION_S_FRAME"),
    "load_bridge_datums": ("20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp1_load_bridge/LOAD_BRIDGE_DATUMS_V1.yaml", 9037, "0F9B413E7B6CD451E2724AD25CA4DA41E52E02C86F1D2874460274EADBAA47A2", "LOAD_BRIDGE_DESIGN_DATUMS_CANDIDATE"),
    "load_bridge_receipt": ("20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp1_load_bridge/FITUP_AND_FRAME_RECEIPT_V1.json", 10133, "4B9114420059AA885F7A3C7CF437E8219F26F7D65E2E1F68F773C91214E426B7", "LOAD_BRIDGE_S_COORDINATE_REOPEN_RECEIPT"),
    "load_bridge_step": ("20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp1_load_bridge/LOAD_BRIDGE_CANDIDATE_V1.step", 24855, "545FE62ADE0E4891FCC84179D18F63B2A6C77F19AD1C96723B3C7208EA13221B", "LOAD_BRIDGE_DESIGN_LEVEL_CANDIDATE_STEP"),
    "m3r_assembly": ("20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/02_interfaces/M3R_INTERFACE_ASSEMBLY_V2.yaml", 4810, "B9A7AE3AC40B00036FC1FCB85C62D153A67500FCCFEC5BB797BC7B4E05A21D7A", "M3R_STAGE_LOCAL_PLACEMENT_LEDGER"),
    "m3r_geometry_validation": ("20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/M3R_INTERFACE_ASSEMBLY_V2_GEOMETRY_VALIDATION.json", 2796, "AD35D83115FD7B8BD2E170C97CB9E212F14BED4C6FAFEF95F266905D42E76180", "M3R_TWO_ONE_SOLID_DESIGN_GEOMETRY_RECEIPT"),
    "m3r_stage_a_step": ("20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/M3R_STAGE_A_REVB_WORKING.step", 35879, "359E304879C254BE54450AA9BAB4C614308CE2C9CD47CE1F79A741722098D36C", "M3R_STAGE_A_DESIGN_LEVEL_STEP"),
    "m3r_stage_b_step": ("20_engineering/F3R2_MECHANICAL_DETAILED_DESIGN_V1/06_parameterized_parts/m3r/M3R_STAGE_B_REVB2_WORKING.step", 37779, "44BED33AEE41CFD170E744BBEEB2BD0B10BBD649C913ECA90D16FC4840A1126B", "M3R_STAGE_B_DESIGN_LEVEL_STEP"),
    "route_c_negative_witness": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_V9F_MANDATORY_M01_FALSIFIER_GATE.json", 7653, "09C3199BD9824DFDBB9782C20BE200F31760F44A89EF68D16F32D0E213F191A0", "LEGACY_NEGATIVE_ONLY_WITNESS_NOT_SYSTEM_PAIR_RESULT"),
}


class ValidationError(RuntimeError):
    def __init__(self, code: str, detail: str | None = None):
        self.code = code
        self.detail = detail
        super().__init__(code if detail is None else f"{code}::{detail}")


def reject_if(condition: bool, code: str, detail: str | None = None) -> None:
    if condition:
        raise ValidationError(code, detail)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256_bytes(payload.encode("utf-8"))


def emitted_artifact_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    return sha256_bytes(payload.encode("utf-8"))


def is_exact_int(value: Any) -> bool:
    return type(value) is int


def is_finite_number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


def require_exact_int(value: Any, expected: int, code: str) -> None:
    reject_if(type(value) is not int or value != expected, code)


def require_finite_number(value: Any, code: str) -> None:
    reject_if(not is_finite_number(value), code)


def exact_typed_equal(actual: Any, expected: Any) -> bool:
    """Value equality with bool/int separation and finite continuous values."""
    if type(expected) is bool:
        return type(actual) is bool and actual is expected
    if type(expected) is int:
        return type(actual) is int and actual == expected
    if type(expected) is float:
        return is_finite_number(actual) and float(actual) == expected
    if expected is None or isinstance(expected, str):
        return type(actual) is type(expected) and actual == expected
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            exact_typed_equal(a, e) for a, e in zip(actual, expected, strict=True)
        )
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual) == set(expected) and all(
            exact_typed_equal(actual[key], expected[key]) for key in expected
        )
    return type(actual) is type(expected) and actual == expected


def _strict_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        reject_if(key in result, "DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def _reject_json_constant(token: str) -> Any:
    raise ValidationError("NONFINITE_JSON_CONSTANT", token)


def _strict_json_float(token: str) -> float:
    value = float(token)
    reject_if(not math.isfinite(value), "NONFINITE_JSON_NUMBER", token)
    return value


def ensure_finite_tree(value: Any) -> None:
    if isinstance(value, float):
        reject_if(not math.isfinite(value), "NONFINITE_NUMBER")
    elif isinstance(value, dict):
        for child in value.values():
            ensure_finite_tree(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            ensure_finite_tree(child)


def strict_json_text(text: str) -> Any:
    try:
        value = json.loads(text, object_pairs_hook=_strict_pairs, parse_constant=_reject_json_constant, parse_float=_strict_json_float)
    except ValidationError:
        raise
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValidationError("JSON_PARSE_ERROR", str(exc)) from exc
    ensure_finite_tree(value)
    return value


def read_json(path: Path) -> dict[str, Any]:
    value = strict_json_text(path.read_text(encoding="utf-8"))
    reject_if(not isinstance(value, dict), "JSON_ROOT_NOT_OBJECT", path.as_posix())
    return value


class _StrictYamlLoader(yaml.SafeLoader):
    pass


def _yaml_mapping(loader: _StrictYamlLoader, node: yaml.Node, deep: bool = False) -> dict[Any, Any]:
    result: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        reject_if(key in result, "DUPLICATE_YAML_KEY", str(key))
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_StrictYamlLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _yaml_mapping)


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=_StrictYamlLoader)
    except ValidationError:
        raise
    except yaml.YAMLError as exc:
        raise ValidationError("YAML_PARSE_ERROR", str(exc)) from exc
    reject_if(not isinstance(value, dict), "YAML_ROOT_NOT_OBJECT", path.as_posix())
    ensure_finite_tree(value)
    return value


def read_csv_strict(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    reader = csv.reader(io.StringIO(path.read_text(encoding="utf-8"), newline=""))
    try:
        header = next(reader)
    except StopIteration as exc:
        raise ValidationError("CSV_EMPTY", path.as_posix()) from exc
    reject_if(len(header) != len(set(header)), "CSV_DUPLICATE_HEADER", path.as_posix())
    rows: list[dict[str, str]] = []
    for line_number, values in enumerate(reader, start=2):
        reject_if(len(values) != len(header), "CSV_ROW_WIDTH_DRIFT", f"{path}:{line_number}")
        rows.append(dict(zip(header, values, strict=True)))
    return header, rows


def load_documents(base: Path = HERE) -> dict[str, dict[str, Any]]:
    documents: dict[str, dict[str, Any]] = {}
    for name in JSON_ARTIFACT_NAMES:
        path = base / name
        reject_if(not path.is_file(), "REQUIRED_ARTIFACT_MISSING", name)
        documents[name] = read_json(path)
    return documents


def expected_source_pin_block(ids: set[str] | frozenset[str] | None = None) -> dict[str, Any]:
    keys = SOURCE_PINS.keys() if ids is None else ids
    return {
        key: {"path": SOURCE_PINS[key][0], "bytes": SOURCE_PINS[key][1], "sha256": SOURCE_PINS[key][2], "role": SOURCE_PINS[key][3]}
        for key in keys
    }


def verify_source_lock(repo_root: Path) -> dict[str, Path]:
    reject_if(len(SOURCE_PINS) != 28, "SOURCE_LOCK_CARDINALITY_DRIFT")
    paths: dict[str, Path] = {}
    for source_id, (relative, expected_bytes, expected_hash, _role) in SOURCE_PINS.items():
        path = repo_root / relative
        reject_if(not path.is_file(), "SOURCE_MISSING", source_id)
        reject_if(path.stat().st_size != expected_bytes, "SOURCE_BYTE_COUNT_DRIFT", source_id)
        reject_if(sha256_file(path) != expected_hash, "SOURCE_HASH_DRIFT", source_id)
        paths[source_id] = path
    return paths


def _matrix_float(rows: Any, code: str) -> list[list[float]]:
    reject_if(not isinstance(rows, list) or len(rows) != 4, code)
    reject_if(any(not isinstance(row, list) or len(row) != 4 for row in rows), code)
    reject_if(any(not is_finite_number(value) for row in rows for value in row), code)
    converted = [[float(value) for value in row] for row in rows]
    reject_if(not all(math.isfinite(value) for row in converted for value in row), "NONFINITE_NUMBER")
    return converted


def _matrix_equal(a: Any, b: Any) -> bool:
    try:
        return _matrix_float(a, "MATRIX_SHAPE_DRIFT") == _matrix_float(b, "MATRIX_SHAPE_DRIFT")
    except (TypeError, ValueError, ValidationError):
        return False


def independent_parent_truth(paths: dict[str, Path]) -> dict[str, Any]:
    owner = read_json(paths["owner_selection"])
    schema = read_json(paths["scene_schema_v2"])
    scene = read_yaml(paths["scene_decision_intake"])
    prebind = read_json(paths["scene_prebind_gate"])
    registry = read_json(paths["system_registry"])
    registry_gate = read_json(paths["registry_gate"])
    motion = read_json(paths["object_motion_contract"])
    oracle = read_json(paths["pair_oracle_contract"])
    clearance = read_json(paths["clearance_policy_intake"])
    query = read_json(paths["query_infrastructure_gate"])
    witness = read_json(paths["route_c_negative_witness"])

    selection = owner.get("selection", {})
    reject_if(selection.get("selected_option") != "A" or selection.get("option_a_selected") is not True, "OWNER_OPTION_A_SELECTION_DRIFT")
    effect = owner.get("execution_effect", {})
    authority_fields = (
        "pair_evaluation_authorized_by_selection_alone",
        "edge_evaluation_authorized_by_selection_alone",
        "path_search_authorized_by_selection_alone",
        "release_credit",
    )
    reject_if(any(effect.get(field) is not False for field in authority_fields), "OWNER_SELECTION_AUTHORITY_OVERCLAIM")

    stages = scene.get("stages")
    reject_if(not isinstance(stages, list) or len(stages) != 3, "SCENE_INTAKE_STAGE_STRUCTURE_DRIFT")
    values: list[Any] = []
    for stage in stages:
        block = stage.get("values") if isinstance(stage, dict) else None
        reject_if(not isinstance(block, dict) or len(block) != 10, "SCENE_INTAKE_FIELD_STRUCTURE_DRIFT")
        values.extend(block.values())
    reject_if(len(values) != 30 or any(value is not None for value in values), "AUTHORITATIVE_SCENE_VALUES_NOT_EXACTLY_30_NULLS")
    accounting = scene.get("authoritative_instance_accounting", {})
    require_exact_int(accounting.get("authoritative_field_values_bound"), 0, "SCENE_AUTHORITY_COUNT_CHANGED")
    require_exact_int(accounting.get("stage_instances_bound"), 0, "SCENE_INSTANCE_COUNT_CHANGED")
    require_exact_int(accounting.get("stage_instances_required"), 3, "SCENE_INSTANCE_COUNT_CHANGED")
    reject_if(accounting.get("active_object_universe_bound_per_stage") is not False or accounting.get("active_pair_universe_bound_per_stage") is not False, "STAGE_UNIVERSE_UNEXPECTEDLY_BOUND")

    current = schema.get("current_instances", {})
    require_exact_int(current.get("stage_instances_bound"), 0, "SCHEMA_INSTANCE_COUNT_CHANGED")
    require_exact_int(current.get("stage_instances_required"), 3, "SCHEMA_INSTANCE_COUNT_CHANGED")
    q_contract = schema.get("schema_contract", {}).get("continuous_q_contract", {})
    reject_if(q_contract.get("candidate_path_bound") is not False or q_contract.get("candidate_path_sha256") is not None, "CANDIDATE_PATH_UNEXPECTEDLY_BOUND")
    reject_if(q_contract.get("joint_order") != Q_ORDER, "SCENE_SCHEMA_Q_ORDER_DRIFT")
    require_exact_int(prebind.get("checks_total"), 18, "PARENT_PREBIND_GATE_DRIFT")
    require_exact_int(prebind.get("checks_passed"), 18, "PARENT_PREBIND_GATE_DRIFT")
    reject_if(not all(value is True for value in prebind.get("checks", {}).values()), "PARENT_PREBIND_GATE_DRIFT")

    objects = registry.get("objects")
    reject_if(not isinstance(objects, list) or len(objects) != 150, "ACTIVE_OBJECT_COUNT_CHANGED")
    object_ids = [row.get("object_id") for row in objects if isinstance(row, dict)]
    reject_if(len(object_ids) != 150 or len(set(object_ids)) != 150, "ACTIVE_OBJECT_IDS_NOT_UNIQUE")
    base = next((row for row in objects if row.get("object_id") == "A::base_link"), None)
    reject_if(base is None, "BASE_OBJECT_MISSING_FROM_REGISTRY")
    base_proxy = base.get("geometry", {}).get("operational_proxy", {}).get("canonical_machine_authority", {})
    reject_if(base_proxy.get("sha256") != SOURCE_PINS["base_proxy_npz"][2] or base_proxy.get("frame") != "base_link" or base_proxy.get("units") != "m", "REGISTRY_BASE_PROXY_BINDING_DRIFT")

    _, readiness = read_csv_strict(paths["operational_asset_readiness"])
    active_rows = [row for row in readiness if row.get("row_class") == "ACTIVE_OBJECT"]
    operational = [row for row in active_rows if row.get("operational_authority") == "true"]
    reject_if(len(active_rows) != 150 or len({row["id"] for row in active_rows}) != 150, "OPERATIONAL_READINESS_COUNT_DRIFT")
    reject_if([row.get("id") for row in operational] != ["A::base_link"], "OPERATIONAL_ASSET_LEDGER_CHANGED")

    _, pairs = read_csv_strict(paths["pair_coverage"])
    indices = [row.get("pair_index") for row in pairs]
    reject_if(len(pairs) != 11175 or len(set(indices)) != 11175, "PAIR_COVERAGE_COUNT_OR_UNIQUENESS_CHANGED")
    status_counts = {status: sum(row.get("status") == status for row in pairs) for status in ("EXCEPTED", "UNASSESSED_FAIL_CLOSED")}
    reject_if(status_counts != {"EXCEPTED": 9, "UNASSESSED_FAIL_CLOSED": 11166}, "PAIR_COVERAGE_STATUS_CHANGED")
    emitted_status_counts = registry_gate.get("pair_coverage", {}).get("status_counts")
    reject_if(emitted_status_counts != status_counts, "PAIR_GATE_AND_LEDGER_DISAGREE")
    reject_if(not isinstance(emitted_status_counts, dict) or any(type(value) is not int for value in emitted_status_counts.values()), "PAIR_GATE_COUNT_TYPE_DRIFT")

    require_exact_int(motion.get("current_readiness", {}).get("system_certified_object_motion_bound_count"), 0, "PARENT_MOTION_COUNT_NO_LONGER_ZERO")
    require_exact_int(clearance.get("policy_rows_emitted"), 0, "CLEARANCE_POLICY_NO_LONGER_ZERO_UNBOUND")
    reject_if(clearance.get("clearance_policy_sha256") is not None, "CLEARANCE_POLICY_NO_LONGER_ZERO_UNBOUND")
    require_exact_int(oracle.get("current_readiness", {}).get("pair_queries_executed"), 0, "PAIR_ORACLE_QUERY_COUNT_CHANGED")
    query_state = query.get("system_collision_state", {})
    require_exact_int(query_state.get("unassessed_fail_closed_pair_count"), 11166, "QUERY_INFRASTRUCTURE_EXECUTION_STATE_CHANGED")
    reject_if(query_state.get("complete_system_collision_pass") is not False, "QUERY_INFRASTRUCTURE_EXECUTION_STATE_CHANGED")
    reject_if(query.get("system_pair_evaluation_authorized") is not False or query.get("path_search_executed") is not False, "QUERY_INFRASTRUCTURE_AUTHORITY_CHANGED")
    for document in (prebind, schema, query):
        reject_if(document.get("path_search_authorized") is True or document.get("next_stage_authorized") is True or document.get("release_credit") is True, "PARENT_AUTHORITY_PROMOTED")

    collision = witness.get("witness", {}).get("collision", {})
    reject_if(not is_finite_number(collision.get("raw_clearance_mm")) or collision.get("raw_clearance_mm") >= 0.0 or collision.get("raw_physical_penetration") is not True, "ROUTE_C_NEGATIVE_WITNESS_CHANGED")
    reject_if(witness.get("scope_boundary", {}).get("architecture_infeasibility_proven") is not False, "ROUTE_C_WITNESS_SCOPE_BROADENED")
    return {
        "option_a_selected": True,
        "authoritative_scene_values_bound": 0,
        "authoritative_scene_values_required": 30,
        "stage_instances_bound": 0,
        "stage_instances_required": 3,
        "stage_object_universe_hashes_bound": 0,
        "stage_pair_universe_hashes_bound": 0,
        "active_object_count": 150,
        "asset_level_operational_count": 1,
        "parent_system_motion_certificate_count": 0,
        "query_required_pair_count": 11166,
        "clearance_policy_rows_bound": 0,
        "pair_queries_executed": 0,
        "edges_certified": 0,
        "path_search_authorized": False,
        "path_search_executed": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }


def independent_urdf_recompute(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SOURCE_PINS["accepted_urdf"][0]
    raw = path.read_bytes()
    try:
        robot = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValidationError("URDF_XML_PARSE_ERROR", str(exc)) from exc
    reject_if(robot.tag != "robot", "URDF_ROOT_TAG_INVALID")
    links = [node.attrib.get("name") for node in robot.findall("link")]
    reject_if(any(not name for name in links) or len(links) != len(set(links)), "URDF_LINK_SET_INVALID")
    joints: dict[str, dict[str, Any]] = {}
    children: set[str] = set()
    for node in robot.findall("joint"):
        name = node.attrib.get("name")
        reject_if(not name or name in joints, "URDF_JOINT_SET_INVALID")
        parent = node.find("parent")
        child = node.find("child")
        reject_if(parent is None or child is None, "URDF_JOINT_PARENT_CHILD_MISSING", str(name))
        parent_name = parent.attrib.get("link")
        child_name = child.attrib.get("link")
        reject_if(parent_name not in links or child_name not in links, "URDF_JOINT_LINK_REFERENCE_INVALID", str(name))
        reject_if(child_name in children, "URDF_LINK_HAS_MULTIPLE_PARENTS", str(child_name))
        children.add(str(child_name))
        limit = node.find("limit")
        joints[str(name)] = {
            "type": node.attrib.get("type"),
            "child": child_name,
            "lower": None if limit is None or "lower" not in limit.attrib else float(limit.attrib["lower"]),
            "upper": None if limit is None or "upper" not in limit.attrib else float(limit.attrib["upper"]),
        }
    roots = sorted(set(links) - children)
    reject_if(roots != ["base_link"], "BASE_LINK_NOT_UNIQUE_URDF_ROOT")
    reject_if(any(joint.get("child") == "base_link" for joint in joints.values()), "BASE_LINK_HAS_PARENT_JOINT")
    for name in Q_ORDER:
        reject_if(name not in joints, "URDF_REQUIRED_JOINT_MISSING", name)
        reject_if(joints[name]["type"] != "revolute", "URDF_JOINT_TYPE_DRIFT", name)
    lower = [joints[name]["lower"] for name in Q_ORDER]
    upper = [joints[name]["upper"] for name in Q_ORDER]
    reject_if(lower != Q_LOWER, "Q_LOWER_DOMAIN_DRIFT")
    reject_if(upper != Q_UPPER, "Q_UPPER_DOMAIN_DRIFT")
    normalized = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return {
        "robot_name": robot.attrib.get("name"),
        "link_count": len(links),
        "joint_count": len(joints),
        "root_links": roots,
        "base_link_parent_joint_count": 0,
        "q_order": Q_ORDER,
        "q_domain_lower_rad": lower,
        "q_domain_upper_rad": upper,
        "raw_bytes_sha256": sha256_bytes(raw),
        "lf_normalized_sha256": sha256_bytes(normalized),
    }


def independent_mount_recompute(paths: dict[str, Path]) -> dict[str, Any]:
    mount = read_json(paths["execution_mount"])
    binding = mount.get("binding")
    expected_binding = {
        "frame_name": "T_S_B601_ARM_BASE_PHYSICAL",
        "parent_frame": "spacecraft_bus_S",
        "child_frame": "base_link",
        "matrix_semantics": "p_parent=R_parent_child*p_child+t_parent_child",
        "translation_unit": "m",
        "rotation_unit": "dimensionless",
        "canonical_decimal_places": 12,
        "canonical_matrix_decimal_strings": MOUNT_DECIMAL_ROWS,
    }
    reject_if(binding != expected_binding, "EXECUTION_MOUNT_BINDING_DRIFT")
    try:
        roundtrip = [[format(Decimal(value), ".12f") for value in row] for row in MOUNT_DECIMAL_ROWS]
    except InvalidOperation as exc:
        raise ValidationError("EXECUTION_MOUNT_DECIMAL_PARSE_FAILED") from exc
    reject_if(roundtrip != MOUNT_DECIMAL_ROWS, "EXECUTION_MOUNT_DECIMAL_SPELLING_NOT_CANONICAL")
    matrix = np.asarray([[float(value) for value in row] for row in MOUNT_DECIMAL_ROWS], dtype=np.float64)
    rotation = matrix[:3, :3]
    metrics = {
        "orthonormal_max_abs_residual": float(np.max(np.abs(rotation.T @ rotation - np.eye(3)))),
        "determinant": float(np.linalg.det(rotation)),
        "homogeneous_bottom_row_max_abs_residual": float(np.max(np.abs(matrix[3, :] - np.asarray([0.0, 0.0, 0.0, 1.0])))),
    }
    reject_if(metrics["orthonormal_max_abs_residual"] > 1.0e-12 or abs(metrics["determinant"] - 1.0) > 1.0e-12 or metrics["homogeneous_bottom_row_max_abs_residual"] != 0.0, "EXECUTION_MOUNT_NOT_RIGID")
    spelling = mount.get("spelling_policy")
    reject_if(canonical_digest(binding) != mount.get("canonical_binding_payload_sha256"), "EXECUTION_MOUNT_CANONICAL_HASH_MISMATCH")
    reject_if(mount.get("system_mount_binding_sha256") != mount.get("canonical_binding_payload_sha256"), "EXECUTION_MOUNT_SYSTEM_HASH_MISMATCH")
    reject_if(not isinstance(spelling, dict) or canonical_digest(spelling) != mount.get("runtime_mount_numeric_spelling_policy_sha256"), "EXECUTION_MOUNT_SPELLING_HASH_MISMATCH")
    return {
        "canonical_decimal_strings": MOUNT_DECIMAL_ROWS,
        "T_S_base_link_rows_m": matrix.tolist(),
        "matrix_semantics": binding["matrix_semantics"],
        "canonical_payload_sha256": canonical_digest(binding),
        "runtime_mount_numeric_spelling_policy_sha256": canonical_digest(spelling),
        "metrics": metrics,
    }


def independent_registration_recompute(paths: dict[str, Path]) -> dict[str, Any]:
    document = read_json(paths["collision_frame_registration"])
    matches = [row for row in document.get("registrations", []) if row.get("object_id") == "A::base_link"]
    reject_if(len(matches) != 1, "BASE_REGISTRATION_COUNT_DRIFT")
    row = matches[0]
    transform = row.get("T_registration_frame_asset_storage", {})
    reject_if(transform.get("rotation") != "IDENTITY" or transform.get("translation") != [0.0, 0.0, 0.0] or transform.get("translation_unit") != "m", "BASE_LINK_COLLISION_REGISTRATION_NOT_IDENTITY")
    reject_if(row.get("asset_storage_frame") != "base_link" or row.get("accepted_urdf_registration_frame") != "base_link", "BASE_LINK_REGISTRATION_FRAME_CHANGED")
    reject_if(row.get("operational_narrowphase_promoted") is not True, "BASE_LINK_OPERATIONAL_PROXY_LOST")
    motion = row.get("motion_registration", {})
    reject_if(motion.get("state_variable") is not None or motion.get("state_value_m") is not None or motion.get("type") != "RIGID_LINK_LOCAL", "BASE_LINK_UNEXPECTED_SCENE_STATE_VARIABLE")
    reject_if(row.get("runtime_object_pose_bound") is not False, "PARENT_BASE_RUNTIME_POSE_ALREADY_BOUND")
    return {
        "object_id": "A::base_link",
        "asset_storage_frame": "base_link",
        "accepted_urdf_registration_frame": "base_link",
        "T_registration_frame_asset_storage_rows": IDENTITY_4,
        "operational_narrowphase_promoted": True,
        "scene_state_variable": None,
    }


def independent_geometry_recompute(repo_root: Path) -> dict[str, Any]:
    npz_path = repo_root / SOURCE_PINS["base_proxy_npz"][0]
    receipt = read_json(repo_root / SOURCE_PINS["base_proxy_receipt"][0])
    with np.load(npz_path, allow_pickle=False) as archive:
        reject_if(set(archive.files) != {"faces", "frame", "solid_ids", "units", "vertices_m"}, "BASE_NPZ_KEY_SET_DRIFT")
        vertices_m = np.asarray(archive["vertices_m"], dtype=np.float64)
        faces = np.asarray(archive["faces"])
        reject_if(vertices_m.shape != (103851, 3), "BASE_NPZ_VERTEX_SHAPE_DRIFT")
        reject_if(faces.ndim != 2 or faces.shape[1] != 3, "BASE_NPZ_FACE_SHAPE_DRIFT")
        reject_if(not np.isfinite(vertices_m).all(), "BASE_NPZ_NONFINITE_VERTEX")
        reject_if(str(archive["frame"].item()) != "base_link", "BASE_NPZ_FRAME_DRIFT")
        reject_if(str(archive["units"].item()) != "meter", "BASE_NPZ_UNIT_DRIFT")
        vertices_mm = vertices_m * np.float64(1000.0)
    bbox = np.vstack((vertices_mm.min(axis=0), vertices_mm.max(axis=0)))
    mesh_vertex_radius = float(np.linalg.norm(vertices_mm, axis=1).max())
    mesh_bbox_radius = float(np.linalg.norm(np.maximum(np.abs(bbox[0, :]), np.abs(bbox[1, :]))))
    receipt_bbox = np.asarray(receipt.get("mesh", {}).get("bbox_mm"), dtype=np.float64)
    reject_if(receipt_bbox.shape != (2, 3) or not np.isfinite(receipt_bbox).all(), "BASE_RECEIPT_MESH_BBOX_INVALID")
    residual = float(np.max(np.abs(bbox - receipt_bbox)))
    reject_if(residual > 1.0e-12, "BASE_BBOX_RECEIPT_MISMATCH")
    brep_bbox = np.asarray(receipt.get("brep", {}).get("tight_bbox_mm"), dtype=np.float64)
    reject_if(brep_bbox.shape != (2, 3) or not np.isfinite(brep_bbox).all(), "BASE_RECEIPT_BREP_BBOX_INVALID")
    brep_radius = float(np.linalg.norm(np.maximum(np.abs(brep_bbox[0, :]), np.abs(brep_bbox[1, :]))))
    radius = max(mesh_vertex_radius, mesh_bbox_radius, brep_radius)
    return {
        "bbox_mm": bbox.tolist(),
        "mesh_bbox_mm": bbox.tolist(),
        "mesh_vertex_radius_mm": mesh_vertex_radius,
        "mesh_max_vertex_radius_mm": mesh_vertex_radius,
        "mesh_bbox_corner_radius_mm": mesh_bbox_radius,
        "brep_bbox_mm": brep_bbox.tolist(),
        "brep_bbox_corner_radius_mm": brep_radius,
        "conservative_radius_mm": radius,
        "geometry_reference_radius_mm": radius,
        "receipt_residual_mm": residual,
        "npz_vertex_count": int(vertices_m.shape[0]),
        "npz_face_count": int(faces.shape[0]),
    }


def independent_fixed_platform_recompute(paths: dict[str, Path]) -> dict[str, Any]:
    frame_tree = read_yaml(paths["digital_frame_tree"])
    m3r_rows = _matrix_float(frame_tree.get("frames", {}).get("M3R_LOCAL", {}).get("T_S_child_rows"), "M3R_FRAME_MATRIX_INVALID")
    reject_if(m3r_rows != M3R_S_ROWS, "M3R_LOCAL_FRAME_DRIFT")
    load_receipt = read_json(paths["load_bridge_receipt"])
    load_rows = _matrix_float(load_receipt.get("frame_consistency", {}).get("T_S_LOAD_BRIDGE_LOCAL_rows"), "LOAD_BRIDGE_DATUM_MATRIX_INVALID")
    reject_if(load_rows != M3R_S_ROWS, "LOAD_BRIDGE_DATUM_AND_M3R_FRAME_DISAGREE")
    load_bbox = load_receipt.get("step_cold_reopen", {}).get("bounding_box_mm")
    reject_if(not isinstance(load_bbox, list) or len(load_bbox) != 6 or load_bbox[0] != 185.25 or load_bbox[3] != 196.0, "LOAD_BRIDGE_STEP_NOT_AUTHORED_IN_S")
    assembly = read_yaml(paths["m3r_assembly"])
    components = {row.get("part_number"): row for row in assembly.get("components", [])}
    validation = read_json(paths["m3r_geometry_validation"])
    receipt_rows = {row.get("part"): row for row in validation.get("parts", [])}
    expected = {
        "STAGE_A": ("M3R_STAGE_A_INTERFACE_RING_REVB_WORKING", "m3r_stage_a_step"),
        "STAGE_B": ("M3R_STAGE_B_LOAD_ADAPTER_REVB2_WORKING", "m3r_stage_b_step"),
    }
    derived: dict[str, Any] = {}
    for validation_id, (part_number, source_id) in expected.items():
        component = components.get(part_number)
        receipt = receipt_rows.get(validation_id)
        reject_if(component is None or receipt is None, "M3R_PART_EVIDENCE_MISSING", part_number)
        placement = component.get("placement", {})
        reject_if(placement.get("translation_xyz_mm") != [0.0, 0.0, 0.0] or placement.get("rotation_xyz_deg") != [0.0, 0.0, 0.0] or placement.get("classification") != "FROZEN", "M3R_LOCAL_PLACEMENT_DRIFT", part_number)
        reject_if(component.get("STEP", {}).get("sha256_generation_instance") != SOURCE_PINS[source_id][2], "M3R_COMPONENT_STEP_HASH_DRIFT", part_number)
        reject_if(receipt.get("working_sha256") != SOURCE_PINS[source_id][2] or receipt.get("working_solid_count") != 1 or receipt.get("geometrically_equivalent") is not True, "M3R_GEOMETRY_RECEIPT_DRIFT", part_number)
        bounds = receipt.get("working_bounds_mm")
        reject_if(not isinstance(bounds, list) or len(bounds) != 6, "M3R_BOUNDS_DRIFT", part_number)
        derived[validation_id] = {"path": SOURCE_PINS[source_id][0], "sha256": SOURCE_PINS[source_id][2], "bbox": [bounds[:3], bounds[3:]], "solid_count": 1}
    return {"m3r_rows": m3r_rows, "load_rows": load_rows, "load_bbox": load_bbox, "parts": derived}


def build_reference(repo_root: Path) -> dict[str, Any]:
    paths = verify_source_lock(repo_root)
    parent = independent_parent_truth(paths)
    urdf = independent_urdf_recompute(repo_root)
    reject_if(urdf["raw_bytes_sha256"] != SOURCE_PINS["accepted_urdf"][2], "URDF_RAW_HASH_RECOMPUTE_MISMATCH")
    reject_if(urdf["lf_normalized_sha256"] != "408147DDC9CC0BBA0FACBF864C559A54D1712262703BA41251514A4303B5A3A4", "URDF_LF_HASH_RECOMPUTE_MISMATCH")
    schema = read_json(paths["scene_schema_v2"])
    reject_if("base_link_pose" in schema.get("field_types", {}) or "base_link_transform" in schema.get("field_types", {}), "BASE_LINK_SCENE_CONTROL_FIELD_PRESENT")
    return {
        "paths": paths,
        "parent": parent,
        "urdf": urdf,
        "mount": independent_mount_recompute(paths),
        "registration": independent_registration_recompute(paths),
        "geometry": independent_geometry_recompute(repo_root),
        "fixed": independent_fixed_platform_recompute(paths),
        "motion_contract": read_json(paths["object_motion_contract"]),
    }


def _expected_samples(mount_rows: list[list[float]]) -> list[dict[str, Any]]:
    lower = np.asarray(Q_LOWER, dtype=np.float64)
    upper = np.asarray(Q_UPPER, dtype=np.float64)
    midpoint = (lower + upper) / np.float64(2.0)
    vectors: list[list[float]] = [lower.tolist(), midpoint.tolist(), upper.tolist()]
    for index in range(6):
        at_lower = midpoint.copy()
        at_upper = midpoint.copy()
        at_lower[index] = lower[index]
        at_upper[index] = upper[index]
        vectors.extend((at_lower.tolist(), at_upper.tolist()))
    return [
        {"sample_id": f"Q{index:02d}", "q_rad": vector, "T_S_base_link_rows_m": mount_rows, "max_abs_residual_vs_canonical_mount": 0.0}
        for index, vector in enumerate(vectors)
    ]


def _require_false_authority(document: dict[str, Any], prefix: str) -> None:
    fields = ("pair_evaluation_authorized", "edge_evaluation_authorized", "path_search_authorized", "next_stage_authorized", "release_credit")
    for field in fields:
        reject_if(document.get(field) is not False, f"{prefix}_AUTHORITY_MUST_BE_FALSE", field)


def validate_candidate_documents(
    repo_root: Path,
    documents: dict[str, dict[str, Any]],
    *,
    validate_local_hashes: bool = True,
    validate_declared_negative: bool = True,
    reference: dict[str, Any] | None = None,
    candidate_local_hashes: dict[str, str] | None = None,
) -> dict[str, Any]:
    reject_if(set(documents) != set(JSON_ARTIFACT_NAMES), "ARTIFACT_DOCUMENT_SET_DRIFT")
    ensure_finite_tree(documents)
    for artifact_name, expected_keys in TOP_LEVEL_KEYS.items():
        reject_if(
            set(documents[artifact_name]) != expected_keys,
            f"TOP_LEVEL_KEY_SET_DRIFT::{artifact_name}",
        )
    ref = build_reference(repo_root) if reference is None else reference
    pose = documents[POSE_NAME]
    recompute = documents[RECOMPUTE_NAME]
    cert = documents[CERT_NAME]
    quarantine = documents[QUARANTINE_NAME]
    negative = documents[NEGATIVE_NAME]
    gate = documents[GATE_NAME]

    pose_pin_ids = frozenset({
        "system_registry", "digital_frame_tree", "load_bridge_datums", "load_bridge_receipt",
        "load_bridge_step", "m3r_assembly", "m3r_geometry_validation", "m3r_stage_a_step",
        "m3r_stage_b_step",
    })
    reject_if(not exact_typed_equal(pose.get("source_pins"), expected_source_pin_block(pose_pin_ids)), "POSE_SOURCE_PIN_BLOCK_DRIFT")
    reject_if(pose.get("schema") != "M01_FIXED_PLATFORM_POSE_BINDING_V1", "POSE_SCHEMA_DRIFT")
    _require_false_authority(pose, "POSE")
    expected_pose_accounting = {
        "asset_level_operational_promotions": 0,
        "design_level_pose_entries_bound": 3,
        "pair_eligible_entries": 0,
        "pair_queries_executed": 0,
        "required_fixed_platform_pose_entries": 3,
        "system_motion_authority_promotions": 0,
    }
    reject_if(not exact_typed_equal(pose.get("accounting"), expected_pose_accounting), "POSE_ACCOUNTING_DRIFT")
    entries = pose.get("entries")
    reject_if(not isinstance(entries, list) or len(entries) != 3, "FIXED_POSE_ENTRY_COUNT_NOT_THREE")
    ids = [row.get("object_id") for row in entries if isinstance(row, dict)]
    reject_if(ids != ["F::LOAD_BRIDGE", "F::M3R_STAGE_A", "F::M3R_STAGE_B"] or len(set(ids)) != 3, "FIXED_POSE_OBJECT_SET_DRIFT")
    by_id = {row["object_id"]: row for row in entries}
    load = by_id["F::LOAD_BRIDGE"]
    reject_if(not _matrix_equal(load.get("T_S_asset_rows"), IDENTITY_4), "LOAD_BRIDGE_RUNTIME_TRANSFORM_NOT_IDENTITY")
    reject_if(load.get("double_transform_forbidden") is not True or load.get("local_design_datum", {}).get("runtime_application_to_step_asset") is not False, "LOAD_BRIDGE_DOUBLE_TRANSFORM_GUARD_MISSING")
    load_asset = load.get("geometry_asset", {})
    reject_if(
        load_asset.get("asset_storage_frame") != "S"
        or load_asset.get("path") != SOURCE_PINS["load_bridge_step"][0]
        or load_asset.get("sha256") != SOURCE_PINS["load_bridge_step"][2]
        or not exact_typed_equal(load_asset.get("step_reopen_bbox_S_mm"), ref["fixed"]["load_bbox"]),
        "LOAD_BRIDGE_ASSET_BINDING_DRIFT",
    )
    for object_id, row in by_id.items():
        reject_if(row.get("design_level_pose_bound") is not True, "FIXED_POSE_NOT_BOUND", object_id)
        reject_if(row.get("asset_level_operational_authority") is not False, f"FIXED_OPERATIONAL_PROMOTION::{object_id}")
        reject_if(row.get("system_motion_authority") is not False, f"FIXED_MOTION_PROMOTION::{object_id}")
        reject_if(row.get("pair_eligible") is not False, f"FIXED_PAIR_PROMOTION::{object_id}")
        reject_if(row.get("pair_evaluation_authorized") is not False, f"FIXED_PAIR_AUTHORITY::{object_id}")
    for object_id, validation_id in (("F::M3R_STAGE_A", "STAGE_A"), ("F::M3R_STAGE_B", "STAGE_B")):
        row = by_id[object_id]
        part = ref["fixed"]["parts"][validation_id]
        reject_if(not _matrix_equal(row.get("T_M3R_LOCAL_asset_rows"), IDENTITY_4), "M3R_LOCAL_PLACEMENT_DRIFT", object_id)
        reject_if(not _matrix_equal(row.get("T_S_asset_rows_mm"), ref["fixed"]["m3r_rows"]), "M3R_S_TRANSFORM_DRIFT", object_id)
        asset = row.get("geometry_asset", {})
        reject_if(
            asset.get("asset_storage_frame") != "M3R_LOCAL"
            or asset.get("path") != part["path"]
            or asset.get("sha256") != part["sha256"]
            or not exact_typed_equal(asset.get("expected_local_bbox_mm"), part["bbox"])
            or type(asset.get("expected_solid_count")) is not int
            or asset.get("expected_solid_count") != 1,
            "M3R_ASSET_BINDING_DRIFT",
            object_id,
        )

    recompute_pin_ids = frozenset({
        "accepted_urdf", "urdf_line_ending_receipt", "execution_mount", "collision_frame_registration",
        "base_proxy_receipt", "base_proxy_npz", "scene_schema_v2", "digital_frame_tree",
        "load_bridge_receipt",
    })
    reject_if(not exact_typed_equal(recompute.get("source_pins"), expected_source_pin_block(recompute_pin_ids)), "RECOMPUTE_SOURCE_PIN_BLOCK_DRIFT")
    reject_if(recompute.get("schema") != "INDEPENDENT_BASE_LINK_ZERO_MOTION_RECOMPUTE_V1", "RECOMPUTE_SCHEMA_DRIFT")
    _require_false_authority(recompute, "RECOMPUTE")
    reject_if(not exact_typed_equal(recompute.get("parent_truth_snapshot"), ref["parent"]), "RECOMPUTE_PARENT_TRUTH_DRIFT")
    emitted_urdf = recompute.get("urdf_graph_recompute", {})
    urdf_fields = (
        "robot_name", "link_count", "joint_count", "root_links", "base_link_parent_joint_count",
        "q_order", "q_domain_lower_rad", "q_domain_upper_rad", "raw_bytes_sha256",
        "lf_normalized_sha256",
    )
    for field in urdf_fields:
        reject_if(not exact_typed_equal(emitted_urdf.get(field), ref["urdf"][field]), "RECOMPUTE_URDF_FIELD_DRIFT", field)
    reject_if(emitted_urdf.get("root_links") != ["base_link"] or emitted_urdf.get("base_link_parent_joint_count") != 0, "BASE_LINK_NOT_UNIQUE_URDF_ROOT")

    emitted_mount = recompute.get("execution_mount_recompute", {})
    for field, expected in ref["mount"].items():
        if field == "metrics":
            for metric, expected_metric in expected.items():
                actual = emitted_mount.get("metrics", {}).get(metric)
                reject_if(not is_finite_number(actual) or float(actual) != expected_metric, "RECOMPUTE_MOUNT_METRIC_DRIFT", metric)
        else:
            reject_if(not exact_typed_equal(emitted_mount.get(field), expected), "RECOMPUTE_MOUNT_FIELD_DRIFT", field)
    reject_if(not exact_typed_equal(recompute.get("collision_registration_recompute"), ref["registration"]), "RECOMPUTE_REGISTRATION_DRIFT")

    geometry = ref["geometry"]
    emitted_geometry = recompute.get("geometry_recompute", {})
    expected_geometry = {
        "npz_vertex_count": geometry["npz_vertex_count"],
        "npz_face_count": geometry["npz_face_count"],
        "mesh_bbox_mm": geometry["mesh_bbox_mm"],
        "receipt_mesh_bbox_max_abs_residual_mm": geometry["receipt_residual_mm"],
        "mesh_max_vertex_radius_mm": geometry["mesh_max_vertex_radius_mm"],
        "mesh_bbox_corner_radius_mm": geometry["mesh_bbox_corner_radius_mm"],
        "brep_tight_bbox_mm": geometry["brep_bbox_mm"],
        "brep_bbox_corner_radius_mm": geometry["brep_bbox_corner_radius_mm"],
        "geometry_reference_radius_mm": geometry["geometry_reference_radius_mm"],
        "radius_selection_rule": "MAX_OF_RECOMPUTED_MESH_VERTEX_MESH_BBOX_AND_RECEIPT_TIGHT_BREP_BBOX_RADII",
    }
    reject_if(not exact_typed_equal(emitted_geometry, expected_geometry), "BASE_BBOX_OR_RADIUS_RECOMPUTE_MISMATCH")
    radius = emitted_geometry.get("geometry_reference_radius_mm")
    reject_if(not is_finite_number(radius), "BASE_RADIUS_NONFINITE")
    reject_if(float(radius) < geometry["mesh_vertex_radius_mm"] or float(radius) < geometry["brep_bbox_corner_radius_mm"], "BASE_RADIUS_NOT_CONSERVATIVE")

    fixed = recompute.get("fixed_platform_transform_recompute", {})
    reject_if(not _matrix_equal(fixed.get("T_S_M3R_LOCAL_rows_mm"), ref["fixed"]["m3r_rows"]), "RECOMPUTE_M3R_TRANSFORM_DRIFT")
    reject_if(not _matrix_equal(fixed.get("T_S_LOAD_BRIDGE_LOCAL_design_datum_rows_mm"), ref["fixed"]["load_rows"]), "RECOMPUTE_LOAD_DATUM_DRIFT")
    reject_if(
        not exact_typed_equal(fixed.get("load_bridge_step_reopen_bbox_S_mm"), ref["fixed"]["load_bbox"])
        or not _matrix_equal(fixed.get("load_bridge_runtime_asset_to_S_rows"), IDENTITY_4)
        or fixed.get("load_bridge_double_transform_forbidden") is not True,
        "RECOMPUTE_FIXED_PLATFORM_BINDING_DRIFT",
    )

    proof = recompute.get("full_domain_zero_motion_proof", {})
    reject_if(not exact_typed_equal(proof.get("q_domain_lower_rad"), Q_LOWER) or not exact_typed_equal(proof.get("q_domain_upper_rad"), Q_UPPER), "RECOMPUTE_PROOF_Q_DOMAIN_DRIFT")
    reject_if(proof.get("scene_state_domain_sha256") != SOURCE_PINS["scene_schema_v2"][2] or proof.get("scene_authoritative_values_consumed") != 0, "RECOMPUTE_PROOF_SCENE_DOMAIN_DRIFT")
    reject_if(not exact_typed_equal(proof.get("global_L_mm_per_rad"), [0.0] * 6) or proof.get("proof_domain_complete") is not True, "RECOMPUTE_ZERO_MOTION_PROOF_DRIFT")
    reject_if(not exact_typed_equal(proof.get("sample_replay"), _expected_samples(ref["mount"]["T_S_base_link_rows_m"])), "RECOMPUTE_SAMPLE_REPLAY_DRIFT")
    checks = recompute.get("checks")
    reject_if(
        not isinstance(checks, dict)
        or set(checks) != RECOMPUTE_CHECK_IDS
        or any(value is not True for value in checks.values())
        or type(recompute.get("checks_passed")) is not int
        or recompute.get("checks_passed") != 14
        or type(recompute.get("checks_total")) is not int
        or recompute.get("checks_total") != 14,
        "RECOMPUTE_CHECK_SET_DRIFT",
    )

    contract = ref["motion_contract"]
    reject_if(cert.get("schema") != "OBJECT_MOTION_BOUND_CERTIFICATE_V1", "MOTION_CERT_SCHEMA_DRIFT")
    for field, expected in CERT_FROZEN_FIELDS.items():
        reject_if(not exact_typed_equal(cert.get(field), expected), f"CERT_FROZEN_FIELD_DRIFT::{field}")
    required_output = set(contract.get("required_object_certificate_output_fields", []))
    required_input = set(contract.get("required_object_certificate_input_fields", []))
    reject_if(not required_output <= set(cert), "MOTION_CERT_REQUIRED_OUTPUT_FIELD_MISSING")
    input_binding = cert.get("input_binding")
    reject_if(not isinstance(input_binding, dict) or not required_input <= set(input_binding), "MOTION_CERT_REQUIRED_INPUT_FIELD_MISSING")
    recompute_hash = sha256_file(HERE / RECOMPUTE_NAME) if validate_local_hashes else cert.get("evidence_sha256")
    expected_input = {
        "registry_sha256": SOURCE_PINS["system_registry"][2],
        "object_id": "A::base_link",
        "motion_class": "DIRECT_RIGID_FK_CANDIDATE",
        "accepted_urdf_raw_bytes_sha256": ref["urdf"]["raw_bytes_sha256"],
        "accepted_urdf_lf_normalized_sha256": ref["urdf"]["lf_normalized_sha256"],
        "urdf_hash_normalization_receipt_sha256": SOURCE_PINS["urdf_line_ending_receipt"][2],
        "mount_binding_sha256": ref["mount"]["canonical_payload_sha256"],
        "physical_to_dynamics_bridge_sha256": SOURCE_PINS["physical_dynamics_bridge"][2],
        "runtime_mount_numeric_spelling_policy_sha256": ref["mount"]["runtime_mount_numeric_spelling_policy_sha256"],
        "collision_asset_frame_registration_sha256": SOURCE_PINS["collision_frame_registration"][2],
        "local_geometry_asset_sha256": SOURCE_PINS["base_proxy_npz"][2],
        "pose_law_source_sha256": SOURCE_PINS["accepted_urdf"][2],
        "scene_state_domain_sha256": SOURCE_PINS["scene_schema_v2"][2],
        "q_domain_lower_rad": Q_LOWER,
        "q_domain_upper_rad": Q_UPPER,
        "units": {"joint": "rad", "motion_bound": "mm", "mount_translation": "m"},
        "derivation_method": "URDF_ROOT_GRAPH_PROOF_PLUS_IDENTITY_COLLISION_REGISTRATION_AND_CONSTANT_FULL_PRECISION_MOUNT",
        "independent_review_evidence_sha256": recompute_hash,
    }
    reject_if(not exact_typed_equal(input_binding, expected_input), "INPUT_BINDING_DRIFT")
    reject_if(cert.get("input_binding_sha256") != canonical_digest(expected_input), "INPUT_BINDING_HASH_MISMATCH")
    expected_replay = {
        "object_id": "A::base_link",
        "T_S_base_link_rows_m": ref["mount"]["T_S_base_link_rows_m"],
        "q_order": Q_ORDER,
        "q_domain_lower_rad": Q_LOWER,
        "q_domain_upper_rad": Q_UPPER,
        "scene_state_domain_sha256": SOURCE_PINS["scene_schema_v2"][2],
        "global_L_mm_per_rad": [0.0] * 6,
        "geometry_reference_radius_mm": geometry["geometry_reference_radius_mm"],
        "proof_domain_complete": True,
    }
    reject_if(not exact_typed_equal(cert.get("deterministic_replay_payload"), expected_replay), "DETERMINISTIC_REPLAY_PAYLOAD_DRIFT")
    reject_if(cert.get("deterministic_replay_sha256") != canonical_digest(expected_replay), "DETERMINISTIC_REPLAY_HASH_MISMATCH")
    reject_if(cert.get("evidence_sha256") != recompute_hash, "MOTION_CERT_EVIDENCE_HASH_MISMATCH")
    reject_if(cert.get("contract_sha256") != SOURCE_PINS["object_motion_contract"][2], "MOTION_CERT_CONTRACT_HASH_DRIFT")
    reject_if(cert.get("object_id") != "A::base_link" or cert.get("motion_class") != "DIRECT_RIGID_FK_CANDIDATE" or cert.get("status") != "CERTIFIED_REGISTERED_ASSET_MOTION_ONLY", "MOTION_CERT_IDENTITY_OR_STATUS_DRIFT")
    reject_if(cert.get("q_order") != Q_ORDER or not exact_typed_equal(cert.get("q_domain_lower_rad"), Q_LOWER) or not exact_typed_equal(cert.get("q_domain_upper_rad"), Q_UPPER), "MOTION_CERT_Q_DOMAIN_DRIFT")
    reject_if(not exact_typed_equal(cert.get("global_L_mm_per_rad"), [0.0] * 6), "MOTION_CERT_L_NOT_SIX_ZEROES")
    reject_if(not exact_typed_equal(cert.get("geometry_reference_radius_mm"), geometry["geometry_reference_radius_mm"]), "MOTION_CERT_RADIUS_DRIFT")
    reject_if(cert.get("proof_domain_complete") is not True or type(cert.get("system_motion_authority_credit")) is not int or cert.get("system_motion_authority_credit") != 1 or cert.get("runtime_object_pose_bound") is not True, "MOTION_CERT_AUTHORITY_CONTENT_DRIFT")
    reject_if(cert.get("pair_eligible") is not False, "BASE_CERT_PAIR_ELIGIBLE")
    reject_if(cert.get("pair_derating_authority_bound") is not False, "BASE_CERT_PAIR_DERATING_PROMOTED")
    _require_false_authority(cert, "CERT")
    for field in PAIR_DERATE_FIELDS:
        reject_if(field not in cert, f"PAIR_DERATE_FIELD_MISSING::{field}")
        reject_if(cert[field] is not None, f"PAIR_DERATE_MUST_REMAIN_NULL::{field}")
    nullability = cert.get("pair_derate_nullability", {})
    reject_if(nullability.get("automatic_zero_fill_forbidden") is not True or nullability.get("unknown_fields") != PAIR_DERATE_FIELDS, "PAIR_DERATE_NULLABILITY_POLICY_DRIFT")

    reject_if(quarantine.get("schema") != "ROUTE_C_NEGATIVE_WITNESS_QUARANTINE_V1", "QUARANTINE_SCHEMA_DRIFT")
    expected_witness_pin = expected_source_pin_block(frozenset({"route_c_negative_witness"}))["route_c_negative_witness"]
    reject_if(not exact_typed_equal(quarantine.get("source_pin"), expected_witness_pin), "QUARANTINE_SOURCE_PIN_DRIFT")
    current_binding = quarantine.get("current_binding")
    reject_if(not isinstance(current_binding, dict) or len(current_binding) != 11 or any(value is not None for value in current_binding.values()), "V9F_CURRENT_BINDING_NOT_ALL_NULL")
    controls = quarantine.get("scope_controls", {})
    reject_if(
        controls.get("imported_as_current_system_pair_result") is not False
        or controls.get("counts_as_pair_query_executed") is not False
        or controls.get("counts_as_edge_certificate") is not False
        or controls.get("counts_as_path_search") is not False,
        "V9F_IMPORTED_OR_CREDITED",
    )
    reject_if(controls.get("alternative_path_impossibility_proven") is not False or controls.get("architecture_infeasibility_proven") is not False, "V9F_SCOPE_OVERCLAIM")
    signed_clearance = quarantine.get("legacy_witness", {}).get("signed_raw_clearance_mm")
    reject_if(not is_finite_number(signed_clearance) or signed_clearance >= 0.0 or quarantine.get("legacy_witness", {}).get("raw_physical_penetration") is not True, "V9F_NEGATIVE_WITNESS_LOST")
    _require_false_authority(quarantine, "QUARANTINE")

    if validate_declared_negative:
        reject_if(negative.get("schema") != "M01_FIXED_PLATFORM_AND_BASE_MOTION_NEGATIVE_CONTROLS_V1", "NEGATIVE_CONTROL_SCHEMA_DRIFT")
        reject_if(negative.get("authority") != "BUILDER_PREEMISSION_DIAGNOSTIC_STRUCTURE_ONLY__NOT_GATE_EVIDENCE", "BUILDER_RECEIPT_NOT_DEMOTED")
        accounting = negative.get("accounting")
        reject_if(not isinstance(accounting, dict) or set(accounting) != {"cases_rejected", "cases_total", "unexpected_acceptances"}, "NEGATIVE_CONTROL_ACCOUNTING_STRUCTURE_DRIFT")
        reject_if(any(type(accounting[field]) is not int for field in accounting), "NEGATIVE_CONTROL_ACCOUNTING_TYPE_DRIFT")
        reject_if(accounting["cases_total"] != 24, "NEGATIVE_CONTROL_ACCOUNTING_STRUCTURE_DRIFT")
        cases = negative.get("cases")
        reject_if(not isinstance(cases, list) or len(cases) != 24, "NEGATIVE_CONTROL_CASE_COUNT_DRIFT")
        prefixes = tuple(case.get("case_id", "")[:4] for case in cases)
        expected_prefixes = tuple(f"NC{index:02d}" for index in range(1, 25))
        reject_if(prefixes != expected_prefixes or len(set(case.get("case_id") for case in cases)) != 24, "NEGATIVE_CONTROL_CASE_ID_DRIFT")
        case_keys = {"case_id", "target", "mutation", "expected_rejection_code", "actual_rejection_codes", "rejected"}
        reject_if(any(not isinstance(case, dict) or set(case) != case_keys for case in cases), "NEGATIVE_CONTROL_CASE_STRUCTURE_DRIFT")
        reject_if(any(type(case["rejected"]) is not bool or not isinstance(case["actual_rejection_codes"], list) for case in cases), "NEGATIVE_CONTROL_CASE_TYPE_DRIFT")
        reject_if(negative.get("next_stage_authorized") is not False or negative.get("release_credit") is not False, "NEGATIVE_RECEIPT_AUTHORITY_PROMOTED")

    reject_if(gate.get("schema") != "M01_FIXED_PLATFORM_AND_BASE_MOTION_PRECERT_GATE_V1", "GATE_SCHEMA_DRIFT")
    for field, expected in GATE_FROZEN_FIELDS.items():
        reject_if(not exact_typed_equal(gate.get(field), expected), f"GATE_FROZEN_FIELD_DRIFT::{field}")
    reject_if(not exact_typed_equal(gate.get("source_pins"), expected_source_pin_block()), "GATE_SOURCE_PIN_BLOCK_DRIFT")
    gate_checks = gate.get("checks")
    reject_if(
        not isinstance(gate_checks, dict)
        or set(gate_checks) != GATE_CHECK_IDS
        or any(value is not True for value in gate_checks.values())
        or type(gate.get("checks_passed")) is not int
        or gate.get("checks_passed") != 30
        or type(gate.get("checks_total")) is not int
        or gate.get("checks_total") != 30,
        "GATE_NOT_30_OF_30",
    )
    reject_if(not exact_typed_equal(gate.get("counters"), EXPECTED_COUNTERS), "GATE_COUNTERS_DRIFT")
    reject_if(gate.get("append_only_package_complete") is not True or gate.get("fixed_platform_pose_prebind_pass") is not True or gate.get("base_link_motion_precert_pass") is not True, "GATE_LOCAL_PASS_FIELDS_DRIFT")
    reject_if(gate.get("system_collision_gate_pass") is not False or gate.get("system_path_gate_pass") is not False, "GATE_PARENT_PASS_PROMOTED")
    _require_false_authority(gate, "GATE")
    reject_if("BASE_MOTION_1_OF_150" not in gate.get("verdict", "") or "SCENE_PAIR_EDGE_PATH_AND_RELEASE_HOLD" not in gate.get("verdict", ""), "GATE_VERDICT_SCOPE_DRIFT")

    local_names = {POSE_NAME, RECOMPUTE_NAME, CERT_NAME, QUARANTINE_NAME, NEGATIVE_NAME}
    local_pins = gate.get("local_artifact_pins")
    reject_if(not isinstance(local_pins, dict) or set(local_pins) != local_names, "GATE_LOCAL_PIN_SET_DRIFT")
    if validate_local_hashes:
        for name in local_names:
            expected_pin = {"path": name, "sha256": sha256_file(HERE / name)}
            reject_if(local_pins[name] != expected_pin, "GATE_LOCAL_PIN_HASH_DRIFT", name)
    elif candidate_local_hashes is not None:
        reject_if(set(candidate_local_hashes) != local_names, "CANDIDATE_LOCAL_HASH_SET_DRIFT")
        for name in local_names:
            expected_pin = {"path": name, "sha256": candidate_local_hashes[name]}
            reject_if(local_pins[name] != expected_pin, "GATE_LOCAL_PIN_HASH_DRIFT", name)

    return {
        "validator": "STANDALONE_STRICT_VALIDATOR_V3",
        "builder_imported_or_executed": False,
        "source_pins_verified": 28,
        "fixed_platform_design_pose_bindings": 3,
        "base_link_geometry_reference_radius_mm": radius,
        "system_motion_certificates_bound": 1,
        "system_motion_certificates_required": 150,
        "authoritative_scene_values_bound": 0,
        "stage_instances_bound": 0,
        "clearance_policy_rows_bound": 0,
        "pair_queries_executed": 0,
        "edges_certified": 0,
        "path_search_executed": False,
        "gate_checks_passed": 30,
        "gate_checks_total": 30,
        "next_stage_authorized": False,
        "release_credit": False,
        "status": "PASS",
    }


def _manifest_rows(path: Path = HERE / MANIFEST_NAME) -> list[dict[str, str]]:
    reject_if(not path.is_file(), "MANIFEST_MISSING")
    header, rows = read_csv_strict(path)
    reject_if(header != ["path", "bytes", "sha256"], "MANIFEST_HEADER_DRIFT")
    return rows


def validate_package_inventory(actual_files: set[str], cache_directories: set[str]) -> None:
    reject_if(bool(cache_directories), "PACKAGE_CACHE_DIRECTORY_PRESENT")
    reject_if(actual_files != PACKAGE_PAYLOAD_FILES, "PACKAGE_FILE_SET_DRIFT")


def validate_manifest_rows(rows: list[dict[str, str]], *, verify_files: bool = True) -> None:
    names = [row.get("path", "") for row in rows]
    reject_if(MANIFEST_NAME in names, "MANIFEST_NOT_SELF_EXCLUDED")
    reject_if(len(names) != len(set(names)), "MANIFEST_DUPLICATE_PATH")
    reject_if(set(names) != PACKAGE_PAYLOAD_FILES, "MANIFEST_PATH_SET_DRIFT")
    for row in rows:
        name = row["path"]
        relative = Path(name)
        reject_if(relative.is_absolute() or ".." in relative.parts or relative.as_posix() != name, "MANIFEST_PATH_ESCAPES_PACKAGE")
        reject_if(not row.get("bytes", "").isdigit(), "MANIFEST_BYTE_FIELD_INVALID")
        digest = row.get("sha256", "")
        reject_if(len(digest) != 64 or any(character not in "0123456789ABCDEF" for character in digest), "MANIFEST_HASH_FIELD_INVALID")
        if verify_files:
            artifact = HERE / relative
            reject_if(not artifact.is_file(), "MANIFEST_FILE_MISSING")
            reject_if(artifact.stat().st_size != int(row["bytes"]), "MANIFEST_BYTE_DRIFT")
            reject_if(sha256_file(artifact) != digest, "MANIFEST_HASH_DRIFT")
    if verify_files:
        forbidden_cache_dirs = {
            path.relative_to(HERE).as_posix()
            for path in HERE.rglob("*")
            if path.is_dir() and path.name in {"__pycache__", ".pytest_cache"}
        }
        actual = {
            path.relative_to(HERE).as_posix()
            for path in HERE.rglob("*")
            if path.is_file()
            and path.name != MANIFEST_NAME
        }
        validate_package_inventory(actual, forbidden_cache_dirs)


def validate_manifest() -> None:
    validate_manifest_rows(_manifest_rows(), verify_files=True)


def _expect_rejection(
    case_id: str,
    target: str,
    expected_code: str,
    action: Callable[[], None],
    downstream_rehashed: list[str] | None = None,
) -> dict[str, Any]:
    actual_code: str | None = None
    try:
        action()
    except ValidationError as exc:
        actual_code = exc.code
    return {
        "case_id": case_id,
        "target": target,
        "expected_rejection_code": expected_code,
        "actual_rejection_code": actual_code,
        "rejected": actual_code == expected_code,
        "downstream_rehashed": [] if downstream_rehashed is None else downstream_rehashed,
    }


def run_independent_negative_controls(
    repo_root: Path,
    documents: dict[str, dict[str, Any]],
    reference: dict[str, Any],
) -> dict[str, Any]:
    """Execute mutations without using the emitted negative-control receipt."""

    cases: list[dict[str, Any]] = []
    baseline_manifest_rows = _manifest_rows()

    def semantic(
        case_id: str,
        expected: str,
        mutate: Callable[[dict[str, dict[str, Any]]], None],
        *,
        local_hashes: bool = False,
        rehash_downstream_of: str | None = None,
    ) -> None:
        candidate = copy.deepcopy(documents)
        mutate(candidate)
        candidate_hashes: dict[str, str] | None = None
        downstream_rehashed: list[str] = []
        if rehash_downstream_of is not None:
            if rehash_downstream_of == RECOMPUTE_NAME:
                evidence_hash = emitted_artifact_digest(candidate[RECOMPUTE_NAME])
                candidate[CERT_NAME]["evidence_sha256"] = evidence_hash
                candidate[CERT_NAME]["input_binding"]["independent_review_evidence_sha256"] = evidence_hash
                candidate[CERT_NAME]["input_binding_sha256"] = canonical_digest(candidate[CERT_NAME]["input_binding"])
                downstream_rehashed.extend(["certificate.evidence_sha256", "certificate.input_binding_sha256"])
            if rehash_downstream_of in {POSE_NAME, RECOMPUTE_NAME, CERT_NAME, QUARANTINE_NAME, NEGATIVE_NAME}:
                candidate_hashes = {
                    name: emitted_artifact_digest(candidate[name])
                    for name in (POSE_NAME, RECOMPUTE_NAME, CERT_NAME, QUARANTINE_NAME, NEGATIVE_NAME)
                }
                for name, digest in candidate_hashes.items():
                    candidate[GATE_NAME]["local_artifact_pins"][name] = {"path": name, "sha256": digest}
                downstream_rehashed.append("gate.local_artifact_pins")
            elif rehash_downstream_of == GATE_NAME:
                mutated_manifest = copy.deepcopy(baseline_manifest_rows)
                gate_bytes = (json.dumps(candidate[GATE_NAME], ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
                gate_row = next(row for row in mutated_manifest if row["path"] == GATE_NAME)
                gate_row["bytes"] = str(len(gate_bytes))
                gate_row["sha256"] = sha256_bytes(gate_bytes)
                validate_manifest_rows(mutated_manifest, verify_files=False)
                downstream_rehashed.append("manifest.gate_row")
        cases.append(
            _expect_rejection(
                case_id,
                "ARTIFACT_SET",
                expected,
                lambda: validate_candidate_documents(
                    repo_root,
                    candidate,
                    validate_local_hashes=local_hashes,
                    validate_declared_negative=False,
                    reference=reference,
                    candidate_local_hashes=candidate_hashes,
                ),
                downstream_rehashed=downstream_rehashed,
            )
        )

    semantic("IV01_LOAD_BRIDGE_TRANSFORM", "LOAD_BRIDGE_RUNTIME_TRANSFORM_NOT_IDENTITY", lambda d: d[POSE_NAME]["entries"][0].update({"T_S_asset_rows": M3R_S_ROWS}))
    semantic("IV02_FIXED_OPERATIONAL_AUTHORITY", "FIXED_OPERATIONAL_PROMOTION::F::M3R_STAGE_A", lambda d: d[POSE_NAME]["entries"][1].update({"asset_level_operational_authority": True}))
    semantic("IV03_FIXED_MOTION_AUTHORITY", "FIXED_MOTION_PROMOTION::F::M3R_STAGE_B", lambda d: d[POSE_NAME]["entries"][2].update({"system_motion_authority": True}))
    semantic("IV04_BASE_TOP_LEVEL_L", "MOTION_CERT_L_NOT_SIX_ZEROES", lambda d: d[CERT_NAME].update({"global_L_mm_per_rad": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]}))

    def mutate_replay_l(documents_copy: dict[str, dict[str, Any]]) -> None:
        replay = documents_copy[CERT_NAME]["deterministic_replay_payload"]
        replay["global_L_mm_per_rad"] = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        documents_copy[CERT_NAME]["deterministic_replay_sha256"] = canonical_digest(replay)

    semantic("IV05_REPLAY_L_WITH_REHASH", "DETERMINISTIC_REPLAY_PAYLOAD_DRIFT", mutate_replay_l, rehash_downstream_of=CERT_NAME)

    def mutate_registry_with_rehash(documents_copy: dict[str, dict[str, Any]]) -> None:
        binding = documents_copy[CERT_NAME]["input_binding"]
        binding["registry_sha256"] = "0" * 64
        documents_copy[CERT_NAME]["input_binding_sha256"] = canonical_digest(binding)

    semantic("IV06_REGISTRY_PIN_WITH_REHASH", "INPUT_BINDING_DRIFT", mutate_registry_with_rehash, rehash_downstream_of=CERT_NAME)
    semantic("IV07_BBOX_NAN", "NONFINITE_NUMBER", lambda d: d[RECOMPUTE_NAME]["geometry_recompute"]["mesh_bbox_mm"][0].__setitem__(0, float("nan")))
    semantic("IV08_RADIUS_UNDERBOUND", "BASE_BBOX_OR_RADIUS_RECOMPUTE_MISMATCH", lambda d: d[RECOMPUTE_NAME]["geometry_recompute"].update({"geometry_reference_radius_mm": 0.0}))
    semantic("IV09_RECOMPUTE_SOURCE_PIN", "RECOMPUTE_SOURCE_PIN_BLOCK_DRIFT", lambda d: d[RECOMPUTE_NAME]["source_pins"]["accepted_urdf"].update({"sha256": "0" * 64}), rehash_downstream_of=RECOMPUTE_NAME)
    semantic("IV10_GATE_SOURCE_PIN", "GATE_SOURCE_PIN_BLOCK_DRIFT", lambda d: d[GATE_NAME]["source_pins"]["system_registry"].update({"sha256": "0" * 64}))
    semantic("IV11_GATE_LOCAL_PIN", "GATE_LOCAL_PIN_HASH_DRIFT", lambda d: d[GATE_NAME]["local_artifact_pins"][POSE_NAME].update({"sha256": "0" * 64}), local_hashes=True)
    semantic("IV12_PAIR_DERATE_ZERO_FILL", "PAIR_DERATE_MUST_REMAIN_NULL::model_uncertainty_bound_mm", lambda d: d[CERT_NAME].update({"model_uncertainty_bound_mm": 0.0}))
    semantic("IV13_PAIR_ELIGIBILITY", "BASE_CERT_PAIR_ELIGIBLE", lambda d: d[CERT_NAME].update({"pair_eligible": True}))
    semantic("IV14_PAIR_AUTHORITY", "CERT_AUTHORITY_MUST_BE_FALSE", lambda d: d[CERT_NAME].update({"pair_evaluation_authorized": True}))
    semantic("IV15_SCENE_COUNT", "GATE_COUNTERS_DRIFT", lambda d: d[GATE_NAME]["counters"].update({"authoritative_scene_values_bound": 1}))
    semantic("IV16_STAGE_COUNT", "GATE_COUNTERS_DRIFT", lambda d: d[GATE_NAME]["counters"].update({"stage_instances_bound": 1}))
    semantic("IV17_CLEARANCE_COUNT", "GATE_COUNTERS_DRIFT", lambda d: d[GATE_NAME]["counters"].update({"clearance_policy_rows_bound": 1}))
    semantic("IV18_PAIR_QUERY_COUNT", "GATE_COUNTERS_DRIFT", lambda d: d[GATE_NAME]["counters"].update({"pair_queries_executed": 1}))
    semantic("IV19_EDGE_COUNT", "GATE_COUNTERS_DRIFT", lambda d: d[GATE_NAME]["counters"].update({"edges_certified": 1}))
    semantic("IV20_PATH_AUTHORITY", "GATE_COUNTERS_DRIFT", lambda d: d[GATE_NAME]["counters"].update({"path_search_authorized": True}))
    semantic("IV21_PATH_EXECUTION", "GATE_COUNTERS_DRIFT", lambda d: d[GATE_NAME]["counters"].update({"path_search_executed": True}))
    semantic("IV22_NEXT_STAGE", "GATE_COUNTERS_DRIFT", lambda d: d[GATE_NAME]["counters"].update({"next_stage_authorized": True}))
    semantic("IV23_RELEASE", "GATE_COUNTERS_DRIFT", lambda d: d[GATE_NAME]["counters"].update({"release_credit": True}))
    semantic("IV24_ROUTE_C_IMPORT", "V9F_CURRENT_BINDING_NOT_ALL_NULL", lambda d: d[QUARANTINE_NAME]["current_binding"].update({"current_system_pair_id": "A::base_link||C::SEG-04"}))

    rows = _manifest_rows()
    duplicate_rows = copy.deepcopy(rows) + [copy.deepcopy(rows[0])]
    cases.append(_expect_rejection("IV25_MANIFEST_DUPLICATE", MANIFEST_NAME, "MANIFEST_DUPLICATE_PATH", lambda: validate_manifest_rows(duplicate_rows, verify_files=False)))
    extra_rows = copy.deepcopy(rows) + [{"path": "EXTRA.txt", "bytes": "0", "sha256": "0" * 64}]
    cases.append(_expect_rejection("IV26_MANIFEST_EXTRA", MANIFEST_NAME, "MANIFEST_PATH_SET_DRIFT", lambda: validate_manifest_rows(extra_rows, verify_files=False)))
    bad_hash_rows = copy.deepcopy(rows)
    bad_hash_rows[0]["sha256"] = "0" * 64
    cases.append(_expect_rejection("IV27_MANIFEST_HASH", MANIFEST_NAME, "MANIFEST_HASH_DRIFT", lambda: validate_manifest_rows(bad_hash_rows, verify_files=True)))
    cases.append(_expect_rejection("IV28_JSON_DUPLICATE_KEY", "STRICT_JSON", "DUPLICATE_JSON_KEY", lambda: strict_json_text('{"x":1,"x":2}')))
    cases.append(_expect_rejection("IV29_JSON_NAN", "STRICT_JSON", "NONFINITE_JSON_CONSTANT", lambda: strict_json_text('{"x":NaN}')))
    cases.append(_expect_rejection("IV30_JSON_INFINITY", "STRICT_JSON", "NONFINITE_JSON_CONSTANT", lambda: strict_json_text('{"x":Infinity}')))

    # Complete independent replay of all 24 builder-side mutation categories.
    semantic("IV31_FIXED_PAIR_ELIGIBILITY", "FIXED_PAIR_PROMOTION::F::M3R_STAGE_B", lambda d: d[POSE_NAME]["entries"][2].update({"pair_eligible": True}))
    semantic("IV32_MOTION_COUNT_OVERCLAIM", "GATE_COUNTERS_DRIFT", lambda d: d[GATE_NAME]["counters"].update({"system_motion_certificates_bound": 2}))
    semantic("IV33_LEGACY_RESULT_PROMOTION", "V9F_IMPORTED_OR_CREDITED", lambda d: d[QUARANTINE_NAME]["scope_controls"].update({"imported_as_current_system_pair_result": True}))
    semantic("IV34_LEGACY_QUERY_CREDIT", "V9F_IMPORTED_OR_CREDITED", lambda d: d[QUARANTINE_NAME]["scope_controls"].update({"counts_as_pair_query_executed": True}))
    semantic("IV35_FIXED_PAIR_AUTHORITY", "FIXED_PAIR_AUTHORITY::F::M3R_STAGE_B", lambda d: d[POSE_NAME]["entries"][2].update({"pair_evaluation_authorized": True}))
    semantic("IV36_BASE_DERATING_AUTHORITY", "BASE_CERT_PAIR_DERATING_PROMOTED", lambda d: d[CERT_NAME].update({"pair_derating_authority_bound": True}))
    semantic("IV37_BASE_PROOF_CONTENT", "MOTION_CERT_AUTHORITY_CONTENT_DRIFT", lambda d: d[CERT_NAME].update({"proof_domain_complete": False}))

    top_level_cases = (
        ("IV38_POSE_TOP_LEVEL_EXTRA", POSE_NAME),
        ("IV39_RECOMPUTE_TOP_LEVEL_EXTRA", RECOMPUTE_NAME),
        ("IV40_CERT_TOP_LEVEL_EXTRA", CERT_NAME),
        ("IV41_QUARANTINE_TOP_LEVEL_EXTRA", QUARANTINE_NAME),
        ("IV42_NEGATIVE_TOP_LEVEL_EXTRA", NEGATIVE_NAME),
        ("IV43_GATE_TOP_LEVEL_EXTRA", GATE_NAME),
    )
    for case_id, artifact_name in top_level_cases:
        semantic(
            case_id,
            f"TOP_LEVEL_KEY_SET_DRIFT::{artifact_name}",
            lambda d, name=artifact_name: d[name].update({"UNLISTED_ESCAPE_FIELD": True}),
            rehash_downstream_of=artifact_name,
        )

    def altered_value(expected: Any) -> Any:
        if type(expected) is bool:
            return not expected
        if expected is None:
            return "MUTATED_NON_NULL"
        if isinstance(expected, str):
            return expected + "__MUTATED"
        if isinstance(expected, list):
            return copy.deepcopy(expected) + ["MUTATED_EXTRA_ITEM"]
        if isinstance(expected, dict):
            mutated = copy.deepcopy(expected)
            first_key = next(iter(mutated))
            mutated[first_key] = altered_value(mutated[first_key])
            return mutated
        raise AssertionError(f"UNSUPPORTED_FROZEN_VALUE:{expected!r}")

    cert_case_index = 44
    for field, expected in CERT_FROZEN_FIELDS.items():
        semantic(
            f"IV{cert_case_index:02d}_CERT_FROZEN_{field.upper()}",
            f"CERT_FROZEN_FIELD_DRIFT::{field}",
            lambda d, key=field, value=altered_value(expected): d[CERT_NAME].update({key: value}),
            rehash_downstream_of=CERT_NAME,
        )
        cert_case_index += 1

    gate_case_index = 53
    for field, expected in GATE_FROZEN_FIELDS.items():
        semantic(
            f"IV{gate_case_index:02d}_GATE_FROZEN_{field.upper()}",
            f"GATE_FROZEN_FIELD_DRIFT::{field}",
            lambda d, key=field, value=altered_value(expected): d[GATE_NAME].update({key: value}),
            rehash_downstream_of=GATE_NAME,
        )
        gate_case_index += 1

    semantic("IV60_BOOL_AS_POSE_COUNT", "POSE_ACCOUNTING_DRIFT", lambda d: d[POSE_NAME]["accounting"].update({"design_level_pose_entries_bound": True}), rehash_downstream_of=POSE_NAME)
    semantic("IV61_BOOL_AS_RECOMPUTE_COUNT", "RECOMPUTE_CHECK_SET_DRIFT", lambda d: d[RECOMPUTE_NAME].update({"checks_total": True}), rehash_downstream_of=RECOMPUTE_NAME)
    semantic("IV62_BOOL_AS_CERT_MOTION_COUNT", "MOTION_CERT_AUTHORITY_CONTENT_DRIFT", lambda d: d[CERT_NAME].update({"system_motion_authority_credit": True}), rehash_downstream_of=CERT_NAME)
    semantic("IV63_BOOL_AS_CERT_RADIUS", "MOTION_CERT_RADIUS_DRIFT", lambda d: d[CERT_NAME].update({"geometry_reference_radius_mm": True}), rehash_downstream_of=CERT_NAME)
    semantic("IV64_BOOL_AS_GATE_COUNT", "GATE_COUNTERS_DRIFT", lambda d: d[GATE_NAME]["counters"].update({"pair_queries_executed": False}), rehash_downstream_of=GATE_NAME)
    semantic("IV65_BOOL_AS_RECOMPUTE_RADIUS", "BASE_BBOX_OR_RADIUS_RECOMPUTE_MISMATCH", lambda d: d[RECOMPUTE_NAME]["geometry_recompute"].update({"geometry_reference_radius_mm": True}), rehash_downstream_of=RECOMPUTE_NAME)
    cases.append(_expect_rejection("IV66_CACHE_DIRECTORY", "PACKAGE_INVENTORY", "PACKAGE_CACHE_DIRECTORY_PRESENT", lambda: validate_package_inventory(set(PACKAGE_PAYLOAD_FILES), {"__pycache__"})))

    builder_case_mapping = {
        "NC01": "IV01_LOAD_BRIDGE_TRANSFORM",
        "NC02": "IV02_FIXED_OPERATIONAL_AUTHORITY",
        "NC03": "IV31_FIXED_PAIR_ELIGIBILITY",
        "NC04": "IV04_BASE_TOP_LEVEL_L",
        "NC05": "IV13_PAIR_ELIGIBILITY",
        "NC06": "IV12_PAIR_DERATE_ZERO_FILL",
        "NC07": "IV15_SCENE_COUNT",
        "NC08": "IV18_PAIR_QUERY_COUNT",
        "NC09": "IV24_ROUTE_C_IMPORT",
        "NC10": "IV32_MOTION_COUNT_OVERCLAIM",
        "NC11": "IV16_STAGE_COUNT",
        "NC12": "IV17_CLEARANCE_COUNT",
        "NC13": "IV19_EDGE_COUNT",
        "NC14": "IV20_PATH_AUTHORITY",
        "NC15": "IV21_PATH_EXECUTION",
        "NC16": "IV22_NEXT_STAGE",
        "NC17": "IV23_RELEASE",
        "NC18": "IV33_LEGACY_RESULT_PROMOTION",
        "NC19": "IV34_LEGACY_QUERY_CREDIT",
        "NC20": "IV03_FIXED_MOTION_AUTHORITY",
        "NC21": "IV35_FIXED_PAIR_AUTHORITY",
        "NC22": "IV14_PAIR_AUTHORITY",
        "NC23": "IV36_BASE_DERATING_AUTHORITY",
        "NC24": "IV37_BASE_PROOF_CONTENT",
    }
    by_case_id = {case["case_id"]: case for case in cases}
    builder_case_replay = [
        {
            "builder_case_id": builder_case_id,
            "independent_case_id": independent_case_id,
            "expected_rejection_code": by_case_id[independent_case_id]["expected_rejection_code"],
            "actual_rejection_code": by_case_id[independent_case_id]["actual_rejection_code"],
            "rejected": by_case_id[independent_case_id]["rejected"],
        }
        for builder_case_id, independent_case_id in builder_case_mapping.items()
    ]

    unexpected = [case for case in cases if case["rejected"] is not True]
    reject_if(bool(unexpected), "INDEPENDENT_NEGATIVE_CONTROL_ESCAPE", json.dumps(unexpected, sort_keys=True))
    reject_if(len(builder_case_replay) != 24 or any(row["rejected"] is not True for row in builder_case_replay), "INDEPENDENT_BUILDER_CASE_REPLAY_ESCAPE")
    return {
        "suite": "STANDALONE_VALIDATOR_MUTATION_SUITE_V3",
        "receipt_consulted": False,
        "builder_receipt_used_as_gate_evidence": False,
        "builder_case_replay": builder_case_replay,
        "cases": cases,
        "accounting": {"cases_total": len(cases), "cases_rejected": len(cases), "unexpected_acceptances": 0},
    }


def validate_on_disk(repo_root: Path) -> dict[str, Any]:
    documents = load_documents()
    reference = build_reference(repo_root)
    summary = validate_candidate_documents(repo_root, documents, reference=reference)
    validate_manifest()
    independent_negative = run_independent_negative_controls(repo_root, documents, reference)
    summary["builder_receipt_structural_rows"] = 24
    summary["builder_receipt_used_as_gate_evidence"] = False
    summary["independent_builder_case_replays_rejected"] = len(independent_negative["builder_case_replay"])
    summary["independent_negative_controls_rejected"] = independent_negative["accounting"]["cases_rejected"]
    summary["independent_negative_control_suite"] = independent_negative["suite"]
    summary["independent_negative_control_receipt_sha256"] = canonical_digest(independent_negative)
    summary["manifest_rows_verified"] = len(PACKAGE_PAYLOAD_FILES)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--negative-controls", action="store_true", help="print independently executed mutation receipt")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    if args.negative_controls:
        documents = load_documents()
        reference = build_reference(repo_root)
        validate_candidate_documents(repo_root, documents, reference=reference)
        validate_manifest()
        receipt = run_independent_negative_controls(repo_root, documents, reference)
        result = {
            "receipt": receipt,
            "receipt_sha256": canonical_digest(receipt),
        }
    else:
        result = validate_on_disk(repo_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
