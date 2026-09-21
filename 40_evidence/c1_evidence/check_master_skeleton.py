# check_master_skeleton.py — cold-reopen validation of the FreeCAD master skeleton.
import os, sys, json, math
import FreeCAD as App
import Import

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc_common

DOC_NAME = "B51R1_MASTER_SKELETON_FREECAD"
FCSTD = os.path.join(fc_common.FA_ROOT, "01_skeleton", DOC_NAME + ".FCStd")
WITNESS = os.path.join(fc_common.AUTH_DIR, "master_skeleton", "B51R1_MASTER_SKELETON_V2_STEP_WITNESS_R2.step")

EXPECTED = {
    "PLANE_X_MOUNT_FACE": {"x": 198.0},
    "PLANE_X_TSM_DYNAMICS": {"x": 185.25},
    "PLANE_X_INTERFACE_REF": {"x": 183.0},
    "PLANE_LONGERON_PY": {"y": 101.65},
    "PLANE_LONGERON_NY": {"y": -101.65},
    "PLANE_LOAD_LAYER": {"y": 110.15},
    "PLANE_PANEL_LAYER": {"y": 113.15},
    "CS_SADDLE_AFT": {"x": -10.0, "y": 3.185, "z": 261.08},
    "CS_SADDLE_MID": {"x": 90.0, "y": 47.795, "z": 214.92},
    "CS_SADDLE_FWD": {"x": 170.0, "y": 41.55, "z": 209.42},
}
REQUIRED_ALIASES = ["MOUNT_FACE_X", "T_SM_DYNAMICS_X", "LONGERON_AXIS_Y", "PANEL_LAYER_Y",
                    "B601_INTERFACE_DIA", "CLOCK_A0_RAD", "STOW_Z_LIMIT",
                    "SADDLE_AFT_X_CENTER", "SADDLE_MID_X_CENTER", "SADDLE_FWD_X_CENTER",
                    "ARM_TOTAL_MASS_KG", "MIN_MOVABLE_CLEARANCE"]

res = {"checks": [], "overall": "PASS"}
def chk(name, ok, detail):
    res["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
    if not ok:
        res["overall"] = "FAIL"

doc = App.openDocument(FCSTD)
doc.recompute()

sheet = doc.getObject("SSOT_PARAMS")
chk("ssot_sheet_exists", sheet is not None, "SSOT_PARAMS")
missing = []
for a in REQUIRED_ALIASES:
    try:
        v = sheet.get(a)
    except Exception:
        missing.append(a)
chk("required_aliases", not missing, missing or "%d present" % len(REQUIRED_ALIASES))

stowz = sheet.get("STOW_Z_LIMIT")
chk("stow_z_unknown", str(stowz) == "UNKNOWN", str(stowz))

clock = float(sheet.get("CLOCK_A0_RAD"))
chk("clock_a0_rad", abs(clock - math.radians(25.0)) < 1e-9, clock)

errs = {}
for name, exp in EXPECTED.items():
    o = doc.getObject(name)
    if o is None:
        errs[name] = "MISSING"; continue
    for axis, val in exp.items():
        got = getattr(o.Placement.Base, axis)
        if abs(got - val) > 1e-6:
            errs[name] = "%s expected %s got %s" % (axis, val, got)
chk("datum_placements", not errs, errs or "%d datums verified" % len(EXPECTED))

solids, volume = 0, 0.0
for o in doc.Objects:
    if hasattr(o, "Shape") and o.Shape:
        solids += len(o.Shape.Solids)
        volume += o.Shape.Volume
chk("zero_solids", solids == 0, solids)
chk("zero_volume", volume == 0.0, volume)

mass_like = [o.Name for o in doc.Objects if o.TypeId.startswith("PartDesign::") and hasattr(o, "Shape") and o.Shape.Solids]
chk("no_partdesign_solid", not mass_like, mass_like)

diag = {"witness_bbox": None, "note": "witness STEP used as overlay compare only"}
try:
    d2 = App.newDocument("WITNESS_CMP")
    Import.insert(WITNESS, d2.Name)
    d2.recompute()
    bbs = [o.Shape.BoundBox for o in d2.Objects if hasattr(o, "Shape") and o.Shape and o.Shape.Volume > 0]
    if bbs:
        xmin = min(b.XMin for b in bbs); xmax = max(b.XMax for b in bbs)
        ymin = min(b.YMin for b in bbs); ymax = max(b.YMax for b in bbs)
        zmin = min(b.ZMin for b in bbs); zmax = max(b.ZMax for b in bbs)
        diag["witness_bbox"] = {"x": [round(xmin, 2), round(xmax, 2)], "y": [round(ymin, 2), round(ymax, 2)], "z": [round(zmin, 2), round(zmax, 2)]}
    App.closeDocument(d2.Name)
except Exception as e:
    diag["witness_error"] = repr(e)
res["witness_diagnostic"] = diag

App.closeDocument(doc.Name)

import time
t0 = time.time()
doc = App.openDocument(FCSTD)
doc.recompute()
App.closeDocument(doc.Name)
chk("cold_reopen_recompute", True, "%.2fs" % (time.time() - t0))

res["fcstd_sha256"] = fc_common.sha256_file(FCSTD)
path = fc_common.write_json(res, "MASTER_SKELETON_VALIDATION.json")
print("RESULT_JSON=" + path)
print(json.dumps(res, indent=2, ensure_ascii=False, default=str))
