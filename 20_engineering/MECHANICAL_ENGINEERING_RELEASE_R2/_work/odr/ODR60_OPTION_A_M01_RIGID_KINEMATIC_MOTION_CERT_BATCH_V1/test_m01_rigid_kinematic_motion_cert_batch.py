from __future__ import annotations

import copy
import csv
import importlib.util
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest


PACKAGE = Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, PACKAGE / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_module("rigid_batch_validator", "validate_m01_rigid_kinematic_motion_cert_batch.py")


def load_json(name: str):
    return validator.strict_json_file(PACKAGE / name)


def load_eligibility():
    with (PACKAGE / validator.ELIGIBILITY_NAME).open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def test_standalone_release_validator_passes():
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-B", str(PACKAGE / "validate_m01_rigid_kinematic_motion_cert_batch.py"), "--release"],
        cwd=validator.PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "STANDALONE_RELEASE_VALIDATION_PASS" in result.stdout


def test_validator_does_not_import_or_execute_builder():
    text = (PACKAGE / "validate_m01_rigid_kinematic_motion_cert_batch.py").read_text(encoding="utf-8")
    assert "import build_m01_rigid_kinematic_motion_cert_batch" not in text
    assert "from build_m01_rigid_kinematic_motion_cert_batch" not in text
    receipt = load_json(validator.RELEASE_RECEIPT_NAME)
    assert receipt["builder_imported_or_executed"] is False


def test_all_frozen_source_pins_match():
    assert validator.verify_sources() == validator.FROZEN_SOURCES


def test_registry_and_motion_class_counts_are_exact():
    context = validator.load_authoritative_context()
    assert context["category_counts"] == {"A": 10, "C": 9, "F": 4, "R": 121, "S": 6}
    assert context["class_counts"] == {
        "DIRECT_RIGID_FK_CANDIDATE": 124,
        "J3_HIDDEN_TRANSLATION": 8,
        "J4_TRAVEL_TRANSLATION": 9,
        "C_SECTION_CAPSULE": 9,
    }


def test_only_base_link_is_asset_level_operational():
    context = validator.load_authoritative_context()
    operational = [key for key, row in context["active_readiness"].items() if row["operational_authority"] == "true"]
    assert operational == ["A::base_link"]


def test_all_ten_A_collision_registrations_are_finite_identity_se3():
    context = validator.load_authoritative_context()
    assert context["registration_se3"] == {
        "registration_count": 10,
        "finite_legal_se3_count": 10,
        "identity_link_frame_registration_count": 10,
        "rotation_determinant": 1.0,
        "maximum_orthogonality_error": 0.0,
    }
    for row in context["registrations"].values():
        assert row["accepted_urdf_registration_frame"] == row["asset_storage_frame"]
        assert row["T_registration_frame_asset_storage"] == {
            "rotation": "IDENTITY", "translation": [0.0, 0.0, 0.0], "translation_unit": "m"
        }


def test_registration_transform_mutations_fail_closed():
    context = validator.load_authoritative_context()
    A_ids = {row["object_id"] for row in context["registry"]["objects"] if row["category"] == "A"}
    cases = [
        ("translation", 1e-6, "A_REGISTRATION_TRANSFORM_NOT_IDENTITY"),
        ("translation", float("inf"), "A_REGISTRATION_TRANSLATION_NOT_FINITE_VECTOR3"),
        ("rotation", "ROT_Z_90", "A_REGISTRATION_ROTATION_NOT_IDENTITY"),
    ]
    for kind, value, code in cases:
        rows = copy.deepcopy(context["registrations"])
        transform = rows["A::link1"]["T_registration_frame_asset_storage"]
        if kind == "translation":
            transform["translation"][0] = value
        else:
            transform["rotation"] = value
        with pytest.raises(validator.ValidationError, match=code):
            validator.validate_A_registration_identity_se3(rows, A_ids)


def test_gripper_axes_limits_and_full_travel_envelope_are_urdf_derived_once():
    context = validator.load_authoritative_context()
    evidence = context["gripper_prismatic"]
    assert set(evidence) == {"A::gripper_left", "A::gripper_right"}
    for object_id, row in evidence.items():
        assert row["axis_norm"] == 1.0
        assert math.isclose(math.sqrt(sum(value * value for value in row["axis_parent_frame"])), 1.0, abs_tol=1e-15)
        assert (row["lower_m"], row["upper_m"], row["stroke_m"], row["full_travel_envelope_m"]) == (
            0.0, 0.0715, 0.0715, 0.0715
        )
        assert row["envelope_composition_rule"].endswith("EXACTLY_ONCE")
        candidate = next(item for item in load_json(validator.CANDIDATE_NAME)["candidates"] if item["object_id"] == object_id)
        expected_radius = validator.upward_mm(candidate["raw_asset_vertex_radius_mm"] / 1000.0 + row["full_travel_envelope_m"])
        assert candidate["geometry_reference_radius_candidate_mm"] == expected_radius
        assert candidate["scene_offset_envelope_mm"] == 71.5


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("registered_axis_norm", "GRIPPER_REGISTERED_AXIS_NOT_UNIT"),
        ("registered_axis_direction", "GRIPPER_REGISTERED_AXIS_DIRECTION_DRIFT"),
        ("urdf_axis_norm", "GRIPPER_PRISMATIC_AXIS_NOT_UNIT"),
        ("urdf_axis_direction", "GRIPPER_REGISTERED_AXIS_DIRECTION_DRIFT"),
        ("urdf_upper_limit", "GRIPPER_PRISMATIC_LIMIT_DRIFT"),
    ],
)
def test_gripper_axis_direction_norm_and_limit_mutations_fail_closed(mutation, expected_code):
    context = validator.load_authoritative_context()
    urdf = copy.deepcopy(context["urdf"])
    registrations = copy.deepcopy(context["registrations"])
    joint = next(item for item in urdf["joints"] if item["name"] == "gripper_joint1")
    if mutation == "registered_axis_norm":
        registrations["A::gripper_left"]["motion_registration"]["axis_in_parent_frame_from_accepted_urdf"] = [0.0, -2.0, 0.0]
    elif mutation == "registered_axis_direction":
        old = registrations["A::gripper_left"]["motion_registration"]["axis_in_parent_frame_from_accepted_urdf"]
        registrations["A::gripper_left"]["motion_registration"]["axis_in_parent_frame_from_accepted_urdf"] = [-value for value in old]
    elif mutation == "urdf_axis_norm":
        joint["axis"] = (2.0, 0.0, 0.0)
    elif mutation == "urdf_axis_direction":
        joint["axis"] = (-1.0, 0.0, 0.0)
    else:
        joint["upper"] = 0.07
    with pytest.raises(validator.ValidationError, match=expected_code):
        validator.validate_gripper_prismatic_contract(urdf, registrations)


def test_eligibility_matrix_is_150_unique_exact_rows():
    headers, rows = load_eligibility()
    context = validator.load_authoritative_context()
    assert headers == validator.ELIGIBILITY_HEADERS
    assert len(rows) == len({row["object_id"] for row in rows}) == 150
    assert rows == validator.expected_eligibility(context)


def test_base_is_observed_but_not_reissued():
    _, rows = load_eligibility()
    base = next(row for row in rows if row["object_id"] == "A::base_link")
    assert base["preexisting_system_certificate_observed"] == "true"
    assert base["batch_system_certificate_emitted"] == "false"
    assert base["disposition"] == "PREEXISTING_APPEND_ONLY_BASE_CERTIFICATE_OBSERVED__NOT_REISSUED"


def test_exact_nine_candidate_ids():
    document = load_json(validator.CANDIDATE_NAME)
    assert [row["object_id"] for row in document["candidates"]] == [
        "A::gripper_left", "A::gripper_link", "A::gripper_right",
        "A::link1", "A::link2", "A::link3", "A::link4", "A::link5", "A::link6",
    ]


def test_all_candidates_are_nonoperational_and_zero_credit():
    document = load_json(validator.CANDIDATE_NAME)
    for row in document["candidates"]:
        assert row["operational_asset_ready"] is False
        assert row["system_certificate_eligible"] is False
        assert type(row["system_motion_authority_credit"]) is int
        assert row["system_motion_authority_credit"] == 0
        assert row["pair_eligible"] is False


def test_all_candidate_numeric_values_are_finite_nonnegative_and_not_bool():
    document = load_json(validator.CANDIDATE_NAME)
    for row in document["candidates"]:
        values = row["global_L_candidate_mm_per_rad"] + [row["geometry_reference_radius_candidate_mm"]]
        assert all(type(value) in (int, float) and not isinstance(value, bool) for value in values)
        assert all(math.isfinite(value) and value >= 0 for value in values)


def test_hard_numeric_link1_vector():
    rows = {row["object_id"]: row for row in load_json(validator.CANDIDATE_NAME)["candidates"]}
    assert rows["A::link1"]["geometry_reference_radius_candidate_mm"] == 99.21635342
    assert rows["A::link1"]["global_L_candidate_mm_per_rad"] == [99.21635342, 0.0, 0.0, 0.0, 0.0, 0.0]


def test_hard_numeric_link6_vector():
    rows = {row["object_id"]: row for row in load_json(validator.CANDIDATE_NAME)["candidates"]}
    assert rows["A::link6"]["geometry_reference_radius_candidate_mm"] == 63.293632881
    assert rows["A::link6"]["global_L_candidate_mm_per_rad"] == [
        781.189126599, 714.186811855, 450.186811855, 201.644258909, 109.783533547, 63.293632881,
    ]


def test_hard_numeric_gripper_right_vector():
    rows = {row["object_id"]: row for row in load_json(validator.CANDIDATE_NAME)["candidates"]}
    assert rows["A::gripper_right"]["scene_offset_envelope_mm"] == 71.5
    assert rows["A::gripper_right"]["geometry_reference_radius_candidate_mm"] == 202.320587227
    assert rows["A::gripper_right"]["global_L_candidate_mm_per_rad"] == [
        1079.926080945, 1012.923766202, 748.923766202, 500.381213256, 408.520487894, 362.030587227,
    ]


def test_gripper_scene_domain_uses_type_domain_without_owner_value():
    rows = {row["object_id"]: row for row in load_json(validator.CANDIDATE_NAME)["candidates"]}
    for object_id, field in [("A::gripper_left", "gripper_joint1_m"), ("A::gripper_right", "gripper_joint2_m")]:
        assert rows[object_id]["scene_type_domain"] == {
            "field": field,
            "domain_m": [0.0, 0.0715],
            "owner_value_consumed": False,
            "edge_rule": "STATE_MUST_BE_CONSTANT_ON_CERTIFIED_EDGE",
        }
        assert rows[object_id]["owner_scene_values_consumed"] == 0


def test_pair_derate_unknowns_are_null_not_zero():
    document = load_json(validator.CANDIDATE_NAME)
    for row in document["candidates"]:
        for key in ["centerline_hausdorff_bound_mm", "radius_uncertainty_bound_mm", "model_uncertainty_bound_mm", "numeric_uncertainty_bound_mm"]:
            assert row[key] is None


def test_system_certificate_batch_is_deliberately_empty():
    batch = load_json(validator.SYSTEM_BATCH_NAME)
    assert batch["system_certificates"] == []
    assert type(batch["batch_new_system_certificate_count"]) is int
    assert batch["batch_new_system_certificate_count"] == 0
    assert batch["batch_system_motion_authority_credit"] == 0


def test_parent_snapshot_and_append_only_observation_are_distinct():
    batch = load_json(validator.SYSTEM_BATCH_NAME)
    assert batch["parent_contract_snapshot"]["parent_system_certified_object_motion_bound_count"] == 0
    assert batch["preexisting_append_only_certificate_observation"]["observed_system_motion_authority_credit"] == 1
    assert batch["effective_observed_append_only_system_certificate_count_after_batch"] == 1
    assert batch["remaining_without_observed_append_only_system_certificate"] == 149


def test_scene_pair_edge_path_release_holds_are_unchanged():
    batch = load_json(validator.SYSTEM_BATCH_NAME)
    assert (batch["scene_authoritative_values_bound"], batch["scene_authoritative_values_required"]) == (0, 30)
    assert (batch["stage_instances_bound"], batch["stage_instances_required"]) == (0, 3)
    assert (batch["clearance_policy_rows_bound"], batch["clearance_policy_rows_required"]) == (0, 11166)
    assert (batch["pair_queries_executed"], batch["pair_queries_required"]) == (0, 11166)
    assert batch["edges_certified"] == 0
    assert all(batch[key] is False for key in ["pair_evaluation_authorized", "edge_evaluation_authorized", "path_search_authorized", "path_search_executed", "next_stage_authorized", "release_credit"])


def test_independent_recompute_covers_all_candidates_and_negatives():
    receipt = load_json(validator.RECOMPUTE_NAME)
    assert receipt["validator_imported_or_executed_builder"] is False
    assert receipt["candidate_comparisons_passed"] == receipt["candidate_comparisons_total"] == 9
    assert receipt["negative_controls_rejected"] == receipt["negative_controls_total"]
    assert receipt["negative_controls_total"] >= 35
    assert receipt["batch_new_system_certificates_recomputed"] == 0


def test_gate_is_exact_28_of_28_and_withholds_system_gate():
    gate = load_json(validator.GATE_NAME)
    assert gate["checks_passed"] == gate["checks_total"] == 28
    assert all(gate["checks"].values())
    assert gate["candidate_bound_gate_pass"] is True
    assert gate["system_motion_certificate_gate_pass"] is False
    assert gate["system_collision_gate_pass"] is False
    assert gate["counters"]["batch_new_system_motion_certificates_bound"] == 0


def test_manifest_is_exact_unique_and_hash_valid():
    headers, rows = validator.parse_manifest(PACKAGE / validator.MANIFEST_NAME)
    validator.validate_manifest_rows(headers, rows)
    assert [row["path"] for row in rows] == validator.INCLUDED_FILES
    assert len(rows) == len({row["path"] for row in rows})


def test_package_has_no_extra_files_or_directories():
    validator.validate_package_file_set(receipt_may_be_absent=False)
    assert not (PACKAGE / "__pycache__").exists()
    assert not (PACKAGE / ".pytest_cache").exists()


def test_release_receipt_binds_sealed_manifest_and_preserves_zero_credit():
    receipt = load_json(validator.RELEASE_RECEIPT_NAME)
    assert receipt["manifest_sha256"] == validator.file_sha(PACKAGE / validator.MANIFEST_NAME)
    assert receipt["gate_sha256"] == validator.file_sha(PACKAGE / validator.GATE_NAME)
    assert receipt["batch_new_system_certificates"] == 0
    assert receipt["all_release_checks_pass"] is True
    assert receipt["release_negative_controls_rejected"] == receipt["release_negative_controls_total"] >= 10


def test_strict_json_rejects_duplicate_nan_and_inf():
    with pytest.raises(validator.ValidationError, match="JSON_DUPLICATE_KEY"):
        validator.strict_json_text('{"x":1,"x":2}')
    for token in ["NaN", "Infinity", "-Infinity"]:
        with pytest.raises(validator.ValidationError, match="JSON_NONFINITE_CONSTANT"):
            validator.strict_json_text('{"x":' + token + "}")


def test_candidate_vectors_are_ancestor_prefix_only():
    rows = {row["object_id"]: row for row in load_json(validator.CANDIDATE_NAME)["candidates"]}
    for index in range(1, 7):
        vector = rows[f"A::link{index}"]["global_L_candidate_mm_per_rad"]
        assert all(value > 0 for value in vector[:index])
        assert all(value == 0 for value in vector[index:])


def test_recomputed_vectors_exactly_equal_artifact_again():
    context = validator.load_authoritative_context()
    artifact = {row["object_id"]: row for row in load_json(validator.CANDIDATE_NAME)["candidates"]}
    for object_id, expected in context["expected_candidates"].items():
        assert artifact[object_id]["global_L_candidate_mm_per_rad"] == expected["L"]
        assert artifact[object_id]["geometry_reference_radius_candidate_mm"] == expected["geometry_reference_radius_mm"]
