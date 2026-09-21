#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1C1 live probe v10: donor-inheritance check for the interface overlaps.

The V5 native gripper assembly shows positive-volume palm<->finger interferences
at the authority-correct poses (probe v9: rail interface ~435.9 mm3 at OPEN,
jaw contact shell ~79.5 mm3 at CLOSED, palm-body rows of 12.055 mm3 at CLOSED).
The three native parts were body-copied from the single 57-body donor part
B51_REF_gripper_detail_LINKLOCAL.SLDPRT (Loop1C0 receipt) whose internal body
arrangement is the donor static pose.  If the SAME overlaps already exist
inside the donor part, they are inherited donor geometry, not a V5 assembly
defect.

Method: insert the donor part alone into a fresh assembly (read-only source),
run interference detection with IncludeMultibodyPartInterferences=True, and
report every positive-volume body-body interference with its bbox (mm), for
direct comparison against the probe-v9 per-state bboxes.

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

DONOR = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807\03_native_cad\B601_ARM_B51_COPY\inputs\vendor_link_parts\B51_REF_gripper_detail_LINKLOCAL.SLDPRT")
T0 = time.time()


def log(step: str) -> None:
    print(f"[{time.time() - T0:8.2f}s] {step}", flush=True)


def main() -> int:
    result: Dict[str, Any] = {"schema": "V5_PROBE_LOOP1C1_DONOR_INHERITANCE_V10", "rows": [], "notes": []}
    sw = types = pythoncom = None
    try:
        log("attach: begin")
        sw, types, pythoncom, session = base.attach_empty_session()
        result["session"] = session
        raw_model = sw.NewDocument(str(m.ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
        model = base.wrap(raw_model, "IModelDoc2", types, pythoncom)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
        raw_part, errors, warnings = m.unpack_document(sw.OpenDoc6(str(DONOR), 1, 3, "", 0, 0), "DONOR_OPEN")
        if raw_part is None or errors != 0:
            raise m.GateError("DONOR_OPEN_FAIL", "donor part did not open read-only", {"errors": errors, "warnings": warnings})
        part_title = str(base.value(base.wrap(raw_part, "IModelDoc2", types, pythoncom), "GetTitle"))
        log(f"donor open: {part_title}")
        assembly_title = str(base.value(model, "GetTitle"))
        m.activate(sw, assembly_title)
        raw_component = assembly.AddComponent5(str(DONOR), 0, "", False, "", 0.0, 0.0, 0.0)
        if raw_component is None:
            raise m.GateError("DONOR_ADD_FAIL", "AddComponent5 returned null")
        component = base.wrap(raw_component, "IComponent2", types, pythoncom)
        sw.CloseDoc(part_title)
        model.EditRebuild3()
        bodies = [base.wrap(item, "IBody2", types, pythoncom) for item in base.as_list(component.GetBodies2(0))]
        result["donor_body_count"] = len(bodies)
        log(f"donor inserted: {len(bodies)} bodies")

        manager = base.wrap(base.value(assembly, "InterferenceDetectionManager"), "IInterferenceDetectionMgr", types, pythoncom)
        try:
            manager.TreatCoincidenceAsInterference = False
            manager.TreatSubAssembliesAsComponents = False
            manager.IncludeMultibodyPartInterferences = True
            manager.IgnoreHiddenBodies = False
            manager.ShowIgnoredInterferences = True
            interferences = base.as_list(manager.GetInterferences())
            for raw in interferences:
                interference = base.wrap(raw, "IInterference", types, pythoncom)
                volume_mm3 = float(base.value(interference, "Volume")) * 1.0e9
                if volume_mm3 <= 0.0:
                    continue
                row: Dict[str, Any] = {"volume_mm3": round(volume_mm3, 6)}
                try:
                    body_raw = interference.GetInterferenceBody()
                    if body_raw is not None:
                        body = base.wrap(body_raw, "IBody2", types, pythoncom)
                        box = [float(v) for v in base.as_list(base.value(body, "GetBodyBox"))]
                        if len(box) == 6:
                            row["bbox_mm"] = [round(v * 1000.0, 4) for v in box]
                except Exception as exc:  # noqa: BLE001
                    row["body_error"] = repr(exc)
                result["rows"].append(row)
        finally:
            manager.Done()
        result["rows"].sort(key=lambda row: -row["volume_mm3"])
        result["positive_volume_count"] = len(result["rows"])
        log(f"donor internal positive-volume interferences: {len(result['rows'])}")
        result["verdict"] = "V5_PROBE_LOOP1C1_DONOR_INHERITANCE_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1C1_DONOR_INHERITANCE_FAIL"
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
