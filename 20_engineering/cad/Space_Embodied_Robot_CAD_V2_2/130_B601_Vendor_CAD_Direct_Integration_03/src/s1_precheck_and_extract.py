"""VENDOR-CAD-03 S0+S1：入口锁 + 厂商整臂 STEP 结构化抽取（XCAF）。

原则（用户指令 2026-07-27）：
1. 使用已登记厂商 STEP（哈希 87a0537d…），禁止重新下载/静默换版；
2. 120_ 目录只读（运动学证据）；本目录为唯一写区；
3. 按 URDF link 分组抽取真实厂商实体（8 顶层组，vendor 装配位形原样）；
4. MASS_AUTHORITY=EXCLUDED（accepted URDF 唯一质量/惯量权威）。
"""
from __future__ import annotations

import gc
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_Label, TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.TopAbs import TopAbs_SOLID
from OCP.TopExp import TopExp_Explorer
from OCP.XCAFDoc import XCAFDoc_DocumentTool

HERE = Path(__file__).resolve().parent.parent
V22 = HERE.parent
NOW = datetime.now(timezone.utc).isoformat()

VENDOR_STEP = Path(r"F:/Robotic arm/High_performance_robotics_arm/vendor/reBot-DevArm/hardware/reBot_B601_DM/reBot_B601_DM_v1.1_20260425.step")
VENDOR_SHA = "87a0537d1afd50c04fc441fde11dd4f2ebbb368fe27f6c10fda8567be696d968"
URDF = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf")
URDF_SHA = "1bc2b7483cd8025d08ba6eadfd9e1f3b0477121714e7cf4ddc1794d9e471c164"


def sha256(p: Path):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def label_name(label: TDF_Label) -> str:
    attr = TDataStd_Name()
    if label.FindAttribute(TDataStd_Name.GetID_s(), attr):
        return TCollection_ExtendedString(attr.Get()).ToExtString()
    return "UNNAMED"


def shape_stats(shape):
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box)
    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    n = 0
    ex = TopExp_Explorer(shape, TopAbs_SOLID)
    while ex.More():
        n += 1
        ex.Next()
    return {"n_solids": n,
            "bbox_mm": {"min": [round(xmin, 2), round(ymin, 2), round(zmin, 2)],
                         "max": [round(xmax, 2), round(ymax, 2), round(zmax, 2)]}}


def main():
    # S0 入口锁：登记源逐位复核（fail-closed）
    v_sha, u_sha = sha256(VENDOR_STEP), sha256(URDF)
    lock = {"lock_id": "VENDORCAD03_S0_INPUT_LOCK", "generated_utc": NOW,
            "no_redownload_rule": "只用已登记厂商 STEP；任何换版必须显式人工裁决",
            "vendor_step": {"path": str(VENDOR_STEP), "sha256": v_sha,
                             "match": v_sha == VENDOR_SHA},
            "accepted_urdf": {"path": str(URDF), "sha256": u_sha,
                               "match": u_sha == URDF_SHA},
            "posemap02_readonly": "120_B601_Geometry_and_PoseMap_02 封存为运动学证据，不覆盖",
            "mass_authority": "EXCLUDED_URDF_ONLY"}
    (HERE / "validation").mkdir(exist_ok=True)
    (HERE / "validation/s0_input_lock.json").write_text(
        json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")
    if not (lock["vendor_step"]["match"] and lock["accepted_urdf"]["match"]):
        raise SystemExit("S0 FAIL: 登记源哈希不匹配，停止（fail-closed）")

    # S1 XCAF 读入 + 顶层组抽取
    doc = TDocStd_Document(TCollection_ExtendedString("doc"))
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    if reader.ReadFile(str(VENDOR_STEP)) != IFSelect_RetDone:
        raise SystemExit("STEP read failed")
    if not reader.Transfer(doc):
        raise SystemExit("STEP transfer failed")
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

    roots = TDF_LabelSequence()
    st.GetFreeShapes(roots)
    census = {"census_id": "VENDORCAD03_S1_GROUP_CENSUS", "generated_utc": NOW,
              "n_roots": roots.Length(), "groups": []}
    (HERE / "vendor_groups").mkdir(exist_ok=True)
    gi = 0
    for r in range(1, roots.Length() + 1):
        root = roots.Value(r)
        comps = TDF_LabelSequence()
        st.GetComponents_s(root, comps)
        for c in range(1, comps.Length() + 1):
            comp = comps.Value(c)
            gi += 1
            name = label_name(comp)
            ref = TDF_Label()
            sub_names = []
            if st.GetReferredShape_s(comp, ref):
                if label_name(ref) != name:
                    sub_names.append({"ref_name": label_name(ref)})
                subs = TDF_LabelSequence()
                st.GetComponents_s(ref, subs)
                for s in range(1, subs.Length() + 1):
                    sub_names.append(label_name(subs.Value(s)))
            shape = st.GetShape_s(comp)  # 含装配位置（vendor 世界系）
            stats = shape_stats(shape)
            safe = "".join(ch if ch.isalnum() or ch in "-_" else "_"
                           for ch in name)[:48]
            out = HERE / f"vendor_groups/G{gi:02d}_{safe}.step"
            w = STEPControl_Writer()
            w.Transfer(shape, STEPControl_AsIs)
            w.Write(str(out))
            census["groups"].append({"index": gi, "name": name,
                                      "depth2": sub_names, **stats,
                                      "extracted_step": out.name,
                                      "frame": "VENDOR_ASSEMBLY_WORLD"})
            print(f"G{gi:02d} {name}: solids={stats['n_solids']} -> {out.name}")
            gc.collect()
    (HERE / "design").mkdir(exist_ok=True)
    (HERE / "design/vendor_group_census.json").write_text(
        json.dumps(census, ensure_ascii=False, indent=2), encoding="utf-8")
    print("groups:", gi)


if __name__ == "__main__":
    main()
