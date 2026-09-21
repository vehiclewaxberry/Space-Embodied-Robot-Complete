from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import math
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
LOCK_NAME = "SOURCE_AUTHORITY_LOCK_V2.json"
GATE_NAME = "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_GATE_V2.json"
MANIFEST_NAME = "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_MANIFEST_V2.json"
RECEIPT_NAME = "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_STANDALONE_VALIDATION_V2.json"
STATIC_MANIFEST_PATHS = (
    "README.md",
    LOCK_NAME,
    "build_increment_gate_v2.py",
    "test_increment_gate_v2.py",
    "validate_increment_gate_v2.py",
    GATE_NAME,
)
MAXIMUM_CLAIM = (
    "PASS_APPEND_ONLY_M01_NINE_CANDIDATE_BOUNDS_ZERO_NEW_SYSTEM_CERTIFICATES__"
    "M4_C01_C09_ZERO_OF_NINE_CURRENT_STEP_D01_SOURCE_ONLY_UNRUN__"
    "TASK_SPACE_STATIC_METRIC_CANDIDATE_ONLY__POSTCAPTURE_SYNTHETIC_FIXTURE_ONLY_"
    "C08_C09_NOT_EVALUATED__PARENT_V4_UNCHANGED__CAD_SCENE_PAIR_EDGE_PATH_CONTACT_"
    "ATTACHMENT_TIME_DOMAIN_HARDWARE_SAFE_SIM13_NONABORT_NEXT_RELEASE_HOLD"
)
TECHNICAL_VERDICT = (
    "PASS_ADDITIVE_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_V2__"
    "NO_PARENT_REISSUE_OR_DOWNSTREAM_AUTHORITY"
)
FALSE_BOUNDARY_KEYS = (
    "attachment_valid",
    "cad_execution_credit",
    "cad_generation_authorized",
    "configuration_current_step_credit",
    "contact_valid",
    "edge_evaluation_authorized",
    "hardware_valid",
    "m01_scene_bound",
    "next_stage_authorized",
    "non_abort_authorized",
    "pair_evaluation_authorized",
    "parent_gate_credit",
    "parent_gate_reissued",
    "path_search_authorized",
    "release_credit",
    "safe_gate_credit",
    "sim13_credit",
    "time_domain_control_valid",
)


def repo_root() -> Path:
    for candidate in (PACKAGE, *PACKAGE.parents):
        if (candidate / "AGENTS.md").is_file():
            return candidate
    raise RuntimeError("REPO_ROOT_NOT_FOUND")


def reject_constant(value: str):
    raise ValueError(f"NONFINITE_JSON_CONSTANT:{value}")


def pairs_no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        out[key] = value
    return out


def strict_json_bytes(raw: bytes):
    value = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=pairs_no_duplicates,
        parse_constant=reject_constant,
    )

    def walk(node):
        if isinstance(node, float) and not math.isfinite(node):
            raise ValueError("NONFINITE_JSON_NUMBER")
        if isinstance(node, dict):
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    return value


def canonical_json(value) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def exact_int(value, expected: int) -> bool:
    return type(value) is int and value == expected


def all_exact_false(document: dict, keys) -> bool:
    return all(document.get(key) is False for key in keys)


def csv_rows(raw: bytes):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    rows = list(reader)
    if reader.fieldnames is None or any(None in row for row in rows):
        raise ValueError("CSV_STRUCTURE_INVALID")
    return tuple(reader.fieldnames), rows


def strict_self_test() -> bool:
    for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}'):
        try:
            strict_json_bytes(raw)
        except ValueError:
            continue
        return False
    return True


def load_sources():
    root = repo_root()
    lock_raw = (PACKAGE / LOCK_NAME).read_bytes()
    lock = strict_json_bytes(lock_raw)
    expected_lock_keys = {
        "schema",
        "generated_utc",
        "decision_rule",
        "maximum_claim_boundary",
        "record_count",
        "records",
        "authority_boundaries",
    }
    if set(lock) != expected_lock_keys:
        raise ValueError("SOURCE_LOCK_KEYS_DRIFT")
    if lock["schema"] != "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_SOURCE_LOCK_V2":
        raise ValueError("SOURCE_LOCK_SCHEMA_DRIFT")
    records = lock["records"]
    if not exact_int(lock["record_count"], 27) or len(records) != 27:
        raise ValueError("SOURCE_LOCK_RECORD_COUNT_DRIFT")
    if any(set(row) != {"id", "path", "bytes", "sha256"} for row in records):
        raise ValueError("SOURCE_LOCK_RECORD_KEYS_DRIFT")
    ids = [row["id"] for row in records]
    paths = [row["path"] for row in records]
    if len(ids) != len(set(ids)) or len(paths) != len(set(paths)):
        raise ValueError("SOURCE_LOCK_ID_OR_PATH_DUPLICATE")
    raws = {}
    docs = {}
    pins = []
    for row in records:
        if type(row["id"]) is not str or type(row["path"]) is not str:
            raise ValueError("SOURCE_LOCK_ID_PATH_TYPE")
        if type(row["bytes"]) is not int or type(row["sha256"]) is not str:
            raise ValueError("SOURCE_LOCK_BYTES_HASH_TYPE")
        path = root / row["path"]
        raw = path.read_bytes()
        actual_bytes = len(raw)
        actual_sha256 = sha256_bytes(raw)
        match = actual_bytes == row["bytes"] and actual_sha256 == row["sha256"]
        pins.append(
            {
                "actual_bytes": actual_bytes,
                "actual_sha256": actual_sha256,
                "expected_bytes": row["bytes"],
                "expected_sha256": row["sha256"],
                "id": row["id"],
                "match": match,
                "path": row["path"],
            }
        )
        if not match:
            raise ValueError(f"SOURCE_PIN_MISMATCH:{row['id']}")
        raws[row["id"]] = raw
        if path.suffix.lower() == ".json":
            docs[row["id"]] = strict_json_bytes(raw)
    return lock_raw, lock, raws, docs, pins


def source_semantics(lock: dict, raws: dict, docs: dict):
    prior = docs["prior_increment_v1_gate"]
    prior_manifest = docs["prior_increment_v1_manifest"]
    prior_receipt = docs["prior_increment_v1_receipt"]
    parent = docs["parent_v4_gate"]
    m01 = docs["m01_hardened_gate"]
    m01_receipt = docs["m01_standalone_receipt"]
    m01_recompute = docs["m01_independent_recompute"]
    m4 = docs["m4_execution_gate"]
    m4_negative = docs["m4_negative_receipt"]
    metric = docs["task_metric_candidate_gate"]
    metric_manifest = docs["task_metric_candidate_manifest"]
    metric_internal = docs["task_metric_standalone_receipt"]
    metric_external_lock = docs["task_metric_external_source_lock"]
    metric_external = docs["task_metric_external_receipt"]
    post = docs["postcapture_candidate_gate"]
    post_manifest = docs["postcapture_candidate_manifest"]
    post_internal = docs["postcapture_internal_receipt"]
    post_external_lock = docs["postcapture_external_source_lock"]
    post_external = docs["postcapture_external_gate"]

    m01_header, m01_manifest_rows = csv_rows(raws["m01_hardened_manifest"])
    m4_header, m4_manifest_rows = csv_rows(raws["m4_execution_manifest"])
    python_sources_parse = True
    expected_functions = {
        "m4_execution_validator": "evaluate_all",
        "task_metric_external_auditor": "validate",
        "task_metric_external_tests": "test_external_audit_inventory_rejects_missing_and_extra_files",
        "postcapture_core_source": "admit_current_system_attachment",
        "postcapture_external_auditor": "build_gate",
    }
    for source_id, function_name in expected_functions.items():
        try:
            tree = ast.parse(raws[source_id].decode("utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            python_sources_parse = False
            continue
        names = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        python_sources_parse = python_sources_parse and function_name in names

    m01_checks = m01.get("checks", {})
    m01_counters = m01.get("counters", {})
    metric_checks = metric.get("checks", {})
    metric_ext_checks = metric_external.get("checks", {})
    metric_gram = metric_external.get("recomputed", {}).get("gram_source_audit", {})
    metric_reload = metric_external.get("recomputed", {}).get("kilogram_gram_independent_reload", {})
    post_checks = post.get("checks", [])
    post_ext_checks = post_external.get("checks", [])
    boundaries = lock.get("authority_boundaries", {})
    facts = {
        "prior_increment_gate_exact": prior.get("schema") == "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_GATE_V1"
        and prior.get("summary") == {"failed": [], "passed": 28, "total": 28}
        and prior.get("parent_gate_reissued") is False
        and prior.get("parent_gate_credit") is False
        and prior.get("next_stage_authorized") is False
        and prior.get("release_credit") is False,
        "prior_increment_manifest_exact": prior_manifest.get("schema") == "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_MANIFEST_V1"
        and exact_int(prior_manifest.get("entry_count"), 6)
        and len(prior_manifest.get("entries", [])) == 6
        and prior_manifest.get("self_excluded") is True,
        "prior_increment_receipt_exact": prior_receipt.get("schema") == "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_INDEPENDENT_VALIDATION_V1"
        and prior_receipt.get("negative_controls", {}).get("all_pass") is True
        and exact_int(prior_receipt.get("negative_controls", {}).get("count"), 26)
        and prior_receipt.get("authority") == {
            "next_stage_authorized": False,
            "parent_gate_credit": False,
            "release_credit": False,
        },
        "parent_v4_gate_exact": parent.get("schema") == "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4"
        and parent.get("summary") == {"failed": [], "passed": 28, "total": 28},
        "parent_v4_cad_unexecuted": all_exact_false(
            parent.get("CAD_state", {}),
            (
                "candidate_artifact_generated",
                "candidate_geometry_validated",
                "candidate_snapshot_executed",
                "candidate_step_present",
                "hidden_glb_present",
                "owner_override_used",
            ),
        )
        and exact_int(parent.get("CAD_state", {}).get("candidate_snapshot_outputs_present"), 0),
        "parent_v4_m01_snapshot_exact": parent.get("M01_state", {}).get("motion_certificates") == "0_OF_150"
        and parent.get("M01_state", {}).get("authoritative_values") == "0_OF_30"
        and parent.get("M01_state", {}).get("stage_instances") == "0_OF_3"
        and parent.get("M01_state", {}).get("clearance_policy") == "0_OF_11166"
        and parent.get("M01_state", {}).get("pair_oracle") == "0_OF_11166"
        and exact_int(parent.get("M01_state", {}).get("continuous_edges_certified"), 0)
        and parent.get("M01_state", {}).get("path_search_authorized") is False
        and parent.get("M01_state", {}).get("path_search_executed") is False,
        "parent_v4_authority_false": parent.get("next_stage_authorized") is False
        and parent.get("release_credit") is False,
        "m01_gate_28_exact": m01.get("schema") == "M01_RIGID_KINEMATIC_MOTION_CERT_BATCH_GATE_V1"
        and exact_int(m01.get("checks_passed"), 28)
        and exact_int(m01.get("checks_total"), 28)
        and len(m01_checks) == 28
        and all(value is True for value in m01_checks.values()),
        "m01_nine_candidates_zero_new": exact_int(m01_counters.get("design_screening_candidate_bounds_emitted"), 9)
        and exact_int(m01_counters.get("batch_new_system_motion_certificates_bound"), 0)
        and m01.get("candidate_bound_gate_pass") is True
        and m01.get("system_motion_certificate_gate_pass") is False,
        "m01_parent_zero_observed_base_one": exact_int(m01_counters.get("parent_contract_system_motion_certificates_bound"), 0)
        and exact_int(m01_counters.get("effective_observed_append_only_system_motion_certificates"), 1)
        and exact_int(m01_counters.get("remaining_objects_without_observed_append_only_system_certificate"), 149)
        and exact_int(m01_counters.get("system_motion_certificates_required"), 150),
        "m01_scene_pair_edge_path_zero": exact_int(m01_counters.get("authoritative_scene_values_bound"), 0)
        and exact_int(m01_counters.get("authoritative_scene_values_required"), 30)
        and exact_int(m01_counters.get("stage_instances_bound"), 0)
        and exact_int(m01_counters.get("stage_instances_required"), 3)
        and exact_int(m01_counters.get("clearance_policy_rows_bound"), 0)
        and exact_int(m01_counters.get("clearance_policy_rows_required"), 11166)
        and exact_int(m01_counters.get("pair_queries_executed"), 0)
        and exact_int(m01_counters.get("pair_queries_required"), 11166)
        and exact_int(m01_counters.get("edges_certified"), 0)
        and m01.get("pair_evaluation_authorized") is False
        and m01.get("edge_evaluation_authorized") is False
        and m01.get("path_search_authorized") is False,
        "m01_claim_and_authority_exact": m01.get("maximum_claim")
        == "9_OF_9_NONBASE_B601_A_OBJECTS_HAVE_HASH_BOUND_FULL_Q_DOMAIN_DESIGN_SCREENING_RIGID_KINEMATIC_CANDIDATE_BOUNDS__0_NEW_SYSTEM_CERTIFICATES"
        and m01.get("authority")
        == "APPEND_ONLY_DESIGN_SCREENING_KINEMATIC_CANDIDATE_BOUNDS_ONLY__ZERO_NEW_SYSTEM_MOTION_CERTIFICATES__NO_PARENT_GATE_REISSUE"
        and m01.get("next_stage_authorized") is False
        and m01.get("release_credit") is False,
        "m01_manifest_exact": m01_header == ("path", "bytes", "sha256", "role")
        and len(m01_manifest_rows) == 9
        and len({row["path"] for row in m01_manifest_rows}) == 9,
        "m01_receipt_exact": m01_receipt.get("schema") == "STANDALONE_RELEASE_VALIDATION_RECEIPT_V1"
        and m01_receipt.get("all_release_checks_pass") is True
        and exact_int(m01_receipt.get("candidate_comparisons_passed"), 9)
        and exact_int(m01_receipt.get("candidate_comparisons_total"), 9)
        and exact_int(m01_receipt.get("batch_new_system_certificates"), 0)
        and exact_int(m01_receipt.get("core_negative_controls_rejected"), 44)
        and exact_int(m01_receipt.get("core_negative_controls_total"), 44)
        and exact_int(m01_receipt.get("release_negative_controls_rejected"), 10)
        and exact_int(m01_receipt.get("release_negative_controls_total"), 10)
        and m01_receipt.get("builder_imported_or_executed") is False
        and m01_receipt.get("next_stage_authorized") is False
        and m01_receipt.get("release_credit") is False,
        "m01_independent_exact": m01_recompute.get("schema") == "INDEPENDENT_RIGID_KINEMATIC_RECOMPUTE_V1"
        and m01_recompute.get("all_independent_checks_pass") is True
        and exact_int(m01_recompute.get("candidate_comparisons_passed"), 9)
        and exact_int(m01_recompute.get("candidate_comparisons_total"), 9)
        and exact_int(m01_recompute.get("batch_new_system_certificates_recomputed"), 0)
        and exact_int(m01_recompute.get("negative_controls_rejected"), 44)
        and exact_int(m01_recompute.get("negative_controls_total"), 44)
        and m01_recompute.get("validator_imported_or_executed_builder") is False,
        "m4_gate_30_exact": m4.get("schema") == "M4_L01_L02_CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_GATE_V1"
        and m4.get("gate_passed") is True
        and exact_int(m4.get("passed_count"), 30)
        and exact_int(m4.get("expected_count"), 30)
        and len(m4.get("checks", [])) == 30
        and all(row.get("pass") is True for row in m4.get("checks", [])),
        "m4_zero_current_step_d01_unrun": exact_int(m4.get("configuration_current_step_buildable_count"), 0)
        and exact_int(m4.get("source_only_diagnostic_recipe_count"), 1)
        and m4.get("step_generation_executed") is False
        and m4.get("cad_kernel_loaded") is False
        and m4.get("fresh_cad_run_authorized") is False,
        "m4_authority_false": all_exact_false(
            m4,
            (
                "configuration_credit",
                "collision_authority",
                "contact_authority",
                "mass_authority",
                "operational_authorized",
                "production_complete",
                "parent_gate_credit",
                "next_stage_authorized",
                "release_credit",
            ),
        ),
        "m4_manifest_and_negative_exact": m4_header == ("path", "bytes", "sha256", "role", "exists")
        and len(m4_manifest_rows) == 17
        and len({row["path"] for row in m4_manifest_rows}) == 17
        and m4_negative.get("schema") == "M4_L01_L02_GEOMETRY_NEGATIVE_CONTROL_RESULTS_V1"
        and exact_int(m4_negative.get("expected_count"), 36)
        and exact_int(m4_negative.get("passed_count"), 36)
        and m4_negative.get("next_stage_authorized") is False
        and m4_negative.get("release_credit") is False,
        "task_metric_candidate_17_exact": metric.get("schema") == "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_GATE_V1"
        and metric.get("all_checks_pass") is True
        and exact_int(metric.get("passed"), 17)
        and exact_int(metric.get("total"), 17)
        and len(metric_checks) == 17
        and all(value is True for value in metric_checks.values()),
        "task_metric_static_claim_authority_exact": metric.get("maximum_claim")
        == "SOURCE_DERIVED_DIMENSIONLESS_TASK_SPACE_METRIC_CANDIDATE_ONLY"
        and metric.get("scope") == "SOURCE_DERIVED_DIMENSIONLESS_TASK_SPACE_METRIC_CANDIDATE_ONLY"
        and metric.get("time_domain_tracking_executed") is False
        and metric.get("precontact_tracking_validated") is False
        and metric.get("collision_valid") is False
        and metric.get("m01_path_bound") is False
        and metric.get("hardware_valid") is False
        and metric.get("safe_review_pass") is False
        and metric.get("parent_control_gate_reissued") is False
        and metric.get("next_stage_authorized") is False
        and metric.get("release_credit") is False,
        "task_metric_manifest_internal_exact": metric_manifest.get("schema") == "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_MANIFEST_V1"
        and metric_manifest.get("claim") == "HASH_BOUND_ADDITIVE_CANDIDATE_ONLY"
        and exact_int(metric_manifest.get("local_record_count"), 9)
        and len(metric_manifest.get("local_records", [])) == 9
        and metric_manifest.get("inventory_policy", {}).get("pass") is True
        and metric_manifest.get("parent_control_gate_reissued") is False
        and metric_manifest.get("next_stage_authorized") is False
        and metric_manifest.get("release_credit") is False
        and metric_internal.get("schema") == "CTRL_R2_TASK_SPACE_METRIC_STANDALONE_INTERNAL_VALIDATION_V1"
        and metric_internal.get("all_pass") is True
        and exact_int(metric_internal.get("passed"), 12)
        and exact_int(metric_internal.get("total"), 12)
        and metric_internal.get("validator_class") == "STANDALONE_INTERNAL__NOT_INDEPENDENT_AUTHORITY"
        and metric_internal.get("parent_control_gate_reissued") is False
        and metric_internal.get("next_stage_authorized") is False
        and metric_internal.get("release_credit") is False,
        "task_metric_external_lock_exact": metric_external_lock.get("schema") == "CTRL_R2_TASK_SPACE_METRIC_EXTERNAL_AUDIT_SOURCE_LOCK_V1"
        and exact_int(metric_external_lock.get("candidate_pin_count"), 13)
        and len(metric_external_lock.get("candidate_pins", [])) == 13
        and exact_int(metric_external_lock.get("direct_source_pin_count"), 7)
        and len(metric_external_lock.get("direct_source_pins", [])) == 7
        and exact_int(metric_external_lock.get("parent_transitive_source_pin_count"), 24)
        and len(metric_external_lock.get("parent_transitive_source_pins", [])) == 24
        and metric_external_lock.get("audit_semantic_profile", {}).get("candidate_gate_schema")
        == "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_GATE_V1"
        and metric_external_lock.get("audit_semantic_profile", {}).get("candidate_scope")
        == "SOURCE_DERIVED_DIMENSIONLESS_TASK_SPACE_METRIC_CANDIDATE_ONLY"
        and metric_external_lock.get("audit_semantic_profile", {}).get("review_status") == "PENDING_OWNER_REVIEW"
        and metric_external_lock.get("audit_semantic_profile", {}).get("expected_candidate_checks")
        == list(metric_checks)
        and metric_external_lock.get("audit_semantic_profile", {}).get("artifact_package_complete_required") is True
        and metric_external_lock.get("audit_semantic_profile", {}).get("inventory_no_extra_or_cache_required") is True
        and metric_external_lock.get("audit_semantic_profile", {}).get("all_parent_hardware_safe_path_and_release_authority_false") is True,
        "task_metric_external_audit_exact": metric_external.get("schema") == "CTRL_R2_TASK_SPACE_METRIC_EXTERNAL_AUDIT_V1"
        and metric_external.get("all_pass") is True
        and exact_int(metric_external.get("passed"), 14)
        and exact_int(metric_external.get("total"), 14)
        and len(metric_ext_checks) == 14
        and all(value is True for value in metric_ext_checks.values())
        and metric_external.get("recomputed_candidate_checks") == metric_checks
        and metric_external.get("negative_controls", {}).get("all_pass") is True
        and exact_int(metric_external.get("negative_controls", {}).get("passed"), 40)
        and exact_int(metric_external.get("negative_controls", {}).get("total"), 40)
        and metric_external_lock.get("audit_semantic_profile", {}).get("external_audit_inventory_exact_required") is True
        and metric_external.get("truthful_gram_test_method")
        == "IN_MEMORY_URDF_ALL_LINK_MASS_AND_INERTIA_X1000__URDF_TREE_DYNAMICS_REASSEMBLY"
        and metric_external_lock.get("audit_semantic_profile", {}).get("truthful_gram_test_method")
        == metric_external.get("truthful_gram_test_method")
        and exact_int(metric_gram.get("transformed_mass_count"), 16)
        and exact_int(metric_gram.get("transformed_inertia_component_count"), 96)
        and metric_gram.get("temporary_file_created") is False
        and metric_gram.get("xml_hashes_differ") is True
        and metric_gram.get("original_urdf_sha256") != metric_gram.get("transformed_urdf_sha256")
        and all(
            row.get("method")
            == "IN_MEMORY_URDF_ALL_LINK_MASS_AND_INERTIA_X1000__URDF_TREE_DYNAMICS_REASSEMBLY"
            and row.get("represented_mass_g_m2_finite") is True
            and type(row.get("represented_mass_vs_1000x_kg_relative")) is float
            and math.isfinite(row["represented_mass_vs_1000x_kg_relative"])
            and row["represented_mass_vs_1000x_kg_relative"] <= 1e-12
            and type(row.get("qdot_error")) is float
            and math.isfinite(row["qdot_error"])
            and row["qdot_error"] <= 1e-12
            for row in (
                metric_reload.get("FAR_APPROACH_5D", {}).get("physical_urdf_reassembly", {}),
                metric_reload.get("FINAL_ALIGNMENT_6D", {}).get("physical_urdf_reassembly", {}),
            )
        )
        and metric_external.get("maximum_claim") == "SOURCE_DERIVED_DIMENSIONLESS_TASK_SPACE_METRIC_CANDIDATE_ONLY"
        and metric_external.get("time_domain_tracking_executed") is False
        and metric_external.get("hardware_valid") is False
        and metric_external.get("safe_review_pass") is False
        and metric_external.get("next_stage_authorized") is False
        and metric_external.get("release_credit") is False,
        "postcapture_candidate_22_exact": post.get("schema") == "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_GATE_V1"
        and post.get("all_checks_pass") is True
        and exact_int(post.get("passed"), 22)
        and exact_int(post.get("total"), 22)
        and len(post_checks) == 22
        and all(row.get("pass") is True for row in post_checks),
        "postcapture_synthetic_status_claim_exact": post.get("current_C08_status")
        == "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3"
        and post.get("current_C09_status") == "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3"
        and post.get("current_system_instance_evaluated") is False
        and post.get("maximum_claim")
        == "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_SYNTHETIC_FIXTURE_PASS__CURRENT_C08_C09_NOT_EVALUATED__NO_CONTACT_ATTACHMENT_NONABORT_PARENT_OR_RELEASE_CREDIT"
        and post.get("verdict") == post.get("maximum_claim"),
        "postcapture_candidate_authority_false": all_exact_false(
            post,
            (
                "attachment_valid",
                "contact_valid",
                "hardware_valid",
                "target_attachment_plant_valid",
                "non_abort_authorized",
                "parent_dynamics_engineering_complete",
                "next_stage_authorized",
                "release_credit",
            ),
        ),
        "postcapture_manifest_internal_exact": post_manifest.get("schema") == "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_MANIFEST_V1"
        and exact_int(post_manifest.get("package_entry_count"), 11)
        and len(post_manifest.get("package_entries", [])) == 11
        and post_manifest.get("directory_payload_exact_at_generation") is True
        and post_manifest.get("cache_bytecode_or_unlisted_payload_allowed") is False
        and post_manifest.get("independent_validation_receipt_excluded") is True
        and post_manifest.get("self_excluded") is True
        and post_manifest.get("next_stage_authorized") is False
        and post_manifest.get("release_credit") is False
        and post_internal.get("schema") == "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_STANDALONE_INTERNAL_VALIDATION_V1"
        and post_internal.get("all_checks_pass") is True
        and exact_int(post_internal.get("passed"), 34)
        and exact_int(post_internal.get("total"), 34)
        and post_internal.get("independence_classification")
        == "PACKAGE_LOCAL_STANDALONE_INTERNAL__EXTERNAL_AUDIT_REQUIRED_FOR_INDEPENDENCE_CLAIM"
        and post_internal.get("negative_controls", {}).get("all_pass") is True
        and exact_int(post_internal.get("negative_controls", {}).get("passed"), 29)
        and exact_int(post_internal.get("negative_controls", {}).get("count"), 29)
        and post_internal.get("current_C08_status") == "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3"
        and post_internal.get("current_C09_status") == "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3"
        and all_exact_false(
            post_internal,
            (
                "attachment_valid",
                "contact_valid",
                "hardware_valid",
                "target_attachment_plant_valid",
                "non_abort_authorized",
                "parent_dynamics_engineering_complete",
                "next_stage_authorized",
                "release_credit",
            ),
        ),
        "postcapture_external_lock_exact": post_external_lock.get("schema") == "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_EXTERNAL_SOURCE_LOCK_V1"
        and post_external_lock.get("lock_policy")
        == "FIXED_EXPECTATIONS_AUTHORED_OUTSIDE_CANDIDATE__NO_RUNTIME_EXPECTATION_GENERATION_FROM_TARGET_PACKAGE"
        and len(post_external_lock.get("pins", [])) == 10
        and post_external_lock.get("expected_candidate_gate") == {"all_checks_pass": True, "passed": 22, "total": 22}
        and post_external_lock.get("expected_internal_validation")
        == {
            "classification": "PACKAGE_LOCAL_STANDALONE_INTERNAL__EXTERNAL_AUDIT_REQUIRED_FOR_INDEPENDENCE_CLAIM",
            "negative_count": 29,
            "negative_passed": 29,
            "passed": 34,
            "total": 34,
        }
        and post_external_lock.get("required_current_status")
        == "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3"
        and post_external_lock.get("all_downstream_authority_must_remain_false") is True,
        "postcapture_external_audit_exact": post_external.get("schema") == "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_EXTERNAL_AUDIT_GATE_V1"
        and post_external.get("all_checks_pass") is True
        and exact_int(post_external.get("passed"), 18)
        and exact_int(post_external.get("total"), 18)
        and len(post_ext_checks) == 18
        and all(row.get("pass") is True for row in post_ext_checks)
        and post_external.get("current_C08_status") == "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3"
        and post_external.get("current_C09_status") == "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3"
        and all_exact_false(
            post_external,
            (
                "attachment_valid",
                "contact_valid",
                "hardware_valid",
                "target_attachment_plant_valid",
                "non_abort_authorized",
                "parent_dynamics_engineering_complete",
                "next_stage_authorized",
                "release_credit",
            ),
        ),
        "python_authority_sources_parse": python_sources_parse
        and "external-audit package inventory is checked by exact set equality"
        in raws["task_metric_external_readme"].decode("utf-8")
        and "16 URDF link masses"
        in raws["task_metric_external_readme"].decode("utf-8")
        and "all 96 inertia-tensor components"
        in raws["task_metric_external_readme"].decode("utf-8"),
        "lock_boundaries_and_claim_exact": set(boundaries) == set(FALSE_BOUNDARY_KEYS)
        and all(boundaries[key] is False for key in FALSE_BOUNDARY_KEYS)
        and lock.get("maximum_claim_boundary") == MAXIMUM_CLAIM,
    }
    return facts


def evaluate():
    lock_raw, lock, raws, docs, pins = load_sources()
    facts = source_semantics(lock, raws, docs)
    checks = {
        "A01_SOURCE_LOCK_SCHEMA_AND_27_RECORDS_EXACT": lock.get("schema")
        == "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_SOURCE_LOCK_V2"
        and exact_int(lock.get("record_count"), 27)
        and len(lock.get("records", [])) == 27,
        "A02_ALL_27_SOURCE_BYTES_AND_SHA256_MATCH": len(pins) == 27 and all(row["match"] for row in pins),
        "A03_STRICT_JSON_DUPLICATE_AND_NONFINITE_CONTROLS": strict_self_test(),
        "A04_PRIOR_V1_GATE_SEMANTICS_EXACT": facts["prior_increment_gate_exact"],
        "A05_PRIOR_V1_MANIFEST_SEMANTICS_EXACT": facts["prior_increment_manifest_exact"],
        "A06_PRIOR_V1_RECEIPT_SEMANTICS_EXACT": facts["prior_increment_receipt_exact"],
        "A07_PARENT_V4_GATE_28_OF_28_EXACT": facts["parent_v4_gate_exact"],
        "A08_PARENT_V4_CAD_REMAINS_UNEXECUTED": facts["parent_v4_cad_unexecuted"],
        "A09_PARENT_V4_M01_SNAPSHOT_REMAINS_ZERO": facts["parent_v4_m01_snapshot_exact"],
        "A10_PARENT_V4_NEXT_AND_RELEASE_FALSE": facts["parent_v4_authority_false"],
        "A11_M01_HARDENED_GATE_28_OF_28": facts["m01_gate_28_exact"],
        "A12_M01_NINE_CANDIDATE_BOUNDS_ZERO_NEW_SYSTEM_CERTIFICATES": facts["m01_nine_candidates_zero_new"],
        "A13_M01_PARENT_ZERO_APPEND_ONLY_OBSERVED_BASE_ONE": facts["m01_parent_zero_observed_base_one"],
        "A14_M01_SCENE_PAIR_EDGE_PATH_REMAIN_ZERO_OR_FALSE": facts["m01_scene_pair_edge_path_zero"],
        "A15_M01_CLAIM_AND_AUTHORITY_EXACT": facts["m01_claim_and_authority_exact"],
        "A16_M01_MANIFEST_EXACT_NINE_ROWS": facts["m01_manifest_exact"],
        "A17_M01_STANDALONE_RECEIPT_EXACT": facts["m01_receipt_exact"],
        "A18_M01_INDEPENDENT_RECOMPUTE_EXACT": facts["m01_independent_exact"],
        "A19_M4_EXECUTION_MATRIX_GATE_30_OF_30": facts["m4_gate_30_exact"],
        "A20_M4_C01_C09_ZERO_CURRENT_STEP_D01_SOURCE_ONLY_UNRUN": facts["m4_zero_current_step_d01_unrun"],
        "A21_M4_ALL_OPERATIONAL_AND_RELEASE_AUTHORITY_FALSE": facts["m4_authority_false"],
        "A22_M4_MANIFEST_AND_36_NEGATIVES_EXACT": facts["m4_manifest_and_negative_exact"],
        "A23_TASK_METRIC_CANDIDATE_GATE_17_OF_17": facts["task_metric_candidate_17_exact"],
        "A24_TASK_METRIC_STATIC_CLAIM_AND_AUTHORITY_EXACT": facts["task_metric_static_claim_authority_exact"],
        "A25_TASK_METRIC_MANIFEST_AND_INTERNAL_RECEIPT_EXACT": facts["task_metric_manifest_internal_exact"],
        "A26_TASK_METRIC_EXTERNAL_SOURCE_LOCK_EXACT": facts["task_metric_external_lock_exact"],
        "A27_TASK_METRIC_EXTERNAL_AUDIT_14_OF_14": facts["task_metric_external_audit_exact"],
        "A28_POSTCAPTURE_CANDIDATE_GATE_22_OF_22": facts["postcapture_candidate_22_exact"],
        "A29_POSTCAPTURE_SYNTHETIC_C08_C09_NOT_EVALUATED_CLAIM_EXACT": facts["postcapture_synthetic_status_claim_exact"],
        "A30_POSTCAPTURE_CANDIDATE_ALL_DOWNSTREAM_AUTHORITY_FALSE": facts["postcapture_candidate_authority_false"],
        "A31_POSTCAPTURE_MANIFEST_AND_INTERNAL_RECEIPT_EXACT": facts["postcapture_manifest_internal_exact"],
        "A32_POSTCAPTURE_EXTERNAL_SOURCE_LOCK_EXACT": facts["postcapture_external_lock_exact"],
        "A33_POSTCAPTURE_EXTERNAL_AUDIT_18_OF_18": facts["postcapture_external_audit_exact"],
        "A34_PINNED_VALIDATOR_AUDITOR_CORE_TEST_AND_README_PARSE": facts["python_authority_sources_parse"],
        "A35_SOURCE_LOCK_CLAIM_AND_18_AUTHORITY_BOUNDARIES_EXACT": facts["lock_boundaries_and_claim_exact"],
        "A36_ALL_SOURCE_SEMANTIC_FACTS_PASS": len(facts) == 32 and all(facts.values()),
        "A37_PARENT_V4_IS_NOT_REISSUED_OR_MUTATED": docs["parent_v4_gate"].get("schema")
        == "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4",
    }
    checks["A38_EVERY_ADDITIVE_CHECK_PASSES"] = all(checks.values())
    failed = [key for key, value in checks.items() if value is not True]
    return {
        "authority_boundaries": {key: False for key in FALSE_BOUNDARY_KEYS},
        "checks": checks,
        "decision_rule": lock["decision_rule"],
        "evidence_state": {
            "m01": {
                "design_screening_candidate_bounds": "9_OF_9",
                "new_system_motion_certificates": 0,
                "observed_append_only_total": "1_OF_150",
                "parent_V4_snapshot": "0_OF_150",
            },
            "m4_geometry": {
                "C01_C09_current_STEP": "0_OF_9",
                "D01_source_only_recipe": "READY_NOT_EXECUTED",
                "cad_kernel_loaded": False,
                "step_generation_executed": False,
            },
            "postcapture": {
                "C08": "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3",
                "C09": "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3",
                "scope": "SYNTHETIC_FIXTURE_ONLY",
            },
            "task_space_metric": {
                "scope": "SOURCE_DERIVED_DIMENSIONLESS_STATIC_CANDIDATE_ONLY",
                "time_domain_tracking_executed": False,
            },
        },
        "gate_passed": not failed,
        "generated_utc": "DETERMINISTIC_NO_WALLCLOCK",
        "maximum_claim": MAXIMUM_CLAIM,
        "next_stage_authorized": False,
        "parent_gate_credit": False,
        "parent_gate_reissued": False,
        "parent_integrity": {
            "parent_V4_gate_path": next(row["path"] for row in lock["records"] if row["id"] == "parent_v4_gate"),
            "parent_V4_sha256": next(row["sha256"] for row in lock["records"] if row["id"] == "parent_v4_gate"),
            "parent_V4_snapshot": "0_OF_150",
            "reissued": False,
        },
        "release_credit": False,
        "retained_holds": [
            "CAD_AND_CONFIGURATION_CURRENT_STEP_NOT_EXECUTED",
            "M01_SCENE_PAIR_EDGE_AND_PATH_NOT_BOUND",
            "CONTACT_AND_AUTHORITATIVE_ATTACHMENT_NOT_BOUND",
            "POSTCAPTURE_CURRENT_C08_C09_NOT_EVALUATED",
            "TIME_DOMAIN_CONTROL_AND_HARDWARE_NOT_VALIDATED",
            "SAFE_SIM13_NONABORT_NEXT_STAGE_AND_RELEASE_NOT_AUTHORIZED",
        ],
        "review_status": "PENDING_OWNER_REVIEW",
        "schema": "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_GATE_V2",
        "scope": "APPEND_ONLY_ADDITIVE_EVIDENCE_CONVERGENCE_ONLY",
        "source_binding": {
            "all_match": all(row["match"] for row in pins),
            "matched": sum(1 for row in pins if row["match"]),
            "pins": pins,
            "source_lock": {
                "bytes": len(lock_raw),
                "path": LOCK_NAME,
                "sha256": sha256_bytes(lock_raw),
            },
            "total": len(pins),
        },
        "summary": {"failed": failed, "passed": len(checks) - len(failed), "total": len(checks)},
        "technical_verdict": TECHNICAL_VERDICT,
    }


def build_manifest(gate_bytes: bytes):
    entries = []
    for rel in STATIC_MANIFEST_PATHS:
        raw = gate_bytes if rel == GATE_NAME else (PACKAGE / rel).read_bytes()
        entries.append({"bytes": len(raw), "path": rel, "sha256": sha256_bytes(raw)})
    entries.sort(key=lambda row: row["path"])
    return {
        "authority": {
            "next_stage_authorized": False,
            "parent_gate_credit": False,
            "parent_gate_reissued": False,
            "release_credit": False,
        },
        "dynamic_exclusions": [
            {"path": MANIFEST_NAME, "reason": "SELF_EXCLUDED_TO_AVOID_CIRCULAR_HASH"},
            {"path": RECEIPT_NAME, "reason": "GENERATED_AFTER_MANIFEST_AND_BINDS_MANIFEST"},
        ],
        "entries": entries,
        "entries_canonical_sha256": sha256_bytes(canonical_json(entries)),
        "entry_count": len(entries),
        "generated_utc": "DETERMINISTIC_NO_WALLCLOCK",
        "inventory_policy": "EXACT_ALLOWLIST_NO_EXTRA_NO_CACHE_OR_BYTECODE",
        "schema": "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_MANIFEST_V2",
        "self_excluded": True,
    }


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    gate_bytes = canonical_json(evaluate())
    manifest_bytes = canonical_json(build_manifest(gate_bytes))
    if args.write:
        (PACKAGE / GATE_NAME).write_bytes(gate_bytes)
        (PACKAGE / MANIFEST_NAME).write_bytes(manifest_bytes)
        print("PASS wrote deterministic V2 additive gate and self-excluded manifest")
        return
    comparisons = {
        GATE_NAME: (PACKAGE / GATE_NAME).read_bytes() == gate_bytes,
        MANIFEST_NAME: (PACKAGE / MANIFEST_NAME).read_bytes() == manifest_bytes,
    }
    if not all(comparisons.values()):
        raise SystemExit(f"DETERMINISTIC_REPLAY_MISMATCH:{comparisons}")
    print("PASS deterministic V2 gate and manifest byte identity")


if __name__ == "__main__":
    main()
