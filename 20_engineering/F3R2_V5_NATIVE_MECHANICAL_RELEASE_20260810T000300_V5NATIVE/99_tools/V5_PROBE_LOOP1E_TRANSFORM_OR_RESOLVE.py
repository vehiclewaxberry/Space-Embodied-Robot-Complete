#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: decisive transform-read vs resolve experiments.

Established 2026-08-11 (probe logs):
  * read-only prebind blocks lightweight->resolved resolution (RESOLVE_LINK6
    probe: 0/20 resolved), while read-write dependent loads allow 20/20
    (PER_COMPONENT_RESOLVE on the earlier session);
  * suppress drive works directly from LIGHTWEIGHT (probe 5: pre=2 ->
    readback 0), so the legacy gripper never needs resolution;
  * ARM_COMPONENT_TRANSFORM_FAIL proved IComponent2.Transform2 returns no
    data on LIGHTWEIGHT components; the driver sign probe needs transforms
    of base_link + link1..link6;
  * the two >260-char vendor files (base_link 261, gripper 266) can only be
    pre-opened READ-ONLY via their 8.3 aliases (read-write 8.3 open fails
    errors=2097152; long-path direct open fails errors=2), while the eight
    shorter files (link1..link6, datums) are read-write-openable.

In-memory only, NO SAVE, on the staged tree:
  S0  hybrid prebind (8 short parts RW; 2 long parts RO/8.3) + asm RW; census
      -> every occurrence must bind V5-local;
  S1  IComponent2.GetTotalTransform on LIGHTWEIGHT base_link and link6 — 16
      finite values?  (would allow dropping the whole resolve sandwich);
  S2  resolve drive (per-iteration rebuild) for every occurrence EXCEPT the
      gripper — do the RW-prebound parts resolve? does RO base_link?;
  S3  if base_link stays lightweight: dependent-reload attempt — close its
      RO doc, then SetSuppression2(1)+rebuild+readback, and re-check the
      component path (must stay V5-local);
  S4  gripper suppress-from-lightweight then restore-lightweight (proven
      pattern) — confirm both directions one more time in this exact
      configuration;
  S5  discard WITHOUT saving; close; session census.

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
SW_COMPONENT_SUPPRESSED = 0
SW_COMPONENT_FULLY_RESOLVED = 1
SW_COMPONENT_LIGHTWEIGHT = 2
SUPPRESSION_LABEL = {0: "SUPPRESSED", 1: "RESOLVED", 2: "LIGHTWEIGHT"}
PROTECTED_WATCH = [m.B51_DONOR] + sorted(m.B51_DONOR_ROOT.rglob("*.SLDPRT"))
LONG_LEAVES = {"B51_REF_base_link_LINKLOCAL.SLDPRT", "B51_REF_gripper_detail_LINKLOCAL.SLDPRT"}


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


def open_part(sw: Any, path_str: str, read_only: bool, types: Any, pythoncom_module: Any) -> None:
    options = 1 | (2 if read_only else 0)
    raw = sw.OpenDoc6(path_str, m.SW_DOC_PART, options, "", 0, 0)
    model_raw, outs = base.unpack(raw)
    errors = int(outs[0]) if outs else 0
    if model_raw is None or errors != 0:
        raise RuntimeError(f"part open failed ro={read_only} {path_str[-50:]} errors={errors}")


def components(assembly: Any, types: Any, pythoncom_module: Any) -> List[Any]:
    return [base.wrap(raw, "IComponent2", types, pythoncom_module) for raw in base.as_list(assembly.GetComponents(True))]


def find_leaf(assembly: Any, leaf: str, types: Any, pythoncom_module: Any) -> Optional[Any]:
    for component in components(assembly, types, pythoncom_module):
        if str(base.value(component, "Name2")).split("/")[-1] == leaf:
            return component
    return None


def total_transform(component: Any) -> Dict[str, Any]:
    try:
        raw = base.value(component, "GetTotalTransform", False)
        if raw is None:
            return {"count": 0, "finite": False}
        values = [float(value) for value in base.as_list(base.value(raw, "ArrayData"))]
        import math
        return {"count": len(values), "finite": len(values) == 16 and all(math.isfinite(v) for v in values)}
    except Exception as exc:  # noqa: BLE001
        return {"exception": repr(exc)}


def transform2(component: Any) -> Dict[str, Any]:
    try:
        values = [float(value) for value in base.as_list(base.value(base.value(component, "Transform2"), "ArrayData"))]
        import math
        return {"count": len(values), "finite": len(values) == 16 and all(math.isfinite(v) for v in values)}
    except Exception as exc:  # noqa: BLE001
        return {"exception": repr(exc)}


def drive(model: Any, component: Any, state: int) -> Dict[str, Any]:
    returned = int(component.SetSuppression2(state))
    rebuilt = bool(model.ForceRebuild3(True))
    readback = int(base.value(component, "GetSuppression2"))
    return {"wanted": state, "returned": returned, "rebuilt": rebuilt, "readback": readback, "readback_label": SUPPRESSION_LABEL.get(readback, str(readback)), "ok": readback == state}


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_TRANSFORM_OR_RESOLVE_V1",
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

        # S0: hybrid prebind + assembly
        for part in sorted(m.LOCAL_ARM_ROOT.rglob("*.SLDPRT")):
            open_part(sw, m.sw_openable_path(part), part.name in LONG_LEAVES, types, pythoncom_module)
        raw_asm = sw.OpenDoc6(m.sw_openable_path(m.LOCAL_ARM), m.SW_DOC_ASSEMBLY, 1, "", 0, 0)
        model_raw, outs = base.unpack(raw_asm)
        errors = int(outs[0]) if outs else 0
        if model_raw is None or errors != 0:
            raise RuntimeError(f"assembly open failed errors={errors}")
        model = base.wrap(model_raw, "IModelDoc2", types, pythoncom_module)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom_module)
        local_root = m.LOCAL_ARM_ROOT.resolve().as_posix()
        census: Dict[str, Any] = {}
        for cfg in m.ARM_CONFIGS:
            if not m.show_config_ok(model, cfg, base, types, pythoncom_module):
                raise RuntimeError(f"census config failed {cfg}")
            rows = []
            for component in components(assembly, types, pythoncom_module):
                path = Path(str(base.value(component, "GetPathName"))).resolve().as_posix()
                rows.append({"name2": str(base.value(component, "Name2")), "local": local_root in path, "path": path})
            census[cfg] = rows
        escaped = [row for rows in census.values() for row in rows if not row["local"]]
        result["phases"]["S0_census"] = {"escaped": escaped, "count": sum(len(r) for r in census.values())}
        log(f"S0 census escaped={len(escaped)}")

        # S1: lightweight transform reads
        s1: Dict[str, Any] = {}
        for leaf in ("B51_REF_base_link_LINKLOCAL-1", "B51_REF_link6_LINKLOCAL-1"):
            component = find_leaf(assembly, leaf, types, pythoncom_module)
            if component is not None:
                s1[leaf] = {
                    "suppression": SUPPRESSION_LABEL.get(int(base.value(component, "GetSuppression2"))),
                    "GetTotalTransform": total_transform(component),
                    "Transform2": transform2(component),
                }
        result["phases"]["S1_lightweight_transforms"] = s1
        log(f"S1 transforms: {s1}")

        # S2: resolve all except gripper
        s2: List[Dict[str, Any]] = []
        for component in components(assembly, types, pythoncom_module):
            name2 = str(base.value(component, "Name2"))
            leaf = name2.split("/")[-1]
            if leaf == m.ARM_LEGACY_GRIPPER_LEAF:
                continue
            pre = int(base.value(component, "GetSuppression2"))
            if pre != SW_COMPONENT_FULLY_RESOLVED:
                outcome = drive(model, component, SW_COMPONENT_FULLY_RESOLVED)
                s2.append({"name2": name2, "pre": SUPPRESSION_LABEL.get(pre), **outcome})
                log(f"resolve {name2}: {SUPPRESSION_LABEL.get(pre)} -> {outcome['readback_label']}")
            else:
                s2.append({"name2": name2, "pre": "RESOLVED", "ok": True})
        result["phases"]["S2_resolve"] = s2
        unresolved = [row for row in s2 if not row.get("ok")]

        # S3: dependent-reload for base_link if still unresolved
        s3: Dict[str, Any] = {}
        base_link = find_leaf(assembly, "B51_REF_base_link_LINKLOCAL-1", types, pythoncom_module)
        if base_link is not None and int(base.value(base_link, "GetSuppression2")) != SW_COMPONENT_FULLY_RESOLVED:
            target_title = None
            for raw2 in base.as_list(base.value(sw, "GetDocuments")):
                try:
                    if str(base.value(raw2, "GetTitle")) == "B51_REF_base_link_LINKLOCAL.SLDPRT":
                        target_title = str(base.value(raw2, "GetTitle"))
                except Exception:  # noqa: BLE001
                    pass
            s3["ro_doc_found"] = target_title is not None
            if target_title:
                sw.CloseDoc(target_title)
                s3["ro_doc_closed_count"] = int(base.value(sw, "GetDocumentCount"))
            component = find_leaf(assembly, "B51_REF_base_link_LINKLOCAL-1", types, pythoncom_module)
            outcome = drive(model, component, SW_COMPONENT_FULLY_RESOLVED)
            s3["reload_resolve"] = outcome
            s3["path_after"] = str(base.value(component, "GetPathName")).replace("\\", "/")
            s3["transform2_after"] = transform2(component)
            log(f"S3 dependent-reload: {outcome['readback_label']} path_v5local={'_native_donor_local' in s3['path_after']}")
        result["phases"]["S3_dependent_reload"] = s3

        # S4: gripper suppress/restore from lightweight
        s4: Dict[str, Any] = {}
        gripper = find_leaf(assembly, m.ARM_LEGACY_GRIPPER_LEAF, types, pythoncom_module)
        if gripper is not None:
            s4["pre"] = SUPPRESSION_LABEL.get(int(base.value(gripper, "GetSuppression2")))
            s4["suppress"] = drive(model, gripper, SW_COMPONENT_SUPPRESSED)
            s4["restore"] = drive(model, gripper, SW_COMPONENT_LIGHTWEIGHT)
        result["phases"]["S4_gripper"] = s4
        log(f"S4 gripper: {s4.get('pre')} -> suppress ok={s4.get('suppress', {}).get('ok')} -> restore ok={s4.get('restore', {}).get('ok')}")

        remaining = close_everything(sw)
        result["phases"]["S5_cleanup_remaining"] = remaining
        log(f"S5 cleanup remaining={remaining}")

        checks = {
            "census_all_local": not escaped,
            "lightweight_gettotaltransform_works": all(s1.get(leaf, {}).get("GetTotalTransform", {}).get("finite") for leaf in s1),
            "rw_prebound_resolve_works": bool(s2) and not [row for row in s2 if "B51_REF_link" in row["name2"] and not row.get("ok")],
            "base_link_resolved_somehow": bool(s2) and (all(row.get("ok") for row in s2 if "base_link" in row["name2"]) or s3.get("reload_resolve", {}).get("ok") is True),
            "dependent_reload_kept_v5_local": (not s3) or "_native_donor_local" in s3.get("path_after", ""),
            "gripper_suppress_restore_ok": s4.get("suppress", {}).get("ok") is True and s4.get("restore", {}).get("ok") is True,
            "session_document_empty_after_cleanup": remaining == 0,
        }
        result["checks"] = checks
        result["verdict"] = "V5_PROBE_LOOP1E_TRANSFORM_OR_RESOLVE_PASS" if checks["census_all_local"] and checks["session_document_empty_after_cleanup"] else "V5_PROBE_LOOP1E_TRANSFORM_OR_RESOLVE_MIXED"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_TRANSFORM_OR_RESOLVE_FAIL"
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
    return 0 if result.get("verdict") == "V5_PROBE_LOOP1E_TRANSFORM_OR_RESOLVE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
