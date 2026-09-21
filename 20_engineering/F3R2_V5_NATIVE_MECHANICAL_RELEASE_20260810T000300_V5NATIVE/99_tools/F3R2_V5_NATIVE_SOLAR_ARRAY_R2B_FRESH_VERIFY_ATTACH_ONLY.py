#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fresh-process, read-only, zero-CAD-mutation verifier for solar R2B-A.

``audit`` is filesystem/source only and never imports COM.  ``verify``
attaches to one explicitly named, already-running, empty SOLIDWORKS 2024 SP5
process.  It requires the write-once R2B-A build receipt and handoff, opens all
46 native files SILENT+READ_ONLY, verifies the six rigid/default-only panel
modules and the two seven-state 3R side assemblies, then proves all protected
bytes unchanged.  It never starts or exits SOLIDWORKS and has no CAD save,
rebuild, transform-drive, mate-creation, configuration-creation, or definition
modification call.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import re
import sys
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


sys.dont_write_bytecode = True

RUN_ROOT = Path(
    r"F:\China Graduate Future Flight Vehicle Innovation Competition"
    r"\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
)
ATTEMPTS_ROOT = RUN_ROOT / "13_validation/solar_r2_attempts"
SOLIDWORKS_EXE = Path(r"F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe")

STATE_AUTHORITY = RUN_ROOT / "00_authority/V5_SOLAR_STATE_AUTHORITY_R2B.json"
ARCHITECTURE = RUN_ROOT / "00_authority/V5_SOLAR_R2_ASSEMBLY_ARCHITECTURE_DECISION.json"
STATIC_ORACLE = RUN_ROOT / "13_validation/V5_SOLAR_R2B_STATIC_KINEMATIC_ORACLE_20260812T181333.205056Z.json"
BUILD_AUTHORIZATION = RUN_ROOT / "13_validation/V5_SOLAR_R2B_BUILD_AUTHORIZATION.json"
PRODUCTION_ROOT_FLIP_AUTHORIZATION = RUN_ROOT / "13_validation/V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_V1.json"
PRODUCTION_ROOT_FLIP_AUTHORIZER_SOURCE = RUN_ROOT / "99_tools/F3R2_V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZE.py"
PRODUCTION_ROOT_BRANCH_PROBE_SOURCE = RUN_ROOT / "99_tools/F3R2_V5_DIAG_SOLAR_R2B_PRODUCTION_ROOT_BRANCH_PROTOCOL_ATTACH_ONLY.py"
PRODUCTION_ROOT_BRANCH_PROBE_RESULT = RUN_ROOT / "99_tools/probe_logs/V5_SOLAR_R2B_PRODUCTION_ROOT_BRANCH_20260813T_ROOTPROTOCOL_G1/RESULT.json"
P5_ROOT_BRANCH_FAILURE = RUN_ROOT / "13_validation/solar_r2_attempts/20260813T164200Z_P5A5/evidence/BUILD_FAILURE_20260813T084845.277077Z.json"
BUILDER_SOURCE = RUN_ROOT / "99_tools/F3R2_V5_NATIVE_SOLAR_ARRAY_R2B_BUILD_STAGE_ATTACH_ONLY.py"
MICROFIXTURE_SOURCE = RUN_ROOT / "99_tools/F3R2_V5_DIAG_SOLAR_R2B_MODULE_CHAIN_ATTACH_ONLY.py"
MICROFIXTURE_ATTEMPTS_ROOT = RUN_ROOT / "99_tools/probe_logs"
BRANCH_PROBE_SOURCE = RUN_ROOT / "99_tools/F3R2_V5_DIAG_SOLAR_R2B_ROOT_BRANCH_PROBE_ATTACH_ONLY.py"
BRANCH_PROBE_RESULT = RUN_ROOT / "99_tools/probe_logs/V5_SOLAR_R2B_ROOT_BRANCH_20260813T1232Z_BRANCH1/RESULT.json"
FROZEN_BINDINGS: Tuple[Tuple[str, Path, str], ...] = (
    ("state_authority_r2b", STATE_AUTHORITY, "BA639C6BF4F0875B6FD9AFFF2E6CA7A5AA3BA1AF77C6BD5FEC07A8EB62D8E6D8"),
    ("assembly_architecture", ARCHITECTURE, "3CC38465A6B7FA6E91F275BAE4052E1787B5A44A6F196AFCEFA88AA7D209D545"),
    ("static_oracle_r2b", STATIC_ORACLE, "F4E5E0CD5A8559991B60826C6221294948CD07889836500D81527AE0982196F6"),
    ("r2b_build_authorization", BUILD_AUTHORIZATION, "BAD16D48EAEDCF27B3953831B7108A4ADB95CC3DD8F476FB02CB29EAE454FCCB"),
    ("r2b_angle_branch_probe_source", BRANCH_PROBE_SOURCE, "3680D614AD10728FC54309D4E8CFC64DB518FA3864989F86B968ED45E119FFE8"),
    ("r2b_angle_branch_probe_result", BRANCH_PROBE_RESULT, "52FF2A64E874FD782008E5971CB3154C976E10068C994337CB0611195E97A77A"),
    ("production_root_flip_authorization", PRODUCTION_ROOT_FLIP_AUTHORIZATION, "07D3D9380668E0308981D0BF85D4EB0951789793F90EAB97503BB23C82C7280E"),
    ("production_root_flip_authorizer_source", PRODUCTION_ROOT_FLIP_AUTHORIZER_SOURCE, "A05E0492CEB5CB6D9A7710BFEB4D04EE9FC1F3E5F54EA51B3360A64B01175726"),
    ("production_root_branch_probe_source", PRODUCTION_ROOT_BRANCH_PROBE_SOURCE, "FBF3F0D53E3078D9E5A5B2CB0060A4EDBCC8BD7F01E6DE7B3C19F9A4ABD3F1D2"),
    ("production_root_branch_probe_result", PRODUCTION_ROOT_BRANCH_PROBE_RESULT, "18393CAC2423032AFF309361E37D5CE3612AA086C9EA5FD16D991EC2DF593DA0"),
    ("p5_root_branch_failure", P5_ROOT_BRANCH_FAILURE, "745F069350F1E04158C9D3479AEDDBAD1E55BB258CE07ED97FD061DBEE249A3E"),
)
# Updated only after the builder owner declares its source immutable.  A fresh
# verifier must never accept a receipt produced by an older R2/R2B draft.
EXPECTED_BUILDER_SHA256 = "E5255A4BE587C43F0C237367E0B2C90E2AF8C66F230A9C630B4D596922F96C4C"
EXPECTED_BUILD_CONTRACT_SHA256 = "B885E6B4F51663DC268FE6C9F5E497B99A514BE1706B616C230D5D35A2D697FB"
EXPECTED_FINAL_MICRO_SOURCE_SHA256 = "CD68B1CA65F200140A331C385902ABA5222D6F0C9D99F59B102760CBA9F5324E"
EXPECTED_ROOT_FLIP_AUTHORIZATION_SHA256 = "07D3D9380668E0308981D0BF85D4EB0951789793F90EAB97503BB23C82C7280E"
EXPECTED_ROOT_FLIP_EVIDENCE_CHAIN_SHA256 = "316A433EF215A38A7E090E0AE88E3E6362D6079B25ACBB01596C810CD2790889"
PRE_PATCH_BUILDER_SHA256 = "A91EC2A29F28F5BA64FD552F75AB6204BA32318604DEB3569D4ACA4C61C05D43"
PRE_PATCH_CONTRACT_SHA256 = "891052B9291FCE299DCEBB7B539D8056525A1F242E8BD5B7417EF347138ABC44"

EXPECTED_BUILD_SCHEMA = "F3R2_V5_SOLAR_R2B_A_BUILD_STAGE_RECEIPT_V1"
EXPECTED_BUILD_VERDICT = "V5_SOLAR_R2B_A_BUILD_STAGE_PASS_AWAITING_FRESH_PID_VERIFIER"
EXPECTED_HANDOFF_SCHEMA = "F3R2_V5_SOLAR_R2B_A_FRESH_PID_VERIFIER_HANDOFF_V1"
EXPECTED_MICRO_BUILD_SCHEMA = "F3R2_V5_SOLAR_R2B_MODULE_CHAIN_BUILD_STAGE_RECEIPT_V1"
EXPECTED_MICRO_BUILD_VERDICT = "V5_SOLAR_R2B_MODULE_CHAIN_BUILD_STAGE_SAME_PID_PASS"
EXPECTED_MICRO_FRESH_SCHEMA = "F3R2_V5_SOLAR_R2B_MODULE_CHAIN_MICROFIXTURE_RECEIPT_V1"
EXPECTED_MICRO_FRESH_VERDICT = "V5_SOLAR_R2B_MODULE_CHAIN_FRESH_PID_READ_ONLY_PASS"
EXPECTED_SW_REVISION_PREFIX = "32.5."
EXPECTED_COUNTS = {"SLDPRT": 38, "MODULE_SLDASM": 6, "SIDE_SLDASM": 2, "TOTAL_CAD": 46}
BUILD_RECEIPT_NAME = "BUILD_STAGE_RECEIPT.json"
HANDOFF_NAME = "FRESH_PID_VERIFIER_HANDOFF.json"
CAD_MANIFEST_NAME = "CAD_MANIFEST.json"
CAD_MANIFEST_SHA256_NAME = "CAD_MANIFEST_SHA256.txt"
MICRO_BUILD_RECEIPT_NAME = "BUILD_STAGE_RECEIPT.json"
MICRO_FRESH_RECEIPT_NAME = "F3R2_V5_SOLAR_R2B_MODULE_CHAIN_MICROFIXTURE_RECEIPT.json"
ATTEMPT_ID_RE = re.compile(r"^V5_SOLAR_R2B_BUILD_(?P<storage_id>20\d{6}T\d{6}Z_[A-Z0-9]{4,16})$")
STORAGE_ID_RE = re.compile(r"^20\d{6}T\d{6}Z_[A-Z0-9]{4,16}$")
ANNULUS_NATIVE_FEATURE_CONTRACT: Dict[str, Any] = {
    "schema": "F3R2_V5_SOLAR_R2B_A_ANNULUS_NATIVE_FEATURE_CONTRACT_V1",
    "production_part_count": 4,
    "outer_radius_mm": 2.75,
    "bore_radius_mm": 2.2,
    "body_depth_mm": 28.0,
    "auxiliary_holes": "EMPTY_LIST_ONLY",
    "feature_sequence": [
        "FRONT_PLANE_SINGLE_OUTER_CIRCLE_FEATUREEXTRUSION2_BOSS",
        "POSITIVE_DEPTH_END_PLANE_SINGLE_INNER_CIRCLE_FEATURECUT3_OVERSHOOT",
    ],
    "cut_depth_multiplier": 2.0,
    "solid_body_count_after_outer_boss": 1,
    "solid_body_count_after_bore_cut": 1,
    "bore_brep": {
        "local_axis": "+/-Z",
        "axis_point_xy_mm": [0.0, 0.0],
        "candidate_count": 1,
        "radius_tolerance_mm": 0.06,
        "axis_point_tolerance_mm": 0.08,
        "axial_length_tolerance_mm": 0.12,
    },
}
COLLAR_KEYS: Tuple[str, ...] = tuple(f"SOLAR_{side}{index}_INBOARD_HINGE_COLLAR_IF_R2B" for side in ("L", "R") for index in (2, 3))
ROOT_LUG_BORE_SELECTION_CONTRACT: Dict[str, Any] = {
    "schema": "F3R2_V5_SOLAR_R2B_A_ROOT_LUG_BORE_SELECTION_CONTRACT_V1",
    "helper": "loop1b.cylinder_entity",
    "candidate_count": 2,
    "radius_mm": 4.2,
    "coaxial_axis": "+/-X",
    "axis_z_mm": 0.0,
    "candidate_order": "ASCENDING_CYLINDER_PARAMS_X_THEN_DESCENDING_FACE_AREA",
    "chosen_candidate": "FIRST_MINIMUM_WORLD_X",
    "chosen_axis_x_mm": -82.0,
    "chosen_face_axial_length_mm": 10.0,
    "coordinate_frame_at_mate_creation": "SIDE_ASSEMBLY_WORLD_WITH_NOMINAL_MODULE_IDENTITY",
    "tolerances_mm": {"axis_point": 0.06, "radius": 0.06, "axial_length": 0.12},
    "sides": {
        "L": {"u_lug_path": "01_native_parts/wing_root/loop1b/LEFT_PANEL_SIDE_U_LUG_NATIVE.SLDPRT", "u_lug_sha256": "5E8BDB76637B7F394560A95A938C3FF363DDAE88950E93266CFE66837ABCD749", "axis_y_mm": 143.15},
        "R": {"u_lug_path": "01_native_parts/wing_root/loop1b/RIGHT_PANEL_SIDE_U_LUG_NATIVE.SLDPRT", "u_lug_sha256": "A5A86890E07990706D106170B99DA0E68A31103EA73BF7161497669BCA4C557B", "axis_y_mm": -143.15},
    },
}
INTERPANEL_NESTED_BREP_FRAME_CONTRACT: Dict[str, Any] = {
    "schema": "F3R2_V5_SOLAR_R2B_A_INTERPANEL_NESTED_BREP_FRAME_CONTRACT_V1",
    "scope": "L/R H12/H23 NESTED RIGID MODULE CHILDREN",
    "entity_signature_coordinate_frame": "NESTED_CHILD_PART_LOCAL",
    "cylinder": {"local_axis": "+/-Z", "local_axis_point_xy_mm": [0.0, 0.0], "candidate_count": 1, "pin_radius_mm": 2.0, "collar_bore_radius_mm": 2.2, "axial_length_mm": 28.0},
    "axial_face": {"local_plane_z_mm": 0.0, "candidate_count": 1, "normal": "+/-Z"},
    "canonical_local_axis_points_mm": [[0.0, 0.0, 0.0], [0.0, 0.0, 28.0]],
    "nominal_world": {
        "local_z0_world_x_mm": -75.0,
        "local_z28_world_x_mm": -47.0,
        "axis_direction": "+/-X",
        "axis_z_mm": 0.0,
        "hinge_y_mm": {"L": {"H12": 199.81666666666666, "H23": 256.48333333333335}, "R": {"H12": -199.81666666666666, "H23": -256.48333333333335}},
    },
    "world_continuity": "PIN_AND_COLLAR_CANONICAL_LOCAL_Z0_POINTS_COINCIDE_AND_AXES_ARE_COLLINEAR",
    "pose_stability": "UPSTREAM_AND_DOWNSTREAM_MODULE_TRANSFORMS_UNCHANGED_ACROSS_CONCENTRIC_AND_COINCIDENT_CREATION",
    "tolerances": {"local_axis_point_mm": 0.08, "radius_mm": 0.06, "axial_length_mm": 0.12, "world_point_mm": 0.08, "world_direction_cross_norm": 1.0e-6, "module_transform_max_abs": 2.0e-7},
}
CONFIGS: Tuple[str, ...] = (
    "SOLAR_STOWED",
    "SOLAR_DEPLOY_STAGE1",
    "SOLAR_DEPLOY_STAGE2",
    "SOLAR_DEPLOYED_NOMINAL",
    "SOLAR_LEFT_FAIL",
    "SOLAR_RIGHT_FAIL",
    "SOLAR_BOTH_FAIL",
)
MODULE_NAMES = {f"{side}{index}": f"SOLAR_PANEL_MODULE_{side}{index}_R2B.SLDASM" for side in ("L", "R") for index in (1, 2, 3)}
SIDE_NAMES = {side: f"{side}_SOLAR_ARRAY_R2B_SUCCESSOR.SLDASM" for side in ("L", "R")}

SW_PROG_ID = "SldWorks.Application"
SW_TLB = ("{83A33D31-27C5-11CE-BFD4-00400513BB57}", 0, 32, 0)
SW_DOC_PART = 1
SW_DOC_ASSEMBLY = 2
SW_OPEN_SILENT = 1
SW_OPEN_READ_ONLY = 2
SW_COMPONENT_RESOLVED = 2
SW_COMPONENT_RIGID = 0
SW_FULLY_CONSTRAINED = 3
SW_MATE_COINCIDENT = 0
SW_MATE_CONCENTRIC = 1
SW_MATE_ANGLE = 6
SW_MATE_LOCK = 16
SW_ALIGN_ALIGNED = 0
ANGLE_LOWER_RAD = 0.0
ANGLE_UPPER_RAD = math.pi / 2.0
TRANS_TOL_MM = 0.08
ROT_TOL_DEG = 0.15
ANGLE_TOL_RAD = 1.0e-9

PRE_PATCH_FLIP_SIDES: Dict[str, Dict[str, bool]] = {
    "L": {"ROOT": True, "H12": False, "H23": True},
    "R": {"ROOT": False, "H12": True, "H23": False},
}
PRODUCTION_FLIP_SIDES: Dict[str, Dict[str, bool]] = {
    "L": {"ROOT": False, "H12": False, "H23": True},
    "R": {"ROOT": True, "H12": True, "H23": False},
}
SIGNED_FOLD_DIRECTION: Dict[str, Dict[str, int]] = {
    "L": {"ROOT": -1, "H12": +1, "H23": -1},
    "R": {"ROOT": +1, "H12": -1, "H23": +1},
}

FLIP_CONTRACT: Dict[str, Any] = {
    "schema": "F3R2_V5_SOLAR_R2B_A_LIMIT_ANGLE_BRANCH_CONTRACT_V2",
    "selection_order": "PARENT_THEN_CHILD",
    "alignment": SW_ALIGN_ALIGNED,
    "alignment_name": "SW_ALIGN_ALIGNED",
    "interpanel_false_branch": "POSITIVE",
    "interpanel_true_branch": "NEGATIVE",
    "root_branch_semantics": "SIDE_SPECIFIC_ACCEPTED_CLEVIS_ENDPOINT_AUTHORIZATION",
    "sides": PRODUCTION_FLIP_SIDES,
    "evidence": {
        "interpanel_generic_probe": {
            "scope": "H12_H23_BRANCH_POLARITY_ONLY",
            "probe_script_sha256": "3680D614AD10728FC54309D4E8CFC64DB518FA3864989F86B968ED45E119FFE8",
            "probe_result_sha256": "52FF2A64E874FD782008E5971CB3154C976E10068C994337CB0611195E97A77A",
            "angles_deg": [1.0, 89.0, 90.0],
            "selection_order_in_probe": "ROOT_FIRST",
            "selected_case_count": 6,
        },
        "production_root_authorization": {
            "scope": "ROOT_ONLY_ACCEPTED_CLEVIS_TO_P1_MODULE",
            "authorization_receipt_sha256": EXPECTED_ROOT_FLIP_AUTHORIZATION_SHA256,
            "evidence_chain_sha256": EXPECTED_ROOT_FLIP_EVIDENCE_CHAIN_SHA256,
            "probe_source_sha256": "FBF3F0D53E3078D9E5A5B2CB0060A4EDBCC8BD7F01E6DE7B3C19F9A4ABD3F1D2",
            "probe_result_sha256": "18393CAC2423032AFF309361E37D5CE3612AA086C9EA5FD16D991EC2DF593DA0",
            "protocols": ["FULL_TABLE_LIKE", "PER_STATE_SUPPRESS_BEFORE_DIMENSION"],
            "angles_deg": [1.0, 89.0, 90.0],
            "case_count": 24,
            "winner_flips": {"L": False, "R": True},
        },
    },
}

PASS_RELATIVE = Path("evidence/F3R2_V5_SOLAR_R2B_A_FRESH_VERIFY_PASS.json")
FAIL_GLOB = "F3R2_V5_SOLAR_R2B_A_FRESH_VERIFY_FAIL_*.json"

# Source audit rejects direct and value()/getattr() calls in these CAD mutation
# families.  Closing an owned read-only document and switching the active saved
# configuration are session/read-navigation operations, not CAD writes.
FORBIDDEN_CALL_PREFIXES: Tuple[str, ...] = (
    "save",
    "settransform",
    "editrebuild",
    "forcerebuild",
    "addmate",
    "addconfiguration",
    "modifydefinition",
    "newdocument",
    "addcomponent",
    "replacecomponent",
    "fixcomponent",
    "unfixcomponent",
    "delete",
    "editdelete",
    "exitapp",
    "dispatch",
)


class VerifyError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Mapping[str, Any]] = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.detail = dict(detail or {})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_fact(path: Path) -> Dict[str, Any]:
    resolved = path.resolve()
    return {"path": norm(resolved), "bytes": resolved.stat().st_size, "sha256": sha256(resolved)}


def load_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise VerifyError("JSON_ROOT_FAIL", "JSON root must be an object", {"path": norm(path)})
    return payload


def canonical_json_sha256(value_in: Any) -> str:
    encoded = json.dumps(value_in, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def parse_utc_timestamp(value_in: Any, label: str) -> float:
    if not isinstance(value_in, str) or not value_in:
        raise VerifyError("TIMESTAMP_TEXT_FAIL", f"{label} is not a non-empty timestamp", {"value": value_in})
    try:
        parsed = datetime.fromisoformat(value_in.replace("Z", "+00:00"))
    except ValueError as exc:
        raise VerifyError("TIMESTAMP_PARSE_FAIL", f"{label} is not ISO-8601", {"value": value_in}) from exc
    if parsed.tzinfo is None:
        raise VerifyError("TIMESTAMP_TIMEZONE_FAIL", f"{label} lacks a timezone", {"value": value_in})
    return parsed.timestamp()


def source_literal_assignment(tree: ast.AST, name: str) -> Any:
    matches: List[Any] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            value_node = node.value
            try:
                matches.append(ast.literal_eval(value_node))
            except (TypeError, ValueError) as exc:
                raise VerifyError("SOURCE_LITERAL_FAIL", f"{name} is not a literal assignment") from exc
    if len(matches) != 1:
        raise VerifyError("SOURCE_ASSIGNMENT_CARDINALITY_FAIL", f"{name} does not have exactly one literal assignment", {"count": len(matches)})
    return matches[0]


def microfixture_source_audit() -> Dict[str, Any]:
    if not MICROFIXTURE_SOURCE.is_file():
        raise VerifyError("MICRO_SOURCE_MISSING", "final module-chain microfixture source is absent", {"path": norm(MICROFIXTURE_SOURCE)})
    source_fact = file_fact(MICROFIXTURE_SOURCE)
    if source_fact["sha256"] != EXPECTED_FINAL_MICRO_SOURCE_SHA256:
        raise VerifyError("MICRO_SOURCE_HASH_FAIL", "module-chain microfixture source differs from the final frozen source", {"expected": EXPECTED_FINAL_MICRO_SOURCE_SHA256, "actual": source_fact})
    source = MICROFIXTURE_SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(MICROFIXTURE_SOURCE))
    builder_literal = source_literal_assignment(tree, "EXPECTED_PRODUCTION_BUILDER_SHA256")
    contract_literal = source_literal_assignment(tree, "EXPECTED_PRODUCTION_CONTRACT_SHA256")
    left_flip_literal = source_literal_assignment(tree, "FIXTURE_LEFT_ANGLE_FLIP")
    production_flip_literal = source_literal_assignment(tree, "PRODUCTION_ANGLE_FLIP")
    required_literals = {
        EXPECTED_MICRO_BUILD_SCHEMA,
        EXPECTED_MICRO_BUILD_VERDICT,
        EXPECTED_MICRO_FRESH_SCHEMA,
        EXPECTED_MICRO_FRESH_VERDICT,
        MICRO_BUILD_RECEIPT_NAME,
        MICRO_FRESH_RECEIPT_NAME,
        FLIP_CONTRACT["evidence"]["interpanel_generic_probe"]["probe_script_sha256"],
        FLIP_CONTRACT["evidence"]["interpanel_generic_probe"]["probe_result_sha256"],
        EXPECTED_ROOT_FLIP_AUTHORIZATION_SHA256,
        EXPECTED_ROOT_FLIP_EVIDENCE_CHAIN_SHA256,
    }
    checks = {
        "source_sha256": source_fact["sha256"] == EXPECTED_FINAL_MICRO_SOURCE_SHA256,
        "production_builder_sha256": builder_literal == EXPECTED_BUILDER_SHA256,
        "production_contract_sha256": contract_literal == EXPECTED_BUILD_CONTRACT_SHA256,
        "left_flip_contract": left_flip_literal == {"ROOT": True, "H12": False, "H23": True},
        "authorized_production_flip_contract": production_flip_literal == PRODUCTION_FLIP_SIDES,
        "schemas_verdicts_filenames_and_branch_hashes": all(token in source for token in required_literals),
    }
    if not all(checks.values()):
        raise VerifyError("MICRO_SOURCE_CONTRACT_FAIL", "final microfixture source literals differ from the release contract", {"checks": checks})
    return {
        "source": source_fact,
        "expected_sha256": EXPECTED_FINAL_MICRO_SOURCE_SHA256,
        "production_builder_sha256": builder_literal,
        "production_contract_sha256": contract_literal,
        "fixture_left_per_hinge_angle_flip": left_flip_literal,
        "authorized_production_per_side_angle_flip": production_flip_literal,
        "fixture_root_note": "MICRO_ROOT_FLIP_IS_FIXTURE_LOCAL_NOT_PRODUCTION_ACCEPTED_CLEVIS_AUTHORITY",
        "checks": checks,
        "verdict": "V5_SOLAR_R2B_A_MICROFIXTURE_SOURCE_PROVENANCE_PASS",
    }


def write_json_once(path: Path, payload: Mapping[str, Any], attempt_root: Path) -> None:
    parent = path.parent.resolve()
    root = attempt_root.resolve()
    if parent != root and root not in parent.parents:
        raise VerifyError("EVIDENCE_SCOPE_FAIL", "evidence path escapes attempt root", {"path": norm(path)})
    # Complete strict serialization before creating either the parent directory or
    # the write-once target.  A non-JSON value (including pathlib.Path) therefore
    # cannot leave a truncated terminal-evidence file behind.
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded)
        stream.write("\n")


def is_under(path: Path, root: Path) -> bool:
    candidate, parent = path.resolve(), root.resolve()
    return candidate == parent or parent in candidate.parents


def receipt_storage_identity(payload: Mapping[str, Any], label: str) -> Dict[str, str]:
    attempt_id = payload.get("attempt_id")
    storage_id = payload.get("storage_id")
    match = ATTEMPT_ID_RE.fullmatch(attempt_id) if isinstance(attempt_id, str) else None
    if (
        match is None
        or not isinstance(storage_id, str)
        or STORAGE_ID_RE.fullmatch(storage_id) is None
        or Path(storage_id).name != storage_id
        or match.group("storage_id") != storage_id
    ):
        raise VerifyError(
            "ATTEMPT_STORAGE_IDENTITY_FAIL",
            f"{label} does not carry one injective semantic-attempt/physical-storage identity",
            {"attempt_id": attempt_id, "storage_id": storage_id},
        )
    return {"attempt_id": attempt_id, "storage_id": storage_id}


def root_storage_identity(attempt_root: Path) -> Dict[str, str]:
    storage_id = attempt_root.resolve().name
    if STORAGE_ID_RE.fullmatch(storage_id) is None or Path(storage_id).name != storage_id:
        raise VerifyError("STORAGE_ID_ROOT_FAIL", "attempt root name is not one safe physical storage token", {"storage_id": storage_id})
    return {"attempt_id": f"V5_SOLAR_R2B_BUILD_{storage_id}", "storage_id": storage_id}


def assert_attempt_root(path: Path) -> Path:
    raw, resolved = path.absolute(), path.resolve()
    controlled_root = ATTEMPTS_ROOT.resolve()
    if not resolved.is_dir() or resolved.parent != controlled_root:
        raise VerifyError("ATTEMPT_ROOT_SCOPE_FAIL", "attempt root must be an existing direct child of the controlled R2 attempts directory", {"path": str(raw)})
    root_storage_identity(resolved)
    cursor = raw
    while cursor != ATTEMPTS_ROOT.absolute() and cursor != cursor.parent:
        if cursor.is_symlink():
            raise VerifyError("ATTEMPT_SYMLINK_FAIL", "attempt path contains a symlink", {"path": str(cursor)})
        cursor = cursor.parent
    return resolved


def assert_scoped_file(path: Path, attempt_root: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file() or not is_under(resolved, attempt_root) or path.absolute().is_symlink():
        raise VerifyError("SCOPED_FILE_FAIL", f"{label} must be a regular file inside the attempt", {"path": norm(resolved)})
    return resolved


def value(obj: Any, name: str, *args: Any) -> Any:
    member = getattr(obj, name)
    return member(*args) if callable(member) else member


def unpack(result: Any) -> Tuple[Any, List[Any]]:
    if isinstance(result, tuple):
        return result[0], list(result[1:])
    return result, []


def as_list(value_in: Any) -> List[Any]:
    if value_in is None:
        return []
    return list(value_in) if isinstance(value_in, (tuple, list)) else [value_in]


def wrap(obj: Any, interface: str, types: Any, pythoncom: Any) -> Any:
    klass = getattr(types, interface)
    ole = obj._oleobj_.QueryInterface(klass.CLSID, pythoncom.IID_IDispatch)
    return klass(ole)


def direct_call_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return None


def is_forbidden_api(name: str) -> bool:
    lowered = name.casefold()
    return any(lowered.startswith(prefix) for prefix in FORBIDDEN_CALL_PREFIXES)


def architecture_external_facts(architecture: Mapping[str, Any]) -> Dict[Path, Dict[str, Any]]:
    """Resolve every frozen root-core and root-envelope live CAD reference."""
    rows: List[Tuple[str, Any]] = []
    live = architecture.get("root_live_references")
    envelope = architecture.get("root_envelope_live_references")
    if not isinstance(live, dict) or not isinstance(envelope, dict):
        raise VerifyError("ARCHITECTURE_ROOT_REFERENCE_FAIL", "architecture lacks root live/envelope reference maps")
    for side in ("LEFT", "RIGHT"):
        side_live, side_envelope = live.get(side), envelope.get(side)
        if not isinstance(side_live, dict) or not isinstance(side_envelope, dict):
            raise VerifyError("ARCHITECTURE_ROOT_SIDE_FAIL", "architecture lacks one root side map", {"side": side})
        rows.extend((f"root_live.{side}.{role}", value_in) for role, value_in in side_live.items())
        rows.extend((f"root_envelope.{side}.{role}", value_in) for role, value_in in side_envelope.items())
    for role in ("shared_spacer", "shared_grommet", "shared_stop_pad"):
        rows.append((f"root_live.{role}", live.get(role)))
    facts: Dict[Path, Dict[str, Any]] = {}
    for label, row in rows:
        if not isinstance(row, list) or len(row) != 2 or not all(isinstance(item, str) for item in row):
            raise VerifyError("ARCHITECTURE_ROOT_ROW_FAIL", "root reference must be [relative_path, sha256]", {"label": label, "row": row})
        relative, expected = row
        if Path(relative).is_absolute():
            raise VerifyError("ARCHITECTURE_ROOT_ABSOLUTE_FAIL", "root reference must be V5-relative", {"label": label})
        path = (RUN_ROOT / relative).resolve()
        if not path.is_file() or not is_under(path, RUN_ROOT):
            raise VerifyError("ARCHITECTURE_ROOT_PATH_FAIL", "root reference is absent or outside V5", {"label": label, "path": norm(path)})
        fact = file_fact(path)
        if fact["sha256"] != expected.upper():
            raise VerifyError("ARCHITECTURE_ROOT_HASH_FAIL", "root reference hash differs from frozen architecture", {"label": label, "expected": expected, "actual": fact["sha256"]})
        if path in facts:
            raise VerifyError("ARCHITECTURE_ROOT_DUPLICATE_FAIL", "root reference path is duplicated", {"label": label, "path": norm(path)})
        facts[path] = {**fact, "architecture_label": label}
    if len(facts) != 19:
        raise VerifyError("ARCHITECTURE_ROOT_COUNT_FAIL", "frozen root live/envelope set must contain exactly 19 files", {"count": len(facts)})
    return facts


def production_root_flip_authorization_audit() -> Dict[str, Any]:
    receipt_fact = file_fact(PRODUCTION_ROOT_FLIP_AUTHORIZATION)
    if receipt_fact["sha256"] != EXPECTED_ROOT_FLIP_AUTHORIZATION_SHA256:
        raise VerifyError("ROOT_FLIP_AUTHORIZATION_HASH_FAIL", "production ROOT Flip authorization hash differs", {"actual": receipt_fact})
    payload = load_json(PRODUCTION_ROOT_FLIP_AUTHORIZATION)
    patch = payload.get("authorized_patch", {})
    expected_patch_core = {
        "authorization_scope": "PRODUCTION_ROOT_LIMIT_ANGLE_FLIP_ONLY",
        "before": PRE_PATCH_FLIP_SIDES,
        "after": PRODUCTION_FLIP_SIDES,
        "changed_cells": [
            {"side": "L", "joint": "ROOT", "before": True, "after": False},
            {"side": "R", "joint": "ROOT", "before": False, "after": True},
        ],
        "unchanged_cells": [
            {"side": side, "joint": joint, "value": PRE_PATCH_FLIP_SIDES[side][joint]}
            for side in ("L", "R")
            for joint in ("H12", "H23")
        ],
    }
    winner_summary = payload.get("production_root_probe_validation", {}).get("winner_summary", {})
    expected_winners = {
        side: {
            protocol: {
                "winner_flip": PRODUCTION_FLIP_SIDES[side]["ROOT"],
                "winner_flips": [PRODUCTION_FLIP_SIDES[side]["ROOT"]],
                "betas_deg": [1.0, 89.0, 90.0],
                "all_winner_cases_side_expected": True,
                "all_loser_cases_opposite_mirror": True,
            }
            for protocol in ("FULL_TABLE_LIKE", "PER_STATE_SUPPRESS_BEFORE_DIMENSION")
        }
        for side in ("L", "R")
    }
    lineage = payload.get("lineage", {})
    expected_lineage = {
        "producer": file_fact(PRODUCTION_ROOT_FLIP_AUTHORIZER_SOURCE),
        "p5_failure_receipt": file_fact(P5_ROOT_BRANCH_FAILURE),
        "production_root_probe_source": file_fact(PRODUCTION_ROOT_BRANCH_PROBE_SOURCE),
        "production_root_probe_result": file_fact(PRODUCTION_ROOT_BRANCH_PROBE_RESULT),
        "state_authority": file_fact(STATE_AUTHORITY),
        "static_oracle": file_fact(STATIC_ORACLE),
    }
    pre_builder = lineage.get("pre_patch_builder", {})
    lineage_checks = {label: lineage.get(label) == fact for label, fact in expected_lineage.items()}
    lineage_checks.update({
        "pre_patch_builder": (
            isinstance(pre_builder, dict)
            and pre_builder.get("path") == norm(BUILDER_SOURCE)
            and pre_builder.get("bytes") == 152050
            and pre_builder.get("sha256") == PRE_PATCH_BUILDER_SHA256
        ),
        "pre_patch_contract": lineage.get("pre_patch_contract_sha256") == PRE_PATCH_CONTRACT_SHA256,
        "probe_input_manifest": lineage.get("probe_input_manifest_sha256") == "13EE8094C8D2492185E770620CD2ADE15B7D10C058575390E649D789F3AE399A",
        "probe_case_semantics": lineage.get("probe_case_semantics_sha256") == "788354B55B10AFE2463C96978BDB59EB849261AD47A6FF3B1CC9FA089DF12C4A",
        "p5_cad_manifest": lineage.get("p5_cad_manifest_sha256") == "50E1D492599F882B488F53CE0D317D2219C96A98BCC76545A4B732F024CF0DF8",
    })
    claims = payload.get("claims", {})
    digest_payload = {
        "lineage": lineage,
        "failure_signature": payload.get("p5_failure_lineage", {}).get("failure_signature"),
        "winner_summary": winner_summary,
        "authorized_patch": patch,
    }
    computed_digest = canonical_json_sha256(digest_payload)
    checks = {
        "schema": payload.get("schema") == "F3R2_V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_V1",
        "verdict": payload.get("verdict") == "V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_PATCH_ONLY_AUTHORIZED",
        "classification": payload.get("classification") == "ENGINEERING_EVIDENCE_BRIDGE__PATCH_AUTHORIZATION_ONLY",
        "scope": payload.get("scope") == "V5_NATIVE_FINALIZATION/MULTI_PANEL_SOLAR_ARRAY_CANDIDATE/ROOT_LIMIT_ANGLE_BRANCH",
        "pre_patch_contract": (
            payload.get("pre_patch_flip_contract", {}).get("schema") == "F3R2_V5_SOLAR_R2B_A_LIMIT_ANGLE_BRANCH_CONTRACT_V1"
            and payload.get("pre_patch_flip_contract", {}).get("sides") == PRE_PATCH_FLIP_SIDES
        ),
        "patch_core": all(patch.get(key) == value for key, value in expected_patch_core.items()),
        "patch_policy": (
            patch.get("post_patch_build_required") is True
            and patch.get("different_pid_read_only_fresh_verification_required") is True
            and patch.get("promotion_authorized") is False
            and "H12_OR_H23_FLIP" in patch.get("prohibited_changes", [])
            and "DIMENSION_WRITE_OR_POSE_RESTORE_PROTOCOL" in patch.get("prohibited_changes", [])
        ),
        "winner_summary": winner_summary == expected_winners,
        "probe_case_count": payload.get("production_root_probe_validation", {}).get("factorial", {}).get("case_count") == 24,
        "probe_semantics": (
            payload.get("production_root_probe_validation", {}).get("all_driver_readbacks_exact") is True
            and payload.get("production_root_probe_validation", {}).get("all_angle_definitions_advanced_0_to_90") is True
            and payload.get("production_root_probe_validation", {}).get("all_final_mates_healthy_and_unsuppressed") is True
        ),
        "claims": (
            claims.get("solidworks_touched") is False
            and claims.get("cad_write_calls") == 0
            and claims.get("cad_files_mutated") == 0
            and claims.get("probe_history_modified") is False
            and claims.get("production_build_passed") is False
            and claims.get("fresh_pid_verified") is False
            and claims.get("promotion_authorized") is False
        ),
        "lineage": all(lineage_checks.values()),
        "evidence_digest": (
            payload.get("evidence_chain_sha256") == EXPECTED_ROOT_FLIP_EVIDENCE_CHAIN_SHA256
            and computed_digest == EXPECTED_ROOT_FLIP_EVIDENCE_CHAIN_SHA256
        ),
    }
    if not all(checks.values()):
        raise VerifyError("ROOT_FLIP_AUTHORIZATION_SEMANTICS_FAIL", "production ROOT Flip authorization semantics differ", {"checks": checks, "lineage_checks": lineage_checks, "computed_digest": computed_digest})
    return {
        "receipt": receipt_fact,
        "schema": payload["schema"],
        "verdict": payload["verdict"],
        "evidence_chain_sha256": payload["evidence_chain_sha256"],
        "authorized_patch": patch,
        "lineage": lineage,
        "winner_summary": winner_summary,
        "case_count": 24,
        "checks": checks,
    }


def branch_evidence_audit() -> Dict[str, Any]:
    payload = load_json(BRANCH_PROBE_RESULT)
    checks = {
        "schema": payload.get("schema") == "F3R2_V5_SOLAR_R2B_ROOT_BRANCH_MATRIX_V1",
        "verdict": payload.get("verdict") == "V5_SOLAR_R2B_ROOT_BRANCH_MATRIX_COMPLETE",
        "case_count": payload.get("case_count_planned") == 24 and payload.get("case_count_complete") == 24,
        "case_rows": isinstance(payload.get("cases"), list) and len(payload.get("cases", [])) == 24,
    }
    if not all(checks.values()):
        raise VerifyError("ANGLE_BRANCH_EVIDENCE_GATE_FAIL", "frozen branch probe is incomplete", {"checks": checks})
    selected: List[Dict[str, Any]] = []
    required_negative_labels: List[str] = []
    for angle_deg in (1.0, 89.0, 90.0):
        for requested_flip in (False, True):
            matches = [
                row
                for row in payload["cases"]
                if isinstance(row, dict)
                and abs(float(row.get("angle_deg", math.inf)) - angle_deg) <= 1.0e-12
                and row.get("requested_alignment") == SW_ALIGN_ALIGNED
                and row.get("requested_flip") is requested_flip
                and row.get("swap_selection_order") is False
            ]
            if len(matches) != 1:
                raise VerifyError("ANGLE_BRANCH_EVIDENCE_CASE_FAIL", "probe lacks one parent-first/aligned case", {"angle_deg": angle_deg, "requested_flip": requested_flip, "matches": len(matches)})
            row = matches[0]
            creation = row.get("creation", {})
            creation_readback = creation.get("readback_at_creation", {}) if isinstance(creation, dict) else {}
            final_readback = row.get("final_mate_readback", {})
            pose = row.get("pose_after_restore", {})
            signed_rx_deg = float(pose.get("signed_rx_deg", math.nan)) if isinstance(pose, dict) else math.nan
            expected_branch = "NEGATIVE_EXPECTED" if requested_flip else "POSITIVE_MIRROR"
            if (
                row.get("case_complete") is not True
                or creation.get("selection_order") != "ROOT_FIRST"
                or creation.get("requested_alignment") != SW_ALIGN_ALIGNED
                or creation.get("requested_flip") is not requested_flip
                or creation_readback.get("alignment") != SW_ALIGN_ALIGNED
                or creation_readback.get("flipped") is not requested_flip
                or not isinstance(final_readback, dict)
                or final_readback.get("alignment") != SW_ALIGN_ALIGNED
                or final_readback.get("flipped") is not requested_flip
                or row.get("restored_branch") != expected_branch
                or not math.isfinite(signed_rx_deg)
                or abs(abs(signed_rx_deg) - angle_deg) > 2.0e-6
                or (signed_rx_deg >= 0.0 if requested_flip else signed_rx_deg <= 0.0)
                or abs(float(row.get("driven_readback_rad", math.inf)) - math.radians(angle_deg)) > 2.0e-9
                or abs(float(final_readback.get("angle_rad", math.inf)) - math.radians(angle_deg)) > 2.0e-9
            ):
                raise VerifyError("ANGLE_BRANCH_EVIDENCE_SEMANTICS_FAIL", "probe does not prove Flip=False positive / Flip=True negative", {"case": row.get("label"), "expected_branch": expected_branch, "signed_rx_deg": signed_rx_deg})
            if requested_flip:
                required_negative_labels.append(str(row.get("label")))
            selected.append({
                "label": str(row.get("label")),
                "angle_deg": angle_deg,
                "requested_alignment": SW_ALIGN_ALIGNED,
                "requested_flip": requested_flip,
                "selection_order": "PARENT_THEN_CHILD",
                "restored_branch": expected_branch,
                "signed_rx_deg": signed_rx_deg,
                "creation_readback": creation_readback,
                "final_readback": final_readback,
            })
    winners = payload.get("negative_branch_winners", [])
    if not isinstance(winners, list) or not set(required_negative_labels).issubset(set(winners)):
        raise VerifyError("ANGLE_BRANCH_NEGATIVE_WINNER_FAIL", "required aligned parent-first negative cases are absent", {"required": required_negative_labels, "actual": winners})
    generic_interpanel = {
        "scope": "H12_H23_BRANCH_POLARITY_ONLY",
        "probe_source": file_fact(BRANCH_PROBE_SOURCE),
        "probe_result": file_fact(BRANCH_PROBE_RESULT),
        "case_count_complete": 24,
        "selected_cases": selected,
        "selected_case_count": len(selected),
        "verdict": "V5_SOLAR_R2B_A_INTERPANEL_BRANCH_EVIDENCE_PASS",
    }
    root_authorization = production_root_flip_authorization_audit()
    return {
        "schema": "F3R2_V5_SOLAR_R2B_A_ANGLE_BRANCH_EVIDENCE_V2",
        "generic_interpanel_evidence": generic_interpanel,
        "production_root_authorization": root_authorization,
        "contract": FLIP_CONTRACT,
        "verdict": "V5_SOLAR_R2B_A_ANGLE_BRANCH_EVIDENCE_V2_PASS",
    }


def frozen_chain_audit() -> Dict[str, Any]:
    facts: Dict[str, Dict[str, Any]] = {}
    failures: List[Dict[str, Any]] = []
    root_external: Dict[Path, Dict[str, Any]] = {}
    branch_evidence: Dict[str, Any] = {}
    micro_source: Dict[str, Any] = {}
    for label, path, expected in FROZEN_BINDINGS:
        if not path.is_file():
            failures.append({"label": label, "reason": "missing", "path": norm(path)})
            continue
        fact = file_fact(path)
        facts[label] = fact
        if fact["sha256"] != expected:
            failures.append({"label": label, "reason": "hash", "expected": expected, "actual": fact["sha256"]})
    semantics: Dict[str, Any] = {}
    if not failures:
        authority = load_json(STATE_AUTHORITY)
        architecture = load_json(ARCHITECTURE)
        oracle = load_json(STATIC_ORACLE)
        authorization = load_json(BUILD_AUTHORIZATION)
        root_external = architecture_external_facts(architecture)
        branch_evidence = branch_evidence_audit()
        try:
            micro_source = microfixture_source_audit()
        except Exception as exc:
            micro_source = {"code": getattr(exc, "code", "MICRO_SOURCE_AUDIT_FAIL"), "error": str(exc), "detail": getattr(exc, "detail", {}), "verdict": "V5_SOLAR_R2B_A_MICROFIXTURE_SOURCE_PROVENANCE_HOLD"}
        semantics = {
            "authority_schema": authority.get("schema") == "F3R2_V5_SOLAR_STATE_AUTHORITY_R2B",
            "authority_variant": authority.get("candidate_geometry", {}).get("serial_fk_candidate", {}).get("variant") == "R2B_A_90_DEG_ORTHOGONAL_ZIGZAG",
            "seven_states": tuple(authority.get("states", {})) == CONFIGS,
            "architecture_status": architecture.get("status") == "V5_NATIVE_FINALIZATION_ARCHITECTURE_FROZEN_FOR_R2B_A_BUILD",
            "architecture_decision": architecture.get("decision") == "PANEL_MODULE_RIGID_ARCHITECTURE",
            "architecture_authority_binding": architecture.get("kinematic_authority", {}).get("sha256") == facts["state_authority_r2b"]["sha256"],
            "architecture_oracle_binding": architecture.get("static_oracle", {}).get("sha256") == facts["static_oracle_r2b"]["sha256"],
            "artifact_counts_38_6_2": (
                architecture.get("new_native_artifacts_per_attempt", {}).get("solar_sldprt_count"),
                architecture.get("new_native_artifacts_per_attempt", {}).get("panel_module_sldasm_count"),
                architecture.get("new_native_artifacts_per_attempt", {}).get("side_sldasm_count"),
            ) == (38, 6, 2),
            "module_default_only": architecture.get("configuration_ownership", {}).get("panel_modules") == "DEFAULT_ONLY_NO_SOLAR_STATE_CONFIGURATIONS",
            "side_owns_states": architecture.get("configuration_ownership", {}).get("side_assemblies") == "SOLE_OWNER_OF_ALL_SEVEN_SOLAR_STATES",
            "oracle_pass": oracle.get("verdict") == "V5_SOLAR_R2B_STATIC_KINEMATIC_ORACLE_PASS" and oracle.get("gates", {}).get("state_count") == 7,
            "authorization_semantics": authorization.get("schema") == "F3R2_V5_SOLAR_R2B_BUILD_AUTHORIZATION_V1" and authorization.get("verdict") == "V5_SOLAR_R2B_BUILD_AUTHORIZED_WITH_ORDERED_HOLDS",
            "root_core_plus_envelope_count": len(root_external) == 19,
            "angle_branch_evidence": branch_evidence.get("verdict") == "V5_SOLAR_R2B_A_ANGLE_BRANCH_EVIDENCE_V2_PASS",
            "production_root_flip_authorization": (
                branch_evidence.get("production_root_authorization", {}).get("evidence_chain_sha256") == EXPECTED_ROOT_FLIP_EVIDENCE_CHAIN_SHA256
                and branch_evidence.get("production_root_authorization", {}).get("authorized_patch", {}).get("after") == PRODUCTION_FLIP_SIDES
            ),
            "microfixture_source_provenance": micro_source.get("verdict") == "V5_SOLAR_R2B_A_MICROFIXTURE_SOURCE_PROVENANCE_PASS",
        }
        failures.extend({"label": key, "reason": "semantic"} for key, passed in semantics.items() if not passed)
    return {
        "facts": facts,
        "root_core_and_envelope_facts": {norm(path): fact for path, fact in sorted(root_external.items(), key=lambda item: norm(item[0]))} if not failures else {},
        "semantics": semantics,
        "angle_branch_evidence": branch_evidence if not failures else {},
        "microfixture_source_provenance": micro_source if not failures else {},
        "failures": failures,
        "verdict": "V5_SOLAR_R2B_A_FROZEN_CHAIN_PASS" if not failures else "V5_SOLAR_R2B_A_FROZEN_CHAIN_HOLD",
    }


def source_policy_audit() -> Dict[str, Any]:
    source_path = Path(__file__).resolve()
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path))
    violations: List[Dict[str, Any]] = []
    local_imports: List[Dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            called = direct_call_name(node.func)
            if called and is_forbidden_api(called):
                violations.append({"line": node.lineno, "kind": "direct_call", "api": called})
            if called in {"value", "getattr"} and len(node.args) >= 2:
                member = node.args[1]
                if isinstance(member, ast.Constant) and isinstance(member.value, str) and is_forbidden_api(member.value):
                    violations.append({"line": node.lineno, "kind": "indirect_call", "api": member.value})
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("F3R2_"):
                    local_imports.append({"line": node.lineno, "module": alias.name})
        elif isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("F3R2_"):
            local_imports.append({"line": node.lineno, "module": node.module})
    checks = {
        "forbidden_cad_mutation_calls_absent": not violations,
        "mutation_capable_local_helpers_not_imported": not local_imports,
        "attach_only_prog_id_present": SW_PROG_ID in source,
        "silent_read_only_open_flags_present": "SW_OPEN_SILENT | SW_OPEN_READ_ONLY" in source,
        "exclusive_attempt_local_evidence_present": 'open("x"' in source,
    }
    return {
        "script": file_fact(source_path),
        "checks": checks,
        "violations": violations,
        "local_helper_imports": local_imports,
        "cad_write_call_count": len(violations),
        "solidworks_touched": False,
        "verdict": "V5_SOLAR_R2B_A_FRESH_VERIFY_SOURCE_POLICY_PASS" if all(checks.values()) else "V5_SOLAR_R2B_A_FRESH_VERIFY_SOURCE_POLICY_HOLD",
    }


def fact_path(row: Mapping[str, Any], label: str) -> Path:
    raw = row.get("path")
    if not isinstance(raw, str) or not Path(raw).is_absolute():
        raise VerifyError("FACT_PATH_FAIL", f"{label} lacks an absolute path", {"row": dict(row)})
    return Path(raw).resolve()


def check_fact(row: Mapping[str, Any], label: str, allowed_root: Optional[Path] = None) -> Tuple[Path, Dict[str, Any]]:
    path = fact_path(row, label)
    if not path.is_file() or (allowed_root is not None and not is_under(path, allowed_root)):
        raise VerifyError("FACT_SCOPE_FAIL", f"{label} file is missing or outside scope", {"path": norm(path)})
    actual = file_fact(path)
    if actual["bytes"] != int(row.get("bytes", -1)) or actual["sha256"] != str(row.get("sha256", "")).upper():
        raise VerifyError("FACT_HASH_FAIL", f"{label} differs from recorded bytes/hash", {"expected": dict(row), "actual": actual})
    return path, actual


def exact_bound_fact(row: Any, label: str, expected_path: Path, expected_sha256: Optional[str] = None, allowed_root: Optional[Path] = None) -> Dict[str, Any]:
    if not isinstance(row, dict):
        raise VerifyError("EXACT_FACT_ROW_FAIL", f"{label} is not a file-fact object", {"row": row})
    path, actual = check_fact(row, label, allowed_root)
    if path != expected_path.resolve() or (expected_sha256 is not None and actual["sha256"] != expected_sha256):
        raise VerifyError("EXACT_FACT_BINDING_FAIL", f"{label} binds a different path/hash", {"expected_path": norm(expected_path), "expected_sha256": expected_sha256, "actual": actual})
    if row != actual:
        raise VerifyError("EXACT_FACT_SHAPE_FAIL", f"{label} is not the exact current path/bytes/hash fact", {"recorded": row, "actual": actual})
    return actual


def validate_micro_cad_manifest(raw: Any, micro_root: Path) -> Dict[str, Dict[str, Any]]:
    if not isinstance(raw, dict) or len(raw) != 13:
        raise VerifyError("MICRO_CAD_MANIFEST_COUNT_FAIL", "micro build CAD snapshot must contain exactly 13 files", {"count": len(raw) if isinstance(raw, dict) else None})
    cad_root = (micro_root / "cad").resolve()
    normalized: Dict[str, Dict[str, Any]] = {}
    paths: Set[Path] = set()
    for key, row in raw.items():
        if not isinstance(key, str) or not isinstance(row, dict):
            raise VerifyError("MICRO_CAD_MANIFEST_ROW_FAIL", "micro CAD snapshot row is malformed", {"key": key})
        path, actual = check_fact(row, f"micro_cad_manifest[{key}]", cad_root)
        if key != norm(path) or row != actual or path in paths:
            raise VerifyError("MICRO_CAD_MANIFEST_FACT_FAIL", "micro CAD snapshot key/fact is not exact and unique", {"key": key, "actual": actual})
        if path.suffix.upper() not in {".SLDPRT", ".SLDASM"}:
            raise VerifyError("MICRO_CAD_MANIFEST_SUFFIX_FAIL", "micro CAD manifest contains a non-native-CAD file", {"path": norm(path)})
        paths.add(path)
        normalized[key] = actual
    actual_paths = {path.resolve() for path in cad_root.rglob("*") if path.is_file() and path.suffix.upper() in {".SLDPRT", ".SLDASM"}}
    suffix_counts = Counter(path.suffix.upper() for path in paths)
    if actual_paths != paths or suffix_counts != Counter({".SLDPRT": 9, ".SLDASM": 4}):
        raise VerifyError("MICRO_CAD_MANIFEST_SET_FAIL", "micro on-disk CAD set differs from 9 parts + 4 assemblies", {"actual_count": len(actual_paths), "manifest_count": len(paths), "suffix_counts": dict(suffix_counts)})
    return normalized


def validate_microfixture_lineage(production_payload: Mapping[str, Any]) -> Dict[str, Any]:
    source_audit = microfixture_source_audit()
    source_fact = source_audit["source"]
    builder_fact = file_fact(BUILDER_SOURCE)
    if builder_fact["sha256"] != EXPECTED_BUILDER_SHA256:
        raise VerifyError("MICRO_LINEAGE_BUILDER_SOURCE_FAIL", "current production builder differs from the final frozen builder", {"actual": builder_fact})
    if production_payload.get("builder") != builder_fact or production_payload.get("contract_sha256") != EXPECTED_BUILD_CONTRACT_SHA256:
        raise VerifyError("MICRO_LINEAGE_PRODUCTION_BUILDER_CONTRACT_FAIL", "production receipt source fact or contract hash differs from the final frozen builder/contract", {"builder": production_payload.get("builder"), "contract_sha256": production_payload.get("contract_sha256")})

    production_micro = production_payload.get("microfixture")
    if not isinstance(production_micro, dict):
        raise VerifyError("MICRO_LINEAGE_PRODUCTION_ROW_FAIL", "production build receipt lacks its microfixture gate row")
    fresh_fact_row = production_micro.get("receipt")
    if not isinstance(fresh_fact_row, dict):
        raise VerifyError("MICRO_LINEAGE_FRESH_FACT_FAIL", "production build receipt lacks the micro fresh receipt fact")
    micro_fresh_path, micro_fresh_fact = check_fact(fresh_fact_row, "production.microfixture.receipt", MICROFIXTURE_ATTEMPTS_ROOT)
    if micro_fresh_path.name != MICRO_FRESH_RECEIPT_NAME or fresh_fact_row != micro_fresh_fact:
        raise VerifyError("MICRO_LINEAGE_FRESH_NAME_FACT_FAIL", "production micro receipt filename/fact is not exact", {"expected_name": MICRO_FRESH_RECEIPT_NAME, "actual": micro_fresh_fact})
    micro_fresh = load_json(micro_fresh_path)
    run_id = micro_fresh.get("run_id")
    if not isinstance(run_id, str) or not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        raise VerifyError("MICRO_LINEAGE_RUN_ID_FAIL", "micro fresh receipt run_id is not a safe single token", {"run_id": run_id})
    micro_root = (MICROFIXTURE_ATTEMPTS_ROOT / f"V5_SOLAR_R2B_MODULE_CHAIN_{run_id}").resolve()
    if micro_fresh_path.parent != micro_root or micro_root.parent != MICROFIXTURE_ATTEMPTS_ROOT.resolve():
        raise VerifyError("MICRO_LINEAGE_ROOT_FAIL", "micro fresh receipt is outside its run-id-derived immutable root", {"expected": norm(micro_root), "actual": norm(micro_fresh_path.parent)})
    if micro_fresh.get("schema") != EXPECTED_MICRO_FRESH_SCHEMA or micro_fresh.get("verdict") != EXPECTED_MICRO_FRESH_VERDICT:
        raise VerifyError("MICRO_LINEAGE_FRESH_GATE_FAIL", "micro fresh schema/verdict differs", {"schema": micro_fresh.get("schema"), "verdict": micro_fresh.get("verdict")})

    micro_build_fact_row = micro_fresh.get("build_receipt")
    if not isinstance(micro_build_fact_row, dict):
        raise VerifyError("MICRO_LINEAGE_BUILD_FACT_FAIL", "micro fresh receipt lacks its build receipt fact")
    micro_build_path, micro_build_fact = check_fact(micro_build_fact_row, "micro_fresh.build_receipt", micro_root)
    if micro_build_path != micro_root / MICRO_BUILD_RECEIPT_NAME or micro_build_fact_row != micro_build_fact:
        raise VerifyError("MICRO_LINEAGE_BUILD_NAME_FACT_FAIL", "micro build receipt filename/path/bytes/hash is not exact", {"expected": norm(micro_root / MICRO_BUILD_RECEIPT_NAME), "actual": micro_build_fact})
    micro_build = load_json(micro_build_path)
    if micro_build.get("schema") != EXPECTED_MICRO_BUILD_SCHEMA or micro_build.get("verdict") != EXPECTED_MICRO_BUILD_VERDICT or micro_build.get("run_id") != run_id:
        raise VerifyError("MICRO_LINEAGE_BUILD_GATE_FAIL", "micro build schema/verdict/run_id differs", {"schema": micro_build.get("schema"), "verdict": micro_build.get("verdict"), "run_id": micro_build.get("run_id")})
    if Path(str(micro_build.get("attempt_root", ""))).resolve() != micro_root:
        raise VerifyError("MICRO_LINEAGE_BUILD_ROOT_FAIL", "micro build receipt binds another attempt root")

    exact_bound_fact(micro_fresh.get("production_builder"), "micro_fresh.production_builder", BUILDER_SOURCE, EXPECTED_BUILDER_SHA256)
    exact_bound_fact(micro_build.get("production_builder"), "micro_build.production_builder", BUILDER_SOURCE, EXPECTED_BUILDER_SHA256)
    if micro_fresh.get("production_builder_sha256") != EXPECTED_BUILDER_SHA256 or micro_fresh.get("production_builder") != micro_build.get("production_builder"):
        raise VerifyError("MICRO_LINEAGE_BUILDER_BINDING_FAIL", "micro build/fresh receipts do not share the final production builder", {"fresh": micro_fresh.get("production_builder"), "build": micro_build.get("production_builder")})

    frozen_sha = {label: expected for label, _path, expected in FROZEN_BINDINGS}
    expected_frozen = {
        "authority": (STATE_AUTHORITY, frozen_sha["state_authority_r2b"]),
        "architecture": (ARCHITECTURE, frozen_sha["assembly_architecture"]),
        "oracle": (STATIC_ORACLE, frozen_sha["static_oracle_r2b"]),
        "authorization": (BUILD_AUTHORIZATION, frozen_sha["r2b_build_authorization"]),
    }
    build_frozen = micro_build.get("frozen_contracts")
    fresh_frozen = micro_fresh.get("frozen_contract_hashes")
    if not isinstance(build_frozen, dict) or set(build_frozen) != {path.name for path, _sha in expected_frozen.values()} or not isinstance(fresh_frozen, dict) or set(fresh_frozen) != set(expected_frozen):
        raise VerifyError("MICRO_LINEAGE_FROZEN_SET_FAIL", "micro frozen-contract key sets differ")
    for label, (path, expected_sha256) in expected_frozen.items():
        exact_bound_fact(build_frozen.get(path.name), f"micro_build.frozen_contracts.{path.name}", path, expected_sha256)
        if fresh_frozen.get(label) != expected_sha256 or micro_fresh.get(f"{label}_sha256") != expected_sha256:
            raise VerifyError("MICRO_LINEAGE_FROZEN_HASH_FAIL", "micro fresh frozen-contract hash differs", {"label": label})

    branch_facts: Dict[str, Dict[str, Any]] = {}
    generic_contract = FLIP_CONTRACT["evidence"]["interpanel_generic_probe"]
    for field, path, expected_sha256 in (
        ("branch_matrix_probe_script", BRANCH_PROBE_SOURCE, generic_contract["probe_script_sha256"]),
        ("branch_matrix_result", BRANCH_PROBE_RESULT, generic_contract["probe_result_sha256"]),
    ):
        fresh_branch_fact = exact_bound_fact(micro_fresh.get(field), f"micro_fresh.{field}", path, expected_sha256)
        build_branch_fact = exact_bound_fact(micro_build.get(field), f"micro_build.{field}", path, expected_sha256)
        if fresh_branch_fact != build_branch_fact:
            raise VerifyError("MICRO_LINEAGE_BRANCH_CROSS_BINDING_FAIL", "micro build/fresh branch facts differ", {"field": field})
        branch_facts[field] = fresh_branch_fact
    expected_left_flip = {"ROOT": True, "H12": False, "H23": True}
    if micro_build.get("fixture_left_per_hinge_angle_flip") != expected_left_flip or micro_fresh.get("fixture_left_per_hinge_angle_flip") != expected_left_flip:
        raise VerifyError("MICRO_LINEAGE_LEFT_FLIP_FAIL", "micro build/fresh LEFT flip map differs from T/F/T")
    if micro_build.get("authorized_production_per_side_angle_flip") != PRODUCTION_FLIP_SIDES or micro_fresh.get("authorized_production_per_side_angle_flip") != PRODUCTION_FLIP_SIDES:
        raise VerifyError("MICRO_LINEAGE_PRODUCTION_FLIP_FAIL", "micro build/fresh authorized production flip map differs from V2")
    expected_creation_contract = "DIAGNOSTIC_ROOT_EQUIVALENT_ONLY; PARENT_TO_CHILD_ROOT_FIRST; ALIGNMENT=0; FIXTURE ROOT/H23 Flip=True -> NEGATIVE; H12 Flip=False -> POSITIVE"
    if micro_build.get("fixture_angle_branch_creation_contract") != expected_creation_contract or micro_fresh.get("fixture_angle_branch_creation_contract") != expected_creation_contract:
        raise VerifyError("MICRO_LINEAGE_ANGLE_CREATION_FAIL", "micro build/fresh angle creation contract differs")
    micro_root_authorization = micro_fresh.get("production_root_flip_authorization")
    if not isinstance(micro_root_authorization, dict) or micro_build.get("production_root_flip_authorization") != micro_root_authorization:
        raise VerifyError("MICRO_LINEAGE_ROOT_AUTHORIZATION_CROSS_BINDING_FAIL", "micro build/fresh production ROOT authorization objects differ")
    root_auth_checks = micro_root_authorization.get("checks", {})
    if (
        micro_root_authorization.get("source") != file_fact(PRODUCTION_ROOT_FLIP_AUTHORIZER_SOURCE)
        or micro_root_authorization.get("receipt") != file_fact(PRODUCTION_ROOT_FLIP_AUTHORIZATION)
        or micro_root_authorization.get("schema") != "F3R2_V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_V1"
        or micro_root_authorization.get("verdict") != "V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_PATCH_ONLY_AUTHORIZED"
        or micro_root_authorization.get("evidence_chain_sha256") != EXPECTED_ROOT_FLIP_EVIDENCE_CHAIN_SHA256
        or micro_root_authorization.get("authorized_production_flip") != PRODUCTION_FLIP_SIDES
        or micro_root_authorization.get("fixture_left_flip") != expected_left_flip
        or not isinstance(root_auth_checks, dict)
        or not root_auth_checks
        or any(value_in is not True for value_in in root_auth_checks.values())
    ):
        raise VerifyError("MICRO_LINEAGE_ROOT_AUTHORIZATION_FAIL", "micro ROOT authorization or fixture/production separation differs")
    if micro_build.get("root_role_separation") != micro_root_authorization.get("root_role_separation") or micro_fresh.get("root_role_separation") != micro_root_authorization.get("root_role_separation"):
        raise VerifyError("MICRO_LINEAGE_ROOT_ROLE_SEPARATION_FAIL", "micro build/fresh ROOT role separation differs from authorization")

    build_session = micro_build.get("session")
    fresh_build_session = micro_fresh.get("build_session")
    verify_session = micro_fresh.get("verify_session")
    if not all(isinstance(row, dict) for row in (build_session, fresh_build_session, verify_session)):
        raise VerifyError("MICRO_LINEAGE_SESSION_ROW_FAIL", "micro build/fresh session rows are incomplete")
    build_pid, verify_pid = int(build_session.get("pid", -1)), int(verify_session.get("pid", -1))
    build_utc = parse_utc_timestamp(build_session.get("create_time_utc"), "micro build process create_time_utc")
    verify_utc = parse_utc_timestamp(verify_session.get("create_time_utc"), "micro verify process create_time_utc")
    build_unix = float(build_session.get("process_create_time_unix", 0.0))
    fresh_build_unix = float(micro_fresh.get("build_process_create_time_unix", 0.0))
    verify_unix = float(micro_fresh.get("verify_process_create_time_unix", 0.0))
    if (
        build_pid <= 0
        or verify_pid <= 0
        or build_pid == verify_pid
        or int(fresh_build_session.get("pid", -2)) != build_pid
        or fresh_build_session.get("create_time_utc") != build_session.get("create_time_utc")
        or int(micro_fresh.get("build_pid", -3)) != build_pid
        or int(micro_fresh.get("verify_pid", -4)) != verify_pid
        or micro_fresh.get("different_pid_and_create_time") is not True
        or build_unix <= 0.0
        or abs(fresh_build_unix - build_unix) > 1.0e-9
        or verify_unix <= build_unix
        or abs(build_utc - build_unix) > 1.0e-3
        or abs(verify_utc - verify_unix) > 1.0e-3
    ):
        raise VerifyError("MICRO_LINEAGE_FRESH_PROCESS_FAIL", "micro build/fresh PID or process-create-time proof differs", {"build_session": build_session, "fresh_build_session": fresh_build_session, "verify_session": verify_session})
    if production_micro.get("build_session") != fresh_build_session or production_micro.get("verify_session") != verify_session:
        raise VerifyError("MICRO_LINEAGE_PRODUCTION_SESSION_BINDING_FAIL", "production receipt micro session summaries differ from the micro fresh receipt")
    micro_checks = production_micro.get("checks")
    required_micro_checks = {"schema", "verdict", "builder", "authority", "architecture", "oracle", "authorization", "build_session", "verify_session", "different_pid_and_create_time", "fresh_read_only", "zero_mutation", "counts", "zero_interference", "production_use_permitted"}
    if not isinstance(micro_checks, dict) or not required_micro_checks.issubset(micro_checks) or any(micro_checks.get(key) is not True for key in required_micro_checks):
        raise VerifyError("MICRO_LINEAGE_PRODUCTION_CHECKS_FAIL", "production builder did not record all micro gate checks true", {"checks": micro_checks})

    if (
        micro_fresh.get("fresh_pid_read_only") is not True
        or micro_fresh.get("mutation_call_count") != 0
        or micro_fresh.get("fresh_verifier_mutation_call_count") != 0
        or (micro_fresh.get("state_count"), micro_fresh.get("module_count"), micro_fresh.get("hinge_count"), micro_fresh.get("advanced_limit_angle_count")) != (7, 3, 3, 3)
        or micro_fresh.get("positive_volume_interference_count") != 0
        or micro_fresh.get("production_use_permitted") is not True
        or [row.get("state") for row in micro_fresh.get("states", []) if isinstance(row, dict)] != list(CONFIGS)
    ):
        raise VerifyError("MICRO_LINEAGE_FRESH_SEMANTICS_FAIL", "micro fresh read-only/count/state/interference contract differs")

    build_manifest = validate_micro_cad_manifest(micro_build.get("cad_snapshot"), micro_root)
    if micro_fresh.get("cad_pre") != build_manifest or micro_fresh.get("cad_post") != build_manifest:
        raise VerifyError("MICRO_LINEAGE_CAD_PRE_POST_FAIL", "micro build manifest and fresh CAD PRE/POST facts differ")
    source_mtime = MICROFIXTURE_SOURCE.stat().st_mtime
    build_receipt_time = parse_utc_timestamp(micro_build.get("timestamp_utc"), "micro build receipt timestamp")
    fresh_receipt_time = parse_utc_timestamp(micro_fresh.get("timestamp_utc"), "micro fresh receipt timestamp")
    if build_receipt_time + 1.0e-6 < source_mtime or fresh_receipt_time < build_receipt_time:
        raise VerifyError("MICRO_LINEAGE_TEMPORAL_PROVENANCE_FAIL", "micro receipts predate the final source or are time-reversed", {"source_mtime_unix": source_mtime, "build_receipt_time": build_receipt_time, "fresh_receipt_time": fresh_receipt_time})

    protected_pre = production_payload.get("protected_pre")
    protected_post = production_payload.get("protected_post")
    static_micro = production_payload.get("static_audit", {}).get("microfixture") if isinstance(production_payload.get("static_audit"), dict) else None
    for label, row in (
        ("protected_pre.exact_r2b_microfixture_receipt", protected_pre.get("exact_r2b_microfixture_receipt") if isinstance(protected_pre, dict) else None),
        ("protected_post.exact_r2b_microfixture_receipt", protected_post.get("exact_r2b_microfixture_receipt") if isinstance(protected_post, dict) else None),
        ("static_audit.microfixture.receipt", static_micro.get("receipt") if isinstance(static_micro, dict) else None),
    ):
        if row != micro_fresh_fact:
            raise VerifyError("MICRO_LINEAGE_PRODUCTION_FACT_CROSS_BINDING_FAIL", "production receipt records different micro fresh receipt facts", {"label": label, "expected": micro_fresh_fact, "actual": row})
    static_audit = production_payload.get("static_audit")
    static_builder = static_audit.get("builder") if isinstance(static_audit, dict) else None
    for label, row in (
        ("protected_pre.builder_source", protected_pre.get("builder_source") if isinstance(protected_pre, dict) else None),
        ("protected_post.builder_source", protected_post.get("builder_source") if isinstance(protected_post, dict) else None),
        ("static_audit.builder", static_builder),
    ):
        if row != builder_fact:
            raise VerifyError("MICRO_LINEAGE_PRODUCTION_BUILDER_FACT_FAIL", "production receipt records different builder source facts", {"label": label, "expected": builder_fact, "actual": row})

    return {
        "schema": "F3R2_V5_SOLAR_R2B_A_RELEASE_PROVENANCE_LINEAGE_V1",
        "microfixture_source": source_fact,
        "microfixture_source_contract": source_audit,
        "production_builder": builder_fact,
        "production_contract_sha256": EXPECTED_BUILD_CONTRACT_SHA256,
        "micro_fresh_receipt": micro_fresh_fact,
        "micro_build_receipt": micro_build_fact,
        "run_id": run_id,
        "branch_evidence": branch_facts,
        "fixture_left_per_hinge_angle_flip": expected_left_flip,
        "authorized_production_per_side_angle_flip": PRODUCTION_FLIP_SIDES,
        "production_root_flip_authorization": micro_root_authorization,
        "build_session": {"pid": build_pid, "create_time_utc": build_session["create_time_utc"], "process_create_time_unix": build_unix},
        "fresh_session": {"pid": verify_pid, "create_time_utc": verify_session["create_time_utc"], "process_create_time_unix": verify_unix},
        "different_pid_and_create_time": True,
        "cad_manifest_file_count": len(build_manifest),
        "cad_manifest_sha256": canonical_json_sha256(build_manifest),
        "cad_manifest": build_manifest,
        "cad_pre_equals_post_equals_build_manifest": True,
        "source_and_receipt_facts_exact": True,
        "verdict": "V5_SOLAR_R2B_A_RELEASE_PROVENANCE_LINEAGE_PASS",
    }


def target_fact(row: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    target = row.get("target")
    if not isinstance(target, dict):
        raise VerifyError("TARGET_FACT_FAIL", f"{label} lacks target file fact")
    return target


def expected_angles(authority: Mapping[str, Any], state: str, side: str) -> List[float]:
    key = "LEFT" if side == "L" else "RIGHT"
    values = authority["states"][state][key]
    if not isinstance(values, list) or len(values) != 3:
        raise VerifyError("AUTHORITY_ANGLE_FAIL", "frozen state lacks three angles", {"state": state, "side": side})
    return [float(value_in) for value_in in values]


def normalize_transform(value_in: Any, label: str) -> List[float]:
    if not isinstance(value_in, list) or len(value_in) != 16:
        raise VerifyError("TRANSFORM_SHAPE_FAIL", f"{label} must contain 16 numbers")
    values = [float(item) for item in value_in]
    if not all(math.isfinite(item) for item in values):
        raise VerifyError("TRANSFORM_FINITE_FAIL", f"{label} contains a non-finite number")
    return values


def expected_flip(side: str, joint: str) -> bool:
    try:
        return bool(FLIP_CONTRACT["sides"][side][joint])
    except KeyError as exc:
        raise VerifyError("ANGLE_BRANCH_IDENTITY_FAIL", "side/joint is outside the frozen flip matrix", {"side": side, "joint": joint}) from exc


def validate_angle_branch_readback(row: Any, side: str, joint: str, label: str) -> Dict[str, Any]:
    if not isinstance(row, dict):
        raise VerifyError("ANGLE_BRANCH_READBACK_ROW_FAIL", f"{label} is not an object")
    wanted_flip = expected_flip(side, joint)
    try:
        alignment = int(row.get("alignment", -1))
    except (TypeError, ValueError):
        alignment = -1
    flipped = row.get("flipped")
    source_row = row.get("flip_readback")
    if not isinstance(source_row, dict) or not isinstance(source_row.get("sources"), dict):
        raise VerifyError("ANGLE_BRANCH_SOURCE_FAIL", f"{label} lacks IMate2/definition flip source readback", {"row": row})
    sources = source_row["sources"]
    allowed_sources = {"IMate2.Flipped", "IAngleMateFeatureData.FlipDimension"}
    if not sources or not set(sources).issubset(allowed_sources) or any(value_in is not wanted_flip for value_in in sources.values()):
        raise VerifyError("ANGLE_BRANCH_SOURCE_VALUE_FAIL", f"{label} flip source readback differs", {"expected_flip": wanted_flip, "sources": sources})
    if alignment != SW_ALIGN_ALIGNED or flipped is not wanted_flip or source_row.get("flipped") is not wanted_flip:
        raise VerifyError("ANGLE_BRANCH_READBACK_FAIL", f"{label} differs from Align=0 / frozen flip", {"side": side, "joint": joint, "expected_flip": wanted_flip, "row": row})
    if "expected_alignment" in row and row.get("expected_alignment") != SW_ALIGN_ALIGNED:
        raise VerifyError("ANGLE_BRANCH_EXPECTED_ALIGNMENT_FAIL", f"{label} carries a different expected alignment", {"row": row})
    if "expected_flip" in row and row.get("expected_flip") is not wanted_flip:
        raise VerifyError("ANGLE_BRANCH_EXPECTED_FLIP_FAIL", f"{label} carries a different expected flip", {"row": row})
    return {
        "side": side,
        "joint": joint,
        "selection_order": "PARENT_THEN_CHILD",
        "alignment": alignment,
        "flipped": flipped,
        "flip_readback": source_row,
        "verdict": "V5_SOLAR_R2B_A_ANGLE_BRANCH_READBACK_PASS",
    }


def validate_bore_brep_readback(row: Any, label: str) -> Dict[str, Any]:
    if not isinstance(row, dict):
        raise VerifyError("COLLAR_BORE_READBACK_ROW_FAIL", f"{label} is not a bore B-rep readback object")
    params_raw = row.get("cylinder_params")
    if not isinstance(params_raw, list) or len(params_raw) < 7:
        raise VerifyError("COLLAR_BORE_PARAMS_FAIL", f"{label} lacks seven CylinderParams values", {"row": row})
    try:
        params = [float(value_in) for value_in in params_raw]
        expected_radius = float(row.get("expected_radius_mm"))
        actual_radius = float(row.get("actual_radius_mm"))
        expected_length = float(row.get("expected_axial_length_mm"))
        actual_length = float(row.get("actual_axial_length_mm"))
        area_mm2 = float(row.get("area_mm2"))
        candidate_count = int(row.get("candidate_count"))
    except (TypeError, ValueError) as exc:
        raise VerifyError("COLLAR_BORE_NUMERIC_FAIL", f"{label} contains a non-numeric B-rep value", {"row": row}) from exc
    bore_contract = ANNULUS_NATIVE_FEATURE_CONTRACT["bore_brep"]
    derived_length = area_mm2 / (2.0 * math.pi * actual_radius) if actual_radius > 0.0 else float("inf")
    checks = {
        "finite": all(math.isfinite(value_in) for value_in in (*params, expected_radius, actual_radius, expected_length, actual_length, area_mm2)),
        "local_axis": row.get("local_axis") == "+/-Z" and abs(params[3]) < 1.0e-5 and abs(params[4]) < 1.0e-5 and abs(abs(params[5]) - 1.0) < 1.0e-5,
        "axis_point": abs(params[0] * 1000.0) <= float(bore_contract["axis_point_tolerance_mm"]) and abs(params[1] * 1000.0) <= float(bore_contract["axis_point_tolerance_mm"]),
        "candidate_count": candidate_count == int(bore_contract["candidate_count"]),
        "expected_radius": abs(expected_radius - float(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_radius_mm"])) <= 1.0e-9,
        "actual_radius": abs(actual_radius - expected_radius) <= float(bore_contract["radius_tolerance_mm"]) and abs(params[6] * 1000.0 - actual_radius) <= 1.0e-6,
        "expected_length": abs(expected_length - float(ANNULUS_NATIVE_FEATURE_CONTRACT["body_depth_mm"])) <= 1.0e-9,
        "actual_length": abs(actual_length - expected_length) <= float(bore_contract["axial_length_tolerance_mm"]) and abs(derived_length - actual_length) <= 1.0e-6,
        "positive_area": area_mm2 > 0.0,
    }
    if not all(checks.values()):
        raise VerifyError("COLLAR_BORE_BREP_FAIL", f"{label} differs from the unique through-bore contract", {"checks": checks, "row": row, "derived_length_mm": derived_length})
    return {
        "local_axis": "+/-Z",
        "expected_radius_mm": expected_radius,
        "actual_radius_mm": actual_radius,
        "expected_axial_length_mm": expected_length,
        "actual_axial_length_mm": actual_length,
        "area_mm2": area_mm2,
        "candidate_count": candidate_count,
        "cylinder_params": params,
    }


def validate_root_lug_bore_readback(row: Any, side: str, label: str) -> Dict[str, Any]:
    if not isinstance(row, dict):
        raise VerifyError("ROOT_LUG_BORE_ROW_FAIL", f"{label} is not a root lug bore readback object")
    params_raw = row.get("cylinder_params")
    if not isinstance(params_raw, list) or len(params_raw) < 7:
        raise VerifyError("ROOT_LUG_BORE_PARAMS_FAIL", f"{label} lacks seven CylinderParams values", {"row": row})
    try:
        params = [float(value_in) for value_in in params_raw]
        area_mm2 = float(row.get("area_mm2"))
        actual_radius_mm = float(row.get("actual_radius_mm"))
        actual_length_mm = float(row.get("actual_axial_length_mm"))
        candidate_count = int(row.get("candidate_count"))
    except (TypeError, ValueError) as exc:
        raise VerifyError("ROOT_LUG_BORE_NUMERIC_FAIL", f"{label} contains a non-numeric B-rep value", {"row": row}) from exc
    side_contract = ROOT_LUG_BORE_SELECTION_CONTRACT["sides"][side]
    tolerance = ROOT_LUG_BORE_SELECTION_CONTRACT["tolerances_mm"]
    derived_length_mm = area_mm2 / (2.0 * math.pi * actual_radius_mm) if actual_radius_mm > 0.0 else float("inf")
    checks = {
        "selection_contract": row.get("selection_contract") == ROOT_LUG_BORE_SELECTION_CONTRACT,
        "selection_verdict": row.get("selection_verdict") == "V5_SOLAR_R2B_A_ROOT_LUG_DUAL_EAR_MIN_X_SELECTION_PASS",
        "finite": all(math.isfinite(value_in) for value_in in (*params, area_mm2, actual_radius_mm, actual_length_mm)),
        "candidate_count": candidate_count == int(ROOT_LUG_BORE_SELECTION_CONTRACT["candidate_count"]),
        "reported_radius": abs(float(row.get("radius_mm", math.inf)) - float(ROOT_LUG_BORE_SELECTION_CONTRACT["radius_mm"])) <= 1.0e-9,
        "reported_axis_y": abs(float(row.get("axis_y_mm", math.inf)) - float(side_contract["axis_y_mm"])) <= 1.0e-9,
        "axis_direction": abs(abs(params[3]) - 1.0) < 1.0e-5 and abs(params[4]) < 1.0e-5 and abs(params[5]) < 1.0e-5,
        "chosen_minimum_x": abs(params[0] * 1000.0 - float(ROOT_LUG_BORE_SELECTION_CONTRACT["chosen_axis_x_mm"])) <= float(tolerance["axis_point"]),
        "axis_y": abs(params[1] * 1000.0 - float(side_contract["axis_y_mm"])) <= float(tolerance["axis_point"]),
        "axis_z": abs(params[2] * 1000.0 - float(ROOT_LUG_BORE_SELECTION_CONTRACT["axis_z_mm"])) <= float(tolerance["axis_point"]),
        "radius": abs(actual_radius_mm - float(ROOT_LUG_BORE_SELECTION_CONTRACT["radius_mm"])) <= float(tolerance["radius"]) and abs(params[6] * 1000.0 - actual_radius_mm) <= 1.0e-6,
        "axial_length": abs(actual_length_mm - float(ROOT_LUG_BORE_SELECTION_CONTRACT["chosen_face_axial_length_mm"])) <= float(tolerance["axial_length"]) and abs(derived_length_mm - actual_length_mm) <= 1.0e-6,
        "positive_area": area_mm2 > 0.0,
    }
    if not all(checks.values()):
        raise VerifyError("ROOT_LUG_BORE_SELECTION_FAIL", f"{label} differs from the frozen two-face minimum-X selection contract", {"side": side, "checks": checks, "row": row, "derived_length_mm": derived_length_mm})
    return {"side": side, "candidate_count": candidate_count, "chosen_cylinder_params": params, "chosen_area_mm2": area_mm2, "chosen_axial_length_mm": actual_length_mm, "verdict": "V5_SOLAR_R2B_A_ROOT_LUG_BORE_BUILD_RECEIPT_PASS"}


def vector_distance(first: Sequence[float], second: Sequence[float]) -> float:
    return math.sqrt(sum((float(first[index]) - float(second[index])) ** 2 for index in range(3)))


def vector_cross_norm(first: Sequence[float], second: Sequence[float]) -> float:
    cross = [first[1] * second[2] - first[2] * second[1], first[2] * second[0] - first[0] * second[2], first[0] * second[1] - first[1] * second[0]]
    return math.sqrt(sum(float(value_in) ** 2 for value_in in cross))


def validate_interpanel_child_receipt(row: Any, expected_radius_mm: float, expected_world_z0_mm: Sequence[float], label: str) -> Dict[str, Any]:
    if not isinstance(row, dict):
        raise VerifyError("INTERPANEL_CHILD_RECEIPT_FAIL", f"{label} is not an object")
    try:
        params = [float(value_in) for value_in in row.get("selected_cylinder_params", [])]
        area_mm2 = float(row.get("selected_cylinder_area_mm2"))
        axial_length_mm = float(row.get("selected_cylinder_axial_length_mm"))
        transform = [float(value_in) for value_in in row.get("child_transform16", [])]
        world_z0 = [float(value_in) for value_in in row.get("canonical_local_z0_world_mm", [])]
        world_z28 = [float(value_in) for value_in in row.get("canonical_local_z28_world_mm", [])]
        direction = [float(value_in) for value_in in row.get("canonical_local_plus_z_world_direction", [])]
    except (TypeError, ValueError) as exc:
        raise VerifyError("INTERPANEL_CHILD_NUMERIC_FAIL", f"{label} contains non-numeric evidence", {"row": row}) from exc
    tolerance = INTERPANEL_NESTED_BREP_FRAME_CONTRACT["tolerances"]
    expected_z28 = [float(expected_world_z0_mm[0]) + 28.0, float(expected_world_z0_mm[1]), float(expected_world_z0_mm[2])]
    mapped_z0 = transform_point_mm(transform, [0.0, 0.0, 0.0]) if len(transform) == 16 else [math.inf] * 3
    mapped_z28 = transform_point_mm(transform, [0.0, 0.0, 28.0]) if len(transform) == 16 else [math.inf] * 3
    mapped_direction = transform_direction(transform, [0.0, 0.0, 1.0]) if len(transform) == 16 else [math.inf] * 3
    checks = {
        "coordinate_frame": row.get("entity_signature_coordinate_frame") == "NESTED_CHILD_PART_LOCAL",
        "shapes": len(params) >= 7 and len(transform) == 16 and len(world_z0) == len(world_z28) == len(direction) == 3,
        "candidate_counts": row.get("cylinder_candidate_count") == 1 and row.get("end_plane_candidate_count") == 1,
        "local_axis": len(params) >= 7 and abs(params[3]) < 1.0e-5 and abs(params[4]) < 1.0e-5 and abs(abs(params[5]) - 1.0) < 1.0e-5,
        "local_axis_point": len(params) >= 7 and abs(params[0] * 1000.0) <= float(tolerance["local_axis_point_mm"]) and abs(params[1] * 1000.0) <= float(tolerance["local_axis_point_mm"]),
        "radius": len(params) >= 7 and abs(params[6] * 1000.0 - expected_radius_mm) <= float(tolerance["radius_mm"]),
        "axial_length": abs(axial_length_mm - 28.0) <= float(tolerance["axial_length_mm"]) and abs(area_mm2 / (2.0 * math.pi * expected_radius_mm) - axial_length_mm) <= 1.0e-5,
        "world_z0": len(world_z0) == 3 and vector_distance(world_z0, expected_world_z0_mm) <= float(tolerance["world_point_mm"]),
        "world_z28": len(world_z28) == 3 and vector_distance(world_z28, expected_z28) <= float(tolerance["world_point_mm"]),
        "world_direction": len(direction) == 3 and abs(abs(direction[0]) - 1.0) <= float(tolerance["world_direction_cross_norm"]) and abs(direction[1]) <= float(tolerance["world_direction_cross_norm"]) and abs(direction[2]) <= float(tolerance["world_direction_cross_norm"]),
        "transform_maps_z0": len(world_z0) == 3 and vector_distance(mapped_z0, world_z0) <= 1.0e-6,
        "transform_maps_z28": len(world_z28) == 3 and vector_distance(mapped_z28, world_z28) <= 1.0e-6,
        "transform_maps_direction": len(direction) == 3 and vector_distance(mapped_direction, direction) <= 1.0e-8,
        "local_z0_plane": isinstance(row.get("selected_end_plane_params"), list) and len(row["selected_end_plane_params"]) >= 6 and abs(float(row["selected_end_plane_params"][5]) * 1000.0) <= float(tolerance["local_axis_point_mm"]),
    }
    if not all(checks.values()):
        raise VerifyError("INTERPANEL_CHILD_RECEIPT_CONTRACT_FAIL", f"{label} differs from the nested local-Z/world mapping contract", {"checks": checks, "row": row})
    return {"selected_cylinder_params": params, "area_mm2": area_mm2, "axial_length_mm": axial_length_mm, "child_transform16": transform, "world_z0_mm": world_z0, "world_z28_mm": world_z28, "world_direction": direction}


def validate_interpanel_build_geometry(geometry: Any, side: str, joint: str) -> Dict[str, Any]:
    if not isinstance(geometry, dict) or geometry.get("interpanel_nested_brep_frame_contract") != INTERPANEL_NESTED_BREP_FRAME_CONTRACT:
        raise VerifyError("INTERPANEL_BUILD_FRAME_CONTRACT_FAIL", "interpanel hinge lacks the exact nested B-rep frame contract", {"side": side, "joint": joint, "geometry": geometry})
    expected = [-75.0, float(INTERPANEL_NESTED_BREP_FRAME_CONTRACT["nominal_world"]["hinge_y_mm"][side][joint]), 0.0]
    pin = validate_interpanel_child_receipt(geometry.get("pin"), 2.0, expected, f"build {side}/{joint}/pin")
    collar = validate_interpanel_child_receipt(geometry.get("collar"), 2.2, expected, f"build {side}/{joint}/collar")
    continuity = geometry.get("world_axis_continuity")
    post_continuity = geometry.get("post_concentric_world_axis_continuity")
    if not isinstance(continuity, dict) or continuity.get("verdict") != "V5_SOLAR_R2B_A_INTERPANEL_WORLD_AXIS_CONTINUITY_PASS" or not isinstance(post_continuity, dict) or post_continuity.get("verdict") != "V5_SOLAR_R2B_A_INTERPANEL_WORLD_AXIS_CONTINUITY_PASS":
        raise VerifyError("INTERPANEL_BUILD_CONTINUITY_RECEIPT_FAIL", "interpanel hinge lacks pre/post-concentric world continuity", {"side": side, "joint": joint})
    pose = geometry.get("mate_pose_stability")
    if not isinstance(pose, dict) or pose.get("verdict") != "V5_SOLAR_R2B_A_INTERPANEL_MATE_POSE_STABILITY_PASS":
        raise VerifyError("INTERPANEL_BUILD_POSE_RECEIPT_FAIL", "interpanel hinge lacks mate pose stability proof", {"side": side, "joint": joint})
    try:
        pre, post_c, post_i = pose["pre"], pose["post_concentric"], pose["post_coincident"]
        derived_c = max(abs(float(pre[key][index]) - float(post_c[key][index])) for key in ("upstream", "downstream") for index in range(16))
        derived_i = max(abs(float(pre[key][index]) - float(post_i[key][index])) for key in ("upstream", "downstream") for index in range(16))
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise VerifyError("INTERPANEL_BUILD_POSE_SHAPE_FAIL", "interpanel pose stability arrays are malformed", {"side": side, "joint": joint, "pose": pose}) from exc
    tolerance = float(INTERPANEL_NESTED_BREP_FRAME_CONTRACT["tolerances"]["module_transform_max_abs"])
    if max(derived_c, derived_i, float(pose.get("concentric_max_abs_error", math.inf)), float(pose.get("coincident_max_abs_error", math.inf))) > tolerance:
        raise VerifyError("INTERPANEL_BUILD_POSE_JUMP_FAIL", "build receipt shows a module pose jump during mate creation", {"side": side, "joint": joint, "derived_concentric": derived_c, "derived_coincident": derived_i, "pose": pose})
    return {"side": side, "joint": joint, "pin": pin, "collar": collar, "world_axis_point_delta_mm": vector_distance(pin["world_z0_mm"], collar["world_z0_mm"]), "world_axis_direction_cross_norm": vector_cross_norm(pin["world_direction"], collar["world_direction"]), "concentric_pose_error": derived_c, "coincident_pose_error": derived_i, "verdict": "V5_SOLAR_R2B_A_INTERPANEL_BUILD_GEOMETRY_RECEIPT_PASS"}


def receipt_reference_paths(rows: Any, label: str) -> Set[Path]:
    if not isinstance(rows, list) or not rows:
        raise VerifyError("REFERENCE_LIST_FAIL", f"{label} reference list is empty")
    paths: Set[Path] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise VerifyError("REFERENCE_ROW_FAIL", f"{label} reference row is not an object", {"index": index})
        path, _ = check_fact(row, f"{label}[{index}]")
        if not is_under(path, RUN_ROOT):
            raise VerifyError("REFERENCE_OUTSIDE_V5", "nested reference escapes unique V5 root", {"path": norm(path)})
        paths.add(path)
    if len(paths) != len(rows):
        raise VerifyError("REFERENCE_DUPLICATE_FAIL", f"{label} repeats a physical reference")
    return paths


def validate_handoff(
    attempt_root: Path,
    path: Path,
    cad_paths: Set[Path],
    build_pid: int,
    production_payload: Mapping[str, Any],
    builder_fact: Mapping[str, Any],
    micro_fresh_fact: Mapping[str, Any],
    manifest_fact: Mapping[str, Any],
    manifest_sha256_fact: Mapping[str, Any],
) -> Dict[str, Any]:
    payload = load_json(path)
    if payload.get("schema") != EXPECTED_HANDOFF_SCHEMA or payload.get("status") != "AWAITING_DIFFERENT_PID_READ_ONLY_ZERO_MUTATION_VERIFICATION":
        raise VerifyError("HANDOFF_GATE_FAIL", "fresh verifier handoff schema/status differs", {"schema": payload.get("schema"), "status": payload.get("status")})
    production_identity = receipt_storage_identity(production_payload, "production build receipt")
    handoff_identity = receipt_storage_identity(payload, "fresh verifier handoff")
    physical_identity = root_storage_identity(attempt_root)
    if (
        production_identity != physical_identity
        or handoff_identity != production_identity
        or Path(str(payload.get("attempt_root", ""))).resolve() != attempt_root
        or int(payload.get("build_pid", -1)) != build_pid
        or payload.get("build_process_start_utc") != production_payload.get("solidworks_build_session", {}).get("process_start_utc")
    ):
        raise VerifyError("HANDOFF_IDENTITY_FAIL", "handoff semantic attempt, physical storage, root, or PID differs from the build receipt", {"production_identity": production_identity, "handoff_identity": handoff_identity, "physical_identity": physical_identity})
    expected_facts = {
        "builder": dict(builder_fact),
        "exact_r2b_module_chain_microfixture_receipt": dict(micro_fresh_fact),
        "cad_manifest": dict(manifest_fact),
        "cad_manifest_sha256_text": dict(manifest_sha256_fact),
    }
    for field, expected in expected_facts.items():
        if payload.get(field) != expected:
            raise VerifyError("HANDOFF_PROVENANCE_FACT_FAIL", "handoff provenance fact differs from production build receipt", {"field": field, "expected": expected, "actual": payload.get(field)})
    if payload.get("contract_sha256") != EXPECTED_BUILD_CONTRACT_SHA256:
        raise VerifyError("HANDOFF_CONTRACT_HASH_FAIL", "handoff does not bind the final production contract")
    if payload.get("authority_bundle") != production_payload.get("authority_bundle"):
        raise VerifyError("HANDOFF_AUTHORITY_BUNDLE_FAIL", "handoff authority bundle differs from production receipt")
    if payload.get("production_root_flip_authorization") != production_payload.get("production_root_flip_authorization"):
        raise VerifyError("HANDOFF_ROOT_FLIP_AUTHORIZATION_FAIL", "handoff ROOT authorization lineage differs from production receipt")
    production_g0 = production_payload.get("g0")
    if not isinstance(production_g0, dict) or payload.get("g0_receipt") != production_g0.get("receipt"):
        raise VerifyError("HANDOFF_G0_FACT_FAIL", "handoff G0 receipt fact differs from production receipt")
    rows = payload.get("pre_verifier_cad_facts")
    if not isinstance(rows, list) or len(rows) != 46:
        raise VerifyError("HANDOFF_CAD_COUNT_FAIL", "handoff does not bind all 46 CAD files")
    handoff_paths = {check_fact(row, f"handoff_cad[{index}]", attempt_root)[0] for index, row in enumerate(rows) if isinstance(row, dict)}
    if len(handoff_paths) != len(rows) or handoff_paths != cad_paths or {norm(path_in): file_fact(path_in) for path_in in handoff_paths} != {str(row["path"]): dict(row) for row in rows}:
        raise VerifyError("HANDOFF_CAD_SET_FAIL", "handoff CAD set differs from build receipt")
    required_process = payload.get("required_verifier_process", {})
    expected_forbidden = ["Save3", "SaveAs", "SetTransformAndSolve3", "EditRebuild3", "ForceRebuild3", "AddConfiguration", "ModifyDefinition"]
    if (
        not isinstance(required_process, dict)
        or not all(required_process.get(key) is True for key in ("different_pid_from_build", "different_process_start_from_build", "attach_only", "empty_session_pre", "zero_mutation_apis"))
        or required_process.get("open_options") != ["SILENT", "READ_ONLY"]
        or required_process.get("forbidden_calls") != expected_forbidden
        or payload.get("promotion_authorized") is not False
    ):
        raise VerifyError("HANDOFF_PROCESS_CONTRACT_FAIL", "handoff fresh-process contract is incomplete")
    required_checks = payload.get("required_checks", [])
    for required_check in (
        "PRODUCTION_ROOT_FLIP_AUTHORIZATION_HASH_SEMANTICS_AND_EVIDENCE_DIGEST",
        "EXACT_V2_FLIP_MATRIX_L_F_F_T_R_T_T_F_IN_ALL_SEVEN_CONFIGURATIONS",
        "ALL_CONFIGURATION_TRANSFORMS_MATCH_STATIC_ORACLE",
    ):
        if required_check not in required_checks:
            raise VerifyError("HANDOFF_REQUIRED_CHECK_FAIL", "handoff omits a V2 ROOT-branch verification requirement", {"missing": required_check})
    return payload


def validate_build_receipt(attempt_root: Path, receipt_path: Path, handoff_path: Path) -> Dict[str, Any]:
    controlled_root = ATTEMPTS_ROOT.resolve()
    physical_identity = root_storage_identity(attempt_root)
    if attempt_root.parent != controlled_root:
        raise VerifyError("BUILD_ATTEMPT_DIRECT_CHILD_FAIL", "production attempt root is not a direct child of the controlled attempts directory", {"attempt_root": norm(attempt_root)})
    expected_evidence = (attempt_root / "evidence").resolve()
    if receipt_path != expected_evidence / BUILD_RECEIPT_NAME or handoff_path != expected_evidence / HANDOFF_NAME:
        raise VerifyError("RELEASE_EVIDENCE_FILENAME_FAIL", "build receipt or handoff does not use the canonical release filename", {"expected_build_receipt": norm(expected_evidence / BUILD_RECEIPT_NAME), "actual_build_receipt": norm(receipt_path), "expected_handoff": norm(expected_evidence / HANDOFF_NAME), "actual_handoff": norm(handoff_path)})
    payload = load_json(receipt_path)
    if payload.get("schema") != EXPECTED_BUILD_SCHEMA or payload.get("verdict") != EXPECTED_BUILD_VERDICT:
        raise VerifyError("BUILD_RECEIPT_GATE_FAIL", "build receipt schema/verdict does not authorize verification", {"schema": payload.get("schema"), "verdict": payload.get("verdict")})
    build_identity = receipt_storage_identity(payload, "production build receipt")
    if build_identity != physical_identity:
        raise VerifyError("BUILD_STORAGE_BINDING_FAIL", "build receipt semantic attempt/physical storage identity differs from the direct-child root", {"build_identity": build_identity, "physical_identity": physical_identity})
    if str(payload.get("contract_sha256", "")).upper() != EXPECTED_BUILD_CONTRACT_SHA256:
        raise VerifyError("BUILD_CONTRACT_HASH_FAIL", "build receipt does not bind the final R2B-A contract", {"expected": EXPECTED_BUILD_CONTRACT_SHA256, "actual": payload.get("contract_sha256")})
    if payload.get("annulus_native_feature_contract") != ANNULUS_NATIVE_FEATURE_CONTRACT:
        raise VerifyError("BUILD_ANNULUS_CONTRACT_FAIL", "build receipt does not carry the exact hash-bound annulus native feature contract")
    if payload.get("root_lug_bore_selection_contract") != ROOT_LUG_BORE_SELECTION_CONTRACT:
        raise VerifyError("BUILD_ROOT_LUG_BORE_CONTRACT_FAIL", "build receipt does not carry the exact hash-bound dual-ear lug bore selection contract")
    if payload.get("interpanel_nested_brep_frame_contract") != INTERPANEL_NESTED_BREP_FRAME_CONTRACT:
        raise VerifyError("BUILD_INTERPANEL_FRAME_CONTRACT_FAIL", "build receipt does not carry the exact hash-bound nested B-rep frame contract")
    root_flip_authorization = production_root_flip_authorization_audit()
    if payload.get("production_root_flip_authorization") != root_flip_authorization:
        raise VerifyError("BUILD_ROOT_FLIP_AUTHORIZATION_FAIL", "build receipt does not carry the independently revalidated production ROOT authorization")
    if Path(str(payload.get("attempt_root", ""))).resolve() != attempt_root:
        raise VerifyError("BUILD_ATTEMPT_FAIL", "build receipt binds another attempt root")
    if payload.get("protected_pre") != payload.get("protected_post"):
        raise VerifyError("BUILD_PROTECTED_DRIFT", "build-stage protected PRE/POST snapshots differ")
    microfixture_lineage = validate_microfixture_lineage(payload)
    if payload.get("angle_branch_contract") != FLIP_CONTRACT:
        raise VerifyError("BUILD_ANGLE_BRANCH_CONTRACT_FAIL", "build receipt does not carry the exact frozen L/R flip matrix")
    branch_evidence = payload.get("angle_branch_evidence")
    expected_branch_evidence = branch_evidence_audit()
    if branch_evidence != expected_branch_evidence or branch_evidence.get("contract") != FLIP_CONTRACT:
        raise VerifyError("BUILD_ANGLE_BRANCH_EVIDENCE_FAIL", "build receipt lacks the independently revalidated V2 branch evidence")
    if branch_evidence.get("production_root_authorization") != root_flip_authorization:
        raise VerifyError("BUILD_ROOT_FLIP_CROSS_BINDING_FAIL", "top-level and angle-branch ROOT authorization objects differ")
    generic_evidence = branch_evidence.get("generic_interpanel_evidence", {})
    generic_contract = FLIP_CONTRACT["evidence"]["interpanel_generic_probe"]
    for field, expected_path, expected_sha256 in (
        ("probe_source", BRANCH_PROBE_SOURCE, generic_contract["probe_script_sha256"]),
        ("probe_result", BRANCH_PROBE_RESULT, generic_contract["probe_result_sha256"]),
    ):
        evidence_fact = generic_evidence.get(field)
        if not isinstance(evidence_fact, dict):
            raise VerifyError("BUILD_ANGLE_BRANCH_FACT_FAIL", "build branch evidence lacks a frozen fact", {"field": field})
        evidence_path, actual_fact = check_fact(evidence_fact, f"angle_branch_evidence.{field}")
        if evidence_path != expected_path.resolve() or actual_fact["sha256"] != expected_sha256:
            raise VerifyError("BUILD_ANGLE_BRANCH_BINDING_FAIL", "build branch evidence binds a different file", {"field": field, "actual": actual_fact})

    build_session = payload.get("solidworks_build_session")
    g0_process = payload.get("g0", {}).get("session_b_process") if isinstance(payload.get("g0"), dict) else None
    if not isinstance(build_session, dict) or not isinstance(g0_process, dict):
        raise VerifyError("BUILD_SESSION_FAIL", "build receipt lacks SOLIDWORKS/G0 process identity")
    build_pid = int(build_session.get("pid", -1))
    if build_pid <= 0 or int(g0_process.get("pid", -2)) != build_pid or not str(build_session.get("revision", "")).startswith(EXPECTED_SW_REVISION_PREFIX):
        raise VerifyError("BUILD_SESSION_BINDING_FAIL", "build PID/revision and G0 identity disagree")
    build_start_text = g0_process.get("process_start_utc")
    if not isinstance(build_start_text, str):
        raise VerifyError("BUILD_CREATE_TIME_FAIL", "G0-bound build process lacks process_start_utc")
    try:
        build_create_time = datetime.fromisoformat(build_start_text.replace("Z", "+00:00")).timestamp()
    except ValueError as exc:
        raise VerifyError("BUILD_CREATE_TIME_PARSE_FAIL", "cannot parse build process start UTC") from exc

    part_rows, module_rows, side_rows = payload.get("parts"), payload.get("modules"), payload.get("side_assemblies")
    if not isinstance(part_rows, list) or not isinstance(module_rows, list) or not isinstance(side_rows, list) or (len(part_rows), len(module_rows), len(side_rows)) != (38, 6, 2):
        raise VerifyError("BUILD_ARTIFACT_COUNT_FAIL", "build rows differ from 38 parts + 6 modules + 2 sides")
    artifacts: Dict[Path, Dict[str, Any]] = {}
    for kind, rows, suffix in (("part", part_rows, ".SLDPRT"), ("module", module_rows, ".SLDASM"), ("side", side_rows, ".SLDASM")):
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise VerifyError("BUILD_ROW_FAIL", f"{kind} row is not an object", {"index": index})
            path, fact = check_fact(target_fact(row, f"{kind}[{index}]"), f"{kind}[{index}]", attempt_root)
            if path.suffix.upper() != suffix or path in artifacts:
                raise VerifyError("BUILD_TARGET_TYPE_FAIL", f"{kind} target suffix/uniqueness differs", {"path": norm(path)})
            artifacts[path] = {"kind": kind, "row": row, "fact": fact}
    actual_cad = {path.resolve() for path in (attempt_root / "cad").rglob("*") if path.is_file() and path.suffix.upper() in {".SLDPRT", ".SLDASM"}}
    if actual_cad != set(artifacts) or len(actual_cad) != 46:
        raise VerifyError("ATTEMPT_CAD_SET_FAIL", "on-disk CAD set differs from exactly 46 receipt targets", {"actual_count": len(actual_cad)})

    expected_annulus_geometry = {
        "kind": "annulus_holes",
        "outer_r_mm": float(ANNULUS_NATIVE_FEATURE_CONTRACT["outer_radius_mm"]),
        "inner_r_mm": float(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_radius_mm"]),
        "holes": [],
        "depth_mm": float(ANNULUS_NATIVE_FEATURE_CONTRACT["body_depth_mm"]),
    }
    collar_rows: Dict[str, Dict[str, Any]] = {}
    for index, row in enumerate(part_rows):
        key = str(row.get("key", ""))
        has_bore_field = "bore_brep_readback_before_save" in row
        if key not in COLLAR_KEYS:
            if row.get("geometry_contract", {}).get("kind") == "annulus_holes" or not has_bore_field or row.get("bore_brep_readback_before_save") is not None:
                raise VerifyError("BUILD_NONCOLLAR_BORE_FIELD_FAIL", "non-collar part receipt has an annulus geometry or non-null/missing bore evidence field", {"index": index, "key": key})
            continue
        if key in collar_rows or row.get("geometry_contract") != expected_annulus_geometry or not has_bore_field:
            raise VerifyError("BUILD_COLLAR_GEOMETRY_FAIL", "collar part identity or exact annulus geometry differs", {"index": index, "key": key, "geometry": row.get("geometry_contract")})
        primitive = row.get("primitive")
        if not isinstance(primitive, dict):
            raise VerifyError("BUILD_COLLAR_PRIMITIVE_FAIL", "collar part receipt lacks its native primitive ledger", {"key": key})
        outer_boss = primitive.get("outer_boss")
        bore_cut = primitive.get("bore_cut")
        if (
            primitive.get("primitive") != "annulus_holes"
            or primitive.get("feature_api") != ["FeatureExtrusion2", "FeatureCut3"]
            or primitive.get("feature_sequence") != ANNULUS_NATIVE_FEATURE_CONTRACT["feature_sequence"]
            or primitive.get("annulus_native_feature_contract") != ANNULUS_NATIVE_FEATURE_CONTRACT
            or not isinstance(outer_boss, dict)
            or outer_boss.get("feature_name") != "R2B_ANNULUS_OUTER_BOSS"
            or abs(float(outer_boss.get("radius_mm", -1.0)) - float(ANNULUS_NATIVE_FEATURE_CONTRACT["outer_radius_mm"])) > 1.0e-9
            or outer_boss.get("body_readback", {}).get("solid_body_count") != int(ANNULUS_NATIVE_FEATURE_CONTRACT["solid_body_count_after_outer_boss"])
            or not isinstance(bore_cut, dict)
            or bore_cut.get("feature_name") != "R2B_ANNULUS_BORE_THROUGH_CUT"
            or abs(float(bore_cut.get("radius_mm", -1.0)) - float(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_radius_mm"])) > 1.0e-9
            or abs(float(bore_cut.get("cut_depth_mm", -1.0)) - float(ANNULUS_NATIVE_FEATURE_CONTRACT["cut_depth_multiplier"]) * float(ANNULUS_NATIVE_FEATURE_CONTRACT["body_depth_mm"])) > 1.0e-9
            or bore_cut.get("body_readback", {}).get("solid_body_count") != int(ANNULUS_NATIVE_FEATURE_CONTRACT["solid_body_count_after_bore_cut"])
            or row.get("body_readback_before_save", {}).get("solid_body_count") != 1
        ):
            raise VerifyError("BUILD_COLLAR_FEATURE_LEDGER_FAIL", "collar boss/cut/body receipt differs from the native annulus feature contract", {"key": key, "primitive": primitive, "body_readback": row.get("body_readback_before_save")})
        bore_readback = validate_bore_brep_readback(row.get("bore_brep_readback_before_save"), f"build part {key} bore")
        if primitive.get("bore_brep_readback") != row.get("bore_brep_readback_before_save"):
            raise VerifyError("BUILD_COLLAR_BORE_CROSS_BINDING_FAIL", "collar primitive and top-level part receipt carry different bore B-rep facts", {"key": key})
        collar_rows[key] = {"row": row, "bore_brep_readback": bore_readback}
    if set(collar_rows) != set(COLLAR_KEYS) or len(collar_rows) != int(ANNULUS_NATIVE_FEATURE_CONTRACT["production_part_count"]):
        raise VerifyError("BUILD_COLLAR_SET_FAIL", "build receipt does not contain exactly the four L2/L3/R2/R3 collar proofs", {"actual": sorted(collar_rows)})

    modules: Dict[str, Dict[str, Any]] = {}
    for row in module_rows:
        key = f"{row.get('side')}{int(row.get('panel_index', -1))}"
        path = fact_path(target_fact(row, f"module {key}"), f"module {key}")
        if key not in MODULE_NAMES or path.name != MODULE_NAMES[key] or key in modules:
            raise VerifyError("MODULE_IDENTITY_FAIL", "module side/index/name set differs", {"key": key, "path": norm(path)})
        references = receipt_reference_paths(row.get("references"), f"module {key}")
        child_count = int(row.get("child_count", -1))
        if child_count != len(references) or len(row.get("mate_ledger", [])) != child_count - 1:
            raise VerifyError("MODULE_BUILD_CONTRACT_FAIL", "module child/lock/reference counts disagree", {"key": key})
        modules[key] = {"path": path, "row": row, "references": references, "child_count": child_count}
    if set(modules) != set(MODULE_NAMES):
        raise VerifyError("MODULE_SET_FAIL", "six module identities are incomplete", {"actual": sorted(modules)})

    authority = load_json(STATE_AUTHORITY)
    architecture = load_json(ARCHITECTURE)
    independent_signed_fk = independent_signed_fk_transforms(authority)
    frozen_external = architecture_external_facts(architecture)
    sides: Dict[str, Dict[str, Any]] = {}
    for row in side_rows:
        side = str(row.get("side", ""))
        path = fact_path(target_fact(row, f"side {side}"), f"side {side}")
        if side not in SIDE_NAMES or path.name != SIDE_NAMES[side] or side in sides:
            raise VerifyError("SIDE_IDENTITY_FAIL", "side assembly identity/name differs", {"side": side, "path": norm(path)})
        expected_side_flip_contract = {
            "selection_order": "PARENT_THEN_CHILD",
            "alignment": SW_ALIGN_ALIGNED,
            "hinges": dict(FLIP_CONTRACT["sides"][side]),
        }
        if row.get("flip_contract") != expected_side_flip_contract:
            raise VerifyError("SIDE_BUILD_FLIP_CONTRACT_FAIL", "side receipt does not carry the exact frozen flip matrix", {"side": side, "expected": expected_side_flip_contract, "actual": row.get("flip_contract")})
        hinges = row.get("hinges")
        if not isinstance(hinges, list) or [hinge.get("joint") for hinge in hinges if isinstance(hinge, dict)] != ["ROOT", "H12", "H23"]:
            raise VerifyError("SIDE_BUILD_HINGE_ROWS_FAIL", "side receipt lacks ordered ROOT/H12/H23 hinge rows", {"side": side})
        root_lug_bore_validation = None
        interpanel_hinge_validations: List[Dict[str, Any]] = []
        for hinge in hinges:
            joint = str(hinge["joint"])
            wanted_flip = expected_flip(side, joint)
            branch_contract = hinge.get("branch_contract")
            expected_hinge_contract = {
                "selection_order": "PARENT_THEN_CHILD",
                "alignment": SW_ALIGN_ALIGNED,
                "flip": wanted_flip,
            "branch": "NEGATIVE" if SIGNED_FOLD_DIRECTION[side][joint] < 0 else "POSITIVE",
            }
            if branch_contract != expected_hinge_contract:
                raise VerifyError("SIDE_BUILD_HINGE_BRANCH_CONTRACT_FAIL", "hinge receipt branch contract differs", {"side": side, "joint": joint, "expected": expected_hinge_contract, "actual": branch_contract})
            limit_angle = hinge.get("advanced_limit_angle")
            if not isinstance(limit_angle, dict) or limit_angle.get("branch_contract") != {
                "selection_order": "PARENT_THEN_CHILD",
                "requested_alignment": SW_ALIGN_ALIGNED,
                "requested_flip": wanted_flip,
            }:
                raise VerifyError("SIDE_BUILD_ANGLE_CREATE_CONTRACT_FAIL", "AddMate3 receipt arguments differ from frozen branch", {"side": side, "joint": joint, "row": limit_angle})
            validate_angle_branch_readback(limit_angle.get("readback"), side, joint, f"build side {side} hinge {joint}")
            if joint == "ROOT":
                geometry = hinge.get("geometry")
                if not isinstance(geometry, dict) or geometry.get("root_lug_bore_selection_contract") != ROOT_LUG_BORE_SELECTION_CONTRACT:
                    raise VerifyError("SIDE_ROOT_LUG_GEOMETRY_CONTRACT_FAIL", "ROOT hinge lacks the exact dual-ear lug selection contract", {"side": side, "geometry": geometry})
                side_contract = ROOT_LUG_BORE_SELECTION_CONTRACT["sides"][side]
                exact_bound_fact(
                    geometry.get("u_lug"),
                    f"side {side} ROOT u_lug",
                    RUN_ROOT / str(side_contract["u_lug_path"]),
                    str(side_contract["u_lug_sha256"]),
                )
                root_lug_bore_validation = validate_root_lug_bore_readback(geometry.get("moving_bore"), side, f"build side {side} ROOT moving bore")
            else:
                interpanel_hinge_validations.append(validate_interpanel_build_geometry(hinge.get("geometry"), side, joint))
        final_branch_rows = row.get("final_angle_branch_readback")
        if not isinstance(final_branch_rows, list) or [item.get("joint") for item in final_branch_rows if isinstance(item, dict)] != ["ROOT", "H12", "H23"]:
            raise VerifyError("SIDE_BUILD_FINAL_BRANCH_ROWS_FAIL", "side receipt lacks three final nominal branch readbacks", {"side": side})
        for item in final_branch_rows:
            joint = str(item["joint"])
            if item.get("selection_order") != "PARENT_THEN_CHILD" or item.get("alignment") != SW_ALIGN_ALIGNED or item.get("flip") is not expected_flip(side, joint):
                raise VerifyError("SIDE_BUILD_FINAL_BRANCH_CONTRACT_FAIL", "final side branch row differs", {"side": side, "joint": joint, "row": item})
            validate_angle_branch_readback(item.get("readback"), side, joint, f"build side {side} final {joint}")
        configs = row.get("configurations")
        if not isinstance(configs, list) or [item.get("state") for item in configs if isinstance(item, dict)] != list(CONFIGS):
            raise VerifyError("SIDE_STATE_SET_FAIL", "side build row does not contain ordered seven states", {"side": side})
        normalized_configs: Dict[str, Dict[str, Any]] = {}
        for config in configs:
            if not isinstance(config, dict):
                raise VerifyError("SIDE_STATE_ROW_FAIL", "side state row is not an object", {"side": side})
            state = str(config["state"])
            angles = [float(value_in) for value_in in config.get("angles_deg", [])]
            if angles != expected_angles(authority, state, side):
                raise VerifyError("SIDE_STATE_ANGLE_FAIL", "build state angles differ from authority", {"side": side, "state": state})
            dimension_rows = config.get("angle_dimension_readback")
            restored_rows = config.get("restored_angle_branch_readback")
            final_angle_rows = config.get("final_full_table_angle_readback")
            expected_joints = ["ROOT", "H12", "H23"]
            if (
                not isinstance(dimension_rows, list)
                or [item.get("joint") for item in dimension_rows if isinstance(item, dict)] != expected_joints
                or not isinstance(restored_rows, list)
                or [item.get("joint") for item in restored_rows if isinstance(item, dict)] != expected_joints
                or not isinstance(final_angle_rows, list)
                or [item.get("joint") for item in final_angle_rows if isinstance(item, dict)] != expected_joints
            ):
                raise VerifyError("SIDE_STATE_BRANCH_ROWS_FAIL", "build state lacks three complete angle-branch readback sets", {"side": side, "state": state})
            for item in dimension_rows:
                joint = str(item["joint"])
                if (
                    item.get("selection_order") != "PARENT_THEN_CHILD"
                    or item.get("requested_alignment") != SW_ALIGN_ALIGNED
                    or item.get("requested_flip") is not expected_flip(side, joint)
                    or item.get("signed_fold_direction_about_world_x") != SIGNED_FOLD_DIRECTION[side][joint]
                ):
                    raise VerifyError("SIDE_STATE_DIMENSION_BRANCH_CONTRACT_FAIL", "configuration dimension branch contract differs", {"side": side, "state": state, "joint": joint, "row": item})
                validate_angle_branch_readback(item.get("angle_mate_readback"), side, joint, f"build {side}/{state}/{joint} dimension")
            for item in restored_rows:
                joint = str(item["joint"])
                validate_angle_branch_readback(item.get("readback"), side, joint, f"build {side}/{state}/{joint} restored")
            for item in final_angle_rows:
                joint = str(item["joint"])
                if item.get("signed_fold_direction_about_world_x") != SIGNED_FOLD_DIRECTION[side][joint]:
                    raise VerifyError("SIDE_STATE_FINAL_SIGNED_DIRECTION_FAIL", "final configuration angle row carries a different signed direction", {"side": side, "state": state, "joint": joint, "row": item})
                validate_angle_branch_readback(item.get("branch_readback"), side, joint, f"build {side}/{state}/{joint} final table")
            reads = config.get("module_readback")
            final_reads = config.get("final_full_table_module_readback")
            if not isinstance(reads, list) or len(reads) != 3 or not isinstance(final_reads, list) or len(final_reads) != 3:
                raise VerifyError("SIDE_MODULE_READBACK_FAIL", "state lacks both complete three-module transform tables", {"side": side, "state": state})
            transforms: Dict[str, List[float]] = {}
            for read in reads:
                if not isinstance(read, dict):
                    raise VerifyError("SIDE_MODULE_READBACK_ROW_FAIL", "module readback is not an object")
                key = str(read.get("module", ""))
                if key not in {f"{side}{index}" for index in (1, 2, 3)} or key in transforms:
                    raise VerifyError("SIDE_MODULE_READBACK_ID_FAIL", "module readback identity differs", {"key": key})
                transforms[key] = normalize_transform(read.get("transform16"), f"{side}/{state}/{key}")
            final_transforms: Dict[str, List[float]] = {}
            for read in final_reads:
                if not isinstance(read, dict):
                    raise VerifyError("SIDE_FINAL_MODULE_READBACK_ROW_FAIL", "final module readback is not an object")
                key = str(read.get("module", ""))
                if key not in {f"{side}{index}" for index in (1, 2, 3)} or key in final_transforms:
                    raise VerifyError("SIDE_FINAL_MODULE_READBACK_ID_FAIL", "final module readback identity differs", {"key": key})
                final_transforms[key] = normalize_transform(read.get("transform16"), f"{side}/{state}/{key}/final")
            signed_expected = independent_signed_fk[side][state]
            for key in sorted(signed_expected):
                assert_transform(transforms[key], signed_expected[key], f"build/{side}/{state}/{key}/independent_signed_fk")
                assert_transform(final_transforms[key], signed_expected[key], f"build/{side}/{state}/{key}/final_independent_signed_fk")
                assert_transform(final_transforms[key], transforms[key], f"build/{side}/{state}/{key}/two_table_consistency")
            normalized_configs[state] = {"angles_deg": angles, "transforms": transforms, "final_transforms": final_transforms, "independent_signed_fk": signed_expected}
        references = receipt_reference_paths(row.get("references"), f"side {side}")
        if len(row.get("mate_ledger", [])) != 11 or len(row.get("hinges", [])) != 3 or len(row.get("root_retainer_mates", [])) != 2:
            raise VerifyError("SIDE_MATE_BUILD_CONTRACT_FAIL", "build side 3R mate cardinality differs", {"side": side})
        root_reuse = row.get("root_reuse")
        envelope_reuse = row.get("root_functional_envelope_reuse")
        if not isinstance(root_reuse, dict) or set(root_reuse) != {"clevis", "pin", "u_lug", "retainer"}:
            raise VerifyError("SIDE_ROOT_REUSE_FAIL", "side receipt root-core reuse map differs", {"side": side})
        if not isinstance(envelope_reuse, dict) or set(envelope_reuse) != {"torsion_spring_1", "torsion_spring_2", "hard_stop", "harness_service_loop"}:
            raise VerifyError("SIDE_ROOT_ENVELOPE_REUSE_FAIL", "side receipt root-envelope reuse map differs", {"side": side})
        root_facts = {role: check_fact(fact, f"side {side} root {role}")[0] for role, fact in root_reuse.items() if isinstance(fact, dict)}
        envelope_facts = {role: check_fact(fact, f"side {side} envelope {role}")[0] for role, fact in envelope_reuse.items() if isinstance(fact, dict)}
        shared_paths: Dict[str, Path] = {}
        for field in ("shared_spacer", "shared_grommet", "shared_stop_pad"):
            fact = row.get(field)
            if not isinstance(fact, dict):
                raise VerifyError("SIDE_SHARED_ROOT_FACT_FAIL", "side receipt lacks shared root fact", {"side": side, "field": field})
            shared_paths[field] = check_fact(fact, f"side {side} {field}")[0]
        top_paths = {
            root_facts["clevis"], root_facts["pin"], root_facts["retainer"],
            *envelope_facts.values(), *shared_paths.values(),
            *(modules[f"{side}{index}"]["path"] for index in (1, 2, 3)),
        }
        if len(top_paths) != 13:
            raise VerifyError("SIDE_TOP_PATH_CONTRACT_FAIL", "side direct root/envelope/module set must contain 13 paths", {"side": side, "count": len(top_paths)})
        if root_lug_bore_validation is None:
            raise VerifyError("SIDE_ROOT_LUG_BORE_VALIDATION_MISSING", "side ROOT hinge lacks its validated dual-ear bore proof", {"side": side})
        if [item["joint"] for item in interpanel_hinge_validations] != ["H12", "H23"]:
            raise VerifyError("SIDE_INTERPANEL_VALIDATION_SET_FAIL", "side lacks validated H12/H23 nested B-rep proofs", {"side": side, "validations": interpanel_hinge_validations})
        sides[side] = {"path": path, "row": row, "references": references, "configs": normalized_configs, "top_paths": top_paths, "root_lug_bore_validation": root_lug_bore_validation, "interpanel_hinge_validations": interpanel_hinge_validations}
    if set(sides) != {"L", "R"}:
        raise VerifyError("SIDE_SET_FAIL", "both side assemblies are required")

    builder_fact = exact_bound_fact(payload.get("builder"), "production.builder", BUILDER_SOURCE, EXPECTED_BUILDER_SHA256)
    builder_path = BUILDER_SOURCE.resolve()
    manifest_fact = payload.get("cad_manifest")
    if not isinstance(manifest_fact, dict):
        raise VerifyError("CAD_MANIFEST_FACT_FAIL", "build receipt lacks CAD manifest fact")
    manifest_path = (attempt_root / "evidence" / CAD_MANIFEST_NAME).resolve()
    manifest_actual = exact_bound_fact(manifest_fact, "cad_manifest", manifest_path, allowed_root=attempt_root)
    manifest = load_json(manifest_path)
    manifest_identity = receipt_storage_identity(manifest, "CAD manifest")
    if (
        manifest.get("schema") != "F3R2_V5_SOLAR_R2B_A_CAD_MANIFEST_V1"
        or manifest_identity != build_identity
        or manifest.get("builder") != builder_fact
        or manifest.get("contract_sha256") != EXPECTED_BUILD_CONTRACT_SHA256
        or manifest.get("production_root_flip_authorization") != root_flip_authorization
        or manifest.get("counts") != EXPECTED_COUNTS
        or not isinstance(manifest.get("files"), list)
        or len(manifest["files"]) != 46
    ):
        raise VerifyError("CAD_MANIFEST_CONTENT_FAIL", "CAD manifest counts/files differ")
    manifest_rows: Dict[Path, Dict[str, Any]] = {}
    for index, row in enumerate(manifest["files"]):
        if not isinstance(row, dict):
            raise VerifyError("CAD_MANIFEST_ROW_FAIL", "CAD manifest file row is not an object", {"index": index})
        path, actual = check_fact(row, f"manifest[{index}]", attempt_root)
        if row != actual or path in manifest_rows:
            raise VerifyError("CAD_MANIFEST_FACT_EXACT_FAIL", "CAD manifest fact is not exact and unique", {"index": index, "row": row, "actual": actual})
        manifest_rows[path] = actual
    manifest_paths = set(manifest_rows)
    if manifest_paths != set(artifacts) or any(manifest_rows[path] != artifacts[path]["fact"] for path in manifest_paths):
        raise VerifyError("CAD_MANIFEST_SET_FAIL", "CAD manifest file set differs")
    manifest_sha256_row = payload.get("cad_manifest_sha256_text")
    if not isinstance(manifest_sha256_row, dict):
        raise VerifyError("CAD_MANIFEST_SHA256_FACT_FAIL", "build receipt lacks CAD manifest SHA256 text fact")
    manifest_sha256_path = (attempt_root / "evidence" / CAD_MANIFEST_SHA256_NAME).resolve()
    manifest_sha256_fact = exact_bound_fact(manifest_sha256_row, "cad_manifest_sha256_text", manifest_sha256_path, allowed_root=attempt_root)
    expected_manifest_lines = [
        f"{fact['sha256']}  {fact['bytes']}  {path.relative_to(attempt_root).as_posix()}"
        for path, fact in manifest_rows.items()
    ]
    expected_manifest_text = "\n".join(sorted(expected_manifest_lines)) + "\n"
    if manifest_sha256_path.read_text(encoding="utf-8") != expected_manifest_text:
        raise VerifyError("CAD_MANIFEST_SHA256_CONTENT_FAIL", "CAD manifest SHA256 text does not exactly bind all 46 relative files")

    # The builder must itself bind the final frozen chain; this prevents an old
    # executable from creating a superficially compatible receipt.
    authority_bundle = payload.get("authority_bundle")
    if not isinstance(authority_bundle, dict):
        raise VerifyError("BUILD_AUTHORITY_BUNDLE_FAIL", "build receipt lacks authority bundle")
    for label, path, expected in FROZEN_BINDINGS:
        row = authority_bundle.get(label)
        if not isinstance(row, dict):
            raise VerifyError("BUILD_FROZEN_BINDING_MISSING", "builder did not bind final frozen input", {"label": label})
        bound_path, bound_fact = check_fact(row, f"authority_bundle.{label}")
        if bound_path != path.resolve() or bound_fact["sha256"] != expected:
            raise VerifyError("BUILD_FROZEN_BINDING_FAIL", "builder bound a different frozen input", {"label": label})

    handoff = validate_handoff(
        attempt_root,
        handoff_path,
        set(artifacts),
        build_pid,
        payload,
        builder_fact,
        microfixture_lineage["micro_fresh_receipt"],
        manifest_actual,
        manifest_sha256_fact,
    )
    if payload.get("fresh_pid_verifier_handoff") != file_fact(handoff_path):
        raise VerifyError("BUILD_HANDOFF_FACT_FAIL", "production build receipt does not carry the exact canonical handoff fact", {"expected": file_fact(handoff_path), "actual": payload.get("fresh_pid_verifier_handoff")})
    external_paths = set().union(*(row["references"] for row in modules.values()), *(row["references"] for row in sides.values())) - set(artifacts)
    if external_paths != set(frozen_external):
        raise VerifyError("FROZEN_EXTERNAL_SET_FAIL", "receipt nested external reference set differs from 19 frozen root core/envelope files", {"expected": sorted(norm(path) for path in frozen_external), "actual": sorted(norm(path) for path in external_paths)})
    return {
        "payload": payload,
        "receipt": file_fact(receipt_path),
        "handoff": file_fact(handoff_path),
        "handoff_payload": handoff,
        "attempt_id": build_identity["attempt_id"],
        "storage_id": build_identity["storage_id"],
        "session": {"pid": build_pid, "process_create_time": build_create_time, "process_start_utc": build_start_text, "revision": build_session["revision"]},
        "artifacts": artifacts,
        "parts": {path: data for path, data in artifacts.items() if data["kind"] == "part"},
        "collars": collar_rows,
        "modules": modules,
        "sides": sides,
        "external": frozen_external,
        "builder": {"path": builder_path, "fact": builder_fact},
        "manifest_path": manifest_path,
        "manifest_sha256_path": manifest_sha256_path,
        "microfixture_lineage": microfixture_lineage,
        "production_root_flip_authorization": root_flip_authorization,
        "angle_branch_evidence": branch_evidence,
    }


def terminal_evidence(attempt_root: Path) -> List[str]:
    evidence = attempt_root / "evidence"
    paths: Set[Path] = set()
    pass_path = attempt_root / PASS_RELATIVE
    if pass_path.exists():
        paths.add(pass_path)
    if evidence.is_dir():
        paths.update(evidence.glob(FAIL_GLOB))
    return [norm(path) for path in sorted(paths, key=norm)]


def protected_snapshot(contract: Mapping[str, Any], receipt_path: Path, handoff_path: Path) -> Dict[str, Dict[str, Any]]:
    paths = set(contract["artifacts"]) | set(contract["external"]) | {
        receipt_path.resolve(),
        handoff_path.resolve(),
        contract["manifest_path"],
        contract["manifest_sha256_path"],
        contract["builder"]["path"],
        MICROFIXTURE_SOURCE.resolve(),
        Path(contract["microfixture_lineage"]["micro_fresh_receipt"]["path"]).resolve(),
        Path(contract["microfixture_lineage"]["micro_build_receipt"]["path"]).resolve(),
    }
    paths.update(Path(path).resolve() for path in contract["microfixture_lineage"]["cad_manifest"])
    paths.update(path.resolve() for _label, path, _sha in FROZEN_BINDINGS)
    return {norm(path): file_fact(path) for path in sorted(paths, key=norm)}


def cad_snapshot(contract: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {norm(path): file_fact(path) for path in sorted(contract["artifacts"], key=norm)}


def transaction_static_audit(attempt_root: Path, receipt_path: Path, handoff_path: Path) -> Dict[str, Any]:
    contract = validate_build_receipt(attempt_root, receipt_path, handoff_path)
    terminal = terminal_evidence(attempt_root)
    return {
        "attempt_root": norm(attempt_root),
        "attempt_id": contract["attempt_id"],
        "storage_id": contract["storage_id"],
        "build_receipt": contract["receipt"],
        "handoff": contract["handoff"],
        "artifact_counts": EXPECTED_COUNTS,
        "module_paths": {key: norm(row["path"]) for key, row in contract["modules"].items()},
        "side_paths": {side: norm(row["path"]) for side, row in contract["sides"].items()},
        "release_provenance_lineage": {
            "microfixture": contract["microfixture_lineage"],
            "production_root_flip_authorization": contract["production_root_flip_authorization"],
            "angle_branch_evidence": contract["angle_branch_evidence"],
        },
        "existing_terminal_evidence": terminal,
        "execution_authorized": not terminal,
        "solidworks_touched": False,
        "verdict": "V5_SOLAR_R2B_A_FRESH_VERIFY_TRANSACTION_READY" if not terminal else "V5_SOLAR_R2B_A_FRESH_VERIFY_TRANSACTION_HOLD",
    }


def attach_fresh_session(expected_pid: int, build_session: Mapping[str, Any]) -> Tuple[Any, Any, Any, Dict[str, Any]]:
    import psutil
    import pythoncom
    import win32com.client
    from win32com.client import gencache

    pythoncom.CoInitialize()
    types = gencache.GetModuleForTypelib(*SW_TLB)
    raw = win32com.client.GetActiveObject(SW_PROG_ID)
    sw = wrap(raw, "ISldWorks", types, pythoncom)
    actual_pid = int(value(sw, "GetProcessID"))
    revision = str(value(sw, "RevisionNumber"))
    document_count = int(value(sw, "GetDocumentCount"))
    if actual_pid != int(expected_pid) or not revision.startswith(EXPECTED_SW_REVISION_PREFIX):
        raise VerifyError("FRESH_SESSION_IDENTITY_FAIL", "active SOLIDWORKS PID/revision differs", {"expected_pid": expected_pid, "actual_pid": actual_pid, "revision": revision})
    if document_count != 0 or value(sw, "ActiveDoc") is not None:
        raise VerifyError("FRESH_SESSION_NOT_EMPTY", "fresh verifier requires zero open documents", {"document_count": document_count})
    process = psutil.Process(actual_pid)
    executable, create_time = Path(process.exe()).resolve(), float(process.create_time())
    if os.path.normcase(str(executable)) != os.path.normcase(str(SOLIDWORKS_EXE.resolve())):
        raise VerifyError("FRESH_EXECUTABLE_FAIL", "active process is not the pinned SOLIDWORKS executable", {"actual": norm(executable)})
    build_pid, build_create_time = int(build_session["pid"]), float(build_session["process_create_time"])
    if actual_pid == build_pid or abs(create_time - build_create_time) < 0.001 or create_time <= build_create_time:
        raise VerifyError("FRESH_PROCESS_IDENTITY_FAIL", "verifier PID/create-time is not newer and distinct", {"build_pid": build_pid, "build_create_time": build_create_time, "verify_pid": actual_pid, "verify_create_time": create_time})
    try:
        old = psutil.Process(build_pid)
        if abs(float(old.create_time()) - build_create_time) < 0.001:
            raise VerifyError("BUILD_PROCESS_STILL_ALIVE", "exact build process remains alive", {"pid": build_pid})
    except psutil.NoSuchProcess:
        pass
    return sw, types, pythoncom, {
        "attach_only": True,
        "pid": actual_pid,
        "process_create_time": create_time,
        "process_start_utc": datetime.fromtimestamp(create_time, timezone.utc).isoformat(),
        "revision": revision,
        "executable": norm(executable),
        "document_count_before": 0,
        "active_doc_is_null_before": True,
        "different_pid_from_build": True,
        "different_process_create_time_from_build": True,
        "newer_process_than_build": True,
    }


def open_read_only(sw: Any, path: Path, document_type: int, types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    returned = sw.OpenDoc6(str(path), document_type, SW_OPEN_SILENT | SW_OPEN_READ_ONLY, "", 0, 0)
    raw, outs = unpack(returned)
    if len(outs) < 2:
        raise VerifyError("READ_ONLY_OPEN_RETURN_FAIL", "OpenDoc6 did not return errors/warnings", {"path": norm(path), "returned": repr(returned)})
    errors, warnings = int(outs[0]), int(outs[1])
    if raw is None or errors != 0 or warnings != 0:
        raise VerifyError("READ_ONLY_OPEN_FAIL", "native document did not open cleanly read-only", {"path": norm(path), "errors": errors, "warnings": warnings})
    model = wrap(raw, "IModelDoc2", types, pythoncom)
    if not bool(value(model, "IsOpenedReadOnly")) or Path(str(value(model, "GetPathName"))).resolve() != path.resolve() or int(value(model, "GetType")) != document_type:
        raise VerifyError("READ_ONLY_OPEN_IDENTITY_FAIL", "opened document mode/path/type differs", {"path": norm(path)})
    if bool(value(model, "GetSaveFlag")):
        raise VerifyError("READ_ONLY_PRE_DIRTY_FAIL", "read-only document is dirty immediately after open", {"path": norm(path)})
    return model, {"errors": errors, "warnings": warnings, "read_only": True, "save_flag_pre": False, "path": norm(path)}


def transform_array(component: Any) -> List[float]:
    transform = value(component, "Transform2")
    if transform is None:
        raise VerifyError("COMPONENT_TRANSFORM_NULL", "component has no Transform2", {"name2": str(value(component, "Name2"))})
    return normalize_transform(as_list(value(transform, "ArrayData")), str(value(component, "Name2")))


def transform_point_mm(transform: Sequence[float], point_mm: Sequence[float]) -> List[float]:
    x, y, z = (float(value_in) / 1000.0 for value_in in point_mm)
    return [(transform[0] * x + transform[3] * y + transform[6] * z + transform[9]) * 1000.0, (transform[1] * x + transform[4] * y + transform[7] * z + transform[10]) * 1000.0, (transform[2] * x + transform[5] * y + transform[8] * z + transform[11]) * 1000.0]


def transform_direction(transform: Sequence[float], direction: Sequence[float]) -> List[float]:
    x, y, z = (float(value_in) for value_in in direction)
    result = [transform[0] * x + transform[3] * y + transform[6] * z, transform[1] * x + transform[4] * y + transform[7] * z, transform[2] * x + transform[5] * y + transform[8] * z]
    length = math.sqrt(sum(value_in * value_in for value_in in result))
    if length <= 1.0e-12:
        raise VerifyError("FRESH_NESTED_DIRECTION_ZERO", "nested component maps local Z to zero")
    return [value_in / length for value_in in result]


def component_by_exact_path(model: Any, path: Path, types: Any, pythoncom: Any) -> Any:
    matches = [component for component in get_components(model, False, types, pythoncom) if Path(str(value(component, "GetPathName"))).resolve() == path.resolve()]
    if len(matches) != 1:
        raise VerifyError("FRESH_NESTED_COMPONENT_CARDINALITY_FAIL", "nested component path is not unique", {"path": norm(path), "count": len(matches)})
    return matches[0]


def component_bodies(component: Any, types: Any, pythoncom: Any) -> List[Any]:
    for name, args in (("GetBodies2", (0,)), ("GetBodies2", (1,)), ("GetBody", ())):
        try:
            bodies = as_list(value(component, name, *args))
        except Exception:
            continue
        if bodies:
            return [wrap(body, "IBody2", types, pythoncom) for body in bodies]
    raise VerifyError("FRESH_NESTED_BODY_FAIL", "nested component exposes no body", {"component": str(value(component, "Name2"))})


def cold_nested_local_z_fact(component: Any, radius_mm: float, expected_world_z0_mm: Sequence[float], label: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    cylinders: List[Tuple[List[float], float]] = []
    all_cylinders: List[Dict[str, Any]] = []
    planes: List[Tuple[List[float], float]] = []
    all_planes: List[Dict[str, Any]] = []
    tolerance = INTERPANEL_NESTED_BREP_FRAME_CONTRACT["tolerances"]
    for body in component_bodies(component, types, pythoncom):
        for raw_face in as_list(value(body, "GetFaces")):
            face = wrap(raw_face, "IFace2", types, pythoncom)
            surface = wrap(value(face, "GetSurface"), "ISurface", types, pythoncom)
            area_mm2 = float(value(face, "GetArea")) * 1.0e6
            if bool(surface.IsCylinder()):
                params = [float(value_in) for value_in in as_list(value(surface, "CylinderParams"))]
                all_cylinders.append({"cylinder_params": params, "area_mm2": area_mm2})
                if len(params) >= 7 and abs(params[3]) < 1.0e-5 and abs(params[4]) < 1.0e-5 and abs(abs(params[5]) - 1.0) < 1.0e-5 and abs(params[0] * 1000.0) <= float(tolerance["local_axis_point_mm"]) and abs(params[1] * 1000.0) <= float(tolerance["local_axis_point_mm"]) and abs(params[6] * 1000.0 - radius_mm) <= float(tolerance["radius_mm"]):
                    cylinders.append((params, area_mm2))
            elif bool(surface.IsPlane()):
                params = [float(value_in) for value_in in as_list(value(surface, "PlaneParams"))]
                all_planes.append({"plane_params": params, "area_mm2": area_mm2})
                if len(params) >= 6 and abs(params[0]) < 1.0e-5 and abs(params[1]) < 1.0e-5 and abs(abs(params[2]) - 1.0) < 1.0e-5 and abs(params[5] * 1000.0) <= float(tolerance["local_axis_point_mm"]):
                    planes.append((params, area_mm2))
    if len(cylinders) != 1 or len(planes) != 1:
        raise VerifyError("FRESH_NESTED_LOCAL_Z_SIGNATURE_FAIL", "cold nested child lacks one local-Z cylinder and one local-Z=0 plane", {"label": label, "cylinder_count": len(cylinders), "plane_count": len(planes), "all_cylinders": all_cylinders, "all_planes": all_planes})
    params, area_mm2 = cylinders[0]
    plane_params, plane_area = planes[0]
    axial_length_mm = area_mm2 / (2.0 * math.pi * params[6] * 1000.0)
    transform = transform_array(component)
    fact = {
        "label": label,
        "component": str(value(component, "Name2")),
        "component_file": file_fact(Path(str(value(component, "GetPathName"))).resolve()),
        "entity_signature_coordinate_frame": "NESTED_CHILD_PART_LOCAL",
        "all_raw_cylinders": all_cylinders,
        "selected_cylinder_params": params,
        "selected_cylinder_area_mm2": area_mm2,
        "selected_cylinder_axial_length_mm": axial_length_mm,
        "cylinder_candidate_count": 1,
        "all_raw_planes": all_planes,
        "selected_end_plane_params": plane_params,
        "selected_end_plane_area_mm2": plane_area,
        "end_plane_candidate_count": 1,
        "child_transform16": transform,
        "canonical_local_z0_world_mm": transform_point_mm(transform, [0.0, 0.0, 0.0]),
        "canonical_local_z28_world_mm": transform_point_mm(transform, [0.0, 0.0, 28.0]),
        "canonical_local_plus_z_world_direction": transform_direction(transform, [0.0, 0.0, 1.0]),
        "expected_world_z0_mm": list(expected_world_z0_mm),
        "expected_world_z28_mm": [float(expected_world_z0_mm[0]) + 28.0, float(expected_world_z0_mm[1]), float(expected_world_z0_mm[2])],
    }
    validation = validate_interpanel_child_receipt(fact, radius_mm, expected_world_z0_mm, label)
    return {**fact, "validation": validation, "verdict": "V5_SOLAR_R2B_A_FRESH_NESTED_LOCAL_Z_CHILD_PASS"}


def cold_interpanel_pair(model: Any, side: str, state: str, joint: str, pin_path: Path, collar_path: Path, expected_world_z0_mm: Sequence[float], types: Any, pythoncom: Any) -> Dict[str, Any]:
    pin = cold_nested_local_z_fact(component_by_exact_path(model, pin_path, types, pythoncom), 2.0, expected_world_z0_mm, f"fresh/{side}/{state}/{joint}/pin", types, pythoncom)
    collar = cold_nested_local_z_fact(component_by_exact_path(model, collar_path, types, pythoncom), 2.2, expected_world_z0_mm, f"fresh/{side}/{state}/{joint}/collar", types, pythoncom)
    point_delta = vector_distance(pin["canonical_local_z0_world_mm"], collar["canonical_local_z0_world_mm"])
    direction_error = vector_cross_norm(pin["canonical_local_plus_z_world_direction"], collar["canonical_local_plus_z_world_direction"])
    tolerance = INTERPANEL_NESTED_BREP_FRAME_CONTRACT["tolerances"]
    if point_delta > float(tolerance["world_point_mm"]) or direction_error > float(tolerance["world_direction_cross_norm"]):
        raise VerifyError("FRESH_INTERPANEL_WORLD_CONTINUITY_FAIL", "cold pin/collar axes are not coincident and collinear", {"side": side, "state": state, "joint": joint, "point_delta_mm": point_delta, "direction_cross_norm": direction_error})
    return {"side": side, "state": state, "joint": joint, "expected_world_z0_mm": list(expected_world_z0_mm), "pin": pin, "collar": collar, "world_point_delta_mm": point_delta, "world_direction_cross_norm": direction_error, "verdict": "V5_SOLAR_R2B_A_FRESH_INTERPANEL_WORLD_AXIS_PASS"}


def mat_mul(first: Sequence[Sequence[float]], second: Sequence[Sequence[float]]) -> List[List[float]]:
    return [[sum(float(first[row][k]) * float(second[k][column]) for k in range(3)) for column in range(3)] for row in range(3)]


def mat_vec(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> List[float]:
    return [sum(float(matrix[row][column]) * float(vector[column]) for column in range(3)) for row in range(3)]


def rx(degrees: float) -> List[List[float]]:
    angle = math.radians(float(degrees))
    cosine, sine = math.cos(angle), math.sin(angle)
    return [[1.0, 0.0, 0.0], [0.0, cosine, -sine], [0.0, sine, cosine]]


def add_vector(first: Sequence[float], second: Sequence[float]) -> List[float]:
    return [float(first[index]) + float(second[index]) for index in range(3)]


def transpose(matrix: Sequence[Sequence[float]]) -> List[List[float]]:
    return [[float(matrix[column][row]) for column in range(3)] for row in range(3)]


def compose(first: Mapping[str, Any], second: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "rotation": mat_mul(first["rotation"], second["rotation"]),
        "translation_mm": [float(first["translation_mm"][axis]) + mat_vec(first["rotation"], second["translation_mm"])[axis] for axis in range(3)],
    }


def inverse_rigid(frame_in: Mapping[str, Any]) -> Dict[str, Any]:
    rotation = transpose(frame_in["rotation"])
    return {"rotation": rotation, "translation_mm": mat_vec(rotation, [-float(value_in) for value_in in frame_in["translation_mm"]])}


def sw_transform(frame_in: Mapping[str, Any]) -> List[float]:
    rotation, translation = frame_in["rotation"], [float(value_in) / 1000.0 for value_in in frame_in["translation_mm"]]
    return [
        rotation[0][0], rotation[1][0], rotation[2][0],
        rotation[0][1], rotation[1][1], rotation[2][1],
        rotation[0][2], rotation[1][2], rotation[2][2],
        translation[0], translation[1], translation[2],
        1.0, 0.0, 0.0, 0.0,
    ]


def transform_error(actual: Sequence[float], expected: Sequence[float]) -> Dict[str, float]:
    translation = math.sqrt(sum((float(actual[index]) - float(expected[index])) ** 2 for index in (9, 10, 11))) * 1000.0
    ar = [[float(actual[column * 3 + row]) for column in range(3)] for row in range(3)]
    er = [[float(expected[column * 3 + row]) for column in range(3)] for row in range(3)]
    relative = mat_mul(transpose(er), ar)
    cosine = max(-1.0, min(1.0, (sum(relative[index][index] for index in range(3)) - 1.0) / 2.0))
    return {"translation_mm": translation, "rotation_deg": math.degrees(math.acos(cosine))}


def assert_transform(actual: Sequence[float], expected: Sequence[float], label: str) -> Dict[str, float]:
    error = transform_error(actual, expected)
    if error["translation_mm"] > TRANS_TOL_MM or error["rotation_deg"] > ROT_TOL_DEG:
        raise VerifyError("TRANSFORM_READBACK_FAIL", f"{label} transform differs", {"error": error})
    return error


def signed_rx_deg(transform: Sequence[float]) -> float:
    values = normalize_transform(transform, "signed_rx")
    return math.degrees(math.atan2(float(values[5]), float(values[4])))


def oracle_expected_transforms() -> Dict[str, Dict[str, Dict[str, List[float]]]]:
    oracle = load_json(STATIC_ORACLE)
    rows = oracle.get("states")
    if not isinstance(rows, list) or len(rows) != 7:
        raise VerifyError("ORACLE_STATE_ROWS_FAIL", "static oracle does not contain seven states")
    indexed = {str(row.get("state")): row for row in rows if isinstance(row, dict)}
    nominal = indexed["SOLAR_DEPLOYED_NOMINAL"]
    result: Dict[str, Dict[str, Dict[str, List[float]]]] = {"L": {}, "R": {}}
    for side, oracle_key in (("L", "left"), ("R", "right")):
        nominal_panels = nominal[oracle_key]["panels"]
        for state in CONFIGS:
            state_panels = indexed[state][oracle_key]["panels"]
            transforms: Dict[str, List[float]] = {}
            for index in range(3):
                state_panel, nominal_panel = state_panels[index], nominal_panels[index]
                current = {"rotation": state_panel["rotation_3x3"], "translation_mm": state_panel["inboard_hinge_mm"]}
                authored = {"rotation": nominal_panel["rotation_3x3"], "translation_mm": nominal_panel["inboard_hinge_mm"]}
                transforms[f"{side}{index + 1}"] = sw_transform(compose(current, inverse_rigid(authored)))
            result[side][state] = transforms
    return result


def independent_signed_fk_transforms(authority: Mapping[str, Any]) -> Dict[str, Dict[str, Dict[str, List[float]]]]:
    """Recompute all 2x7 module poses from signed joint accumulation, independent of the static-oracle file."""
    pitch = float(authority["candidate_geometry"]["panel_pitch_mm"])
    nominal_frames: Dict[str, List[Dict[str, Any]]] = {}
    state_frames: Dict[str, Dict[str, List[Dict[str, Any]]]] = {"L": {}, "R": {}}
    for side in ("L", "R"):
        side_sign = 1.0 if side == "L" else -1.0

        def frames_for(angles_deg: Sequence[float]) -> List[Dict[str, Any]]:
            if len(angles_deg) != 3:
                raise VerifyError("SIGNED_FK_ANGLE_COUNT_FAIL", "signed FK requires exactly three logical angles", {"side": side, "angles": list(angles_deg)})
            beta = [90.0 - float(value_in) for value_in in angles_deg]
            theta = [
                SIGNED_FOLD_DIRECTION[side]["ROOT"] * beta[0],
                0.0,
                0.0,
            ]
            theta[1] = theta[0] + SIGNED_FOLD_DIRECTION[side]["H12"] * beta[1]
            theta[2] = theta[1] + SIGNED_FOLD_DIRECTION[side]["H23"] * beta[2]
            hinge = [-61.0, side_sign * 143.15, 0.0]
            rows: List[Dict[str, Any]] = []
            for index, signed_angle in enumerate(theta, start=1):
                rotation = rx(signed_angle)
                rows.append({"panel_index": index, "signed_rx_deg": signed_angle, "frame": {"rotation": rotation, "translation_mm": list(hinge)}})
                hinge = add_vector(hinge, mat_vec(rotation, [0.0, side_sign * pitch, 0.0]))
            return rows

        nominal_frames[side] = frames_for((90.0, 90.0, 90.0))
        for state in CONFIGS:
            state_frames[side][state] = frames_for(expected_angles(authority, state, side))
    result: Dict[str, Dict[str, Dict[str, List[float]]]] = {"L": {}, "R": {}}
    for side in ("L", "R"):
        for state in CONFIGS:
            result[side][state] = {}
            for current, authored in zip(state_frames[side][state], nominal_frames[side]):
                result[side][state][f"{side}{current['panel_index']}"] = sw_transform(compose(current["frame"], inverse_rigid(authored["frame"])))
    return result


def mirror_transform(left: Sequence[float]) -> List[float]:
    rotation = [[float(left[column * 3 + row]) for column in range(3)] for row in range(3)]
    mirror = [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, 1.0]]
    mirrored = mat_mul(mat_mul(mirror, rotation), mirror)
    translation_mm = [float(left[9]) * 1000.0, -float(left[10]) * 1000.0, float(left[11]) * 1000.0]
    return sw_transform({"rotation": mirrored, "translation_mm": translation_mm})


def get_components(model: Any, top_only: bool, types: Any, pythoncom: Any) -> List[Any]:
    assembly = wrap(model, "IAssemblyDoc", types, pythoncom)
    return [wrap(raw, "IComponent2", types, pythoncom) for raw in as_list(assembly.GetComponents(top_only))]


def component_ledger(model: Any, top_only: bool, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for component in get_components(model, top_only, types, pythoncom):
        raw_path = str(value(component, "GetPathName"))
        if not raw_path:
            raise VerifyError("VIRTUAL_COMPONENT_FAIL", "virtual/unsaved component is prohibited", {"name2": str(value(component, "Name2"))})
        path = Path(raw_path).resolve()
        if not path.is_file() or not is_under(path, RUN_ROOT):
            raise VerifyError("COMPONENT_REFERENCE_FAIL", "component reference is missing or outside V5", {"path": norm(path)})
        try:
            solving = int(value(component, "Solving"))
        except Exception:
            solving = None
        try:
            referenced_configuration = str(value(component, "ReferencedConfiguration"))
        except Exception:
            referenced_configuration = None
        rows.append({
            "name2": str(value(component, "Name2")),
            "path": norm(path),
            "path_text": norm(path),
            "file": file_fact(path),
            "fixed": bool(value(component, "IsFixed")),
            "constrained_status": int(value(component, "GetConstrainedStatus")),
            "suppression": int(value(component, "GetSuppression")),
            "solving": solving,
            "referenced_configuration": referenced_configuration,
            "transform16": transform_array(component),
        })
    return sorted(rows, key=lambda row: (row["path_text"], row["name2"]))


def feature_error_state(feature: Any) -> Dict[str, Any]:
    legacy = int(value(feature, "GetErrorCode"))
    returned = value(feature, "GetErrorCode2", False)
    code2, outs = unpack(returned)
    if len(outs) != 1 or int(code2) != legacy:
        raise VerifyError("MATE_ERROR_API_FAIL", "mate feature error APIs disagree", {"legacy": legacy, "returned": repr(returned)})
    return {"feature_error_code": legacy, "feature_error_code2": int(code2), "feature_is_warning": bool(outs[0]), "suppressed": bool(value(feature, "IsSuppressed"))}


def live_angle_flip_readback(mate: Any, definition: Any) -> Dict[str, Any]:
    values: Dict[str, bool] = {}
    errors: Dict[str, str] = {}
    for label, obj, member in (
        ("IMate2.Flipped", mate, "Flipped"),
        ("IAngleMateFeatureData.FlipDimension", definition, "FlipDimension"),
    ):
        try:
            values[label] = bool(value(obj, member))
        except Exception as exc:
            errors[label] = repr(exc)
    if not values:
        raise VerifyError("ANGLE_FLIP_READBACK_UNAVAILABLE", "neither IMate2.Flipped nor IAngleMateFeatureData.FlipDimension is readable", {"errors": errors})
    if len(set(values.values())) != 1:
        raise VerifyError("ANGLE_FLIP_READBACK_DISAGREEMENT", "live IMate2 and angle-definition flip values disagree", {"values": values, "errors": errors})
    return {"flipped": next(iter(values.values())), "sources": values, "unavailable_sources": errors}


def mate_fact(feature: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    raw_mate = value(feature, "GetSpecificFeature2")
    if raw_mate is None:
        raise VerifyError("MATE_OBJECT_NULL", "mate feature lacks IMate2", {"feature": str(value(feature, "Name"))})
    mate = wrap(raw_mate, "IMate2", types, pythoncom)
    count = int(value(mate, "GetMateEntityCount"))
    endpoints: List[str] = []
    reference_types: List[int] = []
    for index in range(count):
        raw_entity = mate.MateEntity(index)
        if raw_entity is None:
            raise VerifyError("MATE_ENTITY_NULL", "mate endpoint is null", {"index": index})
        entity = wrap(raw_entity, "IMateEntity2", types, pythoncom)
        raw_component = value(entity, "ReferenceComponent")
        if raw_component is None:
            raise VerifyError("MATE_COMPONENT_NULL", "mate endpoint lacks component")
        component = wrap(raw_component, "IComponent2", types, pythoncom)
        path = Path(str(value(component, "GetPathName"))).resolve()
        if not path.is_file():
            raise VerifyError("MATE_ENDPOINT_PATH_FAIL", "mate endpoint path is absent", {"path": norm(path)})
        endpoints.append(norm(path))
        reference_types.append(int(value(entity, "ReferenceType2")))
    row = {
        "feature_name": str(value(feature, "Name")),
        "mate_type": int(value(mate, "Type")),
        "alignment": int(value(mate, "Alignment")),
        "entity_count": count,
        "component_paths": sorted(endpoints),
        "reference_types": sorted(reference_types),
        **feature_error_state(feature),
    }
    if count != 2 or row["feature_error_code"] != 0 or row["feature_error_code2"] != 0 or row["feature_is_warning"] or row["suppressed"]:
        raise VerifyError("MATE_HEALTH_FAIL", "mate is errored, warned, suppressed, or not two-ended", row)
    if row["mate_type"] == SW_MATE_ANGLE:
        raw_definition = value(feature, "GetDefinition")
        if raw_definition is None:
            raise VerifyError("ANGLE_DEFINITION_NULL", "angle mate lacks feature definition", row)
        definition = wrap(raw_definition, "IAngleMateFeatureData", types, pythoncom)
        flip = live_angle_flip_readback(mate, definition)
        row["flipped"] = flip["flipped"]
        row["flip_readback"] = flip
        row["advanced_limit_angle"] = {
            "advanced": bool(value(definition, "IsAdvancedMate")),
            "minimum_angle_rad": float(value(definition, "MinimumAngle")),
            "maximum_angle_rad": float(value(definition, "MaximumAngle")),
            "angle_rad": float(value(definition, "Angle")),
        }
        raw_display = mate.DisplayDimension2(0)
        if raw_display is None:
            raise VerifyError("ANGLE_DISPLAY_DIMENSION_NULL", "angle mate lacks DisplayDimension2(0)", row)
        display = wrap(raw_display, "IDisplayDimension", types, pythoncom)
        raw_dimension = display.GetDimension2(0)
        if raw_dimension is None:
            raise VerifyError("ANGLE_DIMENSION_NULL", "angle mate display lacks IDimension", row)
        dimension = wrap(raw_dimension, "IDimension", types, pythoncom)
        row["angle_dimension_full_name"] = str(value(dimension, "FullName"))
    return row


def angle_dimension_readback(model: Any, feature_name: str, configuration: str, expected_rad: float, types: Any, pythoncom: Any) -> Dict[str, Any]:
    raw = value(model, "FirstFeature")
    for _ in range(10000):
        if raw is None:
            break
        feature = wrap(raw, "IFeature", types, pythoncom)
        if str(value(feature, "GetTypeName2")) == "MateGroup":
            sub = value(feature, "GetFirstSubFeature")
            for _sub in range(10000):
                if sub is None:
                    break
                typed = wrap(sub, "IFeature", types, pythoncom)
                if str(value(typed, "Name")) == feature_name:
                    raw_mate = value(typed, "GetSpecificFeature2")
                    if raw_mate is None:
                        raise VerifyError("ANGLE_MATE_OBJECT_NULL", "named angle feature lacks IMate2", {"feature": feature_name})
                    mate = wrap(raw_mate, "IMate2", types, pythoncom)
                    raw_display = mate.DisplayDimension2(0)
                    if raw_display is None:
                        raise VerifyError("ANGLE_DISPLAY_DIMENSION_NULL", "named angle feature lacks DisplayDimension2(0)", {"feature": feature_name})
                    display = wrap(raw_display, "IDisplayDimension", types, pythoncom)
                    raw_dimension = display.GetDimension2(0)
                    if raw_dimension is None:
                        raise VerifyError("ANGLE_DIMENSION_NULL", "named angle display lacks IDimension", {"feature": feature_name})
                    dimension = wrap(raw_dimension, "IDimension", types, pythoncom)
                    actual_rad = float(dimension.GetSystemValue2(configuration))
                    if abs(actual_rad - expected_rad) > 2.0e-6:
                        raise VerifyError("SIDE_ANGLE_DIMENSION_TABLE_FAIL", "cold configuration-specific angle dimension differs from frozen beta=90-alpha", {"configuration": configuration, "feature": feature_name, "expected_rad": expected_rad, "actual_rad": actual_rad})
                    return {"feature_name": feature_name, "configuration": configuration, "expected_rad": expected_rad, "readback_rad": actual_rad, "logical_alpha_deg": 90.0 - math.degrees(actual_rad), "dimension_full_name": str(value(dimension, "FullName"))}
                sub = value(typed, "GetNextSubFeature")
            else:
                raise VerifyError("MATE_SUBFEATURE_LIMIT", "mate subfeature traversal exceeded guard")
        raw = value(feature, "GetNextFeature")
    raise VerifyError("ANGLE_FEATURE_NOT_FOUND", "named angle mate is absent", {"feature": feature_name, "configuration": configuration})


def mate_ledger(model: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    raw = value(model, "FirstFeature")
    for _ in range(10000):
        if raw is None:
            names = [row["feature_name"] for row in rows]
            if len(names) != len(set(names)):
                raise VerifyError("MATE_NAME_DUPLICATE", "mate feature names are not unique")
            return rows
        feature = wrap(raw, "IFeature", types, pythoncom)
        if str(value(feature, "GetTypeName2")) == "MateGroup":
            sub = value(feature, "GetFirstSubFeature")
            for _sub in range(10000):
                if sub is None:
                    break
                typed = wrap(sub, "IFeature", types, pythoncom)
                rows.append(mate_fact(typed, types, pythoncom))
                sub = value(typed, "GetNextSubFeature")
            else:
                raise VerifyError("MATE_SUBFEATURE_LIMIT", "mate subfeature traversal exceeded guard")
        raw = value(feature, "GetNextFeature")
    raise VerifyError("MATE_FEATURE_LIMIT", "feature traversal exceeded guard")


def external_reference_count(model: Any, label: str) -> int:
    failures = []
    for name, args in (("ListExternalFileReferencesCount2", ()), ("ListExternalFileReferencesCount", (False,))):
        try:
            return int(value(model, name, *args))
        except Exception as exc:
            failures.append({"api": name, "exception": repr(exc)})
    raise VerifyError("EXTERNAL_REFERENCE_QUERY_FAIL", f"cannot prove external-reference count for {label}", {"failures": failures})


def expected_part_dimensions(key: str, authority: Mapping[str, Any]) -> List[float]:
    tokens = key.split("_")
    if len(tokens) < 4 or tokens[0] != "SOLAR" or len(tokens[1]) != 2 or tokens[-1] != "R2B":
        raise VerifyError("PART_KEY_FAIL", "R2B part key grammar differs", {"key": key})
    side, index = tokens[1][0], int(tokens[1][1])
    role = "_".join(tokens[2:-1])
    geometry = authority["candidate_geometry"]
    if role == "PANEL_STRUCTURE":
        x_span = float(geometry["panel_x_span_mm"][1]) - float(geometry["panel_x_span_mm"][0])
        edge = geometry["panel_structure_edge_contract"]
        if index == 1:
            main = [float(value_in) for value_in in edge["L1_main_plate_v_min_max_mm"]]
            relief = geometry["p1_root_structure_relief"]
            centroid = float(geometry["deployed_panel_centroid_abs_y_mm"][0])
            tab_left = [float(value_in) - centroid for value_in in relief["bridge_tabs_world_y_span_left_mm"]]
            main_side = main if side == "L" else [-main[1], -main[0]]
            tab_side = tab_left if side == "L" else [-tab_left[1], -tab_left[0]]
            span = max(main_side[1], tab_side[1]) - min(main_side[0], tab_side[0])
        elif index == 2:
            values = [float(value_in) for value_in in edge["L2_v_min_max_mm"]]
            span = values[1] - values[0]
        elif index == 3:
            values = [float(value_in) for value_in in edge["L3_v_min_max_mm"]]
            span = values[1] - values[0]
        else:
            raise VerifyError("PART_PANEL_INDEX_FAIL", "panel index is not 1..3", {"key": key})
        return sorted((x_span, span, float(geometry["panel_thickness_mm"])))
    fixed = {
        "DEPLOY_STOP_IF": (16.0, 10.0, 2.0),
        "STOW_PAD_IF": (20.0, 6.0, 3.0),
        "HARNESS_EXIT_IF": (8.0, 8.0, 4.0),
        "MASS_PLACEHOLDER_IF": (30.0, 12.0, 2.0),
        "OUTBOARD_HINGE_PIN_IF": (4.0, 4.0, 28.0),
        "INBOARD_HINGE_COLLAR_IF": (5.5, 5.5, 28.0),
    }
    if role not in fixed:
        raise VerifyError("PART_ROLE_FAIL", "unrecognized R2B part role", {"key": key, "role": role})
    return sorted(fixed[role])


def cold_part_bore_signature(model: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    part = wrap(model, "IPartDoc", types, pythoncom)
    candidates: List[Tuple[float, List[float]]] = []
    for raw_body in as_list(part.GetBodies2(0, False)):
        body = wrap(raw_body, "IBody2", types, pythoncom)
        for raw_face in as_list(value(body, "GetFaces")):
            face = wrap(raw_face, "IFace2", types, pythoncom)
            surface = wrap(value(face, "GetSurface"), "ISurface", types, pythoncom)
            if not bool(surface.IsCylinder()):
                continue
            params = [float(value_in) for value_in in as_list(value(surface, "CylinderParams"))]
            if (
                len(params) >= 7
                and abs(params[3]) < 1.0e-5
                and abs(params[4]) < 1.0e-5
                and abs(abs(params[5]) - 1.0) < 1.0e-5
                and abs(params[0] * 1000.0) <= float(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_brep"]["axis_point_tolerance_mm"])
                and abs(params[1] * 1000.0) <= float(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_brep"]["axis_point_tolerance_mm"])
                and abs(params[6] * 1000.0 - float(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_radius_mm"])) <= float(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_brep"]["radius_tolerance_mm"])
            ):
                candidates.append((float(value(face, "GetArea")) * 1.0e6, params))
    if len(candidates) != int(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_brep"]["candidate_count"]):
        raise VerifyError("FRESH_COLLAR_BORE_COUNT_FAIL", "cold-opened collar does not expose exactly one local-Z bore face", {"candidate_count": len(candidates)})
    area_mm2, params = candidates[0]
    actual_radius_mm = float(params[6]) * 1000.0
    actual_length_mm = area_mm2 / (2.0 * math.pi * actual_radius_mm)
    return validate_bore_brep_readback(
        {
            "local_axis": "+/-Z",
            "expected_radius_mm": float(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_radius_mm"]),
            "actual_radius_mm": actual_radius_mm,
            "expected_axial_length_mm": float(ANNULUS_NATIVE_FEATURE_CONTRACT["body_depth_mm"]),
            "actual_axial_length_mm": actual_length_mm,
            "area_mm2": area_mm2,
            "candidate_count": len(candidates),
            "cylinder_params": params,
        },
        "fresh cold collar bore",
    )


def verify_part(
    sw: Any,
    path: Path,
    key: str,
    expected_dimensions_mm: Sequence[float],
    build_row: Mapping[str, Any],
    types: Any,
    pythoncom: Any,
) -> Dict[str, Any]:
    model, opened = open_read_only(sw, path, SW_DOC_PART, types, pythoncom)
    title = str(value(model, "GetTitle"))
    try:
        part = wrap(model, "IPartDoc", types, pythoncom)
        bodies = as_list(part.GetBodies2(0, False))
        external_count = external_reference_count(model, path.name)
        auxiliary_count = int(value(model, "ListAuxiliaryExternalFileReferencesCount"))
        if len(bodies) != 1 or external_count != 0 or auxiliary_count != 0:
            raise VerifyError("PART_NATIVE_BODY_LINK_FAIL", "part is not one solid with zero external links", {"path": norm(path), "solid_body_count": len(bodies), "external_count": external_count, "auxiliary_count": auxiliary_count})
        body = wrap(bodies[0], "IBody2", types, pythoncom)
        box = [float(value_in) * 1000.0 for value_in in as_list(value(body, "GetBodyBox"))]
        if len(box) != 6 or not all(math.isfinite(value_in) for value_in in box):
            raise VerifyError("PART_BODY_BOX_FAIL", "part body box is invalid", {"path": norm(path), "box": box})
        actual_dimensions = sorted((box[3] - box[0], box[4] - box[1], box[5] - box[2]))
        if len(expected_dimensions_mm) != 3 or any(abs(actual - float(wanted)) > 0.12 for actual, wanted in zip(actual_dimensions, expected_dimensions_mm)):
            raise VerifyError("PART_DIMENSION_FAIL", "part B-rep dimensions differ from R2B authority/build contract", {"key": key, "path": norm(path), "actual_mm": actual_dimensions, "expected_mm": list(expected_dimensions_mm)})
        bore_result = None
        if key in COLLAR_KEYS:
            build_bore = validate_bore_brep_readback(build_row.get("bore_brep_readback_before_save"), f"build receipt {key} bore")
            cold_bore = cold_part_bore_signature(model, types, pythoncom)
            cross_errors = {
                "radius_mm": abs(float(cold_bore["actual_radius_mm"]) - float(build_bore["actual_radius_mm"])),
                "axial_length_mm": abs(float(cold_bore["actual_axial_length_mm"]) - float(build_bore["actual_axial_length_mm"])),
                "area_mm2": abs(float(cold_bore["area_mm2"]) - float(build_bore["area_mm2"])),
            }
            if (
                cross_errors["radius_mm"] > float(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_brep"]["radius_tolerance_mm"])
                or cross_errors["axial_length_mm"] > float(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_brep"]["axial_length_tolerance_mm"])
                or cross_errors["area_mm2"] > 2.0 * math.pi * float(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_radius_mm"]) * float(ANNULUS_NATIVE_FEATURE_CONTRACT["bore_brep"]["axial_length_tolerance_mm"])
            ):
                raise VerifyError("FRESH_COLLAR_BUILD_CROSSCHECK_FAIL", "fresh collar bore differs from its build-stage B-rep receipt", {"key": key, "build": build_bore, "fresh": cold_bore, "errors": cross_errors})
            bore_result = {
                "annulus_native_feature_contract": ANNULUS_NATIVE_FEATURE_CONTRACT,
                "build_receipt_bore_brep": build_bore,
                "fresh_cold_bore_brep": cold_bore,
                "build_to_fresh_errors": cross_errors,
                "verdict": "V5_SOLAR_R2B_A_COLLAR_UNIQUE_THROUGH_BORE_FRESH_PASS",
            }
        if bool(value(model, "GetSaveFlag")):
            raise VerifyError("PART_READ_DIRTY_FAIL", "part became dirty during read-only queries", {"path": norm(path)})
        return {"key": key, "target": file_fact(path), "open": opened, "solid_body_count": 1, "external_reference_count": 0, "auxiliary_reference_count": 0, "bounding_box_mm": box, "dimensions_mm": actual_dimensions, "expected_dimensions_mm": list(expected_dimensions_mm), "collar_bore_brep": bore_result, "save_flag_post": False, "verdict": "V5_SOLAR_R2B_A_FRESH_PART_READ_ONLY_PASS"}
    finally:
        sw.CloseDoc(title)


def verify_module(sw: Any, key: str, contract: Mapping[str, Any], authorized: Set[Path], types: Any, pythoncom: Any) -> Dict[str, Any]:
    path = Path(contract["path"])
    model, opened = open_read_only(sw, path, SW_DOC_ASSEMBLY, types, pythoncom)
    title = str(value(model, "GetTitle"))
    try:
        names = [str(name) for name in as_list(value(model, "GetConfigurationNames"))]
        if len(names) != 1 or names[0] not in {"Default", "默认"}:
            raise VerifyError("MODULE_CONFIG_FAIL", "rigid module must contain only the locale-default configuration", {"module": key, "actual": names})
        top = component_ledger(model, True, types, pythoncom)
        recursive = component_ledger(model, False, types, pythoncom)
        actual_paths = {Path(row["path"]).resolve() for row in recursive}
        if len(top) != int(contract["child_count"]) or len(recursive) != len(top) or actual_paths != set(contract["references"]) or not actual_paths.issubset(authorized):
            raise VerifyError("MODULE_REFERENCE_SET_FAIL", "module top/nested reference set differs", {"module": key, "top_count": len(top), "recursive_count": len(recursive), "expected_count": contract["child_count"]})
        if sum(1 for row in top if row["fixed"]) != 1 or any(row["suppression"] != SW_COMPONENT_RESOLVED for row in top):
            raise VerifyError("MODULE_COMPONENT_STATE_FAIL", "module needs one fixed panel and all children resolved", {"module": key, "components": top})
        if any(not row["fixed"] and row["constrained_status"] != SW_FULLY_CONSTRAINED for row in top):
            raise VerifyError("MODULE_RIGID_CONSTRAINT_FAIL", "non-fixed module child is not fully constrained", {"module": key, "components": top})
        mates = mate_ledger(model, types, pythoncom)
        if len(mates) != len(top) - 1 or Counter(row["mate_type"] for row in mates) != Counter({SW_MATE_LOCK: len(top) - 1}):
            raise VerifyError("MODULE_LOCK_MATE_FAIL", "module internal mate set is not all lock mates", {"module": key, "mates": mates})
        if bool(value(model, "GetSaveFlag")):
            raise VerifyError("MODULE_READ_DIRTY_FAIL", "module became dirty during read-only queries", {"module": key})
        return {"module": key, "target": file_fact(path), "open": opened, "configuration_names": names, "sole_configuration": names[0], "top_components": top, "recursive_reference_count": len(recursive), "mate_ledger": mates, "save_flag_post": False, "verdict": "V5_SOLAR_R2B_A_FRESH_MODULE_DEFAULT_RIGID_PASS"}
    finally:
        sw.CloseDoc(title)


def validate_side_mates(side: str, mates: Sequence[Mapping[str, Any]], authorized: Set[Path]) -> Dict[str, Any]:
    expected_names = {f"R2B_{side}_ROOT_RETAINER_CONCENTRIC", f"R2B_{side}_ROOT_RETAINER_COINCIDENT"}
    for joint in ("ROOT", "H12", "H23"):
        expected_names.update({f"R2B_{side}_{joint}_CONCENTRIC", f"R2B_{side}_{joint}_COINCIDENT", f"R2B_{side}_{joint}_LIMIT_ANGLE_0_90"})
    types = Counter(int(row["mate_type"]) for row in mates)
    if len(mates) != 11 or {str(row["feature_name"]) for row in mates} != expected_names or types != Counter({SW_MATE_CONCENTRIC: 4, SW_MATE_COINCIDENT: 4, SW_MATE_ANGLE: 3}):
        raise VerifyError("SIDE_MATE_SET_FAIL", "side native mate set differs from 4 concentric + 4 coincident + 3 angle", {"side": side, "type_counts": dict(types), "names": [row["feature_name"] for row in mates]})
    angles = []
    branch_readbacks = []
    for row in mates:
        if any(Path(path).resolve() not in authorized for path in row["component_paths"]):
            raise VerifyError("SIDE_MATE_REFERENCE_FAIL", "side mate endpoint escapes authorized nested set", {"side": side, "mate": row})
        if int(row["mate_type"]) == SW_MATE_ANGLE:
            name = str(row["feature_name"])
            matching_joints = [joint for joint in ("ROOT", "H12", "H23") if name == f"R2B_{side}_{joint}_LIMIT_ANGLE_0_90"]
            if len(matching_joints) != 1:
                raise VerifyError("SIDE_ANGLE_BRANCH_ID_FAIL", "angle mate name does not resolve one frozen joint", {"side": side, "name": name})
            joint = matching_joints[0]
            branch_readbacks.append(validate_angle_branch_readback(row, side, joint, f"fresh side {side} {joint}"))
            definition = row.get("advanced_limit_angle")
            if not isinstance(definition, dict) or definition.get("advanced") is not True or abs(float(definition.get("minimum_angle_rad", math.inf)) - ANGLE_LOWER_RAD) > ANGLE_TOL_RAD or abs(float(definition.get("maximum_angle_rad", -math.inf)) - ANGLE_UPPER_RAD) > ANGLE_TOL_RAD:
                raise VerifyError("SIDE_LIMIT_ANGLE_FAIL", "angle mate is not advanced 0..90 degrees", {"side": side, "mate": row})
            angle = float(definition.get("angle_rad", math.nan))
            if not math.isfinite(angle) or angle < -ANGLE_TOL_RAD or angle > ANGLE_UPPER_RAD + ANGLE_TOL_RAD:
                raise VerifyError("SIDE_LIMIT_ANGLE_VALUE_FAIL", "saved angle is outside 0..90 degrees", {"side": side, "mate": row})
            angles.append(row)
    if [row["joint"] for row in sorted(branch_readbacks, key=lambda item: ("ROOT", "H12", "H23").index(item["joint"]))] != ["ROOT", "H12", "H23"]:
        raise VerifyError("SIDE_ANGLE_BRANCH_SET_FAIL", "fresh side does not contain all three frozen angle branches", {"side": side, "readbacks": branch_readbacks})
    return {
        "mate_count": 11,
        "type_counts": {str(key): value_in for key, value_in in sorted(types.items())},
        "advanced_limit_angles": angles,
        "angle_branch_contract": {"side": side, "selection_order": "PARENT_THEN_CHILD", "alignment": SW_ALIGN_ALIGNED, "hinges": dict(FLIP_CONTRACT["sides"][side])},
        "angle_branch_readbacks": branch_readbacks,
    }


def verify_side(sw: Any, side: str, contract: Mapping[str, Any], modules: Mapping[str, Mapping[str, Any]], module_default_configs: Mapping[str, str], oracle: Mapping[str, Any], signed_fk: Mapping[str, Any], authorized: Set[Path], types: Any, pythoncom: Any) -> Dict[str, Any]:
    path = Path(contract["path"])
    model, opened = open_read_only(sw, path, SW_DOC_ASSEMBLY, types, pythoncom)
    title = str(value(model, "GetTitle"))
    try:
        names = [str(name) for name in as_list(value(model, "GetConfigurationNames"))]
        if set(names) != set(CONFIGS) or len(names) != 7:
            raise VerifyError("SIDE_CONFIG_SET_FAIL", "side assembly configuration set is not exactly seven", {"side": side, "actual": names})
        state_rows: List[Dict[str, Any]] = []
        actual_transforms: Dict[str, Dict[str, List[float]]] = {}
        for state in CONFIGS:
            if not bool(model.ShowConfiguration2(state)):
                raise VerifyError("SIDE_CONFIG_ACTIVATE_FAIL", "cannot activate saved side configuration", {"side": side, "state": state})
            top = component_ledger(model, True, types, pythoncom)
            recursive = component_ledger(model, False, types, pythoncom)
            recursive_paths = {Path(row["path"]).resolve() for row in recursive}
            if recursive_paths != set(contract["references"]) or not recursive_paths.issubset(authorized):
                raise VerifyError("SIDE_NESTED_REFERENCE_FAIL", "saved nested reference set differs", {"side": side, "state": state, "actual_count": len(recursive_paths), "expected_count": len(contract["references"])})
            expected_module_keys = {f"{side}{index}" for index in (1, 2, 3)}
            # Resolve by authoritative path rather than occurrence display name.
            module_rows = {}
            for key in expected_module_keys:
                matches = [row for row in top if Path(row["path"]).resolve() == Path(modules[key]["path"]).resolve()]
                if len(matches) != 1:
                    raise VerifyError("SIDE_MODULE_OCCURRENCE_FAIL", "side lacks one exact top-level module occurrence", {"side": side, "state": state, "module": key, "matches": len(matches)})
                module_rows[key] = matches[0]
            actual_top_paths = {Path(row["path"]).resolve() for row in top}
            if len(top) != 13 or actual_top_paths != set(contract["top_paths"]):
                raise VerifyError("SIDE_TOP_COMPONENT_COUNT_FAIL", "side must have 3 modules + 6 root-core/shared + 4 root-envelope occurrences", {"side": side, "state": state, "count": len(top), "expected_paths": sorted(norm(path) for path in contract["top_paths"]), "actual_paths": sorted(norm(path) for path in actual_top_paths)})
            for key, row in module_rows.items():
                if row["suppression"] != SW_COMPONENT_RESOLVED or row["solving"] != SW_COMPONENT_RIGID or row["referenced_configuration"] != module_default_configs[key]:
                    raise VerifyError("SIDE_MODULE_RIGID_SOLVING_FAIL", "module occurrence is not resolved/rigid/Default", {"side": side, "state": state, "module": key, "row": row})
            transforms = {key: list(row["transform16"]) for key, row in module_rows.items()}
            build_expected = contract["configs"][state]["transforms"]
            oracle_expected = oracle[side][state]
            signed_expected = signed_fk[side][state]
            comparisons = []
            for key in sorted(expected_module_keys):
                comparisons.append({
                    "module": key,
                    "build_receipt_error": assert_transform(transforms[key], build_expected[key], f"{side}/{state}/{key}/build"),
                    "static_oracle_error": assert_transform(transforms[key], oracle_expected[key], f"{side}/{state}/{key}/oracle"),
                    "independent_signed_fk_error": assert_transform(transforms[key], signed_expected[key], f"{side}/{state}/{key}/independent_signed_fk"),
                    "actual_signed_rx_deg": signed_rx_deg(transforms[key]),
                    "expected_signed_rx_deg": signed_rx_deg(signed_expected[key]),
                })
                if state == "SOLAR_DEPLOYED_NOMINAL":
                    assert_transform(transforms[key], [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0], f"{side}/nominal/{key}/identity")
            interpanel_rows: List[Dict[str, Any]] = []
            for joint, upstream_index, downstream_index in (("H12", 1, 2), ("H23", 2, 3)):
                upstream_key, downstream_key = f"{side}{upstream_index}", f"{side}{downstream_index}"
                nominal_y = float(INTERPANEL_NESTED_BREP_FRAME_CONTRACT["nominal_world"]["hinge_y_mm"][side][joint])
                nominal_axis_point = [-75.0, nominal_y, 0.0]
                oracle_upstream_point = transform_point_mm(oracle_expected[upstream_key], nominal_axis_point)
                oracle_downstream_point = transform_point_mm(oracle_expected[downstream_key], nominal_axis_point)
                oracle_point_delta = vector_distance(oracle_upstream_point, oracle_downstream_point)
                if oracle_point_delta > float(INTERPANEL_NESTED_BREP_FRAME_CONTRACT["tolerances"]["world_point_mm"]):
                    raise VerifyError("FRESH_INTERPANEL_ORACLE_CONTINUITY_FAIL", "static oracle transforms do not map the shared authored hinge point to one state point", {"side": side, "state": state, "joint": joint, "upstream_world_mm": oracle_upstream_point, "downstream_world_mm": oracle_downstream_point, "delta_mm": oracle_point_delta})
                pin_name = f"SOLAR_{side}{upstream_index}_OUTBOARD_HINGE_PIN_IF_R2B.SLDPRT"
                collar_name = f"SOLAR_{side}{downstream_index}_INBOARD_HINGE_COLLAR_IF_R2B.SLDPRT"
                pin_paths = [path_in for path_in in authorized if path_in.name == pin_name]
                collar_paths = [path_in for path_in in authorized if path_in.name == collar_name]
                if len(pin_paths) != 1 or len(collar_paths) != 1:
                    raise VerifyError("FRESH_INTERPANEL_PART_PATH_FAIL", "authorized set lacks one exact pin/collar path", {"side": side, "joint": joint, "pin_count": len(pin_paths), "collar_count": len(collar_paths)})
                pair = cold_interpanel_pair(model, side, state, joint, pin_paths[0], collar_paths[0], oracle_upstream_point, types, pythoncom)
                pair["nominal_authored_axis_point_mm"] = nominal_axis_point
                pair["oracle_upstream_world_mm"] = oracle_upstream_point
                pair["oracle_downstream_world_mm"] = oracle_downstream_point
                pair["oracle_world_point_delta_mm"] = oracle_point_delta
                interpanel_rows.append(pair)
            mates = mate_ledger(model, types, pythoncom)
            mate_contract = validate_side_mates(side, mates, authorized)
            logical_angles = [float(item) for item in contract["configs"][state]["angles_deg"]]
            cold_angle_dimensions = []
            for index, joint in enumerate(("ROOT", "H12", "H23")):
                cold_angle_dimensions.append(angle_dimension_readback(
                    model,
                    f"R2B_{side}_{joint}_LIMIT_ANGLE_0_90",
                    state,
                    math.radians(90.0 - logical_angles[index]),
                    types,
                    pythoncom,
                ))
            if bool(value(model, "GetSaveFlag")):
                raise VerifyError("SIDE_READ_DIRTY_FAIL", "side became dirty during read-only state queries", {"side": side, "state": state})
            actual_transforms[state] = transforms
            state_rows.append({"state": state, "angles_deg": logical_angles, "signed_fold_direction": dict(SIGNED_FOLD_DIRECTION[side]), "cold_angle_dimension_readback": cold_angle_dimensions, "module_occurrences": module_rows, "transform_comparisons": comparisons, "interpanel_nested_brep_frame_contract": INTERPANEL_NESTED_BREP_FRAME_CONTRACT, "interpanel_cold_world_axis_readback": interpanel_rows, "nested_reference_count": len(recursive), "mate_contract": mate_contract, "save_flag": False, "verdict": "V5_SOLAR_R2B_A_FRESH_SIDE_STATE_PASS"})
        return {"side": side, "target": file_fact(path), "open": opened, "configuration_names": names, "root_lug_bore_build_receipt_validation": contract["root_lug_bore_validation"], "interpanel_build_receipt_validations": contract["interpanel_hinge_validations"], "states": state_rows, "actual_transforms": actual_transforms, "verdict": "V5_SOLAR_R2B_A_FRESH_SIDE_READ_ONLY_PASS"}
    finally:
        sw.CloseDoc(title)


def mirror_audit(side_results: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    rows = []
    for left_state in CONFIGS:
        right_state = {"SOLAR_LEFT_FAIL": "SOLAR_RIGHT_FAIL", "SOLAR_RIGHT_FAIL": "SOLAR_LEFT_FAIL"}.get(left_state, left_state)
        for index in (1, 2, 3):
            left_key, right_key = f"L{index}", f"R{index}"
            left = side_results["L"]["actual_transforms"][left_state][left_key]
            right = side_results["R"]["actual_transforms"][right_state][right_key]
            error = assert_transform(right, mirror_transform(left), f"mirror/{left_state}/{right_state}/{index}")
            rows.append({"left_state": left_state, "right_state": right_state, "panel_index": index, "relation": "RIGHT=M_XZ*T_LEFT*M_XZ_WITH_FAILURE_STATE_PAIRING", "error": error})
    return {"comparisons": rows, "comparison_count": 21, "verdict": "V5_SOLAR_R2B_A_XZ_MIRROR_TRANSFORM_PASS"}


def close_only_authorized_documents(sw: Any, authorized: Set[Path]) -> Dict[str, Any]:
    closed: List[str] = []
    unknown: List[Dict[str, str]] = []
    for _ in range(100):
        documents = as_list(value(sw, "GetDocuments"))
        if not documents:
            break
        progress, unknown = False, []
        for raw in documents:
            title, raw_path = str(value(raw, "GetTitle")), str(value(raw, "GetPathName"))
            path = Path(raw_path).resolve() if raw_path else None
            if path is not None and path in authorized:
                sw.CloseDoc(title)
                closed.append(norm(path))
                progress = True
            else:
                unknown.append({"title": title, "path": norm(path) if path is not None else ""})
        if unknown or not progress:
            break
    remaining = int(value(sw, "GetDocumentCount"))
    if unknown or remaining != 0 or value(sw, "ActiveDoc") is not None:
        raise VerifyError("FRESH_CLEANUP_FAIL", "verifier did not close to empty without touching unknown docs", {"remaining": remaining, "unknown": unknown})
    return {"closed_owned_read_only_documents": sorted(set(closed)), "document_count_after": 0, "active_doc_is_null_after": True}


def verify_attempt(attempt_root: Path, receipt_path: Path, handoff_path: Path, expected_pid: int) -> Dict[str, Any]:
    source = source_policy_audit()
    frozen = frozen_chain_audit()
    if not source["verdict"].endswith("_PASS") or not frozen["verdict"].endswith("_PASS"):
        raise VerifyError("STATIC_GATE_HOLD", "source policy or frozen chain failed", {"source": source, "frozen": frozen})
    transaction = transaction_static_audit(attempt_root, receipt_path, handoff_path)
    if not transaction["execution_authorized"]:
        raise VerifyError("TRANSACTION_TERMINAL_HOLD", "attempt already has terminal fresh-verification evidence", transaction)
    contract = validate_build_receipt(attempt_root, receipt_path, handoff_path)
    protected_pre, cad_pre = protected_snapshot(contract, receipt_path, handoff_path), cad_snapshot(contract)
    authorized = set(contract["artifacts"]) | set().union(*(row["references"] for row in contract["modules"].values()), *(row["references"] for row in contract["sides"].values()))
    result: Dict[str, Any] = {
        "schema": "F3R2_V5_SOLAR_R2B_A_FRESH_VERIFY_RECEIPT_V1",
        "timestamp_start_utc": utc_now(),
        "attempt_root": norm(attempt_root),
        "attempt_id": contract["attempt_id"],
        "storage_id": contract["storage_id"],
        "verifier": file_fact(Path(__file__)),
        "source_policy_audit": source,
        "frozen_chain_audit": frozen,
        "transaction_static_audit": transaction,
        "build_receipt": file_fact(receipt_path),
        "handoff": file_fact(handoff_path),
        "release_provenance_lineage": {
            "microfixture": contract["microfixture_lineage"],
            "production_root_flip_authorization": contract["production_root_flip_authorization"],
            "angle_branch_evidence": contract["angle_branch_evidence"],
        },
        "protected_pre": protected_pre,
        "cad_hash_pre": cad_pre,
        "parts": [],
        "modules": [],
        "sides": [],
        "cad_write_calls": 0,
        "read_only": True,
    }
    sw = types = pythoncom = None
    try:
        sw, types, pythoncom, session = attach_fresh_session(expected_pid, contract["session"])
        result["solidworks_verify_session"] = session
        authority = load_json(STATE_AUTHORITY)
        for path in sorted(contract["parts"], key=norm):
            build_row = contract["parts"][path]["row"]
            key = str(build_row.get("key", ""))
            result["parts"].append(verify_part(sw, path, key, expected_part_dimensions(key, authority), build_row, types, pythoncom))
            close_only_authorized_documents(sw, authorized)
        collar_results = [row for row in result["parts"] if row.get("key") in COLLAR_KEYS and row.get("collar_bore_brep") is not None]
        if len(collar_results) != int(ANNULUS_NATIVE_FEATURE_CONTRACT["production_part_count"]) or {row["key"] for row in collar_results} != set(COLLAR_KEYS):
            raise VerifyError("FRESH_COLLAR_RESULT_SET_FAIL", "fresh part verification did not independently prove all four collar bores", {"actual": [row.get("key") for row in collar_results]})
        result["annulus_native_feature_contract"] = ANNULUS_NATIVE_FEATURE_CONTRACT
        result["collar_unique_through_bore_count"] = len(collar_results)
        module_default_configs: Dict[str, str] = {}
        for key in sorted(contract["modules"]):
            module_result = verify_module(sw, key, contract["modules"][key], authorized, types, pythoncom)
            result["modules"].append(module_result)
            module_default_configs[key] = str(module_result["sole_configuration"])
            close_only_authorized_documents(sw, authorized)
        oracle = oracle_expected_transforms()
        signed_fk = independent_signed_fk_transforms(authority)
        side_results: Dict[str, Dict[str, Any]] = {}
        for side in ("L", "R"):
            side_result = verify_side(sw, side, contract["sides"][side], contract["modules"], module_default_configs, oracle, signed_fk, authorized, types, pythoncom)
            side_results[side] = side_result
            result["sides"].append(side_result)
            close_only_authorized_documents(sw, authorized)
        result["mirror_audit"] = mirror_audit(side_results)
        cleanup = close_only_authorized_documents(sw, authorized)
        protected_post, cad_post = protected_snapshot(contract, receipt_path, handoff_path), cad_snapshot(contract)
        if protected_pre != protected_post or cad_pre != cad_post:
            raise VerifyError("HASH_PRE_POST_FAIL", "protected or CAD bytes changed during read-only verification", {"protected_equal": protected_pre == protected_post, "cad_equal": cad_pre == cad_post})
        result.update({
            "timestamp_end_utc": utc_now(),
            "cleanup": cleanup,
            "protected_post": protected_post,
            "cad_hash_post": cad_post,
            "all_46_cad_hash_pre_equals_post": True,
            "protected_hash_pre_equals_post": True,
            "fresh_process": True,
            "different_pid_and_process_create_time": True,
            "module_contract": "6x DEFAULT_ONLY + INTERNAL_LOCK_RIGID + PARENT_SOLVING_RIGID",
            "side_contract": "2x SEVEN_STATES + 3_MODULE_TRANSFORMS_EACH + 3_ADVANCED_LIMIT_ANGLE_0..90",
            "v2_signed_fk_aggregation": {
                "side_state_count": 14,
                "exact_flip_readback_cell_count": 42,
                "independent_signed_fk_transform_count": 42,
                "flip_matrix": PRODUCTION_FLIP_SIDES,
                "signed_fold_direction": SIGNED_FOLD_DIRECTION,
                "verdict": "V5_SOLAR_R2B_A_V2_2X7_EXACT_FLIP_AND_SIGNED_FK_PASS",
            },
            "nested_references_verified": True,
            "configuration_readback_mode": "SHOW_SAVED_CONFIGURATION_READ_ONLY_NO_REBUILD_NO_DRIVER",
            "promotion_authorized": True,
            "verdict": "V5_SOLAR_R2B_A_NEW_PID_READ_ONLY_ZERO_MUTATION_PASS",
        })
        pass_path = attempt_root / PASS_RELATIVE
        write_json_once(pass_path, result, attempt_root)
        return {"receipt": file_fact(pass_path), "payload": result}
    finally:
        if sw is not None:
            try:
                close_only_authorized_documents(sw, authorized)
            except Exception:
                pass
        if pythoncom is not None:
            pythoncom.CoUninitialize()


def failure_path(attempt_root: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return attempt_root / "evidence" / f"F3R2_V5_SOLAR_R2B_A_FRESH_VERIFY_FAIL_{stamp}.json"


def run_verify(args: argparse.Namespace) -> int:
    attempt_root: Optional[Path] = None
    receipt_path: Optional[Path] = None
    handoff_path: Optional[Path] = None
    attempt_id: Optional[str] = None
    storage_id: Optional[str] = None
    try:
        attempt_root = assert_attempt_root(Path(args.attempt_root))
        physical_identity = root_storage_identity(attempt_root)
        attempt_id, storage_id = physical_identity["attempt_id"], physical_identity["storage_id"]
        receipt_path = assert_scoped_file(Path(args.build_receipt), attempt_root, "build receipt")
        handoff_path = assert_scoped_file(Path(args.handoff), attempt_root, "fresh verifier handoff")
        result = verify_attempt(attempt_root, receipt_path, handoff_path, int(args.expected_pid))
        print(json.dumps({"verdict": result["payload"]["verdict"], "attempt_id": result["payload"]["attempt_id"], "storage_id": result["payload"]["storage_id"], "receipt": result["receipt"]}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        failure = {
            "schema": "F3R2_V5_SOLAR_R2B_A_FRESH_VERIFY_FAILURE_V1",
            "timestamp_utc": utc_now(),
            "attempt_root": norm(attempt_root) if attempt_root is not None else str(args.attempt_root),
            "attempt_id": attempt_id,
            "storage_id": storage_id,
            "build_receipt": file_fact(receipt_path) if receipt_path is not None and receipt_path.is_file() else str(args.build_receipt),
            "handoff": file_fact(handoff_path) if handoff_path is not None and handoff_path.is_file() else str(args.handoff),
            "expected_pid": int(args.expected_pid),
            "verifier": file_fact(Path(__file__)),
            "error_code": getattr(exc, "code", "FRESH_VERIFY_UNEXPECTED_FAIL"),
            "error": str(exc),
            "detail": getattr(exc, "detail", {}),
            "traceback": traceback.format_exc(),
            "cad_write_calls": 0,
            "promotion_authorized": False,
            "verdict": "V5_SOLAR_R2B_A_NEW_PID_READ_ONLY_ZERO_MUTATION_FAIL",
        }
        if attempt_root is not None:
            try:
                target = failure_path(attempt_root)
                write_json_once(target, failure, attempt_root)
                failure["failure_receipt"] = file_fact(target)
            except Exception as write_exc:
                failure["failure_receipt_write_error"] = repr(write_exc)
        print(json.dumps(failure, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3


def run_audit(args: argparse.Namespace) -> int:
    source, frozen = source_policy_audit(), frozen_chain_audit()
    result: Dict[str, Any] = {
        "schema": "F3R2_V5_SOLAR_R2B_A_FRESH_VERIFY_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "source_policy": source,
        "frozen_chain": frozen,
        "attempts_root": norm(ATTEMPTS_ROOT),
        "attempt_id": None,
        "storage_id": None,
        "solidworks_touched": False,
    }
    ok = source["verdict"].endswith("_PASS") and frozen["verdict"].endswith("_PASS")
    supplied = [bool(args.attempt_root), bool(args.build_receipt), bool(args.handoff)]
    if any(supplied) and not all(supplied):
        result["transaction_error"] = "--attempt-root, --build-receipt, and --handoff must be supplied together"
        ok = False
    elif all(supplied):
        try:
            attempt_root = assert_attempt_root(Path(args.attempt_root))
            physical_identity = root_storage_identity(attempt_root)
            result.update(physical_identity)
            receipt_path = assert_scoped_file(Path(args.build_receipt), attempt_root, "build receipt")
            handoff_path = assert_scoped_file(Path(args.handoff), attempt_root, "fresh verifier handoff")
            result["transaction"] = transaction_static_audit(attempt_root, receipt_path, handoff_path)
            result["attempt_id"] = result["transaction"]["attempt_id"]
            result["storage_id"] = result["transaction"]["storage_id"]
            ok = ok and bool(result["transaction"]["execution_authorized"])
        except Exception as exc:
            result["transaction_error"] = {"code": getattr(exc, "code", "STATIC_AUDIT_FAIL"), "error": str(exc), "detail": getattr(exc, "detail", {})}
            ok = False
    result["execution_authorized"] = ok
    result["verdict"] = "V5_SOLAR_R2B_A_FRESH_VERIFY_STATIC_AUDIT_PASS" if ok else "V5_SOLAR_R2B_A_FRESH_VERIFY_STATIC_AUDIT_HOLD"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 2


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="source/filesystem-only audit; never touches SOLIDWORKS")
    audit.add_argument("--attempt-root")
    audit.add_argument("--build-receipt")
    audit.add_argument("--handoff")
    verify = commands.add_parser("verify", help="attach to one explicit fresh PID and verify read-only")
    verify.add_argument("--attempt-root", required=True)
    verify.add_argument("--build-receipt", required=True)
    verify.add_argument("--handoff", required=True)
    verify.add_argument("--expected-pid", required=True, type=int)
    return root


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "audit":
        return run_audit(args)
    return run_verify(args)


if __name__ == "__main__":
    raise SystemExit(main())
