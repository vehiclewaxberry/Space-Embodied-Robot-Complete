#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Loop1B hinge probe 4: lock-mate suppress/pose/unsuppress drive.

Probe evidence so far:
  * Final mate recipe (lock; concentric lug-pin ANTI; coincident lug-spacer
    CLOSEST; concentric retainer-pin ALIGNED; coincident retainer-pin CLOSEST)
    creates with ZERO component motion (probe 3, phases R1-R4).
  * The SW2024 lock mate contributes to DOF classification but does NOT enforce
    relative placement under SetTransformAndSolve3: driving the lug leaves the
    panel behind (probe 3), driving both leaves the panel imprecise (probe 2).
  * Free components place exactly (insert phase; solar array per-config poses).

Probe 4 tests the deterministic drive: suppress the lock mate (panel becomes a
free component), place lug and panel with solve-free absolute transforms (both
exact), unsuppress the lock (satisfied identically at the commanded pose),
rebuild, and verify exact transforms + healthy mates + true 1R.
In-memory only; no saves; stdout JSON only.
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

SW_SUPPRESS = 0
SW_UNSUPPRESS = 1
SW_ALL_CONFIGS = 2


def find_lock_feature(model, types, pythoncom):
    feature = L1B.value(model, "FirstFeature")
    for _ in range(10000):
        if feature is None:
            return None
        typed = L1B.wrap(feature, "IFeature", types, pythoncom)
        if str(L1B.value(typed, "GetTypeName2")) == "MateGroup":
            sub = L1B.value(typed, "GetFirstSubFeature")
            for _sub in range(10000):
                if sub is None:
                    break
                sf = L1B.wrap(sub, "IFeature", types, pythoncom)
                raw_mate = L1B.value(sf, "GetSpecificFeature2")
                if raw_mate is not None:
                    mate = L1B.wrap(raw_mate, "IMate2", types, pythoncom)
                    if int(L1B.value(mate, "Type")) == L1B.SW_MATE_LOCK:
                        return sf
                sub = L1B.value(sf, "GetNextSubFeature")
        feature = L1B.value(typed, "GetNextFeature")
    return None


def set_lock_suppression(lock_feature, state):
    returned = lock_feature.SetSuppression2(state, SW_ALL_CONFIGS, None)
    ok = True
    try:
        ok = bool(returned)
    except Exception:
        ok = True
    return ok


def snap(model, components, label, types, pythoncom):
    print("PHASE", label, flush=True, file=sys.stderr)
    row = {"phase": label, "components": {}}
    for name, comp in components.items():
        t = L1B.transform_array(comp)
        row["components"][name] = {
            "translation_mm": [round(t[9] * 1000.0, 6), round(t[10] * 1000.0, 6), round(t[11] * 1000.0, 6)],
            "constrained_status": int(L1B.value(comp, "GetConstrainedStatus")),
        }
    try:
        ledger = L1B.mate_ledger(model, types, pythoncom)
        row["mates"] = [{"name": r["feature_name"], "type": r["mate_type"], "align": r["alignment"], "supp": r["suppressed"], "err": r["feature_error_code"]} for r in ledger]
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
    }


def main() -> int:
    out = {"probe": "LOOP1B_HINGE_PROBE4_LOCK_SUPPRESS_DRIVE_V1", "drive_tests": [], "phases": []}
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
        lug_cyl, _ = L1B.cylinder_entity(components["LUG"], 4.2, ay_mm, 2, types, pythoncom)
        pin_cyl, _ = L1B.cylinder_entity(components["PIN"], 4.0, ay_mm, 1, types, pythoncom)
        L1B.add_entity_mate(model, assembly, lug_cyl, pin_cyl, L1B.SW_MATE_CONCENTRIC, L1B.SW_ALIGN_ANTI_ALIGNED, (components["LUG"], components["PIN"]), types, pythoncom)
        lug_face, _ = L1B.plane_entity_x(components["LUG"], -75.0, types, pythoncom)
        spacer_face, _ = L1B.spacer_axial_plane_entity(components["AXIAL_SPACER"], ay_mm, types, pythoncom)
        L1B.add_entity_mate(model, assembly, lug_face, spacer_face, L1B.SW_MATE_COINCIDENT, L1B.SW_ALIGN_CLOSEST, (components["LUG"], components["AXIAL_SPACER"]), types, pythoncom)
        retainer_cyl, _ = L1B.cylinder_entity(components["RETAINER"], 4.1, ay_mm, 1, types, pythoncom)
        L1B.add_entity_mate(model, assembly, retainer_cyl, pin_cyl, L1B.SW_MATE_CONCENTRIC, L1B.SW_ALIGN_ALIGNED, (components["RETAINER"], components["PIN"]), types, pythoncom)
        retainer_face, _ = L1B.plane_entity_x(components["RETAINER"], -82.0, types, pythoncom)
        pin_face, _ = L1B.plane_entity_x(components["PIN"], -82.0, types, pythoncom)
        L1B.add_entity_mate(model, assembly, retainer_face, pin_face, L1B.SW_MATE_COINCIDENT, L1B.SW_ALIGN_CLOSEST, (components["RETAINER"], components["PIN"]), types, pythoncom)
        out["phases"].append(snap(model, watch, "S1_MATES_COMPLETE", types, pythoncom))

        lock_feature = find_lock_feature(model, types, pythoncom)
        out["lock_feature_found"] = lock_feature is not None
        if lock_feature is not None:
            out["lock_feature_name"] = str(L1B.value(lock_feature, "Name"))
            out["lock_suppressed_initially"] = bool(L1B.value(lock_feature, "IsSuppressed"))

        half = math.radians(0.5)
        stowed = float(spec["stowed_rotation_rad"])
        for angle in (half, -half, 0.0, stowed, 0.0):
            rec = {"angle_rad": angle}
            rec["ok_suppress"] = set_lock_suppression(lock_feature, SW_SUPPRESS)
            model.EditRebuild3()
            data = L1B.rotation_x_about_y_data(angle, ay)
            rec["ok_lug_set"] = bool(components["LUG"].SetTransformAndSolve3(L1B.make_transform(sw, data, types, pythoncom), False))
            rec["ok_panel_set"] = bool(components["PANEL"].SetTransformAndSolve3(L1B.make_transform(sw, data, types, pythoncom), False))
            rec["ok_unsuppress"] = set_lock_suppression(lock_feature, SW_UNSUPPRESS)
            rec["ok_rebuild"] = bool(model.EditRebuild3())
            rec.update(measure(components, angle, ay))
            rec["lock_suppressed_after"] = bool(L1B.value(lock_feature, "IsSuppressed"))
            out["drive_tests"].append(rec)
            print("DRIVE", angle, flush=True, file=sys.stderr)

        out["phases"].append(snap(model, watch, "S2_AFTER_DRIVES", types, pythoncom))
        for name in ("PANEL", "LUG"):
            try:
                out[f"dof_{name}"] = L1B.prove_component_true_1r(components[name], ay_mm, types, pythoncom)["exact_true_1r"]
            except Exception as exc:
                out[f"dof_{name}_error"] = repr(exc)
        out["verdict"] = "PROBE4_COMPLETE"
    except Exception as exc:
        out["verdict"] = "PROBE4_EXCEPTION"
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
    return 0 if out.get("verdict") == "PROBE4_COMPLETE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
