#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Loop1B hinge diagnostic probe (attach-only, in-memory, no saves).

Rebuilds the L-side wing-root assembly step by step using the Loop1B script's
own helpers and dumps PANEL/LUG/PIN component transforms plus mate health
after EVERY phase, to pinpoint which call relocates the components to the
flipped branch seen in HINGE_GROUP_KINEMATIC_DRIFT receipts.

Writes no receipts and no CAD files.  Closes the in-memory assembly without
saving and leaves the session document-empty.  Stdout JSON only.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

RUN_ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3R2_V5_NATIVE_MECHANICAL_RELEASE_20260810T000300_V5NATIVE")
sys.path.insert(0, str(RUN_ROOT / "99_tools"))

import F3R2_V5_NATIVE_LOOP1B_WING_ROOTS_ATTACH_ONLY as L1B  # noqa: E402


def snap(model, components, label, types, pythoncom):
    print("PHASE", label, flush=True, file=sys.stderr)
    row = {"phase": label, "components": {}}
    for name, comp in components.items():
        try:
            t = L1B.transform_array(comp)
            row["components"][name] = {
                "transform": t,
                "translation_mm": [round(t[9] * 1000.0, 6), round(t[10] * 1000.0, 6), round(t[11] * 1000.0, 6)],
                "r_diag": [round(t[0], 6), round(t[4], 6), round(t[8], 6)],
                "fixed": bool(L1B.value(comp, "IsFixed")),
                "constrained_status": int(L1B.value(comp, "GetConstrainedStatus")),
            }
        except Exception as exc:
            row["components"][name] = {"error": repr(exc)}
    try:
        ledger = L1B.mate_ledger(model, types, pythoncom)
        row["mates"] = [
            {"name": r["feature_name"], "type": r["mate_type"], "align": r["alignment"],
             "err": r["feature_error_code"], "warn": r["feature_is_warning"], "supp": r["suppressed"]}
            for r in ledger
        ]
    except Exception as exc:
        row["mates_error"] = repr(exc)
    return row


def main() -> int:
    out = {"probe": "LOOP1B_HINGE_PHASE_PROBE_V1", "phases": []}
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
        ay = float(spec["axis_y_mm"]) / 1000.0
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
        watch = {k: components[k] for k in ("CLEVIS", "PANEL", "LUG", "PIN", "RETAINER", "AXIAL_SPACER")}
        out["phases"].append(snap(model, watch, "P1_AFTER_INSERTS", types, pythoncom))

        lug_initial = L1B.transform_array(components["LUG"])
        ok_align = bool(components["PANEL"].SetTransformAndSolve3(L1B.make_transform(sw, lug_initial, types, pythoncom), True))
        ok_rebuild = bool(model.EditRebuild3())
        out["phases"].append({**snap(model, watch, "P2_AFTER_PANEL_ALIGN", types, pythoncom), "align_ok": ok_align, "rebuild_ok": ok_rebuild})

        mates = []
        mates.append(L1B.add_lock_mate(model, assembly, components["PANEL"], components["LUG"], types, pythoncom))
        out["phases"].append(snap(model, watch, "P3_AFTER_LOCK_MATE", types, pythoncom))

        lug_cyl, _row = L1B.cylinder_entity(components["LUG"], 4.2, float(spec["axis_y_mm"]), 2, types, pythoncom)
        pin_cyl, _row = L1B.cylinder_entity(components["PIN"], 4.0, float(spec["axis_y_mm"]), 1, types, pythoncom)
        mates.append(L1B.add_entity_mate(model, assembly, lug_cyl, pin_cyl, L1B.SW_MATE_CONCENTRIC, L1B.SW_ALIGN_ALIGNED, (components["LUG"], components["PIN"]), types, pythoncom))
        out["phases"].append(snap(model, watch, "P4_AFTER_CONCENTRIC_LUG_PIN", types, pythoncom))

        lug_face, _row = L1B.plane_entity_x(components["LUG"], -75.0, types, pythoncom)
        spacer_face, _row = L1B.spacer_axial_plane_entity(components["AXIAL_SPACER"], float(spec["axis_y_mm"]), types, pythoncom)
        mates.append(L1B.add_entity_mate(model, assembly, lug_face, spacer_face, L1B.SW_MATE_COINCIDENT, L1B.SW_ALIGN_CLOSEST, (components["LUG"], components["AXIAL_SPACER"]), types, pythoncom))
        out["phases"].append(snap(model, watch, "P5_AFTER_COINCIDENT_LUG_SPACER", types, pythoncom))

        retainer_cyl, _row = L1B.cylinder_entity(components["RETAINER"], 4.1, float(spec["axis_y_mm"]), 1, types, pythoncom)
        mates.append(L1B.add_entity_mate(model, assembly, retainer_cyl, pin_cyl, L1B.SW_MATE_CONCENTRIC, L1B.SW_ALIGN_ALIGNED, (components["RETAINER"], components["PIN"]), types, pythoncom))
        retainer_face, _row = L1B.plane_entity_x(components["RETAINER"], -82.0, types, pythoncom)
        pin_face, _row = L1B.plane_entity_x(components["PIN"], -82.0, types, pythoncom)
        mates.append(L1B.add_entity_mate(model, assembly, retainer_face, pin_face, L1B.SW_MATE_COINCIDENT, L1B.SW_ALIGN_CLOSEST, (components["RETAINER"], components["PIN"]), types, pythoncom))
        out["phases"].append(snap(model, watch, "P6_AFTER_RETAINER_MATES", types, pythoncom))

        identity = L1B.make_transform(sw, L1B.transform_data((0.0, 0.0, 0.0)), types, pythoncom)
        ok_panel_set = bool(components["PANEL"].SetTransformAndSolve3(identity, False))
        ok_lug_set = bool(components["LUG"].SetTransformAndSolve3(L1B.make_transform(sw, L1B.transform_data((0.0, 0.0, 0.0)), types, pythoncom), False))
        out["phases"].append({**snap(model, watch, "P7_AFTER_SET_NOSOLVE_BEFORE_REBUILD", types, pythoncom), "panel_set_ok": ok_panel_set, "lug_set_ok": ok_lug_set})
        ok_rebuild2 = bool(model.EditRebuild3())
        out["phases"].append({**snap(model, watch, "P8_AFTER_REBUILD", types, pythoncom), "rebuild_ok": ok_rebuild2})

        for name in ("PANEL", "LUG"):
            try:
                out[f"dof_{name}"] = L1B.remaining_dof_ledger(components[name], types, pythoncom)
            except Exception as exc:
                out[f"dof_{name}_error"] = repr(exc)
        out["mate_facts"] = mates
        out["verdict"] = "PROBE_COMPLETE"
    except Exception as exc:
        out["verdict"] = "PROBE_EXCEPTION"
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
    return 0 if out.get("verdict") == "PROBE_COMPLETE" else 3


if __name__ == "__main__":
    raise SystemExit(main())
