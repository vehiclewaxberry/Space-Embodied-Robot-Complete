"""VENDOR-CAD-03 S8：收拢族对比研究（自审 A 镜头发现后的补课）。

背景：S5a 的 v2 向量把"匹配 120 种子拓扑"当成隐含约束，导致只在越顶折叠族内搜索，
并据此断言"25° 时钟角是必要的"。独立精搜推翻了该断言（无时钟族存在 |Y|≈49mm 解）。
本研究改为公开的多族、多目标扫描，把时钟角当自由变量而非既定结论。

目标（按优先级）：H = 收拢最大 Z（越低越好，因整星盒顶 z=115.15）
约束（fail-closed）：|Y| ≤ 113.15；X ≤ 430；越舱面点 z ≥ 118（避让顶部器件）；
                     必须有越舱面点（否则是纯前伸悬臂，无鞍座支承可能）
评估：厂商组 bbox 角点（8/组）经 T_LG + FK，与 S5a/S6 同一几何源。
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "src"))
import s4_repose as s4

NOW = datetime.now(timezone.utc).isoformat()
LB = np.array([-2.8, -math.pi, -math.pi, -1.87, -1.57, -math.pi])
UB = np.array([2.8, 0.0, 0.0, 1.57, 1.57, math.pi])
Y_LIM, X_LIM, DECK_CLR, DECK_X = 113.15, 430.0, 118.0, 183.0


def corner_sets():
    tr = json.loads((HERE / "design/group_link_transforms.json")
                    .read_text(encoding="utf-8"))["adopted"]
    cen = {f"G{g['index']:02d}": g for g in json.loads(
        (HERE / "design/vendor_group_census.json").read_text(encoding="utf-8"))["groups"]}
    cen["G06"]["bbox_mm"] = {"min": [-70.01, -46.0, 17.3],
                              "max": [70.01, 46.0, 85.96]}   # 底板已删
    out = {}
    for gid, a in tr.items():
        lo = np.array(cen[gid]["bbox_mm"]["min"])
        hi = np.array(cen[gid]["bbox_mm"]["max"])
        c = np.array([[x, y, z] for x in (lo[0], hi[0])
                      for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        out[gid] = (a["urdf_link_frame"],
                    c @ np.array(a["R_rows"]).T + np.array(a["t_mm"]))
    return out


CORN = corner_sets()


def envelope(q, clock):
    frames = s4.link_frames_cs_s(q, clock) if _HAS_CLOCK_ARG else None
    if frames is None:
        frames = _frames_with_clock(q, clock)
    P = [pts @ frames[ln][0].T + frames[ln][1] for ln, pts in CORN.values()]
    return np.vstack(P)


_HAS_CLOCK_ARG = False


def _frames_with_clock(q, clock):
    """复用 s4 的 FK，但时钟角作为参数（不读 JSON）。"""
    import xml.etree.ElementTree as ET
    global _JOINTS
    try:
        joints = _JOINTS
    except NameError:
        root = ET.parse(s4.URDF).getroot()
        joints = {}
        for j in root.findall("joint"):
            o = j.find("origin")
            ax = j.find("axis")
            joints[j.get("name")] = {
                "parent": j.find("parent").get("link"),
                "child": j.find("child").get("link"),
                "xyz": np.array([float(v) for v in
                                 (o.get("xyz") or "0 0 0").split()]) * 1000.0,
                "rpy": [float(v) for v in (o.get("rpy") or "0 0 0").split()],
                "axis": ([float(v) for v in ax.get("xyz").split()]
                          if ax is not None else [0, 0, 1])}
        _JOINTS = joints
    c = math.radians(clock)
    Rz = np.array([[math.cos(c), -math.sin(c), 0],
                   [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    F = {"base_link": (s4.R_SM @ Rz, s4.T_SM_MM.copy())}
    for i, jn in enumerate(["joint1", "joint2", "joint3", "joint4", "joint5",
                             "joint6"]):
        J = joints[jn]
        Rp, pp = F[J["parent"]]
        F[J["child"]] = (Rp @ s4.rpy_to_R(*J["rpy"]) @ s4.rot_axis(J["axis"], q[i]),
                          pp + Rp @ J["xyz"])
    G = joints["gripper_joint"]
    Rp, pp = F[G["parent"]]
    F["gripper_link"] = (Rp @ s4.rpy_to_R(*G["rpy"]), pp + Rp @ G["xyz"])
    return F


def metrics(q, clock):
    P = envelope(q, clock)
    od = P[P[:, 0] < DECK_X]
    return {"max_abs_y": float(np.abs(P[:, 1]).max()),
            "max_x": float(P[:, 0].max()),
            "max_z": float(P[:, 2].max()),
            "min_z": float(P[:, 2].min()),
            "n_over_deck": int(len(od)),
            "min_z_over_deck": (float(od[:, 2].min()) if len(od) else None),
            "min_x": float(P[:, 0].min())}


def cost(q, clock):
    m = metrics(q, clock)
    c = max(0.0, m["max_z"] - 115.15)                  # 主目标：越低越好
    c += 20.0 * max(0.0, m["max_abs_y"] - Y_LIM)       # 硬约束
    c += 20.0 * max(0.0, m["max_x"] - X_LIM)
    if m["n_over_deck"] == 0:
        c += 2000.0                                    # 必须可鞍座支承
    else:
        c += 20.0 * max(0.0, DECK_CLR - m["min_z_over_deck"])
    return c


def descend(q, clock):
    for step in (4.0, 1.0, 0.25):
        for _ in range(3):
            for i in range(6):
                grid = np.arange(LB[i], UB[i] + 1e-9, math.radians(step))
                bv, bc = q[i], cost(q, clock)
                for v in grid:
                    q[i] = v
                    cc = cost(q, clock)
                    if cc < bc - 1e-9:
                        bc, bv = cc, v
                q[i] = bv
    return q, cost(q, clock)


SEEDS = [(0, 0, -180, -107, 0, -99), (0.07, 0, -180, -107, 0, 0),
         (144, -170, -64, -23, -24, -10), (160, -180, -54, -25, -30, 158),
         (0, -90, -90, 0, 0, 0), (90, -90, -90, -60, 0, 0),
         (-90, -90, -90, -60, 0, 0), (0, -180, -90, -90, 0, 0),
         (180, -180, -90, -90, 0, 0), (0, 0, -90, -90, 0, 0)]


def main():
    results = {}
    for clock in (0.0, 25.0):
        best = None
        for s in SEEDS:
            q = np.clip(np.radians(np.array(s, float)), LB + 1e-6, UB - 1e-6)
            qq, cc = descend(q.copy(), clock)
            if best is None or cc < best[0]:
                best = (cc, qq.copy())
        m = metrics(best[1], clock)
        results[f"clock_{clock:g}"] = {
            "cost": round(best[0], 3),
            "q_deg": [round(float(np.degrees(v)), 3) for v in best[1]],
            "metrics": {k: (round(v, 2) if isinstance(v, float) else v)
                         for k, v in m.items()},
            "constraints_met": {
                "y": m["max_abs_y"] <= Y_LIM, "x": m["max_x"] <= X_LIM,
                "deck_clearance": (m["min_z_over_deck"] is not None
                                    and m["min_z_over_deck"] >= DECK_CLR),
                "saddle_supportable": m["n_over_deck"] > 0}}
        print(f"clock={clock:g}: cost={best[0]:.2f} "
              f"maxZ={m['max_z']:.1f} maxY={m['max_abs_y']:.1f} "
              f"maxX={m['max_x']:.1f} q={results[f'clock_{clock:g}']['q_deg']}")

    v2 = json.loads((HERE / "design/b601_stow_joint_vector_v2.json")
                    .read_text(encoding="utf-8"))
    m_v2 = metrics(np.array(v2["q_rad"]), v2["adapter_clock_deg"])
    out = {"study_id": "VENDORCAD03_S8_STOW_FAMILY_STUDY", "generated_utc": NOW,
           "motivation": "自审发现 S5a 隐含地把 120 种子拓扑当约束，并据此断言"
                          "25° 时钟角必要；本研究把时钟角与折叠族都当自由变量重扫",
           "objective": "min max_Z（整星盒顶 z=115.15）s.t. |Y|≤113.15, X≤430, "
                          "越舱面 z≥118, 必须存在越舱面点（可鞍座支承）",
           "results": results,
           "delivered_v2_for_comparison": {
               "q_deg": v2["q_deg"], "clock_deg": v2["adapter_clock_deg"],
               "metrics": {k: (round(v, 2) if isinstance(v, float) else v)
                            for k, v in m_v2.items()}},
           "envelope_finding": {
               "id": "F5_NO_STOWED_Z_ENVELOPE_DEFINED",
               "claim": "冻结输入未定义收拢态 Z 上限；整星主结构盒顶 z=115.15，"
                         "而 110/120/130 全部把臂收在其上方（120 z≈195，"
                         f"130 真实几何 z≈{m_v2['max_z']:.0f}）",
               "status": "UNKNOWN_HOLD（非 FAIL：无冻结判据可违反）",
               "action": "发射包络 Z 需人工裁决后方可判定任一收拢位形合规"}}
    (HERE / "design/stow_family_study.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("delivered v2:", {k: (round(v, 1) if isinstance(v, float) else v)
                             for k, v in m_v2.items()})


if __name__ == "__main__":
    main()
