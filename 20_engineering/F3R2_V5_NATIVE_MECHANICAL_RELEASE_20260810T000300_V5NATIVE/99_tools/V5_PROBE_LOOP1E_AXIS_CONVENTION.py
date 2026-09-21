#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: validate the accepted-axis convention for all joints.

20260812T0801Z: joint2 sign probe measured a pure -0.5 deg about the
accepted axis when driving the native mate +0.5 deg (all three datum planes
agree; alignment/flip/swap variants do not flip the sign).  Before touching
the driver, validate the expected-axis convention itself: the donor's
STOWED pose is ground truth (ARM_CONFIGURATION_Q_DEG), so measure every
joint's relative rotation delta STOWED vs 默认 and compare against
(stow_q - 0) per joint.  If signs/magnitudes match, the convention is right
and joint2's native driver direction is genuinely opposite; if they are
opposite, the expectation math needs correction instead.

In-memory only, NO SAVE, production state.  Never writes inside the release
tree, never mutates the protected donor, never saves; session left
document-empty.
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


def t16(component: Any) -> List[float]:
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


def relative_rotation(assembly: Any, index: int, types: Any, pythoncom_module: Any) -> List[List[float]]:
    parent_leaf = "B51_REF_base_link_LINKLOCAL-1" if index == 1 else f"B51_REF_link{index - 1}_LINKLOCAL-1"
    child_leaf = f"B51_REF_link{index}_LINKLOCAL-1"
    parent = find_leaf(assembly, parent_leaf, types, pythoncom_module)
    child = find_leaf(assembly, child_leaf, types, pythoncom_module)
    return mul(tr(rot(t16(parent))), rot(t16(child)))


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_AXIS_CONVENTION_V1",
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

        joints = m.accepted_urdf_joints()
        stow_q = m.ARM_CONFIGURATION_Q_DEG["STOWED_O13V3"]
        rows: List[Dict[str, Any]] = []
        for index, joint in enumerate(joints, start=1):
            expected = m.rpy_rotation(joint["origin_rpy"])
            axis = [sum(expected[r][i] * joint["axis_xyz"][i] for i in range(3)) for r in range(3)]
            norm = math.sqrt(sum(v * v for v in axis))
            axis = [v / norm for v in axis]
            if not m.show_config_ok(model, "默认", base, types, pythoncom_module) or not bool(model.ForceRebuild3(True)):
                raise RuntimeError("默认 activation failed")
            rel_default = relative_rotation(assembly, index, types, pythoncom_module)
            if not m.show_config_ok(model, "STOWED_O13V3", base, types, pythoncom_module) or not bool(model.ForceRebuild3(True)):
                raise RuntimeError("STOWED activation failed")
            rel_stowed = relative_rotation(assembly, index, types, pythoncom_module)
            delta = mul(rel_stowed, tr(rel_default))
            vector = rotvec(delta)
            projected = sum(vector[i] * axis[i] for i in range(3))
            transverse = math.sqrt(max(0.0, sum(v * v for v in vector) - projected * projected))
            expected_delta = math.radians(float(stow_q[index - 1]))
            rows.append({
                "joint": joint["joint"],
                "expected_axis_parent": axis,
                "measured_delta_rad": projected,
                "transverse_rad": transverse,
                "authorized_delta_rad": expected_delta,
                "sign_match": projected * expected_delta > 0,
                "magnitude_error_rad": abs(abs(projected) - abs(expected_delta)),
            })
            log(f"{joint['joint']}: measured={projected:+.4f} authorized={expected_delta:+.4f} transverse={transverse:.5f} sign_match={projected * expected_delta > 0}")
        result["phases"]["convention"] = rows
        result["verdict"] = "V5_PROBE_LOOP1E_AXIS_CONVENTION_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_AXIS_CONVENTION_FAIL"
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
