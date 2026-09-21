#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: authoritative post-replace component state.

Probe 3 (V5_PROBE_LOOP1E_PER_COMPONENT_RESOLVE_20260811T211545Z.log) proved
resolve-first ReplaceComponents2 succeeds for both externals (gripper detail
and base_link) — but its post-row read used the STALE pre-replace component
handle, so the NEW instance's load state (lightweight vs resolved) and bound
path are unknown.  That state decides whether the Loop1E patch must restore
lightweight state before Save3 (the donor convention every downstream gate
expects: MOTION/COLD gates accept only suppression==2 lightweight or the
whitelisted suppressed legacy gripper).

In-memory only, NO SAVE:
  P1  open the staged copy, resolve-first replace the gripper detail exactly
      as the patched production loop will, then FRESH-re-enumerate all
      top-level components: authoritative (name2, path, suppression) of the
      new gripper instance and of the still-external base_link;
  P2  same fresh census after the base_link replace;
  P3  discard WITHOUT saving; close; session census (the F3R1 base_link
      invisible wedge from probes 1-3 is expected to remain and is recorded).

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
SW_DOC_ASSEMBLY = 2
SW_COMPONENT_RESOLVED = 1
SUPPRESSION_LABEL = {0: "SUPPRESSED", 1: "RESOLVED", 2: "LIGHTWEIGHT"}
PROTECTED_WATCH = [m.B51_DONOR] + sorted(m.B51_DONOR_ROOT.rglob("*.SLDPRT"))


def log(step: str) -> None:
    print(f"[{time.time() - T0:8.2f}s] {step}", flush=True)


def doc_rows(sw: Any) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for raw in base.as_list(base.value(sw, "GetDocuments")):
        try:
            rows.append({"title": str(base.value(raw, "GetTitle")), "path": str(base.value(raw, "GetPathName")).replace("\\", "/")})
        except Exception as exc:  # noqa: BLE001
            rows.append({"title": "<?>", "path": repr(exc)})
    return rows


def close_everything(sw: Any) -> Dict[str, Any]:
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
    for raw in base.as_list(base.value(sw, "GetDocuments")):
        try:
            sw.QuitDoc(str(base.value(raw, "GetTitle")))
        except Exception:  # noqa: BLE001
            pass
    return {"remaining": int(base.value(sw, "GetDocumentCount")), "remaining_docs": doc_rows(sw)}


def fresh_rows(assembly: Any, types: Any, pythoncom_module: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for raw in base.as_list(assembly.GetComponents(True)):
        component = base.wrap(raw, "IComponent2", types, pythoncom_module)
        suppression = int(base.value(component, "GetSuppression2"))
        rows.append({
            "name2": str(base.value(component, "Name2")),
            "path": str(base.value(component, "GetPathName")).replace("\\", "/"),
            "suppression": suppression,
            "suppression_label": SUPPRESSION_LABEL.get(suppression, str(suppression)),
        })
    return sorted(rows, key=lambda row: row["name2"])


def local_target_for(current: Path) -> Optional[Path]:
    for source_root in (m.B51_DONOR_ROOT.resolve(), m.F3R1_B51_COPY_ROOT.resolve(), m.JULY_B51_DONOR_ROOT.resolve()):
        try:
            return (m.LOCAL_ARM_ROOT / current.relative_to(source_root)).resolve()
        except ValueError:
            continue
    return None


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_POST_REPLACE_STATE_V1",
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
        result["session"] = session
        result["protected_pre"] = {m.sha256(path): str(path) for path in PROTECTED_WATCH if path.is_file()}
        result["docs_before"] = doc_rows(sw)
        log(f"attach ok pid={session['pid']} docs_before={len(result['docs_before'])}")

        raw_model = sw.OpenDoc6(str(m.LOCAL_ARM), SW_DOC_ASSEMBLY, 1, "", 0, 0)
        model_raw, outs = base.unpack(raw_model)
        errors = int(outs[0]) if outs else 0
        if model_raw is None or errors != 0:
            raise RuntimeError(f"OpenDoc6 staged failed errors={errors}")
        model = base.wrap(model_raw, "IModelDoc2", types, pythoncom_module)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom_module)
        if not m.show_config_ok(model, m.ARM_CONFIGS[0], base, types, pythoncom_module):
            raise RuntimeError("config activation failed")
        result["phases"]["P0_initial"] = fresh_rows(assembly, types, pythoncom_module)

        censuses: Dict[str, Any] = {}
        for leaf in (m.ARM_LEGACY_GRIPPER_LEAF, "B51_REF_base_link_LINKLOCAL-1"):
            target_component = None
            for raw in base.as_list(assembly.GetComponents(True)):
                candidate = base.wrap(raw, "IComponent2", types, pythoncom_module)
                if str(base.value(candidate, "Name2")).split("/")[-1] == leaf:
                    target_component = candidate
                    break
            if target_component is None:
                censuses[leaf] = {"error": "COMPONENT_NOT_FOUND"}
                continue
            current = Path(str(base.value(target_component, "GetPathName"))).resolve()
            local = local_target_for(current)
            if local is None or not local.is_file():
                censuses[leaf] = {"error": "TARGET_UNRESOLVABLE", "current": str(current).replace("\\", "/")}
                continue
            pre = int(base.value(target_component, "GetSuppression2"))
            drive = None
            if pre != SW_COMPONENT_RESOLVED:
                returned = int(target_component.SetSuppression2(SW_COMPONENT_RESOLVED))
                model.ForceRebuild3(True)
                readback = int(base.value(target_component, "GetSuppression2"))
                drive = {"returned": returned, "readback": readback}
                if readback != SW_COMPONENT_RESOLVED:
                    censuses[leaf] = {"error": "RESOLVE_FIRST_FAILED", "drive": drive}
                    continue
            model.ClearSelection2(True)
            selected = bool(target_component.Select4(False, None, False))
            replaced = bool(assembly.ReplaceComponents2(str(local), "", True, 2, True)) if selected else False
            model.ClearSelection2(True)
            model.ForceRebuild3(True)
            rows = fresh_rows(assembly, types, pythoncom_module)
            censuses[leaf] = {
                "pre_suppression": pre,
                "resolve_drive": drive,
                "select": selected,
                "replace": replaced,
                "new_instance": [row for row in rows if row["name2"].split("/")[-1] == leaf],
                "all_rows": rows,
                "docs": doc_rows(sw),
            }
            log(f"replace {leaf}: {replaced}; new_instance={censuses[leaf]['new_instance']}")
        result["phases"]["P1P2_replaces"] = censuses

        cleanup = close_everything(sw)
        result["phases"]["P3_cleanup"] = cleanup
        log(f"P3 cleanup remaining={cleanup['remaining']}")

        states = {leaf: (data.get("new_instance") or [{}])[0].get("suppression") for leaf, data in censuses.items()}
        paths = {leaf: (data.get("new_instance") or [{}])[0].get("path") for leaf, data in censuses.items()}
        result["checks"] = {
            "both_replaced": all(data.get("replace") for data in censuses.values()),
            "new_instances_local": all(isinstance(path, str) and "_native_donor_local" in path for path in paths.values()),
            "new_instance_suppression": states,
        }
        result["verdict"] = (
            "V5_PROBE_LOOP1E_POST_REPLACE_STATE_PASS"
            if result["checks"]["both_replaced"] and result["checks"]["new_instances_local"]
            else "V5_PROBE_LOOP1E_POST_REPLACE_STATE_MIXED"
        )
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_POST_REPLACE_STATE_FAIL"
        log("exception; see payload")
    finally:
        if sw is not None:
            try:
                leftover = close_everything(sw)
                result["cleanup_document_count"] = leftover["remaining"]
                if leftover["remaining"]:
                    result["cleanup_leftover_docs"] = leftover["remaining_docs"]
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
    return 0 if result.get("verdict") == "V5_PROBE_LOOP1E_POST_REPLACE_STATE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
