#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: per-component resolve semantics in the wedged session.

Probe 1 (discriminator) proved all 20 top-level components of the staged copy
are LIGHTWEIGHT and ReplaceComponents2 returns False on a LIGHTWEIGHT control.
Probe 2 (resolve-first) showed IAssemblyDoc.ResolveAllLightWeightComponents
(True) resolved 0/20 components in THIS session, where the failed control
replace left the F3R1 B51_REF_base_link_LINKLOCAL.SLDPRT open INVISIBLE and
unclosable (CloseDoc / CloseAllDocuments(True) / QuitDoc all no-op).

This probe extracts the remaining discriminating evidence from the wedged
session (in-memory only, NO SAVE):
  P1  per-component SetSuppression2(swComponentResolved=1) drive + rebuild +
      readback for EVERY top-level component of the staged copy — which
      components can be resolved at all while the F3R1 base_link doc is
      wedged (V5-local parts vs the wedge-bound base_link);
  P2  resolve-first ReplaceComponents2 for the GRIPPER detail (its F3R1 part
      is NOT open, so a resolve-first replace is not blocked by the wedge) —
      the exact component of the LOCAL_ARM_REPLACE_FAIL receipt;
  P3  resolve-first ReplaceComponents2 for base_link (expected to stay
      blocked by the wedged same-name open document — recorded as session
      artifact evidence, not as production-logic evidence);
  P4  discard WITHOUT saving; close/escalate; session census.

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


def components(assembly: Any, types: Any, pythoncom_module: Any) -> List[Any]:
    return [base.wrap(raw, "IComponent2", types, pythoncom_module) for raw in base.as_list(assembly.GetComponents(True))]


def row_of(component: Any) -> Dict[str, Any]:
    suppression = int(base.value(component, "GetSuppression2"))
    return {
        "name2": str(base.value(component, "Name2")),
        "path": str(base.value(component, "GetPathName")).replace("\\", "/"),
        "suppression": suppression,
        "suppression_label": SUPPRESSION_LABEL.get(suppression, str(suppression)),
    }


def local_target_for(current: Path) -> Optional[Path]:
    for source_root in (m.B51_DONOR_ROOT.resolve(), m.F3R1_B51_COPY_ROOT.resolve(), m.JULY_B51_DONOR_ROOT.resolve()):
        try:
            relative = current.relative_to(source_root)
            return (m.LOCAL_ARM_ROOT / relative).resolve()
        except ValueError:
            continue
    return None


def resolve_first_replace(model: Any, assembly: Any, component: Any, target: Path, sw: Any) -> Dict[str, Any]:
    pre = int(base.value(component, "GetSuppression2"))
    out: Dict[str, Any] = {"name2": str(base.value(component, "Name2")), "pre_suppression": pre, "target": str(target).replace("\\", "/")}
    if pre != SW_COMPONENT_RESOLVED:
        returned = int(component.SetSuppression2(SW_COMPONENT_RESOLVED))
        model.ForceRebuild3(True)
        readback = int(base.value(component, "GetSuppression2"))
        out["resolve_drive"] = {"returned": returned, "readback": readback, "readback_label": SUPPRESSION_LABEL.get(readback, str(readback))}
        if readback != SW_COMPONENT_RESOLVED:
            out["error"] = "RESOLVE_FIRST_FAILED"
            return out
    docs_pre = int(base.value(sw, "GetDocumentCount"))
    model.ClearSelection2(True)
    out["select"] = bool(component.Select4(False, None, False))
    out["replace"] = bool(assembly.ReplaceComponents2(str(target), "", True, 2, True)) if out["select"] else False
    model.ClearSelection2(True)
    out["doc_count"] = {"pre": docs_pre, "post": int(base.value(sw, "GetDocumentCount"))}
    out["post_row"] = row_of(component)
    return out


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_PER_COMPONENT_RESOLVE_V1",
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
        result["phases"]["P0_initial"] = sorted((row_of(c) for c in components(assembly, types, pythoncom_module)), key=lambda r: r["name2"])

        # ---- P1: per-component resolve drive census ------------------------
        resolve_rows: List[Dict[str, Any]] = []
        for component in components(assembly, types, pythoncom_module):
            name2 = str(base.value(component, "Name2"))
            pre = int(base.value(component, "GetSuppression2"))
            entry: Dict[str, Any] = {"name2": name2, "pre": pre, "pre_label": SUPPRESSION_LABEL.get(pre, str(pre))}
            if pre != SW_COMPONENT_RESOLVED:
                try:
                    returned = int(component.SetSuppression2(SW_COMPONENT_RESOLVED))
                    model.ForceRebuild3(True)
                    post = int(base.value(component, "GetSuppression2"))
                    entry.update({"returned": returned, "post": post, "post_label": SUPPRESSION_LABEL.get(post, str(post)), "resolved": post == SW_COMPONENT_RESOLVED})
                except Exception as exc:  # noqa: BLE001
                    entry.update({"exception": repr(exc), "resolved": False})
            else:
                entry["resolved"] = True
            resolve_rows.append(entry)
            log(f"resolve {name2}: {entry.get('pre_label')} -> {entry.get('post_label', 'RESOLVED')}")
        result["phases"]["P1_per_component_resolve"] = resolve_rows

        # ---- P2/P3: resolve-first replace for gripper then base_link -------
        replaces: Dict[str, Any] = {}
        for leaf in (m.ARM_LEGACY_GRIPPER_LEAF, "B51_REF_base_link_LINKLOCAL-1"):
            target_component = None
            for component in components(assembly, types, pythoncom_module):
                if str(base.value(component, "Name2")).split("/")[-1] == leaf:
                    target_component = component
                    break
            if target_component is None:
                replaces[leaf] = {"error": "COMPONENT_NOT_FOUND"}
                continue
            current = Path(str(base.value(target_component, "GetPathName"))).resolve()
            local = local_target_for(current)
            if local is None or not local.is_file():
                replaces[leaf] = {"error": "TARGET_UNRESOLVABLE", "current": str(current).replace("\\", "/")}
                continue
            outcome = resolve_first_replace(model, assembly, target_component, local, sw)
            outcome["current"] = str(current).replace("\\", "/")
            replaces[leaf] = outcome
            log(f"replace {leaf}: {outcome.get('replace')} (resolve_drive={outcome.get('resolve_drive')})")
        result["phases"]["P2P3_replaces"] = replaces
        result["phases"]["P3_docs_after"] = doc_rows(sw)

        # ---- P4: discard ----------------------------------------------------
        cleanup = close_everything(sw)
        result["phases"]["P4_cleanup"] = cleanup
        log(f"P4 cleanup remaining={cleanup['remaining']}")

        grip = replaces.get(m.ARM_LEGACY_GRIPPER_LEAF, {})
        base_link = replaces.get("B51_REF_base_link_LINKLOCAL-1", {})
        v5_local_resolved = [r for r in resolve_rows if r.get("resolved") and "V5_NATIVE_MECHANICAL_RELEASE" in (r.get("path") or "")]
        checks = {
            "v5_local_components_resolvable": any(r.get("resolved") for r in resolve_rows),
            "gripper_resolve_first_replace_succeeded": grip.get("replace") is True,
            "base_link_blocked_by_wedge_as_expected": base_link.get("replace") is not True,
            "session_document_empty_after_cleanup": cleanup["remaining"] == 0,
        }
        result["checks"] = checks
        result["verdict"] = "V5_PROBE_LOOP1E_PER_COMPONENT_RESOLVE_PASS" if checks["gripper_resolve_first_replace_succeeded"] else "V5_PROBE_LOOP1E_PER_COMPONENT_RESOLVE_MIXED"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_PER_COMPONENT_RESOLVE_FAIL"
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
    return 0 if result.get("verdict") == "V5_PROBE_LOOP1E_PER_COMPONENT_RESOLVE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
