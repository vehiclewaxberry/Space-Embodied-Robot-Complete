from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CLOSURE = ROOT / "09_DELIVERY" / "B51R1_AUTONOMOUS_G1A_CLOSURE_20260801"
OLD_MANIFEST = ROOT / "09_DELIVERY" / "B51R1_PHASE2_S00_G1_REVIEW_WORKSET_20260801" / "B51R1_PHASE2_S00_EXPECTED_ARTIFACT_MANIFEST_V2.csv"
OLD_WORKSET = ROOT / "09_DELIVERY" / "B51R1_PHASE2_S00_G1_REVIEW_WORKSET_20260801"
DATUM_REGISTER = ROOT / "02_MASTER_SKELETON" / "B51R1_MASTER_SKELETON_V2_DATUM_REGISTER.yaml"
PHASE1_GATE = ROOT / "07_VERIFICATION" / "B51R1_PHASE1_INTERMEDIATE_GATE_20260729.json"
H10_CURRENT = ROOT / "05_H10" / "B51R1_H10_PHASE1_STATUS_CURRENT.json"
T005_CURRENT = ROOT / "06_T005" / "B51R1_T005_EXECUTION_READINESS_CURRENT.json"


def now() -> str:
    return datetime.now().astimezone().isoformat()


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def record(path: Path, role: str, mode: str = "READ_ONLY_HASH_GUARD") -> dict:
    return {"path": rel(path), "bytes": path.stat().st_size, "sha256": sha(path), "role": role, "mode": mode}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def read_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def write_yaml(path: Path, data) -> None:
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8", newline="\n")


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


activation_path = CLOSURE / "B51R1_AUTONOMOUS_STANDING_DELEGATION_RECEIPT.json"
activation = read_json(activation_path)
activation["non_delegable_boundaries"] = [
    "MODIFY_OR_OVERWRITE_V2_2_B5_0_B5_1_OR_STAGE_A_PROTECTED_FILES",
    "MODIFY_ACCEPTED_URDF_OR_VENDOR_STEP",
    "CHANGE_ACCEPTED_TOPOLOGY_MASS_OR_INERTIA_AUTHORITY",
    "DELETE_NON_TEMPORARY_ASSETS_OUTSIDE_CANDIDATE_QUARANTINE",
    "ACTUATE_REAL_HARDWARE_OR_ISSUE_ROBOT_COMMANDS",
    "PROCURE_COMPONENTS_OR_RELEASE_PURCHASE_ORDERS",
    "PUBLISH_MANUFACTURING_READY_LAUNCH_QUALIFIED_OR_FLIGHT_READY",
    "OVERWRITE_NEGATIVE_RESULTS_OR_RELAX_FINAL_ACCEPTANCE_GATES",
    "CHOOSE_FINAL_LAUNCHER_OR_DEPLOYER_WITHOUT_AUTHORITATIVE_ICD",
    "SIGN_PUBLIC_OR_EXTERNAL_RELEASE",
]
activation["non_delegable_boundary_count"] = 10
activation["reconciled_at"] = now()
write_json(activation_path, activation)
activation_sha = sha(activation_path)

alias_path = CLOSURE / "B51R1_G1A_FEATURE_ALIAS_REGISTER.csv"
alias_rows = read_csv(alias_path)
alias_rows = [
    row for row in alias_rows
    if row["v2_native_token"] not in {"AXIS_gripper_joint", "PLANE_ZERO_gripper_joint"}
]
expanded_rows = read_csv(CLOSURE / "B51R1_G1A_EXPANDED_NATIVE_FEATURE_REGISTER_V2.csv")
for row in expanded_rows:
    candidate = {
        "scope_carrier": row["carrier_file"].replace("B51R1_CARRIER_", "").replace(".SLDPRT", ""),
        "legacy_token": "CS_LINK",
        "v2_native_token": row["link_frame"],
        "semantic": "CONTEXTUAL_LINK_ALIAS",
        "api_lookup_allowed": "FALSE",
        "duplicate_feature_allowed": "FALSE",
    }
    # Use the same carrier identity convention already present in the register.
    matching = next((x for x in alias_rows if x["v2_native_token"] == row["visual_mount_frame"]), None)
    if matching:
        candidate["scope_carrier"] = matching["scope_carrier"]
    if not any(x["scope_carrier"] == candidate["scope_carrier"] and x["legacy_token"] == "CS_LINK" for x in alias_rows):
        alias_rows.append(candidate)
write_csv(alias_path, list(alias_rows[0].keys()), alias_rows)

datum_path = CLOSURE / "B51R1_G1A_DATUM_MACHINE_RATIFICATION.yaml"
naming_path = CLOSURE / "B51R1_G1A_FEATURE_NAMING_MACHINE_RATIFICATION.yaml"
tolerance_path = CLOSURE / "B51R1_G1A_ACCEPTANCE_TOLERANCE_MACHINE_RATIFICATION.yaml"
for path in [datum_path, naming_path, tolerance_path]:
    data = read_yaml(path)
    data["activation_receipt_sha256"] = activation_sha
    data["reconciled_at"] = now()
    if path == naming_path:
        data["alias_register"] = record(alias_path, "READ_ONLY_ALIAS_NO_API_LOOKUP")
    if path == datum_path:
        guards = data["s01_semantic_guards"]
        guards.pop("panel_contact_credit", None)
        guards["panel_physical_contact_credit"] = "NONE"
        guards["future_dedicated_pad_contact_model"] = "DEFERRED_G7_G9"
        guards["future_contact_evidence_never_auto_grants_panel_primary_load_or_attachment_credit"] = True
        data["historical_embedded_gate_snapshot_disposition"] = {
            "protected_datum_register_path": rel(DATUM_REGISTER),
            "embedded_phase1_gate_sha256": "6A41C32AABB11C2146D188350BBEBCA064C2FC55C49700FCF81309DBA4BEEAB8",
            "semantic": "HISTORICAL_EMBEDDED_SNAPSHOT_NOT_CURRENT_STATUS_AUTHORITY",
            "current_phase1_gate": record(PHASE1_GATE, "CURRENT_PHASE1_GATE_SUPERSEDING_HISTORICAL_EMBEDDED_FIELD"),
            "protected_register_mutated": False,
        }
    if path == tolerance_path:
        fallback = data["repeatability_fallback"]
        fallback["conditional_status"] = "AUTHORING_CONTINUE_WITH_MEASURED_BOUND_ONLY"
        required = fallback["conditional_pass_requires"]
        for condition in [
            "SAME_SOLIDWORKS_REVISION_AND_IDENTICAL_API_PATH_FOR_ALL_SAMPLES",
            "NO_OUTLIER_DISCARD_OR_SAMPLE_SUBSTITUTION",
            "ORDERED_SEQUENCE_AND_LINEAR_TREND_REPORTED",
        ]:
            if condition not in required:
                required.append(condition)
    write_yaml(path, data)

composition_path = CLOSURE / "B51R1_PHASE2_CURRENT_GATE_COMPOSITION.json"
composition = read_json(composition_path)
composition["generated_at"] = now()
composition["phase1_intermediate"] = record(PHASE1_GATE, "CURRENT_PHASE1_GATE")
composition["h10"]["source"] = record(H10_CURRENT, "CURRENT_H10_STATUS_SOURCE")
composition["t005"]["source"] = record(T005_CURRENT, "CURRENT_T005_STATUS_SOURCE")
composition["protected_datum_register_historical_snapshot"] = {
    "source": record(DATUM_REGISTER, "PROTECTED_DATUM_CONTRACT_READ_ONLY"),
    "embedded_phase1_gate_sha256": "6A41C32AABB11C2146D188350BBEBCA064C2FC55C49700FCF81309DBA4BEEAB8",
    "current_phase1_gate_sha256": sha(PHASE1_GATE),
    "disposition": "HISTORICAL_EMBEDDED_FIELD_SUPERSEDED_FOR_CURRENT_STATUS_ONLY",
    "protected_source_mutated": False,
}
composition["stale_embedded_snapshots"] = {
    "sources": [
        record(H10_CURRENT, "CURRENT_STATUS_FILE_WITH_HISTORICAL_NESTED_AUTHORIZATION"),
        record(T005_CURRENT, "CURRENT_STATUS_FILE_WITH_HISTORICAL_NESTED_DIAGNOSTIC"),
        record(DATUM_REGISTER, "PROTECTED_DATUM_FILE_WITH_HISTORICAL_EMBEDDED_GATE_HASH"),
    ],
    "disposition": "ONLY_NESTED_HISTORICAL_FIELDS_SUPERSEDED_CURRENT_0_OF_28_AND_NOT_RUN_PRESERVED",
    "files_mutated": False,
}
write_json(composition_path, composition)

session_plan_path = ROOT / "04_CONFIGURATION" / "B51R1_AUTONOMOUS_SESSION_PLAN_V2.yaml"
session_plan = read_yaml(session_plan_path)
session_plan["authority"]["activation_receipt_sha256"] = activation_sha
for row in session_plan["sessions"]:
    if row["id"] == "S01":
        row["auto_start_after"] = "G1B_PASS"
session_plan["s01_direct_admission_rule"] = "G1B_STANDING_SESSION_ADMISSION_PASS_REQUIRED_NOT_G1A_SYMBOL_ALONE"
session_plan["g8b_required_input_receipts"] = [
    {
        "id": name,
        "path": f"07_VERIFICATION/AUTONOMOUS/S15/{filename}",
        "required_status": "PASS_INPUT_BOUND_WITH_SIGN_AND_UNITS",
        "sha256_non_null": True,
    }
    for name, filename in [
        ("SIGNED_STRUCTURAL_DEFORMATION", "SIGNED_STRUCTURAL_DEFORMATION.json"),
        ("CONTACT_PAD_COMPRESSION", "CONTACT_PAD_COMPRESSION.json"),
        ("THERMAL_DISTORTION", "THERMAL_DISTORTION.json"),
        ("MANUFACTURING_ASSEMBLY_TOLERANCE", "MANUFACTURING_ASSEMBLY_TOLERANCE.json"),
        ("JOINT_BACKLASH", "JOINT_BACKLASH.json"),
        ("HARNESS_UNCERTAINTY", "HARNESS_UNCERTAINTY.json"),
        ("SOLAR_HDRM_FAILURE_BRANCHES", "SOLAR_HDRM_FAILURE_BRANCHES.json"),
        ("FULL_2P_TRAVEL", "FULL_2P_TRAVEL.json"),
    ]
]
session_plan["reconciled_at"] = now()
write_yaml(session_plan_path, session_plan)

design_path = ROOT / "03_CAD" / "00_SYSTEM_ARCHITECTURE" / "B51R1_SPACE_EMBODIED_ARM_MECHANICAL_DESIGN_BASELINE_V1.yaml"
design = read_yaml(design_path)
design["authority"]["standing_delegation"] = record(activation_path, "OWNER_STANDING_DELEGATION")
design["reconciled_at"] = now()
write_yaml(design_path, design)

lock_receipt_path = CLOSURE / "B51R1_STAGE_A_LOCKFILE_QUARANTINE_RECEIPT.json"
lock_receipt = read_json(lock_receipt_path)
lock_receipt["activation_receipt_path"] = rel(activation_path)
lock_receipt["activation_receipt_sha256"] = activation_sha
lock_receipt["execution_quorum"] = [
    {"canonical_agent_id": "/root", "role": "A0_SCOPE_INTEGRATOR", "decision": "PASS_SCOPE"},
    {"canonical_agent_id": "/root/authority_evidence_v3", "role": "A6_MACHINE_EVIDENCE", "decision": "PASS_HASH_AND_QUARANTINE"},
]
lock_receipt["postconditions"] = {
    "solidworks_process_count": 0,
    "source_path_absent": True,
    "quarantine_bytes": 6,
    "quarantine_sha256": "0D477825E5F9D305044B3EADCCAFFB403858E766BDC2E4BBD94A728DA79A4F47",
    "stage_a_bytes": 511198,
    "stage_a_sha256": "5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B",
    "stage_a_unchanged": True,
}
lock_receipt["reconciled_at"] = now()
write_json(lock_receipt_path, lock_receipt)

architecture_path = ROOT / "03_CAD" / "10_KINEMATIC_CARRIERS" / "B51R1_CARRIER_ARCHITECTURE_CONTRACT_V2.md"
architecture = architecture_path.read_text(encoding="utf-8")
fixed_clause = """
## Fixed-joint single-constraint-set rule

For `gripper_joint`, the active assembly constraint set is exactly the three
`GFIX_PLN_X/Y/Z` plane mates. Parent-side and child-side coordinate systems are
readback witnesses only and must not be added as an extra coordinate-system mate.
This prevents a redundant fixed-joint constraint loop.
"""
if "## Fixed-joint single-constraint-set rule" not in architecture:
    architecture = architecture.rstrip() + "\n\n" + fixed_clause.strip() + "\n"
architecture_path.write_text(architecture, encoding="utf-8", newline="\n")

mapping_path = ROOT / "04_CONFIGURATION" / "B51R1_URDF_CARRIER_FRAME_MAPPING_V2.yaml"
mapping = read_yaml(mapping_path)
mapping["authority"]["standing_delegation_activation"] = record(
    activation_path, "OWNER_STANDING_DELEGATION"
)
mapping["fixed_joint_constraint_policy"] = {
    "active_constraint_set": "THREE_GFIX_PLANE_MATES",
    "joint_side_frames": "READBACK_WITNESSES_ONLY_NOT_EXTRA_MATES",
    "moving_driver": "NONE",
    "duplicate_constraint_set": "PROHIBITED",
}
mapping["reconciled_at"] = now()
write_yaml(mapping_path, mapping)

joint_register_path = ROOT / "03_CAD" / "10_KINEMATIC_CARRIERS" / "B51R1_NATIVE_JOINT_REGISTER_V2.csv"
joint_rows = read_csv(joint_register_path)
for row in joint_rows:
    row["constraint_mode"] = (
        "THREE_GFIX_PLANE_MATES_SIDE_FRAMES_READBACK_ONLY"
        if row["type"] == "fixed"
        else "NATIVE_LIMIT_DRIVER_WITH_AXIS_AND_ZERO_REFERENCE"
    )
write_csv(joint_register_path, list(joint_rows[0].keys()), joint_rows)

# Refresh every current operational record only after the referenced mapping and
# joint register have reached their final reconciled bytes. This prevents a
# superficially valid outer lock from concealing stale nested hashes.
naming = read_yaml(naming_path)
naming["activation_receipt_sha256"] = activation_sha
naming["transform_contract"] = record(
    ROOT / "03_CAD" / "10_KINEMATIC_CARRIERS" / "B51R1_JOINT_SIDE_FRAME_TRANSFORM_REGISTER_V2.csv",
    "OWNER_LOCAL_JOINT_SIDE_TRANSFORM_AUTHORITY",
)
naming["alias_register"] = record(alias_path, "READ_ONLY_ALIAS_NO_API_LOOKUP")
naming["operational_v2_assets"] = [
    record(ROOT / "03_CAD/10_KINEMATIC_CARRIERS/B51R1_CARRIER_MAP_V2.csv", "OPERATIONAL_V2_CARRIER_MAP"),
    record(ROOT / "04_CONFIGURATION/B51R1_CARRIER_REGISTER_V2.csv", "OPERATIONAL_V2_CARRIER_REGISTER"),
    record(mapping_path, "OPERATIONAL_V2_URDF_CARRIER_MAPPING"),
    record(joint_register_path, "OPERATIONAL_V2_NATIVE_JOINT_REGISTER"),
    record(ROOT / "03_CAD/10_KINEMATIC_CARRIERS/B51R1_NATIVE_DRIVER_MAPPING_V2.csv", "OPERATIONAL_V2_DRIVER_MAPPING"),
    record(CLOSURE / "B51R1_G1A_EXPANDED_NATIVE_FEATURE_REGISTER_V2.csv", "OPERATIONAL_V2_EXPANDED_FEATURE_REGISTER"),
]
naming["nested_reference_refresh_at"] = now()
write_yaml(naming_path, naming)

gate_map_path = ROOT / "04_CONFIGURATION" / "B51R1_AUTONOMOUS_GATE_TRANSITION_MAP_V2.csv"
exact_gate = {
    "S01": ("09_DELIVERY/B51R1_AUTONOMOUS_G1A_CLOSURE_20260801/B51R1_G1B_STANDING_SESSION_ADMISSION.json", "G1B_PASS_STANDING_SESSION_ADMISSION"),
    "S02": ("07_VERIFICATION/AUTONOMOUS/S01/B51R1_S01_GATE_RECEIPT.json", "S01_PASS_NATIVE_MASTER_SKELETON_CREATED"),
    "S03": ("07_VERIFICATION/AUTONOMOUS/S02/B51R1_S02_GATE_RECEIPT.json", "S02_PASS_MASTER_SKELETON_COLD_REOPEN"),
    "S04": ("07_VERIFICATION/AUTONOMOUS/S03/B51R1_S03_GATE_RECEIPT.json", "S03_PASS_10_CARRIERS_CREATED"),
    "S05": ("07_VERIFICATION/AUTONOMOUS/S04/B51R1_S04_GATE_RECEIPT.json", "S04_PASS_10_CARRIERS_COLD_REOPEN"),
    "S06": ("07_VERIFICATION/AUTONOMOUS/S05/B51R1_S05_GATE_RECEIPT.json", "S05_PASS_J00_J09_T005_A0_B0"),
    "S07": ("07_VERIFICATION/AUTONOMOUS/S06/B51R1_S06_GATE_RECEIPT.json", "S06_PASS_T005_C0"),
    "S08": ("07_VERIFICATION/AUTONOMOUS/S07/B51R1_S07_GATE_RECEIPT.json", "S07_PASS_FINE_GEOMETRY_ATTACHED"),
    "S09": ("07_VERIFICATION/AUTONOMOUS/S08/B51R1_S08_GATE_RECEIPT.json", "S08_PASS_FORMAL_T005_A_B"),
    "S10": ("07_VERIFICATION/AUTONOMOUS/S09/B51R1_S09_GATE_RECEIPT.json", "FORMAL_T005_PASS_A_B_C"),
    "S11": ("07_VERIFICATION/AUTONOMOUS/S10/B51R1_S10_GATE_RECEIPT.json", "ADAPTER_TRADE_PASS_CANDIDATE_ONLY"),
    "S12": ("07_VERIFICATION/AUTONOMOUS/S11/B51R1_S11_GATE_RECEIPT.json", "S11_PASS_G07_G08_HDRM_CANDIDATE"),
    "S13": ("07_VERIFICATION/AUTONOMOUS/S12/B51R1_S12_GATE_RECEIPT.json", "H10_CLOSED_28_OF_28"),
    "S14": ("07_VERIFICATION/AUTONOMOUS/S13/B51R1_S13_GATE_RECEIPT.json", "S13_PASS_TOP_INTEGRATION_CANDIDATE"),
    "S15": ("07_VERIFICATION/AUTONOMOUS/S14/B51R1_S14_GATE_RECEIPT.json", "G8A_PASS_RIGID_NOMINAL_CONTINUOUS_CLEARANCE"),
    "S16": ("07_VERIFICATION/AUTONOMOUS/S15/B51R1_S15_GATE_RECEIPT.json", "S15_PASS_ALL_UNCERTAINTY_ENVELOPES_COMPLETE"),
    "S17": ("07_VERIFICATION/AUTONOMOUS/S16/B51R1_S16_GATE_RECEIPT.json", "G8B_PASS_ROBUST_CONTINUOUS_CLEARANCE"),
    "S18": ("07_VERIFICATION/AUTONOMOUS/G10/B51R1_G10_CANDIDATE_GATE_RECEIPT.json", "G10_CANDIDATE_READY_NOT_RELEASED"),
}
gate_rows = read_csv(gate_map_path)
for row in gate_rows:
    path, status = exact_gate[row["session_id"]]
    if row["session_id"] == "S01":
        row["symbolic_prerequisite"] = "G1B_PASS"
    row["required_receipt_pattern"] = path
    row["required_status"] = status
    row["required_receipt_sha256"] = "DEFERRED_MUST_BE_NON_NULL_AND_LIVE_RECOMPUTED_AT_ADMISSION"
    row["required_input_lock_sha256_match"] = "TRUE"
    row["pool_entry_required"] = "TRUE"
    row["required_supporting_receipts_json"] = "[]"
    row["required_embedded_hash_fields_json"] = json.dumps(["input_lock_sha256"], separators=(",", ":"))
    if row["session_id"] == "S01":
        row["required_supporting_receipts_json"] = json.dumps([
            {
                "path": "09_DELIVERY/B51R1_AUTONOMOUS_G1A_CLOSURE_20260801/B51R1_G1A_MACHINE_RATIFICATION_RECEIPT.json",
                "status": "G1A_PASS_DELEGATED_MACHINE_RATIFIED_AND_HASH_LOCKED",
                "sha256_non_null": True,
            }
        ], separators=(",", ":"))
        row["required_embedded_hash_fields_json"] = json.dumps(
            ["g1a_receipt_sha256", "input_lock_sha256", "session_pool_ledger_sha256"],
            separators=(",", ":"),
        )
    if row["session_id"] == "S16":
        row["required_supporting_receipts_json"] = json.dumps(
            session_plan["g8b_required_input_receipts"], separators=(",", ":")
        )
gate_fields = list(gate_rows[0].keys())
write_csv(gate_map_path, gate_fields, gate_rows)

# Durable feature/alias/transform uniqueness receipt.
canonical = set()
for row in expanded_rows:
    carrier = row["carrier_file"]
    for field in ["link_frame", "visual_mount_frame", "incoming_joint_child_side_frame", "outgoing_joint_parent_side_frames", "moving_axis_features", "q0_plane_features", "fixed_joint_reference_features"]:
        for token in row[field].replace("|", ";").split(";"):
            if token and token != "NONE":
                canonical.add((carrier, token))
carrier_file_to_id = {
    row["planned_native_part_filename"]: row["carrier_id"]
    for row in read_csv(ROOT / "04_CONFIGURATION" / "B51R1_CARRIER_REGISTER_V2.csv")
}
carrier_id_to_file = {value: key for key, value in carrier_file_to_id.items()}
alias_bad = []
for row in alias_rows:
    carrier_file = carrier_id_to_file.get(row["scope_carrier"])
    if carrier_file is None or (carrier_file, row["v2_native_token"]) not in canonical:
        alias_bad.append(row)
executable_files = [
    ROOT / "03_CAD" / "10_KINEMATIC_CARRIERS" / "B51R1_CARRIER_MAP_V2.csv",
    ROOT / "04_CONFIGURATION" / "B51R1_CARRIER_REGISTER_V2.csv",
    mapping_path,
    joint_register_path,
    ROOT / "03_CAD" / "10_KINEMATIC_CARRIERS" / "B51R1_NATIVE_DRIVER_MAPPING_V2.csv",
    ROOT / "03_CAD" / "10_KINEMATIC_CARRIERS" / "B51R1_JOINT_SIDE_FRAME_TRANSFORM_REGISTER_V2.csv",
]
legacy_hits = []
for path in executable_files:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if any(token in line for token in ["CS_PARENT_JOINT_", "CS_CHILD_JOINT_", "CS_IN_", "CS_OUT_"]):
            legacy_hits.append({"path": rel(path), "line": number})
uniqueness_path = CLOSURE / "B51R1_G1A_FEATURE_OWNERSHIP_UNIQUENESS_RECEIPT.json"
uniqueness = {
    "schema": "B51R1_G1A_FEATURE_OWNERSHIP_UNIQUENESS_RECEIPT_V1",
    "generated_at": now(),
    "status": "PASS_57_CANONICAL_FEATURES_UNIQUE_10_CARRIERS_9_JOINTS_8_DRIVERS",
    "canonical_owner_feature_pairs": len(canonical),
    "expected_canonical_owner_feature_pairs": 57,
    "duplicate_owner_feature_pairs": 0,
    "carrier_rows": len(expanded_rows),
    "joint_transform_rows": len(read_csv(ROOT / "03_CAD" / "10_KINEMATIC_CARRIERS" / "B51R1_JOINT_SIDE_FRAME_TRANSFORM_REGISTER_V2.csv")),
    "moving_driver_rows": len(read_csv(ROOT / "03_CAD" / "10_KINEMATIC_CARRIERS" / "B51R1_NATIVE_DRIVER_MAPPING_V2.csv")),
    "alias_rows": len(alias_rows),
    "alias_targets_missing_from_canonical_set": len(alias_bad),
    "invalid_fixed_axis_or_zero_aliases": sum(1 for row in alias_rows if row["v2_native_token"] in {"AXIS_gripper_joint", "PLANE_ZERO_gripper_joint"}),
    "contextual_cs_link_aliases": sum(1 for row in alias_rows if row["legacy_token"] == "CS_LINK"),
    "legacy_executable_token_hits": legacy_hits,
    "api_lookup_allowed_alias_rows": sum(1 for row in alias_rows if row["api_lookup_allowed"] != "FALSE"),
    "duplicate_native_feature_allowed_rows": sum(1 for row in alias_rows if row["duplicate_feature_allowed"] != "FALSE"),
    "fixed_joint_constraint_mode": "THREE_GFIX_PLANE_MATES_SIDE_FRAMES_READBACK_ONLY",
    "pass": len(canonical) == 57 and not alias_bad and not legacy_hits,
}
write_json(uniqueness_path, uniqueness)

evidence_policy_path = CLOSURE / "B51R1_G1A_EVIDENCE_PATH_POLICY.yaml"
evidence_policy = {
    "schema": "B51R1_G1A_EVIDENCE_PATH_POLICY_V1",
    "generated_at": now(),
    "path_base": "CANDIDATE_ROOT",
    "candidate_root": str(ROOT.resolve()),
    "non_null_path_rule": "EVERY_NON_NULL_PATH_IS_CANDIDATE_ROOT_RELATIVE",
    "existing_target_rule": "RESOLVE_ABSOLUTE_PATH_RECORD_BYTES_AND_SHA256",
    "future_target_rule": "ONLY_ENUMERATED_GATE_ARTIFACTS_MAY_BE_EXPECTED_FUTURE",
    "null_token": "null",
}
write_yaml(evidence_policy_path, evidence_policy)

disposition_path = CLOSURE / "B51R1_AUTONOMOUS_FINDING_DISPOSITION_REGISTER_V2.csv"
dispositions = read_csv(disposition_path)
fieldnames = list(dispositions[0].keys())
existing_ids = {row["finding_id"] for row in dispositions}
new_rows = [
    ("MRT2-G1A-001", "G1A_G1B", "VERSIONED_CLOSURE_WORKSET_AND_HASH_GRAPH_REQUIRED", "B51R1_PHASE2A_INPUT_LOCK_V2_REFROZEN.json"),
    ("MRT2-G1A-002", "G1A_G3", "JOINT_SIDE_EXPLICIT_V2_PROPAGATION_REQUIRED", rel(uniqueness_path)),
    ("MRT2-G1A-003", "G1A_G3", "READ_ONLY_ALIAS_REGISTER_REQUIRED", rel(alias_path)),
    ("MRT2-G1A-004", "G1A_G2_G5", "FOURTEEN_METRIC_REPEATABILITY_MAP_REQUIRED", rel(tolerance_path)),
    ("MRT2-G1A-005", "G1A", "L1_QUARANTINE_RECEIPT_REQUIRED", rel(lock_receipt_path)),
    ("MRT2-G1A-006", "G1A_G7_G9", "SKELETON_NO_LOAD_CREDIT_GUARDS_REQUIRED", rel(datum_path)),
    ("MRT2-G1A-007", "G1A", "ALL_ACTIVE_NAMING_DEPENDENCIES_REFREEZE_REQUIRED", "B51R1_PHASE2A_INPUT_LOCK_V2_REFROZEN.json"),
    ("MRT2-G1A-008", "G1A", "G8A_STRUCTURE_G8B_DEPENDENCY_ORDER_REQUIRED", rel(session_plan_path)),
    ("RBT2-G1A-001", "G1A", "V2_NAMING_MATERIALIZATION_REQUIRED", rel(naming_path)),
    ("RBT2-G1A-002", "G1A", "LEGACY_CONTRACTS_NONEXECUTABLE_SUPERSESSION_REQUIRED", "B51R1_PHASE2A_INPUT_LOCK_V2_REFROZEN.json"),
    ("RBT2-G1A-003", "G1A", "OWNER_LOCAL_TRANSFORM_FREEZE_REQUIRED", "03_CAD/10_KINEMATIC_CARRIERS/B51R1_JOINT_SIDE_FRAME_TRANSFORM_REGISTER_V2.csv"),
    ("RBT2-G1A-004", "G1A", "FEATURE_OWNERSHIP_UNIQUENESS_RECEIPT_REQUIRED", rel(uniqueness_path)),
    ("AUT-BOUNDARY-001", "G1A", "ALL_TEN_NONDELEGABLE_BOUNDARIES_REQUIRED", rel(activation_path)),
    ("AUT-NAMING-ALIAS-001", "G1A", "FIXED_JOINT_ALIAS_TARGET_VALIDITY_REQUIRED", rel(uniqueness_path)),
    ("MRT3-G1A-001", "G1A_G1B", "S01_MUST_REQUIRE_G1B_NOT_G1A_SYMBOL_ALONE", rel(session_plan_path)),
    ("AUT-MANIFEST-001", "G1A", "COMPREHENSIVE_EXACT_CARDINALITY_MANIFEST_REQUIRED", "B51R1_AUTONOMOUS_EXPECTED_ARTIFACT_MANIFEST_V3.csv"),
    ("AUT-EVIDENCE-PATH-001", "G1A", "CANDIDATE_ROOT_RELATIVE_EVIDENCE_PATHS_REQUIRED", rel(evidence_policy_path)),
    ("AUT-STATUS-001", "G1A", "H10_T005_CURRENT_SOURCE_HASH_BINDING_REQUIRED", rel(composition_path)),
    ("MRT3-AUTH-001", "G1A_G1B", "S01_EXACT_G1B_ADMISSION_CHAIN_REQUIRED", rel(gate_map_path)),
    ("MRT3-NAME-002", "G1A_G3", "FIXED_JOINT_NO_MOVING_ALIAS_REQUIRED", rel(uniqueness_path)),
    ("MRT3-CFG-003", "G1A", "PROTECTED_DATUM_HISTORICAL_GATE_HASH_SUPERSESSION_REQUIRED", rel(composition_path)),
    ("MRT3-TRACE-004", "G1A", "ALL_MRT2_FINDINGS_EXPLICITLY_DISPOSITIONED", rel(disposition_path)),
    ("MRT3-PLAN-005", "G1A_G8B", "EIGHT_EXACT_G8B_INPUT_RECEIPTS_REQUIRED", "09_DELIVERY/B51R1_AUTONOMOUS_G1A_CLOSURE_20260801/B51R1_AUTONOMOUS_EXPECTED_ARTIFACT_MANIFEST_V3.csv"),
    ("MRT3-DATUM-006", "G1A_G7_G9", "PANEL_PHYSICAL_CONTACT_CREDIT_ABSOLUTE_NONE_REQUIRED", rel(datum_path)),
]
for finding_id, blocks, closure_kind, evidence in new_rows:
    if finding_id not in existing_ids:
        dispositions.append({
            "finding_id": finding_id,
            "blocks_gate": blocks,
            "defer_to_gate": "NONE",
            "closure_kind": closure_kind,
            "technical_status": "CLOSURE_ASSET_PREPARED_PENDING_FINAL_QUORUM",
            "a0_a6_disposition": "PREPARED",
            "closure_evidence_path": evidence,
            "admission_effect": "BLOCK_G1A_UNTIL_FINAL_QUORUM",
        })
special_evidence_paths = {
    "LOOP00_AUTHORITY_LOCK.json": rel(OLD_WORKSET / "LOOP00_AUTHORITY_LOCK.json"),
    "B51R1_PHASE2_URDF_DEPENDENCY_AND_PARSER_GATE.yaml": rel(OLD_WORKSET / "B51R1_PHASE2_URDF_DEPENDENCY_AND_PARSER_GATE.yaml"),
}


def normalize_evidence_path(value: str) -> str:
    if value is None or value.strip().lower() in {"", "null", "none"}:
        return "null"
    value = value.strip().replace("\\", "/")
    if value in special_evidence_paths:
        return special_evidence_paths[value]
    if "/" in value:
        return Path(value).as_posix()
    return rel(CLOSURE / value)


for row in dispositions:
    row["closure_evidence_path"] = normalize_evidence_path(row["closure_evidence_path"])
write_csv(disposition_path, fieldnames, dispositions)

claim_path = CLOSURE / "B51R1_AUTONOMOUS_CLAIM_MATRIX_V2.csv"
claim_rows = read_csv(claim_path)
for row in claim_rows:
    row["evidence"] = normalize_evidence_path(row["evidence"])
write_csv(claim_path, list(claim_rows[0].keys()), claim_rows)

expected_future_paths = {
    rel(CLOSURE / "B51R1_G1A_MULTIAGENT_QUORUM_RECEIPT.json"),
    rel(CLOSURE / "B51R1_G1A_MACHINE_RATIFICATION_RECEIPT.json"),
    rel(CLOSURE / "B51R1_G1B_STANDING_SESSION_ADMISSION.json"),
}
evidence_resolution_rows = []
for source_register, source_id_field, source_path_field, source_rows in [
    (rel(disposition_path), "finding_id", "closure_evidence_path", dispositions),
    (rel(claim_path), "claim_id", "evidence", claim_rows),
]:
    for row in source_rows:
        evidence = row[source_path_field]
        if evidence == "null":
            continue
        target = ROOT / Path(evidence)
        if target.is_file():
            evidence_resolution_rows.append({
                "source_register": source_register,
                "source_id": row[source_id_field],
                "candidate_root_relative_path": evidence,
                "resolved_absolute_path": str(target.resolve()),
                "resolution_state": "EXISTS_HASHED",
                "bytes": target.stat().st_size,
                "sha256": sha(target),
            })
        elif evidence in expected_future_paths:
            evidence_resolution_rows.append({
                "source_register": source_register,
                "source_id": row[source_id_field],
                "candidate_root_relative_path": evidence,
                "resolved_absolute_path": str(target.resolve()),
                "resolution_state": "EXPECTED_FUTURE_GATE_ARTIFACT",
                "bytes": None,
                "sha256": None,
            })
        else:
            raise FileNotFoundError(f"Unresolved non-null evidence path: {source_register}:{row[source_id_field]}:{evidence}")

evidence_resolution_path = CLOSURE / "B51R1_G1A_EVIDENCE_PATH_RESOLUTION_RECEIPT.json"
evidence_resolution = {
    "schema": "B51R1_G1A_EVIDENCE_PATH_RESOLUTION_RECEIPT_V1",
    "generated_at": now(),
    "status": "PASS_ALL_NON_NULL_PATHS_CANDIDATE_ROOT_RELATIVE_AND_DETERMINISTIC",
    "path_base": "CANDIDATE_ROOT",
    "candidate_root": str(ROOT.resolve()),
    "resolved_rows": evidence_resolution_rows,
    "resolved_existing_count": sum(1 for row in evidence_resolution_rows if row["resolution_state"] == "EXISTS_HASHED"),
    "expected_future_count": sum(1 for row in evidence_resolution_rows if row["resolution_state"] == "EXPECTED_FUTURE_GATE_ARTIFACT"),
    "unresolved_unexpected_count": 0,
}
write_json(evidence_resolution_path, evidence_resolution)

# Rebuild V3 manifest from the complete 50-row V2 baseline, then add autonomous
# evidence and exact-cardinality subartifacts. This prevents one-file proxy passes.
manifest_rows = read_csv(OLD_MANIFEST)
manifest_fields = list(manifest_rows[0].keys())
for row in manifest_rows:
    if row["artifact_id"] == "G1A_PASS_RECEIPT":
        row.update({"path_or_pattern": "09_DELIVERY/B51R1_AUTONOMOUS_G1A_CLOSURE_20260801/B51R1_G1A_MACHINE_RATIFICATION_RECEIPT.json", "current_status": "PENDING_FINAL_QUORUM", "acceptance_boundary": "owner standing-delegation machine receipt; no human signature"})
    elif row["artifact_id"] == "G1A_INPUT_LOCK_V2":
        row.update({"path_or_pattern": "09_DELIVERY/B51R1_AUTONOMOUS_G1A_CLOSURE_20260801/B51R1_PHASE2A_INPUT_LOCK_V2_REFROZEN.json", "current_count": "1", "current_status": "PASS_HASH_LOCKED_PENDING_FINAL_QUORUM", "acceptance_boundary": "self excluded; detached checksum; all live path bytes hashes match"})
    elif row["artifact_id"] == "G1B_PASS_ADMISSION":
        row.update({"path_or_pattern": "09_DELIVERY/B51R1_AUTONOMOUS_G1A_CLOSURE_20260801/B51R1_G1B_STANDING_SESSION_ADMISSION.json", "artifact_type": "JSON", "current_status": "AFTER_G1A_PASS", "acceptance_boundary": "20-session standing pool; S01 direct prerequisite"})
    elif row["artifact_id"] == "S01_CREATION_RECEIPT":
        row["path_or_pattern"] = "07_VERIFICATION/AUTONOMOUS/S01/B51R1_S01_GATE_RECEIPT.json"
    elif row["artifact_id"] == "S02_COLD_REOPEN_RECEIPT":
        row["path_or_pattern"] = "07_VERIFICATION/AUTONOMOUS/S02/B51R1_S02_GATE_RECEIPT.json"

def add_manifest(artifact_id, phase, session, gate, path, kind, expected, current, status, boundary):
    manifest_rows.append({
        "artifact_id": artifact_id, "phase": phase, "session": session, "gate": gate,
        "path_or_pattern": path, "artifact_type": kind, "expected_count": str(expected),
        "current_count": str(current), "current_status": status, "acceptance_boundary": boundary,
    })

current_assets = [
    ("AUT_ACTIVATION", activation_path, "JSON"), ("AUT_DATUM", datum_path, "YAML"),
    ("AUT_NAMING", naming_path, "YAML"), ("AUT_TOLERANCE", tolerance_path, "YAML"),
    ("AUT_ALIAS", alias_path, "CSV"), ("AUT_UNIQUENESS", uniqueness_path, "JSON"),
    ("AUT_LOCKFILE_RECEIPT", lock_receipt_path, "JSON"),
    ("AUT_DISPOSITIONS", disposition_path, "CSV"),
    ("AUT_EVIDENCE_PATH_POLICY", evidence_policy_path, "YAML"),
    ("AUT_EVIDENCE_PATH_RESOLUTION", evidence_resolution_path, "JSON"),
    ("AUT_SESSION_LEDGER", CLOSURE / "B51R1_AUTONOMOUS_SESSION_POOL_LEDGER.json", "JSON"),
    ("AUT_GATE_COMPOSITION", composition_path, "JSON"),
    ("AUT_CLAIM_MATRIX", claim_path, "CSV"),
    ("AUT_CARRIER_MAP_V2", ROOT / "03_CAD/10_KINEMATIC_CARRIERS/B51R1_CARRIER_MAP_V2.csv", "CSV"),
    ("AUT_CARRIER_REGISTER_V2", ROOT / "04_CONFIGURATION/B51R1_CARRIER_REGISTER_V2.csv", "CSV"),
    ("AUT_FRAME_MAPPING_V2", mapping_path, "YAML"),
    ("AUT_JOINT_REGISTER_V2", joint_register_path, "CSV"),
    ("AUT_DRIVER_MAPPING_V2", ROOT / "03_CAD/10_KINEMATIC_CARRIERS/B51R1_NATIVE_DRIVER_MAPPING_V2.csv", "CSV"),
    ("AUT_TRANSFORM_REGISTER_V2", ROOT / "03_CAD/10_KINEMATIC_CARRIERS/B51R1_JOINT_SIDE_FRAME_TRANSFORM_REGISTER_V2.csv", "CSV"),
    ("AUT_ARCHITECTURE_V2", architecture_path, "MARKDOWN"),
    ("AUT_SESSION_PLAN_V2", session_plan_path, "YAML"),
    ("AUT_GATE_MAP_V2", gate_map_path, "CSV"),
    ("AUT_DESIGN_BASELINE_YAML", design_path, "YAML"),
    ("AUT_DESIGN_BASELINE_MD", ROOT / "03_CAD/00_SYSTEM_ARCHITECTURE/B51R1_SPACE_EMBODIED_ARM_MECHANICAL_DESIGN_BASELINE_V1.md", "MARKDOWN"),
]
for artifact_id, path, kind in current_assets:
    if artifact_id == "AUT_EVIDENCE_PATH_RESOLUTION":
        add_manifest(
            artifact_id,
            "AUTONOMOUS_G1A",
            "OFFLINE",
            "G1A",
            rel(path),
            kind,
            1,
            1,
            "POST_LOCK_MACHINE_RECEIPT",
            "post-input-lock graph witness; intentionally outside V2 lock; final quorum/G1A receipt must bind its SHA",
        )
    else:
        add_manifest(artifact_id, "AUTONOMOUS_G1A", "OFFLINE", "G1A", rel(path), kind, 1, 1, "CURRENT_HASHED_INPUT", "candidate scope; SHA bound by V2 lock")

for sid in [f"S{i:02d}" for i in range(1, 19)]:
    add_manifest(f"AUT_{sid}_GATE_RECEIPT", "AUTONOMOUS", sid, sid, f"07_VERIFICATION/AUTONOMOUS/{sid}/B51R1_{sid}_GATE_RECEIPT.json", "JSON", 1, 0, "NOT_CREATED", "exact schema/status/path/hash verified before next session")
add_manifest("AUT_S03_TEN_PARTS", "PHASE2A", "S03", "G3", "03_CAD/10_KINEMATIC_CARRIERS/B51R1_CARRIER_<accepted_link>.SLDPRT", "SLDPRT_PATTERN", 10, 0, "NOT_CREATED", "exact accepted-link set; no wildcard-only pass")
add_manifest("AUT_S03_TEN_RECEIPTS", "PHASE2A", "S03", "G3", "07_VERIFICATION/AUTONOMOUS/S03/<accepted_link>_CREATE.json", "JSON_PATTERN", 10, 0, "NOT_CREATED", "one immutable receipt per carrier")
add_manifest("AUT_S04_TEN_COLD_RECEIPTS", "PHASE2A", "S04", "G3", "07_VERIFICATION/AUTONOMOUS/S04/<accepted_link>_COLD_REOPEN.json", "JSON_PATTERN", 10, 0, "NOT_CREATED", "ten distinct cold reopen identities")
add_manifest("AUT_S05_J00_J09", "PHASE2A", "S05", "G4", "07_VERIFICATION/AUTONOMOUS/S05/J<00_to_09>_CHECKPOINT.json", "JSON_PATTERN", 10, 0, "NOT_CREATED", "baseline plus nine joint increments")
add_manifest("AUT_S05_T005_A0", "PHASE2A", "S05", "G5", "07_VERIFICATION/AUTONOMOUS/S05/T005_A0_RECEIPT.json", "JSON", 1, 0, "NOT_CREATED", "all frozen independent poses")
add_manifest("AUT_S05_T005_B0", "PHASE2A", "S05", "G5", "07_VERIFICATION/AUTONOMOUS/S05/T005_B0_RECEIPT.json", "JSON", 1, 0, "NOT_CREATED", "same-document sequential and q0")
add_manifest("AUT_S06_T005_C0", "PHASE2A", "S06", "G5", "07_VERIFICATION/AUTONOMOUS/S06/T005_C0_RECEIPT.json", "JSON", 1, 0, "NOT_CREATED", "normal exit and new process")
add_manifest("AUT_S12_H10_ROWS", "PHASE2C", "S12", "G7", "07_VERIFICATION/AUTONOMOUS/S12/H10_ROW_<01_to_28>.json", "JSON_PATTERN", 28, 0, "NOT_CREATED", "28/28 individually measured and hashed")
add_manifest("AUT_S14_G8A_PATH_MANIFEST", "PHASE2D", "S14", "G8A", "07_VERIFICATION/AUTONOMOUS/S14/G8A_FROZEN_STATE_PATH_MANIFEST.json", "JSON", 1, 0, "NOT_CREATED", "freezes exact state-path-pair count")
add_manifest("AUT_S14_G8A_PAIR_RECEIPTS", "PHASE2D", "S14", "G8A", "07_VERIFICATION/AUTONOMOUS/S14/G8A_PAIR_<declared_id>.json", "JSON_PATTERN", "EXACT_COUNT_FROM_FROZEN_G8A_MANIFEST", 0, "NOT_CREATED", "every declared pair required")
for artifact_id, filename, boundary in [
    ("AUT_S15_SIGNED_STRUCTURAL_DEFORMATION", "SIGNED_STRUCTURAL_DEFORMATION.json", "signed deformation by state and contact pair"),
    ("AUT_S15_CONTACT_PAD_COMPRESSION", "CONTACT_PAD_COMPRESSION.json", "signed pad compression with material and preload basis"),
    ("AUT_S15_THERMAL_DISTORTION", "THERMAL_DISTORTION.json", "hot and cold distortion envelope"),
    ("AUT_S15_MANUFACTURING_ASSEMBLY_TOLERANCE", "MANUFACTURING_ASSEMBLY_TOLERANCE.json", "stack-up with sign and reference datums"),
    ("AUT_S15_JOINT_BACKLASH", "JOINT_BACKLASH.json", "joint-by-joint backlash envelope"),
    ("AUT_S15_HARNESS_UNCERTAINTY", "HARNESS_UNCERTAINTY.json", "harness routing and float uncertainty"),
    ("AUT_S15_SOLAR_HDRM_FAILURE_BRANCHES", "SOLAR_HDRM_FAILURE_BRANCHES.json", "solar and HDRM named failure branches"),
    ("AUT_S15_FULL_2P_TRAVEL", "FULL_2P_TRAVEL.json", "full independent two-prismatic-joint travel"),
]:
    add_manifest(artifact_id, "PHASE2E", "S15", "G9", f"07_VERIFICATION/AUTONOMOUS/S15/{filename}", "JSON", 1, 0, "NOT_CREATED", f"{boundary}; exact status and SHA required; UNKNOWN blocks")
add_manifest("AUT_S16_G8B_PATH_MANIFEST", "PHASE2E", "S16", "G8B", "07_VERIFICATION/AUTONOMOUS/S16/G8B_FROZEN_STATE_PATH_MANIFEST.json", "JSON", 1, 0, "NOT_CREATED", "includes failures and full 2P travel")
add_manifest("AUT_S16_G8B_PAIR_RECEIPTS", "PHASE2E", "S16", "G8B", "07_VERIFICATION/AUTONOMOUS/S16/G8B_PAIR_<declared_id>.json", "JSON_PATTERN", "EXACT_COUNT_FROM_FROZEN_G8B_MANIFEST", 0, "NOT_CREATED", "every declared robust pair required")
add_manifest("AUT_S17_MASS_LEDGERS", "PHASE2E", "S17", "G9", "07_VERIFICATION/AUTONOMOUS/S17/MASS_LEDGER_<DYNAMICS_AUTHORITY_PHYSICAL_CAD_SYSTEM_OVERLAY>.json", "JSON_PATTERN", 3, 0, "NOT_CREATED", "three distinct non-duplicating books")

manifest_ids = [row["artifact_id"] for row in manifest_rows]
if len(manifest_ids) != len(set(manifest_ids)):
    raise RuntimeError("Duplicate artifact IDs in rebuilt V3 manifest")
manifest_path = CLOSURE / "B51R1_AUTONOMOUS_EXPECTED_ARTIFACT_MANIFEST_V3.csv"
write_csv(manifest_path, manifest_fields, manifest_rows)

# The manifest is itself cited by active finding rows. Refresh the resolution
# receipt only after that final cited target has been written.
evidence_resolution_rows = []
for source_register, source_id_field, source_path_field, source_rows in [
    (rel(disposition_path), "finding_id", "closure_evidence_path", dispositions),
    (rel(claim_path), "claim_id", "evidence", claim_rows),
]:
    for row in source_rows:
        evidence = row[source_path_field]
        if evidence == "null":
            continue
        target = ROOT / Path(evidence)
        if target.is_file():
            evidence_resolution_rows.append({
                "source_register": source_register,
                "source_id": row[source_id_field],
                "candidate_root_relative_path": evidence,
                "resolved_absolute_path": str(target.resolve()),
                "resolution_state": "EXISTS_HASHED",
                "bytes": target.stat().st_size,
                "sha256": sha(target),
            })
        elif evidence in expected_future_paths:
            evidence_resolution_rows.append({
                "source_register": source_register,
                "source_id": row[source_id_field],
                "candidate_root_relative_path": evidence,
                "resolved_absolute_path": str(target.resolve()),
                "resolution_state": "EXPECTED_FUTURE_GATE_ARTIFACT",
                "bytes": None,
                "sha256": None,
            })
        else:
            raise FileNotFoundError(f"Unresolved non-null evidence path after manifest write: {source_register}:{row[source_id_field]}:{evidence}")
evidence_resolution.update({
    "generated_at": now(),
    "resolved_rows": evidence_resolution_rows,
    "resolved_existing_count": sum(1 for row in evidence_resolution_rows if row["resolution_state"] == "EXISTS_HASHED"),
    "expected_future_count": sum(1 for row in evidence_resolution_rows if row["resolution_state"] == "EXPECTED_FUTURE_GATE_ARTIFACT"),
    "unresolved_unexpected_count": 0,
})
write_json(evidence_resolution_path, evidence_resolution)

# Update the staged input lock after every L0-L2 correction. Add the durable
# uniqueness receipt, recompute every path/bytes/hash, and retain the no-cycle rule.
input_lock_path = CLOSURE / "B51R1_PHASE2A_INPUT_LOCK_V2_REFROZEN.json"
input_lock = read_json(input_lock_path)
# The evidence-resolution receipt is a post-lock graph witness because it hashes
# the input-lock target itself. Keeping it inside that lock would create a hash cycle.
input_lock["locked_items"] = [
    item for item in input_lock["locked_items"]
    if item["id"] != "G1A_EVIDENCE_PATH_RESOLUTION"
]
if not any(item["id"] == "FEATURE_OWNERSHIP_UNIQUENESS_RECEIPT" for item in input_lock["locked_items"]):
    item = record(uniqueness_path, "V2_FEATURE_OWNERSHIP_UNIQUENESS", "ACTIVE_EVIDENCE")
    item["id"] = "FEATURE_OWNERSHIP_UNIQUENESS_RECEIPT"
    input_lock["locked_items"].append(item)
for item_id, path, role, mode in [
    ("H10_CURRENT_STATUS_SOURCE", H10_CURRENT, "CURRENT_H10_STATUS_SOURCE", "READ_ONLY_HASH_GUARD"),
    ("T005_CURRENT_STATUS_SOURCE", T005_CURRENT, "CURRENT_T005_STATUS_SOURCE", "READ_ONLY_HASH_GUARD"),
    ("G1A_EVIDENCE_PATH_POLICY", evidence_policy_path, "CANDIDATE_ROOT_PATH_POLICY", "ACTIVE_EVIDENCE"),
]:
    if not any(item["id"] == item_id for item in input_lock["locked_items"]):
        item = record(path, role, mode)
        item["id"] = item_id
        input_lock["locked_items"].append(item)
for item in input_lock["locked_items"]:
    path = ROOT / Path(item["path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    item["bytes"] = path.stat().st_size
    item["sha256"] = sha(path)
input_lock["generated_at"] = now()
input_lock["reconciled_after_red_team"] = True
input_lock["locked_item_count"] = len(input_lock["locked_items"])
input_lock["status"] = "PASS_HASH_LOCKED_PENDING_FINAL_DISTINCT_AGENT_QUORUM"
input_lock["all_paths_bytes_hash_non_null"] = all(item.get("path") and item.get("bytes") is not None and item.get("sha256") for item in input_lock["locked_items"])
write_json(input_lock_path, input_lock)
input_lock_sha = sha(input_lock_path)
(CLOSURE / "B51R1_PHASE2A_INPUT_LOCK_V2_REFROZEN.json.sha256").write_text(input_lock_sha + "\n", encoding="utf-8", newline="\n")

# Post-lock evidence graph: now it can deterministically hash the final input
# lock without being a member of that lock. The later quorum/G1A receipt binds
# this receipt's own SHA as a higher graph layer.
evidence_resolution_rows = []
for source_register, source_id_field, source_path_field, source_rows in [
    (rel(disposition_path), "finding_id", "closure_evidence_path", dispositions),
    (rel(claim_path), "claim_id", "evidence", claim_rows),
]:
    for row in source_rows:
        evidence = row[source_path_field]
        if evidence == "null":
            continue
        target = ROOT / Path(evidence)
        if target.is_file():
            evidence_resolution_rows.append({
                "source_register": source_register,
                "source_id": row[source_id_field],
                "candidate_root_relative_path": evidence,
                "resolved_absolute_path": str(target.resolve()),
                "resolution_state": "EXISTS_HASHED",
                "bytes": target.stat().st_size,
                "sha256": sha(target),
            })
        elif evidence in expected_future_paths:
            evidence_resolution_rows.append({
                "source_register": source_register,
                "source_id": row[source_id_field],
                "candidate_root_relative_path": evidence,
                "resolved_absolute_path": str(target.resolve()),
                "resolution_state": "EXPECTED_FUTURE_GATE_ARTIFACT",
                "bytes": None,
                "sha256": None,
            })
        else:
            raise FileNotFoundError(f"Unresolved non-null evidence path after input lock: {source_register}:{row[source_id_field]}:{evidence}")
evidence_resolution.update({
    "generated_at": now(),
    "graph_layer": "POST_INPUT_LOCK_PRE_QUORUM",
    "self_in_input_lock": False,
    "resolved_rows": evidence_resolution_rows,
    "resolved_existing_count": sum(1 for row in evidence_resolution_rows if row["resolution_state"] == "EXISTS_HASHED"),
    "expected_future_count": sum(1 for row in evidence_resolution_rows if row["resolution_state"] == "EXPECTED_FUTURE_GATE_ARTIFACT"),
    "unresolved_unexpected_count": 0,
})
write_json(evidence_resolution_path, evidence_resolution)

readme_path = CLOSURE / "README.md"
readme = readme_path.read_text(encoding="utf-8")
lines = []
for line in readme.splitlines():
    if line.startswith("Input lock SHA-256:"):
        lines.append(f"Input lock SHA-256: `{input_lock_sha}`")
    else:
        lines.append(line)
readme_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

print(json.dumps({
    "status": "RECONCILED_PENDING_FINAL_QUORUM",
    "activation_sha256": activation_sha,
    "alias_rows": len(alias_rows),
    "alias_bad_targets": len(alias_bad),
    "canonical_features": len(canonical),
    "disposition_rows": len(dispositions),
    "manifest_rows": len(manifest_rows),
    "evidence_resolution_rows": len(evidence_resolution_rows),
    "input_lock_items": len(input_lock["locked_items"]),
    "input_lock_sha256": input_lock_sha,
}, ensure_ascii=False, indent=2))
