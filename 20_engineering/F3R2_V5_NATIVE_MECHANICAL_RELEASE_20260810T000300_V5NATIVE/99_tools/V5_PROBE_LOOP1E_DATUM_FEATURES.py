#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: datum FEMALE-1 FirstFeature availability matrix.

Production runs on 2026-08-11:
  * 22:38 (hybrid prebind, datum docs READ-WRITE prebound, STOWED active,
    no 默认-activation gate): add_native_angle_driver joint1 SUCCEEDED —
    component_side_plane(FEMALE-1) found planes via component.FirstFeature
    traversal; the run later failed at the sign-probe kinematic gate;
  * 22:41 (+ activate 默认 before drivers): JOINT_SIDE_PLANE_MISSING
    FEMALE-1 planes=[];
  * 22:44 (+ dependent-reload of ALL non-gripper occurrences):
    JOINT_SIDE_PLANE_MISSING FEMALE-1 planes=[] again — the datum component
    is RESOLVED yet FirstFeature yields nothing.

This probe isolates the variable (in-memory only, NO SAVE):
  A  hybrid prebind, STOWED active, datum doc RW-prebound: traverse
     FEMALE-1 features (expect planes — replicate the 22:38 success);
  B  switch to 默认: traverse again (tests whether the config switch alone
     empties the traversal);
  C  dependent-reload the FEMALE doc (CloseDoc + SetSuppression2(1)):
     traverse resolved, per config (tests the reload mode);
  D  doc-level traversal: FEMALE part document's own IModelDoc2.FirstFeature
     chain in each state (reference: the features exist in the file);
  E  discard WITHOUT saving; close; session census.

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
SW_COMPONENT_FULLY_RESOLVED = 1
SUPPRESSION_LABEL = {0: "SUPPRESSED", 1: "RESOLVED", 2: "LIGHTWEIGHT"}
PROTECTED_WATCH = [m.B51_DONOR] + sorted(m.B51_DONOR_ROOT.rglob("*.SLDPRT"))
LONG_LEAVES = {"B51_REF_base_link_LINKLOCAL.SLDPRT", "B51_REF_gripper_detail_LINKLOCAL.SLDPRT"}
DATUM_DOC = "B51_REV_DATUM_FEMALE.SLDPRT"


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


def component_features(component: Any, types: Any, pythoncom_module: Any) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    raw = base.value(component, "FirstFeature")
    guard = 0
    while raw is not None and guard < 200:
        guard += 1
        feature = base.wrap(raw, "IFeature", types, pythoncom_module)
        rows.append({"name": str(base.value(feature, "Name")), "type": str(base.value(feature, "GetTypeName2"))})
        raw = base.value(feature, "GetNextFeature")
    return rows


def doc_features(doc: Any, types: Any, pythoncom_module: Any) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    raw = base.value(doc, "FirstFeature")
    guard = 0
    while raw is not None and guard < 200:
        guard += 1
        feature = base.wrap(raw, "IFeature", types, pythoncom_module)
        rows.append({"name": str(base.value(feature, "Name")), "type": str(base.value(feature, "GetTypeName2"))})
        raw = base.value(feature, "GetNextFeature")
    return rows


def find_leaf(assembly: Any, leaf: str, types: Any, pythoncom_module: Any) -> Optional[Any]:
    for raw in base.as_list(assembly.GetComponents(True)):
        component = base.wrap(raw, "IComponent2", types, pythoncom_module)
        if str(base.value(component, "Name2")).split("/")[-1] == leaf:
            return component
    return None


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_DATUM_FEATURES_V1",
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

        # hybrid prebind (production), assembly read-write
        for part in sorted(m.LOCAL_ARM_ROOT.rglob("*.SLDPRT")):
            open_form = m.sw_openable_path(part)
            options = 1 | (2 if open_form != str(part.resolve()) else 0)
            raw2 = sw.OpenDoc6(open_form, m.SW_DOC_PART, options, "", 0, 0)
            model_raw, outs = base.unpack(raw2)
            if model_raw is None or (outs and int(outs[0]) != 0):
                raise RuntimeError(f"prebind open failed {part.name}")
        raw_asm = sw.OpenDoc6(m.sw_openable_path(m.LOCAL_ARM), m.SW_DOC_ASSEMBLY, 1, "", 0, 0)
        model_raw, outs = base.unpack(raw_asm)
        if model_raw is None or (outs and int(outs[0]) != 0):
            raise RuntimeError("assembly open failed")
        model = base.wrap(model_raw, "IModelDoc2", types, pythoncom_module)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom_module)

        phases: Dict[str, Any] = {}

        # A: STOWED active, datum doc RW-prebound (replicate 22:38 state)
        if not m.show_config_ok(model, "STOWED_O13V3", base, types, pythoncom_module):
            raise RuntimeError("STOWED activation failed")
        female = find_leaf(assembly, "B51_REV_DATUM_FEMALE-1", types, pythoncom_module)
        phases["A_stowed_prebound"] = {
            "suppression": SUPPRESSION_LABEL.get(int(base.value(female, "GetSuppression2"))),
            "features": component_features(female, types, pythoncom_module),
        }
        log(f"A: {len(phases['A_stowed_prebound']['features'])} features, suppression={phases['A_stowed_prebound']['suppression']}")

        # B: switch to 默认 (tests the config switch alone)
        if not m.show_config_ok(model, "默认", base, types, pythoncom_module):
            raise RuntimeError("默认 activation failed")
        female = find_leaf(assembly, "B51_REV_DATUM_FEMALE-1", types, pythoncom_module)
        phases["B_default_prebound"] = {
            "suppression": SUPPRESSION_LABEL.get(int(base.value(female, "GetSuppression2"))),
            "features": component_features(female, types, pythoncom_module),
        }
        log(f"B: {len(phases['B_default_prebound']['features'])} features, suppression={phases['B_default_prebound']['suppression']}")

        # C: dependent-reload the FEMALE doc, traverse resolved per config
        sw.CloseDoc(DATUM_DOC)
        female = find_leaf(assembly, "B51_REV_DATUM_FEMALE-1", types, pythoncom_module)
        returned = int(female.SetSuppression2(SW_COMPONENT_FULLY_RESOLVED))
        rebuilt = bool(model.ForceRebuild3(True))
        readback = int(base.value(female, "GetSuppression2"))
        phases["C_reload_drive"] = {"returned": returned, "rebuilt": rebuilt, "readback": SUPPRESSION_LABEL.get(readback, readback)}
        for cfg in m.ARM_CONFIGS:
            if not m.show_config_ok(model, cfg, base, types, pythoncom_module):
                raise RuntimeError(f"C config {cfg} failed")
            female = find_leaf(assembly, "B51_REV_DATUM_FEMALE-1", types, pythoncom_module)
            phases[f"C_resolved_{cfg}"] = {
                "suppression": SUPPRESSION_LABEL.get(int(base.value(female, "GetSuppression2"))),
                "features": component_features(female, types, pythoncom_module),
            }
            log(f"C/{cfg}: {len(phases[f'C_resolved_{cfg}']['features'])} features, suppression={phases[f'C_resolved_{cfg}']['suppression']}")

        # D: doc-level traversal on the FEMALE part document
        datum_doc = None
        for raw2 in base.as_list(base.value(sw, "GetDocuments")):
            try:
                if str(base.value(raw2, "GetTitle")) == DATUM_DOC:
                    datum_doc = base.wrap(raw2, "IModelDoc2", types, pythoncom_module)
            except Exception:  # noqa: BLE001
                pass
        phases["D_doc_open"] = datum_doc is not None
        if datum_doc is not None:
            phases["D_doc_features"] = doc_features(datum_doc, types, pythoncom_module)
            log(f"D: {len(phases['D_doc_features'])} doc-level features")

        result["phases"] = phases
        remaining = close_everything(sw)
        result["cleanup_remaining"] = remaining
        log(f"cleanup remaining={remaining}")

        planes_a = [f for f in phases["A_stowed_prebound"]["features"] if f["type"] == "RefPlane"]
        planes_b = [f for f in phases["B_default_prebound"]["features"] if f["type"] == "RefPlane"]
        planes_c = {cfg: [f for f in phases[f"C_resolved_{cfg}"]["features"] if f["type"] == "RefPlane"] for cfg in m.ARM_CONFIGS}
        result["plane_counts"] = {"A_stowed": len(planes_a), "B_default": len(planes_b), "C_resolved": {cfg: len(rows) for cfg, rows in planes_c.items()}, "D_doc": len([f for f in phases.get("D_doc_features", []) if f["type"] == "RefPlane"])}
        result["verdict"] = "V5_PROBE_LOOP1E_DATUM_FEATURES_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_DATUM_FEATURES_FAIL"
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
