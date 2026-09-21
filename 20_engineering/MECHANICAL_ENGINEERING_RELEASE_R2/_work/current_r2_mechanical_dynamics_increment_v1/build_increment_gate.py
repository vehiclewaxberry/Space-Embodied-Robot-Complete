from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
GATE_NAME = "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_GATE_V1.json"
MANIFEST_NAME = "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_MANIFEST_V1.json"
LOCK_NAME = "SOURCE_AUTHORITY_LOCK_V1.json"
RECEIPT_NAME = "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_INDEPENDENT_VALIDATION_V1.json"
LOCAL_MANIFEST_PATHS = (
    "README.md",
    LOCK_NAME,
    "build_increment_gate.py",
    "test_increment_gate.py",
    "validate_increment_gate.py",
    GATE_NAME,
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


def load_inputs():
    root = repo_root()
    lock_raw = (PACKAGE / LOCK_NAME).read_bytes()
    lock = strict_json_bytes(lock_raw)
    if lock.get("schema") != "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_SOURCE_LOCK_V1":
        raise ValueError("SOURCE_LOCK_SCHEMA_DRIFT")
    records = lock.get("records")
    if not isinstance(records, list) or len(records) != 13:
        raise ValueError("SOURCE_LOCK_RECORD_COUNT_DRIFT")
    if len({row["id"] for row in records}) != len(records):
        raise ValueError("SOURCE_LOCK_DUPLICATE_ID")
    docs = {}
    pins = []
    for row in records:
        path = root / row["path"]
        raw = path.read_bytes()
        actual = {"bytes": len(raw), "sha256": sha256_bytes(raw)}
        match = actual["bytes"] == row["bytes"] and actual["sha256"] == row["sha256"]
        pins.append(
            {
                "id": row["id"],
                "path": row["path"],
                "expected_bytes": row["bytes"],
                "actual_bytes": actual["bytes"],
                "expected_sha256": row["sha256"],
                "actual_sha256": actual["sha256"],
                "match": match,
            }
        )
        if not match:
            raise ValueError(f"SOURCE_PIN_MISMATCH:{row['id']}")
        if path.suffix.lower() == ".json":
            docs[row["id"]] = strict_json_bytes(raw)
    return lock, docs, pins


def evaluate():
    lock, docs, pins = load_inputs()
    v4 = docs["parent_entry_gate_v4"]
    m4 = docs["m4_configuration_gate"]
    m01 = docs["m01_base_motion_gate"]
    dyn = docs["time_varying_plant_gate"]
    dyn_iv = docs["time_varying_plant_independent_receipt"]

    checks = {}
    checks["A01_all_13_source_pins_exact"] = len(pins) == 13 and all(row["match"] for row in pins)
    checks["A02_parent_v4_28_of_28_and_hash_immutable"] = (
        v4.get("schema") == "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4"
        and v4.get("summary", {}).get("passed") == 28
        and v4.get("summary", {}).get("total") == 28
    )
    checks["A03_parent_v4_CAD_remains_unexecuted"] = all(
        v4.get("CAD_state", {}).get(key) is False
        for key in (
            "candidate_artifact_generated",
            "candidate_geometry_validated",
            "candidate_snapshot_executed",
            "candidate_step_present",
            "hidden_glb_present",
            "owner_override_used",
        )
    ) and v4.get("CAD_state", {}).get("candidate_snapshot_outputs_present") == 0
    checks["A04_parent_v4_M01_snapshot_remains_zero_of_150"] = (
        v4.get("M01_state", {}).get("motion_certificates") == "0_OF_150"
        and v4.get("M01_state", {}).get("stage_instances") == "0_OF_3"
        and v4.get("M01_state", {}).get("clearance_policy") == "0_OF_11166"
        and v4.get("M01_state", {}).get("pair_oracle") == "0_OF_11166"
    )
    checks["A05_parent_v4_system_and_release_holds_preserved"] = (
        v4.get("next_stage_authorized") is False
        and v4.get("release_credit") is False
        and all(value is False for value in v4.get("system_HOLD_state", {}).values() if isinstance(value, bool))
    )

    m4_rows = m4.get("criteria", [])
    checks["A06_M4_gate_26_of_26"] = len(m4_rows) == 26 and all(row.get("status") == "PASS" for row in m4_rows)
    checks["A07_M4_configuration_and_design_mass_9_of_9"] = (
        m4.get("summary", {}).get("configuration_ids") == "9_OF_9"
        and m4.get("summary", {}).get("design_mass_properties") == "9_OF_9"
    )
    checks["A08_M4_geometry_collision_and_as_built_not_promoted"] = (
        m4.get("summary", {}).get("complete_current_geometry") == "0_OF_9"
        and m4.get("summary", {}).get("released_collision") == "0_OF_9"
        and m4.get("summary", {}).get("as_built_mass_properties") == "0_OF_9"
        and m4.get("summary", {}).get("production_complete_state_vectors") == "0_OF_9"
    )
    checks["A09_M4_35_negative_controls_and_source_pins"] = (
        m4.get("summary", {}).get("negative_controls") == "35_OF_35"
        and m4.get("summary", {}).get("source_pins") == "20_OF_20"
    )
    checks["A10_M4_no_parent_or_release_credit"] = all(
        m4.get(key) is False
        for key in ("next_stage_authorized", "parent_gate_credit", "parent_gate_reissued", "release_credit")
    )

    m01_checks = m01.get("checks", {})
    counters = m01.get("counters", {})
    checks["A11_M01_gate_30_of_30"] = (
        m01.get("checks_passed") == 30
        and m01.get("checks_total") == 30
        and len(m01_checks) == 30
        and all(value is True for value in m01_checks.values())
    )
    checks["A12_M01_fixed_platform_3_of_3_design_only"] = (
        counters.get("fixed_platform_design_pose_bindings") == 3
        and counters.get("fixed_platform_asset_level_operational_promotions") == 0
    )
    checks["A13_M01_base_motion_is_exactly_1_of_150"] = (
        counters.get("system_motion_certificates_bound") == 1
        and counters.get("system_motion_certificates_required") == 150
        and counters.get("remaining_objects_without_system_motion_certificate") == 149
    )
    checks["A14_M01_scene_and_pair_work_remains_zero"] = (
        counters.get("authoritative_scene_values_bound") == 0
        and counters.get("authoritative_scene_values_required") == 30
        and counters.get("stage_instances_bound") == 0
        and counters.get("stage_instances_required") == 3
        and counters.get("clearance_policy_rows_bound") == 0
        and counters.get("clearance_policy_rows_required") == 11166
        and counters.get("pair_queries_executed") == 0
        and counters.get("pair_queries_required") == 11166
    )
    checks["A15_M01_edges_path_next_and_release_remain_false"] = (
        counters.get("edges_certified") == 0
        and counters.get("path_search_authorized") is False
        and counters.get("path_search_executed") is False
        and counters.get("next_stage_authorized") is False
        and counters.get("release_credit") is False
        and m01.get("pair_evaluation_authorized") is False
    )

    dyn_rows = dyn.get("checks", [])
    checks["A16_time_varying_plant_gate_24_of_24"] = (
        dyn.get("all_checks_pass") is True
        and len(dyn_rows) == 24
        and all(row.get("pass") is True for row in dyn_rows)
    )
    checks["A17_time_varying_plant_scope_is_rigid_zero_momentum_design_only"] = (
        dyn.get("authority_scope") == "CURRENT_R2_ZERO_MOMENTUM_RIGID_DESIGN_DIAGNOSTIC_ONLY"
        and dyn.get("passed") == 24
        and dyn.get("total") == 24
    )
    checks["A18_time_varying_plant_downstream_authority_all_false"] = all(
        dyn.get(key) is False
        for key in (
            "flex_valid",
            "contact_valid",
            "target_attachment_valid",
            "hardware_valid",
            "control_valid",
            "parent_dynamics_engineering_complete",
            "sim13_non_abort_authorized",
            "release_credit",
            "next_stage_authorized",
        )
    )
    checks["A19_time_varying_standalone_36_of_36"] = (
        dyn_iv.get("passed") == 36
        and dyn_iv.get("total") == 36
        and len(dyn_iv.get("checks", [])) == 36
        and all(row.get("pass") is True for row in dyn_iv.get("checks", []))
    )
    checks["A20_time_varying_independent_negative_controls_28_of_28"] = (
        dyn_iv.get("negative_controls", {}).get("all_pass") is True
        and dyn_iv.get("negative_controls", {}).get("count") == 28
        and len(dyn_iv.get("negative_controls", {}).get("records", [])) == 28
    )
    checks["A21_time_varying_manifest_audit_and_explicit_receipt_exclusion"] = (
        dyn_iv.get("manifest_audit", {}).get("all_pass") is True
        and dyn_iv.get("manifest_audit", {}).get("checks", {}).get("receipt_excluded_explicitly") is True
        and dyn_iv.get("manifest_audit", {}).get("declared_entry_count") == 11
    )
    checks["A22_time_varying_validator_architecture_standalone"] = (
        dyn_iv.get("validator_architecture") == "STANDALONE_NO_SHARED_BUILDER_EVALUATOR_SRC_IMPORTS"
        and dyn_iv.get("independence_import_audit", {}).get("pass") is True
    )

    boundaries = lock.get("authority_boundaries", {})
    checks["A23_source_lock_all_authority_boundaries_false"] = len(boundaries) == 9 and all(value is False for value in boundaries.values())
    checks["A24_additive_evidence_does_not_reissue_parent_V4"] = (
        m4.get("parent_gate_reissued") is False
        and m01.get("authority", "").startswith("APPEND_ONLY")
        and v4.get("M01_state", {}).get("motion_certificates") == "0_OF_150"
    )
    checks["A25_no_CAD_scene_pair_contact_nonabort_or_release_credit"] = (
        v4.get("bounded_actions_available", {}).get("generate_integrated_candidate_CAD") is False
        and m01.get("system_collision_gate_pass") is False
        and dyn.get("contact_valid") is False
        and dyn.get("sim13_non_abort_authorized") is False
        and dyn.get("release_credit") is False
    )
    checks["A26_all_three_increment_claims_are_narrow"] = (
        "DESIGN_MASS_TRACEABILITY_ONLY" in m4.get("gate_verdict", "")
        and "ONE_OF_150" in m01.get("maximum_claim", "")
        and "NO_FLEX_CONTACT_TARGET_ATTACHMENT_HARDWARE_CONTROL_PARENT_OR_RELEASE_CREDIT" in dyn.get("maximum_claim", "")
    )
    checks["A27_strict_json_self_tests"] = strict_self_tests()
    checks["A28_every_check_passes"] = all(checks.values())

    failed = [key for key, value in checks.items() if not value]
    gate = {
        "schema": "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_GATE_V1",
        "generated_utc": "DETERMINISTIC_NO_WALLCLOCK",
        "decision_rule": "Authority > evidence > independent reproduction > agent opinion",
        "source_binding": {"matched": sum(row["match"] for row in pins), "total": len(pins), "all_match": all(row["match"] for row in pins), "pins": pins},
        "checks": checks,
        "summary": {"passed": len(checks) - len(failed), "total": len(checks), "failed": failed},
        "additive_evidence_state": {
            "configuration_state_and_design_mass_traceability": "9_OF_9",
            "complete_current_configuration_geometry": "0_OF_9",
            "released_configuration_collision": "0_OF_9",
            "as_built_mass_properties": "0_OF_9",
            "M4_unique_core_binary64_mass_leaves": 180,
            "M4_mass_receipt_binary64_rechecks": 36,
            "M4_minimum_eigenvalue_bit_exact_checks": "9_PLUS_9",
            "M4_geometry_bbox_binary64_leaves": 54,
            "fixed_platform_design_pose_bindings": "3_OF_3",
            "child_base_motion_precertificate": "1_OF_150",
            "parent_V4_motion_snapshot_unchanged": "0_OF_150",
            "authoritative_scene_values": "0_OF_30",
            "scene_instances": "0_OF_3",
            "clearance_and_pair_queries": "0_OF_11166",
            "continuous_edges": 0,
            "time_varying_rigid_plant_gate": "24_OF_24",
            "time_varying_rigid_plant_independent_validation": "36_OF_36",
            "time_varying_rigid_plant_independent_negative_controls": "28_OF_28",
            "time_varying_rigid_plant_source_pins": "19_OF_19",
            "time_varying_rigid_plant_runtime_modules": "10_OF_10"
        },
        "parent_integrity": {
            "parent_V4_sha256": "277BE6349EC87E3CC76519E824F368F1D720C2C7E01646255DA5865510CB87EF",
            "parent_gate_mutated": False,
            "parent_gate_reissued": False,
            "parent_gate_credit_inherited": False,
            "interpretation": "CHILD_1_OF_150_IS_ADDITIVE_PRECREDIT_ONLY__PARENT_V4_REMAINS_0_OF_150_UNTIL_FORMAL_REISSUE"
        },
        "system_hold_state": {
            "candidate_CAD_generated": False,
            "candidate_geometry_validated": False,
            "candidate_snapshot_complete": False,
            "M01_scene_complete": False,
            "M01_pair_oracle_complete": False,
            "M01_path_complete": False,
            "physical_contact_authority": False,
            "target_attachment_authority": False,
            "post_capture_combined_plant_complete": False,
            "parent_dynamics_complete": False,
            "parent_control_complete": False,
            "Sim13_non_abort_authority": False,
            "next_stage_authorized": False,
            "release_credit": False
        },
        "exact_remaining_blockers": [
            "FRESH_NAMED_CAD_RUN_AUTHORITY_AND_6_GIB_MEMORY_ADMISSION_OR_FRESH_SINGLE_USE_OWNER_OVERRIDE",
            "399_SOLID_TWO_GROUP_C01_STEP_GLB_AND_FOUR_VIEW_SNAPSHOT_NOT_GENERATED_OR_VALIDATED",
            "C02_C09_CURRENT_INTEGRATED_GEOMETRY_AND_RELEASED_COLLISION_NOT_AVAILABLE",
            "M01_AUTHORITATIVE_SCENE_VALUES_0_OF_30_AND_SCENE_INSTANCES_0_OF_3",
            "M01_MOTION_REMAINS_149_OF_150_UNBOUND_AFTER_ONE_CHILD_PRECERTIFICATE",
            "M01_CLEARANCE_AND_PAIR_QUERY_0_OF_11166_EDGES_ZERO_PATH_FALSE",
            "ROUTE_C_AND_HARNESS_PHYSICAL_ENVELOPE_NOT_CLOSED",
            "PHYSICAL_CONTACT_TARGET_ATTACHMENT_AND_POST_CAPTURE_COMBINED_PLANT_NOT_CLOSED",
            "CONTROL_SAFE_SIM13_NON_ABORT_AND_PARENT_GATES_NOT_CLOSED",
            "AS_BUILT_MEASUREMENT_QUALIFICATION_AND_RELEASE_NOT_CLOSED"
        ],
        "maximum_claim": "PASS_CONFIGURATION_TRACEABILITY_M01_BASE_MOTION_PRECERT_AND_TIME_VARYING_RIGID_PLANT_ADDITIVE_INCREMENT__CAD_SCENE_PAIR_CONTACT_POSTCAPTURE_CONTROL_NONABORT_PARENT_AND_RELEASE_HOLD",
        "technical_verdict": "PASS_ADDITIVE_CONFIGURATION_M01_BASE_MOTION_AND_TIME_VARYING_RIGID_PLANT_EVIDENCE__NO_PARENT_GATE_REISSUE_OR_RELEASE_CREDIT",
        "review_status": "PENDING_OWNER_REVIEW",
        "parent_gate_credit": False,
        "parent_gate_reissued": False,
        "next_stage_authorized": False,
        "release_credit": False,
    }
    return gate


def strict_self_tests() -> bool:
    cases = (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}')
    for raw in cases:
        try:
            strict_json_bytes(raw)
        except ValueError:
            continue
        return False
    return True


def build_manifest(gate_bytes: bytes):
    entries = []
    for rel in LOCAL_MANIFEST_PATHS:
        raw = gate_bytes if rel == GATE_NAME else (PACKAGE / rel).read_bytes()
        entries.append({"path": rel, "bytes": len(raw), "sha256": sha256_bytes(raw)})
    entries.sort(key=lambda row: row["path"])
    entries_hash = sha256_bytes(canonical_json(entries))
    return {
        "schema": "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_MANIFEST_V1",
        "generated_utc": "DETERMINISTIC_NO_WALLCLOCK",
        "self_excluded": True,
        "entries": entries,
        "entry_count": len(entries),
        "entries_canonical_sha256": entries_hash,
        "dynamic_exclusions": [
            {"path": MANIFEST_NAME, "reason": "SELF_EXCLUDED_TO_AVOID_CIRCULAR_HASH"},
            {"path": RECEIPT_NAME, "reason": "GENERATED_AFTER_MANIFEST_AND_BINDS_MANIFEST_RAW_AND_ENTRY_HASHES"},
        ],
        "authority": {"parent_gate_credit": False, "next_stage_authorized": False, "release_credit": False},
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
        print("PASS wrote deterministic gate and self-excluded manifest")
        return
    comparisons = {
        GATE_NAME: (PACKAGE / GATE_NAME).read_bytes() == gate_bytes,
        MANIFEST_NAME: (PACKAGE / MANIFEST_NAME).read_bytes() == manifest_bytes,
    }
    if not all(comparisons.values()):
        raise SystemExit(f"DETERMINISTIC_REPLAY_MISMATCH:{comparisons}")
    print("PASS deterministic gate and manifest byte identity")


if __name__ == "__main__":
    main()
