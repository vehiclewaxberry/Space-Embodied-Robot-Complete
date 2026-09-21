#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Write-once real-production ROOT/P1 angle-branch protocol probe.

``audit`` is filesystem-only. ``run`` attaches to one explicitly identified,
document-empty SOLIDWORKS 2024 SP5 process. It never starts or exits
SOLIDWORKS, never opens a production document writable, and never mutates the
preserved P5A5 attempt. Every output is a new diagnostic-only scratch SLDASM
or JSON below ``99_tools/probe_logs``.

For LEFT and RIGHT independently the probe inserts the frozen production
clevis, pin and spacer plus the corresponding *real P5A5 P1 rigid module*.
It recreates the production physical ROOT mates (nested U-lug/pin concentric
and nested U-lug/spacer coincident), then authors the advanced 0..90 degree
angle between clevis Top Plane and module Top Plane. The 24 independent cases
cross beta={1,89,90}, Flip={false,true}, and two drive protocols:

* FULL_TABLE_LIKE: write active-config dimension, rebuild, suppress angle,
  preposition the expected side branch, restore, rebuild.
* PER_STATE_SUPPRESS_BEFORE_DIMENSION: suppress angle first, write the active
  dimension while suppressed, preposition, restore, rebuild.

The result records angle-definition/flip readback, all relevant transforms,
solver branch, exact input PRE=POST hashes, and per-side/per-protocol winners.
This diagnostic cannot authorize or promote production CAD.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


sys.dont_write_bytecode = True

RUN_ROOT = Path(
    r"F:\China Graduate Future Flight Vehicle Innovation Competition"
    r"\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
)
TOOLS = RUN_ROOT / "99_tools"
PROBE_ROOT = TOOLS / "probe_logs"
P5_ROOT = RUN_ROOT / "13_validation/solar_r2_attempts/20260813T164200Z_P5A5"
R2B_PATH = TOOLS / "F3R2_V5_DIAG_SOLAR_R2B_MODULE_CHAIN_ATTACH_ONLY.py"
L1B_PATH = TOOLS / "F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY.py"
SPACER_PATH = RUN_ROOT / "01_native_parts/wing_root/WING_HINGE_AXIAL_SPACER.SLDPRT"

SIDE_INPUTS: Dict[str, Dict[str, Tuple[Path, str]]] = {
    "L": {
        "module": (P5_ROOT / "cad/modules/SOLAR_PANEL_MODULE_L1_R2B.SLDASM", "7D27D1E5EA5AC8EA9F27B1FDC4494CE6AE87AD3A14380EF736494DDFD967CDBA"),
        "clevis": (RUN_ROOT / "01_native_parts/wing_root/LEFT_WING_ROOT_THREE_WEB_CLEVIS.SLDPRT", "AC60E3A07C84F21CF6E20D01533333345713EE3B28F9966BAAC4B452A4FCE673"),
        "pin": (RUN_ROOT / "01_native_parts/wing_root/loop1b/LEFT_HINGE_PIN_V22_ISOLATED.SLDPRT", "97F6BE610F93605B098590A0C0CD157BE3C14A620B58976AA8A74FF00368733F"),
        "u_lug": (RUN_ROOT / "01_native_parts/wing_root/loop1b/LEFT_PANEL_SIDE_U_LUG_NATIVE.SLDPRT", "5E8BDB76637B7F394560A95A938C3FF363DDAE88950E93266CFE66837ABCD749"),
    },
    "R": {
        "module": (P5_ROOT / "cad/modules/SOLAR_PANEL_MODULE_R1_R2B.SLDASM", "61743934F74F3D0A2C271DFF98EB4535401A9D00D62D169F44CCC568FD2486F0"),
        "clevis": (RUN_ROOT / "01_native_parts/wing_root/RIGHT_WING_ROOT_THREE_WEB_CLEVIS.SLDPRT", "2D8121989230723A9D29C43672D8534D719D2AF7A64C110D0B0D16EAA31B1894"),
        "pin": (RUN_ROOT / "01_native_parts/wing_root/loop1b/RIGHT_HINGE_PIN_V22_ISOLATED.SLDPRT", "82E009F39F2320F53BC8651F7F4282898B0D2ABB4F62C8144A1EAC27B1014AC6"),
        "u_lug": (RUN_ROOT / "01_native_parts/wing_root/loop1b/RIGHT_PANEL_SIDE_U_LUG_NATIVE.SLDPRT", "A5A86890E07990706D106170B99DA0E68A31103EA73BF7161497669BCA4C557B"),
    },
}

EXPECTED_HELPERS = {
    R2B_PATH: "A61A531498ACC415D689F56794776787A57F8E6C0D6A0F2F0F9516938460CF6E",
    L1B_PATH: "32BC06FC6A1EFCD6426FE4608D03EABCBD2902CBA228E95B2AD7A91B4E0F283F",
    SPACER_PATH: "821B9484AB4B7B11A59A0136EDD4C537D37C317AC45830A5C1252ECD0A31577D",
}

RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
BETAS_DEG = (1.0, 89.0, 90.0)
FLIPS = (False, True)
PROTOCOLS = ("FULL_TABLE_LIKE", "PER_STATE_SUPPRESS_BEFORE_DIMENSION")
SW_MATE_ANGLE = 6
SW_MATE_CONCENTRIC = 1
SW_MATE_COINCIDENT = 0
SW_ALIGN_ALIGNED = 0
SW_SET_VALUE_IN_SPECIFIC_CONFIGS = 3
ANGLE_TOL_DEG = 1.0e-3
TRANS_TOL_MM = 0.08
ROT_TOL_DEG = 0.15

sys.path.insert(0, str(TOOLS))
import F3R2_V5_DIAG_SOLAR_R2B_MODULE_CHAIN_ATTACH_ONLY as R2B  # noqa: E402

L1B = R2B.L1B


class ProbeError(RuntimeError):
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
    return {"path": norm(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def input_bindings() -> Dict[Path, str]:
    rows = dict(EXPECTED_HELPERS)
    for roles in SIDE_INPUTS.values():
        for path, expected in roles.values():
            rows[path] = expected
    return rows


def validate_run_id(run_id: str) -> str:
    if not RUN_ID_RE.fullmatch(run_id):
        raise ProbeError("RUN_ID_INVALID", "run id is not a safe leaf name", {"run_id": run_id})
    return run_id


def attempt_root(run_id: str) -> Path:
    return PROBE_ROOT / f"V5_SOLAR_R2B_PRODUCTION_ROOT_BRANCH_{validate_run_id(run_id)}"


def write_json_once(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")


def static_audit(run_id: Optional[str]) -> Dict[str, Any]:
    bindings = []
    for path, expected in input_bindings().items():
        actual = sha256(path) if path.is_file() else None
        bindings.append({"path": norm(path), "expected_sha256": expected, "actual_sha256": actual, "pass": actual == expected})
    source = Path(__file__).read_text(encoding="utf-8")
    forbidden_tokens = tuple(
        left + right
        for left, right in (
            ("win32com.client.", "Dispatch("),
            ("win32com.client.", "DispatchEx("),
            ("GetActive", "Object("),
            ("Exit", "App("),
        )
    )
    forbidden = [token for token in forbidden_tokens if token in source]
    target = attempt_root(run_id) if run_id else None
    passed = all(row["pass"] for row in bindings) and not forbidden and (target is None or not target.exists())
    return {
        "schema": "F3R2_V5_SOLAR_R2B_PRODUCTION_ROOT_BRANCH_PROTOCOL_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "run_id": run_id,
        "attempt_root": norm(target) if target else None,
        "attempt_absent": target is None or not target.exists(),
        "input_bindings": bindings,
        "forbidden_session_tokens": forbidden,
        "side_count": 2,
        "case_count": 2 * len(BETAS_DEG) * len(FLIPS) * len(PROTOCOLS),
        "betas_deg": list(BETAS_DEG),
        "flips": list(FLIPS),
        "protocols": list(PROTOCOLS),
        "write_scope": "NEW_WRITE_ONCE_99_TOOLS_PROBE_LOGS_ATTEMPT_ONLY",
        "production_input_open_mode": "READ_ONLY",
        "solidworks_touched": False,
        "verdict": "V5_SOLAR_R2B_PRODUCTION_ROOT_BRANCH_PROTOCOL_STATIC_PASS" if passed else "V5_SOLAR_R2B_PRODUCTION_ROOT_BRANCH_PROTOCOL_STATIC_HOLD",
    }


def transform_fact(component: Any) -> Dict[str, Any]:
    values = [float(value) for value in L1B.transform_array(component)]
    if len(values) != 16:
        raise ProbeError("TRANSFORM_SHAPE_FAIL", "component transform is not 16 values", {"count": len(values)})
    return {
        "transform16": values,
        "signed_rx_deg": math.degrees(math.atan2(values[5], values[4])),
        "translation_mm": [values[index] * 1000.0 for index in (9, 10, 11)],
    }


def transform_error(actual: Sequence[float], expected: Sequence[float]) -> Dict[str, float]:
    if len(actual) != 16 or len(expected) != 16:
        return {"translation_mm": float("inf"), "rotation_deg": float("inf")}
    translation = math.sqrt(sum((float(actual[index]) - float(expected[index])) ** 2 for index in (9, 10, 11))) * 1000.0
    ar = [[float(actual[column * 3 + row]) for column in range(3)] for row in range(3)]
    er = [[float(expected[column * 3 + row]) for column in range(3)] for row in range(3)]
    relative = [[sum(er[k][i] * ar[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    cosine = max(-1.0, min(1.0, (sum(relative[i][i] for i in range(3)) - 1.0) / 2.0))
    return {"translation_mm": translation, "rotation_deg": math.degrees(math.acos(cosine))}


def expected_transform(side: str, beta_deg: float) -> List[float]:
    left = list(R2B.state_transforms((90.0 - beta_deg, 90.0, 90.0))["M1"])
    if side == "L":
        return left
    # Strict XZ mirror, M*T*M: Rx(-beta)->Rx(+beta), ty->-ty.
    mirrored = list(left)
    mirrored[5] *= -1.0
    mirrored[7] *= -1.0
    mirrored[10] *= -1.0
    return mirrored


def mirror_branch_transform(side: str, expected: Sequence[float]) -> List[float]:
    result = list(expected)
    result[5] *= -1.0
    result[7] *= -1.0
    axis_y_m = (143.15 if side == "L" else -143.15) / 1000.0
    beta = abs(math.atan2(float(expected[5]), float(expected[4])))
    sign = 1.0 if math.atan2(float(expected[5]), float(expected[4])) >= 0.0 else -1.0
    opposite = -sign * beta
    c, s = math.cos(opposite), math.sin(opposite)
    result[4], result[5], result[7], result[8] = c, s, -s, c
    result[10] = axis_y_m - c * axis_y_m
    result[11] = -s * axis_y_m
    return result


def insert_at(sw: Any, model: Any, assembly: Any, path: Path, values: Sequence[float], fixed: bool, types: Any, pythoncom: Any) -> Any:
    opened = None
    title = str(L1B.value(model, "GetTitle"))
    doc_type = R2B.SW_DOC_ASSEMBLY if path.suffix.upper() == ".SLDASM" else R2B.SW_DOC_PART
    try:
        opened, _ = L1B.open_doc(sw, path, doc_type, True, types, pythoncom)
        L1B.activate(sw, title)
        raw = assembly.AddComponent5(str(path), 0, "", False, "", 0.0, 0.0, 0.0)
        if raw is None:
            raise ProbeError("ADD_COMPONENT5_FAIL", "typed AddComponent5 returned null", {"path": norm(path), "doc_type": doc_type})
        component = L1B.wrap(raw, "IComponent2", types, pythoncom)
        if not bool(component.SetTransformAndSolve3(L1B.make_transform(sw, values, types, pythoncom), True)):
            raise ProbeError("INSERT_TRANSFORM_FAIL", "cannot apply exact inserted occurrence transform", {"path": norm(path)})
        model.ClearSelection2(True)
        if not bool(component.Select4(False, None, False)):
            raise ProbeError("INSERT_SELECT_FAIL", "cannot select inserted occurrence", {"path": norm(path)})
        assembly.FixComponent() if fixed else assembly.UnfixComponent()
        model.ClearSelection2(True)
        if bool(L1B.value(component, "IsFixed")) != bool(fixed):
            raise ProbeError("INSERT_FIXED_STATE_FAIL", "inserted occurrence fixed-state differs", {"path": norm(path), "expected": fixed})
        return component
    finally:
        L1B.close_doc(sw, opened)
        L1B.activate(sw, title)


def component_ref_plane(component: Any, types: Any, pythoncom: Any) -> Tuple[Any, Dict[str, Any]]:
    planes: List[Any] = []
    raw = L1B.value(component, "FirstFeature")
    for _ in range(10000):
        if raw is None:
            break
        feature = L1B.wrap(raw, "IFeature", types, pythoncom)
        if str(L1B.value(feature, "GetTypeName2")) == "RefPlane":
            planes.append(feature)
        raw = L1B.value(feature, "GetNextFeature")
    names = {"Top Plane", "上视基准面"}
    named = [feature for feature in planes if str(L1B.value(feature, "Name")) in names]
    candidates = named or (planes[1:2] if len(planes) >= 2 else [])
    if len(candidates) != 1:
        raise ProbeError("ANGLE_PLANE_CARDINALITY_FAIL", "cannot resolve one production Top plane", {"component": str(L1B.value(component, "Name2")), "planes": [str(L1B.value(row, "Name")) for row in planes]})
    selected = candidates[0]
    return selected, {"component": str(L1B.value(component, "Name2")), "selected": str(L1B.value(selected, "Name")), "all_ref_planes": [str(L1B.value(row, "Name")) for row in planes]}


def angle_fact(feature: Any, types: Any, pythoncom: Any) -> Dict[str, Any]:
    raw_mate = L1B.value(feature, "GetSpecificFeature2")
    raw_definition = L1B.value(feature, "GetDefinition")
    if raw_mate is None or raw_definition is None:
        raise ProbeError("ANGLE_OBJECT_NULL", "angle feature lacks native mate/definition")
    mate = L1B.wrap(raw_mate, "IMate2", types, pythoncom)
    definition = L1B.wrap(raw_definition, "IAngleMateFeatureData", types, pythoncom)
    flip_sources: Dict[str, Any] = {}
    for label, obj, member in (("IMate2.Flipped", mate, "Flipped"), ("IAngleMateFeatureData.FlipDimension", definition, "FlipDimension")):
        try:
            flip_sources[label] = bool(L1B.value(obj, member))
        except Exception as exc:
            flip_sources[label] = {"unavailable": repr(exc)}
    dimension = R2B.angle_dimension(feature, types, pythoncom)
    return {
        "feature_name": str(L1B.value(feature, "Name")),
        "mate_type": int(L1B.value(mate, "Type")),
        "alignment": int(L1B.value(mate, "Alignment")),
        "flipped": bool(L1B.value(mate, "Flipped")),
        "flip_sources": flip_sources,
        "advanced": bool(L1B.value(definition, "IsAdvancedMate")),
        "angle_rad": float(L1B.value(definition, "Angle")),
        "minimum_angle_rad": float(L1B.value(definition, "MinimumAngle")),
        "maximum_angle_rad": float(L1B.value(definition, "MaximumAngle")),
        "dimension_full_name": str(L1B.value(dimension, "FullName")),
        "feature_health": L1B.feature_error_state(feature),
    }


def add_angle(model: Any, assembly: Any, clevis: Any, module: Any, flip: bool, name: str, types: Any, pythoncom: Any) -> Tuple[Any, Any, Dict[str, Any]]:
    before = L1B.mate_ledger(model, types, pythoncom)
    first_plane, first_fact = component_ref_plane(clevis, types, pythoncom)
    second_plane, second_fact = component_ref_plane(module, types, pythoncom)
    model.ClearSelection2(True)
    if not bool(first_plane.Select2(False, 1)) or not bool(second_plane.Select2(True, 1)):
        raise ProbeError("ANGLE_SELECTION_FAIL", "cannot select clevis/module Top planes")
    selected = int(L1B.selection_manager(model, types, pythoncom).GetSelectedObjectCount2(1))
    returned = assembly.AddMate3(SW_MATE_ANGLE, SW_ALIGN_ALIGNED, bool(flip), 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, math.pi / 2.0, 0.0, False, 0)
    model.ClearSelection2(True)
    created = L1B.resolve_created_mate(model, returned, before, SW_MATE_ANGLE, SW_ALIGN_ALIGNED, (clevis, module), selected, types, pythoncom)
    feature = R2B.rename_mate(model, created["feature_name"], name, types, pythoncom)
    dimension = R2B.angle_dimension(feature, types, pythoncom)
    return feature, dimension, {**created, "feature_name": name, "requested_flip": flip, "selection_order": "CLEVIS_PARENT_THEN_P1_MODULE_CHILD", "first_plane": first_fact, "second_plane": second_fact, "readback": angle_fact(feature, types, pythoncom)}


def build_physical_root(model: Any, assembly: Any, side: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    axis_y = 143.15 if side == "L" else -143.15
    roles = SIDE_INPUTS[side]
    module = R2B.component_by_path(model, roles["module"][0], types, pythoncom)
    lug = R2B.component_by_path(model, roles["u_lug"][0], types, pythoncom)
    pin = R2B.component_by_path(model, roles["pin"][0], types, pythoncom)
    spacer = R2B.component_by_path(model, SPACER_PATH, types, pythoncom)
    lug_cyl, lug_fact = L1B.cylinder_entity(lug, 4.2, axis_y, 2, types, pythoncom)
    pin_cyl, pin_fact = L1B.cylinder_entity(pin, 4.0, axis_y, 1, types, pythoncom)
    concentric = R2B.add_named_entity_mate(model, assembly, lug_cyl, pin_cyl, SW_MATE_CONCENTRIC, (lug, pin), f"PRB_{side}_ROOT_CONCENTRIC", types, pythoncom)
    module = R2B.component_by_path(model, roles["module"][0], types, pythoncom)
    lug = R2B.component_by_path(model, roles["u_lug"][0], types, pythoncom)
    spacer = R2B.component_by_path(model, SPACER_PATH, types, pythoncom)
    lug_face, lug_plane = L1B.plane_entity_x(lug, -75.0, types, pythoncom)
    spacer_face, spacer_plane = L1B.spacer_axial_plane_entity(spacer, axis_y, types, pythoncom)
    coincident = R2B.add_named_entity_mate(model, assembly, lug_face, spacer_face, SW_MATE_COINCIDENT, (lug, spacer), f"PRB_{side}_ROOT_COINCIDENT", types, pythoncom)
    return {"module": str(L1B.value(module, "Name2")), "nested_u_lug": file_fact(roles["u_lug"][0]), "lug_bore": lug_fact, "pin_bore": pin_fact, "lug_plane": lug_plane, "spacer_plane": spacer_plane, "concentric": concentric, "coincident": coincident}


def classify_branch(side: str, beta_deg: float, actual: Sequence[float], expected: Sequence[float]) -> Dict[str, Any]:
    mirror = mirror_branch_transform(side, expected)
    expected_error = transform_error(actual, expected)
    mirror_error = transform_error(actual, mirror)
    rx = math.degrees(math.atan2(float(actual[5]), float(actual[4])))
    signed_expected = -beta_deg if side == "L" else beta_deg
    signed_mirror = -signed_expected
    if expected_error["translation_mm"] <= TRANS_TOL_MM and expected_error["rotation_deg"] <= ROT_TOL_DEG and abs(rx - signed_expected) <= ANGLE_TOL_DEG:
        branch = "SIDE_EXPECTED"
    elif mirror_error["translation_mm"] <= TRANS_TOL_MM and mirror_error["rotation_deg"] <= ROT_TOL_DEG and abs(rx - signed_mirror) <= ANGLE_TOL_DEG:
        branch = "OPPOSITE_MIRROR"
    else:
        branch = "OTHER"
    return {"branch": branch, "signed_rx_deg": rx, "signed_expected_rx_deg": signed_expected, "signed_mirror_rx_deg": signed_mirror, "expected_error": expected_error, "mirror_error": mirror_error, "mirror_transform16": mirror}


def run_case(sw: Any, side: str, beta_deg: float, flip: bool, protocol: str, case_dir: Path, types: Any, pythoncom: Any) -> Dict[str, Any]:
    from win32com.client import VARIANT

    label = f"{side}_B{int(beta_deg):03d}_F{int(flip)}_{'FT' if protocol == 'FULL_TABLE_LIKE' else 'PS'}"
    target = case_dir / f"{label}.SLDASM"
    roles = SIDE_INPUTS[side]
    model = None
    try:
        model, assembly = R2B.new_assembly(sw, types, pythoncom)
        identity = L1B.transform_data((0.0, 0.0, 0.0))
        clevis = insert_at(sw, model, assembly, roles["clevis"][0], identity, True, types, pythoncom)
        insert_at(sw, model, assembly, roles["pin"][0], identity, True, types, pythoncom)
        spacer_transform = L1B.transform_data((-0.0755, (143.15 if side == "L" else -143.15) / 1000.0, 0.0))
        insert_at(sw, model, assembly, SPACER_PATH, spacer_transform, True, types, pythoncom)
        module = insert_at(sw, model, assembly, roles["module"][0], identity, False, types, pythoncom)
        physical = build_physical_root(model, assembly, side, types, pythoncom)
        clevis = R2B.component_by_path(model, roles["clevis"][0], types, pythoncom)
        module = R2B.component_by_path(model, roles["module"][0], types, pythoncom)
        feature_name = f"PRB_{label}_LIMIT_ANGLE_0_90"
        feature, dimension, creation = add_angle(model, assembly, clevis, module, flip, feature_name, types, pythoncom)
        pose_at_creation = transform_fact(module)
        configuration = L1B.wrap(L1B.value(L1B.value(model, "ConfigurationManager"), "ActiveConfiguration"), "IConfiguration", types, pythoncom)
        config_name = str(L1B.value(configuration, "Name"))
        config_array = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, [config_name])
        requested_rad = math.radians(beta_deg)
        expected = expected_transform(side, beta_deg)

        if protocol == "FULL_TABLE_LIKE":
            drive_status = int(dimension.SetSystemValue3(requested_rad, SW_SET_VALUE_IN_SPECIFIC_CONFIGS, config_array))
            if drive_status != 0 or not bool(model.ForceRebuild3(True)):
                raise ProbeError("FULL_TABLE_DIMENSION_DRIVE_FAIL", "dimension-first drive/rebuild failed", {"label": label, "status": drive_status})
            feature = R2B.mate_feature_map(model, types, pythoncom)[feature_name]
            pose_after_dimension_before_suppress = transform_fact(R2B.component_by_path(model, roles["module"][0], types, pythoncom))
            R2B.feature_suppression(feature, True)
            if not bool(model.EditRebuild3()):
                raise ProbeError("FULL_TABLE_SUPPRESS_REBUILD_FAIL", "rebuild after suppression failed", {"label": label})
        else:
            R2B.feature_suppression(feature, True)
            if not bool(model.EditRebuild3()):
                raise ProbeError("PER_STATE_SUPPRESS_REBUILD_FAIL", "rebuild after suppression failed", {"label": label})
            feature = R2B.mate_feature_map(model, types, pythoncom)[feature_name]
            dimension = R2B.angle_dimension(feature, types, pythoncom)
            drive_status = int(dimension.SetSystemValue3(requested_rad, SW_SET_VALUE_IN_SPECIFIC_CONFIGS, config_array))
            if drive_status != 0:
                raise ProbeError("PER_STATE_DIMENSION_DRIVE_FAIL", "suppressed dimension drive failed", {"label": label, "status": drive_status})
            pose_after_dimension_before_suppress = transform_fact(R2B.component_by_path(model, roles["module"][0], types, pythoncom))

        module = R2B.component_by_path(model, roles["module"][0], types, pythoncom)
        if not bool(module.SetTransformAndSolve3(L1B.make_transform(sw, expected, types, pythoncom), False)):
            raise ProbeError("EXPECTED_BRANCH_PREPOSITION_FAIL", "cannot preposition expected side branch", {"label": label})
        pose_before_restore = transform_fact(R2B.component_by_path(model, roles["module"][0], types, pythoncom))
        preposition_error = transform_error(pose_before_restore["transform16"], expected)
        feature = R2B.mate_feature_map(model, types, pythoncom)[feature_name]
        angle_before_restore = angle_fact(feature, types, pythoncom)
        R2B.feature_suppression(feature, False)
        if not bool(model.ForceRebuild3(True)):
            raise ProbeError("RESTORE_REBUILD_FAIL", "rebuild after angle restore failed", {"label": label})
        feature = R2B.mate_feature_map(model, types, pythoncom)[feature_name]
        module = R2B.component_by_path(model, roles["module"][0], types, pythoncom)
        pose_after_restore = transform_fact(module)
        final_angle = angle_fact(feature, types, pythoncom)
        final_dimension = R2B.angle_dimension(feature, types, pythoncom)
        final_readback = float(final_dimension.GetSystemValue2(config_name))
        branch = classify_branch(side, beta_deg, pose_after_restore["transform16"], expected)
        L1B.set_properties(model, {"ARTIFACT_CLASS": "DIAGNOSTIC_REAL_PRODUCTION_ROOT_BRANCH_NON_RELEASE", "PRODUCTION_USE": "PROHIBITED", "CASE": label, "SIDE": side, "PROTOCOL": protocol})
        saved = L1B.save_as(model, target)
        return {
            "label": label,
            "side": side,
            "beta_deg": beta_deg,
            "requested_flip": flip,
            "protocol": protocol,
            "physical_root_mates": physical,
            "angle_creation": creation,
            "configuration": config_name,
            "typed_drive_status": drive_status,
            "requested_driver_rad": requested_rad,
            "pose_at_angle_creation_zero": pose_at_creation,
            "pose_after_dimension_before_suppress": pose_after_dimension_before_suppress,
            "pose_before_restore_expected_branch": pose_before_restore,
            "preposition_error": preposition_error,
            "angle_before_restore": angle_before_restore,
            "pose_after_restore": pose_after_restore,
            "expected_transform16": expected,
            "solver_branch": branch,
            "final_driver_readback_rad": final_readback,
            "final_angle_readback": final_angle,
            "assembly": saved,
            "case_complete": True,
        }
    finally:
        L1B.close_doc(sw, model)


def winner_summary(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for side in ("L", "R"):
        side_result: Dict[str, Any] = {}
        for protocol in PROTOCOLS:
            complete = [row for row in rows if row.get("case_complete") and row.get("side") == side and row.get("protocol") == protocol]
            per_flip: Dict[str, Any] = {}
            winners: List[bool] = []
            for flip in FLIPS:
                subset = [row for row in complete if row.get("requested_flip") is flip]
                all_expected = len(subset) == len(BETAS_DEG) and all(row.get("solver_branch", {}).get("branch") == "SIDE_EXPECTED" for row in subset)
                per_flip[str(flip).lower()] = {"case_count": len(subset), "branches": {str(row["beta_deg"]): row["solver_branch"]["branch"] for row in subset}, "all_three_side_expected": all_expected}
                if all_expected:
                    winners.append(flip)
            side_result[protocol] = {"flip_matrix": per_flip, "winner_flips": winners, "unique_winner": winners[0] if len(winners) == 1 else None}
        result[side] = side_result
    return result


def execute(run_id: str, expected_pid: int) -> Dict[str, Any]:
    audit = static_audit(run_id)
    if audit["verdict"] != "V5_SOLAR_R2B_PRODUCTION_ROOT_BRANCH_PROTOCOL_STATIC_PASS":
        raise ProbeError("STATIC_AUDIT_HOLD", "production root protocol probe static audit is not PASS", audit)
    root = attempt_root(run_id)
    mutex = R2B.acquire_process_mutex()
    sw = pythoncom = None
    root_created = False
    input_pre = {norm(path): file_fact(path) for path in input_bindings()}
    try:
        root.mkdir(parents=False, exist_ok=False)
        root_created = True
        sw, types, pythoncom, session = L1B.attach_empty_session(expected_pid)
        case_dir = root / "cad/cases"
        case_dir.mkdir(parents=True, exist_ok=False)
        rows: List[Dict[str, Any]] = []
        for side in ("L", "R"):
            for beta_deg in BETAS_DEG:
                for flip in FLIPS:
                    for protocol in PROTOCOLS:
                        try:
                            rows.append(run_case(sw, side, beta_deg, flip, protocol, case_dir, types, pythoncom))
                        except Exception as exc:
                            rows.append({"side": side, "beta_deg": beta_deg, "requested_flip": flip, "protocol": protocol, "case_complete": False, "error_code": getattr(exc, "code", "UNHANDLED_CASE_EXCEPTION"), "error": str(exc), "detail": getattr(exc, "detail", {}), "traceback": traceback.format_exc()})
        L1B.close_owned_documents(sw)
        if int(L1B.value(sw, "GetDocumentCount")) != 0 or L1B.value(sw, "ActiveDoc") is not None:
            raise ProbeError("SESSION_NOT_EMPTY", "probe-owned documents remain open")
        input_post = {norm(path): file_fact(path) for path in input_bindings()}
        input_hash_stability = {path: {"pre": input_pre[path], "post": input_post[path], "pass": input_pre[path] == input_post[path]} for path in input_pre}
        completed = [row for row in rows if row.get("case_complete")]
        winners = winner_summary(rows)
        all_stable = all(row["pass"] for row in input_hash_stability.values())
        result = {
            "schema": "F3R2_V5_SOLAR_R2B_REAL_PRODUCTION_ROOT_BRANCH_PROTOCOL_MATRIX_V1",
            "timestamp_utc": utc_now(),
            "run_id": run_id,
            "attempt_root": norm(root),
            "classification": "DIAGNOSTIC_REAL_PRODUCTION_ROOT_BRANCH_NON_RELEASE",
            "production_use": "PROHIBITED",
            "session": session,
            "input_hash_stability": input_hash_stability,
            "input_pre_equals_post": all_stable,
            "geometry_contract": "FROZEN_SIDE_CLEVIS+PIN+SPACER; REAL_P5A5_P1_RIGID_MODULE_WITH_NESTED_ACCEPTED_U_LUG; PRODUCTION_ROOT_CONCENTRIC+COINCIDENT+TOP_PLANE_ADVANCED_ANGLE",
            "angle_selection_order": "CLEVIS_PARENT_THEN_P1_MODULE_CHILD",
            "case_count_planned": 24,
            "case_count_complete": len(completed),
            "per_side_root_flip_winners": winners,
            "cases": rows,
            "verdict": "V5_SOLAR_R2B_REAL_PRODUCTION_ROOT_BRANCH_PROTOCOL_MATRIX_COMPLETE" if len(completed) == 24 and all_stable else "V5_SOLAR_R2B_REAL_PRODUCTION_ROOT_BRANCH_PROTOCOL_MATRIX_INCOMPLETE",
        }
        write_json_once(root / "RESULT.json", result)
        return result
    except Exception as exc:
        if sw is not None:
            try:
                L1B.close_owned_documents(sw)
            except Exception:
                pass
        if root_created:
            write_json_once(root / f"FAIL_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')}.json", {"schema": "F3R2_V5_SOLAR_R2B_REAL_PRODUCTION_ROOT_BRANCH_PROTOCOL_FAILURE_V1", "timestamp_utc": utc_now(), "run_id": run_id, "error_code": getattr(exc, "code", "UNHANDLED_EXCEPTION"), "error": str(exc), "detail": getattr(exc, "detail", {}), "traceback": traceback.format_exc(), "verdict": "V5_SOLAR_R2B_REAL_PRODUCTION_ROOT_BRANCH_PROTOCOL_FAIL"})
        raise
    finally:
        if pythoncom is not None:
            pythoncom.CoUninitialize()
        R2B.release_process_mutex(mutex)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="filesystem-only audit; never touches SOLIDWORKS")
    audit.add_argument("--run-id")
    run = commands.add_parser("run", help="attach to one explicit empty PID and write one new scratch attempt")
    run.add_argument("--run-id", required=True)
    run.add_argument("--expected-pid", required=True, type=int)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parser().parse_args(argv)
    try:
        payload = static_audit(args.run_id) if args.command == "audit" else execute(args.run_id, args.expected_pid)
        print(json.dumps({"verdict": payload["verdict"], "run_id": payload.get("run_id"), "attempt_root": payload.get("attempt_root")}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if payload["verdict"].endswith(("PASS", "COMPLETE")) else 2
    except Exception as exc:
        print(json.dumps({"error_code": getattr(exc, "code", "UNHANDLED_EXCEPTION"), "error": str(exc), "detail": getattr(exc, "detail", {}), "verdict": "V5_SOLAR_R2B_REAL_PRODUCTION_ROOT_BRANCH_PROTOCOL_HOLD"}, ensure_ascii=False, indent=2, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
