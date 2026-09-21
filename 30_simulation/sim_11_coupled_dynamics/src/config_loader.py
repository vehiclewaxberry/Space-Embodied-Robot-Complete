"""config_loader.py -- sim_11 参数卡与几何 SSOT 装载（零硬编码）。

职责：
  1. 读 20_engineering/config/coupled_scene/*.yaml 参数卡；
  2. 按参数卡 ssot_refs 解析几何/质量 SSOT（frame_tree / flexible_appendage /
     mass_inertia_budget CSV / targets），代码中不出现任何手抄几何或质量数字；
  3. 对帧树 T_SM 与 sim_05 冻结常量做一致性断言（防两套数字漂移，决策 D-YH-1）。

约定：仓库根 = 本文件向上三级（30_simulation/sim_11_coupled_dynamics/src -> repo root）。
纯 numpy + pyyaml，只读，不写任何 SSOT 文件。
"""
import os
import sys
import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
SIM_COMMON = os.path.join(REPO, "30_simulation", "common")
SIM_05 = os.path.join(REPO, "30_simulation", "sim_05_free_floating_arm")
SIM_07 = os.path.join(REPO, "30_simulation", "sim_07_ancf_flexible")
for _p in (SIM_COMMON, SIM_05, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from rigid_body import load_object          # noqa: E402  (30_simulation/common, 只读)
import b601_model                            # noqa: E402  (sim_05, 只读)

MODEL_CARD_DEFAULT = os.path.join(REPO, "20_engineering", "config", "coupled_scene", "coupled_model_v0.yaml")

_AXIS_MAP = {"X_S": np.array([1.0, 0.0, 0.0]),
             "Y_S": np.array([0.0, 1.0, 0.0]),
             "Z_S": np.array([0.0, 0.0, 1.0])}


def _load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_axis_token(token):
    """SSOT 轴语义字符串 -> 单位向量。例 '+Y_S (deploy)' -> [0,1,0]，'-Y_S' -> [0,-1,0]。"""
    tok = str(token).split()[0].strip()
    sign = 1.0
    if tok[0] in "+-":
        sign = -1.0 if tok[0] == "-" else 1.0
        tok = tok[1:]
    if tok not in _AXIS_MAP:
        raise ValueError(f"无法解析 SSOT 轴语义: {token!r}")
    return sign * _AXIS_MAP[tok]


def load_model_config(card_path=MODEL_CARD_DEFAULT):
    """装载模型参数卡 + 全部 SSOT 依赖，返回统一 cfg 字典。"""
    card = _load_yaml(card_path)
    refs = card["ssot_refs"]
    p = lambda rel: os.path.join(REPO, rel)  # noqa: E731

    # ---- 帧树：T_SM 与帆板界面 F_L / F_R ------------------------------------
    ft = _load_yaml(p(refs["frame_tree"]))["frames"]
    t_SM = np.asarray(ft["M"]["transform_S_M"]["translation_mm"], float) / 1000.0
    q_SM = np.asarray(ft["M"]["transform_S_M"]["rotation"]["quat_wxyz"], float)
    w, x, y, z = q_SM / np.linalg.norm(q_SM)
    R_SM = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
    # 与 sim_05 冻结常量一致性断言（nominal_frozen_v1，决策 D-2：不允许两套数字）
    assert np.max(np.abs(t_SM - b601_model.T_SM_t)) < 1e-12, "frame_tree T_SM 平移与 sim_05 冻结值不一致"
    assert np.max(np.abs(R_SM - b601_model.R_SM)) < 1e-7, "frame_tree T_SM 旋转与 sim_05 冻结值不一致"

    panels_frames = {}
    for side, key in (("L", "F_L"), ("R", "F_R")):
        fr = ft[key]
        panels_frames[side] = {
            "root_S": np.asarray(fr["origin_mm"], float) / 1000.0,
            "deploy_S": parse_axis_token(fr["axes"]["Y_F"]),
            "normal_S": parse_axis_token(fr["axes"]["Z_F"]),
        }

    # ---- 帆板几何 / 质量 / 刚度包络 ------------------------------------------
    fa = _load_yaml(p(refs["flexible_appendage"]))
    stiff_cases = {k: float(v["EI_Nm2"]) for k, v in fa["stiffness"]["cases"].items()}
    panel = {
        "span_L_m": float(fa["geometry"]["span_L_m"]),
        "chord_b_m": float(fa["geometry"]["chord_b_m"]),
        "thickness_t_m": float(fa["geometry"]["thickness_t_m"]),
        "m_panel_kg": float(fa["mass"]["m_panel_kg"]),
        "mu_kg_per_m": float(fa["mass"]["mu_kg_per_m"]),
        "I_own_com_kgm2": {k: float(v) for k, v in fa["mass"]["I_own_com_kgm2"].items()},
        "EI_cases_Nm2": stiff_cases,
        "beta1_ssot": float(fa["stiffness"]["beta1"]),
    }

    # ---- 质量惯量预算行（CSV SSOT，经 30_simulation/common 装载器） ---------------------
    csv_path = p(refs["mass_budget_csv"])
    bus = load_object(card["ssot_refs"]["bus_object_id"], csv_path)
    whole = load_object(card["ssot_refs"]["whole_sat_object_id"], csv_path)
    adapter = load_object(card["ssot_refs"]["adapter_object_id"], csv_path)
    # 质量分割闭合断言（mass_split_check 不变式）：m_bus + 2*m_panel == m_whole
    closure = abs(bus["mass"] + 2.0 * panel["m_panel_kg"] - whole["mass"])
    assert closure < 1e-9, f"质量分割闭合失败: |m_bus+2m_panel-m_whole| = {closure:.3e}"

    # ---- 目标 / 捕获接口 SSOT -------------------------------------------------
    tg = _load_yaml(p(refs["targets"]))
    capture_interface = _load_yaml(p(refs["capture_interface"]))

    return {
        "card": card,
        "card_path": card_path,
        "repo": REPO,
        "t_SM": t_SM, "R_SM": R_SM,
        "panels_frames": panels_frames,
        "panel": panel,
        "bus": bus, "whole_sat": whole, "adapter": adapter,
        "mass_budget_csv": csv_path,
        "targets": tg,
        "capture_interface": capture_interface,
        "panel_cfg": card["panels"],
        "integrator": card["integrator"],
        "provisional": bool(card["panels"].get("provisional", False)),
        "provisional_fields": list(card["panels"].get("provisional_fields", [])),
    }


def load_scene(scene_path):
    """装载场景参数卡；自动级联装载 model_card（以及 A2 的 base_scene）。"""
    scene_abs = (scene_path if os.path.isabs(scene_path)
                 else os.path.join(REPO, scene_path))
    scene_abs = os.path.normpath(scene_abs)
    sc = _load_yaml(scene_abs)
    cfg = load_model_config(os.path.join(REPO, sc["model_card"]))
    out = {"scene": sc, "scene_path": scene_abs, "cfg": cfg}
    if "base_scene" in sc:
        base_path = os.path.normpath(os.path.join(REPO, sc["base_scene"]))
        base = _load_yaml(base_path)
        if os.path.normpath(base["model_card"]) != os.path.normpath(sc["model_card"]):
            raise ValueError("A2 base_scene 与 model_card 不一致")
        out["base_scene"] = base
        out["base_scene_path"] = base_path
    return out


if __name__ == "__main__":
    cfg = load_model_config()
    print("bus:", cfg["bus"]["mass"], "whole:", cfg["whole_sat"]["mass"],
          "panel:", cfg["panel"]["m_panel_kg"])
    print("F_L root:", cfg["panels_frames"]["L"]["root_S"],
          "deploy:", cfg["panels_frames"]["L"]["deploy_S"])
    print("F_R root:", cfg["panels_frames"]["R"]["root_S"],
          "deploy:", cfg["panels_frames"]["R"]["deploy_S"])
    print("EI cases:", cfg["panel"]["EI_cases_Nm2"])
