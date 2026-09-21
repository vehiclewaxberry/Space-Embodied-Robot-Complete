#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: validate resolve-first ReplaceComponents2 repair.

Probe 1 (V5_PROBE_LOOP1E_REPLACE_DISCRIMINATOR_20260811T210756Z.log) proved:
  * every top-level component of the protected donor AND of the staged
    V5-local copy is LIGHTWEIGHT (GetSuppression2 == 2) in both ARM_CONFIGS;
  * ReplaceComponents2 returns False for a byte-identical LIGHTWEIGHT control
    (B51_REF_base_link_LINKLOCAL-1), not only for the gripper detail, so the
    failure is not component-specific and not mate-specific at first order;
  * a failed ReplaceComponents2 on a LIGHTWEIGHT component leaves the old
    referenced document open INVISIBLE and unclosable (CloseDoc /
    CloseAllDocuments(True) / QuitDoc all leave GetDocumentCount == 1) — the
    same wedge class that terminated the previous Session B.

This probe validates the candidate production fix in-memory only (NO SAVE):
  P1  open the staged V5-local assembly (read-write), activate 默认, then
      IAssemblyDoc.ResolveAllLightWeightComponents(True); read back that every
      top-level component is fully RESOLVED (GetSuppression2 == 1);
  P2  run the production replace loop semantics per external component, but
      with a per-component resolve-first guard (SetSuppression2(1) + rebuild +
      readback) before Select4/ReplaceComponents2; record every outcome and
      the live document count after each replace (a successful replace must
      also close/release the wedged old document);
  P3  per-config readback of the gripper occurrence states (feasibility of the
      downstream suppression gate is unchanged: probe does not suppress);
  P4  discard WITHOUT saving and close everything; escalate CloseDoc ->
      CloseAllDocuments(True) -> QuitDoc; session must end document-empty.

Never writes inside the release tree, never mutates the protected donor,
never saves, and leaves Session B document-empty.
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
    attempts: List[str] = []
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
                attempts.append(f"CloseDoc({title})")
            except Exception as exc:  # noqa: BLE001
                attempts.append(f"CloseDoc({title}) EXC {exc!r}")
    if int(base.value(sw, "GetDocumentCount")):
        try:
            sw.CloseAllDocuments(True)
            attempts.append("CloseAllDocuments(True)")
        except Exception as exc:  # noqa: BLE001
            attempts.append(f"CloseAllDocuments EXC {exc!r}")
    for raw in base.as_list(base.value(sw, "GetDocuments")):
        try:
            sw.QuitDoc(str(base.value(raw, "GetTitle")))
            attempts.append("QuitDoc")
        except Exception as exc:  # noqa: BLE001
            attempts.append(f"QuitDoc EXC {exc!r}")
    return {"attempts": attempts, "remaining": int(base.value(sw, "GetDocumentCount")), "remaining_docs": doc_rows(sw)}


def component_rows(assembly: Any, types: Any, pythoncom_module: Any) -> List[Dict[str, Any]]:
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


def external_components(assembly: Any, types: Any, pythoncom_module: Any) -> List[Any]:
    externals: List[Any] = []
    for raw in base.as_list(assembly.GetComponents(True)):
        component = base.wrap(raw, "IComponent2", types, pythoncom_module)
        current = Path(str(base.value(component, "GetPathName"))).resolve()
        if m.LOCAL_ARM_ROOT.resolve() not in current.parents:
            externals.append(component)
    return externals


def local_target_for(current: Path) -> Optional[Path]:
    for source_root in (m.B51_DONOR_ROOT.resolve(), m.F3R1_B51_COPY_ROOT.resolve(), m.JULY_B51_DONOR_ROOT.resolve()):
        try:
            relative = current.relative_to(source_root)
            return (m.LOCAL_ARM_ROOT / relative).resolve()
        except ValueError:
            continue
    return None


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_RESOLVE_FIRST_REPLACE_V1",
        "timestamp_start_utc": datetime.now(timezone.utc).isoformat(),
        "prior_probe_log": "99_tools/probe_logs/V5_PROBE_LOOP1E_REPLACE_DISCRIMINATOR_20260811T210756Z.log",
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
        log(f"attach ok pid={session['pid']} rev={session['revision']} docs_before={len(result['docs_before'])}")

        # ---- P1: open staged copy, resolve all lightweight -----------------
        raw_model = sw.OpenDoc6(str(m.LOCAL_ARM), SW_DOC_ASSEMBLY, 1, "", 0, 0)
        model_raw, outs = base.unpack(raw_model)
        errors = int(outs[0]) if outs else 0
        if model_raw is None or errors != 0:
            raise RuntimeError(f"OpenDoc6 staged failed errors={errors}")
        model = base.wrap(model_raw, "IModelDoc2", types, pythoncom_module)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom_module)
        config = m.ARM_CONFIGS[0]
        if not m.show_config_ok(model, config, base, types, pythoncom_module):
            raise RuntimeError(f"config activation failed: {config}")
        before_rows = component_rows(assembly, types, pythoncom_module)
        assembly.ResolveAllLightWeightComponents(True)
        model.ForceRebuild3(True)
        after_rows = component_rows(assembly, types, pythoncom_module)
        unresolved = [row for row in after_rows if row["suppression"] != SW_COMPONENT_RESOLVED]
        result["phases"]["P1_before_resolve"] = before_rows
        result["phases"]["P1_after_resolve"] = after_rows
        result["phases"]["P1_unresolved_after"] = unresolved
        log(f"P1 resolve-all: {len(before_rows)} comps, unresolved_after={len(unresolved)}")
        if unresolved:
            raise RuntimeError(f"ResolveAllLightWeightComponents left {len(unresolved)} non-resolved")

        # ---- P2: resolve-first production replace semantics ----------------
        attempts: List[Dict[str, Any]] = []
        guard = 0
        while guard < 64:
            guard += 1
            externals = external_components(assembly, types, pythoncom_module)
            if not externals:
                break
            component = externals[0]
            name2 = str(base.value(component, "Name2"))
            current = Path(str(base.value(component, "GetPathName"))).resolve()
            target = local_target_for(current)
            if target is None or not target.is_file():
                attempts.append({"name2": name2, "error": "TARGET_UNRESOLVABLE", "current": str(current)})
                break
            pre = int(base.value(component, "GetSuppression2"))
            resolve_drive = None
            if pre != SW_COMPONENT_RESOLVED:
                returned = int(component.SetSuppression2(SW_COMPONENT_RESOLVED))
                model.ForceRebuild3(True)
                readback = int(base.value(component, "GetSuppression2"))
                resolve_drive = {"wanted": SW_COMPONENT_RESOLVED, "returned": returned, "readback": readback}
                if readback != SW_COMPONENT_RESOLVED:
                    attempts.append({"name2": name2, "resolve_drive": resolve_drive, "error": "RESOLVE_FIRST_FAILED"})
                    break
            docs_pre = int(base.value(sw, "GetDocumentCount"))
            model.ClearSelection2(True)
            selected = bool(component.Select4(False, None, False))
            replaced = bool(assembly.ReplaceComponents2(str(target), "", True, 2, True)) if selected else False
            model.ClearSelection2(True)
            docs_post = int(base.value(sw, "GetDocumentCount"))
            attempts.append({
                "order": guard,
                "name2": name2,
                "leaf": name2.split("/")[-1],
                "current": str(current).replace("\\", "/"),
                "target": str(target).replace("\\", "/"),
                "pre_suppression": pre,
                "resolve_drive": resolve_drive,
                "select": selected,
                "replace": replaced,
                "doc_count_pre": docs_pre,
                "doc_count_post": docs_post,
            })
            log(f"replace {name2}: select={selected} replace={replaced} docs {docs_pre}->{docs_post}")
            if not replaced:
                break
        result["phases"]["P2_attempts"] = attempts
        result["phases"]["P2_components_after"] = component_rows(assembly, types, pythoncom_module)
        result["phases"]["P2_docs_after_loop"] = doc_rows(sw)

        # ---- P3: per-config gripper state census (no suppression drive) ----
        per_config: Dict[str, Any] = {}
        for cfg in m.ARM_CONFIGS:
            if m.show_config_ok(model, cfg, base, types, pythoncom_module):
                rows = [row for row in component_rows(assembly, types, pythoncom_module) if row["name2"].split("/")[-1] == m.ARM_LEGACY_GRIPPER_LEAF]
                per_config[cfg] = rows
        result["phases"]["P3_gripper_per_config"] = per_config

        # ---- P4: discard without save --------------------------------------
        cleanup = close_everything(sw)
        result["phases"]["P4_cleanup"] = cleanup
        log(f"P4 cleanup remaining={cleanup['remaining']}")

        replaced_ok = [row for row in attempts if row.get("replace")]
        failed = [row for row in attempts if row.get("replace") is False]
        checks = {
            "resolve_all_succeeded": not unresolved,
            "all_external_replaces_succeeded": bool(attempts) and not failed and not external_components(assembly, types, pythoncom_module),
            "old_docs_closed_by_replace": all(row.get("doc_count_post", 0) <= row.get("doc_count_pre", 0) for row in replaced_ok),
            "session_document_empty_after_cleanup": cleanup["remaining"] == 0,
        }
        result["checks"] = checks
        result["verdict"] = "V5_PROBE_LOOP1E_RESOLVE_FIRST_REPLACE_PASS" if all(checks.values()) else "V5_PROBE_LOOP1E_RESOLVE_FIRST_REPLACE_MIXED"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_RESOLVE_FIRST_REPLACE_FAIL"
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
    return 0 if result.get("verdict") == "V5_PROBE_LOOP1E_RESOLVE_FIRST_REPLACE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
