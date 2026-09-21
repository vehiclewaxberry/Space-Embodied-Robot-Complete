#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only diagnostic probe: enumerate the frozen B51 gripper source SLDPRT
57 physical solid bodies in their link-6-local frame and emit local B-rep
facts (name, faces, volume, bbox, mass centroid).  No SolidWorks writes."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
SOURCE_PART = ROOT / (
    "20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807/03_native_cad/"
    "B601_ARM_B51_COPY/inputs/vendor_link_parts/B51_REF_gripper_detail_LINKLOCAL.SLDPRT"
)
sys.path.insert(0, str(RUN_ROOT / "99_tools"))
import F3R2_V5_SESSION_BINDING as sbin
import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base


SW_DOC_PART = 1
SW_OPEN_SILENT_READONLY = 3


def row(body: Any, index: int) -> Dict[str, Any]:
    name = str(base.value(body, "Name"))
    faces = int(base.value(body, "GetFaceCount"))
    mass = [float(value) for value in base.as_list(body.GetMassProperties(1.0))]
    volume_mm3 = mass[3] * 1.0e9 if len(mass) > 3 else None
    centroid_mm = [mass[i] * 1000.0 for i in range(3)] if len(mass) > 3 else None
    raw_box = [float(value) * 1000.0 for value in base.as_list(base.value(body, "GetBodyBox"))]
    return {
        "enum_index": index,
        "name": name,
        "faces": faces,
        "volume_mm3": round(volume_mm3, 6) if volume_mm3 is not None else None,
        "bbox_mm": [round(v, 6) for v in raw_box],
        "mass_centroid_mm": [round(v, 6) for v in centroid_mm] if centroid_mm is not None else None,
    }


def main() -> int:
    sw = types = pythoncom = None
    model = None
    try:
        sw, types, pythoncom, session = base.attach_empty_session()
        pid = int(session["pid"])
        if pid != int(sbin.resolve_pid(42276)):
            raise SystemExit(f"PID_MISMATCH actual={pid}")
        raw = sw.OpenDoc6(str(SOURCE_PART), SW_DOC_PART, SW_OPEN_SILENT_READONLY, "", 0, 0)
        model_raw, outs = base.unpack(raw)
        errors, warnings = int(outs[0]), int(outs[1])
        if model_raw is None or errors != 0 or warnings != 0:
            raise SystemExit(f"OPEN_FAIL errors={errors} warnings={warnings}")
        model = base.wrap(model_raw, "IModelDoc2", types, pythoncom)
        part = base.wrap(model, "IPartDoc", types, pythoncom)
        bodies = [base.wrap(b, "IBody2", types, pythoncom) for b in base.as_list(part.GetBodies2(0, False))]
        rows = [row(body, index) for index, body in enumerate(bodies)]
        total_volume = sum(float(r["volume_mm3"]) for r in rows)
        total_faces = sum(int(r["faces"]) for r in rows)
        print(json.dumps({
            "schema": "F3R2_V5_DIAG_SOURCE_BODY_PROBE_V1",
            "pid": pid,
            "source": str(SOURCE_PART),
            "body_count": len(rows),
            "total_volume_mm3": round(total_volume, 6),
            "total_faces": total_faces,
            "bodies": rows,
        }, ensure_ascii=False, indent=2))
        return 0
    finally:
        if model is not None:
            try:
                sw.CloseDoc(str(base.value(model, "GetTitle")))
            except Exception:
                pass
        if sw is not None and int(base.value(sw, "GetDocumentCount")) != 0:
            raise SystemExit("LEAKED_DOCUMENT")


if __name__ == "__main__":
    sys.exit(main())
