#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1C1 live probe v5: pin the design-pose distance-mate recipe.

Established by probes v2/v4 (this session, PID 87516):
  - all four guide coincident mates with alignment=1 hold BOTH fingers at the
    identity-rotation design pose (ty = +/-71.5 mm at OPEN);
  - production-order (palm first) positive-distance creates land the finger on
    the mirrored side (R: ty=-138.82, L: ty=+192.87);
  - negative Distance at create -> swAddMateError_ErrorUknown (0), no mate;
  - crossed alignment (distance mate whose align contradicts the true-normal
    relationship) -> OverDefinedAssembly (5).  Parallel normals need align=0,
    anti-parallel need align=1.

Probe v5 finds, per side, the variant that (a) returns error=1 AND (b) keeps the
finger at the DESIGN pose, then confirms it WITH the production limit arguments,
then exercises the per-configuration dimension drive OPEN->PREGRASP->CLOSED->OPEN
reading the finger translation at each state.

Variants per side: finger-first selection order, and Flip=True.

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
PREGRASP_TRAVEL_MM = float(m.STATES["PREGRASP"]["travel_mm"])
R_BASE_M = m.LIMIT_R_BASE_MM / 1000.0
L_BASE_M = m.LIMIT_L_BASE_MM / 1000.0
R_OPEN_M = (m.LIMIT_R_BASE_MM + OPEN_TRAVEL_MM) / 1000.0
L_OPEN_M = (m.LIMIT_L_BASE_MM + OPEN_TRAVEL_MM) / 1000.0
T0 = time.time()


def log(step: str) -> None:
    print(f"[{time.time() - T0:8.2f}s] {step}", flush=True)


def transform_array(component: Any, types: Any, pythoncom: Any) -> List[float]:
    raw = base.value(component, "Transform2")
    return [float(value) for value in base.as_list(base.value(raw, "ArrayData"))]


def pose_fact(data: List[float]) -> Dict[str, Any]:
    return {
        "translation_mm": [round(data[9] * 1000.0, 6), round(data[10] * 1000.0, 6), round(data[11] * 1000.0, 6)],
        "rotation_diag": [round(data[0], 9), round(data[4], 9), round(data[8], 9)],
    }


def main() -> int:
    result: Dict[str, Any] = {"schema": "V5_PROBE_LOOP1C1_DRIVE_V5", "cases": [], "drive_tests": [], "notes": []}
    sw = types = pythoncom = None
    try:
        log("attach: begin")
        sw, types, pythoncom, session = base.attach_empty_session()
        result["session"] = session
        log(f"attach: ok pid={session['pid']}")
        raw_model = sw.NewDocument(str(m.ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
        model = base.wrap(raw_model, "IModelDoc2", types, pythoncom)
        assembly = base.wrap(model, "IAssemblyDoc", types, pythoncom)
        log("new assembly document: ok")
        for role in ("PALM", "LEFT", "RIGHT"):
            spec = m.PARTS[role]
            translation = m.expected_translation_m(role, OPEN_TRAVEL_MM)
            m.insert_component(sw, model, assembly, role, Path(spec["path"]), bool(spec["fixed"]), translation, types, pythoncom)
            log(f"insert {role}: ok")
        components = m.assembly_components(model, assembly, types, pythoncom)

        # ---- guides: all four at alignment=1 (probe v4 confirmed identity poses) ----
        for side, prefix in (("LEFT", "L"), ("RIGHT", "R")):
            for guide in ("A", "B"):
                palm_face, _pf = m.guide_face(model, components["PALM"], "PALM", guide, types, pythoncom)
                finger_face, _ff = m.guide_face(model, components[side], side, guide, types, pythoncom)
                m.add_face_mate(model, assembly, palm_face, finger_face, 1, m.MATE_NAMES[f"{prefix}_{guide}"], types, pythoncom)
                log(f"guide {prefix}_{guide}: ok")
        snapshot = {role: transform_array(component, types, pythoncom) for role, component in components.items()}
        result["post_guide_poses"] = {role: pose_fact(snapshot[role]) for role in snapshot}
        log(f"post-guide poses: {json.dumps(result['post_guide_poses'])}")

        def select_pair(first: Any, second: Any) -> bool:
            model.ClearSelection2(True)
            manager = m.selection_manager(model, types, pythoncom)
            data = base.wrap(manager.CreateSelectData(), "ISelectData", types, pythoncom)
            data.Mark = 1
            ok_first = bool(first.Select4(False, data))
            ok_second = bool(second.Select4(True, data))
            return ok_first and ok_second

        def restore(role: str) -> bool:
            transform = m.make_transform(sw, snapshot[role], types, pythoncom)
            ok = bool(components[role].SetTransformAndSolve3(transform, True))
            model.EditRebuild3()
            return ok

        def delete_named(name: str) -> Any:
            try:
                ok = bool(model.Extension.SelectByID2(name, "MATE", 0, 0, 0, False, 0, None, 0))
                if ok:
                    model.EditDelete()
                    model.ClearSelection2(True)
                    model.EditRebuild3()
                return ok
            except Exception as exc:  # noqa: BLE001
                return repr(exc)

        def distance_case(side: str, role: str, label: str, align: int, flip: bool, dist_m: float, upper_m: float, lower_m: float, swap: bool) -> Dict[str, Any]:
            palm_ent, _pf = m.limit_face(model, components["PALM"], "PALM", side, "palm", types, pythoncom)
            finger_ent, _ff = m.limit_face(model, components[role], role, side, "finger", types, pythoncom)
            first, second = (finger_ent, palm_ent) if swap else (palm_ent, finger_ent)
            selected = select_pair(first, second)
            before_names = [str(base.value(feature, "Name")) for feature in m.mate_features(model, types, pythoncom)]
            returned = assembly.AddMate3(m.SW_MATE_DISTANCE, align, flip, dist_m, upper_m, lower_m, 0.0, 0.0, 0.0, 0.0, 0.0, False, 0)
            mate_raw, outs = base.unpack(returned)
            error = int(outs[0]) if outs else None
            model.ClearSelection2(True)
            row: Dict[str, Any] = {"label": label, "side": side, "align": align, "flip": flip, "swap": swap, "dist_m": dist_m, "upper_m": upper_m, "lower_m": lower_m, "selected": selected, "error": error, "mate_raw_is_none": mate_raw is None}
            log(f"case {label}: error={error}")
            if mate_raw is not None:
                feature = m.added_mate_feature(before_names, model, label, types, pythoncom)
                try:
                    data = m.distance_mate_data(feature, types, pythoncom)
                    row["stored_distance_mm"] = float(base.value(data, "Distance")) * 1000.0
                    row["stored_alignment"] = int(base.value(data, "MateAlignment"))
                    row["is_advanced"] = bool(base.value(data, "IsAdvancedMate"))
                except Exception as exc:  # noqa: BLE001
                    row["readback_exception"] = repr(exc)
                row["finger_pose_after"] = pose_fact(transform_array(components[role], types, pythoncom))
                row["feature_name"] = label
            else:
                row["restored"] = restore(role)
            return row

        def drive_test(side: str, role: str, feature: Any, law) -> Dict[str, Any]:
            dimension = m.mate_dimension(feature, types, pythoncom)
            rows = []
            for state, travel in (("OPEN", OPEN_TRAVEL_MM), ("PREGRASP", PREGRASP_TRAVEL_MM), ("CLOSED", 0.0), ("OPEN_AGAIN", OPEN_TRAVEL_MM)):
                target_m = law(travel)
                status = int(dimension.SetSystemValue3(target_m, 1, []))
                model.EditRebuild3()
                ty = transform_array(components[role], types, pythoncom)[10] * 1000.0
                readback = [float(v) for v in base.as_list(dimension.GetSystemValue3(1, []))]
                rows.append({"state": state, "target_mm": round(target_m * 1000.0, 6), "status": status, "readback_mm": [round(v * 1000.0, 6) for v in readback], "finger_ty_mm": round(ty, 6)})
                log(f"drive {side} {state}: target={rows[-1]['target_mm']} ty={rows[-1]['finger_ty_mm']}")
            return {"side": side, "rows": rows}

        winners: Dict[str, Dict[str, Any]] = {}
        # ---- R side: anti-parallel normals -> align=1; test swap and flip ----
        for label, swap, flip in (("R4_fingerfirst", True, False), ("R5_flip", False, True)):
            row = distance_case("R", "RIGHT", label, 1, flip, R_OPEN_M, 0.0, 0.0, swap)
            result["cases"].append(row)
            pose = row.get("finger_pose_after", {})
            if row.get("error") == 1 and pose and abs(pose["translation_mm"][1] - 71.5) < 0.5:
                winners["R"] = row
                break
            if row.get("feature_name"):
                delete_named(row["feature_name"])
                restore("RIGHT")
        # ---- L side: parallel normals -> align=0; test swap and flip ----
        for label, swap, flip in (("L4_fingerfirst", True, False), ("L5_flip", False, True)):
            row = distance_case("L", "LEFT", label, 0, flip, L_OPEN_M, 0.0, 0.0, swap)
            result["cases"].append(row)
            pose = row.get("finger_pose_after", {})
            if row.get("error") == 1 and pose and abs(pose["translation_mm"][1] + 71.5) < 0.5:
                winners["L"] = row
                break
            if row.get("feature_name"):
                delete_named(row["feature_name"])
                restore("LEFT")
        result["notes"].append(f"winners: {sorted(winners)}")

        # ---- confirm winners: convert the plain mate to an advanced limit in place
        # (exactly the production F1 path), read back raw values, drive states ----
        for side, role, open_m, base_m in (("R", "RIGHT", R_OPEN_M, R_BASE_M), ("L", "LEFT", L_OPEN_M, L_BASE_M)):
            win = winners.get(side)
            if not win:
                continue
            feature = None
            for f in m.mate_features(model, types, pythoncom):
                if str(base.value(f, "Name")) == win["feature_name"]:
                    feature = f
                    break
            if feature is None:
                continue
            stored_m = float(win["stored_distance_mm"]) / 1000.0
            sign = 1.0 if stored_m >= 0.0 else -1.0
            conv: Dict[str, Any] = {"side": side, "stored_distance_mm": win["stored_distance_mm"], "align": win["align"], "flip": win["flip"], "swap": win["swap"]}
            try:
                data = m.distance_mate_data(feature, types, pythoncom)
                data.IsAdvancedMate = True
                data.Distance = stored_m
                if sign > 0.0:
                    data.MinimumDistance = 0.0
                    data.MaximumDistance = open_m
                else:
                    data.MinimumDistance = -open_m
                    data.MaximumDistance = 0.0
                conv["modify_definition_ok"] = bool(feature.ModifyDefinition(data, model, None))
                conv["rebuild_ok"] = bool(model.ForceRebuild3(True))
                data2 = m.distance_mate_data(feature, types, pythoncom)
                conv["readback"] = {
                    "is_advanced": bool(base.value(data2, "IsAdvancedMate")),
                    "distance_mm": float(base.value(data2, "Distance")) * 1000.0,
                    "min_mm": float(base.value(data2, "MinimumDistance")) * 1000.0,
                    "max_mm": float(base.value(data2, "MaximumDistance")) * 1000.0,
                }
                conv["finger_pose_after_conversion"] = pose_fact(transform_array(components[role], types, pythoncom))
                law = lambda t, _b=base_m, _s=sign: _s * (_b + t / 1000.0)  # noqa: E731
                result["drive_tests"].append(drive_test(side, role, feature, law))
            except Exception as exc:  # noqa: BLE001
                conv["exception"] = repr(exc)
            result.setdefault("conversions", []).append(conv)
        result["verdict"] = "V5_PROBE_LOOP1C1_DRIVE_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1C1_DRIVE_FAIL"
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
