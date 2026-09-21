#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: pre-open same-name target docs reference binding.

Established so far (logs in 99_tools/probe_logs/, 2026-08-11):
  * ReplaceComponents2 returns False on LIGHTWEIGHT components (probe 1);
  * resolve-first / suppress-first make it return True but the reference
    STAYS on the F3R1 lineage path — ReplaceComponents2 is name-bound and
    cannot re-point to a same-name file (probes 3/4/5, fresh enumeration);
  * ISldWorks.ReplaceReferencedDocument(referencing, old, new) returns False
    for these same-name LIGHTWEIGHT references (probe 6).

Candidate technique (classic SolidWorks name-binding rule): documents that
are ALREADY OPEN win reference resolution by file name.  Therefore:
  1) pre-open every V5-local part of a throwaway mirror tree (read-only),
  2) open the throwaway copy of the staged assembly read-write — every
     reference whose baked path points at the lineage trees must bind to the
     already-open same-name local parts,
  3) SAVE the throwaway assembly, close ALL documents, cold read-only reopen
     — proves the saved reference table now stores the local paths (this is
     what the production cold LOCAL_ARM_REFERENCE_ESCAPE audit reads).

The whole mirror lives in %TEMP% (never inside the release tree; the staged
V5 tree is NOT touched).  NOTE: the pre-existing invisible F3R1
B51_REF_base_link_LINKLOCAL.SLDPRT wedge (probes 1-3) is still open in this
session and wins the name race for base_link here — recorded as a session
artifact; the production session is guaranteed document-empty at
configure_local_arm entry, so no same-name competitor exists there.

Never writes inside the release tree, never mutates the protected donor.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
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
SW_DOC_ASSEMBLY = 2
SW_DOC_PART = 1
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


def open_doc(sw: Any, path: Path, doc_type: int, read_only: bool, types: Any, pythoncom_module: Any) -> Any:
    options = 1 | (2 if read_only else 0)
    raw = sw.OpenDoc6(str(path), doc_type, options, "", 0, 0)
    model_raw, outs = base.unpack(raw)
    errors = int(outs[0]) if outs else 0
    warnings = int(outs[1]) if len(outs) > 1 else 0
    if model_raw is None or errors != 0:
        raise RuntimeError(f"OpenDoc6 failed path={path} errors={errors} warnings={warnings}")
    return base.wrap(model_raw, "IModelDoc2", types, pythoncom_module)


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_PREOPEN_BINDING_V1",
        "timestamp_start_utc": datetime.now(timezone.utc).isoformat(),
        "phases": {},
    }
    sw = types = pythoncom_module = None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    mirror_root = Path(tempfile.gettempdir()) / f"V5_PROBE_LOOP1E_PREOPEN_{stamp}"
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

        # ---- P0: throwaway mirror of the staged tree in %TEMP% -------------
        if mirror_root.exists():
            raise RuntimeError(f"mirror collision: {mirror_root}")
        shutil.copytree(m.LOCAL_ARM_ROOT, mirror_root)
        mirror_asm = mirror_root / "assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"
        mirror_parts = sorted(mirror_root.rglob("*.SLDPRT"))
        result["phases"]["P0_mirror"] = {"root": str(mirror_root), "parts": len(mirror_parts)}
        log(f"P0 mirror: {len(mirror_parts)} parts -> {mirror_root}")

        # ---- P1: pre-open all mirror parts read-only -----------------------
        preopened: List[Dict[str, Any]] = []
        for part in mirror_parts:
            try:
                doc = open_doc(sw, part, SW_DOC_PART, True, types, pythoncom_module)
                preopened.append({"part": str(part).replace("\\", "/"), "opened": True, "title": str(base.value(doc, "GetTitle"))})
            except Exception as exc:  # noqa: BLE001
                preopened.append({"part": str(part).replace("\\", "/"), "opened": False, "exception": repr(exc)})
                log(f"pre-open failed for {part.name}: {exc!r}")
        result["phases"]["P1_preopened"] = preopened
        result["phases"]["P1_docs"] = doc_rows(sw)
        log(f"P1 pre-opened {sum(1 for p in preopened if p['opened'])}/{len(mirror_parts)} parts")

        # ---- P2: open mirror assembly read-write; census --------------------
        model = open_doc(sw, mirror_asm, SW_DOC_ASSEMBLY, False, types, pythoncom_module)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom_module)
        if not m.show_config_ok(model, m.ARM_CONFIGS[0], base, types, pythoncom_module):
            raise RuntimeError("config activation failed")
        warm_rows = fresh_rows(assembly, types, pythoncom_module)
        result["phases"]["P2_warm_rows"] = warm_rows
        mirror_prefix = str(mirror_root).replace("\\", "/")
        warm_nonlocal = [row for row in warm_rows if mirror_prefix not in row["path"]]
        log(f"P2 warm non-local={[(r['name2'], r['path'].split('/20_engineering/')[-1][:60]) for r in warm_nonlocal]}")

        # ---- P3: save mirror assembly; close all; cold reopen ---------------
        saved = model.Save3(1, 0, 0)
        ok, outs = base.unpack(saved)
        result["phases"]["P3_save"] = {"ok": bool(ok), "outs": [str(o) for o in outs] if outs else []}
        mid_cleanup = close_everything(sw)
        result["phases"]["P3_close_all"] = mid_cleanup
        if mid_cleanup["remaining"] != len([d for d in mid_cleanup["remaining_docs"] if "B51_REF_base_link_LINKLOCAL.SLDPRT" in d["title"]]):
            raise RuntimeError(f"unexpected cleanup state: {mid_cleanup}")
        cold = open_doc(sw, mirror_asm, SW_DOC_ASSEMBLY, True, types, pythoncom_module)
        cold_assembly = base.wrap(cold, "IAssemblyDoc", types, pythoncom_module)
        if not m.show_config_ok(cold, m.ARM_CONFIGS[0], base, types, pythoncom_module):
            raise RuntimeError("cold config activation failed")
        cold_rows = fresh_rows(cold_assembly, types, pythoncom_module)
        result["phases"]["P3_cold_rows"] = cold_rows
        cold_nonlocal = [row for row in cold_rows if mirror_prefix not in row["path"]]
        result["phases"]["P3_cold_nonlocal"] = cold_nonlocal
        log(f"P3 cold non-local={[(r['name2'], r['path'].split('/20_engineering/')[-1][:60]) for r in cold_nonlocal]}")

        cleanup = close_everything(sw)
        result["phases"]["P4_cleanup"] = cleanup
        log(f"P4 cleanup remaining={cleanup['remaining']}")

        base_link_artifact = [row for row in cold_nonlocal if "base_link" in row["name2"]]
        other_nonlocal = [row for row in cold_nonlocal if "base_link" not in row["name2"]]
        checks = {
            "warm_all_local_except_wedge_base_link": not [row for row in warm_nonlocal if "base_link" not in row["name2"]],
            "cold_all_local_except_wedge_base_link": not other_nonlocal,
            "base_link_only_wedge_artifact": all("F3R1_MECHANICAL" in row["path"] for row in base_link_artifact),
            "gripper_bound_local_cold": any("gripper_detail" in row["name2"] and mirror_prefix in row["path"] for row in cold_rows),
            "save_ok": bool(ok),
        }
        result["checks"] = checks
        result["verdict"] = "V5_PROBE_LOOP1E_PREOPEN_BINDING_PASS" if all(checks.values()) else "V5_PROBE_LOOP1E_PREOPEN_BINDING_MIXED"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_PREOPEN_BINDING_FAIL"
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
    return 0 if result.get("verdict") == "V5_PROBE_LOOP1E_PREOPEN_BINDING_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
