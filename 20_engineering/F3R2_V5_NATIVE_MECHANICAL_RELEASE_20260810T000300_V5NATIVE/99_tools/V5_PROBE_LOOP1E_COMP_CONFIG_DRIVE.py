#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: selection-free component config drive for the ARM occurrence.

20260812T0936Z run (after the 8-arg CompConfigProperties6 fix) failed
COMP_CONFIG_SELECT_FAIL on the top-assembly ARM occurrence
(B51_B601_ARTICULATED_ENGINEERING_ARM-1): IComponent2.Select4 returns False
(likely a lightweight subassembly).  IComponent2 exposes ReferencedConfiguration
and Solving as read/write properties (gen_py propput accessors present), so
set_component_config may not need selection/CompConfigProperties6 at all.

In-memory only, NO SAVE:
  P1  new assembly from the production template; insert the local arm via the
      production insert_component helper; read the occurrence's suppression
      state and Select4 result (reproduce the failure);
  P2  direct property drive: ReferencedConfiguration=STOWED_O13V3 + readback;
      Solving=0 (flexible) + readback;
  P3  per-config independence: create top config STATE_B, drive ARM ref config
      per top configuration, verify 默认 keeps 默认 and STATE_B keeps STOWED;
  P4  discard WITHOUT saving; close; session census.

Never writes inside the release tree, never mutates the protected donor,
never saves.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import pythoncom  # noqa: E402
import win32com.client  # noqa: E402
from win32com.client import gencache  # noqa: E402

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base  # noqa: E402
import F3R2_V5_NATIVE_LOOP1E_TOP_ASSEMBLY_ATTACH_ONLY as m  # noqa: E402
import F3R2_V5_SESSION_BINDING as sbin  # noqa: E402

T0 = time.time()
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


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_COMP_CONFIG_DRIVE_V1",
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

        raw_model = sw.NewDocument(str(m.ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
        model = base.wrap(raw_model, "IModelDoc2", types, pythoncom_module)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom_module)
        component = m.insert_component(sw, model, assembly, m.LOCAL_ARM, m.IDENTITY_T16, base, types, pythoncom_module)
        suppression = int(base.value(component, "GetSuppression2"))
        select_ok = bool(component.Select4(False, None, False))
        result["phases"]["P1_inserted"] = {
            "name2": str(base.value(component, "Name2")),
            "suppression": suppression,
            "suppression_label": SUPPRESSION_LABEL.get(suppression, str(suppression)),
            "select4_ok": select_ok,
        }
        model.ClearSelection2(True)
        log(f"P1: suppression={SUPPRESSION_LABEL.get(suppression)} select4={select_ok}")

        # P2: direct property drive
        component.ReferencedConfiguration = "STOWED_O13V3"
        readback_config = str(base.value(component, "ReferencedConfiguration"))
        component.Solving = 0
        readback_solving = int(base.value(component, "Solving"))
        rebuilt = bool(model.ForceRebuild3(True))
        result["phases"]["P2_direct_drive"] = {"ref_config_readback": readback_config, "solving_readback": readback_solving, "rebuilt": rebuilt}
        log(f"P2: ref_config={readback_config} solving={readback_solving} rebuilt={rebuilt}")

        # P3: per-config independence
        manager = base.wrap(base.value(model, "ConfigurationManager"), "IConfigurationManager", types, pythoncom_module)
        active = base.wrap(base.value(manager, "ActiveConfiguration"), "IConfiguration", types, pythoncom_module)
        active.Name = "STATE_A"
        manager.AddConfiguration2("STATE_B", "probe", "", 0, "", "probe", True)
        # STATE_B currently active? activate STATE_A, set 默认; STATE_B set STOWED
        if not m.show_config_ok(model, "STATE_A", base, types, pythoncom_module):
            raise RuntimeError("STATE_A activation failed")
        component2 = None
        for raw2 in base.as_list(assembly.GetComponents(True)):
            component2 = base.wrap(raw2, "IComponent2", types, pythoncom_module)
        component2.ReferencedConfiguration = "默认"
        model.ForceRebuild3(True)
        if not m.show_config_ok(model, "STATE_B", base, types, pythoncom_module):
            raise RuntimeError("STATE_B activation failed")
        component3 = None
        for raw2 in base.as_list(assembly.GetComponents(True)):
            component3 = base.wrap(raw2, "IComponent2", types, pythoncom_module)
        component3.ReferencedConfiguration = "STOWED_O13V3"
        model.ForceRebuild3(True)
        reads: Dict[str, Any] = {}
        for cfg in ("STATE_A", "STATE_B"):
            if not m.show_config_ok(model, cfg, base, types, pythoncom_module):
                raise RuntimeError(f"{cfg} activation failed")
            for raw2 in base.as_list(assembly.GetComponents(True)):
                comp = base.wrap(raw2, "IComponent2", types, pythoncom_module)
                reads[cfg] = str(base.value(comp, "ReferencedConfiguration"))
        result["phases"]["P3_per_config"] = reads
        log(f"P3: {reads}")

        remaining = close_everything(sw)
        result["cleanup_remaining"] = remaining
        log(f"cleanup remaining={remaining}")
        checks = {
            "direct_config_drive_ok": readback_config == "STOWED_O13V3",
            "solving_drive_ok": readback_solving == 0,
            "per_config_independent": reads.get("STATE_A") == "默认" and reads.get("STATE_B") == "STOWED_O13V3",
            "session_document_empty_after_cleanup": remaining == 0,
        }
        result["checks"] = checks
        result["verdict"] = "V5_PROBE_LOOP1E_COMP_CONFIG_DRIVE_PASS" if all(checks.values()) else "V5_PROBE_LOOP1E_COMP_CONFIG_DRIVE_MIXED"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_COMP_CONFIG_DRIVE_FAIL"
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
    return 0 if result.get("verdict") == "V5_PROBE_LOOP1E_COMP_CONFIG_DRIVE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
