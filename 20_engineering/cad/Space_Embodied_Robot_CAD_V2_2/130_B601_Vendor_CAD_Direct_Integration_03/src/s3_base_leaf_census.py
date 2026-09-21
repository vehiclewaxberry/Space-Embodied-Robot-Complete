"""VENDOR-CAD-03 S3a：Base 组叶件普查（识别桌面固定件用）。"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.TDF import TDF_Label, TDF_LabelSequence
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFDoc import XCAFDoc_DocumentTool

HERE = Path(__file__).resolve().parent.parent
NOW = datetime.now(timezone.utc).isoformat()
VENDOR_STEP = Path(r"F:/Robotic arm/High_performance_robotics_arm/vendor/reBot-DevArm/hardware/reBot_B601_DM/reBot_B601_DM_v1.1_20260425.step")


def label_name(label: TDF_Label) -> str:
    attr = TDataStd_Name()
    if label.FindAttribute(TDataStd_Name.GetID_s(), attr):
        return TCollection_ExtendedString(attr.Get()).ToExtString()
    return "UNNAMED"


def walk(st, label, path, out, depth=0, max_depth=6):
    name = label_name(label)
    ref = TDF_Label()
    target = label
    if st.GetReferredShape_s(label, ref):
        target = ref
    subs = TDF_LabelSequence()
    st.GetComponents_s(target, subs)
    if subs.Length() == 0 or depth >= max_depth:
        shape = st.GetShape_s(label)
        box = Bnd_Box()
        BRepBndLib.Add_s(shape, box)
        xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
        out.append({"path": path + [name],
                     "bbox_mm": [round(v, 1) for v in
                                 (xmin, ymin, zmin, xmax, ymax, zmax)]})
        return
    for s in range(1, subs.Length() + 1):
        walk(st, subs.Value(s), path + [name], out, depth + 1, max_depth)


def main():
    doc = TDocStd_Document(TCollection_ExtendedString("doc"))
    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    assert reader.ReadFile(str(VENDOR_STEP)) == IFSelect_RetDone
    assert reader.Transfer(doc)
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    roots = TDF_LabelSequence()
    st.GetFreeShapes(roots)
    leaves = []
    for r in range(1, roots.Length() + 1):
        comps = TDF_LabelSequence()
        st.GetComponents_s(roots.Value(r), comps)
        for c in range(1, comps.Length() + 1):
            comp = comps.Value(c)
            if label_name(comp).startswith("Base"):
                walk(st, comp, [], leaves)
    (HERE / "design/base_leaf_census.json").write_text(
        json.dumps({"id": "VENDORCAD03_BASE_LEAF_CENSUS", "generated_utc": NOW,
                     "n_leaves": len(leaves), "leaves": leaves},
                    ensure_ascii=False, indent=2), encoding="utf-8")
    for l in leaves:
        print("/".join(l["path"][1:]), l["bbox_mm"])


if __name__ == "__main__":
    main()
