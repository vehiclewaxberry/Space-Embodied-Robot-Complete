#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: stale-handle vs genuine non-driving angle mate.

The A/B probe (V5_PROBE_LOOP1E_MODIFY_AB_20260811T231359Z.log) created the
joint1 driver cleanly in both configurations, but the +0.5 deg drive
returned: SetSystemValue3 status=SUCCESS, ForceRebuild3=True, yet
data.Angle stayed 0.0 and GetSystemValue3([默认]) came back EMPTY on the
creation-time handles.  This either means the angle dimension genuinely
does not drive the joint, or every readback was a stale-handle artifact
(the known SW2024 handle-death class after config switches/rebuilds).

In-memory only, NO SAVE, Arm-B state (full dependent-reload + 默认 gate):
  R1  fresh-handle baseline transforms (base_link, link1);
  R2  drive the creation-returned dimension +0.5 deg in 默认 + rebuild;
  R3  FRESH re-acquisition: feature by name -> data.Angle; fresh
      DisplayDimension2(0) dimension -> GetSystemValue3; fresh component
      transforms -> relative rotation delta;
  R4  ModifyDefinition drive (data.Angle=+0.5 deg) + rebuild -> fresh
      readbacks again (feature/data/dimension/transforms);
  R5  discard WITHOUT saving; close; session census.

Never writes inside the release tree, never mutates the protected donor,
never saves.
"""

from __future__ import annotations

import json
import math
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import pythoncom  # noqa: E402
import win32com.client  # noqa: E402
from win32com.client import gencache  # noqa: E402

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base  # noqa: E402
import F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY as m  # noqa: E402
import F3R2_V5_SESSION_BINDING as sbin  # noqa: E402

T0 = time.time()
SW_COMPONENT_FULLY_RESOLVED = 1
SW_SET_VALUE_IN_SPECIFIC_CONFIGS = 3
PROTECTED_WATCH = [m.B51_DONOR] + sorted(m.B51_DONOR_ROOT.rglob("*.SLDPRT"))
FEATURE_NAME = "V5_LOOP2_JOINT1_LIMIT_ANGLE"


def log(step: str) -> None:
    print(f"[{time.time() - T0:8.2f}s] {step}", flush=True)


def close_everything(sw: Any) -> int:
    for _pass in range(4):
        documents = base.as_list(base.value(sw, "GetDocuments"))
        if not documents:
            break
        titles: List[str] = []
        for raw in documents:
            try:
                titles.append(str(base.value(raw, "GetTitle")))
            except Exception:  # noqa: BLE001
                continue
        for title in reversed(list(dict.fromkeys(titles))):
            try:
                sw.CloseDoc(title)
            except Exception:  # noqa: BLE001
                pass
    if int(base.value(sw, "GetDocumentCount")):
        try:
            sw.CloseAllDocuments(True)
        except Exception:  # noqa: BLE001
            pass
    return int(base.value(sw, "GetDocumentCount"))


def find_leaf(assembly: Any, leaf: str, types: Any, pythoncom_module: Any) -> Optional[Any]:
    for raw in base.as_list(assembly.GetComponents(True)):
        component = base.wrap(raw, "IComponent2", types, pythoncom_module)
        if str(base.value(component, "Name2")).split("/")[-1] == leaf:
            return component
    return None


def transform16(component: Any) -> List[float]:
    raw = base.value(component, "Transform2")
    values = [float(value) for value in base.as_list(base.value(raw, "ArrayData"))] if raw is not None else []
    if len(values) != 16:
        raw_total = base.value(component, "GetTotalTransform", False)
        values = [float(value) for value in base.as_list(base.value(raw_total, "ArrayData"))] if raw_total is not None else []
    return values


def rot(values: List[float]) -> List[List[float]]:
    return [[values[0], values[3], values[6]], [values[1], values[4], values[7]], [values[2], values[5], values[8]]]


def mul(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    return [[sum(a[r][i] * b[i][c] for i in range(3)) for c in range(3)] for r in range(3)]


def tr(a: List[List[float]]) -> List[List[float]]:
    return [[a[c][r] for c in range(3)] for r in range(3)]


def rotvec(matrix: List[List[float]]) -> List[float]:
    cos_angle = (matrix[0][0] + matrix[1][1] + matrix[2][2] - 1.0) / 2.0
    angle = math.acos(max(-1.0, min(1.0, cos_angle)))
    if abs(angle) < 1.0e-12:
        return [0.0, 0.0, 0.0]
    denom = 2.0 * math.sin(angle)
    return [angle * (matrix[2][1] - matrix[1][2]) / denom, angle * (matrix[0][2] - matrix[2][0]) / denom, angle * (matrix[1][0] - matrix[0][1]) / denom]


def relative_rotation(assembly: Any, types: Any, pythoncom_module: Any) -> List[float]:
    parent = find_leaf(assembly, "B51_REF_base_link_LINKLOCAL-1", types, pythoncom_module)
    child = find_leaf(assembly, "B51_REF_link1_LINKLOCAL-1", types, pythoncom_module)
    return rotvec(mul(tr(rot(transform16(parent))), rot(transform16(child))))


def fresh_mate_reads(model: Any, types: Any, pythoncom_module: Any) -> Dict[str, Any]:
    features = m.mate_features(model, base, types, pythoncom_module)
    feature = features.get(FEATURE_NAME)
    if feature is None:
        return {"error": "FEATURE_NOT_FOUND"}
    data = m.angle_mate_data(feature, base, types, pythoncom_module)
    dimension = m.angle_mate_dimension(feature, base, types, pythoncom_module)
    values = [float(v) for v in base.as_list(dimension.GetSystemValue3(SW_SET_VALUE_IN_SPECIFIC_CONFIGS, [m.ARM_CONFIGS[0]]))]
    return {
        "data_angle": float(base.value(data, "Angle")),
        "advanced": bool(base.value(data, "IsAdvancedMate")),
        "limits": [float(base.value(data, "MinimumAngle")), float(base.value(data, "MaximumAngle"))],
        "dimension_full_name": str(base.value(dimension, "FullName")),
        "dimension_values": values,
        "feature_error_code": m.feature_error_code(feature, base),
        "feature_suppressed": bool(base.value(feature, "IsSuppressed")),
    }


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_DRIVE_FRESH_READS_V1",
        "timestamp_start_utc": datetime.now(timezone.utc).isoformat(),
        "phases": {},
    }
    sw = types = pythoncom_module = None
    try:
        pythoncom_module = pythoncom
        pythoncom_module.CoInitialize()
        types = gencache.GetModuleForTypelib(*base.SW_TLB)
        raw = win32com.client.GetActiveObject(base.SW_PROG_ID)
        sw = base.wrap(raw, "ISldWorks", types, pythoncom_module)
        session = {"pid": int(base.value(sw, "GetProcessID")), "revision": str(base.value(sw, "RevisionNumber"))}
        expected_pid = int(sbin.resolve_pid(json.loads(m.LOOP1_RECEIPT.read_text(encoding="utf-8-sig")).get("solidworks", {}).get("pid", -1)))
        if session["pid"] != expected_pid:
            raise RuntimeError(f"session PID drifted: {session['pid']} != {expected_pid}")
        if int(base.value(sw, "GetDocumentCount")) != 0:
            raise RuntimeError("session not document-empty at probe start")
        result["session"] = session
        result["protected_pre"] = {m.sha256(path): str(path) for path in PROTECTED_WATCH if path.is_file()}
        log(f"attach ok pid={session['pid']}")

        # Arm-B state: prebind, census, full dependent-reload, 默认 gate
        for part in sorted(m.LOCAL_ARM_ROOT.rglob("*.SLDPRT")):
            open_form = m.sw_openable_path(part)
            options = 1 | (2 if open_form != str(part.resolve()) else 0)
            raw2 = sw.OpenDoc6(open_form, m.SW_DOC_PART, options, "", 0, 0)
            model_raw, outs = base.unpack(raw2)
            if model_raw is None or (outs and int(outs[0]) != 0):
                raise RuntimeError(f"prebind failed {part.name}")
        raw_asm = sw.OpenDoc6(m.sw_openable_path(m.LOCAL_ARM), m.SW_DOC_ASSEMBLY, 1, "", 0, 0)
        model_raw, outs = base.unpack(raw_asm)
        if model_raw is None or (outs and int(outs[0]) != 0):
            raise RuntimeError("assembly open failed")
        model = base.wrap(model_raw, "IModelDoc2", types, pythoncom_module)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom_module)
        for cfg in m.ARM_CONFIGS:
            if not m.show_config_ok(model, cfg, base, types, pythoncom_module):
                raise RuntimeError(f"census config failed {cfg}")
        for raw2 in base.as_list(assembly.GetComponents(True)):
            component = base.wrap(raw2, "IComponent2", types, pythoncom_module)
            name2 = str(base.value(component, "Name2"))
            leaf = name2.split("/")[-1]
            if leaf == m.ARM_LEGACY_GRIPPER_LEAF or int(base.value(component, "GetSuppression2")) == SW_COMPONENT_FULLY_RESOLVED:
                continue
            part_title = Path(str(base.value(component, "GetPathName"))).name
            try:
                sw.CloseDoc(part_title)
            except Exception:  # noqa: BLE001
                pass
            component.SetSuppression2(SW_COMPONENT_FULLY_RESOLVED)
            if not bool(model.ForceRebuild3(True)):
                raise RuntimeError(f"reload rebuild failed {name2}")
        if not m.show_config_ok(model, m.ARM_CONFIGS[0], base, types, pythoncom_module) or not bool(model.ForceRebuild3(True)):
            raise RuntimeError("默认 activation failed")
        log("state ready")

        joint = m.accepted_urdf_joints()[0]
        female = find_leaf(assembly, "B51_REV_DATUM_FEMALE-1", types, pythoncom_module)
        male = find_leaf(assembly, "B51_REV_DATUM_MALE-1", types, pythoncom_module)
        feature, dimension, creation = m.add_native_angle_driver(model, assembly, female, male, joint, base, types, pythoncom_module)
        log("driver created")
        result["phases"]["R0_creation"] = creation

        # R1: baseline
        baseline = relative_rotation(assembly, types, pythoncom_module)
        result["phases"]["R1_baseline_rotvec"] = baseline

        # R2: dimension drive
        probe = math.radians(0.5)
        status = int(dimension.SetSystemValue3(probe, SW_SET_VALUE_IN_SPECIFIC_CONFIGS, [m.ARM_CONFIGS[0]]))
        rebuilt = bool(model.ForceRebuild3(True))
        result["phases"]["R2_dimension_drive"] = {"status": status, "rebuilt": rebuilt, "probe_rad": probe}

        # R3: fresh reads after dimension drive
        fresh_after_dim = fresh_mate_reads(model, types, pythoncom_module)
        current_dim = relative_rotation(assembly, types, pythoncom_module)
        result["phases"]["R3_fresh_after_dimension_drive"] = {"mate": fresh_after_dim, "rotvec": current_dim}
        log(f"R3: data_angle={fresh_after_dim.get('data_angle')} dim_values={fresh_after_dim.get('dimension_values')} rotvec={current_dim}")

        # R4: ModifyDefinition drive
        data = m.angle_mate_data(feature, base, types, pythoncom_module)
        data.Angle = probe
        modified = bool(feature.ModifyDefinition(data, model, None))
        rebuilt2 = bool(model.ForceRebuild3(True))
        fresh_after_mod = fresh_mate_reads(model, types, pythoncom_module)
        current_mod = relative_rotation(assembly, types, pythoncom_module)
        result["phases"]["R4_modifydefinition_drive"] = {"modified": modified, "rebuilt": rebuilt2, "mate": fresh_after_mod, "rotvec": current_mod}
        log(f"R4: modified={modified} data_angle={fresh_after_mod.get('data_angle')} dim_values={fresh_after_mod.get('dimension_values')} rotvec={current_mod}")

        remaining = close_everything(sw)
        result["cleanup_remaining"] = remaining
        log(f"cleanup remaining={remaining}")
        result["verdict"] = "V5_PROBE_LOOP1E_DRIVE_FRESH_READS_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_DRIVE_FRESH_READS_FAIL"
        log("exception; see payload")
    finally:
        if sw is not None:
            try:
                result["cleanup_document_count"] = close_everything(sw)
            except Exception as cleanup_exc:  # noqa: BLE001
                result["cleanup_exception"] = repr(cleanup_exc)
        try:
            post = {m.sha256(path): str(path) for path in PROTECTED_WATCH if path.is_file()}
            result["protected_post_unchanged"] = post == result.get("protected_pre")
        except Exception as exc:  # noqa: BLE001
            result["protected_post_exception"] = repr(exc)
        result["timestamp_end_utc"] = datetime.now(timezone.utc).isoformat()
        if pythoncom_module is not None:
            try:
                pythoncom_module.CoUninitialize()
            except Exception:  # noqa: BLE001
                pass
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
