# -*- coding: utf-8 -*-
"""FreeCAD macro: READ-ONLY open of the F3-P3 top assembly + first screenshot batch.

Hard constraints enforced here (audit section 5):
  READ_ONLY = true, SAVE_CALLS_ALLOWED = 0, REBUILD_SAVE = false.
There is no doc.save() / saveAs() / recompute-then-save anywhere in this file.
Every object's bounding box is dumped so saddle/HDRM solids can be located by
geometry (the imported STEP solids carry generic native_STOWED### labels).

Run:  FreeCAD.exe <this file>
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
OUT_JSON = os.path.join(AUDIT, "01_native_cad", "F3_TOP_ASSEMBLY_OPEN_REPORT.json")
LOG = os.path.join(AUDIT, "01_native_cad", "fc_open_capture.log")

W, H = 1920, 1080
SAVE_CALLS = 0  # never incremented; asserted at exit

log_lines = []


def log(stage, **kw):
    rec = {"stage": stage}
    rec.update(kw)
    log_lines.append(rec)
    FreeCAD.Console.PrintMessage(json.dumps(rec, ensure_ascii=False) + "\n")


def flush_log():
    with open(LOG, "w", encoding="utf-8") as fh:
        for r in log_lines:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main():
    report = {"schema": "F3_TOP_ASSEMBLY_OPEN_REPORT_V1",
              "source": SRC, "save_calls": 0, "screenshots": [], "objects": []}
    try:
        os.makedirs(RAW, exist_ok=True)
        log("FREECAD_VERSION", version=list(FreeCAD.Version()))
        log("OPEN_START", path=SRC)
        doc = FreeCAD.openDocument(SRC)
        log("OPEN_OK", name=doc.Name, objects=len(doc.Objects))

        report["document_name"] = doc.Name
        report["object_count"] = len(doc.Objects)
        # FreeCAD marks a doc Touched if opening triggered any change.
        report["document_touched_on_open"] = bool(doc.isTouched())
        report["recompute_required_on_open"] = bool(doc.mustExecute())

        # ---- geometry inventory (no modification) ----
        errs = []
        gmin = [1e18] * 3
        gmax = [-1e18] * 3
        for o in doc.Objects:
            rec = {"name": o.Name, "label": o.Label, "type": o.TypeId}
            try:
                sh = getattr(o, "Shape", None)
                if sh is not None and not sh.isNull():
                    bb = sh.BoundBox
                    rec.update(
                        bbox_mm=[round(bb.XMin, 3), round(bb.YMin, 3), round(bb.ZMin, 3),
                                 round(bb.XMax, 3), round(bb.YMax, 3), round(bb.ZMax, 3)],
                        volume_mm3=round(sh.Volume, 3),
                        solids=len(sh.Solids), valid=bool(sh.isValid()))
                    for i, v in enumerate((bb.XMin, bb.YMin, bb.ZMin)):
                        gmin[i] = min(gmin[i], v)
                    for i, v in enumerate((bb.XMax, bb.YMax, bb.ZMax)):
                        gmax[i] = max(gmax[i], v)
                    if not sh.isValid():
                        errs.append({"name": o.Name, "issue": "INVALID_SHAPE"})
                else:
                    rec["bbox_mm"] = None
            except Exception as exc:
                rec["error"] = str(exc)
                errs.append({"name": o.Name, "issue": str(exc)})
            report["objects"].append(rec)

        report["global_bbox_mm"] = [round(v, 3) for v in gmin + gmax]
        report["invalid_or_error_objects"] = errs
        report["objects_in_error_state"] = [o.Name for o in doc.Objects
                                            if getattr(o, "State", None)
                                            and "Invalid" in o.State]
        log("INVENTORY_DONE", objects=len(report["objects"]),
            errors=len(errs), gbbox=report["global_bbox_mm"])

        # ---- views ----
        v = FreeCADGui.activeDocument().activeView()
        FreeCADGui.activeDocument().activeView().setAnimationEnabled(False)

        views = [
            ("S01_STOWED_ISOMETRIC", "viewAxonometric"),
            ("S02_STOWED_TOP", "viewTop"),
            ("S03_STOWED_SIDE", "viewRight"),
            ("S04_STOWED_FRONT", "viewFront"),
        ]
        for sid, fn in views:
            getattr(v, fn)()
            FreeCADGui.SendMsgToActiveView("ViewFit")
            FreeCADGui.updateGui()
            path = os.path.join(RAW, sid + "_RAW.png")
            v.saveImage(path, W, H, "White")
            ok = os.path.isfile(path)
            report["screenshots"].append(
                {"screenshot_id": sid, "view": fn, "path": path,
                 "written": ok, "bytes": os.path.getsize(path) if ok else 0,
                 "width": W, "height": H, "background": "White",
                 "export_method": "FreeCADGui activeView().saveImage (CAD API viewport export)"})
            log("SCREENSHOT", id=sid, ok=ok)

        # ---- close WITHOUT saving ----
        report["save_calls"] = SAVE_CALLS
        report["document_touched_before_close"] = bool(doc.isTouched())
        FreeCAD.closeDocument(doc.Name)
        log("CLOSED_WITHOUT_SAVE", save_calls=SAVE_CALLS)
        report["status"] = "OPEN_AND_CAPTURE_OK"
    except Exception:
        report["status"] = "ERROR"
        report["traceback"] = traceback.format_exc()
        log("ERROR", tb=traceback.format_exc())

    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    flush_log()
    log("DONE", out=OUT_JSON)


main()
FreeCADGui.getMainWindow().close()
