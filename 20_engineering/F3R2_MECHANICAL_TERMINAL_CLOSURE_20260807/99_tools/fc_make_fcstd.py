# -*- coding: utf-8 -*-
"""FreeCADCmd: wrap the F3R2 STEP into an FCStd document.

env: F3R2_STEP  F3R2_FCSTD
"""
import os

import FreeCAD
import Import

STEP = os.environ["F3R2_STEP"]
OUT = os.environ["F3R2_FCSTD"]

doc = FreeCAD.newDocument("F3R2_OPERATIONAL_BASELINE")
Import.insert(STEP, doc.Name)
n = len([o for o in doc.Objects if getattr(o, "Shape", None) is not None])
doc.recompute()
doc.saveAs(OUT)
print("objects:", n)
print("saved:", OUT, os.path.getsize(OUT), "bytes")
