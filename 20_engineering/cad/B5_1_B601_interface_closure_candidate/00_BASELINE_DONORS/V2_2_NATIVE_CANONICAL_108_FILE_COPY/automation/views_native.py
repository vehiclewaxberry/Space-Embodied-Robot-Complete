"""NATIVE-01 第一阶段视图：正交/等轴、三向剖视、细节、维护态、爆炸尝试。

SaveBMP 为 B3 已验证路径（1600×1200），随后转 PNG。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

V22_AUTO = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/Space_Embodied_Robot_CAD_V2_2/automation")
sys.path.insert(0, str(V22_AUTO))
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from b3_lib.sw_core import (BuildLog, cast, connect, get_com_member,
                            open_document, rebuild_or_fail)
from build_native import TOP_ASM
from b3_lib.sw_part_factory import FRONT, RIGHT, TOP

ROOT = HERE.parent
VIEWS = ROOT / "views"
NOW = datetime.now(timezone.utc).isoformat()
ORIENT = {"front": 1, "back": 2, "left": 3, "right": 4, "top": 5, "bottom": 6,
          "iso": 7, "trimetric": 8, "dimetric": 9}


def shoot(m, path: Path, orient="iso"):
    m.ShowNamedView2("", ORIENT[orient])
    m.ViewZoomtofit2()
    bmp = path.with_suffix(".bmp")
    ok = m.SaveBMP(str(bmp), 1600, 1200)
    if not ok or not bmp.exists():
        return None
    try:
        from PIL import Image
        Image.open(bmp).convert("RGB").save(path)
        bmp.unlink()
    except Exception:
        return bmp
    return path


def section_on(m, log, plane_names, asm_name):
    """选基准面 → 剖视显示。装配内基准面需 '面名@装配名' 全限定。"""
    m.ClearSelection2(True)
    cands = [f"{nm}@{asm_name}" for nm in plane_names] + list(plane_names)
    for nm in cands:
        if m.Extension.SelectByID2(nm, "PLANE", 0, 0, 0, False, 0, None, 0):
            for meth in ("ViewDisplaySection", "ViewSectionBy",
                          "ViewDisplaySectionView"):
                fn = getattr(m, meth, None)
                if fn is None:
                    continue
                try:
                    fn()
                    return f"OK:{meth}:{nm}"
                except Exception as e:
                    return f"API_FAILED:{meth}:{e}"
            return f"NO_SECTION_API:{nm}"
    return "PLANE_SELECT_FAILED"


def main():
    VIEWS.mkdir(exist_ok=True)
    log = BuildLog("native01_views")
    # 出图必须可见会话：无头模式下 ShowNamedView2 全形式静默失效（本轮实测，
    # 12 种调用形式图像哈希逐位相同）——视角旋转依赖真实图形窗口
    sw = connect(log, visible=True)
    m = open_document(sw, log, ROOT / "Assembly" / f"{TOP_ASM}.SLDASM")
    rec = {"views_id": "NATIVE01_PHASE1_VIEWS", "generated_utc": NOW, "views": []}

    def add(vid, fname, desc, cfg="STOWED", orient="iso", section=None):
        m.ShowConfiguration2(cfg)
        act = cast(m, "IModelDoc2").ConfigurationManager.ActiveConfiguration.Name
        m.ForceRebuild3(False)       # 切配置后必须重建，否则抑制不进图形
        m.GraphicsRedraw2()
        sec_ok = None
        if section:
            sec_ok = section_on(m, log, section, TOP_ASM)
        p = shoot(m, VIEWS / fname, orient)
        if section:
            section_on(m, log, section, TOP_ASM)   # 再次调用=关闭剖视
        rec["views"].append({"id": vid, "file": fname, "config_requested": cfg,
                              "config_active": act, "orientation": orient,
                              "section": bool(section), "section_ok": sec_ok,
                              "description": desc,
                              "saved": bool(p and Path(p).exists())})
        print(vid, fname, "OK" if p else "FAIL")

    add("V01", "v01_top_iso_stowed.png", "顶层装配等轴测（STOWED）")
    add("V02", "v02_front.png", "前视（+X 任务面）", orient="front")
    add("V03", "v03_top.png", "顶视", orient="top")
    add("V04", "v04_right.png", "右视", orient="right")
    add("V05", "v05_section_XY.png", "上视基准面剖视（Y=0，露主结构与安装链）",
        orient="iso", section=TOP)
    add("V06", "v06_section_XZ.png", "前视基准面剖视（Z=0，露三舱与甲板）",
        orient="iso", section=FRONT)
    add("V07", "v07_section_YZ.png", "右视基准面剖视（X=0，露框截面）",
        orient="front", section=RIGHT)
    add("V08", "v08_maintenance_openpanel.png",
        "MAINTENANCE 配置（外板抑制=开盖态，露设备甲板/线束通道）",
        cfg="MAINTENANCE")
    add("V09", "v09_comparator_no_clock.png",
        "STOW_NO_CLOCK_COMPARATOR 配置（收拢支承抑制）",
        cfg="STOW_NO_CLOCK_COMPARATOR")
    add("V10", "v10_stow_25deg_proposal.png",
        "STOW_VENDOR_25DEG_PROPOSAL 配置（鞍座解析）",
        cfg="STOW_VENDOR_25DEG_PROPOSAL", orient="trimetric")

    # 爆炸视图尝试（已知本机组件变换持久性缺陷，fail-closed 如实记录）
    exploded = {"attempted": True, "achieved": False, "reason": ""}
    try:
        asm = cast(m, "IAssemblyDoc")
        cfg = cast(m, "IModelDoc2").ConfigurationManager.ActiveConfiguration
        n = cfg.GetExplodedViewCount()
        exploded["existing_exploded_views"] = int(n)
        exploded["reason"] = ("未创建：本机组件变换持久性缺陷（V2.2 三次复现，"
                               "爆炸视图以组件变换存储，同型风险）；"
                               "改以 MAINTENANCE 抑制态 V08 表达装配层次")
    except Exception as e:
        exploded["reason"] = f"API 不可用: {e}"
    rec["exploded_view"] = exploded
    (ROOT / "evidence").mkdir(exist_ok=True)
    (ROOT / "evidence/phase1_views.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    sw.CloseAllDocuments(True)
    print("views:", sum(1 for v in rec["views"] if v["saved"]), "/", len(rec["views"]))


if __name__ == "__main__":
    main()
