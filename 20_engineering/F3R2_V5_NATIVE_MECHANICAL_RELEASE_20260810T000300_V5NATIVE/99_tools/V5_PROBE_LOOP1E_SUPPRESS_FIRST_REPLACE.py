#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: suppress-first ReplaceComponents2 rebase technique.

Established so far (logs in 99_tools/probe_logs/, 2026-08-11):
  * probe 1: every top-level component of the staged copy is LIGHTWEIGHT;
    ReplaceComponents2 returns False on a LIGHTWEIGHT component (control
    base_link failed identically to the gripper); a failed replace leaks the
    old document as an INVISIBLE unclosable doc (the wedge class that ended
    the previous Session B; one such wedge is still present).
  * probe 3/4: resolve-first (SetSuppression2(1)) makes ReplaceComponents2
    return True for BOTH externals, and new instances come back LIGHTWEIGHT —
    but fresh enumeration proves the reference STAYS on the F3R1 lineage path:
    resolving loads the current same-name document, and SolidWorks' open
    same-name document wins over the replacement path.  Resolve-first is a
    silent path no-op; the LOCAL_ARM_REFERENCE_ESCAPE cold audit would fail.

Candidate real rebase: SUPPRESS the occurrence first.  Suppression unloads
the referenced document from the session, so ReplaceComponents2(target) has
no open same-name competitor and must bind the V5-local file; the replacement
inherits the suppressed state (which is the legacy gripper's required end
state anyway; base_link is restored to LIGHTWEIGHT afterwards).

In-memory only, NO SAVE:
  P1  gripper: SetSuppression2(0) + rebuild + readback; doc census (the F3R1
      gripper doc must be UNLOADED); ReplaceComponents2(V5-local); fresh
      census -> path must be V5-local, state suppressed(0);
  P2  base_link: same suppress-first replace; fresh census -> V5-local; then
      restore LIGHTWEIGHT (SetSuppression2(2) + rebuild + readback == 2);
  P3  discard WITHOUT saving; close; session census (pre-existing F3R1
      base_link wedge is expected to remain and is recorded, not created
      here).

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
SW_COMPONENT_SUPPRESSED = 0
SW_COMPONENT_RESOLVED = 1
SW_COMPONENT_LIGHTWEIGHT = 2
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


def find_leaf(assembly: Any, leaf: str, types: Any, pythoncom_module: Any) -> Optional[Any]:
    for raw in base.as_list(assembly.GetComponents(True)):
        candidate = base.wrap(raw, "IComponent2", types, pythoncom_module)
        if str(base.value(candidate, "Name2")).split("/")[-1] == leaf:
            return candidate
    return None


def suppress_first_replace(model: Any, assembly: Any, leaf: str, restore_lightweight: bool, sw: Any, types: Any, pythoncom_module: Any) -> Dict[str, Any]:
    component = find_leaf(assembly, leaf, types, pythoncom_module)
    if component is None:
        return {"error": "COMPONENT_NOT_FOUND"}
    current = Path(str(base.value(component, "GetPathName"))).resolve()
    local = local_target_for(current)
    if local is None or not local.is_file():
        return {"error": "TARGET_UNRESOLVABLE", "current": str(current).replace("\\", "/")}
    out: Dict[str, Any] = {"leaf": leaf, "current": str(current).replace("\\", "/"), "target": str(local).replace("\\", "/")}
    out["pre_suppression"] = int(base.value(component, "GetSuppression2"))
    returned = int(component.SetSuppression2(SW_COMPONENT_SUPPRESSED))
    model.ForceRebuild3(True)
    readback = int(base.value(component, "GetSuppression2"))
    out["suppress_drive"] = {"returned": returned, "readback": readback, "readback_label": SUPPRESSION_LABEL.get(readback, str(readback))}
    if readback != SW_COMPONENT_SUPPRESSED:
        out["error"] = "SUPPRESS_FIRST_FAILED"
        return out
    out["docs_after_suppress"] = doc_rows(sw)
    model.ClearSelection2(True)
    out["select"] = bool(component.Select4(False, None, False))
    out["replace"] = bool(assembly.ReplaceComponents2(str(local), "", True, 2, True)) if out["select"] else False
    model.ClearSelection2(True)
    model.ForceRebuild3(True)
    rows = fresh_rows(assembly, types, pythoncom_module)
    out["new_instance"] = [row for row in rows if row["name2"].split("/")[-1] == leaf]
    out["docs_after_replace"] = doc_rows(sw)
    if restore_lightweight:
        component2 = find_leaf(assembly, leaf, types, pythoncom_module)
        if component2 is None:
            out["restore_error"] = "NEW_INSTANCE_HANDLE_NOT_FOUND"
        else:
            returned2 = int(component2.SetSuppression2(SW_COMPONENT_LIGHTWEIGHT))
            model.ForceRebuild3(True)
            readback2 = int(base.value(component2, "GetSuppression2"))
            out["restore_lightweight_drive"] = {"returned": returned2, "readback": readback2, "readback_label": SUPPRESSION_LABEL.get(readback2, str(readback2))}
            out["final_instance"] = [row for row in fresh_rows(assembly, types, pythoncom_module) if row["name2"].split("/")[-1] == leaf]
    return out


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_SUPPRESS_FIRST_REPLACE_V1",
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

        gripper = suppress_first_replace(model, assembly, m.ARM_LEGACY_GRIPPER_LEAF, False, sw, types, pythoncom_module)
        result["phases"]["P1_gripper"] = gripper
        log(f"P1 gripper: replace={gripper.get('replace')} new={gripper.get('new_instance')}")
        base_link = suppress_first_replace(model, assembly, "B51_REF_base_link_LINKLOCAL-1", True, sw, types, pythoncom_module)
        result["phases"]["P2_base_link"] = base_link
        log(f"P2 base_link: replace={base_link.get('replace')} final={base_link.get('final_instance')}")

        cleanup = close_everything(sw)
        result["phases"]["P3_cleanup"] = cleanup
        log(f"P3 cleanup remaining={cleanup['remaining']}")

        def rebound_local(data: Dict[str, Any]) -> bool:
            rows = data.get("final_instance") or data.get("new_instance") or []
            return bool(rows) and "_native_donor_local" in str(rows[0].get("path"))

        checks = {
            "gripper_replace_true": gripper.get("replace") is True,
            "gripper_rebound_v5_local": rebound_local(gripper),
            "gripper_end_suppressed": bool(gripper.get("new_instance")) and gripper["new_instance"][0].get("suppression") == SW_COMPONENT_SUPPRESSED,
            "gripper_f3r1_doc_unloaded_after_suppress": not any("gripper_detail" in d["title"] for d in gripper.get("docs_after_suppress", [])),
            "base_link_replace_true": base_link.get("replace") is True,
            "base_link_rebound_v5_local": rebound_local(base_link),
            "base_link_restored_lightweight": bool(base_link.get("final_instance")) and base_link["final_instance"][0].get("suppression") == SW_COMPONENT_LIGHTWEIGHT,
        }
        result["checks"] = checks
        functional = [k for k in checks if not k.startswith("session_")]
        result["verdict"] = "V5_PROBE_LOOP1E_SUPPRESS_FIRST_REPLACE_PASS" if all(checks[k] for k in functional) else "V5_PROBE_LOOP1E_SUPPRESS_FIRST_REPLACE_MIXED"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_SUPPRESS_FIRST_REPLACE_FAIL"
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
    return 0 if result.get("verdict") == "V5_PROBE_LOOP1E_SUPPRESS_FIRST_REPLACE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
