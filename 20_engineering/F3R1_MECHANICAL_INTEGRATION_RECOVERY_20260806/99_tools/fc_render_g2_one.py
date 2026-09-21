# -*- coding: utf-8 -*-
"""FreeCAD macro: render witness ISO views of the four G2 key-state STEPs.

Reads the per-config STEPs exported by g2d_cold_reopen (step/F3R1_V3_*.step) and
writes one ISO PNG per configuration under 11_screenshots/RAW/G2. These are raw
witness views of the actual exported geometry -- states differentiated by real
config content, not by moving parts for the camera.
"""
import json
import os

import FreeCAD
import FreeCADGui
import Part

AUDIT = (r"F:\China Graduate Future Flight Vehicle Innovation Competition"
         r"\20_engineering\F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806")
STEPDIR = os.path.join(AUDIT, "04_configurations", "G2", "step")
RAW = os.path.join(AUDIT, "11_screenshots", "RAW", "G2")
OUT = os.path.join(AUDIT, "11_screenshots", "F3R1_G2_RENDER_INDEX.json")
W, H = 1920, 1080
CONFIGS = ["R_FAIL"]

rep = {"schema": "F3R1_G2_RENDER_V1", "shots": []}
os.makedirs(RAW, exist_ok=True)

for cname in CONFIGS:
    step = os.path.join(STEPDIR, "F3R1_V3_%s.step" % cname)
    if not os.path.isfile(step):
        rep["shots"].append({"config": cname, "status": "STEP_MISSING"})
        continue
    doc = FreeCAD.newDocument("G2_%s" % cname)
    Part.insert(step, doc.Name)
    FreeCADGui.updateGui()
    gui = FreeCADGui.getDocument(doc.Name)
    n = 0
    for o in doc.Objects:
        sh = getattr(o, "Shape", None)
        if sh is not None and not sh.isNull():
            n += 1
            try:
                gui.getObject(o.Name).Visibility = True
            except Exception:
                pass
    v = FreeCADGui.activeDocument().activeView()
    v.viewAxonometric()
    FreeCADGui.updateGui()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    FreeCADGui.updateGui()
    p = os.path.join(RAW, "G2_%s_ISO_RAW.png" % cname)
    v.saveImage(p, W, H, "White")
    rep["shots"].append({"config": cname, "path": p,
                         "objects_with_shape": n,
                         "bytes": os.path.getsize(p) if os.path.isfile(p) else 0})
    FreeCAD.Console.PrintMessage("SHOT %s shapes=%d %s\n"
                                 % (cname, n, os.path.getsize(p)))
    FreeCAD.closeDocument(doc.Name)

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(rep, fh, indent=2, ensure_ascii=False)
FreeCADGui.getMainWindow().close()
