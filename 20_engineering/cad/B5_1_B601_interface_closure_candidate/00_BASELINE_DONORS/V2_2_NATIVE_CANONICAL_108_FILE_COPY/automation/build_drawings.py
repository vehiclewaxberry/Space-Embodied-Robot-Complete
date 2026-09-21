"""NATIVE-01 原生工程图（.SLDDRW）——真正的 SolidWorks 视觉交付。

背景（D-NATIVE-02）：本机 SaveBMP 渲染固定内部相机，视角 API 全失效，
无法用截图给出可信的 SolidWorks 视图。工程图是另一条完全原生的路径：
标准三视图 + 等轴测由 Create3rdAngleViews2 生成，剖视由 CreateSectionViewAt5
在图纸上真实切出，导出 PDF/SLDDRW 皆为原生产物（非 Python 渲染）。

用法：python build_drawings.py [config]
"""
from __future__ import annotations

import glob
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

V22_AUTO = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/automation")
sys.path.insert(0, str(V22_AUTO))
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from b3_lib.sw_core import (BuildLog, cast, connect, get_com_member,
                            open_document, rebuild_or_fail, save_as,
                            set_custom_properties)
from build_native import TOP_ASM
import native_spec as S

ROOT = HERE.parent
DRW = ROOT / "drawings"
NOW = datetime.now(timezone.utc).isoformat()


def drawing_template(sw):
    p = sw.GetUserPreferenceStringValue(26)      # swDefaultTemplateDrawing
    if p and os.path.isfile(p):
        return p
    for d in (r"C:\ProgramData\SolidWorks\SOLIDWORKS *\templates",):
        for pat in ("gb_a2.drwdot", "gb_a1.drwdot", "gb_a3.drwdot", "*.drwdot"):
            m = glob.glob(os.path.join(d, pat))
            if m:
                return m[0]
    raise RuntimeError("找不到工程图模板")


def main():
    cfg = sys.argv[1] if len(sys.argv) > 1 else "STOWED"
    DRW.mkdir(exist_ok=True)
    log = BuildLog(f"native01_drawing_{cfg}")
    sw = connect(log, visible=True)
    asm_path = ROOT / "Assembly" / f"{TOP_ASM}.SLDASM"

    # 先把装配切到目标配置并保存，使工程图取到该配置
    m = open_document(sw, log, asm_path)
    m.ShowConfiguration2(cfg)
    act = cast(m, "IModelDoc2").ConfigurationManager.ActiveConfiguration.Name
    if act != cfg:
        log.fail("配置激活失败", config=cfg)
    # 治理：图框「重量」栏会自动取 SolidWorks 按默认密度算的质量（实测 6.159kg），
    # 与 MASS_AUTHORITY=EXCLUDED 冲突（唯一权威=accepted URDF 4.6955559493429862kg）。
    # 用自定义属性覆盖，杜绝无权威质量数字随图流出。
    set_custom_properties(m, log, {
        "Weight": "EXCLUDED", "重量": "EXCLUDED",
        "SW-Mass": "EXCLUDED",
        "MASS_AUTHORITY": "EXCLUDED_ACCEPTED_URDF_ONLY",
        "MASS_NOTE": "SolidWorks 默认密度质量无权威，不得引用；"
                      "B601 质量 4.6955559493429862kg 在 accepted URDF"})
    m.ForceRebuild3(False)
    m.Save3(1, None, None)
    # 模型文档保持打开——CreateDrawViewFromModelView3 需要模型已加载

    tpl = drawing_template(sw)
    d = sw.NewDocument(tpl, 0, 0, 0)
    if d is None:
        d = sw.ActiveDoc
    if d is None:
        log.fail("NewDocument(drawing) 未返回文档", template=tpl)
    d = cast(d, "IModelDoc2")
    log.event("DRW_NEW", template=tpl)
    dd = cast(d, "IDrawingDoc")

    rec = {"id": "NATIVE01_DRAWING", "generated_utc": NOW, "config": cfg,
           "template": tpl, "model": str(asm_path), "views": [], "sections": []}

    # 逐视图放置（Create3rdAngleViews2 在本机返回 false 且零视图，实测不可用）
    layout = [("*前视", "*Front", 0.12, 0.30), ("*上视", "*Top", 0.12, 0.12),
              ("*右视", "*Right", 0.34, 0.30), ("*等轴测", "*Isometric", 0.34, 0.12)]
    placed = []
    for cn, en, x, y in layout:
        v = None
        for nm in (cn, en):
            try:
                v = dd.CreateDrawViewFromModelView3(str(asm_path), nm, x, y, 0.0)
            except Exception:
                v = None
            if v is not None:
                placed.append((nm, v))
                break
        log.event("VIEW_PLACED", view=cn, ok=v is not None)
    rec["create_3rd_angle_views"] = False
    rec["n_placed"] = len(placed)
    rebuild_or_fail(d, log, "std_views")

    # 枚举生成的视图
    sheet = cast(dd.GetCurrentSheet(), "ISheet")
    names = list(sheet.GetViews() or [])
    for v in names:
        vv = cast(v, "IView")
        rec["views"].append({"name": get_com_member(vv, "GetName2"),
                             "type": int(vv.Type),
                             "scale": float(vv.ScaleDecimal)})
    log.event("VIEWS_ENUM", n=len(rec["views"]))

    # 剖视：在第一个正交视图上画一条水平线并切剖
    try:
        base = None
        for v in names:
            vv = cast(v, "IView")
            if int(vv.Type) == 3:       # swDrawingNamedView / 正交
                base = vv
                break
        if base is None and names:
            base = cast(names[0], "IView")
        if base is not None:
            d.ClearSelection2(True)
            dd.ActivateView(get_com_member(base, "GetName2"))
            op = base.Position           # 视图中心（图纸坐标 m）
            sk = d.SketchManager
            sk.InsertSketch(True)
            sk.CreateLine(op[0] - 0.15, op[1], 0.0, op[0] + 0.15, op[1], 0.0)
            sk.InsertSketch(True)
            sec = dd.CreateSectionViewAt5(op[0] + 0.20, op[1] - 0.16, 0.0,
                                          "A", 0, None, 0)
            rec["sections"].append({"label": "A-A", "created": bool(sec),
                                     "base_view": get_com_member(base, "GetName2")})
            log.event("SECTION", created=bool(sec))
    except Exception as e:
        rec["sections"].append({"label": "A-A", "created": False, "error": str(e)})
        log.event("SECTION_FAILED", error=str(e))

    # 图框「重量」栏链接的是系统属性 SW-Mass，自定义属性覆盖不掉（实测）。
    # 进入图框编辑态，把链接了质量的注释文本直接改为 EXCLUDED——
    # 杜绝无权威质量数字随图流出。
    blanked = []
    try:
        dd.EditTemplate()
        ann = d.Extension.GetFirstAnnotation2()
        while ann is not None:
            a = cast(ann, "IAnnotation")
            nxt = a.GetNext3()
            try:
                if int(a.GetType()) == 3:          # swNote
                    nt = cast(get_com_member(a, "GetSpecificAnnotation"), "INote")
                    raw = str(get_com_member(nt, "GetText") or "")
                    if ("SW-Mass" in raw or "Weight" in raw
                            or "质量" in raw or "重量" in raw):
                        nt.SetText("EXCLUDED")
                        blanked.append(raw[:60])
            except Exception:
                pass
            ann = nxt
        dd.EditSheet()
    except Exception as e:
        rec["titleblock_mass_blank_error"] = str(e)
    rec["titleblock_mass_fields_blanked"] = blanked

    # 图面注释：权威与限制声明（随图流出，防止脱离上下文误用）
    try:
        d.ClearSelection2(True)
        nt = d.InsertNote(
            "NATIVE-01 PHASE1 REVIEW DRAWING — NOT FOR MANUFACTURE\n"
            "MASS_AUTHORITY = EXCLUDED (accepted URDF only; title-block weight void)\n"
            "NO MATERIAL / NO TOLERANCE / NO STRENGTH CLAIM\n"
            f"CONFIG = {cfg}   STOW_VECTOR = CANDIDATE_HOLD   STOW_Z_LIMIT = UNKNOWN")
        if nt is not None:
            n2 = cast(nt, "INote")
            n2.SetTextJustification(1)
            ann = cast(get_com_member(n2, "GetAnnotation"), "IAnnotation")
            ann.SetPosition(0.02, 0.40, 0.0)
            rec["note_inserted"] = True
    except Exception as e:
        rec["note_inserted"] = False
        rec["note_error"] = str(e)

    set_custom_properties(d, log, S.props(
        f"NATIVE01_DRAWING_{cfg}", "NATIVE_DRAWING", "PHASE1_REVIEW", "SW_BUILDER",
        S.CLAIM, TOP_ASM,
        extra={"CONFIG": cfg, "PURPOSE": "第一阶段评审用原生工程图（非制造图）",
               "DIMENSIONS": "未标注——按任务书不定义公差/制造",
               "Weight": "EXCLUDED", "重量": "EXCLUDED", "SW-Mass": "EXCLUDED"}))
    rebuild_or_fail(d, log, "drawing")
    out = DRW / f"NATIVE01_{cfg}.SLDDRW"
    save_as(d, log, out, overwrite=True)
    pdf = DRW / f"NATIVE01_{cfg}.pdf"
    d.SaveAs3(str(pdf), 0, 0)
    rec["outputs"] = {"slddrw": out.name, "slddrw_exists": out.exists(),
                       "pdf": pdf.name, "pdf_exists": pdf.exists(),
                       "pdf_bytes": pdf.stat().st_size if pdf.exists() else 0}
    (ROOT / "evidence").mkdir(exist_ok=True)
    (ROOT / f"evidence/drawing_{cfg}.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    sw.CloseAllDocuments(True)
    print(json.dumps({"config": cfg, "views": len(rec["views"]),
                      "sections": rec["sections"], "outputs": rec["outputs"]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
