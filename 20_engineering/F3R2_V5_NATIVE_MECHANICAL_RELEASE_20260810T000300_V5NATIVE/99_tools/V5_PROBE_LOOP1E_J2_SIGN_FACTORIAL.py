#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: joint2 driver sign-correction factorial.

Proven 2026-08-12: the accepted-axis convention is correct for all six
joints (AXIS_CONVENTION: STOWED-vs-默认 pose deltas match the authorized q
to 4 decimals, transverse 0, sign_match True everywhere).  joint2's native
datum hinge increases its mate angle in the -q2 direction, and no single
mate parameter flips it (flip/swap give +; anti-align re-poses grossly).

For a reversed joint the driver must satisfy: (a) creation at Angle=0 keeps
the q=0 pose, (b) driving to +0.5 deg yields delta = -0.5 deg on the
accepted axis with transverse ~0.  This probe runs the full factorial of
AddMate3 variants on FEMALE-2 x MALE-2 (swap entity order, Flip,
anti-align) with production delta metrics, testing BOTH zero-pose
preservation and the +0.5 deg drive direction.

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


def joint2_relative(assembly: Any, types: Any, pythoncom_module: Any) -> List[List[float]]:
    parent = find_leaf(assembly, "B51_REF_link1_LINKLOCAL-1", types, pythoncom_module)
    child = find_leaf(assembly, "B51_REF_link2_LINKLOCAL-1", types, pythoncom_module)
    return mul(tr(rot(t16(parent))), rot(t16(child)))


def measure(before: List[List[float]], after: List[List[float]], joint: Dict[str, Any]) -> Dict[str, Any]:
    delta = mul(after, tr(before))
    vector = rotvec(delta)
    expected = m.rpy_rotation(joint["origin_rpy"])
    axis = [sum(expected[r][i] * joint["axis_xyz"][i] for i in range(3)) for r in range(3)]
    norm = math.sqrt(sum(v * v for v in axis))
    axis = [v / norm for v in axis]
    projected = sum(vector[i] * axis[i] for i in range(3))
    transverse = math.sqrt(max(0.0, sum(v * v for v in vector) - projected * projected))
    return {"projected": projected, "transverse": transverse}


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


def attempt(model: Any, assembly: Any, joint: Dict[str, Any], angle: float, align: int, flip: bool, swap: bool, baseline: List[List[float]], types: Any, pythoncom_module: Any) -> Dict[str, Any]:
    female = find_leaf(assembly, "B51_REV_DATUM_FEMALE-2", types, pythoncom_module)
    male = find_leaf(assembly, "B51_REV_DATUM_MALE-2", types, pythoncom_module)
    first_component, second_component = (male, female) if swap else (female, male)
    first_plane = m.component_side_plane(first_component, base, types, pythoncom_module)
    second_plane = m.component_side_plane(second_component, base, types, pythoncom_module)
    before_names = set(m.mate_features(model, base, types, pythoncom_module))
    model.ClearSelection2(True)
    if not bool(first_plane.Select2(False, 1)) or not bool(second_plane.Select2(True, 1)):
        return {"error": "SELECT_FAIL"}
    returned = assembly.AddMate3(6, align, flip, 0.0, 0.0, 0.0, 0.0, 0.0, float(angle), float(joint["upper_rad"]), float(joint["lower_rad"]), False, 0)
    mate_raw, outs = base.unpack(returned)
    error = int(outs[0]) if outs else -1
    model.ClearSelection2(True)
    after = m.mate_features(model, base, types, pythoncom_module)
    additions = [item for name, item in after.items() if name not in before_names]
    out: Dict[str, Any] = {"align": align, "flip": flip, "swap": swap, "angle_arg": angle, "error_status": error, "additions": len(additions)}
    if mate_raw is not None and additions:
        out["pose_delta"] = measure(baseline, joint2_relative(assembly, types, pythoncom_module), joint)
        delete_feature(model, additions[0])
        model.ForceRebuild3(True)
    return out


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_J2_SIGN_FACTORIAL_V1",
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
        if not m.show_config_ok(model, m.ARM_CONFIGS[0], base, types, pythoncom_module) or not bool(model.ForceRebuild3(True)):
            raise RuntimeError("默认 activation failed")
        log("state ready")

        joint2 = m.accepted_urdf_joints()[1]
        probe = math.radians(0.5)
        baseline = joint2_relative(assembly, types, pythoncom_module)
        variants = []
        for swap in (False, True):
            for flip in (False, True):
                for align in (0, 1):
                    variants.append((swap, flip, align))
        for swap, flip, align in variants:
            # zero-pose preservation: create at angle 0
            zero = attempt(model, assembly, joint2, 0.0, align, flip, swap, baseline, types, pythoncom_module)
            drive = attempt(model, assembly, joint2, probe, align, flip, swap, baseline, types, pythoncom_module)
            key = f"swap={int(swap)},flip={int(flip)},align={align}"
            result["phases"][key] = {"zero_pose": zero, "drive": drive}
            zd = (zero.get("pose_delta") or {})
            dd = (drive.get("pose_delta") or {})
            log(f"{key}: zero_proj={zd.get('projected')} drive_proj={dd.get('projected')} drive_trans={dd.get('transverse')}")

        remaining = close_everything(sw)
        result["cleanup_remaining"] = remaining
        log(f"cleanup remaining={remaining}")
        result["verdict"] = "V5_PROBE_LOOP1E_J2_SIGN_FACTORIAL_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_J2_SIGN_FACTORIAL_FAIL"
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
