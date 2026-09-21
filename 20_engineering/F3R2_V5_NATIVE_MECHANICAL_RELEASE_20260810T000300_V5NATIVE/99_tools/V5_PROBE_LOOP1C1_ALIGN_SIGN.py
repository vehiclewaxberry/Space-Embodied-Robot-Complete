#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""V5 Loop1C1 live probe v3: identity-preserving guide alignments + signed
distance-mate conventions for both travel limits.

Root-cause chain established by probe v2 (V5_PROBE_LOOP1C1_R_LIMIT_MATRIX):
  - R_GUIDE_A coincident (align=0) rotated the RIGHT finger 180 deg about Z,
    flipping its limit-face normal parallel to the palm's; the R limit distance
    mate's align=1 then contradicted the locked rotations -> OverDefinedAssembly(5).
  - LEFT rotated 180 deg about Y (keeps +Y normals), so the L align=0 limit mate
    stayed consistent and passed.
  - align=0 distance mates succeed; align=1 over-defines IN THE ROTATED STATE.

Probe v3 measures, in one run:
  1. TRUE face normals (PlaneParams) for all guide and limit faces at the
     design (identity-rotation) pose.
  2. Guide coincident alignment that preserves identity rotation
     (hypothesis: parallel true normals -> align=1 keeps zero-motion).
  3. Post-guide component poses (must be identity rotation, ty = +/-71.5 mm).
  4. For each side: plain distance mate create with align in {original, alt},
     reading back the stored signed Distance and the resulting finger pose, to
     pin the signed-distance law dim(t) and the correct alignment.
  5. The winner variant re-created WITH production limit arguments to confirm
     error=1 end to end.

Never saves, never writes receipts, leaves the session document-empty.
Flushed step logging localizes any hang. Result JSON on stdout.
"""

from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import F3R2_V5_NATIVE_LOOP1_IMPORT_ATTACH_ONLY as base  # noqa: E402
import F3R2_V5_NATIVE_LOOP1C1_GRIPPER_ASSEMBLY_ATTACH_ONLY as m  # noqa: E402

OPEN_TRAVEL_MM = float(m.STATES["OPEN"]["travel_mm"])
R_OPEN_M = (m.LIMIT_R_BASE_MM + OPEN_TRAVEL_MM) / 1000.0
R_MAX_M = float(m.LIMIT_MAX_MM["R"]) / 1000.0
L_OPEN_M = (m.LIMIT_L_BASE_MM + OPEN_TRAVEL_MM) / 1000.0
L_MAX_M = float(m.LIMIT_MAX_MM["L"]) / 1000.0
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


def true_normal(entity: Any, types: Any, pythoncom: Any) -> List[float]:
    face = base.wrap(entity, "IFace2", types, pythoncom)
    surface = base.wrap(base.value(face, "GetSurface"), "ISurface", types, pythoncom)
    params = [float(value) for value in base.as_list(base.value(surface, "PlaneParams"))]
    return [round(params[0], 9), round(params[1], 9), round(params[2], 9)]


def dot3(a: List[float], b: List[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def main() -> int:
    result: Dict[str, Any] = {"schema": "V5_PROBE_LOOP1C1_ALIGN_SIGN_V4", "guides": [], "distance_cases": [], "notes": []}
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

        # ---- phase 1+2: guides with identity-preserving alignment ----
        for side, prefix in (("LEFT", "L"), ("RIGHT", "R")):
            for guide in ("A", "B"):
                palm_face, palm_fact = m.guide_face(model, components["PALM"], "PALM", guide, types, pythoncom)
                finger_face, finger_fact = m.guide_face(model, components[side], side, guide, types, pythoncom)
                palm_n = true_normal(palm_face, types, pythoncom)
                finger_n = true_normal(finger_face, types, pythoncom)
                alignment = 1
                name = m.MATE_NAMES[f"{prefix}_{guide}"]
                m.add_face_mate(model, assembly, palm_face, finger_face, alignment, name, types, pythoncom)
                row = {
                    "mate": name,
                    "palm_true_normal": palm_n,
                    "finger_true_normal": finger_n,
                    "chosen_alignment": alignment,
                    "production_alignment": int(m.GUIDE_CONTRACTS[guide][f"{side}_alignment"]),
                }
                result["guides"].append(row)
                log(f"guide {name}: align={alignment} (production {row['production_alignment']}) ok")
        snapshot = {role: transform_array(component, types, pythoncom) for role, component in components.items()}
        result["post_guide_poses"] = {role: pose_fact(snapshot[role]) for role in snapshot}
        log(f"post-guide poses: {json.dumps(result['post_guide_poses'])}")

        def is_identity(role: str, expected_ty_mm: float) -> bool:
            data = transform_array(components[role], types, pythoncom)
            diag_ok = all(abs(data[index] - 1.0) < 1.0e-6 for index in (0, 4, 8))
            off_ok = all(abs(data[index]) < 1.0e-6 for index in (1, 2, 3, 5, 6, 7))
            return diag_ok and off_ok and abs(data[10] * 1000.0 - expected_ty_mm) < 0.5

        # ---- phase 2b: RIGHT branch fallback: (1,1) -> (0,0) -> pose-pin ----
        result["right_branch_attempts"] = []
        if not is_identity("RIGHT", 71.5):
            for combo in ((0, 0),):
                for guide in ("A", "B"):
                    name = m.MATE_NAMES[f"R_{guide}"]
                    deleted = bool(model.Extension.SelectByID2(name, "MATE", 0, 0, 0, False, 0, None, 0))
                    if deleted:
                        model.EditDelete()
                        model.ClearSelection2(True)
                model.EditRebuild3()
                # restore design pose before re-mating so the solver starts on the identity branch
                pin = m.make_transform(sw, m.transform_data(m.expected_translation_m("RIGHT", OPEN_TRAVEL_MM)), types, pythoncom)
                components["RIGHT"].SetTransformAndSolve3(pin, True)
                model.EditRebuild3()
                for guide, align in (("A", combo[0]), ("B", combo[1])):
                    palm_face, _pf = m.guide_face(model, components["PALM"], "PALM", guide, types, pythoncom)
                    finger_face, _ff = m.guide_face(model, components["RIGHT"], "RIGHT", guide, types, pythoncom)
                    m.add_face_mate(model, assembly, palm_face, finger_face, align, m.MATE_NAMES[f"R_{guide}"], types, pythoncom)
                pose_now = pose_fact(transform_array(components["RIGHT"], types, pythoncom))
                result["right_branch_attempts"].append({"combo": list(combo), "pose": pose_now})
                log(f"RIGHT guide combo {combo}: pose={json.dumps(pose_now)}")
                if is_identity("RIGHT", 71.5):
                    break
            if not is_identity("RIGHT", 71.5):
                pin = m.make_transform(sw, m.transform_data(m.expected_translation_m("RIGHT", OPEN_TRAVEL_MM)), types, pythoncom)
                components["RIGHT"].SetTransformAndSolve3(pin, True)
                model.EditRebuild3()
                pose_now = pose_fact(transform_array(components["RIGHT"], types, pythoncom))
                result["right_branch_attempts"].append({"combo": "pose_pin", "pose": pose_now})
                log(f"RIGHT pose-pin: pose={json.dumps(pose_now)}")
        snapshot = {role: transform_array(component, types, pythoncom) for role, component in components.items()}
        result["poses_for_distance_tests"] = {role: pose_fact(snapshot[role]) for role in snapshot}

        # ---- phase 3: true normals of limit faces (identity pose) ----
        limit_normals: Dict[str, Any] = {}
        for side, role in (("L", "LEFT"), ("R", "RIGHT")):
            palm_ent, _pf = m.limit_face(model, components["PALM"], "PALM", side, "palm", types, pythoncom)
            finger_ent, _ff = m.limit_face(model, components[role], role, side, "finger", types, pythoncom)
            limit_normals[side] = {
                "palm_true_normal": true_normal(palm_ent, types, pythoncom),
                "finger_true_normal": true_normal(finger_ent, types, pythoncom),
            }
        result["limit_face_true_normals"] = limit_normals
        log(f"limit true normals: {json.dumps(limit_normals)}")

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

        def distance_case(side: str, role: str, label: str, align: int, dist_m: float, upper_m: float, lower_m: float) -> Dict[str, Any]:
            palm_ent, _pf = m.limit_face(model, components["PALM"], "PALM", side, "palm", types, pythoncom)
            finger_ent, _ff = m.limit_face(model, components[role], role, side, "finger", types, pythoncom)
            selected = select_pair(palm_ent, finger_ent)
            before_names = [str(base.value(feature, "Name")) for feature in m.mate_features(model, types, pythoncom)]
            returned = assembly.AddMate3(m.SW_MATE_DISTANCE, align, False, dist_m, upper_m, lower_m, 0.0, 0.0, 0.0, 0.0, 0.0, False, 0)
            mate_raw, outs = base.unpack(returned)
            error = int(outs[0]) if outs else None
            model.ClearSelection2(True)
            row: Dict[str, Any] = {"label": label, "side": side, "align": align, "dist_m": dist_m, "upper_m": upper_m, "lower_m": lower_m, "selected": selected, "error": error, "mate_raw_is_none": mate_raw is None}
            log(f"case {label}: error={error}")
            if mate_raw is not None:
                feature = m.added_mate_feature(before_names, model, label, types, pythoncom)
                try:
                    data = m.distance_mate_data(feature, types, pythoncom)
                    row["stored_distance_mm"] = float(base.value(data, "Distance")) * 1000.0
                    row["stored_alignment"] = int(base.value(data, "MateAlignment"))
                    row["is_advanced"] = bool(base.value(data, "IsAdvancedMate"))
                    row["stored_min_mm"] = float(base.value(data, "MinimumDistance")) * 1000.0
                    row["stored_max_mm"] = float(base.value(data, "MaximumDistance")) * 1000.0
                except Exception as exc:  # noqa: BLE001
                    row["readback_exception"] = repr(exc)
                row["finger_pose_after"] = pose_fact(transform_array(components[role], types, pythoncom))
                row["deleted"] = delete_named(label)
            row["restored"] = restore(role)
            return row

        # ---- phase 4: R side alignment/sign exploration ----
        result["distance_cases"].append(distance_case("R", "RIGHT", "R1_anti_pos_plain", 1, R_OPEN_M, 0.0, 0.0))
        result["distance_cases"].append(distance_case("R", "RIGHT", "R2_aligned_pos_plain", 0, R_OPEN_M, 0.0, 0.0))
        r_winner = next((row for row in result["distance_cases"] if row["label"].startswith("R") and row.get("error") == 1 and abs(row["finger_pose_after"]["translation_mm"][1] - 71.5) < 0.5), None)
        result["notes"].append(f"R winner at design pose: {r_winner['label'] if r_winner else 'NONE'}")
        if r_winner is not None:
            result["distance_cases"].append(distance_case("R", "RIGHT", "R3_winner_with_limits", int(r_winner["align"]), R_OPEN_M, R_MAX_M, 0.0))

        # ---- phase 5: L side sign exploration (production alignment = 0) ----
        result["distance_cases"].append(distance_case("L", "LEFT", "L1_aligned_pos_plain", 0, L_OPEN_M, 0.0, 0.0))
        result["distance_cases"].append(distance_case("L", "LEFT", "L2_aligned_neg_plain", 0, -L_OPEN_M, 0.0, 0.0))
        l_winner = next((row for row in result["distance_cases"] if row["label"].startswith("L") and row.get("error") == 1 and abs(row["finger_pose_after"]["translation_mm"][1] + 71.5) < 0.5), None)
        result["notes"].append(f"L winner at design pose: {l_winner['label'] if l_winner else 'NONE'}")
        if l_winner is not None:
            stored = float(l_winner.get("stored_distance_mm", 0.0))
            if stored < 0.0:
                result["distance_cases"].append(distance_case("L", "LEFT", "L3_winner_with_limits", int(l_winner["align"]), float(l_winner["dist_m"]), 0.0, -L_MAX_M))
            else:
                result["distance_cases"].append(distance_case("L", "LEFT", "L3_winner_with_limits", int(l_winner["align"]), float(l_winner["dist_m"]), L_MAX_M, 0.0))

        result["verdict"] = "V5_PROBE_LOOP1C1_ALIGN_SIGN_V4_PASS"
    except Exception:  # noqa: BLE001
        result["exception"] = traceback.format_exc()
        result["verdict"] = "V5_PROBE_LOOP1C1_ALIGN_SIGN_V4_FAIL"
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
