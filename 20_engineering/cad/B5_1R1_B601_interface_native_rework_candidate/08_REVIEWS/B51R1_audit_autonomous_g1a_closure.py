from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import psutil
import yaml


ROOT = Path(__file__).resolve().parents[1]
CLOSURE = ROOT / "09_DELIVERY" / "B51R1_AUTONOMOUS_G1A_CLOSURE_20260801"
OUTPUT = ROOT / "07_VERIFICATION" / "AUTONOMOUS" / "G1A" / "B51R1_G1A_PREQUORUM_MACHINE_AUDIT.json"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


result: dict[str, object] = {"checks": {}, "failures": []}
failures: list[str] = result["failures"]

closure_files = sorted(p for p in CLOSURE.rglob("*") if p.is_file())
utf8_failures = []
for path in closure_files:
    try:
        path.read_text(encoding="utf-8", errors="strict")
    except Exception as exc:
        utf8_failures.append(f"{path.name}:{type(exc).__name__}")
result["checks"]["closure_files"] = len(closure_files)
result["checks"]["strict_utf8_failures"] = utf8_failures
if utf8_failures:
    failures.append("STRICT_UTF8")

json_files = list(CLOSURE.glob("*.json"))
yaml_files = list(CLOSURE.glob("*.yaml"))
csv_files = list(CLOSURE.glob("*.csv"))
for path in json_files:
    json.loads(path.read_text(encoding="utf-8"))
for path in yaml_files:
    yaml.safe_load(path.read_text(encoding="utf-8"))
for path in csv_files:
    rows(path)
result["checks"]["parsed"] = {"json": len(json_files), "yaml": len(yaml_files), "csv": len(csv_files)}

lock_path = CLOSURE / "B51R1_PHASE2A_INPUT_LOCK_V2_REFROZEN.json"
lock = json.loads(lock_path.read_text(encoding="utf-8"))
locked = lock["locked_items"]
ids = [entry["id"] for entry in locked]
paths = [entry["path"] for entry in locked]
lock_failures = []
for entry in locked:
    path = ROOT / Path(entry["path"])
    if not path.is_file():
        lock_failures.append(f"MISSING:{entry['id']}:{entry['path']}")
        continue
    if path.stat().st_size != entry["bytes"]:
        lock_failures.append(f"BYTES:{entry['id']}")
    if sha(path) != entry["sha256"]:
        lock_failures.append(f"SHA:{entry['id']}")
result["checks"]["input_lock"] = {
    "status": lock["status"],
    "items": len(locked),
    "unique_ids": len(ids) == len(set(ids)),
    "unique_paths": len(paths) == len(set(paths)),
    "self_included": lock["self_included"],
    "failures": lock_failures,
    "sha256": sha(lock_path),
}
sidecar = (CLOSURE / "B51R1_PHASE2A_INPUT_LOCK_V2_REFROZEN.json.sha256").read_text(encoding="utf-8").strip()
required_lock_ids = {
    "H10_CURRENT_STATUS_SOURCE",
    "T005_CURRENT_STATUS_SOURCE",
    "G1A_EVIDENCE_PATH_POLICY",
    "FEATURE_OWNERSHIP_UNIQUENESS_RECEIPT",
}
result["checks"]["input_lock"]["sidecar_match"] = sidecar == sha(lock_path)
result["checks"]["input_lock"]["required_ids_present"] = sorted(required_lock_ids.intersection(ids))
if (
    lock_failures
    or len(ids) != len(set(ids))
    or len(paths) != len(set(paths))
    or lock["self_included"]
    or sidecar != sha(lock_path)
    or len(locked) < 52
    or not required_lock_ids.issubset(ids)
):
    failures.append("INPUT_LOCK")

feature_rows = rows(CLOSURE / "B51R1_G1A_EXPANDED_NATIVE_FEATURE_REGISTER_V2.csv")
canonical = []
for row in feature_rows:
    canonical.append((row["carrier_file"], row["link_frame"]))
    canonical.append((row["carrier_file"], row["visual_mount_frame"]))
    for field in ["incoming_joint_child_side_frame", "outgoing_joint_parent_side_frames", "moving_axis_features", "q0_plane_features", "fixed_joint_reference_features"]:
        for token in row[field].replace("|", ";").split(";"):
            if token and token != "NONE":
                canonical.append((row["carrier_file"], token))
feature_summary = {
    "carrier_rows": len(feature_rows),
    "canonical_feature_count": len(canonical),
    "unique_owner_feature_pairs": len(set(canonical)),
    "duplicates": sorted([f"{a}::{b}" for a, b in set(canonical) if canonical.count((a, b)) > 1]),
}
result["checks"]["features"] = feature_summary
if feature_summary["carrier_rows"] != 10 or feature_summary["canonical_feature_count"] != 57 or feature_summary["duplicates"]:
    failures.append("FEATURE_UNIQUENESS")

transform_rows = rows(ROOT / "03_CAD" / "10_KINEMATIC_CARRIERS" / "B51R1_JOINT_SIDE_FRAME_TRANSFORM_REGISTER_V2.csv")
transform_failures = []
for row in transform_rows:
    if row["child_side_xyz_m"] != "0 0 0" or row["child_side_rpy_rad"] != "0 0 0":
        transform_failures.append(f"CHILD_NOT_IDENTITY:{row['joint_name']}")
    if row["origin_application_count_required"] != "EXACTLY_ONCE_ON_PARENT_SIDE":
        transform_failures.append(f"ORIGIN_COUNT:{row['joint_name']}")
result["checks"]["joint_side_transforms"] = {"rows": len(transform_rows), "failures": transform_failures}
if len(transform_rows) != 9 or transform_failures:
    failures.append("JOINT_SIDE_TRANSFORMS")

carrier_register = rows(ROOT / "04_CONFIGURATION" / "B51R1_CARRIER_REGISTER_V2.csv")
carrier_map = rows(ROOT / "03_CAD" / "10_KINEMATIC_CARRIERS" / "B51R1_CARRIER_MAP_V2.csv")
joint_register = rows(ROOT / "03_CAD" / "10_KINEMATIC_CARRIERS" / "B51R1_NATIVE_JOINT_REGISTER_V2.csv")
driver_register = rows(ROOT / "03_CAD" / "10_KINEMATIC_CARRIERS" / "B51R1_NATIVE_DRIVER_MAPPING_V2.csv")
result["checks"]["register_counts"] = {
    "carriers": len(carrier_register),
    "carrier_map": len(carrier_map),
    "joints": len(joint_register),
    "drivers": len(driver_register),
    "driver_types": {t: sum(1 for r in driver_register if r["joint_type"] == t) for t in {r["joint_type"] for r in driver_register}},
}
if [len(carrier_register), len(carrier_map), len(joint_register), len(driver_register)] != [10, 10, 9, 8]:
    failures.append("REGISTER_COUNTS")

alias = rows(CLOSURE / "B51R1_G1A_FEATURE_ALIAS_REGISTER.csv")
alias_bad = [r for r in alias if r["api_lookup_allowed"] != "FALSE" or r["duplicate_feature_allowed"] != "FALSE"]
carrier_id_to_file = {
    row["carrier_id"]: row["planned_native_part_filename"]
    for row in rows(ROOT / "04_CONFIGURATION" / "B51R1_CARRIER_REGISTER_V2.csv")
}
canonical_set = set(canonical)
alias_missing_targets = [
    f"{r['scope_carrier']}::{r['v2_native_token']}"
    for r in alias
    if r["scope_carrier"] not in carrier_id_to_file
    or (carrier_id_to_file[r["scope_carrier"]], r["v2_native_token"]) not in canonical_set
]
invalid_fixed_aliases = [
    r for r in alias if r["v2_native_token"] in {"AXIS_gripper_joint", "PLANE_ZERO_gripper_joint"}
]
contextual_link_aliases = [r for r in alias if r["legacy_token"] == "CS_LINK"]
result["checks"]["alias"] = {
    "rows": len(alias),
    "policy_bad_rows": len(alias_bad),
    "missing_canonical_targets": alias_missing_targets,
    "invalid_fixed_axis_zero_aliases": len(invalid_fixed_aliases),
    "contextual_cs_link_aliases": len(contextual_link_aliases),
}
if alias_bad or alias_missing_targets or invalid_fixed_aliases or len(contextual_link_aliases) != 10:
    failures.append("ALIAS_POLICY")

fixed_rows = [r for r in joint_register if r["type"] == "fixed"]
fixed_constraint_ok = (
    len(fixed_rows) == 1
    and fixed_rows[0].get("constraint_mode") == "THREE_GFIX_PLANE_MATES_SIDE_FRAMES_READBACK_ONLY"
    and fixed_rows[0]["native_driver"] == "NONE_FIXED_JOINT"
)
result["checks"]["fixed_joint_constraint_set"] = {"rows": len(fixed_rows), "ok": fixed_constraint_ok}
if not fixed_constraint_ok:
    failures.append("FIXED_JOINT_CONSTRAINT_SET")

tolerance = yaml.safe_load((CLOSURE / "B51R1_G1A_ACCEPTANCE_TOLERANCE_MACHINE_RATIFICATION.yaml").read_text(encoding="utf-8"))
tolerance_rows = tolerance["tolerances"]
tolerance_bad = [name for name, item in tolerance_rows.items() if item.get("conditional_authoring_only_ceiling") is None or item.get("selected_metric") is None]
fallback = tolerance["repeatability_fallback"]
required_fallback_conditions = {
    "SAME_SOLIDWORKS_REVISION_AND_IDENTICAL_API_PATH_FOR_ALL_SAMPLES",
    "NO_OUTLIER_DISCARD_OR_SAMPLE_SUBSTITUTION",
    "ORDERED_SEQUENCE_AND_LINEAR_TREND_REPORTED",
}
fallback_conditions = set(fallback["conditional_pass_requires"])
result["checks"]["tolerances"] = {
    "items": len(tolerance_rows),
    "bad_items": tolerance_bad,
    "gate_pass": fallback["gate_pass"],
    "formal_t005_release": fallback["formal_t005_release"],
    "control_model_release": fallback["control_model_release"],
    "conditional_status": fallback.get("conditional_status"),
    "required_fallback_conditions_present": sorted(required_fallback_conditions.intersection(fallback_conditions)),
}
if (
    len(tolerance_rows) != 14
    or tolerance_bad
    or fallback["gate_pass"]
    or fallback["formal_t005_release"]
    or fallback["control_model_release"]
    or fallback.get("conditional_status") != "AUTHORING_CONTINUE_WITH_MEASURED_BOUND_ONLY"
    or not required_fallback_conditions.issubset(fallback_conditions)
):
    failures.append("TOLERANCE_POLICY")

session = yaml.safe_load((ROOT / "04_CONFIGURATION" / "B51R1_AUTONOMOUS_SESSION_PLAN_V2.yaml").read_text(encoding="utf-8"))
session_by_id = {row["id"]: row for row in session["sessions"]}
session_order_ok = (
    session_by_id["S14"]["purpose"] == "G8A_RIGID_CONTINUOUS_CLEARANCE"
    and session_by_id["S15"]["purpose"] == "PRELIMINARY_STRUCTURE_MODAL_AND_UNCERTAINTY_ENVELOPES"
    and session_by_id["S16"]["purpose"] == "G8B_ROBUST_CONTINUOUS_CLEARANCE"
    and session_by_id["S17"]["auto_start_after"] == "G8B_PASS"
)
g8b_receipts = session.get("g8b_required_input_receipts", [])
result["checks"]["session_plan"] = {
    "sessions": len(session_by_id),
    "order_ok": session_order_ok,
    "s01_after": session_by_id["S01"]["auto_start_after"],
    "g8b_exact_input_receipts": len(g8b_receipts),
    "budget": session["max_visible_sessions"],
    "recovery": session["global_recovery_reserve"],
}
if (
    len(session_by_id) != 18
    or not session_order_ok
    or session_by_id["S01"]["auto_start_after"] != "G1B_PASS"
    or len(g8b_receipts) != 8
    or len({row["path"] for row in g8b_receipts}) != 8
    or any(row["required_status"] != "PASS_INPUT_BOUND_WITH_SIGN_AND_UNITS" or not row["sha256_non_null"] for row in g8b_receipts)
    or session["max_visible_sessions"] != 20
):
    failures.append("SESSION_PLAN")

gate_rows = rows(ROOT / "04_CONFIGURATION" / "B51R1_AUTONOMOUS_GATE_TRANSITION_MAP_V2.csv")
s01_gate = next(row for row in gate_rows if row["session_id"] == "S01")
s16_gate = next(row for row in gate_rows if row["session_id"] == "S16")
gate_paths_exact = all("*" not in row["required_receipt_pattern"] and "?" not in row["required_receipt_pattern"] for row in gate_rows)
try:
    s01_support = json.loads(s01_gate["required_supporting_receipts_json"])
    s16_support = json.loads(s16_gate["required_supporting_receipts_json"])
    s01_hash_fields = json.loads(s01_gate["required_embedded_hash_fields_json"])
except Exception:
    s01_support, s16_support, s01_hash_fields = [], [], []
gate_ok = (
    len(gate_rows) == 18
    and gate_paths_exact
    and s01_gate["symbolic_prerequisite"] == "G1B_PASS"
    and s01_gate["required_receipt_pattern"] == "09_DELIVERY/B51R1_AUTONOMOUS_G1A_CLOSURE_20260801/B51R1_G1B_STANDING_SESSION_ADMISSION.json"
    and s01_gate["required_status"] == "G1B_PASS_STANDING_SESSION_ADMISSION"
    and len(s01_support) == 1
    and set(s01_hash_fields) == {"g1a_receipt_sha256", "input_lock_sha256", "session_pool_ledger_sha256"}
    and len(s16_support) == 8
    and all(row["required_input_lock_sha256_match"] == "TRUE" and row["pool_entry_required"] == "TRUE" for row in gate_rows)
)
result["checks"]["gate_transition_map"] = {
    "rows": len(gate_rows),
    "exact_paths": gate_paths_exact,
    "s01_prerequisite": s01_gate["symbolic_prerequisite"],
    "s01_supporting_receipts": len(s01_support),
    "s16_supporting_receipts": len(s16_support),
    "ok": gate_ok,
}
if not gate_ok:
    failures.append("GATE_TRANSITION_MAP")

ledger = json.loads((CLOSURE / "B51R1_AUTONOMOUS_SESSION_POOL_LEDGER.json").read_text(encoding="utf-8"))
result["checks"]["session_ledger"] = {k: ledger[k] for k in ["budget", "consumed_since_activation", "remaining", "concurrent_processes_max"]}
if [ledger["budget"], ledger["consumed_since_activation"], ledger["remaining"], ledger["concurrent_processes_max"]] != [20, 0, 20, 1]:
    failures.append("SESSION_LEDGER")

dispositions = rows(CLOSURE / "B51R1_AUTONOMOUS_FINDING_DISPOSITION_REGISTER_V2.csv")
deferred = [r for r in dispositions if r["a0_a6_disposition"] == "APPROVED_DEFERRED_HOLD_REGISTERED"]
pending_quorum = [r for r in dispositions if "PENDING_FINAL_QUORUM" in r["technical_status"] or "UNTIL_FINAL_QUORUM" in r["admission_effect"]]
required_findings = {
    *{f"MRT2-G1A-{i:03d}" for i in range(1, 9)},
    *{f"RBT2-G1A-{i:03d}" for i in range(1, 5)},
    "AUT-BOUNDARY-001", "AUT-NAMING-ALIAS-001", "AUT-MANIFEST-001",
    "AUT-EVIDENCE-PATH-001", "AUT-STATUS-001",
    "MRT3-AUTH-001", "MRT3-NAME-002", "MRT3-CFG-003",
    "MRT3-TRACE-004", "MRT3-PLAN-005", "MRT3-DATUM-006",
}
finding_ids = {r["finding_id"] for r in dispositions}
result["checks"]["findings"] = {
    "rows": len(dispositions),
    "unique": len(finding_ids) == len(dispositions),
    "deferred_approved": len(deferred),
    "pending_final_quorum": len(pending_quorum),
    "required_findings_missing": sorted(required_findings.difference(finding_ids)),
}
if len(dispositions) != 62 or len(deferred) != 19 or len(finding_ids) != len(dispositions) or not required_findings.issubset(finding_ids):
    failures.append("FINDING_COUNTS")

manifest = rows(CLOSURE / "B51R1_AUTONOMOUS_EXPECTED_ARTIFACT_MANIFEST_V3.csv")
manifest_by_id = {row["artifact_id"]: row for row in manifest}
expected_manifest_counts = {
    "AUT_S03_TEN_PARTS": "10",
    "AUT_S03_TEN_RECEIPTS": "10",
    "AUT_S04_TEN_COLD_RECEIPTS": "10",
    "AUT_S05_J00_J09": "10",
    "AUT_S05_T005_A0": "1",
    "AUT_S05_T005_B0": "1",
    "AUT_S06_T005_C0": "1",
    "AUT_S12_H10_ROWS": "28",
    "AUT_S17_MASS_LEDGERS": "3",
}
s15_ids = {
    "AUT_S15_SIGNED_STRUCTURAL_DEFORMATION",
    "AUT_S15_CONTACT_PAD_COMPRESSION",
    "AUT_S15_THERMAL_DISTORTION",
    "AUT_S15_MANUFACTURING_ASSEMBLY_TOLERANCE",
    "AUT_S15_JOINT_BACKLASH",
    "AUT_S15_HARNESS_UNCERTAINTY",
    "AUT_S15_SOLAR_HDRM_FAILURE_BRANCHES",
    "AUT_S15_FULL_2P_TRAVEL",
}
manifest_count_failures = [
    artifact_id for artifact_id, expected in expected_manifest_counts.items()
    if artifact_id not in manifest_by_id or manifest_by_id[artifact_id]["expected_count"] != expected
]
manifest_type_failures = []
for row in manifest:
    suffix = Path(row["path_or_pattern"]).suffix.lower()
    allowed_types = {
        ".json": {"JSON", "JSON_PATTERN"},
        ".yaml": {"YAML", "YAML_PATTERN"},
        ".yml": {"YAML", "YAML_PATTERN"},
        ".csv": {"CSV", "CSV_PATTERN"},
    }.get(suffix)
    if allowed_types and row["artifact_type"] not in allowed_types:
        manifest_type_failures.append(
            f"{row['artifact_id']}:{row['artifact_type']}!in{sorted(allowed_types)}"
        )
current_hashed_rows = [row for row in manifest if row["current_status"] == "CURRENT_HASHED_INPUT"]
manifest_unlocked_current = [row["artifact_id"] for row in current_hashed_rows if row["path_or_pattern"] not in paths]
resolution_manifest = manifest_by_id.get("AUT_EVIDENCE_PATH_RESOLUTION", {})
manifest_ok = (
    len(manifest) >= 110
    and len(manifest_by_id) == len(manifest)
    and not manifest_count_failures
    and s15_ids.issubset(manifest_by_id)
    and all(manifest_by_id[item]["expected_count"] == "1" for item in s15_ids)
    and "AUT_S15_MARGIN_ENVELOPES" not in manifest_by_id
    and manifest_by_id["AUT_S14_G8A_PAIR_RECEIPTS"]["expected_count"] == "EXACT_COUNT_FROM_FROZEN_G8A_MANIFEST"
    and manifest_by_id["AUT_S16_G8B_PAIR_RECEIPTS"]["expected_count"] == "EXACT_COUNT_FROM_FROZEN_G8B_MANIFEST"
    and not manifest_type_failures
    and not manifest_unlocked_current
    and resolution_manifest.get("current_status") == "POST_LOCK_MACHINE_RECEIPT"
    and resolution_manifest.get("path_or_pattern") not in paths
)
result["checks"]["artifact_manifest"] = {
    "rows": len(manifest),
    "unique_ids": len(manifest_by_id) == len(manifest),
    "count_failures": manifest_count_failures,
    "s15_exact_inputs": len(s15_ids.intersection(manifest_by_id)),
    "type_failures": manifest_type_failures,
    "unlocked_current_hashed_inputs": manifest_unlocked_current,
    "evidence_resolution_status": resolution_manifest.get("current_status"),
    "ok": manifest_ok,
}
if not manifest_ok:
    failures.append("ARTIFACT_MANIFEST")

activation = json.loads((CLOSURE / "B51R1_AUTONOMOUS_STANDING_DELEGATION_RECEIPT.json").read_text(encoding="utf-8"))
directive_path = ROOT / Path(activation["directive"]["path"])
directive_text = directive_path.read_text(encoding="utf-8")
activation_ok = (
    activation["authority_type"] == "OWNER_STANDING_DELEGATION"
    and activation["human_signature_present"] is False
    and activation["non_delegable_boundary_count"] == 10
    and len(activation["non_delegable_boundaries"]) == 10
    and "DELETE_NON_TEMPORARY_ASSETS_OUTSIDE_CANDIDATE_QUARANTINE" in activation["non_delegable_boundaries"]
    and directive_path.stat().st_size == activation["directive"]["utf8_bytes"] == 207
    and sha(directive_path) == activation["directive"]["sha256"] == "BAF77DD06C7918E63BA8BCACAB06C51AD8BC143E24CA1671C082699CB5FE60A8"
    and directive_text == activation["directive"]["exact_text"]
)
result["checks"]["standing_delegation"] = {
    "boundary_count": len(activation["non_delegable_boundaries"]),
    "directive_exact_match": directive_text == activation["directive"]["exact_text"],
    "ok": activation_ok,
}
if not activation_ok:
    failures.append("STANDING_DELEGATION")

composition = json.loads((CLOSURE / "B51R1_PHASE2_CURRENT_GATE_COMPOSITION.json").read_text(encoding="utf-8"))
datum_ratification = yaml.safe_load((CLOSURE / "B51R1_G1A_DATUM_MACHINE_RATIFICATION.yaml").read_text(encoding="utf-8"))
h10_source = composition["h10"].get("source", {})
t005_source = composition["t005"].get("source", {})
historical = composition.get("protected_datum_register_historical_snapshot", {})
datum_guards = datum_ratification["s01_semantic_guards"]
composition_ok = (
    composition["h10"]["closed"] == 0
    and composition["h10"]["total"] == 28
    and composition["h10"]["unresolved"] == 28
    and [composition["t005"][key] for key in ["A", "B", "C"]] == ["NOT_RUN", "NOT_RUN", "NOT_RUN"]
    and h10_source.get("bytes") == 4592
    and h10_source.get("sha256") == "DC25010418B6A49D619C149B60BA2DB9435E5B251EC10FF163240D636C6F6440"
    and t005_source.get("bytes") == 3955
    and t005_source.get("sha256") == "8E43C9DFE82AF1EC5572E1916E7265717505688143D743C5A4466852E576B7F4"
    and historical.get("embedded_phase1_gate_sha256") == "6A41C32AABB11C2146D188350BBEBCA064C2FC55C49700FCF81309DBA4BEEAB8"
    and historical.get("current_phase1_gate_sha256") == "D0D0BEA077F4967BFDCA1091869A611D5C49C05DD4F761808693943B5B9E4FFD"
    and historical.get("protected_source_mutated") is False
    and datum_guards.get("panel_physical_contact_credit") == "NONE"
    and datum_guards.get("future_dedicated_pad_contact_model") == "DEFERRED_G7_G9"
    and datum_guards.get("panel_load_credit") == "NONE"
    and datum_guards.get("panel_attachment_credit") == "NONE"
    and "panel_contact_credit" not in datum_guards
)
result["checks"]["current_gate_composition_and_datum"] = {
    "h10_source_sha256": h10_source.get("sha256"),
    "t005_source_sha256": t005_source.get("sha256"),
    "embedded_phase1_gate_sha256": historical.get("embedded_phase1_gate_sha256"),
    "current_phase1_gate_sha256": historical.get("current_phase1_gate_sha256"),
    "panel_physical_contact_credit": datum_guards.get("panel_physical_contact_credit"),
    "ok": composition_ok,
}
if not composition_ok:
    failures.append("CURRENT_STATUS_COMPOSITION")

evidence_policy = yaml.safe_load((CLOSURE / "B51R1_G1A_EVIDENCE_PATH_POLICY.yaml").read_text(encoding="utf-8"))
evidence_receipt = json.loads((CLOSURE / "B51R1_G1A_EVIDENCE_PATH_RESOLUTION_RECEIPT.json").read_text(encoding="utf-8"))
claims = rows(CLOSURE / "B51R1_AUTONOMOUS_CLAIM_MATRIX_V2.csv")
expected_evidence_rows = []
for source_register, source_id_field, source_path_field, source_rows in [
    ("09_DELIVERY/B51R1_AUTONOMOUS_G1A_CLOSURE_20260801/B51R1_AUTONOMOUS_FINDING_DISPOSITION_REGISTER_V2.csv", "finding_id", "closure_evidence_path", dispositions),
    ("09_DELIVERY/B51R1_AUTONOMOUS_G1A_CLOSURE_20260801/B51R1_AUTONOMOUS_CLAIM_MATRIX_V2.csv", "claim_id", "evidence", claims),
]:
    for row in source_rows:
        evidence = row[source_path_field]
        if evidence not in {"", "null", "none", "NONE"}:
            expected_evidence_rows.append((source_register, row[source_id_field], evidence))
receipt_index = {
    (row["source_register"], row["source_id"], row["candidate_root_relative_path"]): row
    for row in evidence_receipt["resolved_rows"]
}
evidence_failures = []
for key in expected_evidence_rows:
    evidence = key[2]
    if Path(evidence).is_absolute() or "\\" in evidence or "/" not in evidence:
        evidence_failures.append(f"NON_ROOT_RELATIVE:{key[1]}:{evidence}")
        continue
    receipt_row = receipt_index.get(key)
    if receipt_row is None:
        evidence_failures.append(f"MISSING_RECEIPT_ROW:{key[1]}")
        continue
    target = ROOT / Path(evidence)
    if target.is_file():
        if receipt_row["resolution_state"] != "EXISTS_HASHED" or receipt_row["bytes"] != target.stat().st_size or receipt_row["sha256"] != sha(target):
            evidence_failures.append(f"STALE_HASH:{key[1]}")
    elif receipt_row["resolution_state"] != "EXPECTED_FUTURE_GATE_ARTIFACT":
        evidence_failures.append(f"UNRESOLVED:{key[1]}")
evidence_ok = (
    evidence_policy["path_base"] == "CANDIDATE_ROOT"
    and evidence_receipt["path_base"] == "CANDIDATE_ROOT"
    and evidence_receipt.get("graph_layer") == "POST_INPUT_LOCK_PRE_QUORUM"
    and evidence_receipt.get("self_in_input_lock") is False
    and "G1A_EVIDENCE_PATH_RESOLUTION" not in ids
    and evidence_receipt["unresolved_unexpected_count"] == 0
    and len(receipt_index) == len(expected_evidence_rows)
    and not evidence_failures
)
result["checks"]["evidence_paths"] = {
    "non_null_rows": len(expected_evidence_rows),
    "receipt_rows": len(receipt_index),
    "existing": evidence_receipt["resolved_existing_count"],
    "expected_future": evidence_receipt["expected_future_count"],
    "failures": evidence_failures,
    "ok": evidence_ok,
}
if not evidence_ok:
    failures.append("EVIDENCE_PATHS")

# Recursively validate every live nested path/bytes/SHA record inside locked
# JSON/YAML assets. Three protected current-status sources contain explicitly
# superseded historical nested snapshots; only those named sources are skipped.
nested_superseded_sources = {
    "02_MASTER_SKELETON/B51R1_MASTER_SKELETON_V2_DATUM_REGISTER.yaml",
    "05_H10/B51R1_H10_PHASE1_STATUS_CURRENT.json",
    "06_T005/B51R1_T005_EXECUTION_READINESS_CURRENT.json",
}
nested_reference_failures = []
nested_reference_checked = 0
nested_reference_superseded = 0


def walk_nested(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_nested(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_nested(child)


for lock_item in locked:
    source_rel = lock_item["path"]
    source_path = ROOT / Path(source_rel)
    if source_path.suffix.lower() not in {".json", ".yaml", ".yml"}:
        continue
    try:
        source_data = (
            json.loads(source_path.read_text(encoding="utf-8"))
            if source_path.suffix.lower() == ".json"
            else yaml.safe_load(source_path.read_text(encoding="utf-8"))
        )
    except Exception:
        continue
    for node in walk_nested(source_data):
        if not isinstance(node.get("path"), str) or not isinstance(node.get("sha256"), str):
            continue
        target_rel = node["path"].replace("\\", "/")
        if Path(target_rel).is_absolute() or len(node["sha256"]) != 64:
            continue
        target = ROOT / Path(target_rel)
        if not target.is_file():
            continue
        if source_rel in nested_superseded_sources:
            nested_reference_superseded += 1
            continue
        nested_reference_checked += 1
        if sha(target) != node["sha256"]:
            nested_reference_failures.append(f"SHA:{source_rel}->{target_rel}")
        if isinstance(node.get("bytes"), int) and target.stat().st_size != node["bytes"]:
            nested_reference_failures.append(f"BYTES:{source_rel}->{target_rel}")

result["checks"]["nested_live_references"] = {
    "checked": nested_reference_checked,
    "explicitly_superseded_in_protected_sources": nested_reference_superseded,
    "failures": sorted(set(nested_reference_failures)),
}
if nested_reference_failures:
    failures.append("NESTED_LIVE_REFERENCES")

lock_receipt = json.loads((CLOSURE / "B51R1_STAGE_A_LOCKFILE_QUARANTINE_RECEIPT.json").read_text(encoding="utf-8"))
stage_a = ROOT / "02_MASTER_SKELETON" / "B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT"
old_lock = ROOT / "02_MASTER_SKELETON" / "~$B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT"
quarantine = ROOT / Path(lock_receipt["quarantine"]["path"])
lock_ok = (
    not old_lock.exists()
    and quarantine.is_file()
    and quarantine.stat().st_size == 6
    and sha(quarantine) == "0D477825E5F9D305044B3EADCCAFFB403858E766BDC2E4BBD94A728DA79A4F47"
    and stage_a.stat().st_size == 511198
    and sha(stage_a) == "5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B"
)
result["checks"]["stage_a_quarantine"] = {"ok": lock_ok, "receipt_status": lock_receipt["status"]}
if not lock_ok:
    failures.append("STAGE_A_QUARANTINE")

immutable = {
    "phase2a_zip": (ROOT / "09_DELIVERY" / "B51R1_PHASE2A_NATIVE_SKELETON_CARRIER_START_PACKAGE_20260801.zip", "EE44124CC0DB1E0F6757F3662D66729B2D4CB3CF2F3391D2370CC0F8CC8D226C"),
    "s00_zip": (ROOT / "09_DELIVERY" / "B51R1_PHASE2_S00_G1_REVIEW_WORKSET_20260801.zip", "31DD09B8FA33238C963861E9049F1FCB8E460159FDC348EEEB45F99CBBE3EF6E"),
    "urdf": (ROOT / "00_BASELINE" / "AUTHORITIES" / "accepted_urdf" / "arm_b601_v1.urdf", "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"),
    "stage_a": (stage_a, "5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B"),
}
immutable_result = {name: sha(path) == expected for name, (path, expected) in immutable.items()}
result["checks"]["immutable_hashes"] = immutable_result
if not all(immutable_result.values()):
    failures.append("IMMUTABLE_HASH")

sw_processes = [p.info for p in psutil.process_iter(["pid", "name"]) if (p.info.get("name") or "").lower() == "sldworks.exe"]
result["checks"]["solidworks_processes"] = sw_processes
if sw_processes:
    failures.append("SOLIDWORKS_RUNNING")

result["overall"] = "PASS_PRE_FINAL_QUORUM_AUDIT" if not failures else "FAIL_PRE_FINAL_QUORUM_AUDIT"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps(result, ensure_ascii=False, indent=2))
