#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Loop1B hinge probe 3: final mate-alignment recipe + drive-strategy variants.

Probe evidence so far:
  * concentric(lug bore inner, pin OD) with ALIGNED flips the lock group 180 deg
    about Z at creation (probe 1); ANTI_ALIGNED creates with zero motion (probe 2).
  * concentric(retainer ID, pin OD) is the opposite: ALIGNED creates with zero
    motion (probe 1); ANTI_ALIGNED flips the retainer (probe 2).
  * driving BOTH panel and lug leaves the panel off by 1e-5..0.286 because the
    lock-mate solve repositions the panel (probe 2).

Probe 3 verifies the final recipe: concentric lug-pin ANTI, concentric
retainer-pin ALIGNED, both coincidents CLOSEST, then compares drive strategies:
  A: lug-only, SolveMates=True
  B: lug-only, SolveMates=False
  C: lug set to commanded, then panel set to the LUG READBACK (SolveMates=False)
Angles: +0.5, -0.5, 0, stowed(-90 deg), 0.  In-memory only; no saves.
"""

from __future__ import annotations

import json
import math
import sys
import traceback
from pathlib import Path

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY as L1B  # noqa: E402

IDENTITY = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]


def snap(model, components, label, types, pythoncom):
    print("PHASE", label, flush=True, file=sys.stderr)
    row = {"phase": label, "components": {}}
    for name, comp in components.items():
        t = L1B.transform_array(comp)
        row["components"][name] = {
            "translation_mm": [round(t[9] * 1000.0, 6), round(t[10] * 1000.0, 6), round(t[11] * 1000.0, 6)],
            "max_abs_err_vs_identity": max(abs(a - b) for a, b in zip(t, IDENTITY)),
            "constrained_status": int(L1B.value(comp, "GetConstrainedStatus")),
        }
    try:
        ledger = L1B.mate_ledger(model, types, pythoncom)
        row["mates"] = [{"name": r["feature_name"], "type": r["mate_type"], "align": r["alignment"], "err": r["feature_error_code"]} for r in ledger]
    except Exception as exc:
        row["mates_error"] = repr(exc)
    return row


def measure(components, angle_rad, ay_m):
    expected = L1B.rotation_x_about_y_data(angle_rad, ay_m)
    pt = L1B.transform_array(components["PANEL"])
    lt = L1B.transform_array(components["LUG"])
    return {
        "lug_err": max(abs(a - b) for a, b in zip(lt, expected)),
        "panel_err": max(abs(a - b) for a, b in zip(pt, expected)),
        "rigid_err": max(abs(a - b) for a, b in zip(pt, lt)),
        "panel_t_mm": [round(pt[9] * 1000.0, 6), round(pt[10] * 1000.0, 6), round(pt[11] * 1000.0, 6)],
        "lug_t_mm": [round(lt[9] * 1000.0, 6), round(lt[10] * 1000.0, 6), round(lt[11] * 1000.0, 6)],
    }


def drive(model, sw, components, angle_rad, ay_m, mode, types, pythoncom):
    data = L1B.rotation_x_about_y_data(angle_rad, ay_m)
    panel, lug = components["PANEL"], components["LUG"]
    if mode == "A_LUG_ONLY_SOLVE":
        ok1 = bool(lug.SetTransformAndSolve3(L1B.make_transform(sw, data, types, pythoncom), True))
        ok2 = True
    elif mode == "B_LUG_ONLY_NOSOLVE":
        ok1 = bool(lug.SetTransformAndSolve3(L1B.make_transform(sw, data, types, pythoncom), False))
        ok2 = True
    elif mode == "C_LUG_THEN_PANEL_TO_READBACK":
        ok1 = bool(lug.SetTransformAndSolve3(L1B.make_transform(sw, data, types, pythoncom), False))
        actual = L1B.transform_array(lug)
        ok2 = bool(panel.SetTransformAndSolve3(L1B.make_transform(sw, actual, types, pythoncom), False))
    else:
        raise ValueError(mode)
    okr = bool(model.EditRebuild3())
    return {"mode": mode, "ok_lug_set": ok1, "ok_panel_set": ok2, "ok_rebuild": okr}


def main() -> int:
    out = {"probe": "LOOP1B_HINGE_PROBE3_DRIVE_VARIANTS_V1", "phases": [], "drive_tests": []}
    sw = types = pythoncom = None
    model = None
    try:
        expected_pid = L1B.registered_baseline()["session_b_pid"]
        sw, types, pythoncom, session = L1B.attach_empty_session(expected_pid)
        out["session"] = session
        raw = sw.NewDocument(str(L1B.ASSEMBLY_TEMPLATE), 0, 0.0, 0.0)
        if raw is None:
            raw = L1B.value(sw, "ActiveDoc")
        model = L1B.wrap(raw, "IModelDoc2", types, pythoncom)
        assembly = L1B.wrap(model, "IAssemblyDoc", types, pythoncom)
        spec = L1B.SIDES["L"]
        ay_mm = float(spec["axis_y_mm"])
        ay = ay_mm / 1000.0
        entries = [
            ("CLEVIS", Path(spec["clevis"]), True, (0.0, 0.0, 0.0)),
            ("PANEL", Path(spec["panel"]), False, (0.0, 0.0, 0.0)),
            ("LUG", Path(spec["lug"]), False, (0.0, 0.0, 0.0)),
            ("PIN", Path(spec["pin"]), True, (0.0, 0.0, 0.0)),
            ("SPRING_1", Path(spec["springs"][0]), True, (0.0, 0.0, 0.0)),
            ("SPRING_2", Path(spec["springs"][1]), True, (0.0, 0.0, 0.0)),
            ("DONOR_STOP", Path(spec["stop"]), True, (0.0, 0.0, 0.0)),
            ("SERVICE_LOOP", Path(spec["loop"]), True, (0.0, 0.0, 0.0)),
            ("RETAINER", Path(spec["retainer"]), False, (0.0, 0.0, 0.0)),
            ("AXIAL_SPACER", L1B.V5_PART["SPACER"], True, (-0.0755, ay, 0.0)),
            ("GROMMET", L1B.V5_PART["GROMMET"], True, (-0.110, ay, -0.020)),
            ("STOP_PAD", L1B.V5_PART["STOP_PAD"], True, (-0.058, 0.12115, 0.037)),
        ]
        components = {}
        for role, path, fixed, translation in entries:
            print("INSERT", role, flush=True, file=sys.stderr)
            components[role] = L1B.insert_component(sw, model, assembly, path, fixed, translation, types, pythoncom)
        watch = {k: components[k] for k in ("PANEL", "LUG", "RETAINER")}
        lug_initial = L1B.transform_array(components["LUG"])
        components["PANEL"].SetTransformAndSolve3(L1B.make_transform(sw, lug_initial, types, pythoncom), True)
        model.EditRebuild3()
        L1B.add_lock_mate(model, assembly, components["PANEL"], components["LUG"], types, pythoncom)
        out["phases"].append(snap(model, watch, "R1_AFTER_LOCK", types, pythoncom))

        lug_cyl, _ = L1B.cylinder_entity(components["LUG"], 4.2, ay_mm, 2, types, pythoncom)
        pin_cyl, _ = L1B.cylinder_entity(components["PIN"], 4.0, ay_mm, 1, types, pythoncom)
        L1B.add_entity_mate(model, assembly, lug_cyl, pin_cyl, L1B.SW_MATE_CONCENTRIC, L1B.SW_ALIGN_ANTI_ALIGNED, (components["LUG"], components["PIN"]), types, pythoncom)
        out["phases"].append(snap(model, watch, "R2_AFTER_CONCENTRIC_LUG_ANTI", types, pythoncom))

        lug_face, _ = L1B.plane_entity_x(components["LUG"], -75.0, types, pythoncom)
        spacer_face, _ = L1B.spacer_axial_plane_entity(components["AXIAL_SPACER"], ay_mm, types, pythoncom)
        L1B.add_entity_mate(model, assembly, lug_face, spacer_face, L1B.SW_MATE_COINCIDENT, L1B.SW_ALIGN_CLOSEST, (components["LUG"], components["AXIAL_SPACER"]), types, pythoncom)
        out["phases"].append(snap(model, watch, "R3_AFTER_COINCIDENT_LUG_SPACER", types, pythoncom))

        retainer_cyl, _ = L1B.cylinder_entity(components["RETAINER"], 4.1, ay_mm, 1, types, pythoncom)
        L1B.add_entity_mate(model, assembly, retainer_cyl, pin_cyl, L1B.SW_MATE_CONCENTRIC, L1B.SW_ALIGN_ALIGNED, (components["RETAINER"], components["PIN"]), types, pythoncom)
        retainer_face, _ = L1B.plane_entity_x(components["RETAINER"], -82.0, types, pythoncom)
        pin_face, _ = L1B.plane_entity_x(components["PIN"], -82.0, types, pythoncom)
        L1B.add_entity_mate(model, assembly, retainer_face, pin_face, L1B.SW_MATE_COINCIDENT, L1B.SW_ALIGN_CLOSEST, (components["RETAINER"], components["PIN"]), types, pythoncom)
        out["phases"].append(snap(model, watch, "R4_AFTER_RETAINER_MATES", types, pythoncom))

        half = math.radians(0.5)
        stowed = float(spec["stowed_rotation_rad"])
        for mode in ("A_LUG_ONLY_SOLVE", "B_LUG_ONLY_NOSOLVE", "C_LUG_THEN_PANEL_TO_READBACK"):
            for angle in (half, -half, 0.0, stowed, 0.0):
                meta = drive(model, sw, components, angle, ay, mode, types, pythoncom)
                meas = measure(components, angle, ay)
                out["drive_tests"].append({"angle_rad": angle, **meta, **meas})
                print("DRIVE", mode, angle, flush=True, file=sys.stderr)

        for name in ("PANEL", "LUG"):
            try:
                out[f"dof_{name}"] = L1B.prove_component_true_1r(components[name], ay_mm, types, pythoncom)["exact_true_1r"]
            except Exception as exc:
                out[f"dof_{name}_error"] = repr(exc)
        out["verdict"] = "PROBE3_COMPLETE"
    except Exception as exc:
        out["verdict"] = "PROBE3_EXCEPTION"
        out["error"] = repr(exc)
        out["traceback"] = traceback.format_exc()
    finally:
        try:
            L1B.close_doc(sw, model)
        except Exception:
            pass
        try:
            L1B.close_owned_documents(sw)
            out["final_document_count"] = int(L1B.value(sw, "GetDocumentCount")) if sw is not None else None
        except Exception:
            out["final_document_count"] = "UNKNOWN"
        if pythoncom is not None:
            pythoncom.CoUninitialize()
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out.get("verdict") == "PROBE3_COMPLETE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
