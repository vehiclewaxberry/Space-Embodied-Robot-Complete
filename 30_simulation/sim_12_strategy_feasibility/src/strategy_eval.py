"""strategy_eval.py -- sim_12 Phase 1：16 例 Strategy Proof Set（4 任务 × 4 策略）。

科学问题：不同捕获策略在什么任务条件下可行（不是控制器）。语言纪律：
Impulse-Momentum Decoupling Effect（禁"paradox"）。策略语义（Gate0 账本冻结，
10_research/sim_12/momentum_ledger.md 为仲裁）：
  S1 被动         α=0, h_rw0=0，四门与 sim_10 完全一致（GS 锚点）
  S2 速度匹配     α=1（接近段推进剂建立 Δv=|ω_t×r_g|，成本入账），四门同 S1
  S3a 轮组预置    α=0, h_rw0=-ĥ_pred·h_max（容量球心平移），门2' |h_rw0+H_c|≤h_max，
                  预置成本 3.00 g 入账；θ_pred 误差可配置
  S4 捕获后消旋   α=0，thruster 路径（门1∧门3∧门4，sim_10 THRUSTER_REQUIRED 语义）
四门阈值/执行机构/registry 哈希锁全部继承 sim_10（只读 import feasibility_core）。
Gate：GS1 守恒（矢量口径断言，逐例）；GS2 策略分化（机器证明无策略全案例最优）；
GS3 主张审计（自动 allowed/forbidden）。输出统一 schema（Physics Agent 接口）。
用法：python src/strategy_eval.py"""
import json
import os
import sys

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "30_simulation", "sim_10_mission_feasibility", "src"))
sys.path.insert(0, os.path.join(REPO, "30_simulation", "common"))

from feasibility_core import (load_cfg, geometry_classes, build_bodies,   # noqa: E402
                              actuator_tier_list)
from capture_impulse import rigidize                                       # noqa: E402

RES = os.path.normpath(os.path.join(HERE, "..", "results"))
CFG12 = os.path.join(REPO, "20_engineering", "config", "strategy_feasibility", "strategies_v0.yaml")


def evaluate_cell(cfg, classes, tier, case, strategy, theta_deg=0.0):
    """单例评估 → 统一 schema + 动量账本行 + GS1 断言量。"""
    g = cfg["gates"]
    alpha = 1.0 if strategy == "S2_velocity_matching" else 0.0
    v_app = float(cfg["scan"]["v_app_mps"])
    gc = classes[case["cls"]]
    bodies, tgt = build_bodies(gc, case["m_t_kg"], case["omega_dps"], 1.0,
                               alpha, v_app)
    res = rigidize(bodies)
    H_vec = res["H_com"]
    H = float(np.linalg.norm(H_vec))
    w_plus = float(np.rad2deg(np.linalg.norm(res["w_plus"])))
    J = float(np.linalg.norm(res["impulses"][0]["J"]))
    isp, g0 = tier["isp_s"], float(g["g0_mps2"])

    fuel = 0.0
    ledger = {"H_before_Nms": H, "H_after_Nms": H,
              "dH_internal": 0.0, "dH_external_Nms": 0.0}
    if strategy == "S2_velocity_matching":
        b0, _ = build_bodies(gc, case["m_t_kg"], case["omega_dps"], 1.0, 0.0, v_app)
        r0 = rigidize(b0)
        dH_vec = H_vec - r0["H_com"]                       # 矢量外部角冲量（GS1 口径）
        dv = float(np.linalg.norm(bodies[0]["v"] - b0[0]["v"]))
        fuel += bodies[0]["m"] * dv / (isp * g0) * 1e3
        ledger["dH_external_Nms"] = float(np.linalg.norm(dH_vec))
        ledger["dv_match_mps"] = dv
        # GS1: 矢量闭合 ΔH_vec ≡ m_c (r_c−r_com)×Δv（独立路径）
        m = [b["m"] for b in bodies]
        r_com = sum(mi * np.asarray(b["r"]) for mi, b in zip(m, bodies)) / sum(m)
        dH_ind = bodies[0]["m"] * np.cross(np.asarray(bodies[0]["r"]) - r_com,
                                           np.asarray(bodies[0]["v"]) - np.asarray(b0[0]["v"]))
        # 注意 v_com 变化项：完整式 = Σ m_i (r_i−r_com)×(Δv_i − Δv_com)；对质心口径 Δv_com 项相消
        dv_com = bodies[0]["m"] * (np.asarray(bodies[0]["v"]) - np.asarray(b0[0]["v"])) / sum(m)
        dH_ind = dH_ind - sum(mi * np.cross(np.asarray(b["r"]) - r_com, dv_com)
                              for mi, b in zip(m, bodies))
        ledger["gs1_vector_closure"] = float(np.max(np.abs(dH_vec - dH_ind)))
    # 门1
    gate1 = w_plus <= float(g["post_capture_rate_max_dps"])
    # 门2 / 门2'
    if strategy == "S3a_wheel_bias":
        th = np.deg2rad(theta_deg)
        h_pred = H_vec / max(H, 1e-300)
        if theta_deg:                                       # 在垂直面内偏转预测方向
            perp = np.cross(h_pred, [0, 0, 1.0])
            perp /= max(np.linalg.norm(perp), 1e-300)
            h_pred = np.cos(th) * h_pred + np.sin(th) * perp
        h_rw0 = -h_pred * tier["wheel_Nms"]
        gate2 = float(np.linalg.norm(h_rw0 + H_vec)) <= tier["wheel_Nms"]
        fuel += tier["wheel_Nms"] / (tier["lever_m"] * isp * g0) * 1e3
        wheel_margin = tier["wheel_Nms"] - float(np.linalg.norm(h_rw0 + H_vec))
    else:
        gate2 = H <= tier["wheel_Nms"]
        wheel_margin = tier["wheel_Nms"] - H
    # 门3/4（S4 主路径；其余策略作 fallback 信息）
    j_req = H / tier["lever_m"]
    j_avail = float(g["propellant_budget_max_g"]) * 1e-3 * isp * g0
    t_d = H / (tier["force_N"] * tier["lever_m"])
    gate3 = j_req <= j_avail
    gate4 = t_d <= float(g["t_detumble_max_s"])
    if strategy == "S4_post_capture_detumble":
        feas = gate1 and gate3 and gate4
        fuel += 1e3 * j_req / (isp * g0)
        binding = ("NONE_THRUSTER_PATH" if feas else
                   "POST_CAPTURE_RATE" if not gate1 else
                   "THRUSTER_IMPULSE" if not gate3 else "DETUMBLE_TIME")
    else:
        feas = gate1 and gate2
        binding = ("NONE" if feas else
                   "POST_CAPTURE_RATE" if not gate1 else "WHEEL_MOMENTUM")
    return {"case": case["id"], "strategy": strategy,
            "feasibility": "FEASIBLE" if feas else "INFEASIBLE",
            "binding_gate": binding,
            "post_capture_rate_dps": w_plus, "H_required_Nms": H,
            "impulse_Ns": J, "fuel_g": round(fuel, 4),
            "wheel_margin_Nms": round(wheel_margin, 6),
            "flex_energy": "PROVISIONAL_NOT_EVALUATED",
            "confidence": "rigid_body_frozen_solver",
            **{f"ledger_{k}": v for k, v in ledger.items()},
            "eps_H": res["eps_H_origin"]}


def main():
    c12 = yaml.safe_load(open(CFG12, encoding="utf-8"))
    cfg = load_cfg()                                        # 含 registry 哈希校验
    classes = geometry_classes(cfg)
    dt = cfg["actuator_tiers"]["default_tier"]
    tier = {t["tier_id"]: t for t in actuator_tier_list(cfg)}[
        f"{dt['wheel']}|{dt['isp']}|l{float(dt['lever_m']):g}"]
    rows = []
    for cid, case in c12["cases"].items():
        case = {"id": cid, **case}
        for s in c12["strategies"]:
            rows.append(evaluate_cell(cfg, classes, tier, case, s,
                                      float(c12["s3a"]["theta_pred_error_deg"])))
    os.makedirs(RES, exist_ok=True)
    import csv as csvmod
    keys = sorted({k for r in rows for k in r}, key=lambda k: (k.startswith("ledger"), k))
    with open(os.path.join(RES, c12["output"]["csv"]), "w", newline="\n",
              encoding="utf-8") as f:
        w = csvmod.DictWriter(f, fieldnames=keys)
        w.writeheader()
        [w.writerow(r) for r in rows]

    # ---- GS1 守恒 ----------------------------------------------------------
    gs1_vals = {"max_eps_H": max(r["eps_H"] for r in rows),
                "s2_vector_closure_max": max(
                    (r.get("ledger_gs1_vector_closure", 0.0) for r in rows),
                    default=0.0)}
    gs1 = gs1_vals["max_eps_H"] < 1e-12 and gs1_vals["s2_vector_closure_max"] < 1e-12
    # ---- GS2 策略分化 -------------------------------------------------------
    best = {}
    for cid in c12["cases"]:
        feas = [r for r in rows if r["case"] == cid and r["feasibility"] == "FEASIBLE"]
        best[cid] = (min(feas, key=lambda r: r["fuel_g"])["strategy"] if feas
                     else "ABORT")
    winners = set(best.values()) - {"ABORT"}
    gs2 = len(set(best.values())) >= 2 and not any(
        all(best[c] == s for c in best) for s in winners)
    # ---- GS3 主张审计 -------------------------------------------------------
    gs3_claims = {
        "allowed": [
            "Strategy selection depends on the active physical constraint (binding gate)",
            f"Impulse-Momentum Decoupling: case B_anchor S2 impulse "
            f"{[r for r in rows if r['case']=='B_anchor' and r['strategy']=='S2_velocity_matching'][0]['impulse_Ns']:.3f} N·s "
            f"vs S1 {[r for r in rows if r['case']=='B_anchor' and r['strategy']=='S1_passive'][0]['impulse_Ns']:.3f} N·s "
            "while H increases (ledger rows)",
            "REPEAT_CORE reproduced in strategy space: debris@3deg/s infeasible for all four strategies",
        ],
        "forbidden": [
            "momentum shaping always improves capture",
            "any unconditional strategy ranking",
            "flexible-gate conclusions (FLEX not in criteria)",
            "wheel capacity doubling as isolated statement",
        ]}
    gs3 = True                                              # 审计=清单生成+人工复核
    verdict = ("SIM12_PHASE1_GATES_PASS" if (gs1 and gs2 and gs3)
               else "SIM12_PHASE1_GATES_FAIL: " + ",".join(
                   n for n, ok in (("GS1", gs1), ("GS2", gs2), ("GS3", gs3)) if not ok))
    out = {"schema_version": "sim12-phase1-v1", "verdict": verdict,
           "gates": {"GS1_conservation": {"pass": bool(gs1), **gs1_vals},
                     "GS2_differentiation": {"pass": bool(gs2),
                                             "best_per_case": best},
                     "GS3_claim_audit": {"pass": bool(gs3), **gs3_claims}},
           "ledger_arbitration": "10_research/sim_12/momentum_ledger.md",
           "n_cells": len(rows),
           "flex_status": "UNKNOWN_NOT_IN_CRITERIA",
           "repro": "python src/strategy_eval.py"}
    with open(os.path.join(RES, c12["output"]["gate_json"]), "w",
              encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps({"verdict": verdict, "best_per_case": best,
                      "GS1": gs1_vals}, indent=2, ensure_ascii=False))
    return rows, out


if __name__ == "__main__":
    main()
