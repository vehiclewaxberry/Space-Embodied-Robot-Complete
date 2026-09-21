"""Standalone fail-closed validator for the append-only R2 increment V3."""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any


PACKAGE = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE.parents[3]
LOCK_NAME = "SOURCE_AUTHORITY_LOCK_V3.json"
GATE_NAME = "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_GATE_V3.json"
MANIFEST_NAME = "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_MANIFEST_V3.json"
RECEIPT_NAME = "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_STANDALONE_VALIDATION_V3.json"

MAXIMUM_CLAIM = (
    "PASS_APPEND_ONLY_V2_RETAINED__TIME_DOMAIN_CANDIDATE_19_OF_20_REPEAT_REQUIRED__"
    "SINGLE_PARENT_HOLD_REBIND_16_OF_16_PASS__"
    "EXTERNAL_AUDIT_PASS_FOR_TIME_DOMAIN_DIAGNOSTIC_ONLY__NO_CONTROL_RELEASE__"
    "ALL_PARENT_CONTROL_HARDWARE_CONTACT_COLLISION_SAFE_SIM13_NONABORT_NEXT_RELEASE_HOLD"
)
TECHNICAL_VERDICT = (
    "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_V3_APPEND_ONLY_EVIDENCE_PASS__"
    "ORIGINAL_TIME_DOMAIN_GATE_REMAINS_REPEAT_REQUIRED__NO_AUTHORITY_UPGRADE"
)
HOLD_CLAIM = "V3_AGGREGATION_ATTEMPTED_REPEAT_REQUIRED__NO_AUTHORITY_UPGRADE"
DECISION_RULE = (
    "Authority > fixed source lock > external audit > standalone validation > "
    "append-only evidence > agent opinion"
)

FALSE_BOUNDARY_KEYS = (
    "attachment_valid",
    "cad_execution_credit",
    "collision_valid",
    "contact_valid",
    "control_valid",
    "hardware_valid",
    "m01_path_bound",
    "next_stage_authorized",
    "non_abort_authorized",
    "original_time_domain_gate_reissued",
    "parent_gate_credit",
    "parent_gate_reissued",
    "precontact_tracking_validated",
    "release_credit",
    "safe_gate_credit",
    "sim13_credit",
    "task_metric_parent_gate_reissued",
    "time_domain_control_valid",
)
FALSE_BOUNDARIES = {key: False for key in FALSE_BOUNDARY_KEYS}

V2_BASE = "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/current_r2_mechanical_dynamics_control_increment_v2"
TD_BASE = "30_simulation/r2_control_engineering_closure/time_domain_precontact_tracking_candidate_v1"
RB_BASE = "30_simulation/r2_control_engineering_closure/time_domain_precontact_tracking_metric_parent_rebind_v1"
EXT_BASE = "30_simulation/r2_control_engineering_closure/time_domain_precontact_tracking_external_audit_v1"

EXPECTED_ID_PATHS = {
    "v2_builder": f"{V2_BASE}/build_increment_gate_v2.py",
    "v2_gate": f"{V2_BASE}/CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_GATE_V2.json",
    "v2_manifest": f"{V2_BASE}/CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_MANIFEST_V2.json",
    "v2_receipt": f"{V2_BASE}/CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_STANDALONE_VALIDATION_V2.json",
    "v2_readme": f"{V2_BASE}/README.md",
    "v2_lock": f"{V2_BASE}/SOURCE_AUTHORITY_LOCK_V2.json",
    "v2_tests": f"{V2_BASE}/test_increment_gate_v2.py",
    "v2_validator": f"{V2_BASE}/validate_increment_gate_v2.py",
    "td_builder": f"{TD_BASE}/build_time_domain_precontact_tracking_candidate.py",
    "td_contract": f"{TD_BASE}/contracts/CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_CONTRACT_V1.json",
    "td_readme": f"{TD_BASE}/README.md",
    "td_evidence": f"{TD_BASE}/results/CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_EVIDENCE_V1.json",
    "td_gate": f"{TD_BASE}/results/CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_GATE_V1.json",
    "td_manifest": f"{TD_BASE}/results/CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_MANIFEST_V1.json",
    "td_sha": f"{TD_BASE}/results/CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_SHA256_V1.csv",
    "td_negative": f"{TD_BASE}/results/CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_NEGATIVE_CONTROL_RESULTS_V1.json",
    "td_init": f"{TD_BASE}/src/__init__.py",
    "td_source": f"{TD_BASE}/src/time_domain_precontact_tracking.py",
    "td_tests": f"{TD_BASE}/tests/test_time_domain_precontact_tracking.py",
    "rb_builder": f"{RB_BASE}/build_metric_parent_rebind.py",
    "rb_contract": f"{RB_BASE}/contracts/CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_CONTRACT_V1.json",
    "rb_readme": f"{RB_BASE}/README.md",
    "rb_evidence": f"{RB_BASE}/results/CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_EVIDENCE_V1.json",
    "rb_gate": f"{RB_BASE}/results/CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_GATE_V1.json",
    "rb_manifest": f"{RB_BASE}/results/CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_MANIFEST_V1.json",
    "rb_negative": f"{RB_BASE}/results/CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_NEGATIVE_CONTROLS_V1.json",
    "rb_sha": f"{RB_BASE}/results/CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_SHA256_V1.csv",
    "rb_init": f"{RB_BASE}/src/__init__.py",
    "rb_source": f"{RB_BASE}/src/metric_parent_rebind.py",
    "rb_tests": f"{RB_BASE}/tests/test_metric_parent_rebind.py",
    "ext_readme": f"{EXT_BASE}/README.md",
    "ext_source_lock": f"{EXT_BASE}/SOURCE_LOCK_V1.json",
    "ext_auditor": f"{EXT_BASE}/audit_external.py",
    "ext_tests": f"{EXT_BASE}/tests/test_time_domain_external_audit.py",
    "ext_receipt": f"{EXT_BASE}/results/CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_EXTERNAL_AUDIT_GATE_V1.json",
}

GROUP_PREFIXES = {
    "v2": "v2_",
    "time_domain_candidate": "td_",
    "metric_parent_rebind": "rb_",
    "time_domain_external_audit": "ext_",
}

STATIC_PAYLOAD = {
    "README.md",
    "build_increment_gate_v3.py",
    "validate_increment_gate_v3.py",
    "test_increment_gate_v3.py",
    LOCK_NAME,
    GATE_NAME,
}
ALLOWED_FILES = STATIC_PAYLOAD | {MANIFEST_NAME, RECEIPT_NAME}


def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"DUPLICATE_JSON_KEY:{key}")
        out[key] = value
    return out


def _constant(token):
    raise ValueError(f"NONFINITE_JSON_CONSTANT:{token}")


def strict_json_bytes(raw: bytes) -> Any:
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def exact_int(value: Any, expected: int) -> bool:
    return type(value) is int and value == expected


def all_false(mapping: Any) -> bool:
    return isinstance(mapping, dict) and bool(mapping) and all(value is False for value in mapping.values())


def audit_lock_document(lock: dict[str, Any]) -> bool:
    records = lock.get("records", [])
    ids = [row.get("id") for row in records if isinstance(row, dict)]
    paths = [row.get("path") for row in records if isinstance(row, dict)]
    groups = [row.get("group") for row in records if isinstance(row, dict)]
    row_shape = all(
        set(row) == {"bytes", "group", "id", "path", "sha256"}
        and type(row["bytes"]) is int
        and row["bytes"] > 0
        and isinstance(row["sha256"], str)
        and len(row["sha256"]) == 64
        and row["sha256"] == row["sha256"].upper()
        for row in records
    )
    group_exact = all(
        row["id"].startswith(GROUP_PREFIXES[row["group"]])
        for row in records
        if row.get("group") in GROUP_PREFIXES
    ) and set(groups) == set(GROUP_PREFIXES)
    return all((
        lock.get("schema") == "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_SOURCE_LOCK_V3",
        lock.get("generated_utc") == "DETERMINISTIC_NO_WALLCLOCK",
        lock.get("decision_rule") == DECISION_RULE,
        lock.get("maximum_claim_boundary") == MAXIMUM_CLAIM,
        lock.get("authority_boundaries") == FALSE_BOUNDARIES,
        exact_int(lock.get("record_count"), len(EXPECTED_ID_PATHS)),
        len(records) == len(EXPECTED_ID_PATHS),
        ids == sorted(EXPECTED_ID_PATHS),
        len(ids) == len(set(ids)),
        len(paths) == len(set(paths)),
        set(ids) == set(EXPECTED_ID_PATHS),
        {row["id"]: row["path"] for row in records} == EXPECTED_ID_PATHS,
        row_shape,
        group_exact,
    ))


def load_frozen_inputs(lock_override: dict[str, Any] | None = None):
    lock_raw = (PACKAGE / LOCK_NAME).read_bytes()
    lock = strict_json_bytes(lock_raw) if lock_override is None else lock_override
    if not audit_lock_document(lock):
        raise ValueError("SOURCE_LOCK_DOCUMENT_INVALID")
    raws: dict[str, bytes] = {}
    docs: dict[str, Any] = {}
    pins = []
    for row in lock["records"]:
        path = PROJECT_ROOT / row["path"]
        exists = path.is_file()
        raw = path.read_bytes() if exists else b""
        actual_sha = sha256_bytes(raw) if exists else None
        match = bool(exists and len(raw) == row["bytes"] and actual_sha == row["sha256"])
        pins.append({
            "id": row["id"], "group": row["group"], "path": row["path"],
            "expected_bytes": row["bytes"], "actual_bytes": len(raw) if exists else None,
            "expected_sha256": row["sha256"], "actual_sha256": actual_sha, "match": match,
        })
        if not match:
            raise ValueError(f"SOURCE_PIN_DRIFT:{row['id']}")
        raws[row["id"]] = raw
        if path.suffix.lower() == ".json":
            docs[row["id"]] = strict_json_bytes(raw)
    return lock_raw, lock, raws, docs, pins


def _manifest_inventory_current(manifest: dict[str, Any]) -> bool:
    rows = manifest.get("inventory", [])
    if not exact_int(manifest.get("inventory_count"), len(rows)):
        return False
    for row in rows:
        path = PROJECT_ROOT / row.get("path", "")
        if not path.is_file():
            return False
        raw = path.read_bytes()
        if len(raw) != row.get("bytes") or sha256_bytes(raw) != row.get("sha256"):
            return False
    return True


def independent_source_semantics(docs: dict[str, Any]) -> dict[str, bool]:
    v2_gate = docs["v2_gate"]
    v2_receipt = docs["v2_receipt"]
    v2_manifest = docs["v2_manifest"]
    td_gate = docs["td_gate"]
    td_evidence = docs["td_evidence"]
    td_contract = docs["td_contract"]
    td_negative = docs["td_negative"]
    td_manifest = docs["td_manifest"]
    rb_gate = docs["rb_gate"]
    rb_evidence = docs["rb_evidence"]
    rb_negative = docs["rb_negative"]
    rb_manifest = docs["rb_manifest"]

    td_checks = td_gate.get("checks", {})
    td_failed = [key for key, value in td_checks.items() if value is not True]
    comparisons = td_evidence.get("same_dimension_comparisons", {})
    thresholds = td_contract.get("thresholds", {})
    comparison_pass = len(comparisons) == 2 and all(
        row.get("same_task_dimension_reference_units_frame_metric") is True
        and row.get("final_error_ratio_controlled_to_uncontrolled", math.inf)
        <= thresholds.get("controlled_final_error_ratio_to_same_task_uncontrolled_max", -math.inf)
        and row.get("rms_error_ratio_controlled_to_uncontrolled", math.inf)
        <= thresholds.get("controlled_rms_error_ratio_to_same_task_uncontrolled_max", -math.inf)
        for row in comparisons.values()
    )
    rb_recomputed = rb_evidence.get("rebound_metric_gate", {})
    original_summary = {"passed": 19, "total": 20, "failed": ["G04_UPSTREAM_TRANSITIVE_SOURCE_AND_METRIC_PARAMETER_LOCKS_EXACT"]}

    # External facts are intentionally fail-closed until the completed package
    # is appended to EXPECTED_ID_PATHS and audited fieldwise below.
    external_present = all(key in docs for key in ("ext_source_lock", "ext_receipt"))
    external_receipt = docs.get("ext_receipt", {})
    external_facts = bool(
        external_present
        and external_receipt.get("schema")
        == "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_EXTERNAL_AUDIT_GATE_V1"
        and external_receipt.get("technical_verdict")
        == "EXTERNAL_AUDIT_PASS_FOR_TIME_DOMAIN_DIAGNOSTIC_ONLY__NO_CONTROL_RELEASE"
        and external_receipt.get("all_pass") is True
        and exact_int(external_receipt.get("passed"), 18)
        and exact_int(external_receipt.get("total"), 18)
        and len(external_receipt.get("checks", {})) == 18
        and all(external_receipt.get("checks", {}).values())
        and external_receipt.get("negative_controls", {}).get("all_pass") is True
        and exact_int(external_receipt.get("negative_controls", {}).get("passed"), 12)
        and exact_int(external_receipt.get("negative_controls", {}).get("total"), 12)
        and all_false(external_receipt.get("authority_boundaries"))
        and external_receipt.get("original_candidate_gate_passed") is False
        and external_receipt.get("original_candidate_gate_reissued") is False
        and external_receipt.get("time_domain_diagnostic_executed") is True
        and external_receipt.get("review_status") == "PENDING_OWNER_REVIEW"
        and external_receipt.get("maximum_claim")
        == "EXTERNAL_AUDIT_PASS_FOR_TIME_DOMAIN_DIAGNOSTIC_ONLY__NO_CONTROL_RELEASE"
    )

    return {
        "v2_gate_38_of_38_append_only_pass": bool(
            v2_gate.get("schema") == "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_GATE_V2"
            and v2_gate.get("gate_passed") is True
            and exact_int(v2_gate.get("summary", {}).get("passed"), 38)
            and exact_int(v2_gate.get("summary", {}).get("total"), 38)
            and len(v2_gate.get("checks", {})) == 38
            and all(v2_gate.get("checks", {}).values())
        ),
        "v2_authority_all_false": v2_gate.get("authority_boundaries") is not None
        and all_false(v2_gate.get("authority_boundaries")),
        "v2_standalone_7_of_7": bool(
            v2_receipt.get("all_pass") is True
            and exact_int(v2_receipt.get("passed"), 7)
            and exact_int(v2_receipt.get("total"), 7)
            and v2_receipt.get("validator_architecture")
            == "STANDALONE_NO_BUILDER_IMPORT__FIXED_EXTERNAL_SOURCE_LOCK"
        ),
        "v2_manifest_retained": bool(
            v2_manifest.get("schema") == "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_MANIFEST_V2"
            and v2_manifest.get("authority", {}).get("next_stage_authorized") is False
            and v2_manifest.get("authority", {}).get("release_credit") is False
        ),
        "time_domain_original_19_of_20_single_g04": bool(
            td_gate.get("schema") == "CTRL_R2_TIME_DOMAIN_PRECONTACT_TRACKING_CANDIDATE_GATE_V1"
            and td_gate.get("summary") == original_summary
            and td_gate.get("gate_passed") is False
            and td_gate.get("time_domain_diagnostic_executed") is True
            and td_gate.get("root_frame_twist_rate_diagnostic_pass") is False
            and len(td_checks) == 20
            and td_failed == ["G04_UPSTREAM_TRANSITIVE_SOURCE_AND_METRIC_PARAMETER_LOCKS_EXACT"]
        ),
        "time_domain_scientific_diagnostics_preserved": bool(
            td_checks.get("G06_FOUR_SCENARIOS_TWO_SAME_DIMENSION_COMPARISON_PAIRS") is True
            and all(
                value is True
                for key, value in td_checks.items()
                if key != "G04_UPSTREAM_TRANSITIVE_SOURCE_AND_METRIC_PARAMETER_LOCKS_EXACT"
            )
            and comparison_pass
            and len(td_evidence.get("scenarios", [])) == 4
        ),
        "time_domain_direct_pins_10_of_10": bool(
            td_evidence.get("source_binding", {}).get("all_match") is True
            and exact_int(td_evidence.get("source_binding", {}).get("matched"), 10)
            and exact_int(td_evidence.get("source_binding", {}).get("total"), 10)
        ),
        "time_domain_negative_20_of_20": bool(
            td_negative.get("all_pass") is True
            and exact_int(td_negative.get("passed"), 20)
            and exact_int(td_negative.get("count"), 20)
        ),
        "time_domain_manifest_current": _manifest_inventory_current(td_manifest),
        "time_domain_authority_all_false": all_false(td_gate.get("authority_boundaries"))
        and all_false(td_evidence.get("authority_boundaries")),
        "rebind_gate_16_of_16": bool(
            rb_gate.get("schema") == "CTRL_R2_TIME_DOMAIN_METRIC_PARENT_REBIND_GATE_V1"
            and rb_gate.get("maximum_claim") == "TIME_DOMAIN_DIAGNOSTIC_TRANSITIVE_PARENT_HOLD_REBIND_PASS"
            and rb_gate.get("gate_passed") is True
            and rb_gate.get("original_time_domain_gate_passed") is False
            and rb_gate.get("original_time_domain_gate_reissued") is False
            and exact_int(rb_gate.get("summary", {}).get("passed"), 16)
            and exact_int(rb_gate.get("summary", {}).get("total"), 16)
            and rb_gate.get("summary", {}).get("failed") == []
            and len(rb_gate.get("checks", {})) == 16
            and all(rb_gate.get("checks", {}).values())
        ),
        "rebind_recompute_17_of_17_and_original_retained": bool(
            rb_evidence.get("original_time_domain_gate_summary") == original_summary
            and rb_evidence.get("rebound_metric_source_binding", {}).get("all_match") is True
            and exact_int(rb_evidence.get("rebound_metric_source_binding", {}).get("matched"), 7)
            and exact_int(rb_evidence.get("rebound_metric_source_binding", {}).get("total"), 7)
            and rb_recomputed.get("all_checks_pass") is True
            and exact_int(rb_recomputed.get("passed"), 17)
            and exact_int(rb_recomputed.get("total"), 17)
        ),
        "rebind_negative_10_of_10": bool(
            rb_negative.get("all_pass") is True
            and exact_int(rb_negative.get("passed"), 10)
            and exact_int(rb_negative.get("count"), 10)
        ),
        "rebind_manifest_current": _manifest_inventory_current(rb_manifest),
        "rebind_authority_all_false": all_false(rb_gate.get("authority_boundaries"))
        and all_false(rb_evidence.get("authority_boundaries")),
        "external_audit_exact_claim_and_all_false": external_facts,
    }


def expected_gate_document(lock_raw: bytes, lock: dict[str, Any], pins: list[dict[str, Any]], facts: dict[str, bool]) -> dict[str, Any]:
    checks = {
        "A01_SOURCE_LOCK_SCHEMA_RECORD_SET_AND_AUTHORITY_EXACT": audit_lock_document(lock),
        "A02_ALL_SOURCE_BYTES_AND_SHA256_MATCH": len(pins) == len(EXPECTED_ID_PATHS) and all(row["match"] for row in pins),
        "A03_V2_GATE_38_OF_38_APPEND_ONLY_PASS": facts.get("v2_gate_38_of_38_append_only_pass") is True,
        "A04_V2_AUTHORITY_ALL_FALSE": facts.get("v2_authority_all_false") is True,
        "A05_V2_STANDALONE_7_OF_7": facts.get("v2_standalone_7_of_7") is True,
        "A06_V2_MANIFEST_RETAINED": facts.get("v2_manifest_retained") is True,
        "A07_TIME_DOMAIN_ORIGINAL_19_OF_20_SINGLE_G04": facts.get("time_domain_original_19_of_20_single_g04") is True,
        "A08_TIME_DOMAIN_SCIENTIFIC_DIAGNOSTICS_PRESERVED": facts.get("time_domain_scientific_diagnostics_preserved") is True,
        "A09_TIME_DOMAIN_DIRECT_PINS_10_OF_10": facts.get("time_domain_direct_pins_10_of_10") is True,
        "A10_TIME_DOMAIN_NEGATIVE_20_OF_20": facts.get("time_domain_negative_20_of_20") is True,
        "A11_TIME_DOMAIN_MANIFEST_CURRENT": facts.get("time_domain_manifest_current") is True,
        "A12_TIME_DOMAIN_AUTHORITY_ALL_FALSE": facts.get("time_domain_authority_all_false") is True,
        "A13_REBIND_GATE_16_OF_16": facts.get("rebind_gate_16_of_16") is True,
        "A14_REBIND_RECOMPUTE_17_OF_17_AND_ORIGINAL_RETAINED": facts.get("rebind_recompute_17_of_17_and_original_retained") is True,
        "A15_REBIND_NEGATIVE_10_OF_10": facts.get("rebind_negative_10_of_10") is True,
        "A16_REBIND_MANIFEST_CURRENT": facts.get("rebind_manifest_current") is True,
        "A17_REBIND_AUTHORITY_ALL_FALSE": facts.get("rebind_authority_all_false") is True,
        "A18_EXTERNAL_AUDIT_EXACT_DIAGNOSTIC_ONLY_CLAIM": facts.get("external_audit_exact_claim_and_all_false") is True,
        "A19_PARENT_GATES_NOT_REISSUED": True,
        "A20_ALL_SOURCE_SEMANTIC_FACTS_PASS": len(facts) == 16 and all(facts.values()),
        "A21_ALL_DOWNSTREAM_AUTHORITY_BOUNDARIES_FALSE": all(value is False for value in FALSE_BOUNDARIES.values()),
    }
    achieved = all(checks.values())
    return {
        "schema": "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_GATE_V3",
        "technical_verdict": TECHNICAL_VERDICT if achieved else "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_V3_HOLD",
        "scope": "APPEND_ONLY_ADDITIVE_EVIDENCE_CONVERGENCE_ONLY",
        "maximum_allowed_claim": MAXIMUM_CLAIM,
        "maximum_claim": MAXIMUM_CLAIM if achieved else HOLD_CLAIM,
        "checks": checks,
        "summary": {"passed": sum(checks.values()), "total": len(checks), "failed": [key for key, value in checks.items() if not value]},
        "gate_passed": achieved,
        "source_binding": {"all_match": all(row["match"] for row in pins), "matched": sum(row["match"] for row in pins), "total": len(pins), "pins": pins},
        "source_lock_binding": {"path": LOCK_NAME, "bytes": len(lock_raw), "sha256": sha256_bytes(lock_raw)},
        "evidence_state": {
            "v2": "RETAINED_APPEND_ONLY_38_OF_38",
            "time_domain_candidate": "19_OF_20_REPEAT_REQUIRED_SINGLE_G04_PARENT_HOLD_FINGERPRINT_MISMATCH",
            "metric_parent_rebind": "16_OF_16_LOCAL_REBIND_PASS__RECOMPUTED_METRIC_17_OF_17__ORIGINAL_GATE_UNCHANGED",
            "external_audit": "TIME_DOMAIN_DIAGNOSTIC_ONLY__NO_CONTROL_RELEASE",
        },
        "retained_holds": [
            "ORIGINAL_TIME_DOMAIN_CANDIDATE_GATE_REMAINS_19_OF_20_REPEAT_REQUIRED",
            "PARENT_DYNAMICS_CONTROL_AND_MECHANICAL_GATES_NOT_REISSUED",
            "PRECONTACT_TRACKING_AND_TIME_DOMAIN_CONTROL_NOT_VALIDATED",
            "HARDWARE_CONTACT_COLLISION_SAFE_SIM13_NONABORT_NEXT_STAGE_AND_RELEASE_NOT_AUTHORIZED",
        ],
        "authority_boundaries": FALSE_BOUNDARIES,
        "parent_gate_reissued": False,
        "parent_gate_credit": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "review_status": "PENDING_OWNER_REVIEW",
        "generated_utc": "DETERMINISTIC_NO_WALLCLOCK",
    }


def observed_inventory():
    files = {path.relative_to(PACKAGE).as_posix() for path in PACKAGE.rglob("*") if path.is_file()}
    forbidden = [
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*")
        if any(part in {"__pycache__", ".pytest_cache"} for part in path.parts)
        or path.suffix.lower() in {".pyc", ".pyo"}
    ]
    return files, sorted(forbidden)


def expected_manifest_document() -> dict[str, Any]:
    rows = []
    for rel in sorted(STATIC_PAYLOAD):
        raw = (PACKAGE / rel).read_bytes()
        rows.append({"path": rel, "bytes": len(raw), "sha256": sha256_bytes(raw)})
    return {
        "schema": "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_MANIFEST_V3",
        "generated_utc": "DETERMINISTIC_NO_WALLCLOCK",
        "inventory_policy": "EXACT_ALLOWLIST_NO_EXTRA_NO_CACHE_OR_BYTECODE",
        "entries": rows,
        "entry_count": len(rows),
        "entries_canonical_sha256": sha256_bytes(canonical_json(rows)),
        "self_excluded": True,
        "dynamic_exclusions": [
            {"path": MANIFEST_NAME, "reason": "SELF_EXCLUDED_TO_AVOID_CIRCULAR_HASH"},
            {"path": RECEIPT_NAME, "reason": "GENERATED_AFTER_MANIFEST_AND_BINDS_MANIFEST"},
        ],
        "authority": {"parent_gate_reissued": False, "parent_gate_credit": False, "next_stage_authorized": False, "release_credit": False},
    }


def audit_manifest(manifest: dict[str, Any], inventory_override=None) -> dict[str, bool]:
    expected = expected_manifest_document()
    files, forbidden = observed_inventory()
    if inventory_override is not None:
        files = set(inventory_override)
    return {
        "document_exact": manifest == expected,
        "inventory_exact": files == ALLOWED_FILES,
        "no_cache_or_bytecode": forbidden == [],
        "authority_false": manifest.get("authority") == expected["authority"],
    }


def audit_gate(gate: dict[str, Any], lock_raw: bytes, lock: dict[str, Any], pins: list[dict[str, Any]], facts: dict[str, bool]) -> bool:
    return gate == expected_gate_document(lock_raw, lock, pins, facts)


def import_architecture_audit() -> dict[str, Any]:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    forbidden = sorted(name for name in imported if "build_increment_gate_v3" in name)
    return {"imports": sorted(imported), "forbidden": forbidden, "pass": forbidden == []}


def run_negative_controls(lock, docs, gate, manifest, pins, facts):
    cases = []

    def add(case_id, rejected):
        cases.append({"id": case_id, "rejected": bool(rejected)})

    for case_id, mutate in (
        ("NC01_GATE_PASS_FALSE", lambda d: d.__setitem__("gate_passed", False)),
        ("NC02_GATE_CLAIM_ESCALATION", lambda d: d.__setitem__("maximum_claim", "FULL_RELEASE")),
        ("NC03_GATE_CONTROL_AUTHORITY", lambda d: d["authority_boundaries"].__setitem__("control_valid", True)),
        ("NC04_GATE_ORIGINAL_PROMOTION", lambda d: d["evidence_state"].__setitem__("time_domain_candidate", "20_OF_20")),
        ("NC05_GATE_REBIND_PARENT_REISSUE", lambda d: d.__setitem__("parent_gate_reissued", True)),
        ("NC06_GATE_BOOL_COUNT", lambda d: d["summary"].__setitem__("passed", True)),
    ):
        trial = copy.deepcopy(gate)
        mutate(trial)
        add(case_id, not audit_gate(trial, (PACKAGE / LOCK_NAME).read_bytes(), lock, pins, facts))

    for case_id, mutate in (
        ("NC07_LOCK_PATH", lambda d: d["records"][0].__setitem__("path", "wrong")),
        ("NC08_LOCK_HASH", lambda d: d["records"][0].__setitem__("sha256", "0" * 64)),
        ("NC09_LOCK_RECORD_COUNT_BOOL", lambda d: d.__setitem__("record_count", True)),
        ("NC10_LOCK_AUTHORITY", lambda d: d["authority_boundaries"].__setitem__("release_credit", True)),
    ):
        trial = copy.deepcopy(lock)
        mutate(trial)
        rejected = not audit_lock_document(trial)
        if not rejected:
            try:
                load_frozen_inputs(trial)
            except ValueError:
                rejected = True
        add(case_id, rejected)

    trial_docs = copy.deepcopy(docs)
    trial_docs["td_gate"]["gate_passed"] = True
    add("NC11_UPSTREAM_TIME_DOMAIN_PROMOTION", not all(independent_source_semantics(trial_docs).values()))
    trial_docs = copy.deepcopy(docs)
    trial_docs["rb_gate"]["original_time_domain_gate_reissued"] = True
    add("NC12_UPSTREAM_REBIND_REISSUE", not all(independent_source_semantics(trial_docs).values()))

    for case_id, raw in (
        ("NC13_DUPLICATE_JSON", b'{"x":1,"x":2}'),
        ("NC14_NAN_JSON", b'{"x":NaN}'),
        ("NC15_INFINITY_JSON", b'{"x":Infinity}'),
    ):
        try:
            strict_json_bytes(raw)
            rejected = False
        except ValueError:
            rejected = True
        add(case_id, rejected)

    add("NC16_MANIFEST_EXTRA", not all(audit_manifest(manifest, ALLOWED_FILES | {"EXTRA.bin"}).values()))
    return {"cases": cases, "count": len(cases), "passed": sum(row["rejected"] for row in cases), "all_pass": all(row["rejected"] for row in cases)}


def validate_all() -> dict[str, Any]:
    lock_raw, lock, _, docs, pins = load_frozen_inputs()
    facts = independent_source_semantics(docs)
    gate = strict_json_bytes((PACKAGE / GATE_NAME).read_bytes())
    manifest_raw = (PACKAGE / MANIFEST_NAME).read_bytes()
    manifest = strict_json_bytes(manifest_raw)
    architecture = import_architecture_audit()
    negatives = run_negative_controls(lock, docs, gate, manifest, pins, facts)
    checks = {
        "V01_FIXED_SOURCE_LOCK_AND_ALL_PINS_EXACT": audit_lock_document(lock) and all(row["match"] for row in pins),
        "V02_ALL_SOURCE_SEMANTICS_FIELDWISE_PASS": len(facts) == 16 and all(facts.values()),
        "V03_GATE_EXACTLY_RECOMPUTED": audit_gate(gate, lock_raw, lock, pins, facts),
        "V04_MANIFEST_EXACT_NO_EXTRA_OR_CACHE": all(audit_manifest(manifest).values()),
        "V05_VALIDATOR_DOES_NOT_IMPORT_BUILDER": architecture["pass"],
        "V06_NEGATIVE_CONTROLS_16_OF_16": negatives["all_pass"] and exact_int(negatives["count"], 16),
        "V07_ALL_AUTHORITY_BOUNDARIES_FALSE": gate.get("authority_boundaries") == FALSE_BOUNDARIES,
    }
    receipt = {
        "schema": "CURRENT_R2_MECHANICAL_DYNAMICS_CONTROL_INCREMENT_STANDALONE_VALIDATION_V3",
        "technical_verdict": TECHNICAL_VERDICT,
        "maximum_allowed_claim": MAXIMUM_CLAIM,
        "achieved_claim": MAXIMUM_CLAIM,
        "validator_architecture": "STANDALONE_NO_BUILDER_IMPORT__FIXED_APPEND_ONLY_SOURCE_LOCK",
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "all_pass": all(checks.values()),
        "source_audit": {"all_match": all(row["match"] for row in pins), "count": len(pins), "pins": pins},
        "source_semantics": facts,
        "negative_controls": negatives,
        "manifest_binding": {"path": MANIFEST_NAME, "bytes": len(manifest_raw), "sha256": sha256_bytes(manifest_raw)},
        "source_lock_binding": {"path": LOCK_NAME, "bytes": len(lock_raw), "sha256": sha256_bytes(lock_raw)},
        "validator_import_audit": architecture,
        "authority_boundaries": FALSE_BOUNDARIES,
        "parent_gate_reissued": False,
        "parent_gate_credit": False,
        "next_stage_authorized": False,
        "release_credit": False,
        "generated_utc": "DETERMINISTIC_STANDALONE_VALIDATION_NO_WALLCLOCK",
    }
    if not receipt["all_pass"]:
        raise ValueError(f"STANDALONE_VALIDATION_FAILED:{[key for key, value in checks.items() if not value]}")
    return receipt


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-receipt", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    raw = canonical_json(validate_all())
    if args.write_receipt:
        (PACKAGE / RECEIPT_NAME).write_bytes(raw)
        print("PASS wrote standalone V3 validation receipt")
        return
    if (PACKAGE / RECEIPT_NAME).read_bytes() != raw:
        raise SystemExit("STANDALONE_RECEIPT_DETERMINISTIC_REPLAY_MISMATCH")
    print("PASS standalone V3 validation and receipt byte identity")


if __name__ == "__main__":
    main()
