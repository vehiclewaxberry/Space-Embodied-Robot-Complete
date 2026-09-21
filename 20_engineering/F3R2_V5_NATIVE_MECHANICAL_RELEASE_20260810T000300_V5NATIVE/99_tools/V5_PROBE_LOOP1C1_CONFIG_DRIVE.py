#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1C1 live probe v6: per-configuration dimension drive API matrix.

Run-2 failure evidence (receipt V5_LOOP1C1_FAIL_20260811T014649.223295Z.json):
SetSystemValue3(value, swThisConfiguration=1, []) returned status 0 but the
PREGRASP value stayed at the OPEN value, while probe v5's identical call worked
in a single-configuration document.  The option-3 name-array GET returned an
empty list in run 1 (status 0 on the SET though).

This probe builds the exact production state (4 guides @ align=1, both advanced
limit mates via the patched production functions), creates the 4 configurations
exactly like establish_configurations, then on the L limit dimension tries:

  set variants (distinct sentinel values so attribution is unambiguous):
    S1 SetSystemValue3(v, 1, [])
    S2 SetSystemValue2(v, 1)
    S3 SetSystemValue3(v, 3, ["PREGRASP"])                 (python list)
    S4 SetSystemValue3(v, 3, VARIANT(VT_ARRAY|VT_BSTR,...)) (typed array)
  get variants after each set (plus finger translation as ground truth):
    G1 GetSystemValue3(1, [])
    G2 GetSystemValue2("PREGRASP")
    G3 GetSystemValue3(3, ["PREGRASP"])
    G4 GetSystemValue3(3, VARIANT(VT_ARRAY|VT_BSTR,...))

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
    result: Dict[str, Any] = {"schema": "V5_PROBE_LOOP1C1_CONFIG_DRIVE_V6", "sets": [], "notes": []}
    sw = types = pythoncom = None
    try:
        log("attach: begin")
        sw, types, pythoncom, session = base.attach_empty_session()
        result["session"] = session
        log(f"attach: ok pid={session['pid']}")
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

        # configuration preamble identical to establish_configurations
        manager = base.wrap(base.value(model, "ConfigurationManager"), "IConfigurationManager", types, pythoncom)
        active = base.wrap(base.value(manager, "ActiveConfiguration"), "IConfiguration", types, pythoncom)
        active.Name = "OPEN"
        for name in ("PREGRASP", "CLOSED", "HOLDING"):
            created = manager.AddConfiguration2(name, f"F3R2 B601 gripper {name}", "", 0, "", "", True)
            if created is None:
                raise m.GateError("CONFIGURATION_CREATE_FAIL", "AddConfiguration2 returned null", {"configuration": name})
        log("configurations created: OPEN/PREGRASP/CLOSED/HOLDING")

        l_feature = None
        for feature in m.mate_features(model, types, pythoncom):
            if str(base.value(feature, "Name")) == m.MATE_NAMES["L_LIMIT"]:
                l_feature = feature
        if l_feature is None:
            raise m.GateError("PROBE_L_LIMIT_MISSING", "L limit feature not found")
        dimension = m.mate_dimension(l_feature, types, pythoncom)

        def ty_mm() -> float:
            fresh = m.assembly_components(model, assembly, types, pythoncom)
            data = [float(v) for v in base.as_list(base.value(base.value(fresh["LEFT"], "Transform2"), "ArrayData"))]
            return round(data[10] * 1000.0, 6)

        def getters() -> Dict[str, Any]:
            from win32com.client import VARIANT

            row: Dict[str, Any] = {}
            try:
                row["G1_this"] = [float(v) for v in base.as_list(dimension.GetSystemValue3(1, []))]
            except Exception as exc:  # noqa: BLE001
                row["G1_this"] = repr(exc)
            try:
                row["G2_named"] = float(dimension.GetSystemValue2("PREGRASP"))
            except Exception as exc:  # noqa: BLE001
                row["G2_named"] = repr(exc)
            try:
                row["G3_list"] = [float(v) for v in base.as_list(dimension.GetSystemValue3(3, ["PREGRASP"]))]
            except Exception as exc:  # noqa: BLE001
                row["G3_list"] = repr(exc)
            try:
                row["G4_variant"] = [float(v) for v in base.as_list(dimension.GetSystemValue3(3, VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, ["PREGRASP"])))]
            except Exception as exc:  # noqa: BLE001
                row["G4_variant"] = repr(exc)
            row["left_ty_mm"] = ty_mm()
            return row

        m.show_configuration(model, "PREGRASP", types, pythoncom)
        result["pregrasp_before"] = getters()
        log(f"pregrasp before: {json.dumps(result['pregrasp_before'])}")

        from win32com.client import VARIANT

        sentinels = [("S1_set3_this", 0.115700), ("S2_set2_this", 0.115600), ("S3_set3_list", 0.115500), ("S4_set3_bstr_array", 0.115400)]
        for label, value_m in sentinels:
            row: Dict[str, Any] = {"label": label, "requested_m": value_m}
            try:
                if label == "S1_set3_this":
                    row["status"] = int(dimension.SetSystemValue3(value_m, 1, []))
                elif label == "S2_set2_this":
                    row["status"] = int(dimension.SetSystemValue2(value_m, 1))
                elif label == "S3_set3_list":
                    row["status"] = int(dimension.SetSystemValue3(value_m, 3, ["PREGRASP"]))
                else:
                    row["status"] = int(dimension.SetSystemValue3(value_m, 3, VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_BSTR, ["PREGRASP"])))
            except Exception as exc:  # noqa: BLE001
                row["status"] = repr(exc)
            model.EditRebuild3()
            row["after"] = getters()
            result["sets"].append(row)
            log(f"{label}: status={row['status']} after={json.dumps(row['after'])}")
        result["verdict"] = "V5_PROBE_LOOP1C1_CONFIG_DRIVE_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1C1_CONFIG_DRIVE_FAIL"
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
