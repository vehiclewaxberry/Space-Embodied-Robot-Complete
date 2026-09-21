# -*- coding: utf-8 -*-
"""
compute_candidates.py — F4R1 C3 阶段第一步：三个候选内部结构架构的质量/CG 机器复算
====================================================================================
仅标准库 (os/re/json/math/csv/hashlib)。确定性：无随机数，generated_at 固定 2026-08-27。

输入（只读）：
  - ../../50_c1_layout/EQUIPMENT_LIST_V1.yaml      (regex 提取设备 id + mounting_face，做覆盖核查)
  - ../../../30_simulation/sim_06_capture_impulse/results/capture_impulse_matrix_v0.csv
      (max |J| 与 max |couple| → T_c=20 ms 半正弦窗峰值力/力矩)
  - ./CANDIDATE_ARCHITECTURES_V1.yaml              (regex 提取 members mass_g 与 equipment_mounting_map，做一致性核查)

方法：
  - 构件质量 = dims_mm 体积 × 材料密度 × count × fill_factor （长方体估计，DESIGN_RESEARCH_CANDIDATE 级）
  - 全船 CG：把 C1 CG_INERTIA_CHECK_V1.json 中 CG 中性的 EQ-SEC-STRUCT 1.0 kg@[0,0,0] 占位
    替换为本候选构件质点组，两口径（SCENARIO_A / SCENARIO_CDS_VARIANT）分别复算
  - C1 基线数值硬编码自 CG_INERTIA_CHECK_V1.json (sha256_12 c7759162f54d)，并在 JSON 中登记

输出：CANDIDATE_MASS_CG_V1.json （同目录）
"""
import os, re, json, math, csv, hashlib

GENERATED_AT = "2026-08-27"
HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                      # F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1
ENG = os.path.dirname(PKG)                       # 20_engineering
ROOT = os.path.dirname(ENG)                      # 项目根

def p_rel(*parts):
    return os.path.join(ROOT, *parts)

def sha256_12(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:12]

# ---------------------------------------------------------------- 材料密度表
# 6061-T6 2700 kg/m3: 仓内出处 02_PRODUCT_STRUCTURE.yaml SPACECRAFT_LOAD_BRIDGE
#   "mass_class: MATERIAL_DERIVED 6061-T6 2700 kg/m3" (sha256_12 0f9897ef4e41)
# 其余标 ASSUMED（工程手册常规值，仓内无权威行）
DENSITIES = {
    "al6061":   {"rho_kg_m3": 2700.0, "provenance": "repo:20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/02_PRODUCT_STRUCTURE.yaml#SPACECRAFT_LOAD_BRIDGE MATERIAL_DERIVED 6061-T6 2700 kg/m3 (sha256_12 0f9897ef4e41)"},
    "al7075":   {"rho_kg_m3": 2810.0, "provenance": "ASSUMED: 工程手册常规值 2810 kg/m3 (CDS §2.2.12 许可材料, B1 §1.2)"},
    "cfrp":     {"rho_kg_m3": 1600.0, "provenance": "ASSUMED: 准各向同性 CFRP 板典型 1550-1650 kg/m3 取中值"},
    "steel":    {"rho_kg_m3": 7800.0, "provenance": "ASSUMED: 普通结构钢 7800 kg/m3 (压载块)"},
    "isolator": {"rho_kg_m3": 3000.0, "provenance": "ASSUMED: 金属-弹性体隔振器等效密度 3000 kg/m3"},
}

# ---------------------------------------------------------------- C1 基线（CG_INERTIA_CHECK_V1.json sha256_12 c7759162f54d）
SEC_STRUCT_PLACEHOLDER_KG = 1.0   # EQ-SEC-STRUCT 占位，CG 中性 [0,0,0]
SCENARIOS = {
    "SCENARIO_A_DESIGN_POINT": {
        "total_mass_kg": 31.022864807342987,
        "cg_S_mm": [63.24250788155471, -26.880696522506742, -19.021853790155188],
        "note": "C1 主口径（读法 A 切出），ODR 登记 31.0229 kg；结构质量变化按新候选差异声明登记，不改 ODR 值",
    },
    "SCENARIO_CDS_VARIANT_24KG": {
        "total_mass_kg": 15.356651407342985,
        "cg_S_mm": [127.82659726897663, -54.30325870040869, -39.10243515039356],
        "note": "C1 CDS 合规变体（干重，未含 15% 余量）；现状 x 超差 -57.83 mm / y -9.30 mm（GATE_C1 OI-1）",
    },
}
CDS_ENVELOPE_MM = {"x": 70.0, "y": 45.0, "z": 45.0}   # CDS Table 2 (B1 §1.1)
CDS_MASS_LIMIT_KG = 24.0
SYSTEM_MARGIN = 0.15                                  # B1 R2 / VMMO 15%

# ---------------------------------------------------------------- 候选架构构件表
# dims_mm = [x,y,z] 长方体估计；pos_mm = 构件质心 S frame；fill_factor = 挖空/轻质化系数
CANDIDATES = {
    "CA-A": {
        "concept_zh": "中央堆栈+托盘：中舱 PC/104 双堆栈笼 + 前/后托盘，COTS 兼容优先",
        "members": [
            {"name": "stack_cage_rails",        "type": "rail",     "dims_mm": [120, 6, 6],     "material": "al6061", "count": 8, "fill_factor": 1.0,  "pos_mm": [0, -60, 30],   "function": "PC/104 双堆栈笼角轨 (OBC+EPS 堆栈 A)"},
            {"name": "stack_cage_endplates",    "type": "plate",    "dims_mm": [96, 90, 1.5],   "material": "al6061", "count": 4, "fill_factor": 1.0,  "pos_mm": [0, -60, 30],   "function": "堆栈笼端板，先成组件整体入框 (B1 R5)"},
            {"name": "battery_plate",           "type": "plate",    "dims_mm": [180, 96, 2],    "material": "al6061", "count": 1, "fill_factor": 1.0,  "pos_mm": [-10, 0, -75],  "function": "双 BPX 电池独立 -z 安装面 (B1 R9)"},
            {"name": "rw_cluster_bracket",      "type": "bracket",  "dims_mm": [70, 70, 4],     "material": "al6061", "count": 2, "fill_factor": 1.0,  "pos_mm": [0, 0, 0],      "function": "4xRW400 金字塔轮组支架 (近几何中心, B1 R6)"},
            {"name": "front_tray",              "type": "plate",    "dims_mm": [200, 210, 2],   "material": "al6061", "count": 1, "fill_factor": 1.0,  "pos_mm": [120, 0, 0],    "function": "前舱任务托盘 (CAM-NAV/ILLUM/SS5)"},
            {"name": "rear_tray",               "type": "plate",    "dims_mm": [220, 210, 2.5], "material": "al6061", "count": 1, "fill_factor": 1.0,  "pos_mm": [-113.5, 0, 0], "function": "后舱服务托盘 (MiPS/电台/GPS)"},
            {"name": "mid_deck",                "type": "plate",    "dims_mm": [100, 210, 1.5], "material": "al6061", "count": 1, "fill_factor": 1.0,  "pos_mm": [50, 0, 0],     "function": "中舱甲板 (MTQ-X/Z 等)"},
            {"name": "corner_posts",            "type": "rail",     "dims_mm": [60, 8, 8],      "material": "al6061", "count": 8, "fill_factor": 1.0,  "pos_mm": [0, 0, 0],      "function": "托盘/甲板与主结构连接角柱"},
            {"name": "panel_root_hinge_brackets","type": "bracket", "dims_mm": [40, 30, 6],     "material": "al6061", "count": 4, "fill_factor": 1.0,  "pos_mm": [-61, 0, 0],    "function": "帆板根铰/HDRM 站位安装座 (F_L/F_R, 每翼 2 站)"},
        ],
    },
    "CA-B": {
        "concept_zh": "三舱隔框+剪切板盒式：双隔框 + 纵向长梁 + 中舱剪切盒 + 前后剪切腹板，刚度/传力优先",
        "members": [
            {"name": "bulkhead_front",          "type": "bulkhead", "dims_mm": [3, 220, 220],   "material": "al6061", "count": 1, "fill_factor": 0.65, "pos_mm": [56.75, 0, 0],  "function": "front/mid 舱界隔框 (x=+56.75), 35% 挖空"},
            {"name": "bulkhead_rear",           "type": "bulkhead", "dims_mm": [3, 220, 220],   "material": "al6061", "count": 1, "fill_factor": 0.65, "pos_mm": [-56.75, 0, 0], "function": "mid/rear 舱界隔框 (x=-56.75), 35% 挖空"},
            {"name": "longerons",               "type": "rail",     "dims_mm": [340, 10, 10],   "material": "al6061", "count": 4, "fill_factor": 1.0,  "pos_mm": [0, 0, 0],      "function": "四角纵向长梁 (避开 CDS 8.5 mm 导轨带, B1 R1)"},
            {"name": "shear_mid_top",           "type": "plate",    "dims_mm": [113.5, 220, 1.5],"material": "al6061", "count": 1, "fill_factor": 0.85, "pos_mm": [0, 0, 111],   "function": "中舱剪切盒顶板"},
            {"name": "shear_mid_bottom",        "type": "plate",    "dims_mm": [113.5, 220, 1.5],"material": "al6061", "count": 1, "fill_factor": 0.85, "pos_mm": [0, 0, -111],  "function": "中舱剪切盒底板"},
            {"name": "shear_mid_left",          "type": "plate",    "dims_mm": [113.5, 1.5, 220],"material": "al6061", "count": 1, "fill_factor": 0.85, "pos_mm": [0, 111, 0],   "function": "中舱剪切盒 +y 侧板"},
            {"name": "shear_mid_right",         "type": "plate",    "dims_mm": [113.5, 1.5, 220],"material": "al6061", "count": 1, "fill_factor": 0.85, "pos_mm": [0, -111, 0],  "function": "中舱剪切盒 -y 侧板"},
            {"name": "front_shear_web",         "type": "plate",    "dims_mm": [110, 200, 3],   "material": "al6061", "count": 1, "fill_factor": 0.7,  "pos_mm": [125, 0, 0],    "function": "前舱剪切腹板: 隔框→前法兰站传力 (臂基座载荷)"},
            {"name": "rear_shear_web",          "type": "plate",    "dims_mm": [110, 200, 3],   "material": "al6061", "count": 1, "fill_factor": 0.7,  "pos_mm": [-125, 0, 0],   "function": "后舱剪切腹板: 隔框→后面板传力"},
            {"name": "arm_base_gussets",        "type": "bracket",  "dims_mm": [40, 40, 5],     "material": "al6061", "count": 4, "fill_factor": 1.0,  "pos_mm": [170, 0, 0],    "function": "臂基座/前法兰角撑 (x=196-210 载荷扩散, 配合冻结 M3R+bridge)"},
            {"name": "stack_frame_rails",       "type": "rail",     "dims_mm": [120, 6, 6],     "material": "al6061", "count": 8, "fill_factor": 1.0,  "pos_mm": [0, -60, 30],   "function": "中舱设备堆栈笼角轨"},
            {"name": "stack_frame_endplates",   "type": "plate",    "dims_mm": [96, 90, 1.5],   "material": "al6061", "count": 4, "fill_factor": 1.0,  "pos_mm": [0, -60, 30],   "function": "堆栈笼端板"},
            {"name": "battery_plate",           "type": "plate",    "dims_mm": [180, 96, 2],    "material": "al6061", "count": 1, "fill_factor": 1.0,  "pos_mm": [-10, 0, -75],  "function": "双 BPX 电池独立 -z 安装面 (B1 R9)"},
            {"name": "rw_cluster_bracket",      "type": "bracket",  "dims_mm": [70, 70, 4],     "material": "al6061", "count": 2, "fill_factor": 1.0,  "pos_mm": [0, 0, 0],      "function": "4xRW400 金字塔轮组支架"},
            {"name": "panel_root_hinge_brackets","type": "bracket", "dims_mm": [40, 30, 6],     "material": "al6061", "count": 4, "fill_factor": 1.0,  "pos_mm": [-61, 0, 0],    "function": "帆板根铰/HDRM 站位安装座"},
        ],
    },
    "CA-C": {
        "concept_zh": "混合集成压载：中舱框架堆栈 + 后舱推进/压载一体化模块 + 前舱任务设备隔振安装，CG 优先 (针对 CDS 变体 OI-1)",
        "members": [
            {"name": "mid_frame_rails",         "type": "rail",     "dims_mm": [120, 8, 8],     "material": "al6061", "count": 8, "fill_factor": 1.0,  "pos_mm": [0, -40, 20],   "function": "中舱框架堆栈角轨"},
            {"name": "mid_frame_decks",         "type": "plate",    "dims_mm": [200, 180, 1.5], "material": "cfrp",   "count": 2, "fill_factor": 1.0,  "pos_mm": [0, 0, 0],      "function": "中舱 CFRP 设备甲板 x2 (轻量)"},
            {"name": "battery_plate",           "type": "plate",    "dims_mm": [180, 96, 2],    "material": "al6061", "count": 1, "fill_factor": 1.0,  "pos_mm": [-10, 0, -75],  "function": "双 BPX 电池独立 -z 安装面 (B1 R9)"},
            {"name": "rw_cluster_bracket",      "type": "bracket",  "dims_mm": [70, 70, 4],     "material": "al6061", "count": 2, "fill_factor": 1.0,  "pos_mm": [0, 0, 0],      "function": "4xRW400 金字塔轮组支架"},
            {"name": "rear_module_deck",        "type": "plate",    "dims_mm": [220, 210, 3],   "material": "al7075", "count": 1, "fill_factor": 1.0,  "pos_mm": [-150, 0, 0],   "function": "后舱推进/压载一体化模块主甲板 (MiPS 升级 2U 兼容, OI-7)"},
            {"name": "rear_module_sideplates",  "type": "plate",    "dims_mm": [40, 210, 2],    "material": "al7075", "count": 2, "fill_factor": 1.0,  "pos_mm": [-150, 0, 0],   "function": "后舱模块侧板 x2"},
            {"name": "ballast_steel",           "type": "plate",    "dims_mm": [15, 140, 220],  "material": "steel",  "count": 1, "fill_factor": 1.0,  "pos_mm": [-163, 40, 0],  "function": "后部压载钢块 (~3.2 kg 级, C1 OI-1 补救; +y 偏移配平 y 超差; 贴后面板 x∈[-170.25,-155.75])"},
            {"name": "front_iso_brackets",      "type": "bracket",  "dims_mm": [40, 40, 3],     "material": "al6061", "count": 4, "fill_factor": 1.0,  "pos_mm": [150, 0, 40],   "function": "前舱任务设备隔振安装支架 x4"},
            {"name": "isolator_elements",       "type": "bracket",  "dims_mm": [20, 20, 15],    "material": "isolator","count": 4, "fill_factor": 1.0, "pos_mm": [150, 0, 40],   "function": "金属-弹性体隔振器 x4 (相机/照明与臂扰动隔离, sim_05 19.2°)"},
            {"name": "front_deck",              "type": "plate",    "dims_mm": [200, 210, 1.5], "material": "cfrp",   "count": 1, "fill_factor": 1.0,  "pos_mm": [120, 0, 0],    "function": "前舱 CFRP 轻甲板"},
            {"name": "panel_root_hinge_brackets","type": "bracket", "dims_mm": [40, 30, 6],     "material": "al6061", "count": 4, "fill_factor": 1.0,  "pos_mm": [-61, 0, 0],    "function": "帆板根铰/HDRM 站位安装座"},
        ],
    },
}

# ---------------------------------------------------------------- 计算
def member_mass_g(m):
    vol_mm3 = m["dims_mm"][0] * m["dims_mm"][1] * m["dims_mm"][2]
    return vol_mm3 * DENSITIES[m["material"]]["rho_kg_m3"] * 1e-6 * m["count"] * m["fill_factor"]

def scenario_replace(sec_struct_placeholder_kg, scenario, members):
    """把 CG 中性 1.0 kg@[0,0,0] 占位替换为候选构件质点组，复算两口径 CG。"""
    M0 = scenario["total_mass_kg"]
    cg0 = scenario["cg_S_mm"]
    M_s = sum(member_mass_g(m) for m in members) / 1000.0   # kg
    M1 = M0 - sec_struct_placeholder_kg + M_s
    num = [M0 * cg0[i] - sec_struct_placeholder_kg * 0.0 + sum(member_mass_g(m) * m["pos_mm"][i] for m in members) / 1000.0 for i in range(3)]
    cg1 = [num[i] / M1 for i in range(3)]
    delta = [cg1[i] - cg0[i] for i in range(3)]
    margins = {"x": CDS_ENVELOPE_MM["x"] - abs(cg1[0]),
               "y": CDS_ENVELOPE_MM["y"] - abs(cg1[1]),
               "z": CDS_ENVELOPE_MM["z"] - abs(cg1[2])}
    return {"new_total_mass_kg": M1, "structure_mass_kg": M_s,
            "new_cg_S_mm": cg1, "cg_delta_mm": delta,
            "cds_margins_mm": margins,
            "mass_with_15pct_margin_kg": M1 * (1.0 + SYSTEM_MARGIN),
            "cds_mass_pass": M1 * (1.0 + SYSTEM_MARGIN) <= CDS_MASS_LIMIT_KG}

# ---------------------------------------------------------------- 捕获冲量 → 峰值力/力矩
def capture_loads():
    p_csv = p_rel("30_simulation", "sim_06_capture_impulse", "results", "capture_impulse_matrix_v0.csv")
    j_max = l_max = 0.0
    with open(p_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            j_max = max(j_max, abs(float(row["contact_impulse_N_s"])))
            l_max = max(l_max, abs(float(row["grasp_couple_N_m_s"])))
    t_c = 0.020   # s, PROVISIONAL (scene_A2_capture.yaml sha256_12 4b979a1dfd18, 待夹爪实测 GAP-IF-01)
    peak_force = (math.pi / 2.0) * j_max / t_c        # 半正弦窗峰值 = π/2 × 均值
    peak_moment = (math.pi / 2.0) * l_max / t_c
    return {"j_max_N_s": j_max, "couple_max_N_m_s": l_max, "t_c_s": t_c,
            "peak_force_N_half_sine": peak_force, "peak_moment_N_m_half_sine": peak_moment,
            "source": "30_simulation/sim_06_capture_impulse/results/capture_impulse_matrix_v0.csv (max |J|, max |couple| over 40 cases)"}

# ---------------------------------------------------------------- 一致性核查（regex，stdlib）
def parse_equipment_faces():
    p_yaml = os.path.join(PKG, "50_c1_layout", "EQUIPMENT_LIST_V1.yaml")
    txt = open(p_yaml, encoding="utf-8").read()
    blocks = re.split(r"\n  - id: ", txt)
    items = {}
    for b in blocks[1:]:
        eid = b.split("\n", 1)[0].strip()
        m = re.search(r"mounting_face:\s*(\S+)", b)
        items[eid] = m.group(1) if m else None
    return items

def parse_candidate_yaml():
    p_yaml = os.path.join(HERE, "CANDIDATE_ARCHITECTURES_V1.yaml")
    if not os.path.exists(p_yaml):
        return None
    txt = open(p_yaml, encoding="utf-8").read()
    # members mass_g: `- name: xxx` 块内 `mass_g: v`
    masses = {}
    for m in re.finditer(r"-\s*name:\s*(\S+)(.*?)mass_g:\s*([\d.]+)", txt, re.S):
        masses[m.group(1)] = float(m.group(3))
    # equipment_mounting_map 各区间的 key
    maps = {}
    for cm in re.finditer(r"-\s*id:\s*(CA-[ABC])(.*?)(?=\n-\s*id:\s*CA-|\Z)", txt, re.S):
        cid, body = cm.group(1), cm.group(2)
        sec = re.search(r"equipment_mounting_map:\s*\n((?:\s{4,}\S+:\s*\S+\n?)+)", body)
        keys = set()
        if sec:
            keys = set(re.findall(r"^\s{4,}(\S+):", sec.group(1), re.M))
        maps[cid] = keys
    return {"masses": masses, "maps": maps}

def main():
    equipment = parse_equipment_faces()
    faces_needed = set(v for v in equipment.values() if v)
    cyaml = parse_candidate_yaml()

    out = {
        "title": "F4R1 C3 候选内部结构架构 质量/CG 机器复算 V1",
        "generated_at": GENERATED_AT,
        "status": "DESIGN_RESEARCH_CANDIDATE",
        "method": "构件=长方体×密度×count×fill_factor；CG=替换 C1 CG 中性 1.0 kg@[0,0,0] 二级结构占位为构件质点组；两口径 (SCENARIO_A / CDS_VARIANT) 分别复算",
        "inputs": {
            "equipment_list": {"path": "20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/50_c1_layout/EQUIPMENT_LIST_V1.yaml",
                               "sha256_12": sha256_12(os.path.join(PKG, "50_c1_layout", "EQUIPMENT_LIST_V1.yaml"))},
            "cg_baseline": {"path": "20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/50_c1_layout/CG_INERTIA_CHECK_V1.json",
                            "sha256_12": sha256_12(os.path.join(PKG, "50_c1_layout", "CG_INERTIA_CHECK_V1.json")),
                            "note": "基线数值硬编码引用 (SCENARIO_A / CDS_VARIANT 总质量与 CG)"},
            "capture_csv": {"path": "30_simulation/sim_06_capture_impulse/results/capture_impulse_matrix_v0.csv",
                            "sha256_12": sha256_12(p_rel("30_simulation", "sim_06_capture_impulse", "results", "capture_impulse_matrix_v0.csv"))},
            "candidate_yaml": {"path": "20_engineering/F4R1_INTERNAL_CONFIGURATION_COMPLETION_V1/55_c3_design_basis/CANDIDATE_ARCHITECTURES_V1.yaml",
                               "sha256_12": sha256_12(os.path.join(HERE, "CANDIDATE_ARCHITECTURES_V1.yaml")) if os.path.exists(os.path.join(HERE, "CANDIDATE_ARCHITECTURES_V1.yaml")) else "PENDING"},
        },
        "densities": DENSITIES,
        "cds_envelope_mm": CDS_ENVELOPE_MM,
        "system_margin": SYSTEM_MARGIN,
        "capture_loads": capture_loads(),
        "candidates": {},
        "checks": {},
    }

    for cid, cand in CANDIDATES.items():
        members_out = []
        for m in cand["members"]:
            mg = member_mass_g(m)
            members_out.append({**m, "mass_g": round(mg, 3), "density_kg_m3": DENSITIES[m["material"]]["rho_kg_m3"]})
        struct_kg = sum(mm["mass_g"] for mm in members_out) / 1000.0
        res = {"concept_zh": cand["concept_zh"], "members": members_out,
               "structure_mass_kg": round(struct_kg, 6),
               "structure_mass_proper_excl_ballast_kg": round(sum(mm["mass_g"] for mm in members_out if mm["name"] != "ballast_steel") / 1000.0, 6),
               "est_mass_growth_vs_budget_pct": round((struct_kg / SEC_STRUCT_PLACEHOLDER_KG - 1.0) * 100.0, 2),
               "budget_ref": "C1 MASS_BUDGET_V1.csv EQ-SEC-STRUCT = 1.0 kg (ASSUMED 行, sha256_12 365c9ebf9493)",
               "scenarios": {}}
        for sid, sc in SCENARIOS.items():
            r = scenario_replace(SEC_STRUCT_PLACEHOLDER_KG, sc, cand["members"])
            r["baseline_total_mass_kg"] = sc["total_mass_kg"]
            r["baseline_cg_S_mm"] = sc["cg_S_mm"]
            r["note"] = sc["note"]
            res["scenarios"][sid] = r
        out["candidates"][cid] = res

    # ---- checks
    checks = {}
    # 1) 设备安装面覆盖：每候选 equipment_mounting_map 必须覆盖 C1 全部 mounting_face
    if cyaml:
        cov = {}
        for cid in CANDIDATES:
            have = cyaml["maps"].get(cid, set())
            missing = sorted(faces_needed - have)
            cov[cid] = {"faces_required": len(faces_needed), "faces_mapped": len(have & faces_needed),
                        "missing": missing, "pass": len(missing) == 0}
        checks["equipment_mounting_map_coverage"] = cov
        checks["equipment_rows_parsed"] = len(equipment)
        # 2) YAML mass_g 与脚本复算一致 (±0.5 g 容差)
        mass_ok, diffs = True, []
        for cid, cand in CANDIDATES.items():
            for m in cand["members"]:
                yv = cyaml["masses"].get(cid + "/" + m["name"], cyaml["masses"].get(m["name"]))
                cv = member_mass_g(m)
                if yv is None:
                    diffs.append({"member": m["name"], "issue": "missing_in_yaml"}); mass_ok = False
                elif abs(yv - cv) > 0.5:
                    diffs.append({"member": m["name"], "yaml": yv, "computed": round(cv, 3)}); mass_ok = False
        checks["yaml_mass_consistency"] = {"pass": mass_ok, "diffs": diffs}
    else:
        checks["note"] = "CANDIDATE_ARCHITECTURES_V1.yaml 尚不存在，跳过一致性核查"

    out["checks"] = checks
    p_out = os.path.join(HERE, "CANDIDATE_MASS_CG_V1.json")
    with open(p_out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("written:", p_out)
    for cid in CANDIDATES:
        c = out["candidates"][cid]
        a = c["scenarios"]["SCENARIO_A_DESIGN_POINT"]
        v = c["scenarios"]["SCENARIO_CDS_VARIANT_24KG"]
        print(f"{cid}: structure={c['structure_mass_kg']:.4f} kg (growth {c['est_mass_growth_vs_budget_pct']:+.1f}%)")
        print(f"   A : M={a['new_total_mass_kg']:.4f} kg CG={[round(x,2) for x in a['new_cg_S_mm']]} margins={ {k: round(x,2) for k,x in a['cds_margins_mm'].items()} }")
        print(f"   CDS: M={v['new_total_mass_kg']:.4f} kg (+15%={v['mass_with_15pct_margin_kg']:.2f}) CG={[round(x,2) for x in v['new_cg_S_mm']]} margins={ {k: round(x,2) for k,x in v['cds_margins_mm'].items()} } pass={v['cds_mass_pass']}")
    cl = out["capture_loads"]
    print(f"capture: |J|max={cl['j_max_N_s']:.4f} N·s |L|max={cl['couple_max_N_m_s']:.4f} N·m·s -> peak {cl['peak_force_N_half_sine']:.1f} N / {cl['peak_moment_N_m_half_sine']:.1f} N·m (T_c=20ms half-sine)")

if __name__ == "__main__":
    main()
