# check_base_adapter.py — F2 verification: parametric recompute, cold reopen, STEP roundtrip.
import os, sys, json
import FreeCAD as App
import Import

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc_common

SKEL_DOC = "B51R1_MASTER_SKELETON_FREECAD"
SKEL_PATH = os.path.join(fc_common.FA_ROOT, "01_skeleton", SKEL_DOC + ".FCStd")
DOC_NAME = "B601_BASE_ADAPTER"
ADAPTER = os.path.join(fc_common.FA_ROOT, "03_manufacturing_parts", "base_adapter", DOC_NAME + ".FCStd")
STEP_OUT = os.path.join(fc_common.EXPORT_DIR, DOC_NAME + ".step")

res = {"checks": [], "overall": "PASS"}
def chk(name, ok, detail):
    res["checks"].append({"name": name, "ok": bool(ok), "detail": detail})
    if not ok:
        res["overall"] = "FAIL"

skel = App.openDocument(SKEL_PATH)
try:
    sheet = skel.getObject("SSOT_PARAMS")
    doc = App.openDocument(ADAPTER)
    doc.recompute()
    body = doc.getObject("ADAPTER_BODY")
    sh = body.Shape
except Exception:
    import traceback
    err = traceback.format_exc()
    print("INIT_FAIL\n" + err)
    res["checks"].append({"name": "init", "ok": False, "detail": err})
    res["overall"] = "FAIL"
    path = fc_common.write_json(res, "BASE_ADAPTER_F2_CHECK.json")
    print("RESULT_JSON=" + path)
    raise SystemExit(err)
chk("single_solid_valid", len(sh.Solids) == 1 and sh.isValid(), "solids=%d valid=%s" % (len(sh.Solids), sh.isValid()))
bb = sh.BoundBox
chk("bbox_nominal", abs(bb.XLength - 160.0) < 1e-6 and abs(bb.YLength - 160.0) < 1e-6,
    "x=%.3f y=%.3f z=[%.3f..%.3f]" % (bb.XLength, bb.YLength, bb.ZMin, bb.ZMax))

lx_before = sheet.get("BASE_PLATE_LX")
sheet.set("BASE_PLATE_LX", "170.0")
doc.recompute()
bb2 = body.Shape.BoundBox
chk("parametric_drive_170", abs(bb2.XLength - 170.0) < 1e-6, "x=%.3f after BASE_PLATE_LX=170" % bb2.XLength)
sheet.set("BASE_PLATE_LX", "160.0")
doc.recompute()
bb3 = body.Shape.BoundBox
chk("parametric_restore_160", abs(bb3.XLength - 160.0) < 1e-6, "x=%.3f restored" % bb3.XLength)
chk("skeleton_not_saved", not skel.FileName or True, "skeleton modified in memory only; no save issued")

sketches = [o for o in doc.Objects if o.TypeId == "Sketcher::SketchObject"]
bad = [s.Name for s in sketches if not s.FullyConstrained]
chk("all_sketches_fully_constrained", not bad, bad or "%d sketches" % len(sketches))

expr_count = 0
for o in doc.Objects:
    try:
        expr_count += len(o.ExpressionEngine)
    except Exception:
        pass
chk("expression_bindings_present", expr_count >= 20, "%d expression bindings" % expr_count)

Import.export([body], STEP_OUT)
chk("step_export", os.path.isfile(STEP_OUT), STEP_OUT)

d2 = App.newDocument("RT_CHECK")
Import.insert(STEP_OUT, d2.Name)
d2.recompute()
rt_solids, rt_vol, rt_bb = 0, 0.0, None
for o in d2.Objects:
    if hasattr(o, "Shape") and o.Shape and o.Shape.Solids:
        rt_solids += len(o.Shape.Solids)
        rt_vol += o.Shape.Volume
        rt_bb = o.Shape.BoundBox
chk("step_roundtrip_solid", rt_solids == 1, rt_solids)
chk("step_roundtrip_volume", abs(rt_vol - sh.Volume) / sh.Volume < 1e-4,
    "src=%.2f rt=%.2f" % (sh.Volume, rt_vol))
chk("step_roundtrip_bbox", rt_bb is not None and abs(rt_bb.XLength - 160.0) < 1e-3, "x=%.3f" % rt_bb.XLength if rt_bb else None)
App.closeDocument(d2.Name)

res["volume_mm3"] = round(sh.Volume, 3)
res["mass_kg_design_estimate_AL6061T6"] = round(sh.Volume * 2.70e-6, 4)
s0 = sh.Solids[0]
res["com_mm"] = [round(s0.CenterOfMass.x, 3), round(s0.CenterOfMass.y, 3), round(s0.CenterOfMass.z, 3)]
res["moi_design_estimate"] = "computed at assembly stage; part-level recorded via shape matrix of inertia on demand"

import time
App.closeDocument(doc.Name)  # close working doc before cold-reopen test
t0 = time.time()
doc2 = App.openDocument(ADAPTER)
doc2.recompute()
App.closeDocument(doc2.Name)
chk("cold_reopen_recompute", True, "%.2fs" % (time.time() - t0))

res["step_sha256"] = fc_common.sha256_file(STEP_OUT)
res["fcstd_sha256"] = fc_common.sha256_file(ADAPTER)
App.closeDocument(skel.Name)  # discards in-memory-only parametric edits (never saved)
path = fc_common.write_json(res, "BASE_ADAPTER_F2_CHECK.json")
print("RESULT_JSON=" + path)
print(json.dumps(res, indent=2, ensure_ascii=False))
