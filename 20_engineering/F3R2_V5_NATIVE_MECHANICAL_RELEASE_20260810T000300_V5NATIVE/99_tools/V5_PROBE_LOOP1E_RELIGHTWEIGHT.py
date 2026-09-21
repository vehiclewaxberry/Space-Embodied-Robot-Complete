#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: re-lightweight drive on a dependent-resolved component.

20260812T0841Z run passed all six joint drivers/sign probes/flips/seeds,
then failed LOCAL_ARM_RELIGHTWEIGHT_FAIL on base_link: SetSuppression2(2)
returned 2 but readback stayed RESOLVED(1) after a per-iteration rebuild.
The re-lightweight must restore the donor convention before Save3 (the
top-assembly gates expect suppression==2 for all non-gripper components).

Variants under test (in-memory, NO SAVE, production state):
  V1  production sequence: SetSuppression2(2) + ForceRebuild3 + readback;
  V2  two more V1 attempts (retry);
  V3  SetSuppression2(2) with NO rebuild, immediate readback;
  V4  config round-trip (STOWED then 默认) then V1;
  V5  assembly-level LightweightAllResolved? no - IAssemblyDoc has
      LightweightAllResolved/ResolveAllLightweight helpers? recorded only.

Record per-variant returned/readback.  Never writes inside the release
tree, never mutates the protected donor, never saves; session left
document-empty.
"""

from __future__ import annotations

import json
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
SW_COMPONENT_LIGHTWEIGHT = 2
SUPPRESSION_LABEL = {0: "SUPPRESSED", 1: "RESOLVED", 2: "LIGHTWEIGHT"}
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


def drive(model: Any, component: Any, state: int, rebuild: bool = True) -> Dict[str, Any]:
    returned = int(component.SetSuppression2(state))
    if rebuild:
        model.ForceRebuild3(True)
    readback = int(base.value(component, "GetSuppression2"))
    return {"wanted": state, "returned": returned, "readback": readback, "readback_label": SUPPRESSION_LABEL.get(readback, str(readback)), "ok": readback == state}


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_RELIGHTWEIGHT_V1",
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
        log("state ready (all resolved)")

        phases: Dict[str, Any] = {}
        base_link = find_leaf(assembly, "B51_REF_base_link_LINKLOCAL-1", types, pythoncom_module)
        phases["V1_first"] = drive(model, base_link, SW_COMPONENT_LIGHTWEIGHT)
        log(f"V1: {phases['V1_first']}")
        if not phases["V1_first"]["ok"]:
            base_link = find_leaf(assembly, "B51_REF_base_link_LINKLOCAL-1", types, pythoncom_module)
            phases["V2_retry1"] = drive(model, base_link, SW_COMPONENT_LIGHTWEIGHT)
            if not phases["V2_retry1"]["ok"]:
                base_link = find_leaf(assembly, "B51_REF_base_link_LINKLOCAL-1", types, pythoncom_module)
                phases["V2_retry2"] = drive(model, base_link, SW_COMPONENT_LIGHTWEIGHT)
            log(f"V2: { {k: v['readback_label'] for k, v in phases.items() if k.startswith('V2')} }")
        if not phases.get("V1_first", {}).get("ok") and not all(v.get("ok") for k, v in phases.items() if k.startswith("V2")):
            base_link = find_leaf(assembly, "B51_REF_base_link_LINKLOCAL-1", types, pythoncom_module)
            phases["V3_no_rebuild"] = drive(model, base_link, SW_COMPONENT_LIGHTWEIGHT, rebuild=False)
            model.ForceRebuild3(True)
            phases["V3_readback_after_late_rebuild"] = int(base.value(find_leaf(assembly, "B51_REF_base_link_LINKLOCAL-1", types, pythoncom_module), "GetSuppression2"))
            log(f"V3: {phases['V3_no_rebuild']} late={phases['V3_readback_after_late_rebuild']}")
        if not any(v.get("ok") for v in phases.values() if isinstance(v, dict)):
            if not m.show_config_ok(model, "STOWED_O13V3", base, types, pythoncom_module):
                raise RuntimeError("STOWED activation failed")
            if not m.show_config_ok(model, "默认", base, types, pythoncom_module):
                raise RuntimeError("默认 re-activation failed")
            base_link = find_leaf(assembly, "B51_REF_base_link_LINKLOCAL-1", types, pythoncom_module)
            phases["V4_config_roundtrip"] = drive(model, base_link, SW_COMPONENT_LIGHTWEIGHT)
            log(f"V4: {phases['V4_config_roundtrip']}")
        if not any(v.get("ok") for v in phases.values() if isinstance(v, dict)):
            # V5: two-step 1->0->2 (suppress then lightweight; 0->2 proven
            # in probe SUPPRESS_FIRST_REPLACE restore drives).
            base_link = find_leaf(assembly, "B51_REF_base_link_LINKLOCAL-1", types, pythoncom_module)
            step1 = drive(model, base_link, 0)
            base_link = find_leaf(assembly, "B51_REF_base_link_LINKLOCAL-1", types, pythoncom_module)
            step2 = drive(model, base_link, SW_COMPONENT_LIGHTWEIGHT)
            phases["V5_two_step"] = {"suppress_first": step1, "then_lightweight": step2}
            log(f"V5 two-step: suppress ok={step1['ok']} lightweight ok={step2['ok']}")
        result["phases"] = phases

        remaining = close_everything(sw)
        result["cleanup_remaining"] = remaining
        log(f"cleanup remaining={remaining}")
        result["verdict"] = "V5_PROBE_LOOP1E_RELIGHTWEIGHT_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_RELIGHTWEIGHT_FAIL"
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
