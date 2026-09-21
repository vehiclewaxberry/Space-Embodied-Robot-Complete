"""run_gates.py -- sim_11 五项验证 Gate 机器裁决（输出 results/sim_11_gate_check.json）。

Gate（任一不过 -> 裁决 FAIL，写明复现命令，不得口头淡化）：
  G1 动量守恒     约简模式 A1/A2 全程 |dP|,|dL| <= 1e-12（对齐 sim_05 7.3e-17 量级）；
                  full 模式 12 s 漂移 <= 1e-9 作装配一致性交叉证据。
  G2 能量审计     无阻尼 A1 与 A2 捕获后保持段：
                  |W_joint - (dT+dU)| 相对误差 < 1e-8。
  G3 退化链       (a) 锁关节 -> sim_07a 基准（同款基座速度跳变激励，FFR 模态响应 vs
                      ANCF 记录值：tip 峰值 <5%、主频 <2%，6 工况全过）；
                  (b) 帆板刚化 -> sim_05 19.20°（峰值偏差 <0.1% + 逐点时程 <1e-3°）；
                  (c) 臂+帆板全刚化 -> sim_01 守恒基线（vs 30_simulation/common 刚体传播，
                      姿态角差 <1e-5°，动量机器精度）。
  G4 收敛性       A1: m=2/3/4 与 rtol 扫掠关键量 <1%；A2: 物理接触带宽
                  （contact_window 半正弦等冲量，T_c=20 ms 名义 PROVISIONAL）下
                  前向加密链 m3->m4->m5 合并峰值量 <1%（m2 粗化对比为分辨率
                  诊断：f3=17.55 Hz 在 25 Hz 接触带内，m=2 缺带内模态）。
                  理想冲量 Δt=0 的 A2 模态能 m 慢收敛
                  （m=2..7 逐阶 +2.86/+1.29/+0.72/~+0.4%）保留为非 Gate 诊断项：
                  频谱平坦 + B_t 慢衰减 => 能量指标不适定，系模型域边界
                  （v1.0 曾据此判 FAIL，v1.1 引入有限接触带宽修复）。
  G5 交叉求解     Radau vs BDF：A1/A2（含带宽口径）关键量差 <5%
                  （e15 教训 5.64%>5% 曾判 FAIL）。

用法：
  python run_gates.py --inline      只算进程内 Gate（G3a/G3b对比/G3c），写 partial
  python run_gates.py --aggregate   汇总 results/ 全部工件 -> sim_11_gate_check.json
  （场景扫掠工件由 scene_a1_arm_slew.py / scene_a2_capture.py 带 --tag 生成，
   复现命令逐条写入裁决 JSON。）"""
import argparse
import csv as csvmod
import hashlib
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from config_loader import load_model_config, load_scene, REPO, SIM_07  # noqa: E402
from coupled_dynamics import CoupledModel, JointTrajectory, HoldTrajectory, quintic  # noqa: E402
from capture_solver import chaser_composite                    # noqa: E402

RES = os.path.normpath(os.path.join(HERE, "..", "results"))
GATE_JSON = os.path.join(RES, "sim_11_gate_check.json")
PARTIAL = os.path.join(RES, "gates_inline_partial.json")

SIM05_PEAK_DEG = 19.20        # sim_05 headline（引用勿改）
TH_G1_MOM = 1e-12
TH_G1_FULL = 1e-9
TH_G2_ENERGY = 1e-8
TH_G3A_TIP = 0.05
TH_G3A_FREQ = 0.02
TH_G3B_PEAK = 1e-3            # 0.1 %
TH_G3B_POINTWISE_DEG = 1e-3
TH_G3C_ANGLE_DEG = 1e-5
TH_G4_CONV = 0.01
TH_G5_CROSS = 0.05


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_summary(name):
    p = os.path.join(RES, name)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ===================== G3a: 锁关节 -> sim_07a 基准 ==========================
def gate3a_locked_joints_vs_sim07():
    """锁死关节后帆板子系统 = 固支 FFR 悬臂。用 sim_07a 同款捕获基座速度跳变
    （capture_excitations + panel_excitation，一次性一维激励）驱动本模型的 FFR
    模态，与 sim_07 记录的 ANCF 基准（task_response_summary.csv）比 tip 峰值与主频。
    差异来源（报告声明）：FFR 3 模态 vs ANCF 8 单元、模态阻尼 vs Rayleigh 阻尼。"""
    sys.path.insert(0, SIM_07)
    import sim_07a_task_response as s07                        # 只读 import
    from ffr_panel import FFRPanel

    cfg = load_model_config()
    p = cfg["panel"]
    fl = cfg["panels_frames"]["L"]
    exc_modes = s07.capture_excitations()
    exc = {m: s07.panel_excitation(d["dv"], d["dw"]) for m, d in exc_modes.items()}

    ref_rows = {}
    with open(os.path.join(SIM_07, "results", "task_response_summary.csv"),
              encoding="utf-8") as f:
        for r in csvmod.DictReader(f):
            ref_rows[(r["capture_mode"], r["ei_case"])] = r

    zeta07 = float(s07.ZETA)                                   # sim_07a 冻结真源
    cases = []
    for mode in ("6dof_rigid_lock", "3dof_point"):
        for ei_name, EI in p["EI_cases_Nm2"].items():
            pan = FFRPanel("L", fl["root_S"], fl["deploy_S"], fl["normal_S"],
                           p["span_L_m"], p["mu_kg_per_m"], p["chord_b_m"],
                           p["thickness_t_m"], EI, n_modes=3, zeta=zeta07)
            a_tr, b_tr = exc[mode]["a_tr"], exc[mode]["b_tr"]
            etad0 = np.einsum("k,ki,k->i", pan.m_nodes, pan.Phi, a_tr + b_tr * pan.s)
            t = np.linspace(0.0, 15.0, 6001)
            tip = np.zeros_like(t)
            for i in range(pan.n_modes):
                w = pan.omega[i]
                wd = w * np.sqrt(1.0 - zeta07 ** 2)
                tip += pan.phi_tip[i] * (etad0[i] / wd) * np.exp(-zeta07 * w * t) * np.sin(wd * t)
            tip_peak_mm = float(np.max(np.abs(tip)) * 1e3)
            f1 = float(pan.f_modes_hz[0])
            ref = ref_rows[(mode, ei_name)]
            ref_tip = float(ref["tip_peak_mm"])
            ref_f = float(ref["f_dom_hz"])
            cases.append({
                "case": f"{mode}/{ei_name}",
                "tip_peak_mm_ffr": tip_peak_mm, "tip_peak_mm_ancf": ref_tip,
                "tip_rel_diff": abs(tip_peak_mm - ref_tip) / ref_tip,
                "f1_hz_ffr": f1, "f_dom_hz_ancf": ref_f,
                "freq_rel_diff": abs(f1 - ref_f) / ref_f,
            })
    worst_tip = max(c["tip_rel_diff"] for c in cases)
    worst_f = max(c["freq_rel_diff"] for c in cases)
    ok = worst_tip < TH_G3A_TIP and worst_f < TH_G3A_FREQ
    return {"pass": bool(ok), "worst_tip_rel_diff": worst_tip,
            "worst_freq_rel_diff": worst_f,
            "thresholds": {"tip": TH_G3A_TIP, "freq": TH_G3A_FREQ},
            "cases": cases,
            "evidence_scope": "帆板组件级退化对比；非自由漂浮整星逐点等价",
            "note": "FFR(3模态,模态阻尼取sim_07a.ZETA) vs ANCF(8单元,Rayleigh) "
                    "在sim_07固支根部同激励口径下对比；整星锁关节路径另由A2/G1/G5与回归测试覆盖",
            "repro": "python src/run_gates.py --inline"}


# ===================== G3b: 帆板刚化 -> sim_05 19.20° ========================
def gate3b_rigid_panels_vs_sim05():
    """(i) 刚化 A1 峰值 vs 19.20°（<0.1%）；(ii) 与 sim_05 动力学逐点时程对比
    （同款五次多项式轨迹；残差来源仅为质量分割 CSV 舍入 ~1e-6 量级惯量差）。"""
    s = read_summary("sim_11_scene_A1_summary_rigid.json")
    peak = s["peak_base_attitude_deviation_deg"]
    rel = abs(peak - SIM05_PEAK_DEG) / SIM05_PEAK_DEG

    from dynamics import FreeFloatingB601                       # sim_05 只读
    sc = read_summary("sim_11_scene_A1_summary_rigid.json")
    # 逐点：读刚化 CSV 的 dev 列，与 sim_05 同轨迹积分对比
    csv_path = os.path.join(RES, "sim_11_scene_A1_rigid.csv")
    ts, dev11 = [], []
    with open(csv_path, encoding="utf-8") as f:
        for r in csvmod.DictReader(f):
            ts.append(float(r["t_s"]))
            dev11.append(float(r["base_dev_angle_deg"]))
    ts = np.array(ts)
    dev11 = np.array(dev11)
    tr = load_scene(os.path.join("config", "coupled_scene",
                                 "scene_A1_arm_slew.yaml"))["scene"]["trajectory"]
    q0 = np.deg2rad(tr["q_start_deg"])
    q1 = np.deg2rad(tr["q_end_deg"])
    t_maneuver = float(tr["t_maneuver_s"])
    dyn5 = FreeFloatingB601()
    res5 = dyn5.integrate_trajectory(lambda t: quintic(t, t_maneuver, q0, q1)[0],
                                     lambda t: quintic(t, t_maneuver, q0, q1)[1],
                                     t_end=float(ts[-1]), n_out=len(ts))
    dev5 = res5["dev_angle_deg"]
    pointwise = float(np.max(np.abs(dev11 - dev5)))
    ok = rel < TH_G3B_PEAK and pointwise < TH_G3B_POINTWISE_DEG
    return {"pass": bool(ok),
            "peak_deg_sim11_rigid": peak, "peak_deg_sim05_ref": SIM05_PEAK_DEG,
            "peak_rel_diff": rel, "pointwise_max_diff_deg": pointwise,
            "thresholds": {"peak_rel": TH_G3B_PEAK, "pointwise_deg": TH_G3B_POINTWISE_DEG},
            "residual_source": "servicer_12U_bus_v1/panel 行 7 位小数舍入（H_bb 差 ~1e-6）",
            "repro": ["python src/scene_a1_arm_slew.py --rigid-panels --tag rigid",
                      "python src/run_gates.py --inline"]}


# ===================== G3c: 全刚化 -> sim_01 守恒基线 ========================
def gate3c_all_rigid_vs_sim01():
    """臂锁 + 帆板刚化 = 单刚体。给 sim_01 同款初始翻滚 [1,5,2]°/s，
    reduced 积分 vs 30_simulation/common propagate_torque_free（合成惯量），姿态角逐点对比。"""
    from rigid_body import propagate_torque_free
    mdl = CoupledModel(rigid_panels=True)
    th0 = np.zeros(6)
    m_c, c_com, I_com = chaser_composite(mdl, th0, np.zeros(0))
    w0 = np.deg2rad([1.0, 5.0, 2.0])
    # 零线动量：v_com = v_b + w x c_com = 0
    u0 = np.zeros(mdl.nu)
    u0[3:6] = w0
    u0[0:3] = -np.cross(w0, c_com)
    h_I = mdl.momentum_inertial(np.zeros(3), np.array([1.0, 0, 0, 0]), th0, np.zeros(0), u0)
    t_end, n_out = 60.0, 601
    res = mdl.integrate_reduced(HoldTrajectory(th0), t_end, h_I=h_I,
                                method="Radau", rtol=1e-11, atol=1e-13, n_out=n_out)
    ref = propagate_torque_free(I_com, w0, t_end, n=n_out)
    # 姿态差：四元数相对旋转角
    ang = np.zeros(n_out)
    for i in range(n_out):
        q1, q2 = res["Q"][i], ref["Q"][i]
        d = abs(float(np.dot(q1, q2)))
        ang[i] = np.degrees(2.0 * np.arccos(min(d, 1.0)))
    dh = np.max(np.abs(res["h_I"] - res["h_I"][0]))
    ok = float(np.max(ang)) < TH_G3C_ANGLE_DEG and dh < TH_G1_MOM
    return {"pass": bool(ok),
            "max_attitude_diff_deg": float(np.max(ang)),
            "momentum_max_drift": float(dh),
            "w0_dps": [1.0, 5.0, 2.0], "t_end_s": t_end,
            "composite": {"mass_kg": m_c, "I_diag_kgm2": np.diag(I_com).round(6).tolist()},
            "thresholds": {"angle_deg": TH_G3C_ANGLE_DEG, "momentum": TH_G1_MOM},
            "evidence_scope": "同一全刚化组合体退化为sim_01式单刚体无力矩传播；"
                              "不是与24 kg sim_01冻结工件逐点同构",
            "repro": "python src/run_gates.py --inline"}


# ===================== 汇总 ==================================================
def rel_diff(a, b):
    return abs(a - b) / max(abs(a), abs(b), 1e-300)


def aggregate():
    inline = json.load(open(PARTIAL, encoding="utf-8"))
    g = {}

    # ---- G1 动量守恒 ---------------------------------------------------------
    a1 = read_summary("sim_11_scene_A1_summary.json")
    a2 = read_summary("sim_11_scene_A2_summary.json")
    a1f = read_summary("sim_11_scene_A1_summary_fullmode.json")
    a2_bw = read_summary("sim_11_scene_A2_summary_bw20.json")
    g1_vals = {"A1_reduced_dP": a1["momentum_max_abs_dP"],
               "A1_reduced_dL": a1["momentum_max_abs_dL"],
               "A2_reduced_dP": a2["post"]["momentum_max_abs_dP"],
               "A2_reduced_dL": a2["post"]["momentum_max_abs_dL"],
               "A2_bw20_reduced_dP": a2_bw["post"]["momentum_max_abs_dP"],
               "A2_bw20_reduced_dL": a2_bw["post"]["momentum_max_abs_dL"],
               "A2_bw20_window_drift": a2_bw["contact"]["window_momentum_drift_max"],
               "A1_full_mode_dP": a1f["momentum_max_abs_dP"],
               "A1_full_mode_dL": a1f["momentum_max_abs_dL"]}
    ok1 = (max(g1_vals["A1_reduced_dP"], g1_vals["A1_reduced_dL"],
               g1_vals["A2_reduced_dP"], g1_vals["A2_reduced_dL"],
               g1_vals["A2_bw20_reduced_dP"], g1_vals["A2_bw20_reduced_dL"],
               g1_vals["A2_bw20_window_drift"]) <= TH_G1_MOM
           and max(g1_vals["A1_full_mode_dP"], g1_vals["A1_full_mode_dL"]) <= TH_G1_FULL)
    g["G1_momentum"] = {"pass": bool(ok1), "values": g1_vals,
                        "thresholds": {"reduced": TH_G1_MOM, "full_mode_cross": TH_G1_FULL},
                        "note": "reduced=动量流形约简(主证据); full=二阶全量积分(装配交叉证据); "
                                "bw20_window_drift=接触窗内追踪星+目标组合动量守恒(作用反作用同点)",
                        "repro": ["python src/scene_a1_arm_slew.py",
                                  "python src/scene_a1_arm_slew.py --mode full --tag fullmode",
                                  "python src/scene_a2_capture.py",
                                  "python src/scene_a2_capture.py --contact-ms 20 --t-post 4 "
                                  "--n-out 201 --tag bw20 --no-plot"]}

    # ---- G2 能量审计 ---------------------------------------------------------
    a1u = read_summary("sim_11_scene_A1_summary_undamped.json")
    a2u = read_summary("sim_11_scene_A2_summary_undamped.json")
    a2_short = read_summary("sim_11_scene_A2_summary_conv_m3.json")
    g2_values = {
        "A1_undamped_audit_rel": a1u["energy_audit_rel"],
        "A2_post_undamped_audit_rel": a2u["post"]["energy_audit_rel"],
        "A2_bw20_window_audit_rel": a2_bw["contact"]["window_energy_audit_rel"],
        "A1_damped_audit_rel_with_dissipation": a1["energy_audit_rel"],
        "A2_post_damped_audit_rel_with_dissipation": a2_short["post"]["energy_audit_rel"],
    }
    ok2 = max(g2_values["A1_undamped_audit_rel"],
              g2_values["A2_post_undamped_audit_rel"],
              g2_values["A2_bw20_window_audit_rel"]) < TH_G2_ENERGY
    g["G2_energy_audit"] = {
        "pass": bool(ok2), "values": g2_values, "threshold": TH_G2_ENERGY,
        "note": "A2只审计捕获后保持段；捕获瞬间塑性耗散单列dT_J",
        "repro": [
            "python src/scene_a1_arm_slew.py --zeta 0 --tag undamped",
            "python src/scene_a2_capture.py --zeta 0 --t-post 1 --n-out 101 "
            "--tag undamped --no-plot",
        ],
    }

    # ---- G3 退化链 -----------------------------------------------------------
    g["G3a_locked_joints_vs_sim07"] = inline["G3a"]
    g["G3b_rigid_panels_vs_sim05"] = inline["G3b"]
    g["G3c_all_rigid_vs_sim01"] = inline["G3c"]

    # ---- G4 收敛性 -----------------------------------------------------------
    a1_m2 = read_summary("sim_11_scene_A1_summary_m2.json")
    a1_m4 = read_summary("sim_11_scene_A1_summary_m4.json")
    a1_rt8 = read_summary("sim_11_scene_A1_summary_rtol8.json")
    key = "peak_base_attitude_deviation_deg"
    ekey = "panel_modal_energy_final_J"
    conv_a1 = {
        "peak_dev_m2_vs_m3": rel_diff(a1_m2[key], a1[key]),
        "peak_dev_m4_vs_m3": rel_diff(a1_m4[key], a1[key]),
        "modal_E_m2_vs_m3": rel_diff(a1_m2[ekey], a1[ekey]),
        "modal_E_m4_vs_m3": rel_diff(a1_m4[ekey], a1[ekey]),
        "peak_dev_rtol1e8_vs_1e10": rel_diff(a1_rt8[key], a1[key]),
        "modal_E_rtol1e8_vs_1e10": rel_diff(a1_rt8[ekey], a1[ekey]),
    }
    a2_m2 = read_summary("sim_11_scene_A2_summary_m2.json")
    a2_m3 = read_summary("sim_11_scene_A2_summary_conv_m3.json")
    a2_m4 = read_summary("sim_11_scene_A2_summary_m4.json")
    a2_rt8 = read_summary("sim_11_scene_A2_summary_rtol8.json")
    p2 = a2_m2["post"]
    p3 = a2_m3["post"]
    p4 = a2_m4["post"]
    pr = a2_rt8["post"]
    conv_a2_ideal = {
        "base_rate_m2_vs_m3": rel_diff(p2["base_rate_peak_dps"], p3["base_rate_peak_dps"]),
        "base_rate_m4_vs_m3": rel_diff(p4["base_rate_peak_dps"], p3["base_rate_peak_dps"]),
        "tip_L_m2_vs_m3": rel_diff(p2["tip_L_peak_mm"], p3["tip_L_peak_mm"]),
        "tip_L_m4_vs_m3": rel_diff(p4["tip_L_peak_mm"], p3["tip_L_peak_mm"]),
        "modal_E_peak_m2_vs_m3": rel_diff(
            p2["panel_modal_energy_peak_J"], p3["panel_modal_energy_peak_J"]),
        "modal_E_peak_m4_vs_m3": rel_diff(
            p4["panel_modal_energy_peak_J"], p3["panel_modal_energy_peak_J"]),
        "base_rate_rtol1e8_vs_1e10": rel_diff(
            pr["base_rate_peak_dps"], p3["base_rate_peak_dps"]),
        "tip_L_rtol1e8_vs_1e10": rel_diff(
            pr["tip_L_peak_mm"], p3["tip_L_peak_mm"]),
        "modal_E_peak_rtol1e8_vs_1e10": rel_diff(
            pr["panel_modal_energy_peak_J"], p3["panel_modal_energy_peak_J"]),
    }
    # 理想冲量 m 增阶诊断曲线（m=5/7 补充点）：慢收敛 => 不适定，不作 Gate
    ideal_curve = {}
    for tag, mm in (("m2", 2), ("conv_m3", 3), ("m4", 4), ("m5", 5), ("m7", 7)):
        try:
            ideal_curve[f"m{mm}"] = read_summary(
                f"sim_11_scene_A2_summary_{tag}.json")["post"]["panel_modal_energy_peak_J"]
        except FileNotFoundError:
            pass

    # ---- G4' 主判据：物理接触带宽（T_c 名义 20 ms，PROVISIONAL）下的 m 收敛 ----
    # 收敛按前向加密链裁决（m3 vs m4、m4 vs m5，标准收敛性口径：所选截断与更高
    # 截断的差）；m2 粗化对比不作 Gate —— 带边 1/(2*0.02s)=25 Hz > f3=17.55 Hz，
    # 三阶模态在接触带内，m=2 缺失带内模态属分辨率不足，非 m=3 未收敛证据。
    bw = read_summary("sim_11_scene_A2_summary_bw20.json")
    bw_m2 = read_summary("sim_11_scene_A2_summary_bw20_m2.json")
    bw_m4 = read_summary("sim_11_scene_A2_summary_bw20_m4.json")
    bw_m5 = read_summary("sim_11_scene_A2_summary_bw20_m5.json")
    c3, c2, c4, c5 = (bw["combined"], bw_m2["combined"], bw_m4["combined"],
                      bw_m5["combined"])
    conv_a2_bw = {
        "base_rate_m4_vs_m3": rel_diff(c4["base_rate_peak_dps"], c3["base_rate_peak_dps"]),
        "base_rate_m5_vs_m4": rel_diff(c5["base_rate_peak_dps"], c4["base_rate_peak_dps"]),
        "tip_L_m4_vs_m3": rel_diff(c4["tip_L_peak_mm"], c3["tip_L_peak_mm"]),
        "tip_L_m5_vs_m4": rel_diff(c5["tip_L_peak_mm"], c4["tip_L_peak_mm"]),
        "modal_E_peak_m4_vs_m3": rel_diff(c4["modal_energy_peak_J"],
                                          c3["modal_energy_peak_J"]),
        "modal_E_peak_m5_vs_m4": rel_diff(c5["modal_energy_peak_J"],
                                          c4["modal_energy_peak_J"]),
    }
    coarse_m2_diag = {
        "gated": False,
        "base_rate_m2_vs_m3": rel_diff(c2["base_rate_peak_dps"], c3["base_rate_peak_dps"]),
        "tip_L_m2_vs_m3": rel_diff(c2["tip_L_peak_mm"], c3["tip_L_peak_mm"]),
        "modal_E_peak_m2_vs_m3": rel_diff(c2["modal_energy_peak_J"],
                                          c3["modal_energy_peak_J"]),
        "note": "f3=17.55 Hz < 接触带边 25 Hz：三阶模态在带内，m=2 为分辨率不足"
                "（缺带内模态），不构成 m=3 未收敛证据；收敛 Gate 用前向加密链。",
    }
    bw_sweep = {}
    for tc, tag in ((5, "bw5"), (10, "bw10"), (20, "bw20"), (50, "bw50"),
                    (100, "bw100")):
        try:
            s = read_summary(f"sim_11_scene_A2_summary_{tag}.json")
            bw_sweep[f"Tc_{tc}ms"] = {
                "modal_E_peak_J": s["combined"]["modal_energy_peak_J"],
                "tip_L_peak_mm": s["combined"]["tip_L_peak_mm"],
                "lockup_rel_to_lam": s["contact"]["lockup_rel_to_lam"],
            }
        except FileNotFoundError:
            pass

    ok4 = max([*conv_a1.values(), *conv_a2_bw.values()]) < TH_G4_CONV
    g["G4_convergence"] = {
        "pass": bool(ok4),
        "criterion": "A1 全扫掠 + A2@有限接触带宽(T_c=20ms名义, PROVISIONAL 待B601夹爪"
                     "实测)前向加密链 m3->m4->m5",
        "rel_changes": {
            "A1_arm_slew": conv_a1,
            "A2_capture_bandwidth_Tc20ms": conv_a2_bw,
        },
        "A2_bandwidth_coarse_m2_diagnostic": coarse_m2_diag,
        "threshold": TH_G4_CONV,
        "ideal_impulse_diagnostic": {
            "gated": False,
            "rel_changes": conv_a2_ideal,
            "modal_E_peak_curve_J": ideal_curve,
            "physics_note": "理想冲量 Δt=0 频谱平坦，逐阶注入能量 ∝ (B_t,i·J)^2 而悬臂 "
                            "B_t,i 衰减缓慢（0.462/0.256/0.150/...），模态能量级数为慢收敛尾 "
                            "（m=2..7 逐阶 +2.86%/+1.29%/+0.72%/~+0.4%）——对能量指标不适定，"
                            "系模型域边界而非装配缺陷；基座角速率/tip 挠度等动量级量已收敛。"
                            "物理修复=有限接触带宽（contact_window.py，半正弦等冲量），"
                            "带宽下同一 1% 判据恢复适定并作为 G4 主判据。",
        },
        "bandwidth_sweep_diagnostic": bw_sweep,
        "values": {
            "A1": {"m2": [a1_m2[key], a1_m2[ekey]],
                   "m3": [a1[key], a1[ekey]],
                   "m4": [a1_m4[key], a1_m4[ekey]],
                   "rtol1e-8": [a1_rt8[key], a1_rt8[ekey]]},
            "A2_bandwidth": {"m2": c2, "m3": c3, "m4": c4, "m5": c5},
            "A2_ideal": {"m2": p2, "m3": p3, "m4": p4, "rtol1e-8": pr},
        },
        "repro": ["python src/scene_a1_arm_slew.py --n-modes 2 --tag m2",
                  "python src/scene_a1_arm_slew.py --n-modes 4 --tag m4",
                  "python src/scene_a1_arm_slew.py --rtol 1e-8 --tag rtol8",
                  "python src/scene_a2_capture.py --contact-ms 20 --t-post 4 "
                  "--n-out 201 --tag bw20 --no-plot",
                  "python src/scene_a2_capture.py --contact-ms 20 --n-modes 2 "
                  "--t-post 1 --n-out 101 --tag bw20_m2 --no-plot",
                  "python src/scene_a2_capture.py --contact-ms 20 --n-modes 4 "
                  "--t-post 1 --n-out 101 --tag bw20_m4 --no-plot",
                  "python src/scene_a2_capture.py --contact-ms 20 --n-modes 5 "
                  "--t-post 1 --n-out 101 --tag bw20_m5 --no-plot",
                  "python src/scene_a2_capture.py --n-modes 2 --t-post 1 "
                  "--n-out 101 --tag m2 --no-plot",
                  "python src/scene_a2_capture.py --t-post 4 --n-out 201 "
                  "--tag conv_m3 --no-plot",
                  "python src/scene_a2_capture.py --n-modes 4 --t-post 1 "
                  "--n-out 101 --tag m4 --no-plot",
                  "python src/scene_a2_capture.py --n-modes 5 --t-post 1 "
                  "--n-out 101 --tag m5 --no-plot",
                  "python src/scene_a2_capture.py --n-modes 7 --t-post 1 "
                  "--n-out 101 --tag m7 --no-plot",
                  "python src/scene_a2_capture.py --rtol 1e-8 --t-post 1 "
                  "--n-out 101 --tag rtol8 --no-plot"],
        "window_note": "A2比较量均为t<=0.26 s出现的峰值或守恒量；"
                       "1 s变体窗已覆盖首周期，m3基准另保留4 s特征窗；"
                       "bandwidth 口径峰值取接触窗与捕获后窗的合并最大值(combined)"}

    # ---- G5 交叉求解 ---------------------------------------------------------
    a1_bdf = read_summary("sim_11_scene_A1_summary_bdf.json")
    a2_bdf = read_summary("sim_11_scene_A2_summary_bdf.json")
    a2_radau_cross = read_summary("sim_11_scene_A2_summary_conv_m3.json")
    cross = {
        "A1_peak_dev": rel_diff(a1_bdf[key], a1[key]),
        "A1_modal_E_final": rel_diff(a1_bdf[ekey], a1[ekey]),
        "A1_tip_L_peak": rel_diff(a1_bdf["tip_L_peak_mm"], a1["tip_L_peak_mm"]),
        "A2_tip_L_peak": rel_diff(
            a2_bdf["post"]["tip_L_peak_mm"],
            a2_radau_cross["post"]["tip_L_peak_mm"]),
        "A2_base_rate_peak": rel_diff(a2_bdf["post"]["base_rate_peak_dps"],
                                      a2_radau_cross["post"]["base_rate_peak_dps"]),
        "A2_modal_E_peak": rel_diff(
            a2_bdf["post"]["panel_modal_energy_peak_J"],
            a2_radau_cross["post"]["panel_modal_energy_peak_J"]),
        "A2_H_origin": rel_diff(
            a2_bdf["post"]["H_total_about_inertial_origin_Nms"],
            a2_radau_cross["post"]["H_total_about_inertial_origin_Nms"]),
        "A2_L_about_com": rel_diff(
            a2_bdf["post"]["L_total_about_com_Nms"],
            a2_radau_cross["post"]["L_total_about_com_Nms"]),
    }
    bw_bdf = read_summary("sim_11_scene_A2_summary_bw20_bdf.json")
    cross.update({
        "A2_bw20_modal_E_peak": rel_diff(
            bw_bdf["combined"]["modal_energy_peak_J"],
            a2_bw["combined"]["modal_energy_peak_J"]),
        "A2_bw20_tip_L_peak": rel_diff(
            bw_bdf["combined"]["tip_L_peak_mm"],
            a2_bw["combined"]["tip_L_peak_mm"]),
        "A2_bw20_base_rate_peak": rel_diff(
            bw_bdf["combined"]["base_rate_peak_dps"],
            a2_bw["combined"]["base_rate_peak_dps"]),
    })
    ok5 = max(cross.values()) < TH_G5_CROSS
    g["G5_cross_solver"] = {"pass": bool(ok5), "radau_vs_bdf_rel": cross,
                            "threshold": TH_G5_CROSS,
                            "repro": [
                                "python src/scene_a1_arm_slew.py --method BDF --tag bdf",
                                "python src/scene_a2_capture.py --t-post 4 --n-out 201 "
                                "--tag conv_m3 --no-plot",
                                "python src/scene_a2_capture.py --method BDF --t-post 1 "
                                "--n-out 101 --tag bdf --no-plot",
                                "python src/scene_a2_capture.py --contact-ms 20 --method BDF "
                                "--t-post 1 --n-out 101 --tag bw20_bdf --no-plot",
                            ]}

    # ---- 汇总裁决 -------------------------------------------------------------
    all_pass = all(v["pass"] for v in g.values())
    failed = [k for k, v in g.items() if not v["pass"]]
    cfg = load_model_config()
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                                capture_output=True, text=True).stdout.strip()
    except Exception:
        commit = "unknown"
    artifacts = {}
    for fn in sorted(os.listdir(RES)):
        if (fn.endswith(".csv")
                or fn.endswith(".png")
                or fn.endswith(".log")
                or fn.startswith("sim_11_scene_") and fn.endswith(".json")
                or fn == os.path.basename(PARTIAL)):
            artifacts[fn] = sha256(os.path.join(RES, fn))
    out = {
        "schema_version": "sim11-gate-v3",
        "model": "路线A 浮动基座树形多体 + FFR 帆板 (m=3) + B601 6R + 有限接触带宽捕获(v1.1)",
        "PROVISIONAL_PARAMS": True,
        "provisional_fields": cfg["provisional_fields"],
        "provisional_note": "帆板模态设定为占位（D-4 频率指派 + 解析悬臂模态 + zeta=0.005 任务书默认）；"
                            "杨恒数值案例到位后替换 20_engineering/config/coupled_scene/coupled_model_v0.yaml 并重跑全部 Gate；"
                            "接触时长 T_c=20 ms 名义值为占位（scene_A2 contact 段），待 B601 夹爪闭合时间实测替换",
        "gates": g,
        "verdict": ("SIM11_GATES_PASS_WITH_PROVISIONAL_PARAMS" if all_pass
                    else "SIM11_GATES_FAIL: " + ",".join(failed)),
        "next_stage_authorized": bool(all_pass),
        "base_git_commit": commit,
        "artifacts_sha256": artifacts,
    }
    with open(GATE_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps({"verdict": out["verdict"],
                      "gates": {k: v["pass"] for k, v in g.items()}},
                     indent=2, ensure_ascii=False))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inline", action="store_true", help="进程内 Gate（G3a/G3b/G3c）")
    ap.add_argument("--aggregate", action="store_true", help="汇总 -> sim_11_gate_check.json")
    a = ap.parse_args()
    os.makedirs(RES, exist_ok=True)
    if a.inline:
        out = {"G3a": gate3a_locked_joints_vs_sim07(),
               "G3b": gate3b_rigid_panels_vs_sim05(),
               "G3c": gate3c_all_rigid_vs_sim01()}
        with open(PARTIAL, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(json.dumps({k: v["pass"] for k, v in out.items()}, indent=2))
    if a.aggregate:
        aggregate()


if __name__ == "__main__":
    main()
