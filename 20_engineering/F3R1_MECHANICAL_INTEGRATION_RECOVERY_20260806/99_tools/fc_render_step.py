# -*- coding: utf-8 -*-
"""FreeCAD macro: render witness views of the F3R1 STOWED STEP export.

Views: S01 iso / S02 top / S03 side / S04 front + saddle-region closeup.
1920x1080, white background, forced visibility (lesson from the F3 audit v1).
READ-ONLY on the STEP; writes PNGs + a JSON index under 11_screenshots/RAW.
"""
import json
import os

import FreeCAD
import FreeCADGui
import Part

AUDIT = (r"F:\China Graduate Future Flight Vehicle Innovation Competition"
         r"\20_engineering\F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806")
STEP = os.path.join(AUDIT, "03_native_cad",
                    "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_STOWED.step")
RAW = os.path.join(AUDIT, "11_screenshots", "RAW")
OUT = os.path.join(AUDIT, "11_screenshots", "F3R1_FIRST_RENDER_INDEX.json")
W, H = 1920, 1080

rep = {"schema": "F3R1_FIRST_RENDER_V1", "source_step": STEP, "shots": []}
os.makedirs(RAW, exist_ok=True)

doc = FreeCAD.newDocument("F3R1_RENDER")
Part.insert(STEP, doc.Name)
FreeCADGui.updateGui()

gui = FreeCADGui.getDocument(doc.Name)
n_shapes = 0
for o in doc.Objects:
    sh = getattr(o, "Shape", None)
    if sh is not None and not sh.isNull():
        n_shapes += 1
        try:
            gui.getObject(o.Name).Visibility = True
        except Exception:
            pass
rep["objects_with_shape"] = n_shapes

v = FreeCADGui.activeDocument().activeView()
for sid, fn in [("S01_F3R1_STOWED_ISO", "viewAxonometric"),
                ("S02_F3R1_STOWED_TOP", "viewTop"),
                ("S03_F3R1_STOWED_SIDE", "viewRight"),
                ("S04_F3R1_STOWED_FRONT", "viewFront")]:
    getattr(v, fn)()
    FreeCADGui.updateGui()
    FreeCADGui.SendMsgToActiveView("ViewFit")
    FreeCADGui.updateGui()
    p = os.path.join(RAW, sid + "_RAW.png")
    v.saveImage(p, W, H, "White")
    rep["shots"].append({"id": sid, "path": p,
                         "bytes": os.path.getsize(p) if os.path.isfile(p) else 0})
    FreeCAD.Console.PrintMessage("SHOT %s %s\n" % (sid, os.path.getsize(p)))

with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(rep, fh, indent=2, ensure_ascii=False)
FreeCAD.closeDocument(doc.Name)
FreeCADGui.getMainWindow().close()
