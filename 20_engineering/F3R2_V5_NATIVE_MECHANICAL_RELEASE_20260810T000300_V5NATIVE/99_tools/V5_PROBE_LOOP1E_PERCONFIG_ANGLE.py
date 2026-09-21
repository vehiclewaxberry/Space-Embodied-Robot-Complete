#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: per-config angle-mate behavior (seed design decision).

Proven 2026-08-12 (MODIFY_PATHS_20260812T070647Z.log): AddMate3 with
Angle=+0.5 deg at creation moves joint1 exactly +0.5 deg about the accepted
axis (creation-angle drive is reliable; ModifyDefinition is not).  The
remaining question is per-config semantics of the new driving angle mate:
  P1  create the joint1 mate at Angle=0 in 默认; measure the base_link<-
      link1 relative rotation;
  P2  activate STOWED_O13V3; measure again — does the joint hold the donor
      stow pose (+145.572 deg stored positions) or does the driving mate
      snap it to 0?  Read data.Angle in STOWED (fresh feature handle);
  P3  in STOWED, delete+recreate the mate with Angle=stow_q1 (145.572 deg);
      measure; read data.Angle;
  P4  switch back to 默认; measure — per-config independence check (默认
      must return to 0); read data.Angle in 默认;
  P5  discard WITHOUT saving; close; session census.

This decides whether the per-config seed loop needs any ModifyDefinition
writes at all, or is pure verification.  Never writes inside the release
tree, never mutates the protected donor, never saves.
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
PROTECTED_WATCH = [m.B51_DONOR] + sorted(m.B51_DONOR_ROOT.rglob("*.SLDPRT"))


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


def delete_feature(model: Any, feature: Any) -> bool:
    model.ClearSelection2(True)
    if not bool(feature.Select2(False, 0)):
        return False
    try:
        model.EditDelete()
        return True
    except Exception:  # noqa: BLE001
        return False
    finally:
        model.ClearSelection2(True)


def mate_angle(model: Any, feature_name: str, types: Any, pythoncom_module: Any) -> float:
    feature = m.mate_features(model, base, types, pythoncom_module).get(feature_name)
    if feature is None:
        return float("nan")
    return float(base.value(m.angle_mate_data(feature, base, types, pythoncom_module), "Angle"))


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_PERCONFIG_ANGLE_V1",
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
        log("state ready")

        joint = m.accepted_urdf_joints()[0]
        stow_q1 = math.radians(float(m.ARM_CONFIGURATION_Q_DEG["STOWED_O13V3"][0]))
        MATE_NAME = "V5_LOOP2_JOINT1_LIMIT_ANGLE"

        # P1: create at 0 in STOWED (active after census) — WAIT: production
        # activates 默认 first; replicate: activate 默认, create at 0.
        if not m.show_config_ok(model, "默认", base, types, pythoncom_module) or not bool(model.ForceRebuild3(True)):
            raise RuntimeError("默认 activation failed")
        m1 = create_mate(model, assembly, joint, 0.0, types, pythoncom_module)
        m1.Name = MATE_NAME
        p1 = {"rotvec_default": joint1_angle(assembly, types, pythoncom_module), "mate_angle": mate_angle(model, MATE_NAME, types, pythoncom_module)}
        result["phases"]["P1_created_in_default"] = p1
        log(f"P1: rotvec={p1['rotvec_default']} mate_angle={p1['mate_angle']}")

        # P2: activate STOWED — pose and mate angle readback
        if not m.show_config_ok(model, "STOWED_O13V3", base, types, pythoncom_module) or not bool(model.ForceRebuild3(True)):
            raise RuntimeError("STOWED activation failed")
        p2 = {"rotvec_stowed": joint1_angle(assembly, types, pythoncom_module), "mate_angle_stowed": mate_angle(model, MATE_NAME, types, pythoncom_module)}
        result["phases"]["P2_stowed_after_switch"] = p2
        log(f"P2: rotvec={p2['rotvec_stowed']} mate_angle={p2['mate_angle_stowed']} (stow target {stow_q1})")

        # P3: delete+recreate in STOWED at stow angle
        feature = m.mate_features(model, base, types, pythoncom_module).get(MATE_NAME)
        deleted = delete_feature(model, feature) if feature is not None else False
        m3 = create_mate(model, assembly, joint, stow_q1, types, pythoncom_module)
        m3.Name = MATE_NAME
        p3 = {"deleted": deleted, "rotvec_stowed_recreated": joint1_angle(assembly, types, pythoncom_module), "mate_angle_stowed_recreated": mate_angle(model, MATE_NAME, types, pythoncom_module)}
        result["phases"]["P3_stowed_recreated"] = p3
        log(f"P3: deleted={deleted} rotvec={p3['rotvec_stowed_recreated']} mate_angle={p3['mate_angle_stowed_recreated']}")

        # P4: back to 默认 — per-config independence
        if not m.show_config_ok(model, "默认", base, types, pythoncom_module) or not bool(model.ForceRebuild3(True)):
            raise RuntimeError("默认 re-activation failed")
        p4 = {"rotvec_default_back": joint1_angle(assembly, types, pythoncom_module), "mate_angle_default_back": mate_angle(model, MATE_NAME, types, pythoncom_module)}
        result["phases"]["P4_default_back"] = p4
        log(f"P4: rotvec={p4['rotvec_default_back']} mate_angle={p4['mate_angle_default_back']}")

        remaining = close_everything(sw)
        result["cleanup_remaining"] = remaining
        log(f"cleanup remaining={remaining}")
        result["verdict"] = "V5_PROBE_LOOP1E_PERCONFIG_ANGLE_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_PERCONFIG_ANGLE_FAIL"
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
