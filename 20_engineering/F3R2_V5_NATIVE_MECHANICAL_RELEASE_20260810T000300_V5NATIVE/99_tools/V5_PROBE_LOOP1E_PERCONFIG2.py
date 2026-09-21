#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: mate health + per-config value across configs.

PERCONFIG_ANGLE (20260812T071100Z) showed: joint1 mate created at Angle=0 in
默认; on switching to STOWED the pose follows stored positions (+145.572
deg) while the mate value stays 0 — the driving mate does not enforce its
value across config switches.  Missing datums for the seed design:
  Q1  is the mate HEALTHY (error 0, not suppressed) in STOWED with value 0
      against the 2.54 rad pose, or does it error?
  Q2  does model.Parameter(dim).SetSystemValue3(stow, SPECIFIC, [STOWED])
      write the per-config mate value (motion and/or value readback)?
  Q3  after any write attempt, does the STOWED mate readback change?

In-memory only, NO SAVE.  Never writes inside the release tree, never
mutates the protected donor, never saves; session left document-empty.
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
MATE_NAME = "V5_LOOP2_JOINT1_LIMIT_ANGLE"


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


def joint1_angle(assembly: Any, types: Any, pythoncom_module: Any) -> List[float]:
    parent = find_leaf(assembly, "B51_REF_base_link_LINKLOCAL-1", types, pythoncom_module)
    child = find_leaf(assembly, "B51_REF_link1_LINKLOCAL-1", types, pythoncom_module)
    return rotvec(mul(tr(rot(transform16(parent))), rot(transform16(child))))


def create_mate(model: Any, assembly: Any, joint: Dict[str, Any], angle: float, types: Any, pythoncom_module: Any) -> Any:
    female = find_leaf(assembly, "B51_REV_DATUM_FEMALE-1", types, pythoncom_module)
    male = find_leaf(assembly, "B51_REV_DATUM_MALE-1", types, pythoncom_module)
    first_plane = m.component_side_plane(female, base, types, pythoncom_module)
    second_plane = m.component_side_plane(male, base, types, pythoncom_module)
    before_names = set(m.mate_features(model, base, types, pythoncom_module))
    model.ClearSelection2(True)
    if not bool(first_plane.Select2(False, 1)) or not bool(second_plane.Select2(True, 1)):
        raise RuntimeError("plane selection failed")
    returned = assembly.AddMate3(6, 0, False, 0.0, 0.0, 0.0, 0.0, 0.0, float(angle), float(joint["upper_rad"]), float(joint["lower_rad"]), False, 0)
    mate_raw, outs = base.unpack(returned)
    error = int(outs[0]) if outs else -1
    model.ClearSelection2(True)
    if mate_raw is None or error != 1:
        raise RuntimeError(f"AddMate3 failed error={error}")
    after = m.mate_features(model, base, types, pythoncom_module)
    additions = [item for name, item in after.items() if name not in before_names]
    if len(additions) != 1:
        raise RuntimeError(f"additions != 1: {[str(base.value(i, 'Name')) for i in additions]}")
    return additions[0]


def mate_state(model: Any, types: Any, pythoncom_module: Any) -> Dict[str, Any]:
    feature = m.mate_features(model, base, types, pythoncom_module).get(MATE_NAME)
    if feature is None:
        return {"error": "FEATURE_NOT_FOUND"}
    definition = m.angle_mate_data(feature, base, types, pythoncom_module)
    return {
        "angle": float(base.value(definition, "Angle")),
        "advanced": bool(base.value(definition, "IsAdvancedMate")),
        "error_code": m.feature_error_code(feature, base),
        "suppressed": bool(base.value(feature, "IsSuppressed")),
    }


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_PERCONFIG2_V1",
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

        for part in sorted(p for p in m.LOCAL_ARM_ROOT.rglob("*.SLDPRT") if not p.name.startswith("~$")):
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
        log("state ready")

        joint = m.accepted_urdf_joints()[0]
        stow_q1 = math.radians(float(m.ARM_CONFIGURATION_Q_DEG["STOWED_O13V3"][0]))

        if not m.show_config_ok(model, "默认", base, types, pythoncom_module) or not bool(model.ForceRebuild3(True)):
            raise RuntimeError("默认 activation failed")
        m1 = create_mate(model, assembly, joint, 0.0, types, pythoncom_module)
        m1.Name = MATE_NAME
        result["phases"]["created_default"] = {"pose": joint1_angle(assembly, types, pythoncom_module), "mate": mate_state(model, types, pythoncom_module)}
        log(f"created in 默认: mate={result['phases']['created_default']['mate']}")

        if not m.show_config_ok(model, "STOWED_O13V3", base, types, pythoncom_module) or not bool(model.ForceRebuild3(True)):
            raise RuntimeError("STOWED activation failed")
        stowed_state = {"pose": joint1_angle(assembly, types, pythoncom_module), "mate": mate_state(model, types, pythoncom_module)}
        result["phases"]["Q1_stowed_state"] = stowed_state
        log(f"Q1 STOWED: pose={stowed_state['pose']} mate={stowed_state['mate']}")

        # Q2: parameter dimension drive attempt in STOWED
        dim_name = result["phases"]["created_default"]["mate"].get("angle") is not None and f"D1@{MATE_NAME}@B51_B601_ARTICULATED_ENGINEERING_ARM.Assembly"
        q2: Dict[str, Any] = {"dimension_name": dim_name}
        dimension = model.Parameter(dim_name) if dim_name else None
        if dimension is None:
            q2["parameter_resolved"] = False
        else:
            q2["parameter_resolved"] = True
            status = int(dimension.SetSystemValue3(float(stow_q1), SW_SET_VALUE_IN_SPECIFIC_CONFIGS, ["STOWED_O13V3"]))
            rebuilt = bool(model.ForceRebuild3(True))
            values = [float(v) for v in base.as_list(dimension.GetSystemValue3(SW_SET_VALUE_IN_SPECIFIC_CONFIGS, ["STOWED_O13V3"]))]
            q2.update({"status": status, "rebuilt": rebuilt, "values": values})
        result["phases"]["Q2_parameter_drive"] = q2
        after_q2 = {"pose": joint1_angle(assembly, types, pythoncom_module), "mate": mate_state(model, types, pythoncom_module)}
        result["phases"]["Q3_after_parameter_drive"] = after_q2
        log(f"Q2 parameter drive: {q2} -> mate={after_q2['mate']}")

        remaining = close_everything(sw)
        result["cleanup_remaining"] = remaining
        log(f"cleanup remaining={remaining}")
        result["verdict"] = "V5_PROBE_LOOP1E_PERCONFIG2_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_PERCONFIG2_FAIL"
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
