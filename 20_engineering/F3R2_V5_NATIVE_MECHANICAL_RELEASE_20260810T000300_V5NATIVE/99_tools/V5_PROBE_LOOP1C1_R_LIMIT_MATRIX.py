#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1C1 live probe v2: discriminate the R advanced-limit-mate error 5.

Attach-only against the qualified empty SolidWorks 2024 session (PID 87516).
Builds the EXACT pre-R-limit state with the Loop1C1 script's own functions
(insert 3 native parts at OPEN translations, 4 guide coincident mates, L advanced
limit mate), then runs an AddMate3 argument matrix for the R limit face pair.

v2 changes vs the timed-out v1:
  - no ForPositioningOnly calls (suspected modal-dialog hang); every case is a
    REAL create (exactly the production call path, proven non-blocking by the
    13 prior production failures) followed by mate deletion + transform restore;
  - flushed step logging so a hang localizes to an exact call;
  - Phase 2 pre-validates the F1 patch end to end: plain distance create
    (upper=lower=0) -> IDistanceMateFeatureData advanced conversion via
    ModifyDefinition -> production advanced_limit_facts readback gate.

Never saves, never writes receipts, leaves the session document-empty via the
production close_all_owned(). Result JSON on stdout.
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
OPEN_M = (m.LIMIT_R_BASE_MM + OPEN_TRAVEL_MM) / 1000.0
MAX_M = float(m.LIMIT_MAX_MM["R"]) / 1000.0
T0 = time.time()


def log(step: str) -> None:
    print(f"[{time.time() - T0:8.2f}s] {step}", flush=True)


def transform_array(component: Any, types: Any, pythoncom: Any) -> List[float]:
    raw = base.value(component, "Transform2")
    return [float(value) for value in base.as_list(base.value(raw, "ArrayData"))]


def translation_mm(data: List[float]) -> List[float]:
    return [round(data[9] * 1000.0, 6), round(data[10] * 1000.0, 6), round(data[11] * 1000.0, 6)]


def rotation_diag(data: List[float]) -> List[float]:
    return [round(data[0], 9), round(data[4], 9), round(data[8], 9)]


def main() -> int:
    result: Dict[str, Any] = {"schema": "V5_PROBE_LOOP1C1_R_LIMIT_MATRIX_V2", "cases": [], "notes": []}
    sw = types = pythoncom = None
    try:
        log("attach: begin")
        sw, types, pythoncom, session = base.attach_empty_session()
        result["session"] = session
        log(f"attach: ok pid={session['pid']} rev={session['revision']}")
        raw_model = sw.NewDocument(str(m.ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
        if raw_model is None:
            raise m.GateError("NEW_ASSEMBLY_FAIL", "NewDocument returned null")
        model = base.wrap(raw_model, "IModelDoc2", types, pythoncom)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
        log("new assembly document: ok")
        for role in ("PALM", "LEFT", "RIGHT"):
            spec = m.PARTS[role]
            translation = m.expected_translation_m(role, OPEN_TRAVEL_MM)
            m.insert_component(sw, model, assembly, role, Path(spec["path"]), bool(spec["fixed"]), translation, types, pythoncom)
            log(f"insert {role}: ok")
        components = m.assembly_components(model, assembly, types, pythoncom)
        for side, prefix in (("LEFT", "L"), ("RIGHT", "R")):
            for guide in ("A", "B"):
                palm_face, _palm_fact = m.guide_face(model, components["PALM"], "PALM", guide, types, pythoncom)
                finger_face, _finger_fact = m.guide_face(model, components[side], side, guide, types, pythoncom)
                name = m.MATE_NAMES[f"{prefix}_{guide}"]
                alignment = int(m.GUIDE_CONTRACTS[guide][f"{side}_alignment"])
                m.add_face_mate(model, assembly, palm_face, finger_face, alignment, name, types, pythoncom)
                log(f"guide {name}: ok")
        m.add_advanced_limit_distance(
            model, assembly, components["PALM"], components["LEFT"],
            m.MATE_NAMES["L_LIMIT"], "L", int(m.LIMIT_CONTRACTS["L"]["alignment"]), types, pythoncom,
        )
        log("L advanced limit mate: ok")
        snapshot = {role: transform_array(component, types, pythoncom) for role, component in components.items()}
        result["state_after_guides_and_l_limit"] = {
            role: {"translation_mm": translation_mm(snapshot[role]), "rotation_diag": rotation_diag(snapshot[role])}
            for role in snapshot
        }
        result["mate_names"] = [str(base.value(feature, "Name")) for feature in m.mate_features(model, types, pythoncom)]

        palm_entity, palm_fact = m.limit_face(model, components["PALM"], "PALM", "R", "palm", types, pythoncom)
        finger_entity, finger_fact = m.limit_face(model, components["RIGHT"], "RIGHT", "R", "finger", types, pythoncom)
        result["r_limit_faces"] = {"palm_offset_mm": palm_fact["offset_mm"], "finger_offset_mm": finger_fact["offset_mm"]}
        log("R limit faces resolved")

        def select_pair(first: Any, second: Any) -> bool:
            model.ClearSelection2(True)
            manager = m.selection_manager(model, types, pythoncom)
            data = base.wrap(manager.CreateSelectData(), "ISelectData", types, pythoncom)
            data.Mark = 1
            ok_first = bool(first.Select4(False, data))
            ok_second = bool(second.Select4(True, data))
            return ok_first and ok_second

        def restore_right() -> bool:
            transform = m.make_transform(sw, snapshot["RIGHT"], types, pythoncom)
            ok = bool(components["RIGHT"].SetTransformAndSolve3(transform, True))
            model.EditRebuild3()
            return ok

        def delete_mate_named(name: str) -> Any:
            try:
                ok = bool(model.Extension.SelectByID2(name, "MATE", 0, 0, 0, False, 0, None, 0))
                if ok:
                    model.EditDelete()
                    model.ClearSelection2(True)
                    model.EditRebuild3()
                return ok
            except Exception as exc:  # noqa: BLE001
                return repr(exc)

        cases: List[Dict[str, Any]] = [
            {"label": "C1_control_limit_current", "align": 1, "flip": False, "dist": OPEN_M, "upper": MAX_M, "lower": 0.0},
            {"label": "C2_plain_anti", "align": 1, "flip": False, "dist": OPEN_M, "upper": 0.0, "lower": 0.0},
            {"label": "C3_limit_strict_upper", "align": 1, "flip": False, "dist": OPEN_M, "upper": MAX_M + 0.001, "lower": 0.0},
            {"label": "C5_limit_aligned", "align": 0, "flip": False, "dist": OPEN_M, "upper": MAX_M, "lower": 0.0},
            {"label": "C6_plain_aligned", "align": 0, "flip": False, "dist": OPEN_M, "upper": 0.0, "lower": 0.0},
            {"label": "C9_plain_anti_finger_first", "align": 1, "flip": False, "dist": OPEN_M, "upper": 0.0, "lower": 0.0, "swap": True},
            {"label": "C4_limit_wide", "align": 1, "flip": False, "dist": OPEN_M, "upper": 0.2, "lower": -0.2},
            {"label": "C8_plain_anti_flip", "align": 1, "flip": True, "dist": OPEN_M, "upper": 0.0, "lower": 0.0},
        ]

        for case in cases:
            log(f"case {case['label']}: select+call")
            first, second = (finger_entity, palm_entity) if case.get("swap") else (palm_entity, finger_entity)
            selected = select_pair(first, second)
            before_ty = translation_mm(transform_array(components["RIGHT"], types, pythoncom))
            before_names = [str(base.value(feature, "Name")) for feature in m.mate_features(model, types, pythoncom)]
            returned = assembly.AddMate3(
                m.SW_MATE_DISTANCE, int(case["align"]), bool(case["flip"]),
                float(case["dist"]), float(case["upper"]), float(case["lower"]),
                0.0, 0.0, 0.0, 0.0, 0.0, False, 0,
            )
            mate_raw, outs = base.unpack(returned)
            error = int(outs[0]) if outs else None
            model.ClearSelection2(True)
            after_ty = translation_mm(transform_array(components["RIGHT"], types, pythoncom))
            row: Dict[str, Any] = {
                "label": case["label"],
                "selected": selected,
                "error": error,
                "mate_raw_is_none": mate_raw is None,
                "right_translation_before_mm": before_ty,
                "right_translation_after_mm": after_ty,
            }
            log(f"case {case['label']}: error={error}")
            if mate_raw is not None:
                names_now = [str(base.value(feature, "Name")) for feature in m.mate_features(model, types, pythoncom)]
                added = [name for name in names_now if name not in before_names]
                row["added_mates"] = added
                for name in added:
                    row.setdefault("deleted", {})[name] = delete_mate_named(name)
                    log(f"case {case['label']}: deleted {name} -> {row['deleted'][name]}")
            row["restored"] = restore_right()
            result["cases"].append(row)

        plain = next((row for row in result["cases"] if row["label"] == "C2_plain_anti"), None)
        if plain is not None and plain.get("error") == 1:
            log("phase 2: F1 plain create + advanced conversion")
            before_names = [str(base.value(feature, "Name")) for feature in m.mate_features(model, types, pythoncom)]
            select_pair(palm_entity, finger_entity)
            returned = assembly.AddMate3(m.SW_MATE_DISTANCE, 1, False, OPEN_M, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False, 0)
            mate_raw, outs = base.unpack(returned)
            error = int(outs[0]) if outs else None
            model.ClearSelection2(True)
            f1: Dict[str, Any] = {"create_error": error, "mate_raw_is_none": mate_raw is None}
            if error == 1 and mate_raw is not None:
                feature = m.added_mate_feature(before_names, model, "PROBE_R_PLAIN_DIST", types, pythoncom)
                data = m.distance_mate_data(feature, types, pythoncom)
                data.IsAdvancedMate = True
                data.MinimumDistance = 0.0
                data.MaximumDistance = MAX_M
                data.Distance = OPEN_M
                data.MateAlignment = 1
                f1["modify_definition_ok"] = bool(feature.ModifyDefinition(data, model, None))
                f1["rebuild_ok"] = bool(model.ForceRebuild3(True))
                f1["facts"] = m.advanced_limit_facts(feature, types, pythoncom, float(m.LIMIT_MAX_MM["R"]))
                f1["right_translation_mm"] = translation_mm(transform_array(components["RIGHT"], types, pythoncom))
                log(f"phase 2: modify_ok={f1['modify_definition_ok']} readback_pass={f1['facts'].get('pass')}")
            result["f1_real_create_and_convert"] = f1
        result["verdict"] = "V5_PROBE_LOOP1C1_R_LIMIT_MATRIX_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1C1_R_LIMIT_MATRIX_FAIL"
        log("exception; see result payload")
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
