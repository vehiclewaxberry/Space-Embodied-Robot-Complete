"""scan_grid.py -- sim_10 主扫描驱动：全网格精确 rigidize + 解析对照 + 四门裁决。

网格（参数卡 20_engineering/config/mission_feasibility/scan_v0.yaml，零硬编码）：
    μ(25, log) × ω_t(20, log) × 几何类(3) × λ(3) × α(2) = 9000 物理点
    + 两个锚点行（G1@μ=6.25、G2@μ=0.9167，λ=1、α=0、ω=3°/s，必须精确回 sim_06）。
每点输出：ω⁺ 精确矢量解、|H_c|、dT、守恒残差、共轴解析近似与 δ_analytic；
随后对 8 个执行机构档逐点过四门 → 区域标签（fail-closed）。
确定性：无随机数；两次运行 CSV 逐字节一致（tests 断言）。
用法：python src/scan_grid.py [--quick]（quick: 5×4 小网格冒烟）"""
import argparse
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from feasibility_core import (load_cfg, geometry_classes, exact_point,      # noqa: E402
                              analytic_point, gate_point, actuator_tier_list,
                              REPO)

RES = os.path.normpath(os.path.join(HERE, "..", "results"))


def grid_points(cfg, quick=False):
    sc = cfg["scan"]
    n_mu = 5 if quick else int(sc["n_mu"])
    n_om = 4 if quick else int(sc["n_omega"])
    mus = np.geomspace(*map(float, sc["mu_range_log"]), n_mu)
    oms = np.geomspace(*map(float, sc["omega_dps_range_log"]), n_om)
    return mus, oms


def anchor_rows(cfg):
    """锚点行：与 sim_06 名义工况完全一致（λ=1、α=0、ω=3°/s、v_app=0.01）。"""
    m_bus = float(cfg["mass_reference"]["servicer_bus_kg"])
    return [
        {"anchor": "debris_sim06", "cls": "G1_slender", "m_t": 150.0,
         "mu": 150.0 / m_bus, "omega_dps": 3.0, "lam": 1.0, "alpha": 0.0},
        {"anchor": "satellite_sim06", "cls": "G2_cubesat", "m_t": 22.0,
         "mu": 22.0 / m_bus, "omega_dps": 3.0, "lam": 1.0, "alpha": 0.0},
    ]


def run_scan(quick=False):
    cfg = load_cfg()
    classes = geometry_classes(cfg)
    tiers = actuator_tier_list(cfg)
    sc = cfg["scan"]
    m_bus = float(cfg["mass_reference"]["servicer_bus_kg"])
    v_app = float(sc["v_app_mps"])
    mus, oms = grid_points(cfg, quick)
    w_budget = float(cfg["gates"]["post_capture_rate_max_dps"])

    phys_rows = []
    pid = 0
    def eval_point(cls_name, mu, m_t, om, lam, alpha, anchor=""):
        nonlocal pid
        ex = exact_point(classes[cls_name], m_t, om, lam, alpha, v_app)
        an = analytic_point(classes[cls_name], m_t, om, lam)
        delta = abs(ex["w_plus_dps"] - an["w_plus_analytic_dps"]) / max(ex["w_plus_dps"], 1e-300)
        row = {"point_id": pid, "anchor": anchor, "geometry_class": cls_name,
               "mu": mu, "m_t_kg": m_t, "omega_t_dps": om,
               "omega_hat": om / w_budget, "lambda_scale": lam, "alpha": alpha,
               **ex, **an, "delta_analytic": delta}
        pid += 1
        return row

    for cls_name in classes:
        for mu in mus:
            m_t = mu * m_bus
            for om in oms:
                for lam in map(float, sc["lambda_scale"]):
                    for alpha in map(float, sc["alpha"]):
                        phys_rows.append(eval_point(cls_name, float(mu), m_t,
                                                    float(om), lam, alpha))
    for a in anchor_rows(cfg):
        phys_rows.append(eval_point(a["cls"], a["mu"], a["m_t"], a["omega_dps"],
                                    a["lam"], a["alpha"], anchor=a["anchor"]))

    gate_rows = []
    for r in phys_rows:
        for t in tiers:
            g = gate_point(r["H_c_Nms"], r["w_plus_dps"], t, cfg)
            gate_rows.append({"point_id": r["point_id"], "tier_id": t["tier_id"], **g})

    os.makedirs(RES, exist_ok=True)
    suffix = "_quick" if quick else ""
    out = cfg["output"]
    p_csv = os.path.join(RES, out["physics_csv"].replace(".csv", f"{suffix}.csv"))
    g_csv = os.path.join(RES, out["gates_csv"].replace(".csv", f"{suffix}.csv"))
    with open(p_csv, "w", newline="\n", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(phys_rows[0].keys()))
        wr.writeheader()
        for r in phys_rows:
            wr.writerow({k: (f"{v:.12e}" if isinstance(v, float) else v)
                         for k, v in r.items()})
    with open(g_csv, "w", newline="\n", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(gate_rows[0].keys()))
        wr.writeheader()
        for r in gate_rows:
            wr.writerow({k: (f"{v:.12e}" if isinstance(v, float) else v)
                         for k, v in r.items()})

    # ---- 摘要（默认档区域计数 + 锚点 + 守恒最差值） ---------------------------
    dt = cfg["actuator_tiers"]["default_tier"]
    default_tier_id = f"{dt['wheel']}|{dt['isp']}|l{float(dt['lever_m']):g}"
    counts = {}
    for gr in gate_rows:
        if gr["tier_id"] != default_tier_id:
            continue
        counts[gr["region"]] = counts.get(gr["region"], 0) + 1
    anchors = {r["anchor"]: {
        "w_plus_dps": r["w_plus_dps"], "H_c_Nms": r["H_c_Nms"],
        "region_default_tier": next(g["region"] for g in gate_rows
                                    if g["point_id"] == r["point_id"]
                                    and g["tier_id"] == default_tier_id)}
        for r in phys_rows if r["anchor"]}
    summary = {
        "quick": quick, "n_physics_points": len(phys_rows),
        "n_gate_rows": len(gate_rows), "n_tiers": len(tiers),
        "default_tier": default_tier_id,
        "region_counts_default_tier": counts,
        "anchors": anchors,
        "worst_eps_P": max(r["eps_P"] for r in phys_rows),
        "worst_eps_H": max(r["eps_H"] for r in phys_rows),
        "delta_analytic_max": max(r["delta_analytic"] for r in phys_rows),
        "delta_analytic_median": float(np.median([r["delta_analytic"]
                                                  for r in phys_rows])),
        "thresholds_widened": cfg["_thresholds_widened"],
        "physics_csv": os.path.relpath(p_csv, REPO),
        "gates_csv": os.path.relpath(g_csv, REPO),
    }
    s_json = os.path.join(RES, out["summary_json"].replace(".json", f"{suffix}.json"))
    with open(s_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(json.dumps({k: summary[k] for k in
                      ("n_physics_points", "region_counts_default_tier",
                       "anchors", "worst_eps_P", "worst_eps_H")},
                     indent=2, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    run_scan(quick=a.quick)
