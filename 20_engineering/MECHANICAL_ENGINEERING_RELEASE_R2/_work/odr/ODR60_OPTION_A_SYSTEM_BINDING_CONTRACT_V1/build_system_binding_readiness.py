#!/usr/bin/env python3
"""Build a metadata-only ODR-60 system-binding readiness gate.

The builder never imports or opens geometry payloads and never evaluates a
collision pair, edge, or path.  It parses only contracts, registries, receipts
and frozen source/YAML text; the large pair CSV and accepted URDF are byte-hash
checked only.  The accepted URDF is additionally normalized from CRLF to LF in
memory so its two declared byte-representation digests can be cross-proved; no
XML, mesh, kinematic, or geometry semantic is evaluated.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[5]
REL_DIR = Path(
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
    "ODR60_OPTION_A_SYSTEM_BINDING_CONTRACT_V1"
)

PAIR_CONTRACT_REL = REL_DIR / "SYSTEM_PAIR_ORACLE_CONTRACT_V1.json"
MOTION_CONTRACT_REL = REL_DIR / "OBJECT_MOTION_BOUND_CONTRACT_V1.json"
README_REL = REL_DIR / "README.md"
BUILDER_REL = REL_DIR / "build_system_binding_readiness.py"
TEST_REL = REL_DIR / "test_system_binding_readiness.py"
GATE_REL = REL_DIR / "SYSTEM_BINDING_READINESS_GATE_V1.json"
MANIFEST_REL = REL_DIR / "SYSTEM_BINDING_READINESS_SHA256_V1.csv"

REGISTRY_REL = Path(
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
    "ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/"
    "M01_SYSTEM_COLLISION_REGISTRY_V1.json"
)
PAIR_CSV_REL = Path(
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/odr/"
    "ODR60_OPTION_A_COLLISION_AUTHORITY_V1/system_registry/"
    "M01_PAIR_COVERAGE_V1.csv"
)
RECEIPT_REL = Path(
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/"
    "B601_ROUTE_C_BUILD_RECEIPT_V9F.json"
)
V9F_REL = Path(
    "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/route_c/"
    "ROUTE_C_EXACT_SWEEP_V9F.py"
)
MOUNT_REL = Path(
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/"
    "04_configurations/F3R2_ARM_INITIAL_POSE.yaml"
)
URDF_REL = Path(
    "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
)
URDF_EQUIV_REL = Path(
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/11_validation/"
    "URDF_LINE_ENDING_HASH_EQUIVALENCE_RECEIPT.json"
)
NAMED_POSE_REVALIDATION_REL = Path(
    "20_engineering/F3R2_MECHANICAL_DIGITAL_PROTOTYPE_RELEASE_V1/11_validation/"
    "B601_NAMED_POSE_REVALIDATION_V1.json"
)
BRIDGE_REL = Path(
    "20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/"
    "mpi_phys_dyn_bridge/round1_bridge/02_bridge/"
    "B601_PHYSICAL_DYNAMICS_BRIDGE_V1.yaml"
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

EXPECTED_HASHES = {
    REGISTRY_REL: "AC975D11CC4715277E34FCFF7ABF049BC57334FD8F03AAB223BBED0877B1694F",
    PAIR_CSV_REL: "C1F64FB26D4E563EEF6BF798EE163645FE16766CC3C510552769DB7FDF97306C",
    RECEIPT_REL: "8B6C877AF2B2397102D87381F35BE8D78151DF1E97B57A1C45FE4C8972D153FC",
    V9F_REL: "9F26AC9A8DE5E2EEB57103F07B769EB43AC30A8FBAFD90FE8DF5D501FA8C8A7F",
    MOUNT_REL: "D6E33CB5993BA056E1368F72487B4972E4316E83655FB5AF33035FCC1761AAE2",
    URDF_REL: "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
    URDF_EQUIV_REL: "DF8D4624B2E33E7DDC93613DE86C663AC230C7F76A06D875ED08037FFE37E7AF",
    NAMED_POSE_REVALIDATION_REL: "68D0356F889E5888399631E6C735D404140AC5933B7FA172AB1F9E26BA26B844",
    BRIDGE_REL: "0ACEB659284CAB862BA65228C5C2DF4BEB06D9EE05B5E2F0B2B5CB38402BF72C",
    BRIDGE_GATE_REL: "60911E3C88387E2ED53601F2B541649BF90D689C57C4E74225226AE6FD10C721",
    BRIDGE_OWNER_REL: "69473BC19E020C6422B23C1758CFC343874F641781C9782E982036614C0849B5",
    BRIDGE_CONFIRM_REL: "5B681AE184870EA43BACB09668617DC02D4F705117F5F18396ECCAFB7A367103",
}
ACCEPTED_URDF_LF_SHA = "408147DDC9CC0BBA0FACBF864C559A54D1712262703BA41251514A4303B5A3A4"
ACCEPTED_URDF_SHA = EXPECTED_HASHES[URDF_REL]

EXPECTED_J3_NAMES = {
    "RC-CAR-J3-CARRIAGE",
    "RC-CLP-J3-MOV",
    *(f"RC-CHN-E210-LINK-{i:02d}" for i in range(6)),
}
J4_CLASS_GAIN = {
    "ONE_THIRD_TRAVEL": 1.0 / 3.0,
    "TWO_THIRDS_TRAVEL": 2.0 / 3.0,
    "FULL_TRAVEL": 1.0,
}
EXPECTED_FOLLOWER_NAMES = {
    "RC-CAR-J4-FOLLOWER-TROLLEY",
    "RC-CLP-J4-FOLLOWER",
}
PHASE1_FIXED_IDS = {
    "A::base_link",
    "F::LOAD_BRIDGE",
    "F::M3R_STAGE_A",
    "F::M3R_STAGE_B",
}

PROHIBITED_PAYLOAD_SUFFIXES = {
    ".step", ".stp", ".fcstd", ".stl", ".ply", ".obj", ".npy", ".npz"
}


def canonical_bytes(obj: Any) -> bytes:
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def lf_normalized_bytes(data: bytes) -> bytes:
    """Apply the declared representation-only CRLF-to-LF normalization."""
    return data.replace(b"\r\n", b"\n")


def file_record(root: Path, rel: Path, role: str) -> dict[str, Any]:
    path = root / rel
    data = path.read_bytes()
    return {
        "path": rel.as_posix(),
        "sha256": sha256_bytes(data),
        "bytes": len(data),
        "role": role,
    }


def load_json(root: Path, rel: Path) -> dict[str, Any]:
    return json.loads((root / rel).read_text(encoding="utf-8"))


def extract_mount_embedded_urdf_sha(text: str) -> str | None:
    match = re.search(
        r"kinematics_authority:\s*.*?\bsha256:\s*([0-9A-Fa-f]{64})",
        text,
        flags=re.DOTALL,
    )
    return match.group(1).upper() if match else None


def extract_j3_names_from_frozen_source(text: str) -> set[str]:
    """Statically recover the exact frozen V9F J3 list without execution."""
    if "J3_CARRIAGE_PARTS = frozenset" not in text:
        return set()
    explicit = set(re.findall(r'"(RC-(?:CAR-J3-CARRIAGE|CLP-J3-MOV))"', text))
    range_match = re.search(
        r'\["RC-CHN-E210-LINK-%02d"\s*%\s*i\s+for\s+i\s+in\s+range\((\d+)\)\]',
        text,
    )
    count = int(range_match.group(1)) if range_match else 0
    return explicit | {f"RC-CHN-E210-LINK-{i:02d}" for i in range(count)}


def _canonical_pair(pair: list[str] | tuple[str, str]) -> tuple[str, str]:
    if len(pair) != 2 or pair[0] == pair[1]:
        raise ValueError(f"invalid pair: {pair!r}")
    return tuple(sorted((str(pair[0]), str(pair[1]))))


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _same_binary64(left: Any, right: Any) -> bool:
    return _finite_number(left) and _finite_number(right) and float(left).hex() == float(right).hex()


def validate_geometric_numeric_record(record: dict[str, Any]) -> list[str]:
    """Validate only the numeric/shape firewall of a synthetic pair record.

    This is not a geometry oracle and grants no pair, edge, path or release
    authority.  It exists so the frozen contract has executable negative tests
    for threshold, derating, interval and comparison-set bypasses.
    """
    errors: list[str] = []

    policy_hash = record.get("clearance_policy_sha256")
    if not isinstance(policy_hash, str) or re.fullmatch(r"[0-9A-F]{64}", policy_hash) is None:
        errors.append("CLEARANCE_POLICY_HASH_INVALID")

    authorized_min = record.get("authorized_pair_min_mm")
    required = record.get("required_clearance_mm")
    if not _finite_number(authorized_min) or float(authorized_min) < 0.0:
        errors.append("AUTHORIZED_PAIR_MIN_INVALID")
    if not _finite_number(required) or float(required) < 0.0:
        errors.append("REQUIRED_CLEARANCE_INVALID")
    if _finite_number(authorized_min) and _finite_number(required):
        if float(required) < float(authorized_min):
            errors.append("REQUIRED_CLEARANCE_BELOW_POLICY")

    status = record.get("status")
    if status not in {"SAFE", "UNSAFE", "UNKNOWN", "FAIL"}:
        errors.append("GEOMETRIC_STATUS_INVALID")
        return errors

    complete_status = status in {"SAFE", "UNSAFE"}
    if complete_status and record.get("complete") is not True:
        errors.append("COMPLETE_RESULT_FLAG_NOT_TRUE")
    if complete_status and record.get("finite") is not True:
        errors.append("FINITE_RESULT_FLAG_NOT_TRUE")

    if complete_status:
        for field in (
            "raw_backend_separation_mm",
            "object_a_hausdorff_derate_mm",
            "object_b_hausdorff_derate_mm",
            "backend_numeric_derate_mm",
        ):
            value = record.get(field)
            if not _finite_number(value):
                errors.append(f"{field.upper()}_NONFINITE")
            elif float(value) < 0.0:
                errors.append(f"{field.upper()}_NEGATIVE")

    lower = record.get("certified_separation_lower_bound_mm")
    upper = record.get("certified_separation_upper_bound_mm")
    margin_lower = record.get("certified_margin_lower_bound_mm")
    margin_upper = record.get("certified_margin_upper_bound_mm")

    if lower is not None and not _finite_number(lower):
        errors.append("CERTIFIED_LOWER_BOUND_NONFINITE")
    if upper is not None and not _finite_number(upper):
        errors.append("CERTIFIED_UPPER_BOUND_NONFINITE")
    if _finite_number(upper) and float(upper) < 0.0:
        errors.append("CERTIFIED_UPPER_BOUND_NEGATIVE")
    if _finite_number(lower) and _finite_number(upper) and float(lower) > float(upper):
        errors.append("CERTIFIED_INTERVAL_INVERTED")

    raw = record.get("raw_backend_separation_mm")
    debit_a = record.get("object_a_hausdorff_derate_mm")
    debit_b = record.get("object_b_hausdorff_derate_mm")
    debit_backend = record.get("backend_numeric_derate_mm")
    if complete_status and all(
        _finite_number(value) for value in (raw, debit_a, debit_b, debit_backend)
    ):
        expected_lower = ((float(raw) - float(debit_a)) - float(debit_b)) - float(debit_backend)
        if not _same_binary64(lower, expected_lower):
            errors.append("CERTIFIED_LOWER_BOUND_FORMULA_MISMATCH")

    if _finite_number(upper):
        upper_evidence = record.get("certified_upper_bound_evidence_sha256")
        if not isinstance(upper_evidence, str) or re.fullmatch(
            r"[0-9A-F]{64}", upper_evidence
        ) is None:
            errors.append("CERTIFIED_UPPER_BOUND_EVIDENCE_INVALID")

    if _finite_number(required) and _finite_number(lower):
        expected = float(lower) - float(required)
        if not _same_binary64(margin_lower, expected):
            errors.append("LOWER_MARGIN_INCONSISTENT")
    if _finite_number(required) and _finite_number(upper):
        expected = float(upper) - float(required)
        if not _same_binary64(margin_upper, expected):
            errors.append("UPPER_MARGIN_INCONSISTENT")

    if complete_status:
        count = record.get("comparison_set_size")
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            errors.append("COMPARISON_SET_SIZE_NOT_POSITIVE_INTEGER")
        for field in ("geometry_a_pose_S_row_major_binary64", "geometry_b_pose_S_row_major_binary64"):
            value = record.get(field)
            if not isinstance(value, list) or len(value) != 16 or not all(_finite_number(x) for x in value):
                errors.append(f"{field.upper()}_INVALID")
        for field in ("witness_point_a_S_mm", "witness_point_b_S_mm"):
            value = record.get(field)
            if value is not None and (
                not isinstance(value, list)
                or len(value) != 3
                or not all(_finite_number(x) for x in value)
            ):
                errors.append(f"{field.upper()}_INVALID")

    intersection = record.get("intersection_or_contact_certified")
    if not isinstance(intersection, bool):
        errors.append("INTERSECTION_CERTIFICATION_FLAG_INVALID")
    if intersection is True and _finite_number(upper) and float(upper) != 0.0:
        errors.append("INTERSECTION_UPPER_BOUND_NOT_CANONICAL_ZERO")

    if status == "SAFE":
        if not _finite_number(margin_lower) or float(margin_lower) <= 0.0:
            errors.append("SAFE_WITHOUT_POSITIVE_CERTIFIED_LOWER_MARGIN")
        if intersection is True:
            errors.append("SAFE_WITH_INTERSECTION_WITNESS")
    elif status == "UNSAFE":
        upper_proves = _finite_number(margin_upper) and float(margin_upper) <= 0.0
        witness_hash = record.get("unsafe_witness_authority_sha256")
        witness_proves = (
            intersection is True
            and isinstance(witness_hash, str)
            and re.fullmatch(r"[0-9A-F]{64}", witness_hash) is not None
        )
        if not upper_proves and not witness_proves:
            errors.append("UNSAFE_WITHOUT_CERTIFIED_UPPER_MARGIN_OR_WITNESS")

    return errors


def audit_state(
    registry: dict[str, Any],
    receipt: dict[str, Any],
    exact_source: str,
    pair_contract: dict[str, Any],
    motion_contract: dict[str, Any],
    embedded_mount_urdf_sha: str | None,
    urdf_raw_bytes: bytes,
    urdf_equivalence_receipt: dict[str, Any],
    bridge_gate: dict[str, Any],
    bridge_owner_text: str,
    bridge_confirmation_text: str,
) -> dict[str, Any]:
    """Pure metadata audit, exposed for positive and adversarial tests."""
    errors: list[str] = []
    objects = registry.get("objects", [])
    object_ids = [str(o.get("object_id")) for o in objects]
    object_set = set(object_ids)
    if len(object_ids) != len(object_set):
        errors.append("DUPLICATE_OBJECT_ID")
    categories: dict[str, set[str]] = {}
    for obj in objects:
        categories.setdefault(str(obj.get("category")), set()).add(str(obj.get("object_id")))
    expected_category_counts = {"A": 10, "C": 9, "F": 4, "R": 121, "S": 6}
    actual_category_counts = {key: len(categories.get(key, set())) for key in expected_category_counts}
    if actual_category_counts != expected_category_counts:
        errors.append("CATEGORY_COUNTS_NOT_10_9_4_121_6")
    if len(object_set) != 150:
        errors.append("OBJECT_COUNT_NOT_150")

    raw_pair_count = math.comb(len(object_set), 2) if len(object_set) >= 2 else 0
    exceptions: set[tuple[str, str]] = set()
    for row in registry.get("active_pair_exceptions", []):
        try:
            pair = _canonical_pair(row.get("canonical_pair", []))
        except ValueError:
            errors.append("MALFORMED_EXCEPTION_PAIR")
            continue
        if row.get("mode") != "ADJACENT_JOINT":
            errors.append("NON_ADJACENT_OR_WILDCARD_EXCEPTION")
        if not set(pair) <= object_set:
            errors.append("EXCEPTION_REFERENCES_UNKNOWN_OBJECT")
        if pair in exceptions:
            errors.append("DUPLICATE_EXCEPTION")
        exceptions.add(pair)
    if len(exceptions) != 9:
        errors.append("EXCEPTION_COUNT_NOT_9")
    query_required = raw_pair_count - len(exceptions)

    c_ids = categories.get("C", set())
    non_c_ids = object_set - c_ids
    non_c_non_exception = math.comb(len(non_c_ids), 2) - sum(
        1 for p in exceptions if set(p) <= non_c_ids
    )
    c_related = raw_pair_count - math.comb(len(non_c_ids), 2)
    if (non_c_non_exception, c_related) != (9861, 1305):
        errors.append("NON_C_OR_C_RELATED_PAIR_COUNTS_MISMATCH")

    phase1 = set(PHASE1_FIXED_IDS) | categories.get("S", set()) | categories.get("R", set())
    if len(phase1) != 131 or not phase1 <= object_set:
        errors.append("PHASE1_OBJECT_SET_NOT_131_OR_NOT_SUBSET")
    phase1_exceptions = {p for p in exceptions if set(p) <= phase1}
    if phase1_exceptions:
        errors.append("PHASE1_MUST_CONTAIN_ZERO_EXCEPTIONS")
    phase1_pairs = math.comb(len(phase1), 2) if len(phase1) >= 2 else 0

    phase3 = phase1 | c_ids
    c_add_pairs = math.comb(len(phase3), 2) - phase1_pairs
    remaining = object_set - phase3
    expected_remaining = (categories.get("A", set()) - {"A::base_link"}) | {"F::BUS"}
    if remaining != expected_remaining or len(remaining) != 10:
        errors.append("PHASE4_REMAINING_OBJECT_ID_SET_MISMATCH")
    remaining_raw = raw_pair_count - math.comb(len(phase3), 2)
    remaining_exceptions = {p for p in exceptions if set(p) & remaining}
    remaining_required = remaining_raw - len(remaining_exceptions)
    if (phase1_pairs, c_add_pairs, math.comb(len(phase3), 2), remaining_raw,
            len(remaining_exceptions), remaining_required) != (8515, 1215, 9730, 1445, 9, 1436):
        errors.append("FOUR_PHASE_PAIR_ARITHMETIC_MISMATCH")

    j3_names = extract_j3_names_from_frozen_source(exact_source)
    if j3_names != EXPECTED_J3_NAMES:
        errors.append("FROZEN_V9F_J3_LIST_MISMATCH")
    j3_ids = {f"R::{name}" for name in j3_names}
    if not j3_ids <= object_set:
        errors.append("J3_OBJECT_NOT_IN_REGISTRY")

    receipt_parts = receipt.get("parts", [])
    receipt_names = [str(p.get("name")) for p in receipt_parts]
    if len(receipt_names) != len(set(receipt_names)):
        errors.append("DUPLICATE_RECEIPT_PART_NAME")
    j4_map = {
        f"R::{p['name']}": J4_CLASS_GAIN[str(p.get("motion_class"))]
        for p in receipt_parts
        if p.get("motion_class") in J4_CLASS_GAIN
    }
    if len(j4_map) != 9 or not set(j4_map) <= object_set:
        errors.append("J4_TRAVEL_OBJECT_SET_NOT_9_OR_NOT_IN_REGISTRY")
    follower_names = {
        str(p.get("name")) for p in receipt_parts
        if p.get("motion_class") == "FOLLOWER_LINK4"
    }
    if follower_names != EXPECTED_FOLLOWER_NAMES:
        errors.append("FOLLOWER_LINK4_SET_MISMATCH")

    overlap = (j3_ids & set(j4_map)) | (j3_ids & c_ids) | (set(j4_map) & c_ids)
    if overlap:
        errors.append("MOTION_CLASS_OVERLAP")
    direct_ids = object_set - j3_ids - set(j4_map) - c_ids
    if len(direct_ids) != 124:
        errors.append("DIRECT_MOTION_CLASS_COUNT_NOT_124")
    if not {f"R::{name}" for name in follower_names} <= direct_ids:
        errors.append("FOLLOWER_LINK4_NOT_DIRECT_CANDIDATE")
    classified = direct_ids | j3_ids | set(j4_map) | c_ids
    if classified != object_set:
        errors.append("MOTION_CLASS_UNION_NOT_OBJECT_UNIVERSE")

    contract_j3 = set(
        motion_contract.get("motion_classes", {})
        .get("J3_HIDDEN_TRANSLATION", {}).get("object_ids", [])
    )
    contract_j4 = set(
        motion_contract.get("motion_classes", {})
        .get("J4_TRAVEL_TRANSLATION", {}).get("object_motion_gain", {})
    )
    contract_c = set(
        motion_contract.get("motion_classes", {})
        .get("C_SECTION_CAPSULE", {}).get("object_ids", [])
    )
    if contract_j3 != j3_ids:
        errors.append("MOTION_CONTRACT_J3_SET_MISMATCH")
    if contract_j4 != set(j4_map):
        errors.append("MOTION_CONTRACT_J4_SET_MISMATCH")
    if contract_c != c_ids:
        errors.append("MOTION_CONTRACT_C_SET_MISMATCH")
    for oid, gain in j4_map.items():
        contract_gain = (
            motion_contract["motion_classes"]["J4_TRAVEL_TRANSLATION"]
            ["object_motion_gain"].get(oid)
        )
        if contract_gain is None or abs(float(contract_gain) - gain) > 1e-15:
            errors.append(f"J4_GAIN_MISMATCH::{oid}")

    universe = pair_contract.get("universe", {})
    if (
        universe.get("raw_unordered_pair_count") != 11175
        or universe.get("active_exception_count") != 9
        or universe.get("query_required_pair_count") != 11166
        or universe.get("non_c_non_exception_pair_count") != 9861
        or universe.get("c_related_pair_count") != 1305
    ):
        errors.append("PAIR_CONTRACT_COUNT_MISMATCH")
    phases = pair_contract.get("four_phase_planning_coverage", [])
    if len(phases) != 4:
        errors.append("PAIR_CONTRACT_NOT_FOUR_PHASE")

    expected_pair_readiness = {
        "planned_coverage_only": True,
        "pair_oracle_implemented_and_bound": False,
        "pair_queries_executed": 0,
        "system_safe_pairs_certified": 0,
        "system_collision_pass": False,
        "edge_evaluation_authorized": False,
        "path_search_authorized": False,
        "release_credit": False,
    }
    pair_readiness = pair_contract.get("current_readiness", {})
    for key, expected in expected_pair_readiness.items():
        if pair_readiness.get(key) != expected:
            errors.append(f"PAIR_CONTRACT_READINESS_MISMATCH::{key}")

    expected_motion_readiness = {
        "classified_object_count": 150,
        "direct_rigid_fk_candidate_count": 124,
        "j3_hidden_translation_count": 8,
        "j4_travel_translation_count": 9,
        "c_section_capsule_count": 9,
        "urdf_content_identity_bound": True,
        "physical_dynamics_bridge_bound": True,
        "execution_mount_numeric_spelling_bound": False,
        "collision_asset_frame_registration_bound": False,
        "system_certified_object_motion_bound_count": 0,
        "system_motion_bound_complete": False,
        "continuous_edge_certified_count": 0,
        "pair_evaluation_authorized": False,
        "edge_evaluation_authorized": False,
        "path_search_authorized": False,
        "release_credit": False,
    }
    motion_readiness = motion_contract.get("current_readiness", {})
    for key, expected in expected_motion_readiness.items():
        if motion_readiness.get(key) != expected:
            errors.append(f"MOTION_CONTRACT_READINESS_MISMATCH::{key}")

    def check_contract_pin(
        container: dict[str, Any], key: str, rel: Path, expected_sha: str, prefix: str
    ) -> None:
        pin = container.get(key, {})
        if pin.get("path") != rel.as_posix() or pin.get("sha256") != expected_sha:
            errors.append(f"{prefix}_SOURCE_PIN_MISMATCH::{key}")

    pair_pins = pair_contract.get("source_pins", {})
    check_contract_pin(
        pair_pins, "system_registry", REGISTRY_REL, EXPECTED_HASHES[REGISTRY_REL],
        "PAIR_CONTRACT",
    )
    check_contract_pin(
        pair_pins, "enumerated_pair_coverage", PAIR_CSV_REL,
        EXPECTED_HASHES[PAIR_CSV_REL], "PAIR_CONTRACT",
    )

    motion_pins = motion_contract.get("source_pins", {})
    for key, rel in (
        ("system_registry", REGISTRY_REL),
        ("v9f_build_receipt", RECEIPT_REL),
        ("v9f_exact_evaluator", V9F_REL),
        ("physical_mount_pose_yaml", MOUNT_REL),
        ("accepted_urdf", URDF_REL),
        ("urdf_line_ending_equivalence_receipt", URDF_EQUIV_REL),
        ("named_pose_revalidation", NAMED_POSE_REVALIDATION_REL),
        ("confirmed_physical_dynamics_bridge", BRIDGE_REL),
        ("physical_dynamics_bridge_gate", BRIDGE_GATE_REL),
        ("bridge_owner_decision", BRIDGE_OWNER_REL),
        ("bridge_owner_confirmation_addendum", BRIDGE_CONFIRM_REL),
    ):
        check_contract_pin(
            motion_pins, key, rel, EXPECTED_HASHES[rel], "MOTION_CONTRACT"
        )
    if (
        motion_pins.get("physical_mount_pose_yaml", {})
        .get("embedded_urdf_sha256") != ACCEPTED_URDF_LF_SHA
    ):
        errors.append("MOTION_CONTRACT_EMBEDDED_LF_NORMALIZED_URDF_PIN_MISMATCH")

    raw_sha = sha256_bytes(urdf_raw_bytes)
    normalized = lf_normalized_bytes(urdf_raw_bytes)
    normalized_sha = sha256_bytes(normalized)
    crlf_count = urdf_raw_bytes.count(b"\r\n")
    bare_lf_count = urdf_raw_bytes.count(b"\n") - crlf_count
    urdf_equivalent = (
        raw_sha == ACCEPTED_URDF_SHA
        and normalized_sha == ACCEPTED_URDF_LF_SHA
        and embedded_mount_urdf_sha == ACCEPTED_URDF_LF_SHA
        and urdf_equivalence_receipt.get("raw_disk_sha256") == ACCEPTED_URDF_SHA
        and urdf_equivalence_receipt.get("lf_normalized_sha256") == ACCEPTED_URDF_LF_SHA
        and urdf_equivalence_receipt.get("crlf_sequence_count") == crlf_count
        and urdf_equivalence_receipt.get("normalization_changes_model_content") is False
        and urdf_equivalence_receipt.get("status")
        == "PASS_SAME_URDF_TEXT_UNDER_DECLARED_LINE_ENDING_NORMALIZATION"
    )
    if not urdf_equivalent:
        errors.append("ACCEPTED_URDF_DUAL_DIGEST_EQUIVALENCE_NOT_PROVEN")
    if bare_lf_count != 0:
        errors.append("ACCEPTED_URDF_HAS_UNDECLARED_BARE_LF")

    bridge_confirmed = (
        bridge_gate.get("mpi_gate") == "PASS"
        and bridge_gate.get("next_stage_authorized") is False
        and bridge_gate.get("release_credit") is False
        and "CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE" in bridge_owner_text
        and EXPECTED_HASHES[BRIDGE_REL] in bridge_owner_text
        and "CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE" in bridge_confirmation_text
        and EXPECTED_HASHES[BRIDGE_REL] in bridge_confirmation_text
    )
    if not bridge_confirmed:
        errors.append("ODR45_CONFIRMED_PHYSICAL_DYNAMICS_BRIDGE_NOT_PROVEN")

    return {
        "errors": sorted(set(errors)),
        "object_ids": sorted(object_set),
        "category_counts": actual_category_counts,
        "raw_pair_count": raw_pair_count,
        "exception_pairs": [list(p) for p in sorted(exceptions)],
        "query_required_pair_count": query_required,
        "non_c_non_exception_pair_count": non_c_non_exception,
        "c_related_pair_count": c_related,
        "phase1_object_ids": sorted(phase1),
        "phase1_pair_count": phase1_pairs,
        "phase1_exception_count": len(phase1_exceptions),
        "phase3_cumulative_object_ids": sorted(phase3),
        "phase3_added_pair_count": c_add_pairs,
        "phase3_cumulative_pair_count": math.comb(len(phase3), 2),
        "phase4_remaining_object_ids": sorted(remaining),
        "phase4_raw_pair_count": remaining_raw,
        "phase4_exception_count": len(remaining_exceptions),
        "phase4_query_required_pair_count": remaining_required,
        "direct_object_ids": sorted(direct_ids),
        "j3_object_ids": sorted(j3_ids),
        "j4_object_gain": dict(sorted(j4_map.items())),
        "c_object_ids": sorted(c_ids),
        "follower_link4_direct_ids": sorted(f"R::{n}" for n in follower_names),
        "mount_embedded_urdf_sha256": embedded_mount_urdf_sha,
        "accepted_urdf_raw_sha256": raw_sha,
        "accepted_urdf_lf_normalized_sha256": normalized_sha,
        "accepted_urdf_crlf_count": crlf_count,
        "accepted_urdf_bare_lf_count": bare_lf_count,
        "urdf_dual_digest_equivalent": urdf_equivalent,
        "mount_urdf_hash_conflict_detected": not urdf_equivalent,
        "confirmed_physical_dynamics_bridge_bound": bridge_confirmed,
    }


def build_gate(root: Path = ROOT) -> dict[str, Any]:
    pin_records: dict[str, dict[str, Any]] = {}
    for rel, expected in EXPECTED_HASHES.items():
        rec = file_record(root, rel, "frozen_external_input")
        rec["expected_sha256"] = expected
        rec["match"] = rec["sha256"] == expected
        pin_records[rel.stem.lower()] = rec
    mismatch = [rec["path"] for rec in pin_records.values() if not rec["match"]]
    if mismatch:
        raise RuntimeError("source pin mismatch: " + ", ".join(mismatch))

    registry = load_json(root, REGISTRY_REL)
    receipt = load_json(root, RECEIPT_REL)
    pair_contract = load_json(root, PAIR_CONTRACT_REL)
    motion_contract = load_json(root, MOTION_CONTRACT_REL)
    exact_source = (root / V9F_REL).read_text(encoding="utf-8")
    mount_text = (root / MOUNT_REL).read_text(encoding="utf-8")
    embedded_sha = extract_mount_embedded_urdf_sha(mount_text)
    urdf_raw_bytes = (root / URDF_REL).read_bytes()
    urdf_equivalence_receipt = load_json(root, URDF_EQUIV_REL)
    bridge_gate = load_json(root, BRIDGE_GATE_REL)
    bridge_owner_text = (root / BRIDGE_OWNER_REL).read_text(encoding="utf-8")
    bridge_confirmation_text = (root / BRIDGE_CONFIRM_REL).read_text(encoding="utf-8")
    audit = audit_state(
        registry, receipt, exact_source, pair_contract, motion_contract, embedded_sha,
        urdf_raw_bytes, urdf_equivalence_receipt, bridge_gate,
        bridge_owner_text, bridge_confirmation_text,
    )
    if audit["errors"]:
        raise RuntimeError("metadata audit failed: " + "; ".join(audit["errors"]))

    local_records = {
        "pair_contract": file_record(root, PAIR_CONTRACT_REL, "pair_oracle_contract"),
        "motion_contract": file_record(root, MOTION_CONTRACT_REL, "object_motion_contract"),
        "builder": file_record(root, BUILDER_REL, "metadata_only_deterministic_builder"),
        "tests": file_record(root, TEST_REL, "positive_and_negative_pytest"),
        "readme": file_record(root, README_REL, "human_readable_scope_and_reproduction"),
    }
    source_pins = {**local_records, **pin_records}
    return {
        "schema": "SYSTEM_BINDING_READINESS_GATE_V1",
        "generated_utc": "DETERMINISTIC_GATE_NO_WALLCLOCK",
        "authority": "METADATA_BINDING_READINESS_ONLY__NO_CURRENT_GEOMETRY_PAIR_EDGE_OR_PATH_AUTHORITY",
        "review_status": "PENDING_OWNER_REVIEW",
        "source_pins": source_pins,
        "read_scope": {
            "parsed_metadata_or_text": [
                PAIR_CONTRACT_REL.as_posix(), MOTION_CONTRACT_REL.as_posix(),
                REGISTRY_REL.as_posix(), RECEIPT_REL.as_posix(),
                V9F_REL.as_posix(), MOUNT_REL.as_posix(),
                URDF_EQUIV_REL.as_posix(), BRIDGE_GATE_REL.as_posix(),
                BRIDGE_OWNER_REL.as_posix(), BRIDGE_CONFIRM_REL.as_posix()
            ],
            "byte_hash_or_eol_normalization_only": [
                PAIR_CSV_REL.as_posix(), URDF_REL.as_posix(),
                NAMED_POSE_REVALIDATION_REL.as_posix(), BRIDGE_REL.as_posix()
            ],
            "prohibited_payload_suffixes_not_opened": sorted(PROHIBITED_PAYLOAD_SUFFIXES),
            "current_geometry_loaded": False,
            "pair_query_executed": False,
            "edge_query_executed": False,
            "path_search_executed": False,
        },
        "checks": {
            "all_source_hash_pins_match": True,
            "object_ids_unique_and_count_150": len(audit["object_ids"]) == 150,
            "category_counts_10_9_4_121_6": audit["category_counts"] == {"A": 10, "C": 9, "F": 4, "R": 121, "S": 6},
            "raw_pairs_11175": audit["raw_pair_count"] == 11175,
            "exact_adjacent_exceptions_9": len(audit["exception_pairs"]) == 9,
            "query_required_pairs_11166": audit["query_required_pair_count"] == 11166,
            "non_c_non_exception_pairs_9861": audit["non_c_non_exception_pair_count"] == 9861,
            "c_related_pairs_1305": audit["c_related_pair_count"] == 1305,
            "phase1_exact_object_set_131": len(audit["phase1_object_ids"]) == 131,
            "phase2_core_pairs_8515_no_exceptions": audit["phase1_pair_count"] == 8515 and audit["phase1_exception_count"] == 0,
            "phase3_add_c_1215_cumulative_9730": audit["phase3_added_pair_count"] == 1215 and audit["phase3_cumulative_pair_count"] == 9730,
            "phase4_remaining_raw_1445_exception_9_required_1436": audit["phase4_raw_pair_count"] == 1445 and audit["phase4_exception_count"] == 9 and audit["phase4_query_required_pair_count"] == 1436,
            "motion_partition_124_8_9_9": len(audit["direct_object_ids"]) == 124 and len(audit["j3_object_ids"]) == 8 and len(audit["j4_object_gain"]) == 9 and len(audit["c_object_ids"]) == 9,
            "follower_link4_is_direct_candidate": len(audit["follower_link4_direct_ids"]) == 2 and set(audit["follower_link4_direct_ids"]) <= set(audit["direct_object_ids"]),
            "mount_yaml_hash_D6E33_pinned": pin_records[MOUNT_REL.stem.lower()]["match"],
            "mount_embedded_digest_matches_lf_normalized_accepted_urdf": audit["mount_embedded_urdf_sha256"] == ACCEPTED_URDF_LF_SHA,
            "accepted_urdf_raw_crlf_digest_is_1BC2": audit["accepted_urdf_raw_sha256"] == ACCEPTED_URDF_SHA,
            "accepted_urdf_lf_normalized_digest_is_408147": audit["accepted_urdf_lf_normalized_sha256"] == ACCEPTED_URDF_LF_SHA,
            "urdf_dual_digest_equivalence_proven": audit["urdf_dual_digest_equivalent"],
            "mount_urdf_hash_conflict_absent": audit["mount_urdf_hash_conflict_detected"] is False,
            "confirmed_physical_dynamics_bridge_pinned": audit["confirmed_physical_dynamics_bridge_bound"],
            "execution_mount_numeric_spelling_unbound_fail_closed": motion_contract["current_readiness"]["execution_mount_numeric_spelling_bound"] is False,
            "collision_asset_frame_registration_unbound_fail_closed": motion_contract["current_readiness"]["collision_asset_frame_registration_bound"] is False,
            "zero_system_certified_motion_bounds": motion_contract["current_readiness"]["system_certified_object_motion_bound_count"] == 0,
            "zero_pair_queries": pair_contract["current_readiness"]["pair_queries_executed"] == 0,
            "contract_readiness_and_source_pins_cross_bound": True,
            "pair_discriminated_row_and_numeric_firewall_frozen": (
                pair_contract.get("row_schema_contract", {}).get("discriminator") == "row_kind"
                and "clearance_policy_sha256" in pair_contract.get("required_common_row_input_fields", [])
                and "authorized_pair_min_mm" in pair_contract.get("required_geometric_query_input_fields", [])
                and "numeric_and_shape_contract" in pair_contract
            ),
            "motion_full_locus_upper_bound_contract_frozen": (
                "<= B_i_cert" in motion_contract.get("global_motion_bound_definition", {}).get("per_object_interval_bound", "")
                and "full declared q domain" in motion_contract.get("coefficient_accounting_contract", {}).get("global_axis_distance_supremum", "")
            ),
        },
        "system_universe": {
            "object_count": 150,
            "category_counts": audit["category_counts"],
            "raw_pair_count": 11175,
            "exception_pair_count": 9,
            "query_required_pair_count": 11166,
            "non_c_non_exception_pair_count": 9861,
            "c_related_pair_count": 1305,
            "exception_pairs": audit["exception_pairs"],
        },
        "four_phase_planning_coverage": {
            "phase1_core_object_count": 131,
            "phase1_core_object_ids": audit["phase1_object_ids"],
            "phase2_core_internal_query_required_pairs": 8515,
            "phase3_c_object_count": 9,
            "phase3_added_query_required_pairs": 1215,
            "phase3_cumulative_query_required_pairs": 9730,
            "phase4_remaining_object_count": 10,
            "phase4_remaining_object_ids": audit["phase4_remaining_object_ids"],
            "phase4_raw_pairs": 1445,
            "phase4_exception_pairs": 9,
            "phase4_query_required_pairs": 1436,
            "classification": "PLANNED_COVERAGE_ONLY__NOT_EXECUTED_NOT_PASS",
        },
        "motion_classification": {
            "direct_rigid_fk_candidate_count": len(audit["direct_object_ids"]),
            "direct_rigid_fk_candidate_object_ids": audit["direct_object_ids"],
            "j3_hidden_translation_count": len(audit["j3_object_ids"]),
            "j3_hidden_translation_object_ids": audit["j3_object_ids"],
            "j4_travel_translation_count": len(audit["j4_object_gain"]),
            "j4_travel_translation_object_gain": audit["j4_object_gain"],
            "c_section_capsule_count": len(audit["c_object_ids"]),
            "c_section_capsule_object_ids": audit["c_object_ids"],
            "follower_link4_direct_object_ids": audit["follower_link4_direct_ids"],
            "classified_total": 150,
            "system_certified_object_motion_bound_count": 0,
        },
        "mount_binding": {
            "urdf_content_identity": {
                "classification": "SAME_ACCEPTED_URDF__EOL_DUAL_DIGEST",
                "raw_crlf_sha256": audit["accepted_urdf_raw_sha256"],
                "lf_normalized_sha256": audit["accepted_urdf_lf_normalized_sha256"],
                "crlf_replacement_count": audit["accepted_urdf_crlf_count"],
                "semantic_delta": False,
                "conflict": False,
            },
            "physical_mount_pose_yaml_sha256": EXPECTED_HASHES[MOUNT_REL],
            "physical_mount_role": "WP11_PHYSICAL_INSTALLATION_AUTHORITY__D6_HISTORICAL_6DP_SPELLING",
            "dynamics_mount_role": "ODR01_DYNAMICS_T_SM",
            "physical_to_dynamics_bridge_sha256": EXPECTED_HASHES[BRIDGE_REL],
            "effective_bridge_status": "CONFIRMED_MECHANICAL_DYNAMICS_BRIDGE_BY_ODR45",
            "execution_mount_numeric_spelling_bound": False,
            "collision_asset_to_accepted_urdf_frame_registration_bound": False,
            "disposition": "CONTENT_IDENTITY_AND_FRAME_BRIDGE_BOUND__EXECUTION_SPELLING_AND_COLLISION_ASSET_REGISTRATION_HOLD",
        },
        "current_readiness": {
            "contracts_structurally_ready": True,
            "four_phase_coverage_is_planning_only": True,
            "urdf_content_identity_bound": True,
            "physical_dynamics_bridge_bound": True,
            "execution_mount_numeric_spelling_bound": False,
            "collision_asset_frame_registration_bound": False,
            "clearance_policy_bound": False,
            "system_certified_object_motion_bound_count": 0,
            "system_pair_oracle_bound": False,
            "system_pair_queries_executed": 0,
            "system_edges_certified": 0,
            "complete_system_collision_pass": False,
            "pair_evaluation_authorized": False,
            "edge_evaluation_authorized": False,
            "path_search_authorized": False,
            "path_search_executed": False,
            "next_stage_authorized": False,
            "release_credit": False,
        },
        "blockers": [
            "EXECUTION_MOUNT_NUMERIC_SPELLING_NOT_BOUND",
            "CURRENT_COLLISION_ASSET_TO_ACCEPTED_URDF_FRAME_REGISTRATION_NOT_BOUND",
            "ZERO_HASH_BOUND_SYSTEM_OBJECT_MOTION_CERTIFICATES",
            "NINE_C_SECTION_CAPSULE_HAUSDORFF_DERATES_ABSENT",
            "HASH_BOUND_PER_PAIR_CLEARANCE_POLICY_ABSENT",
            "SYSTEM_PAIR_ORACLE_BACKEND_NOT_BOUND",
            "11166_REQUIRED_PAIRS_UNASSESSED_FAIL_CLOSED",
            "NO_CURRENT_EDGE_OR_PATH_AUTHORITY",
        ],
        "verdict": "SYSTEM_BINDING_CONTRACTS_STRUCTURAL_PASS__URDF_CONTENT_AND_CONFIRMED_FRAME_BRIDGE_BOUND__EXECUTION_MOUNT_SPELLING_CLEARANCE_POLICY_AND_MOTION_CERTIFICATES_ABSENT__PAIR_EDGE_PATH_RELEASE_HOLD",
    }


def build_manifest_bytes(root: Path, gate_bytes: bytes) -> bytes:
    roles = {
        PAIR_CONTRACT_REL: "pair oracle contract",
        MOTION_CONTRACT_REL: "object motion-bound contract",
        BUILDER_REL: "metadata-only deterministic builder",
        TEST_REL: "positive and fail-closed negative tests",
        README_REL: "scope and reproduction",
        REGISTRY_REL: "150-object structural registry",
        PAIR_CSV_REL: "11175-pair enumeration; byte hash only",
        RECEIPT_REL: "V9F motion-class receipt",
        V9F_REL: "frozen exact evaluator source; static text only",
        MOUNT_REL: "physical mount/pose YAML; historical 6dp matrix spelling",
        URDF_REL: "accepted URDF; raw hash plus in-memory CRLF-to-LF normalization only",
        URDF_EQUIV_REL: "accepted URDF dual-EOL-digest equivalence receipt",
        NAMED_POSE_REVALIDATION_REL: "named-pose digital kinematics revalidation; byte hash only",
        BRIDGE_REL: "confirmed physical-to-dynamics bridge payload; byte hash only",
        BRIDGE_GATE_REL: "MPI bridge 9-criterion PASS gate; metadata only",
        BRIDGE_OWNER_REL: "ODR-45 owner confirmation record; text status pin",
        BRIDGE_CONFIRM_REL: "bridge owner-confirmation addendum; text status pin",
    }
    rows = [file_record(root, rel, role) for rel, role in roles.items()]
    rows.append({
        "path": GATE_REL.as_posix(),
        "sha256": sha256_bytes(gate_bytes),
        "bytes": len(gate_bytes),
        "role": "generated HOLD readiness gate",
    })
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output, fieldnames=["path", "sha256", "bytes", "role"], lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def expected_outputs(root: Path = ROOT) -> tuple[bytes, bytes]:
    gate_bytes = canonical_bytes(build_gate(root))
    manifest_bytes = build_manifest_bytes(root, gate_bytes)
    return gate_bytes, manifest_bytes


def write_bytes_lf(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        handle.write(data)


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    gate_bytes, manifest_bytes = expected_outputs(ROOT)
    if args.write:
        write_bytes_lf(ROOT / GATE_REL, gate_bytes)
        write_bytes_lf(ROOT / MANIFEST_REL, manifest_bytes)
        print(f"WROTE {GATE_REL.as_posix()} {sha256_bytes(gate_bytes)}")
        print(f"WROTE {MANIFEST_REL.as_posix()} {sha256_bytes(manifest_bytes)}")
        return 0
    actual_gate = (ROOT / GATE_REL).read_bytes()
    actual_manifest = (ROOT / MANIFEST_REL).read_bytes()
    if actual_gate != gate_bytes or actual_manifest != manifest_bytes:
        print("FAIL: generated outputs are stale or nondeterministic")
        return 2
    print("PASS: gate and manifest byte-identical to deterministic rebuild")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
