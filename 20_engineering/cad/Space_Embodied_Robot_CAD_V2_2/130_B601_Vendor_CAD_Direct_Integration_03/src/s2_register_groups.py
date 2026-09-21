"""VENDOR-CAD-03 S2：厂商组（vendor 世界系）→ URDF 连杆局部系刚体配准。

方法：24 个轴向旋转候选 × 包围盒中心平移；残差 = 8 角点最大偏差。
真值：URDF STL（连杆局部系，单位自检测）。Gripper 组对 gripper_link+left+right
合并网格（滑移关节零位）。输出 T_LG（p_L = R·p_G + t）+ 残差 + 歧义裕度。
"""
from __future__ import annotations

import itertools
import json
import struct
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.IFSelect import IFSelect_RetDone
from OCP.STEPControl import STEPControl_Reader
from OCP.TopAbs import TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS

HERE = Path(__file__).resolve().parent.parent
NOW = datetime.now(timezone.utc).isoformat()
MESH = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/spacecraft_layout/arm_b601_v1/meshes_b601_gripper")

MAPPING = {  # 厂商组名（census）→ URDF 连杆
    "G01": ("Link1:1", ["link1"]), "G02": ("Link2:1", ["link2"]),
    "G03": ("Link3:1", ["link3"]), "G04": ("Link4:1", ["link4"]),
    "G05": ("Link6:1", ["link6"]), "G06": ("Base:1", ["base_link"]),
    "G07": ("Link5:1", ["link5"]),
    "G08": ("Gripper:1", ["gripper_link", "gripper_left", "gripper_right"]),
}
# gripper_left/right 相对 gripper_link 的原点（URDF gripper_joint1/2 origin，
# 滑移零位）——由 S2 运行时从 URDF 读出，不硬编码。


def read_stl_vertices(p: Path) -> np.ndarray:
    data = p.read_bytes()
    if data[:5].lower() == b"solid" and b"facet" in data[:500]:
        verts = []
        for line in data.decode(errors="ignore").splitlines():
            t = line.split()
            if t and t[0] == "vertex":
                verts.append([float(t[1]), float(t[2]), float(t[3])])
        v = np.array(verts)
    else:
        n = struct.unpack_from("<I", data, 80)[0]
        arr = np.frombuffer(data, dtype=np.uint8, count=n * 50, offset=84)
        rec = arr.reshape(n, 50)
        tri = rec[:, 12:48].copy().view("<f4").reshape(n, 3, 3)
        v = tri.reshape(-1, 3).astype(float)
    # 单位自检测：ROS 网格常为米
    if np.max(np.abs(v)) < 10.0:
        v = v * 1000.0
    return v


def read_step_vertices(p: Path) -> np.ndarray:
    r = STEPControl_Reader()
    if r.ReadFile(str(p)) != IFSelect_RetDone:
        raise RuntimeError(p.name)
    r.TransferRoots()
    shape = r.OneShape()
    verts = []
    ex = TopExp_Explorer(shape, TopAbs_VERTEX)
    while ex.More():
        pt = BRep_Tool.Pnt_s(TopoDS.Vertex_s(ex.Current()))
        verts.append([pt.X(), pt.Y(), pt.Z()])
        ex.Next()
    return np.array(verts)


def axis_rotations():
    mats = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product((1, -1), repeat=3):
            R = np.zeros((3, 3))
            for i, (p_, s_) in enumerate(zip(perm, signs)):
                R[i, p_] = s_
            if np.linalg.det(R) > 0.5:
                mats.append(R)
    return mats  # 24


def bbox(v):
    return v.min(axis=0), v.max(axis=0)


def corners(lo, hi):
    return np.array([[a, b, c] for a in (lo[0], hi[0])
                     for b in (lo[1], hi[1]) for c in (lo[2], hi[2])])


def _subsample(v, n=2000, seed=7):
    rng = np.random.default_rng(seed)   # 固定种子=确定性
    idx = rng.choice(len(v), size=min(n, len(v)), replace=False)
    return v[idx]


def _nn_mean(a, b):
    """a 每点到 b 的最近距离均值（分块暴力，2000×2000 级）。"""
    d2 = ((a[:, None, :] - b[None, :, :]) ** 2).sum(-1)
    return float(np.sqrt(d2.min(axis=1)).mean())


def register(gv, lv):
    """bbox 粗筛 24 旋转 → 最近邻均距精判（可分辨翻转/镜像歧义）→ 平移微调。"""
    lo_l, hi_l = bbox(lv)
    c_l = (lo_l + hi_l) / 2
    corn_l = corners(lo_l, hi_l)
    coarse = []
    for R in axis_rotations():
        gv_r_box = gv @ R.T
        lo_g, hi_g = bbox(gv_r_box)
        t = c_l - (lo_g + hi_g) / 2
        corn_g = corners(lo_g + t, hi_g + t)
        resid = float(np.max(np.linalg.norm(corn_g - corn_l, axis=1)))
        coarse.append((resid, R, t))
    coarse.sort(key=lambda x: x[0])
    cutoff = coarse[0][0] + 20.0
    shortlist = [c for c in coarse if c[0] <= cutoff][:8]

    gs, ls_ = _subsample(gv), _subsample(lv)
    fine = []
    for resid_box, R, t0 in shortlist:
        pts = gs @ R.T + t0
        t = t0.copy()
        for _ in range(2):      # 两步平移微调（NN 均移）
            d2 = ((pts[:, None, :] - ls_[None, :, :]) ** 2).sum(-1)
            nn = ls_[d2.argmin(axis=1)]
            dt = (nn - pts).mean(axis=0)
            t = t + dt
            pts = pts + dt
        score = _nn_mean(pts, ls_)
        fine.append((score, resid_box, R, t))
    fine.sort(key=lambda x: x[0])
    best = fine[0]
    second = fine[1] if len(fine) > 1 else (float("inf"), 0, None, None)
    return {"R_rows": best[2].tolist(),
            "t_mm": [round(float(x), 3) for x in best[3]],
            "nn_mean_mm": round(best[0], 3),
            "bbox_corner_residual_mm": round(best[1], 3),
            "second_best_nn_mm": (round(second[0], 3)
                                    if np.isfinite(second[0]) else None),
            "ambiguity_margin_mm": (round(second[0] - best[0], 3)
                                     if np.isfinite(second[0]) else None),
            "n_rotation_candidates_screened": len(shortlist)}


def main():
    import xml.etree.ElementTree as ET
    urdf = ET.parse(r"F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf").getroot()
    grip_off = {}
    for j in urdf.findall("joint"):
        if j.get("name") in ("gripper_joint1", "gripper_joint2"):
            child = j.find("child").get("link")
            o = j.find("origin")
            grip_off[child] = np.array(
                [float(x) for x in (o.get("xyz") or "0 0 0").split()]) * 1000.0

    out = {"registration_id": "VENDORCAD03_S2_GROUP_LINK_REGISTRATION",
           "generated_utc": NOW, "convention": "p_link = R @ p_vendor + t (mm)",
           "method": "24 轴向旋转 × bbox 中心平移；残差=8 角点最大偏差",
           "groups": {}}
    for gid, (gname, links) in MAPPING.items():
        gstep = next((HERE / "vendor_groups").glob(f"{gid}_*.step"))
        gv = read_step_vertices(gstep)
        lvs = []
        for ln in links:
            v = read_stl_vertices(MESH / f"{ln}.STL")
            if ln in grip_off:
                v = v + grip_off[ln]  # 合并到 gripper_link 局部系（滑移零位）
            lvs.append(v)
        lv = np.vstack(lvs)
        reg = register(gv, lv)
        reg.update({"vendor_group": gname, "urdf_links": links,
                    "n_step_vertices": int(len(gv)),
                    "n_stl_vertices": int(len(lv)),
                    "extracted_step": gstep.name})
        out["groups"][gid] = reg
        print(f"{gid} {gname:11s} -> {'+'.join(links):40s} "
              f"nn={reg['nn_mean_mm']:8.3f} box={reg['bbox_corner_residual_mm']:8.3f} "
              f"margin={reg['ambiguity_margin_mm']}")
    (HERE / "design/group_link_registration.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
