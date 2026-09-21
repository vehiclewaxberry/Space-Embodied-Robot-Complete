from __future__ import annotations

import copy
import csv
import io
import ast
import json
import math
from pathlib import Path
import subprocess
import sys

import pytest


PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

import validate_configuration_contract as validator  # noqa: E402
import frozen_contract_v1 as spec  # noqa: E402


@pytest.fixture(scope="module")
def docs():
    return validator.load_core_docs()


@pytest.fixture(scope="module")
def full():
    return validator.validate_full()


@pytest.fixture(scope="module")
def core(docs):
    return validator.evaluate_core(docs)


@pytest.fixture(scope="module")
def negative():
    return validator.run_negative_controls()


def test_full_validation_passes(full):
    assert full["verdict"] == "PASS"


def test_full_validation_is_29_of_29(full):
    assert full["summary"] == {"passed": 29, "total": 29, "failed": []}


def test_source_lock_has_exactly_twenty_sources(docs):
    assert docs["source_lock"]["source_count"] == 20
    assert len(docs["source_lock"]["sources"]) == 20
    assert docs["source_lock"]["all_sources_match"] is True
    assert len({row["source_id"] for row in docs["source_lock"]["sources"]}) == 20
    assert len({row["path"] for row in docs["source_lock"]["sources"]}) == 20


def test_source_lock_matches_every_expected_pin(docs):
    rows = {row["source_id"]: row for row in docs["source_lock"]["sources"]}
    for source_id, (rel, size, digest, role) in validator.EXPECTED_PINS.items():
        assert rows[source_id] == {"source_id": source_id, "path": rel, "bytes": size, "sha256": digest, "role": role, "match": True}


def test_source_files_still_match_pins():
    for _, (rel, size, digest, _) in validator.EXPECTED_PINS.items():
        path = validator.WORKSPACE / rel
        assert path.stat().st_size == size
        assert validator.sha256(path) == digest


@pytest.mark.parametrize("escape", ["duplicate_id", "duplicate_path", "count", "count_type", "all_match"])
def test_source_lock_raw_map_count_and_aggregate_escapes_are_rejected(docs, escape):
    mutated = copy.deepcopy(docs)
    lock = mutated["source_lock"]
    if escape == "duplicate_id":
        lock["sources"][1]["source_id"] = lock["sources"][0]["source_id"]
    elif escape == "duplicate_path":
        lock["sources"][1]["path"] = lock["sources"][0]["path"]
    elif escape == "count":
        lock["source_count"] = 19
    elif escape == "count_type":
        lock["source_count"] = 20.0
    else:
        lock["all_sources_match"] = False
    result = validator.evaluate_core(mutated)
    assert not result["checks"]["CORE01_SOURCE_PINS_EXACT"]["pass"]


def test_crosswalk_has_exactly_nine_unique_ids(docs):
    rows = docs["crosswalk"]["records"]
    assert len(rows) == 9
    assert {r["configuration_id"] for r in rows} == set(validator.CONFIG_NAMES)


def test_crosswalk_preserves_legacy_aliases(docs):
    rows = {r["configuration_id"]: r for r in docs["crosswalk"]["records"]}
    assert {cid: rows[cid]["m4_legacy_alias"] for cid in rows} == validator.LEGACY_NAMES


def test_only_c01_is_selected_current_r2(docs):
    selected = [r["configuration_id"] for r in docs["crosswalk"]["records"] if r["selected_current_r2"]]
    assert selected == ["C01"]


def test_mass_view_has_nine_design_candidates(docs):
    assert docs["mass"]["model_class"] == "DESIGN_MODEL_CANDIDATE_ONLY_NOT_AS_BUILT"
    assert len(docs["mass"]["configurations"]) == 9


def test_mass_view_is_bit_exact_to_design_ssot(docs):
    source = validator.load_sources()["design_mass"]
    source_rows = {r["configuration_id"]: r for r in source["configurations"]}
    for row in docs["mass"]["configurations"]:
        src = source_rows[row["configuration_id"]]
        assert row["mass_kg"] == src["mass"]["value_kg"]
        assert row["cg_S_m"] == src["center_of_mass"]["xyz_m"]
        assert row["inertia_about_system_cg_S_kg_m2"] == src["inertia"]["components_kg_m2"]


def test_as_built_mass_fields_are_all_null(docs):
    for row in docs["mass"]["configurations"]:
        assert row["as_built_mass_kg"] is None
        assert row["as_built_cg_S_m"] is None
        assert row["as_built_inertia_kg_m2"] is None


def test_all_ssot_design_checks_and_inertia_physics_checks_pass(core):
    assert core["checks"]["CORE06_DESIGN_CHECKS_SSOT_EXACT_MIN_EIGENVALUE_IEEE754_AND_INERTIA_PHYSICS"]["pass"]


def test_mass_audit_separates_180_unique_leaves_from_36_receipt_rechecks(core):
    detail = core["checks"]["CORE05_MASS_CG_INERTIA_IEEE754_BIT_EXACT_AND_TYPE_AUDITED"]["detail"]
    assert detail["unique_core_binary64_leaves_checked"] == detail["expected_unique_core"] == 180
    assert detail["receipt_binary64_rechecks"] == detail["expected_receipt_rechecks"] == 36
    assert detail["total_binary64_comparisons"] == 216
    assert all(not row["type_or_bit_errors"] for row in detail["configurations"].values())


def test_min_eigenvalue_is_bit_exact_to_ssot_and_receipt(core):
    detail = core["checks"]["CORE06_DESIGN_CHECKS_SSOT_EXACT_MIN_EIGENVALUE_IEEE754_AND_INERTIA_PHYSICS"]["detail"]
    assert detail["ssot_min_eigenvalue_binary64_leaves_checked"] == 9
    assert detail["receipt_min_eigenvalue_binary64_rechecks"] == 9
    assert all(row["design_checks_exact"] for row in detail["configurations"].values())


def test_every_design_checks_field_matches_ssot_and_receipt(docs):
    sources = validator.load_sources()
    ssot = {row["configuration_id"]: row["checks"] for row in sources["design_mass"]["configurations"]}
    receipts = {row["configuration_id"]: row["checks"] for row in sources["design_mass_receipt"]["per_configuration"]}
    for row in docs["mass"]["configurations"]:
        cid = row["configuration_id"]
        checks = row["design_checks_from_ssot"]
        assert set(checks) == spec.EXPECTED_DESIGN_CHECK_KEYS
        assert validator.audit_binary64_tree(checks, ssot[cid])[0]
        assert validator.audit_binary64_tree(checks, receipts[cid])[0]


def test_design_checks_boolean_tamper_is_rejected(docs):
    mutated = copy.deepcopy(docs)
    mutated["mass"]["configurations"][0]["design_checks_from_ssot"]["non_solar_members_carried_verbatim"] = False
    result = validator.evaluate_core(mutated)
    assert not result["checks"]["CORE06_DESIGN_CHECKS_SSOT_EXACT_MIN_EIGENVALUE_IEEE754_AND_INERTIA_PHYSICS"]["pass"]


def test_min_eigenvalue_one_ulp_tamper_is_rejected(docs):
    mutated = copy.deepcopy(docs)
    checks = mutated["mass"]["configurations"][0]["design_checks_from_ssot"]
    checks["min_eigenvalue_kg_m2"] = math.nextafter(checks["min_eigenvalue_kg_m2"], math.inf)
    result = validator.evaluate_core(mutated)
    assert not result["checks"]["CORE06_DESIGN_CHECKS_SSOT_EXACT_MIN_EIGENVALUE_IEEE754_AND_INERTIA_PHYSICS"]["pass"]


def test_mass_integer_downcast_fails_binary64_audit(docs):
    mutated = copy.deepcopy(docs)
    mutated["mass"]["configurations"][0]["mass_kg"] = 31
    result = validator.evaluate_core(mutated)
    assert not result["checks"]["CORE05_MASS_CG_INERTIA_IEEE754_BIT_EXACT_AND_TYPE_AUDITED"]["pass"]


def test_mass_one_ulp_change_fails_binary64_audit(docs):
    mutated = copy.deepcopy(docs)
    current = mutated["mass"]["configurations"][0]["mass_kg"]
    mutated["mass"]["configurations"][0]["mass_kg"] = math.nextafter(current, math.inf)
    result = validator.evaluate_core(mutated)
    assert not result["checks"]["CORE05_MASS_CG_INERTIA_IEEE754_BIT_EXACT_AND_TYPE_AUDITED"]["pass"]


def test_state_vector_order_separates_6r_and_2p(docs):
    assert docs["state"]["continuous_state_order"] == ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "gripper_joint1", "gripper_joint2"]
    assert docs["state"]["q6_is_separate_from_discrete_state"] is True


def test_c01_to_c04_q6_are_authority_bound(docs):
    rows = {r["configuration_id"]: r for r in docs["state"]["configurations"]}
    for cid in ("C01", "C02", "C03", "C04"):
        assert rows[cid]["authoritative_state"]["q6_rad"]["value"] == validator.Q_HOME


def test_c05_to_c09_q6_remain_candidates(docs):
    rows = {r["configuration_id"]: r for r in docs["state"]["configurations"]}
    for cid in ("C05", "C06", "C07", "C08", "C09"):
        assert rows[cid]["authoritative_state"]["q6_rad"]["value"] is None
        assert len(rows[cid]["non_authoritative_candidates"]["q6_rad"]["value"]) == 6


def test_every_available_q_is_inside_ehw(docs):
    for row in docs["state"]["configurations"]:
        q = row["authoritative_state"]["q6_rad"]["value"] or row["non_authoritative_candidates"]["q6_rad"]["value"]
        assert all(lo <= v <= hi for v, (lo, hi) in zip(q, validator.JOINT_LIMITS))


def test_c01_qhome_qzero_conflict_is_unresolved(docs):
    conflict = docs["state"]["configurations"][0]["representation_conflicts"]["cad_static_pose_vs_configuration_pose"]
    assert conflict["configuration_semantic_q6_rad"] == validator.Q_HOME
    assert conflict["cad_static_representation_q6_rad"] == [0.0] * 6
    assert conflict["resolved"] is False


def test_c05_fk_hold_is_preserved(docs):
    row = docs["state"]["configurations"][4]
    assert row["operational_state"] == "HOLD_ABORT_ONLY"
    assert "567P734_MM" in row["non_authoritative_candidates"]["q6_rad"]["status"]


def test_all_gripper_values_are_null(docs):
    for row in docs["state"]["configurations"]:
        assert row["authoritative_state"]["gripper_joint1_m"]["value"] is None
        assert row["authoritative_state"]["gripper_joint2_m"]["value"] is None


def test_gripper_domains_are_not_state_values(docs):
    for row in docs["state"]["configurations"]:
        assert row["authoritative_state"]["gripper_joint1_m"]["allowed_domain_m"] == [0.0, 0.0715]
        assert row["authoritative_state"]["gripper_joint2_m"]["allowed_domain_m"] == [0.0, 0.0715]


def test_hdrm_and_latch_unknowns_are_structured_null(docs):
    for row in docs["state"]["configurations"]:
        auth = row["authoritative_state"]
        assert auth["solar_hdrm_state"] == spec.EXPECTED_SOLAR_HDRM_NULL
        assert auth["solar_latch_state"] == spec.EXPECTED_SOLAR_LATCH_NULL
        assert auth["arm_hdrm_state"] == spec.EXPECTED_ARM_HDRM_NULL


@pytest.mark.parametrize("field", ["solar_hdrm_state", "solar_latch_state"])
def test_empty_mapping_cannot_vacuously_pass_structured_null(docs, field):
    mutated = copy.deepcopy(docs)
    mutated["state"]["configurations"][0]["authoritative_state"][field]["value"] = {}
    result = validator.evaluate_core(mutated)
    assert not result["checks"]["CORE12_SOLAR_HDRM_LATCH_AND_ARM_HDRM_STRUCTURED_NULL"]["pass"]


def test_arm_hdrm_wrapper_shape_drift_is_rejected(docs):
    mutated = copy.deepcopy(docs)
    mutated["state"]["configurations"][0]["authoritative_state"]["arm_hdrm_state"] = {"value": None}
    result = validator.evaluate_core(mutated)
    assert not result["checks"]["CORE12_SOLAR_HDRM_LATCH_AND_ARM_HDRM_STRUCTURED_NULL"]["pass"]


def test_c01_solar_transforms_are_bound(docs):
    solar = docs["state"]["configurations"][0]["authoritative_state"]["solar"]
    assert solar["logical_state"]["value"] == "DEPLOYED_NOMINAL_FIXED_SNAPSHOT"
    assert solar["left_transform_S_rows"]["value"][1][3] == 0.1154
    assert solar["right_transform_S_rows"]["value"][1][3] == -0.1154


def test_failure_solar_semantics_do_not_invent_transforms(docs):
    for row in docs["state"]["configurations"][1:4]:
        solar = row["authoritative_state"]["solar"]
        assert solar["failure_retention_semantics"]["value"] == "ATTACHED_STUCK__JETTISON_FORBIDDEN"
        assert solar["left_transform_S_rows"]["value"] is None
        assert solar["right_transform_S_rows"]["value"] is None


def test_c08_c09_target_design_fixtures_are_low_confidence(docs):
    for row in docs["state"]["configurations"][7:9]:
        target = row["authoritative_state"]["target"]
        assert target["scenario_member"]["value"] is True
        assert target["target_attached"]["value"] is True
        assert target["confidence"].startswith("low")
        assert target["operational_attachment_authority"] is False


def test_target_attachment_transforms_are_all_null(docs):
    for row in docs["state"]["configurations"]:
        assert row["authoritative_state"]["target"]["attachment_transform_S_rows"]["value"] is None


def test_geometry_counts_are_fail_closed(docs):
    rows = docs["geometry"]
    assert sum(r["current_complete_integrated_geometry"] == "true" for r in rows) == 0
    assert sum(r["current_source_only_topology_candidate"] == "true" for r in rows) == 1
    assert sum(r["diagnostic_m5_geometry_present"] == "true" for r in rows) == 9
    assert sum(r["released_collision_clear"] == "true" for r in rows) == 0


def test_m5_diagnostic_witness_hashes_resolve(docs):
    for row in docs["geometry"]:
        path = validator.WORKSPACE / row["diagnostic_snapshot_path"]
        assert validator.sha256(path) == row["diagnostic_snapshot_sha256"]
        assert row["diagnostic_mass_properties_authority"] == "false"


def test_geometry_bbox_cells_strictly_parse_and_bit_match_m5(docs):
    source_rows = {
        row["configuration_id"]: row
        for row in validator.load_sources()["m5_geometry_contract"]["records"]
    }
    for row in docs["geometry"]:
        cid = row["configuration_id"]
        bbox_min = validator.parse_bbox_cell(row["diagnostic_bbox_min_S_m"], f"{cid}.min")
        bbox_max = validator.parse_bbox_cell(row["diagnostic_bbox_max_S_m"], f"{cid}.max")
        assert validator.audit_binary64_tree(bbox_min, source_rows[cid]["bbox_S_m"][0])[0]
        assert validator.audit_binary64_tree(bbox_max, source_rows[cid]["bbox_S_m"][1])[0]


def test_malformed_geometry_bbox_is_rejected(docs):
    mutated = copy.deepcopy(docs)
    mutated["geometry"][0]["diagnostic_bbox_min_S_m"] = "[0.0,NaN,1.0]"
    result = validator.evaluate_core(mutated)
    assert not result["checks"]["CORE17_M5_GEOMETRY_WITNESSES_HASHED_BBOX_EXACT_AND_NOT_PROMOTED"]["pass"]


def test_geometry_bbox_one_ulp_drift_is_rejected(docs):
    mutated = copy.deepcopy(docs)
    current = validator.parse_bbox_cell(mutated["geometry"][0]["diagnostic_bbox_min_S_m"], "test")
    current[0] = math.nextafter(current[0], math.inf)
    mutated["geometry"][0]["diagnostic_bbox_min_S_m"] = json.dumps(current, separators=(",", ":"), allow_nan=False)
    result = validator.evaluate_core(mutated)
    assert not result["checks"]["CORE17_M5_GEOMETRY_WITNESSES_HASHED_BBOX_EXACT_AND_NOT_PROMOTED"]["pass"]


def test_all_dynamics_rows_refuse_geometry_and_parent_credit(docs):
    for row in docs["dynamics"]["records"]:
        assert row["design_mass_property_loading_allowed"] is True
        assert row["current_geometry_collision_allowed"] is False
        assert row["target_attachment_plant_allowed"] is False
        assert row["parent_gate_credit"] is False


def test_dynamics_matrix_preserves_abort_and_attachment_boundaries(docs):
    rows = {r["configuration_id"]: r for r in docs["dynamics"]["records"]}
    assert rows["C05"]["maximum_permitted_use"].endswith("POSE_ABORT_HOLD")
    assert rows["C08"]["maximum_permitted_use"].endswith("NO_ATTACHED_PLANT")
    assert rows["C09"]["maximum_permitted_use"].endswith("NO_ATTACHED_PLANT")


def test_all_local_authority_parent_release_next_boundaries_are_false(core):
    check = core["checks"]["CORE20_ALL_LOCAL_TOP_LEVEL_AND_RECURSIVE_AUTHORITY_BOUNDARIES_FALSE"]
    assert check["pass"]
    assert check["detail"]["violations"] == []


def test_candidate_authority_promotion_is_detected(docs):
    mutated = copy.deepcopy(docs)
    mutated["state"]["configurations"][0]["non_authoritative_candidates"]["q6_rad"]["authority"] = True
    result = validator.evaluate_core(mutated)
    assert not result["checks"]["CORE20_ALL_LOCAL_TOP_LEVEL_AND_RECURSIVE_AUTHORITY_BOUNDARIES_FALSE"]["pass"]


def test_released_collision_promotion_is_detected_across_local_views(docs):
    mutated = copy.deepcopy(docs)
    mutated["crosswalk"]["records"][0]["machine_truth_available"]["released_collision_clear"] = True
    result = validator.evaluate_core(mutated)
    assert not result["checks"]["CORE20_ALL_LOCAL_TOP_LEVEL_AND_RECURSIVE_AUTHORITY_BOUNDARIES_FALSE"]["pass"]


def test_configuration_names_are_exact_across_all_five_local_views(core):
    check = core["checks"]["CORE21_CONFIGURATION_NAMES_EXACT_ACROSS_ALL_FIVE_LOCAL_VIEWS"]
    assert check["pass"]
    assert set(check["detail"]) == set(spec.CONFIG_NAMES)


def test_partial_geometry_is_only_c01_and_never_complete(core):
    check = core["checks"]["CORE23_PARTIAL_GEOMETRY_ISOLATED_TO_C01_AND_NEVER_COMPLETE"]
    assert check["pass"]
    assert check["detail"] == {"partial_configuration_ids": ["C01"], "complete_count": 0}


def test_negative_controls_are_thirty_five_of_thirty_five(negative):
    assert negative["summary"] == {"passed": 35, "total": 35, "all_caught": True}
    assert [row["id"] for row in negative["controls"]] == validator.NEGATIVE_CONTROL_IDS


def test_red_team_mutations_cover_new_boundary_and_binary64_classes(negative):
    rows = {row["id"]: row for row in negative["controls"]}
    expected = {
        "NC11_NONFINITE_JSON_INFINITY": "STRICT_PARSER",
        "NC12_DUPLICATE_YAML_KEY": "STRICT_PARSER",
        "NC13_MASS_TYPE_DOWNCAST": "CORE05_MASS_CG_INERTIA_IEEE754_BIT_EXACT_AND_TYPE_AUDITED",
        "NC14_MASS_ONE_ULP_TAMPER": "CORE05_MASS_CG_INERTIA_IEEE754_BIT_EXACT_AND_TYPE_AUDITED",
        "NC15_TOP_LEVEL_NEXT_STAGE_TRUE": "CORE20_ALL_LOCAL_TOP_LEVEL_AND_RECURSIVE_AUTHORITY_BOUNDARIES_FALSE",
        "NC16_TOP_LEVEL_RELEASE_CREDIT_TRUE": "CORE20_ALL_LOCAL_TOP_LEVEL_AND_RECURSIVE_AUTHORITY_BOUNDARIES_FALSE",
        "NC17_OPERATIONAL_AUTHORITY_TRUE": "CORE20_ALL_LOCAL_TOP_LEVEL_AND_RECURSIVE_AUTHORITY_BOUNDARIES_FALSE",
        "NC18_PRODUCTION_COMPLETE_TRUE": "CORE20_ALL_LOCAL_TOP_LEVEL_AND_RECURSIVE_AUTHORITY_BOUNDARIES_FALSE",
        "NC19_PARTIAL_GEOMETRY_SPREAD": "CORE23_PARTIAL_GEOMETRY_ISOLATED_TO_C01_AND_NEVER_COMPLETE",
        "NC20_CONFIGURATION_NAME_DRIFT": "CORE21_CONFIGURATION_NAMES_EXACT_ACROSS_ALL_FIVE_LOCAL_VIEWS",
        "NC26_SOURCE_LOCK_DUPLICATE_ID": "CORE01_SOURCE_PINS_EXACT",
        "NC27_SOURCE_LOCK_DUPLICATE_PATH": "CORE01_SOURCE_PINS_EXACT",
        "NC28_SOURCE_LOCK_COUNT_TAMPER": "CORE01_SOURCE_PINS_EXACT",
        "NC29_SOURCE_LOCK_ALL_MATCH_FALSE": "CORE01_SOURCE_PINS_EXACT",
        "NC30_STRUCTURED_NULL_EMPTY_MAPPING": "CORE12_SOLAR_HDRM_LATCH_AND_ARM_HDRM_STRUCTURED_NULL",
        "NC31_GEOMETRY_BBOX_MALFORMED_JSON": "CORE17_M5_GEOMETRY_WITNESSES_HASHED_BBOX_EXACT_AND_NOT_PROMOTED",
        "NC32_GEOMETRY_BBOX_ONE_ULP_TAMPER": "CORE17_M5_GEOMETRY_WITNESSES_HASHED_BBOX_EXACT_AND_NOT_PROMOTED",
        "NC33_DESIGN_CHECK_BOOLEAN_TAMPER": "CORE06_DESIGN_CHECKS_SSOT_EXACT_MIN_EIGENVALUE_IEEE754_AND_INERTIA_PHYSICS",
        "NC34_MIN_EIGENVALUE_ONE_ULP_TAMPER": "CORE06_DESIGN_CHECKS_SSOT_EXACT_MIN_EIGENVALUE_IEEE754_AND_INERTIA_PHYSICS",
        "NC35_MANIFEST_ROLE_TAMPER": "FULL28_MANIFEST_EXACT_UNIQUE_ROLE_NO_EXTRA_SELF_EXCLUDED",
    }
    assert {control_id: rows[control_id]["expected_failed_check"] for control_id in expected} == expected
    assert all(rows[control_id]["caught"] for control_id in expected)


def test_internal_hash_source_and_manifest_negative_controls_are_caught(negative):
    rows = {row["id"]: row for row in negative["controls"]}
    expected = {
        "NC09_SOURCE_HASH_TAMPER": "CORE01_SOURCE_PINS_EXACT",
        "NC21_GATE_LOCAL_HASH_TAMPER": "FULL27_GATE_COUNTS_FLAGS_SPEC_AND_LOCAL_BINDINGS",
        "NC22_MANIFEST_EXTRA_ROW": "FULL28_MANIFEST_EXACT_UNIQUE_ROLE_NO_EXTRA_SELF_EXCLUDED",
        "NC23_MANIFEST_DUPLICATE_ROW": "FULL28_MANIFEST_EXACT_UNIQUE_ROLE_NO_EXTRA_SELF_EXCLUDED",
        "NC24_SOURCE_PATH_TAMPER": "CORE01_SOURCE_PINS_EXACT",
        "NC25_SPEC_BINDING_HASH_TAMPER": "FULL27_GATE_COUNTS_FLAGS_SPEC_AND_LOCAL_BINDINGS",
        "NC35_MANIFEST_ROLE_TAMPER": "FULL28_MANIFEST_EXACT_UNIQUE_ROLE_NO_EXTRA_SELF_EXCLUDED",
    }
    assert {control_id: rows[control_id]["expected_failed_check"] for control_id in expected} == expected
    assert all(rows[control_id]["caught"] for control_id in expected)


def test_duplicate_json_key_is_rejected():
    with pytest.raises(validator.StrictDataError):
        validator.strict_json_loads('{"x":1,"x":2}')


def test_duplicate_yaml_key_is_rejected():
    with pytest.raises(validator.StrictDataError):
        validator.strict_yaml_loads("x: 1\nx: 2\n")


def test_nonfinite_json_is_rejected():
    with pytest.raises(validator.StrictDataError):
        validator.strict_json_loads('{"x":NaN}')


def test_json_infinity_is_rejected():
    with pytest.raises(validator.StrictDataError):
        validator.strict_json_loads('{"x":Infinity}')


def test_nonfinite_yaml_is_rejected():
    with pytest.raises(validator.StrictDataError):
        validator.strict_yaml_loads("x: .inf\n")


def test_gate_flags_are_all_false():
    gate = validator.read_json(PACKAGE / validator.GATE_FILE)
    assert gate["parent_gate_credit"] is False
    assert gate["parent_gate_reissued"] is False
    assert gate["next_stage_authorized"] is False
    assert gate["release_credit"] is False


def test_gate_has_twenty_six_pass_criteria():
    gate = validator.read_json(PACKAGE / validator.GATE_FILE)
    assert len(gate["criteria"]) == 26
    assert all(row["status"] == "PASS" for row in gate["criteria"])


def test_gate_criterion_ids_exactly_bind_independent_core_and_negative_results(core):
    gate = validator.read_json(PACKAGE / validator.GATE_FILE)
    assert [row["id"] for row in gate["criteria"]] == list(core["checks"]) + ["GATE26_NEGATIVE_CONTROLS_ALL_CAUGHT"]
    assert gate["summary"]["negative_controls"] == "35_OF_35"


def test_gate_binds_every_core_and_negative_artifact():
    gate = validator.read_json(PACKAGE / validator.GATE_FILE)
    expected = set(validator.CORE_FILES.values()) | {validator.NEGATIVE_FILE}
    assert set(gate["local_artifact_bindings"]) == expected
    for rel, binding in gate["local_artifact_bindings"].items():
        path = PACKAGE / rel
        assert binding == {"bytes": path.stat().st_size, "sha256": validator.sha256(path)}


def test_gate_binds_frozen_spec_by_exact_bytes_hash_and_schema():
    gate = validator.read_json(PACKAGE / validator.GATE_FILE)
    path = PACKAGE / validator.SPEC_FILE
    assert gate["contract_spec_binding"] == {
        "path": validator.SPEC_FILE,
        "bytes": path.stat().st_size,
        "sha256": validator.sha256(path),
        "schema": spec.SPEC_SCHEMA,
    }


def test_manifest_has_exactly_fourteen_records():
    rows = validator.read_manifest_csv(PACKAGE / validator.MANIFEST_FILE)
    assert len(rows) == 14


def test_manifest_has_exact_unique_set_with_no_extra_rows():
    rows = validator.read_manifest_csv(PACKAGE / validator.MANIFEST_FILE)
    paths = [row["path"] for row in rows]
    assert len(paths) == len(set(paths))
    assert set(paths) == spec.EXPECTED_MANIFEST_FILES
    assert {row["path"]: row["role"] for row in rows} == spec.EXPECTED_MANIFEST_ROLES


def test_manifest_role_tamper_fails_production_integrity_path():
    rows = validator.read_manifest_csv(PACKAGE / validator.MANIFEST_FILE)
    mutated = copy.deepcopy(rows)
    mutated[0]["role"] = "WRONG_ROLE"
    meta = validator.artifact_metadata(PACKAGE, spec.EXPECTED_MANIFEST_FILES)
    assert not validator.evaluate_manifest_integrity(mutated, meta)["pass"]


def test_manifest_excludes_itself_and_hashes_every_record():
    rows = validator.read_manifest_csv(PACKAGE / validator.MANIFEST_FILE)
    assert validator.MANIFEST_FILE not in {row["path"] for row in rows}
    for row in rows:
        path = PACKAGE / row["path"]
        assert row["bytes"] == str(path.stat().st_size)
        assert row["sha256"] == validator.sha256(path)


def test_generated_csv_files_use_lf_only():
    for rel in (validator.CORE_FILES["geometry"], validator.MANIFEST_FILE):
        assert b"\r" not in (PACKAGE / rel).read_bytes()


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    return imported


def test_builder_validator_and_spec_import_graph_is_acyclic():
    builder_imports = _imported_roots(PACKAGE / "build_configuration_contract.py")
    validator_imports = _imported_roots(PACKAGE / "validate_configuration_contract.py")
    spec_imports = _imported_roots(PACKAGE / validator.SPEC_FILE)
    assert "validate_configuration_contract" not in builder_imports
    assert "build_configuration_contract" not in validator_imports
    assert not ({"build_configuration_contract", "validate_configuration_contract"} & spec_imports)


def test_builder_has_no_validator_evaluation_symbol_references():
    tree = ast.parse((PACKAGE / "build_configuration_contract.py").read_text(encoding="utf-8"))
    referenced_names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not {"evaluate_core", "run_negative_controls", "load_core_docs"} & referenced_names


def test_frozen_spec_has_no_io_or_evaluation_functions():
    tree = ast.parse((PACKAGE / validator.SPEC_FILE).read_text(encoding="utf-8"))
    assert not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Call)) for node in ast.walk(tree))


def test_builder_check_proves_byte_identity():
    proc = subprocess.run(
        [sys.executable, "build_configuration_contract.py", "--check"],
        cwd=PACKAGE,
        check=False,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS deterministic byte identity" in proc.stdout
