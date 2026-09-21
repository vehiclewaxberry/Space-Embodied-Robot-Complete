# -*- coding: utf-8 -*-
"""
THERMAL_ARCHITECTURE_B_DESIGN_TARGETS_20260917

需求反解灵敏度分析（在 THERMAL_ARCHITECTURE_B_SCREEN_20260917.json 基础上；不修改该文件）。
对 B1b（桥块+导热带加倍）与 B2（载板->x 向纵梁->±Y 辐射板）分别反解：
  目标 M：载板温度不确定区间上限 <= 85 C（95 C 限留 >=10 K 裕度）
  目标 Z：载板温度不确定区间上限 <= 95 C（零裕度临界）
每个关键设计参数给出 REQUIRED_vs_CURRENT：当前值、需求值、比值、物理可达性。
物理可达范围全部 ESTIMATE_DECLARED。若 85 C 目标在声明物理范围外 ->
MARGIN_NOT_ACHIEVABLE_WITHIN_PHYSICAL_RANGE，并同时报告 95 C 零裕度临界值。

输出（open(...,'wb') 二进制写入，LF 行尾，禁止 CRLF）：
  results/thermal_architecture_20260917/THERMAL_ARCHITECTURE_B_DESIGN_TARGETS_20260917.json
  results/thermal_architecture_20260917/THERMAL_ARCHITECTURE_B_DESIGN_TARGETS_20260917.json.sha256
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMPL = HERE.parent
OUTDIR = IMPL / "results" / "thermal_architecture_20260917"
OUTDIR.mkdir(parents=True, exist_ok=True)
OUT = OUTDIR / "THERMAL_ARCHITECTURE_B_DESIGN_TARGETS_20260917.json"
PRIOR = "implementation/results/thermal_architecture_20260917/THERMAL_ARCHITECTURE_B_SCREEN_20260917.json"

# ---------------- 证据锚点（CALCULATED_FROM_EVIDENCE，与 screen 同源性只读引用）
Q = 27.591989608311465          # 模块节点热 W（CF1 验收点，Q201 x2）
Q2 = Q / 2.0
Q201_R = 1.81                   # K/W，载板->Tj（IF_CF1_01）
Q201_Q = 22.504157336763274
T_LIMIT = 95.0
T_MARGIN_TARGET = 85.0          # 95 - 10 K

# ---------------- B1b 模型（与 screen 相同口径）
# 链路最坏分解（ESTIMATE_DECLARED，与 screen 区间一致：-Y 合计 2.931，+Y 合计 1.411）
B1B_WORST = {
    "minus_Y": {"arch_riser": 1.20, "plate_spread": 0.80, "strap_bar": 0.50,
                "TIM_total": 0.35, "lug": 0.05, "bridge": 0.031},
    "plus_Y":  {"arch_riser": 0.45, "strap_bar": 0.46,
                "TIM_total": 0.42, "lug": 0.05, "bridge": 0.031},
}
# 有效边界温度（ESTIMATE_DECLARED，screen 同口径：热导加权 + STOP 1.483 W 增量）
W_PY = (1.0 / 1.27) / (1.0 / 1.27 + 1.0 / 2.725)
TB_B1B_MIN = W_PY * 55.0 + (1 - W_PY) * 62.0 + 0.5
TB_B1B_MAX = W_PY * 76.0 + (1 - W_PY) * 79.0 + 1.5
# 声明物理可达下限（ESTIMATE_DECLARED）
B1B_FLOOR = {
    "strap_bar": [0.2279, 0.2848],   # L=57.15 mm, k=167, A=1200..1500 mm2（现加倍后 750 mm2）
    "TIM_per_iface": [0.09, 0.14],   # 0.28 C in2/W 实现 + 面积 x2（声明）
    "arch_riser_minus_Y": [0.55, 0.65],  # 截面 x2 结构改造（声明）
    "arch_riser_plus_Y": [0.20, 0.25],
    "plate_spread": [0.35, 0.42],    # 2-D 展宽信用/接触重布置（声明）
    "lug": [0.048, 0.05],
    "bridge": [0.006, 0.015],        # 桥面积 x2（声明）
}

# ---------------- B2 模型
B2_WORST = {"carrier_to_rail": 0.30, "rail": 2.1978, "rail_end": 0.35, "panel_spread": 0.30}
TB_B2_MIN = 0.5 * (55.0 + 62.0) + 0.5
TB_B2_MAX = 0.5 * (76.0 + 79.0) + 1.5
B2_FLOOR = {
    "carrier_to_rail": [0.05, 0.10],
    "rail": [0.4491, 0.7984],        # A=1500..2000 mm2, k=167, L=150..200 mm（现 700..900 mm2）
    "rail_end": [0.08, 0.15],
    "panel_spread": [0.03, 0.10],
}
B2_RAIL_A_PHYS_MAX_MM2 = 2000.0      # 声明物理上限


def par(*rs):
    return 1.0 / sum(1.0 / r for r in rs)


def link_total(d):
    return sum(d.values())


# ================= B1b 反解 =================
R1_w = link_total(B1B_WORST["minus_Y"])     # 2.931
R2_w = link_total(B1B_WORST["plus_Y"])      # 1.411
R_eff_cur = par(R1_w, R2_w)
R_req85_b1b = (T_MARGIN_TARGET - TB_B1B_MAX) / Q
R_req95_b1b = (T_LIMIT - TB_B1B_MAX) / Q
f85_b1b = R_req85_b1b / R_eff_cur
f95_b1b = R_req95_b1b / R_eff_cur

# 联合物理下限（全部杆件同时打到声明下限）
R1_fl = (B1B_FLOOR["arch_riser_minus_Y"][0] + B1B_FLOOR["plate_spread"][0]
         + B1B_FLOOR["strap_bar"][0] + 2 * B1B_FLOOR["TIM_per_iface"][0]
         + B1B_FLOOR["lug"][0] + B1B_FLOOR["bridge"][0])
R2_fl = (B1B_FLOOR["arch_riser_plus_Y"][0] + B1B_FLOOR["strap_bar"][0]
         + 2 * B1B_FLOOR["TIM_per_iface"][0] + B1B_FLOOR["lug"][0] + B1B_FLOOR["bridge"][0])
R1_fl_c = (B1B_FLOOR["arch_riser_minus_Y"][1] + B1B_FLOOR["plate_spread"][1]
           + B1B_FLOOR["strap_bar"][1] + 2 * B1B_FLOOR["TIM_per_iface"][1]
           + B1B_FLOOR["lug"][1] + B1B_FLOOR["bridge"][1])
R2_fl_c = (B1B_FLOOR["arch_riser_plus_Y"][1] + B1B_FLOOR["strap_bar"][1]
           + 2 * B1B_FLOOR["TIM_per_iface"][1] + B1B_FLOOR["lug"][1] + B1B_FLOOR["bridge"][1])
R_eff_floor = par(R1_fl, R2_fl)
R_eff_floor_c = par(R1_fl_c, R2_fl_c)
T_b1b_floor = TB_B1B_MAX + Q * R_eff_floor
T_b1b_floor_c = TB_B1B_MAX + Q * R_eff_floor_c

# 单杆件反解（其余保持当前最坏）：需要的 R1（并联公式，R2 固定 1.411）
def req_R1(R_eff_req, R2):
    g = 1.0 / R_eff_req - 1.0 / R2
    return None if g <= 0 else 1.0 / g

R1_req85 = req_R1(R_req85_b1b, R2_w)
R1_req95 = req_R1(R_req95_b1b, R2_w)
# 导热带单杠杆：R1_rest = R1_w - bar1；需要 bar1 <= R1_req - R1_rest
bar1_cur, bar2_cur = B1B_WORST["minus_Y"]["strap_bar"], B1B_WORST["plus_Y"]["strap_bar"]
R1_rest = R1_w - bar1_cur
bar1_req85 = (R1_req85 - R1_rest) if R1_req85 else None
bar1_req95 = (R1_req95 - R1_rest) if R1_req95 else None
# TIM 单杠杆：四界面全归零后的并联值
R_eff_noTIM = par(R1_w - B1B_WORST["minus_Y"]["TIM_total"], R2_w - B1B_WORST["plus_Y"]["TIM_total"])
# 结构（立柱+板展宽）联合缩放 s：R1=rest1+s*struct1, R2=rest2+s*struct2
struct1 = B1B_WORST["minus_Y"]["arch_riser"] + B1B_WORST["minus_Y"]["plate_spread"]
struct2 = B1B_WORST["plus_Y"]["arch_riser"]
rest1, rest2 = R1_w - struct1, R2_w - struct2

def solve_s(target):
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if par(rest1 + mid * struct1, rest2 + mid * struct2) > target:
            hi = mid
        else:
            lo = mid
    return lo

s85 = solve_s(R_req85_b1b)
s95 = solve_s(R_req95_b1b)
# 边界温度杠杆
Tb_req85_cur_links = T_MARGIN_TARGET - Q * R_eff_cur
Tb_req95_cur_links = T_LIMIT - Q * R_eff_cur
Tb_req85_floor_links = T_MARGIN_TARGET - Q * R_eff_floor

b1b = {
    "model": "T_carrier_max = T_b_eff_max + Q x R_eff；R_eff = (R_-Y+R_bridge) || (R_+Y+R_bridge)",
    "T_b_eff_C": {"min": round(TB_B1B_MIN, 3), "max": round(TB_B1B_MAX, 3), "class": "ESTIMATE_DECLARED"},
    "R_eff_current_worst_K_W": round(R_eff_cur, 5),
    "R_eff_required_K_W": {"target_85C": round(R_req85_b1b, 5), "target_95C_zero_margin": round(R_req95_b1b, 5)},
    "uniform_scale_factor_required": {"target_85C": round(f85_b1b, 4), "target_95C_zero_margin": round(f95_b1b, 4)},
    "joint_physical_floor": {"R_eff_K_W_best": round(R_eff_floor, 5), "R_eff_K_W_conservative": round(R_eff_floor_c, 5),
                             "T_carrier_max_at_floor_C": round(T_b1b_floor, 2),
                             "T_carrier_max_at_floor_conservative_C": round(T_b1b_floor_c, 2),
                             "class": "ESTIMATE_DECLARED"},
    "target_85C_achievable_conduction_only": T_b1b_floor_c <= T_MARGIN_TARGET,
    "REQUIRED_vs_CURRENT": [
        {"parameter": "strap_bar_R（两侧导热带，等效截面）",
         "current_K_W": {"minus_Y": bar1_cur, "plus_Y": bar2_cur,
                         "note": "已加倍截面 750 mm2 后：57.15 mm/(167 x 750e-6)"},
         "required_sole_lever": {"target_85C": "不可行（需要 bar_R <= %s，即负值；即使双带 R=0，R_eff=%.3f > %.3f）"
                                  % (("%.3f" % bar1_req85) if bar1_req85 is not None else "N/A", par(R1_rest, R2_w - bar2_cur), R_req85_b1b),
                                 "target_95C_zero_margin": "不可行（双带 R=0 时 R_eff=%.3f > %.3f）"
                                  % (par(R1_rest, R2_w - bar2_cur), R_req95_b1b)},
         "required_joint_floor_K_W": B1B_FLOOR["strap_bar"],
         "equivalent_section_mm2_at_floor": [1200, 1500],
         "physical_range": "ESTIMATE_DECLARED A<=1500 mm2（25x60，几何/质量约束）",
         "reachability_85C": "NOT_ACHIEVABLE_SOLE_LEVER",
         "reachability_95C": "NOT_ACHIEVABLE_SOLE_LEVER"},
        {"parameter": "TIM_R（4 个压接界面合计）",
         "current_K_W": {"minus_Y": 0.35, "plus_Y": 0.42},
         "required_sole_lever": {"target_85C": "不可行（TIM 全归零 R_eff=%.3f > %.3f）" % (R_eff_noTIM, R_req85_b1b),
                                 "target_95C_zero_margin": "不可行（TIM 全归零 R_eff=%.3f > %.3f）" % (R_eff_noTIM, R_req95_b1b)},
         "required_joint_floor_K_W_per_iface": B1B_FLOOR["TIM_per_iface"],
         "physical_range": "ESTIMATE_DECLARED 0.28 C in2/W @25psi 实现 + 面积 x2；25 psi clamp 未设计",
         "reachability_85C": "NOT_ACHIEVABLE_SOLE_LEVER",
         "reachability_95C": "NOT_ACHIEVABLE_SOLE_LEVER"},
        {"parameter": "arch_riser + plate_spread（结构件，主导热阻）",
         "current_K_W": {"minus_Y_riser_plate": struct1, "plus_Y_riser": struct2},
         "required_sole_lever_scale": {"target_85C": round(s85, 4),
                                       "target_95C_zero_margin": round(s95, 4),
                                       "note": "s=结构件 R 缩放因子；其余件保持当前最坏"},
         "required_joint_floor_K_W": {"riser_minus_Y": B1B_FLOOR["arch_riser_minus_Y"],
                                      "riser_plus_Y": B1B_FLOOR["arch_riser_plus_Y"],
                                      "plate_spread": B1B_FLOOR["plate_spread"]},
         "physical_range": "ESTIMATE_DECLARED：立柱截面 x2 勉强可达；板展宽 x4.5（95C 临界 s=%.2f）需 4 mm 板 -> ~18 mm，物理不可达" % s95,
         "reachability_85C": "NOT_ACHIEVABLE_SOLE_LEVER（s=%.3f << 物理下限 ~0.5）" % s85,
         "reachability_95C": "NOT_ACHIEVABLE_SOLE_LEVER（s=%.3f 要求板展宽超物理范围）" % s95},
        {"parameter": "boundary_T_b_eff（辐射板局部温度，伪参数）",
         "current_C": round(TB_B1B_MAX, 2),
         "required_C": {"target_85C_at_current_links": round(Tb_req85_cur_links, 2),
                        "target_95C_at_current_links": round(Tb_req95_cur_links, 2),
                        "target_85C_at_joint_floor_links": round(Tb_req85_floor_links, 2)},
         "physical_range": "ESTIMATE_DECLARED：仅靠链路改造不动边界；降边界需 +X 蒙皮/辐射面扩展（evidence：桥块+全面积蒙皮名义 86.4 C）",
         "reachability_85C": "REQUIRES_ENVELOPE_CHANGE（当前链路需边界 <=%.1f C，降 %.1f K）" % (Tb_req85_cur_links, TB_B1B_MAX - Tb_req85_cur_links),
         "reachability_95C": "BORDERLINE"},
        {"parameter": "JOINT（全部传导杠杆同时打到声明物理下限）",
         "current_K_W": round(R_eff_cur, 4),
         "required_K_W": {"target_85C": round(R_req85_b1b, 4), "target_95C_zero_margin": round(R_req95_b1b, 4)},
         "joint_floor_K_W": [round(R_eff_floor, 4), round(R_eff_floor_c, 4)],
         "T_at_floor_C": [round(T_b1b_floor, 2), round(T_b1b_floor_c, 2)],
         "reachability_85C": "MARGIN_NOT_ACHIEVABLE_WITHIN_PHYSICAL_RANGE（最好下限组合 T=%.1f C > 85）" % T_b1b_floor,
         "reachability_95C": "ACHIEVABLE_AT_JOINT_PHYSICAL_FLOOR（保守下限 T=%.1f C <= 95，零裕度）" % T_b1b_floor_c},
    ],
    "verdict_85C": "MARGIN_NOT_ACHIEVABLE_WITHIN_PHYSICAL_RANGE",
    "verdict_85C_basis": ("全部传导杠杆同时打到声明物理下限，载板区间上限 %.1f..%.1f C 仍 > 85 C；"
                          "达成 85 C 还需边界温度再降 >= %.1f K（辐射面/蒙皮扩展，超出 B1b 声明范围）。"
                          "95 C 零裕度在联合物理下限可达。" % (T_b1b_floor, T_b1b_floor_c, T_b1b_floor - T_MARGIN_TARGET)),
}

# ================= B2 反解 =================
R_side_cur = link_total(B2_WORST)
R_req85_b2 = (T_MARGIN_TARGET - TB_B2_MAX) / Q2
R_req95_b2 = (T_LIMIT - TB_B2_MAX) / Q2
f85_b2 = R_req85_b2 / R_side_cur
f95_b2 = R_req95_b2 / R_side_cur
R_path_floor = sum(v[0] for v in B2_FLOOR.values())
R_path_floor_c = sum(v[1] for v in B2_FLOOR.values())
T_b2_1rail_floor = TB_B2_MAX + Q2 * R_path_floor
T_b2_1rail_floor_c = TB_B2_MAX + Q2 * R_path_floor_c
T_b2_2rail_floor = TB_B2_MAX + Q2 * R_path_floor / 2.0
T_b2_2rail_floor_c = TB_B2_MAX + Q2 * R_path_floor_c / 2.0
# 纵梁截面单杠杆（其余保持当前最坏 0.95）
R_other_b2 = R_side_cur - B2_WORST["rail"]
R_rail_req85 = R_req85_b2 - R_other_b2
R_rail_req95 = R_req95_b2 - R_other_b2
A_req95_mm2 = (200.0 * 1e-3) / (130.0 * R_rail_req95) * 1e6 if R_rail_req95 > 0 else None
A_req95_mm2_best = (150.0 * 1e-3) / (167.0 * R_rail_req95) * 1e6 if R_rail_req95 > 0 else None
# TIM 单杠杆：两界面归零
R_b2_noTIM = B2_WORST["rail"] + B2_WORST["panel_spread"]
# 每侧纵梁数杠杆
n_rail_req85 = R_path_floor / R_req85_b2     # >1 -> 需要并联
per_rail_req85_dual = 2.0 * R_req85_b2
Tb_req85_b2_cur = T_MARGIN_TARGET - Q2 * R_side_cur
Tb_req95_b2_cur = T_LIMIT - Q2 * R_side_cur
Tb_req85_b2_1rail_floor = T_MARGIN_TARGET - Q2 * R_path_floor

b2 = {
    "model": "T_carrier_max = T_b_eff_max + (Q/2) x R_side；对称双路径，每侧 Q/2 = %.4f W" % Q2,
    "T_b_eff_C": {"min": round(TB_B2_MIN, 3), "max": round(TB_B2_MAX, 3), "class": "ESTIMATE_DECLARED"},
    "R_side_current_worst_K_W": round(R_side_cur, 5),
    "R_side_required_K_W": {"target_85C": round(R_req85_b2, 5), "target_95C_zero_margin": round(R_req95_b2, 5)},
    "uniform_scale_factor_required": {"target_85C": round(f85_b2, 4), "target_95C_zero_margin": round(f95_b2, 4)},
    "joint_physical_floor": {"R_path_K_W_best": round(R_path_floor, 4), "R_path_K_W_conservative": round(R_path_floor_c, 4),
                             "T_1rail_C": [round(T_b2_1rail_floor, 2), round(T_b2_1rail_floor_c, 2)],
                             "T_2rail_per_side_C": [round(T_b2_2rail_floor, 2), round(T_b2_2rail_floor_c, 2)],
                             "class": "ESTIMATE_DECLARED"},
    "REQUIRED_vs_CURRENT": [
        {"parameter": "rail_section（纵梁等效导热截面，主导热阻）",
         "current": {"A_mm2": [700, 900], "R_rail_K_W": [0.998, 2.198]},
         "required_sole_lever": {"target_85C": "不可行（需要 R_rail <= %.3f K/W，即负值）" % R_rail_req85,
                                 "target_95C_zero_margin": {"R_rail_K_W": round(R_rail_req95, 4),
                                                            "A_mm2": [round(A_req95_mm2_best, 0), round(A_req95_mm2, 0)]}},
         "physical_range": "ESTIMATE_DECLARED A<=2000 mm2（45x45，质量/包络约束）",
         "reachability_85C": "NOT_ACHIEVABLE_SOLE_LEVER",
         "reachability_95C": "MARGIN_NOT_ACHIEVABLE_WITHIN_PHYSICAL_RANGE（需 %0.0f..%0.0f mm2 > 2000 mm2 物理上限）" % (A_req95_mm2_best, A_req95_mm2)},
        {"parameter": "TIM_R（载板-纵梁 + 纵梁端角件两界面）",
         "current_K_W": B2_WORST["carrier_to_rail"] + B2_WORST["rail_end"],
         "required_sole_lever": {"target_85C": "不可行（TIM 全归零 R_side=%.3f > %.3f）" % (R_b2_noTIM, R_req85_b2),
                                 "target_95C_zero_margin": "不可行（TIM 全归零 R_side=%.3f > %.3f）" % (R_b2_noTIM, R_req95_b2)},
         "required_joint_floor_K_W": {"carrier_to_rail": B2_FLOOR["carrier_to_rail"], "rail_end": B2_FLOOR["rail_end"]},
         "physical_range": "ESTIMATE_DECLARED 0.28 C in2/W @25psi 实现 + 面积增大",
         "reachability_85C": "NOT_ACHIEVABLE_SOLE_LEVER",
         "reachability_95C": "NOT_ACHIEVABLE_SOLE_LEVER"},
        {"parameter": "rails_per_side（每侧并联纵梁数）",
         "current": 1,
         "required": {"target_85C": {"n_min_continuous": round(n_rail_req85, 3), "n": 2,
                                     "per_rail_R_required_K_W_at_n2": round(per_rail_req85_dual, 4),
                                     "per_rail_physical_floor_K_W": [round(R_path_floor, 4), round(R_path_floor_c, 4)]},
                      "target_95C_zero_margin": {"n": 1, "per_rail_R_required_K_W": round(R_req95_b2, 4)}},
         "reachability_85C": "ACHIEVABLE_WITH_COMBINED_LEVERS（n=2 且每梁路径 R <= %.3f K/W，落在声明物理下限带 [%.3f, %.3f] 内；质量代价 4 梁 ~1.5 kg 未计入裁决）" % (per_rail_req85_dual, R_path_floor, R_path_floor_c),
         "reachability_95C": "ACHIEVABLE_AT_JOINT_PHYSICAL_FLOOR（单梁保守下限 T=%.1f C <= 95，零裕度）" % T_b2_1rail_floor_c},
        {"parameter": "boundary_T_b_eff（辐射板局部温度，伪参数）",
         "current_C": round(TB_B2_MAX, 2),
         "required_C": {"target_85C_at_current_chain": round(Tb_req85_b2_cur, 2),
                        "target_95C_at_current_chain": round(Tb_req95_b2_cur, 2),
                        "target_85C_at_1rail_floor": round(Tb_req85_b2_1rail_floor, 2)},
         "physical_range": "ESTIMATE_DECLARED：当前链路下 85 C 需边界 <= %.1f C（降 %.1f K），不现实；双梁下限组合下边界 79 C 可接受" % (Tb_req85_b2_cur, TB_B2_MAX - Tb_req85_b2_cur),
         "reachability_85C": "NOT_REQUIRED_IF_DUAL_RAIL",
         "reachability_95C": "NOT_REQUIRED_IF_JOINT_FLOOR"},
    ],
    "verdict_85C": "ACHIEVABLE_WITH_COMBINED_LEVERS__DUAL_RAIL_PER_SIDE_REQUIRED",
    "verdict_85C_basis": ("单梁路径即使打到声明物理下限，T=%.1f..%.1f C > 85 C；"
                          "每侧双梁并联 + 全界面下限时 T=%.1f..%.1f C，最好点 %.1f C <= 85 C 达成 10 K 裕度，"
                          "保守点 %.1f C 仍跨限 -> 需 FE/试验压缩界面与梁截面不确定性后才可判 PASS。"
                          % (T_b2_1rail_floor, T_b2_1rail_floor_c, T_b2_2rail_floor, T_b2_2rail_floor_c,
                             T_b2_2rail_floor, T_b2_2rail_floor_c)),
}

out = {
    "schema": "THERMAL_ARCHITECTURE_B_DESIGN_TARGETS",
    "date": "2026-09-17",
    "author_tool": "implementation/tools/thermal_architecture_b_design_targets_20260917.py",
    "prior_screen_readonly": PRIOR,
    "method": ("需求反解：目标 M = 载板不确定区间上限 <= 85 C（95 C 限留 >=10 K）；目标 Z = <= 95 C 零裕度临界。"
               "对每个关键设计参数：(a) 单杠杆反解（其余保持当前最坏）；(b) 联合物理下限组合（全部杠杆同时打到 ESTIMATE_DECLARED 下限）。"
               "所有物理可达范围为 ESTIMATE_DECLARED；证据锚点 CALCULATED_FROM_EVIDENCE。"
               "不修改 THERMAL_ARCHITECTURE_B_SCREEN_20260917.json；不改动任何既有证据/gate 文件。"),
    "targets": {"limit_C": T_LIMIT, "margin_target_C": T_MARGIN_TARGET, "margin_K": 10.0},
    "heat_loads_W": {"Q_module": Q, "Q_per_side_B2": Q2, "STOP_board_boundary_increment": "同 screen（+0.5..1.5 K）"},
    "B1b_bridge_plus_doubled_straps": b1b,
    "B2_longeron_deck_direct_to_panels": b2,
    "dominant_R_summary": {
        "B1b": {"dominant": "arch_riser+plate_spread（结构件，-Y 侧 2.00/2.93 K/W）",
                "required_vs_current": "联合下限组合 R_eff %.3f->需 %.3f（85C）/%.3f（95C）K/W" % (R_eff_cur, R_req85_b1b, R_req95_b1b)},
        "B2": {"dominant": "rail lateral（当前最坏 2.198/3.148 K/W per side）",
               "required_vs_current": "R_side %.3f->需 %.3f（85C）/%.3f（95C）K/W" % (R_side_cur, R_req85_b2, R_req95_b2)},
    },
    "Q201_Tj_note": ("载板 85 C 目标达成时 Tj = 85 + %.2f = %.1f C <= 150 C，载板限仍为先约束。"
                     % (Q201_Q * Q201_R, T_MARGIN_TARGET + Q201_Q * Q201_R)),
    "caveats": [
        "全部物理下限为 ESTIMATE_DECLARED，无供应商数据/试验支撑；TIM 25 psi clamp 未设计",
        "边界温度带（含 STOP 1.483 W 增量）为声明区间；未分配热 33.27 W 未计入（计入将进一步压缩可达性）",
        "B2 双梁方案质量 ~1.5 kg、机械接口与窄相位未评估；模块位姿 REJECTED 状态不变",
        "本文件是需求反解，不是设计放行；PASS/FAIL 仍须 FE 或试验裁决",
    ],
    "verdict": "ARCHITECTURE_B_DESIGN_TARGETS_EMITTED__FE_OR_TEST_REQUIRED",
    "review_status": "PENDING_REVIEW",
    "next_stage_authorized": False,
    "whole_design_complete": False,
    "manufacturing_release": False,
}

payload = (json.dumps(out, ensure_ascii=False, indent=1) + "\n").encode("utf-8")
assert b"\r" not in payload, "CRLF guard"
with open(OUT, "wb") as fh:
    fh.write(payload)
digest = hashlib.sha256(payload).hexdigest()
with open(str(OUT) + ".sha256", "wb") as fh:
    fh.write((digest + "  " + OUT.name + "\n").encode("ascii"))

print("B1b: R_eff current %.3f -> required %.3f (85C) / %.3f (95C); floor T %.1f..%.1f C -> %s"
      % (R_eff_cur, R_req85_b1b, R_req95_b1b, T_b1b_floor, T_b1b_floor_c, b1b["verdict_85C"]))
print("B2 : R_side current %.3f -> required %.3f (85C) / %.3f (95C); 1-rail floor T %.1f..%.1f; 2-rail floor T %.1f..%.1f -> %s"
      % (R_side_cur, R_req85_b2, R_req95_b2, T_b2_1rail_floor, T_b2_1rail_floor_c,
         T_b2_2rail_floor, T_b2_2rail_floor_c, b2["verdict_85C"]))
print("B2 rail A required (95C sole lever): %.0f..%.0f mm2 vs phys max 2000" % (A_req95_mm2_best, A_req95_mm2))
print("sha256:", digest)
print("out:", OUT)
