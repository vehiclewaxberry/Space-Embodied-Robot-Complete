#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnostic probe for the Loop1C1 RIGHT travel-limit mate (attach-only).

Builds the same three-component gripper assembly, adds the four guide
coincident mates and the LEFT limit mate, then inspects:
  * the live RIGHT/LEFT component transforms;
  * the world positions of the two RIGHT limit faces;
  * whether the RIGHT finger Y DOF is free (SetTransformAndSolve3 round trip);
  * AddMate3 outcomes for the RIGHT distance mate under ALIGNED / ANTI and
    advanced / regular distance semantics.
The script only attaches to the qualified empty Session B, never starts or
stops SolidWorks, and closes every document it opens.
"""

from __future__ import annotations

import json
import math
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

sys.dont_write_bytecode = True

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
TOOLS = RUN_ROOT / "99_tools"
sys.path.insert(0, str(TOOLS))

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base  # noqa: E402
import F3R2_V5_SESSION_BINDING as sbin  # noqa: E402
import F3R2_V5_NATIVE_LOOP1C1_GRIPPER_ASSEMBLY_ATTACH_ONLY as c1  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def transform_parts(tf: Sequence[float]) -> Dict[str, Any]:
    values = [float(value) for value in tf]
    rotation = [
        [values[0], values[1], values[2]],
        [values[3], values[4], values[5]],
        [values[6], values[7], values[8]],
    ]
    translation = [values[9], values[10], values[11]]
    return {"rotation": rotation, "translation": translation, "array": values}


def apply_transform(tf: Sequence[float], point: Sequence[float]) -> List[float]:
    values = [float(value) for value in tf]
    return [
        values[0] * point[0] + values[1] * point[1] + values[2] * point[2] + values[9],
        values[3] * point[0] + values[4] * point[1] + values[5] * point[2] + values[10],
        values[6] * point[0] + values[7] * point[1] + values[8] * point[2] + values[11],
    ]


def rotate_only(tf: Sequence[float], vector: Sequence[float]) -> List[float]:
    values = [float(value) for value in tf]
    return [
        values[0] * vector[0] + values[1] * vector[1] + values[2] * vector[2],
        values[3] * vector[0] + values[4] * vector[1] + values[5] * vector[2],
        values[6] * vector[0] + values[7] * vector[1] + values[8] * vector[2],
    ]


def norm(vector: Sequence[float]) -> float:
    return math.sqrt(sum(float(value) ** 2 for value in vector))


def world_plane(face_fact: Dict[str, Any], tf: Sequence[float]) -> Dict[str, Any]:
    local_normal = [float(value) for value in face_fact["normal"]]
    local_point = [float(value) for value in face_fact["point_mm"]]
    world_normal = rotate_only(tf, local_normal)
    nlen = norm(world_normal)
    world_normal = [value / nlen for value in world_normal]
    world_point = apply_transform(tf, local_point)
    offset = sum(world_normal[index] * world_point[index] for index in range(3))
    return {
        "world_normal": world_normal,
        "world_point_mm": world_point,
        "world_offset_mm": offset,
        "local_normal": local_normal,
        "local_point_mm": local_point,
    }


def component_transform(component: Any, types: Any, pythoncom: Any) -> List[float]:
    raw = base.value(component, "Transform2")
    return [float(value) for value in base.as_list(base.value(raw, "ArrayData"))]


def close_owned(sw: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for _pass in range(4):
        documents = base.as_list(base.value(sw, "GetDocuments"))
        if not documents:
            break
        titles = []
        for raw in documents:
            try:
                titles.append(str(base.value(raw, "GetTitle")))
            except Exception:
                continue
        for title in reversed(list(dict.fromkeys(titles))):
            try:
                sw.CloseDoc(title)
                rows.append({"title": title, "closed": True})
            except Exception as exc:
                rows.append({"title": title, "closed": False, "exception": repr(exc)})
    return rows


def assembly_mate_names(model: Any, types: Any, pythoncom: Any) -> List[str]:
    return [str(base.value(feature, "Name")) for feature in c1.mate_features(model, types, pythoncom)]


def main() -> int:
    started = utc_now()
    sw = types = pythoncom = None
    result: Dict[str, Any] = {"schema": "F3R2_V5_DIAG_LOOP1C1_R_LIMIT_PROBE_V1", "timestamp_utc": started}
    try:
        sw, types, pythoncom, session = base.attach_empty_session()
        expected_pid = int(sbin.resolve_pid(87_516))
        if int(session["pid"]) != expected_pid:
            raise RuntimeError(f"session pid {session['pid']} != registered {expected_pid}")
        result["session"] = session

        raw_model = sw.NewDocument(str(c1.ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
        if raw_model is None:
            raise RuntimeError("NewDocument returned null")
        model = base.wrap(raw_model, "IModelDoc2", types, pythoncom)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
        components: Dict[str, Any] = {}
        insert_rows: List[Dict[str, Any]] = []
        for role in ("PALM", "LEFT", "RIGHT"):
            spec = c1.PARTS[role]
            translation = c1.expected_translation_m(role, float(c1.STATES["OPEN"]["travel_mm"]))
            component = c1.insert_component(sw, model, assembly, role, Path(spec["path"]), bool(spec["fixed"]), translation, types, pythoncom)
            components[role] = component
            insert_rows.append({
                "role": role,
                "name2": str(base.value(component, "Name2")),
                "initial_open_translation_m": list(translation),
            })
        components = c1.assembly_components(model, assembly, types, pythoncom)

        created: Dict[str, Any] = {}
        for side, prefix in (("LEFT", "L"), ("RIGHT", "R")):
            for guide in ("A", "B"):
                palm_face, palm_fact = c1.guide_face(model, components["PALM"], "PALM", guide, types, pythoncom)
                finger_face, finger_fact = c1.guide_face(model, components[side], side, guide, types, pythoncom)
                name = c1.MATE_NAMES[f"{prefix}_{guide}"]
                alignment = int(c1.GUIDE_CONTRACTS[guide][f"{side}_alignment"])
                created[name] = c1.add_face_mate(model, assembly, palm_face, finger_face, alignment, name, types, pythoncom)
                result.setdefault("guides", []).append({
                    "mate": name, "alignment": alignment,
                    "palm_local_offset_mm": palm_fact["offset_mm"], "finger_local_offset_mm": finger_fact["offset_mm"],
                })
        limit_name = c1.MATE_NAMES["L_LIMIT"]
        limit_alignment = int(c1.LIMIT_CONTRACTS["L"]["alignment"])
        created[limit_name] = c1.add_advanced_limit_distance(model, assembly, components["PALM"], components["LEFT"], limit_name, "L", limit_alignment, types, pythoncom)["feature"]

        result["components_after_guides_and_l_limit"] = {
            role: {
                "name2": str(base.value(component, "Name2")),
                "transform": component_transform(component, types, pythoncom),
                "transform_parsed": transform_parts(component_transform(component, types, pythoncom)),
            }
            for role, component in components.items()
        }

        # World geometry of the two RIGHT limit faces.
        right_tf = component_transform(components["RIGHT"], types, pythoncom)
        palm_tf = component_transform(components["PALM"], types, pythoncom)
        _palm_entity, palm_fact = c1.limit_face(model, components["PALM"], "PALM", "R", "palm", types, pythoncom)
        _finger_entity, finger_fact = c1.limit_face(model, components["RIGHT"], "RIGHT", "R", "finger", types, pythoncom)
        palm_world = world_plane(palm_fact, palm_tf)
        finger_world = world_plane(finger_fact, right_tf)
        dot = sum(palm_world["world_normal"][i] * finger_world["world_normal"][i] for i in range(3))
        finger_world["world_normal"] = [finger_world["world_normal"][i] * (1.0 if dot >= 0 else -1.0) for i in range(3)]
        finger_world["flipped_to_palm_sense"] = dot < 0
        finger_world["world_offset_mm"] = sum(finger_world["world_normal"][i] * finger_world["world_point_mm"][i] for i in range(3))
        result["right_limit_world_geometry"] = {
            "palm": palm_world,
            "finger": finger_world,
            "signed_distance_mm": palm_world["world_offset_mm"] - finger_world["world_offset_mm"],
            "nominal_open_mm": float(c1.LIMIT_R_BASE_MM) + float(c1.STATES["OPEN"]["travel_mm"]),
            "base_mm": float(c1.LIMIT_R_BASE_MM),
        }

        # Y-freedom check: translate RIGHT to CLOSED (t=0) and back to OPEN.
        math_utility = base.wrap(base.value(sw, "GetMathUtility"), "IMathUtility", types, pythoncom)
        from win32com.client import VARIANT

        def move_component_y(component: Any, y_mm: float, label: str) -> Dict[str, Any]:
            translation = (0.0, float(y_mm) / 1000.0, 0.0)
            data = c1.transform_data(translation)
            transform = math_utility.CreateTransform(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, data))
            ok = bool(component.SetTransformAndSolve3(transform, True))
            readback = component_transform(component, types, pythoncom)
            return {"label": label, "set_ok": ok, "readback": readback, "readback_parsed": transform_parts(readback)}

        result["y_freedom"] = [
            move_component_y(components["RIGHT"], 0.0, "RIGHT_TO_CLOSED"),
            move_component_y(components["RIGHT"], 71.5, "RIGHT_BACK_TO_OPEN"),
        ]

        # Attempt RIGHT limit AddMate3 variants.  Each failed attempt is
        # cleaned up so the next variant starts from the same base state.
        attempts: List[Dict[str, Any]] = []
        for alignment in (1, 0):
            for advanced in (True, False):
                before_names = assembly_mate_names(model, types, pythoncom)
                model.ClearSelection2(True)
                manager = base.wrap(base.value(model, "SelectionManager"), "ISelectionMgr", types, pythoncom)
                select_data = base.wrap(manager.CreateSelectData(), "ISelectData", types, pythoncom)
                select_data.Mark = 1
                palm_selected = bool(_palm_entity.Select4(False, select_data))
                finger_selected = bool(_finger_entity.Select4(True, select_data))
                selected = int(manager.GetSelectedObjectCount2(1))
                max_m = (float(c1.LIMIT_R_BASE_MM) + 71.5) / 1000.0 if advanced else 0.0
                dist_m = max_m
                returned = assembly.AddMate3(
                    c1.SW_MATE_DISTANCE, alignment, False,
                    dist_m, max_m, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False, 0,
                )
                mate_raw, outs = base.unpack(returned)
                error = int(outs[0]) if outs else -1
                after_names = assembly_mate_names(model, types, pythoncom)
                additions = [name for name in after_names if name not in set(before_names)]
                row = {
                    "alignment": alignment,
                    "advanced": advanced,
                    "dist_m": dist_m,
                    "max_m": max_m,
                    "palm_selected": palm_selected,
                    "finger_selected": finger_selected,
                    "selected": selected,
                    "error": error,
                    "mate_raw_is_none": mate_raw is None,
                    "new_mate_names": additions,
                }
                # Clean up any feature the failed call may have created.
                if additions:
                    model.ClearSelection2(True)
                    for feature in c1.mate_features(model, types, pythoncom):
                        if str(base.value(feature, "Name")) in additions:
                            try:
                                feature.Select2(False, 0)
                                model.EditDelete()
                            except Exception as exc:
                                row["cleanup_exception"] = repr(exc)
                model.ClearSelection2(True)
                attempts.append(row)
                if error == c1.SW_ADD_MATE_NO_ERROR and mate_raw is not None:
                    break
        result["right_limit_attempts"] = attempts

        result["cleanup"] = close_owned(sw)
        result["verdict"] = "V5_DIAG_LOOP1C1_R_LIMIT_PROBE_COMPLETE"
        out = RUN_ROOT / "13_validation/V5_DIAG_LOOP1C1_R_LIMIT_PROBE.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"verdict": result["verdict"], "out": str(out)}, ensure_ascii=False))
        return 0
    except Exception as exc:
        result["code"] = "UNHANDLED_EXCEPTION"
        result["message"] = str(exc)
        result["traceback"] = traceback.format_exc()
        if sw is not None:
            try:
                result["cleanup"] = close_owned(sw)
            except Exception as cleanup_exc:
                result["cleanup_exception"] = repr(cleanup_exc)
        out = RUN_ROOT / "13_validation/V5_DIAG_LOOP1C1_R_LIMIT_PROBE.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"verdict": "V5_DIAG_LOOP1C1_R_LIMIT_PROBE_FAIL", "message": str(exc)}, ensure_ascii=False))
        return 2
    finally:
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
