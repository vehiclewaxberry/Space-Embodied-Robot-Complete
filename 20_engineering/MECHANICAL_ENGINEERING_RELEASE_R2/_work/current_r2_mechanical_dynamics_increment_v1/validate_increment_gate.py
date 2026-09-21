from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import math
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
LOCK_NAME = "SOURCE_AUTHORITY_LOCK_V1.json"
GATE_NAME = "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_GATE_V1.json"
MANIFEST_NAME = "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_MANIFEST_V1.json"
RECEIPT_NAME = "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_INDEPENDENT_VALIDATION_V1.json"
STATIC_PAYLOAD = {
    "README.md",
    LOCK_NAME,
    "build_increment_gate.py",
    "test_increment_gate.py",
    "validate_increment_gate.py",
    GATE_NAME,
}
EXPECTED_SOURCE_IDS = {
    "parent_entry_gate_v4",
    "m4_configuration_gate",
    "m4_configuration_manifest",
    "m4_standalone_validator",
    "m4_negative_control_receipt",
    "m01_base_motion_gate",
    "m01_base_motion_manifest",
    "m01_standalone_validator",
    "m01_builder_negative_control_receipt",
    "time_varying_plant_gate",
    "time_varying_plant_manifest",
    "time_varying_plant_independent_receipt",
    "time_varying_plant_standalone_validator",
}
EXPECTED_GATE_CHECKS = {f"A{i:02d}_" for i in range(1, 29)}
EXPECTED_MAXIMUM_CLAIM = (
    "PASS_CONFIGURATION_TRACEABILITY_M01_BASE_MOTION_PRECERT_AND_TIME_VARYING_RIGID_PLANT_ADDITIVE_INCREMENT__"
    "CAD_SCENE_PAIR_CONTACT_POSTCAPTURE_CONTROL_NONABORT_PARENT_AND_RELEASE_HOLD"
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


def is_exact_int(value, expected: int) -> bool:
    return type(value) is int and value == expected


def load_frozen_inputs():
    root = repo_root()
    lock = strict_json_bytes((PACKAGE / LOCK_NAME).read_bytes())
    rows = lock.get("records")
    if not isinstance(rows, list) or len(rows) != 13:
        raise ValueError("LOCK_ROWS_NOT_EXACT_13")
    ids = [row.get("id") for row in rows]
    paths = [row.get("path") for row in rows]
    if set(ids) != EXPECTED_SOURCE_IDS or len(ids) != len(set(ids)):
        raise ValueError("LOCK_ID_SET_OR_UNIQUENESS_DRIFT")
    if len(paths) != len(set(paths)):
        raise ValueError("LOCK_PATH_NOT_UNIQUE")
    docs = {}
    pins = []
    for row in rows:
        path = root / row["path"]
        raw = path.read_bytes()
        actual_bytes = len(raw)
        actual_sha = sha256_bytes(raw)
        if type(row.get("bytes")) is not int:
            raise ValueError(f"LOCK_BYTES_TYPE:{row['id']}")
        match = actual_bytes == row["bytes"] and actual_sha == row["sha256"]
        if not match:
            raise ValueError(f"LOCK_PIN_MISMATCH:{row['id']}")
        pins.append(
            {
                "id": row["id"],
                "path": row["path"],
                "expected_bytes": row["bytes"],
                "actual_bytes": actual_bytes,
                "expected_sha256": row["sha256"],
                "actual_sha256": actual_sha,
                "match": True,
            }
        )
        if path.suffix.lower() == ".json":
            docs[row["id"]] = strict_json_bytes(raw)
    return lock, docs, pins


def source_semantics(lock, docs):
    v4 = docs["parent_entry_gate_v4"]
    m4 = docs["m4_configuration_gate"]
    m01 = docs["m01_base_motion_gate"]
    dyn = docs["time_varying_plant_gate"]
    dyn_iv = docs["time_varying_plant_independent_receipt"]
    m4_rows = m4.get("criteria", [])
    m01_rows = m01.get("checks", {})
    dyn_rows = dyn.get("checks", [])
    iv_rows = dyn_iv.get("checks", [])
    counters = m01.get("counters", {})
    boundaries = lock.get("authority_boundaries", {})

    facts = {
        "parent_schema_and_28": v4.get("schema") == "CURRENT_R2_DIGITAL_PROTOTYPE_DYNAMICS_ENTRY_GATE_V4"
        and is_exact_int(v4.get("summary", {}).get("passed"), 28)
        and is_exact_int(v4.get("summary", {}).get("total"), 28),
        "parent_cad_false": all(
            v4.get("CAD_state", {}).get(key) is False
            for key in (
                "candidate_artifact_generated",
                "candidate_geometry_validated",
                "candidate_snapshot_executed",
                "candidate_step_present",
                "hidden_glb_present",
                "owner_override_used",
            )
        )
        and is_exact_int(v4.get("CAD_state", {}).get("candidate_snapshot_outputs_present"), 0),
        "parent_m01_snapshot": v4.get("M01_state", {}).get("motion_certificates") == "0_OF_150"
        and v4.get("M01_state", {}).get("stage_instances") == "0_OF_3"
        and v4.get("M01_state", {}).get("clearance_policy") == "0_OF_11166"
        and v4.get("M01_state", {}).get("pair_oracle") == "0_OF_11166",
        "parent_holds": v4.get("next_stage_authorized") is False
        and v4.get("release_credit") is False
        and all(value is False for value in v4.get("system_HOLD_state", {}).values() if type(value) is bool),
        "m4_26": len(m4_rows) == 26 and all(row.get("status") == "PASS" for row in m4_rows),
        "m4_9_design": m4.get("summary", {}).get("configuration_ids") == "9_OF_9"
        and m4.get("summary", {}).get("design_mass_properties") == "9_OF_9",
        "m4_zero_promotions": m4.get("summary", {}).get("complete_current_geometry") == "0_OF_9"
        and m4.get("summary", {}).get("released_collision") == "0_OF_9"
        and m4.get("summary", {}).get("as_built_mass_properties") == "0_OF_9"
        and m4.get("summary", {}).get("production_complete_state_vectors") == "0_OF_9",
        "m4_pins_and_nc": m4.get("summary", {}).get("source_pins") == "20_OF_20"
        and m4.get("summary", {}).get("negative_controls") == "35_OF_35",
        "m4_authority_false": all(
            m4.get(key) is False
            for key in ("next_stage_authorized", "parent_gate_credit", "parent_gate_reissued", "release_credit")
        ),
        "m4_claim_exact": m4.get("gate_verdict")
        == "PASS_CONFIGURATION_CONTRACT_AND_DESIGN_MASS_TRACEABILITY_ONLY__ZERO_COMPLETE_CURRENT_GEOMETRY_ZERO_RELEASED_COLLISION_NO_PARENT_GATE_CREDIT",
        "m01_30": is_exact_int(m01.get("checks_passed"), 30)
        and is_exact_int(m01.get("checks_total"), 30)
        and len(m01_rows) == 30
        and all(value is True for value in m01_rows.values()),
        "m01_fixed_design": is_exact_int(counters.get("fixed_platform_design_pose_bindings"), 3)
        and is_exact_int(counters.get("fixed_platform_asset_level_operational_promotions"), 0),
        "m01_motion_1_150": is_exact_int(counters.get("system_motion_certificates_bound"), 1)
        and is_exact_int(counters.get("system_motion_certificates_required"), 150)
        and is_exact_int(counters.get("remaining_objects_without_system_motion_certificate"), 149),
        "m01_scene_pair_zero": is_exact_int(counters.get("authoritative_scene_values_bound"), 0)
        and is_exact_int(counters.get("authoritative_scene_values_required"), 30)
        and is_exact_int(counters.get("stage_instances_bound"), 0)
        and is_exact_int(counters.get("stage_instances_required"), 3)
        and is_exact_int(counters.get("clearance_policy_rows_bound"), 0)
        and is_exact_int(counters.get("clearance_policy_rows_required"), 11166)
        and is_exact_int(counters.get("pair_queries_executed"), 0)
        and is_exact_int(counters.get("pair_queries_required"), 11166),
        "m01_downstream_false": is_exact_int(counters.get("edges_certified"), 0)
        and counters.get("path_search_authorized") is False
        and counters.get("path_search_executed") is False
        and counters.get("next_stage_authorized") is False
        and counters.get("release_credit") is False
        and m01.get("pair_evaluation_authorized") is False,
        "m01_claim_exact": m01.get("maximum_claim")
        == "THREE_DESIGN_LEVEL_FIXED_PLATFORM_POSES_BOUND_AND_A_BASE_LINK_GLOBAL_ZERO_MOTION_CERTIFIED_AS_EXACTLY_ONE_OF_150__NO_SCENE_PAIR_EDGE_PATH_OR_RELEASE_CREDIT",
        "dyn_24": dyn.get("all_checks_pass") is True
        and is_exact_int(dyn.get("passed"), 24)
        and is_exact_int(dyn.get("total"), 24)
        and len(dyn_rows) == 24
        and all(row.get("pass") is True for row in dyn_rows),
        "dyn_scope": dyn.get("authority_scope") == "CURRENT_R2_ZERO_MOMENTUM_RIGID_DESIGN_DIAGNOSTIC_ONLY",
        "dyn_authority_false": all(
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
        ),
        "dyn_claim_exact": dyn.get("maximum_claim")
        == "R2_TIME_VARYING_TORQUE_DRIVEN_ZERO_MOMENTUM_RIGID_PLANT_CANDIDATE_PASS__ARBITRARY_DESIGN_EFFORT_ONLY__NO_FLEX_CONTACT_TARGET_ATTACHMENT_HARDWARE_CONTROL_PARENT_OR_RELEASE_CREDIT",
        "dyn_iv_36": is_exact_int(dyn_iv.get("passed"), 36)
        and is_exact_int(dyn_iv.get("total"), 36)
        and len(iv_rows) == 36
        and all(row.get("pass") is True for row in iv_rows),
        "dyn_iv_nc28": dyn_iv.get("negative_controls", {}).get("all_pass") is True
        and is_exact_int(dyn_iv.get("negative_controls", {}).get("count"), 28)
        and len(dyn_iv.get("negative_controls", {}).get("records", [])) == 28,
        "dyn_source_pins_19": dyn_iv.get("source_audit", {}).get("all_match") is True
        and len(dyn_iv.get("source_audit", {}).get("records", [])) == 19,
        "dyn_manifest_audit": dyn_iv.get("manifest_audit", {}).get("all_pass") is True
        and dyn_iv.get("manifest_audit", {}).get("checks", {}).get("receipt_excluded_explicitly") is True
        and is_exact_int(dyn_iv.get("manifest_audit", {}).get("declared_entry_count"), 11),
        "dyn_architecture": dyn_iv.get("validator_architecture") == "STANDALONE_NO_SHARED_BUILDER_EVALUATOR_SRC_IMPORTS"
        and dyn_iv.get("independence_import_audit", {}).get("pass") is True,
        "lock_boundaries": len(boundaries) == 9 and all(value is False for value in boundaries.values()),
    }
    return facts


def audit_gate(gate, pins, source_facts):
    expected_check_keys = {
        "A01_all_13_source_pins_exact",
        "A02_parent_v4_28_of_28_and_hash_immutable",
        "A03_parent_v4_CAD_remains_unexecuted",
        "A04_parent_v4_M01_snapshot_remains_zero_of_150",
        "A05_parent_v4_system_and_release_holds_preserved",
        "A06_M4_gate_26_of_26",
        "A07_M4_configuration_and_design_mass_9_of_9",
        "A08_M4_geometry_collision_and_as_built_not_promoted",
        "A09_M4_35_negative_controls_and_source_pins",
        "A10_M4_no_parent_or_release_credit",
        "A11_M01_gate_30_of_30",
        "A12_M01_fixed_platform_3_of_3_design_only",
        "A13_M01_base_motion_is_exactly_1_of_150",
        "A14_M01_scene_and_pair_work_remains_zero",
        "A15_M01_edges_path_next_and_release_remain_false",
        "A16_time_varying_plant_gate_24_of_24",
        "A17_time_varying_plant_scope_is_rigid_zero_momentum_design_only",
        "A18_time_varying_plant_downstream_authority_all_false",
        "A19_time_varying_standalone_36_of_36",
        "A20_time_varying_independent_negative_controls_28_of_28",
        "A21_time_varying_manifest_audit_and_explicit_receipt_exclusion",
        "A22_time_varying_validator_architecture_standalone",
        "A23_source_lock_all_authority_boundaries_false",
        "A24_additive_evidence_does_not_reissue_parent_V4",
        "A25_no_CAD_scene_pair_contact_nonabort_or_release_credit",
        "A26_all_three_increment_claims_are_narrow",
        "A27_strict_json_self_tests",
        "A28_every_check_passes",
    }
    pin_map = {row["id"]: row for row in pins}
    gate_pin_map = {row.get("id"): row for row in gate.get("source_binding", {}).get("pins", [])}
    facts = {
        "schema": gate.get("schema") == "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_GATE_V1",
        "decision_rule": gate.get("decision_rule") == "Authority > evidence > independent reproduction > agent opinion",
        "checks_exact": set(gate.get("checks", {})) == expected_check_keys
        and all(value is True for value in gate.get("checks", {}).values()),
        "summary": is_exact_int(gate.get("summary", {}).get("passed"), 28)
        and is_exact_int(gate.get("summary", {}).get("total"), 28)
        and gate.get("summary", {}).get("failed") == [],
        "pins": gate.get("source_binding", {}).get("all_match") is True
        and is_exact_int(gate.get("source_binding", {}).get("matched"), 13)
        and is_exact_int(gate.get("source_binding", {}).get("total"), 13)
        and gate_pin_map == pin_map,
        "source_semantics": all(source_facts.values()),
        "parent_integrity": gate.get("parent_integrity")
        == {
            "parent_V4_sha256": "277BE6349EC87E3CC76519E824F368F1D720C2C7E01646255DA5865510CB87EF",
            "parent_gate_mutated": False,
            "parent_gate_reissued": False,
            "parent_gate_credit_inherited": False,
            "interpretation": "CHILD_1_OF_150_IS_ADDITIVE_PRECREDIT_ONLY__PARENT_V4_REMAINS_0_OF_150_UNTIL_FORMAL_REISSUE",
        },
        "system_holds": len(gate.get("system_hold_state", {})) == 14
        and all(value is False for value in gate.get("system_hold_state", {}).values()),
        "claim": gate.get("maximum_claim") == EXPECTED_MAXIMUM_CLAIM,
        "verdict": gate.get("technical_verdict")
        == "PASS_ADDITIVE_CONFIGURATION_M01_BASE_MOTION_AND_TIME_VARYING_RIGID_PLANT_EVIDENCE__NO_PARENT_GATE_REISSUE_OR_RELEASE_CREDIT",
        "review": gate.get("review_status") == "PENDING_OWNER_REVIEW",
        "authority": all(
            gate.get(key) is False
            for key in ("parent_gate_credit", "parent_gate_reissued", "next_stage_authorized", "release_credit")
        ),
    }
    return facts


def audit_manifest(manifest):
    entries = manifest.get("entries", [])
    paths = [row.get("path") for row in entries]
    entry_map = {row.get("path"): row for row in entries}
    actual_files = {
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*")
        if path.is_file()
    }
    allowed_files = STATIC_PAYLOAD | {MANIFEST_NAME, RECEIPT_NAME}
    checks = {
        "schema": manifest.get("schema") == "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_MANIFEST_V1",
        "self_excluded": manifest.get("self_excluded") is True and MANIFEST_NAME not in paths,
        "paths_exact": set(paths) == STATIC_PAYLOAD and len(paths) == len(set(paths)) == len(STATIC_PAYLOAD),
        "entry_count": is_exact_int(manifest.get("entry_count"), len(STATIC_PAYLOAD)),
        "paths_sorted": paths == sorted(paths),
        "entry_hashes": all(
            type(entry_map[rel].get("bytes")) is int
            and entry_map[rel]["bytes"] == (PACKAGE / rel).stat().st_size
            and entry_map[rel]["sha256"] == sha256_bytes((PACKAGE / rel).read_bytes())
            for rel in STATIC_PAYLOAD
        ) if set(paths) == STATIC_PAYLOAD else False,
        "entries_hash": manifest.get("entries_canonical_sha256") == sha256_bytes(canonical_json(entries)),
        "exclusions": manifest.get("dynamic_exclusions")
        == [
            {"path": MANIFEST_NAME, "reason": "SELF_EXCLUDED_TO_AVOID_CIRCULAR_HASH"},
            {"path": RECEIPT_NAME, "reason": "GENERATED_AFTER_MANIFEST_AND_BINDS_MANIFEST_RAW_AND_ENTRY_HASHES"},
        ],
        "no_unlisted_files": actual_files <= allowed_files and STATIC_PAYLOAD | {MANIFEST_NAME} <= actual_files,
        "no_cache_or_bytecode": not any(
            any(part in {"__pycache__", ".pytest_cache"} for part in path.parts)
            or path.suffix.lower() in {".pyc", ".pyo"}
            for path in PACKAGE.rglob("*")
        ),
        "authority": manifest.get("authority")
        == {"parent_gate_credit": False, "next_stage_authorized": False, "release_credit": False},
    }
    return checks


def import_architecture_audit():
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    forbidden = {name for name in imported if "build_increment_gate" in name}
    return {"imports": sorted(imported), "forbidden": sorted(forbidden), "pass": not forbidden}


def run_negative_controls(lock, docs, gate, manifest):
    cases = []

    def source_case(case_id, mutate):
        trial_lock = copy.deepcopy(lock)
        trial_docs = copy.deepcopy(docs)
        mutate(trial_lock, trial_docs)
        rejected = not all(source_semantics(trial_lock, trial_docs).values())
        cases.append({"id": case_id, "rejected": rejected})

    source_case("NC01_PARENT_CAD_PROMOTION", lambda _, d: d["parent_entry_gate_v4"]["CAD_state"].__setitem__("candidate_artifact_generated", True))
    source_case("NC02_PARENT_MOTION_REWRITE", lambda _, d: d["parent_entry_gate_v4"]["M01_state"].__setitem__("motion_certificates", "1_OF_150"))
    source_case("NC03_M4_CRITERION_FAIL", lambda _, d: d["m4_configuration_gate"]["criteria"][0].__setitem__("status", "FAIL"))
    source_case("NC04_M4_GEOMETRY_PROMOTION", lambda _, d: d["m4_configuration_gate"]["summary"].__setitem__("complete_current_geometry", "1_OF_9"))
    source_case("NC05_M4_PARENT_CREDIT", lambda _, d: d["m4_configuration_gate"].__setitem__("parent_gate_credit", True))
    source_case("NC06_M4_CLAIM_ESCALATION", lambda _, d: d["m4_configuration_gate"].__setitem__("gate_verdict", "FULL_RELEASE"))
    source_case("NC07_M01_BOOL_AS_COUNT", lambda _, d: d["m01_base_motion_gate"]["counters"].__setitem__("system_motion_certificates_bound", True))
    source_case("NC08_M01_MOTION_PROMOTION", lambda _, d: d["m01_base_motion_gate"]["counters"].__setitem__("system_motion_certificates_bound", 2))
    source_case("NC09_M01_SCENE_PROMOTION", lambda _, d: d["m01_base_motion_gate"]["counters"].__setitem__("stage_instances_bound", 1))
    source_case("NC10_M01_PAIR_PROMOTION", lambda _, d: d["m01_base_motion_gate"]["counters"].__setitem__("pair_queries_executed", 1))
    source_case("NC11_M01_PATH_PROMOTION", lambda _, d: d["m01_base_motion_gate"]["counters"].__setitem__("path_search_authorized", True))
    source_case("NC12_M01_CLAIM_ESCALATION", lambda _, d: d["m01_base_motion_gate"].__setitem__("maximum_claim", "FULL_RELEASE"))
    source_case("NC13_DYN_GATE_FAIL", lambda _, d: d["time_varying_plant_gate"]["checks"][0].__setitem__("pass", False))
    source_case("NC14_DYN_SCOPE_ESCALATION", lambda _, d: d["time_varying_plant_gate"].__setitem__("authority_scope", "PRODUCTION"))
    source_case("NC15_DYN_CONTACT_PROMOTION", lambda _, d: d["time_varying_plant_gate"].__setitem__("contact_valid", True))
    source_case("NC16_DYN_CLAIM_ESCALATION", lambda _, d: d["time_varying_plant_gate"].__setitem__("maximum_claim", "FULL_RELEASE"))
    source_case("NC17_DYN_IV_COUNT", lambda _, d: d["time_varying_plant_independent_receipt"].__setitem__("passed", 35))
    source_case("NC18_DYN_IV_NEGATIVE_COUNT", lambda _, d: d["time_varying_plant_independent_receipt"]["negative_controls"].__setitem__("count", 23))
    source_case("NC19_DYN_MANIFEST_AUDIT", lambda _, d: d["time_varying_plant_independent_receipt"]["manifest_audit"].__setitem__("all_pass", False))
    source_case("NC20_DYN_ARCHITECTURE", lambda _, d: d["time_varying_plant_independent_receipt"].__setitem__("validator_architecture", "SHARED_BUILDER"))
    source_case("NC21_LOCK_AUTHORITY", lambda l, _: l["authority_boundaries"].__setitem__("release_credit", True))

    gate_trial = copy.deepcopy(gate)
    gate_trial["review_status"] = "OWNER_APPROVED"
    gate_pins = copy.deepcopy(gate.get("source_binding", {}).get("pins", []))
    source_facts = source_semantics(lock, docs)
    review_audit = audit_gate(gate_trial, gate_pins, source_facts)
    cases.append(
        {
            "id": "NC22_AGGREGATE_REVIEW_ESCALATION",
            "rejected": review_audit.get("review") is False
            and all(value is True for key, value in review_audit.items() if key != "review"),
        }
    )
    manifest_trial = copy.deepcopy(manifest)
    manifest_trial["entries"].append(copy.deepcopy(manifest_trial["entries"][0]))
    cases.append({"id": "NC23_MANIFEST_DUPLICATE", "rejected": not all(audit_manifest(manifest_trial).values())})
    parser_cases = (
        ("NC24_JSON_DUPLICATE", b'{"x":1,"x":2}'),
        ("NC25_JSON_NAN", b'{"x":NaN}'),
        ("NC26_JSON_INFINITY", b'{"x":Infinity}'),
    )
    for case_id, raw in parser_cases:
        try:
            strict_json_bytes(raw)
            rejected = False
        except ValueError:
            rejected = True
        cases.append({"id": case_id, "rejected": rejected})
    return {"count": len(cases), "passed": sum(case["rejected"] for case in cases), "all_pass": all(case["rejected"] for case in cases), "cases": cases}


def validate_all():
    lock, docs, pins = load_frozen_inputs()
    gate = strict_json_bytes((PACKAGE / GATE_NAME).read_bytes())
    manifest_raw = (PACKAGE / MANIFEST_NAME).read_bytes()
    manifest = strict_json_bytes(manifest_raw)
    source_facts = source_semantics(lock, docs)
    gate_checks = audit_gate(gate, pins, source_facts)
    manifest_checks = audit_manifest(manifest)
    architecture = import_architecture_audit()
    negative = run_negative_controls(lock, docs, gate, manifest)
    checks = {
        "source_facts_all_pass": all(source_facts.values()),
        "gate_audit_all_pass": all(gate_checks.values()),
        "manifest_audit_all_pass": all(manifest_checks.values()),
        "validator_does_not_import_builder": architecture["pass"],
        "negative_controls_26_of_26": negative["all_pass"] and negative["count"] == 26,
    }
    receipt = {
        "schema": "CURRENT_R2_MECHANICAL_DYNAMICS_INCREMENT_INDEPENDENT_VALIDATION_V1",
        "generated_utc": "DETERMINISTIC_NO_WALLCLOCK",
        "validator_architecture": "STANDALONE_NO_BUILDER_IMPORT",
        "source_pin_count": len(pins),
        "source_facts": source_facts,
        "gate_audit": gate_checks,
        "manifest_audit": {
            "checks": manifest_checks,
            "raw_bytes": len(manifest_raw),
            "raw_sha256": sha256_bytes(manifest_raw),
            "entries_canonical_sha256": manifest.get("entries_canonical_sha256"),
            "dynamic_receipt_exclusion_reason": "RECEIPT_IS_GENERATED_AFTER_AND_BINDS_MANIFEST_TO_AVOID_CIRCULAR_HASH",
        },
        "import_audit": architecture,
        "negative_controls": negative,
        "checks": checks,
        "summary": {"passed": sum(checks.values()), "total": len(checks), "all_pass": all(checks.values())},
        "authority": {"parent_gate_credit": False, "next_stage_authorized": False, "release_credit": False},
        "maximum_claim": EXPECTED_MAXIMUM_CLAIM,
    }
    return receipt


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    receipt = validate_all()
    raw = canonical_json(receipt)
    if not receipt["summary"]["all_pass"]:
        raise SystemExit(json.dumps(receipt["summary"], sort_keys=True))
    if args.write:
        (PACKAGE / RECEIPT_NAME).write_bytes(raw)
        print("PASS standalone aggregate validation receipt written")
        return
    if (PACKAGE / RECEIPT_NAME).read_bytes() != raw:
        raise SystemExit("STORED_RECEIPT_CANONICAL_MISMATCH")
    print(
        json.dumps(
            {
                "all_pass": True,
                "source_pins": receipt["source_pin_count"],
                "aggregate_checks": "5/5",
                "negative_controls": "26/26",
                "stored_receipt_canonical_exact": True,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
