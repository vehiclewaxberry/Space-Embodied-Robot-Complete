# -*- coding: utf-8 -*-
"""FreeCAD macro v3: saddle/HDRM detail views + Mid 2mm gap measurement. READ-ONLY.

v2 located the three saddle posts by bbox but its "closeup" frames also caught the
arm-stow envelope block (native_STOWED046, z 264.08-354), which dominated the view.
v3 frames each saddle alone, measures the actual vertical gap between each saddle
top and whatever sits above it, and captures the solar-array-root / HDRM region.

Constraints unchanged: READ_ONLY, SAVE_CALLS_ALLOWED = 0.
"""
import json
import os
import traceback

import FreeCAD
import FreeCADGui

SRC = (r"F:\Space-Embodied-Robot-HAG_A_20260804\12_f3_p1_hifi_attachment"
       r"\15_f3_p3_top_assembly\F3_P3_TOP_ASSEMBLY.FCStd")
AUDIT = (r"F:\China Graduate Future Flight Vehicle Innovation Competition"
         r"\20_engineering\F3_MECHANICAL_TERMINAL_AUDIT_20260806")
RAW = os.path.join(AUDIT, "03_screenshots", "RAW")
OUT = os.path.join(AUDIT, "01_native_cad", "F3_SADDLE_AND_GAP_MEASUREMENT.json")

W, H = 1920, 1080

SADDLES = {  # name -> (audit id, frozen nominal top z)
    "native_STOWED041": ("S13_G07_SADDLE_ONLY", 261.08),
    "native_STOWED043": ("S14_G08_SADDLE_ONLY", 209.42),
    "native_STOWED042": ("S15_MID_SADDLE_ONLY", 214.92),
}
ENVELOPE = "native_STOWED046"

log_lines = []


def log(stage, **kw):
    rec = {"stage": stage}
    rec.update(kw)
    log_lines.append(rec)
    FreeCAD.Console.PrintMessage(json.dumps(rec, ensure_ascii=False) + "\n")


def shot(v, sid):
    FreeCADGui.updateGui()
    p = os.path.join(RAW, sid + "_RAW.png")
    v.saveImage(p, W, H, "White")
    n = os.path.getsize(p) if os.path.isfile(p) else 0
    log("SCREENSHOT", id=sid, bytes=n)
    return {"screenshot_id": sid, "path": p, "bytes": n}


def main():
    rep = {"schema": "F3_SADDLE_AND_GAP_MEASUREMENT_V1", "source": SRC,
           "save_calls": 0, "saddles": {}, "screenshots": []}
    try:
        doc = FreeCAD.openDocument(SRC)
        gui = FreeCADGui.getDocument(doc.Name)
        by_name = {o.Name: o for o in doc.Objects}

        for o in doc.Objects:
            sh = getattr(o, "Shape", None)
            if sh is not None and not sh.isNull():
                try:
                    gui.getObject(o.Name).Visibility = True
                except Exception:
                    pass

        v = FreeCADGui.activeDocument().activeView()

        env = by_name.get(ENVELOPE)
        if env is not None:
            b = env.Shape.BoundBox
            rep["arm_stow_envelope"] = {
                "name": ENVELOPE,
                "bbox_mm": [round(b.XMin, 2), round(b.YMin, 2), round(b.ZMin, 2),
                            round(b.XMax, 2), round(b.YMax, 2), round(b.ZMax, 2)],
                "volume_mm3": round(env.Shape.Volume, 2),
                "solids": len(env.Shape.Solids),
                "note": "block above the saddles; candidate arm-stow / keepout placeholder"}

        # ---- per-saddle geometry + what is directly above its top face ----
        for nm, (sid, nominal_top) in SADDLES.items():
            o = by_name.get(nm)
            if o is None:
                rep["saddles"][nm] = {"status": "NOT_FOUND"}
                continue
            bb = o.Shape.BoundBox
            entry = {
                "audit_view": sid,
                "bbox_mm": [round(bb.XMin, 2), round(bb.YMin, 2), round(bb.ZMin, 2),
                            round(bb.XMax, 2), round(bb.YMax, 2), round(bb.ZMax, 2)],
                "top_z_mm": round(bb.ZMax, 3),
                "frozen_nominal_top_z_mm": nominal_top,
                "top_z_matches_frozen": abs(bb.ZMax - nominal_top) < 1e-3,
                "height_mm": round(bb.ZMax - bb.ZMin, 3),
                "footprint_mm": [round(bb.XMax - bb.XMin, 3), round(bb.YMax - bb.YMin, 3)],
                "volume_mm3": round(o.Shape.Volume, 2),
                "solids": len(o.Shape.Solids),
                "shape_valid": bool(o.Shape.isValid()),
            }
            # nearest solid above this saddle's top, overlapping its XY footprint
            above = []
            for other in doc.Objects:
                if other.Name == nm:
                    continue
                sh = getattr(other, "Shape", None)
                if sh is None or sh.isNull():
                    continue
                ob = sh.BoundBox
                if ob.XMax < bb.XMin or ob.XMin > bb.XMax:
                    continue
                if ob.YMax < bb.YMin or ob.YMin > bb.YMax:
                    continue
                if ob.ZMin >= bb.ZMax - 1e-6:
                    above.append({"name": other.Name,
                                  "gap_mm": round(ob.ZMin - bb.ZMax, 4),
                                  "z_range": [round(ob.ZMin, 2), round(ob.ZMax, 2)]})
            above.sort(key=lambda d: d["gap_mm"])
            entry["solids_above_footprint"] = above[:6]
            entry["min_vertical_gap_mm"] = above[0]["gap_mm"] if above else None
            rep["saddles"][nm] = entry
            log("SADDLE", name=nm, top=entry["top_z_mm"],
                gap=entry["min_vertical_gap_mm"])

            # isolate: hide everything else, frame this saddle alone
            for other in doc.Objects:
                sh = getattr(other, "Shape", None)
                if sh is None or sh.isNull():
                    continue
                try:
                    gui.getObject(other.Name).Visibility = (other.Name == nm)
                except Exception:
                    pass
            v.viewAxonometric()
            FreeCADGui.updateGui()
            FreeCADGui.SendMsgToActiveView("ViewFit")
            rep["screenshots"].append(shot(v, sid))

        # ---- restore all visible, then capture the +Z / equipment-deck top region ----
        for o in doc.Objects:
            sh = getattr(o, "Shape", None)
            if sh is not None and not sh.isNull():
                try:
                    gui.getObject(o.Name).Visibility = True
                except Exception:
                    pass
        for sid, fn in [("S16_SADDLE_LINEUP_TOP", "viewTop"),
                        ("S17_SADDLE_LINEUP_RIGHT", "viewRight"),
                        ("S05_REAR_ISO", "viewRear")]:
            getattr(v, fn)()
            FreeCADGui.updateGui()
            FreeCADGui.SendMsgToActiveView("ViewFit")
            rep["screenshots"].append(shot(v, sid))

        FreeCAD.closeDocument(doc.Name)
        log("CLOSED_WITHOUT_SAVE", save_calls=0)
        rep["status"] = "OK"
    except Exception:
        rep["status"] = "ERROR"
        rep["traceback"] = traceback.format_exc()
        log("ERROR", tb=traceback.format_exc())

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2, ensure_ascii=False)


main()
FreeCADGui.getMainWindow().close()
