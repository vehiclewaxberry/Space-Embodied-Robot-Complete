#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: A/B discrimination of ModifyDefinition poisoning.

The production add_native_angle_driver succeeded in runs 20260811T2238
(STOWED active, only base_link reloaded) and 20260811T2251 (full 18
dependent-reload + 默认 activation gate), but fails at
ANGLE_MATE_ADVANCED_FAIL in probe-replicated states.  This A/B probe
recreates both exact sequences on fresh opens of the staged tree and
records ModifyDefinition/ rebuild outcomes plus the angle-mate definition
before and after the call (in-memory only, NO SAVE):
  A  prebind -> open -> census both configs -> add_native_angle_driver
     (22:38-like: STOWED active, no reload);
  B  prebind -> open -> census -> full dependent-reload -> 默认 gate ->
     add_native_angle_driver (22:51-like);
plus a control read of the created mate's data.Angle and the dimension
drive truth for whichever arm succeeds.

Never writes inside the release tree, never mutates the protected donor,
never saves; session left document-empty.
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


def prebind_and_open(sw: Any, types: Any, pythoncom_module: Any) -> Any:
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
    for cfg in m.ARM_CONFIGS:
        if not m.show_config_ok(model, cfg, base, types, pythoncom_module):
            raise RuntimeError(f"census config failed {cfg}")
    return model


def attempt_driver(model: Any, types: Any, pythoncom_module: Any, label: str) -> Dict[str, Any]:
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom_module)
    joint = m.accepted_urdf_joints()[0]
    female = find_leaf(assembly, "B51_REV_DATUM_FEMALE-1", types, pythoncom_module)
    male = find_leaf(assembly, "B51_REV_DATUM_MALE-1", types, pythoncom_module)
    out: Dict[str, Any] = {"label": label}
    try:
        feature, dimension, creation = m.add_native_angle_driver(model, assembly, female, male, joint, base, types, pythoncom_module)
        data = m.angle_mate_data(feature, base, types, pythoncom_module)
        out["ok"] = True
        out["creation"] = creation
        out["data_angle"] = float(base.value(data, "Angle"))
        out["advanced"] = bool(base.value(data, "IsAdvancedMate"))
        out["limits"] = [float(base.value(data, "MinimumAngle")), float(base.value(data, "MaximumAngle"))]
        # drive truth: +0.5 deg, read back mate angle
        probe = math.radians(0.5)
        status = int(dimension.SetSystemValue3(probe, 3, [m.ARM_CONFIGS[0]]))
        rebuilt = bool(model.ForceRebuild3(True))
        data2 = m.angle_mate_data(feature, base, types, pythoncom_module)
        out["drive"] = {"status": status, "rebuilt": rebuilt, "data_angle_after": float(base.value(data2, "Angle")), "dimension_value_after": [float(v) for v in base.as_list(dimension.GetSystemValue3(3, [m.ARM_CONFIGS[0]]))]}
    except Exception as exc:  # noqa: BLE001
        out["ok"] = False
        out["exception"] = repr(exc)
    return out


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_MODIFY_AB_V1",
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

        # ---- Arm A: 22:38-like (STOWED active, no reload) -----------------
        model_a = prebind_and_open(sw, types, pythoncom_module)
        out_a = attempt_driver(model_a, types, pythoncom_module, "A_stowed_no_reload")
        result["phases"]["A"] = out_a
        log(f"A: ok={out_a['ok']} {out_a.get('exception', '')[:120]}")
        if close_everything(sw) != 0:
            raise RuntimeError("Arm A close left documents open")

        # ---- Arm B: 22:51-like (full reload + 默认 gate) ------------------
        model_b = prebind_and_open(sw, types, pythoncom_module)
        assembly_b = base.wrap(model_b, "IAssemblyDoc", types, pythoncom_module)
        for raw2 in base.as_list(assembly_b.GetComponents(True)):
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
            if not bool(model_b.ForceRebuild3(True)):
                raise RuntimeError(f"B reload rebuild failed {name2}")
        if not m.show_config_ok(model_b, m.ARM_CONFIGS[0], base, types, pythoncom_module) or not bool(model_b.ForceRebuild3(True)):
            raise RuntimeError("B 默认 activation failed")
        out_b = attempt_driver(model_b, types, pythoncom_module, "B_default_full_reload")
        result["phases"]["B"] = out_b
        log(f"B: ok={out_b['ok']} {out_b.get('exception', '')[:120]}")
        if close_everything(sw) != 0:
            raise RuntimeError("Arm B close left documents open")

        result["cleanup_document_count"] = int(base.value(sw, "GetDocumentCount"))
        result["verdict"] = "V5_PROBE_LOOP1E_MODIFY_AB_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_MODIFY_AB_FAIL"
        log("exception; see payload")
    finally:
        if sw is not None:
            try:
                result["cleanup_remaining"] = close_everything(sw)
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
