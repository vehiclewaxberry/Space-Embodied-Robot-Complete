# build_base_adapter.py �?F2 manufacturing pilot: B601_BASE_ADAPTER.FCStd
# Native PartDesign, single solid, skeleton-driven via cross-document expressions.
import os, sys, json
import FreeCAD as App
import Part
import Sketcher

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc_common

SKEL_DOC = "B51R1_MASTER_SKELETON_FREECAD"
SKEL_PATH = os.path.join(fc_common.FA_ROOT, "01_skeleton", SKEL_DOC + ".FCStd")
DOC_NAME = "B601_BASE_ADAPTER"
OUT_FCSTD = os.path.join(fc_common.FA_ROOT, "03_manufacturing_parts", "base_adapter", DOC_NAME + ".FCStd")
SK = SKEL_DOC + "#SSOT_PARAMS."

stage = {"stages": [], "overall": "PASS"}
def st(name, ok, detail=""):
    stage["stages"].append({"name": name, "ok": bool(ok), "detail": detail})
    if not ok:
        stage["overall"] = "FAIL"
    print("STAGE %s: %s %s" % (name, ok, detail))

def build():
    skel = App.openDocument(SKEL_PATH)
    sheet = skel.getObject("SSOT_PARAMS")
    # part-specific pattern params must exist before any expression references them
    if DOC_NAME in App.listDocuments():
        App.closeDocument(DOC_NAME)
    doc = App.newDocument(DOC_NAME)
    doc.Comment = ("B601 base adapter - F2 manufacturing pilot. AL6061-T6 candidate. "
                   "Mass = design estimate EXCLUDED from URDF authority. PRELIMINARY_UNIT_LOAD_ASSESSMENT only.")
    doc.saveAs(OUT_FCSTD)  # cross-document expressions require a saved owner document
    body = doc.addObject("PartDesign::Body", "ADAPTER_BODY")
    body.addProperty("App::PropertyString", "MATERIAL_CANDIDATE").MATERIAL_CANDIDATE = "AL6061-T6"
    body.addProperty("App::PropertyString", "STOCK_FORM").STOCK_FORM = "sawn plate 170x170x14"
    body.addProperty("App::PropertyString", "DATUM_SCHEME").DATUM_SCHEME = "A=bottom face; B=XZ center plane; C=YZ center plane"
    body.addProperty("App::PropertyString", "TOLERANCE_PLACEHOLDER").TOLERANCE_PLACEHOLDER = "ISO 2768-mK general; interface holes H7/position TBD"
    body.addProperty("App::PropertyString", "SURFACE_FINISH").SURFACE_FINISH = "Ra3.2 general; Ra1.6 interface faces"
    body.addProperty("App::PropertyString", "MFG_ROUTE").MFG_ROUTE = "CNC 3-axis, 2 setups"
    body.addProperty("App::PropertyString", "MASS_AUTHORITY").MASS_AUTHORITY = "DESIGN_ESTIMATE_ONLY_EXCLUDED_FROM_URDF"

    # ---- 1. base plate 160x160x12, top at Z=0 (pad downward) ----
    sk = body.newObject("Sketcher::SketchObject", "SK_PLATE")
    sk.MapMode = "Deactivated"
    LX, LY = 160.0, 160.0
    pts = [(-LX/2, -LY/2), (LX/2, -LY/2), (LX/2, LY/2), (-LX/2, LY/2)]
    geo = [Part.LineSegment(App.Vector(*pts[i], 0), App.Vector(*pts[(i+1) % 4], 0)) for i in range(4)]
    for g in geo:
        sk.addGeometry(g, False)
    for i in range(4):
        sk.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i+1) % 4, 1))
    sk.addConstraint(Sketcher.Constraint("Horizontal", 0)); sk.addConstraint(Sketcher.Constraint("Horizontal", 2))
    sk.addConstraint(Sketcher.Constraint("Vertical", 1)); sk.addConstraint(Sketcher.Constraint("Vertical", 3))
    c_px = sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, -LX/2)); sk.renameConstraint(c_px, "PX")
    c_py = sk.addConstraint(Sketcher.Constraint("DistanceY", 0, 1, -LY/2)); sk.renameConstraint(c_py, "PY")
    c_lx = sk.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, LX)); sk.renameConstraint(c_lx, "LX")
    c_ly = sk.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, LY)); sk.renameConstraint(c_ly, "LY")
    sk.setExpression("Constraints.PX", "-(" + SK + "BASE_PLATE_LX)/2")
    sk.setExpression("Constraints.PY", "-(" + SK + "BASE_PLATE_LY)/2")
    sk.setExpression("Constraints.LX", SK + "BASE_PLATE_LX")
    sk.setExpression("Constraints.LY", SK + "BASE_PLATE_LY")
    st("sketch_plate_solve", sk.solve() == 0, "solver rc=%d" % sk.solve())
    doc.recompute()
    st("sketch_plate_fully_constrained", sk.FullyConstrained, "DOF=%d" % sk.solve() if hasattr(sk, "solve") else "")

    pad = body.newObject("PartDesign::Pad", "PLATE_PAD")
    pad.Profile = sk
    pad.Length = 12.0
    pad.Reversed = True  # downward: top face at Z=0
    pad.setExpression("Length", SK + "BASE_PLATE_T")
    doc.recompute()
    st("plate_pad", pad.Shape.Solids and len(pad.Shape.Solids) == 1, "vol=%.1f mm^3" % pad.Shape.Volume)

    # ---- 2. central boss D100 x 15 on plate top ----
    skb = body.newObject("Sketcher::SketchObject", "SK_BOSS")
    skb.MapMode = "Deactivated"
    skb.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 50.0), False)
    cb = skb.addConstraint(Sketcher.Constraint("Coincident", 0, 3, -1, 1))  # center on origin
    cb_r = skb.addConstraint(Sketcher.Constraint("Radius", 0, 50.0)); skb.renameConstraint(cb_r, "R_BOSS")
    skb.setExpression("Constraints.R_BOSS", SK + "B601_INTERFACE_DIA/2")
    doc.recompute()
    st("sketch_boss_fully_constrained", skb.FullyConstrained, "")

    padb = body.newObject("PartDesign::Pad", "BOSS_PAD")
    padb.Profile = skb
    padb.Length = 15.0
    padb.setExpression("Length", "15")
    doc.recompute()
    st("boss_pad_single_solid", len(padb.Shape.Solids) == 1, "vol=%.1f" % padb.Shape.Volume)

    # ---- 3. central harness bore D40 through boss + plate ----
    skh = body.newObject("Sketcher::SketchObject", "SK_BORE")
    skh.MapMode = "Deactivated"
    skh.Placement.Base.z = 15.0
    skh.addGeometry(Part.Circle(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 20.0), False)
    skh.addConstraint(Sketcher.Constraint("Coincident", 0, 3, -1, 1))
    ch_r = skh.addConstraint(Sketcher.Constraint("Radius", 0, 20.0)); skh.renameConstraint(ch_r, "R_BORE")
    skh.setExpression("Constraints.R_BORE", "40/2")
    doc.recompute()
    pock = body.newObject("PartDesign::Pocket", "BORE_POCKET")
    pock.Profile = skh
    pock.Length = 27.0  # 15 boss + 12 plate
    doc.recompute()
    st("central_bore", len(pock.Shape.Solids) == 1, "vol=%.1f" % pock.Shape.Volume)

    # ---- 4. arm-flange hole pattern: 4x D9 on BCD130, through boss+plate ----
    skf = body.newObject("Sketcher::SketchObject", "SK_HOLES_FLANGE")
    skf.MapMode = "Deactivated"
    skf.Placement.Base.z = 15.0
    centers = [(65.0, 0.0), (0.0, 65.0), (-65.0, 0.0), (0.0, -65.0)]
    for i, (cx, cy) in enumerate(centers):
        skf.addGeometry(Part.Circle(App.Vector(cx, cy, 0), App.Vector(0, 0, 1), 4.5), False)
        cx_c = skf.addConstraint(Sketcher.Constraint("DistanceX", i, 3, cx)); skf.renameConstraint(cx_c, "HX%d" % i)
        cy_c = skf.addConstraint(Sketcher.Constraint("DistanceY", i, 3, cy)); skf.renameConstraint(cy_c, "HY%d" % i)
        cr = skf.addConstraint(Sketcher.Constraint("Radius", i, 4.5)); skf.renameConstraint(cr, "HR%d" % i)
        skf.setExpression("Constraints.HX%d" % i, "%sBCD_FLANGE/2*(%d)" % (SK, 1 if cx >= 0 else -1) if cy == 0 else "0")
        skf.setExpression("Constraints.HY%d" % i, "%sBCD_FLANGE/2*(%d)" % (SK, 1 if cy >= 0 else -1) if cx == 0 else "0")
        skf.setExpression("Constraints.HR%d" % i, "9/2")
    doc.recompute()
    st("sketch_flange_holes_fully_constrained", skf.FullyConstrained, "")
    pockf = body.newObject("PartDesign::Pocket", "FLANGE_HOLES")
    pockf.Profile = skf
    pockf.Length = 27.0
    doc.recompute()
    st("flange_holes", len(pockf.Shape.Solids) == 1, "vol=%.1f" % pockf.Shape.Volume)

    # ---- 5. spacecraft corner holes: 4x D6.6 at (+-70,+-70), through plate ----
    skc = body.newObject("Sketcher::SketchObject", "SK_HOLES_CORNER")
    skc.MapMode = "Deactivated"
    corners = [(70.0, 70.0), (70.0, -70.0), (-70.0, 70.0), (-70.0, -70.0)]
    for i, (cx, cy) in enumerate(corners):
        skc.addGeometry(Part.Circle(App.Vector(cx, cy, 0), App.Vector(0, 0, 1), 3.3), False)
        cx_c = skc.addConstraint(Sketcher.Constraint("DistanceX", i, 3, cx)); skc.renameConstraint(cx_c, "CX%d" % i)
        cy_c = skc.addConstraint(Sketcher.Constraint("DistanceY", i, 3, cy)); skc.renameConstraint(cy_c, "CY%d" % i)
        cr = skc.addConstraint(Sketcher.Constraint("Radius", i, 3.3)); skc.renameConstraint(cr, "CR%d" % i)
        skc.setExpression("Constraints.CX%d" % i, "%sCORNER_PATTERN/2*(%d)" % (SK, 1 if cx > 0 else -1))
        skc.setExpression("Constraints.CY%d" % i, "%sCORNER_PATTERN/2*(%d)" % (SK, 1 if cy > 0 else -1))
        skc.setExpression("Constraints.CR%d" % i, "6.6/2")
    doc.recompute()
    st("sketch_corner_holes_fully_constrained", skc.FullyConstrained, "")
    pockc = body.newObject("PartDesign::Pocket", "CORNER_HOLES")
    pockc.Profile = skc
    pockc.Length = 12.0
    doc.recompute()
    st("corner_holes", len(pockc.Shape.Solids) == 1, "vol=%.1f" % pockc.Shape.Volume)

    # ---- 6. two dowel pin holes D6 x 8 deep on boss face ----
    skd = body.newObject("Sketcher::SketchObject", "SK_DOWEL")
    skd.MapMode = "Deactivated"
    skd.Placement.Base.z = 15.0
    for i, cx in enumerate((25.0, -25.0)):
        skd.addGeometry(Part.Circle(App.Vector(cx, 0, 0), App.Vector(0, 0, 1), 3.0), False)
        dx = skd.addConstraint(Sketcher.Constraint("DistanceX", i, 3, cx)); skd.renameConstraint(dx, "DX%d" % i)
        dy = skd.addConstraint(Sketcher.Constraint("DistanceY", i, 3, 0.0)); skd.renameConstraint(dy, "DY%d" % i)
        dr = skd.addConstraint(Sketcher.Constraint("Radius", i, 3.0)); skd.renameConstraint(dr, "DR%d" % i)
        skd.setExpression("Constraints.DX%d" % i, "25*(%d)" % (1 if cx > 0 else -1))
        skd.setExpression("Constraints.DR%d" % i, "6/2")
    doc.recompute()
    st("sketch_dowel_fully_constrained", skd.FullyConstrained, "")
    pockd = body.newObject("PartDesign::Pocket", "DOWEL_HOLES")
    pockd.Profile = skd
    pockd.Length = 8.0
    doc.recompute()
    st("dowel_holes", len(pockd.Shape.Solids) == 1, "vol=%.1f" % pockd.Shape.Volume)

    # ---- 7. ribs: triangular stiffeners on XZ and YZ planes ----
    for name, plane in (("XZ", App.Rotation()), ("YZ", App.Rotation(App.Vector(0, 0, 1), 90))):
        skr = body.newObject("Sketcher::SketchObject", "SK_RIB_" + name)
        skr.MapMode = "Deactivated"
        skr.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(1, 0, 0), 90))
        if name == "YZ":
            skr.Placement = App.Placement(App.Vector(0, 0, 0), App.Rotation(App.Vector(1, 1, 1), 120))
        # triangle: (49,0) -> (80,0) -> (49,20) in local XY (local X = world X or Y, local Y = world Z)
        v = [(49.0, 0.0), (80.0, 0.0), (49.0, 20.0)]
        for i in range(3):
            skr.addGeometry(Part.LineSegment(App.Vector(v[i][0], v[i][1], 0), App.Vector(v[(i+1) % 3][0], v[(i+1) % 3][1], 0)), False)
        for i in range(3):
            skr.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i+1) % 3, 1))
        skr.addConstraint(Sketcher.Constraint("Horizontal", 0))
        skr.addConstraint(Sketcher.Constraint("Vertical", 2))
        c0 = skr.addConstraint(Sketcher.Constraint("DistanceY", 0, 1, 0.0)); skr.renameConstraint(c0, "RIB_BASE_Z")
        c1 = skr.addConstraint(Sketcher.Constraint("DistanceX", 2, 2, 49.0)); skr.renameConstraint(c1, "RIB_INNER")
        c2 = skr.addConstraint(Sketcher.Constraint("DistanceX", 0, 2, 80.0)); skr.renameConstraint(c2, "RIB_OUTER")
        c3 = skr.addConstraint(Sketcher.Constraint("DistanceY", 1, 2, 20.0)); skr.renameConstraint(c3, "RIB_H")
        skr.setExpression("Constraints.RIB_INNER", SK + "B601_INTERFACE_DIA/2-1")
        skr.setExpression("Constraints.RIB_OUTER", SK + "BASE_PLATE_LX/2")
        doc.recompute()
        st("sketch_rib_%s_fully_constrained" % name, skr.FullyConstrained, "")
        padr = body.newObject("PartDesign::Pad", "RIB_" + name)
        padr.Profile = skr
        padr.Length = 8.0
        padr.Midplane = True
        doc.recompute()
        st("rib_%s_single_solid" % name, len(padr.Shape.Solids) == 1, "vol=%.1f" % padr.Shape.Volume)

    # ---- 8. harness slot through plate edge ----
    sks = body.newObject("Sketcher::SketchObject", "SK_SLOT")
    sks.MapMode = "Deactivated"
    sks.Placement.Base.z = -12.0  # plate bottom, cut upward
    sw, sh = 40.0, 12.0
    sx, sy = 0.0, 74.0  # breaks plate edge at y=80
    pts = [(sx - sw/2, sy - sh/2), (sx + sw/2, sy - sh/2), (sx + sw/2, sy + sh/2), (sx - sw/2, sy + sh/2)]
    for i in range(4):
        sks.addGeometry(Part.LineSegment(App.Vector(pts[i][0], pts[i][1], 0), App.Vector(pts[(i+1) % 4][0], pts[(i+1) % 4][1], 0)), False)
    for i in range(4):
        sks.addConstraint(Sketcher.Constraint("Coincident", i, 2, (i+1) % 4, 1))
    sks.addConstraint(Sketcher.Constraint("Horizontal", 0)); sks.addConstraint(Sketcher.Constraint("Horizontal", 2))
    sks.addConstraint(Sketcher.Constraint("Vertical", 1)); sks.addConstraint(Sketcher.Constraint("Vertical", 3))
    cpx = sks.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, sx - sw/2)); sks.renameConstraint(cpx, "SLOT_PX")
    cpy = sks.addConstraint(Sketcher.Constraint("DistanceY", 0, 1, sy - sh/2)); sks.renameConstraint(cpy, "SLOT_PY")
    csw = sks.addConstraint(Sketcher.Constraint("DistanceX", 0, 1, 0, 2, sw)); sks.renameConstraint(csw, "SLOT_W")
    csh = sks.addConstraint(Sketcher.Constraint("DistanceY", 1, 1, 1, 2, sh)); sks.renameConstraint(csh, "SLOT_H")
    sks.setExpression("Constraints.SLOT_PX", "-40/2")
    sks.setExpression("Constraints.SLOT_W", "40")
    sks.setExpression("Constraints.SLOT_H", "12")
    sks.setExpression("Constraints.SLOT_PY", SK + "BASE_PLATE_LY/2-12")
    st("sketch_slot_solve", sks.solve() == 0, "solver rc=%d" % sks.solve())
    doc.recompute()
    st("sketch_slot_fully_constrained", sks.FullyConstrained, "")
    pocks = body.newObject("PartDesign::Pocket", "HARNESS_SLOT")
    pocks.Profile = sks
    pocks.Length = 12.0
    pocks.Reversed = True
    doc.recompute()
    st("harness_slot", len(pocks.Shape.Solids) == 1, "vol=%.1f" % pocks.Shape.Volume)

    doc.recompute()
    final = body.Shape
    st("final_single_solid", len(final.Solids) == 1, "solids=%d" % len(final.Solids))
    st("final_valid", final.isValid(), "")
    bb = final.BoundBox
    stage["bbox_mm"] = {"x": [round(bb.XMin, 3), round(bb.XMax, 3)],
                        "y": [round(bb.YMin, 3), round(bb.YMax, 3)],
                        "z": [round(bb.ZMin, 3), round(bb.ZMax, 3)]}
    stage["volume_mm3"] = round(final.Volume, 3)
    density_al = 2.70e-6  # kg/mm^3 AL6061-T6
    stage["mass_kg_design_estimate_AL6061T6"] = round(final.Volume * density_al, 4)
    solid0 = final.Solids[0]
    stage["com_mm"] = [round(solid0.CenterOfMass.x, 3), round(solid0.CenterOfMass.y, 3), round(solid0.CenterOfMass.z, 3)]

    doc.saveAs(OUT_FCSTD)
    App.closeDocument(DOC_NAME)
    return doc

def _alias_exists(sheet, alias):
    try:
        sheet.get(alias)
        return True
    except Exception:
        return False

def _append_param(sheet, name, value, unit):
    row = 2
    while True:
        try:
            v = sheet.get("A%d" % row)
        except Exception:
            v = None
        if v in (None, ""):
            break
        row += 1
    sheet.set("A%d" % row, name)
    sheet.set("B%d" % row, value)
    sheet.set("C%d" % row, unit)
    sheet.setAlias("B%d" % row, name)

if __name__ == "__main__" or True:
    build()
    stage["fcstd"] = OUT_FCSTD
    stage["fcstd_sha256"] = fc_common.sha256_file(OUT_FCSTD) if os.path.isfile(OUT_FCSTD) else None
    path = fc_common.write_json(stage, "build_base_adapter_result.json")
    print("RESULT_JSON=" + path)
    print(json.dumps(stage, indent=2, ensure_ascii=False))
