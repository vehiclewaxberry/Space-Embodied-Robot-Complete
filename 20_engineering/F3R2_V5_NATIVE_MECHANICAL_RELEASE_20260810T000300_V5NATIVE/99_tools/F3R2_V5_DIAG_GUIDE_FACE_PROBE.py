#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only probe of planar guide-face candidates on the three native
gripper parts (PALM body 012, LEFT body 009, RIGHT body 004) in link-6-local
frame: normal, plane offset, area, owner body name."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
RUN_ROOT = ROOT / "20_engineering/F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE"
PARTS = {
    "PALM": (RUN_ROOT / "01_native_parts/gripper/B601_GRIPPER_PALM.SLDPRT", "B51_REF_gripper_detail_LINKLOCAL012"),
    "LEFT": (RUN_ROOT / "01_native_parts/gripper/B601_GRIPPER_LEFT_FINGER.SLDPRT", "B51_REF_gripper_detail_LINKLOCAL009"),
    "RIGHT": (RUN_ROOT / "01_native_parts/gripper/B601_GRIPPER_RIGHT_FINGER.SLDPRT", "B51_REF_gripper_detail_LINKLOCAL004"),
}
EXTRA = {
    "PALM_MAIN_054": (RUN_ROOT / "01_native_parts/gripper/B601_GRIPPER_PALM.SLDPRT", "B51_REF_gripper_detail_LINKLOCAL054"),
    "LEFT_INNER_049": (RUN_ROOT / "01_native_parts/gripper/B601_GRIPPER_LEFT_FINGER.SLDPRT", "B51_REF_gripper_detail_LINKLOCAL049"),
    "RIGHT_INNER_053": (RUN_ROOT / "01_native_parts/gripper/B601_GRIPPER_RIGHT_FINGER.SLDPRT", "B51_REF_gripper_detail_LINKLOCAL053"),
}
sys.path.insert(0, str(RUN_ROOT / "99_tools"))
import F3R2_V5_SESSION_BINDING as sbin
import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base


def norm(v: List[float]) -> float:
    return math.sqrt(sum(float(x) ** 2 for x in v))


def main() -> int:
    sw = types = pythoncom = None
    try:
        sw, types, pythoncom, session = base.attach_empty_session()
        if int(session["pid"]) != int(sbin.resolve_pid(42276)):
            raise SystemExit("PID_MISMATCH")
        out: Dict[str, Any] = {}
        for role, (path, suffix) in {**PARTS, **EXTRA}.items():
            raw = sw.OpenDoc6(str(path), 1, 3, "", 0, 0)
            model_raw, outs = base.unpack(raw)
            errors, warnings = int(outs[0]), int(outs[1])
            if model_raw is None or errors != 0 or warnings != 0:
                raise SystemExit(f"OPEN_FAIL {role} e={errors} w={warnings}")
            model = base.wrap(model_raw, "IModelDoc2", types, pythoncom)
            part = base.wrap(model, "IPartDoc", types, pythoncom)
            rows: List[Dict[str, Any]] = []
            for raw_body in base.as_list(part.GetBodies2(0, False)):
                body = base.wrap(raw_body, "IBody2", types, pythoncom)
                name = str(base.value(body, "Name"))
                if not name.endswith(suffix):
                    continue
                for raw_face in base.as_list(base.value(body, "GetFaces")):
                    face = base.wrap(raw_face, "IFace2", types, pythoncom)
                    surface = base.wrap(base.value(face, "GetSurface"), "ISurface", types, pythoncom)
                    if not bool(base.value(surface, "IsPlane")):
                        continue
                    params = [float(v) for v in base.as_list(base.value(surface, "PlaneParams"))]
                    if len(params) < 6:
                        continue
                    n = params[:3]
                    length = norm(n)
                    normal = [v / length for v in n]
                    rows.append({
                        "body": name,
                        "normal": [round(v, 6) for v in normal],
                        "point_mm": [round(v * 1000.0, 6) for v in params[3:6]],
                        "offset_mm": round(sum(normal[i] * params[3 + i] for i in range(3)) * 1000.0, 6),
                        "area_mm2": round(float(base.value(face, "GetArea")) * 1.0e6, 6),
                    })
            sw.CloseDoc(str(base.value(model, "GetTitle")))
            out[role] = rows
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    finally:
        if sw is not None and int(base.value(sw, "GetDocumentCount")) != 0:
            raise SystemExit("LEAKED_DOCUMENT")


if __name__ == "__main__":
    sys.exit(main())
