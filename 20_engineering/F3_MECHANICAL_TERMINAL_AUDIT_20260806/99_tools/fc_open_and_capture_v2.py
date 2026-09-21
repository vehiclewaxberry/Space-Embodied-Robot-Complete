# -*- coding: utf-8 -*-
"""FreeCAD macro v2: READ-ONLY capture with forced visibility + geometry-located detail views.

Fixes v1's blank frames: v1 called ViewFit before the ViewProviders had geometry
attached, and never asserted Visibility, so every export was an empty white frame.
v2 forces Visibility on all shaped objects, calls Gui.updateGui() before fitting,
and verifies each PNG is non-blank by byte size.

Constraints unchanged: READ_ONLY, SAVE_CALLS_ALLOWED = 0, no recompute-then-save.
Saddle / HDRM / base solids are located by bounding box against the frozen S3
coordinates (G07 X[-20,0] z=261.08 / G08 X[160,180] z=209.42 / Mid X[80,100] z=214.92).
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
OUT_JSON = os.path.join(AUDIT, "01_native_cad", "F3_TOP_ASSEMBLY_OPEN_REPORT_V2.json")
LOG = os.path.join(AUDIT, "01_native_cad", "fc_open_capture_v2.log")

W, H = 1920, 1080
BLANK_MAX_BYTES = 30000  # a real shaded 1920x1080 CAD frame is far larger

# frozen S3 nominal locations, mm, from F3_P5A_SOURCE_GEOMETRY_MANIFEST
PROBES = [
    ("G07_AFT_SADDLE", (-20.0, 0.0), 261.08),
    ("G08_FWD_SADDLE", (160.0, 180.0), 209.42),
    ("MID_SADDLE", (80.0, 100.0), 214.92),
]

log_lines = []


def log(stage, **kw):
    rec = {"stage": stage}
    rec.update(kw)
    log_lines.append(rec)
    FreeCAD.Console.PrintMessage(json.dumps(rec, ensure_ascii=False) + "\n")


def shot(view, sid, purpose):
    FreeCADGui.updateGui()
    path = os.path.join(RAW, sid + "_RAW.png")
    view.saveImage(path, W, H, "White")
    ok = os.path.isfile(path)
    size = os.path.getsize(path) if ok else 0
    rec = {"screenshot_id": sid, "path": path, "written": ok, "bytes": size,
           "width": W, "height": H, "background": "White",
           "export_method": "FreeCADGui activeView().saveImage (CAD API viewport export)",
           "blank_frame_suspected": size < BLANK_MAX_BYTES, "review_purpose": purpose}
    log("SCREENSHOT", id=sid, bytes=size, blank=rec["blank_frame_suspected"])
    return rec


def main():
    rep = {"schema": "F3_TOP_ASSEMBLY_OPEN_REPORT_V2", "source": SRC,
           "save_calls": 0, "screenshots": [], "probe_hits": {}}
    try:
        os.makedirs(RAW, exist_ok=True)
        doc = FreeCAD.openDocument(SRC)
        log("OPEN_OK", name=doc.Name, objects=len(doc.Objects))
        rep["document_name"] = doc.Name
        rep["object_count"] = len(doc.Objects)

        gui = FreeCADGui.getDocument(doc.Name)

        # ---- force visibility on every shaped object (view state only, never saved) ----
        shaped, made_visible, invalid = [], 0, []
        for o in doc.Objects:
            sh = getattr(o, "Shape", None)
            if sh is None or sh.isNull():
                continue
            shaped.append(o)
            if not sh.isValid():
                invalid.append(o.Name)
            try:
                vo = gui.getObject(o.Name)
                if vo is not None and not vo.Visibility:
                    vo.Visibility = True
                    made_visible += 1
            except Exception as exc:
                log("VISIBILITY_FAIL", name=o.Name, error=str(exc))
        rep["shaped_objects"] = len(shaped)
        rep["objects_made_visible"] = made_visible
        rep["invalid_shapes"] = invalid
        log("VISIBILITY_DONE", shaped=len(shaped), forced=made_visible,
            invalid=len(invalid))

        v = FreeCADGui.activeDocument().activeView()
        try:
            v.setAnimationEnabled(False)
        except Exception:
            pass

        # ---- overall views ----
        for sid, fn, purpose in [
            ("S01_STOWED_ISOMETRIC", "viewAxonometric",
             "overall proportion / arm stow path / equipment bay occupancy"),
            ("S02_STOWED_TOP", "viewTop", "plan footprint, saddle line-up"),
            ("S03_STOWED_SIDE", "viewRight", "stow height, saddle z-steps"),
            ("S04_STOWED_FRONT", "viewFront", "base position, symmetry"),
        ]:
            getattr(v, fn)()
            FreeCADGui.SendMsgToActiveView("ViewFit")
            FreeCADGui.updateGui()
            FreeCADGui.SendMsgToActiveView("ViewFit")
            rep["screenshots"].append(shot(v, sid, purpose))

        # ---- locate saddle candidates by bbox, then frame them ----
        for tag, (x0, x1), z in PROBES:
            hits = []
            for o in shaped:
                bb = o.Shape.BoundBox
                if bb.XMax >= x0 - 8 and bb.XMin <= x1 + 8 and \
                   bb.ZMax >= z - 25 and bb.ZMin <= z + 25:
                    hits.append({"name": o.Name, "label": o.Label,
                                 "bbox_mm": [round(bb.XMin, 2), round(bb.YMin, 2),
                                             round(bb.ZMin, 2), round(bb.XMax, 2),
                                             round(bb.YMax, 2), round(bb.ZMax, 2)],
                                 "volume_mm3": round(o.Shape.Volume, 2)})
            hits.sort(key=lambda d: -d["volume_mm3"])
            rep["probe_hits"][tag] = {"expected_x_mm": [x0, x1],
                                      "expected_z_mm": z, "hit_count": len(hits),
                                      "hits": hits[:12]}
            log("PROBE", tag=tag, hits=len(hits))

            if hits:
                names = [h["name"] for h in hits[:6]]
                FreeCADGui.Selection.clearSelection()
                for n in names:
                    FreeCADGui.Selection.addSelection(doc.Name, n)
                v.viewAxonometric()
                FreeCADGui.SendMsgToActiveView("ViewSelection")
                FreeCADGui.updateGui()
                sid = {"G07_AFT_SADDLE": "S13_G07_CLOSEUP",
                       "G08_FWD_SADDLE": "S14_G08_CLOSEUP",
                       "MID_SADDLE": "S15_MID_2MM_GAP_CLOSEUP"}[tag]
                rep["screenshots"].append(
                    shot(v, sid, "%s geometry present? contact vs 2mm nominal gap" % tag))
                FreeCADGui.Selection.clearSelection()

        rep["document_touched_before_close"] = bool(doc.isTouched())
        FreeCAD.closeDocument(doc.Name)
        log("CLOSED_WITHOUT_SAVE", save_calls=0)
        rep["status"] = "OK"
    except Exception:
        rep["status"] = "ERROR"
        rep["traceback"] = traceback.format_exc()
        log("ERROR", tb=traceback.format_exc())

    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(rep, fh, indent=2, ensure_ascii=False)
    with open(LOG, "w", encoding="utf-8") as fh:
        for r in log_lines:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


main()
FreeCADGui.getMainWindow().close()
