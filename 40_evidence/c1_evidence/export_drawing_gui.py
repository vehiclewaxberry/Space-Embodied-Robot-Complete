# export_drawing_gui.py �?GUI session: render TechDraw page to PDF + SVG + DXF.
# Run with FreeCAD.exe (GUI), not FreeCADCmd. FreeCAD 1.1.3 API: exportPageAsPdf/Svg.
import os, sys, json, traceback
import FreeCAD as App

RESULT = {"pdf": None, "svg": None, "dxf": None, "errors": []}
try:
    MIG = r"F:\Space-Embodied-Robot-Complete_FREECAD_MIGRATION_20260803"
    FA = os.path.join(MIG, "20_engineering", "cad", "freecad_authoritative")
    ADAPTER = os.path.join(FA, "03_manufacturing_parts", "base_adapter", "B601_BASE_ADAPTER.FCStd")
    DRAW = os.path.join(FA, "05_drawings", "B601_BASE_ADAPTER_DRAWING.FCStd")
    EXP = os.path.join(FA, "07_exports")
    os.makedirs(EXP, exist_ok=True)

    src = App.openDocument(ADAPTER)  # open source first so cross-doc links resolve
    doc = App.openDocument(DRAW)
    body = src.getObject("ADAPTER_BODY")
    rebound = 0
    for o in doc.Objects:
        if o.TypeId in ("TechDraw::DrawViewPart", "TechDraw::DrawViewSection"):
            o.Source = [body]
            rebound += 1
    doc.recompute()
    doc.save()
    RESULT["views_rebound"] = rebound
    page = doc.getObject("PAGE_A4")
    import FreeCADGui as Gui
    import TechDrawGui
    import TechDraw

    pdf_path = os.path.join(EXP, "B601_BASE_ADAPTER.pdf")
    try:
        TechDrawGui.exportPageAsPdf(page, pdf_path)
        RESULT["pdf"] = pdf_path if os.path.isfile(pdf_path) else None
    except Exception:
        RESULT["errors"].append("pdf: " + traceback.format_exc())

    svg_path = os.path.join(EXP, "B601_BASE_ADAPTER.svg")
    try:
        TechDrawGui.exportPageAsSvg(page, svg_path)
        RESULT["svg"] = svg_path if os.path.isfile(svg_path) else None
    except Exception:
        RESULT["errors"].append("svg: " + traceback.format_exc())

    dxf_path = os.path.join(EXP, "B601_BASE_ADAPTER.dxf")
    try:
        TechDraw.writeDXFPage(page, dxf_path)
        RESULT["dxf"] = dxf_path if os.path.isfile(dxf_path) else None
    except Exception:
        RESULT["errors"].append("dxf: " + traceback.format_exc())

    out = os.path.join(FA, "08_verification", "drawing_export_gui_result.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(RESULT, f, indent=2, ensure_ascii=False)
    for name in list(App.listDocuments().keys()):
        App.closeDocument(name)
except Exception:
    RESULT["errors"].append("top: " + traceback.format_exc())
    print(json.dumps(RESULT, indent=2, ensure_ascii=False))

import FreeCADGui as Gui
Gui.getMainWindow().close()
