#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bisect the Loop1C1 guide-mate orientation branch (attach-only).

The previous probe proved that both fingers are solved into a 180-degree
rotated branch after the four guide coincident mates, so the RIGHT travel
limit cannot be added (AddMate3 error 5).  This script inserts the three
native parts once, then for each finger tries every (A alignment, B
alignment, A flip, B flip) combination, deleting all mates and resetting the
intended OPEN pose before each trial, and records which combination keeps
the finger in the intended identity-rotation branch.
"""

from __future__ import annotations

import json
import math
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

sys.dont_write_bytecode = True

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
TOOLS = RUN_ROOT / "99_tools"
sys.path.insert(0, str(TOOLS))

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base  # noqa: E402
import F3R2_V5_SESSION_BINDING as sbin  # noqa: E402
import F3R2_V5_NATIVE_LOOP1C1_GRIPPER_ASSEMBLY_ATTACH_ONLY as c1  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def component_transform(component: Any, types: Any, pythoncom: Any) -> List[float]:
    raw = base.value(component, "Transform2")
    return [float(value) for value in base.as_list(base.value(raw, "ArrayData"))]


def parse_transform(values: Sequence[float]) -> Dict[str, Any]:
    v = [float(value) for value in values]
    return {
        "rotation": [[v[0], v[1], v[2]], [v[3], v[4], v[5]], [v[6], v[7], v[8]]],
        "translation_mm": [v[9] * 1000.0, v[10] * 1000.0, v[11] * 1000.0],
    }


def identity_rotation_error(transform: Sequence[float]) -> float:
    v = [float(value) for value in transform]
    error = 0.0
    for row in range(3):
        for col in range(3):
            expected = 1.0 if row == col else 0.0
            error = max(error, abs(v[row * 3 + col] - expected))
    return error


def set_pose(sw: Any, component: Any, y_mm: float, types: Any, pythoncom: Any) -> bool:
    math_utility = base.wrap(base.value(sw, "GetMathUtility"), "IMathUtility", types, pythoncom)
    from win32com.client import VARIANT

    data = c1.transform_data((0.0, float(y_mm) / 1000.0, 0.0))
    transform = math_utility.CreateTransform(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, data))
    return bool(component.SetTransformAndSolve3(transform, True))


def delete_mates(model: Any, types: Any, pythoncom: Any) -> List[str]:
    removed: List[str] = []
    for feature in list(c1.mate_features(model, types, pythoncom)):
        name = str(base.value(feature, "Name"))
        try:
            feature.Delete()
            removed.append(name)
        except Exception as exc:
            removed.append(f"{name}:{exc!r}")
    return removed


def add_coincident(
    model: Any,
    assembly: Any,
    first: Any,
    second: Any,
    alignment: int,
    flip: bool,
    name: str,
    types: Any,
    pythoncom: Any,
) -> Dict[str, Any]:
    manager = c1.selection_manager(model, types, pythoncom)
    model.ClearSelection2(True)
    data = base.wrap(manager.CreateSelectData(), "ISelectData", types, pythoncom)
    data.Mark = 1
    first_ok = bool(first.Select4(False, data))
    second_ok = bool(second.Select4(True, data))
    selected = int(manager.GetSelectedObjectCount2(1))
    before = set(str(base.value(feature, "Name")) for feature in c1.mate_features(model, types, pythoncom))
    returned = assembly.AddMate3(c1.SW_MATE_COINCIDENT, alignment, flip, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False, 0)
    mate_raw, outs = base.unpack(returned)
    error = int(outs[0]) if outs else -1
    model.ClearSelection2(True)
    row = {
        "name": name,
        "alignment": alignment,
        "flip": flip,
        "first_selected": first_ok,
        "second_selected": second_ok,
        "selected": selected,
        "error": error,
        "mate_raw_is_none": mate_raw is None,
    }
    if mate_raw is not None and error == c1.SW_ADD_MATE_NO_ERROR:
        additions = [feature for feature in c1.mate_features(model, types, pythoncom) if str(base.value(feature, "Name")) not in before]
        if additions:
            try:
                additions[0].Name = name
            except Exception:
                pass
    return row


def trial_guides(
    sw: Any,
    model: Any,
    assembly: Any,
    components: Dict[str, Any],
    side: str,
    prefix: str,
    a_align: int,
    b_align: int,
    a_flip: bool,
    b_flip: bool,
    types: Any,
    pythoncom: Any,
) -> Dict[str, Any]:
    delete_mates(model, types, pythoncom)
    for role, y in (("LEFT", -71.5), ("RIGHT", 71.5)):
        set_pose(sw, components[role], y, types, pythoncom)
    guide_a_face, _a_fact = c1.guide_face(model, components["PALM"], "PALM", "A", types, pythoncom)
    guide_b_face, _b_fact = c1.guide_face(model, components["PALM"], "PALM", "B", types, pythoncom)
    finger_a_face, _fa_fact = c1.guide_face(model, components[side], side, "A", types, pythoncom)
    finger_b_face, _fb_fact = c1.guide_face(model, components[side], side, "B", types, pythoncom)
    a_row = add_coincident(model, assembly, guide_a_face, finger_a_face, a_align, a_flip, f"{prefix}_A_TEST", types, pythoncom)
    b_row = add_coincident(model, assembly, guide_b_face, finger_b_face, b_align, b_flip, f"{prefix}_B_TEST", types, pythoncom)
    transform = component_transform(components[side], types, pythoncom)
    parsed = parse_transform(transform)
    return {
        "side": side,
        "a": a_row,
        "b": b_row,
        "transform": transform,
        "rotation_error": identity_rotation_error(transform),
        "translation_mm": parsed["translation_mm"],
        "orientation_identity": identity_rotation_error(transform) < 2.0e-4,
    }


def main() -> int:
    started = utc_now()
    sw = types = pythoncom = None
    result: Dict[str, Any] = {"schema": "F3R2_V5_DIAG_GUIDE_ALIGNMENT_HUNT_V1", "timestamp_utc": started}
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
        for role in ("PALM", "LEFT", "RIGHT"):
            spec = c1.PARTS[role]
            translation = c1.expected_translation_m(role, float(c1.STATES["OPEN"]["travel_mm"]))
            component = c1.insert_component(sw, model, assembly, role, Path(spec["path"]), bool(spec["fixed"]), translation, types, pythoncom)
            components[role] = component
        components = c1.assembly_components(model, assembly, types, pythoncom)

        trials: List[Dict[str, Any]] = []
        for side, prefix in (("LEFT", "L"), ("RIGHT", "R")):
            for a_align in (0, 1):
                for b_align in (0, 1):
                    for a_flip in (False, True):
                        for b_flip in (False, True):
                            row = trial_guides(
                                sw, model, assembly, components,
                                side, prefix, a_align, b_align, a_flip, b_flip,
                                types, pythoncom,
                            )
                            row["combo"] = {"a_align": a_align, "b_align": b_align, "a_flip": a_flip, "b_flip": b_flip}
                            trials.append(row)

        # Summarise only the working combinations (both mates added, identity orientation).
        result["trials"] = trials
        result["working_combinations"] = [
            {
                "side": row["side"],
                "combo": row["combo"],
                "a_error": row["a"]["error"],
                "b_error": row["b"]["error"],
                "rotation_error": row["rotation_error"],
                "translation_mm": row["translation_mm"],
            }
            for row in trials
            if row["a"]["error"] == c1.SW_ADD_MATE_NO_ERROR
            and row["b"]["error"] == c1.SW_ADD_MATE_NO_ERROR
            and row["orientation_identity"]
        ]

        result["cleanup"] = close_owned(sw)
        result["verdict"] = "V5_DIAG_GUIDE_ALIGNMENT_HUNT_COMPLETE"
        out = RUN_ROOT / "13_validation/V5_DIAG_GUIDE_ALIGNMENT_HUNT.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"verdict": result["verdict"], "out": str(out), "working": len(result["working_combinations"])}, ensure_ascii=False))
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
        out = RUN_ROOT / "13_validation/V5_DIAG_GUIDE_ALIGNMENT_HUNT.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"verdict": "V5_DIAG_GUIDE_ALIGNMENT_HUNT_FAIL", "message": str(exc)}, ensure_ascii=False))
        return 2
    finally:
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
