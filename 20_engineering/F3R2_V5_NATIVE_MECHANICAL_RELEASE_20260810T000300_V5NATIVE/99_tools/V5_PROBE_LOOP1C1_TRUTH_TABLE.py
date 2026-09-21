#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1C1 live probe v7: full truth table for per-config dimension drive.

Run-4 evidence (V5_LOOP1C1_FAIL_20260811T024640): after establish_configurations
passed all eight named set+readback pairs, verify_state(OPEN) still reads the
RIGHT finger at ty=0 with a quasi-identity rotation.  Two candidate mechanisms:
  T1: per-config named writes landed in wrong slots (OPEN actually holds the
      CLOSED value 0.0337 m -> ty 0);
  T2: values are right but configuration activation does not re-solve the mate
      geometry (and/or Transform2 reads are stale even on fresh handles).

v6b was ambiguous (PREGRASP was both active and named).  v7 discriminates by
printing, for every drive step and every later activation, the active config,
the named readbacks of ALL four configs, and the fresh finger translation.

Never saves, never writes receipts, leaves the session document-empty.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base  # noqa: E402
import F3R2_V5_NATIVE_LOOP1C1_GRIPPER_ASSEMBLY_ATTACH_ONLY as m  # noqa: E402

OPEN_TRAVEL_MM = float(m.STATES["OPEN"]["travel_mm"])
T0 = time.time()


def log(step: str) -> None:
    print(f"[{time.time() - T0:8.2f}s] {step}", flush=True)


def main() -> int:
    result: Dict[str, Any] = {"schema": "V5_PROBE_LOOP1C1_TRUTH_TABLE_V8", "drive_steps": [], "activations": [], "notes": []}
    sw = types = pythoncom = None
    try:
        from win32com.client import VARIANT

        log("attach: begin")
        sw, types, pythoncom, session = base.attach_empty_session()
        result["session"] = session
        raw_model = sw.NewDocument(str(m.ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
        model = base.wrap(raw_model, "IModelDoc2", types, pythoncom)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
        for role in ("PALM", "LEFT", "RIGHT"):
            spec = m.PARTS[role]
            translation = m.expected_translation_m(role, OPEN_TRAVEL_MM)
            m.insert_component(sw, model, assembly, role, Path(spec["path"]), bool(spec["fixed"]), translation, types, pythoncom)
            log(f"insert {role}: ok")
        components = m.assembly_components(model, assembly, types, pythoncom)
        for side, prefix in (("LEFT", "L"), ("RIGHT", "R")):
            for guide in ("A", "B"):
                palm_face, _pf = m.guide_face(model, components["PALM"], "PALM", guide, types, pythoncom)
                finger_face, _ff = m.guide_face(model, components[side], side, guide, types, pythoncom)
                m.add_face_mate(model, assembly, palm_face, finger_face, 1, m.MATE_NAMES[f"{prefix}_{guide}"], types, pythoncom)
            m.add_advanced_limit_distance(
                model, assembly, components["PALM"], components[side],
                m.MATE_NAMES[f"{prefix}_LIMIT"], prefix, int(m.LIMIT_CONTRACTS[prefix]["alignment"]), types, pythoncom,
            )
            log(f"{prefix} guides+limit: ok")

        limit_features = []
        for feature in m.mate_features(model, types, pythoncom):
            if str(base.value(feature, "Name")) in (m.MATE_NAMES["L_LIMIT"], m.MATE_NAMES["R_LIMIT"]):
                limit_features.append(feature)
        limit_features.sort(key=lambda f: str(base.value(f, "Name")))
        drive_info = m.establish_configurations(model, limit_features, types, pythoncom)
        result["establish_drive_rows"] = len(drive_info["dimension_drive"])
        log(f"establish_configurations: ok ({result['establish_drive_rows']} drive rows)")
        m.set_assembly_properties(model)
        log("set_assembly_properties: ok")

        dims = {}
        for feature in m.mate_features(model, types, pythoncom):
            fname = str(base.value(feature, "Name"))
            if fname in (m.MATE_NAMES["L_LIMIT"], m.MATE_NAMES["R_LIMIT"]):
                dims[fname] = m.mate_dimension(feature, types, pythoncom)

        def ty_mm(role: str) -> Any:
            try:
                fresh = m.assembly_components(model, assembly, types, pythoncom)
                data = [float(v) for v in base.as_list(base.value(base.value(fresh[role], "Transform2"), "ArrayData"))]
                return round(data[10] * 1000.0, 6)
            except Exception as exc:  # noqa: BLE001
                return repr(exc)

        def named_gets(dim) -> Dict[str, Any]:
            row: Dict[str, Any] = {}
            for cfg in ("OPEN", "PREGRASP", "CLOSED", "HOLDING"):
                try:
                    row[cfg] = float(dim.GetSystemValue2(cfg))
                except Exception as exc:  # noqa: BLE001
                    row[cfg] = repr(exc)
            return row

        for name in ("OPEN", "PREGRASP", "CLOSED", "HOLDING"):
            m.show_configuration(model, name, types, pythoncom)
            row = {
                "active": name,
                "l_named_gets": named_gets(dims[m.MATE_NAMES["L_LIMIT"]]),
                "r_named_gets": named_gets(dims[m.MATE_NAMES["R_LIMIT"]]),
                "left_ty_mm": ty_mm("LEFT"),
                "right_ty_mm": ty_mm("RIGHT"),
            }
            result["activations"].append(row)
            log(f"activate {name}: L={row['left_ty_mm']} R={row['right_ty_mm']}")
        result["verdict"] = "V5_PROBE_LOOP1C1_TRUTH_TABLE_V8_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1C1_TRUTH_TABLE_V8_FAIL"
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
