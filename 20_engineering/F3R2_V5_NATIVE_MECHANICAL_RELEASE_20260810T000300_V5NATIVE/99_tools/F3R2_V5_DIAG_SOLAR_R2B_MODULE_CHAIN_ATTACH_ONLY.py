#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R2B-A exact-architecture SOLIDWORKS module-chain microfixture.

This is a diagnostic, write-once two-process transaction.  ``audit`` is pure
filesystem inspection.  ``build-stage`` attaches to one explicitly named,
document-empty SW2024 SP5 process and writes only below
``99_tools/probe_logs``.  It creates a fixed root equivalent, three rigid
child-module SLDASM documents, and a parent three-hinge serial-chain SLDASM.
The root, H12 and H23 joints each contain a concentric mate, an axial
coincident mate, and a native advanced 0..90 degree angle mate.  Seven native
configurations receive typed per-configuration IDimension values and exact
R2B-A rigid-module poses.

``fresh-verify`` must attach to a different, later-created, document-empty
SOLIDWORKS PID.  It opens every CAD document read-only, performs zero mutation
calls, re-reads the seven configuration tuples, nested face/mate references,
and native B-rep interference, and emits the sole PASS receipt.  No production
CAD or release path is written by this script.  A failed attempt is immutable;
retry requires a new run id.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import re
import sys
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


sys.dont_write_bytecode = True

ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
TOOLS = RUN_ROOT / "99_tools"
PROBE_ROOT = TOOLS / "probe_logs"
L1B_HELPER = TOOLS / "F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY.py"
AUTHORITY = RUN_ROOT / "00_authority/V5_SOLAR_STATE_AUTHORITY_R2B.json"
ARCHITECTURE = RUN_ROOT / "00_authority/V5_SOLAR_R2_ASSEMBLY_ARCHITECTURE_DECISION.json"
ORACLE = RUN_ROOT / "13_validation/V5_SOLAR_R2B_STATIC_KINEMATIC_ORACLE_20260812T181333.205056Z.json"
AUTHORIZATION = RUN_ROOT / "13_validation/V5_SOLAR_R2B_BUILD_AUTHORIZATION.json"
BRANCH_PROBE_SCRIPT = TOOLS / "F3R2_V5_DIAG_SOLAR_R2B_ROOT_BRANCH_PROBE_ATTACH_ONLY.py"
BRANCH_MATRIX_RESULT = PROBE_ROOT / "V5_SOLAR_R2B_ROOT_BRANCH_20260813T1232Z_BRANCH1/RESULT.json"
ROOT_FLIP_AUTHORIZATION_SOURCE = TOOLS / "F3R2_V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZE.py"
ROOT_FLIP_AUTHORIZATION_RECEIPT = RUN_ROOT / "13_validation/V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_V1.json"
PART_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_part.prtdot")
ASSEMBLY_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_assembly.asmdot")

PINNED = {
    L1B_HELPER: "32BC06FC6A1EFCD6426FE4608D03EABCBD2902CBA228E95B2AD7A91B4E0F283F",
    AUTHORITY: "BA639C6BF4F0875B6FD9AFFF2E6CA7A5AA3BA1AF77C6BD5FEC07A8EB62D8E6D8",
    ARCHITECTURE: "3CC38465A6B7FA6E91F275BAE4052E1787B5A44A6F196AFCEFA88AA7D209D545",
    ORACLE: "F4E5E0CD5A8559991B60826C6221294948CD07889836500D81527AE0982196F6",
    AUTHORIZATION: "BAD16D48EAEDCF27B3953831B7108A4ADB95CC3DD8F476FB02CB29EAE454FCCB",
    BRANCH_PROBE_SCRIPT: "3680D614AD10728FC54309D4E8CFC64DB518FA3864989F86B968ED45E119FFE8",
    BRANCH_MATRIX_RESULT: "52FF2A64E874FD782008E5971CB3154C976E10068C994337CB0611195E97A77A",
    ROOT_FLIP_AUTHORIZATION_SOURCE: "A05E0492CEB5CB6D9A7710BFEB4D04EE9FC1F3E5F54EA51B3360A64B01175726",
    ROOT_FLIP_AUTHORIZATION_RECEIPT: "07D3D9380668E0308981D0BF85D4EB0951789793F90EAB97503BB23C82C7280E",
    PART_TEMPLATE: "5DA21678EFE07EF465770630BEB4FFE540F23D47FCA07715F74D2AFDBEA87271",
    ASSEMBLY_TEMPLATE: "37DED9268BABC616A97BF9DA29BDCC2FFD60E8E4353670748F74A18A3BB450CC",
}

sys.path.insert(0, str(TOOLS))
import F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY as L1B  # noqa: E402


SW_DOC_PART = 1
SW_DOC_ASSEMBLY = 2
SW_MATE_COINCIDENT = 0
SW_MATE_CONCENTRIC = 1
SW_MATE_ANGLE = 6
SW_ALIGN_ALIGNED = 0
SW_ALIGN_CLOSEST = 2
SW_SET_VALUE_IN_SPECIFIC_CONFIGS = 3
SW_SET_VALUE_SUCCESS = 0
HINGE_LOWER_RAD = 0.0
HINGE_UPPER_RAD = math.pi / 2.0
TRANS_TOL = 2.0e-7
ANGLE_TOL_RAD = 2.0e-6
POSITIVE_VOLUME_TOL_MM3 = 1.0e-6
EXPECTED_PRODUCTION_BUILDER_SHA256 = "E5255A4BE587C43F0C237367E0B2C90E2AF8C66F230A9C630B4D596922F96C4C"
EXPECTED_PRODUCTION_CONTRACT_SHA256 = "B885E6B4F51663DC268FE6C9F5E497B99A514BE1706B616C230D5D35A2D697FB"
EXPECTED_ROOT_FLIP_AUTHORIZATION_SOURCE_SHA256 = "A05E0492CEB5CB6D9A7710BFEB4D04EE9FC1F3E5F54EA51B3360A64B01175726"
EXPECTED_ROOT_FLIP_AUTHORIZATION_RECEIPT_SHA256 = "07D3D9380668E0308981D0BF85D4EB0951789793F90EAB97503BB23C82C7280E"
EXPECTED_ROOT_FLIP_EVIDENCE_CHAIN_SHA256 = "316A433EF215A38A7E090E0AE88E3E6362D6079B25ACBB01596C810CD2790889"
RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
STATES = (
    "SOLAR_STOWED",
    "SOLAR_DEPLOY_STAGE1",
    "SOLAR_DEPLOY_STAGE2",
    "SOLAR_DEPLOYED_NOMINAL",
    "SOLAR_LEFT_FAIL",
    "SOLAR_RIGHT_FAIL",
    "SOLAR_BOTH_FAIL",
)
LEFT_TUPLES = {
    "SOLAR_STOWED": (0.0, 0.0, 0.0),
    "SOLAR_DEPLOY_STAGE1": (90.0, 0.0, 0.0),
    "SOLAR_DEPLOY_STAGE2": (90.0, 90.0, 0.0),
    "SOLAR_DEPLOYED_NOMINAL": (90.0, 90.0, 90.0),
    "SOLAR_LEFT_FAIL": (0.0, 0.0, 0.0),
    "SOLAR_RIGHT_FAIL": (90.0, 90.0, 90.0),
    "SOLAR_BOTH_FAIL": (0.0, 0.0, 0.0),
}
HINGE_NAMES = ("ROOT", "H12", "H23")
# The diagnostic root is a simplified ROOT_EQUIVALENT primitive.  Its LEFT
# ROOT branch is intentionally True and is not the production clevis branch.
FIXTURE_LEFT_ANGLE_FLIP = {"ROOT": True, "H12": False, "H23": True}
PRODUCTION_ANGLE_FLIP = {
    "L": {"ROOT": False, "H12": False, "H23": True},
    "R": {"ROOT": True, "H12": True, "H23": False},
}
PRE_AUTHORIZATION_PRODUCTION_ANGLE_FLIP = {
    "L": {"ROOT": True, "H12": False, "H23": True},
    "R": {"ROOT": False, "H12": True, "H23": False},
}
MODULE_KEYS = ("M1", "M2", "M3")
PITCH_MM = 56.666666666666664
ROOT_Y_MM = 143.15
X_START_MM = -12.0
X_DEPTH_MM = 12.0
PIN_RADIUS_MM = 2.0
BORE_RADIUS_MM = 2.2


class GateError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Mapping[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.detail = dict(detail or {})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_fact(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise GateError("FILE_MISSING", "required file is absent", {"path": norm(path)})
    return {"path": norm(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def is_under(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    base = root.resolve()
    return resolved == base or base in resolved.parents


def assert_probe_path(path: Path, allow_root: bool = False) -> Path:
    resolved = path.resolve()
    if not is_under(resolved, PROBE_ROOT) or (resolved == PROBE_ROOT.resolve() and not allow_root):
        raise GateError("WRITE_SCOPE_ESCAPE", "path escapes diagnostic probe root", {"path": norm(path)})
    return resolved


def attempt_root(run_id: str) -> Path:
    if not RUN_ID_RE.fullmatch(run_id) or run_id in {".", ".."}:
        raise GateError("RUN_ID_INVALID", "run id is not a safe single path token", {"run_id": run_id})
    return assert_probe_path(PROBE_ROOT / f"V5_SOLAR_R2B_MODULE_CHAIN_{run_id}")


def write_text_once(path: Path, text: str) -> None:
    assert_probe_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def write_json_once(path: Path, payload: Mapping[str, Any]) -> None:
    write_text_once(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def acquire_process_mutex() -> Any:
    import ctypes

    kernel = ctypes.windll.kernel32
    handle = kernel.CreateMutexW(None, False, "Local\\F3R2_V5_SOLAR_R2B_MODULE_CHAIN_ATTACH_ONLY")
    if not handle:
        raise GateError("MUTEX_CREATE_FAIL", "cannot create diagnostic exclusive-process mutex")
    status = int(kernel.WaitForSingleObject(handle, 0))
    if status not in (0x00000000, 0x00000080):
        kernel.CloseHandle(handle)
        raise GateError("MUTEX_BUSY", "another R2B module-chain build/verify owns the exclusive mutex", {"wait_status": status})
    return handle


def release_process_mutex(handle: Any) -> None:
    if handle:
        import ctypes

        ctypes.windll.kernel32.ReleaseMutex(handle)
        ctypes.windll.kernel32.CloseHandle(handle)


def read_json(path: Path) -> Dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GateError("JSON_OBJECT_FAIL", "JSON root is not an object", {"path": norm(path)})
    return value


def digest_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def root_role_separation_fact() -> Dict[str, Any]:
    return {
        "schema": "F3R2_V5_SOLAR_R2B_FIXTURE_PRODUCTION_ROOT_SEPARATION_V1",
        "diagnostic_fixture_root": {
            "geometry": "MF_R2B_ROOT_EQUIVALENT.SLDPRT",
            "role": "DIAGNOSTIC_ROOT_EQUIVALENT_NON_RELEASE",
            "side": "LEFT_ONLY",
            "root_flip": True,
            "production_root_authority": False,
            "production_use": "PROHIBITED",
        },
        "production_root": {
            "geometry": "ACCEPTED_CLEVIS_TO_P1_MODULE",
            "role": "PRODUCTION_ROOT_LIMIT_ANGLE",
            "per_side_flip": {side: dict(values) for side, values in PRODUCTION_ANGLE_FLIP.items()},
            "authority": "HASH_BOUND_ROOT_FLIP_AUTHORIZATION_RECEIPT_ONLY",
        },
        "invariants": {
            "fixture_left_root_flip_remains_true": FIXTURE_LEFT_ANGLE_FLIP["ROOT"] is True,
            "production_left_root_flip_is_false": PRODUCTION_ANGLE_FLIP["L"]["ROOT"] is False,
            "fixture_root_must_not_be_treated_as_production_root": True,
            "diagnostic_cad_promotion_authorized": False,
        },
    }


def production_root_flip_authorization_gate() -> Dict[str, Any]:
    source_fact = file_fact(ROOT_FLIP_AUTHORIZATION_SOURCE)
    receipt_fact = file_fact(ROOT_FLIP_AUTHORIZATION_RECEIPT)
    payload = read_json(ROOT_FLIP_AUTHORIZATION_RECEIPT)
    patch = payload.get("authorized_patch", {})
    claims = payload.get("claims", {})
    lineage = payload.get("lineage", {})
    expected_changed = [
        {"side": "L", "joint": "ROOT", "before": True, "after": False},
        {"side": "R", "joint": "ROOT", "before": False, "after": True},
    ]
    expected_unchanged = [
        {"side": side, "joint": joint, "value": PRE_AUTHORIZATION_PRODUCTION_ANGLE_FLIP[side][joint]}
        for side in ("L", "R")
        for joint in ("H12", "H23")
    ]
    digest_payload = {
        "lineage": lineage,
        "failure_signature": payload.get("p5_failure_lineage", {}).get("failure_signature"),
        "winner_summary": payload.get("production_root_probe_validation", {}).get("winner_summary"),
        "authorized_patch": patch,
    }
    computed_digest = digest_json(digest_payload)
    checks = {
        "source_hash": source_fact["sha256"] == EXPECTED_ROOT_FLIP_AUTHORIZATION_SOURCE_SHA256,
        "receipt_hash": receipt_fact["sha256"] == EXPECTED_ROOT_FLIP_AUTHORIZATION_RECEIPT_SHA256,
        "schema": payload.get("schema") == "F3R2_V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_V1",
        "verdict": payload.get("verdict") == "V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_PATCH_ONLY_AUTHORIZED",
        "classification": payload.get("classification") == "ENGINEERING_EVIDENCE_BRIDGE__PATCH_AUTHORIZATION_ONLY",
        "scope": payload.get("scope") == "V5_NATIVE_FINALIZATION/MULTI_PANEL_SOLAR_ARRAY_CANDIDATE/ROOT_LIMIT_ANGLE_BRANCH",
        "producer": payload.get("producer") == source_fact and lineage.get("producer") == source_fact,
        "evidence_digest": payload.get("evidence_chain_sha256") == EXPECTED_ROOT_FLIP_EVIDENCE_CHAIN_SHA256 and computed_digest == EXPECTED_ROOT_FLIP_EVIDENCE_CHAIN_SHA256,
        "before_flip_map": patch.get("before") == PRE_AUTHORIZATION_PRODUCTION_ANGLE_FLIP,
        "after_flip_map": patch.get("after") == PRODUCTION_ANGLE_FLIP,
        "root_only_changes": patch.get("authorization_scope") == "PRODUCTION_ROOT_LIMIT_ANGLE_FLIP_ONLY" and patch.get("changed_cells") == expected_changed,
        "h12_h23_unchanged": patch.get("unchanged_cells") == expected_unchanged and "H12_OR_H23_FLIP" in patch.get("prohibited_changes", []),
        "fixture_root_separation": patch.get("fixture_root_note") == "ROOT_EQUIVALENT_MICROFIXTURE_FLIP_IS_FIXTURE_LOCAL_AND_MUST_NOT_BE_MECHANICALLY_REPLACED_BY_THE_PRODUCTION_CLEVIS_FLIP",
        "rebuild_and_fresh_required": patch.get("post_patch_build_required") is True and patch.get("different_pid_read_only_fresh_verification_required") is True,
        "no_promotion": patch.get("promotion_authorized") is False and "DIAGNOSTIC_CAD_PROMOTION" in patch.get("prohibited_changes", []),
        "zero_mutation_authorization": claims.get("solidworks_touched") is False and claims.get("cad_write_calls") == 0 and claims.get("cad_files_mutated") == 0 and claims.get("probe_history_modified") is False,
        "diagnostic_production_use_prohibited": claims.get("diagnostic_cad_production_use") == "PROHIBITED" and claims.get("promotion_authorized") is False,
        "fixture_map_stays_diagnostic": FIXTURE_LEFT_ANGLE_FLIP == {"ROOT": True, "H12": False, "H23": True},
        "production_map_is_distinct": PRODUCTION_ANGLE_FLIP["L"]["ROOT"] is False and FIXTURE_LEFT_ANGLE_FLIP["ROOT"] is True,
    }
    if not all(checks.values()):
        raise GateError(
            "ROOT_FLIP_AUTHORIZATION_GATE_FAIL",
            "production ROOT authorization or diagnostic-fixture separation differs from the frozen evidence chain",
            {"checks": checks, "computed_evidence_chain_sha256": computed_digest},
        )
    return {
        "source": source_fact,
        "receipt": receipt_fact,
        "schema": payload["schema"],
        "verdict": payload["verdict"],
        "evidence_chain_sha256": payload["evidence_chain_sha256"],
        "authorized_production_flip": {side: dict(values) for side, values in PRODUCTION_ANGLE_FLIP.items()},
        "fixture_left_flip": dict(FIXTURE_LEFT_ANGLE_FLIP),
        "root_role_separation": root_role_separation_fact(),
        "checks": checks,
    }


def script_policy_audit() -> Dict[str, Any]:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = []
    fixture_angle_function_names: Dict[str, List[str]] = {}
    parents: Dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = None
        if isinstance(node.func, ast.Attribute):
            name = node.func.attr
        elif isinstance(node.func, ast.Name):
            name = node.func.id
        if name in {"Dispatch", "DispatchEx", "CoCreateInstance", "KillDoc", "ExitApp", "SetTransformAndSolve3", "SetSystemValue3", "Save3", "SaveAs"}:
            # Mutation APIs are permitted only in named build helpers.  The
            # fresh verifier is checked separately below for a zero call set.
            owner = ""
            cursor: ast.AST = node
            while cursor in parents:
                cursor = parents[cursor]
                if isinstance(cursor, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    owner = cursor.name
                    break
            if owner.startswith("fresh_") and name not in {""}:
                forbidden.append({"line": node.lineno, "api": name, "owner": owner})
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {"add_limit_angle", "angle_definition_fact"}:
            fixture_angle_function_names[node.name] = sorted({child.id for child in ast.walk(node) if isinstance(child, ast.Name)})
    fresh_source = source[source.index("def fresh_verify("): source.index("def parser(")]
    mutation_tokens = (
        "SetTransformAndSolve3(", "SetSystemValue3(", "Save3(", ".SaveAs(",
        "AddComponent", "AddMate", "AddConfiguration", "Delete", "EditDelete",
        "ForceRebuild3(",
    )
    lexical_hits = [token for token in mutation_tokens if token in fresh_source]
    fixture_angle_functions_use_fixture_map_only = (
        set(fixture_angle_function_names) == {"add_limit_angle", "angle_definition_fact"}
        and all("FIXTURE_LEFT_ANGLE_FLIP" in names and "PRODUCTION_ANGLE_FLIP" not in names for names in fixture_angle_function_names.values())
    )
    return {
        "ast_fresh_forbidden_calls": forbidden,
        "fresh_lexical_mutation_hits": lexical_hits,
        "fresh_verifier_zero_mutation_policy": not forbidden and not lexical_hits,
        "fixture_angle_function_names": fixture_angle_function_names,
        "fixture_angle_functions_use_fixture_map_only": fixture_angle_functions_use_fixture_map_only,
    }


def static_audit(run_id: Optional[str] = None, production_builder: Optional[Path] = None, require_final_builder: bool = False) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    for path, expected in PINNED.items():
        actual = sha256(path) if path.is_file() else None
        checks.append({"check": f"pinned_{path.name}", "pass": actual == expected, "path": norm(path), "expected_sha256": expected, "actual_sha256": actual})
    authority = read_json(AUTHORITY) if AUTHORITY.is_file() else {}
    checks.append({
        "check": "authority_exact_seven_tuple_contract",
        "pass": tuple(authority.get("states", {})) == STATES and all(tuple(authority["states"][name]["LEFT"]) == LEFT_TUPLES[name] for name in STATES),
    })
    checks.append({
        "check": "r2b_geometry_contract",
        "pass": authority.get("candidate_geometry", {}).get("serial_fk_candidate", {}).get("variant") == "R2B_A_90_DEG_ORTHOGONAL_ZIGZAG"
        and authority.get("candidate_geometry", {}).get("interpanel_pin_diameter_mm") == 4.0
        and authority.get("candidate_geometry", {}).get("interpanel_bore_diameter_mm") == 4.4
        and authority.get("candidate_geometry", {}).get("interpanel_collar_outer_diameter_max_mm") == 5.5
        and authority.get("candidate_geometry", {}).get("panel_structure_edge_contract", {}).get("interpanel_edge_relief_mm") == 3.5,
    })
    branch = read_json(BRANCH_MATRIX_RESULT) if BRANCH_MATRIX_RESULT.is_file() else {}
    branch_rows = [
        row for row in branch.get("cases", [])
        if row.get("requested_alignment") == SW_ALIGN_ALIGNED
        and row.get("swap_selection_order") is False
        and float(row.get("angle_deg", -1.0)) in {1.0, 89.0, 90.0}
        and row.get("requested_flip") in {False, True}
    ]
    branch_by_key = {(float(row["angle_deg"]), bool(row["requested_flip"])): row for row in branch_rows}
    branch_semantic_pass = (
        branch.get("schema") == "F3R2_V5_SOLAR_R2B_ROOT_BRANCH_MATRIX_V1"
        and branch.get("verdict") == "V5_SOLAR_R2B_ROOT_BRANCH_MATRIX_COMPLETE"
        and branch.get("case_count_planned") == 24
        and branch.get("case_count_complete") == 24
        and len(branch.get("cases", [])) == 24
        and len(branch_by_key) == 6
    )
    for angle_deg in (1.0, 89.0, 90.0):
        for flip in (False, True):
            row = branch_by_key.get((angle_deg, flip), {})
            final_mate = row.get("final_mate_readback", {})
            expected_branch = "NEGATIVE_EXPECTED" if flip else "POSITIVE_MIRROR"
            expected_rx = -angle_deg if flip else angle_deg
            branch_semantic_pass = branch_semantic_pass and (
                row.get("case_complete") is True
                and row.get("restored_branch") == expected_branch
                and final_mate.get("alignment") == SW_ALIGN_ALIGNED
                and final_mate.get("flipped") is flip
                and abs(float(row.get("pose_after_restore", {}).get("signed_rx_deg", 1.0e9)) - expected_rx) <= 1.0e-6
            )
    checks.append({
        "check": "branch_matrix_fixed_parent_child_flip_truth",
        "pass": bool(branch_semantic_pass),
        "branch_probe_script": file_fact(BRANCH_PROBE_SCRIPT) if BRANCH_PROBE_SCRIPT.is_file() else None,
        "branch_matrix_result": file_fact(BRANCH_MATRIX_RESULT) if BRANCH_MATRIX_RESULT.is_file() else None,
        "fixed_selection_order": "PARENT_TO_CHILD_ROOT_FIRST",
        "fixed_alignment": SW_ALIGN_ALIGNED,
        "fixture_left_per_hinge_flip": dict(FIXTURE_LEFT_ANGLE_FLIP),
        "scope": "DIAGNOSTIC_ROOT_EQUIVALENT_ONLY",
        "evidence_rows": [
            {
                "angle_deg": row.get("angle_deg"),
                "requested_flip": row.get("requested_flip"),
                "restored_branch": row.get("restored_branch"),
                "signed_rx_deg": row.get("pose_after_restore", {}).get("signed_rx_deg"),
                "stored_alignment": row.get("final_mate_readback", {}).get("alignment"),
                "stored_flip": row.get("final_mate_readback", {}).get("flipped"),
            }
            for row in sorted(branch_rows, key=lambda item: (float(item["angle_deg"]), bool(item["requested_flip"])))
        ],
    })
    root_authorization: Optional[Dict[str, Any]] = None
    root_authorization_error: Optional[Dict[str, Any]] = None
    try:
        root_authorization = production_root_flip_authorization_gate()
    except Exception as exc:
        root_authorization_error = {
            "error_code": getattr(exc, "code", "UNHANDLED_EXCEPTION"),
            "error": str(exc),
            "detail": getattr(exc, "detail", {}),
        }
    checks.append({
        "check": "production_root_authorization_and_fixture_root_separation",
        "pass": root_authorization is not None,
        "authorization": root_authorization,
        "error": root_authorization_error,
    })
    policy = script_policy_audit()
    checks.append({"check": "fresh_verifier_zero_mutation_source_policy", "pass": policy["fresh_verifier_zero_mutation_policy"], **policy})
    checks.append({
        "check": "diagnostic_angle_functions_use_fixture_map_only",
        "pass": policy["fixture_angle_functions_use_fixture_map_only"],
        "fixture_left_flip": dict(FIXTURE_LEFT_ANGLE_FLIP),
        "authorized_production_flip": {side: dict(values) for side, values in PRODUCTION_ANGLE_FLIP.items()},
        "root_role_separation": root_role_separation_fact(),
    })
    builder_fact = None
    if production_builder is not None:
        builder = production_builder.resolve()
        permitted = builder.is_file() and builder.parent == TOOLS.resolve() and builder.name.endswith(".py") and builder != Path(__file__).resolve()
        checks.append({"check": "production_builder_is_existing_tools_script", "pass": permitted, "path": norm(builder)})
        if permitted:
            builder_fact = file_fact(builder)
            builder_check = {
                "check": "production_builder_final_sha256",
                "pass": builder_fact["sha256"] == EXPECTED_PRODUCTION_BUILDER_SHA256,
                "expected_sha256": EXPECTED_PRODUCTION_BUILDER_SHA256,
                "actual_sha256": builder_fact["sha256"],
                "contract_sha256_prefix": EXPECTED_PRODUCTION_CONTRACT_SHA256,
                "required_for_execution": require_final_builder,
            }
            if require_final_builder:
                checks.append(builder_check)
            else:
                builder_check["pass"] = True
                builder_check["note"] = "informational in audit; build-stage/fresh-verify require the frozen final hash"
                checks.append(builder_check)
    target = None
    if run_id is not None:
        target = attempt_root(run_id)
        checks.append({"check": "attempt_write_once", "pass": not target.exists(), "path": norm(target)})
        for relative in planned_relatives():
            assert_probe_path(target / relative)
    passed = all(row["pass"] for row in checks)
    return {
        "schema": "F3R2_V5_DIAG_SOLAR_R2B_MODULE_CHAIN_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "script": file_fact(Path(__file__)),
        "production_builder": builder_fact,
        "production_contract_sha256": EXPECTED_PRODUCTION_CONTRACT_SHA256,
        "production_root_flip_authorization": root_authorization,
        "root_role_separation": root_role_separation_fact(),
        "run_id": run_id,
        "attempt_root": norm(target) if target else None,
        "checks": checks,
        "solidworks_touched": False,
        "execution_authorized": passed,
        "verdict": "V5_SOLAR_R2B_MODULE_CHAIN_STATIC_PASS" if passed else "V5_SOLAR_R2B_MODULE_CHAIN_STATIC_HOLD",
    }


def planned_relatives() -> Tuple[Path, ...]:
    return (
        Path("cad/parts/MF_R2B_ROOT_EQUIVALENT.SLDPRT"),
        Path("cad/parts/MF_R2B_M1_BODY.SLDPRT"),
        Path("cad/parts/MF_R2B_M2_BODY.SLDPRT"),
        Path("cad/parts/MF_R2B_M3_BODY.SLDPRT"),
        Path("cad/parts/MF_R2B_M1_INBOARD_COLLAR.SLDPRT"),
        Path("cad/parts/MF_R2B_M2_INBOARD_COLLAR.SLDPRT"),
        Path("cad/parts/MF_R2B_M3_INBOARD_COLLAR.SLDPRT"),
        Path("cad/parts/MF_R2B_M1_OUTBOARD_PIN.SLDPRT"),
        Path("cad/parts/MF_R2B_M2_OUTBOARD_PIN.SLDPRT"),
        Path("cad/modules/MF_R2B_MODULE_M1.SLDASM"),
        Path("cad/modules/MF_R2B_MODULE_M2.SLDASM"),
        Path("cad/modules/MF_R2B_MODULE_M3.SLDASM"),
        Path("cad/MF_R2B_THREE_MODULE_CHAIN.SLDASM"),
        Path("BUILD_STAGE_RECEIPT.json"),
        Path("F3R2_V5_SOLAR_R2B_MODULE_CHAIN_MICROFIXTURE_RECEIPT.json"),
    )


def rx_about_y(angle_deg: float, axis_y_mm: float) -> List[float]:
    angle = math.radians(angle_deg)
    c, s = math.cos(angle), math.sin(angle)
    ay = axis_y_mm / 1000.0
    return [1.0, 0.0, 0.0, 0.0, c, s, 0.0, -s, c, 0.0, ay * (1.0 - c), -ay * s, 1.0, 0.0, 0.0, 0.0]


def mmul_transform(first: Sequence[float], second: Sequence[float]) -> List[float]:
    # SolidWorks ArrayData follows row-vector storage as used by the proven
    # Loop1B helpers.  Compose via explicit point/basis mapping.
    def apply(t: Sequence[float], p: Sequence[float], vector: bool = False) -> List[float]:
        return [
            t[0] * p[0] + t[3] * p[1] + t[6] * p[2] + (0.0 if vector else t[9]),
            t[1] * p[0] + t[4] * p[1] + t[7] * p[2] + (0.0 if vector else t[10]),
            t[2] * p[0] + t[5] * p[1] + t[8] * p[2] + (0.0 if vector else t[11]),
        ]
    basis = [apply(first, apply(second, axis, True), True) for axis in ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0])]
    origin = apply(first, apply(second, [0.0, 0.0, 0.0]))
    return [basis[0][0], basis[0][1], basis[0][2], basis[1][0], basis[1][1], basis[1][2], basis[2][0], basis[2][1], basis[2][2], origin[0], origin[1], origin[2], 1.0, 0.0, 0.0, 0.0]


def state_transforms(angles: Sequence[float]) -> Dict[str, List[float]]:
    a1, a2, a3 = (float(value) for value in angles)
    phi = [a1 - 90.0, 0.0, 0.0]
    phi[1] = phi[0] + (90.0 - a2)
    phi[2] = phi[1] - (90.0 - a3)
    q_in = -PITCH_MM / 2.0
    q_out = PITCH_MM / 2.0

    def rotate_yz(angle_deg: float, vector: Sequence[float]) -> List[float]:
        angle = math.radians(angle_deg)
        c, s = math.cos(angle), math.sin(angle)
        return [float(vector[0]), c * float(vector[1]) - s * float(vector[2]), s * float(vector[1]) + c * float(vector[2])]

    centers: List[List[float]] = []
    r0 = rotate_yz(phi[0], [0.0, q_in, 0.0])
    centers.append([0.0, ROOT_Y_MM - r0[1], -r0[2]])
    for index in (1, 2):
        parent_out = rotate_yz(phi[index - 1], [0.0, q_out, 0.0])
        child_in = rotate_yz(phi[index], [0.0, q_in, 0.0])
        centers.append([
            0.0,
            centers[index - 1][1] + parent_out[1] - child_in[1],
            centers[index - 1][2] + parent_out[2] - child_in[2],
        ])

    nominal_centers = [[0.0, ROOT_Y_MM + (index + 0.5) * PITCH_MM, 0.0] for index in range(3)]
    transforms: Dict[str, List[float]] = {}
    for index, key in enumerate(MODULE_KEYS):
        angle = math.radians(phi[index])
        c, s = math.cos(angle), math.sin(angle)
        local = nominal_centers[index]
        rotated_local = [local[0], c * local[1] - s * local[2], s * local[1] + c * local[2]]
        translation_mm = [centers[index][axis] - rotated_local[axis] for axis in range(3)]
        transforms[key] = [
            1.0, 0.0, 0.0,
            0.0, c, s,
            0.0, -s, c,
            translation_mm[0] / 1000.0,
            translation_mm[1] / 1000.0,
            translation_mm[2] / 1000.0,
            1.0, 0.0, 0.0, 0.0,
        ]
    return transforms


def transform_error(actual: Sequence[float], expected: Sequence[float]) -> float:
    return max((abs(float(a) - float(b)) for a, b in zip(actual, expected)), default=float("inf")) if len(actual) == len(expected) == 16 else float("inf")


def unix_time_utc(value: float) -> str:
    if float(value) <= 0.0:
        raise GateError("PROCESS_CREATE_TIME_INVALID", "process create time must be positive", {"value": value})
    return datetime.fromtimestamp(float(value), timezone.utc).isoformat().replace("+00:00", "Z")


def transform_point_mm(transform: Sequence[float], point_mm: Sequence[float]) -> List[float]:
    if len(transform) != 16 or len(point_mm) != 3:
        raise GateError("TRANSFORM_POINT_SHAPE_FAIL", "transform/point shape is invalid")
    x, y, z = (float(value) / 1000.0 for value in point_mm)
    return [
        (transform[0] * x + transform[3] * y + transform[6] * z + transform[9]) * 1000.0,
        (transform[1] * x + transform[4] * y + transform[7] * z + transform[10]) * 1000.0,
        (transform[2] * x + transform[5] * y + transform[8] * z + transform[11]) * 1000.0,
    ]


def select_right_plane(model: Any) -> str:
    return L1B.select_base_plane(model, ("右视基准面", "Right Plane"))


def part_cylinder_signature(model: Any, radius_mm: float, axis_y_mm: float, axis_z_mm: float, types: Any, pythoncom: Any) -> Dict[str, Any]:
    """Read one native X-axis cylindrical face directly from a part B-rep."""
    part = L1B.wrap(model, "IPartDoc", types, pythoncom)
    candidates = []
    for raw_body in L1B.as_list(part.GetBodies2(0, False)):
        body = L1B.wrap(raw_body, "IBody2", types, pythoncom)
        for raw_face in L1B.as_list(L1B.value(body, "GetFaces")):
            face = L1B.wrap(raw_face, "IFace2", types, pythoncom)
            surface = L1B.wrap(L1B.value(face, "GetSurface"), "ISurface", types, pythoncom)
            if not bool(surface.IsCylinder()):
                continue
            params = [float(value) for value in L1B.as_list(L1B.value(surface, "CylinderParams"))]
            if (
                len(params) >= 7
                and abs(abs(params[3]) - 1.0) < 1.0e-5
                and abs(params[4]) < 1.0e-5
                and abs(params[5]) < 1.0e-5
                and abs(params[1] * 1000.0 - axis_y_mm) <= 0.08
                and abs(params[2] * 1000.0 - axis_z_mm) <= 0.08
                and abs(params[6] * 1000.0 - radius_mm) <= 0.06
            ):
                candidates.append((float(L1B.value(face, "GetArea")), params))
    if len(candidates) != 1:
        raise GateError(
            "PART_CYLINDER_SIGNATURE_FAIL",
            "expected one native X-axis cylindrical face in part B-rep",
            {"radius_mm": radius_mm, "axis_y_mm": axis_y_mm, "axis_z_mm": axis_z_mm, "count": len(candidates)},
        )
    area, params = candidates[0]
    return {
        "radius_mm": radius_mm,
        "axis_y_mm": axis_y_mm,
        "axis_z_mm": axis_z_mm,
        "cylinder_params": params,
        "area_mm2": area * 1.0e6,
        "candidate_count": 1,
    }


def create_ring_part(sw: Any, types: Any, pythoncom: Any, target: Path, role: str, center_y_mm: float, outer_radius_mm: float, inner_radius_mm: float, run_id: str) -> Dict[str, Any]:
    if target.exists():
        raise GateError("PART_EXISTS", "write-once diagnostic part exists", {"path": norm(target)})
    model = None
    try:
        model = L1B.new_part(sw, types, pythoncom)
        if abs(X_START_MM) > 1.0e-12:
            L1B.create_offset_plane(model, ("右视基准面", "Right Plane"), X_START_MM, f"MF_R2B_{role}_X_START")
            if not bool(model.Extension.SelectByID2(f"MF_R2B_{role}_X_START", "PLANE", 0.0, 0.0, 0.0, False, 0, None, 0)):
                raise GateError("RING_OFFSET_PLANE_FAIL", "cannot select ring X-start plane", {"role": role})
        else:
            select_right_plane(model)
        sketch = model.SketchManager
        sketch.InsertSketch(True)
        if sketch.CreateCircleByRadius(0.0, center_y_mm / 1000.0, 0.0, outer_radius_mm / 1000.0) is None:
            raise GateError("RING_OUTER_SKETCH_FAIL", "ring outer circle returned null", {"role": role})
        sketch.InsertSketch(True)
        extrusion = model.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, X_DEPTH_MM / 1000.0, 0.0, False, False, False, False, 0.0, 0.0, False, False, False, False, True, True, True, 0, 0.0, False)
        if extrusion is None:
            raise GateError("RING_OUTER_EXTRUSION_FAIL", "ring outer-cylinder extrusion returned null", {"role": role})
        extrusion.Name = f"MF_R2B_{role}_OUTER_EXTRUSION"
        # SW2024 returned null for the first OD5.5/ID4.4 collar when both
        # concentric contours were submitted to FeatureExtrusion2 in one
        # sketch (write-once attempt 20260813T1144Z_G1).  Every preceding
        # single-contour solid in that attempt saved correctly.  Author the
        # identical annulus as two deterministic native features instead:
        # solid outer cylinder, then a blind cut longer than the 12 mm body.
        # This changes neither the B-rep contract nor any hinge datum.
        if inner_radius_mm > 0.0:
            model.ClearSelection2(True)
            # The proven FeatureCut3 direction from a Right-plane sketch is
            # toward -X (Loop1B U-lug bore witness).  The collar occupies
            # X=[-12,0], so sketch the bore on the x=0 Right Plane.  Cutting
            # from the x=-12 boss start plane would point away from the body
            # and correctly returned null in preserved attempt G3.
            plane_name = select_right_plane(model)
            sketch.InsertSketch(True)
            if sketch.CreateCircleByRadius(0.0, center_y_mm / 1000.0, 0.0, inner_radius_mm / 1000.0) is None:
                raise GateError("RING_INNER_SKETCH_FAIL", "ring bore circle returned null", {"role": role})
            sketch.InsertSketch(True)
            cut = model.FeatureManager.FeatureCut3(
                True, False, False, 0, 0, 2.0 * X_DEPTH_MM / 1000.0, 0.0,
                False, False, False, False, 0.0, 0.0,
                False, False, False, False, False, True, True, True, True,
                False, 0, 0.0, False,
            )
            if cut is None:
                raise GateError("RING_BORE_CUT_FAIL", "collar bore cut returned null", {"role": role})
            cut.Name = f"MF_R2B_{role}_BORE_CUT"
        L1B.set_properties(model, {"PartNumber": f"V5-DIAG-R2B-{role}", "ARTIFACT_CLASS": "DIAGNOSTIC_MICROFIXTURE_NON_RELEASE", "PRODUCTION_USE": "PROHIBITED", "RUN_ID": run_id})
        saved = L1B.save_as(model, target)
        body_readback = L1B.body_facts(model, types, pythoncom)
        if body_readback.get("solid_body_count") != 1:
            raise GateError("RING_BODY_COUNT_FAIL", "final ring/pin part is not exactly one native solid", {"role": role, "body_facts": body_readback})
        bore_signature = None
        if inner_radius_mm > 0.0:
            bore_signature = part_cylinder_signature(model, inner_radius_mm, center_y_mm, 0.0, types, pythoncom)
    finally:
        L1B.close_doc(sw, model)
    return {
        "role": role,
        "target": saved,
        "axis_y_mm": center_y_mm,
        "outer_diameter_mm": 2.0 * outer_radius_mm,
        "bore_diameter_mm": 2.0 * inner_radius_mm,
        "body_facts": body_readback,
        "bore_cylinder_signature": bore_signature,
    }


def create_module_body(sw: Any, types: Any, pythoncom: Any, target: Path, module: str, center_y_mm: float, run_id: str) -> Dict[str, Any]:
    # This child is the relieved module beam.  The Ø4.4 inboard collar and
    # (for M1/M2) Ø4 outboard pin are separate world-authored native children
    # fixed in the module SLDASM.  A 3.5 mm beam setback at each hinge is the
    # exact interpanel edge-relief contract and prevents orthogonal-fold plate
    # overlap from being hidden by a coarse link primitive.
    if target.exists():
        raise GateError("PART_EXISTS", "write-once module body exists", {"path": norm(target)})
    model = None
    try:
        model = L1B.new_part(sw, types, pythoncom)
        if abs(X_START_MM) > 1.0e-12:
            L1B.create_offset_plane(model, ("右视基准面", "Right Plane"), X_START_MM, f"MF_R2B_{module}_X_START")
            if not bool(model.Extension.SelectByID2(f"MF_R2B_{module}_X_START", "PLANE", 0.0, 0.0, 0.0, False, 0, None, 0)):
                raise GateError("MODULE_OFFSET_PLANE_FAIL", "cannot select module X-start plane", {"module": module})
        else:
            select_right_plane(model)
        sketch = model.SketchManager
        sketch.InsertSketch(True)
        y0, y1 = center_y_mm - PITCH_MM / 2.0, center_y_mm + PITCH_MM / 2.0
        body_y0, body_y1 = y0 + 3.5, y1 - 3.5
        points = ((-1.0, body_y0), (-1.0, body_y1), (1.0, body_y1), (1.0, body_y0), (-1.0, body_y0))
        # On Right Plane, sketch x maps to global Z and sketch y to global Y.
        for (z0, yy0), (z1, yy1) in zip(points[:-1], points[1:]):
            if sketch.CreateLine(z0 / 1000.0, yy0 / 1000.0, 0.0, z1 / 1000.0, yy1 / 1000.0, 0.0) is None:
                raise GateError("MODULE_PROFILE_FAIL", "module body profile line returned null", {"module": module})
        sketch.InsertSketch(True)
        extrusion = model.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, X_DEPTH_MM / 1000.0, 0.0, False, False, False, False, 0.0, 0.0, False, False, False, False, True, True, True, 0, 0.0, False)
        if extrusion is None:
            raise GateError("MODULE_EXTRUSION_FAIL", "module body extrusion returned null", {"module": module})
        extrusion.Name = f"MF_R2B_{module}_RIGID_BODY"
        L1B.set_properties(model, {"PartNumber": f"V5-DIAG-R2B-{module}-BEAM", "ARTIFACT_CLASS": "DIAGNOSTIC_MICROFIXTURE_NON_RELEASE", "MODULE_RIGID": "TRUE", "EDGE_RELIEF_MM": "3.5", "RUN_ID": run_id})
        saved = L1B.save_as(model, target)
    finally:
        L1B.close_doc(sw, model)
    return {"module": module, "target": saved, "center_y_mm": center_y_mm, "inboard_axis_y_mm": center_y_mm - PITCH_MM / 2.0, "outboard_axis_y_mm": None if module == "M3" else center_y_mm + PITCH_MM / 2.0}


def new_assembly(sw: Any, types: Any, pythoncom: Any) -> Tuple[Any, Any]:
    raw = sw.NewDocument(str(ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
    if raw is None:
        raw = L1B.value(sw, "ActiveDoc")
    if raw is None:
        raise GateError("NEW_ASSEMBLY_FAIL", "cannot create diagnostic assembly")
    model = L1B.wrap(raw, "IModelDoc2", types, pythoncom)
    return model, L1B.wrap(model, "IAssemblyDoc", types, pythoncom)


def insert_component_typed(sw: Any, model: Any, assembly: Any, path: Path, fixed: bool, types: Any, pythoncom: Any) -> Any:
    """Insert either a native part or a native subassembly with correct doc type."""
    opened = None
    title = str(L1B.value(model, "GetTitle"))
    doc_type = SW_DOC_ASSEMBLY if path.suffix.upper() == ".SLDASM" else SW_DOC_PART
    try:
        opened, _ = L1B.open_doc(sw, path, doc_type, True, types, pythoncom)
        L1B.activate(sw, title)
        raw = assembly.AddComponent5(str(path), 0, "", False, "", 0.0, 0.0, 0.0)
        if raw is None:
            raise GateError("ADD_COMPONENT5_FAIL", "typed AddComponent5 returned null", {"path": norm(path), "doc_type": doc_type})
        component = L1B.wrap(raw, "IComponent2", types, pythoncom)
        if not bool(component.SetTransformAndSolve3(L1B.make_transform(sw, L1B.transform_data((0.0, 0.0, 0.0)), types, pythoncom), True)):
            raise GateError("COMPONENT_TRANSFORM_FAIL", "typed component identity transform failed", {"path": norm(path)})
        model.EditRebuild3()
        model.ClearSelection2(True)
        if not bool(component.Select4(False, None, False)):
            raise GateError("COMPONENT_SELECTION_FAIL", "typed component selection failed", {"path": norm(path)})
        assembly.FixComponent() if fixed else assembly.UnfixComponent()
        model.ClearSelection2(True)
        if bool(L1B.value(component, "IsFixed")) != fixed:
            raise GateError("FIXED_STATE_FAIL", "typed component fixed-state readback mismatch", {"path": norm(path), "fixed": fixed})
        return component
    finally:
        L1B.close_doc(sw, opened)
        L1B.activate(sw, title)


def create_rigid_module(sw: Any, types: Any, pythoncom: Any, target: Path, child_paths: Sequence[Path], module: str, run_id: str) -> Dict[str, Any]:
    model = None
    try:
        model, assembly = new_assembly(sw, types, pythoncom)
        components = [insert_component_typed(sw, model, assembly, child, True, types, pythoncom) for child in child_paths]
        if any(not bool(L1B.value(component, "IsFixed")) for component in components):
            raise GateError("MODULE_CHILD_NOT_FIXED", "every module child must be rigid/fixed", {"module": module})
        L1B.set_properties(model, {"PartNumber": f"V5-DIAG-R2B-MODULE-{module}", "ARTIFACT_CLASS": "DIAGNOSTIC_MICROFIXTURE_NON_RELEASE", "RIGID_CHILD_COUNT": str(len(child_paths)), "RUN_ID": run_id})
        saved = L1B.save_as(model, target)
    finally:
        L1B.close_doc(sw, model)
    return {"module": module, "target": saved, "children": [file_fact(path) for path in child_paths], "rigid_child_count": len(child_paths)}


def mate_feature_map(model: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    feature = L1B.value(model, "FirstFeature")
    for _ in range(10000):
        if feature is None:
            return result
        typed = L1B.wrap(feature, "IFeature", types, pythoncom)
        if str(L1B.value(typed, "GetTypeName2")) == "MateGroup":
            sub = L1B.value(typed, "GetFirstSubFeature")
            for _sub in range(10000):
                if sub is None:
                    break
                item = L1B.wrap(sub, "IFeature", types, pythoncom)
                name = str(L1B.value(item, "Name"))
                if name in result:
                    raise GateError("MATE_NAME_COLLISION", "duplicate mate name", {"name": name})
                result[name] = item
                sub = L1B.value(item, "GetNextSubFeature")
        feature = L1B.value(typed, "GetNextFeature")
    raise GateError("MATE_TRAVERSAL_LIMIT", "mate traversal exceeded guard")


def rename_mate(model: Any, old: str, new: str, types: Any, pythoncom: Any) -> Any:
    before = mate_feature_map(model, types, pythoncom)
    if old not in before or new in before:
        raise GateError("MATE_RENAME_PRECONDITION_FAIL", "mate rename precondition failed", {"old": old, "new": new, "available": sorted(before)})
    before[old].Name = new
    after = mate_feature_map(model, types, pythoncom)
    if old in after or new not in after:
        raise GateError("MATE_RENAME_FAIL", "mate rename did not persist", {"old": old, "new": new})
    return after[new]


def nested_children(component: Any, types: Any, pythoncom: Any) -> List[Any]:
    rows = [L1B.wrap(raw, "IComponent2", types, pythoncom) for raw in L1B.as_list(L1B.value(component, "GetChildren"))]
    if not rows:
        raise GateError("NESTED_CHILD_CARDINALITY_FAIL", "rigid module exposes no child", {"module": str(L1B.value(component, "Name2"))})
    return rows


def component_cylinder_entity(component: Any, radius_mm: float, axis_y_mm: float, axis_z_mm: float, types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    candidates = []
    for body in L1B.component_bodies(component, types, pythoncom):
        for raw_face in L1B.as_list(L1B.value(body, "GetFaces")):
            face = L1B.wrap(raw_face, "IFace2", types, pythoncom)
            surface = L1B.wrap(L1B.value(face, "GetSurface"), "ISurface", types, pythoncom)
            if not bool(surface.IsCylinder()):
                continue
            params = [float(value) for value in L1B.as_list(L1B.value(surface, "CylinderParams"))]
            if (
                len(params) >= 7
                and abs(abs(params[3]) - 1.0) < 1.0e-5
                and abs(params[4]) < 1.0e-5
                and abs(params[5]) < 1.0e-5
                and abs(params[1] * 1000.0 - axis_y_mm) <= 0.08
                and abs(params[2] * 1000.0 - axis_z_mm) <= 0.08
                and abs(params[6] * 1000.0 - radius_mm) <= 0.06
            ):
                candidates.append((float(L1B.value(face, "GetArea")), face, params))
    if len(candidates) != 1:
        raise GateError("CYLINDER_YZ_SIGNATURE_FAIL", "expected one X-axis cylinder at world Y/Z", {"component": str(L1B.value(component, "Name2")), "radius_mm": radius_mm, "axis_y_mm": axis_y_mm, "axis_z_mm": axis_z_mm, "count": len(candidates)})
    area, face, params = candidates[0]
    return L1B.wrap(face, "IEntity", types, pythoncom), {"radius_mm": radius_mm, "axis_y_mm": axis_y_mm, "axis_z_mm": axis_z_mm, "cylinder_params": params, "area_mm2": area * 1.0e6, "candidate_count": 1}


def nested_geometry(component: Any, role: str, axis_y_mm: float, radius_mm: float, face_x_mm: float, types: Any, pythoncom: Any, axis_z_mm: float = 0.0) -> Tuple[Any, Any, Dict[str, Any], Any]:
    matches = []
    failures = []
    for child in nested_children(component, types, pythoncom):
        try:
            cylinder, cylinder_fact = component_cylinder_entity(child, radius_mm, axis_y_mm, axis_z_mm, types, pythoncom)
            face, face_fact = L1B.plane_entity_x(child, face_x_mm, types, pythoncom)
            matches.append((cylinder, face, cylinder_fact, face_fact, child))
        except Exception as exc:
            failures.append({"child": str(L1B.value(child, "Name2")), "error": str(exc)})
    if len(matches) != 1:
        raise GateError("NESTED_GEOMETRY_CARDINALITY_FAIL", "nested signature did not resolve exactly one rigid child", {"role": role, "match_count": len(matches), "failures": failures})
    cylinder, face, cylinder_fact, face_fact, child = matches[0]
    return cylinder, face, {
        "role": role,
        "parent_module": str(L1B.value(component, "Name2")),
        "nested_child": str(L1B.value(child, "Name2")),
        "nested_child_path": norm(L1B.component_path(child)),
        "resolution": "PARENT_IComponent2.GetChildren -> NESTED_CHILD -> LIVE_IFace2/IEntity",
        "cylinder": cylinder_fact,
        "axial_face": face_fact,
    }, child


def component_top_plane(component: Any, types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    planes = []
    feature = L1B.value(component, "FirstFeature")
    for _ in range(10000):
        if feature is None:
            break
        typed = L1B.wrap(feature, "IFeature", types, pythoncom)
        if str(L1B.value(typed, "GetTypeName2")) == "RefPlane":
            planes.append(typed)
        feature = L1B.value(typed, "GetNextFeature")
    named = [row for row in planes if str(L1B.value(row, "Name")) in {"上视基准面", "Top Plane"}]
    candidates = named or (planes[1:2] if len(planes) >= 2 else [])
    if len(candidates) != 1:
        raise GateError("ANGLE_PLANE_FAIL", "cannot resolve one module Top plane", {"component": str(L1B.value(component, "Name2")), "planes": [str(L1B.value(row, "Name")) for row in planes]})
    return candidates[0], {"component": str(L1B.value(component, "Name2")), "plane": str(L1B.value(candidates[0], "Name"))}


def add_named_entity_mate(model: Any, assembly: Any, first: Any, second: Any, mate_type: int, components: Sequence[Any], name: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    result = L1B.add_entity_mate(model, assembly, first, second, mate_type, SW_ALIGN_CLOSEST, components, types, pythoncom)
    rename_mate(model, result["feature_name"], name, types, pythoncom)
    return {**result, "feature_name": name}


def add_limit_angle(model: Any, assembly: Any, first_component: Any, second_component: Any, hinge: str, name: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    if hinge not in FIXTURE_LEFT_ANGLE_FLIP:
        raise GateError("ANGLE_HINGE_MAP_FAIL", "angle hinge is absent from the diagnostic-fixture LEFT flip map", {"hinge": hinge, "map": FIXTURE_LEFT_ANGLE_FLIP})
    requested_flip = FIXTURE_LEFT_ANGLE_FLIP[hinge]
    before = L1B.mate_ledger(model, types, pythoncom)
    first_plane, first_fact = component_top_plane(first_component, types, pythoncom)
    second_plane, second_fact = component_top_plane(second_component, types, pythoncom)
    model.ClearSelection2(True)
    if not bool(first_plane.Select2(False, 1)) or not bool(second_plane.Select2(True, 1)):
        raise GateError("ANGLE_PLANE_SELECTION_FAIL", "cannot select two module angle planes", {"name": name})
    selected = int(L1B.selection_manager(model, types, pythoncom).GetSelectedObjectCount2(1))
    returned = assembly.AddMate3(SW_MATE_ANGLE, SW_ALIGN_ALIGNED, requested_flip, 0.0, 0.0, 0.0, 0.0, 0.0, HINGE_LOWER_RAD, HINGE_UPPER_RAD, HINGE_LOWER_RAD, False, 0)
    model.ClearSelection2(True)
    created = L1B.resolve_created_mate(model, returned, before, SW_MATE_ANGLE, SW_ALIGN_ALIGNED, (first_component, second_component), selected, types, pythoncom)
    feature = rename_mate(model, created["feature_name"], name, types, pythoncom)
    definition_readback = angle_definition_fact(feature, hinge, types, pythoncom)
    dimension = angle_dimension(feature, types, pythoncom)
    return {
        **created,
        "feature_name": name,
        "hinge": hinge,
        "requested_alignment": SW_ALIGN_ALIGNED,
        "requested_flip": requested_flip,
        "first_plane": first_fact,
        "second_plane": second_fact,
        "definition_readback": definition_readback,
        "dimension_full_name": str(L1B.value(dimension, "FullName")),
    }


def angle_dimension(feature: Any, types: Any, pythoncom: Any) -> Any:
    raw_mate = L1B.value(feature, "GetSpecificFeature2")
    raw_definition = L1B.value(feature, "GetDefinition")
    if raw_mate is None or raw_definition is None:
        raise GateError("ANGLE_MATE_OBJECT_NULL", "angle mate lacks native mate/definition", {"feature": str(L1B.value(feature, "Name"))})
    definition = L1B.wrap(raw_definition, "IAngleMateFeatureData", types, pythoncom)
    if not bool(L1B.value(definition, "IsAdvancedMate")) or abs(float(L1B.value(definition, "MinimumAngle"))) > 1e-9 or abs(float(L1B.value(definition, "MaximumAngle")) - HINGE_UPPER_RAD) > 1e-9:
        raise GateError("ANGLE_LIMIT_DEFINITION_FAIL", "mate is not native advanced 0..90 degree", {"feature": str(L1B.value(feature, "Name"))})
    mate = L1B.wrap(raw_mate, "IMate2", types, pythoncom)
    display = L1B.wrap(mate.DisplayDimension2(0), "IDisplayDimension", types, pythoncom)
    raw_dimension = display.GetDimension2(0)
    if raw_dimension is None:
        raise GateError("ANGLE_DIMENSION_NULL", "angle mate has no IDimension", {"feature": str(L1B.value(feature, "Name"))})
    return L1B.wrap(raw_dimension, "IDimension", types, pythoncom)


def angle_definition_fact(feature: Any, hinge: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    if hinge not in FIXTURE_LEFT_ANGLE_FLIP:
        raise GateError("ANGLE_HINGE_MAP_FAIL", "cold angle hinge is absent from the diagnostic-fixture LEFT flip map", {"hinge": hinge, "map": FIXTURE_LEFT_ANGLE_FLIP})
    expected_flip = FIXTURE_LEFT_ANGLE_FLIP[hinge]
    raw_mate = L1B.value(feature, "GetSpecificFeature2")
    raw_definition = L1B.value(feature, "GetDefinition")
    if raw_mate is None or raw_definition is None:
        raise GateError("ANGLE_MATE_OBJECT_NULL", "angle mate lacks cold definition", {"feature": str(L1B.value(feature, "Name"))})
    mate = L1B.wrap(raw_mate, "IMate2", types, pythoncom)
    definition = L1B.wrap(raw_definition, "IAngleMateFeatureData", types, pythoncom)
    fact = {
        "feature_name": str(L1B.value(feature, "Name")),
        "hinge": hinge,
        "mate_type": int(L1B.value(mate, "Type")),
        "alignment": int(L1B.value(mate, "Alignment")),
        "flipped": bool(L1B.value(mate, "Flipped")),
        "advanced": bool(L1B.value(definition, "IsAdvancedMate")),
        "definition_mate_alignment": int(L1B.value(definition, "MateAlignment")),
        "definition_flip_dimension": bool(L1B.value(definition, "FlipDimension")),
        "flip_dimension_api_property": "IAngleMateFeatureData.FlipDimension",
        "expected_alignment": SW_ALIGN_ALIGNED,
        "expected_flip": expected_flip,
        "minimum_angle_rad": float(L1B.value(definition, "MinimumAngle")),
        "maximum_angle_rad": float(L1B.value(definition, "MaximumAngle")),
        "feature_health": L1B.feature_error_state(feature),
    }
    if (
        fact["mate_type"] != SW_MATE_ANGLE
        or fact["alignment"] != SW_ALIGN_ALIGNED
        or fact["flipped"] is not expected_flip
        or fact["definition_flip_dimension"] is not expected_flip
        or not fact["advanced"]
        or abs(fact["minimum_angle_rad"] - HINGE_LOWER_RAD) > 1e-9
        or abs(fact["maximum_angle_rad"] - HINGE_UPPER_RAD) > 1e-9
    ):
        raise GateError("ANGLE_DEFINITION_READBACK_FAIL", "cold angle definition does not retain the frozen advanced 0..90 alignment/flip branch", fact)
    return fact


def establish_configurations(model: Any, angle_feature_names: Sequence[str], types: Any, pythoncom: Any) -> Dict[str, Any]:
    from win32com.client import VARIANT

    manager = L1B.wrap(L1B.value(model, "ConfigurationManager"), "IConfigurationManager", types, pythoncom)
    active = L1B.wrap(L1B.value(manager, "ActiveConfiguration"), "IConfiguration", types, pythoncom)
    active.Name = STATES[0]
    for state in STATES[1:]:
        if manager.AddConfiguration2(state, "R2B-A exact-architecture microfixture state", "", 0, "", False, False) is None:
            raise GateError("CONFIG_CREATE_FAIL", "native configuration creation returned null", {"state": state})
    names = tuple(str(name) for name in L1B.as_list(L1B.value(model, "GetConfigurationNames")))
    if set(names) != set(STATES) or len(names) != 7:
        raise GateError("CONFIG_SET_FAIL", "native seven-configuration set is not exact", {"actual": names})
    # Handles must be fetched after all configurations exist.  Only typed
    # VT_ARRAY|VT_BSTR with swSetValue_InSpecificConfigs is accepted.
    feature_map = mate_feature_map(model, types, pythoncom)
    dimensions = {name: angle_dimension(feature_map[name], types, pythoncom) for name in angle_feature_names}
    pending = []
    for state in STATES:
        angles = LEFT_TUPLES[state]
        for index, hinge in enumerate(HINGE_NAMES):
            # The native advanced-angle dimension is the physical fold
            # magnitude beta=90-alpha.  The normalized interface angle is
            # recovered exactly as alpha=90-beta.  Sign comes from the
            # pre-positioned branch: ROOT=-beta, H12=+beta, H23=-beta.
            requested = math.radians(90.0 - float(angles[index]))
            config_array = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, [state])
            status = int(dimensions[f"MF_R2B_{hinge}_LIMIT_ANGLE"].SetSystemValue3(requested, SW_SET_VALUE_IN_SPECIFIC_CONFIGS, config_array))
            if status != SW_SET_VALUE_SUCCESS:
                raise GateError("CONFIG_DIMENSION_WRITE_FAIL", "typed angle write failed", {"state": state, "hinge": hinge, "status": status})
            pending.append({"state": state, "hinge": hinge, "normalized_alpha_deg": float(angles[index]), "requested_driver_beta_rad": requested, "status": status})
    if not bool(model.ForceRebuild3(True)):
        raise GateError("CONFIG_DIMENSION_REBUILD_FAIL", "rebuild failed after all typed angle writes")
    # Full 21-cell table read only after all writes and rebuild.
    for row in pending:
        feature = mate_feature_map(model, types, pythoncom)[f"MF_R2B_{row['hinge']}_LIMIT_ANGLE"]
        readback = float(angle_dimension(feature, types, pythoncom).GetSystemValue2(row["state"]))
        row["readback_driver_beta_rad"] = readback
        row["normalized_alpha_readback_deg"] = 90.0 - math.degrees(readback)
        row["pass"] = abs(readback - row["requested_driver_beta_rad"]) <= ANGLE_TOL_RAD and abs(row["normalized_alpha_readback_deg"] - row["normalized_alpha_deg"]) <= 1.0e-4
        if not row["pass"]:
            raise GateError("CONFIG_DIMENSION_READBACK_FAIL", "stored angle differs from exact seven-tuple contract", row)
    return {"configurations": list(STATES), "dimension_table": pending, "write_api": "IDimension.SetSystemValue3(value,3,VARIANT(VT_ARRAY|VT_BSTR,[config]))"}


def feature_suppression(feature: Any, suppress: bool) -> None:
    state = 0 if suppress else 1
    feature.SetSuppression2(state, 2, None)
    if bool(L1B.value(feature, "IsSuppressed")) != suppress:
        raise GateError("MATE_SUPPRESSION_FAIL", "mate suppression readback differs", {"feature": str(L1B.value(feature, "Name")), "suppress": suppress})


def component_by_path(model: Any, target: Path, types: Any, pythoncom: Any) -> Any:
    matches = [row for row in L1B.get_components(model, types, pythoncom) if L1B.component_path(row) == target.resolve()]
    if len(matches) != 1:
        raise GateError("COMPONENT_PATH_CARDINALITY_FAIL", "top occurrence path is not unique", {"target": norm(target), "count": len(matches)})
    return matches[0]


def apply_state_poses(sw: Any, model: Any, module_paths: Mapping[str, Path], state: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    expected = state_transforms(LEFT_TUPLES[state])
    angle_names = [f"MF_R2B_{hinge}_LIMIT_ANGLE" for hinge in HINGE_NAMES]
    features = mate_feature_map(model, types, pythoncom)
    for name in angle_names:
        feature_suppression(features[name], True)
    if not bool(model.EditRebuild3()):
        raise GateError("POSE_SUPPRESSION_REBUILD_FAIL", "rebuild failed before exact occurrence placement", {"state": state})
    for key in MODULE_KEYS:
        component = component_by_path(model, module_paths[key], types, pythoncom)
        transform = L1B.make_transform(sw, expected[key], types, pythoncom)
        if not bool(component.SetTransformAndSolve3(transform, False)):
            raise GateError("MODULE_POSE_WRITE_FAIL", "exact module occurrence pose failed", {"state": state, "module": key})
    features = mate_feature_map(model, types, pythoncom)
    for name in angle_names:
        feature_suppression(features[name], False)
    if not bool(model.ForceRebuild3(True)):
        raise GateError("POSE_RESTORE_REBUILD_FAIL", "rebuild failed after angle mate restore", {"state": state})
    rows = []
    for key in MODULE_KEYS:
        actual = L1B.transform_array(component_by_path(model, module_paths[key], types, pythoncom))
        error = transform_error(actual, expected[key])
        if error > TRANS_TOL:
            raise GateError("MODULE_POSE_READBACK_FAIL", "module transform differs from R2B-A FK", {"state": state, "module": key, "error": error, "actual": actual, "expected": expected[key]})
        rows.append({"module": key, "transform16": actual, "max_abs_error": error})
    return {"state": state, "angles_deg": list(LEFT_TUPLES[state]), "modules": rows}


def interference_fact(assembly: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    raw_manager = L1B.value(assembly, "InterferenceDetectionManager")
    if raw_manager is None:
        raise GateError("INTERFERENCE_MANAGER_NULL", "assembly has no native interference manager")
    manager = L1B.wrap(raw_manager, "IInterferenceDetectionMgr", types, pythoncom)
    try:
        manager.TreatCoincidenceAsInterference = False
        manager.TreatSubAssembliesAsComponents = False
        manager.IncludeMultibodyPartInterferences = True
        manager.IgnoreHiddenBodies = False
        rows = []
        for raw in L1B.as_list(manager.GetInterferences()):
            item = L1B.wrap(raw, "IInterference", types, pythoncom)
            paths = []
            for raw_component in L1B.as_list(L1B.value(item, "Components")):
                paths.append(norm(L1B.component_path(L1B.wrap(raw_component, "IComponent2", types, pythoncom))))
            volume_mm3 = float(L1B.value(item, "Volume")) * 1.0e9
            rows.append({"component_paths": sorted(paths), "volume_mm3": volume_mm3, "possible": bool(L1B.value(item, "IsPossibleInterference"))})
        reported = int(L1B.value(manager, "GetInterferenceCount"))
        if reported != len(rows):
            raise GateError("INTERFERENCE_COUNT_FAIL", "interference count and rows disagree", {"reported": reported, "rows": rows})
        positive = [row for row in rows if len(set(row["component_paths"])) >= 2 and row["volume_mm3"] > POSITIVE_VOLUME_TOL_MM3]
        return {"reported_count": reported, "rows": rows, "positive_volume_interference_count": len(positive), "positive": positive, "treat_coincidence_as_interference": False, "nested_subassemblies_expanded": True}
    finally:
        manager.Done()


def create_parent_chain(sw: Any, types: Any, pythoncom: Any, target: Path, root_path: Path, module_paths: Mapping[str, Path], run_id: str) -> Dict[str, Any]:
    model = None
    try:
        model, assembly = new_assembly(sw, types, pythoncom)
        root = insert_component_typed(sw, model, assembly, root_path, True, types, pythoncom)
        modules = {key: insert_component_typed(sw, model, assembly, module_paths[key], False, types, pythoncom) for key in MODULE_KEYS}
        geometry = []
        mates = []
        for index, hinge in enumerate(HINGE_NAMES):
            axis_y = ROOT_Y_MM + index * PITCH_MM
            if hinge == "ROOT":
                first_cyl, first_face = L1B.cylinder_entity(root, PIN_RADIUS_MM, axis_y, 1, types, pythoncom)[0], L1B.plane_entity_x(root, X_START_MM, types, pythoncom)[0]
                second_cyl, second_face, nested, second_endpoint = nested_geometry(modules["M1"], "M1_ROOT_BORE", axis_y, BORE_RADIUS_MM, X_START_MM, types, pythoncom)
                first_component, second_component = root, modules["M1"]
                first_endpoint = root
                geometry.append({"hinge": hinge, "root_equivalent": True, "moving_nested": nested})
            else:
                upstream_key, downstream_key = ("M1", "M2") if hinge == "H12" else ("M2", "M3")
                first_cyl, first_face, first_nested, first_endpoint = nested_geometry(modules[upstream_key], f"{upstream_key}_OUTBOARD_PIN", axis_y, PIN_RADIUS_MM, X_START_MM, types, pythoncom)
                second_cyl, second_face, second_nested, second_endpoint = nested_geometry(modules[downstream_key], f"{downstream_key}_INBOARD_BORE", axis_y, BORE_RADIUS_MM, X_START_MM, types, pythoncom)
                first_component, second_component = modules[upstream_key], modules[downstream_key]
                geometry.append({"hinge": hinge, "upstream_nested": first_nested, "downstream_nested": second_nested})
            mates.append(add_named_entity_mate(model, assembly, first_cyl, second_cyl, SW_MATE_CONCENTRIC, (first_endpoint, second_endpoint), f"MF_R2B_{hinge}_CONCENTRIC", types, pythoncom))
            # B-rep handles are re-resolved after concentric-mate rebuild.
            if hinge == "ROOT":
                first_face = L1B.plane_entity_x(root, X_START_MM, types, pythoncom)[0]
                second_face = nested_geometry(modules["M1"], "M1_ROOT_BORE", axis_y, BORE_RADIUS_MM, X_START_MM, types, pythoncom)[1]
            else:
                upstream_key, downstream_key = ("M1", "M2") if hinge == "H12" else ("M2", "M3")
                first_face = nested_geometry(modules[upstream_key], f"{upstream_key}_OUTBOARD_PIN", axis_y, PIN_RADIUS_MM, X_START_MM, types, pythoncom)[1]
                second_face = nested_geometry(modules[downstream_key], f"{downstream_key}_INBOARD_BORE", axis_y, BORE_RADIUS_MM, X_START_MM, types, pythoncom)[1]
            mates.append(add_named_entity_mate(model, assembly, first_face, second_face, SW_MATE_COINCIDENT, (first_endpoint, second_endpoint), f"MF_R2B_{hinge}_COINCIDENT", types, pythoncom))
            mates.append(add_limit_angle(model, assembly, first_component, second_component, hinge, f"MF_R2B_{hinge}_LIMIT_ANGLE", types, pythoncom))
        configuration = establish_configurations(model, [f"MF_R2B_{hinge}_LIMIT_ANGLE" for hinge in HINGE_NAMES], types, pythoncom)
        states = []
        for state in STATES:
            if not bool(model.ShowConfiguration2(state)):
                raise GateError("CONFIG_ACTIVATE_FAIL", "configuration activation failed", {"state": state})
            states.append(apply_state_poses(sw, model, module_paths, state, types, pythoncom))
        if not bool(model.ShowConfiguration2("SOLAR_DEPLOYED_NOMINAL")):
            raise GateError("NOMINAL_ACTIVATE_FAIL", "cannot leave nominal configuration active")
        nominal = {row["module"]: row["transform16"] for row in next(row for row in states if row["state"] == "SOLAR_DEPLOYED_NOMINAL")["modules"]}
        identity = L1B.transform_data((0.0, 0.0, 0.0))
        if any(transform_error(nominal[key], identity) > TRANS_TOL for key in MODULE_KEYS):
            raise GateError("NOMINAL_IDENTITY_FAIL", "world-authored module occurrence is not identity at deployed nominal", {"nominal": nominal})
        mate_rows = L1B.mate_ledger(model, types, pythoncom)
        counts = Counter(row["mate_type"] for row in mate_rows)
        if len(mate_rows) != 9 or counts != Counter({SW_MATE_CONCENTRIC: 3, SW_MATE_COINCIDENT: 3, SW_MATE_ANGLE: 3}):
            raise GateError("MATE_SET_FAIL", "parent chain does not contain exact 3x3 mate contract", {"mates": mate_rows, "counts": dict(counts)})
        L1B.set_properties(model, {"PartNumber": "V5-DIAG-R2B-MODULE-CHAIN", "ARTIFACT_CLASS": "DIAGNOSTIC_MICROFIXTURE_NON_RELEASE", "MODULE_COUNT": "3", "HINGE_COUNT": "3", "STATE_COUNT": "7", "RUN_ID": run_id})
        saved = L1B.save_as(model, target)
    finally:
        L1B.close_doc(sw, model)
    return {"target": saved, "geometry": geometry, "mates": mate_rows, "mate_creation": mates, "configuration": configuration, "states": states}


def snapshot(paths: Iterable[Path]) -> Dict[str, Dict[str, Any]]:
    return {norm(path): file_fact(path) for path in sorted((item.resolve() for item in paths), key=norm)}


def build_stage(run_id: str, expected_pid: int, production_builder: Path) -> Dict[str, Any]:
    audit = static_audit(run_id, production_builder, require_final_builder=True)
    if not audit["execution_authorized"]:
        raise GateError("STATIC_AUDIT_HOLD", "static audit does not authorize build stage", {"audit": audit})
    root_authorization = production_root_flip_authorization_gate()
    root_separation = root_role_separation_fact()
    root = attempt_root(run_id)
    sw = pythoncom = None
    mutex = acquire_process_mutex()
    attempt_created = False
    try:
        root.mkdir(parents=False, exist_ok=False)
        attempt_created = True
        sw, types, pythoncom, session = L1B.attach_empty_session(expected_pid)
        import psutil
        process_create_time = float(psutil.Process(int(session["pid"])).create_time())
        session = {**session, "process_create_time_unix": process_create_time, "create_time_utc": unix_time_utc(process_create_time)}
        part_paths = {
            "ROOT": root / "cad/parts/MF_R2B_ROOT_EQUIVALENT.SLDPRT",
            "M1": root / "cad/parts/MF_R2B_M1_BODY.SLDPRT",
            "M2": root / "cad/parts/MF_R2B_M2_BODY.SLDPRT",
            "M3": root / "cad/parts/MF_R2B_M3_BODY.SLDPRT",
            "M1_PIN": root / "cad/parts/MF_R2B_M1_OUTBOARD_PIN.SLDPRT",
            "M2_PIN": root / "cad/parts/MF_R2B_M2_OUTBOARD_PIN.SLDPRT",
            "M1_COLLAR": root / "cad/parts/MF_R2B_M1_INBOARD_COLLAR.SLDPRT",
            "M2_COLLAR": root / "cad/parts/MF_R2B_M2_INBOARD_COLLAR.SLDPRT",
            "M3_COLLAR": root / "cad/parts/MF_R2B_M3_INBOARD_COLLAR.SLDPRT",
        }
        root_result = create_ring_part(sw, types, pythoncom, part_paths["ROOT"], "ROOT_EQUIVALENT_PIN", ROOT_Y_MM, PIN_RADIUS_MM, 0.0, run_id)
        body_results = [create_module_body(sw, types, pythoncom, part_paths[key], key, ROOT_Y_MM + (index + 0.5) * PITCH_MM, run_id) for index, key in enumerate(MODULE_KEYS)]
        pin_results = [
            create_ring_part(sw, types, pythoncom, part_paths["M1_PIN"], "M1_OUTBOARD_PIN", ROOT_Y_MM + PITCH_MM, PIN_RADIUS_MM, 0.0, run_id),
            create_ring_part(sw, types, pythoncom, part_paths["M2_PIN"], "M2_OUTBOARD_PIN", ROOT_Y_MM + 2.0 * PITCH_MM, PIN_RADIUS_MM, 0.0, run_id),
        ]
        collar_results = [
            create_ring_part(sw, types, pythoncom, part_paths[f"{key}_COLLAR"], f"{key}_INBOARD_COLLAR", ROOT_Y_MM + index * PITCH_MM, 2.75, BORE_RADIUS_MM, run_id)
            for index, key in enumerate(MODULE_KEYS)
        ]
        module_paths = {key: root / f"cad/modules/MF_R2B_MODULE_{key}.SLDASM" for key in MODULE_KEYS}
        module_children = {
            "M1": (part_paths["M1"], part_paths["M1_COLLAR"], part_paths["M1_PIN"]),
            "M2": (part_paths["M2"], part_paths["M2_COLLAR"], part_paths["M2_PIN"]),
            "M3": (part_paths["M3"], part_paths["M3_COLLAR"]),
        }
        module_results = [create_rigid_module(sw, types, pythoncom, module_paths[key], module_children[key], key, run_id) for key in MODULE_KEYS]
        chain_path = root / "cad/MF_R2B_THREE_MODULE_CHAIN.SLDASM"
        chain = create_parent_chain(sw, types, pythoncom, chain_path, part_paths["ROOT"], module_paths, run_id)
        L1B.close_owned_documents(sw)
        if int(L1B.value(sw, "GetDocumentCount")) != 0 or L1B.value(sw, "ActiveDoc") is not None:
            raise GateError("BUILD_SESSION_NOT_EMPTY", "owned diagnostic documents remain open")
        cad_paths = list(part_paths.values()) + list(module_paths.values()) + [chain_path]
        cad_snapshot = snapshot(cad_paths)
        receipt = {
            "schema": "F3R2_V5_SOLAR_R2B_MODULE_CHAIN_BUILD_STAGE_RECEIPT_V1",
            "timestamp_utc": utc_now(),
            "run_id": run_id,
            "attempt_root": norm(root),
            "classification": "DIAGNOSTIC_MICROFIXTURE_NON_RELEASE",
            "production_builder": file_fact(production_builder.resolve()),
            "production_contract_sha256": EXPECTED_PRODUCTION_CONTRACT_SHA256,
            "frozen_contracts": {path.name: file_fact(path) for path in (AUTHORITY, ARCHITECTURE, ORACLE, AUTHORIZATION)},
            "branch_matrix_probe_script": file_fact(BRANCH_PROBE_SCRIPT),
            "branch_matrix_result": file_fact(BRANCH_MATRIX_RESULT),
            "production_root_flip_authorization": root_authorization,
            "root_role_separation": root_separation,
            "fixture_left_per_hinge_angle_flip": dict(FIXTURE_LEFT_ANGLE_FLIP),
            "authorized_production_per_side_angle_flip": {side: dict(values) for side, values in PRODUCTION_ANGLE_FLIP.items()},
            "fixture_angle_branch_creation_contract": "DIAGNOSTIC_ROOT_EQUIVALENT_ONLY; PARENT_TO_CHILD_ROOT_FIRST; ALIGNMENT=0; FIXTURE ROOT/H23 Flip=True -> NEGATIVE; H12 Flip=False -> POSITIVE",
            "production_root_branch_contract": "ACCEPTED_CLEVIS_TO_P1_MODULE_ONLY; AUTHORIZED L ROOT Flip=False; R ROOT Flip=True; FIXTURE ROOT IS NOT PRODUCTION AUTHORITY",
            "session": session,
            "parts": [root_result, *body_results, *collar_results, *pin_results],
            "modules": module_results,
            "chain": chain,
            "cad_snapshot": cad_snapshot,
            "fresh_pid_verification_required": True,
            "production_use_permitted": False,
            "verdict": "V5_SOLAR_R2B_MODULE_CHAIN_BUILD_STAGE_SAME_PID_PASS",
        }
        write_json_once(root / "BUILD_STAGE_RECEIPT.json", receipt)
        return receipt
    except Exception as exc:
        if sw is not None:
            try:
                L1B.close_owned_documents(sw)
            except Exception:
                pass
        failure = {"schema": "F3R2_V5_SOLAR_R2B_MODULE_CHAIN_BUILD_FAILURE_V1", "timestamp_utc": utc_now(), "run_id": run_id, "error_code": getattr(exc, "code", "UNHANDLED_EXCEPTION"), "error": str(exc), "detail": getattr(exc, "detail", {}), "traceback": traceback.format_exc(), "verdict": "V5_SOLAR_R2B_MODULE_CHAIN_BUILD_FAIL"}
        if attempt_created and root.exists() and not (root / "BUILD_STAGE_FAIL.json").exists():
            write_json_once(root / "BUILD_STAGE_FAIL.json", failure)
        raise
    finally:
        if pythoncom is not None:
            pythoncom.CoUninitialize()
        release_process_mutex(mutex)


def fresh_read_module(model: Any, expected_children: Sequence[Path], types: Any, pythoncom: Any) -> Dict[str, Any]:
    components = L1B.get_components(model, types, pythoncom)
    actual = {L1B.component_path(child): child for child in components}
    expected = {path.resolve() for path in expected_children}
    if set(actual) != expected or len(actual) != len(expected_children):
        raise GateError("FRESH_MODULE_CHILD_COUNT_FAIL", "module child set differs", {"actual": [norm(path) for path in actual], "expected": [norm(path) for path in expected]})
    rows = []
    for path in sorted(expected, key=norm):
        child = actual[path]
        if not bool(L1B.value(child, "IsFixed")):
            raise GateError("FRESH_MODULE_CHILD_FAIL", "module child is not fixed", {"path": norm(path)})
        rows.append({"path": norm(path), "fixed": True, "transform16": L1B.transform_array(child)})
    return {"children": rows, "rigid_child_count": len(rows)}


def fresh_verify(run_id: str, expected_pid: int, production_builder: Path) -> Dict[str, Any]:
    """Different-PID read-only verification.  Mutation call count is zero."""
    root = attempt_root(run_id)
    if not root.is_dir():
        raise GateError("ATTEMPT_MISSING", "diagnostic attempt directory is absent", {"path": norm(root)})
    pass_path = root / "F3R2_V5_SOLAR_R2B_MODULE_CHAIN_MICROFIXTURE_RECEIPT.json"
    if pass_path.exists() or any(root.glob("FRESH_VERIFY_FAIL_*.json")):
        raise GateError("ATTEMPT_TERMINAL", "attempt already has terminal fresh verification evidence", {"path": norm(root)})
    build_path = root / "BUILD_STAGE_RECEIPT.json"
    build = read_json(build_path)
    if build.get("schema") != "F3R2_V5_SOLAR_R2B_MODULE_CHAIN_BUILD_STAGE_RECEIPT_V1" or build.get("verdict") != "V5_SOLAR_R2B_MODULE_CHAIN_BUILD_STAGE_SAME_PID_PASS":
        raise GateError("BUILD_RECEIPT_FAIL", "build-stage receipt does not authorize verification")
    if Path(str(build.get("attempt_root", ""))).resolve() != root.resolve():
        raise GateError("BUILD_ATTEMPT_BINDING_FAIL", "build receipt binds another attempt")
    builder_fact = file_fact(production_builder.resolve())
    if builder_fact["sha256"] != EXPECTED_PRODUCTION_BUILDER_SHA256:
        raise GateError("FINAL_BUILDER_HASH_FAIL", "fresh verifier builder is not the frozen final production script", {"expected": EXPECTED_PRODUCTION_BUILDER_SHA256, "actual": builder_fact["sha256"]})
    if builder_fact != build.get("production_builder"):
        raise GateError("BUILDER_HASH_DRIFT", "production builder differs from build-stage binding", {"expected": build.get("production_builder"), "actual": builder_fact})
    if build.get("production_contract_sha256") != EXPECTED_PRODUCTION_CONTRACT_SHA256:
        raise GateError("PRODUCTION_CONTRACT_HASH_DRIFT", "build-stage production contract binding differs", {"build": build.get("production_contract_sha256"), "expected": EXPECTED_PRODUCTION_CONTRACT_SHA256})
    root_authorization = production_root_flip_authorization_gate()
    root_separation = root_role_separation_fact()
    if build.get("production_root_flip_authorization") != root_authorization:
        raise GateError("ROOT_FLIP_AUTHORIZATION_DRIFT", "production ROOT authorization differs from build-stage binding", {"build": build.get("production_root_flip_authorization"), "actual": root_authorization})
    if build.get("root_role_separation") != root_separation:
        raise GateError("ROOT_ROLE_SEPARATION_DRIFT", "fixture/production ROOT separation differs from build-stage binding", {"build": build.get("root_role_separation"), "actual": root_separation})
    branch_probe_fact = file_fact(BRANCH_PROBE_SCRIPT)
    branch_result_fact = file_fact(BRANCH_MATRIX_RESULT)
    if branch_probe_fact != build.get("branch_matrix_probe_script") or branch_result_fact != build.get("branch_matrix_result"):
        raise GateError("BRANCH_EVIDENCE_DRIFT", "branch probe/result differs from build-stage binding", {
            "build_probe": build.get("branch_matrix_probe_script"),
            "actual_probe": branch_probe_fact,
            "build_result": build.get("branch_matrix_result"),
            "actual_result": branch_result_fact,
        })
    if build.get("fixture_left_per_hinge_angle_flip") != FIXTURE_LEFT_ANGLE_FLIP:
        raise GateError("FIXTURE_BRANCH_FLIP_MAP_DRIFT", "build-stage diagnostic-fixture LEFT angle flip map differs", {"build": build.get("fixture_left_per_hinge_angle_flip"), "expected": FIXTURE_LEFT_ANGLE_FLIP})
    if build.get("authorized_production_per_side_angle_flip") != PRODUCTION_ANGLE_FLIP:
        raise GateError("PRODUCTION_BRANCH_FLIP_MAP_DRIFT", "build-stage authorized production angle flip map differs", {"build": build.get("authorized_production_per_side_angle_flip"), "expected": PRODUCTION_ANGLE_FLIP})
    build_session = build.get("session", {})
    before = snapshot(Path(path) for path in build.get("cad_snapshot", {}))
    if before != build.get("cad_snapshot"):
        raise GateError("CAD_PREVERIFY_DRIFT", "diagnostic CAD differs from build-stage snapshot", {"expected": build.get("cad_snapshot"), "actual": before})
    sw = pythoncom = None
    mutex = acquire_process_mutex()
    opened_models: List[Any] = []
    try:
        sw, types, pythoncom, verify_session = L1B.attach_empty_session(expected_pid)
        import psutil
        verify_process_create_time = float(psutil.Process(int(verify_session["pid"])).create_time())
        verify_session = {**verify_session, "process_create_time_unix": verify_process_create_time, "create_time_utc": unix_time_utc(verify_process_create_time)}
        if int(verify_session["pid"]) == int(build_session.get("pid", -1)):
            raise GateError("FRESH_PID_REUSE_FAIL", "fresh verifier attached to build PID", {"pid": verify_session["pid"]})
        build_create = float(build_session.get("process_create_time_unix", 0.0))
        verify_create = float(verify_session.get("process_create_time_unix", 0.0))
        if build_create <= 0.0 or verify_create <= build_create:
            raise GateError("FRESH_PROCESS_TIME_FAIL", "verify process is not later-created than build process", {"build_create_time": build_create, "verify_create_time": verify_create})
        part_paths = {
            "ROOT": root / "cad/parts/MF_R2B_ROOT_EQUIVALENT.SLDPRT",
            **{key: root / f"cad/parts/MF_R2B_{key}_BODY.SLDPRT" for key in MODULE_KEYS},
            "M1_PIN": root / "cad/parts/MF_R2B_M1_OUTBOARD_PIN.SLDPRT",
            "M2_PIN": root / "cad/parts/MF_R2B_M2_OUTBOARD_PIN.SLDPRT",
            "M1_COLLAR": root / "cad/parts/MF_R2B_M1_INBOARD_COLLAR.SLDPRT",
            "M2_COLLAR": root / "cad/parts/MF_R2B_M2_INBOARD_COLLAR.SLDPRT",
            "M3_COLLAR": root / "cad/parts/MF_R2B_M3_INBOARD_COLLAR.SLDPRT",
        }
        module_children = {
            "M1": (part_paths["M1"], part_paths["M1_COLLAR"], part_paths["M1_PIN"]),
            "M2": (part_paths["M2"], part_paths["M2_COLLAR"], part_paths["M2_PIN"]),
            "M3": (part_paths["M3"], part_paths["M3_COLLAR"]),
        }
        module_paths = {key: root / f"cad/modules/MF_R2B_MODULE_{key}.SLDASM" for key in MODULE_KEYS}
        collar_axis_y = {
            "M1_COLLAR": ROOT_Y_MM,
            "M2_COLLAR": ROOT_Y_MM + PITCH_MM,
            "M3_COLLAR": ROOT_Y_MM + 2.0 * PITCH_MM,
        }
        part_rows = []
        for key, path in part_paths.items():
            model, opened = L1B.open_doc(sw, path, SW_DOC_PART, True, types, pythoncom)
            opened_models.append(model)
            facts = L1B.body_facts(model, types, pythoncom)
            if facts["solid_body_count"] != 1:
                raise GateError("FRESH_PART_BODY_FAIL", "diagnostic part is not one native solid", {"path": norm(path), "facts": facts})
            bore_signature = part_cylinder_signature(model, BORE_RADIUS_MM, collar_axis_y[key], 0.0, types, pythoncom) if key in collar_axis_y else None
            part_rows.append({"key": key, "path": norm(path), "open": opened, "body_facts": facts, "bore_cylinder_signature": bore_signature})
            L1B.close_doc(sw, model); opened_models.pop()
        module_rows = []
        for key in MODULE_KEYS:
            model, opened = L1B.open_doc(sw, module_paths[key], SW_DOC_ASSEMBLY, True, types, pythoncom)
            opened_models.append(model)
            module_rows.append({"module": key, "open": opened, **fresh_read_module(model, module_children[key], types, pythoncom)})
            L1B.close_doc(sw, model); opened_models.pop()
        chain_path = root / "cad/MF_R2B_THREE_MODULE_CHAIN.SLDASM"
        model, opened = L1B.open_doc(sw, chain_path, SW_DOC_ASSEMBLY, True, types, pythoncom)
        opened_models.append(model)
        assembly = L1B.wrap(model, "IAssemblyDoc", types, pythoncom)
        names = tuple(str(name) for name in L1B.as_list(L1B.value(model, "GetConfigurationNames")))
        if set(names) != set(STATES) or len(names) != 7:
            raise GateError("FRESH_CONFIG_SET_FAIL", "fresh chain lacks exact seven states", {"names": names})
        mate_rows = L1B.mate_ledger(model, types, pythoncom)
        counts = Counter(row["mate_type"] for row in mate_rows)
        if len(mate_rows) != 9 or counts != Counter({SW_MATE_CONCENTRIC: 3, SW_MATE_COINCIDENT: 3, SW_MATE_ANGLE: 3}):
            raise GateError("FRESH_MATE_SET_FAIL", "fresh parent mate set drifted", {"mates": mate_rows, "counts": dict(counts)})
        state_rows = []
        total_positive = 0
        for state in STATES:
            if not bool(model.ShowConfiguration2(state)):
                raise GateError("FRESH_CONFIG_ACTIVATE_FAIL", "read-only state activation failed", {"state": state})
            features = mate_feature_map(model, types, pythoncom)
            angle_rows = []
            for index, hinge in enumerate(HINGE_NAMES):
                feature = features[f"MF_R2B_{hinge}_LIMIT_ANGLE"]
                dimension = angle_dimension(feature, types, pythoncom)
                actual = float(dimension.GetSystemValue2(state))
                expected = math.radians(90.0 - LEFT_TUPLES[state][index])
                if abs(actual - expected) > ANGLE_TOL_RAD:
                    raise GateError("FRESH_ANGLE_TABLE_FAIL", "fresh angle dimension table drifted", {"state": state, "hinge": hinge, "actual": actual, "expected": expected})
                normalized = 90.0 - math.degrees(actual)
                if abs(normalized - LEFT_TUPLES[state][index]) > 1.0e-4:
                    raise GateError("FRESH_NORMALIZED_ALPHA_FAIL", "normalized alpha readback drifted", {"state": state, "hinge": hinge, "normalized": normalized, "expected": LEFT_TUPLES[state][index]})
                angle_rows.append({
                    "hinge": hinge,
                    "normalized_alpha_deg": normalized,
                    "stored_driver_beta_rad": actual,
                    "dimension_full_name": str(L1B.value(dimension, "FullName")),
                    "cold_definition": angle_definition_fact(feature, hinge, types, pythoncom),
                    "creation_alignment": SW_ALIGN_ALIGNED,
                    "creation_flip": FIXTURE_LEFT_ANGLE_FLIP[hinge],
                })
            expected_transforms = state_transforms(LEFT_TUPLES[state])
            transform_rows = []
            for key in MODULE_KEYS:
                actual = L1B.transform_array(component_by_path(model, module_paths[key], types, pythoncom))
                error = transform_error(actual, expected_transforms[key])
                if error > TRANS_TOL:
                    raise GateError("FRESH_TRANSFORM_FAIL", "fresh module pose differs from exact FK", {"state": state, "module": key, "error": error, "actual": actual, "expected": expected_transforms[key]})
                transform_rows.append({"module": key, "transform16": actual, "max_abs_error": error})
            absolute = {row["module"]: math.degrees(math.atan2(row["transform16"][5], row["transform16"][4])) for row in transform_rows}
            def wrap_deg(value: float) -> float:
                return (value + 180.0) % 360.0 - 180.0
            signed_relative = {
                "ROOT": wrap_deg(absolute["M1"]),
                "H12": wrap_deg(absolute["M2"] - absolute["M1"]),
                "H23": wrap_deg(absolute["M3"] - absolute["M2"]),
            }
            expected_relative = {
                "ROOT": -(90.0 - LEFT_TUPLES[state][0]),
                "H12": +(90.0 - LEFT_TUPLES[state][1]),
                "H23": -(90.0 - LEFT_TUPLES[state][2]),
            }
            if any(abs(signed_relative[key] - expected_relative[key]) > 1.0e-4 for key in HINGE_NAMES):
                raise GateError("FRESH_SIGNED_RELATIVE_ANGLE_FAIL", "cold transforms do not retain ROOT-/H12+/H23- branch mapping", {"state": state, "actual": signed_relative, "expected": expected_relative})
            # Nested live face selection is repeated in every state.  H12/H23
            # must resolve Ø4 pin and Ø4.4 bore from rigid child assemblies.
            components = {key: component_by_path(model, module_paths[key], types, pythoncom) for key in MODULE_KEYS}
            nested_rows = []
            root_component = component_by_path(model, part_paths["ROOT"], types, pythoncom)
            root_pin, root_pin_fact = component_cylinder_entity(root_component, PIN_RADIUS_MM, ROOT_Y_MM, 0.0, types, pythoncom)
            _root_bore, _root_face, root_bore_fact, _root_child = nested_geometry(components["M1"], "M1_ROOT_BORE", ROOT_Y_MM, BORE_RADIUS_MM, X_START_MM, types, pythoncom, 0.0)
            nested_rows.append({"hinge": "ROOT", "root_pin": root_pin_fact, "moving_bore": root_bore_fact, "root_pin_entity_non_null": root_pin is not None})
            for hinge, upstream, downstream, nominal_axis_y in (("H12", "M1", "M2", ROOT_Y_MM + PITCH_MM), ("H23", "M2", "M3", ROOT_Y_MM + 2.0 * PITCH_MM)):
                upstream_transform = next(row["transform16"] for row in transform_rows if row["module"] == upstream)
                downstream_transform = next(row["transform16"] for row in transform_rows if row["module"] == downstream)
                local_axis_point_mm = [0.0, nominal_axis_y, 0.0]
                world_axis_upstream = transform_point_mm(upstream_transform, local_axis_point_mm)
                world_axis_downstream = transform_point_mm(downstream_transform, local_axis_point_mm)
                world_axis_delta = [world_axis_upstream[index] - world_axis_downstream[index] for index in range(3)]
                world_axis_error = math.sqrt(sum(value * value for value in world_axis_delta))
                if world_axis_error > 0.08:
                    raise GateError("FRESH_WORLD_AXIS_CONSISTENCY_FAIL", "upstream/downstream module transforms do not map the shared local hinge axis to one world point", {
                        "state": state,
                        "hinge": hinge,
                        "upstream": upstream,
                        "downstream": downstream,
                        "local_axis_point_mm": local_axis_point_mm,
                        "world_axis_upstream_mm": world_axis_upstream,
                        "world_axis_downstream_mm": world_axis_downstream,
                        "world_axis_delta_mm": world_axis_delta,
                        "world_axis_consistency_error_mm": world_axis_error,
                        "tolerance_mm": 0.08,
                    })
                # CylinderParams returned for a nested rigid child are in the
                # module-local authored frame.  Search the native B-rep with
                # the nominal local Y/Z signature; world axes above are a
                # separate transform-consistency witness, not search inputs.
                _pin, _face, pin_fact, _pin_child = nested_geometry(components[upstream], f"{upstream}_OUTBOARD_PIN", nominal_axis_y, PIN_RADIUS_MM, X_START_MM, types, pythoncom, 0.0)
                _bore, _bface, bore_fact, _bore_child = nested_geometry(components[downstream], f"{downstream}_INBOARD_BORE", nominal_axis_y, BORE_RADIUS_MM, X_START_MM, types, pythoncom, 0.0)
                nested_rows.append({
                    "hinge": hinge,
                    "entity_signature_coordinate_frame": "NESTED_MODULE_LOCAL",
                    "local_axis_point_mm": local_axis_point_mm,
                    "world_axis_upstream_mm": world_axis_upstream,
                    "world_axis_downstream_mm": world_axis_downstream,
                    "world_axis_delta_mm": world_axis_delta,
                    "world_axis_consistency_error_mm": world_axis_error,
                    "world_axis_consistency_tolerance_mm": 0.08,
                    "pin": pin_fact,
                    "bore": bore_fact,
                })
            interference = interference_fact(assembly, types, pythoncom)
            joint_pairs = {
                frozenset((norm(part_paths["ROOT"]), norm(part_paths["M1_COLLAR"]))),
                frozenset((norm(part_paths["M1_PIN"]), norm(part_paths["M2_COLLAR"]))),
                frozenset((norm(part_paths["M2_PIN"]), norm(part_paths["M3_COLLAR"]))),
            }
            # The Ø4 male / Ø4.4 female diagnostics intentionally occupy the
            # same joint volume.  Those three exact joint pairs are native
            # fit-contact witnesses, not collision failures; every other
            # positive-volume B-rep row is forbidden.
            def leaf_pair(row: Mapping[str, Any]) -> frozenset[str]:
                leaves = []
                for text in row["component_paths"]:
                    path = Path(str(text)).resolve()
                    if path.suffix.lower() == ".sldasm":
                        key = next((item for item in MODULE_KEYS if path == module_paths[item].resolve()), None)
                        if key is not None:
                            # Expanded native interference should normally
                            # report leaf SLDPRTs.  A parent-module-only row is
                            # deliberately left unmatched/forbidden because it
                            # cannot prove which rigid child generated volume.
                            return frozenset((norm(path),))
                    leaves.append(norm(path))
                return frozenset(leaves)

            unexpected_positive = [row for row in interference["positive"] if leaf_pair(row) not in joint_pairs]
            interference["accepted_joint_fit_positive_count"] = len(interference["positive"]) - len(unexpected_positive)
            interference["unexpected_positive_volume_interference_count"] = len(unexpected_positive)
            interference["unexpected_positive"] = unexpected_positive
            total_positive += len(unexpected_positive)
            if unexpected_positive:
                raise GateError("FRESH_POSITIVE_VOLUME_INTERFERENCE", "native B-rep found non-joint positive-volume collision", {"state": state, "interference": interference})
            state_rows.append({"state": state, "tuple_deg": list(LEFT_TUPLES[state]), "angles": angle_rows, "transforms": transform_rows, "signed_relative_angle_deg": signed_relative, "expected_signed_relative_angle_deg": expected_relative, "nested_face_selection": nested_rows, "interference": interference})
        L1B.close_doc(sw, model); opened_models.pop()
        L1B.close_owned_documents(sw)
        if int(L1B.value(sw, "GetDocumentCount")) != 0 or L1B.value(sw, "ActiveDoc") is not None:
            raise GateError("FRESH_SESSION_NOT_EMPTY_AFTER", "read-only verification left documents open")
        after = snapshot(Path(path) for path in build.get("cad_snapshot", {}))
        if before != after:
            raise GateError("READ_ONLY_HASH_DRIFT", "fresh read-only verification changed native CAD bytes", {"before": before, "after": after})
        receipt = {
            "schema": "F3R2_V5_SOLAR_R2B_MODULE_CHAIN_MICROFIXTURE_RECEIPT_V1",
            "timestamp_utc": utc_now(),
            "run_id": run_id,
            "classification": "R2B_A_EXACT_ARCHITECTURE_DIAGNOSTIC_GATE",
            "production_builder_sha256": builder_fact["sha256"],
            "production_builder": builder_fact,
            "production_contract_sha256": EXPECTED_PRODUCTION_CONTRACT_SHA256,
            "frozen_contract_hashes": {
                "authority": PINNED[AUTHORITY],
                "architecture": PINNED[ARCHITECTURE],
                "oracle": PINNED[ORACLE],
                "authorization": PINNED[AUTHORIZATION],
            },
            "authority_sha256": PINNED[AUTHORITY],
            "architecture_sha256": PINNED[ARCHITECTURE],
            "oracle_sha256": PINNED[ORACLE],
            "authorization_sha256": PINNED[AUTHORIZATION],
            "branch_matrix_probe_script": file_fact(BRANCH_PROBE_SCRIPT),
            "branch_matrix_result": file_fact(BRANCH_MATRIX_RESULT),
            "production_root_flip_authorization": root_authorization,
            "root_role_separation": root_separation,
            "fixture_left_per_hinge_angle_flip": dict(FIXTURE_LEFT_ANGLE_FLIP),
            "authorized_production_per_side_angle_flip": {side: dict(values) for side, values in PRODUCTION_ANGLE_FLIP.items()},
            "fixture_angle_branch_creation_contract": "DIAGNOSTIC_ROOT_EQUIVALENT_ONLY; PARENT_TO_CHILD_ROOT_FIRST; ALIGNMENT=0; FIXTURE ROOT/H23 Flip=True -> NEGATIVE; H12 Flip=False -> POSITIVE",
            "production_root_branch_contract": "ACCEPTED_CLEVIS_TO_P1_MODULE_ONLY; AUTHORIZED L ROOT Flip=False; R ROOT Flip=True; FIXTURE ROOT IS NOT PRODUCTION AUTHORITY",
            "build_session": {"pid": int(build_session["pid"]), "create_time_utc": str(build_session["create_time_utc"])},
            "verify_session": {"pid": int(verify_session["pid"]), "create_time_utc": str(verify_session["create_time_utc"])},
            "different_pid_and_create_time": True,
            "build_pid": int(build_session["pid"]),
            "build_process_create_time_unix": build_create,
            "verify_pid": int(verify_session["pid"]),
            "verify_process_create_time_unix": verify_create,
            "fresh_pid_read_only": True,
            "mutation_call_count": 0,
            "fresh_verifier_mutation_call_count": 0,
            "state_count": 7,
            "module_count": 3,
            "hinge_count": 3,
            "advanced_limit_angle_count": 3,
            "positive_volume_interference_count": total_positive,
            "production_use_permitted": True,
            "scope_of_permission": "MAY_GATE_THE_HASH_BOUND_PRODUCTION_BUILDER_ONLY; DIAGNOSTIC_CAD_ITSELF_REMAINS_NON_PRODUCTION",
            "diagnostic_fixture_root_production_use": "PROHIBITED",
            "fixture_root_is_production_root": False,
            "build_receipt": file_fact(build_path),
            "cad_pre": before,
            "cad_post": after,
            "part_readback": part_rows,
            "module_readback": module_rows,
            "chain_open": opened,
            "mate_ledger": mate_rows,
            "states": state_rows,
            "relative_angle_mapping": {
                "ROOT": "DIAGNOSTIC_ROOT_EQUIVALENT_ONLY; native alpha1=0..90; module absolute phi1=alpha1-90; parent->child Alignment=0 Flip=True; not production clevis authority",
                "H12": "native alpha2=0..90; relative module rotation +(90-alpha2); parent->child Alignment=0 Flip=False",
                "H23": "native alpha3=0..90; relative module rotation -(90-alpha3); parent->child Alignment=0 Flip=True",
            },
            "verdict": "V5_SOLAR_R2B_MODULE_CHAIN_FRESH_PID_READ_ONLY_PASS",
        }
        write_json_once(pass_path, receipt)
        return receipt
    except Exception as exc:
        for model in reversed(opened_models):
            try:
                L1B.close_doc(sw, model)
            except Exception:
                pass
        if sw is not None:
            try:
                L1B.close_owned_documents(sw)
            except Exception:
                pass
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        failure = {"schema": "F3R2_V5_SOLAR_R2B_MODULE_CHAIN_FRESH_VERIFY_FAILURE_V1", "timestamp_utc": utc_now(), "run_id": run_id, "error_code": getattr(exc, "code", "UNHANDLED_EXCEPTION"), "error": str(exc), "detail": getattr(exc, "detail", {}), "traceback": traceback.format_exc(), "verdict": "V5_SOLAR_R2B_MODULE_CHAIN_FRESH_PID_READ_ONLY_FAIL"}
        write_json_once(root / f"FRESH_VERIFY_FAIL_{stamp}.json", failure)
        raise
    finally:
        if pythoncom is not None:
            pythoncom.CoUninitialize()
        release_process_mutex(mutex)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="filesystem-only static audit; never touches SOLIDWORKS")
    audit.add_argument("--run-id")
    audit.add_argument("--production-builder", type=Path)
    build = commands.add_parser("build-stage", help="write diagnostic scratch CAD in one explicit empty PID")
    build.add_argument("--run-id", required=True)
    build.add_argument("--expected-pid", required=True, type=int)
    build.add_argument("--production-builder", required=True, type=Path)
    verify = commands.add_parser("fresh-verify", help="different-PID, read-only, zero-mutation verification")
    verify.add_argument("--run-id", required=True)
    verify.add_argument("--expected-pid", required=True, type=int)
    verify.add_argument("--production-builder", required=True, type=Path)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "audit":
            payload = static_audit(args.run_id, args.production_builder)
        elif args.command == "build-stage":
            payload = build_stage(args.run_id, args.expected_pid, args.production_builder)
        else:
            payload = fresh_verify(args.run_id, args.expected_pid, args.production_builder)
        print(json.dumps({"verdict": payload["verdict"], "run_id": payload.get("run_id"), "attempt_root": payload.get("attempt_root")}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if "PASS" in payload["verdict"] else 2
    except Exception as exc:
        payload = {"timestamp_utc": utc_now(), "exception_type": type(exc).__name__, "error_code": getattr(exc, "code", "UNHANDLED_EXCEPTION"), "error": str(exc), "detail": getattr(exc, "detail", {}), "verdict": "V5_SOLAR_R2B_MODULE_CHAIN_HOLD"}
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
