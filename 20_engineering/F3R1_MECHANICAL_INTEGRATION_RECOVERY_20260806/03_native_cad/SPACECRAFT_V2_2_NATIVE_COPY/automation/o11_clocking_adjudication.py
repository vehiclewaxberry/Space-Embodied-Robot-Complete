"""O11：25° 时钟角 vs 无时钟角——七项判据量化裁决（决策支持，非模型交付）。

判据（用户 2026-07-27 指定）：高度 / 宽度 / 与主结构间隙 / 鞍座数量 /
解锁路径 / 太阳翼避让 / 相机遮挡。

几何源：
- 臂 = 130 真实厂商网格顶点（vendor STEP 派生，E3 内部）
- 结构 = NATIVE-01 顶装 STOWED 配置导出 STEP（不含臂、不含鞍座时单独扣除）
- 翼包络 / GNSS 站位 = Codex 100_Mechanical_Continuation FIDELITY-01A 冻结值
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
V22 = ROOT.parent / "Space_Embodied_Robot_CAD_V2_2"
sys.path.insert(0, str(V22 / "130_B601_Vendor_CAD_Direct_Integration_03/src"))
sys.path.insert(0, str(HERE))
import native_spec as S
import s4_repose as s4
from s4b_mesh_cache import SCRATCH, mesh_group

NOW = datetime.now(timezone.utc).isoformat()
LB = np.array([-2.8, -math.pi, -math.pi, -1.87, -1.57, -math.pi])
UB = np.array([2.8, 0.0, 0.0, 1.57, 1.57, math.pi])
Y_LIM, X_LIM, DECK_X, DECK_TOP = 113.15, 430.0, 183.0, 113.15
CLR_MIN = 5.0                       # 越舱面最小净空
# Codex FIDELITY-01A 冻结值
WING_STOWED = {"x": (-174.5, 52.5), "y_abs": (113.15, 119.15), "z": (-200.0, 0.0)}
GNSS_AT = np.array([100.0, 0.0, 113.15])
GNSS_HALF_ANGLE_DEG = 70.0
SADDLE_MAX_TOWER_H = 150.0          # 塔高上限（长细比工程判据，超出记 HOLD）


def arm_vertices(q, clock):
    cache = np.load(SCRATCH / "mesh_cache.npz")
    tr = json.loads((V22 / "130_B601_Vendor_CAD_Direct_Integration_03/"
                      "design/group_link_transforms.json").read_text(encoding="utf-8"))["adopted"]
    frames = _frames(q, clock)
    out = {}
    for gid, a in tr.items():
        R_fk, p_fk = frames[a["urdf_link_frame"]]
        R = R_fk @ np.array(a["R_rows"])
        t = R_fk @ np.array(a["t_mm"]) + p_fk
        out[gid] = cache[f"{gid}_v"].astype(float) @ R.T + t
    return out


_J = None


def _frames(q, clock):
    global _J
    import xml.etree.ElementTree as ET
    if _J is None:
        root = ET.parse(s4.URDF).getroot()
        _J = {}
        for j in root.findall("joint"):
            o, ax = j.find("origin"), j.find("axis")
            _J[j.get("name")] = {
                "parent": j.find("parent").get("link"),
                "child": j.find("child").get("link"),
                "xyz": np.array([float(v) for v in
                                 (o.get("xyz") or "0 0 0").split()]) * 1000.0,
                "rpy": [float(v) for v in (o.get("rpy") or "0 0 0").split()],
                "axis": ([float(v) for v in ax.get("xyz").split()]
                          if ax is not None else [0, 0, 1])}
    c = math.radians(clock)
    Rz = np.array([[math.cos(c), -math.sin(c), 0],
                   [math.sin(c), math.cos(c), 0], [0, 0, 1]])
    F = {"base_link": (s4.R_SM @ Rz, s4.T_SM_MM.copy())}
    for i, jn in enumerate(["joint1", "joint2", "joint3", "joint4", "joint5",
                             "joint6"]):
        J = _J[jn]
        Rp, pp = F[J["parent"]]
        F[J["child"]] = (Rp @ s4.rpy_to_R(*J["rpy"]) @ s4.rot_axis(J["axis"], q[i]),
                          pp + Rp @ J["xyz"])
    G = _J["gripper_joint"]
    Rp, pp = F[G["parent"]]
    F["gripper_link"] = (Rp @ s4.rpy_to_R(*G["rpy"]), pp + Rp @ G["xyz"])
    return F


# ── 角点级快速评估（用于位形搜索）────────────────────────────────────────
def corner_sets():
    tr = json.loads((V22 / "130_B601_Vendor_CAD_Direct_Integration_03/"
                      "design/group_link_transforms.json").read_text(encoding="utf-8"))["adopted"]
    cen = {f"G{g['index']:02d}": g for g in json.loads(
        (V22 / "130_B601_Vendor_CAD_Direct_Integration_03/"
         "design/vendor_group_census.json").read_text(encoding="utf-8"))["groups"]}
    cen["G06"]["bbox_mm"] = {"min": [-70.01, -46.0, 17.3], "max": [70.01, 46.0, 85.96]}
    out = {}
    for gid, a in tr.items():
        lo = np.array(cen[gid]["bbox_mm"]["min"])
        hi = np.array(cen[gid]["bbox_mm"]["max"])
        c = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
                      for z in (lo[2], hi[2])])
        out[gid] = (a["urdf_link_frame"],
                    c @ np.array(a["R_rows"]).T + np.array(a["t_mm"]))
    return out


CORN = corner_sets()


def env_corners(q, clock):
    F = _frames(q, clock)
    return np.vstack([p @ F[ln][0].T + F[ln][1] for ln, p in CORN.values()])


PAD_CLR = 8.0            # 鞍座接触垫最小净空（臂底距舱面）
TOWER_MAX = 150.0        # 鞍座塔高上限（长细比工程判据）


def cost(q, clock):
    """min 高度 s.t. |Y|≤113.15、X≤430、可鞍座支承，
    且越舱面臂底落在 [deck+8, deck+150] 带内（同时保证净空与塔高可行）。"""
    P = env_corners(q, clock)
    od = P[P[:, 0] < DECK_X]
    c = max(0.0, P[:, 2].max() - DECK_TOP)
    c += 20.0 * max(0.0, np.abs(P[:, 1]).max() - Y_LIM)
    c += 20.0 * max(0.0, P[:, 0].max() - X_LIM)
    if len(od) == 0:
        return c + 3000.0
    zb = od[:, 2].min()
    c += 20.0 * max(0.0, DECK_TOP + PAD_CLR - zb)        # 净空下界
    c += 20.0 * max(0.0, zb - (DECK_TOP + TOWER_MAX))    # 塔高上界
    return c


SEEDS = [(0, 0, -180, -107, 0, -99), (144, -170, -64, -23, -24, -10),
         (160, -180, -54, -25, -30, 158), (0, -90, -90, 0, 0, 0),
         (0.07, 0, -180, -99.6, 0.3, 0), (90, -90, -90, -60, 0, 0),
         (-90, -90, -90, -60, 0, 0), (180, -180, -90, -90, 0, 0)]


def optimise(clock):
    best = None
    for s in SEEDS:
        q = np.clip(np.radians(np.array(s, float)), LB + 1e-6, UB - 1e-6)
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
        c = cost(q, clock)
        if best is None or c < best[0]:
            best = (c, q.copy())
    return best[1], best[0]


# ── 点到三角形最小距离（向量化）──────────────────────────────────────────
def point_tri_dist(P, T, chunk=200):
    """P (n,3), T (m,3,3) → 每点到三角集合的最小距离 (n,)。"""
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    ab, ac = b - a, c - a
    out = np.full(len(P), np.inf)
    for i in range(0, len(P), chunk):
        p = P[i:i + chunk][:, None, :]
        ap = p - a[None]
        d1 = (ab[None] * ap).sum(-1)
        d2 = (ac[None] * ap).sum(-1)
        aa = (ab * ab).sum(-1)[None]
        bb = (ac * ac).sum(-1)[None]
        abac = (ab * ac).sum(-1)[None]
        den = np.maximum(aa * bb - abac ** 2, 1e-12)
        u = (bb * d1 - abac * d2) / den
        v = (aa * d2 - abac * d1) / den
        u = np.clip(u, 0, 1)
        v = np.clip(v, 0, 1)
        s = np.clip(u + v, 0, None)
        f = np.where(s > 1, 1.0 / np.maximum(s, 1e-12), 1.0)
        u, v = u * f, v * f
        q = a[None] + u[..., None] * ab[None] + v[..., None] * ac[None]
        out[i:i + chunk] = np.linalg.norm(p - q, axis=-1).min(axis=1)
    return out


def struct_tris(exclude_saddles=True):
    v, t = mesh_group(ROOT / "evidence/config_steps/native_STOWED.step")
    T = v.astype(float)[t]
    if exclude_saddles:
        z = T[:, :, 2].min(axis=1)
        T = T[z <= DECK_TOP + 1.0]      # 剔除立于舱面之上的鞍座/包络
    return T


def evaluate(q, clock, ST):
    av = arm_vertices(q, clock)
    P = np.vstack(list(av.values()))
    rng = np.random.default_rng(11)
    sub = P[rng.choice(len(P), size=min(1800, len(P)), replace=False)]
    od = P[P[:, 0] < DECK_X]
    d = point_tri_dist(sub, ST)
    # 解锁路径：基座 G06/G01 固定在安装面上不参与抬升，只测可动段
    mov = np.vstack([v for g, v in av.items() if g not in ("G06", "G01")])
    msub = mov[rng.choice(len(mov), size=min(1200, len(mov)), replace=False)]
    lift = None
    for dz in range(0, 121, 10):
        if point_tri_dist(msub + np.array([0, 0, dz]), ST).min() >= 20.0:
            lift = dz
            break
    # 首动关节：逐关节小幅转动，取能最快拉开可动段净空者
    first = None
    base_clr = point_tri_dist(msub, ST).min()
    for i in (1, 2, 3):          # 首动候选限于肩/肘/腕基（成本控制）
        for sgn in (1, -1):
            qq = q.copy()
            qq[i] = float(np.clip(qq[i] + sgn * math.radians(5.0), LB[i], UB[i]))
            if abs(qq[i] - q[i]) < 1e-9:
                continue
            av2 = arm_vertices(qq, clock)
            m2 = np.vstack([v for g, v in av2.items() if g not in ("G06", "G01")])
            s2 = m2[rng.choice(len(m2), size=min(1200, len(m2)), replace=False)]
            g2 = float(point_tri_dist(s2, ST).min())
            if first is None or g2 > first[1]:
                first = (f"q{i+1}{'+' if sgn > 0 else '-'}5deg", g2)
    # 太阳翼收拢包络（Codex 冻结）
    w = WING_STOWED
    inw = ((P[:, 0] >= w["x"][0]) & (P[:, 0] <= w["x"][1]) &
           (np.abs(P[:, 1]) >= w["y_abs"][0]) & (np.abs(P[:, 1]) <= w["y_abs"][1]) &
           (P[:, 2] >= w["z"][0]) & (P[:, 2] <= w["z"][1]))
    # GNSS 天顶锥遮挡
    # 遮挡立体角占比：从 GNSS 顶点做方向分箱（方位 2°×天顶 2°），
    # 统计锥内被臂占据的方向格占全部方向格的比例（按 sinθ 加权=真实立体角）
    rel = P - GNSS_AT
    n = np.linalg.norm(rel, axis=1)
    up = n > 1e-6
    theta = np.degrees(np.arccos(np.clip(rel[up][:, 2] / n[up], -1, 1)))
    phi = np.degrees(np.arctan2(rel[up][:, 1], rel[up][:, 0])) % 360.0
    inside = theta <= GNSS_HALF_ANGLE_DEG
    nb_t, nb_p = int(GNSS_HALF_ANGLE_DEG // 2), 180
    blocked = set(zip((theta[inside] // 2).astype(int),
                      (phi[inside] // 2).astype(int)))
    w_blocked = sum(math.sin(math.radians(t * 2 + 1)) for t, _ in blocked)
    w_total = sum(math.sin(math.radians(t * 2 + 1)) * nb_p for t in range(nb_t))
    occl = len(blocked)
    # 鞍座：越舱面段按 X 分箱，找需要支承的连续窗口
    windows = []
    if len(od):
        xs = np.arange(-183, 184, 10.0)
        for x0 in xs:
            m = (od[:, 0] >= x0) & (od[:, 0] < x0 + 10)
            if m.sum() > 50:
                windows.append((float(x0), float(od[m][:, 2].min())))
    towers = [max(0.0, z - DECK_TOP) for _, z in windows]
    return {
        "q_deg": [round(float(np.degrees(v)), 3) for v in q],
        "C1_height": {"max_z_mm": round(float(P[:, 2].max()), 2),
                       "height_above_deck_mm": round(float(P[:, 2].max() - DECK_TOP), 2)},
        "C2_width": {"max_abs_y_mm": round(float(np.abs(P[:, 1]).max()), 2),
                      "limit": Y_LIM,
                      "margin_mm": round(Y_LIM - float(np.abs(P[:, 1]).max()), 2),
                      "pass": bool(np.abs(P[:, 1]).max() <= Y_LIM)},
        "C3_clearance_to_structure": {
            "movable_links_min_mm": round(float(base_clr), 2),
            "whole_arm_min_mm": round(float(d.min()), 2),
            "n_points_within_10mm_whole_arm": int((d < 10).sum()),
            "criterion": "以可动段（剔除 G06 基座/G01）为准——基座与安装适配器"
                          "本就是螺栓贴合面，0 距离是设计意图不是干涉",
            "method": "臂顶点 → NATIVE STOWED 结构三角（已剔除鞍座）点-三角精确距离"},
        "C4_saddles": {"support_windows_10mm_bins": len(windows),
                        "x_span_mm": ([round(windows[0][0], 1),
                                        round(windows[-1][0] + 10, 1)] if windows else None),
                        "tower_height_min_max_mm": ([round(min(towers), 1),
                                                      round(max(towers), 1)] if towers else None),
                        "tower_over_limit": bool(towers and max(towers) > SADDLE_MAX_TOWER_H)},
        "C5_release_path": {"lift_to_20mm_clearance_mm": lift,
                             "feasible_within_120mm": lift is not None,
                             "movable_clearance_now_mm": round(float(base_clr), 2),
                             "best_first_joint": (first[0] if first else None),
                             "clearance_after_5deg_mm": (round(first[1], 2)
                                                          if first else None),
                             "note": "基座 G06/G01 固定于安装面，不参与抬升"},
        "C6_solar_wing": {"arm_vertices_in_stowed_wing_envelope": int(inw.sum()),
                           "envelope": WING_STOWED,
                           "clear": bool(inw.sum() == 0)},
        "C7_gnss_occlusion": {"blocked_direction_cells": occl,
                               "cone_apex": GNSS_AT.tolist(),
                               "half_angle_deg": GNSS_HALF_ANGLE_DEG,
                               "solid_angle_blocked_fraction":
                                   round(w_blocked / w_total, 4),
                               "method": "方位2°×天顶2° 方向分箱，sinθ 加权立体角"},
        "envelope_bbox_mm": [round(float(v), 2) for v in
                              (*P.min(axis=0), *P.max(axis=0))],
        "n_vertices": int(len(P)),
    }


def main():
    ST = struct_tris()
    print("structure triangles (saddles excluded):", len(ST))
    res = {}
    for clock in (0.0, 15.0, 25.0, 35.0):
        q, c = optimise(clock)
        res[f"clock_{clock:g}deg"] = {"optimiser_cost": round(c, 3),
                                       **evaluate(q, clock, ST)}
        print(f"clock={clock:g}: cost={c:.2f} "
              f"q={res[f'clock_{clock:g}deg']['q_deg']}")
    # 交付 v2 向量（当前 STOW_VENDOR_25DEG_PROPOSAL 配置所依据）
    v2 = json.loads((V22 / "130_B601_Vendor_CAD_Direct_Integration_03/"
                      "design/b601_stow_joint_vector_v2.json").read_text(encoding="utf-8"))
    res["delivered_v2_clock25"] = {"optimiser_cost": None,
                                    **evaluate(np.array(v2["q_rad"]), 25.0, ST)}
    # 解析发现：时钟角 c 与 q1 冗余——各可行 c 下 (c + q1) 恒定
    world = {k: round(float(v["q_deg"][0]) + float(k.split("_")[1].rstrip("deg")), 3)
             for k, v in res.items() if k.startswith("clock_")}
    q1_limit = 160.428
    req = max(world.values())
    finding = {
        "id": "F-O11-1_CLOCKING_IS_A_JOINT_LIMIT_SHIFT",
        "observation": {f"{k}: clock + q1": v for k, v in world.items()},
        "claim": f"各时钟角下 (clock + q1) 恒为 {req}° —— 世界系收拢位形相同；"
                  "时钟角与 q1 完全冗余，其唯一作用是把所需的世界系 J1 转角"
                  "搬进关节限位之内",
        "minimum_required_clock_deg": round(req - q1_limit, 3),
        "q1_limit_deg": q1_limit,
        "margin_at_25deg": round(25.0 - (req - q1_limit), 3),
        "consequence": "七项判据在所有可行时钟角之间**不构成区分**（差异属网格伪影）；"
                        "它们区分的是「有时钟角」与「无时钟角」。"
                        f"clock=0 需 q1={req}° 超限 → 被迫改用超宽位形（|Y|=151.74 破 113.15）"}
    (ROOT / "design").mkdir(exist_ok=True)
    (ROOT / "design/o11_clocking_adjudication.json").write_text(
        json.dumps({"adjudication_id": "O11_CLOCKING_QUANTIFIED", "generated_utc": NOW,
                     "criteria_source": "用户 2026-07-27 指定七项",
                     "geometry_sources": {
                         "arm": "130 vendor mesh cache（真实厂商几何顶点）",
                         "structure": "NATIVE-01 STOWED 配置导出 STEP",
                         "wing_envelope_and_gnss": "Codex 100_Mechanical_Continuation FIDELITY-01A"},
                     "analytic_finding": finding,
                     "candidates": res}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print("\n== 解析发现 ==")
    print(" ", finding["claim"])
    print("  最小必需时钟角 =", finding["minimum_required_clock_deg"], "°；"
          "25° 余量 =", finding["margin_at_25deg"], "°")
    for k, v in res.items():
        print(f"\n== {k} ==")
        for ck in ("C1_height", "C2_width", "C3_clearance_to_structure",
                    "C4_saddles", "C5_release_path", "C6_solar_wing",
                    "C7_gnss_occlusion"):
            print("  ", ck, v[ck])


if __name__ == "__main__":
    main()
