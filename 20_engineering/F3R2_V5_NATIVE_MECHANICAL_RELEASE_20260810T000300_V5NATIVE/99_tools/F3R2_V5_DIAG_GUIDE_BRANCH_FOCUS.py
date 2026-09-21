#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused branch test for the two guide coincident mates (attach-only).

Tests a small set of mate-construction strategies per finger in one
assembly, with rigorous cleanup of failed mate features between trials:
  1. Guide A first, then Guide B (baseline, current order);
  2. Guide B first, then Guide A;
  3. Guide A first, nudge the finger back to the intended identity pose,
     then Guide B;
  4. Guide B first, nudge, then Guide A.
The intended branch is identity rotation at the OPEN translation.
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence

sys.dont_write_bytecode = True

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
TOOLS = RUN_ROOT / "99_tools"
sys.path.insert(0, str(TOOLS))

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base  # noqa: E402
import F3R2_V5_SESSION_BINDING as sbin  # noqa: E402
import F3R2_V5_NATIVE_LOOP1C1_GRIPPER_ASSEMBLY_ATTACH_ONLY as c1  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def progress(text: str) -> None:
    print(text, flush=True)


def append_progress(row: Dict[str, Any]) -> None:
    path = RUN_ROOT / "13_validation/V5_DIAG_GUIDE_BRANCH_FOCUS_PROGRESS.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


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


def identity_rotation_error(transform: Sequence[float]) -> float:
    v = [float(value) for value in transform]
    error = 0.0
    for row in range(3):
        for col in range(3):
            expected = 1.0 if row == col else 0.0
            error = max(error, abs(v[row * 3 + col] - expected))
    return error


def set_pose(sw: Any, component: Any, y_mm: float, types: Any, pythoncom: Any) -> Dict[str, Any]:
    math_utility = base.wrap(base.value(sw, "GetMathUtility"), "IMathUtility", types, pythoncom)
    from win32com.client import VARIANT

    data = c1.transform_data((0.0, float(y_mm) / 1000.0, 0.0))
    transform = math_utility.CreateTransform(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, data))
    ok = bool(component.SetTransformAndSolve3(transform, True))
    readback = component_transform(component, types, pythoncom)
    return {"set_ok": ok, "readback": readback}


def delete_all_mates(model: Any, types: Any, pythoncom: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for _pass in range(6):
        features = list(c1.mate_features(model, types, pythoncom))
        if not features:
            break
        for feature in features:
            name = str(base.value(feature, "Name"))
            try:
                model.ClearSelection2(True)
                selected = bool(feature.Select2(False, 0))
                if selected:
                    model.EditDelete()
                    rows.append({"name": name, "deleted": True})
                else:
                    rows.append({"name": name, "deleted": False, "select_ok": False})
            except Exception as exc:
                rows.append({"name": name, "deleted": False, "exception": repr(exc)})
    remaining = [str(base.value(feature, "Name")) for feature in c1.mate_features(model, types, pythoncom)]
    if remaining:
        raise RuntimeError(f"mates remain after cleanup: {remaining}")
    return rows


def add_coincident_raw(
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
    if error == c1.SW_ADD_MATE_NO_ERROR:
        additions = [feature for feature in c1.mate_features(model, types, pythoncom) if str(base.value(feature, "Name")) not in before]
        if additions:
            try:
                additions[0].Name = name
            except Exception:
                pass
        row["feature_added"] = True
    elif mate_raw is not None:
        # Remove the errored mate feature immediately to keep state clean.
        try:
            feature = base.wrap(mate_raw, "IFeature", types, pythoncom)
            model.ClearSelection2(True)
            selected = bool(feature.Select2(False, 0))
            if selected:
                model.EditDelete()
                row["errored_feature_deleted"] = True
            else:
                row["errored_feature_deleted"] = False
                row["delete_select_ok"] = False
        except Exception as exc:
            row["errored_feature_deleted"] = False
            row["delete_exception"] = repr(exc)
    return row


def guides(
    model: Any,
    components: Dict[str, Any],
    side: str,
    types: Any,
    pythoncom: Any,
) -> Dict[str, Any]:
    palm_a, _ = c1.guide_face(model, components["PALM"], "PALM", "A", types, pythoncom)
    palm_b, _ = c1.guide_face(model, components["PALM"], "PALM", "B", types, pythoncom)
    finger_a, _ = c1.guide_face(model, components[side], side, "A", types, pythoncom)
    finger_b, _ = c1.guide_face(model, components[side], side, "B", types, pythoncom)
    a_align = int(c1.GUIDE_CONTRACTS["A"][f"{side}_alignment"])
    b_align = int(c1.GUIDE_CONTRACTS["B"][f"{side}_alignment"])
    return {
        "palm_a": palm_a,
        "palm_b": palm_b,
        "finger_a": finger_a,
        "finger_b": finger_b,
        "a_align": a_align,
        "b_align": b_align,
    }


def trial(
    sw: Any,
    model: Any,
    assembly: Any,
    components: Dict[str, Any],
    side: str,
    prefix: str,
    strategy: str,
    types: Any,
    pythoncom: Any,
) -> Dict[str, Any]:
    delete_all_mates(model, types, pythoncom)
    expected_y = -71.5 if side == "LEFT" else 71.5
    set_pose(sw, components[side], expected_y, types, pythoncom)
    g = guides(model, components, side, types, pythoncom)
    rows: List[Dict[str, Any]] = []
    nudge: Dict[str, Any] = {}

    def add_a() -> Dict[str, Any]:
        return add_coincident_raw(model, assembly, g["palm_a"], g["finger_a"], g["a_align"], False, f"{prefix}_A_{strategy}", types, pythoncom)

    def add_b() -> Dict[str, Any]:
        return add_coincident_raw(model, assembly, g["palm_b"], g["finger_b"], g["b_align"], False, f"{prefix}_B_{strategy}", types, pythoncom)

    if strategy == "A_THEN_B":
        rows.append(add_a())
        rows.append(add_b())
    elif strategy == "B_THEN_A":
        rows.append(add_b())
        rows.append(add_a())
    elif strategy == "A_NUDGE_B":
        rows.append(add_a())
        nudge = set_pose(sw, components[side], expected_y, types, pythoncom)
        rows.append(add_b())
    elif strategy == "B_NUDGE_A":
        rows.append(add_b())
        nudge = set_pose(sw, components[side], expected_y, types, pythoncom)
        rows.append(add_a())
    else:
        raise RuntimeError(f"unknown strategy {strategy}")
    transform = component_transform(components[side], types, pythoncom)
    return {
        "side": side,
        "strategy": strategy,
        "rows": rows,
        "nudge": nudge,
        "transform": transform,
        "rotation_error": identity_rotation_error(transform),
        "translation_mm": [transform[9] * 1000.0, transform[10] * 1000.0, transform[11] * 1000.0],
        "orientation_identity": identity_rotation_error(transform) < 2.0e-4,
    }


def run_finger(sw: Any, side: str, prefix: str, types: Any, pythoncom: Any) -> Dict[str, Any]:
    raw_model = sw.NewDocument(str(c1.ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
    if raw_model is None:
        raise RuntimeError("NewDocument returned null")
    model = base.wrap(raw_model, "IModelDoc2", types, pythoncom)
    assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
    components: Dict[str, Any] = {}
    for role in ("PALM", side):
        spec = c1.PARTS[role]
        translation = c1.expected_translation_m(role, float(c1.STATES["OPEN"]["travel_mm"]))
        component = c1.insert_component(sw, model, assembly, role, Path(spec["path"]), bool(spec["fixed"]), translation, types, pythoncom)
        components[role] = component
    strategies = ["A_THEN_B", "B_THEN_A", "A_NUDGE_B", "B_NUDGE_A"]
    rows = []
    for strategy in strategies:
        progress(f"{side} {strategy}")
        row = trial(sw, model, assembly, components, side, prefix, strategy, types, pythoncom)
        rows.append(row)
        append_progress({"side": side, "strategy": strategy, "rotation_error": row["rotation_error"], "translation_mm": row["translation_mm"], "rows": row["rows"]})
    close_owned(sw)
    return rows


def main() -> int:
    started = utc_now()
    sw = types = pythoncom = None
    result: Dict[str, Any] = {"schema": "F3R2_V5_DIAG_GUIDE_BRANCH_FOCUS_V1", "timestamp_utc": started}
    try:
        sw, types, pythoncom, session = base.attach_empty_session()
        expected_pid = int(sbin.resolve_pid(87_516))
        if int(session["pid"]) != expected_pid:
            raise RuntimeError(f"session pid {session['pid']} != registered {expected_pid}")
        result["session"] = session
        result["LEFT"] = run_finger(sw, "LEFT", "L", types, pythoncom)
        result["RIGHT"] = run_finger(sw, "RIGHT", "R", types, pythoncom)
        result["working"] = {
            "LEFT": [row for row in result["LEFT"] if row["orientation_identity"] and all(r["error"] == c1.SW_ADD_MATE_NO_ERROR for r in row["rows"])],
            "RIGHT": [row for row in result["RIGHT"] if row["orientation_identity"] and all(r["error"] == c1.SW_ADD_MATE_NO_ERROR for r in row["rows"])],
        }
        result["cleanup"] = close_owned(sw)
        result["verdict"] = "V5_DIAG_GUIDE_BRANCH_FOCUS_COMPLETE"
        out = RUN_ROOT / "13_validation/V5_DIAG_GUIDE_BRANCH_FOCUS.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        progress(json.dumps({
            "verdict": result["verdict"],
            "left_working": [r["strategy"] for r in result["working"]["LEFT"]],
            "right_working": [r["strategy"] for r in result["working"]["RIGHT"]],
            "out": str(out),
        }, ensure_ascii=False))
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
        out = RUN_ROOT / "13_validation/V5_DIAG_GUIDE_BRANCH_FOCUS.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        progress(json.dumps({"verdict": "V5_DIAG_GUIDE_BRANCH_FOCUS_FAIL", "message": str(exc)}, ensure_ascii=False))
        return 2
    finally:
        if pythoncom is not None:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
