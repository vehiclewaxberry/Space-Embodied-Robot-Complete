#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1D live probe: IBody2.GetExtremePoint call-form matrix.

Dress rehearsal + lightweight probe proved: cold read-only reopen loads active
components lightweight (GetSuppression2()=2); SetSuppression2(1) on fresh
handles resolves them in place on the read-only document; per-config saved
suppression patterns and Transform2 (including suppressed occurrences) read
back exactly.  The only unproven cold-verifier primitive is
assembly_brep_bbox_mm: its makepy call
``body.GetExtremePoint(dx, dy, dz, outx, outy, outz)`` with explicit
VT_BYREF|VT_R8 VARIANTs raised ``TypeError: float() argument must be a string
or a real number, not 'VARIANT'`` (probe
V5_PROBE_LOOP1D_LIGHTWEIGHT_RESOLVE_20260811T072000Z.log, L3).

This micro-probe measures working call forms on the cold read-only
dress-rehearsal assembly
(%TEMP%/V5_PROBE_LOOP1D_DRESS_REHEARSAL_20260811T065052.107926Z.SLDASM):
  E1  makepy wrapped call WITHOUT explicit out args (makepy-managed byrefs)
  E2  makepy wrapped call WITH explicit VARIANTs (the failing production form)
  E3  late-bound dynamic dispatch WITH explicit VARIANTs (Loop1C1 recipe)
  E4  GetBodyBox (the proven base.body_facts form) + transformed-corner AABB
      reconstruction under the component transform
and cross-checks E1/E3/E4 extrema agree on the probe bodies.
Read-only; saves nothing; leaves the session document-empty.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base  # noqa: E402
import F3R2_V5_NATIVE_LOOP1D_HDRM_CAMERA_HARNESS_ATTACH_ONLY as m  # noqa: E402

T0 = time.time()
TARGET = Path.home() / "AppData/Local/Temp/V5_PROBE_LOOP1D_DRESS_REHEARSAL_20260811T065052.107926Z.SLDASM"


def log(step: str) -> None:
    print(f"[{time.time() - T0:8.2f}s] {step}", flush=True)


def memory_gib() -> float:
    try:
        import psutil

        return round(psutil.virtual_memory().available / 2**30, 3)
    except Exception:  # noqa: BLE001
        return -1.0


def close_all(sw: Any) -> int:
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
    return int(base.value(sw, "GetDocumentCount"))


def main() -> int:
    result: Dict[str, Any] = {
        "schema": "V5_PROBE_LOOP1D_EXTREME_POINT_API_V1",
        "timestamp_start_utc": datetime.now(timezone.utc).isoformat(),
        "target": str(TARGET),
        "target_exists": TARGET.is_file(),
        "forms": {},
    }
    sw = types = pythoncom = None
    try:
        if not TARGET.is_file():
            raise RuntimeError(f"probe target missing: {TARGET}")
        sw, types, pythoncom, session = base.attach_empty_session()
        result["session"] = session
        result["memory_available_gib_start"] = memory_gib()
        log(f"attach: ok pid={session['pid']} rev={session['revision']} docs={session['document_count']}")

        raw, errors, warnings = m.unpack_document(sw.OpenDoc6(str(TARGET), 2, 3, "", 0, 0), "E_OPEN")
        if raw is None or errors != 0 or warnings != 0:
            raise RuntimeError(f"cold open failed errors={errors} warnings={warnings}")
        model = base.wrap(raw, "IModelDoc2", types, pythoncom)
        title = str(base.value(model, "GetTitle"))
        if not bool(base.value(model, "IsOpenedReadOnly")):
            raise RuntimeError("open was not read-only")

        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
        component = None
        for raw_component in base.as_list(assembly.GetComponents(True)):
            candidate = base.wrap(raw_component, "IComponent2", types, pythoncom)
            if str(base.value(candidate, "Name2")) == "ARM_HDRM_LOAD_TRANSFER_BASE-1":
                component = candidate
        if component is None:
            raise RuntimeError("probe component not found")
        component.SetSuppression2(1)
        model.ForceRebuild3(True)
        bodies = base.as_list(component.GetBodies2(0))
        if not bodies:
            raise RuntimeError("no solid bodies on resolved cold component")
        raw_body = bodies[0]
        # Expected truth for ARM_HDRM_LOAD_TRANSFER_BASE local body: annulus
        # outer radius 30 mm, depth 10 mm -> +X extreme point x = +0.03 m.
        expected_local_x_m = 0.03

        import pythoncom as pcom
        from win32com.client import VARIANT, Dispatch

        # ---- E1: makepy wrapped, no explicit out args ------------------------
        body_w = base.wrap(raw_body, "IBody2", types, pythoncom)
        try:
            returned = body_w.GetExtremePoint(1.0, 0.0, 0.0)
            result["forms"]["E1_makepy_no_outargs"] = {"returned_type": type(returned).__name__, "returned": repr(returned)[:400]}
        except Exception as exc:  # noqa: BLE001
            result["forms"]["E1_makepy_no_outargs"] = {"exception": repr(exc)}

        # ---- E2: makepy wrapped, explicit VARIANTs (failing production form) -
        try:
            ox = VARIANT(pcom.VT_BYREF | pcom.VT_R8, 0.0)
            oy = VARIANT(pcom.VT_BYREF | pcom.VT_R8, 0.0)
            oz = VARIANT(pcom.VT_BYREF | pcom.VT_R8, 0.0)
            returned = body_w.GetExtremePoint(1.0, 0.0, 0.0, ox, oy, oz)
            result["forms"]["E2_makepy_variants"] = {"returned": repr(returned)[:300], "ox": repr(ox.value)[:120], "oy": repr(oy.value)[:120], "oz": repr(oz.value)[:120]}
        except Exception as exc:  # noqa: BLE001
            result["forms"]["E2_makepy_variants"] = {"exception": repr(exc)}

        # ---- E3: late-bound dispatch with explicit VARIANTs ------------------
        try:
            body_d = Dispatch(raw_body)
            ox = VARIANT(pcom.VT_BYREF | pcom.VT_R8, 0.0)
            oy = VARIANT(pcom.VT_BYREF | pcom.VT_R8, 0.0)
            oz = VARIANT(pcom.VT_BYREF | pcom.VT_R8, 0.0)
            returned = body_d.GetExtremePoint(1.0, 0.0, 0.0, ox, oy, oz)
            result["forms"]["E3_latebound_variants"] = {"returned": repr(returned)[:300], "ox": repr(ox.value)[:120], "oy": repr(oy.value)[:120], "oz": repr(oz.value)[:120]}
        except Exception as exc:  # noqa: BLE001
            result["forms"]["E3_latebound_variants"] = {"exception": repr(exc)}

        # ---- E4: GetBodyBox + transformed corners -----------------------------
        try:
            box = [float(number) for number in base.as_list(base.value(body_w, "GetBodyBox"))]
            transform = [float(value) for value in base.as_list(base.value(base.value(component, "Transform2"), "ArrayData"))]
            corners = []
            for cx in (box[0], box[3]):
                for cy in (box[1], box[4]):
                    for cz in (box[2], box[5]):
                        corners.append(m.transform_point(transform, [cx, cy, cz]))
            world = [min(c[axis] for c in corners) for axis in range(3)] + [max(c[axis] for c in corners) for axis in range(3)]
            result["forms"]["E4_bodybox_corners"] = {"local_box_m": box, "world_bbox_mm": [round(v * 1000.0, 6) for v in world]}
        except Exception as exc:  # noqa: BLE001
            result["forms"]["E4_bodybox_corners"] = {"exception": repr(exc)}

        log("E1..E4 captured")
        sw.CloseDoc(title)

        result["expected_local_plus_x_m"] = expected_local_x_m
        result["verdict"] = "V5_PROBE_LOOP1D_EXTREME_POINT_API_DONE"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1D_EXTREME_POINT_API_FAIL"
        log("exception; see payload")
    finally:
        if sw is not None:
            try:
                remaining = close_all(sw)
                result["cleanup_document_count"] = remaining
                log(f"cleanup: document_count={remaining}")
            except Exception as cleanup_exc:  # noqa: BLE001
                result["cleanup_exception"] = repr(cleanup_exc)
        result["memory_available_gib_end"] = memory_gib()
        result["timestamp_end_utc"] = datetime.now(timezone.utc).isoformat()
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:  # noqa: BLE001
                pass
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0 if result.get("verdict") == "V5_PROBE_LOOP1D_EXTREME_POINT_API_DONE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
