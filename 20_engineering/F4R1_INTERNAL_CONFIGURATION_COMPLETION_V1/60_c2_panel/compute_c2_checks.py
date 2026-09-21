#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compute_c2_checks.py — F4R1 C2 帆板参数成熟化机器核算
======================================================
DESIGN_RESEARCH_CANDIDATE — 不改写任何冻结文件, 只读验证 + 输出 PANEL_VERIFICATION_V1.json

核算内容 (全部公式来源: B3 基准 §5/§6, 仓内路径见 input_files):
  (a) 面积×面密度→质量三档: m = sigma * A, 两条几何线
      (sim 单板 A = L*b = 0.0454 m2; R2 叶 A = 0.3*0.2 = 0.06 m2, 翼 = 3 叶 + 0.24 kg 硬件);
      对拍占位 0.3483933 kg/板 与 R2 冻结 0.78 kg/翼.
  (b) 悬臂板/等效梁公式→f1 三档构造方案 (B3 §5.2):
      f1 = (beta1^2 / (2*pi*L^2)) * sqrt(EI/mu),  均匀板 D = E*t^3/(12*(1-nu^2)), EI = D*b, mu = sigma*b;
      夹层板 D = E_f*t_f*h^2/2. 并反算占位 f1=1.0 Hz 隐含 EI 与 SSOT 给定 EI 的一致性.
  (c) 展开力矩裕度: R2 展开力矩账本阻力矩 × ≥2× 判据
      (JAXA JERG-2-215A §5.3.3 定义裕度 Ms = T_drive/T_resist − 1 > 1; MDPI Coatings 2023 规范).
  (d) 占位失真量化: f1 比值带 (8–20×) 与质量比值带 (1.5–3.8×) 正面验证 C-ISS-03/CHARTER 表述;
      EI 失真 (FR4 1.6mm 构造 EI / 占位 EI).
  (e) A1 解析缩放 (PRE_CAMPAIGN_ANALYTIC): 等冲量半正弦接触窗幅频 |H(f)| = |cos(pi*f*Tc)|/|1-(2*f*Tc)^2|
      (contact_window.py 等冲量形式, 冲量等效谱, 归一 |H(0)|=1);
      模态能比 ∝ (sigma/sigma0)*(|H|/|H0|)^2; 基座姿态反馈比 ∝ (sigma/sigma0)*(f0/f1)*(|H|/|H0|);
      tip 幅值比 ∝ (f0/f1)*(|H|/|H0|); 5% 振铃衰减时间 t5 = ln(20)/(zeta*2*pi*f1).
  (f) C1 接口: 帆板档质量变化 → CG 一阶点质量更新 (冻结 C01 + R2 翼 CG), 判定对 C1 OI-1 的影响.
  (g) 与 R2_FLEXIBILITY_VALIDITY_ENVELOPE_V3 包络角点的并置映射 (对齐/扩展声明依据).

输入完整性: 对全部引用文件实测 sha256, 有历史记录值的逐一比对 (B3 §0/资产盘点/C1 Gate),
不一致即 FAIL 退出 (fail-closed, 同 C1 纪律).

运行: python compute_c2_checks.py   (Windows Git Bash, 仅标准库)
确定性: 无随机数, 无实时钟 (generated_at 固定 "2026-08-27"); 重跑输出应字节一致.
"""

import hashlib
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT_JSON = os.path.join(HERE, "PANEL_VERIFICATION_V1.json")

GENERATED_AT = "2026-08-27"  # 固定日期, 保证确定性重跑

# ---------- 引用文件登记 (relpath, 历史记录 sha256 前12位 或 None=仅记录) ----------
INPUT_FILES = {
    "agents_root": ("AGENTS.md", "3d2269562678"),
    "charter": ("20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/00_charter/CHARTER.md", "5d70de9121b3"),
    "b3_benchmark": ("20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/10_benchmark/B3_DEPLOYABLE_SOLAR_ARRAY_BENCHMARK.md", None),
    "gap_registry": ("20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/30_gap_registry/GAP_REGISTRY.csv", "49d28658904e"),
    "repo_asset_inventory": ("20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/20_repo_assets/REPO_ASSET_INVENTORY.md", "d3326b44e4d4"),
    "flexible_appendage_v1": ("20_engineering/config/geometry/flexible_appendage_v1.yaml", "52fa88084c62"),
    "coupled_model_v0": ("20_engineering/config/coupled_scene/coupled_model_v0.yaml", "67a532fb29c7"),
    "scene_a2_capture": ("20_engineering/config/coupled_scene/scene_A2_capture.yaml", "4b979a1dfd18"),
    "r2_geometry_candidate_v3": ("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/v3_source_reissue/SOLAR_ARRAY_R2_GEOMETRY_CANDIDATE_V3.yaml", None),
    "r2_mass_properties_v1": ("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_ARRAY_R2_MASS_PROPERTIES_V1.json", "d5b7dd16532f"),
    "r2_deployment_torque_ledger": ("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_R2_DEPLOYMENT_TORQUE_LEDGER_V1.yaml", "5c78e5916b1d"),
    "r2_mechanism_analytical_ledger": ("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/SOLAR_R2_MECHANISM_ANALYTICAL_LEDGER_V1.yaml", "11d585258597"),
    "r2_hdrm_latch_design_v3": ("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/ecr_solar_array_r2/v3_source_reissue/SOLAR_ARRAY_R2_HDRM_LATCH_DESIGN_V3.yaml", None),
    "release_11_solar_r2_mechanism": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/11_SOLAR_R2_MECHANISM.yaml", "ef02ecc2f283"),
    "release_13_r2_flex_model": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/13_R2_FLEX_MODEL.yaml", "8cadf790cf6a"),
    "release_02_product_structure": ("20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/02_PRODUCT_STRUCTURE.yaml", "0f9897ef4e41"),
    "r2_validity_envelope_v3": ("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/round4_hf_rom_v3/R2_FLEXIBILITY_VALIDITY_ENVELOPE_V3.json", "5a15d0d3b8a1"),
    "r2_hf_model_v3": ("20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/r2_full_flex_closure/round4_hf_rom_v3/R2_HF_MODEL_V3.yaml", "584cccc7e03d"),
    "sim_11_gate_check": ("30_simulation/sim_11_coupled_dynamics/results/sim_11_gate_check.json", None),
    "sim_11_contact_window_src": ("30_simulation/sim_11_coupled_dynamics/src/contact_window.py", None),
    "sim_12_gate_check": ("30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json", None),
    "e23_coupled_gate": ("30_simulation/e23_r2_full_flex_coupled_recert/results/E23_R2_FULL_FLEX_COUPLED_GATE_V1.json", None),
    "sim_07a_readme": ("30_simulation/sim_07_ancf_flexible/README_sim_07a.md", None),
    "c1_gate": ("20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/50_c1_layout/GATE_C1_CHECK.json", None),
    "c1_cg_inertia_check": ("20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/50_c1_layout/CG_INERTIA_CHECK_V1.json", "c7759162f54d"),
}

# ---------- B3 §6 三档参数集 (输入常量, 出处: B3 基准 §6 表) ----------
TIER_SIGMA = {"LOW": 2.0, "NOMINAL": 4.0, "HIGH": 7.7}       # kg/m2 (B3 §6)
TIER_F1 = {"LOW": 1.0, "NOMINAL": 8.0, "HIGH": 20.0}         # Hz   (B3 §6)
TIER_ZETA = {"LOW": 0.002, "NOMINAL": 0.01, "HIGH": 0.03}    # -    (B3 §6)

# ---------- B3 §5.2 构造方案 (输入常量, 出处: B3 基准 §5.2 表) ----------
CONSTRUCTIONS = {
    "FR4_PCB_1p6mm": {"kind": "uniform", "E_Pa": 20.0e9, "nu": 0.18, "t_m": 1.6e-3, "sigma_kg_m2": 3.5},
    "FR4_PCB_1p2mm": {"kind": "uniform", "E_Pa": 20.0e9, "nu": 0.18, "t_m": 1.2e-3, "sigma_kg_m2": 2.7},
    "CFRP_AL_HONEYCOMB_5mm": {"kind": "sandwich", "E_f_Pa": 70.0e9, "t_f_m": 1.0e-4, "h_m": 5.0e-3, "sigma_kg_m2": 1.8},
}

TORQUE_MARGIN_RULE_MIN = 2.0   # T_drive >= 2 x T_resist (JAXA JERG-2-215A §5.3.3 定义 Ms>1; MDPI Coatings 2023 规范)

# sim 单板根部 frame F 在 S 系位置 (出处: sim_07a README §1, 见 input sim_07a_readme); CG 近似 = 根部 + L/2 沿 +Y
SIM_PANEL_ROOT_S_M = [-0.05675, 0.11315, 0.0]  # ASSUMED (根部点; CG 用根部+L/2 沿跨向近似, 仅用于一阶 CG 接口评估)

LN20 = math.log(20.0)


# ---------- 工具 ----------
def sha256_12(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def repo_path(rel):
    return os.path.join(REPO_ROOT, rel.replace("/", os.sep))


def read_text(rel):
    with open(repo_path(rel), encoding="utf-8") as fh:
        return fh.read()


def read_json(rel):
    with open(repo_path(rel), encoding="utf-8") as fh:
        return json.load(fh)


def rx_float(pattern, text, name, group=1, occurrence=0):
    """fail-closed 正则抽取 float; occurrence 取第 N 个匹配."""
    matches = list(re.finditer(pattern, text))
    if len(matches) <= occurrence:
        raise ValueError("字段抽取失败 (fail-closed): %s" % name)
    return float(matches[occurrence].group(group))


def rx_int(pattern, text, name, group=1):
    m = re.search(pattern, text)
    if not m:
        raise ValueError("字段抽取失败 (fail-closed): %s" % name)
    return int(m.group(group))


def half_sine_H(f_hz, t_c_s):
    """等冲量半正弦接触窗的冲量等效幅频 (归一 |H(0)|=1).

    s(t) = (pi/(2 Tc)) sin(pi t/Tc), 0<t<Tc 的傅里叶幅值:
    |H(f)| = |cos(pi f Tc)| / |1 - (2 f Tc)^2|; f Tc -> 0.5 时极限 pi/4."""
    x = f_hz * t_c_s
    den = 1.0 - (2.0 * x) ** 2
    if abs(den) < 1e-12:
        return math.pi / 4.0
    return abs(math.cos(math.pi * x)) / abs(den)


def cantilever_f1_hz(beta1, L_m, EI_Nm2, mu_kg_per_m):
    return (beta1 ** 2 / (2.0 * math.pi * L_m ** 2)) * math.sqrt(EI_Nm2 / mu_kg_per_m)


def construction_D_EI(con, b_m):
    """返回 (D [N m], EI [N m2]) — 公式 B3 §5.2."""
    if con["kind"] == "uniform":
        D = con["E_Pa"] * con["t_m"] ** 3 / (12.0 * (1.0 - con["nu"] ** 2))
    else:  # sandwich: D = E_f * t_f * h^2 / 2 (双面板, t_f 为单面厚度)
        D = con["E_f_Pa"] * con["t_f_m"] * con["h_m"] ** 2 / 2.0
    return D, D * b_m


def t5_ringdown_s(zeta, f1_hz):
    return LN20 / (zeta * 2.0 * math.pi * f1_hz)


# ---------- 主流程 ----------
def main():
    problems = []
    self_checks = []

    def check(name, ok, detail):
        self_checks.append({"name": name, "pass": bool(ok), "detail": detail})
        if not ok:
            problems.append("%s: %s" % (name, detail))

    # 1) 输入完整性
    input_files = {}
    for key, (rel, expected) in INPUT_FILES.items():
        p = repo_path(rel)
        if not os.path.isfile(p):
            problems.append("缺少输入文件: %s" % rel)
            continue
        actual = sha256_12(p)
        entry = {"path": rel, "sha256_12": actual}
        if expected is not None:
            entry["expected_sha256_12"] = expected
            entry["match_recorded"] = actual == expected
            if actual != expected:
                problems.append("sha256 与历史记录不符: %s (recorded %s, actual %s)" % (rel, expected, actual))
        input_files[key] = entry
    if problems:
        print("FATAL: 输入完整性失败, 终止。")
        for pr in problems:
            print(" -", pr)
        sys.exit(2)

    # 2) sim 线 SSOT 几何/质量 (flexible_appendage_v1.yaml)
    fa = read_text(input_files["flexible_appendage_v1"]["path"])
    L = rx_float(r"span_L_m:\s*([\d.]+)", fa, "span_L_m")
    b = rx_float(r"chord_b_m:\s*([\d.]+)", fa, "chord_b_m")
    t_sim = rx_float(r"thickness_t_m:\s*([\d.]+)", fa, "thickness_t_m")
    m_sim = rx_float(r"m_panel_kg:\s*([\d.]+)", fa, "m_panel_kg")
    mu_sim = rx_float(r"mu_kg_per_m:\s*([\d.]+)", fa, "mu_kg_per_m")
    beta1 = rx_float(r"beta1:\s*([\d.]+)", fa, "beta1")
    f1_ssot = rx_float(r"nominal:\s*\{f1_hz:\s*([\d.]+),\s*EI_Nm2:\s*([\deE.+-]+)\}", fa, "ssot nominal f1")
    ei_ssot = rx_float(r"nominal:\s*\{f1_hz:\s*([\d.]+),\s*EI_Nm2:\s*([\deE.+-]+)\}", fa, "ssot nominal EI", group=2)
    zeta_appendage = rx_float(r"damping:\s*\{type:\s*modal,\s*zeta:\s*([\d.]+)", fa, "damping zeta")

    A_sim = L * b
    sigma_sim = m_sim / A_sim
    check("sim_geom_area_closure", abs(A_sim - 0.0454) < 1e-4, "A_sim=%.6f m2 (L=%.3f, b=%.3f)" % (A_sim, L, b))
    check("sim_mu_closure", abs(mu_sim - m_sim / L) < 1e-6, "mu=%.7f vs m/L=%.7f" % (mu_sim, m_sim / L))

    cm = read_text(input_files["coupled_model_v0"]["path"])
    zeta_sim11 = rx_float(r"zeta_modal:\s*([\d.]+)", cm, "zeta_modal")

    sc = read_text(input_files["scene_a2_capture"]["path"])
    tc_nom_ms = rx_float(r"T_c_ms_nominal:\s*([\d.]+)", sc, "T_c_ms_nominal")
    tc_sweep = [float(v) for v in re.search(r"T_c_ms_sweep:\s*\[([^\]]+)\]", sc).group(1).split(",")]

    # 3) R2 线几何/质量
    geo = read_text(input_files["r2_geometry_candidate_v3"]["path"])
    leaf_x = rx_float(r"leaf_planform_mm:\s*\n\s*-\s*([\d.]+)\s*\n\s*-\s*([\d.]+)", geo, "leaf planform x")
    leaf_y = rx_float(r"leaf_planform_mm:\s*\n\s*-\s*([\d.]+)\s*\n\s*-\s*([\d.]+)", geo, "leaf planform y", group=2)
    leaf_t_mm = rx_float(r"leaf_thickness_mm:\s*([\d.]+)", geo, "leaf thickness")
    leaves_per_wing = rx_int(r"leaves_per_wing:\s*(\d+)", geo, "leaves per wing")
    wings = rx_int(r"wings:\s*(\d+)", geo, "wings")
    A_leaf = (leaf_x / 1000.0) * (leaf_y / 1000.0)

    mp = read_json(input_files["r2_mass_properties_v1"]["path"])
    leaf_kg = float(mp["mass_model"]["leaf_kg"])
    wing_kg = float(mp["configurations"]["C01"]["left_wing"]["mass_kg"])
    both_wings_kg = float(mp["configurations"]["C01"]["both_wings"]["mass_kg"])
    wing_cg_left = mp["configurations"]["C01"]["left_wing"]["cg_S_m"]
    wing_cg_pair = mp["configurations"]["C01"]["both_wings"]["cg_S_m"]
    hardware_per_wing = wing_kg - leaves_per_wing * leaf_kg
    sigma_r2_leaf = leaf_kg / A_leaf
    check("r2_leaf_areal_density", abs(sigma_r2_leaf - 3.0) < 1e-9, "sigma_R2_leaf=%.6f kg/m2 (leaf=%.3f kg, A_leaf=%.4f m2)" % (sigma_r2_leaf, leaf_kg, A_leaf))
    check("r2_hardware_share", abs(hardware_per_wing - 0.24) < 1e-9, "hardware/wing=%.6f kg (hinge_root 0.05 + hinge_inter 2x0.03 + HDRM 0.08 + harness 0.05)" % hardware_per_wing)
    check("r2_both_wings", abs(both_wings_kg - 2.0 * wing_kg) < 1e-9, "both_wings=%.6f kg" % both_wings_kg)

    # 4) 展开力矩账本
    tl = read_text(input_files["r2_deployment_torque_ledger"]["path"])
    fric_lo = rx_float(r"hinge_friction:\s*\{low:\s*([\d.]+),\s*high:\s*([\d.]+)", tl, "friction low")
    fric_hi = rx_float(r"hinge_friction:\s*\{low:\s*([\d.]+),\s*high:\s*([\d.]+)", tl, "friction high", group=2)
    harn_lo = rx_float(r"harness_jumper_bend:\s*\{low:\s*([\d.]+),\s*high:\s*([\d.]+)", tl, "harness low")
    harn_hi = rx_float(r"harness_jumper_bend:\s*\{low:\s*([\d.]+),\s*high:\s*([\d.]+)", tl, "harness high", group=2)
    latch_nom = rx_float(r"latch_engagement_final_5deg:\s*\{nominal:\s*([\d.]+)", tl, "latch nominal")
    spring_nom = rx_float(r"torsion_spring_per_hinge_Nm:\s*\{nominal:\s*([\d.]+)", tl, "spring nominal")
    t_avail_mid = rx_float(r"T_available:\s*([\d.]+)", tl, "T_available mid", occurrence=0)
    t_avail_fin = rx_float(r"T_available:\s*([\d.]+)", tl, "T_available final", occurrence=1)
    t_res_mid = rx_float(r"T_resisting_worst:\s*([\d.]+)", tl, "T_resist mid", occurrence=0)
    t_res_fin = rx_float(r"T_resisting_worst:\s*([\d.]+)", tl, "T_resist final", occurrence=1)
    gravity_ground = rx_float(r"gravity_ground_test_only:\s*\n\s*value:\s*([\d.]+)", tl, "gravity ground")
    t_res_low = fric_lo + harn_lo
    check("torque_resist_mid_composition", abs(t_res_mid - (fric_hi + harn_hi)) < 1e-12, "mid worst = friction_hi + harness_hi = %.3f" % (fric_hi + harn_hi))
    check("torque_resist_fin_composition", abs(t_res_fin - (fric_hi + harn_hi + latch_nom)) < 1e-12, "final worst = mid + latch = %.3f" % (fric_hi + harn_hi + latch_nom))

    # 5) V3 柔性包络
    env = read_json(input_files["r2_validity_envelope_v3"]["path"])
    v3_corners = env["parameter_corners"]
    v3_b1 = env["retained_mode_frequency_envelope"]["BENDING_1"]["by_corner_hz"]

    # 6) C1 冻结 CG 场景 (接口)
    c1 = read_json(input_files["c1_cg_inertia_check"]["path"])
    c1_total = float(c1["scenarios"]["SCENARIO_A_CARVE_OUT_READING_A"]["total_mass_kg"])
    c1_cg_mm = c1["scenarios"]["SCENARIO_A_CARVE_OUT_READING_A"]["cg_S_mm"]
    oi1_residual_mm = c1["scenarios"]["SCENARIO_CDS_VARIANT_24KG"]["iteration"]["residual_margins_mm"]

    # ================= (a) 面积×面密度→质量三档 =================
    mass_lines = {"sim_line_per_panel": {}, "r2_line_per_leaf": {}, "r2_line_per_wing": {}}
    for tier, sig in TIER_SIGMA.items():
        m_panel_t = sig * A_sim
        m_leaf_t = sig * A_leaf
        m_wing_t = leaves_per_wing * m_leaf_t + hardware_per_wing
        mass_lines["sim_line_per_panel"][tier] = {
            "sigma_kg_m2": sig, "area_m2": A_sim, "mass_kg": m_panel_t,
            "ratio_vs_placeholder_0p3483933": m_panel_t / m_sim,
        }
        mass_lines["r2_line_per_leaf"][tier] = {
            "sigma_kg_m2": sig, "area_m2": A_leaf, "mass_kg": m_leaf_t,
            "ratio_vs_frozen_leaf_0p18": m_leaf_t / leaf_kg,
        }
        mass_lines["r2_line_per_wing"][tier] = {
            "sigma_kg_m2": sig, "leaves_mass_kg": leaves_per_wing * m_leaf_t,
            "hardware_kg": hardware_per_wing, "mass_kg": m_wing_t,
            "ratio_vs_frozen_wing_0p78": m_wing_t / wing_kg,
        }

    # ================= (b) 悬臂板公式→f1 =================
    coef = beta1 ** 2 / (2.0 * math.pi * L ** 2)
    constructions_out = {}
    for cname, con in CONSTRUCTIONS.items():
        D, EI = construction_D_EI(con, b)
        mu = con["sigma_kg_m2"] * b
        f1 = cantilever_f1_hz(beta1, L, EI, mu)
        constructions_out[cname] = {
            "inputs": con, "D_Nm": D, "EI_Nm2": EI, "mu_kg_per_m": mu, "f1_hz": f1,
            "note": ("板弯曲上界; 实际系统级受铰链/根部刚度限制回落 ~5–15 Hz (B3 §5.2)" if cname.startswith("CFRP") else "PCB 基构造板弯曲频率 (B3 §5.2)"),
        }
    # 占位反算一致性
    ei_back = mu_sim * (f1_ssot / coef) ** 2
    ei_back_rel_diff = abs(ei_back - ei_ssot) / ei_ssot
    check("placeholder_ei_backcalc", ei_back_rel_diff < 2e-3, "EI_back=%.6e vs SSOT %.6e (rel %.2e, 差源于 beta1 舍入)" % (ei_back, ei_ssot, ei_back_rel_diff))
    ei_distortion = constructions_out["FR4_PCB_1p6mm"]["EI_Nm2"] / ei_ssot

    # ================= (c) 展开力矩裕度 =================
    def margin_case(t_avail, t_res):
        ratio = t_avail / t_res
        return {
            "T_available_Nm": t_avail, "T_resisting_worst_Nm": t_res,
            "ratio_drive_over_resist": ratio,
            "jaxa_static_margin_Ms": ratio - 1.0,
            "rule_min_ratio": TORQUE_MARGIN_RULE_MIN,
            "required_drive_min_Nm": TORQUE_MARGIN_RULE_MIN * t_res,
            "pass_2x_rule": ratio >= TORQUE_MARGIN_RULE_MIN,
        }

    torque = {
        "inputs_per_hinge": {
            "hinge_friction_low_high_Nm": [fric_lo, fric_hi],
            "harness_jumper_low_high_Nm": [harn_lo, harn_hi],
            "latch_engagement_final_5deg_Nm": latch_nom,
            "torsion_spring_candidate_Nm": spring_nom,
            "gravity_ground_test_only_Nm": gravity_ground,
        },
        "optimistic_low_resist": margin_case(spring_nom, t_res_low),
        "mid_travel_worst": margin_case(t_avail_mid, t_res_mid),
        "final_5deg_worst": margin_case(t_avail_fin, t_res_fin),
        "ground_test_note": "地面 1g 重力矩 %.3f N m > 弹簧候选 %.3f N m → 地面展开试验需卸载工装 (账本 test-config 结论, 非在轨缺陷)" % (gravity_ground, spring_nom),
    }
    torque["verdict"] = (
        "CANDIDATE_SPRING_FAILS_2X_RULE_AT_MID_AND_FINAL_5DEG"
        if not (torque["mid_travel_worst"]["pass_2x_rule"] and torque["final_5deg_worst"]["pass_2x_rule"])
        else "CANDIDATE_SPRING_PASSES_2X_RULE"
    )

    # ================= (d) 占位失真量化 =================
    f1_ratio_band = [TIER_F1["NOMINAL"] / f1_ssot, TIER_F1["HIGH"] / f1_ssot]
    mass_ratio_band = [sigma_sim / 5.0, sigma_sim / 2.0]
    distortion = {
        "f1_ratio_vs_real_band": {
            "placeholder_f1_hz": f1_ssot, "real_band_hz": [8.0, 20.0],
            "ratio_band": f1_ratio_band,
            "c_iss_03_statement": "占位 f1 低 8–20×",
            "verified": abs(f1_ratio_band[0] - 8.0) < 1e-12 and abs(f1_ratio_band[1] - 20.0) < 1e-12,
        },
        "mass_ratio_vs_real_band": {
            "placeholder_sigma_kg_m2": sigma_sim, "real_band_kg_m2": [2.0, 5.0],
            "ratio_band": mass_ratio_band,
            "c_iss_03_statement": "质量差 1.5–3.8× (占位偏重)",
            "verified": abs(mass_ratio_band[0] - 1.5) < 0.05 and abs(mass_ratio_band[1] - 3.8) < 0.05,
            "agents_todo3_correction": "AGENTS.md 待办3 「差 5–10 倍」方向正确 (占位偏重) 但量级偏大; 5–10× 仅对柔性/薄膜毯 (sigma<1.5) 成立 (B3 §5.1)",
        },
        "stiffness_distortion": {
            "placeholder_EI_Nm2": ei_ssot, "fr4_1p6mm_EI_Nm2": constructions_out["FR4_PCB_1p6mm"]["EI_Nm2"],
            "ratio_placeholder_softer_by": ei_distortion,
            "b3_statement": "占位 EI 比真实 PCB 板软 ~180× (B3 §5.2)",
            "verified": 150.0 < ei_distortion < 220.0,
        },
        "headline": "质量轴失真 %.2f–%.2f× (偏重) 远小于刚度/频率轴失真 (f1 低 %.0f–%.0f×, EI 软 ~%.0f×) — 主要矛盾在刚度轴 (B3 §7)" % (
            mass_ratio_band[0], mass_ratio_band[1], f1_ratio_band[0], f1_ratio_band[1], ei_distortion),
    }

    # ================= (e) A1 解析缩放 (PRE_CAMPAIGN_ANALYTIC) =================
    tc_list = [v / 1000.0 for v in tc_sweep]
    a1 = {"reference": {"sigma0_kg_m2": sigma_sim, "f0_hz": f1_ssot, "zeta0_sim11": zeta_sim11,
                        "zeta0_appendage_ssot": zeta_appendage, "tc_nominal_ms": tc_nom_ms},
          "H_abs_tables": {}, "tiers": {}}
    for tc_ms in tc_sweep:
        tc = tc_ms / 1000.0
        a1["H_abs_tables"]["Tc_%gms" % tc_ms] = {
            "band_edge_1_over_2Tc_hz": 1.0 / (2.0 * tc),
            "H_ref_f0": half_sine_H(f1_ssot, tc),
            "H_per_tier": {t: half_sine_H(f, tc) for t, f in TIER_F1.items()},
        }
    tc_nom = tc_nom_ms / 1000.0
    H0 = half_sine_H(f1_ssot, tc_nom)
    for tier in TIER_SIGMA:
        sig, f1, zeta = TIER_SIGMA[tier], TIER_F1[tier], TIER_ZETA[tier]
        H = half_sine_H(f1, tc_nom)
        a1["tiers"][tier] = {
            "sigma_kg_m2": sig, "f1_hz": f1, "zeta": zeta,
            "H_at_Tc_nominal": H,
            "modal_energy_ratio_vs_placeholder": (sig / sigma_sim) * (H / H0) ** 2,
            "base_attitude_feedback_ratio_vs_placeholder": (sig / sigma_sim) * (f1_ssot / f1) * (H / H0),
            "tip_amplitude_ratio_vs_placeholder": (f1_ssot / f1) * (H / H0),
            "ringdown_t5_s": t5_ringdown_s(zeta, f1),
            "a1_flip_boundary_f1_hz": sig / sigma_sim * f1_ssot,
            "a1_verdict_analytic": "HOLDS" if (sig / sigma_sim) * (f1_ssot / f1) * (H / H0) <= 1.0 else "FLIPS",
        }
    a1["flip_boundary_rule"] = (
        "A1 (G3b 型基座姿态反馈指标) 反馈比 >= 1 需 f1 < sigma/%.4f Hz (|H|≈1 时); "
        "B3 刚性板包络 (sigma 2–5 kg/m2) 对应翻转边界 f1 < 0.26–0.65 Hz — 仅大型柔性翼/薄膜毯可达, "
        "COTS 刚性板包络内不翻转" % sigma_sim)
    a1["caveat"] = "PRE_CAMPAIGN_ANALYTIC: 基于等冲量半正弦接触模型与悬臂板缩放律; 终稿待 C4 campaign (SENSITIVITY_CAMPAIGN_PLAN_V1)"

    # ================= (f) C1 接口: 帆板档质量→CG =================
    cg_frozen_m = [v / 1000.0 for v in c1_cg_mm]
    c1_interface = {"frozen_scenario": "SCENARIO_A_CARVE_OUT_READING_A (C1 主口径)", "tiers": {}}
    for tier, sig in TIER_SIGMA.items():
        m_wing_t = leaves_per_wing * sig * A_leaf + hardware_per_wing
        dm_pair = 2.0 * (m_wing_t - wing_kg)
        m_new = c1_total + dm_pair
        cg_new_m = [
            (c1_total * cg_frozen_m[i] + dm_pair * wing_cg_pair[i]) / m_new for i in range(3)
        ]
        d_cg_mm = [(cg_new_m[i] - cg_frozen_m[i]) * 1000.0 for i in range(3)]
        c1_interface["tiers"][tier] = {
            "wing_mass_kg": m_wing_t, "delta_pair_kg": dm_pair, "new_total_kg": m_new,
            "delta_cg_mm": d_cg_mm,
            "oi1_residual_mm_CDS_variant": oi1_residual_mm,
            "relaxes_oi1": bool(abs(d_cg_mm[0]) >= abs(oi1_residual_mm["x"]) or abs(d_cg_mm[1]) >= abs(oi1_residual_mm["y"])),
        }
    # sim 线信息性对照 (若 sim 质量模型按档调整): 单板 CG 近似 = 根部 + L/2 沿 +Y
    sim_panel_cg = [SIM_PANEL_ROOT_S_M[0], SIM_PANEL_ROOT_S_M[1] + L / 2.0, SIM_PANEL_ROOT_S_M[2]]
    c1_interface["sim_line_informational"] = {
        "note": "sim 单板 CG 近似 [%.5f, %.5f, %.5f] m (根部+半跨, ASSUMED, 出处 sim_07a README); 双板对称 y 向抵消" % tuple(sim_panel_cg),
        "per_tier_delta_pair_kg": {t: 2.0 * (TIER_SIGMA[t] * A_sim - m_sim) for t in TIER_SIGMA},
    }

    # ================= (g) V3 包络映射 =================
    v3_mapping = {
        "v3_corners": v3_corners,
        "v3_bending1_hz": v3_b1,
        "c2_tiers": {"sigma": TIER_SIGMA, "f1_hz": TIER_F1, "zeta": TIER_ZETA},
        "alignment_notes": [
            "C2 f1 LOW=1.0 Hz 低于 V3 LOW 角点 BENDING_1=%.3f Hz: C2 向下扩展 (保留占位=超柔性界)" % v3_b1["LOW"],
            "C2 f1 NOMINAL=8.0 Hz ≈ V3 HIGH 角点 BENDING_1=%.3f Hz (叶尺度悬臂公式 vs R2 整翼 ROM 系统级)" % v3_b1["HIGH"],
            "C2 zeta NOMINAL=0.01 (B3 工程惯例中值=现 sim 占位) vs V3 NOMINAL=0.005 (R2 ROM 线): 差异已声明, 两线并存",
            "V3 角点 (EI/GJ/k_root/k_inter) 为 R2 整翼 PROVISIONAL_DERIVED 区间; C2 叶尺度公式为论文灵敏度线 — C2 对齐并扩展 V3, 不另起炉灶",
        ],
    }

    # ================= 汇总输出 =================
    overall = "pass" if not problems else "fail"
    out = {
        "title": "F4R1 C2 帆板参数成熟化机器核算输出 V1",
        "generated_at": GENERATED_AT,
        "status": "DESIGN_RESEARCH_CANDIDATE",
        "method": "见脚本头注释: (a) m=sigma*A 双线; (b) 悬臂板公式 f1; (c) 展开力矩 ≥2× 判据; (d) 占位失真量化; (e) A1 解析缩放 (PRE_CAMPAIGN_ANALYTIC); (f) C1 CG 接口; (g) V3 包络映射",
        "input_files": input_files,
        "extracted_inputs": {
            "sim_line": {"L_m": L, "b_m": b, "t_m": t_sim, "A_m2": A_sim, "m_panel_kg": m_sim,
                         "mu_kg_per_m": mu_sim, "sigma_kg_m2": sigma_sim, "beta1": beta1,
                         "f1_ssot_hz": f1_ssot, "EI_ssot_Nm2": ei_ssot,
                         "zeta_sim11_modal": zeta_sim11, "zeta_appendage_ssot": zeta_appendage,
                         "T_c_ms_nominal": tc_nom_ms, "T_c_ms_sweep": tc_sweep},
            "r2_line": {"leaf_planform_mm": [leaf_x, leaf_y], "leaf_thickness_mm": leaf_t_mm,
                        "A_leaf_m2": A_leaf, "leaves_per_wing": leaves_per_wing, "wings": wings,
                        "leaf_kg": leaf_kg, "wing_kg": wing_kg, "both_wings_kg": both_wings_kg,
                        "hardware_per_wing_kg": hardware_per_wing, "sigma_leaf_kg_m2": sigma_r2_leaf},
        },
        "a_mass_from_areal_density": mass_lines,
        "b_f1_from_cantilever_formula": {
            "formula": "f1 = (beta1^2/(2*pi*L^2)) * sqrt(EI/mu); uniform D=E*t^3/(12*(1-nu^2)), EI=D*b, mu=sigma*b; sandwich D=E_f*t_f*h^2/2",
            "coefficient_beta1sq_over_2piL2": coef,
            "constructions": constructions_out,
            "placeholder_backcheck": {"EI_backcalc_Nm2": ei_back, "EI_ssot_Nm2": ei_ssot, "rel_diff": ei_back_rel_diff},
        },
        "c_deployment_torque_margin": torque,
        "d_placeholder_distortion": distortion,
        "e_a1_analytic_scaling": a1,
        "f_c1_interface_panel_mass_to_cg": c1_interface,
        "g_v3_envelope_mapping": v3_mapping,
        "self_checks": self_checks,
        "overall": overall,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print("== F4R1 C2 panel checks ==")
    print("sim 单板: A=%.6f m2, sigma=%.4f kg/m2, m=%.7f kg, f1=%.2f Hz (占位), EI=%.4e N m2" % (A_sim, sigma_sim, m_sim, f1_ssot, ei_ssot))
    print("R2 翼: A_leaf=%.4f m2 x3 叶 + %.2f kg 硬件 = %.2f kg/翼 (冻结), sigma_leaf=%.2f kg/m2" % (A_leaf, hardware_per_wing, wing_kg, sigma_r2_leaf))
    for tier in ("LOW", "NOMINAL", "HIGH"):
        ml = mass_lines["sim_line_per_panel"][tier]
        mr = mass_lines["r2_line_per_wing"][tier]
        print("  %s: sigma=%.1f -> sim板 %.4f kg (x%.3f), R2翼 %.3f kg (x%.3f), f1=%.1f Hz, zeta=%.3f" % (
            tier, ml["sigma_kg_m2"], ml["mass_kg"], ml["ratio_vs_placeholder_0p3483933"],
            mr["mass_kg"], mr["ratio_vs_frozen_wing_0p78"], TIER_F1[tier], TIER_ZETA[tier]))
    for cname, co in constructions_out.items():
        print("  f1 构造 %s: D=%.3f N m, EI=%.4f N m2, f1=%.2f Hz" % (cname, co["D_Nm"], co["EI_Nm2"], co["f1_hz"]))
    print("  力矩裕度: mid %.3f (req>=%.3f), final5deg %.3f (req>=%.3f) -> %s" % (
        torque["mid_travel_worst"]["ratio_drive_over_resist"], torque["mid_travel_worst"]["required_drive_min_Nm"],
        torque["final_5deg_worst"]["ratio_drive_over_resist"], torque["final_5deg_worst"]["required_drive_min_Nm"],
        torque["verdict"]))
    print("  失真: f1 低 %.0f–%.0f× (C-ISS-03 verified=%s), 质量 %.2f–%.2f× (verified=%s), EI 软 %.0f×" % (
        f1_ratio_band[0], f1_ratio_band[1], distortion["f1_ratio_vs_real_band"]["verified"],
        mass_ratio_band[0], mass_ratio_band[1], distortion["mass_ratio_vs_real_band"]["verified"], ei_distortion))
    for tier in ("LOW", "NOMINAL", "HIGH"):
        a = a1["tiers"][tier]
        print("  A1 %s: 能量比 %.3f, 姿态反馈比 %.4f, tip 比 %.4f, t5=%.2f s -> %s" % (
            tier, a["modal_energy_ratio_vs_placeholder"], a["base_attitude_feedback_ratio_vs_placeholder"],
            a["tip_amplitude_ratio_vs_placeholder"], a["ringdown_t5_s"], a["a1_verdict_analytic"]))
    print("self_checks: %d/%d pass" % (sum(1 for c in self_checks if c["pass"]), len(self_checks)))
    print("overall:", overall)
    print("written:", OUT_JSON)
    if problems:
        for pr in problems:
            print(" PROBLEM:", pr)
        sys.exit(1)


if __name__ == "__main__":
    main()
