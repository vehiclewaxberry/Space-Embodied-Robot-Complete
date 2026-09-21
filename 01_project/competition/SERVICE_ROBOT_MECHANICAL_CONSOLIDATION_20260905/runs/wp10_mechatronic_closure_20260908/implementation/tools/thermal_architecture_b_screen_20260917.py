# -*- coding: utf-8 -*-
"""
THERMAL_ARCHITECTURE_B_SCREEN_20260917

整星热控架构 B 候选筛（架构 A 已被 CF1 r3 机器裁决证伪之后的重开筛）。
本脚本只做稳态 1-D 热阻链估计；所有证据值标注 CALCULATED_FROM_EVIDENCE 并给出出处，
所有工程区间标注 ESTIMATE_DECLARED（MIN/MAX）。不重跑父本 sheet 求解器，不改动任何既有文件。

输出（二进制写入）：
  implementation/results/thermal_architecture_20260917/THERMAL_ARCHITECTURE_B_SCREEN_20260917.json
  implementation/results/thermal_architecture_20260917/THERMAL_ARCHITECTURE_B_SCREEN_20260917.json.sha256
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMPL = HERE.parent
OUTDIR = IMPL / "results" / "thermal_architecture_20260917"
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR / "THERMAL_ARCHITECTURE_B_SCREEN_20260917.json"

SRC_ACCEPT = "implementation/cf1_layout_thermal/results/thermal/THERMAL_ACCEPTANCE_CF1.json"
SRC_GEO = "implementation/cf1_layout_thermal/mechanical/THERMAL_PATH_GEOMETRY_CF1.json"
SRC_PROBE = "implementation/cf1_layout_thermal/results/mechanical/WEB_FACE_PROBE_CF1.json"
SRC_BUDGET = "implementation/results/stop_v36/thermal_scope_20260917/THERMAL_BUDGET_20260917.json"

# ---------------------------------------------------------------- 证据值（只读引用）
EV = {
    "Q_module_W": 27.591989608311465,          # THERMAL_ACCEPTANCE_CF1 module_heat_W（Q201 x2=22.504 + 铜/分流/熔断器 ~5W，并入节点，已披露）
    "Q201_heat_W": 22.504157336763274,
    "Q201_case_to_node_R_K_W": 1.81,           # 0.31 + 1.5（IF_CF1_01 预算，DESIGN_SPEC；README notes）
    "carrier_limit_C": 95.0,
    "Q201_Tj_limit_C": 150.0,
    "CHB_limit_C": 105.0,
    # 架构 A 链路阻值（evidence CALCULATED，与 STEP 同源）
    "A_link_minus_Y_K_W": 3.1356862612230088,
    "A_link_plus_Y_K_W": 1.6718299903895912,
    "A_link_minus_Y_terms_K_W": {"arch_riser": 1.111, "plate_spreading_1D": 0.703,
                                 "TIM_source": 0.181, "strap_bar": 0.913,
                                 "TIM_sink": 0.181, "lug_through": 0.048},
    "A_link_plus_Y_terms_K_W": {"arch_riser": 0.392, "TIM_source": 0.223,
                                "strap_bar": 0.845, "TIM_sink": 0.167, "lug_through": 0.044},
    # 架构 A 裁决锚点（evidence CALCULATED）
    "A_carrier_worst_C": 137.1627412150085,    # HOT_C_SUN_MINUS_Y
    "A_carrier_margin_C": -42.16274121500851,
    "A_Q201_Tj_worst_C": 177.89526599455004,
    "A_web_peak_plus_Y_C": 119.5244,           # HOT_C +Y 内腹板峰值（不辐射）
    # 假设性宿主改动（桥块，evidence 已算，sheet 求解器名义值，10 mm 网格）
    "A_bridge_only_carrier_by_env_C": {"HOT_A_SUN_PLUS_Y": 100.59549185279207,
                                       "HOT_B_SUN_MINUS_Z": 96.69064522248402,
                                       "HOT_C_SUN_MINUS_Y": 98.26378986130351,
                                       "DARK_330K_OCCLUDER": 88.29591542972156},
    # 辐射板温度锚点（A-run，用于声明边界区间）
    "panel_mean_C": {"HOT_A": {"minus_Z": 71.0785, "plus_Y": 64.7845, "minus_Y": 60.9623},
                     "HOT_C": {"minus_Z": 71.1562, "plus_Y": 52.9041, "minus_Y": 71.9304}},
    "panel_max_C": {"HOT_A": {"minus_Z": 83.9114, "plus_Y": 72.374, "minus_Y": 65.5544},
                    "HOT_C": {"minus_Z": 84.0243, "plus_Y": 64.3924, "minus_Y": 74.7001}},
    # STOP 板（T3 已登记板级热预算，不含 Q101）
    "STOP_board_heat_W": 1.483,
    # 未分配热->载板灵敏度（evidence：三面摊分 +33.269 W -> 载板 +20.39 K）
    "dT_carrier_per_W_face_heat": (157.16916141620004 - 136.7834754046139) / 33.26902279718156,
    # 探测几何
    "gap_thickness_mm": 2.0, "web_thickness_mm": 2.0, "panel_thickness_mm": 8.0,
    "bridge_plus_Y": {"distance_mm": 110.635, "area_mm2": 1373.84, "note": "+Y 唯一桥块=CHB 冷指座，同时承担 ~14 W CHB 热"},
    "bridge_minus_Y_nearest": {"distance_mm": 15.0, "area_mm2": 1980.0},
    "lug_footprint_mm2": {"plus_Y": 1080.0, "minus_Y": 1000.0},
}

# ---------------------------------------------------------------- 声明工程区间（ESTIMATE_DECLARED）
DECL = {
    "k_al_W_mK": [130.0, 167.0],               # 与父本一致：130=壁/桥保守值，167=6061-T6 手册典型；无证书无批次追溯
    "TIM_R_C_in2_W": [0.28, 0.42],             # 0.28=父本 TIM 族@25psi 声明点；上限 0.42=压力未实现惩罚（clamp 未设计）
    "web_lateral_width_mm": [25.0, 40.0],      # 腹板横向导热有效宽（接耳 25..27 mm 宽 + 扩散裕度）
    # 候选 B 的边界温度（辐射板局部注入点，含 STOP 1.483 W 系统级增量 ~+0.9K 与注入扩散）
    "T_boundary_plus_Y_C": [55.0, 76.0],       # 锚：+Y 板 mean 52.9..64.8 / max 64.4..72.4（A-run 四环境）
    "T_boundary_minus_Y_C": [62.0, 79.0],      # 锚：-Y 板 mean 61.0..71.9 / max 65.6..74.7
    "STOP_boundary_increment_C": [0.5, 1.5],   # STOP 1.483 W 摊入辐射系统对边界温度的抬升（灵敏度 0.613 K/W 量级）
    # B1b：导热带截面加倍后的链路阻声明带（在 evidence 桥块名义值基础上按 1-D 重算 nominal，带宽覆盖 k 区间与展宽简化）
    "B1b_link_minus_Y_K_W": [2.55, 2.90],      # nominal 2.696（立柱 1.111 + 板展宽 0.703 不变；带 0.913/2；TIM 上带）
    "B1b_link_plus_Y_K_W": [1.16, 1.38],       # nominal 1.264（带 0.845/2）
    "B_bridge_K_W": [0.011, 0.031],            # 2 mm 间隙 / (k 130..167 x 桥面积 500..1080 mm2)，桥面积=接耳脚下新增桥块
    # B2：x 向导热纵梁-甲板新路径（旁路腹板）
    "B2_rail_section_mm2": [700.0, 900.0],     # 设计点 30x30 纵梁；下限含机加/法兰有效截面折减
    "B2_rail_length_mm": [150.0, 200.0],       # 载板形心到 +/-Y 辐射板内面距离
    "B2_carrier_to_rail_R_K_W": [0.10, 0.30],  # 载板->纵梁螺栓+TIM 压接（声明）
    "B2_rail_end_R_K_W": [0.15, 0.35],         # 纵梁端角件+TIM->8mm 辐射板内面（600..1200 mm2）
    "B2_panel_spread_R_K_W": [0.05, 0.30],     # 板贯穿+局部展宽（声明）
}


def r_cond(L_mm, k, A_mm2):
    return (L_mm * 1e-3) / (k * A_mm2 * 1e-6)


def par(*rs):
    return 1.0 / sum(1.0 / r for r in rs)


def band(nom_pair):
    return {"min": min(nom_pair), "max": max(nom_pair)}


screen = {
    "schema": "THERMAL_ARCHITECTURE_B_SCREEN",
    "date": "2026-09-17",
    "author_tool": "implementation/tools/thermal_architecture_b_screen_20260917.py",
    "method": ("稳态 1-D 热阻链筛；evidence 值只读引用并标 CALCULATED_FROM_EVIDENCE；"
               "材料 k / TIM / 界面 / 边界温度全部用声明区间 ESTIMATE_DECLARED_MIN/MAX；"
               "结果给区间。不重跑父本 sheet 求解器，不改动任何既有证据/gate 文件。"),
    "sources_readonly": [SRC_ACCEPT, SRC_GEO, SRC_PROBE, SRC_BUDGET],
    "heat_loads": {
        "Q_module_W": {"value": EV["Q_module_W"], "class": "CALCULATED_FROM_EVIDENCE", "source": SRC_ACCEPT},
        "STOP_board_W": {"value": EV["STOP_board_heat_W"], "class": "CALCULATED_FROM_EVIDENCE",
                         "source": SRC_BUDGET,
                         "note": "板级 1.483 W（不含 Q101，T1 未闭）。T3 已登记：在轨对流=0，仅安装孔传导+辐射；"
                                 "本筛把它作为辐射系统边界温度的 +0.5..1.5 K 声明增量接入，不进载板节点。"},
    },

    # ------------------------------------------------------------ 1. 架构 A 根因链
    "architecture_A_root_cause": {
        "verdict_evidence": {"carrier_worst_C": EV["A_carrier_worst_C"], "limit_C": 95.0,
                             "margin_C": EV["A_carrier_margin_C"], "Q201_Tj_worst_C": EV["A_Q201_Tj_worst_C"],
                             "class": "CALCULATED_FROM_EVIDENCE", "source": SRC_ACCEPT},
        "chain": [
            {"seg": "载板节点->±Y 链路（拱形梁立柱/板展宽/TIM/导热带/接耳贯穿）",
             "R_minus_Y_K_W": EV["A_link_minus_Y_K_W"], "R_plus_Y_K_W": EV["A_link_plus_Y_K_W"],
             "terms_minus_Y": EV["A_link_minus_Y_terms_K_W"], "terms_plus_Y": EV["A_link_plus_Y_terms_K_W"],
             "class": "CALCULATED_FROM_EVIDENCE", "source": SRC_GEO,
             "note": "链路终点在 2 mm 不辐射内腹板上的接耳补丁，不在辐射板。"},
            {"seg": "+Y 内腹板横向到唯一桥块（CHB 冷指座，110.635 mm）",
             "R_K_W": band([r_cond(110.635, DECL["k_al_W_mK"][1], DECL["web_lateral_width_mm"][1] * 2.0),
                            r_cond(110.635, DECL["k_al_W_mK"][0], DECL["web_lateral_width_mm"][0] * 2.0)]),
             "class": "ESTIMATE_DECLARED",
             "basis": "R=L/(k*t*W)，L=110.635 mm(evidence 探测)，t=2 mm(evidence)，W=25..40 mm(声明)，k=130..167(声明)",
             "note": "该桥块同时承担 ~14 W CHB 冷指热；+Y 腹板峰值 119.5 C vs +Y 辐射板 mean 52.9 C = 热在腹板内堵死。"},
            {"seg": "-Y 内腹板横向到最近桥块（设备座，15 mm）",
             "R_K_W": band([r_cond(15.0, DECL["k_al_W_mK"][1], DECL["web_lateral_width_mm"][1] * 2.0),
                            r_cond(15.0, DECL["k_al_W_mK"][0], DECL["web_lateral_width_mm"][0] * 2.0)]),
             "class": "ESTIMATE_DECLARED",
             "basis": "同上，L=15 mm(evidence 探测)"},
            {"seg": "桥块贯穿 2 mm 间隙层",
             "R_plus_Y_K_W": band([r_cond(2.0, DECL["k_al_W_mK"][1], 1373.84),
                                   r_cond(2.0, DECL["k_al_W_mK"][0], 1373.84)]),
             "R_minus_Y_K_W": band([r_cond(2.0, DECL["k_al_W_mK"][1], 1980.0),
                                    r_cond(2.0, DECL["k_al_W_mK"][0], 1980.0)]),
             "class": "ESTIMATE_DECLARED",
             "basis": "R=gap/(k*A_bridge)，几何与面积均为 evidence 探测值；此项本身可忽略"},
            {"seg": "8 mm 辐射板->空间（ε 0.89/α 0.17，四环境）",
             "class": "CALCULATED_FROM_EVIDENCE", "source": SRC_ACCEPT,
             "note": "板温锚点 panel_mean_C/panel_max_C；辐射环节不是瓶颈。"},
        ],
        "breakpoint": ("几何断点：两接耳脚下间隙层材料 = 0 mm3（WEB_FACE_PROBE_CF1.json），"
                       "接耳只能贴在 2 mm 不辐射内腹板上；+Y 腹板唯一出口在 110.6 mm 外的 CHB 座。"
                       "27.59 W 模块热中约一半被迫在 2 mm 腹板内横向走 110.6 mm（等效 10.6..15.8 K/W，ESTIMATE_DECLARED），"
                       "与链路 1.67..3.14 K/W（CALCULATED）串联后载板节点 137.2 C，超 95 C 限 42.2 K。"),
        "one_liner": ("架构 A 把 27.6 W 载板热送进只连 2 mm 不辐射内腹板的接耳，而接耳脚下无桥块，"
                      "热须在 2 mm 腹板内横向走 110.6 mm(+Y)/15 mm(-Y) 才能到辐射板，腹板横向热阻主导导致载板 137.2 C vs 95 C 限。"),
    },

    "candidates": {},
    "unknowns": [],
    "followup": {},
}

# ------------------------------------------------------------ 2. 候选 B1a：接耳脚下桥块（evidence 名义值锚定 + 声明带）
b1a_worst = max(EV["A_bridge_only_carrier_by_env_C"].values())
b1a_best = min(EV["A_bridge_only_carrier_by_env_C"].values())
screen["candidates"]["B1a_bridge_under_lugs_only"] = {
    "change": ("宿主改动：在两接耳脚下间隙层各加一块 6061 桥块（同设备座做法，面积=接耳 footprint 1000..1080 mm2），"
               "打通 web->8 mm 辐射板的贯穿路径；导热带/链路不变。模块位姿问题不在本筛范围。"),
    "R_bridge_K_W": DECL["B_bridge_K_W"],
    "R_bridge_class": "ESTIMATE_DECLARED",
    "evidence_anchor": {"carrier_by_env_C": EV["A_bridge_only_carrier_by_env_C"],
                        "class": "CALCULATED_FROM_EVIDENCE",
                        "source": SRC_ACCEPT + " fallback.HOST_CHANGE_bridge_under_lugs",
                        "note": "父本 sheet 求解器名义热（未分配热=0）、10 mm 网格名义值"},
    "carrier_C_interval": {"min": round(b1a_best - 3.0, 2), "max": round(b1a_worst + 3.0, 2),
                           "band_basis": "ESTIMATE_DECLARED ±3 K 包 k/TIM/展宽简化不确定性"},
    "margin_to_95_C": {"nominal_worst_env": round(95.0 - b1a_worst, 2)},
    "verdict": "FAIL",
    "verdict_basis": ("evidence 名义值最坏环境 100.60 C > 95 C（超 5.60 K）；"
                      "声明带 [85.30, 103.60] 上界同样超限。几何改动消除了腹板横向瓶颈，"
                      "但链路 1.67..3.14 K/W 与 HOT 环境边界温度主导，27.59 W 下裕度为负。"),
}

# ------------------------------------------------------------ 2. 候选 B1b：桥块 + 导热带截面加倍
Rb = DECL["B_bridge_K_W"]
Rmy = DECL["B1b_link_minus_Y_K_W"]
Rpy = DECL["B1b_link_plus_Y_K_W"]
R_eff_B1b = band([par(Rmy[0] + Rb[0], Rpy[0] + Rb[0]), par(Rmy[1] + Rb[1], Rpy[1] + Rb[1])])
# 有效边界温度：按两侧热导加权 + STOP 增量
w_py = (1.0 / ((Rpy[0] + Rpy[1]) / 2)) / (1.0 / ((Rpy[0] + Rpy[1]) / 2) + 1.0 / ((Rmy[0] + Rmy[1]) / 2))
Tb_eff_min = w_py * DECL["T_boundary_plus_Y_C"][0] + (1 - w_py) * DECL["T_boundary_minus_Y_C"][0] + DECL["STOP_boundary_increment_C"][0]
Tb_eff_max = w_py * DECL["T_boundary_plus_Y_C"][1] + (1 - w_py) * DECL["T_boundary_minus_Y_C"][1] + DECL["STOP_boundary_increment_C"][1]
Q = EV["Q_module_W"]
T_B1b = band([Tb_eff_min + Q * R_eff_B1b["min"], Tb_eff_max + Q * R_eff_B1b["max"]])
# 名义点（evidence 标定：桥块案 T_b_eff = 100.595-27.59*R_eff_bridge；R_eff_bridge=par(3.136+0.015,1.672+0.015)）
R_eff_bridge_ev = par(EV["A_link_minus_Y_K_W"] + 0.015, EV["A_link_plus_Y_K_W"] + 0.015)
Tb_cal = EV["A_bridge_only_carrier_by_env_C"]["HOT_A_SUN_PLUS_Y"] - Q * R_eff_bridge_ev
T_B1b_nominal = Tb_cal + Q * par(2.696, 1.264)
screen["candidates"]["B1b_bridge_plus_doubled_straps"] = {
    "change": ("B1a 基础上把两条导热带导电截面加倍（-Y 带 25x15->25x30，+Y 带 27x15->27x30，同 6061-T6，不改封装/不改辐射板）："
               "-Y 链 3.136->~2.70（立柱 1.111 与板展宽 0.703 不变，带 0.913->0.457），"
               "+Y 链 1.672->~1.26（带 0.845->0.423）。"),
    "R_chain": {
        "R_link_minus_Y_K_W": {"interval": Rmy, "class": "ESTIMATE_DECLARED", "nominal": 2.696},
        "R_link_plus_Y_K_W": {"interval": Rpy, "class": "ESTIMATE_DECLARED", "nominal": 1.264},
        "R_bridge_K_W": {"interval": Rb, "class": "ESTIMATE_DECLARED"},
        "R_eff_parallel_K_W": {"interval": {k: round(v, 4) for k, v in R_eff_B1b.items()},
                               "nominal": round(par(2.696 + 0.015, 1.264 + 0.015), 4)},
    },
    "boundary": {"T_b_eff_C_interval": [round(Tb_eff_min, 2), round(Tb_eff_max, 2)],
                 "class": "ESTIMATE_DECLARED",
                 "anchor": "evidence 标定点 T_b_eff(HOT_A)= %.2f C（桥块案名义反推）；+Y/-Y 板温锚见 architecture_A_root_cause" % Tb_cal,
                 "STOP_1p483W_increment_C": DECL["STOP_boundary_increment_C"]},
    "carrier_C_interval": {"min": round(T_B1b["min"], 2), "max": round(T_B1b["max"], 2)},
    "carrier_C_nominal_calibrated": round(T_B1b_nominal, 2),
    "Q201_Tj_C_interval": {"min": round(T_B1b["min"] + EV["Q201_heat_W"] * EV["Q201_case_to_node_R_K_W"], 2),
                           "max": round(T_B1b["max"] + EV["Q201_heat_W"] * EV["Q201_case_to_node_R_K_W"], 2),
                           "note": "Tj = 载板 + 22.504 W x 1.81 K/W（IF_CF1_01，CALCULATED_FROM_EVIDENCE）；载板 95 限先于 Tj 150 限约束"},
    "margin_to_95_C": {"at_interval_max": round(95.0 - T_B1b["max"], 2), "at_nominal": round(95.0 - T_B1b_nominal, 2)},
    "verdict": "UNKNOWN",
    "verdict_basis": ("标定名义点 94.0 C（+1.0 K 边际），但声明区间 [%0.2f, %0.2f] 跨越 95 C 限；"
                      "fail-closed 规则下 UNKNOWN 不得计 PASS。立柱(1.111)与载板展宽(0.703)成为新瓶颈。" % (T_B1b["min"], T_B1b["max"])),
}

# ------------------------------------------------------------ 2. 候选 B2：载板->x 向导热纵梁->±Y 辐射板（旁路腹板）
Rr = band([r_cond(DECL["B2_rail_length_mm"][0], DECL["k_al_W_mK"][1], DECL["B2_rail_section_mm2"][1]),
           r_cond(DECL["B2_rail_length_mm"][1], DECL["k_al_W_mK"][0], DECL["B2_rail_section_mm2"][0])])
R_side = band([DECL["B2_carrier_to_rail_R_K_W"][0] + Rr["min"] + DECL["B2_rail_end_R_K_W"][0] + DECL["B2_panel_spread_R_K_W"][0],
               DECL["B2_carrier_to_rail_R_K_W"][1] + Rr["max"] + DECL["B2_rail_end_R_K_W"][1] + DECL["B2_panel_spread_R_K_W"][1]])
Tb2_min = 0.5 * (DECL["T_boundary_plus_Y_C"][0] + DECL["T_boundary_minus_Y_C"][0]) + DECL["STOP_boundary_increment_C"][0]
Tb2_max = 0.5 * (DECL["T_boundary_plus_Y_C"][1] + DECL["T_boundary_minus_Y_C"][1]) + DECL["STOP_boundary_increment_C"][1]
T_B2 = band([Tb2_min + (Q / 2.0) * R_side["min"], Tb2_max + (Q / 2.0) * R_side["max"]])
R_side_nom = r_cond(175.0, 150.0, 800.0) + 0.20 + 0.25 + 0.15
T_B2_nom = 0.5 * (64.7845 + 71.9304) + 0.9 + (Q / 2.0) * R_side_nom
screen["candidates"]["B2_longeron_deck_direct_to_panels"] = {
    "change": ("新路径：载板下方加两根 x 向 6061 导热纵梁（设计点 30x30 mm，截面声明 700..900 mm2，"
               "有效长度声明 150..200 mm），纵梁两端经角件+TIM 直接压接到 ±Y 8 mm 辐射板内表面（y=±105.15，"
               "穿过间隙层，等效桥面积声明 600..1200 mm2/侧），完全旁路 2 mm 内腹板与远端桥块；"
               "原 ±Y 导热带保守不计（可作冗余）。热量近似对半分（Q/2=13.80 W/侧）。"),
    "R_chain_per_side": {
        "carrier_to_rail_TIM_K_W": {"interval": DECL["B2_carrier_to_rail_R_K_W"], "class": "ESTIMATE_DECLARED"},
        "rail_lateral_K_W": {"interval": {k: round(v, 3) for k, v in Rr.items()}, "class": "ESTIMATE_DECLARED",
                             "basis": "R=L/(kA)，L=150..200 mm，A=700..900 mm2，k=130..167"},
        "rail_end_bracket_TIM_K_W": {"interval": DECL["B2_rail_end_R_K_W"], "class": "ESTIMATE_DECLARED"},
        "panel_through_spread_K_W": {"interval": DECL["B2_panel_spread_R_K_W"], "class": "ESTIMATE_DECLARED"},
        "total_per_side_K_W": {k: round(v, 3) for k, v in R_side.items()},
        "nominal_per_side_K_W": round(R_side_nom, 3),
    },
    "boundary": {"T_b_eff_C_interval": [round(Tb2_min, 2), round(Tb2_max, 2)], "class": "ESTIMATE_DECLARED",
                 "anchor": "+Y/-Y 板 mean（A-run 四环境）+STOP 增量"},
    "carrier_C_interval": {"min": round(T_B2["min"], 2), "max": round(T_B2["max"], 2)},
    "carrier_C_nominal": round(T_B2_nom, 2),
    "margin_to_95_C": {"at_interval_max": round(95.0 - T_B2["max"], 2), "at_nominal": round(95.0 - T_B2_nom, 2)},
    "verdict": "UNKNOWN",
    "verdict_basis": ("名义点 ~%0.1f C（约 +%0.1f K），但声明区间 [%0.2f, %0.2f] 跨限；"
                      "主要不确定性=纵梁有效截面/界面 TIM 压力未实现/辐射板局部注入温度。"
                      "CHB 壳温判据不受 B2 影响（独立冷指）。质量代价：两根纵梁约 2 x 0.175 m x 800 mm2 x 2700 kg/m3 ≈ 0.76 kg，未计入裁决。" % (T_B2_nom, 95.0 - T_B2_nom, T_B2["min"], T_B2["max"])),
}

# ------------------------------------------------------------ 3. 总裁决
cand_verdicts = {k: v["verdict"] for k, v in screen["candidates"].items()}
if all(v == "PASS" for v in cand_verdicts.values()):
    overall = "ARCHITECTURE_B_SCREEN_PASS_WITH_DECLARED_ESTIMATES__FE_OR_TEST_REQUIRED"
elif all(v == "FAIL" for v in cand_verdicts.values()):
    overall = "ARCHITECTURE_B_SCREEN_FAIL__ALL_CANDIDATES_EXCEED_95C_LIMIT"
else:
    overall = ("ARCHITECTURE_B_SCREEN_UNKNOWN__B1A_FAIL_B1B_B2_STRADDLE_95C__FE_OR_TEST_REQUIRED")
screen["verdict"] = overall
screen["verdict_rule"] = ("候选逐项：区间上界 ≤95 -> PASS；evidence 名义值或区间下界 >95 -> FAIL；区间跨限 -> UNKNOWN（fail-closed，不计 PASS）。"
                          "总裁决要求至少一个候选 PASS 才给 PASS。")
screen["unknowns"] = [
    "B1b/B2 的界面 TIM 压力（25 psi clamp 未设计）与接触热导实际值 — 需要 WP 级界面数据或试验",
    "辐射板局部注入点温度（本筛用板 mean/max + 声明扩散带）— 需要 FE 模型或父本 sheet 求解器对 B 几何重跑",
    "STOP 板 Q101 发热（T1 OPEN：K1 线圈电流/占空比缺输入）— 1.483 W 为不含 Q101 的板级值",
    "B2 纵梁与宿主结构的机械接口、振动/热循环下 TIM 退化 — 未评估",
    "模块位姿仍被精确窄相位 REJECTED（MODULE_POSE_NARROWPHASE_CF1.json）；任何 B 架构的实体布置需重过窄相位",
    "未分配热 33.27 W 的归宿（CF1 r3：含 22 W 未分配热时任何组合都不通过）— 本筛按名义热，未分配热另列",
]
screen["followup"] = {
    "to_promote_candidate": [
        "FE 模型：把 B1b/B2 几何接入 tools/spatial_radiator_network.py 同类 sheet 求解（或等效 FE），复用 CF1 r3 的 verify_* 独立复算链；判据=四环境载板 ≤95 C",
        "WP 级界面数据：每个螺栓压接面的 TIM 压力-热导曲线（T3 登记 required_inputs_for_T3_verdict 同款清单）",
        "试验：TIM 压接热导实测 + 纵梁/桥块组件级热稳态试验（地面自然对流仅作组件级，在轨口径=传导+辐射）",
        "机械闭环：B 实体窄相位 + 模块位姿重解（当前无任何精确无干涉位姿）",
        "Q201 焊盘入口颈 62.9 A/mm2 与四项规格偏离仍为开放项，不随热架构改变",
    ],
    "STOP_board_T3_integration": ("THERMAL_BUDGET_20260917.json 的 1.483 W 已作为边界温度 +0.5..1.5 K 声明增量接入本筛；"
                                  "T3 转正需 WP 级：安装孔热导（扭矩/垫圈/TIM）、安装点结构汇温度、板表面发射率与角系数；"
                                  "这些输入到位后应把 STOP 板作为显式节点并入 B 架构 FE 模型，而非边界增量。"),
    "do_not_touch": "架构 A 负结果文件（THERMAL_ACCEPTANCE_CF1.json 等）不改动；本筛只新增 results/thermal_architecture_20260917/。",
}
screen["review_status"] = "PENDING_REVIEW"
screen["next_stage_authorized"] = False

payload = json.dumps(screen, ensure_ascii=False, indent=1, sort_keys=False).encode("utf-8")
OUT.write_bytes(payload)
digest = hashlib.sha256(payload).hexdigest()
(OUTDIR / (OUT.name + ".sha256")).write_bytes((digest + "  " + OUT.name + "\n").encode("ascii"))

print("verdict:", overall)
for k, v in screen["candidates"].items():
    print(k, "->", v["verdict"], "carrier interval:", v.get("carrier_C_interval"))
print("sha256:", digest)
print("out:", OUT)
