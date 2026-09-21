"""VENDOR-CAD-03 S5a：真实几何收拢向量重拟合（v2，CANDIDATE_HOLD）。

发现：120 候选向量在真实厂商几何下 STOW Y_max=154.7 > ±113.15 整星半宽。
目标改为包络驱动：min max|Y|（真实组角点 FK 解析评估），约束：
- 越顶：跨舱面（X<183）组角点 z ≥ 118（舱顶 113.15 + ~5 净空）
- X 包络：≤ 430（厂商折叠参考）；Z 上限惩罚（发射包络高度）
- 保持越顶族拓扑（初值=120 向量；限位内坐标下降）
评估器：组世界角点 = FK_link(q)∘T_LG ∘ (census bbox 8 角点)——解析、无需变换实体。
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import s4_repose as s4

HERE = Path(__file__).resolve().parent.parent
NOW = datetime.now(timezone.utc).isoformat()


def load_inputs():
    adopted = json.loads((HERE / "design/group_link_transforms.json")
                         .read_text(encoding="utf-8"))["adopted"]
    census = {f"G{g['index']:02d}": g for g in json.loads(
        (HERE / "design/vendor_group_census.json").read_text(encoding="utf-8"))["groups"]}
    # G06 用过滤后包络（叶普查：底板已删 → y ±46 为主导，z 17.3..86）
    census["G06"]["bbox_mm"] = {"min": [-70.01, -46.0, 17.3],
                                  "max": [70.01, 46.0, 85.96]}
    corners = {}
    for gid, a in adopted.items():
        lo = np.array(census[gid]["bbox_mm"]["min"])
        hi = np.array(census[gid]["bbox_mm"]["max"])
        c = np.array([[x, y, z] for x in (lo[0], hi[0])
                      for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        R_l, t_l = np.array(a["R_rows"]), np.array(a["t_mm"])
        corners[gid] = {"link": a["urdf_link_frame"],
                         "pts_link": c @ R_l.T + t_l}   # 预转入连杆局部系
    return corners


def world_corners(corners, q):
    frames = s4.link_frames_cs_s(q)
    out = {}
    for gid, c in corners.items():
        R, p = frames[c["link"]]
        out[gid] = c["pts_link"] @ R.T + p
    return out


def metrics(corners, q):
    wc = world_corners(corners, q)
    allp = np.vstack(list(wc.values()))
    over_deck = allp[allp[:, 0] < 183.0]
    return {"max_abs_y": float(np.abs(allp[:, 1]).max()),
            "max_x": float(allp[:, 0].max()),
            "max_z": float(allp[:, 2].max()),
            "min_z_over_deck": (float(over_deck[:, 2].min())
                                  if len(over_deck) else None),
            "per_group_y": {g: round(float(np.abs(p[:, 1]).max()), 1)
                             for g, p in wc.items()}}


def cost(corners, q):
    m = metrics(corners, q)
    c = m["max_abs_y"]                                   # 主目标
    c += 5.0 * max(0.0, m["max_x"] - 430.0)              # X 包络
    c += 0.2 * max(0.0, m["max_z"] - 340.0)              # 高度软惩罚
    if m["min_z_over_deck"] is not None:
        c += 5.0 * max(0.0, 118.0 - m["min_z_over_deck"])  # 舱面净空硬惩罚
    return c


def main():
    corners = load_inputs()
    stow120 = json.loads(
        (HERE.parent / "120_B601_Geometry_and_PoseMap_02/design/b601_stow_joint_vector.json")
        .read_text(encoding="utf-8"))
    q0 = np.array(stow120["q_rad"], float)
    lb = np.array([-2.8, -math.pi, -math.pi, -1.87, -1.57, -math.pi])
    ub = np.array([2.8, 0.0, 0.0, 1.57, 1.57, math.pi])

    m_before = metrics(corners, q0)
    q = q0.copy()
    for step_deg in (5.0, 2.0, 0.5):
        for _sweep in range(3):
            for i in range(6):
                grid = np.arange(lb[i], ub[i] + 1e-9, math.radians(step_deg))
                best_v, best_c = q[i], cost(corners, q)
                for v in grid:
                    q[i] = v
                    cc = cost(corners, q)
                    if cc < best_c - 1e-9:
                        best_c, best_v = cc, v
                q[i] = best_v
    m_after = metrics(corners, q)

    out = {"vector_id": "B601_STOW_JOINT_VECTOR_V2_REAL_GEOMETRY",
           "generated_utc": NOW,
           "adapter_clock_deg": s4._clock_deg(),
           "STOW_VECTOR_STATUS": "CANDIDATE_HOLD",
           "objective": "min max|Y|（真实厂商组角点包络）s.t. 越顶净空/X 包络/高度",
           "basis": "120 候选为初值；F1 不可达/F3 限位饱和结论不变；"
                     "本 v2 仍非 accepted，正式向量需人工批准",
           "q_rad": [round(float(v), 6) for v in q],
           "q_deg": [round(math.degrees(float(v)), 3) for v in q],
           "metrics_before_120_vector": {k: (round(v, 2) if isinstance(v, float)
                                              else v)
                                           for k, v in m_before.items()},
           "metrics_after": {k: (round(v, 2) if isinstance(v, float) else v)
                              for k, v in m_after.items()},
           "acceptance_frame": "走廊重定义（用户 2026-07-27）：|Y|≤113.15 余量制；"
                                 "旧 |Y|≤40 保留为 120 负发现不作为通过条件"}
    (HERE / "design/b601_stow_joint_vector_v2.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("before:", {k: v for k, v in m_before.items() if k != "per_group_y"})
    print("after :", {k: v for k, v in m_after.items() if k != "per_group_y"})
    print("q_deg v2:", out["q_deg"])


if __name__ == "__main__":
    main()
