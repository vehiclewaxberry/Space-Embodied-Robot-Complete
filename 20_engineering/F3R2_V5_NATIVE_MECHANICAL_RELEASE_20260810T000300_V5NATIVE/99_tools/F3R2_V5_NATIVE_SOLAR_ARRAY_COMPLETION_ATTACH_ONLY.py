#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 solar array completion loop "LOOP-SOLAR-B" (attach-only).

Closes the residual gaps registered in
``V5_SOLAR_ARRAY_RESIDUAL_GAPS_20260810.md`` against the candidate solar build
receipt ``13_validation/V5_SOLAR_ARRAY_NATIVE_RECEIPT_20260810T135905.775293Z.json``:

* F-3 / R16: NON-resume full re-verification.  Each side assembly is opened,
  every one of the 7 solar configurations is shown, each panel pose is
  re-applied from the expected pose table and read back within tolerance, then
  the saved assembly is cold-reopened read-only and all 7x3 poses are verified
  again.  A fresh PASS receipt proves config-internal poses were exercised.
* R4: per-state register ``04_configurations/V5_SOLAR_STATE_REGISTER.csv``
  (write-once) generated from the verified pose table.  collision_state /
  camera_visibility / arm_clearance_mm stay ``PENDING_LOOP2``; no values are
  fabricated.
* R7: as-built FAIL-config poses are preserved unchanged and registered
  explicitly as CANDIDATE intermediate-angle semantics with a mapping note to
  the authoritative single-panel L_FAIL(0/90)/R_FAIL(90/0) (proposal P-3).
* R6/R8/R9: placeholder-level native parts SOLAR_HARNESS_EXIT_{L,R},
  SOLAR_STOW_PAD_{L,R}, SOLAR_DEPLOY_STOP_{L,R}_H{1,2} (identity custom
  properties only, no UNKNOWN/HOLD-listed parameter values), inserted into the
  side assemblies in fixed non-configuration-specific reference poses.
* R2: hinge-axis semantics extended as text custom properties
  (HINGE_AXIS_INBOARD / HINGE_AXIS_OUTBOARD) to every panel, recorded as
  PARTIAL semantics pending Loop1B's hinge-mate pattern.

SolidWorks API transforms are metres; the build script's millimetre pose
geometry is divided by 1000 before application.  Any drift between the
as-found transform and the expected table is recorded per panel/config and
corrected explicitly (never silently).

CLI: ``audit`` (default, filesystem-only, never attaches) / ``execute``.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple


sys.dont_write_bytecode = True
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import F3R2_V5_SESSION_BINDING as sbin
import F3R2_V5_MEMORY_OVERRIDE as mo
import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base
import F3R2_V5_NATIVE_LOOP1D_HDRM_CAMERA_HARNESS_ATTACH_ONLY as loop1d
import F3R2_V5_NATIVE_SOLAR_ARRAY_BUILD as solar


RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = RUN_ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
SOLAR_DIR = RUN_ROOT / "01_native_parts/solar_array"
SUBASM_DIR = RUN_ROOT / "02_native_subassemblies"
TOP_DIR = RUN_ROOT / "03_top_assembly"
CONFIG_DIR = RUN_ROOT / "04_configurations"
VALIDATION = RUN_ROOT / "13_validation"
AUTHORITY = RUN_ROOT / "00_authority"
REGISTER = CONFIG_DIR / "V5_SOLAR_STATE_REGISTER.csv"

PART_TEMPLATE = Path(r"C:\ProgramData\SolidWorks\SOLIDWORKS 2024\templates\gb_part.prtdot")

POSE_TOLERANCE_M = 2.0e-7
SESSION_DEFAULT_PID = 42276

PANEL_LEN_MM = solar.PANEL_LEN_MM
ROOT_HINGE_Y_MM = solar.ROOT_Y_L  # 143.15, sign applied per side
HINGE_AXIS_Y_MM = {1: ROOT_HINGE_Y_MM, 2: ROOT_HINGE_Y_MM + PANEL_LEN_MM, 3: ROOT_HINGE_Y_MM + 2.0 * PANEL_LEN_MM}

NON_CLAIMS = [
    "NOT_FINAL_NATIVE_BASELINE",
    "NOT_FLIGHT_READY",
    "NO_SOLAR_CELL_DETAIL",
    "NO_L0_MASS_OVERRIDE",
    "CANDIDATE_ANGLES_NOT_AUTHORITATIVE",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def posix(path: Path) -> str:
    return solar.posix(path)


def sha256(path: Path) -> str:
    return solar.sha256(path)


def file_fact(path: Path) -> Dict[str, Any]:
    return solar.file_fact(path)


def json_safe(value: Any) -> Any:
    return solar.json_safe(value)


def axis_text(sign: float, y_mm: float) -> str:
    return f"X@Y={sign * y_mm:+.2f}mm Z=0"


def placeholder_specs() -> Dict[str, Dict[str, Any]]:
    specs: Dict[str, Dict[str, Any]] = {}
    for side in ("L", "R"):
        sign = 1.0 if side == "L" else -1.0
        specs[f"SOLAR_HARNESS_EXIT_{side}"] = {
            "side": side,
            "target": SOLAR_DIR / f"SOLAR_HARNESS_EXIT_{side}.SLDPRT",
            "geometry": {"kind": "cylinder", "radius_mm": 4.5, "depth_mm": 20.0},
            "expected_sorted_mm": [9.0, 9.0, 20.0],
            "reference_pose_mm": [0.0, sign * 110.0, 10.0],
            "properties": {
                "FUNCTION": "SOLAR_HARNESS_EXIT_OD9_PLACEHOLDER",
                "SIDE": side,
                "INTERFACE_CLASS": "OD9_HARNESS_EXIT_PER_SIDE",
                "INTERFACE_STATUS": "CANDIDATE_PLACEHOLDER",
                "MASS_SOURCE": "EXTERNAL_MECHANICAL_ONLY",
                "MIN_BEND_RADIUS_NATIVE_BREP_VERIFICATION": "PENDING_LOOP2",
            },
        }
        specs[f"SOLAR_STOW_PAD_{side}"] = {
            "side": side,
            "target": SOLAR_DIR / f"SOLAR_STOW_PAD_{side}.SLDPRT",
            "geometry": {"kind": "box", "width_mm": 30.0, "height_mm": 30.0, "depth_mm": 4.0},
            "expected_sorted_mm": [4.0, 30.0, 30.0],
            "reference_pose_mm": [0.0, sign * 116.15, -2.0],
            "properties": {
                "FUNCTION": "SOLAR_STOW_PAD_PLACEHOLDER",
                "SIDE": side,
                "INTERFACE_STATUS": "CANDIDATE_PLACEHOLDER",
                "STOW_CONTACT_SEMANTICS": "REGISTERED_SEPARATELY_FROM_G07_G08_MID_PER_REQU_2.3",
                "STOW_PRELOAD": "NO_VALUE_UNKNOWN_HOLD",
                "MASS_SOURCE": "EXTERNAL_MECHANICAL_ONLY",
            },
        }
        for hinge in (1, 2):
            axis_y = ROOT_HINGE_Y_MM + hinge * PANEL_LEN_MM
            specs[f"SOLAR_DEPLOY_STOP_{side}_H{hinge}"] = {
                "side": side,
                "target": SOLAR_DIR / f"SOLAR_DEPLOY_STOP_{side}_H{hinge}.SLDPRT",
                "geometry": {"kind": "box", "width_mm": 12.0, "height_mm": 10.0, "depth_mm": 6.0},
                "expected_sorted_mm": [6.0, 10.0, 12.0],
                "reference_pose_mm": [0.0, sign * axis_y, 0.0],
                "properties": {
                    "FUNCTION": "SOLAR_DEPLOY_STOP_PLACEHOLDER",
                    "SIDE": side,
                    "HINGE_REF": f"INTER_PANEL_HINGE_{side}_H{hinge}",
                    "HINGE_AXIS": axis_text(sign, axis_y),
                    "ONE_STOP_PER_HINGE": "PLACEHOLDER_COUNT_SATISFIED",
                    "STOP_ANGLE": "NO_VALUE_UNKNOWN_HOLD_PER_REQU_3",
                    "STOP_CONTACT_NATIVE_BREP_EVIDENCE": "PENDING_LOOP2",
                    "MASS_SOURCE": "EXTERNAL_MECHANICAL_ONLY",
                },
            }
    return specs


def expected_transform_m(side: str, index: int, deployed: bool) -> List[float]:
    """Expected pose: build-script rotation (unitless) + mm translation scaled to metres."""
    data = solar.panel_pose(side, index, deployed)
    return list(data[:9]) + [float(value) / 1000.0 for value in data[9:12]] + list(data[12:])


def reference_transform_m(pose_mm: Sequence[float]) -> List[float]:
    return [
        1.0, 0.0, 0.0,
        0.0, 1.0, 0.0,
        0.0, 0.0, 1.0,
        float(pose_mm[0]) / 1000.0, float(pose_mm[1]) / 1000.0, float(pose_mm[2]) / 1000.0,
        1.0, 0.0, 0.0, 0.0,
    ]


def component_transform_readback(component: Any) -> List[float]:
    raw = base.value(component, "Transform2")
    if raw is None:
        raise base.GateError("COMPONENT_TRANSFORM_NULL", "component has no Transform2", {"name2": str(base.value(component, "Name2"))})
    data = [float(value) for value in base.as_list(base.value(raw, "ArrayData"))]
    if len(data) != 16:
        raise base.GateError("COMPONENT_TRANSFORM_SHAPE_FAIL", "Transform2 ArrayData is not 16 elements", {"name2": str(base.value(component, "Name2"))})
    return data


def max_abs_delta(actual: Sequence[float], expected: Sequence[float]) -> float:
    return max(abs(float(a) - float(e)) for a, e in zip(actual, expected))


def transforms_match(actual: Sequence[float], expected: Sequence[float]) -> bool:
    return len(actual) == len(expected) and max_abs_delta(actual, expected) <= POSE_TOLERANCE_M


def close_all_documents(sw: Any) -> None:
    try:
        docs = [doc for doc in (base.as_list(base.value(sw, "GetDocuments")) or [])]
        for doc in docs:
            try:
                sw.CloseDoc(str(base.value(doc, "GetTitle")))
            except Exception:
                pass
    except Exception:
        pass


def set_identity_properties(model: Any, properties: Dict[str, str]) -> None:
    manager = model.Extension.CustomPropertyManager("")
    for name, value in properties.items():
        if int(manager.Add3(str(name), 30, str(value), 2)) < 0:
            raise base.GateError("CUSTOM_PROPERTY_FAIL", "cannot set native custom property", {"name": name, "value": value})


def save_in_place(model: Any, target: Path, label: str) -> None:
    returned = model.Save3(1, 0, 0)
    if not isinstance(returned, tuple) or len(returned) < 3:
        raise base.GateError(f"{label}_SAVE_RETURN_SHAPE_FAIL", "typed Save3 did not return api/errors/warnings", {"returned": repr(returned)})
    ok, outs = base.unpack(returned)
    errors = int(outs[0]) if len(outs) > 0 else None
    warnings = int(outs[1]) if len(outs) > 1 else None
    if not bool(ok) or errors != 0 or warnings != 0:
        raise base.GateError(f"{label}_SAVE_FAIL", "Save3 did not finalize the native document", {"ok": bool(ok), "errors": errors, "warnings": warnings, "target": posix(target)})


def update_panel_hinge_semantics(sw: Any, types: Any, pythoncom: Any, name: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """R2: extend the as-built HINGE_AXIS text convention to inter-panel hinges."""
    target = Path(spec["target"])
    side = str(spec["properties"]["SIDE"])
    index = int(spec["properties"]["PANEL_INDEX"])
    sign = 1.0 if side == "L" else -1.0
    pre = file_fact(target)
    raw, errors, warnings = loop1d.unpack_document(sw.OpenDoc6(str(target), 1, 1, "", 0, 0), "OPEN_PANEL_EDIT")
    if raw is None or errors != 0 or warnings not in (0, 128):
        raise base.GateError("OPEN_PANEL_EDIT_FAIL", "cannot open panel for identity property extension", {"name": name, "errors": errors, "warnings": warnings})
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    title = str(base.value(model, "GetTitle"))
    try:
        manager = model.Extension.CustomPropertyManager("")
        existing = None
        try:
            got = manager.Get5("HINGE_AXIS", False)
            existing = got[0] if isinstance(got, tuple) else got
        except Exception:
            existing = None
        inboard = axis_text(sign, HINGE_AXIS_Y_MM[index])
        outboard = axis_text(sign, HINGE_AXIS_Y_MM[index + 1]) if index < 3 else "NONE_TERMINAL_PANEL"
        written = {
            "HINGE_AXIS_INBOARD": inboard,
            "HINGE_AXIS_OUTBOARD": outboard,
            "HINGE_SEMANTICS": "PARTIAL_TEXT_ONLY_PENDING_LOOP1B_HINGE_MATE_PATTERN",
            "HINGE_MATE_STATE": "NO_KINEMATIC_MATE_YET",
        }
        set_identity_properties(model, written)
        save_in_place(model, target, "PANEL_SEMANTICS_SAVE")
    finally:
        try:
            sw.CloseDoc(title)
        except Exception:
            pass
    if int(base.value(sw, "GetDocumentCount")) != 0:
        raise base.GateError("PANEL_SEMANTICS_CLEANUP_FAIL", "panel edit left documents open", {"name": name})
    cold = loop1d.verify_part_cold(sw, types, pythoncom, name, spec)
    post = file_fact(target)
    return {
        "name": name,
        "pre_sha256": pre["sha256"],
        "post_sha256": post["sha256"],
        "hash_changed_by_additive_identity_properties": pre["sha256"] != post["sha256"],
        "existing_hinge_axis_property": existing,
        "hinge_axis_inboard": inboard,
        "hinge_axis_outboard": outboard,
        "hinge_semantics": "PARTIAL_TEXT_ONLY_PENDING_LOOP1B_HINGE_MATE_PATTERN",
        "geometry_modified": False,
        "cold": cold,
    }


def build_placeholder_part(sw: Any, types: Any, pythoncom: Any, name: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    target = Path(spec["target"])
    if target.exists():
        cold = loop1d.verify_part_cold(sw, types, pythoncom, name, spec)
        return {"name": name, "side": spec["side"], "resumed_from_existing": True, "cold": cold}
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = sw.NewDocument(str(PART_TEMPLATE), 0, 0.0, 0.0)
    if raw is None:
        raw = base.value(sw, "ActiveDoc")
    if raw is None:
        raise base.GateError("PLACEHOLDER_NEW_DOCUMENT_FAIL", "cannot create native part document", {"name": name})
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    owned_title = str(base.value(model, "GetTitle"))
    try:
        primitive = loop1d.create_native_primitive(model, spec["geometry"])
        set_identity_properties(model, {
            "PartNumber": f"SEI-MECH-V5-{name}",
            "Description": name.replace("_", " "),
            "REPRESENTATION_LAYER": "LOOP_SOLAR_B_CANDIDATE_PLACEHOLDER",
            "FLIGHT_QUALIFICATION": "HOLD",
            **{str(key): str(value) for key, value in spec["properties"].items()},
        })
        save = base.save_native_part(model, target)
        saved_path = Path(str(base.value(model, "GetPathName"))).resolve()
        if saved_path != target.resolve():
            raise base.GateError("PLACEHOLDER_SAVE_PATH_READBACK_FAIL", "saved part path readback drifted", {"actual": str(saved_path), "expected": str(target)})
    finally:
        try:
            sw.CloseDoc(str(base.value(model, "GetTitle")))
        except Exception:
            sw.CloseDoc(owned_title)
    if int(base.value(sw, "GetDocumentCount")) != 0:
        raise base.GateError("PLACEHOLDER_CLOSE_FAIL", "placeholder part remained open before cold verification", {"name": name})
    cold = loop1d.verify_part_cold(sw, types, pythoncom, name, spec)
    return {"name": name, "side": spec["side"], "primitive": primitive, "save": save, "cold": cold}


def open_side_assembly_edit(sw: Any, target: Path, types: Any, pythoncom: Any) -> Tuple[Any, Any, Any]:
    raw, errors, warnings = loop1d.unpack_document(sw.OpenDoc6(str(target), 2, 1, "", 0, 0), "OPEN_SIDE_ASSEMBLY_EDIT")
    if raw is None or errors != 0 or warnings not in (0, 128):
        raise base.GateError("OPEN_SIDE_ASSEMBLY_EDIT_FAIL", "cannot open side assembly for completion", {"target": posix(target), "errors": errors, "warnings": warnings})
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    manager = base.wrap(base.value(model, "ConfigurationManager"), "IConfigurationManager", types, pythoncom)
    names = [str(name) for name in base.as_list(base.value(model, "GetConfigurationNames"))]
    if set(names) != set(solar.CONFIGS):
        raise base.GateError("SIDE_ASSEMBLY_CONFIG_SET_FAIL", "side assembly configuration set drifted", {"target": posix(target), "configurations": names})
    return model, assembly, manager


def placeholder_components(model: Any, assembly: Any, side: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    wanted = {name for name, spec in placeholder_specs().items() if spec["side"] == side}
    found: Dict[str, Any] = {}
    for raw in base.as_list(assembly.GetComponents(False)):
        component = base.wrap(raw, "IComponent2", types, pythoncom)
        name = Path(str(base.value(component, "GetPathName"))).stem
        if name in wanted:
            found[name] = component
    missing = sorted(wanted - set(found))
    if missing:
        raise base.GateError("PLACEHOLDER_SET_INCOMPLETE", "side assembly is missing placeholder components", {"side": side, "missing": missing})
    return found


def insert_placeholder(sw: Any, model: Any, assembly: Any, spec: Dict[str, Any], types: Any, pythoncom: Any) -> Dict[str, Any]:
    name = Path(str(spec["target"])).stem
    target = Path(spec["target"])
    if not target.is_file():
        raise base.GateError("PLACEHOLDER_PART_MISSING", "placeholder part must exist before assembly insertion", {"name": name})
    title = str(base.value(model, "GetTitle"))
    part = None
    part_title: Optional[str] = None
    try:
        raw_part, errors, warnings = loop1d.unpack_document(sw.OpenDoc6(str(target), 1, 3, "", 0, 0), "OPEN_PLACEHOLDER")
        if raw_part is not None:
            part = base.wrap(raw_part, "IModelDoc2", types, pythoncom)
            part_title = str(base.value(part, "GetTitle"))
        if raw_part is None or errors != 0 or warnings not in (0, 128):
            raise base.GateError("OPEN_PLACEHOLDER_FAIL", "placeholder preload was not a clean read-only open", {"name": name, "errors": errors, "warnings": warnings})
        loop1d.activate(sw, title)
        raw_component = assembly.AddComponent5(str(target), 0, "", False, "", 0.0, 0.0, 0.0)
        if raw_component is None:
            raise base.GateError("PLACEHOLDER_ADD_COMPONENT_FAIL", "AddComponent5 returned null", {"name": name})
        component = base.wrap(raw_component, "IComponent2", types, pythoncom)
        pose = reference_transform_m(spec["reference_pose_mm"])
        if not bool(component.SetTransformAndSolve3(solar.make_transform(sw, pose, types, pythoncom), True)):
            raise base.GateError("PLACEHOLDER_TRANSFORM_FAIL", "placeholder reference pose could not be solved", {"name": name})
        if not bool(model.EditRebuild3()):
            raise base.GateError("PLACEHOLDER_REBUILD_FAIL", "rebuild failed after placeholder insert", {"name": name})
        model.ClearSelection2(True)
        if not bool(component.Select4(False, None, False)):
            raise base.GateError("PLACEHOLDER_SELECT_FAIL", "cannot select placeholder for fixed-state assignment", {"name": name})
        assembly.FixComponent()
        model.ClearSelection2(True)
        if not bool(base.value(component, "IsFixed")):
            raise base.GateError("PLACEHOLDER_FIXED_STATE_FAIL", "placeholder did not remain fixed", {"name": name})
        readback = component_transform_readback(component)
        if not transforms_match(readback, pose):
            raise base.GateError("PLACEHOLDER_TRANSFORM_READBACK_FAIL", "placeholder reference pose readback drifted", {"name": name, "expected": pose, "actual": readback})
        return {
            "name": name,
            "inserted": True,
            "fixed": True,
            "configuration_specific": False,
            "reference_pose_mm": list(spec["reference_pose_mm"]),
            "reference_pose_status": "CANDIDATE_PLACEHOLDER_REFERENCE_POSE",
            "readback_max_abs_delta_m": max_abs_delta(readback, pose),
        }
    finally:
        if part_title:
            try:
                sw.CloseDoc(part_title)
            except Exception:
                pass
        loop1d.activate(sw, title)


def apply_and_verify_config_poses(sw: Any, model: Any, assembly: Any, manager: Any, side: str, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    """F-3 closure: apply + read back every panel pose in every configuration."""
    rows: List[Dict[str, Any]] = []
    pose_map = solar.config_pose_map(side)
    for config in solar.CONFIGS:
        if not bool(model.ShowConfiguration2(config)):
            raise base.GateError("SHOW_CONFIGURATION_FAIL", "cannot show solar configuration", {"side": side, "configuration": config})
        active = str(base.value(base.wrap(base.value(manager, "ActiveConfiguration"), "IConfiguration", types, pythoncom), "Name"))
        if active != config:
            raise base.GateError("SHOW_CONFIGURATION_FAIL", "active configuration readback drifted", {"side": side, "configuration": config, "active": active})
        if not bool(model.EditRebuild3()):
            raise base.GateError("CONFIG_REBUILD_FAIL", "rebuild failed after show configuration", {"side": side, "configuration": config})
        fresh = solar.fresh_panels(model, assembly, side, types, pythoncom)
        config_rows: Dict[int, Dict[str, Any]] = {}
        for index, component in fresh.items():
            if bool(base.value(component, "IsFixed")):
                model.ClearSelection2(True)
                if not bool(component.Select4(False, None, False)):
                    raise base.GateError("PANEL_SELECT_FAIL", "cannot select panel for unfix", {"side": side, "configuration": config, "panel": index})
                assembly.UnfixComponent()
                model.ClearSelection2(True)
            deployed = bool(pose_map[config][int(index)])
            expected = expected_transform_m(side, int(index), deployed)
            as_found = component_transform_readback(component)
            found_ok = transforms_match(as_found, expected)
            if not bool(component.SetTransformAndSolve3(solar.make_transform(sw, expected, types, pythoncom), False)):
                raise base.GateError("CONFIG_POSE_APPLY_FAIL", "expected pose transform could not be solved", {"side": side, "configuration": config, "panel": int(index)})
            config_rows[int(index)] = {
                "configuration": config,
                "panel": int(index),
                "deployed": deployed,
                "angle_deg": 90 if deployed else 0,
                "as_found_transform_m": as_found,
                "as_found_within_tolerance": found_ok,
                "as_found_max_abs_delta_m": max_abs_delta(as_found, expected),
                "pose_corrected_by_this_run": not found_ok,
                "expected_transform_m": expected,
            }
        if not bool(model.ForceRebuild3(True)):
            raise base.GateError("CONFIG_FORCE_REBUILD_FAIL", "force rebuild failed after pose application", {"side": side, "configuration": config})
        verified = solar.fresh_panels(model, assembly, side, types, pythoncom)
        for index, component in verified.items():
            readback = component_transform_readback(component)
            expected = config_rows[int(index)]["expected_transform_m"]
            if not transforms_match(readback, expected):
                raise base.GateError("CONFIG_POSE_VERIFY_FAIL", "applied pose readback is outside tolerance", {"side": side, "configuration": config, "panel": int(index), "expected": expected, "actual": readback})
            config_rows[int(index)]["verified_transform_m"] = readback
            config_rows[int(index)]["verified_max_abs_delta_m"] = max_abs_delta(readback, expected)
            config_rows[int(index)]["verified_within_tolerance"] = True
        placeholders = placeholder_components(model, assembly, side, types, pythoncom)
        placeholder_state = {}
        for name, component in sorted(placeholders.items()):
            placeholder_state[name] = {
                "fixed": bool(base.value(component, "IsFixed")),
                "suppressed": bool(base.value(component, "IsSuppressed")),
            }
            if placeholder_state[name]["suppressed"]:
                raise base.GateError("PLACEHOLDER_SUPPRESSED", "placeholder must be resolved in every configuration", {"side": side, "configuration": config, "placeholder": name})
        for index in sorted(config_rows):
            config_rows[index]["placeholder_state"] = placeholder_state
            rows.append(config_rows[index])
    if not bool(model.ShowConfiguration2("SOLAR_DEPLOYED_NOMINAL")):
        raise base.GateError("RESTORE_NOMINAL_FAIL", "cannot restore SOLAR_DEPLOYED_NOMINAL", {"side": side})
    return rows


def complete_side_assembly(sw: Any, types: Any, pythoncom: Any, side: str) -> Dict[str, Any]:
    target = SUBASM_DIR / f"{side}_SOLAR_ARRAY.SLDASM"
    if not target.is_file():
        raise base.GateError("SIDE_ASSEMBLY_MISSING", "candidate side assembly does not exist", {"target": posix(target)})
    pre = file_fact(target)
    model = assembly = None
    try:
        model, assembly, manager = open_side_assembly_edit(sw, target, types, pythoncom)
        inserted: List[Dict[str, Any]] = []
        existing_names = set()
        for raw in base.as_list(assembly.GetComponents(True)):
            existing_names.add(Path(str(base.value(base.wrap(raw, "IComponent2", types, pythoncom), "GetPathName"))).stem)
        for name, spec in placeholder_specs().items():
            if spec["side"] != side:
                continue
            if name in existing_names:
                inserted.append({"name": name, "inserted": False, "already_present": True})
            else:
                inserted.append(insert_placeholder(sw, model, assembly, spec, types, pythoncom))
        pose_rows = apply_and_verify_config_poses(sw, model, assembly, manager, side, types, pythoncom)
        if not bool(model.ForceRebuild3(True)):
            raise base.GateError("PRE_SAVE_REBUILD_FAIL", "full rebuild failed before in-place save", {"side": side})
        save_in_place(model, target, "SIDE_ASSEMBLY_SAVE")
    finally:
        close_all_documents(sw)
    if int(base.value(sw, "GetDocumentCount")) != 0:
        raise base.GateError("SIDE_ASSEMBLY_CLEANUP_FAIL", "completion left documents open", {"side": side, "document_count": int(base.value(sw, "GetDocumentCount"))})
    post = file_fact(target)
    return {
        "side": side,
        "target": posix(target),
        "resumed_from_existing": False,
        "non_resume_full_reverification": True,
        "pre_sha256": pre["sha256"],
        "post_sha256": post["sha256"],
        "assembly_modified": pre["sha256"] != post["sha256"],
        "placeholder_components": inserted,
        "configuration_pose_rows": pose_rows,
        "configurations_exercised": len(solar.CONFIGS),
        "panel_poses_applied_and_verified": len(pose_rows),
    }


def cold_verify_side(sw: Any, types: Any, pythoncom: Any, side: str) -> Dict[str, Any]:
    """Read-only cold reopen: prove the saved poses persist in every configuration."""
    target = SUBASM_DIR / f"{side}_SOLAR_ARRAY.SLDASM"
    raw, errors, warnings = loop1d.unpack_document(sw.OpenDoc6(str(target), 2, 3, "", 0, 0), "COLD_SIDE_ASSEMBLY")
    if raw is None or errors != 0 or warnings not in (0, 128):
        raise base.GateError("COLD_OPEN_SIDE_ASSEMBLY_FAIL", "cold open failed", {"target": posix(target), "errors": errors, "warnings": warnings})
    model = base.wrap(raw, "IModelDoc2", types, pythoncom)
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    manager = base.wrap(base.value(model, "ConfigurationManager"), "IConfigurationManager", types, pythoncom)
    title = str(base.value(model, "GetTitle"))
    try:
        names = [str(name) for name in base.as_list(base.value(model, "GetConfigurationNames"))]
        if set(names) != set(solar.CONFIGS):
            raise base.GateError("COLD_CONFIG_SET_FAIL", "cold configuration set mismatch", {"side": side, "configurations": names})
        pose_map = solar.config_pose_map(side)
        rows: List[Dict[str, Any]] = []
        for config in solar.CONFIGS:
            if not bool(model.ShowConfiguration2(config)):
                raise base.GateError("COLD_SHOW_CONFIGURATION_FAIL", "cold show configuration failed", {"side": side, "configuration": config})
            active = str(base.value(base.wrap(base.value(manager, "ActiveConfiguration"), "IConfiguration", types, pythoncom), "Name"))
            if active != config:
                raise base.GateError("COLD_SHOW_CONFIGURATION_FAIL", "cold active configuration drifted", {"side": side, "configuration": config, "active": active})
            if not bool(model.EditRebuild3()):
                raise base.GateError("COLD_CONFIG_REBUILD_FAIL", "cold rebuild failed", {"side": side, "configuration": config})
            fresh = solar.fresh_panels(model, assembly, side, types, pythoncom)
            for index, component in fresh.items():
                deployed = bool(pose_map[config][int(index)])
                expected = expected_transform_m(side, int(index), deployed)
                readback = component_transform_readback(component)
                if not transforms_match(readback, expected):
                    raise base.GateError("COLD_POSE_VERIFY_FAIL", "cold pose readback outside tolerance", {"side": side, "configuration": config, "panel": int(index), "expected": expected, "actual": readback})
                rows.append({
                    "configuration": config,
                    "panel": int(index),
                    "deployed": deployed,
                    "angle_deg": 90 if deployed else 0,
                    "cold_transform_m": readback,
                    "cold_max_abs_delta_m": max_abs_delta(readback, expected),
                    "cold_within_tolerance": True,
                })
            placeholders = placeholder_components(model, assembly, side, types, pythoncom)
            for name, component in sorted(placeholders.items()):
                if bool(base.value(component, "IsSuppressed")) or not bool(base.value(component, "IsFixed")):
                    raise base.GateError("COLD_PLACEHOLDER_STATE_FAIL", "cold placeholder is not fixed and resolved", {"side": side, "configuration": config, "placeholder": name})
        facts = file_fact(target)
        return {
            "side": side,
            "target": facts,
            "configurations": names,
            "cold_pose_rows": rows,
            "panel_poses_cold_verified": len(rows),
            "placeholders_fixed_and_resolved_all_configurations": True,
        }
    finally:
        try:
            sw.CloseDoc(title)
        except Exception:
            pass
        close_all_documents(sw)


def write_state_register(evidence_ref: str) -> Dict[str, Any]:
    """R4: per-state register from the verified pose table; Loop2 fields stay PENDING."""
    header = "state,panel_angle_deg_L[3],panel_angle_deg_R[3],hinge_state,collision_state,camera_visibility,arm_clearance_mm,evidence_ref,owner"
    pose_map = solar.config_pose_map("L")  # as-built pose table is identical for both sides
    lines = [header]
    for config in solar.CONFIGS:
        triple = "/".join("90" if pose_map[config][index] else "0" for index in (1, 2, 3))
        lines.append(",".join([
            config,
            triple,
            triple,
            "NO_KINEMATIC_MATE_YET",
            "PENDING_LOOP2",
            "PENDING_LOOP2",
            "PENDING_LOOP2",
            evidence_ref,
            "V5_LOOP_SOLAR_B_UNRATIFIED_CANDIDATE",
        ]))
    if REGISTER.exists():
        raise base.GateError("REGISTER_EXISTS", "state register is write-once and already exists", {"path": posix(REGISTER)})
    REGISTER.parent.mkdir(parents=True, exist_ok=True)
    with REGISTER.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines) + "\n")
    return file_fact(REGISTER)


def latest_solar_receipt() -> Optional[Path]:
    receipts = sorted(VALIDATION.glob("V5_SOLAR_ARRAY_NATIVE_RECEIPT_*.json"))
    return receipts[-1] if receipts else None


def static_audit() -> Dict[str, Any]:
    """Filesystem-only audit; never attaches to SolidWorks, never imports win32com."""
    inputs: List[Dict[str, Any]] = []

    def row(label: str, path: Path, must_exist: bool = True) -> Dict[str, Any]:
        item = {"label": label, "path": posix(path), "exists": path.is_file(), "pass": (path.is_file() or not must_exist)}
        if path.is_file():
            item["bytes"] = path.stat().st_size
            item["sha256"] = sha256(path)
        inputs.append(item)
        return item

    row("RUN_ROOT_MARKER_GAP_REPORT", RUN_ROOT / "V5_SOLAR_ARRAY_RESIDUAL_GAPS_20260810.md")
    row("AUTHORITY_REQUIREMENTS", AUTHORITY / "SOLAR_ARRAY_INTERFACE_REQUIREMENTS.md")
    row("AUTHORITY_BUILD_PLAN", AUTHORITY / "SOLAR_ARRAY_CANDIDATE_BUILD_PLAN.md")
    row("BUILD_SCRIPT", TOOLS / "F3R2_V5_NATIVE_SOLAR_ARRAY_BUILD.py")
    row("PART_TEMPLATE", PART_TEMPLATE)
    row("ASSEMBLY_TEMPLATE", solar.ASSEMBLY_TEMPLATE)
    for name, spec in solar.panel_specs().items():
        row(f"PANEL:{name}", Path(spec["target"]))
    for side in ("L", "R"):
        row(f"SIDE_ASSEMBLY:{side}", SUBASM_DIR / f"{side}_SOLAR_ARRAY.SLDASM")

    receipt_path = latest_solar_receipt()
    receipt_row: Dict[str, Any] = {"label": "SOLAR_NATIVE_RECEIPT", "path": posix(receipt_path) if receipt_path else None, "exists": receipt_path is not None, "pass": False}
    if receipt_path is not None:
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt_row.update({
            "bytes": receipt_path.stat().st_size,
            "sha256": sha256(receipt_path),
            "schema": payload.get("schema"),
            "verdict": payload.get("verdict"),
            "pass": payload.get("verdict") == "V5_SOLAR_ARRAY_CANDIDATE_NATIVE_PANELS_AND_SIDE_ASMS_PASS",
        })
    inputs.append(receipt_row)

    placeholder_rows = []
    for name, spec in placeholder_specs().items():
        placeholder_rows.append({"name": name, "path": posix(spec["target"]), "exists": Path(spec["target"]).is_file()})
    completion_receipts = sorted(posix(path) for path in VALIDATION.glob("V5_SOLAR_ARRAY_COMPLETION_RECEIPT_*.json"))
    top_contents = sorted(posix(path) for path in TOP_DIR.glob("*")) if TOP_DIR.is_dir() else []

    inputs_pass = all(item["pass"] for item in inputs)
    execution_authorized = (
        inputs_pass
        and not REGISTER.exists()
        and not completion_receipts
        and not top_contents
    )
    return {
        "schema": "F3R2_V5_SOLAR_B_STATIC_AUDIT_V1",
        "timestamp_utc": utc_now(),
        "run_root": posix(RUN_ROOT),
        "script": {"path": posix(Path(__file__).resolve()), "bytes": Path(__file__).stat().st_size, "sha256": sha256(Path(__file__))},
        "attach_attempted": False,
        "win32com_imported_by_this_script": any("win32" in name.lower() or "pythoncom" in name.lower() for name in sys.modules),
        "inputs": inputs,
        "inputs_pass": inputs_pass,
        "placeholder_targets": placeholder_rows,
        "state_register": {"path": posix(REGISTER), "exists": REGISTER.exists(), "write_once": True},
        "completion_receipts_existing": completion_receipts,
        "top_assembly_contents": top_contents,
        "top_assembly_must_be_empty": "Loop-SOLAR-B must run before Loop1E",
        "session_binding": sbin.binding_summary(SESSION_DEFAULT_PID),
        "memory_override": mo.summary(),
        "expected_configurations": list(solar.CONFIGS),
        "pose_tolerance_m": POSE_TOLERANCE_M,
        "non_claims": list(NON_CLAIMS),
        "execution_authorized": execution_authorized,
        "verdict": "V5_SOLAR_B_STATIC_AUDIT_PASS" if execution_authorized else "V5_SOLAR_B_STATIC_AUDIT_HOLD",
    }


def execute() -> int:
    result: Dict[str, Any] = {
        "schema": "F3R2_V5_SOLAR_ARRAY_COMPLETION_RECEIPT_V1",
        "timestamp_start_utc": utc_now(),
        "run_root": posix(RUN_ROOT),
        "script": {"path": posix(Path(__file__).resolve()), "sha256": sha256(Path(__file__))},
        "non_claims": list(NON_CLAIMS),
        "pose_table_unit_note": "SolidWorks API transforms are metres; build-script millimetre pose geometry divided by 1000",
        "pose_tolerance_m": POSE_TOLERANCE_M,
    }
    sw = types = pythoncom = None
    try:
        audit = static_audit()
        result["static_audit"] = audit
        if not audit["execution_authorized"]:
            raise base.GateError("SOLAR_B_STATIC_EXECUTION_HOLD", "static audit is not executable", {"audit_verdict": audit["verdict"]})
        sw, types, pythoncom, session = base.attach_empty_session()
        if int(session["pid"]) != int(sbin.resolve_pid(SESSION_DEFAULT_PID)):
            raise base.GateError("SESSION_PID_MISMATCH", "attached session is not the resolved V5 session", {"session": session})
        result["solidworks"] = session
        result["memory_samples_gib"] = base.memory_gate()
        result["memory_override_allowed"] = mo.override_allowed()

        # R2: extend hinge-axis text semantics to inter-panel hinges (additive only).
        panel_rows = []
        for name, spec in solar.panel_specs().items():
            panel_rows.append(update_panel_hinge_semantics(sw, types, pythoncom, name, spec))
        result["panels"] = panel_rows
        result["hinge_axis_semantics"] = {
            "status": "PARTIAL_TEXT_ONLY_PENDING_LOOP1B_HINGE_MATE_PATTERN",
            "convention": "HINGE_AXIS* custom properties carry axis text; no kinematic mates exist yet",
            "root_axis": {"L": axis_text(1.0, ROOT_HINGE_Y_MM), "R": axis_text(-1.0, ROOT_HINGE_Y_MM)},
            "inter_panel_axes_per_side_mm": {"H1_between_panels_1_2": ROOT_HINGE_Y_MM + PANEL_LEN_MM, "H2_between_panels_2_3": ROOT_HINGE_Y_MM + 2.0 * PANEL_LEN_MM},
            "kinematic_mates": "NO_KINEMATIC_MATE_YET",
        }

        # R6/R8/R9: placeholder-level native parts.
        placeholder_rows = []
        for name, spec in placeholder_specs().items():
            placeholder_rows.append(build_placeholder_part(sw, types, pythoncom, name, spec))
        result["placeholder_parts"] = placeholder_rows

        # F-3: non-resume apply/verify of every configuration pose, per side.
        assembly_rows = []
        cold_rows = []
        for side in ("L", "R"):
            assembly_rows.append(complete_side_assembly(sw, types, pythoncom, side))
        for side in ("L", "R"):
            cold_rows.append(cold_verify_side(sw, types, pythoncom, side))
        result["assemblies"] = assembly_rows
        result["cold_reverification"] = cold_rows

        if int(base.value(sw, "GetDocumentCount")) != 0:
            raise base.GateError("POST_COMPLETION_SESSION_NOT_EMPTY", "documents remain open after solar completion", {"document_count": int(base.value(sw, "GetDocumentCount"))})

        # R4: per-state register from the verified pose table.
        evidence_ref = f"F3R2_V5_SOLAR_ARRAY_COMPLETION_RECEIPT_V1@{result['timestamp_start_utc']}"
        result["state_register"] = write_state_register(evidence_ref)
        result["state_register_note"] = "collision_state/camera_visibility/arm_clearance_mm remain PENDING_LOOP2; no values fabricated"

        # R7: FAIL-config registration (poses preserved as-built).
        result["fail_config_registration"] = {
            "as_built_semantics": "CANDIDATE_INTERMEDIATE_ANGLE_ENCODING",
            "poses_changed": False,
            "as_built_pose_table": {config: {str(index): bool(flag) for index, flag in solar.config_pose_map("L")[config].items()} for config in solar.CONFIGS},
            "mapping_note": (
                "Authoritative single-panel FAIL semantics are L_FAIL(0/90) and R_FAIL(90/0) per "
                "SOLAR_ARRAY_INTERFACE_REQUIREMENTS §1. The as-built three-panel SOLAR_LEFT_FAIL "
                "{panel1 deployed, panels 2/3 stowed} and SOLAR_RIGHT_FAIL {panels 1-3 deployed} "
                "encode unissued intermediate-angle candidates on BOTH side assemblies "
                "(config_pose_map ignores the side parameter). Registered as CANDIDATE per "
                "proposal P-3; no pose change performed; no authoritative upgrade."
            ),
            "authoritative_mapping": {"SOLAR_LEFT_FAIL": "L_FAIL(0/90)_SINGLE_PANEL_AUTHORITY", "SOLAR_RIGHT_FAIL": "R_FAIL(90/0)_SINGLE_PANEL_AUTHORITY", "SOLAR_BOTH_FAIL": "DEPLOY_FAILED_BOTH(0/0)"},
        }

        result["timestamp_end_utc"] = utc_now()
        result["verdict"] = "V5_SOLAR_ARRAY_COMPLETION_PASS"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        receipt = VALIDATION / f"V5_SOLAR_ARRAY_COMPLETION_RECEIPT_{stamp}.json"
        solar.write_json_once(receipt, json_safe(result))
        print(json.dumps({
            "verdict": result["verdict"],
            "receipt": posix(receipt),
            "panels": len(result["panels"]),
            "placeholder_parts": len(result["placeholder_parts"]),
            "panel_poses_applied_and_verified": sum(row["panel_poses_applied_and_verified"] for row in assembly_rows),
            "panel_poses_cold_verified": sum(row["panel_poses_cold_verified"] for row in cold_rows),
            "state_register": result["state_register"],
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        result.update({
            "verdict": "V5_SOLAR_ARRAY_COMPLETION_FAIL",
            "reason": str(exc),
            "detail": getattr(exc, "detail", {}),
            "traceback": traceback.format_exc(),
            "timestamp_end_utc": utc_now(),
        })
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        failure = VALIDATION / f"V5_SOLAR_ARRAY_COMPLETION_FAIL_{stamp}.json"
        try:
            solar.write_json_once(failure, json_safe(result))
        except Exception:
            pass
        print(json.dumps({"verdict": result["verdict"], "failure": posix(failure), "reason": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    finally:
        if sw is not None:
            close_all_documents(sw)
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="F3R2 V5 solar array completion loop (LOOP-SOLAR-B, attach-only)")
    parser.add_argument("command", nargs="?", default="audit", choices=("audit", "execute"))
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    if args.command == "audit":
        print(json.dumps(static_audit(), ensure_ascii=False, indent=2))
        return 0
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
