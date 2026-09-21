from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "system_binding_readiness_builder", HERE / "build_system_binding_readiness.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _inputs():
    root = MODULE.ROOT
    registry = MODULE.load_json(root, MODULE.REGISTRY_REL)
    receipt = MODULE.load_json(root, MODULE.RECEIPT_REL)
    pair_contract = MODULE.load_json(root, MODULE.PAIR_CONTRACT_REL)
    motion_contract = MODULE.load_json(root, MODULE.MOTION_CONTRACT_REL)
    exact_source = (root / MODULE.V9F_REL).read_text(encoding="utf-8")
    mount_text = (root / MODULE.MOUNT_REL).read_text(encoding="utf-8")
    embedded = MODULE.extract_mount_embedded_urdf_sha(mount_text)
    urdf_raw = (root / MODULE.URDF_REL).read_bytes()
    equivalence = MODULE.load_json(root, MODULE.URDF_EQUIV_REL)
    bridge_gate = MODULE.load_json(root, MODULE.BRIDGE_GATE_REL)
    bridge_owner = (root / MODULE.BRIDGE_OWNER_REL).read_text(encoding="utf-8")
    bridge_confirmation = (root / MODULE.BRIDGE_CONFIRM_REL).read_text(encoding="utf-8")
    return (
        registry, receipt, exact_source, pair_contract, motion_contract, embedded,
        urdf_raw, equivalence, bridge_gate, bridge_owner, bridge_confirmation,
    )


def _audit(*items):
    return MODULE.audit_state(*items)


def test_positive_metadata_audit_has_exact_universe_partition_and_motion_counts():
    audit = _audit(*_inputs())
    assert audit["errors"] == []
    assert audit["category_counts"] == {"A": 10, "C": 9, "F": 4, "R": 121, "S": 6}
    assert (audit["raw_pair_count"], len(audit["exception_pairs"]), audit["query_required_pair_count"]) == (11175, 9, 11166)
    assert (audit["non_c_non_exception_pair_count"], audit["c_related_pair_count"]) == (9861, 1305)
    assert len(audit["phase1_object_ids"]) == 131
    assert audit["phase1_pair_count"] == 8515
    assert audit["phase1_exception_count"] == 0
    assert audit["phase3_added_pair_count"] == 1215
    assert audit["phase3_cumulative_pair_count"] == 9730
    assert len(audit["phase4_remaining_object_ids"]) == 10
    assert (audit["phase4_raw_pair_count"], audit["phase4_exception_count"], audit["phase4_query_required_pair_count"]) == (1445, 9, 1436)
    assert (len(audit["direct_object_ids"]), len(audit["j3_object_ids"]), len(audit["j4_object_gain"]), len(audit["c_object_ids"])) == (124, 8, 9, 9)


def test_phase_object_ids_are_the_required_sets():
    audit = _audit(*_inputs())
    phase1 = set(audit["phase1_object_ids"])
    assert MODULE.PHASE1_FIXED_IDS <= phase1
    assert all(x.startswith(("R::", "S::")) or x in MODULE.PHASE1_FIXED_IDS for x in phase1)
    assert set(audit["phase4_remaining_object_ids"]) == {
        "A::gripper_left", "A::gripper_link", "A::gripper_right",
        "A::link1", "A::link2", "A::link3", "A::link4", "A::link5", "A::link6",
        "F::BUS",
    }


def test_follower_link4_is_direct_and_only_three_travel_classes_are_hidden_j4():
    audit = _audit(*_inputs())
    assert set(audit["follower_link4_direct_ids"]) == {
        "R::RC-CAR-J4-FOLLOWER-TROLLEY", "R::RC-CLP-J4-FOLLOWER"
    }
    assert set(audit["follower_link4_direct_ids"]) <= set(audit["direct_object_ids"])
    assert set(audit["j4_object_gain"].values()) <= {1.0 / 3.0, 2.0 / 3.0, 1.0}


def test_mount_yaml_digest_is_same_accepted_urdf_under_eol_normalization():
    audit = _audit(*_inputs())
    assert audit["mount_embedded_urdf_sha256"] == MODULE.ACCEPTED_URDF_LF_SHA
    assert audit["accepted_urdf_raw_sha256"] == MODULE.ACCEPTED_URDF_SHA
    assert audit["accepted_urdf_lf_normalized_sha256"] == MODULE.ACCEPTED_URDF_LF_SHA
    assert audit["accepted_urdf_crlf_count"] == 292
    assert audit["accepted_urdf_bare_lf_count"] == 0
    assert audit["urdf_dual_digest_equivalent"] is True
    assert audit["mount_urdf_hash_conflict_detected"] is False
    assert audit["confirmed_physical_dynamics_bridge_bound"] is True


@pytest.mark.parametrize("mutation,expected", [
    ("drop_object", "OBJECT_COUNT_NOT_150"),
    ("wildcard_exception", "NON_ADJACENT_OR_WILDCARD_EXCEPTION"),
    ("drop_j4", "J4_TRAVEL_OBJECT_SET_NOT_9_OR_NOT_IN_REGISTRY"),
    ("false_motion_credit", "MOTION_CONTRACT_READINESS_MISMATCH::system_certified_object_motion_bound_count"),
    ("false_pair_authority", "PAIR_CONTRACT_READINESS_MISMATCH::path_search_authorized"),
    ("false_motion_authority", "MOTION_CONTRACT_READINESS_MISMATCH::release_credit"),
    ("pair_source_pin", "PAIR_CONTRACT_SOURCE_PIN_MISMATCH::system_registry"),
    ("motion_source_pin", "MOTION_CONTRACT_SOURCE_PIN_MISMATCH::accepted_urdf"),
])
def test_negative_metadata_mutations_fail_closed(mutation, expected):
    items = list(copy.deepcopy(_inputs()))
    registry, receipt, source, pair_contract, motion_contract, embedded = items[:6]
    if mutation == "drop_object":
        registry["objects"].pop()
    elif mutation == "wildcard_exception":
        registry["active_pair_exceptions"][0]["mode"] = "WILDCARD"
    elif mutation == "drop_j4":
        for part in receipt["parts"]:
            if part.get("motion_class") == "ONE_THIRD_TRAVEL":
                part["motion_class"] = None
                break
    elif mutation == "false_motion_credit":
        motion_contract["current_readiness"]["system_certified_object_motion_bound_count"] = 1
    elif mutation == "false_pair_authority":
        pair_contract["current_readiness"]["path_search_authorized"] = True
    elif mutation == "false_motion_authority":
        motion_contract["current_readiness"]["release_credit"] = True
    elif mutation == "pair_source_pin":
        pair_contract["source_pins"]["system_registry"]["sha256"] = "0" * 64
    elif mutation == "motion_source_pin":
        motion_contract["source_pins"]["accepted_urdf"]["sha256"] = "0" * 64
    items[:6] = [registry, receipt, source, pair_contract, motion_contract, embedded]
    audit = _audit(*items)
    assert expected in audit["errors"]


def test_negative_j3_source_change_and_urdf_representation_drift_fail_closed():
    items = list(_inputs())
    registry, receipt, source, pair_contract, motion_contract, embedded = items[:6]
    bad_source = source.replace("range(6)", "range(5)", 1)
    items[2] = bad_source
    audit = _audit(*items)
    assert "FROZEN_V9F_J3_LIST_MISMATCH" in audit["errors"]
    items = list(_inputs())
    items[5] = MODULE.ACCEPTED_URDF_SHA
    audit = _audit(*items)
    assert "ACCEPTED_URDF_DUAL_DIGEST_EQUIVALENCE_NOT_PROVEN" in audit["errors"]
    items = list(_inputs())
    items[6] = items[6].replace(b"robot", b"ROB0T", 1)
    audit = _audit(*items)
    assert "ACCEPTED_URDF_DUAL_DIGEST_EQUIVALENCE_NOT_PROVEN" in audit["errors"]


def test_contracts_define_strict_outputs_hausdorff_derate_and_unknown_rules():
    items = _inputs()
    pair_contract, motion_contract = items[3], items[4]
    pair_fields = set(pair_contract["required_common_row_output_fields"]) | set(pair_contract["required_geometric_result_output_fields"])
    assert {
        "pair_id", "q_bytes_sha256", "certified_separation_lower_bound_mm",
        "certified_separation_upper_bound_mm", "certified_margin_lower_bound_mm",
        "certified_margin_upper_bound_mm", "comparison_set_size", "status",
        "reason_codes", "evidence_sha256"
    } <= pair_fields
    assert pair_contract["status_contract"]["UNKNOWN"].endswith("threshold ambiguity")
    assert "never inferred" in pair_contract["status_contract"]["UNSAFE"]
    assert "m_lower_ij <= 0 alone" in pair_contract["geometric_oracle_formulae"]["unsafe_rule"]
    assert "only that SAFE is not certified" in pair_contract["geometric_oracle_formulae"]["threshold_rule"]
    batch = pair_contract["batch_completeness_contract"]
    assert "all 11175 stable pair_id rows" in batch["emitted_pair_set"]
    assert "all 9 active adjacent exception pair_id rows" in batch["exception_row_set"]
    assert "all 11166 query-required pair_id rows" in batch["required_pair_set"]
    assert "All 11175 stable rows are present" in batch["safe_batch"]
    row_schema = pair_contract["row_schema_contract"]
    assert row_schema["discriminator"] == "row_kind"
    assert "forbidden" in row_schema["EXCEPTION_RESULT"]
    exception_fields = set(pair_contract["required_exception_result_output_fields"])
    assert {"exception_rule_id", "exception_rule_sha256", "exception_pair_set_membership_proof_sha256"} <= exception_fields
    assert "allowed_collision_exact_pair_set_sha256" in pair_contract["required_common_row_output_fields"]
    assert "raw_backend_separation_mm" in pair_contract["forbidden_exception_result_fields"]
    c_contract = motion_contract["motion_classes"]["C_SECTION_CAPSULE"]
    assert "d_H" in c_contract["hausdorff_requirement"]
    assert c_contract["current_hausdorff_certificates"] == 0
    assert c_contract["missing_certificate_disposition"] == "UNKNOWN_ABORT"
    assert motion_contract["fail_closed_rules"]["urdf_dual_digest_not_equivalent"] == "FAIL_ABORT"
    assert motion_contract["fail_closed_rules"]["missing_execution_mount_numeric_spelling_policy"] == "UNKNOWN_ABORT"
    assert motion_contract["fail_closed_rules"]["missing_collision_asset_frame_registration"] == "UNKNOWN_ABORT"
    motion_bound = motion_contract["global_motion_bound_definition"]
    assert "<= B_i_cert" in motion_bound["per_object_interval_bound"]
    assert "define B_i_cert :=" in motion_bound["coefficient_form"]
    assert "B_i <=" not in motion_bound["coefficient_form"]
    outputs = set(motion_contract["required_object_certificate_output_fields"])
    assert "geometry_reference_radius_mm" in outputs
    assert "fixed_translation_bound_mm" not in outputs
    accounting = motion_contract["coefficient_accounting_contract"]
    assert "full declared q domain" in accounting["global_axis_distance_supremum"]
    assert "never a q=0 radius" in accounting["global_axis_distance_supremum"]
    assert "complete clipped J3" in accounting["hidden_travel_in_full_locus"]
    assert "never added to B_i_cert" in accounting["geometry_reference_radius_mm"]
    assert "exactly once" in accounting["class_specific_hidden_motion"]
    assert "must not be omitted or double-counted" in accounting["single_count_rule"]
    assert "final all-inclusive global_L_i" in motion_contract["motion_classes"]["J3_HIDDEN_TRANSLATION"]["bound_formula"]
    assert "final all-inclusive global_L_i" in motion_contract["motion_classes"]["J4_TRAVEL_TRANSLATION"]["hidden_bound_formula"]


def _valid_geometric_numeric_record():
    pose = [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]
    raw = 2.3
    debit_a = 0.1
    debit_b = 0.1
    debit_backend = 0.1
    lower = ((raw - debit_a) - debit_b) - debit_backend
    upper = 2.2
    required = 1.0
    return {
        "clearance_policy_sha256": "A" * 64,
        "authorized_pair_min_mm": 1.0,
        "required_clearance_mm": required,
        "status": "SAFE",
        "complete": True,
        "finite": True,
        "raw_backend_separation_mm": raw,
        "object_a_hausdorff_derate_mm": debit_a,
        "object_b_hausdorff_derate_mm": debit_b,
        "backend_numeric_derate_mm": debit_backend,
        "certified_separation_lower_bound_mm": lower,
        "certified_separation_upper_bound_mm": upper,
        "certified_upper_bound_evidence_sha256": "B" * 64,
        "certified_margin_lower_bound_mm": lower - required,
        "certified_margin_upper_bound_mm": upper - required,
        "comparison_set_size": 4,
        "geometry_a_pose_S_row_major_binary64": pose,
        "geometry_b_pose_S_row_major_binary64": pose.copy(),
        "witness_point_a_S_mm": [0.0, 0.0, 0.0],
        "witness_point_b_S_mm": [2.3, 0.0, 0.0],
        "intersection_or_contact_certified": False,
        "unsafe_witness_authority_sha256": None,
    }


def test_numeric_record_firewall_accepts_consistent_safe_fixture():
    assert MODULE.validate_geometric_numeric_record(_valid_geometric_numeric_record()) == []


@pytest.mark.parametrize("mutation,expected", [
    ("negative_required", "REQUIRED_CLEARANCE_INVALID"),
    ("below_policy", "REQUIRED_CLEARANCE_BELOW_POLICY"),
    ("negative_derate", "OBJECT_A_HAUSDORFF_DERATE_MM_NEGATIVE"),
    ("nan_derate", "BACKEND_NUMERIC_DERATE_MM_NONFINITE"),
    ("inverted_interval", "CERTIFIED_INTERVAL_INVERTED"),
    ("inflated_lower", "CERTIFIED_LOWER_BOUND_FORMULA_MISMATCH"),
    ("upper_without_evidence", "CERTIFIED_UPPER_BOUND_EVIDENCE_INVALID"),
    ("negative_upper", "CERTIFIED_UPPER_BOUND_NEGATIVE"),
    ("zero_comparisons", "COMPARISON_SET_SIZE_NOT_POSITIVE_INTEGER"),
    ("boolean_comparisons", "COMPARISON_SET_SIZE_NOT_POSITIVE_INTEGER"),
    ("bad_pose", "GEOMETRY_A_POSE_S_ROW_MAJOR_BINARY64_INVALID"),
    ("lower_only_false_unsafe", "UNSAFE_WITHOUT_CERTIFIED_UPPER_MARGIN_OR_WITNESS"),
])
def test_numeric_record_firewall_rejects_false_safe_and_malformed_values(mutation, expected):
    record = _valid_geometric_numeric_record()
    if mutation == "negative_required":
        record["required_clearance_mm"] = -0.1
    elif mutation == "below_policy":
        record["required_clearance_mm"] = 0.5
    elif mutation == "negative_derate":
        record["object_a_hausdorff_derate_mm"] = -0.1
    elif mutation == "nan_derate":
        record["backend_numeric_derate_mm"] = float("nan")
    elif mutation == "inverted_interval":
        record["certified_separation_lower_bound_mm"] = 2.4
        record["certified_margin_lower_bound_mm"] = 1.4
    elif mutation == "inflated_lower":
        record["certified_separation_lower_bound_mm"] += 0.5
        record["certified_margin_lower_bound_mm"] += 0.5
    elif mutation == "upper_without_evidence":
        record["certified_upper_bound_evidence_sha256"] = None
    elif mutation == "negative_upper":
        record["certified_separation_upper_bound_mm"] = -0.1
        record["certified_margin_upper_bound_mm"] = -1.1
    elif mutation == "zero_comparisons":
        record["comparison_set_size"] = 0
    elif mutation == "boolean_comparisons":
        record["comparison_set_size"] = True
    elif mutation == "bad_pose":
        record["geometry_a_pose_S_row_major_binary64"] = [1.0] * 15
    elif mutation == "lower_only_false_unsafe":
        record["status"] = "UNSAFE"
        record["certified_separation_lower_bound_mm"] = 0.5
        record["certified_margin_lower_bound_mm"] = -0.5
        record["certified_separation_upper_bound_mm"] = 2.0
        record["certified_margin_upper_bound_mm"] = 1.0
    errors = MODULE.validate_geometric_numeric_record(record)
    assert expected in errors


def test_gate_is_hold_with_zero_certificates_and_all_authorities_false():
    gate = MODULE.build_gate(MODULE.ROOT)
    assert all(gate["checks"].values())
    ready = gate["current_readiness"]
    assert ready["system_certified_object_motion_bound_count"] == 0
    assert ready["urdf_content_identity_bound"] is True
    assert ready["physical_dynamics_bridge_bound"] is True
    assert ready["execution_mount_numeric_spelling_bound"] is False
    assert ready["collision_asset_frame_registration_bound"] is False
    assert ready["clearance_policy_bound"] is False
    assert ready["system_pair_queries_executed"] == 0
    assert ready["system_edges_certified"] == 0
    for key in (
        "complete_system_collision_pass", "pair_evaluation_authorized",
        "edge_evaluation_authorized", "path_search_authorized",
        "path_search_executed", "next_stage_authorized", "release_credit"
    ):
        assert ready[key] is False
    assert gate["verdict"].endswith("PAIR_EDGE_PATH_RELEASE_HOLD")
    assert "HASH_BOUND_PER_PAIR_CLEARANCE_POLICY_ABSENT" in gate["blockers"]


def test_builder_is_deterministic_and_manifest_is_not_self_referential():
    gate1, manifest1 = MODULE.expected_outputs(MODULE.ROOT)
    gate2, manifest2 = MODULE.expected_outputs(MODULE.ROOT)
    assert gate1 == gate2
    assert manifest1 == manifest2
    assert MODULE.MANIFEST_REL.as_posix().encode("utf-8") not in manifest1
    assert MODULE.GATE_REL.as_posix().encode("utf-8") in manifest1
    parsed = json.loads(gate1)
    assert parsed["read_scope"]["current_geometry_loaded"] is False
    assert parsed["read_scope"]["pair_query_executed"] is False
    assert parsed["read_scope"]["edge_query_executed"] is False
    assert parsed["read_scope"]["path_search_executed"] is False


def test_no_geometry_or_planning_backend_imports():
    source = (HERE / "build_system_binding_readiness.py").read_text(encoding="utf-8")
    forbidden_imports = ("import numpy", "import trimesh", "import FreeCAD", "import fcl", "import pybullet", "import ompl")
    assert not any(token in source for token in forbidden_imports)
    assert MODULE.PROHIBITED_PAYLOAD_SUFFIXES == {".step", ".stp", ".fcstd", ".stl", ".ply", ".obj", ".npy", ".npz"}
