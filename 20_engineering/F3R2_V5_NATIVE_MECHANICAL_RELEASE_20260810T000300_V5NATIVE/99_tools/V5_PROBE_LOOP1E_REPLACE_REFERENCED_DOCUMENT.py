#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: ISldWorks.ReplaceReferencedDocument rebase technique.

Established so far (logs in 99_tools/probe_logs/, 2026-08-11):
  * ReplaceComponents2 returns False on LIGHTWEIGHT components (probe 1);
  * resolve-first makes it return True but the reference STAYS on the lineage
    path — the open same-name document wins (probe 3/4, fresh enumeration);
  * suppress-first unloads the referenced doc yet the replace STILL returns
    True with the path unchanged (probe 5) — ReplaceComponents2 is name-bound
    and cannot re-point a reference to a same-name file in another folder.

Candidate: ISldWorks.ReplaceReferencedDocument(oldPath, newPath) — the
application-level, path-based reference redirection API (designed for
redirecting references to a different folder; works at the reference table,
not at component-name identity).

In-memory only, NO SAVE:
  P1  open the staged copy; fresh census of externals;
  P2  ReplaceReferencedDocument(F3R1 gripper -> V5-local gripper); fresh
      census must show the gripper occurrence bound to the V5-local path
      with its load state preserved (LIGHTWEIGHT);
  P3  ReplaceReferencedDocument(F3R1 base_link -> V5-local base_link); fresh
      census ditto; doc census records whether the pre-existing invisible
      F3R1 base_link wedge is absorbed/closed by the operation;
  P4  escape check: every top-level component path inside the V5-local tree;
      discard WITHOUT saving; close; session census.

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
        "schema": "V5_PROBE_LOOP1E_REPLACE_REFERENCED_DOCUMENT_V1",
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
        initial = fresh_rows(assembly, types, pythoncom_module)
        result["phases"]["P1_initial"] = initial
        local_root = m.LOCAL_ARM_ROOT.resolve().as_posix()
        externals = [row for row in initial if local_root not in Path(row["path"]).resolve().as_posix()]
        log(f"P1 externals={[(r['name2'], r['path'].split('/20_engineering/')[-1][:60]) for r in externals]}")

        redirects: List[Dict[str, Any]] = []
        for row in externals:
            current = Path(row["path"]).resolve()
            target = local_target_for(current)
            if target is None or not target.is_file():
                redirects.append({"name2": row["name2"], "error": "TARGET_UNRESOLVABLE", "current": str(current).replace("\\", "/")})
                continue
            entry: Dict[str, Any] = {"name2": row["name2"], "old": str(current).replace("\\", "/"), "new": str(target).replace("\\", "/")}
            try:
                returned = sw.ReplaceReferencedDocument(str(m.LOCAL_ARM), str(current), str(target))
                entry["returned"] = returned
            except Exception as exc:  # noqa: BLE001
                entry["exception"] = repr(exc)
            model.ForceRebuild3(True)
            rows = fresh_rows(assembly, types, pythoncom_module)
            entry["instance_after"] = [item for item in rows if item["name2"] == row["name2"]]
            entry["docs_after"] = doc_rows(sw)
            redirects.append(entry)
            log(f"redirect {row['name2']}: returned={entry.get('returned')} after={entry['instance_after']}")
        result["phases"]["P2_redirects"] = redirects

        final_rows = fresh_rows(assembly, types, pythoncom_module)
        escaped = [row for row in final_rows if local_root not in Path(row["path"]).resolve().as_posix()]
        result["phases"]["P3_final_rows"] = final_rows
        result["phases"]["P3_escaped"] = escaped
        result["phases"]["P3_docs"] = doc_rows(sw)

        cleanup = close_everything(sw)
        result["phases"]["P4_cleanup"] = cleanup
        log(f"P4 cleanup remaining={cleanup['remaining']}")

        checks = {
            "redirect_calls_ok": all(entry.get("returned") in (True, 1, -1) for entry in redirects) and bool(redirects),
            "all_components_v5_local": not escaped,
            "states_preserved_lightweight": all(row["suppression"] == 2 for row in final_rows),
        }
        result["checks"] = checks
        result["verdict"] = "V5_PROBE_LOOP1E_REPLACE_REFERENCED_DOCUMENT_PASS" if checks["all_components_v5_local"] and checks["redirect_calls_ok"] else "V5_PROBE_LOOP1E_REPLACE_REFERENCED_DOCUMENT_MIXED"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_REPLACE_REFERENCED_DOCUMENT_FAIL"
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
    return 0 if result.get("verdict") == "V5_PROBE_LOOP1E_REPLACE_REFERENCED_DOCUMENT_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
