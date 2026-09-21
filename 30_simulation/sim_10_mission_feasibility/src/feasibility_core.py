"""feasibility_core.py -- sim_10 任务可行域核心（设计书 01_project/competition/sim10_mission_feasibility_design.md）。

物理链（全部来自已验证求解器，只读 import）：
    目标(ω_t, I_t) --rigidize()--> ω⁺, |H_c|          [30_simulation/common/capture_impulse, sim_06 验证]
      门1 捕获后转速  |ω⁺| ≤ ω_budget (registry post_capture_rate_max_dps = 2°/s)
      门2 轮组容量    |H_c| ≤ n_w·h_w                  [sim_08 wheels]
      门3 推力器冲量  J_req = |H_c|/l_T ≤ J_avail = m_prop·Isp·g0   [registry 派生链]
      门4 消旋时间    t_d = |H_c|/(F·l_T) ≤ t_max      [sim_08]
区域（fail-closed）：WHEELS_ONLY_FEASIBLE / THRUSTER_REQUIRED_FEASIBLE /
    INFEASIBLE_RATE / INFEASIBLE_RESOURCE。
几何类 ι(μ) 映射：等密度缩放 s=(m_t/m0)^(1/3)，I_t = I0·(m_t/m0)^(5/3)，杠杆 r_g = λ·s·r_g0；
G1 按 target_debris_v0、G2 按 target_satellite_v0 标定（λ=1、m_t=m0 时精确回 sim_06 锚点），
G3 均质球（无 CAD 锚点，设计空间外推）。
解析近似（共轴骨架，X4 对照）：ω⁺ ≈ Ī_t ω_t / (Ī_t + Ī_s + μ_red d_⊥²)，|H_c| ≈ Ī_t ω_t。
阈值经冻结 registry 装载并断言与参数卡一致（禁止放宽）。纯 numpy。"""
import hashlib
import os
import sys

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "30_simulation", "common"))

from capture_impulse import (rigidize, chaser_stack, GRASP, TUMBLE_AXIS)  # noqa: E402  只读
from rigid_body import load_object                                        # noqa: E402  只读

CFG_PATH = os.path.join(REPO, "20_engineering", "config", "mission_feasibility", "scan_v0.yaml")
APPROACH_AXIS = np.array([1.0, 0.0, 0.0])          # sim_06 约定：沿 +X 接近
R_FLIP = np.diag([-1.0, -1.0, 1.0])                # stack +X_S -> -X 惯性（sim_06 约定）

REGIONS = ("WHEELS_ONLY_FEASIBLE", "THRUSTER_REQUIRED_FEASIBLE",
           "INFEASIBLE_RATE", "INFEASIBLE_RESOURCE")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_cfg(verify_hashes=True):
    """装载参数卡 + 冻结 registry；校验哈希与阈值一致性（thresholds_widened 检测）。"""
    with open(CFG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    frozen = cfg["frozen_inputs"]
    hash_report = {}
    for key, spec in frozen.items():
        actual = sha256_file(os.path.join(REPO, spec["path"]))
        hash_report[key] = {"path": spec["path"], "expected": spec["sha256"],
                            "actual": actual, "match": actual == spec["sha256"]}
        if verify_hashes and actual != spec["sha256"]:
            raise RuntimeError(f"冻结输入哈希漂移: {spec['path']}")
    with open(os.path.join(REPO, frozen["threshold_registry"]["path"]),
              encoding="utf-8") as f:
        reg = yaml.safe_load(f)
    # 阈值一致性断言（参数卡手抄值必须等于 registry，防"放宽"）
    thr = reg["thresholds"]
    assert float(cfg["gates"]["post_capture_rate_max_dps"]) == float(
        thr["post_capture_rate_max_dps"]["value"]), "门1 阈值与 registry 不一致"
    assert abs(float(cfg["gates"]["propellant_budget_max_g"])
               - float(thr["propellant_budget_max_g"]["value"])) < 1e-12, \
        "门3 推进剂预算与 registry 不一致"
    cfg["_registry"] = reg
    cfg["_hash_report"] = hash_report
    cfg["_thresholds_widened"] = False          # 断言通过即未放宽；Gate JSON 落此字段
    return cfg


# ================= 几何类：ι(μ) 等密度缩放映射 ================================
class GeometryClass:
    def __init__(self, name, spec):
        self.name = name
        if "calibration_target" in spec:
            tgt = load_object(spec["calibration_target"])
            self.m0 = float(spec["calibration_mass_kg"])
            assert abs(tgt["mass"] - self.m0) < 1e-9, \
                f"{name} 标定质量与 SSOT 不符: {tgt['mass']} vs {self.m0}"
            self.I0 = np.asarray(tgt["I"], float)
            self.r_g0 = np.asarray(GRASP[spec["calibration_target"]], float)
            self.anchor_id = spec["calibration_target"]
        else:                                    # G3 均质球
            rho = float(spec["sphere_density_kg_m3"])
            self.m0 = 1.0                        # 任意基准（球类纯解析缩放）
            R0 = (3.0 * self.m0 / (4.0 * np.pi * rho)) ** (1.0 / 3.0)
            self.I0 = (2.0 / 5.0) * self.m0 * R0 ** 2 * np.eye(3)
            self.r_g0 = float(spec["grasp_lever_over_radius"]) * R0 * APPROACH_AXIS
            self.anchor_id = None

    def target(self, m_t, lam):
        """等密度缩放：I ∝ m^(5/3)，杠杆 ∝ m^(1/3)；λ 为名义杠杆比例。"""
        k = m_t / self.m0
        s = k ** (1.0 / 3.0)
        return {"m": float(m_t), "I": self.I0 * k ** (5.0 / 3.0),
                "r_g": self.r_g0 * s * float(lam)}


# ================= 单点求精确解 ==============================================
def build_bodies(geo_cls, m_t, omega_dps, lam, alpha, v_app):
    """按 sim_06 build_capture_scenario 同款约定构造 [chaser, target]；
    G1@λ=1、m_t=150 时与 sim_06 场景逐位一致（锚点）。alpha=1 时追踪星平动
    额外叠加目标抓点横向速度（速度匹配；接近速度 v_app 保留）。"""
    t = geo_cls.target(m_t, lam)
    m_c, com_c, I_c, ee_x = chaser_stack()
    w_t = np.deg2rad(omega_dps) * TUMBLE_AXIS
    v_grasp = np.cross(w_t, t["r_g"])            # 目标抓点速度（目标质心系=原点静止）
    bodies = [
        {"m": m_c, "I": R_FLIP @ I_c @ R_FLIP.T,
         "r": t["r_g"] + APPROACH_AXIS * (ee_x - com_c[0]),
         "v": -v_app * APPROACH_AXIS + float(alpha) * v_grasp, "w": np.zeros(3)},
        {"m": t["m"], "I": t["I"], "r": np.zeros(3), "v": np.zeros(3), "w": w_t},
    ]
    return bodies, t


def exact_point(geo_cls, m_t, omega_dps, lam, alpha, v_app):
    bodies, t = build_bodies(geo_cls, m_t, omega_dps, lam, alpha, v_app)
    res = rigidize(bodies)
    return {
        "w_plus_dps": float(np.rad2deg(np.linalg.norm(res["w_plus"]))),
        "H_c_Nms": float(np.linalg.norm(res["H_com"])),
        "dT_J": float(res["dT"]),
        "eps_P": res["eps_P"], "eps_H": res["eps_H_origin"],
        "lever_m": float(np.linalg.norm(t["r_g"])),
        "target_Ibar": float(TUMBLE_AXIS @ t["I"] @ TUMBLE_AXIS),
    }


def analytic_point(geo_cls, m_t, omega_dps, lam):
    """共轴解析骨架：ω⁺ ≈ Ī_t ω / (Ī_t + Ī_s + μ_red d_⊥²)，|H_c| ≈ Ī_t ω。
    Ī = â·I·â（翻滚轴投影）；d_⊥ = 质心连线对 â 的垂距；忽略 v_app 与离轴耦合。"""
    t = geo_cls.target(m_t, lam)
    m_c, com_c, I_c, ee_x = chaser_stack()
    a = TUMBLE_AXIS
    I_t_bar = float(a @ t["I"] @ a)
    I_s_bar = float(a @ (R_FLIP @ I_c @ R_FLIP.T) @ a)
    d = t["r_g"] + APPROACH_AXIS * (ee_x - com_c[0])          # 追踪星质心-目标质心
    d_perp2 = float(d @ d - (d @ a) ** 2)
    mu_red = m_c * t["m"] / (m_c + t["m"])
    w_plus = I_t_bar * np.deg2rad(omega_dps) / (I_t_bar + I_s_bar + mu_red * d_perp2)
    return {"w_plus_analytic_dps": float(np.rad2deg(w_plus)),
            "H_analytic_Nms": float(I_t_bar * np.deg2rad(omega_dps))}


# ================= 四门裁决 ==================================================
def actuator_tier_list(cfg):
    at = cfg["actuator_tiers"]
    tiers = []
    for wname, hw in at["wheel_capacity_Nms"].items():
        for iname, isp in at["thruster_isp_s"].items():
            for lever in at["lever_arm_m"]:
                tiers.append({"tier_id": f"{wname}|{iname}|l{lever:g}",
                              "wheel_Nms": float(hw), "isp_s": float(isp),
                              "lever_m": float(lever),
                              "force_N": float(at["thruster_force_N"])})
    return tiers


def gate_point(H_c, w_plus_dps, tier, cfg):
    g = cfg["gates"]
    j_avail = float(g["propellant_budget_max_g"]) * 1e-3 * tier["isp_s"] * float(g["g0_mps2"])
    j_req = H_c / tier["lever_m"]
    t_d = H_c / (tier["force_N"] * tier["lever_m"])
    gate1 = w_plus_dps <= float(g["post_capture_rate_max_dps"])
    gate2 = H_c <= tier["wheel_Nms"]
    gate3 = j_req <= j_avail
    gate4 = t_d <= float(g["t_detumble_max_s"])
    if not gate1:
        region, binding = "INFEASIBLE_RATE", "POST_CAPTURE_RATE_EXCEEDS_LIMIT"
    elif gate2:
        region, binding = "WHEELS_ONLY_FEASIBLE", "NONE"
    elif gate3 and gate4:
        region, binding = "THRUSTER_REQUIRED_FEASIBLE", "NONE_THRUSTER_PATH"
    else:
        region = "INFEASIBLE_RESOURCE"
        binding = ("THRUSTER_IMPULSE_EXCEEDS_LIMIT" if not gate3
                   else "DETUMBLE_TIME_EXCEEDS_LIMIT")
    return {"region": region, "binding": binding,
            "gate1_rate": bool(gate1), "gate2_wheels": bool(gate2),
            "gate3_impulse": bool(gate3), "gate4_time": bool(gate4),
            "h_star": H_c / tier["wheel_Nms"],
            "j_star": j_avail / max(j_req, 1e-300),
            "J_req_Ns": j_req, "t_d_s": t_d,
            "propellant_g": 1e3 * j_req / (tier["isp_s"] * float(g["g0_mps2"]))}


def geometry_classes(cfg):
    return {name: GeometryClass(name, spec)
            for name, spec in cfg["scan"]["geometry_classes"].items()}
