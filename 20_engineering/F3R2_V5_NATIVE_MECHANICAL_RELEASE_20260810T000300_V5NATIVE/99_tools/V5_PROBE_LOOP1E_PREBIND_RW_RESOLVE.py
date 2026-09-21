#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: read-only vs read-write prebind for full resolve.

Production run 20260811T2212 failed LOCAL_ARM_RESOLVE_FAIL on
B51_REF_link6_LINKLOCAL-1 (SetSuppression2(1) returned 2, readback stayed
LIGHTWEIGHT) while link1..link5 resolved — with the ten V5-local parts
pre-opened READ-ONLY.  Probe 3 (PER_COMPONENT_RESOLVE) resolved all 20
occurrences with the parts open as read-write dependents.  Hypothesis: a
read-only part document can block the lightweight->resolved load-state
change for some components.

This probe reproduces the production sequence IN-MEMORY ONLY (NO SAVE):
  P1  pre-open all ten staged parts READ-WRITE (silent), open the staged
      assembly, activate 默认;
  P2  per-component resolve drive with per-iteration ForceRebuild3+readback
      (the exact production sandwich) — must reach 20/20 RESOLVED;
  P3  transform sanity: component_transform16-equivalent read on base_link
      (the ARM_COMPONENT_TRANSFORM_FAIL site) must return 16 finite values;
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


def open_doc(sw: Any, path_str: str, doc_type: int, read_only: bool, types: Any, pythoncom_module: Any) -> Any:
    options = 1 | (2 if read_only else 0)
    raw = sw.OpenDoc6(path_str, doc_type, options, "", 0, 0)
    model_raw, outs = base.unpack(raw)
    errors = int(outs[0]) if outs else 0
    if model_raw is None or errors != 0:
        raise RuntimeError(f"OpenDoc6 failed path={path_str[-60:]} errors={errors}")
    return base.wrap(model_raw, "IModelDoc2", types, pythoncom_module)


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_PREBIND_RW_RESOLVE_V1",
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

        # P1: prebind READ-WRITE (silent), then open the assembly
        for part in sorted(m.LOCAL_ARM_ROOT.rglob("*.SLDPRT")):
            open_doc(sw, m.sw_openable_path(part), m.SW_DOC_PART, False, types, pythoncom_module)
        model = open_doc(sw, m.sw_openable_path(m.LOCAL_ARM), m.SW_DOC_ASSEMBLY, False, types, pythoncom_module)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom_module)
        if not m.show_config_ok(model, m.ARM_CONFIGS[0], base, types, pythoncom_module):
            raise RuntimeError("config activation failed")
        log("P1 prebind RW + assembly open ok")

        # P2: production resolve sandwich
        rows: List[Dict[str, Any]] = []
        comps = [base.wrap(raw2, "IComponent2", types, pythoncom_module) for raw2 in base.as_list(assembly.GetComponents(True))]
        for component in comps:
            name2 = str(base.value(component, "Name2"))
            pre = int(base.value(component, "GetSuppression2"))
            entry: Dict[str, Any] = {"name2": name2, "pre": SUPPRESSION_LABEL.get(pre, pre)}
            if pre != m.SW_COMPONENT_FULLY_RESOLVED:
                returned = int(component.SetSuppression2(m.SW_COMPONENT_FULLY_RESOLVED))
                rebuilt = bool(model.ForceRebuild3(True))
                readback = int(base.value(component, "GetSuppression2"))
                entry.update({"returned": returned, "rebuilt": rebuilt, "post": SUPPRESSION_LABEL.get(readback, readback), "resolved": readback == m.SW_COMPONENT_FULLY_RESOLVED})
            else:
                entry["resolved"] = True
            rows.append(entry)
            log(f"resolve {name2}: {entry['pre']} -> {entry.get('post', 'RESOLVED')}")
        result["phases"]["P2_resolve"] = rows
        unresolved = [r for r in rows if not r.get("resolved")]

        # P3: transform sanity on base_link
        sanity: Dict[str, Any] = {}
        for component in [base.wrap(raw2, "IComponent2", types, pythoncom_module) for raw2 in base.as_list(assembly.GetComponents(True))]:
            if str(base.value(component, "Name2")).split("/")[-1] == "B51_REF_base_link_LINKLOCAL-1":
                try:
                    values = [float(value) for value in base.as_list(base.value(base.value(component, "Transform2"), "ArrayData"))]
                    sanity = {"count": len(values), "finite": len(values) == 16}
                except Exception as exc:  # noqa: BLE001
                    sanity = {"exception": repr(exc)}
                break
        result["phases"]["P3_transform_sanity"] = sanity
        log(f"P3 transform sanity: {sanity}")

        remaining = close_everything(sw)
        result["phases"]["P4_cleanup_remaining"] = remaining
        log(f"P4 cleanup remaining={remaining}")

        checks = {
            "all_resolved": not unresolved,
            "transform_16_finite": sanity.get("finite") is True,
            "session_document_empty_after_cleanup": remaining == 0,
        }
        result["checks"] = checks
        result["unresolved"] = unresolved
        result["verdict"] = "V5_PROBE_LOOP1E_PREBIND_RW_RESOLVE_PASS" if all(checks.values()) else "V5_PROBE_LOOP1E_PREBIND_RW_RESOLVE_MIXED"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_PREBIND_RW_RESOLVE_FAIL"
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
    return 0 if result.get("verdict") == "V5_PROBE_LOOP1E_PREBIND_RW_RESOLVE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
