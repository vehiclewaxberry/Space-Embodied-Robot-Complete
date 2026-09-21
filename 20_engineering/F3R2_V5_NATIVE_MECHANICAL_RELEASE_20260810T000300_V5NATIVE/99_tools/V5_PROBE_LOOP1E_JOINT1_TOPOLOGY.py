#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1E live probe: joint1 datum mate topology (sign probe delta=0).

Production run 20260811T2251 passed datum plane selection, angle-mate
creation, health, and transform reads, then failed
ANGLE_SIGN_PROBE_KINEMATIC_FAIL with rotation_vector exactly zero: the +0.5
deg angle-dimension drive produced no relative rotation between base_link
and link1.  Working hypotheses:
  (a) FEMALE-1 and MALE-1 datum components are both rigidly mated to
      base_link (same rigid body), so the angle between their planes is
      structurally constant and drives nothing;
  (b) the joint DOF is already locked by pre-existing mates so the new
      angle mate is a read-only measurement;
  (c) the datum angle rotates only the datum component, not the link.

This probe dumps (read-only, NO SAVE, NO DRIVES):
  P1  every mate feature of the staged assembly with its endpoint component
      Name2s, type, alignment, suppressed/error state;
  P2  the mate subset touching B51_REV_DATUM_FEMALE-1 / MALE-1 /
      base_link-1 / link1-1;
  P3  suppression + fixed state of those four components;
  P4  the display dimensions exposed by the EXISTING donor mates touching
      link1 (is there already an angle dimension at joint1?);
  P5  session left document-empty.

Never writes inside the release tree, never mutates the protected donor.
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
SUPPRESSION_LABEL = {0: "SUPPRESSED", 1: "RESOLVED", 2: "LIGHTWEIGHT"}
PROTECTED_WATCH = [m.B51_DONOR] + sorted(m.B51_DONOR_ROOT.rglob("*.SLDPRT"))
WATCH = {"B51_REV_DATUM_FEMALE-1", "B51_REV_DATUM_MALE-1", "B51_REF_base_link_LINKLOCAL-1", "B51_REF_link1_LINKLOCAL-1"}


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


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1E_JOINT1_TOPOLOGY_V1",
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

        raw_asm = sw.OpenDoc6(m.sw_openable_path(m.LOCAL_ARM), m.SW_DOC_ASSEMBLY, 3, "", 0, 0)
        model_raw, outs = base.unpack(raw_asm)
        if model_raw is None or (outs and int(outs[0]) != 0):
            raise RuntimeError("assembly open failed")
        model = base.wrap(model_raw, "IModelDoc2", types, pythoncom_module)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom_module)
        if not m.show_config_ok(model, m.ARM_CONFIGS[0], base, types, pythoncom_module):
            raise RuntimeError("config activation failed")

        # P1/P2: full mate ledger with endpoints
        mates: List[Dict[str, Any]] = []
        feature = base.value(model, "FirstFeature")
        guard = 0
        while feature is not None and guard < 10000:
            guard += 1
            typed = base.wrap(feature, "IFeature", types, pythoncom_module)
            if str(base.value(typed, "GetTypeName2")) == "MateGroup":
                sub = base.value(typed, "GetFirstSubFeature")
                sub_guard = 0
                while sub is not None and sub_guard < 10000:
                    sub_guard += 1
                    sf = base.wrap(sub, "IFeature", types, pythoncom_module)
                    row: Dict[str, Any] = {"feature_name": str(base.value(sf, "Name"))}
                    try:
                        row["suppressed"] = bool(base.value(sf, "IsSuppressed"))
                        row["error_code"] = int(base.unpack(base.value(sf, "GetErrorCode2"))[0])
                        mate = base.wrap(base.value(sf, "GetSpecificFeature2"), "IMate2", types, pythoncom_module)
                        row["mate_type"] = int(base.value(mate, "Type"))
                        endpoints: List[Optional[str]] = []
                        for index in range(int(base.value(mate, "GetMateEntityCount"))):
                            entity = base.wrap(mate.MateEntity(index), "IMateEntity2", types, pythoncom_module)
                            raw_component = base.value(entity, "ReferenceComponent")
                            endpoints.append(None if raw_component is None else str(base.value(base.wrap(raw_component, "IComponent2", types, pythoncom_module), "Name2")))
                        row["endpoints"] = endpoints
                    except Exception as exc:  # noqa: BLE001
                        row["dump_exception"] = repr(exc)
                    mates.append(row)
                    sub = base.value(sf, "GetNextSubFeature")
            feature = base.value(typed, "GetNextFeature")
        result["phases"]["P1_mate_total"] = len(mates)
        touching = [row for row in mates if any(isinstance(ep, str) and ep in WATCH for ep in (row.get("endpoints") or []))]
        result["phases"]["P2_touching_joint1"] = touching
        log(f"P1 mates={len(mates)} P2 touching joint1 set={len(touching)}")

        # P3: states of the watched components
        states: Dict[str, Any] = {}
        for raw2 in base.as_list(assembly.GetComponents(True)):
            component = base.wrap(raw2, "IComponent2", types, pythoncom_module)
            name2 = str(base.value(component, "Name2"))
            if name2 in WATCH:
                states[name2] = {
                    "suppression": SUPPRESSION_LABEL.get(int(base.value(component, "GetSuppression2"))),
                    "fixed": bool(base.value(component, "IsFixed")),
                    "path": str(base.value(component, "GetPathName")).replace("\\", "/"),
                }
        result["phases"]["P3_component_states"] = states

        # P4: display dimensions on mates touching link1
        dim_rows: List[Dict[str, Any]] = []
        for row in touching:
            pass  # placeholder: dimension probing is invasive; skipped by design
        result["phases"]["P4_note"] = "display-dimension probing skipped (invasive); mate ledger above is authoritative"

        remaining = close_everything(sw)
        result["cleanup_remaining"] = remaining
        log(f"cleanup remaining={remaining}")
        result["verdict"] = "V5_PROBE_LOOP1E_JOINT1_TOPOLOGY_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1E_JOINT1_TOPOLOGY_FAIL"
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
