"""VENDOR-CAD-03 S3b：Base 组桌面件过滤（用户裁决表 2026-07-27）。

- 删除：01_BASE_Plate（桌面底板；vendor 世界系唯一 z_max<18mm 实体）
- 保留：01_BASE_Link、02_Base_Reinforcement_Part、HM4-75 支柱×4、DM-J4340P、
  轴承（AXK5578/6707ZZ）、销/螺钉——即除底板外全部
- 木工夹/桌面电源不在厂商 STEP 内（叶普查 17 件确认）
输出：vendor_groups/G06_Base_FILTERED.step + design/base_classification.json
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from OCP.BRep import BRep_Builder
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import (STEPControl_AsIs, STEPControl_Reader,
                              STEPControl_Writer)
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS_Compound

HERE = Path(__file__).resolve().parent.parent
NOW = datetime.now(timezone.utc).isoformat()


def solid_bbox(s):
    box = Bnd_Box()
    BRepBndLib.Add_s(s, box)
    return box.Get()  # xmin ymin zmin xmax ymax zmax


def main():
    src = next((HERE / "vendor_groups").glob("G06_Base_*.step"))
    assert "FILTERED" not in src.name
    r = STEPControl_Reader()
    assert r.ReadFile(str(src)) == IFSelect_RetDone
    r.TransferRoots()
    shape = r.OneShape()

    kept, dropped = [], []
    ex = TopExp_Explorer(shape, TopAbs_SOLID)
    while ex.More():
        s = ex.Current()
        xmin, ymin, zmin, xmax, ymax, zmax = solid_bbox(s)
        if zmax < 18.0:   # 桌面底板判据（叶普查：plate 世界 z 3.3..17.8 唯一）
            dropped.append([round(v, 1) for v in (xmin, ymin, zmin, xmax, ymax, zmax)])
        else:
            kept.append(s)
        ex.Next()

    builder = BRep_Builder()
    comp = TopoDS_Compound()
    builder.MakeCompound(comp)
    for s in kept:
        builder.Add(comp, s)
    out = HERE / "vendor_groups/G06_Base_FILTERED.step"
    w = STEPControl_Writer()
    w.Transfer(comp, STEPControl_AsIs)
    w.Write(str(out))

    record = {"id": "VENDORCAD03_BASE_CLASSIFICATION", "generated_utc": NOW,
              "ruling_source": "用户裁决表 2026-07-27（原样保留/条件保留/删除/新建）",
              "deleted": {"01_BASE_Plate": {"criterion": "z_max<18mm(vendor world)",
                                              "solids_dropped": len(dropped),
                                              "bboxes": dropped}},
              "kept_conditional": ["01_BASE_Link", "02_Base_Reinforcement_Part",
                                     "HM4-75 支柱×4（M4 安装模式转接适配器）"],
              "kept_asis": ["DM-J4340P 电机", "AXK5578/6707ZZ 轴承",
                              "PIN-D3L8×2", "KM3-8-XIAO×5"],
              "not_in_step": ["木工夹", "桌面电源及附件（叶普查 17 件无此类）"],
              "yaw_limit_note": "02_Arm_Yaw_Limit 不在 Base 组（若存在应在 Link1 组，"
                                  "本轮原样保留组内不拆）",
              "n_solids_kept": len(kept),
              "output": out.name}
    (HERE / "design/base_classification.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"kept={len(kept)} dropped={len(dropped)} -> {out.name}")


if __name__ == "__main__":
    main()
