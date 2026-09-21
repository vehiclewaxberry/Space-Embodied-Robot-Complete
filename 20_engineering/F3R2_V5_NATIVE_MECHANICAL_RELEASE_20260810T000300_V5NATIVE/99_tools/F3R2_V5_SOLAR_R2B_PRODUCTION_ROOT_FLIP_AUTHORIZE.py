#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure-file, write-once authorization for the R2B production ROOT flip patch.

This program never imports a SOLIDWORKS automation module and never opens or
mutates CAD.  It bridges the preserved P5A5 failure lineage to the independent
real-production ROOT branch matrix, re-evaluates every matrix case, and may
write exactly one authorization JSON in ``13_validation``.

The authorization is deliberately narrow: only LEFT ROOT True->False and
RIGHT ROOT False->True are authorized.  H12/H23, geometry, topology, state
authority, the native dimension protocol, and every release claim remain
unchanged or pending fresh verification.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


sys.dont_write_bytecode = True

RUN_ROOT = Path(
    r"F:\China Graduate Future Flight Vehicle Innovation Competition"
    r"\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
)
TOOLS = RUN_ROOT / "99_tools"
VALIDATION = RUN_ROOT / "13_validation"
P5_ROOT = VALIDATION / "solar_r2_attempts/20260813T164200Z_P5A5"
P5_FAILURE = P5_ROOT / "evidence/BUILD_FAILURE_20260813T084845.277077Z.json"
PRE_PATCH_BUILDER = TOOLS / "F3R2_V5_NATIVE_SOLAR_ARRAY_R2B_BUILD_STAGE_ATTACH_ONLY.py"
PROBE_SOURCE = TOOLS / "F3R2_V5_DIAG_SOLAR_R2B_PRODUCTION_ROOT_BRANCH_PROTOCOL_ATTACH_ONLY.py"
PROBE_RESULT = (
    TOOLS
    / "probe_logs/V5_SOLAR_R2B_PRODUCTION_ROOT_BRANCH_20260813T_ROOTPROTOCOL_G1/RESULT.json"
)
STATE_AUTHORITY = RUN_ROOT / "00_authority/V5_SOLAR_STATE_AUTHORITY_R2B.json"
STATIC_ORACLE = VALIDATION / "V5_SOLAR_R2B_STATIC_KINEMATIC_ORACLE_20260812T181333.205056Z.json"
MICRO_SOURCE = TOOLS / "F3R2_V5_DIAG_SOLAR_R2B_MODULE_CHAIN_ATTACH_ONLY.py"
LOOP1B_SOURCE = TOOLS / "F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY.py"
AUTHORIZATION_RECEIPT = VALIDATION / "V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_V1.json"

EXPECTED_SHA256 = {
    PRE_PATCH_BUILDER: "A91EC2A29F28F5BA64FD552F75AB6204BA32318604DEB3569D4ACA4C61C05D43",
    P5_FAILURE: "745F069350F1E04158C9D3479AEDDBAD1E55BB258CE07ED97FD061DBEE249A3E",
    PROBE_SOURCE: "FBF3F0D53E3078D9E5A5B2CB0060A4EDBCC8BD7F01E6DE7B3C19F9A4ABD3F1D2",
    PROBE_RESULT: "18393CAC2423032AFF309361E37D5CE3612AA086C9EA5FD16D991EC2DF593DA0",
    STATE_AUTHORITY: "BA639C6BF4F0875B6FD9AFFF2E6CA7A5AA3BA1AF77C6BD5FEC07A8EB62D8E6D8",
    STATIC_ORACLE: "F4E5E0CD5A8559991B60826C6221294948CD07889836500D81527AE0982196F6",
    MICRO_SOURCE: "A61A531498ACC415D689F56794776787A57F8E6C0D6A0F2F0F9516938460CF6E",
    LOOP1B_SOURCE: "32BC06FC6A1EFCD6426FE4608D03EABCBD2902CBA228E95B2AD7A91B4E0F283F",
}

PRE_PATCH_CONTRACT_SHA256 = "891052B9291FCE299DCEBB7B539D8056525A1F242E8BD5B7417EF347138ABC44"
P5_ATTEMPT_ID = "V5_SOLAR_R2B_BUILD_20260813T164200Z_P5A5"
P5_STORAGE_ID = "20260813T164200Z_P5A5"
P5_L1_SHA256 = "7D27D1E5EA5AC8EA9F27B1FDC4494CE6AE87AD3A14380EF736494DDFD967CDBA"
P5_R1_SHA256 = "61743934F74F3D0A2C271DFF98EB4535401A9D00D62D169F44CCC568FD2486F0"

ROOT_FILES: Dict[str, Dict[str, Path]] = {
    "L": {
        "module": P5_ROOT / "cad/modules/SOLAR_PANEL_MODULE_L1_R2B.SLDASM",
        "clevis": RUN_ROOT / "01_native_parts/wing_root/LEFT_WING_ROOT_THREE_WEB_CLEVIS.SLDPRT",
        "pin": RUN_ROOT / "01_native_parts/wing_root/loop1b/LEFT_HINGE_PIN_V22_ISOLATED.SLDPRT",
        "u_lug": RUN_ROOT / "01_native_parts/wing_root/loop1b/LEFT_PANEL_SIDE_U_LUG_NATIVE.SLDPRT",
    },
    "R": {
        "module": P5_ROOT / "cad/modules/SOLAR_PANEL_MODULE_R1_R2B.SLDASM",
        "clevis": RUN_ROOT / "01_native_parts/wing_root/RIGHT_WING_ROOT_THREE_WEB_CLEVIS.SLDPRT",
        "pin": RUN_ROOT / "01_native_parts/wing_root/loop1b/RIGHT_HINGE_PIN_V22_ISOLATED.SLDPRT",
        "u_lug": RUN_ROOT / "01_native_parts/wing_root/loop1b/RIGHT_PANEL_SIDE_U_LUG_NATIVE.SLDPRT",
    },
}
SPACER = RUN_ROOT / "01_native_parts/wing_root/WING_HINGE_AXIAL_SPACER.SLDPRT"

EXPECTED_PROBE_INPUT_SHA256: Dict[Path, str] = {
    ROOT_FILES["L"]["module"]: P5_L1_SHA256,
    ROOT_FILES["R"]["module"]: P5_R1_SHA256,
    ROOT_FILES["L"]["clevis"]: "AC60E3A07C84F21CF6E20D01533333345713EE3B28F9966BAAC4B452A4FCE673",
    ROOT_FILES["R"]["clevis"]: "2D8121989230723A9D29C43672D8534D719D2AF7A64C110D0B0D16EAA31B1894",
    ROOT_FILES["L"]["pin"]: "97F6BE610F93605B098590A0C0CD157BE3C14A620B58976AA8A74FF00368733F",
    ROOT_FILES["R"]["pin"]: "82E009F39F2320F53BC8651F7F4282898B0D2ABB4F62C8144A1EAC27B1014AC6",
    ROOT_FILES["L"]["u_lug"]: "5E8BDB76637B7F394560A95A938C3FF363DDAE88950E93266CFE66837ABCD749",
    ROOT_FILES["R"]["u_lug"]: "A5A86890E07990706D106170B99DA0E68A31103EA73BF7161497669BCA4C557B",
    SPACER: "821B9484AB4B7B11A59A0136EDD4C537D37C317AC45830A5C1252ECD0A31577D",
    MICRO_SOURCE: EXPECTED_SHA256[MICRO_SOURCE],
    LOOP1B_SOURCE: EXPECTED_SHA256[LOOP1B_SOURCE],
}

BEFORE_FLIP = {
    "L": {"ROOT": True, "H12": False, "H23": True},
    "R": {"ROOT": False, "H12": True, "H23": False},
}
AFTER_FLIP = {
    "L": {"ROOT": False, "H12": False, "H23": True},
    "R": {"ROOT": True, "H12": True, "H23": False},
}
ROOT_WINNER = {"L": False, "R": True}
BETAS_DEG = (1.0, 89.0, 90.0)
FLIPS = (False, True)
PROTOCOLS = ("FULL_TABLE_LIKE", "PER_STATE_SUPPRESS_BEFORE_DIMENSION")
TRANS_TOL_MM = 0.08
ROT_TOL_DEG = 0.15
ANGLE_TOL_RAD = 2.0e-9
ANGLE_TOL_DEG = 1.0e-3


class AuthorizationError(RuntimeError):
    def __init__(self, code: str, message: str, detail: Optional[Mapping[str, Any]] = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.detail = dict(detail or {})


def require(condition: bool, code: str, message: str, detail: Optional[Mapping[str, Any]] = None) -> None:
    if not condition:
        raise AuthorizationError(code, message, detail)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def norm(path: Path) -> str:
    return path.resolve().as_posix()


def is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def file_fact(path: Path) -> Dict[str, Any]:
    require(path.is_file(), "FILE_MISSING", "required file is absent", {"path": norm(path)})
    return {"path": norm(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def check_file(path: Path, expected_sha256: str) -> Dict[str, Any]:
    fact = file_fact(path)
    require(
        fact["sha256"] == expected_sha256,
        "FILE_HASH_FAIL",
        "required file differs from the frozen hash",
        {"path": fact["path"], "expected_sha256": expected_sha256, "actual_sha256": fact["sha256"]},
    )
    return fact


def load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise AuthorizationError("JSON_READ_FAIL", "cannot parse required JSON", {"path": norm(path), "exception": repr(exc)}) from exc
    require(isinstance(payload, dict), "JSON_ROOT_FAIL", "JSON root must be an object", {"path": norm(path)})
    return payload


def digest_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest().upper()


def as_float(value: Any, label: str) -> float:
    require(not isinstance(value, bool), "NUMERIC_BOOL_FAIL", "boolean supplied where a number is required", {"label": label})
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise AuthorizationError("NUMERIC_PARSE_FAIL", "value is not numeric", {"label": label, "value": value}) from exc
    require(math.isfinite(result), "NUMERIC_FINITE_FAIL", "value is not finite", {"label": label, "value": value})
    return result


def close(actual: float, expected: float, tolerance: float) -> bool:
    return abs(actual - expected) <= tolerance


def normalize_transform(value: Any, label: str) -> List[float]:
    require(isinstance(value, list) and len(value) == 16, "TRANSFORM_SHAPE_FAIL", "transform must contain 16 values", {"label": label})
    return [as_float(item, f"{label}[{index}]") for index, item in enumerate(value)]


def analytic_root_transform(side: str, beta_deg: float, mirror: bool = False) -> List[float]:
    require(side in ("L", "R"), "SIDE_FAIL", "side must be L or R", {"side": side})
    signed_beta = -beta_deg if side == "L" else beta_deg
    if mirror:
        signed_beta *= -1.0
    theta = math.radians(signed_beta)
    c, s = math.cos(theta), math.sin(theta)
    axis_y_m = (143.15 if side == "L" else -143.15) / 1000.0
    return [
        1.0, 0.0, 0.0,
        0.0, c, s,
        0.0, -s, c,
        0.0, axis_y_m - c * axis_y_m, -s * axis_y_m,
        1.0, 0.0, 0.0, 0.0,
    ]


def transform_error(actual: Sequence[float], expected: Sequence[float]) -> Dict[str, float]:
    translation = math.sqrt(sum((float(actual[index]) - float(expected[index])) ** 2 for index in (9, 10, 11))) * 1000.0
    actual_rotation = [[float(actual[column * 3 + row]) for column in range(3)] for row in range(3)]
    expected_rotation = [[float(expected[column * 3 + row]) for column in range(3)] for row in range(3)]
    relative = [
        [sum(expected_rotation[k][i] * actual_rotation[k][j] for k in range(3)) for j in range(3)]
        for i in range(3)
    ]
    cosine = max(-1.0, min(1.0, (sum(relative[index][index] for index in range(3)) - 1.0) / 2.0))
    return {"translation_mm": translation, "rotation_deg": math.degrees(math.acos(cosine))}


def require_transform(actual: Sequence[float], expected: Sequence[float], label: str) -> Dict[str, float]:
    error = transform_error(actual, expected)
    require(
        error["translation_mm"] <= TRANS_TOL_MM and error["rotation_deg"] <= ROT_TOL_DEG,
        "TRANSFORM_SEMANTICS_FAIL",
        "transform differs from the independently evaluated ROOT branch",
        {"label": label, "error": error, "actual": list(actual), "expected": list(expected)},
    )
    return error


def require_stored_error(stored: Any, computed: Mapping[str, float], label: str) -> None:
    require(isinstance(stored, dict), "ERROR_ROW_FAIL", "stored transform error is not an object", {"label": label})
    for key in ("translation_mm", "rotation_deg"):
        value = as_float(stored.get(key), f"{label}.{key}")
        require(close(value, float(computed[key]), 1.0e-9), "ERROR_RECOMPUTE_FAIL", "stored transform error differs from independent recomputation", {"label": label, "field": key, "stored": value, "computed": computed[key]})


def _literal(node: ast.AST, names: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        require(node.id in names, "AST_NAME_FAIL", "builder literal uses an unauthorized name", {"name": node.id})
        return names[node.id]
    if isinstance(node, ast.Dict):
        return {_literal(key, names): _literal(value, names) for key, value in zip(node.keys, node.values)}
    if isinstance(node, ast.List):
        return [_literal(item, names) for item in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_literal(item, names) for item in node.elts)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_literal(node.operand, names)
    raise AuthorizationError("AST_LITERAL_FAIL", "builder assignment is not a permitted literal expression", {"node": ast.dump(node, include_attributes=False)})


def builder_flip_literal() -> Dict[str, Any]:
    tree = ast.parse(PRE_PATCH_BUILDER.read_text(encoding="utf-8"), filename=str(PRE_PATCH_BUILDER))
    matches: List[ast.AST] = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "FLIP_CONTRACT" for target in node.targets):
                matches.append(node.value)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "FLIP_CONTRACT":
            matches.append(node.value)
    require(len(matches) == 1, "BUILDER_FLIP_AST_CARDINALITY_FAIL", "pre-patch builder must define FLIP_CONTRACT exactly once", {"count": len(matches)})
    value = _literal(matches[0], {"SW_ALIGN_ALIGNED": 0})
    require(isinstance(value, dict), "BUILDER_FLIP_AST_TYPE_FAIL", "FLIP_CONTRACT is not an object")
    return value


def expected_part_names() -> set[str]:
    names: set[str] = set()
    for side in ("L", "R"):
        for index in (1, 2, 3):
            prefix = f"SOLAR_{side}{index}_"
            for role in ("PANEL_STRUCTURE", "DEPLOY_STOP_IF", "STOW_PAD_IF", "HARNESS_EXIT_IF", "MASS_PLACEHOLDER_IF"):
                names.add(f"{prefix}{role}_R2B.SLDPRT")
            if index < 3:
                names.add(f"{prefix}OUTBOARD_HINGE_PIN_IF_R2B.SLDPRT")
            if index > 1:
                names.add(f"{prefix}INBOARD_HINGE_COLLAR_IF_R2B.SLDPRT")
    return names


def validate_saved_fact(row: Any, expected_parent: Path, expected_suffix: str, label: str) -> Dict[str, Any]:
    require(isinstance(row, dict), "SAVED_FACT_ROW_FAIL", "saved artifact fact is not an object", {"label": label})
    try:
        path = Path(str(row["path"])).resolve()
        expected_bytes = int(row["bytes"])
        expected_hash = str(row["sha256"]).upper()
    except Exception as exc:
        raise AuthorizationError("SAVED_FACT_SHAPE_FAIL", "saved artifact fact lacks path/bytes/hash", {"label": label, "row": row}) from exc
    require(path.parent == expected_parent.resolve(), "SAVED_FACT_PARENT_FAIL", "saved artifact is outside the exact P5 CAD leaf", {"label": label, "path": norm(path), "expected_parent": norm(expected_parent)})
    require(path.suffix.upper() == expected_suffix, "SAVED_FACT_SUFFIX_FAIL", "saved artifact has the wrong native suffix", {"label": label, "path": norm(path)})
    current = file_fact(path)
    require(current["bytes"] == expected_bytes and current["sha256"] == expected_hash, "SAVED_FACT_CURRENT_DRIFT", "preserved P5 artifact differs from its failure receipt", {"label": label, "receipt": row, "current": current})
    return current


def validate_p5_failure() -> Dict[str, Any]:
    failure_fact = check_file(P5_FAILURE, EXPECTED_SHA256[P5_FAILURE])
    payload = load_json(P5_FAILURE)
    checks = {
        "schema": payload.get("schema") == "F3R2_V5_SOLAR_R2B_A_BUILD_STAGE_RECEIPT_V1",
        "verdict": payload.get("verdict") == "CONFIG_TRANSFORM_READBACK_FAIL",
        "attempt_id": payload.get("attempt_id") == P5_ATTEMPT_ID,
        "storage_id": payload.get("storage_id") == P5_STORAGE_ID,
        "attempt_root": Path(str(payload.get("attempt_root", ""))).resolve() == P5_ROOT.resolve(),
        "attempt_preserved": payload.get("attempt_preserved") is True,
        "pre_patch_builder": payload.get("builder") == file_fact(PRE_PATCH_BUILDER),
        "pre_patch_contract": payload.get("contract_sha256") == PRE_PATCH_CONTRACT_SHA256,
    }
    require(all(checks.values()), "P5_LINEAGE_FAIL", "P5 failure lineage does not match the frozen pre-patch build", {"checks": checks})
    detail = payload.get("detail")
    require(isinstance(detail, dict), "P5_DETAIL_FAIL", "P5 failure detail is absent")
    error = detail.get("error")
    require(
        detail.get("side") == "L"
        and detail.get("state") == "SOLAR_STOWED"
        and detail.get("panel") == 1
        and isinstance(error, dict)
        and as_float(error.get("translation_mm"), "p5.translation_mm") == 286.3
        and as_float(error.get("rotation_deg"), "p5.rotation_deg") == 180.0,
        "P5_FAILURE_SIGNATURE_FAIL",
        "P5 failure is not the exact L/STOWED/P1 positive-mirror signature",
        {"detail": detail},
    )

    parts = payload.get("parts")
    modules = payload.get("modules")
    sides = payload.get("side_assemblies")
    require(isinstance(parts, list) and isinstance(modules, list) and sides == [], "P5_ARTIFACT_LIST_FAIL", "P5 failure artifact lists are malformed")
    require((len(parts), len(modules), len(sides)) == (38, 6, 0), "P5_ARTIFACT_COUNT_FAIL", "P5 must contain 38 parts, 6 modules, and no saved side assembly", {"counts": [len(parts), len(modules), len(sides)]})

    part_facts: List[Dict[str, Any]] = []
    actual_part_names: set[str] = set()
    for index, item in enumerate(parts):
        require(isinstance(item, dict) and isinstance(item.get("target"), dict), "P5_PART_ROW_FAIL", "P5 part row lacks target fact", {"index": index})
        fact = validate_saved_fact(item["target"], P5_ROOT / "cad/parts", ".SLDPRT", f"part[{index}]")
        require(fact["path"] not in {row["path"] for row in part_facts}, "P5_PART_DUPLICATE_FAIL", "P5 part target is duplicated", {"path": fact["path"]})
        actual_part_names.add(Path(fact["path"]).name)
        part_facts.append(fact)
    require(actual_part_names == expected_part_names(), "P5_PART_NAME_SET_FAIL", "P5 native part filename set differs from the 38-part contract", {"actual": sorted(actual_part_names), "expected": sorted(expected_part_names())})

    expected_module_names = {f"SOLAR_PANEL_MODULE_{side}{index}_R2B.SLDASM" for side in ("L", "R") for index in (1, 2, 3)}
    module_facts: List[Dict[str, Any]] = []
    for index, item in enumerate(modules):
        require(isinstance(item, dict) and isinstance(item.get("target"), dict), "P5_MODULE_ROW_FAIL", "P5 module row lacks target fact", {"index": index})
        fact = validate_saved_fact(item["target"], P5_ROOT / "cad/modules", ".SLDASM", f"module[{index}]")
        require(fact["path"] not in {row["path"] for row in module_facts}, "P5_MODULE_DUPLICATE_FAIL", "P5 module target is duplicated", {"path": fact["path"]})
        module_facts.append(fact)
    require({Path(row["path"]).name for row in module_facts} == expected_module_names, "P5_MODULE_NAME_SET_FAIL", "P5 module filename set differs from the six-module contract")

    by_name = {Path(row["path"]).name: row for row in module_facts}
    require(by_name["SOLAR_PANEL_MODULE_L1_R2B.SLDASM"]["sha256"] == P5_L1_SHA256, "P5_L1_HASH_FAIL", "P5 L1 module differs from the root probe input")
    require(by_name["SOLAR_PANEL_MODULE_R1_R2B.SLDASM"]["sha256"] == P5_R1_SHA256, "P5_R1_HASH_FAIL", "P5 R1 module differs from the root probe input")

    manifest = sorted([*part_facts, *module_facts], key=lambda row: row["path"])
    return {
        "failure_receipt": failure_fact,
        "attempt_id": P5_ATTEMPT_ID,
        "storage_id": P5_STORAGE_ID,
        "attempt_root": norm(P5_ROOT),
        "pre_patch_builder": file_fact(PRE_PATCH_BUILDER),
        "pre_patch_contract_sha256": PRE_PATCH_CONTRACT_SHA256,
        "failure_signature": {"side": "L", "state": "SOLAR_STOWED", "panel": 1, "translation_mm": 286.3, "rotation_deg": 180.0, "classification": "POSITIVE_MIRROR_OF_EXPECTED_NEGATIVE_ROOT_BRANCH"},
        "artifact_counts": {"sldprt": 38, "module_sldasm": 6, "side_sldasm": 0},
        "p1_module_facts": {"L": by_name["SOLAR_PANEL_MODULE_L1_R2B.SLDASM"], "R": by_name["SOLAR_PANEL_MODULE_R1_R2B.SLDASM"]},
        "cad_manifest": manifest,
        "cad_manifest_sha256": digest_json(manifest),
        "verdict": "V5_SOLAR_R2B_P5_FAILURE_LINEAGE_PASS",
    }


def validate_authority_and_oracle() -> Dict[str, Any]:
    authority_fact = check_file(STATE_AUTHORITY, EXPECTED_SHA256[STATE_AUTHORITY])
    oracle_fact = check_file(STATIC_ORACLE, EXPECTED_SHA256[STATIC_ORACLE])
    authority = load_json(STATE_AUTHORITY)
    oracle = load_json(STATIC_ORACLE)
    require(authority.get("schema") == "F3R2_V5_SOLAR_STATE_AUTHORITY_R2B", "AUTHORITY_SCHEMA_FAIL", "state authority schema differs")
    stowed = authority.get("states", {}).get("SOLAR_STOWED", {})
    require(stowed.get("LEFT") == [0, 0, 0] and stowed.get("RIGHT") == [0, 0, 0], "AUTHORITY_STOWED_FAIL", "SOLAR_STOWED is not exact 0/0/0 on both sides")
    coordinate = authority.get("coordinate_contract", {})
    require(coordinate.get("root_axis") == "X" and coordinate.get("left_root_axis_point_mm") == [-61.0, 143.15, 0.0] and coordinate.get("right_root_axis_point_mm") == [-61.0, -143.15, 0.0], "AUTHORITY_ROOT_AXIS_FAIL", "root axis authority differs")
    require(oracle.get("schema") == "F3R2_V5_SOLAR_R2B_STATIC_KINEMATIC_ORACLE_V2" and oracle.get("verdict") == "V5_SOLAR_R2B_STATIC_KINEMATIC_ORACLE_PASS", "ORACLE_VERDICT_FAIL", "static oracle is not the frozen PASS")
    gates = oracle.get("gates", {})
    require(gates.get("state_count") == 7 and gates.get("fail_mapping_pass") is True and gates.get("positive_volume_panel_pair_count") == 0, "ORACLE_GATE_FAIL", "static oracle gates differ", {"gates": gates})
    oracle_inputs = {Path(str(row.get("path", ""))).resolve(): row for row in oracle.get("inputs", []) if isinstance(row, dict)}
    require(STATE_AUTHORITY.resolve() in oracle_inputs and oracle_inputs[STATE_AUTHORITY.resolve()].get("sha256") == authority_fact["sha256"], "ORACLE_AUTHORITY_BIND_FAIL", "oracle does not bind the exact state authority")
    stowed_oracle = [row for row in oracle.get("states", []) if isinstance(row, dict) and row.get("state") == "SOLAR_STOWED"]
    require(len(stowed_oracle) == 1, "ORACLE_STOWED_CARDINALITY_FAIL", "oracle lacks one SOLAR_STOWED row")
    left_panels = stowed_oracle[0].get("left", {}).get("panels", [])
    right_panels = stowed_oracle[0].get("right", {}).get("panels", [])
    # ``native_absolute_rotation_deg`` is a normalized local primitive angle;
    # it is -90 deg on both mirrored sides.  The world-space signed branch is
    # carried by the proper-rotation matrices: L has r[2,1]=-1, R has r[2,1]=+1.
    left_rotation = left_panels[0].get("rotation_3x3") if left_panels else None
    right_rotation = right_panels[0].get("rotation_3x3") if right_panels else None
    expected_left = [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]]
    expected_right = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]
    def matrix_close(actual: Any, expected: Any) -> bool:
        return (
            isinstance(actual, list)
            and len(actual) == 3
            and all(isinstance(row, list) and len(row) == 3 for row in actual)
            and max(abs(as_float(actual[i][j], f"oracle.rotation[{i}][{j}]") - expected[i][j]) for i in range(3) for j in range(3)) <= 1.0e-12
        )
    require(
        left_panels
        and right_panels
        and as_float(left_panels[0].get("native_absolute_rotation_deg"), "oracle.L1") == -90.0
        and as_float(right_panels[0].get("native_absolute_rotation_deg"), "oracle.R1") == -90.0
        and matrix_close(left_rotation, expected_left)
        and matrix_close(right_rotation, expected_right),
        "ORACLE_ROOT_SIGN_FAIL",
        "oracle stowed P1 proper mirrored rotations differ",
        {"left_rotation_3x3": left_rotation, "right_rotation_3x3": right_rotation},
    )
    return {
        "state_authority": authority_fact,
        "static_oracle": oracle_fact,
        "stowed_root_local_primitive_rotation_deg": {"L": -90.0, "R": -90.0},
        "stowed_root_world_signed_rotation_deg": {"L": -90.0, "R": 90.0},
        "stowed_root_rotation_3x3": {"L": left_rotation, "R": right_rotation},
        "verdict": "V5_SOLAR_R2B_ROOT_SIGN_AUTHORITY_PASS",
    }


def validate_angle_stage(stage: Any, expected_flip: bool, expected_angle: float, expected_suppressed: bool, label: str) -> Dict[str, Any]:
    require(isinstance(stage, dict), "ANGLE_STAGE_ROW_FAIL", "angle stage is not an object", {"label": label})
    health = stage.get("feature_health")
    sources = stage.get("flip_sources")
    require(isinstance(health, dict) and isinstance(sources, dict), "ANGLE_STAGE_DETAIL_FAIL", "angle stage lacks health or flip sources", {"label": label})
    checks = {
        "mate_type": stage.get("mate_type") == 6,
        "alignment": stage.get("alignment") == 0,
        "flipped": stage.get("flipped") is expected_flip,
        "flip_sources": sources == {"IAngleMateFeatureData.FlipDimension": expected_flip, "IMate2.Flipped": expected_flip},
        "advanced": stage.get("advanced") is True,
        "minimum": close(as_float(stage.get("minimum_angle_rad"), f"{label}.minimum"), 0.0, 1.0e-15),
        "maximum": close(as_float(stage.get("maximum_angle_rad"), f"{label}.maximum"), math.pi / 2.0, 1.0e-15),
        "angle": close(as_float(stage.get("angle_rad"), f"{label}.angle"), expected_angle, ANGLE_TOL_RAD),
        "health": health.get("feature_error_code") == 0 and health.get("feature_error_code2") == 0 and health.get("feature_is_warning") is False and health.get("suppressed") is expected_suppressed,
        "dimension": isinstance(stage.get("dimension_full_name"), str) and bool(stage.get("dimension_full_name")),
    }
    require(all(checks.values()), "ANGLE_STAGE_SEMANTICS_FAIL", "angle definition/readback/health differs", {"label": label, "checks": checks, "stage": stage})
    return {"angle_rad": expected_angle, "suppressed": expected_suppressed, "flipped": expected_flip, "alignment": 0, "advanced": True, "health_pass": True}


def validate_root_physical(case: Mapping[str, Any], side: str, label: str) -> Dict[str, Any]:
    physical = case.get("physical_root_mates")
    require(isinstance(physical, dict), "PHYSICAL_ROOT_ROW_FAIL", "case lacks physical ROOT mate evidence", {"label": label})
    axis_y = 143.15 if side == "L" else -143.15
    expected_module_name = f"SOLAR_PANEL_MODULE_{side}1_R2B-1"
    require(physical.get("module") == expected_module_name, "PHYSICAL_ROOT_MODULE_FAIL", "physical ROOT uses a different P1 module", {"label": label, "module": physical.get("module")})
    require(physical.get("nested_u_lug") == file_fact(ROOT_FILES[side]["u_lug"]), "PHYSICAL_ROOT_LUG_FACT_FAIL", "physical ROOT U-lug fact differs", {"label": label})
    lug = physical.get("lug_bore")
    pin = physical.get("pin_bore")
    require(isinstance(lug, dict) and isinstance(pin, dict), "PHYSICAL_ROOT_BORE_ROW_FAIL", "physical ROOT lacks lug/pin B-rep facts", {"label": label})
    lug_params = normalize_numeric_list(lug.get("cylinder_params"), 7, f"{label}.lug")
    pin_params = normalize_numeric_list(pin.get("cylinder_params"), 7, f"{label}.pin")
    require(lug.get("candidate_count") == 2 and close(as_float(lug.get("radius_mm"), f"{label}.lug.radius"), 4.2, 1.0e-9) and close(lug_params[0] * 1000.0, -82.0, 0.06) and close(lug_params[1] * 1000.0, axis_y, 0.06) and close(lug_params[2] * 1000.0, 0.0, 0.06) and close(abs(lug_params[6]) * 1000.0, 4.2, 0.06), "PHYSICAL_ROOT_LUG_BORE_FAIL", "dual-ear minimum-X lug bore differs", {"label": label, "lug": lug})
    require(pin.get("candidate_count") == 1 and close(as_float(pin.get("radius_mm"), f"{label}.pin.radius"), 4.0, 1.0e-9) and close(pin_params[1] * 1000.0, axis_y, 0.06) and close(pin_params[2] * 1000.0, 0.0, 0.06) and close(abs(pin_params[6]) * 1000.0, 4.0, 0.06), "PHYSICAL_ROOT_PIN_BORE_FAIL", "root pin bore differs", {"label": label, "pin": pin})
    lug_plane = physical.get("lug_plane")
    spacer_plane = physical.get("spacer_plane")
    require(isinstance(lug_plane, dict) and lug_plane.get("candidate_count") == 1 and close(as_float(lug_plane.get("x_mm"), f"{label}.lug_plane"), -75.0, 0.06), "PHYSICAL_ROOT_LUG_PLANE_FAIL", "root lug axial face differs", {"label": label})
    require(isinstance(spacer_plane, dict) and spacer_plane.get("candidate_count_at_local_x_plus_0p5") == 1 and close(as_float(spacer_plane.get("mapped_world_x_mm"), f"{label}.spacer_plane"), -75.0, 0.06), "PHYSICAL_ROOT_SPACER_PLANE_FAIL", "root spacer axial face differs", {"label": label})
    for key, mate_type, expected_paths in (
        ("concentric", 1, {ROOT_FILES[side]["u_lug"].resolve(), ROOT_FILES[side]["pin"].resolve()}),
        ("coincident", 0, {ROOT_FILES[side]["u_lug"].resolve(), SPACER.resolve()}),
    ):
        mate = physical.get(key)
        require(isinstance(mate, dict), "PHYSICAL_ROOT_MATE_ROW_FAIL", "physical ROOT mate row is absent", {"label": label, "mate": key})
        actual_paths = {Path(str(path)).resolve() for path in mate.get("component_paths", [])}
        require(mate.get("mate_type") == mate_type and mate.get("selected_count") == 2 and mate.get("mate_object_returned") is True and mate.get("error_status") == 1 and actual_paths == expected_paths, "PHYSICAL_ROOT_MATE_FAIL", "physical ROOT mate differs", {"label": label, "mate": key, "row": mate})
    return {"axis_y_mm": axis_y, "module": expected_module_name, "lug_candidate_count": 2, "lug_chosen_axis_x_mm": -82.0, "concentric_pass": True, "coincident_pass": True}


def normalize_numeric_list(value: Any, count: int, label: str) -> List[float]:
    require(isinstance(value, list) and len(value) >= count, "NUMERIC_LIST_SHAPE_FAIL", "numeric list is too short", {"label": label, "count": len(value) if isinstance(value, list) else None})
    return [as_float(item, f"{label}[{index}]") for index, item in enumerate(value)]


def validate_probe_inputs(result: Mapping[str, Any], p5: Mapping[str, Any]) -> Dict[str, Any]:
    rows = result.get("input_hash_stability")
    require(isinstance(rows, dict), "PROBE_INPUT_ROWS_FAIL", "probe result lacks input_hash_stability")
    expected_paths = {path.resolve() for path in EXPECTED_PROBE_INPUT_SHA256}
    actual_paths = {Path(str(path)).resolve() for path in rows}
    require(actual_paths == expected_paths and len(rows) == 11, "PROBE_INPUT_SET_FAIL", "probe input set differs from the exact eleven frozen inputs", {"actual": sorted(norm(path) for path in actual_paths), "expected": sorted(norm(path) for path in expected_paths)})
    facts: List[Dict[str, Any]] = []
    for path, expected_hash in EXPECTED_PROBE_INPUT_SHA256.items():
        key = norm(path)
        row = rows.get(key)
        require(isinstance(row, dict) and row.get("pass") is True and row.get("pre") == row.get("post"), "PROBE_INPUT_PRE_POST_FAIL", "probe input PRE and POST differ", {"path": key, "row": row})
        current = check_file(path, expected_hash)
        require(row.get("pre") == current, "PROBE_INPUT_CURRENT_DRIFT", "probe input differs from PRE/POST and current fact", {"path": key, "probe": row.get("pre"), "current": current})
        facts.append(current)
    p1 = p5["p1_module_facts"]
    require(rows[norm(ROOT_FILES["L"]["module"])]["pre"] == p1["L"], "PROBE_P5_L1_CROSSLINK_FAIL", "probe L1 input is not the P5 L1 module fact")
    require(rows[norm(ROOT_FILES["R"]["module"])]["pre"] == p1["R"], "PROBE_P5_R1_CROSSLINK_FAIL", "probe R1 input is not the P5 R1 module fact")
    facts.sort(key=lambda row: row["path"])
    return {"input_count": 11, "input_pre_equals_post": True, "facts": facts, "manifest_sha256": digest_json(facts), "p5_p1_crosslink": True}


def validate_case(case: Any) -> Dict[str, Any]:
    require(isinstance(case, dict), "PROBE_CASE_ROW_FAIL", "probe case is not an object")
    side = str(case.get("side"))
    beta = as_float(case.get("beta_deg"), "case.beta_deg")
    flip = case.get("requested_flip")
    protocol = case.get("protocol")
    require(side in ("L", "R") and beta in BETAS_DEG and flip in FLIPS and protocol in PROTOCOLS, "PROBE_CASE_FACTOR_FAIL", "probe case is outside the frozen factorial", {"case": case.get("label")})
    suffix = "FT" if protocol == "FULL_TABLE_LIKE" else "PS"
    expected_label = f"{side}_B{int(beta):03d}_F{int(flip)}_{suffix}"
    require(case.get("label") == expected_label and case.get("case_complete") is True, "PROBE_CASE_ID_FAIL", "probe case label/completion differs", {"expected": expected_label, "actual": case.get("label")})
    requested_rad = math.radians(beta)
    require(case.get("typed_drive_status") == 0 and close(as_float(case.get("requested_driver_rad"), f"{expected_label}.requested"), requested_rad, 1.0e-15) and close(as_float(case.get("final_driver_readback_rad"), f"{expected_label}.driver"), requested_rad, ANGLE_TOL_RAD), "PROBE_DRIVER_FAIL", "typed driver or exact readback differs", {"label": expected_label})

    creation = case.get("angle_creation")
    require(isinstance(creation, dict), "PROBE_ANGLE_CREATION_ROW_FAIL", "case lacks angle creation", {"label": expected_label})
    expected_first = f"{'LEFT' if side == 'L' else 'RIGHT'}_WING_ROOT_THREE_WEB_CLEVIS-1"
    expected_second = f"SOLAR_PANEL_MODULE_{side}1_R2B-1"
    first_plane = creation.get("first_plane")
    second_plane = creation.get("second_plane")
    require(isinstance(first_plane, dict) and isinstance(second_plane, dict), "PROBE_DATUM_ROW_FAIL", "case lacks datum plane facts", {"label": expected_label})
    for datum, expected_component, datum_label in ((first_plane, expected_first, "first"), (second_plane, expected_second, "second")):
        all_planes = datum.get("all_ref_planes")
        require(isinstance(all_planes, list) and len(all_planes) == 3 and len(set(all_planes)) == 3 and datum.get("selected") == all_planes[1] and datum.get("component") == expected_component, "PROBE_DATUM_FAIL", "case does not select the production Top plane", {"label": expected_label, "datum": datum_label, "row": datum})
    expected_creation_paths = {ROOT_FILES[side]["clevis"].resolve(), ROOT_FILES[side]["module"].resolve()}
    actual_creation_paths = {Path(str(path)).resolve() for path in creation.get("component_paths", [])}
    require(creation.get("mate_type") == 6 and creation.get("align") == 0 and creation.get("resolved_alignment") == 0 and creation.get("requested_flip") is flip and creation.get("selection_order") == "CLEVIS_PARENT_THEN_P1_MODULE_CHILD" and creation.get("selected_count") == 2 and creation.get("mate_object_returned") is True and creation.get("error_status") == 1 and actual_creation_paths == expected_creation_paths, "PROBE_ANGLE_CREATION_FAIL", "production ROOT angle creation differs", {"label": expected_label, "creation": creation})
    validate_angle_stage(creation.get("readback"), flip, 0.0, False, f"{expected_label}.creation")
    validate_angle_stage(case.get("angle_before_restore"), flip, requested_rad, True, f"{expected_label}.before_restore")
    validate_angle_stage(case.get("final_angle_readback"), flip, requested_rad, False, f"{expected_label}.final")

    expected = analytic_root_transform(side, beta, False)
    mirror = analytic_root_transform(side, beta, True)
    stored_expected = normalize_transform(case.get("expected_transform16"), f"{expected_label}.stored_expected")
    require_transform(stored_expected, expected, f"{expected_label}.expected_contract")
    pre_pose = case.get("pose_before_restore_expected_branch")
    require(isinstance(pre_pose, dict), "PROBE_PREPOSE_ROW_FAIL", "case lacks preposition pose", {"label": expected_label})
    pre_transform = normalize_transform(pre_pose.get("transform16"), f"{expected_label}.preposition")
    pre_error = require_transform(pre_transform, expected, f"{expected_label}.preposition")
    require_stored_error(case.get("preposition_error"), pre_error, f"{expected_label}.preposition_error")

    actual_pose = case.get("pose_after_restore")
    require(isinstance(actual_pose, dict), "PROBE_FINAL_POSE_ROW_FAIL", "case lacks final pose", {"label": expected_label})
    actual = normalize_transform(actual_pose.get("transform16"), f"{expected_label}.actual")
    computed_signed = math.degrees(math.atan2(actual[5], actual[4]))
    require(close(as_float(actual_pose.get("signed_rx_deg"), f"{expected_label}.pose_signed"), computed_signed, ANGLE_TOL_DEG), "PROBE_POSE_SIGN_FAIL", "pose signed angle differs from transform", {"label": expected_label})
    translation = [actual[index] * 1000.0 for index in (9, 10, 11)]
    stored_translation = normalize_numeric_list(actual_pose.get("translation_mm"), 3, f"{expected_label}.translation")
    require(max(abs(stored_translation[index] - translation[index]) for index in range(3)) <= 1.0e-6, "PROBE_POSE_TRANSLATION_FAIL", "pose translation witness differs from transform", {"label": expected_label})

    expected_error = transform_error(actual, expected)
    mirror_error = transform_error(actual, mirror)
    branch = case.get("solver_branch")
    require(isinstance(branch, dict), "PROBE_BRANCH_ROW_FAIL", "case lacks solver branch", {"label": expected_label})
    require_stored_error(branch.get("expected_error"), expected_error, f"{expected_label}.expected_error")
    require_stored_error(branch.get("mirror_error"), mirror_error, f"{expected_label}.mirror_error")
    require_transform(normalize_transform(branch.get("mirror_transform16"), f"{expected_label}.mirror_contract"), mirror, f"{expected_label}.mirror_contract")
    signed_expected = -beta if side == "L" else beta
    require(close(as_float(branch.get("signed_expected_rx_deg"), f"{expected_label}.signed_expected"), signed_expected, ANGLE_TOL_DEG) and close(as_float(branch.get("signed_mirror_rx_deg"), f"{expected_label}.signed_mirror"), -signed_expected, ANGLE_TOL_DEG) and close(as_float(branch.get("signed_rx_deg"), f"{expected_label}.signed_actual"), computed_signed, ANGLE_TOL_DEG), "PROBE_BRANCH_SIGN_FAIL", "solver branch signed witnesses differ", {"label": expected_label})
    is_winner = flip is ROOT_WINNER[side]
    wanted_branch = "SIDE_EXPECTED" if is_winner else "OPPOSITE_MIRROR"
    require(branch.get("branch") == wanted_branch, "PROBE_BRANCH_CLASS_FAIL", "solver branch classification differs", {"label": expected_label, "expected": wanted_branch, "actual": branch.get("branch")})
    final_error = require_transform(actual, expected if is_winner else mirror, f"{expected_label}.final_branch")
    require(abs(abs(computed_signed) - beta) <= ANGLE_TOL_DEG, "PROBE_BRANCH_MAGNITUDE_FAIL", "final branch magnitude differs", {"label": expected_label, "signed_rx_deg": computed_signed})

    physical = validate_root_physical(case, side, expected_label)
    assembly = case.get("assembly")
    require(isinstance(assembly, dict), "PROBE_ASSEMBLY_FACT_FAIL", "case lacks scratch assembly fact", {"label": expected_label})
    assembly_path = Path(str(assembly.get("path", ""))).resolve()
    expected_case_dir = PROBE_RESULT.parent / "cad/cases"
    require(assembly_path.parent == expected_case_dir.resolve() and assembly_path.name == f"{expected_label}.SLDASM", "PROBE_ASSEMBLY_PATH_FAIL", "scratch case assembly path differs", {"label": expected_label, "path": norm(assembly_path)})
    require(assembly.get("save_as_errors") == 0 and assembly.get("save_as_warnings") == 0 and assembly.get("save3") == {"errors": 0, "warnings": 0}, "PROBE_ASSEMBLY_SAVE_FAIL", "scratch case assembly save was not clean", {"label": expected_label, "assembly": assembly})
    require(assembly == file_fact(assembly_path) | {"save3": {"errors": 0, "warnings": 0}, "save_as_errors": 0, "save_as_warnings": 0}, "PROBE_ASSEMBLY_CURRENT_DRIFT", "scratch case assembly differs from result fact", {"label": expected_label})

    return {
        "label": expected_label,
        "side": side,
        "beta_deg": beta,
        "requested_flip": flip,
        "protocol": protocol,
        "winner": is_winner,
        "branch": wanted_branch,
        "signed_rx_deg": computed_signed,
        "driver_readback_rad": requested_rad,
        "preposition_error": pre_error,
        "final_branch_error": final_error,
        "angle_health_pass": True,
        "physical_root": physical,
        "assembly": file_fact(assembly_path),
    }


def validate_winner_summary(result: Mapping[str, Any], cases: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    summary = result.get("per_side_root_flip_winners")
    require(isinstance(summary, dict), "PROBE_WINNER_SUMMARY_FAIL", "probe result lacks winner summary")
    normalized: Dict[str, Any] = {}
    for side in ("L", "R"):
        require(isinstance(summary.get(side), dict), "PROBE_WINNER_SIDE_FAIL", "winner summary lacks side", {"side": side})
        normalized[side] = {}
        for protocol in PROTOCOLS:
            row = summary[side].get(protocol)
            require(isinstance(row, dict), "PROBE_WINNER_PROTOCOL_FAIL", "winner summary lacks protocol", {"side": side, "protocol": protocol})
            winner = ROOT_WINNER[side]
            # ``unique_winner`` stores the winning Flip value.  For LEFT the
            # correct, unique value is literally False; truthiness is invalid.
            require(row.get("winner_flips") == [winner] and row.get("unique_winner") is winner, "PROBE_UNIQUE_WINNER_FAIL", "winner list/value differs", {"side": side, "protocol": protocol, "expected_flip": winner, "row": row})
            matrix = row.get("flip_matrix")
            require(isinstance(matrix, dict), "PROBE_FLIP_MATRIX_FAIL", "winner summary lacks flip matrix", {"side": side, "protocol": protocol})
            for flip in FLIPS:
                key = str(flip).lower()
                item = matrix.get(key)
                subset = [case for case in cases if case["side"] == side and case["protocol"] == protocol and case["requested_flip"] is flip]
                expected_branch = "SIDE_EXPECTED" if flip is winner else "OPPOSITE_MIRROR"
                expected_branches = {str(beta): expected_branch for beta in BETAS_DEG}
                require(isinstance(item, dict) and item.get("case_count") == 3 and item.get("branches") == expected_branches and item.get("all_three_side_expected") is (flip is winner) and len(subset) == 3 and all(case["branch"] == expected_branch for case in subset), "PROBE_FLIP_MATRIX_SEMANTICS_FAIL", "flip matrix differs from independently evaluated cases", {"side": side, "protocol": protocol, "flip": flip, "item": item})
            normalized[side][protocol] = {"winner_flip": winner, "winner_flips": [winner], "betas_deg": list(BETAS_DEG), "all_winner_cases_side_expected": True, "all_loser_cases_opposite_mirror": True}
    return normalized


def validate_probe_result(p5: Mapping[str, Any]) -> Dict[str, Any]:
    source_fact = check_file(PROBE_SOURCE, EXPECTED_SHA256[PROBE_SOURCE])
    result_fact = check_file(PROBE_RESULT, EXPECTED_SHA256[PROBE_RESULT])
    result = load_json(PROBE_RESULT)
    checks = {
        "schema": result.get("schema") == "F3R2_V5_SOLAR_R2B_REAL_PRODUCTION_ROOT_BRANCH_PROTOCOL_MATRIX_V1",
        "verdict": result.get("verdict") == "V5_SOLAR_R2B_REAL_PRODUCTION_ROOT_BRANCH_PROTOCOL_MATRIX_COMPLETE",
        "classification": result.get("classification") == "DIAGNOSTIC_REAL_PRODUCTION_ROOT_BRANCH_NON_RELEASE",
        "production_use": result.get("production_use") == "PROHIBITED",
        "run_id": result.get("run_id") == "20260813T_ROOTPROTOCOL_G1",
        "attempt_root": Path(str(result.get("attempt_root", ""))).resolve() == PROBE_RESULT.parent.resolve(),
        "angle_selection_order": result.get("angle_selection_order") == "CLEVIS_PARENT_THEN_P1_MODULE_CHILD",
        "case_count": result.get("case_count_planned") == 24 and result.get("case_count_complete") == 24,
        "input_pre_equals_post": result.get("input_pre_equals_post") is True,
    }
    require(all(checks.values()), "PROBE_RESULT_HEADER_FAIL", "production ROOT probe header differs", {"checks": checks})
    session = result.get("session")
    require(isinstance(session, dict) and session.get("attach_only") is True and session.get("document_count") == 0 and session.get("executable") == "F:/Windows_profile/solidworks/SOLIDWORKS/SLDWORKS.exe" and str(session.get("revision", "")).startswith("32.5.") and isinstance(session.get("pid"), int) and session.get("pid") > 0, "PROBE_SESSION_FAIL", "probe session evidence differs", {"session": session})
    inputs = validate_probe_inputs(result, p5)

    raw_cases = result.get("cases")
    require(isinstance(raw_cases, list) and len(raw_cases) == 24, "PROBE_CASE_COUNT_FAIL", "probe must contain exactly 24 case rows")
    cases = [validate_case(case) for case in raw_cases]
    factors = {(case["side"], case["beta_deg"], case["requested_flip"], case["protocol"]) for case in cases}
    expected_factors = {(side, beta, flip, protocol) for side in ("L", "R") for beta in BETAS_DEG for flip in FLIPS for protocol in PROTOCOLS}
    require(factors == expected_factors and len(factors) == 24, "PROBE_FACTORIAL_FAIL", "probe cases do not form the exact 2x3x2x2 factorial")
    require(len({case["label"] for case in cases}) == 24 and len({case["assembly"]["path"] for case in cases}) == 24, "PROBE_CASE_DUPLICATE_FAIL", "probe labels or scratch assemblies are duplicated")
    winners = validate_winner_summary(result, cases)
    max_pre_t = max(case["preposition_error"]["translation_mm"] for case in cases)
    max_pre_r = max(case["preposition_error"]["rotation_deg"] for case in cases)
    winner_cases = [case for case in cases if case["winner"]]
    max_final_t = max(case["final_branch_error"]["translation_mm"] for case in winner_cases)
    max_final_r = max(case["final_branch_error"]["rotation_deg"] for case in winner_cases)
    case_digest_rows = [
        {
            "label": case["label"],
            "side": case["side"],
            "beta_deg": case["beta_deg"],
            "requested_flip": case["requested_flip"],
            "protocol": case["protocol"],
            "winner": case["winner"],
            "branch": case["branch"],
            "signed_rx_deg": case["signed_rx_deg"],
            "assembly": case["assembly"],
        }
        for case in cases
    ]
    return {
        "probe_source": source_fact,
        "probe_result": result_fact,
        "result_header_checks": checks,
        "session": session,
        "input_stability": inputs,
        "factorial": {"side_count": 2, "betas_deg": list(BETAS_DEG), "flips": list(FLIPS), "protocols": list(PROTOCOLS), "case_count": 24},
        "winner_summary": winners,
        "case_semantics": case_digest_rows,
        "case_semantics_sha256": digest_json(case_digest_rows),
        "max_preposition_translation_mm": max_pre_t,
        "max_preposition_rotation_deg": max_pre_r,
        "max_winner_final_translation_mm": max_final_t,
        "max_winner_final_rotation_deg": max_final_r,
        "all_driver_readbacks_exact": True,
        "all_angle_definitions_advanced_0_to_90": True,
        "all_final_mates_healthy_and_unsuppressed": True,
        "diagnostic_production_use": "PROHIBITED",
        "verdict": "V5_SOLAR_R2B_REAL_PRODUCTION_ROOT_BRANCH_SEMANTICS_PASS",
    }


def authorized_patch_contract() -> Dict[str, Any]:
    for side in ("L", "R"):
        for joint in ("H12", "H23"):
            require(BEFORE_FLIP[side][joint] is AFTER_FLIP[side][joint], "PATCH_SCOPE_INTERNAL_FAIL", "interpanel Flip changed inside authorization constants", {"side": side, "joint": joint})
    return {
        "authorization_scope": "PRODUCTION_ROOT_LIMIT_ANGLE_FLIP_ONLY",
        "before": BEFORE_FLIP,
        "after": AFTER_FLIP,
        "changed_cells": [
            {"side": "L", "joint": "ROOT", "before": True, "after": False},
            {"side": "R", "joint": "ROOT", "before": False, "after": True},
        ],
        "unchanged_cells": [
            {"side": side, "joint": joint, "value": BEFORE_FLIP[side][joint]}
            for side in ("L", "R")
            for joint in ("H12", "H23")
        ],
        "allowed_dependent_source_updates": [
            "ANGLE_BRANCH_CONTRACT_SCHEMA_V1_TO_V2",
            "ROOT_EVIDENCE_POINTER_TO_THIS_AUTHORIZATION_RECEIPT",
            "BUILDER_MICROFIXTURE_FRESH_HASH_INTERLOCKS_AND_CONTRACT_DIGEST",
            "RECEIPT_HANDOFF_MANIFEST_LINEAGE_FIELDS",
        ],
        "prohibited_changes": [
            "H12_OR_H23_FLIP",
            "MATE_TOPOLOGY_OR_MATE_COUNT",
            "SOLAR_GEOMETRY_OR_NATIVE_PART_CONTENT",
            "STATE_AUTHORITY_OR_STATIC_ORACLE",
            "CONFIGURATION_NAMES_OR_LOGICAL_ANGLES",
            "DIMENSION_WRITE_OR_POSE_RESTORE_PROTOCOL",
            "ACCEPTED_B601_URDF_OR_MASS_INERTIA_TRUTH",
            "DIAGNOSTIC_CAD_PROMOTION",
        ],
        "fixture_root_note": "ROOT_EQUIVALENT_MICROFIXTURE_FLIP_IS_FIXTURE_LOCAL_AND_MUST_NOT_BE_MECHANICALLY_REPLACED_BY_THE_PRODUCTION_CLEVIS_FLIP",
        "post_patch_build_required": True,
        "different_pid_read_only_fresh_verification_required": True,
        "promotion_authorized": False,
    }


def build_authorization_payload(timestamp_utc: str) -> Dict[str, Any]:
    for path, expected in EXPECTED_SHA256.items():
        check_file(path, expected)
    old_flip = builder_flip_literal()
    require(old_flip.get("schema") == "F3R2_V5_SOLAR_R2B_A_LIMIT_ANGLE_BRANCH_CONTRACT_V1" and old_flip.get("selection_order") == "PARENT_THEN_CHILD" and old_flip.get("alignment") == 0 and old_flip.get("sides") == BEFORE_FLIP, "PRE_PATCH_FLIP_LITERAL_FAIL", "pre-patch builder Flip contract differs", {"actual": old_flip, "expected_sides": BEFORE_FLIP})
    authority = validate_authority_and_oracle()
    p5 = validate_p5_failure()
    probe = validate_probe_result(p5)
    patch = authorized_patch_contract()
    producer = file_fact(Path(__file__))
    lineage = {
        "producer": producer,
        "pre_patch_builder": p5["pre_patch_builder"],
        "pre_patch_contract_sha256": PRE_PATCH_CONTRACT_SHA256,
        "p5_failure_receipt": p5["failure_receipt"],
        "production_root_probe_source": probe["probe_source"],
        "production_root_probe_result": probe["probe_result"],
        "state_authority": authority["state_authority"],
        "static_oracle": authority["static_oracle"],
        "p5_cad_manifest_sha256": p5["cad_manifest_sha256"],
        "probe_input_manifest_sha256": probe["input_stability"]["manifest_sha256"],
        "probe_case_semantics_sha256": probe["case_semantics_sha256"],
    }
    evidence_digest_payload = {
        "lineage": lineage,
        "failure_signature": p5["failure_signature"],
        "winner_summary": probe["winner_summary"],
        "authorized_patch": patch,
    }
    return {
        "schema": "F3R2_V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_V1",
        "timestamp_utc": timestamp_utc,
        "classification": "ENGINEERING_EVIDENCE_BRIDGE__PATCH_AUTHORIZATION_ONLY",
        "scope": "V5_NATIVE_FINALIZATION/MULTI_PANEL_SOLAR_ARRAY_CANDIDATE/ROOT_LIMIT_ANGLE_BRANCH",
        "producer": producer,
        "lineage": lineage,
        "pre_patch_flip_contract": old_flip,
        "authority_and_oracle": authority,
        "p5_failure_lineage": p5,
        "production_root_probe_validation": probe,
        "authorized_patch": patch,
        "evidence_chain_sha256": digest_json(evidence_digest_payload),
        "claims": {
            "solidworks_touched": False,
            "cad_write_calls": 0,
            "cad_files_mutated": 0,
            "receipt_write_calls": 1,
            "probe_history_modified": False,
            "diagnostic_cad_production_use": "PROHIBITED",
            "production_build_passed": False,
            "fresh_pid_verified": False,
            "promotion_authorized": False,
            "flight_ready": False,
            "launch_qualified": False,
        },
        "verdict": "V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_PATCH_ONLY_AUTHORIZED",
    }


def source_purity_audit() -> Dict[str, Any]:
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(Path(__file__)))
    imports: List[str] = []
    forbidden_import_roots = {"win32com", "pythoncom", "pywintypes"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    forbidden_imports = sorted(name for name in imports if name.split(".")[0] in forbidden_import_roots)
    forbidden_calls = {"Dispatch", "DispatchEx", "GetActiveObject", "OpenDoc6", "Save3", "SaveAs", "SetTransformAndSolve3", "SetSystemValue3"}
    seen_forbidden_calls: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
                seen_forbidden_calls.append(node.func.id)
            elif isinstance(node.func, ast.Attribute) and node.func.attr in forbidden_calls:
                seen_forbidden_calls.append(node.func.attr)
    require(not forbidden_imports and not seen_forbidden_calls, "SOURCE_PURITY_FAIL", "authorization tool contains a forbidden SOLIDWORKS runtime capability", {"forbidden_imports": forbidden_imports, "forbidden_calls": seen_forbidden_calls})
    return {"ast_parse": True, "imports": sorted(imports), "forbidden_solidworks_imports": [], "forbidden_solidworks_calls": [], "write_scope": norm(AUTHORIZATION_RECEIPT), "verdict": "V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZER_PURE_FILE_PASS"}


def static_audit() -> Dict[str, Any]:
    purity = source_purity_audit()
    payload = build_authorization_payload("STATIC_AUDIT_PREVIEW")
    return {
        "schema": "F3R2_V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "producer": file_fact(Path(__file__)),
        "purity": purity,
        "receipt_path": norm(AUTHORIZATION_RECEIPT),
        "receipt_absent": not AUTHORIZATION_RECEIPT.exists(),
        "source_lineage_hashes": {key: value["sha256"] if isinstance(value, dict) and "sha256" in value else value for key, value in payload["lineage"].items() if key in {"pre_patch_builder", "pre_patch_contract_sha256", "p5_failure_receipt", "production_root_probe_source", "production_root_probe_result"}},
        "evidence_chain_sha256_preview": payload["evidence_chain_sha256"],
        "authorized_after_map": payload["authorized_patch"]["after"],
        "case_count": payload["production_root_probe_validation"]["factorial"]["case_count"],
        "winner_flips": {side: payload["production_root_probe_validation"]["winner_summary"][side][PROTOCOLS[0]]["winner_flip"] for side in ("L", "R")},
        "verdict": "V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_EXECUTION_READY" if not AUTHORIZATION_RECEIPT.exists() else "V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_ALREADY_SEALED",
    }


def write_json_once(path: Path, payload: Mapping[str, Any]) -> None:
    require(path.parent == VALIDATION.resolve() or path.parent.resolve() == VALIDATION.resolve(), "RECEIPT_PARENT_FAIL", "authorization receipt parent differs from 13_validation")
    require(not path.exists(), "RECEIPT_ALREADY_EXISTS", "write-once authorization receipt already exists", {"path": norm(path)})
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        raise


def execute() -> Dict[str, Any]:
    audit = static_audit()
    require(audit["verdict"] == "V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_EXECUTION_READY", "STATIC_AUDIT_HOLD", "authorization static audit is not execution-ready", audit)
    timestamp = utc_now()
    payload = build_authorization_payload(timestamp)
    write_json_once(AUTHORIZATION_RECEIPT, payload)
    actual = load_json(AUTHORIZATION_RECEIPT)
    require(actual == payload, "RECEIPT_COLD_READ_FAIL", "written authorization receipt differs on immediate cold read")
    return {"verdict": payload["verdict"], "receipt": file_fact(AUTHORIZATION_RECEIPT), "evidence_chain_sha256": payload["evidence_chain_sha256"], "solidworks_touched": False, "cad_files_mutated": 0}


def verify() -> Dict[str, Any]:
    receipt_fact = file_fact(AUTHORIZATION_RECEIPT)
    payload = load_json(AUTHORIZATION_RECEIPT)
    require(payload.get("schema") == "F3R2_V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_V1" and payload.get("verdict") == "V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_PATCH_ONLY_AUTHORIZED", "RECEIPT_HEADER_FAIL", "authorization receipt header differs")
    expected = build_authorization_payload(str(payload.get("timestamp_utc")))
    require(payload == expected, "RECEIPT_SEMANTICS_DRIFT", "authorization receipt differs from a complete independent re-evaluation")
    return {"schema": "F3R2_V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_VERIFY_V1", "timestamp_utc": utc_now(), "receipt": receipt_fact, "evidence_chain_sha256": payload["evidence_chain_sha256"], "case_count": payload["production_root_probe_validation"]["factorial"]["case_count"], "winner_flips": {"L": False, "R": True}, "solidworks_touched": False, "cad_files_mutated": 0, "verdict": "V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_VERIFY_PASS"}


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("audit", "execute", "verify"))
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "audit":
            result = static_audit()
            code = 0 if result["verdict"] == "V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_EXECUTION_READY" else 2
        elif args.command == "execute":
            result = execute()
            code = 0
        else:
            result = verify()
            code = 0
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return code
    except Exception as exc:
        result = {
            "error_code": getattr(exc, "code", "UNHANDLED_EXCEPTION"),
            "error": str(exc),
            "detail": getattr(exc, "detail", {}),
            "solidworks_touched": False,
            "cad_files_mutated": 0,
            "verdict": "V5_SOLAR_R2B_PRODUCTION_ROOT_FLIP_AUTHORIZATION_HOLD",
        }
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
