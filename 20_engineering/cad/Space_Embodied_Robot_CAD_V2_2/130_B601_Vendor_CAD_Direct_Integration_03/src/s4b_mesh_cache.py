"""VENDOR-CAD-03 S4b：厂商组粗网格缓存（vendor 世界系；接触测量+视图渲染共用）。

缓存放 scratchpad（派生二进制不入库树）；线性挠度 2mm 足够工程视图与
mm 级接触测量。逐组处理 + gc，控制峰值内存。
"""
from __future__ import annotations

import gc
import json
import os
from pathlib import Path

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS

HERE = Path(__file__).resolve().parent.parent
SCRATCH = Path(os.environ.get("CLAUDE_SCRATCHPAD",
    r"C:/Users/stude/AppData/Local/Temp/claude/F--China-Graduate-Future-Flight-Vehicle-Innovation-Competition/f82d04fc-7dca-4a0f-ac0b-f39116f6b403/scratchpad")) / "vendorcad03"
SCRATCH.mkdir(parents=True, exist_ok=True)


def mesh_group(step_path: Path):
    r = STEPControl_Reader()
    assert r.ReadFile(str(step_path)) == IFSelect_RetDone
    r.TransferRoots()
    shape = r.OneShape()
    BRepMesh_IncrementalMesh(shape, 2.0, False, 0.5, True)
    verts_all, tris_all = [], []
    off = 0
    ex = TopExp_Explorer(shape, TopAbs_FACE)
    while ex.More():
        face = TopoDS.Face_s(ex.Current())
        loc = TopLoc_Location()
        tri = BRep_Tool.Triangulation_s(face, loc)
        if tri is not None:
            trsf = loc.Transformation()
            n = tri.NbNodes()
            pts = np.empty((n, 3))
            for i in range(1, n + 1):
                p = tri.Node(i).Transformed(trsf)
                pts[i - 1] = (p.X(), p.Y(), p.Z())
            m = tri.NbTriangles()
            idx = np.empty((m, 3), dtype=np.int64)
            for i in range(1, m + 1):
                t = tri.Triangle(i)
                idx[i - 1] = (t.Value(1) - 1, t.Value(2) - 1, t.Value(3) - 1)
            verts_all.append(pts.astype(np.float32))
            tris_all.append(idx + off)
            off += n
        ex.Next()
    v = np.vstack(verts_all) if verts_all else np.zeros((0, 3), np.float32)
    t = np.vstack(tris_all) if tris_all else np.zeros((0, 3), np.int64)
    return v, t


def main():
    adopted = json.loads((HERE / "design/group_link_transforms.json")
                         .read_text(encoding="utf-8"))["adopted"]
    cache = {}
    for gid, a in adopted.items():
        fname = ("G06_Base_FILTERED.step" if gid == "G06" else a["extracted_step"])
        v, t = mesh_group(HERE / "vendor_groups" / fname)
        cache[f"{gid}_v"] = v
        cache[f"{gid}_t"] = t
        print(gid, fname, "verts:", len(v), "tris:", len(t))
        gc.collect()
    np.savez_compressed(SCRATCH / "mesh_cache.npz", **cache)
    print("cache ->", SCRATCH / "mesh_cache.npz")


if __name__ == "__main__":
    main()
