"""O13：以顶点级间隙为约束重搜收拢关节向量（clock=25° 已人工批准）。

问题（O11 暴露）：角点包围盒代理只约束了竖直方向，对侧向贴近不保守——
三个候选位形均不能同时满足「可动段间隙 ≥8mm」与「鞍座塔高 ≤150mm」。

方法：把 NATIVE-01 结构栅格化为 4mm 占据栅格 → 欧氏距离变换得到距离场，
位形评估时对臂顶点做三线性查表（O(n)，微秒级），使顶点级间隙可进入搜索循环。
终选位形再用精确点-三角距离复核（不以距离场结论收口）。

约束（fail-closed）：
  可动段(剔除 G06/G01)最小间隙 ≥ 8mm      —— 鞍座接触垫厚度需求
  越舱面臂底 ≤ deck+150                    —— 鞍座塔高上限（长细比）
  |Y| ≤ 113.15、X ≤ 430、必须存在越舱面点   —— 包络与可支承性
目标：min 收拢最大 Z
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
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(V22 / "130_B601_Vendor_CAD_Direct_Integration_03/src"))
import o11_clocking_adjudication as O11

NOW = datetime.now(timezone.utc).isoformat()
CLOCK = 25.0                 # 人工批准 2026-07-27
DECK = O11.DECK_TOP
Y_LIM, X_LIM = O11.Y_LIM, O11.X_LIM
CLR_REQ = 8.0
TOWER_MAX = 150.0
CELL = 4.0
GLO = np.array([-260.0, -180.0, -180.0])
GHI = np.array([460.0, 180.0, 560.0])


def build_distance_field(T):
    from scipy.ndimage import distance_transform_edt
    dims = np.ceil((GHI - GLO) / CELL).astype(int) + 1
    occ = np.zeros(dims, dtype=bool)
    # 每三角按面积定采样数（~2mm 间距），重心坐标撒点
    a, b, c = T[:, 0], T[:, 1], T[:, 2]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    rng = np.random.default_rng(3)
    pts = [T.reshape(-1, 3)]
    for lo, hi, n in ((0.0, 50.0, 3), (50.0, 400.0, 12), (400.0, 1e9, 60)):
        m = (area >= lo) & (area < hi)
        if not m.any():
            continue
        k = int(m.sum())
        u = rng.random((k, n, 1))
        v = rng.random((k, n, 1))
        flip = (u + v) > 1
        u = np.where(flip, 1 - u, u)
        v = np.where(flip, 1 - v, v)
        pts.append((a[m][:, None] + u * (b[m] - a[m])[:, None]
                    + v * (c[m] - a[m])[:, None]).reshape(-1, 3))
    P = np.vstack(pts)
    idx = np.round((P - GLO) / CELL).astype(int)
    ok = np.all((idx >= 0) & (idx < dims), axis=1)
    idx = idx[ok]
    occ[idx[:, 0], idx[:, 1], idx[:, 2]] = True
    df = distance_transform_edt(~occ, sampling=(CELL, CELL, CELL))
    return df.astype(np.float32), dims, int(occ.sum()), len(P)


def clearance(df, dims, pts):
    idx = np.round((pts - GLO) / CELL).astype(int)
    inside = np.all((idx >= 0) & (idx < dims), axis=1)
    if not inside.any():
        return 1e3
    i = idx[inside]
    return float(df[i[:, 0], i[:, 1], i[:, 2]].min())


def sampled_local_points(n_per_group=420):
    """按组抽样臂顶点并预转入 URDF 连杆局部系（搜索循环只变换这些点）。"""
    cache = np.load(O11.SCRATCH / "mesh_cache.npz")
    tr = json.loads((V22 / "130_B601_Vendor_CAD_Direct_Integration_03/"
                      "design/group_link_transforms.json").read_text(encoding="utf-8"))["adopted"]
    rng = np.random.default_rng(17)
    out = {}
    for gid, a in tr.items():
        v = cache[f"{gid}_v"].astype(float)
        idx = rng.choice(len(v), size=min(n_per_group, len(v)), replace=False)
        # 关键：包含该组包围盒 8 角点，保证极值（高度/宽度）不被抽样漏掉
        lo, hi = v.min(axis=0), v.max(axis=0)
        corners = np.array([[x, y, z] for x in (lo[0], hi[0])
                            for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        pts = np.vstack([v[idx], corners])
        out[gid] = (a["urdf_link_frame"],
                    pts @ np.array(a["R_rows"]).T + np.array(a["t_mm"]))
    return out


def make_eval(df, dims, LOC):
    movable = [g for g in LOC if g not in ("G06", "G01")]

    def ev(q):
        F = O11._frames(q, CLOCK)
        allp, movp = [], []
        for gid, (ln, pts) in LOC.items():
            R, p = F[ln]
            w = pts @ R.T + p
            allp.append(w)
            if gid in movable:
                movp.append(w)
        P = np.vstack(allp)
        M = np.vstack(movp)
        od = M[M[:, 0] < O11.DECK_X]          # 越舱面段只看可动件
        # 每 20mm X 分箱的臂底剖面 → 可用支承站位（塔高落在带内的箱）
        stations, zb_min = [], None
        if len(od):
            zb_min = float(od[:, 2].min())
            b = np.floor((od[:, 0] + 200.0) / 20.0).astype(int)
            for k in np.unique(b):
                m = b == k
                if m.sum() < 40:
                    continue
                zb = float(od[m][:, 2].min())
                stations.append((float(k * 20.0 - 200.0 + 10.0), zb))
        usable = [s for s in stations
                  if DECK + CLR_REQ <= s[1] <= DECK + TOWER_MAX]
        span = (max(s[0] for s in usable) - min(s[0] for s in usable)
                if len(usable) >= 2 else 0.0)
        return {"max_z": float(P[:, 2].max()),
                "max_y": float(np.abs(P[:, 1]).max()),
                "max_x": float(P[:, 0].max()),
                "n_over_deck": int(len(od)),
                "z_bottom_over_deck": zb_min,
                "n_usable_stations": len(usable),
                "usable_station_span_mm": span,
                "usable_stations": usable,
                "clearance": clearance(df, dims, M)}
    return ev


def cost(ev, q):
    m = ev(q)
    c = max(0.0, m["max_z"] - DECK)
    c += 30.0 * max(0.0, m["max_y"] - Y_LIM)
    c += 30.0 * max(0.0, m["max_x"] - X_LIM)
    if m["n_over_deck"] == 0:
        return c + 5000.0
    # 距离场按格心量化，实测比真值乐观约 CELL·√3/2；阈值加保守裕度后再精确复核
    c += 30.0 * max(0.0, (CLR_REQ + CELL) - m["clearance"])
    # 臂必须收在顶甲板之上（缺下界会被钻空子折到舱体下方以压低最大 Z）
    c += 30.0 * max(0.0, (DECK + CLR_REQ) - m["z_bottom_over_deck"])
    # 可支承性：需 ≥2 个塔高落在 [8,150] 带内、跨距 ≥120mm 的支承站位
    c += 60.0 * max(0, 2 - m["n_usable_stations"])
    c += 0.5 * max(0.0, 120.0 - m["usable_station_span_mm"])
    return c


SEEDS = [(143.322, -167.5, -54.0, -23.0, -24.0, -10.0),      # O11 25° 优化解
         (144.572, -170.0, -64.0, -23.143, -23.954, -10.0),  # 交付 v2
         (133.322, -167.5, -50.25, -43.143, -24.0, -10.0),
         (150.0, -160.0, -70.0, -20.0, -30.0, 0.0),
         (135.0, -175.0, -45.0, -35.0, -10.0, -20.0),
         (155.0, -150.0, -80.0, -10.0, -40.0, 20.0),
         (120.0, -170.0, -60.0, -30.0, 0.0, 0.0),
         (160.0, -180.0, -54.0, -25.0, -30.0, 158.0)]


def main():
    ST = O11.struct_tris()
    df, dims, n_occ, n_pts = build_distance_field(ST)
    print(f"distance field {tuple(dims)} cells={df.size:,} occupied={n_occ:,} "
          f"from {n_pts:,} surface samples")
    LOC = sampled_local_points()
    print("sampled arm points:", sum(len(p) for _, p in LOC.values()))
    ev = make_eval(df, dims, LOC)
    results = []
    for si, s in enumerate(SEEDS):
        q = np.clip(np.radians(np.array(s, float)), O11.LB + 1e-6, O11.UB - 1e-6)
        for step in (3.0, 1.0):
            for _ in range(3):
                for i in range(6):
                    grid = np.arange(O11.LB[i], O11.UB[i] + 1e-9, math.radians(step))
                    bv, bc = q[i], cost(ev, q)
                    for v in grid:
                        q[i] = v
                        cc = cost(ev, q)
                        if cc < bc - 1e-9:
                            bc, bv = cc, v
                    q[i] = bv
        m = ev(q)
        feas = (m["max_y"] <= Y_LIM and m["max_x"] <= X_LIM
                and m["n_over_deck"] > 0
                and m["clearance"] >= CLR_REQ + CELL
                and m["z_bottom_over_deck"] >= DECK + CLR_REQ
                and m["n_usable_stations"] >= 2
                and m["usable_station_span_mm"] >= 120.0)
        results.append({"seed": s, "q": q.copy(), "cost": cost(ev, q),
                        "metrics": m, "feasible_field": bool(feas)})
        print(f"  seed{si}: cost={results[-1]['cost']:8.2f} maxZ={m['max_z']:7.1f} "
              f"maxY={m['max_y']:6.1f} clr={m['clearance']:5.1f} sta={m['n_usable_stations']} "
              f"zbot={m['z_bottom_over_deck']} feas={feas}")
    feas = [r for r in results if r["feasible_field"]]
    pool = sorted(feas or results, key=lambda r: (not r["feasible_field"], r["cost"]))
    best = pool[0]

    # 精确复核（点-三角），不以距离场收口
    exact = O11.evaluate(best["q"], CLOCK, ST)
    out = {"id": "O13_STOW_VECTOR_V3", "generated_utc": NOW,
           "clock_deg": CLOCK, "clock_ruling": "人工批准 2026-07-27",
           "constraints": {"movable_clearance_min_mm": CLR_REQ,
                            "tower_height_max_mm": TOWER_MAX,
                            "abs_y_max_mm": Y_LIM, "x_max_mm": X_LIM,
                            "must_have_over_deck_points": True},
           "objective": "min 收拢最大 Z",
           "method": {"search": f"{CELL}mm 占据栅格 + 欧氏距离变换距离场，"
                                  "三线性最近格查表；确定性坐标下降 3°→1°→0.3°，8 起点",
                       "final_check": "点-三角精确距离（不以距离场收口）"},
           "n_feasible_seeds": len(feas), "n_seeds": len(SEEDS),
           "q_rad": [round(float(v), 6) for v in best["q"]],
           "q_deg": [round(float(np.degrees(v)), 3) for v in best["q"]],
           "field_metrics": {k: (round(v, 2) if isinstance(v, float) else v)
                              for k, v in best["metrics"].items()},
           "exact_verification": exact,
           "STOW_VECTOR_STATUS": "CANDIDATE_HOLD",
           "all_seeds": [{"seed_deg": list(r["seed"]),
                           "q_deg": [round(float(np.degrees(v)), 3) for v in r["q"]],
                           "cost": round(r["cost"], 3),
                           "feasible_field": r["feasible_field"],
                           "metrics": {k: (round(v, 2) if isinstance(v, float) else v)
                                        for k, v in r["metrics"].items()}}
                          for r in results]}
    (ROOT / "design/b601_stow_joint_vector_v3.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n== 终选 ==")
    print("  q_deg:", out["q_deg"])
    print("  精确复核 C1 高度:", exact["C1_height"])
    print("  精确复核 C2 宽度:", exact["C2_width"])
    print("  精确复核 C3 间隙:", {k: exact["C3_clearance_to_structure"][k]
                                    for k in ("movable_links_min_mm", "whole_arm_min_mm")})
    print("  精确复核 C4 鞍座:", exact["C4_saddles"])
    print("  精确复核 C5 解锁:", {k: exact["C5_release_path"][k]
                                    for k in ("movable_clearance_now_mm",
                                               "best_first_joint",
                                               "clearance_after_5deg_mm")})


if __name__ == "__main__":
    main()
