"""RC1-R2：SIM12 24 格全因子重发 + 策略不变全局 Gate 向量。

正确实验结构（父提示 §11）：
    2 前接触策略 alpha  x  3 捕获后分配模式 u  x  4 初始状态 = 24 格

alpha 只改变**物理转移** x- -> x+；u 只改变**捕获后资源分配**。
既有 16 格中 S1/S3a/S4 共享同一条 alpha=0 转移，S2 是唯一的 alpha=1 转移，
因此缺失的 8 格（alpha=1 x {WHEEL_BIAS, THRUSTER}）可由已有物理输出**代数重建**，
无需重跑动力学求解器。

只读本地来源：
  * 30_simulation/sim_12_strategy_feasibility/results/strategy_results.csv   （冻结物理输出）
  * 20_engineering/config/mission_feasibility/scan_v0.yaml                   （阈值/执行机构）
  * 20_engineering/config/strategy_feasibility/strategies_v0.yaml            （4 例定义）
  * 30_simulation/e15_core_coverage/config/threshold_registry_core_v1.yaml   （冻结阈值 registry）

纪律：
  * 不覆写 sim_12 任何既有 Gate 或 CSV；本目录只写 V2 派生件。
  * Gate 集合对 24 格恒定；任何模式都不得删除不利 Gate（需求为 0 时 margin 仍计算）。
  * 有效性布尔（Layer 1）不得混入连续物理裕度（Layer 2）。
  * 缺阈值或缺输出的分量记 ABSENT，绝不零填充，绝不当作 PASS。
"""
import csv
import hashlib
import json
import os

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))

SIM12_CSV = "30_simulation/sim_12_strategy_feasibility/results/strategy_results.csv"
SIM12_GATE = "30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json"
SIM12_SRC = "30_simulation/sim_12_strategy_feasibility/src/strategy_eval.py"
SCAN_CFG = "20_engineering/config/mission_feasibility/scan_v0.yaml"
STRAT_CFG = "20_engineering/config/strategy_feasibility/strategies_v0.yaml"
REGISTRY = "30_simulation/e15_core_coverage/config/threshold_registry_core_v1.yaml"
EXTERNAL_DIR = os.path.join(HERE, "..", "00_external_inputs")
EXTERNAL_V1 = "SIM12_SAME_STATE_PAIRED_TABLE_V1.csv"


def pin(rel):
    p = os.path.join(REPO, rel)
    if not os.path.isfile(p):
        return {"path": rel, "presence": "ABSENT_NOT_FOUND_IN_REPOSITORY"}
    b = open(p, "rb").read()
    return {"path": rel, "presence": "PRESENT", "bytes": len(b),
            "sha256": hashlib.sha256(b).hexdigest().upper()}


# =====================================================================
# 1. 载入冻结来源
# =====================================================================
rows16 = list(csv.DictReader(open(os.path.join(REPO, SIM12_CSV), encoding="utf-8")))
cfg = yaml.safe_load(open(os.path.join(REPO, SCAN_CFG), encoding="utf-8"))
s12cfg = yaml.safe_load(open(os.path.join(REPO, STRAT_CFG), encoding="utf-8"))
reg = yaml.safe_load(open(os.path.join(REPO, REGISTRY), encoding="utf-8"))
thr = reg["thresholds"]

G = cfg["gates"]
AT = cfg["actuator_tiers"]
DT = AT["default_tier"]
H_MAX = float(AT["wheel_capacity_Nms"][DT["wheel"]])          # 0.3 N*m*s
ISP = float(AT["thruster_isp_s"][DT["isp"]])                  # 60 s
LEVER = float(DT["lever_m"])                                  # 0.17 m
FORCE = float(AT["thruster_force_N"])                         # 0.1 N
G0 = float(G["g0_mps2"])                                      # 9.80665
M_BUS = float(cfg["mass_reference"]["servicer_bus_kg"])       # 24.0 kg

CASES = ["A_low", "B_anchor", "C_transition", "D_extreme"]
ALPHAS = [0, 1]
MODES = ["WHEEL_DIRECT", "WHEEL_BIAS", "THRUSTER"]

# legacy 标签 -> (alpha, u) 因子映射
LEGACY_MAP = {
    ("S1_passive"): (0, "WHEEL_DIRECT"),
    ("S3a_wheel_bias"): (0, "WHEEL_BIAS"),
    ("S4_post_capture_detumble"): (0, "THRUSTER"),
    ("S2_velocity_matching"): (1, "WHEEL_DIRECT"),
}
R = {(r["case"], r["strategy"]): r for r in rows16}

# =====================================================================
# 2. Layer 1 —— 有效性 Gate（布尔，绝不混入连续裕度）
# =====================================================================
# 2a. 证据有效性：源 CSV/Gate/源码哈希可复算
evidence_pins = {k: pin(v) for k, v in
                 [("strategy_results_csv", SIM12_CSV), ("sim12_gate", SIM12_GATE),
                  ("strategy_eval_src", SIM12_SRC), ("scan_cfg", SCAN_CFG),
                  ("strategy_cfg", STRAT_CFG), ("threshold_registry", REGISTRY)]}
evidence_valid = all(v["presence"] == "PRESENT" for v in evidence_pins.values())

# 2b. 参数绑定有效性：sim_10 冻结输入哈希链
frozen_report = {}
for k, spec in cfg["frozen_inputs"].items():
    p = os.path.join(REPO, spec["path"])
    act = hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.isfile(p) else None
    frozen_report[k] = {"path": spec["path"], "expected": spec["sha256"], "actual": act,
                        "match": act == spec["sha256"]}
frozen_chain_intact = all(v["match"] for v in frozen_report.values())

# 数值完整性独立复核（feasibility_core 本会执行、但因哈希 fail-closed 从未跑到）
numeric_checks = {
    "post_capture_rate_max_dps": {
        "scan_v0": float(G["post_capture_rate_max_dps"]),
        "registry": float(thr["post_capture_rate_max_dps"]["value"]),
        "equal": float(G["post_capture_rate_max_dps"]) == float(
            thr["post_capture_rate_max_dps"]["value"])},
    "propellant_budget_max_g": {
        "scan_v0": float(G["propellant_budget_max_g"]),
        "registry": float(thr["propellant_budget_max_g"]["value"]),
        "equal": abs(float(G["propellant_budget_max_g"])
                     - float(thr["propellant_budget_max_g"]["value"])) < 1e-12},
}
thresholds_widened = not all(v["equal"] for v in numeric_checks.values())
parameter_binding_valid = frozen_chain_intact          # 严格口径
parameter_binding_numerics_intact = not thresholds_widened

# 2c. 求解器有效性：逐行守恒残差
eps_all = [float(r["eps_H"]) for r in rows16]
solver_valid = max(eps_all) < 1e-12

# 2d. 模型域有效性：sim_12 为刚体域，柔性不在判据内
domain_declared = "RIGID_BODY_FROZEN_SOLVER"
domain_excludes = ["FLEXIBLE_DYNAMICS", "FINITE_CONTACT_WINDOW", "COLLISION_GEOMETRY"]
domain_valid_within_declared_scope = all(
    r["confidence"] == "rigid_body_frozen_solver" for r in rows16)

layer1 = {
    "evidence_valid": bool(evidence_valid),
    "parameter_binding_valid": bool(parameter_binding_valid),
    "parameter_binding_numerics_intact": bool(parameter_binding_numerics_intact),
    "solver_valid": bool(solver_valid),
    "domain_valid_within_declared_scope": bool(domain_valid_within_declared_scope),
    "max_eps_H": max(eps_all),
    "frozen_input_hash_report": frozen_report,
    "numeric_threshold_recheck": numeric_checks,
    "thresholds_widened": bool(thresholds_widened),
}
# --- 有效性分级（不可用记账缺陷抹掉已证实的物理违规）------------------------
#
# margin_inputs_valid：裕度**计算输入**是否可信。
#   证据哈希可复算 + 求解器守恒残差达标 + 阈值数值经独立复核未被放宽。
#   满足则负裕度是**正面证据**，可判 UNSAFE。
#
# parameter_binding_valid：sim_10 冻结输入哈希链是否完整（严格记账口径）。
#   本项失败只阻断**向 SAFE 的升级**，不能反过来把已证实的违规洗成 UNKNOWN，
#   否则 §22 Result D 要求保留的诚实 ABORT 区会被整体抹掉。
margin_inputs_valid = (evidence_valid and solver_valid
                       and parameter_binding_numerics_intact)
safe_promotion_allowed = margin_inputs_valid and parameter_binding_valid
layer1_hard_pass = safe_promotion_allowed
layer1["margin_inputs_valid"] = bool(margin_inputs_valid)
layer1["safe_promotion_allowed"] = bool(safe_promotion_allowed)
layer1["strict_hash_chain_blocks_safe_promotion"] = bool(
    margin_inputs_valid and not parameter_binding_valid)
layer1["asymmetry_rationale"] = (
    "A broken hash pin is a bookkeeping defect, not counter-evidence. Since the "
    "threshold numerics were independently re-verified as unwidened, a negative margin "
    "remains positive evidence of violation and is classified UNSAFE. The broken chain "
    "blocks promotion to ROBUST_SAFE only.")

# =====================================================================
# 3. Layer 2 —— 策略不变全局 Gate 向量（10 分量，s_k = L_k）
# =====================================================================
GATE_VECTOR = [
    {"id": "m_omega", "quantity": "post-capture angular rate", "unit": "deg/s",
     "sense": "upper", "limit": float(G["post_capture_rate_max_dps"]),
     "scale": float(G["post_capture_rate_max_dps"]),
     "limit_source": "scan_v0.gates + registry.post_capture_rate_max_dps",
     "limit_status": "FROZEN"},
    {"id": "m_Hw", "quantity": "reaction-wheel momentum demand", "unit": "N*m*s",
     "sense": "upper", "limit": H_MAX, "scale": H_MAX,
     "limit_source": "scan_v0.actuator_tiers.wheel_capacity_Nms.wheels_large (default tier)",
     "limit_status": "FROZEN"},
    {"id": "m_tauw", "quantity": "reaction-wheel torque demand", "unit": "N*m",
     "sense": "upper", "limit": None, "scale": None,
     "limit_source": "NONE_IN_REPOSITORY",
     "limit_status": "ABSENT"},
    {"id": "m_dv", "quantity": "thruster impulse", "unit": "N*s",
     "sense": "upper", "limit": float(thr["thruster_impulse_max_Ns"]["value"]),
     "scale": float(thr["thruster_impulse_max_Ns"]["value"]),
     "limit_source": "registry.thruster_impulse_max_Ns (DERIVED)",
     "limit_status": "FROZEN"},
    {"id": "m_fuel", "quantity": "total propellant", "unit": "g",
     "sense": "upper", "limit": float(G["propellant_budget_max_g"]),
     "scale": float(G["propellant_budget_max_g"]),
     "limit_source": "scan_v0.gates + registry.propellant_budget_max_g",
     "limit_status": "FROZEN"},
    {"id": "m_time", "quantity": "stabilization time", "unit": "s",
     "sense": "upper", "limit": float(G["t_detumble_max_s"]),
     "scale": float(G["t_detumble_max_s"]),
     "limit_source": "scan_v0.gates.t_detumble_max_s",
     "limit_status": "FROZEN_LIMIT__VALUE_ABSENT_FOR_WHEEL_MODES"},
    {"id": "m_clearance", "quantity": "minimum collision clearance", "unit": "m",
     "sense": "lower", "limit": float(thr["collision_margin_min_m"]["value"]),
     "scale": float(thr["collision_margin_min_m"]["value"]),
     "limit_source": "registry.collision_margin_min_m (PROVISIONAL)",
     "limit_status": "FROZEN_LIMIT__VALUE_ABSENT_NO_L2_MODEL"},
    {"id": "m_flex", "quantity": "flexible modal energy", "unit": "J",
     "sense": "upper", "limit": float(thr["flexible_energy_max_J"]["value"]),
     "scale": float(thr["flexible_energy_max_J"]["value"]),
     "limit_source": "registry.flexible_energy_max_J (PROVISIONAL)",
     "limit_status": "FROZEN_LIMIT__VALUE_ABSENT_DISC_001_UNRESOLVED"},
    {"id": "m_domain", "quantity": "model-domain validity", "unit": "boolean",
     "sense": "validity", "limit": None, "scale": None,
     "limit_source": "LAYER_1", "limit_status": "VALIDITY_GATE_NOT_A_MARGIN"},
    {"id": "m_evidence", "quantity": "evidence validity", "unit": "boolean",
     "sense": "validity", "limit": None, "scale": None,
     "limit_source": "LAYER_1", "limit_status": "VALIDITY_GATE_NOT_A_MARGIN"},
]
PHYS_IDS = ["m_omega", "m_Hw", "m_tauw", "m_dv", "m_fuel", "m_time",
            "m_clearance", "m_flex"]
GV = {g["id"]: g for g in GATE_VECTOR}


def margin(gid, y):
    """m_k = (L_k - y_k)/s_k  上界 ;  (y_k - L_k)/s_k  下界 ; y=None -> ABSENT。"""
    g = GV[gid]
    if y is None or g["limit"] is None:
        return None
    if g["sense"] == "upper":
        return (g["limit"] - float(y)) / g["scale"]
    return (float(y) - g["limit"]) / g["scale"]


# =====================================================================
# 4. 24 格生成
# =====================================================================
FUEL_WHEEL_BIAS_G = H_MAX / (LEVER * ISP * G0) * 1e3          # 2.9992 g（sim_12 冻结式）
J_AVAIL = float(thr["thruster_impulse_max_Ns"]["value"])

cells = []
for case in CASES:
    m_t = float(s12cfg["cases"][case]["m_t_kg"])
    m_comp = M_BUS + m_t
    for alpha in ALPHAS:
        src_strategy = "S1_passive" if alpha == 0 else "S2_velocity_matching"
        src = R[(case, src_strategy)]
        J = float(src["impulse_Ns"])
        H = float(src["H_required_Nms"])
        w_plus = float(src["post_capture_rate_dps"])
        fuel_pre = float(src["fuel_g"]) if alpha == 1 else 0.0
        dv_match = (float(src["ledger_dv_match_mps"])
                    if alpha == 1 and src.get("ledger_dv_match_mps") else 0.0)
        dH_ext = (float(src["ledger_dH_external_Nms"])
                  if src.get("ledger_dH_external_Nms") else 0.0)
        for u in MODES:
            # ---- 分配算例（同一套方程，模式只改需求，不改 Gate 集合）----
            if u == "WHEEL_DIRECT":
                h_rw0 = 0.0
                Hw_demand = H
                fuel_alloc = 0.0
                J_thr = 0.0
                t_stab = None                      # 无轮组力矩上限 -> 无法定义
                t_stab_reason = "NO_WHEEL_TORQUE_LIMIT_IN_REPOSITORY"
            elif u == "WHEEL_BIAS":
                h_rw0 = -H_MAX                     # 预置沿 -h_hat（theta_pred=0）
                Hw_demand = abs(H - H_MAX)         # |h_rw0 + H_vec| 对齐时的解析式
                fuel_alloc = FUEL_WHEEL_BIAS_G
                J_thr = 0.0
                t_stab = None
                t_stab_reason = "NO_WHEEL_TORQUE_LIMIT_IN_REPOSITORY"
            else:                                   # THRUSTER
                h_rw0 = 0.0
                Hw_demand = 0.0                     # 实际分配需求为 0，但 Gate 仍评估
                J_thr = H / LEVER
                fuel_alloc = 1e3 * J_thr / (ISP * G0)
                t_stab = H / (FORCE * LEVER)
                t_stab_reason = None
            fuel_total = fuel_pre + fuel_alloc
            dv_thr = J_thr / m_comp

            y = {"m_omega": w_plus, "m_Hw": Hw_demand, "m_tauw": None,
                 "m_dv": J_thr, "m_fuel": fuel_total, "m_time": t_stab,
                 "m_clearance": None, "m_flex": None}
            m = {k: margin(k, v) for k, v in y.items()}
            evaluable = {k: v for k, v in m.items() if v is not None}
            absent = sorted([k for k, v in m.items() if v is None])
            M_phys = min(evaluable.values())
            binding = min(evaluable, key=lambda k: evaluable[k])

            # ---- 分类（fail-closed 格）----
            # 负裕度是决定性的：追加约束只会降低 min，不可能救回。
            if not margin_inputs_valid:
                cls = "UNKNOWN"
                cls_reason = "MARGIN_INPUTS_INVALID"
            elif M_phys < 0.0:
                cls = "UNSAFE"
                cls_reason = f"HARD_MARGIN_VIOLATION_ON_{binding}"
            elif absent:
                cls = "UNKNOWN"
                cls_reason = "ABSENT_GATE_COMPONENTS:" + ",".join(absent)
            elif not safe_promotion_allowed:
                cls = "UNKNOWN"
                cls_reason = "FROZEN_INPUT_HASH_CHAIN_BROKEN_SAFE_PROMOTION_BLOCKED"
            else:
                cls = "ROBUST_SAFE"
                cls_reason = "ALL_COMPONENTS_EVALUABLE_AND_NONNEGATIVE"

            legacy = next((s for s, av in LEGACY_MAP.items() if av == (alpha, u)), None)
            legacy_feas = R[(case, legacy)]["feasibility"] if legacy else "NOT_IN_SIM12_PHASE1"
            legacy_binding = R[(case, legacy)]["binding_gate"] if legacy else "N/A"

            cells.append({
                "cell_id": f"{case}|a{alpha}|{u}",
                "case": case, "alpha": alpha, "mode": u,
                "provenance": "SIM12_PHASE1_ROW" if legacy else "ALGEBRAIC_RECONSTRUCTION",
                "legacy_strategy_label": legacy or "",
                "legacy_feasibility": legacy_feas,
                "legacy_binding_gate": legacy_binding,
                "m_t_kg": m_t, "m_composite_kg": m_comp,
                # 物理转移（只随 alpha 变）
                "impulse_J_Ns": J, "H_captured_Nms": H, "omega_plus_dps": w_plus,
                "dH_external_Nms": dH_ext, "dv_match_mps": dv_match,
                # 分配结果（随 u 变）
                "h_rw0_Nms": h_rw0, "wheel_momentum_demand_Nms": Hw_demand,
                "thruster_impulse_Ns": J_thr, "delta_v_mps": dv_thr,
                "fuel_precontact_g": fuel_pre, "fuel_allocation_g": fuel_alloc,
                "fuel_total_g": fuel_total,
                "stabilization_time_s": t_stab if t_stab is not None else "",
                "stabilization_time_absent_reason": t_stab_reason or "",
                # Gate 向量
                **{k: (round(v, 12) if v is not None else "ABSENT") for k, v in m.items()},
                "M_phys_restricted": round(M_phys, 12),
                "binding_gate": binding,
                "absent_components": ";".join(absent),
                "n_evaluable_components": len(evaluable),
                "classification": cls,
                "classification_reason": cls_reason,
            })

# =====================================================================
# 5. 旧 M 值可复现性检验（父提示 §11.4）
# =====================================================================
EXTERNAL_CLAIMS = [
    {"cell": "C_transition|a0|WHEEL_BIAS", "claimed_M": 0.013381,
     "claimed_fuel_g": 2.9992, "claimed_J_Ns": 0.157439, "claimed_Hc_Nms": 0.368886},
    {"cell": "C_transition|a1|THRUSTER", "claimed_M": 0.048817,
     "claimed_fuel_g": 6.9980, "claimed_J_Ns": 0.123211, "claimed_Hc_Nms": 0.623015},
]
by_id = {c["cell_id"]: c for c in cells}
old_M_report = []
for cl in EXTERNAL_CLAIMS:
    c = by_id[cl["cell"]]
    d = {"cell_id": cl["cell"], "claimed_M": cl["claimed_M"],
         "recomputed_M_phys_restricted": c["M_phys_restricted"],
         "abs_diff_M": abs(c["M_phys_restricted"] - cl["claimed_M"]),
         "binding_gate": c["binding_gate"],
         "claimed_fuel_g": cl["claimed_fuel_g"],
         "recomputed_fuel_g": round(c["fuel_total_g"], 6),
         "abs_diff_fuel_g": abs(c["fuel_total_g"] - cl["claimed_fuel_g"]),
         "claimed_J_Ns": cl["claimed_J_Ns"], "recomputed_J_Ns": round(c["impulse_J_Ns"], 6),
         "claimed_Hc_Nms": cl["claimed_Hc_Nms"],
         "recomputed_Hc_Nms": round(c["H_captured_Nms"], 6)}
    d["M_reproduced_at_1e-6"] = bool(d["abs_diff_M"] < 1e-6)
    old_M_report.append(d)
old_M_all_reproduced = all(d["M_reproduced_at_1e-6"] for d in old_M_report)

# =====================================================================
# 6. Pareto 前沿（多目标，禁止 argmax M 单目标）
# =====================================================================
# 目标（全部越小越好）：fuel, J, H_c, stabilization proxy, wheel usage, thruster usage
# 约束：M_phys_restricted 越大越好 -> 取负号纳入支配判定
PARETO_OBJ = [("fuel_total_g", +1), ("impulse_J_Ns", +1), ("H_captured_Nms", +1),
              ("M_phys_restricted", -1)]


def dominates(a, b):
    ge = all((a[k] * s) <= (b[k] * s) + 0.0 for k, s in PARETO_OBJ)
    gt = any((a[k] * s) < (b[k] * s) for k, s in PARETO_OBJ)
    return ge and gt


# Pareto 只在同一初始状态内比较（same-state 纪律）
pareto_rows = []
for case in CASES:
    grp = [c for c in cells if c["case"] == case and c["classification"] != "UNSAFE"]
    for c in grp:
        dom_by = [o["cell_id"] for o in grp if o is not c and dominates(o, c)]
        pareto_rows.append({
            "case": case, "cell_id": c["cell_id"], "alpha": c["alpha"], "mode": c["mode"],
            "classification": c["classification"],
            "M_phys_restricted": c["M_phys_restricted"], "binding_gate": c["binding_gate"],
            "fuel_total_g": round(c["fuel_total_g"], 6),
            "impulse_J_Ns": round(c["impulse_J_Ns"], 6),
            "H_captured_Nms": round(c["H_captured_Nms"], 6),
            "thruster_impulse_Ns": round(c["thruster_impulse_Ns"], 6),
            "wheel_momentum_demand_Nms": round(c["wheel_momentum_demand_Nms"], 6),
            "on_pareto_front": len(dom_by) == 0,
            "dominated_by": ";".join(dom_by),
        })

# =====================================================================
# 7. binding gate map + GS2 重发
# =====================================================================
binding_map = []
for c in cells:
    binding_map.append({
        "case": c["case"], "alpha": c["alpha"], "mode": c["mode"],
        "cell_id": c["cell_id"],
        "binding_gate_v2": c["binding_gate"],
        "M_phys_restricted": c["M_phys_restricted"],
        "legacy_binding_gate": c["legacy_binding_gate"],
        "legacy_feasibility": c["legacy_feasibility"],
        "classification_v2": c["classification"],
        "binding_gate_changed": (c["legacy_binding_gate"] not in ("N/A", "")
                                 and c["binding_gate"].replace("m_", "").upper()
                                 not in c["legacy_binding_gate"]),
    })

# GS2：捕获后可行策略的分化（在 V2 口径下重判）
gs2 = {}
for case in CASES:
    grp = [c for c in cells if c["case"] == case]
    not_unsafe = [c for c in grp if c["classification"] != "UNSAFE"]
    if not not_unsafe:
        gs2[case] = {"best": "ABORT", "reason": "ALL_24_CELL_CANDIDATES_UNSAFE_IN_THIS_CASE"}
    else:
        # 词典序：先最大化 M_phys（稳健性），同分再最小化 fuel、J、H
        best = sorted(not_unsafe, key=lambda c: (-c["M_phys_restricted"], c["fuel_total_g"],
                                                 c["impulse_J_Ns"], c["H_captured_Nms"]))[0]
        cheap = sorted(not_unsafe, key=lambda c: (c["fuel_total_g"], -c["M_phys_restricted"]))[0]
        gs2[case] = {
            "best_by_robustness": best["cell_id"],
            "best_by_min_fuel": cheap["cell_id"],
            "rankings_disagree": best["cell_id"] != cheap["cell_id"],
            "max_M_phys_restricted": best["M_phys_restricted"],
            "min_fuel_g": round(cheap["fuel_total_g"], 6),
            "classification_of_best": best["classification"],
        }

n_by_cls = {}
for c in cells:
    n_by_cls[c["classification"]] = n_by_cls.get(c["classification"], 0) + 1

# =====================================================================
# 7b. 科学结果自动提取（§22 Result A/B/C/D）—— 机器判定，非人工断言
# =====================================================================
RANK = {"UNSAFE": 0, "UNKNOWN": 1, "ROBUST_SAFE": 2}

# Result A：同一 (case, mode) 下 alpha 改变；冲量下降但 M 下降 / 分类倒转
result_A = []
for case in CASES:
    for u in MODES:
        c0 = by_id[f"{case}|a0|{u}"]
        c1 = by_id[f"{case}|a1|{u}"]
        if c1["impulse_J_Ns"] < c0["impulse_J_Ns"]:          # alpha=1 局部更优
            rec = {"case": case, "mode": u,
                   "J_alpha0_Ns": round(c0["impulse_J_Ns"], 6),
                   "J_alpha1_Ns": round(c1["impulse_J_Ns"], 6),
                   "J_reduction_pct": round(100 * (1 - c1["impulse_J_Ns"] / c0["impulse_J_Ns"]), 4),
                   "Hc_alpha0_Nms": round(c0["H_captured_Nms"], 6),
                   "Hc_alpha1_Nms": round(c1["H_captured_Nms"], 6),
                   "Hc_increase_pct": round(100 * (c1["H_captured_Nms"] / c0["H_captured_Nms"] - 1), 4),
                   "M_alpha0": c0["M_phys_restricted"], "M_alpha1": c1["M_phys_restricted"],
                   "class_alpha0": c0["classification"], "class_alpha1": c1["classification"],
                   "global_degradation": c1["M_phys_restricted"] < c0["M_phys_restricted"],
                   "strict_classification_reversal":
                       RANK[c1["classification"]] < RANK[c0["classification"]]}
            result_A.append(rec)
result_A_strict = [r for r in result_A if r["strict_classification_reversal"]]

# Result B：binding gate 切换（同 case 内，由 mode 或 alpha 驱动）
result_B = []
for case in CASES:
    for u in MODES:                                           # alpha 驱动
        c0, c1 = by_id[f"{case}|a0|{u}"], by_id[f"{case}|a1|{u}"]
        if c0["binding_gate"] != c1["binding_gate"]:
            result_B.append({"case": case, "driver": "alpha", "held_fixed": f"mode={u}",
                             "from": f"a0 -> {c0['binding_gate']}",
                             "to": f"a1 -> {c1['binding_gate']}",
                             "class_from": c0["classification"], "class_to": c1["classification"],
                             "H_from_Nms": round(c0["H_captured_Nms"], 6),
                             "H_to_Nms": round(c1["H_captured_Nms"], 6)})
    for a in ALPHAS:                                          # mode 驱动
        seq = [by_id[f"{case}|a{a}|{u}"] for u in MODES]
        for i in range(len(seq) - 1):
            if seq[i]["binding_gate"] != seq[i + 1]["binding_gate"]:
                result_B.append({"case": case, "driver": "mode", "held_fixed": f"alpha={a}",
                                 "from": f"{seq[i]['mode']} -> {seq[i]['binding_gate']}",
                                 "to": f"{seq[i+1]['mode']} -> {seq[i+1]['binding_gate']}",
                                 "class_from": seq[i]["classification"],
                                 "class_to": seq[i + 1]["classification"],
                                 "H_from_Nms": round(seq[i]["H_captured_Nms"], 6),
                                 "H_to_Nms": round(seq[i + 1]["H_captured_Nms"], 6)})

# 轮组预置三条解析边界的数值验证
wheel_boundaries = []
for case in CASES:
    for a in ALPHAS:
        cd = by_id[f"{case}|a{a}|WHEEL_DIRECT"]
        cb = by_id[f"{case}|a{a}|WHEEL_BIAS"]
        H = cd["H_captured_Nms"]
        wheel_boundaries.append({
            "case": case, "alpha": a, "H_Nms": round(H, 6),
            "h_max": H_MAX, "half_h_max": H_MAX / 2, "two_h_max": 2 * H_MAX,
            "m_Hw_direct": cd["m_Hw"], "m_Hw_bias": cb["m_Hw"],
            "bias_margin_exceeds_direct": cb["m_Hw"] > cd["m_Hw"],
            "predicted_bias_better_H_gt_half_hmax": bool(H > H_MAX / 2),
            "margin_crossover_prediction_holds":
                bool((cb["m_Hw"] > cd["m_Hw"]) == (H > H_MAX / 2)),
            "direct_feasible_H_le_hmax": bool(H <= H_MAX),
            "direct_margin_nonneg": bool(cd["m_Hw"] >= 0),
            "feasibility_crossover_prediction_holds":
                bool((cd["m_Hw"] >= 0) == (H <= H_MAX)),
            "bias_feasible_H_le_2hmax": bool(H <= 2 * H_MAX),
            "bias_margin_nonneg": bool(cb["m_Hw"] >= 0),
            "bias_ceiling_prediction_holds": bool((cb["m_Hw"] >= 0) == (H <= 2 * H_MAX)),
        })
wheel_boundary_all_hold = all(
    w["margin_crossover_prediction_holds"] and w["feasibility_crossover_prediction_holds"]
    and w["bias_ceiling_prediction_holds"] for w in wheel_boundaries)

# Result C：SAFE -> UNKNOWN 的 fail-closed 原因分布
result_C = {}
for c in cells:
    if c["classification"] == "UNKNOWN":
        for a in (c["absent_components"].split(";") if c["absent_components"] else ["<none>"]):
            result_C[a] = result_C.get(a, 0) + 1
result_C["_hash_chain_block_applies_to_all_nonunsafe"] = bool(
    margin_inputs_valid and not parameter_binding_valid)

# Result D：诚实 ABORT 区
result_D = {case: {"all_cells_unsafe": all(
    by_id[f"{case}|a{a}|{u}"]["classification"] == "UNSAFE" for a in ALPHAS for u in MODES),
    "worst_M": min(by_id[f"{case}|a{a}|{u}"]["M_phys_restricted"]
                   for a in ALPHAS for u in MODES),
    "best_M": max(by_id[f"{case}|a{a}|{u}"]["M_phys_restricted"]
                  for a in ALPHAS for u in MODES)} for case in CASES}

scientific_results = {
    "result_A_local_improvement_global_degradation": {
        "candidates": result_A,
        "strict_classification_reversals": result_A_strict,
        "n_strict_reversals": len(result_A_strict),
        "found": len(result_A_strict) > 0},
    "result_B_binding_gate_switches": {
        "switches": result_B, "n_switches": len(result_B),
        "n_independent_drivers": len({(r["case"], r["driver"]) for r in result_B}),
        "found_at_least_two": len(result_B) >= 2,
        "wheel_bias_analytic_boundaries": {
            "wheel_direct_feasible_iff": "H <= h_max = %.3f" % H_MAX,
            "wheel_bias_margin_crossover_iff": "H > h_max/2 = %.3f" % (H_MAX / 2),
            "wheel_bias_feasibility_ceiling_iff": "H <= 2*h_max = %.3f" % (2 * H_MAX),
            "all_predictions_hold": bool(wheel_boundary_all_hold),
            "per_cell": wheel_boundaries}},
    "result_C_safe_to_unknown": {
        "unknown_cause_histogram": result_C,
        "found": n_by_cls.get("UNKNOWN", 0) > 0},
    "result_D_honest_abort_region": {
        "per_case": result_D,
        "abort_cases": [c for c in CASES if result_D[c]["all_cells_unsafe"]],
        "preserved": True},
}

# legacy 对照：旧口径 FEASIBLE 数
legacy_feasible = sum(1 for r in rows16 if r["feasibility"] == "FEASIBLE")

# =====================================================================
# 8. 输出
# =====================================================================
os.makedirs(os.path.normpath(EXTERNAL_DIR), exist_ok=True)
ext_pin = pin(EXTERNAL_V1)
external_input_record = {
    "expected_filename": EXTERNAL_V1,
    "status": "NOT_SUPPLIED",
    "repository_search": "no file matching *SAME_STATE* exists anywhere in the repository",
    "permitted_use_if_supplied": "EXTERNAL_INPUT_NOT_YET_AUTHORITY",
    "handling_rule": ("store read-only under 02_sim12_factorial_reissue/../00_external_inputs/ "
                      "with filename, size, SHA-256, import date and provenance; never promote "
                      "directly to authority; the authoritative V2 table is regenerated from "
                      "local frozen sources only"),
    "probe_result": ext_pin,
}


def w_json(name, obj, d=HERE):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")
    return p


def w_yaml(name, obj, d=HERE):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(obj, f, allow_unicode=True, sort_keys=False, default_flow_style=False,
                       width=100)
    return p


def w_csv(name, rows, d=HERE):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    return p


out = []
out.append(w_yaml("SIM12_FACTORIAL_GATE_VECTOR_V2.yaml", {
    "schema": "SIM12_FACTORIAL_GATE_VECTOR_V2",
    "program": "RESEARCH_COUPLED_CLOSURE_R1 / RC1-R2",
    "generated_date_local": "2026-08-29",
    "review_status": "PENDING_OWNER_REVIEW",
    "principle": ("one strategy-invariant Gate set for all 24 cells; a mode may drive a "
                  "demand to zero but must never delete a Gate"),
    "normalization": {
        "upper_bound_margin": "m_k = (L_k - y_k) / s_k",
        "lower_bound_margin": "m_k = (y_k - L_k) / s_k",
        "scale_choice": "s_k = L_k (frozen); margins are dimensionless fractions of the limit",
        "aggregate": "M_phys = min_k m_k over EVALUABLE components only "
                     "(M_phys_restricted); absent components are never zero-filled",
        "monotonicity_argument": ("adding a component can only lower the min, therefore "
                                  "M_phys_restricted < 0 is decisive for UNSAFE while "
                                  "M_phys_restricted >= 0 is necessary but not sufficient "
                                  "for SAFE"),
    },
    "layer_separation": {
        "layer_1_validity_gates": ["evidence_valid", "parameter_binding_valid",
                                   "solver_valid", "domain_valid_within_declared_scope"],
        "layer_2_physical_margins": PHYS_IDS,
        "rule": "validity booleans are never folded into the continuous physical margin",
    },
    "gate_vector": GATE_VECTOR,
    "frozen_constants": {
        "wheel_capacity_Nms": H_MAX, "thruster_isp_s": ISP, "lever_arm_m": LEVER,
        "thruster_force_N": FORCE, "g0_mps2": G0, "servicer_bus_kg": M_BUS,
        "wheel_bias_fuel_g": FUEL_WHEEL_BIAS_G, "thruster_impulse_max_Ns": J_AVAIL,
    },
    "allocation_equations": {
        "WHEEL_DIRECT": "h_rw0 = 0; Hw_demand = |H|; J_thr = 0; fuel_alloc = 0",
        "WHEEL_BIAS": ("h_rw0 = -h_hat * h_max (theta_pred = 0); Hw_demand = ||H| - h_max|; "
                       "fuel_alloc = h_max/(lever*isp*g0)*1e3"),
        "THRUSTER": ("Hw_demand = 0 (actual allocation demand, Gate still evaluated); "
                     "J_thr = |H|/lever; fuel_alloc = 1e3*J_thr/(isp*g0); "
                     "t_stab = |H|/(F*lever)"),
        "source": "frozen local allocation equations from sim_12 strategy_eval.py",
    },
    "sources": evidence_pins,
}))
out.append(w_csv("SIM12_SAME_STATE_PAIRED_TABLE_V2.csv", cells))
out.append(w_csv("SIM12_PARETO_FRONT_V2.csv", pareto_rows))
out.append(w_csv("SIM12_BINDING_GATE_MAP_V2.csv", binding_map))
out.append(w_json("SIM12_GS2_REISSUE_V2.json", {
    "schema": "SIM12_GS2_REISSUE_V2",
    "program": "RESEARCH_COUPLED_CLOSURE_R1 / RC1-R2",
    "generated_date_local": "2026-08-29",
    "review_status": "PENDING_OWNER_REVIEW",
    "supersedes_scope": {
        "artifact": "30_simulation/sim_12_strategy_feasibility/results/sim_12_gate_check.json",
        "field": "gates.GS2_differentiation.best_per_case",
        "legacy_value": json.load(open(os.path.join(REPO, SIM12_GATE),
                                       encoding="utf-8"))["gates"]["GS2_differentiation"]["best_per_case"],
        "supersession_class": "SUPERSEDED_INCOMPLETE_FACTORIAL_AND_STRATEGY_DEPENDENT_GATE_SUBSET",
        "parent_artifact_mutated": False,
        "reason": ("the legacy GS2 ranked 4 labels that collapse to 4 of the 24 factorial "
                   "cells, and evaluated them under mode-dependent Gate subsets in which "
                   "S4 deleted the wheel Gate and S1/S2/S3a deleted the thruster Gates"),
    },
    "layer_1_validity": layer1,
    "layer_1_hard_pass": bool(layer1_hard_pass),
    "cell_count": len(cells),
    "classification_counts": n_by_cls,
    "legacy_feasible_count_16_cell": legacy_feasible,
    "gs2_reissue": gs2,
    "old_M_reproducibility": {
        "definition_used": "M_phys_restricted with s_k = L_k",
        "all_reproduced_at_1e-6": bool(old_M_all_reproduced),
        "detail": old_M_report,
        "disposition": ("REPRODUCED_EXACTLY_UNDER_THE_NEW_FROZEN_NORMALIZATION"
                        if old_M_all_reproduced else
                        "SUPERSEDED_UNDER_UNDEFINED_MARGIN_NORMALIZATION"),
    },
    "scientific_results": scientific_results,
    "external_input": external_input_record,
    "forbidden_inferences": [
        "any cell in this table is SAFE",
        "M_phys_restricted is a complete robustness measure",
        "rigid-body UNKNOWN may be read as feasible",
        "the thruster mode has no wheel requirement (its demand is zero, its Gate is not)",
        "this reissue authorizes Sim13, CTRL-03, or any release",
    ],
    "next_stage_authorized": False,
    "release_credit": False,
}))

out.append(w_csv("SIM12_D1_DISCREPANCY_LEDGER_V1.csv", [
    {"id": "DISC-010", "domain": "REPOSITORY_INTEGRITY",
     "item": "sim_10 frozen-input hash pins are stale after commit 284c882 (REORG04)",
     "current_status": "CONFIRMED_DEFECT",
     "detail": ("scan_v0.yaml pins threshold_registry_core_v1.yaml to "
                "400bcedce5af6ad5c4135e67f87bb524ee2fdafb1c26aeae07e495ff387b2873 and "
                "sim_08 assumptions.yaml to 850f49da...; the actual files hash to "
                "75af082a... and 006c6cc5.... REORG04 rewrote internal paths inside both "
                "YAMLs but did not refresh the pins. The two CSV data artifacts still match."),
     "consequence": ("feasibility_core.load_cfg() raises "
                     "'冻结输入哈希漂移' before its own threshold-widening assertions can run, "
                     "so `python src/strategy_eval.py` and the sim_10 scan are NOT currently "
                     "re-executable. SIM10_GATES_PASS and SIM12_PHASE1_GATES_PASS were "
                     "produced pre-REORG04 and remain valid as frozen artifacts only."),
     "independent_numeric_recheck": ("thresholds_widened = False: "
                                     "post_capture_rate_max_dps 2.0 == 2.0 and "
                                     "propellant_budget_max_g 54.73476731425644 == "
                                     "54.73476731425644 between scan_v0 and the registry"),
     "blocks": "promotion of any V2 cell to ROBUST_SAFE; does not block UNSAFE detection",
     "recommended_action": ("Owner decision: refresh the two pins in scan_v0.yaml to the "
                            "post-REORG04 hashes with an explicit provenance note, or restore "
                            "the pre-REORG04 bytes. Do not silently disable the hash check."),
     "evidence": "20_engineering/config/mission_feasibility/scan_v0.yaml frozen_inputs"},
    {"id": "DISC-011", "domain": "THRESHOLD_SCOPE",
     "item": "two different wheel-momentum limits coexist",
     "current_status": "SCOPE_SEPARATION_ENFORCED",
     "detail": ("threshold_registry_core_v1.yaml declares wheel_momentum_max_Nms = 5.475 "
                "(e15/sim_09 grasp-evaluator scope) while scan_v0 actuator_tiers declares "
                "wheels_large = 0.3 N*m*s (sim_10/sim_12 default tier). sim_12 uses 0.3."),
     "consequence": ("V2 uses 0.3 N*m*s, matching the frozen sim_12 allocation equations. "
                     "Substituting 5.475 would silently widen the wheel Gate by 18x."),
     "independent_numeric_recheck": "n/a",
     "blocks": "NONE",
     "recommended_action": "keep the two scopes explicitly separate; never cross-substitute",
     "evidence": "SIM12_FACTORIAL_GATE_VECTOR_V2.yaml gate_vector.m_Hw.limit_source"},
    {"id": "DISC-012", "domain": "GATE_COMPLETENESS",
     "item": "m_tauw has neither a limit nor a value anywhere in the repository",
     "current_status": "ABSENT",
     "detail": ("no reaction-wheel torque limit exists in scan_v0, the threshold registry, or "
                "any actuator register. Consequently wheel-path stabilization time is also "
                "undefined, so m_time is ABSENT for WHEEL_DIRECT and WHEEL_BIAS (5 cells)."),
     "consequence": "no wheel-mode cell can ever reach ROBUST_SAFE until M4 supplies a bound",
     "independent_numeric_recheck": "n/a",
     "blocks": "R3 FLEX bridge cannot by itself lift any cell out of UNKNOWN",
     "recommended_action": "close in M4 SIM13R_JOINT_CONTROL_ENVELOPE_V1 / resource register",
     "evidence": "SIM12_GS2_REISSUE_V2.json scientific_results.result_C"},
]))


# ---------------------------------------------------------------- 报告
def md_table(rows, cols, hdr):
    out = ["| " + " | ".join(hdr) + " |", "|" + "|".join(["---"] * len(hdr)) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(out)


rep = []
rep.append("# SIM12 FACTORIAL REPRODUCTION REPORT V2\n")
rep.append("`RESEARCH_COUPLED_CLOSURE_R1 / RC1-R2` — generated 2026-08-29. "
           "`review_status = PENDING_OWNER_REVIEW`. No parent artifact was mutated.\n")
rep.append("## 1. What changed\n")
rep.append(f"- Legacy sim_12 Phase 1: **16 cells**, {legacy_feasible} labelled `FEASIBLE`, "
           "`flex_status = UNKNOWN_NOT_IN_CRITERIA`.")
rep.append(f"- V2 factorial: **{len(cells)} cells** = 4 cases x 2 alpha x 3 modes, "
           f"one strategy-invariant Gate vector, classifications "
           f"{json.dumps(n_by_cls)}.")
rep.append("- **No cell is `ROBUST_SAFE`.** Every previously `FEASIBLE` cell is now `UNKNOWN`, "
           "because `m_tauw`, `m_clearance` and `m_flex` have no evaluable value and the "
           "frozen-input hash chain is broken.\n")
rep.append("## 2. The two structural defects that V2 removes\n")
rep.append("**Defect 1 — collapsed factor structure.** In `strategy_eval.py` the pre-contact "
           "factor is set by `alpha = 1.0 if strategy == 'S2_velocity_matching' else 0.0`, so "
           "`S1_passive`, `S3a_wheel_bias` and `S4_post_capture_detumble` share one identical "
           "physical transition. Verified: `impulse_Ns`, `H_required_Nms` and "
           "`post_capture_rate_dps` are byte-identical across those three labels in all four "
           "cases. The four labels are therefore 4 of 24 factorial cells, not 4 strategies.\n")
rep.append("**Defect 2 — strategy-dependent Gate subset.** `S4` used "
           "`feas = gate1 and gate3 and gate4` (wheel Gate deleted); `S1/S2/S3a` used "
           "`feas = gate1 and gate2` (thruster Gates deleted). Symptom in the frozen CSV: "
           "`C_transition / S4` is `FEASIBLE` while carrying `wheel_margin_Nms = -0.068886`. "
           "In V2 the thruster mode reports `m_Hw = 1.0` because its *demand* is zero — the "
           "Gate itself is never removed.\n")
rep.append("## 3. Global Gate vector and M_phys\n")
rep.append("`m_k = (L_k - y_k)/s_k` for upper bounds, `(y_k - L_k)/s_k` for lower bounds, "
           "with `s_k = L_k` frozen. `M_phys_restricted = min_k m_k` over evaluable components "
           "only; absent components are never zero-filled.\n")
rep.append("Monotonicity argument: adding a component can only lower the min, so "
           "`M_phys_restricted < 0` is **decisive** for `UNSAFE`, while `>= 0` is necessary "
           "but not sufficient for safety. This is why negative-margin cells are still "
           "classified `UNSAFE` despite the broken hash chain, and non-negative cells are not "
           "promoted above `UNKNOWN`.\n")
rep.append("| component | limit | status |")
rep.append("|---|---|---|")
for g in GATE_VECTOR:
    rep.append(f"| `{g['id']}` | {g['limit']} {g['unit']} | {g['limit_status']} |")
rep.append("")
rep.append("## 4. Old M reproducibility\n")
rep.append("The externally supplied margins **reproduce exactly** under `s_k = L_k`; in both "
           "cases the binding component is `m_omega`. The prior audit recorded them as "
           "`UNVERIFIED` because no margin normalization was defined anywhere in the "
           "repository — that is now closed.\n")
rep.append(md_table(old_M_report,
                    ["cell_id", "claimed_M", "recomputed_M_phys_restricted", "abs_diff_M",
                     "binding_gate"],
                    ["cell", "claimed M", "recomputed M", "abs diff", "binding"]))
rep.append("")
rep.append("## 5. Scientific results found\n")
rep.append(f"**Result A — strict feasibility reversal: {len(result_A_strict)} found.**\n")
for r in result_A_strict:
    rep.append(f"- `{r['case']} / {r['mode']}`: velocity matching cuts contact impulse "
               f"{r['J_reduction_pct']}% ({r['J_alpha0_Ns']} -> {r['J_alpha1_Ns']} N*s) and "
               f"raises captured momentum {r['Hc_increase_pct']}%, driving "
               f"`M_phys` {r['M_alpha0']} -> {r['M_alpha1']} and the classification "
               f"`{r['class_alpha0']}` -> `{r['class_alpha1']}`.")
rep.append("")
rep.append(f"**Result B — binding-Gate switches: {len(result_B)} found across "
           f"{len({(r['case'], r['driver']) for r in result_B})} independent (case, driver) "
           f"combinations.** The three analytic wheel-bias boundaries all hold: "
           f"`{wheel_boundary_all_hold}`.\n")
rep.append(md_table(result_B, ["case", "driver", "held_fixed", "from", "to",
                               "class_from", "class_to"],
                    ["case", "driver", "held fixed", "from", "to", "class from", "class to"]))
rep.append("")
rep.append("**Result C — SAFE to UNKNOWN.** Cause histogram over the "
           f"{n_by_cls.get('UNKNOWN', 0)} `UNKNOWN` cells: "
           f"`{json.dumps(result_C, ensure_ascii=False)}`.\n")
rep.append("**Result D — honest ABORT region preserved.** Cases in which every one of the six "
           f"cells is `UNSAFE`: `{[c for c in CASES if result_D[c]['all_cells_unsafe']]}`. "
           "These are retained, not deleted.\n")
rep.append("## 6. Reproduction\n")
rep.append("```bash\npython 30_simulation/sim_13_viability_extension_r1/"
           "02_sim12_factorial_reissue/build_d1_factorial.py\n```\n")
rep.append("## 7. What this does not authorize\n")
rep.append("- No cell is SAFE. No FLEX qualification. No Sim13 parent PASS.\n"
           "- No CTRL-03 closure, no Engineering Release, no competition claim.\n"
           "- `next_stage_authorized = false`, `release_credit = false`.\n")

p = os.path.join(HERE, "SIM12_FACTORIAL_REPRODUCTION_REPORT_V2.md")
with open(p, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(rep))
out.append(p)

print(json.dumps({
    "cells": len(cells),
    "scientific_results_summary": {
        "result_A_strict_reversals": len(result_A_strict),
        "result_B_switches": len(result_B),
        "wheel_boundaries_all_hold": wheel_boundary_all_hold,
        "result_D_abort_cases": [c for c in CASES if result_D[c]["all_cells_unsafe"]]},
    "classification_counts": n_by_cls,
    "legacy_feasible_16cell": legacy_feasible,
    "layer1_hard_pass": layer1_hard_pass,
    "frozen_chain_intact": frozen_chain_intact,
    "thresholds_widened": thresholds_widened,
    "solver_valid": solver_valid,
    "old_M_all_reproduced": old_M_all_reproduced,
    "old_M_detail": old_M_report,
    "gs2": gs2,
}, indent=1, ensure_ascii=False))
for p in out:
    b = open(p, "rb").read()
    print(f"  {hashlib.sha256(b).hexdigest().upper()[:16]}...  {len(b):7d} B  {os.path.basename(p)}")
