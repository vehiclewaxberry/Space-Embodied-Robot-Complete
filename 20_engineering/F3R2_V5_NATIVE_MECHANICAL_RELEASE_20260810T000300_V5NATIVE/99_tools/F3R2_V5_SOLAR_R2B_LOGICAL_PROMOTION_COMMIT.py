#!/usr/bin/env python3
"""Create or verify the write-once R2B logical promotion commit.

This program is deliberately a pure filesystem evidence tool.  It never opens
SOLIDWORKS, never writes CAD, never copies an attempt artifact, and never
replaces an existing output.  Creation is permitted only after all input JSON
has parsed, every required semantic check has passed, and the final payload has
been completely serialized with ``allow_nan=False``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "F3R2_V5_SOLAR_R2B_LOGICAL_PROMOTION_COMMIT_V1"
VERDICT = "V5_SOLAR_R2B_A_LOGICALLY_PROMOTED_IN_PLACE_FOR_TOP_INTEGRATION"
ATTEMPT_ID = "V5_SOLAR_R2B_BUILD_20260813T123100Z_P9E9"
STORAGE_ID = "20260813T123100Z_P9E9"

BUILD_RECEIPT_SHA256 = "6537E44BF91E92EC747EA4335BE6E96D2D6BCABC5FBB3BA692C132D2C153EF62"
HANDOFF_SHA256 = "3A894DBADD5FE3D64E005D1999C0B4FC6F8A534DCE66D9D06FEF7134A222B8CD"
FRESH_PASS_SHA256 = "1E4AC41F97317F0D16A8113CCDA79117B4AC08A026F9E5ED39E0F64E569EA753"
BUILDER_SHA256 = "E5255A4BE587C43F0C237367E0B2C90E2AF8C66F230A9C630B4D596922F96C4C"
VERIFIER_SHA256 = "9735518A5B9498793BA967DCC41E5C1AE6E31AA7CB1DCDA64D019236E5C5EDF9"
CONTRACT_SHA256 = "B885E6B4F51663DC268FE6C9F5E497B99A514BE1706B616C230D5D35A2D697FB"
ACCEPTED_URDF_SHA256 = "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164"
ROOT_FLIP_EVIDENCE_CHAIN_SHA256 = "316A433EF215A38A7E090E0AE88E3E6362D6079B25ACBB01596C810CD2790889"

STATE_NAMES = [
    "SOLAR_STOWED",
    "SOLAR_DEPLOY_STAGE1",
    "SOLAR_DEPLOY_STAGE2",
    "SOLAR_DEPLOYED_NOMINAL",
    "SOLAR_LEFT_FAIL",
    "SOLAR_RIGHT_FAIL",
    "SOLAR_BOTH_FAIL",
]

EXPECTED_STATE_ANGLES = {
    "SOLAR_STOWED": {"LEFT": [0, 0, 0], "RIGHT": [0, 0, 0]},
    "SOLAR_DEPLOY_STAGE1": {"LEFT": [90, 0, 0], "RIGHT": [90, 0, 0]},
    "SOLAR_DEPLOY_STAGE2": {"LEFT": [90, 90, 0], "RIGHT": [90, 90, 0]},
    "SOLAR_DEPLOYED_NOMINAL": {"LEFT": [90, 90, 90], "RIGHT": [90, 90, 90]},
    "SOLAR_LEFT_FAIL": {"LEFT": [0, 0, 0], "RIGHT": [90, 90, 90]},
    "SOLAR_RIGHT_FAIL": {"LEFT": [90, 90, 90], "RIGHT": [0, 0, 0]},
    "SOLAR_BOTH_FAIL": {"LEFT": [0, 0, 0], "RIGHT": [0, 0, 0]},
}

EXPECTED_AUTHORITY_SHA256 = {
    "interface_requirements": "62DDF827056D5199CCA68FD1714874E52FFB06398D4B856175435DD576504014",
    "interface_freeze": "B60D8C635A030B0DB49DF7129D6B7F50ACB0F5B9FC912C2E5DED4405FF6542C8",
    "state_authority_r2b": "BA639C6BF4F0875B6FD9AFFF2E6CA7A5AA3BA1AF77C6BD5FEC07A8EB62D8E6D8",
    "assembly_architecture": "3CC38465A6B7FA6E91F275BAE4052E1787B5A44A6F196AFCEFA88AA7D209D545",
    "static_oracle_r2b": "F4E5E0CD5A8559991B60826C6221294948CD07889836500D81527AE0982196F6",
    "r2b_build_authorization": "BAD16D48EAEDCF27B3953831B7108A4ADB95CC3DD8F476FB02CB29EAE454FCCB",
    "production_root_flip_authorization": "07D3D9380668E0308981D0BF85D4EB0951789793F90EAB97503BB23C82C7280E",
    "production_root_branch_probe_source": "FBF3F0D53E3078D9E5A5B2CB0060A4EDBCC8BD7F01E6DE7B3C19F9A4ABD3F1D2",
    "production_root_branch_probe_result": "18393CAC2423032AFF309361E37D5CE3612AA086C9EA5FD16D991EC2DF593DA0",
    "accepted_b601_urdf": ACCEPTED_URDF_SHA256,
}

EXPECTED_SIDE_FILES = {
    "L": "L_SOLAR_ARRAY_R2B_SUCCESSOR.SLDASM",
    "R": "R_SOLAR_ARRAY_R2B_SUCCESSOR.SLDASM",
}

FORBIDDEN_OLD_LIVE_TOKENS = (
    "SINGLE_PANEL",
    "LEFT_WING_ROOT_TRUE_HINGE.SLDASM",
    "RIGHT_WING_ROOT_TRUE_HINGE.SLDASM",
    "LEFT_SOLAR_PANEL_NATIVE",
    "RIGHT_SOLAR_PANEL_NATIVE",
)


class PromotionError(RuntimeError):
    """A fail-closed evidence validation error."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PromotionError(message)


def norm_path(path: Path | str) -> str:
    return Path(path).resolve().as_posix()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def file_fact(path: Path) -> dict[str, Any]:
    path = path.resolve()
    require(path.is_file(), f"required file missing: {path}")
    require(not path.is_symlink(), f"symlink is not accepted as immutable evidence: {path}")
    data = path.read_bytes()
    return {"path": path.as_posix(), "bytes": len(data), "sha256": sha256_bytes(data)}


def require_fact(actual: dict[str, Any], expected: dict[str, Any], label: str) -> None:
    require(isinstance(expected, dict), f"{label}: recorded fact is not an object")
    require(expected.get("path") == actual["path"], f"{label}: path mismatch")
    require(expected.get("bytes") == actual["bytes"], f"{label}: byte count mismatch")
    require(str(expected.get("sha256", "")).upper() == actual["sha256"], f"{label}: SHA256 mismatch")


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # exact source exception is preserved in the message
        raise PromotionError(f"{label}: invalid UTF-8 JSON: {exc}") from exc
    require(isinstance(value, dict), f"{label}: root must be a JSON object")
    return value


def canonical_json_bytes(value: Any, *, pretty: bool) -> bytes:
    if pretty:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    else:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return text.encode("utf-8")


def canonical_digest(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value, pretty=False))


def parse_utc(value: str, label: str) -> datetime:
    require(isinstance(value, str) and value, f"{label}: missing UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PromotionError(f"{label}: invalid timestamp {value!r}") from exc
    require(parsed.tzinfo is not None, f"{label}: timestamp has no timezone")
    return parsed.astimezone(timezone.utc)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def record_target(record: dict[str, Any], label: str) -> dict[str, Any]:
    target = record.get("target")
    require(isinstance(target, dict), f"{label}: target fact missing")
    return target


def facts_by_path(records: Iterable[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        fact = record_target(record, f"{label}[{index}]")
        path = fact.get("path")
        require(isinstance(path, str), f"{label}[{index}]: target path missing")
        require(path not in result, f"{label}: duplicate target path {path}")
        result[path] = fact
    return result


def list_tree_facts(root: Path) -> list[dict[str, Any]]:
    root = root.resolve()
    require(root.is_dir(), f"attempt root missing: {root}")
    facts = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_file():
            facts.append(file_fact(path))
        elif path.is_symlink():
            raise PromotionError(f"attempt tree contains a symlink: {path}")
    return facts


def require_exact_fact_hash(fact: dict[str, Any], expected_sha: str, label: str) -> None:
    require(fact["sha256"] == expected_sha, f"{label}: expected {expected_sha}, got {fact['sha256']}")


def artifact_fact_set(
    attempt_root: Path,
    build: dict[str, Any],
    handoff: dict[str, Any],
    fresh: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    parts = build.get("parts")
    modules = build.get("modules")
    sides = build.get("side_assemblies")
    require(isinstance(parts, list) and len(parts) == 38, "build receipt must contain exactly 38 parts")
    require(isinstance(modules, list) and len(modules) == 6, "build receipt must contain exactly 6 modules")
    require(isinstance(sides, list) and len(sides) == 2, "build receipt must contain exactly 2 side assemblies")

    build_records = parts + modules + sides
    build_map = facts_by_path(build_records, "build artifacts")
    require(len(build_map) == 46, "build artifact paths are not 46 unique files")

    fresh_parts = fresh.get("parts")
    fresh_modules = fresh.get("modules")
    fresh_sides = fresh.get("sides")
    require(isinstance(fresh_parts, list) and len(fresh_parts) == 38, "fresh receipt must contain 38 parts")
    require(isinstance(fresh_modules, list) and len(fresh_modules) == 6, "fresh receipt must contain 6 modules")
    require(isinstance(fresh_sides, list) and len(fresh_sides) == 2, "fresh receipt must contain 2 side assemblies")
    fresh_map = facts_by_path(fresh_parts + fresh_modules + fresh_sides, "fresh artifacts")
    require(set(fresh_map) == set(build_map), "fresh artifact path set differs from build artifact path set")

    handoff_facts = handoff.get("pre_verifier_cad_facts")
    require(isinstance(handoff_facts, list) and len(handoff_facts) == 46, "handoff must contain 46 pre-verifier CAD facts")
    handoff_map: dict[str, dict[str, Any]] = {}
    for index, fact in enumerate(handoff_facts):
        require(isinstance(fact, dict) and isinstance(fact.get("path"), str), f"handoff fact {index} malformed")
        require(fact["path"] not in handoff_map, f"handoff contains duplicate path {fact['path']}")
        handoff_map[fact["path"]] = fact
    require(set(handoff_map) == set(build_map), "handoff artifact path set differs from build artifact path set")

    cad_pre = fresh.get("cad_hash_pre")
    cad_post = fresh.get("cad_hash_post")
    require(isinstance(cad_pre, dict) and len(cad_pre) == 46, "fresh PRE hash map must contain 46 files")
    require(isinstance(cad_post, dict) and len(cad_post) == 46, "fresh POST hash map must contain 46 files")
    require(cad_pre == cad_post, "fresh CAD PRE and POST hash maps differ")
    require(set(cad_pre) == set(build_map), "fresh CAD hash path set differs from build path set")

    cad_root = (attempt_root / "cad").resolve()
    result: list[dict[str, Any]] = []
    for path_text in sorted(build_map, key=str.casefold):
        path = Path(path_text).resolve()
        require(os.path.commonpath((str(cad_root), str(path))) == str(cad_root), f"CAD file escapes attempt CAD root: {path}")
        actual = file_fact(path)
        require_fact(actual, build_map[path_text], f"build fact {path.name}")
        require_fact(actual, fresh_map[path_text], f"fresh target fact {path.name}")
        require_fact(actual, handoff_map[path_text], f"handoff fact {path.name}")
        require_fact(actual, cad_pre[path_text], f"fresh PRE fact {path.name}")
        require_fact(actual, cad_post[path_text], f"fresh POST fact {path.name}")

        relative = path.relative_to(cad_root).as_posix()
        if relative.startswith("parts/"):
            role = "SLDPRT"
            require(path.suffix.upper() == ".SLDPRT", f"part extension invalid: {path}")
        elif relative.startswith("modules/"):
            role = "RIGID_PANEL_MODULE_SLDASM"
            require(path.suffix.upper() == ".SLDASM", f"module extension invalid: {path}")
        elif relative.startswith("sides/"):
            role = "SIDE_STATE_OWNER_SLDASM"
            require(path.suffix.upper() == ".SLDASM", f"side extension invalid: {path}")
        else:
            raise PromotionError(f"unexpected CAD artifact location: {path}")
        result.append({"role": role, **actual})

    counts = {
        "SLDPRT": sum(item["role"] == "SLDPRT" for item in result),
        "RIGID_PANEL_MODULE_SLDASM": sum(item["role"] == "RIGID_PANEL_MODULE_SLDASM" for item in result),
        "SIDE_STATE_OWNER_SLDASM": sum(item["role"] == "SIDE_STATE_OWNER_SLDASM" for item in result),
    }
    require(counts == {"SLDPRT": 38, "RIGID_PANEL_MODULE_SLDASM": 6, "SIDE_STATE_OWNER_SLDASM": 2}, "38+6+2 CAD count contract failed")

    side_facts: list[dict[str, Any]] = []
    side_records = {record.get("side"): record for record in sides}
    fresh_side_records = {record.get("side"): record for record in fresh_sides}
    require(set(side_records) == {"L", "R"}, "build side labels must be exactly L and R")
    require(set(fresh_side_records) == {"L", "R"}, "fresh side labels must be exactly L and R")
    for side in ("L", "R"):
        build_side = side_records[side]
        fresh_side = fresh_side_records[side]
        actual = file_fact(Path(record_target(build_side, f"build side {side}")["path"]))
        require(Path(actual["path"]).name == EXPECTED_SIDE_FILES[side], f"unexpected {side} side filename")
        configuration_names = fresh_side.get("configuration_names")
        require(isinstance(configuration_names, list), f"fresh side {side} configuration names missing")
        require(len(configuration_names) == 7 and len(set(configuration_names)) == 7, f"fresh side {side} configuration count/uniqueness failed")
        require(set(configuration_names) == set(STATE_NAMES), f"fresh side {side} configurations differ from exact seven-state contract")
        fresh_states = fresh_side.get("states")
        require(isinstance(fresh_states, list) and [item.get("state") for item in fresh_states] == STATE_NAMES, f"fresh side {side} state record order/names failed")
        build_configs = build_side.get("configurations")
        require(isinstance(build_configs, list) and [item.get("state") for item in build_configs] == STATE_NAMES, f"build side {side} configuration order/names failed")
        for state_record in build_configs:
            state = state_record["state"]
            require(state_record.get("angles_deg") == EXPECTED_STATE_ANGLES[state]["LEFT" if side == "L" else "RIGHT"], f"build {side}/{state} logical angles differ from authority")
        for state_record in fresh_states:
            state = state_record["state"]
            require(state_record.get("angles_deg") == EXPECTED_STATE_ANGLES[state]["LEFT" if side == "L" else "RIGHT"], f"fresh {side}/{state} logical angles differ from authority")
        side_facts.append({
            "side": side,
            **actual,
            "configuration_names_authority_order": STATE_NAMES,
            "configuration_count": 7,
            "configuration_owner": "SIDE_SLDASM_ONLY",
            "top_level_occurrence_solving": "RIGID",
        })

    return result, side_facts, build_map


def collect_and_validate() -> dict[str, Any]:
    script = Path(__file__).resolve()
    release_root = script.parent.parent.resolve()
    attempt_root = (release_root / "13_validation" / "solar_r2_attempts" / STORAGE_ID).resolve()
    evidence_root = attempt_root / "evidence"

    build_path = evidence_root / "BUILD_STAGE_RECEIPT.json"
    handoff_path = evidence_root / "FRESH_PID_VERIFIER_HANDOFF.json"
    fresh_path = evidence_root / "F3R2_V5_SOLAR_R2B_A_FRESH_VERIFY_PASS.json"
    builder_path = release_root / "99_tools" / "F3R2_V5_NATIVE_SOLAR_ARRAY_R2B_BUILD_STAGE_ATTACH_ONLY.py"
    verifier_path = release_root / "99_tools" / "F3R2_V5_NATIVE_SOLAR_ARRAY_R2B_FRESH_VERIFY_ATTACH_ONLY.py"

    build_fact = file_fact(build_path)
    handoff_fact = file_fact(handoff_path)
    fresh_fact = file_fact(fresh_path)
    builder_fact = file_fact(builder_path)
    verifier_fact = file_fact(verifier_path)
    require_exact_fact_hash(build_fact, BUILD_RECEIPT_SHA256, "build receipt")
    require_exact_fact_hash(handoff_fact, HANDOFF_SHA256, "fresh verifier handoff")
    require_exact_fact_hash(fresh_fact, FRESH_PASS_SHA256, "fresh PASS receipt")
    require_exact_fact_hash(builder_fact, BUILDER_SHA256, "current builder source")
    require_exact_fact_hash(verifier_fact, VERIFIER_SHA256, "current fresh verifier source")

    build = load_json(build_path, "build receipt")
    handoff = load_json(handoff_path, "fresh verifier handoff")
    fresh = load_json(fresh_path, "fresh PASS receipt")

    require(build.get("schema") == "F3R2_V5_SOLAR_R2B_A_BUILD_STAGE_RECEIPT_V1", "unexpected build receipt schema")
    require(build.get("verdict") == "V5_SOLAR_R2B_A_BUILD_STAGE_PASS_AWAITING_FRESH_PID_VERIFIER", "unexpected build verdict")
    require(handoff.get("schema") == "F3R2_V5_SOLAR_R2B_A_FRESH_PID_VERIFIER_HANDOFF_V1", "unexpected handoff schema")
    require(handoff.get("status") == "AWAITING_DIFFERENT_PID_READ_ONLY_ZERO_MUTATION_VERIFICATION", "unexpected handoff status")
    require(fresh.get("schema") == "F3R2_V5_SOLAR_R2B_A_FRESH_VERIFY_RECEIPT_V1", "unexpected fresh receipt schema")
    require(fresh.get("verdict") == "V5_SOLAR_R2B_A_NEW_PID_READ_ONLY_ZERO_MUTATION_PASS", "unexpected fresh receipt verdict")
    for label, record in (("build", build), ("handoff", handoff), ("fresh", fresh)):
        require(record.get("attempt_id") == ATTEMPT_ID, f"{label} attempt_id mismatch")
        require(record.get("storage_id") == STORAGE_ID, f"{label} storage_id mismatch")
        require(norm_path(record.get("attempt_root")) == attempt_root.as_posix(), f"{label} attempt_root mismatch")

    require_fact(builder_fact, build.get("builder", {}), "build builder source pointer")
    require_fact(builder_fact, handoff.get("builder", {}), "handoff builder source pointer")
    require_fact(build_fact, fresh.get("build_receipt", {}), "fresh build receipt pointer")
    require_fact(handoff_fact, fresh.get("handoff", {}), "fresh handoff pointer")
    require_fact(verifier_fact, fresh.get("verifier", {}), "fresh verifier source pointer")
    require(build.get("contract_sha256") == CONTRACT_SHA256, "build contract digest mismatch")
    require(handoff.get("contract_sha256") == CONTRACT_SHA256, "handoff contract digest mismatch")
    require(fresh.get("release_provenance_lineage", {}).get("microfixture", {}).get("production_contract_sha256") == CONTRACT_SHA256, "fresh lineage contract digest mismatch")
    require(fresh.get("release_provenance_lineage", {}).get("microfixture", {}).get("production_builder", {}).get("sha256") == BUILDER_SHA256, "fresh lineage builder digest mismatch")

    require(build.get("protected_pre") == build.get("protected_post"), "build protected PRE/POST facts differ")
    require(fresh.get("protected_pre") == fresh.get("protected_post"), "fresh protected PRE/POST facts differ")
    require(fresh.get("protected_hash_pre_equals_post") is True, "fresh protected PRE=POST claim is false")
    require(fresh.get("cad_hash_pre") == fresh.get("cad_hash_post"), "fresh CAD PRE/POST facts differ")
    require(fresh.get("all_46_cad_hash_pre_equals_post") is True, "fresh all-46 PRE=POST claim is false")
    require(fresh.get("read_only") is True, "fresh verifier did not assert read-only mode")
    require(fresh.get("cad_write_calls") == 0, "fresh verifier recorded CAD write calls")
    require(fresh.get("different_pid_and_process_create_time") is True, "fresh process separation claim is false")
    require(fresh.get("promotion_authorized") is True, "fresh receipt does not authorize logical promotion")
    require(handoff.get("promotion_authorized") is False, "handoff must not pre-authorize promotion")

    build_session = build.get("session", {})
    verify_session = fresh.get("solidworks_verify_session", {})
    build_pid = build_session.get("pid")
    fresh_pid = verify_session.get("pid")
    require(isinstance(build_pid, int) and isinstance(fresh_pid, int), "build/fresh PID is missing")
    require(build_pid == handoff.get("build_pid"), "handoff build PID differs from build receipt")
    require(build_pid != fresh_pid, "fresh PID equals build PID")
    build_time = parse_utc(build_session.get("process_create_time"), "build process create time")
    fresh_time = parse_utc(verify_session.get("process_start_utc"), "fresh process create time")
    require(fresh_time > build_time, "fresh process is not newer than build process")
    require(verify_session.get("different_pid_from_build") is True, "fresh session different-PID readback failed")
    require(verify_session.get("different_process_create_time_from_build") is True, "fresh session different-create-time readback failed")
    require(verify_session.get("newer_process_than_build") is True, "fresh session newer-process readback failed")
    require(verify_session.get("attach_only") is True, "fresh session was not attach-only")
    require(verify_session.get("active_doc_is_null_before") is True and verify_session.get("document_count_before") == 0, "fresh session was not empty before verification")
    cleanup = fresh.get("cleanup", {})
    require(cleanup.get("active_doc_is_null_after") is True and cleanup.get("document_count_after") == 0, "fresh session cleanup did not return to empty")
    require(cleanup.get("closed_owned_read_only_documents") == [], "fresh cleanup unexpectedly owned documents")

    authority_bundle = build.get("authority_bundle")
    require(isinstance(authority_bundle, dict), "build authority bundle missing")
    authority_facts: dict[str, dict[str, Any]] = {}
    for label, expected_sha in EXPECTED_AUTHORITY_SHA256.items():
        recorded = authority_bundle.get(label)
        require(isinstance(recorded, dict), f"authority bundle item missing: {label}")
        actual = file_fact(Path(recorded.get("path", "")))
        require_fact(actual, recorded, f"authority bundle {label}")
        require_exact_fact_hash(actual, expected_sha, f"authority bundle {label}")
        require_fact(actual, handoff.get("authority_bundle", {}).get(label, {}), f"handoff authority bundle {label}")
        authority_facts[label] = actual

    state_authority = load_json(Path(authority_facts["state_authority_r2b"]["path"]), "state authority")
    require(state_authority.get("schema") == "F3R2_V5_SOLAR_STATE_AUTHORITY_R2B", "state authority schema mismatch")
    require(list(state_authority.get("states", {})) == STATE_NAMES, "state authority exact state order/names mismatch")
    for state in STATE_NAMES:
        for side in ("LEFT", "RIGHT"):
            require(state_authority["states"][state].get(side) == EXPECTED_STATE_ANGLES[state][side], f"state authority angle mismatch: {state}/{side}")

    architecture = load_json(Path(authority_facts["assembly_architecture"]["path"]), "assembly architecture")
    require(architecture.get("schema") == "F3R2_V5_SOLAR_R2_ASSEMBLY_ARCHITECTURE_DECISION_V1", "architecture schema mismatch")
    require(architecture.get("decision") == "PANEL_MODULE_RIGID_ARCHITECTURE", "architecture decision mismatch")
    ownership = architecture.get("configuration_ownership", {})
    require(ownership.get("side_assemblies") == "SOLE_OWNER_OF_ALL_SEVEN_SOLAR_STATES", "architecture side configuration ownership mismatch")
    require(ownership.get("top_assembly") == "SELECT_REFERENCED_CONFIGURATION_ONLY; NO_SECOND_SOLAR_ANGLE_DRIVER", "architecture top driver prohibition mismatch")
    require(architecture.get("release_contract", {}).get("old_single_panel_reintroduced") is False, "architecture permits old single-panel reintroduction")
    require(architecture.get("release_contract", {}).get("urdf_and_l0_mass_truth_unchanged") is True, "architecture does not preserve URDF/L0 truth")

    oracle = load_json(Path(authority_facts["static_oracle_r2b"]["path"]), "static oracle")
    require(oracle.get("verdict") == "V5_SOLAR_R2B_STATIC_KINEMATIC_ORACLE_PASS", "static oracle did not pass")
    build_authorization = load_json(Path(authority_facts["r2b_build_authorization"]["path"]), "build authorization")
    require(build_authorization.get("verdict") == "V5_SOLAR_R2B_BUILD_AUTHORIZED_WITH_ORDERED_HOLDS", "build authorization verdict mismatch")
    root_flip = load_json(Path(authority_facts["production_root_flip_authorization"]["path"]), "root flip authorization")
    require(root_flip.get("verdict") == "V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_PATCH_ONLY_AUTHORIZED", "root flip authorization verdict mismatch")
    require(root_flip.get("evidence_chain_sha256") == ROOT_FLIP_EVIDENCE_CHAIN_SHA256, "root flip evidence-chain digest mismatch")
    require(root_flip.get("authorized_patch", {}).get("after") == {"L": {"H12": False, "H23": True, "ROOT": False}, "R": {"H12": True, "H23": False, "ROOT": True}}, "authorized production flip map mismatch")

    accepted_pre = build.get("protected_pre", {}).get("accepted_b601_urdf")
    accepted_post = build.get("protected_post", {}).get("accepted_b601_urdf")
    require(isinstance(accepted_pre, dict) and isinstance(accepted_post, dict), "accepted B601 URDF protected facts missing")
    accepted_actual = file_fact(Path(accepted_pre.get("path", "")))
    require_fact(accepted_actual, accepted_pre, "accepted B601 URDF PRE")
    require_fact(accepted_actual, accepted_post, "accepted B601 URDF POST")
    require_exact_fact_hash(accepted_actual, ACCEPTED_URDF_SHA256, "accepted B601 URDF current")
    require_fact(accepted_actual, authority_facts["accepted_b601_urdf"], "accepted B601 URDF authority bundle")

    artifacts, side_facts, build_artifact_map = artifact_fact_set(attempt_root, build, handoff, fresh)

    old_live_scan = canonical_json_bytes(
        {
            "artifact_paths": [item["path"] for item in artifacts],
            "side_references": [item.get("references") for item in build.get("side_assemblies", [])],
            "side_expected_reference_paths": [item.get("expected_reference_paths") for item in build.get("side_assemblies", [])],
        },
        pretty=False,
    ).decode("utf-8").upper()
    for token in FORBIDDEN_OLD_LIVE_TOKENS:
        require(token not in old_live_scan, f"old single-panel live reference found: {token}")

    tree_facts = list_tree_facts(attempt_root)
    require(len(tree_facts) == 52, f"P9 attempt tree must contain exactly 52 immutable files, found {len(tree_facts)}")
    require(sum(item["path"].upper().endswith(".SLDPRT") for item in tree_facts) == 38, "attempt tree SLDPRT count differs from 38")
    require(sum(item["path"].upper().endswith(".SLDASM") for item in tree_facts) == 8, "attempt tree SLDASM count differs from 8")
    require(set(build_artifact_map) == {item["path"] for item in artifacts}, "artifact commitment does not match build map")

    authority_commitment = {label: authority_facts[label] for label in sorted(authority_facts)}
    return {
        "release_root": release_root.as_posix(),
        "attempt_root": attempt_root.as_posix(),
        "producer": file_fact(script),
        "inputs": {
            "build_receipt": build_fact,
            "fresh_pid_verifier_handoff": handoff_fact,
            "fresh_read_only_pass": fresh_fact,
            "builder": builder_fact,
            "fresh_verifier": verifier_fact,
            "contract_sha256": CONTRACT_SHA256,
        },
        "authority_bundle": authority_commitment,
        "root_flip_evidence": {
            "authorization": authority_facts["production_root_flip_authorization"],
            "evidence_chain_sha256": ROOT_FLIP_EVIDENCE_CHAIN_SHA256,
            "production_probe_source": authority_facts["production_root_branch_probe_source"],
            "production_probe_result": authority_facts["production_root_branch_probe_result"],
            "authorized_flip_map": root_flip["authorized_patch"]["after"],
        },
        "process_separation": {
            "build_pid": build_pid,
            "build_process_create_time_utc": build_time.isoformat().replace("+00:00", "Z"),
            "fresh_pid": fresh_pid,
            "fresh_process_create_time_utc": fresh_time.isoformat().replace("+00:00", "Z"),
            "different_pid": True,
            "different_process_create_time": True,
            "fresh_process_newer": True,
            "fresh_attach_only": True,
            "fresh_empty_before": True,
            "fresh_empty_after": True,
        },
        "zero_mutation": {
            "fresh_read_only": True,
            "cad_write_calls": 0,
            "cad_hash_pre_equals_post": True,
            "all_46_cad_hash_pre_equals_post": True,
            "protected_hash_pre_equals_post": True,
            "accepted_b601_urdf_pre_equals_post_equals_current": True,
            "accepted_b601_urdf": accepted_actual,
        },
        "cad_artifacts": artifacts,
        "cad_artifact_counts": {
            "sldprt": 38,
            "rigid_panel_module_sldasm": 6,
            "side_state_owner_sldasm": 2,
            "total": 46,
        },
        "cad_artifact_set_sha256": canonical_digest(artifacts),
        "side_assemblies": side_facts,
        "state_angles_deg": EXPECTED_STATE_ANGLES,
        "attempt_tree_files": tree_facts,
        "attempt_tree_file_count": len(tree_facts),
        "attempt_tree_sha256": canonical_digest(tree_facts),
    }


def build_payload(evidence: dict[str, Any], timestamp_utc: str) -> dict[str, Any]:
    parse_utc(timestamp_utc, "promotion timestamp")
    input_commitment = {
        "inputs": evidence["inputs"],
        "authority_bundle": evidence["authority_bundle"],
        "root_flip_evidence": evidence["root_flip_evidence"],
        "cad_artifact_set_sha256": evidence["cad_artifact_set_sha256"],
        "attempt_tree_sha256": evidence["attempt_tree_sha256"],
    }
    return {
        "schema": SCHEMA,
        "timestamp_utc": timestamp_utc,
        "verdict": VERDICT,
        "attempt_id": ATTEMPT_ID,
        "storage_id": STORAGE_ID,
        "attempt_root": evidence["attempt_root"],
        "producer": evidence["producer"],
        "promotion_scope": {
            "classification": "COMPETITION_PROTOTYPE_BASELINE_CANDIDATE",
            "authorized_action": "REFERENCE_IMMUTABLE_P9_SIDE_SLDASM_IN_TOP_LEVEL_INTEGRATION",
            "authorization_mode": "IMMUTABLE_ATTEMPT_TREE_IN_PLACE_REFERENCE_ONLY",
            "attempt_tree_authorized_in_place": True,
            "copy_performed": False,
            "copy_required": False,
            "cad_write_performed": False,
            "configuration_owner": "SIDE_SLDASM_ONLY",
            "top_level_second_driver": "PROHIBITED",
            "top_level_side_occurrence_solving": "RIGID",
            "top_level_allowed_operation": "SELECT_REFERENCED_CONFIGURATION_ONLY",
        },
        "inputs": evidence["inputs"],
        "input_commitment_sha256": canonical_digest(input_commitment),
        "authority_bundle": evidence["authority_bundle"],
        "root_flip_evidence": evidence["root_flip_evidence"],
        "process_separation": evidence["process_separation"],
        "zero_mutation": evidence["zero_mutation"],
        "configuration_contract": {
            "configuration_owner": "SIDE_SLDASM_ONLY",
            "top_level_second_driver": "PROHIBITED",
            "exact_configuration_count_each_side": 7,
            "exact_configurations_authority_order": STATE_NAMES,
            "state_angles_deg": evidence["state_angles_deg"],
            "module_configuration_contract": "DEFAULT_ONLY_NO_SOLAR_STATE_CONFIGURATIONS",
        },
        "side_assemblies": evidence["side_assemblies"],
        "cad_baseline": {
            "counts": evidence["cad_artifact_counts"],
            "artifacts": evidence["cad_artifacts"],
            "artifact_set_sha256": evidence["cad_artifact_set_sha256"],
        },
        "immutable_attempt_tree": {
            "authorized_in_place": True,
            "reference_only": True,
            "copy_performed": False,
            "must_remain_hash_identical_to_this_commit": True,
            "file_count": evidence["attempt_tree_file_count"],
            "tree_sha256": evidence["attempt_tree_sha256"],
            "files": evidence["attempt_tree_files"],
        },
        "live_reference_policy": {
            "old_single_panel_live_use": "PROHIBITED",
            "old_single_panel_reintroduced": False,
            "old_root_single_panel_assemblies": "WITNESS_ONLY_NOT_LIVE",
            "authorized_live_side_assemblies": [item["path"] for item in evidence["side_assemblies"]],
        },
        "claims": {
            "logical_promotion_complete": True,
            "native_solar_38_parts_6_modules_2_sides_verified": True,
            "fresh_pid_read_only_zero_mutation_verified": True,
            "accepted_b601_urdf_unchanged": True,
            "l0_mass_inertia_truth_modified": False,
            "top_level_integration_complete": False,
            "native_clearance_complete": False,
            "camera_visibility_complete": False,
            "harness_sweep_complete": False,
            "drawing_bom_pack_and_go_complete": False,
            "cold_reopen_release_complete": False,
            "full_native_mechanical_baseline_closed": False,
            "flight_ready": False,
            "launch_qualified": False,
        },
        "remaining_holds": [
            "TOP_LEVEL_INTEGRATION_PENDING",
            "ARM_SOLAR_ARM_BUS_CAMERA_SOLAR_HARNESS_SOLAR_NATIVE_CLEARANCE_PENDING",
            "DRAWING_BOM_PACK_AND_GO_COLD_REOPEN_HASH_RELEASE_PENDING",
            "LAUNCH_LOAD_HOLD",
            "THERMAL_VACUUM_HOLD",
            "RANDOM_VIBRATION_HOLD",
            "FORMAL_FASTENER_MOS_HOLD",
        ],
    }


def target_path() -> Path:
    return Path(__file__).resolve().parent.parent / "13_validation" / "V5_SOLAR_R2B_LOGICAL_PROMOTION_COMMIT.json"


def create_exclusive(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    require(path.parent.is_dir(), f"target parent directory missing: {path.parent}")
    require(not path.exists(), f"write-once promotion target already exists: {path}")

    # Full pre-serialization occurs before O_EXCL creates the target.
    serialized = canonical_json_bytes(payload, pretty=True)
    reparsed = json.loads(serialized.decode("utf-8"))
    require(reparsed == payload, "pre-serialized payload did not round-trip exactly")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(path, flags, 0o444)
    try:
        view = memoryview(serialized)
        written = 0
        while written < len(serialized):
            count = os.write(fd, view[written:])
            require(count > 0, "zero-byte write while creating promotion target")
            written += count
        os.fsync(fd)
    finally:
        os.close(fd)
    fact = file_fact(path)
    require(fact["bytes"] == len(serialized), "created target byte count differs from pre-serialized payload")
    require(fact["sha256"] == sha256_bytes(serialized), "created target hash differs from pre-serialized payload")
    return fact


def audit_mode() -> dict[str, Any]:
    target = target_path().resolve()
    evidence = collect_and_validate()
    require(not target.exists(), f"audit-for-create requires absent write-once target: {target}")
    return {
        "mode": "audit",
        "ready_for_exclusive_create": True,
        "schema_to_create": SCHEMA,
        "verdict_to_create": VERDICT,
        "target": target.as_posix(),
        "target_absent": True,
        "producer": evidence["producer"],
        "attempt_root": evidence["attempt_root"],
        "attempt_tree_file_count": evidence["attempt_tree_file_count"],
        "attempt_tree_sha256": evidence["attempt_tree_sha256"],
        "cad_counts": evidence["cad_artifact_counts"],
        "cad_artifact_set_sha256": evidence["cad_artifact_set_sha256"],
        "build_pid": evidence["process_separation"]["build_pid"],
        "fresh_pid": evidence["process_separation"]["fresh_pid"],
        "cad_write_calls": evidence["zero_mutation"]["cad_write_calls"],
    }


def create_mode() -> dict[str, Any]:
    target = target_path().resolve()
    evidence = collect_and_validate()
    require(not target.exists(), f"write-once promotion target already exists: {target}")
    payload = build_payload(evidence, now_utc())
    target_fact = create_exclusive(target, payload)
    return {
        "mode": "create",
        "created": True,
        "schema": payload["schema"],
        "verdict": payload["verdict"],
        "target": target_fact,
        "input_commitment_sha256": payload["input_commitment_sha256"],
        "attempt_tree_sha256": payload["immutable_attempt_tree"]["tree_sha256"],
        "cad_artifact_set_sha256": payload["cad_baseline"]["artifact_set_sha256"],
    }


def verify_mode() -> dict[str, Any]:
    target = target_path().resolve()
    require(target.is_file(), f"promotion target missing: {target}")
    before = file_fact(target)
    payload = load_json(target, "logical promotion target")
    require(payload.get("schema") == SCHEMA, "promotion target schema mismatch")
    require(payload.get("verdict") == VERDICT, "promotion target verdict mismatch")
    evidence = collect_and_validate()
    expected = build_payload(evidence, payload.get("timestamp_utc"))
    require(payload == expected, "promotion target differs from independently reconstructed expected payload")
    after = file_fact(target)
    require(before == after, "promotion target changed during read-only verification")
    require(payload.get("promotion_scope", {}).get("copy_performed") is False, "promotion target claims a copy")
    require(payload.get("promotion_scope", {}).get("cad_write_performed") is False, "promotion target claims a CAD write")
    return {
        "mode": "verify",
        "verified": True,
        "schema": payload["schema"],
        "verdict": payload["verdict"],
        "target": after,
        "input_commitment_sha256": payload["input_commitment_sha256"],
        "attempt_tree_sha256": payload["immutable_attempt_tree"]["tree_sha256"],
        "cad_artifact_set_sha256": payload["cad_baseline"]["artifact_set_sha256"],
        "cad_file_count": payload["cad_baseline"]["counts"]["total"],
        "configuration_owner": payload["configuration_contract"]["configuration_owner"],
        "top_level_second_driver": payload["configuration_contract"]["top_level_second_driver"],
        "copy_performed": payload["promotion_scope"]["copy_performed"],
        "cad_write_performed": payload["promotion_scope"]["cad_write_performed"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("audit", "create", "verify"))
    args = parser.parse_args()
    try:
        if args.mode == "audit":
            result = audit_mode()
        elif args.mode == "create":
            result = create_mode()
        else:
            result = verify_mode()
    except Exception as exc:
        error = {
            "mode": args.mode,
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "target": target_path().resolve().as_posix(),
        }
        sys.stderr.write(json.dumps(error, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n")
        return 2
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
