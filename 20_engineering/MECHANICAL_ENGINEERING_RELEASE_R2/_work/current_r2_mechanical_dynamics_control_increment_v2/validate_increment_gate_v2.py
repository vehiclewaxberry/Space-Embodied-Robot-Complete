from __future__ import annotations

import argparse
import ast
import copy
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
EXPECTED_LOCK_BYTES = 10010
EXPECTED_LOCK_SHA256 = "7449CA17A071D05851846DFDAE96F24794C6231C856A781DFBAD2C961E0DA63E"
EXPECTED_SOURCE_IDS = (
    "prior_increment_v1_gate",
    "prior_increment_v1_manifest",
    "prior_increment_v1_receipt",
    "parent_v4_gate",
    "m01_hardened_gate",
    "m01_hardened_manifest",
    "m01_standalone_receipt",
    "m01_independent_recompute",
    "m4_execution_gate",
    "m4_execution_manifest",
    "m4_execution_validator",
    "m4_negative_receipt",
    "task_metric_candidate_gate",
    "task_metric_candidate_manifest",
    "task_metric_standalone_receipt",
    "task_metric_external_source_lock",
    "task_metric_external_auditor",
    "task_metric_external_tests",
    "task_metric_external_readme",
    "task_metric_external_receipt",
    "postcapture_candidate_gate",
    "postcapture_candidate_manifest",
    "postcapture_internal_receipt",
    "postcapture_core_source",
    "postcapture_external_source_lock",
    "postcapture_external_auditor",
    "postcapture_external_gate",
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
EXPECTED_GATE_CHECKS = {
    "A01_SOURCE_LOCK_SCHEMA_AND_27_RECORDS_EXACT",
    "A02_ALL_27_SOURCE_BYTES_AND_SHA256_MATCH",
    "A03_STRICT_JSON_DUPLICATE_AND_NONFINITE_CONTROLS",
    "A04_PRIOR_V1_GATE_SEMANTICS_EXACT",
    "A05_PRIOR_V1_MANIFEST_SEMANTICS_EXACT",
    "A06_PRIOR_V1_RECEIPT_SEMANTICS_EXACT",
    "A07_PARENT_V4_GATE_28_OF_28_EXACT",
    "A08_PARENT_V4_CAD_REMAINS_UNEXECUTED",
    "A09_PARENT_V4_M01_SNAPSHOT_REMAINS_ZERO",
    "A10_PARENT_V4_NEXT_AND_RELEASE_FALSE",
    "A11_M01_HARDENED_GATE_28_OF_28",
    "A12_M01_NINE_CANDIDATE_BOUNDS_ZERO_NEW_SYSTEM_CERTIFICATES",
    "A13_M01_PARENT_ZERO_APPEND_ONLY_OBSERVED_BASE_ONE",
    "A14_M01_SCENE_PAIR_EDGE_PATH_REMAIN_ZERO_OR_FALSE",
    "A15_M01_CLAIM_AND_AUTHORITY_EXACT",
    "A16_M01_MANIFEST_EXACT_NINE_ROWS",
    "A17_M01_STANDALONE_RECEIPT_EXACT",
    "A18_M01_INDEPENDENT_RECOMPUTE_EXACT",
    "A19_M4_EXECUTION_MATRIX_GATE_30_OF_30",
    "A20_M4_C01_C09_ZERO_CURRENT_STEP_D01_SOURCE_ONLY_UNRUN",
    "A21_M4_ALL_OPERATIONAL_AND_RELEASE_AUTHORITY_FALSE",
    "A22_M4_MANIFEST_AND_36_NEGATIVES_EXACT",
    "A23_TASK_METRIC_CANDIDATE_GATE_17_OF_17",
    "A24_TASK_METRIC_STATIC_CLAIM_AND_AUTHORITY_EXACT",
    "A25_TASK_METRIC_MANIFEST_AND_INTERNAL_RECEIPT_EXACT",
    "A26_TASK_METRIC_EXTERNAL_SOURCE_LOCK_EXACT",
    "A27_TASK_METRIC_EXTERNAL_AUDIT_14_OF_14",
    "A28_POSTCAPTURE_CANDIDATE_GATE_22_OF_22",
    "A29_POSTCAPTURE_SYNTHETIC_C08_C09_NOT_EVALUATED_CLAIM_EXACT",
    "A30_POSTCAPTURE_CANDIDATE_ALL_DOWNSTREAM_AUTHORITY_FALSE",
    "A31_POSTCAPTURE_MANIFEST_AND_INTERNAL_RECEIPT_EXACT",
    "A32_POSTCAPTURE_EXTERNAL_SOURCE_LOCK_EXACT",
    "A33_POSTCAPTURE_EXTERNAL_AUDIT_18_OF_18",
    "A34_PINNED_VALIDATOR_AUDITOR_CORE_TEST_AND_README_PARSE",
    "A35_SOURCE_LOCK_CLAIM_AND_18_AUTHORITY_BOUNDARIES_EXACT",
    "A36_ALL_SOURCE_SEMANTIC_FACTS_PASS",
    "A37_PARENT_V4_IS_NOT_REISSUED_OR_MUTATED",
    "A38_EVERY_ADDITIVE_CHECK_PASSES",
}
STATIC_PAYLOAD = {
    "README.md",
    LOCK_NAME,
    "build_increment_gate_v2.py",
    "test_increment_gate_v2.py",
    "validate_increment_gate_v2.py",
    GATE_NAME,
}
ALLOWED_FILES = STATIC_PAYLOAD | {MANIFEST_NAME, RECEIPT_NAME}


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


def audit_lock_document(lock: dict) -> bool:
    return (
        sha256_bytes(canonical_json(lock)) == EXPECTED_LOCK_SHA256
        and set(lock)
        == {
            "schema",
            "generated_utc",
            "decision_rule",
            "maximum_claim_boundary",
            "record_count",
            "records",
            "authority_boundaries",
        }
        and lock.get("schema") == "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_SOURCE_LOCK_V2"
        and exact_int(lock.get("record_count"), 27)
        and len(lock.get("records", [])) == 27
        and tuple(row.get("id") for row in lock.get("records", [])) == EXPECTED_SOURCE_IDS
        and all(set(row) == {"id", "path", "bytes", "sha256"} for row in lock.get("records", []))
        and len({row.get("path") for row in lock.get("records", [])}) == 27
        and all(type(row.get("bytes")) is int for row in lock.get("records", []))
        and all(type(row.get("sha256")) is str and len(row["sha256"]) == 64 for row in lock.get("records", []))
        and lock.get("maximum_claim_boundary") == MAXIMUM_CLAIM
        and set(lock.get("authority_boundaries", {})) == set(FALSE_BOUNDARY_KEYS)
        and all(lock["authority_boundaries"].get(key) is False for key in FALSE_BOUNDARY_KEYS)
    )


def load_frozen_inputs():
    root = repo_root()
    lock_raw = (PACKAGE / LOCK_NAME).read_bytes()
    if len(lock_raw) != EXPECTED_LOCK_BYTES or sha256_bytes(lock_raw) != EXPECTED_LOCK_SHA256:
        raise ValueError("SOURCE_LOCK_RAW_PIN_DRIFT")
    lock = strict_json_bytes(lock_raw)
    if not audit_lock_document(lock):
        raise ValueError("SOURCE_LOCK_DOCUMENT_DRIFT")
    raws = {}
    docs = {}
    pins = []
    for row in lock["records"]:
        raw = (root / row["path"]).read_bytes()
        actual_bytes = len(raw)
        actual_sha = sha256_bytes(raw)
        if actual_bytes != row["bytes"] or actual_sha != row["sha256"]:
            raise ValueError(f"SOURCE_PIN_MISMATCH:{row['id']}")
        pins.append(
            {
                "actual_bytes": actual_bytes,
                "actual_sha256": actual_sha,
                "expected_bytes": row["bytes"],
                "expected_sha256": row["sha256"],
                "id": row["id"],
                "match": True,
                "path": row["path"],
            }
        )
        raws[row["id"]] = raw
        if Path(row["path"]).suffix.lower() == ".json":
            docs[row["id"]] = strict_json_bytes(raw)
    return lock_raw, lock, raws, docs, pins


def independent_source_semantics(lock: dict, raws: dict, docs: dict):
    prior = docs["prior_increment_v1_gate"]
    prior_manifest = docs["prior_increment_v1_manifest"]
    prior_receipt = docs["prior_increment_v1_receipt"]
    parent = docs["parent_v4_gate"]
    m01 = docs["m01_hardened_gate"]
    m01_receipt = docs["m01_standalone_receipt"]
    m01_iv = docs["m01_independent_recompute"]
    m4 = docs["m4_execution_gate"]
    m4_negative = docs["m4_negative_receipt"]
    metric = docs["task_metric_candidate_gate"]
    metric_manifest = docs["task_metric_candidate_manifest"]
    metric_internal = docs["task_metric_standalone_receipt"]
    metric_lock = docs["task_metric_external_source_lock"]
    metric_external = docs["task_metric_external_receipt"]
    post = docs["postcapture_candidate_gate"]
    post_manifest = docs["postcapture_candidate_manifest"]
    post_internal = docs["postcapture_internal_receipt"]
    post_lock = docs["postcapture_external_source_lock"]
    post_external = docs["postcapture_external_gate"]
    m01_header, m01_rows = csv_rows(raws["m01_hardened_manifest"])
    m4_header, m4_rows = csv_rows(raws["m4_execution_manifest"])
    metric_gram = metric_external.get("recomputed", {}).get("gram_source_audit", {})
    metric_reload = metric_external.get("recomputed", {}).get("kilogram_gram_independent_reload", {})

    py_expect = {
        "m4_execution_validator": "evaluate_all",
        "task_metric_external_auditor": "validate",
        "task_metric_external_tests": "test_external_audit_inventory_rejects_missing_and_extra_files",
        "postcapture_core_source": "admit_current_system_attachment",
        "postcapture_external_auditor": "build_gate",
    }
    python_parse = True
    for source_id, required_name in py_expect.items():
        try:
            tree = ast.parse(raws[source_id].decode("utf-8"))
            functions = {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
            python_parse = python_parse and required_name in functions
        except (SyntaxError, UnicodeDecodeError):
            python_parse = False

    facts = {
        "lock_exact": audit_lock_document(lock),
        "prior_gate": prior.get("schema") == "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_GATE_V1"
        and prior.get("summary") == {"failed": [], "passed": 28, "total": 28}
        and all_exact_false(prior, ("parent_gate_reissued", "parent_gate_credit", "next_stage_authorized", "release_credit")),
        "prior_manifest_receipt": prior_manifest.get("schema") == "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_MANIFEST_V1"
        and exact_int(prior_manifest.get("entry_count"), 6)
        and len(prior_manifest.get("entries", [])) == 6
        and prior_receipt.get("schema") == "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_INDEPENDENT_VALIDATION_V1"
        and prior_receipt.get("negative_controls", {}).get("all_pass") is True
        and exact_int(prior_receipt.get("negative_controls", {}).get("count"), 26)
        and prior_receipt.get("authority")
        == {"next_stage_authorized": False, "parent_gate_credit": False, "release_credit": False},
        "parent": parent.get("schema") == "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4"
        and parent.get("summary") == {"failed": [], "passed": 28, "total": 28}
        and parent.get("CAD_state", {}).get("candidate_artifact_generated") is False
        and parent.get("CAD_state", {}).get("candidate_step_present") is False
        and parent.get("CAD_state", {}).get("candidate_snapshot_executed") is False
        and parent.get("M01_state", {}).get("motion_certificates") == "0_OF_150"
        and parent.get("M01_state", {}).get("authoritative_values") == "0_OF_30"
        and parent.get("M01_state", {}).get("stage_instances") == "0_OF_3"
        and parent.get("M01_state", {}).get("clearance_policy") == "0_OF_11166"
        and parent.get("M01_state", {}).get("pair_oracle") == "0_OF_11166"
        and exact_int(parent.get("M01_state", {}).get("continuous_edges_certified"), 0)
        and parent.get("M01_state", {}).get("path_search_authorized") is False
        and parent.get("next_stage_authorized") is False
        and parent.get("release_credit") is False,
        "m01_gate": m01.get("schema") == "M01_RIGID_KINEMATIC_MOTION_CERT_BATCH_GATE_V1"
        and exact_int(m01.get("checks_passed"), 28)
        and exact_int(m01.get("checks_total"), 28)
        and len(m01.get("checks", {})) == 28
        and all(value is True for value in m01.get("checks", {}).values())
        and m01.get("maximum_claim")
        == "9_OF_9_NONBASE_B601_A_OBJECTS_HAVE_HASH_BOUND_FULL_Q_DOMAIN_DESIGN_SCREENING_RIGID_KINEMATIC_CANDIDATE_BOUNDS__0_NEW_SYSTEM_CERTIFICATES"
        and m01.get("authority")
        == "APPEND_ONLY_DESIGN_SCREENING_KINEMATIC_CANDIDATE_BOUNDS_ONLY__ZERO_NEW_SYSTEM_MOTION_CERTIFICATES__NO_PARENT_GATE_REISSUE",
        "m01_counts_authority": exact_int(m01.get("counters", {}).get("design_screening_candidate_bounds_emitted"), 9)
        and exact_int(m01.get("counters", {}).get("batch_new_system_motion_certificates_bound"), 0)
        and exact_int(m01.get("counters", {}).get("parent_contract_system_motion_certificates_bound"), 0)
        and exact_int(m01.get("counters", {}).get("effective_observed_append_only_system_motion_certificates"), 1)
        and exact_int(m01.get("counters", {}).get("authoritative_scene_values_bound"), 0)
        and exact_int(m01.get("counters", {}).get("stage_instances_bound"), 0)
        and exact_int(m01.get("counters", {}).get("clearance_policy_rows_bound"), 0)
        and exact_int(m01.get("counters", {}).get("pair_queries_executed"), 0)
        and exact_int(m01.get("counters", {}).get("edges_certified"), 0)
        and m01.get("pair_evaluation_authorized") is False
        and m01.get("edge_evaluation_authorized") is False
        and m01.get("path_search_authorized") is False
        and m01.get("next_stage_authorized") is False
        and m01.get("release_credit") is False,
        "m01_manifest_receipts": m01_header == ("path", "bytes", "sha256", "role")
        and len(m01_rows) == 9
        and len({row["path"] for row in m01_rows}) == 9
        and m01_receipt.get("schema") == "STANDALONE_RELEASE_VALIDATION_RECEIPT_V1"
        and m01_receipt.get("all_release_checks_pass") is True
        and exact_int(m01_receipt.get("candidate_comparisons_passed"), 9)
        and exact_int(m01_receipt.get("candidate_comparisons_total"), 9)
        and exact_int(m01_receipt.get("batch_new_system_certificates"), 0)
        and exact_int(m01_receipt.get("core_negative_controls_rejected"), 44)
        and exact_int(m01_receipt.get("release_negative_controls_rejected"), 10)
        and m01_receipt.get("builder_imported_or_executed") is False
        and m01_iv.get("schema") == "INDEPENDENT_RIGID_KINEMATIC_RECOMPUTE_V1"
        and m01_iv.get("all_independent_checks_pass") is True
        and exact_int(m01_iv.get("candidate_comparisons_passed"), 9)
        and exact_int(m01_iv.get("batch_new_system_certificates_recomputed"), 0)
        and exact_int(m01_iv.get("negative_controls_rejected"), 44)
        and m01_iv.get("validator_imported_or_executed_builder") is False,
        "m4": m4.get("schema") == "M4_L01_L02_CONFIGURATION_GEOMETRY_EXECUTION_MATRIX_GATE_V1"
        and m4.get("gate_passed") is True
        and exact_int(m4.get("passed_count"), 30)
        and exact_int(m4.get("expected_count"), 30)
        and len(m4.get("checks", [])) == 30
        and all(row.get("pass") is True for row in m4.get("checks", []))
        and exact_int(m4.get("configuration_current_step_buildable_count"), 0)
        and exact_int(m4.get("source_only_diagnostic_recipe_count"), 1)
        and all_exact_false(
            m4,
            (
                "step_generation_executed",
                "cad_kernel_loaded",
                "fresh_cad_run_authorized",
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
        "m4_manifest_negative": m4_header == ("path", "bytes", "sha256", "role", "exists")
        and len(m4_rows) == 17
        and len({row["path"] for row in m4_rows}) == 17
        and m4_negative.get("schema") == "M4_L01_L02_GEOMETRY_NEGATIVE_CONTROL_RESULTS_V1"
        and exact_int(m4_negative.get("expected_count"), 36)
        and exact_int(m4_negative.get("passed_count"), 36)
        and m4_negative.get("next_stage_authorized") is False
        and m4_negative.get("release_credit") is False,
        "metric_gate": metric.get("schema") == "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_GATE_V1"
        and metric.get("all_checks_pass") is True
        and exact_int(metric.get("passed"), 17)
        and exact_int(metric.get("total"), 17)
        and len(metric.get("checks", {})) == 17
        and all(value is True for value in metric.get("checks", {}).values())
        and metric.get("maximum_claim") == "SOURCE_DERIVED_DIMENSIONLESS_TASK_SPACE_METRIC_CANDIDATE_ONLY"
        and metric.get("scope") == "SOURCE_DERIVED_DIMENSIONLESS_TASK_SPACE_METRIC_CANDIDATE_ONLY"
        and all_exact_false(
            metric,
            (
                "time_domain_tracking_executed",
                "precontact_tracking_validated",
                "collision_valid",
                "m01_path_bound",
                "hardware_valid",
                "safe_review_pass",
                "parent_control_gate_reissued",
                "next_stage_authorized",
                "release_credit",
            ),
        ),
        "metric_manifest_internal": metric_manifest.get("schema") == "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_MANIFEST_V1"
        and metric_manifest.get("claim") == "HASH_BOUND_ADDITIVE_CANDIDATE_ONLY"
        and exact_int(metric_manifest.get("local_record_count"), 9)
        and len(metric_manifest.get("local_records", [])) == 9
        and metric_manifest.get("inventory_policy", {}).get("pass") is True
        and all_exact_false(metric_manifest, ("parent_control_gate_reissued", "next_stage_authorized", "release_credit"))
        and metric_internal.get("schema") == "CTRL_R2_TASK_SPACE_METRIC_STANDALONE_INTERNAL_VALIDATION_V1"
        and metric_internal.get("all_pass") is True
        and exact_int(metric_internal.get("passed"), 12)
        and exact_int(metric_internal.get("total"), 12)
        and metric_internal.get("validator_class") == "STANDALONE_INTERNAL__NOT_INDEPENDENT_AUTHORITY"
        and all_exact_false(metric_internal, ("parent_control_gate_reissued", "next_stage_authorized", "release_credit")),
        "metric_external": metric_lock.get("schema") == "CTRL_R2_TASK_SPACE_METRIC_EXTERNAL_AUDIT_SOURCE_LOCK_V1"
        and exact_int(metric_lock.get("candidate_pin_count"), 13)
        and len(metric_lock.get("candidate_pins", [])) == 13
        and exact_int(metric_lock.get("direct_source_pin_count"), 7)
        and len(metric_lock.get("direct_source_pins", [])) == 7
        and exact_int(metric_lock.get("parent_transitive_source_pin_count"), 24)
        and len(metric_lock.get("parent_transitive_source_pins", [])) == 24
        and metric_lock.get("audit_semantic_profile", {}).get("candidate_gate_schema")
        == "CTRL_R2_TASK_SPACE_METRIC_CANDIDATE_GATE_V1"
        and metric_lock.get("audit_semantic_profile", {}).get("candidate_scope")
        == "SOURCE_DERIVED_DIMENSIONLESS_TASK_SPACE_METRIC_CANDIDATE_ONLY"
        and metric_lock.get("audit_semantic_profile", {}).get("review_status") == "PENDING_OWNER_REVIEW"
        and metric_lock.get("audit_semantic_profile", {}).get("expected_candidate_checks")
        == list(metric.get("checks", {}))
        and metric_lock.get("audit_semantic_profile", {}).get("artifact_package_complete_required") is True
        and metric_lock.get("audit_semantic_profile", {}).get("inventory_no_extra_or_cache_required") is True
        and metric_lock.get("audit_semantic_profile", {}).get("all_parent_hardware_safe_path_and_release_authority_false") is True
        and metric_lock.get("audit_semantic_profile", {}).get("external_audit_inventory_exact_required") is True
        and metric_lock.get("audit_semantic_profile", {}).get("truthful_gram_test_method")
        == "IN_MEMORY_URDF_ALL_LINK_MASS_AND_INERTIA_X1000__URDF_TREE_DYNAMICS_REASSEMBLY"
        and metric_external.get("schema") == "CTRL_R2_TASK_SPACE_METRIC_EXTERNAL_AUDIT_V1"
        and metric_external.get("all_pass") is True
        and exact_int(metric_external.get("passed"), 14)
        and exact_int(metric_external.get("total"), 14)
        and len(metric_external.get("checks", {})) == 14
        and all(value is True for value in metric_external.get("checks", {}).values())
        and metric_external.get("recomputed_candidate_checks") == metric.get("checks", {})
        and metric_external.get("negative_controls", {}).get("all_pass") is True
        and exact_int(metric_external.get("negative_controls", {}).get("passed"), 40)
        and exact_int(metric_external.get("negative_controls", {}).get("total"), 40)
        and metric_external.get("truthful_gram_test_method")
        == "IN_MEMORY_URDF_ALL_LINK_MASS_AND_INERTIA_X1000__URDF_TREE_DYNAMICS_REASSEMBLY"
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
        and all_exact_false(
            metric_external,
            (
                "time_domain_tracking_executed",
                "hardware_valid",
                "safe_review_pass",
                "parent_control_gate_reissued",
                "next_stage_authorized",
                "release_credit",
            ),
        ),
        "post_gate": post.get("schema") == "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_GATE_V1"
        and post.get("all_checks_pass") is True
        and exact_int(post.get("passed"), 22)
        and exact_int(post.get("total"), 22)
        and len(post.get("checks", [])) == 22
        and all(row.get("pass") is True for row in post.get("checks", []))
        and post.get("current_C08_status") == "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3"
        and post.get("current_C09_status") == "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3"
        and post.get("maximum_claim")
        == "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_SYNTHETIC_FIXTURE_PASS__CURRENT_C08_C09_NOT_EVALUATED__NO_CONTACT_ATTACHMENT_NONABORT_PARENT_OR_RELEASE_CREDIT"
        and post.get("verdict") == post.get("maximum_claim")
        and all_exact_false(
            post,
            (
                "current_system_instance_evaluated",
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
        "post_manifest_internal": post_manifest.get("schema") == "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_MANIFEST_V1"
        and exact_int(post_manifest.get("package_entry_count"), 11)
        and len(post_manifest.get("package_entries", [])) == 11
        and post_manifest.get("directory_payload_exact_at_generation") is True
        and post_manifest.get("cache_bytecode_or_unlisted_payload_allowed") is False
        and post_manifest.get("independent_validation_receipt_excluded") is True
        and post_manifest.get("self_excluded") is True
        and all_exact_false(post_manifest, ("next_stage_authorized", "release_credit"))
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
                "current_system_instance_evaluated",
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
        "post_external": post_lock.get("schema") == "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_EXTERNAL_SOURCE_LOCK_V1"
        and post_lock.get("lock_policy")
        == "FIXED_EXPECTATIONS_AUTHORED_OUTSIDE_CANDIDATE__NO_RUNTIME_EXPECTATION_GENERATION_FROM_TARGET_PACKAGE"
        and len(post_lock.get("pins", [])) == 10
        and post_lock.get("required_current_status") == "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3"
        and post_lock.get("all_downstream_authority_must_remain_false") is True
        and post_external.get("schema") == "POST_CAPTURE_SPATIAL_INERTIA_KERNEL_EXTERNAL_AUDIT_GATE_V1"
        and post_external.get("all_checks_pass") is True
        and exact_int(post_external.get("passed"), 18)
        and exact_int(post_external.get("total"), 18)
        and len(post_external.get("checks", [])) == 18
        and all(row.get("pass") is True for row in post_external.get("checks", []))
        and post_external.get("current_C08_status") == "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3"
        and post_external.get("current_C09_status") == "NOT_EVALUATED_MISSING_AUTHORITATIVE_ATTACHMENT_SE3"
        and all_exact_false(
            post_external,
            (
                "current_system_instance_evaluated",
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
        "python_sources": python_parse
        and "external-audit package inventory is checked by exact set equality"
        in raws["task_metric_external_readme"].decode("utf-8")
        and "16 URDF link masses"
        in raws["task_metric_external_readme"].decode("utf-8")
        and "all 96 inertia-tensor components"
        in raws["task_metric_external_readme"].decode("utf-8"),
    }
    return facts


def audit_gate(gate: dict, lock_raw: bytes, lock: dict, pins: list, source_facts: dict):
    expected_evidence = {
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
    }
    expected_holds = [
        "CAD_AND_CONFIGURATION_CURRENT_STEP_NOT_EXECUTED",
        "M01_SCENE_PAIR_EDGE_AND_PATH_NOT_BOUND",
        "CONTACT_AND_AUTHORITATIVE_ATTACHMENT_NOT_BOUND",
        "POSTCAPTURE_CURRENT_C08_C09_NOT_EVALUATED",
        "TIME_DOMAIN_CONTROL_AND_HARDWARE_NOT_VALIDATED",
        "SAFE_SIM13_NONABORT_NEXT_STAGE_AND_RELEASE_NOT_AUTHORIZED",
    ]
    parent_record = next(row for row in lock["records"] if row["id"] == "parent_v4_gate")
    return {
        "schema": gate.get("schema") == "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_GATE_V2",
        "generated": gate.get("generated_utc") == "DETERMINISTIC_NO_WALLCLOCK",
        "decision": gate.get("decision_rule") == lock.get("decision_rule"),
        "scope": gate.get("scope") == "APPEND_ONLY_ADDITIVE_EVIDENCE_CONVERGENCE_ONLY",
        "checks": set(gate.get("checks", {})) == EXPECTED_GATE_CHECKS
        and all(value is True for value in gate.get("checks", {}).values()),
        "summary": gate.get("summary") == {"failed": [], "passed": 38, "total": 38},
        "gate_passed_bool": gate.get("gate_passed") is True,
        "source_binding": gate.get("source_binding")
        == {
            "all_match": True,
            "matched": 27,
            "pins": pins,
            "source_lock": {"bytes": len(lock_raw), "path": LOCK_NAME, "sha256": sha256_bytes(lock_raw)},
            "total": 27,
        },
        "source_semantics": len(source_facts) == 16 and all(source_facts.values()),
        "claim": gate.get("maximum_claim") == MAXIMUM_CLAIM,
        "verdict": gate.get("technical_verdict") == TECHNICAL_VERDICT,
        "review": gate.get("review_status") == "PENDING_OWNER_REVIEW",
        "boundaries": gate.get("authority_boundaries") == {key: False for key in FALSE_BOUNDARY_KEYS},
        "top_authority": all_exact_false(
            gate,
            ("next_stage_authorized", "parent_gate_credit", "parent_gate_reissued", "release_credit"),
        ),
        "evidence_state": gate.get("evidence_state") == expected_evidence,
        "parent_integrity": gate.get("parent_integrity")
        == {
            "parent_V4_gate_path": parent_record["path"],
            "parent_V4_sha256": parent_record["sha256"],
            "parent_V4_snapshot": "0_OF_150",
            "reissued": False,
        },
        "holds": gate.get("retained_holds") == expected_holds,
    }


def observed_inventory():
    files = {
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*")
        if path.is_file()
    }
    forbidden = [
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*")
        if any(part in {"__pycache__", ".pytest_cache"} for part in path.parts)
        or path.suffix.lower() in {".pyc", ".pyo"}
    ]
    return files, sorted(forbidden)


def audit_manifest(manifest: dict, inventory_override=None):
    entries = manifest.get("entries", [])
    paths = [row.get("path") for row in entries]
    entry_map = {row.get("path"): row for row in entries}
    actual_files, forbidden = observed_inventory()
    if inventory_override is not None:
        actual_files = set(inventory_override)
    return {
        "schema": manifest.get("schema") == "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_MANIFEST_V2",
        "generated": manifest.get("generated_utc") == "DETERMINISTIC_NO_WALLCLOCK",
        "policy": manifest.get("inventory_policy") == "EXACT_ALLOWLIST_NO_EXTRA_NO_CACHE_OR_BYTECODE",
        "self_excluded": manifest.get("self_excluded") is True and MANIFEST_NAME not in paths,
        "paths": set(paths) == STATIC_PAYLOAD and len(paths) == len(set(paths)) == len(STATIC_PAYLOAD),
        "sorted": paths == sorted(paths),
        "count": exact_int(manifest.get("entry_count"), len(STATIC_PAYLOAD)),
        "hashes": set(paths) == STATIC_PAYLOAD
        and all(
            set(entry_map[rel]) == {"bytes", "path", "sha256"}
            and type(entry_map[rel]["bytes"]) is int
            and entry_map[rel]["bytes"] == (PACKAGE / rel).stat().st_size
            and entry_map[rel]["sha256"] == sha256_bytes((PACKAGE / rel).read_bytes())
            for rel in STATIC_PAYLOAD
        ),
        "entries_digest": manifest.get("entries_canonical_sha256") == sha256_bytes(canonical_json(entries)),
        "exclusions": manifest.get("dynamic_exclusions")
        == [
            {"path": MANIFEST_NAME, "reason": "SELF_EXCLUDED_TO_AVOID_CIRCULAR_HASH"},
            {"path": RECEIPT_NAME, "reason": "GENERATED_AFTER_MANIFEST_AND_BINDS_MANIFEST"},
        ],
        "inventory": actual_files == ALLOWED_FILES,
        "no_cache": forbidden == [],
        "authority": manifest.get("authority")
        == {
            "next_stage_authorized": False,
            "parent_gate_credit": False,
            "parent_gate_reissued": False,
            "release_credit": False,
        },
    }


def import_architecture_audit():
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = sorted(name for name in imported if "build_increment_gate_v2" in name)
    return {"forbidden": forbidden, "imports": sorted(imported), "pass": forbidden == []}


def run_negative_controls(lock, docs, gate, manifest, source_facts):
    cases = []

    def add(case_id: str, rejected: bool):
        cases.append({"id": case_id, "rejected": bool(rejected)})

    def gate_case(case_id, mutate):
        trial = copy.deepcopy(gate)
        mutate(trial)
        audit = audit_gate(trial, (PACKAGE / LOCK_NAME).read_bytes(), lock, gate["source_binding"]["pins"], source_facts)
        add(case_id, not all(audit.values()))

    gate_case("NC01_GATE_PASS_FALSE", lambda d: d.__setitem__("gate_passed", False))
    gate_case("NC02_GATE_CLAIM_ESCALATION", lambda d: d.__setitem__("maximum_claim", "FULL_RELEASE"))
    gate_case("NC03_GATE_RELEASE_AUTHORITY", lambda d: d["authority_boundaries"].__setitem__("release_credit", True))
    gate_case("NC04_GATE_BOOL_AS_COUNT", lambda d: d["summary"].__setitem__("passed", True))
    gate_case("NC05_GATE_M01_COUNT_ESCALATION", lambda d: d["evidence_state"]["m01"].__setitem__("new_system_motion_certificates", 1))
    gate_case("NC06_GATE_TIME_DOMAIN_ESCALATION", lambda d: d["evidence_state"]["task_space_metric"].__setitem__("time_domain_tracking_executed", True))
    gate_case("NC07_GATE_POSTCAPTURE_PROMOTION", lambda d: d["evidence_state"]["postcapture"].__setitem__("C08", "PASS"))
    gate_case("NC08_GATE_PARENT_REISSUE", lambda d: d["parent_integrity"].__setitem__("reissued", True))
    gate_case("NC09_GATE_SOURCE_HASH_MUTATION", lambda d: d["source_binding"]["pins"][0].__setitem__("actual_sha256", "0" * 64))

    lock_trials = []
    for case_id, mutate in (
        ("NC10_LOCK_PATH_MUTATION", lambda d: d["records"][0].__setitem__("path", "wrong")),
        ("NC11_LOCK_BYTES_MUTATION", lambda d: d["records"][0].__setitem__("bytes", 1)),
        ("NC12_LOCK_HASH_MUTATION", lambda d: d["records"][0].__setitem__("sha256", "0" * 64)),
        ("NC13_LOCK_EXTRA_RECORD", lambda d: d["records"].append(copy.deepcopy(d["records"][0]))),
        ("NC14_LOCK_AUTHORITY_ESCALATION", lambda d: d["authority_boundaries"].__setitem__("next_stage_authorized", True)),
    ):
        trial = copy.deepcopy(lock)
        mutate(trial)
        lock_trials.append((case_id, not audit_lock_document(trial)))
    for case_id, rejected in lock_trials:
        add(case_id, rejected)

    for case_id, record_id in (
        ("NC27_EXTERNAL_TEST_DIRECT_PIN_TAMPER", "task_metric_external_tests"),
        ("NC28_EXTERNAL_README_DIRECT_PIN_TAMPER", "task_metric_external_readme"),
    ):
        trial = copy.deepcopy(lock)
        next(row for row in trial["records"] if row["id"] == record_id)["sha256"] = "0" * 64
        add(case_id, not audit_lock_document(trial))

    source_mutations = (
        ("NC15_PARENT_MOTION_PROMOTION", "parent_v4_gate", lambda d: d["M01_state"].__setitem__("motion_certificates", "1_OF_150"), "parent"),
        ("NC16_M01_CANDIDATE_COUNT", "m01_hardened_gate", lambda d: d["counters"].__setitem__("design_screening_candidate_bounds_emitted", 10), "m01_counts_authority"),
        ("NC17_M4_CURRENT_STEP_PROMOTION", "m4_execution_gate", lambda d: d.__setitem__("configuration_current_step_buildable_count", 1), "m4"),
        ("NC18_METRIC_TIME_DOMAIN_PROMOTION", "task_metric_candidate_gate", lambda d: d.__setitem__("time_domain_tracking_executed", True), "metric_gate"),
        ("NC19_POST_C08_PROMOTION", "postcapture_candidate_gate", lambda d: d.__setitem__("current_C08_status", "PASS"), "post_gate"),
        ("NC20_POST_EXTERNAL_RELEASE", "postcapture_external_gate", lambda d: d.__setitem__("release_credit", True), "post_external"),
    )
    for case_id, doc_id, mutate, fact_id in source_mutations:
        trial_docs = copy.deepcopy(docs)
        mutate(trial_docs[doc_id])
        trial_facts = independent_source_semantics(lock, {key: value for key, value in load_frozen_inputs()[2].items()}, trial_docs)
        add(case_id, trial_facts.get(fact_id) is False)

    manifest_trial = copy.deepcopy(manifest)
    manifest_trial["entries"].append(copy.deepcopy(manifest_trial["entries"][0]))
    add("NC21_MANIFEST_DUPLICATE", not all(audit_manifest(manifest_trial).values()))
    manifest_trial = copy.deepcopy(manifest)
    manifest_trial["entries"][0]["sha256"] = "0" * 64
    add("NC22_MANIFEST_HASH", not all(audit_manifest(manifest_trial).values()))
    add("NC23_INVENTORY_EXTRA", not all(audit_manifest(manifest, ALLOWED_FILES | {"EXTRA.bin"}).values()))

    for case_id, raw in (
        ("NC24_JSON_DUPLICATE", b'{"x":1,"x":2}'),
        ("NC25_JSON_NAN", b'{"x":NaN}'),
        ("NC26_JSON_INFINITY", b'{"x":Infinity}'),
    ):
        try:
            strict_json_bytes(raw)
            rejected = False
        except ValueError:
            rejected = True
        add(case_id, rejected)
    return {
        "all_pass": all(case["rejected"] for case in cases),
        "cases": cases,
        "count": len(cases),
        "passed": sum(1 for case in cases if case["rejected"]),
    }


def validate_all():
    lock_raw, lock, raws, docs, pins = load_frozen_inputs()
    gate = strict_json_bytes((PACKAGE / GATE_NAME).read_bytes())
    manifest_raw = (PACKAGE / MANIFEST_NAME).read_bytes()
    manifest = strict_json_bytes(manifest_raw)
    source_facts = independent_source_semantics(lock, raws, docs)
    gate_audit = audit_gate(gate, lock_raw, lock, pins, source_facts)
    manifest_audit = audit_manifest(manifest)
    architecture = import_architecture_audit()
    negative = run_negative_controls(lock, docs, gate, manifest, source_facts)
    top_checks = {
        "V01_SOURCE_LOCK_RAW_AND_27_PINS_EXACT": audit_lock_document(lock) and len(pins) == 27,
        "V02_SOURCE_SEMANTICS_FIELDWISE_ALL_PASS": len(source_facts) == 16 and all(source_facts.values()),
        "V03_GATE_AUDIT_ALL_PASS": all(gate_audit.values()),
        "V04_MANIFEST_EXACT_NO_EXTRA_OR_CACHE": all(manifest_audit.values()),
        "V05_VALIDATOR_DOES_NOT_IMPORT_BUILDER": architecture["pass"],
        "V06_NEGATIVE_CONTROLS_28_OF_28": negative["all_pass"] and exact_int(negative["count"], 28),
        "V07_ALL_AUTHORITY_REMAINS_FALSE": gate.get("authority_boundaries") == {key: False for key in FALSE_BOUNDARY_KEYS},
    }
    receipt = {
        "all_pass": all(top_checks.values()),
        "authority_boundaries": {key: False for key in FALSE_BOUNDARY_KEYS},
        "checks": top_checks,
        "gate_audit": gate_audit,
        "generated_utc": "DETERMINISTIC_STANDALONE_VALIDATION_NO_WALLCLOCK",
        "manifest_audit": manifest_audit,
        "manifest_binding": {
            "bytes": len(manifest_raw),
            "path": MANIFEST_NAME,
            "sha256": sha256_bytes(manifest_raw),
        },
        "maximum_claim": MAXIMUM_CLAIM,
        "negative_controls": negative,
        "next_stage_authorized": False,
        "parent_gate_credit": False,
        "parent_gate_reissued": False,
        "passed": sum(1 for value in top_checks.values() if value),
        "release_credit": False,
        "schema": "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_STANDALONE_VALIDATION_V2",
        "source_audit": {"all_match": True, "count": len(pins), "pins": pins},
        "source_lock_binding": {"bytes": len(lock_raw), "path": LOCK_NAME, "sha256": sha256_bytes(lock_raw)},
        "source_semantics": source_facts,
        "technical_verdict": TECHNICAL_VERDICT,
        "total": len(top_checks),
        "validator_architecture": "STANDALONE_NO_BUILDER_IMPORT__FIXED_EXTERNAL_SOURCE_LOCK",
        "validator_import_audit": architecture,
    }
    if not receipt["all_pass"]:
        failed = [key for key, value in top_checks.items() if not value]
        raise ValueError(f"STANDALONE_VALIDATION_FAILED:{failed}")
    return receipt


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-receipt", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    receipt_bytes = canonical_json(validate_all())
    if args.write_receipt:
        (PACKAGE / RECEIPT_NAME).write_bytes(receipt_bytes)
        print("PASS wrote standalone V2 validation receipt")
        return
    if (PACKAGE / RECEIPT_NAME).read_bytes() != receipt_bytes:
        raise SystemExit("STANDALONE_RECEIPT_DETERMINISTIC_REPLAY_MISMATCH")
    print("PASS standalone V2 validation and receipt byte identity")


if __name__ == "__main__":
    main()
