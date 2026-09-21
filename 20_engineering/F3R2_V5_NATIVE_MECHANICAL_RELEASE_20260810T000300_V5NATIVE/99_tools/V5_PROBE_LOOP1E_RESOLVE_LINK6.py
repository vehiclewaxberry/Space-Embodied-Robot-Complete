#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: link6 resolve failure + fallback remedies.

Production run 20260811T2212 failed LOCAL_ARM_RESOLVE_FAIL on
B51_REF_link6_LINKLOCAL-1 (SetSuppression2(1) returned 2, readback stayed
LIGHTWEIGHT) after link1..link5 resolved, with read-only prebind parts and
STOWED_O13V3 the active config (the census loop ends in STOWED).  Per-config
census proves all 20 occurrences are LIGHTWEIGHT in both configs, so the
failure is not a per-config state anomaly.

This probe reproduces the production sequence EXACTLY (in-memory, NO SAVE):
  P1  read-only prebind (production), open assembly read-write, census both
      configs leaving STOWED active;
  P2  production resolve sandwich (per-iteration ForceRebuild3+readback) in
      GetComponents order; record every outcome;
  P3  on the first failure, try fallback remedies in order and record:
      (a) retry SetSuppression2(1) + rebuild;
      (b) activate 默认, retry;
      (c) IAssemblyDoc.ResolveAllLightWeightComponents(True) + rebuild;
      (d) IAssemblyDoc.ResolveOutOfDateLightWeightComponents(True) + rebuild;
  P4  continue the loop with the working remedy to scope all remaining;
  P5  discard WITHOUT saving; close; session census.

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
SW_COMPONENT_FULLY_RESOLVED = 1
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


def suppression(component: Any) -> int:
    return int(base.value(component, "GetSuppression2"))


def drive_resolve(model: Any, component: Any) -> Dict[str, Any]:
    returned = int(component.SetSuppression2(SW_COMPONENT_FULLY_RESOLVED))
    rebuilt = bool(model.ForceRebuild3(True))
    readback = suppression(component)
    return {"returned": returned, "rebuilt": rebuilt, "readback": readback, "readback_label": SUPPRESSION_LABEL.get(readback, str(readback)), "resolved": readback == SW_COMPONENT_FULLY_RESOLVED}


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_RESOLVE_LINK6_V1",
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
        try:
            result["memory_gib_start"] = round(base.available_gib(), 3)
        except Exception:  # noqa: BLE001
            pass
        log(f"attach ok pid={session['pid']}")

        # P1: production prebind (read-only) + read-write assembly + census
        for part in sorted(m.LOCAL_ARM_ROOT.rglob("*.SLDPRT")):
            open_form = m.sw_openable_path(part)
            raw2 = sw.OpenDoc6(open_form, m.SW_DOC_PART, 3, "", 0, 0)
            model_raw, outs = base.unpack(raw2)
            errors = int(outs[0]) if outs else 0
            if model_raw is None or errors != 0:
                raise RuntimeError(f"prebind open failed {part.name} errors={errors}")
        raw3 = sw.OpenDoc6(m.sw_openable_path(m.LOCAL_ARM), m.SW_DOC_ASSEMBLY, 1, "", 0, 0)
        model_raw, outs = base.unpack(raw3)
        errors = int(outs[0]) if outs else 0
        if model_raw is None or errors != 0:
            raise RuntimeError(f"assembly open failed errors={errors}")
        model = base.wrap(model_raw, "IModelDoc2", types, pythoncom_module)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom_module)
        for cfg in m.ARM_CONFIGS:
            if not m.show_config_ok(model, cfg, base, types, pythoncom_module):
                raise RuntimeError(f"census config activation failed {cfg}")
        log("P1 prebind RO + census done; STOWED active")

        # P2: production resolve sandwich
        attempts: List[Dict[str, Any]] = []
        failure: Dict[str, Any] = {}
        for raw2 in base.as_list(assembly.GetComponents(True)):
            component = base.wrap(raw2, "IComponent2", types, pythoncom_module)
            name2 = str(base.value(component, "Name2"))
            pre = suppression(component)
            if pre == SW_COMPONENT_FULLY_RESOLVED:
                attempts.append({"name2": name2, "pre": pre, "resolved": True})
                continue
            outcome = drive_resolve(model, component)
            attempts.append({"name2": name2, "pre": pre, **outcome})
            log(f"resolve {name2}: pre={SUPPRESSION_LABEL.get(pre)} -> {outcome['readback_label']} (resolved={outcome['resolved']})")
            if not outcome["resolved"]:
                failure = attempts[-1]
                break
        result["phases"]["P2_attempts"] = attempts

        # P3: fallback remedies on the first failure
        remedies: Dict[str, Any] = {}
        if failure:
            name2 = failure["name2"]
            component = None
            for raw2 in base.as_list(assembly.GetComponents(True)):
                candidate = base.wrap(raw2, "IComponent2", types, pythoncom_module)
                if str(base.value(candidate, "Name2")) == name2:
                    component = candidate
                    break
            if component is not None:
                remedies["a_retry"] = drive_resolve(model, component)
                log(f"remedy a retry: {remedies['a_retry']['readback_label']}")
                if not remedies["a_retry"]["resolved"]:
                    if not m.show_config_ok(model, m.ARM_CONFIGS[0], base, types, pythoncom_module):
                        remedies["b_config_error"] = "ACTIVATE_FAIL"
                    else:
                        remedies["b_default_config"] = drive_resolve(model, component)
                    log(f"remedy b 默认: {remedies.get('b_default_config', remedies.get('b_config_error'))}")
                if not any(remedies[key].get("resolved") for key in ("a_retry", "b_default_config") if isinstance(remedies.get(key), dict)):
                    try:
                        returned = assembly.ResolveAllLightWeightComponents(True)
                        rebuilt = bool(model.ForceRebuild3(True))
                        readback = suppression(component)
                        remedies["c_resolve_all"] = {"returned": returned, "rebuilt": rebuilt, "readback": readback, "readback_label": SUPPRESSION_LABEL.get(readback, str(readback)), "resolved": readback == SW_COMPONENT_FULLY_RESOLVED}
                    except Exception as exc:  # noqa: BLE001
                        remedies["c_resolve_all"] = {"exception": repr(exc)}
                    log(f"remedy c ResolveAll: {remedies['c_resolve_all']}")
                if not any(remedies[key].get("resolved") for key in ("a_retry", "b_default_config", "c_resolve_all") if isinstance(remedies.get(key), dict)):
                    try:
                        returned = assembly.ResolveOutOfDateLightWeightComponents(True)
                        rebuilt = bool(model.ForceRebuild3(True))
                        readback = suppression(component)
                        remedies["d_outofdate"] = {"returned": returned, "rebuilt": rebuilt, "readback": readback, "readback_label": SUPPRESSION_LABEL.get(readback, str(readback)), "resolved": readback == SW_COMPONENT_FULLY_RESOLVED}
                    except Exception as exc:  # noqa: BLE001
                        remedies["d_outofdate"] = {"exception": repr(exc)}
                    log(f"remedy d OutOfDate: {remedies['d_outofdate']}")
                # P4: continue the loop with whatever state we are in
                remaining_rows: List[Dict[str, Any]] = []
                for raw2 in base.as_list(assembly.GetComponents(True)):
                    candidate = base.wrap(raw2, "IComponent2", types, pythoncom_module)
                    pre = suppression(candidate)
                    if pre != SW_COMPONENT_FULLY_RESOLVED:
                        outcome = drive_resolve(model, candidate)
                        remaining_rows.append({"name2": str(base.value(candidate, "Name2")), "pre": pre, **outcome})
                        log(f"continue {remaining_rows[-1]['name2']}: -> {outcome['readback_label']}")
                result["phases"]["P4_continue"] = remaining_rows
        result["phases"]["P3_remedies"] = remedies

        final_states = {str(base.value(c, "Name2")): SUPPRESSION_LABEL.get(int(base.value(c, "GetSuppression2"))) for c in [base.wrap(r2, "IComponent2", types, pythoncom_module) for r2 in base.as_list(assembly.GetComponents(True))]}
        result["phases"]["P5_final_states"] = final_states
        remaining = close_everything(sw)
        result["phases"]["P5_cleanup_remaining"] = remaining
        try:
            result["memory_gib_end"] = round(base.available_gib(), 3)
        except Exception:  # noqa: BLE001
            pass
        log(f"P5 cleanup remaining={remaining}")

        remedy_used = next((key for key, value in remedies.items() if isinstance(value, dict) and value.get("resolved")), None)
        checks = {
            "failure_reproduced": bool(failure),
            "remedy_found": remedy_used is not None,
            "all_resolved_end": all(label == "RESOLVED" for label in final_states.values()),
            "session_document_empty_after_cleanup": remaining == 0,
        }
        result["checks"] = checks
        result["remedy_used"] = remedy_used
        result["verdict"] = "V5_PROBE_LOOP1E_RESOLVE_LINK6_PASS" if checks["remedy_found"] and checks["all_resolved_end"] else "V5_PROBE_LOOP1E_RESOLVE_LINK6_MIXED"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_RESOLVE_LINK6_FAIL"
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
    return 0 if result.get("verdict") == "V5_PROBE_LOOP1E_RESOLVE_LINK6_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
