#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 micro-probe: find a working accessor for mate-entity face references.

Context: IMateEntity2.Reference (dispid 4) raises DISP_E_MEMBERNOTFOUND via the
makepy static binding on this installation (run-6 receipt).  The Loop1C1 mate
ledger needs the endpoint face objects for persist-reference evidence.

Builds a MINIMAL state (PALM + RIGHT finger, one coincident guide mate) and on
that mate's first entity tries:
  A1  makepy property  entity.Reference                      (expect failure)
  A2  dynamic dispatch  dynamic.Dispatch(raw) -> .Reference  (name-based dispid)
  A3  entity.IGetEntityParams / EntityParams peek            (may embed ref info)
  A4  IMateEntity(v1) GetEntityType / GetEntityParams peek
and for any object obtained, runs the production persist_record() to prove the
persist-reference pipeline end to end.

Never saves, never writes receipts, leaves the session document-empty.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base  # noqa: E402
import F3R2_V5_NATIVE_LOOP1C1_GRIPPER_ASSEMBLY_ATTACH_ONLY as m  # noqa: E402

OPEN_TRAVEL_MM = float(m.STATES["OPEN"]["travel_mm"])
T0 = time.time()


def log(step: str) -> None:
    print(f"[{time.time() - T0:8.2f}s] {step}", flush=True)


def main() -> int:
    result: Dict[str, Any] = {"schema": "V5_PROBE_MATE_ENTITY_REF_V1", "accessors": {}, "notes": []}
    sw = types = pythoncom = None
    try:
        log("attach: begin")
        sw, types, pythoncom, session = base.attach_empty_session()
        result["session"] = session
        raw_model = sw.NewDocument(str(m.ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
        model = base.wrap(raw_model, "IModelDoc2", types, pythoncom)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
        components: Dict[str, Any] = {}
        for role in ("PALM", "RIGHT"):
            spec = m.PARTS[role]
            translation = m.expected_translation_m(role, OPEN_TRAVEL_MM)
            components[role] = m.insert_component(sw, model, assembly, role, Path(spec["path"]), bool(spec["fixed"]), translation, types, pythoncom)
            log(f"insert {role}: ok")
        palm_face, _pf = m.guide_face(model, components["PALM"], "PALM", "A", types, pythoncom)
        finger_face, _ff = m.guide_face(model, components["RIGHT"], "RIGHT", "A", types, pythoncom)
        m.add_face_mate(model, assembly, palm_face, finger_face, 1, "PROBE_MATE_A", types, pythoncom)
        log("coincident mate: ok")
        feature = None
        for candidate in m.mate_features(model, types, pythoncom):
            if str(base.value(candidate, "Name")) == "PROBE_MATE_A":
                feature = candidate
        if feature is None:
            raise m.GateError("PROBE_MATE_MISSING", "probe mate feature not found")
        mate = m.distance_mate_object(feature, types, pythoncom)
        raw_entity = mate.MateEntity(0)
        entity = base.wrap(raw_entity, "IMateEntity2", types, pythoncom)
        extension = model.Extension

        # A1: makepy static property (expected to fail, documents the defect)
        try:
            value = base.value(entity, "Reference")
            result["accessors"]["A1_makepy_Reference"] = {"ok": value is not None}
            if value is not None:
                result["accessors"]["A1_makepy_Reference"]["persist"] = m.persist_record(extension, value)
        except Exception as exc:  # noqa: BLE001
            result["accessors"]["A1_makepy_Reference"] = {"ok": False, "error": repr(exc)}
        log("A1 done")

        # A2: dynamic dispatch by name
        try:
            import win32com.client.dynamic

            raw_ptr = getattr(raw_entity, "_oleobj_", None) or getattr(entity, "_oleobj_")
            dyn = win32com.client.dynamic.Dispatch(raw_ptr)
            value = getattr(dyn, "Reference", None)
            row: Dict[str, Any] = {"ok": value is not None}
            if value is not None:
                row["persist"] = m.persist_record(extension, value)
            result["accessors"]["A2_dynamic_Reference"] = row
        except Exception as exc:  # noqa: BLE001
            result["accessors"]["A2_dynamic_Reference"] = {"ok": False, "error": repr(exc)}
        log("A2 done")

        # A3: entity params peek
        for label, call in (
            ("A3_IGetEntityParams", lambda: entity.IGetEntityParams(int(entity.GetEntityParamsSize()))),
            ("A3_EntityParams", lambda: base.value(entity, "EntityParams")),
        ):
            try:
                value = call()
                result["accessors"][label] = {"ok": True, "repr": repr(value)[:400]}
            except Exception as exc:  # noqa: BLE001
                result["accessors"][label] = {"ok": False, "error": repr(exc)}
            log(f"{label} done")

        # A4: v1 interface members
        try:
            v1 = base.wrap(raw_entity, "IMateEntity", types, pythoncom)
            result["accessors"]["A4_v1_GetEntityType"] = {"ok": True, "value": int(v1.GetEntityType())}
        except Exception as exc:  # noqa: BLE001
            result["accessors"]["A4_v1_GetEntityType"] = {"ok": False, "error": repr(exc)}
        result["verdict"] = "V5_PROBE_MATE_ENTITY_REF_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_MATE_ENTITY_REF_FAIL"
        log("exception; see payload")
    finally:
        if sw is not None:
            try:
                result["cleanup"] = m.close_all_owned(sw)
                log("cleanup: session document-empty")
            except Exception as cleanup_exc:  # noqa: BLE001
                result["cleanup_exception"] = repr(cleanup_exc)
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:  # noqa: BLE001
                pass
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0 if result.get("verdict", "").endswith("_PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
