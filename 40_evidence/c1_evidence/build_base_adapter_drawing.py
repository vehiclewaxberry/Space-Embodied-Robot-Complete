# build_base_adapter_drawing.py — TechDraw drawing doc for B601_BASE_ADAPTER (console).
import os, sys, json, traceback
import FreeCAD as App

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fc_common

ADAPTER = os.path.join(fc_common.FA_ROOT, "03_manufacturing_parts", "base_adapter", "B601_BASE_ADAPTER.FCStd")
DOC_NAME = "B601_BASE_ADAPTER_DRAWING"
OUT_FCSTD = os.path.join(fc_common.FA_ROOT, "05_drawings", DOC_NAME + ".FCStd")
TEMPLATE = r"G:\Windows_program_file\FreeCAD\data\Mod\TechDraw\Templates\ISO\A4_Landscape_ISO5457_advanced.svg"

res = {"stages": [], "overall": "PASS"}
def st(name, ok, detail=""):
    res["stages"].append({"name": name, "ok": bool(ok), "detail": detail})
    if not ok:
        res["overall"] = "FAIL"
    print("STAGE %s: %s %s" % (name, ok, detail))

def build():
    src = App.openDocument(ADAPTER)
    body = src.getObject("ADAPTER_BODY")
    if DOC_NAME in App.listDocuments():
        App.closeDocument(DOC_NAME)
    doc = App.newDocument(DOC_NAME)
    doc.saveAs(OUT_FCSTD)
    # self-contained snapshot: avoids cross-doc lost-link; drawing authority stays with part doc
    snap = doc.addObject("Part::Feature", "ADAPTER_SNAPSHOT")
    snap.Shape = body.Shape.copy()
    snap.addProperty("App::PropertyString", "SNAPSHOT_NOTE").SNAPSHOT_NOTE = \
        "Geometry snapshot for drawing only; authority = B601_BASE_ADAPTER.FCStd"
    body = snap
    page = doc.addObject("TechDraw::DrawPage", "PAGE_A4")
    tmpl = doc.addObject("TechDraw::DrawSVGTemplate", "TEMPLATE")
    tmpl.Template = TEMPLATE
    page.Template = tmpl
    try:
        tmpl.setEditFieldContent("TITLE-NAME", "B601 BASE ADAPTER - F2 PILOT")
    except Exception:
        pass

    views = []

    def add_view(name, direction, x, y, scale=1.0):
        v = doc.addObject("TechDraw::DrawViewPart", name)
        v.Source = [body]
        v.Direction = App.Vector(*direction)
        v.X = x
        v.Y = y
        v.ScaleType = "Custom"
        v.Scale = scale
        page.addView(v)
        views.append(name)
        return v

    add_view("VIEW_FRONT", (0, -1, 0), 105.0, 100.0, 0.8)
    add_view("VIEW_TOP", (0, 0, -1), 105.0, 190.0, 0.8)
    add_view("VIEW_RIGHT", (1, 0, 0), 200.0, 100.0, 0.8)
    add_view("VIEW_ISO", (1, -1, 1), 250.0, 190.0, 0.6)

    try:
        sec = doc.addObject("TechDraw::DrawViewSection", "VIEW_SECTION_AA")
        sec.Source = [body]
        front = doc.getObject("VIEW_FRONT")
        sec.BaseView = front
        sec.SectionNormal = App.Vector(1.0, 0.0, 0.0)
        sec.SectionOrigin = App.Vector(0.0, 0.0, 0.0)
        sec.X = 200.0
        sec.Y = 190.0
        sec.ScaleType = "Custom"
        sec.Scale = 0.8
        page.addView(sec)
        views.append("VIEW_SECTION_AA")
        st("section_view", True, "A-A via SectionNormal +X")
    except Exception:
        st("section_view", False, traceback.format_exc())

    doc.recompute()
    doc.save()
    st("drawing_doc_saved", os.path.isfile(OUT_FCSTD), OUT_FCSTD)
    res["views"] = views
    App.closeDocument(src.Name)
    return doc

if __name__ == "__main__" or True:
    try:
        build()
    except Exception:
        st("build", False, traceback.format_exc())
    path = fc_common.write_json(res, "build_base_adapter_drawing_result.json")
    print("RESULT_JSON=" + path)
