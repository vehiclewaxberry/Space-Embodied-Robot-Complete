from __future__ import annotations

import ast
import copy
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
REPO = next(parent for parent in HERE.parents if (parent / "PROJECT_MAP.md").is_file())


def import_file(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def builder():
    return import_file("m01_fixed_platform_builder_test", HERE / "build_m01_fixed_platform_and_base_motion_precert.py")


@pytest.fixture(scope="module")
def validator():
    return import_file("m01_fixed_platform_validator_test", HERE / "validate_m01_fixed_platform_and_base_motion_precert.py")


@pytest.fixture(scope="module")
def documents(validator):
    return validator.load_documents()


def test_builder_deterministically_reproduces_outputs(builder):
    assert builder.check_outputs(REPO) == HERE


def test_strict_validator_passes_full_package(validator):
    summary = validator.validate_on_disk(REPO)
    assert summary["status"] == "PASS"
    assert summary["source_pins_verified"] == 28
    assert summary["gate_checks_passed"] == summary["gate_checks_total"] == 30
    assert summary["builder_imported_or_executed"] is False
    assert summary["builder_receipt_structural_rows"] == 24
    assert summary["builder_receipt_used_as_gate_evidence"] is False
    assert summary["independent_builder_case_replays_rejected"] == 24
    assert summary["independent_negative_controls_rejected"] == 66
    assert len(summary["independent_negative_control_receipt_sha256"]) == 64


def test_validator_ast_has_no_builder_import_or_dynamic_import():
    source = (HERE / "validate_m01_fixed_platform_and_base_motion_precert.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "importlib" not in imported
    assert not any("build_m01_fixed_platform" in name for name in imported)
    assert "load_builder" not in source
    assert "builder." not in source


def test_all_dependency_hash_pins_match(builder):
    assert len(builder.SOURCE_PINS) == 28
    for _source_id, (rel_path, expected, _role) in builder.SOURCE_PINS.items():
        assert hashlib.sha256((REPO / rel_path).read_bytes()).hexdigest().upper() == expected


def test_fixed_platform_ledger_has_exact_three_objects(builder, documents):
    pose = documents[builder.POSE_NAME]
    assert [row["object_id"] for row in pose["entries"]] == [
        "F::LOAD_BRIDGE",
        "F::M3R_STAGE_A",
        "F::M3R_STAGE_B",
    ]
    assert pose["accounting"]["design_level_pose_entries_bound"] == 3


def test_load_bridge_step_is_already_in_S_and_transform_is_identity(builder, documents):
    load = documents[builder.POSE_NAME]["entries"][0]
    assert load["geometry_asset"]["asset_storage_frame"] == "S"
    assert load["geometry_asset"]["step_reopen_bbox_S_mm"][0] == 185.25
    assert load["geometry_asset"]["step_reopen_bbox_S_mm"][3] == 196.0
    assert load["T_S_asset_rows"] == builder.IDENTITY_4
    assert load["local_design_datum"]["runtime_application_to_step_asset"] is False
    assert load["double_transform_forbidden"] is True


def test_m3r_stages_use_local_identity_and_same_full_precision_S_transform(builder, documents):
    rows = {row["object_id"]: row for row in documents[builder.POSE_NAME]["entries"]}
    for object_id in ("F::M3R_STAGE_A", "F::M3R_STAGE_B"):
        assert rows[object_id]["T_M3R_LOCAL_asset_rows"] == builder.IDENTITY_4
        assert rows[object_id]["T_S_asset_rows_mm"] == builder.M3R_S_ROWS_EXPECTED
        assert rows[object_id]["geometry_asset"]["expected_solid_count"] == 1


def test_fixed_platform_entries_never_gain_operational_motion_or_pair_credit(builder, documents):
    for row in documents[builder.POSE_NAME]["entries"]:
        assert row["design_level_pose_bound"] is True
        assert row["asset_level_operational_authority"] is False
        assert row["system_motion_authority"] is False
        assert row["pair_eligible"] is False
        assert row["pair_evaluation_authorized"] is False


def test_independent_urdf_graph_recompute_finds_unique_base_root(builder, documents):
    urdf = documents[builder.RECOMPUTE_NAME]["urdf_graph_recompute"]
    assert urdf["root_links"] == ["base_link"]
    assert urdf["base_link_parent_joint_count"] == 0
    assert urdf["raw_bytes_sha256"] == builder.SOURCE_PINS["accepted_urdf"][1]
    assert urdf["lf_normalized_sha256"] == "408147DDC9CC0BBA0FACBF864C559A54D1712262703BA41251514A4303B5A3A4"


def test_full_six_joint_domain_is_exact(builder, documents):
    urdf = documents[builder.RECOMPUTE_NAME]["urdf_graph_recompute"]
    assert urdf["q_order"] == builder.Q_ORDER
    assert urdf["q_domain_lower_rad"] == builder.EXPECTED_Q_LOWER
    assert urdf["q_domain_upper_rad"] == builder.EXPECTED_Q_UPPER


def test_mount_and_registration_are_rigid_and_identity_registered(builder, documents):
    recompute = documents[builder.RECOMPUTE_NAME]
    metrics = recompute["execution_mount_recompute"]["metrics"]
    assert metrics["orthonormal_max_abs_residual"] <= 1.0e-12
    assert abs(metrics["determinant"] - 1.0) <= 1.0e-12
    assert metrics["homogeneous_bottom_row_max_abs_residual"] == 0.0
    registration = recompute["collision_registration_recompute"]
    assert registration["T_registration_frame_asset_storage_rows"] == builder.IDENTITY_4
    assert registration["operational_narrowphase_promoted"] is True
    assert registration["scene_state_variable"] is None


def test_bbox_and_conservative_radius_are_independently_recomputed(builder, validator, documents):
    independent = validator.independent_geometry_recompute(REPO)
    emitted = documents[builder.RECOMPUTE_NAME]["geometry_recompute"]
    assert emitted["mesh_bbox_mm"] == independent["bbox_mm"]
    assert emitted["geometry_reference_radius_mm"] == independent["conservative_radius_mm"]
    assert math.isclose(emitted["geometry_reference_radius_mm"], 105.18157763600612, rel_tol=0.0, abs_tol=1.0e-12)
    assert emitted["geometry_reference_radius_mm"] >= emitted["mesh_max_vertex_radius_mm"]


def test_zero_motion_proof_covers_full_q_and_scene_schema_domain(builder, documents):
    proof = documents[builder.RECOMPUTE_NAME]["full_domain_zero_motion_proof"]
    assert proof["proof_domain_complete"] is True
    assert proof["scene_state_domain_sha256"] == builder.SOURCE_PINS["scene_schema_v2"][1]
    assert proof["scene_authoritative_values_consumed"] == 0
    assert proof["global_L_mm_per_rad"] == [0.0] * 6
    assert len(proof["sample_replay"]) == 15
    assert all(row["max_abs_residual_vs_canonical_mount"] == 0.0 for row in proof["sample_replay"])


def test_motion_certificate_contains_all_pinned_contract_fields(builder, documents):
    contract = json.loads((REPO / builder.SOURCE_PINS["object_motion_contract"][0]).read_text(encoding="utf-8"))
    cert = documents[builder.CERT_NAME]
    assert set(contract["required_object_certificate_output_fields"]) <= set(cert)
    assert set(contract["required_object_certificate_input_fields"]) <= set(cert["input_binding"])
    assert cert["object_id"] == "A::base_link"
    assert cert["motion_class"] == "DIRECT_RIGID_FK_CANDIDATE"
    assert cert["status"] == "CERTIFIED_REGISTERED_ASSET_MOTION_ONLY"
    assert cert["proof_domain_complete"] is True


def test_motion_certificate_is_exactly_zero_motion_and_pair_ineligible(builder, documents):
    cert = documents[builder.CERT_NAME]
    assert cert["global_L_mm_per_rad"] == [0.0] * 6
    assert cert["system_motion_authority_credit"] == 1
    assert cert["runtime_object_pose_bound"] is True
    assert cert["pair_eligible"] is False
    assert cert["pair_derating_authority_bound"] is False
    assert cert["pair_evaluation_authorized"] is False


def test_pair_derating_unknowns_are_null_never_zero_filled(builder, documents):
    cert = documents[builder.CERT_NAME]
    assert all(field in cert and cert[field] is None for field in builder.PAIR_DERATE_FIELDS)
    policy = cert["pair_derate_nullability"]
    assert policy["automatic_zero_fill_forbidden"] is True
    assert policy["unknown_fields"] == builder.PAIR_DERATE_FIELDS


def test_gate_has_exact_authorized_and_held_counts(builder, documents):
    gate = documents[builder.GATE_NAME]
    counters = gate["counters"]
    assert counters["authoritative_scene_values_bound"] == 0
    assert counters["authoritative_scene_values_required"] == 30
    assert counters["stage_instances_bound"] == 0
    assert counters["stage_instances_required"] == 3
    assert counters["fixed_platform_design_pose_bindings"] == 3
    assert counters["system_motion_certificates_bound"] == 1
    assert counters["system_motion_certificates_required"] == 150
    assert counters["remaining_objects_without_system_motion_certificate"] == 149


def test_pair_clearance_edge_path_next_and_release_all_remain_held(builder, documents):
    gate = documents[builder.GATE_NAME]
    counters = gate["counters"]
    assert counters["clearance_policy_rows_bound"] == 0
    assert counters["clearance_policy_rows_required"] == 11166
    assert counters["pair_queries_executed"] == 0
    assert counters["pair_queries_required"] == 11166
    assert counters["system_safe_pairs_certified"] == 0
    assert counters["edges_certified"] == 0
    assert counters["path_search_authorized"] is False
    assert counters["path_search_executed"] is False
    assert gate["next_stage_authorized"] is False
    assert gate["release_credit"] is False


def test_route_c_signed_witness_is_quarantined_with_all_current_bindings_null(builder, documents):
    quarantine = documents[builder.QUARANTINE_NAME]
    assert quarantine["legacy_witness"]["signed_raw_clearance_mm"] == -10.729480331980062
    assert all(value is None for value in quarantine["current_binding"].values())
    assert quarantine["scope_controls"]["imported_as_current_system_pair_result"] is False
    assert quarantine["scope_controls"]["counts_as_pair_query_executed"] is False
    assert quarantine["scope_controls"]["alternative_path_impossibility_proven"] is False


def test_builder_receipt_is_twenty_four_row_diagnostic_only(builder, documents):
    negative = documents[builder.NEGATIVE_NAME]
    assert negative["authority"] == "BUILDER_PREEMISSION_DIAGNOSTIC_STRUCTURE_ONLY__NOT_GATE_EVIDENCE"
    assert negative["accounting"] == {
        "cases_rejected": 24,
        "cases_total": 24,
        "unexpected_acceptances": 0,
    }
    assert len({case["case_id"] for case in negative["cases"]}) == 24
    assert all(case["rejected"] and case["expected_rejection_code"] in case["actual_rejection_codes"] for case in negative["cases"])


def test_forged_builder_receipt_outcomes_cannot_supply_gate_evidence(validator, documents):
    candidate = copy.deepcopy(documents)
    diagnostic = candidate[validator.NEGATIVE_NAME]
    diagnostic["accounting"] = {"cases_total": 24, "cases_rejected": 0, "unexpected_acceptances": 24}
    for case in diagnostic["cases"]:
        case["actual_rejection_codes"] = []
        case["rejected"] = False
    candidate_hashes = {
        name: validator.emitted_artifact_digest(candidate[name])
        for name in (
            validator.POSE_NAME,
            validator.RECOMPUTE_NAME,
            validator.CERT_NAME,
            validator.QUARANTINE_NAME,
            validator.NEGATIVE_NAME,
        )
    }
    for name, digest in candidate_hashes.items():
        candidate[validator.GATE_NAME]["local_artifact_pins"][name] = {"path": name, "sha256": digest}
    summary = validator.validate_candidate_documents(
        REPO,
        candidate,
        validate_local_hashes=False,
        candidate_local_hashes=candidate_hashes,
    )
    assert summary["status"] == "PASS"


def test_independent_negative_suite_reexecutes_without_receipt(validator, documents):
    reference = validator.build_reference(REPO)
    receipt = validator.run_independent_negative_controls(REPO, documents, reference)
    assert receipt["receipt_consulted"] is False
    assert receipt["builder_receipt_used_as_gate_evidence"] is False
    assert receipt["accounting"] == {
        "cases_total": 66,
        "cases_rejected": 66,
        "unexpected_acceptances": 0,
    }
    assert len({case["case_id"] for case in receipt["cases"]}) == 66
    assert len(receipt["builder_case_replay"]) == 24
    assert all(row["rejected"] is True for row in receipt["builder_case_replay"])


def test_six_artifact_top_level_allowlists_are_exact(validator, documents):
    assert set(validator.TOP_LEVEL_KEYS) == set(validator.JSON_ARTIFACT_NAMES)
    for name in validator.JSON_ARTIFACT_NAMES:
        assert set(documents[name]) == validator.TOP_LEVEL_KEYS[name]


def test_frozen_cert_and_gate_fields_have_rehash_escape_controls(validator, documents):
    receipt = validator.run_independent_negative_controls(REPO, documents, validator.build_reference(REPO))
    cases = {case["case_id"]: case for case in receipt["cases"]}
    cert_cases = [case for case in cases.values() if "_CERT_FROZEN_" in case["case_id"]]
    gate_cases = [case for case in cases.values() if "_GATE_FROZEN_" in case["case_id"]]
    assert len(cert_cases) == len(validator.CERT_FROZEN_FIELDS) == 9
    assert len(gate_cases) == len(validator.GATE_FROZEN_FIELDS) == 7
    assert all(case["rejected"] and "gate.local_artifact_pins" in case["downstream_rehashed"] for case in cert_cases)
    assert all(case["rejected"] and "manifest.gate_row" in case["downstream_rehashed"] for case in gate_cases)


def test_numeric_bool_masquerades_and_cache_inventory_are_rejected(validator, documents):
    receipt = validator.run_independent_negative_controls(REPO, documents, validator.build_reference(REPO))
    cases = {case["case_id"]: case for case in receipt["cases"]}
    for case_id in (
        "IV60_BOOL_AS_POSE_COUNT",
        "IV61_BOOL_AS_RECOMPUTE_COUNT",
        "IV62_BOOL_AS_CERT_MOTION_COUNT",
        "IV63_BOOL_AS_CERT_RADIUS",
        "IV64_BOOL_AS_GATE_COUNT",
        "IV65_BOOL_AS_RECOMPUTE_RADIUS",
        "IV66_CACHE_DIRECTORY",
    ):
        assert cases[case_id]["rejected"] is True


@pytest.mark.parametrize("payload,code", [
    ('{"x":1,"x":2}', "DUPLICATE_JSON_KEY"),
    ('{"x":NaN}', "NONFINITE_JSON_CONSTANT"),
    ('{"x":Infinity}', "NONFINITE_JSON_CONSTANT"),
    ('{"x":1e9999}', "NONFINITE_JSON_NUMBER"),
])
def test_strict_json_rejects_duplicates_and_nonfinite(validator, payload, code):
    with pytest.raises(validator.ValidationError) as caught:
        validator.strict_json_text(payload)
    assert caught.value.code == code


def test_red_team_registry_rehash_escape_is_rejected(validator, documents):
    candidate = copy.deepcopy(documents)
    binding = candidate[validator.CERT_NAME]["input_binding"]
    binding["registry_sha256"] = "0" * 64
    candidate[validator.CERT_NAME]["input_binding_sha256"] = validator.canonical_digest(binding)
    with pytest.raises(validator.ValidationError) as caught:
        validator.validate_candidate_documents(REPO, candidate, validate_local_hashes=False, validate_declared_negative=False)
    assert caught.value.code == "INPUT_BINDING_DRIFT"


def test_red_team_replay_l_rehash_escape_is_rejected(validator, documents):
    candidate = copy.deepcopy(documents)
    replay = candidate[validator.CERT_NAME]["deterministic_replay_payload"]
    replay["global_L_mm_per_rad"] = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    candidate[validator.CERT_NAME]["deterministic_replay_sha256"] = validator.canonical_digest(replay)
    with pytest.raises(validator.ValidationError) as caught:
        validator.validate_candidate_documents(REPO, candidate, validate_local_hashes=False, validate_declared_negative=False)
    assert caught.value.code == "DETERMINISTIC_REPLAY_PAYLOAD_DRIFT"


def test_red_team_bbox_nan_escape_is_rejected(validator, documents):
    candidate = copy.deepcopy(documents)
    candidate[validator.RECOMPUTE_NAME]["geometry_recompute"]["mesh_bbox_mm"][0][0] = float("nan")
    with pytest.raises(validator.ValidationError) as caught:
        validator.validate_candidate_documents(REPO, candidate, validate_local_hashes=False, validate_declared_negative=False)
    assert caught.value.code == "NONFINITE_NUMBER"


def test_strict_validator_rejects_live_forbidden_mutations(builder, validator, documents):
    mutations = []

    def mutated(change):
        candidate = copy.deepcopy(documents)
        change(candidate)
        return candidate

    mutations.append((
        "LOAD_BRIDGE_RUNTIME_TRANSFORM_NOT_IDENTITY",
        mutated(lambda docs: docs[builder.POSE_NAME]["entries"][0].update({"T_S_asset_rows": builder.M3R_S_ROWS_EXPECTED})),
    ))
    mutations.append((
        "FIXED_OPERATIONAL_PROMOTION::F::M3R_STAGE_A",
        mutated(lambda docs: docs[builder.POSE_NAME]["entries"][1].update({"asset_level_operational_authority": True})),
    ))
    mutations.append((
        "MOTION_CERT_L_NOT_SIX_ZEROES",
        mutated(lambda docs: docs[builder.CERT_NAME].update({"global_L_mm_per_rad": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]})),
    ))
    mutations.append((
        "PAIR_DERATE_MUST_REMAIN_NULL::model_uncertainty_bound_mm",
        mutated(lambda docs: docs[builder.CERT_NAME].update({"model_uncertainty_bound_mm": 0.0})),
    ))
    mutations.append((
        "V9F_CURRENT_BINDING_NOT_ALL_NULL",
        mutated(lambda docs: docs[builder.QUARANTINE_NAME]["current_binding"].update({"current_system_pair_id": "A::link3||C::SEG-04"})),
    ))
    mutations.append((
        "GATE_COUNTERS_DRIFT",
        mutated(lambda docs: docs[builder.GATE_NAME]["counters"].update({"pair_queries_executed": 1})),
    ))
    for expected_code, candidate in mutations:
        with pytest.raises(validator.ValidationError) as caught:
            validator.validate_candidate_documents(REPO, candidate, validate_local_hashes=False)
        assert caught.value.code == expected_code


def test_gate_is_30_of_30_append_only_hold(builder, documents):
    gate = documents[builder.GATE_NAME]
    assert gate["checks_passed"] == gate["checks_total"] == 30
    assert all(gate["checks"].values())
    assert gate["append_only_package_complete"] is True
    assert gate["fixed_platform_pose_prebind_pass"] is True
    assert gate["base_link_motion_precert_pass"] is True
    assert gate["system_collision_gate_pass"] is False
    assert gate["system_path_gate_pass"] is False
    assert "BASE_MOTION_1_OF_150" in gate["verdict"]
    assert "SCENE_PAIR_EDGE_PATH_AND_RELEASE_HOLD" in gate["verdict"]


def test_manifest_is_fresh_complete_self_excluded_and_package_local(builder):
    manifest = HERE / builder.MANIFEST_NAME
    with manifest.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    names = {row["path"] for row in rows}
    assert builder.MANIFEST_NAME not in names
    required = {
        "README.md",
        "build_m01_fixed_platform_and_base_motion_precert.py",
        "validate_m01_fixed_platform_and_base_motion_precert.py",
        "test_m01_fixed_platform_and_base_motion_precert.py",
        builder.POSE_NAME,
        builder.RECOMPUTE_NAME,
        builder.CERT_NAME,
        builder.QUARANTINE_NAME,
        builder.NEGATIVE_NAME,
        builder.GATE_NAME,
    }
    assert required == names
    assert len(rows) == len(names)
    for row in rows:
        rel = Path(row["path"])
        assert not rel.is_absolute() and ".." not in rel.parts
        artifact = HERE / rel
        payload = artifact.read_bytes()
        assert len(payload) == int(row["bytes"])
        assert hashlib.sha256(payload).hexdigest().upper() == row["sha256"]
