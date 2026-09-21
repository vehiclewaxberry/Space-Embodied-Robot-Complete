#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1D live probe: lightweight-on-cold-open resolution semantics.

Dress rehearsal (V5_PROBE_LOOP1D_DRESS_REHEARSAL_20260811T065500Z.log) proved
the patched live configure_document passes (per-config explicit mate
suppression now follows the state-proxy endpoints), but the patched cold
verifier failed at CONFIG_COMPONENT_STATE_FAIL: on a cold READ-ONLY reopen
active components report GetSuppression2()=2 (lightweight), not 1 (resolved).
Probe V5_PROBE_LOOP1D_COLD_REOPEN_DIAG C0/C2/C5 showed the same and that
IAssemblyDoc.ResolveAllLightWeightComponents(True) returns False (no-op) on a
read-only document.

This probe measures, on the still-existing dress-rehearsal assembly
(%TEMP%/V5_PROBE_LOOP1D_DRESS_REHEARSAL_20260811T065052.107926Z.SLDASM, saved
with STATE_A active; per-config suppression: STATE_A has SLIDER-2 suppressed,
STATE_B has SLIDER-1 suppressed):

  L1  cold read-only open; as-opened component dump (suppression/fixed/
      Transform2) in the saved-active STATE_A
  L2  per-component IComponent2.SetSuppression2(1) drive on lightweight
      components (fresh handles, read-only doc) -> readback 1 or failure;
      suppressed component left untouched
  L3  per configuration: show_configuration + resolve-active drive +
      full Transform2 readback of every occurrence (including the suppressed
      one) + GetBodies2(0) body counts + IBody2.GetExtremePoint sanity, i.e.
      everything the cold verifier's snapshot + B-rep witness needs
  L4  diagnostic only: reopen NON-read-only (silent) and dump as-opened
      suppression values, to attribute the lightweight load mode
  L5  session left document-empty; the probe never saves anything
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

EXPECTED_TRANSFORMS = {
    "ARM_HDRM_LOAD_TRANSFER_BASE-1": [0.0, 0.0, 150.0],
    "ARM_HDRM_LATCH_SLIDER-1": [8.0, 0.0, 150.0],
    "ARM_HDRM_LATCH_SLIDER-2": [2.0, 0.0, 150.0],
}


def log(step: str) -> None:
    print(f"[{time.time() - T0:8.2f}s] {step}", flush=True)


def memory_gib() -> float:
    try:
        import psutil

        return round(psutil.virtual_memory().available / 2**30, 3)
    except Exception:  # noqa: BLE001
        return -1.0


def transform_translation(component: Any) -> Any:
    raw = base.value(component, "Transform2")
    if raw is None:
        return None
    array = [float(value) for value in base.as_list(base.value(raw, "ArrayData"))]
    if len(array) != 16:
        return {"bad_len": len(array)}
    return [round(array[9] * 1000.0, 6), round(array[10] * 1000.0, 6), round(array[11] * 1000.0, 6)]


def dump_components(model: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    rows: List[Dict[str, Any]] = []
    for raw in base.as_list(assembly.GetComponents(True)):
        component = base.wrap(raw, "IComponent2", types, pythoncom)
        name2 = str(base.value(component, "Name2"))
        body_count = None
        try:
            body_count = len(base.as_list(component.GetBodies2(0)))
        except Exception as exc:  # noqa: BLE001
            body_count = f"exception:{exc!r}"
        rows.append({
            "name2": name2,
            "suppression": int(base.value(component, "GetSuppression2")),
            "fixed": bool(base.value(component, "IsFixed")),
            "translation_mm": transform_translation(component),
            "expected_translation_mm": EXPECTED_TRANSFORMS.get(name2),
            "solid_body_count": body_count,
        })
    return sorted(rows, key=lambda row: row["name2"])


def resolve_active_drive(model: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    """SetSuppression2(1) on every non-suppressed component; never touch suppressed."""
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    rows: List[Dict[str, Any]] = []
    for raw in base.as_list(assembly.GetComponents(True)):
        component = base.wrap(raw, "IComponent2", types, pythoncom)
        name2 = str(base.value(component, "Name2"))
        before = int(base.value(component, "GetSuppression2"))
        row: Dict[str, Any] = {"name2": name2, "before": before}
        if before != 0:
            try:
                returned = component.SetSuppression2(1)
                row["returned"] = returned
            except Exception as exc:  # noqa: BLE001
                row["exception"] = repr(exc)
            row["after"] = int(base.value(component, "GetSuppression2"))
        rows.append(row)
    return rows


def extreme_point_sanity(model: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    from win32com.client import VARIANT

    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    rows: List[Dict[str, Any]] = []
    for raw in base.as_list(assembly.GetComponents(True)):
        component = base.wrap(raw, "IComponent2", types, pythoncom)
        name2 = str(base.value(component, "Name2"))
        if int(base.value(component, "GetSuppression2")) == 0:
            continue
        bodies = base.as_list(component.GetBodies2(0))
        row: Dict[str, Any] = {"name2": name2, "bodies": len(bodies)}
        if bodies:
            body = base.wrap(bodies[0], "IBody2", types, pythoncom)
            outx = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
            outy = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
            outz = VARIANT(pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
            try:
                ok = bool(body.GetExtremePoint(1.0, 0.0, 0.0, outx, outy, outz))
                row["extreme_ok"] = ok
                row["extreme_x_mm"] = round(float(outx.value) * 1000.0, 6) if ok else None
            except Exception as exc:  # noqa: BLE001
                row["extreme_exception"] = repr(exc)
        rows.append(row)
    return rows


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
        "schema": "V5_PROBE_LOOP1D_LIGHTWEIGHT_RESOLVE_V1",
        "timestamp_start_utc": datetime.now(timezone.utc).isoformat(),
        "target": str(TARGET),
        "target_exists": TARGET.is_file(),
        "phases": {},
    }
    sw = types = pythoncom = None
    try:
        if not TARGET.is_file():
            raise RuntimeError(f"probe target missing: {TARGET}")
        sw, types, pythoncom, session = base.attach_empty_session()
        result["session"] = session
        result["memory_available_gib_start"] = memory_gib()
        log(f"attach: ok pid={session['pid']} rev={session['revision']} docs={session['document_count']}")

        # ---- L1: cold read-only open, as-opened dump ------------------------
        raw, errors, warnings = m.unpack_document(sw.OpenDoc6(str(TARGET), 2, 3, "", 0, 0), "L1_OPEN")
        if raw is None or errors != 0 or warnings != 0:
            raise RuntimeError(f"cold open failed errors={errors} warnings={warnings}")
        model = base.wrap(raw, "IModelDoc2", types, pythoncom)
        if not bool(base.value(model, "IsOpenedReadOnly")):
            raise RuntimeError("L1 open was not read-only")
        title = str(base.value(model, "GetTitle"))
        result["phases"]["L1_as_opened"] = {
            "active": None,
            "components": dump_components(model, types, pythoncom),
        }
        log("L1: as-opened dump captured (read-only)")

        # ---- L2: SetSuppression2(1) drive on lightweight components ---------
        drive = resolve_active_drive(model, types, pythoncom)
        result["phases"]["L2_resolve_drive"] = drive
        log(f"L2: resolve drive -> {[(r['name2'], r.get('before'), r.get('after')) for r in drive]}")
        model.ForceRebuild3(True)
        result["phases"]["L2_post_rebuild"] = dump_components(model, types, pythoncom)

        # ---- L3: per-config full readback (what the cold verifier needs) ----
        per_config: Dict[str, Any] = {}
        for config in ("STATE_A", "STATE_B"):
            m.show_configuration(model, config, types, pythoncom)
            model.ForceRebuild3(True)
            per_config[config] = {
                "resolve_drive": resolve_active_drive(model, types, pythoncom),
                "components": dump_components(model, types, pythoncom),
                "extreme_points": extreme_point_sanity(model, types, pythoncom),
            }
            log(f"L3: {config} captured")
        result["phases"]["L3_per_config"] = per_config
        sw.CloseDoc(title)

        # ---- L4: diagnostic non-read-only reopen -----------------------------
        raw2, errors2, warnings2 = m.unpack_document(sw.OpenDoc6(str(TARGET), 2, 1, "", 0, 0), "L4_OPEN")
        if raw2 is None or errors2 != 0 or warnings2 != 0:
            raise RuntimeError(f"L4 open failed errors={errors2} warnings={warnings2}")
        model2 = base.wrap(raw2, "IModelDoc2", types, pythoncom)
        title2 = str(base.value(model2, "GetTitle"))
        result["phases"]["L4_writable_open"] = {
            "read_only": bool(base.value(model2, "IsOpenedReadOnly")),
            "components": dump_components(model2, types, pythoncom),
        }
        log("L4: writable-open dump captured")
        sw.CloseDoc(title2)

        # ---- verdict synthesis ----------------------------------------------
        l2_ok = all(row.get("after") == 1 for row in drive if row["before"] != 0)
        transforms_ok = True
        for config, payload in per_config.items():
            for row in payload["components"]:
                expected = row["expected_translation_mm"]
                actual = row["translation_mm"]
                if not isinstance(actual, list) or expected is None or any(abs(a - e) > 1.0e-6 for a, e in zip(actual, expected)):
                    transforms_ok = False
        bodies_ok = all(
            row["bodies"] >= 1 and row.get("extreme_ok") is True
            for payload in per_config.values()
            for row in payload["extreme_points"]
        )
        checks = {
            "L2_set_suppression_resolves_lightweight_readonly": l2_ok,
            "L3_transforms_exact_including_suppressed": transforms_ok,
            "L3_bodies_and_extreme_points_ok": bodies_ok,
        }
        result["checks"] = checks
        result["verdict"] = "V5_PROBE_LOOP1D_LIGHTWEIGHT_RESOLVE_PASS" if all(checks.values()) else "V5_PROBE_LOOP1D_LIGHTWEIGHT_RESOLVE_MIXED"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1D_LIGHTWEIGHT_RESOLVE_FAIL"
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
    return 0 if result.get("verdict") == "V5_PROBE_LOOP1D_LIGHTWEIGHT_RESOLVE_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
