#!/usr/bin/env python3
"""Build the metadata-only ODR-60 mount/clearance/scene intake gate.

This builder opens JSON/text metadata and the accepted URDF raw bytes only.  It
does not open CAD, STEP, mesh, NPZ/NPY, run FK, evaluate a pair/edge, or search
a path.  Its purpose is to make missing execution bindings machine-visible.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[5]
REL_DIR = Path(
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
    "ODR60_OPTION_A_BINDING_INTAKE_V1"
)

URDF_AUDIT_REL = REL_DIR / "URDF_CONTENT_IDENTITY_AUDIT_V1.json"
MOUNT_REL = REL_DIR / "PROVISIONAL_MOUNT_REBIND_CANDIDATE_V1.json"
CLEARANCE_REL = REL_DIR / "CLEARANCE_POLICY_INTAKE_V1.json"
SCENE_REL = REL_DIR / "SYSTEM_SCENE_STATE_INTAKE_V1.json"
BUILDER_REL = REL_DIR / "build_binding_intake_gate.py"
TEST_REL = REL_DIR / "test_binding_intake_gate.py"
README_REL = REL_DIR / "README.md"
GATE_REL = REL_DIR / "BINDING_INTAKE_GATE_V1.json"
MANIFEST_REL = REL_DIR / "BINDING_INTAKE_SHA256_V1.csv"

REGISTRY_REL = Path(
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
    "ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/"
    "M01_SYSTEM_COLLISION_REGISTRY_V1.json"
)
PAIR_CSV_REL = REGISTRY_REL.parent / "M01_PAIR_COVERAGE_V1.csv"
LOCAL_WINDOWS_REL = REGISTRY_REL.parent / "M01_LOCAL_CONTACT_WINDOWS_SOURCE_V1.json"
SEMANTICS_REL = Path(
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
    "ODR60_OPTION_A_PREFLIGHT_V1/M01_COLLISION_SEMANTICS_DRAFT_V1.yaml"
)
PAIR_CONTRACT_REL = Path(
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
    "ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1/SYSTEM_PAIR_ORACLE_CONTRACT_V1.json"
)
MOTION_CONTRACT_REL = PAIR_CONTRACT_REL.parent / "OBJECT_MOTION_BOUND_CONTRACT_V1.json"
BINDING_GATE_REL = PAIR_CONTRACT_REL.parent / "SYSTEM_BINDING_READINESS_GATE_V1.json"
URDF_REL = Path("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf")
URDF_EQUIV_REL = Path(
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/11_validation/"
    "URDF_LINE_ENDING_HASH_EQUIVALENCE_RECEIPT.json"
)
SOURCE_MOUNT_REL = Path(
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/04_configurations/"
    "F3R2_ARM_INITIAL_POSE.yaml"
)
BRIDGE_REL = Path(
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "mpi_phys_dyn_bridge/round1_bridge/02_bridge/B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml"
)
BRIDGE_GATE_REL = Path(
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "mpi_phys_dyn_bridge/round1_bridge/08_gate/MPI_BRIDGE_GATE_V1.json"
)
BRIDGE_OWNER_REL = Path(
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/00_authority/"
    "M7_OWNER_DECISION_ODR45_TO_ODR49_MPI_CONFIRMATION_AND_TERMINAL_PATH_V1.yaml"
)
BRIDGE_CONFIRM_REL = Path(
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "mpi_phys_dyn_bridge/round1_bridge/00_authority/"
    "MPI_BRIDGE_OWNER_CONFIRMATION_ADDENDUM_V1.yaml"
)
TRAJECTORY_REL = Path(
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "ecr_b601_harness_rated_envelope/04_mission/"
    "B601_MANDATORY_MISSION_TRAJECTORY_CONTRACT_V1.yaml"
)
SOLAR_STATE_REL = Path(
    "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE/"
    "00_authority/V5_SOLAR_STATE_AUTHORITY_R2B.json"
)
SOLAR_LATCH_REL = Path(
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "ecr_solar_array_r2/SOLAR_ARRAY_R2_HDRM_LATCH_DESIGN_V1.yaml"
)
ARM_HDRM_REL = Path(
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/07_hdrm/"
    "F3R2_ARM_HDRM_DEFINITION.json"
)
GRIPPER_REL = Path(
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "ecr_gripper_velocity_unit_authority/01_interface/"
    "GRIPPER_ACTUATION_INTERFACE_CANDIDATE_V1.yaml"
)
TARGET_REL = Path("20_engineering/config/geometry/target_models_v1.yaml")
TARGET_TRANSFORM_REL = Path(
    "20_engineering/F3R2_M6_CANDIDATE_AUTHORITY_CLOSURE_V1/wp2_mass_properties/"
    "CONFIGURATION_TRANSFORM_CANDIDATES_V1.yaml"
)
M5_CONFIG_REL = Path(
    "20_engineering/F3R2_M5_PHYSICAL_GEOMETRY_AND_LOADS_CLOSURE_V1/"
    "02_configurations/M5_CONFIGURATION_GEOMETRY_CONTRACT_V1.yaml"
)
COLLISION_CONTRACT_REL = Path(
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/16_EMBODIED_MECHANICAL_CONTRACT.yaml"
)
V9F_REL = Path(
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/ROUTE_C_EXACT_SWEEP_V9F.py"
)
V9F_FALSIFIER_REL = V9F_REL.parent / "ROUTE_C_V9F_MANDATORY_M01_FALSIFIER_GATE.json"
PHYSICAL_CAPABILITY_REL = V9F_REL.parent / "ROUTE_C_PHYSICAL_CAPABILITY_REGISTRY_V2.yaml"

EXPECTED_HASHES: dict[Path, str] = {
    REGISTRY_REL: "AC975D11CC4715277E34FCFF7ABF049BC57334FD8F03AAB223BBED0877B1694F",
    PAIR_CSV_REL: "C1F64FB26D4E563EEF6BF798EE163645FE16766CC3C510552769DB7FDF97306C",
    LOCAL_WINDOWS_REL: "6B48C382D10E2C89EE56544707248B4D37DB55CB3BDABF5BAE39AF8AC470E47C",
    SEMANTICS_REL: "595900AE2EC33708F81D0154FE094E1C86F0334D226726CC43D0F62DD04B38C9",
    PAIR_CONTRACT_REL: "D8B9CEE66BBD1793732F08F8E52C070B91CC5A6FCAAE56820E09E3C13BC81417",
    MOTION_CONTRACT_REL: "CA1A741576A90301D77FD684DFA07882FB1AB88A00E927C1381D8709C715A5CD",
    BINDING_GATE_REL: "D93D9710EB1177417565B303138956CC70A41B0373A7148863CDEC6CF9877223",
    URDF_REL: "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
    URDF_EQUIV_REL: "DF8D4624B2E33E7DDC93613DE86C663AC230C7F76A06D875ED08037FFE37E7AF",
    SOURCE_MOUNT_REL: "D6E33CB5993BA056E1368F72487B4972E4316E83655FB5AF33035FCC1761AAE2",
    BRIDGE_REL: "0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C",
    BRIDGE_GATE_REL: "60911E3C88387E2ED53601F2B541649BF90D689C57C4E74225226AE6FD10C721",
    BRIDGE_OWNER_REL: "69473BC19E020C6422B23C1758CFC343874F641781C9782E982036614C0849B5",
    BRIDGE_CONFIRM_REL: "5B681AE184870EA43BACB09668617DC02D4F705117F5F18396ECCAFB7A367103",
    TRAJECTORY_REL: "C06A40DE171F0517ACB34CCC14C918A9A4252F7B55A425B2CBAC95229B44A98A",
    SOLAR_STATE_REL: "BA639C6BF4F0875B6FD9AFFF2E6CA7A5AA3BA1AF77C6BD5FEC07A8EB62D8E6D8",
    SOLAR_LATCH_REL: "BF8F76E654C56D31E2B9539B8239ED68CA0D8F513F5ECD1410AA7530ADDC06A5",
    ARM_HDRM_REL: "90E227F582A4155DD8BAC11B8EC0838EC2195F8D5A36C67475243060911435FD",
    GRIPPER_REL: "364D7F2C54B6A77CC80B105EC24F3B7DDEA5FD5648FD7F01E7A2F96BE21A5F51",
    TARGET_REL: "45666D9D37460FD825F0ED7301BF69113016689FDF00A13DFF8046358A76AE45",
    TARGET_TRANSFORM_REL: "F43D871FAA6831652441C75916B1E890D760EAE3D5781DDF3650CFB65159DE51",
    M5_CONFIG_REL: "DA18F5A6E2F553FC709E90BA1035CDD7770A6FCEECA13EDC1FDB448CAF75838D",
    COLLISION_CONTRACT_REL: "5DDA627794A4B29D087D7489BECC7A98ED632BC6EAC0413CD9F7226C03AE1E7C",
    V9F_REL: "9F26AC9A8DE5E2EEB57103F07B769EB43AC30A8FBAFD90FE8DF5D501FA8C8A7F",
    V9F_FALSIFIER_REL: "09C3199BD9824DFDBB9782C20BE200F31760F44A89EF68D16F32D0E213F191A0",
    PHYSICAL_CAPABILITY_REL: "1E70D6F95141C136480EE6F0601DA044C69437EF9AB7066B8A72E8550027CC51",
}

EXPECTED_SCENE_FIELDS = {
    "q6", "gripper_joint1_m", "gripper_joint2_m", "solar_state",
    "solar_latch_state", "arm_hdrm_state_t0_minus", "arm_hdrm_state_t0_plus",
    "target_present", "target_attached",
}
PROHIBITED_ACTION_FIELDS = {
    "pair_evaluation_authorized", "edge_evaluation_authorized",
    "path_search_authorized", "next_stage_authorized", "release_credit",
}


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json_bytes(data: bytes) -> dict[str, Any]:
    return json.loads(data.decode("utf-8"), object_pairs_hook=_reject_duplicates)


def strict_load(root: Path, rel: Path) -> dict[str, Any]:
    return strict_json_bytes((root / rel).read_bytes())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def file_record(root: Path, rel: Path, role: str) -> dict[str, Any]:
    data = (root / rel).read_bytes()
    return {"path": rel.as_posix(), "sha256": sha256_bytes(data), "bytes": len(data), "role": role}


def audit_documents(
    registry: dict[str, Any], urdf_audit: dict[str, Any], mount: dict[str, Any],
    clearance: dict[str, Any], scene: dict[str, Any], binding_gate: dict[str, Any],
    urdf_raw: bytes,
) -> list[str]:
    errors: list[str] = []
    raw_sha = sha256_bytes(urdf_raw)
    lf = urdf_raw.replace(b"\r\n", b"\n")
    lf_sha = sha256_bytes(lf)
    crlf_count = urdf_raw.count(b"\r\n")
    bare_lf = urdf_raw.count(b"\n") - crlf_count
    norm = urdf_audit.get("normalization", {})
    if raw_sha != EXPECTED_HASHES[URDF_REL] or norm.get("raw_crlf_sha256") != raw_sha:
        errors.append("URDF_RAW_DIGEST_MISMATCH")
    if lf_sha != "408147DDC9CC0BBA0FACBF864C559A54D1712262703BA41251514A4303B5A3A4" or norm.get("lf_normalized_sha256") != lf_sha:
        errors.append("URDF_LF_NORMALIZED_DIGEST_MISMATCH")
    if (crlf_count, bare_lf, len(urdf_raw), len(lf)) != (292, 0, 11321, 11029):
        errors.append("URDF_EOL_COUNT_OR_SIZE_MISMATCH")
    if norm.get("crlf_replacement_count") != 292 or urdf_audit.get("semantic_delta") is not False:
        errors.append("URDF_IDENTITY_AUDIT_SEMANTICS_MISMATCH")
    if urdf_audit.get("legacy_or_new_model_conflict") is not False:
        errors.append("FALSE_URDF_LEGACY_CONFLICT_CLAIM")

    mount_identity = mount.get("urdf_content_identity", {})
    if mount_identity.get("raw_crlf_sha256") != raw_sha or mount_identity.get("lf_normalized_sha256") != lf_sha:
        errors.append("MOUNT_URDF_IDENTITY_NOT_CROSS_BOUND")
    bridge = mount.get("physical_to_dynamics_bridge", {})
    if bridge.get("sha256") != EXPECTED_HASHES[BRIDGE_REL] or bridge.get("effective_status") != "CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE_BY_ODR45":
        errors.append("CONFIRMED_BRIDGE_NOT_CROSS_BOUND")
    execution = mount.get("execution_binding", {})
    for key in (
        "runtime_mount_numeric_spelling", "runtime_mount_numeric_spelling_policy_sha256",
        "collision_asset_to_accepted_urdf_frame_registration_sha256", "system_mount_binding_sha256",
    ):
        if execution.get(key) is not None:
            errors.append(f"UNAUTHORIZED_MOUNT_EXECUTION_VALUE::{key}")
    if mount.get("system_object_motion_certificates_emitted") != 0:
        errors.append("FALSE_SYSTEM_MOTION_CERTIFICATE_CREDIT")

    registry_scene = registry.get("scene", {})
    if registry_scene.get("binding_status") != "INCOMPLETE":
        errors.append("UPSTREAM_SCENE_NOT_INCOMPLETE")
    if set(registry_scene.get("required_bindings", [])) != EXPECTED_SCENE_FIELDS:
        errors.append("REGISTRY_SCENE_REQUIRED_FIELD_SET_MISMATCH")
    scene_fields = scene.get("required_bindings", {})
    if set(scene_fields) != EXPECTED_SCENE_FIELDS:
        errors.append("INTAKE_SCENE_REQUIRED_FIELD_SET_MISMATCH")
    for key in EXPECTED_SCENE_FIELDS:
        if scene_fields.get(key, {}).get("value") is not None:
            errors.append(f"UNAUTHORIZED_SCENE_VALUE::{key}")
    if scene.get("required_schema_extension", {}).get("solar_hdrm_state", {}).get("value") is not None:
        errors.append("UNAUTHORIZED_SOLAR_HDRM_VALUE")
    if scene.get("bound_required_binding_count") != 0 or scene.get("scene_state_sha256") is not None:
        errors.append("FALSE_SCENE_BINDING_CREDIT")
    if scene.get("scene_binding_complete") is not False:
        errors.append("FALSE_SCENE_COMPLETE_CLAIM")
    if scene.get("event_partition_required") != [
        "M01_PRE_RELEASE_CONSTANT_SCENE_EDGE", "M01_RELEASE_EVENT_CONTRACT",
        "M01_POST_RELEASE_CONSTANT_SCENE_EDGE",
    ]:
        errors.append("M01_EVENT_PARTITION_NOT_FAIL_CLOSED")
    if scene.get("canonicalization_contract", {}).get("q_must_not_be_reencoded_inside_discrete_scene_state") is not True:
        errors.append("Q_AND_DISCRETE_SCENE_NOT_SEPARATED")

    universe = clearance.get("universe", {})
    if (universe.get("object_count"), universe.get("raw_pair_count"),
            universe.get("typed_adjacent_exception_count"),
            universe.get("query_required_pair_count")) != (150, 11175, 9, 11166):
        errors.append("CLEARANCE_UNIVERSE_MISMATCH")
    if clearance.get("policy_rows") != [] or clearance.get("policy_rows_emitted") != 0:
        errors.append("UNAUTHORIZED_OR_NONEMPTY_CLEARANCE_POLICY_ROWS")
    if clearance.get("clearance_policy_sha256") is not None or clearance.get("clearance_policy_bound") is not False:
        errors.append("FALSE_CLEARANCE_POLICY_CREDIT")
    coverage = clearance.get("coverage_contract", {})
    for key in ("wildcard", "pair_class_default", "inheritance", "caller_override", "automatic_zero_fill"):
        if coverage.get(key) != "FORBIDDEN":
            errors.append(f"CLEARANCE_FALLBACK_NOT_FORBIDDEN::{key}")
    required_fields = clearance.get("required_query_policy_row_fields", [])
    if len(required_fields) != len(set(required_fields)) or "authorized_pair_min_mm" not in required_fields or "requirement_source_sha256" not in required_fields:
        errors.append("CLEARANCE_ROW_SCHEMA_INCOMPLETE_OR_DUPLICATE")

    if "URDF_CONTENT_AND_CONFIRMED_FRAME_BRIDGE_BOUND" not in binding_gate.get("verdict", ""):
        errors.append("UPSTREAM_BINDING_GATE_NOT_CORRECTED")
    upstream_ready = binding_gate.get("current_readiness", {})
    if upstream_ready.get("urdf_content_identity_bound") is not True or upstream_ready.get("physical_dynamics_bridge_bound") is not True:
        errors.append("UPSTREAM_IDENTITY_OR_BRIDGE_NOT_BOUND")
    if upstream_ready.get("execution_mount_numeric_spelling_bound") is not False or upstream_ready.get("clearance_policy_bound") is not False:
        errors.append("UPSTREAM_FAIL_CLOSED_BINDING_STATE_MISMATCH")

    for document_name, document in (("mount", mount), ("scene", scene)):
        for key in PROHIBITED_ACTION_FIELDS:
            if document.get(key) is not False:
                errors.append(f"ACTION_FIELD_NOT_FALSE::{document_name}::{key}")
    for key in ("next_stage_authorized", "release_credit"):
        if clearance.get(key) is not False or urdf_audit.get(key) is not False:
            errors.append(f"ACTION_FIELD_NOT_FALSE::intake::{key}")
    return sorted(set(errors))


def load_inputs(root: Path = ROOT) -> tuple[dict[str, Any], ...]:
    return (
        strict_load(root, REGISTRY_REL), strict_load(root, URDF_AUDIT_REL),
        strict_load(root, MOUNT_REL), strict_load(root, CLEARANCE_REL),
        strict_load(root, SCENE_REL), strict_load(root, BINDING_GATE_REL),
        (root / URDF_REL).read_bytes(),
    )


def build_gate(root: Path = ROOT) -> dict[str, Any]:
    source_pins: list[dict[str, Any]] = []
    for rel, expected in EXPECTED_HASHES.items():
        rec = file_record(root, rel, "frozen_external_metadata_or_raw_urdf_input")
        rec["expected_sha256"] = expected
        rec["match"] = rec["sha256"] == expected
        source_pins.append(rec)
    mismatch = [x["path"] for x in source_pins if not x["match"]]
    if mismatch:
        raise RuntimeError("source pin mismatch: " + ", ".join(mismatch))
    errors = audit_documents(*load_inputs(root))
    if errors:
        raise RuntimeError("binding intake audit failed: " + "; ".join(errors))
    local_pins = {
        "urdf_identity_audit": file_record(root, URDF_AUDIT_REL, "dual-EOL digest identity audit"),
        "mount_candidate": file_record(root, MOUNT_REL, "provisional mount metadata candidate"),
        "clearance_intake": file_record(root, CLEARANCE_REL, "zero-row clearance policy intake"),
        "scene_intake": file_record(root, SCENE_REL, "zero-bound-field scene intake"),
        "builder": file_record(root, BUILDER_REL, "metadata-only deterministic builder"),
        "tests": file_record(root, TEST_REL, "positive and adversarial tests"),
        "readme": file_record(root, README_REL, "scope and reproduction"),
    }
    return {
        "schema": "BINDING_INTAKE_GATE_V1",
        "generated_utc": "DETERMINISTIC_GATE_NO_WALLCLOCK",
        "authority": "INTAKE_SCHEMA_AND_HASH_CROSS_BINDING_ONLY__NO_GEOMETRY_PAIR_EDGE_OR_PATH_AUTHORITY",
        "review_status": "PENDING_OWNER_REVIEW",
        "source_pins": source_pins,
        "local_pins": local_pins,
        "checks": {
            "all_external_source_hashes_match": True,
            "strict_json_duplicate_keys_rejected": True,
            "accepted_urdf_raw_and_lf_digest_identity_proven": True,
            "legacy_urdf_conflict_claim_absent": True,
            "confirmed_physical_dynamics_bridge_cross_bound": True,
            "execution_mount_numeric_spelling_unbound_fail_closed": True,
            "collision_asset_frame_registration_unbound_fail_closed": True,
            "scene_required_field_set_exactly_nine": True,
            "scene_bound_fields_zero_of_nine": True,
            "solar_hdrm_schema_gap_registered": True,
            "m01_event_partition_required": True,
            "target_true_requires_registry_reissue": True,
            "clearance_policy_rows_zero_of_11166": True,
            "wildcard_default_inheritance_and_zero_fill_forbidden": True,
            "all_action_and_release_authorities_false": True,
            "no_geometry_pair_edge_or_path_execution": True
        },
        "read_scope": {
            "json_metadata_parsed": [
                REGISTRY_REL.as_posix(), BINDING_GATE_REL.as_posix(),
                URDF_EQUIV_REL.as_posix(), BRIDGE_GATE_REL.as_posix(),
                URDF_AUDIT_REL.as_posix(), MOUNT_REL.as_posix(),
                CLEARANCE_REL.as_posix(), SCENE_REL.as_posix()
            ],
            "text_or_byte_hash_only": [x.as_posix() for x in EXPECTED_HASHES if x not in {REGISTRY_REL, BINDING_GATE_REL, URDF_EQUIV_REL, BRIDGE_GATE_REL}],
            "urdf_operation": "RAW_SHA256_PLUS_CRLF_TO_LF_NORMALIZATION_ONLY__NO_XML_PARSE",
            "geometry_loaded": False,
            "pair_query_executed": False,
            "edge_query_executed": False,
            "path_search_executed": False
        },
        "resolved_findings": {
            "urdf_408147_vs_1bc2": "SAME_ACCEPTED_URDF__EOL_DUAL_DIGEST__NO_SEMANTIC_CONFLICT",
            "physical_vs_dynamics_mount": "UNIQUE_CONFIRMED_BRIDGE_BOUND__NO_SELECTION_OR_AVERAGING"
        },
        "current_readiness": {
            "urdf_content_identity_bound": True,
            "physical_dynamics_bridge_bound": True,
            "execution_mount_numeric_spelling_bound": False,
            "collision_asset_frame_registration_bound": False,
            "scene_required_binding_count": 9,
            "scene_bound_required_binding_count": 0,
            "scene_binding_complete": False,
            "clearance_numeric_policy_required_pair_count": 11166,
            "clearance_numeric_policy_row_count": 0,
            "clearance_policy_bound": False,
            "system_object_motion_certificate_count": 0,
            "pair_evaluation_authorized": False,
            "edge_evaluation_authorized": False,
            "path_search_authorized": False,
            "next_stage_authorized": False,
            "release_credit": False
        },
        "blockers": [
            "EXECUTION_MOUNT_NUMERIC_SPELLING_NOT_BOUND",
            "CURRENT_COLLISION_ASSET_TO_ACCEPTED_URDF_FRAME_REGISTRATION_NOT_BOUND",
            "M01_SCENE_ZERO_OF_NINE_REQUIRED_BINDINGS_BOUND",
            "M01_RELEASE_EVENT_NOT_PARTITIONED_FROM_CONSTANT_SCENE_EDGES",
            "SOLAR_HDRM_REQUIRED_FIELD_MISSING_FROM_M01_SCHEMA",
            "ARM_HDRM_STOW_SUPPORTS_AND_TARGET_ABSENT_FROM_150_OBJECT_UNIVERSE",
            "11166_EXPLICIT_NUMERIC_CLEARANCE_POLICY_ROWS_ABSENT",
            "ZERO_HASH_BOUND_SYSTEM_OBJECT_MOTION_CERTIFICATES",
            "NINE_C_SECTION_CAPSULE_HAUSDORFF_DERATES_ABSENT",
            "SYSTEM_PAIR_ORACLE_BACKEND_NOT_BOUND",
            "NO_CURRENT_PAIR_EDGE_OR_PATH_AUTHORITY"
        ],
        "next_stage_authorized": False,
        "release_credit": False,
        "verdict": "BINDING_INTAKE_SCHEMAS_PASS__URDF_IDENTITY_AND_FRAME_BRIDGE_RESOLVED__MOUNT_EXECUTION_SCENE_CLEARANCE_MOTION_CERTIFICATES_UNBOUND__PAIR_EDGE_PATH_RELEASE_HOLD"
    }


def build_manifest_bytes(root: Path, gate_bytes: bytes) -> bytes:
    rows: list[dict[str, Any]] = []
    for rel in EXPECTED_HASHES:
        rows.append(file_record(root, rel, "hash-pinned external metadata/raw-URDF input"))
    for rel, role in (
        (URDF_AUDIT_REL, "dual-EOL digest identity audit"),
        (MOUNT_REL, "provisional mount metadata candidate"),
        (CLEARANCE_REL, "zero-row clearance policy intake"),
        (SCENE_REL, "zero-bound-field scene intake"),
        (BUILDER_REL, "metadata-only deterministic builder"),
        (TEST_REL, "positive and adversarial tests"),
        (README_REL, "scope and reproduction"),
    ):
        rows.append(file_record(root, rel, role))
    rows.append({
        "path": GATE_REL.as_posix(), "sha256": sha256_bytes(gate_bytes),
        "bytes": len(gate_bytes), "role": "generated fail-closed intake gate"
    })
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=["path", "sha256", "bytes", "role"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def expected_outputs(root: Path = ROOT) -> tuple[bytes, bytes]:
    gate_bytes = canonical_bytes(build_gate(root))
    return gate_bytes, build_manifest_bytes(root, gate_bytes)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    gate_bytes, manifest_bytes = expected_outputs(ROOT)
    if args.write:
        (ROOT / GATE_REL).write_bytes(gate_bytes)
        (ROOT / MANIFEST_REL).write_bytes(manifest_bytes)
        print(f"WROTE {GATE_REL.as_posix()} {sha256_bytes(gate_bytes)}")
        print(f"WROTE {MANIFEST_REL.as_posix()} {sha256_bytes(manifest_bytes)}")
        return 0
    existing_gate = (ROOT / GATE_REL).read_bytes()
    existing_manifest = (ROOT / MANIFEST_REL).read_bytes()
    if existing_gate != gate_bytes or existing_manifest != manifest_bytes:
        print("FAIL: gate or manifest differs from deterministic rebuild")
        return 1
    print("PASS: gate and manifest byte-identical to deterministic rebuild")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
