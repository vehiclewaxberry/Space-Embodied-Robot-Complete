"""SSOT 装载、场景级联与零硬编码约束测试。"""
import os

import numpy as np

from config_loader import REPO, load_model_config, load_scene, parse_axis_token
import b601_model


def test_axis_token_parse():
    assert np.allclose(parse_axis_token("+Y_S (deploy)"), [0, 1, 0])
    assert np.allclose(parse_axis_token("-Y_S (deploy)"), [0, -1, 0])
    assert np.allclose(parse_axis_token("+Z_S"), [0, 0, 1])
    return 0.0


def test_ssot_closure_and_frames():
    cfg = load_model_config()
    closure = abs(cfg["bus"]["mass"] + 2 * cfg["panel"]["m_panel_kg"]
                  - cfg["whole_sat"]["mass"])
    assert closure < 1e-9, closure
    # T_SM 与 sim_05 冻结常量一致（loader 内已断言，这里再显式复核）
    err_t = float(np.max(np.abs(cfg["t_SM"] - b601_model.T_SM_t)))
    err_R = float(np.max(np.abs(cfg["R_SM"] - b601_model.R_SM)))
    assert err_t < 1e-12 and err_R < 1e-7
    # 帆板界面：L/R 根部对称、展开方向反向、法向同为 +Z_S
    L, R = cfg["panels_frames"]["L"], cfg["panels_frames"]["R"]
    assert np.allclose(L["root_S"] * [1, -1, 1], R["root_S"])
    assert np.allclose(L["deploy_S"], -R["deploy_S"])
    assert np.allclose(L["normal_S"], R["normal_S"])
    return max(closure, err_t)


def test_provisional_flags_present():
    cfg = load_model_config()
    assert cfg["provisional"] is True
    assert "zeta_modal" in cfg["provisional_fields"]
    assert cfg["card"]["status"] == "PROVISIONAL_PARAMS"
    return 0.0


def test_a2_base_scene_chain_is_resolved():
    """A2 必须实际解析其 base_scene，而不是静默回退到源码常量。"""
    bundle = load_scene("20_engineering/config/coupled_scene/scene_A2_capture.yaml")
    expected = os.path.normpath(os.path.join(
        REPO, "20_engineering", "config", "coupled_scene", "scene_A1_arm_slew.yaml"))
    assert bundle["base_scene"]["scene_id"] == "scene_A1_arm_slew"
    assert os.path.normpath(bundle["base_scene_path"]) == expected
    assert bundle["base_scene"]["model_card"] == bundle["scene"]["model_card"]
    cap = bundle["scene"]["capture"]
    modes = bundle["cfg"]["capture_interface"]["constraint_modes"]
    assert cap["constraint_mode"] in modes
    assert cap["secondary_mode"] in modes
    assert cap["tumble_axis_convention"] == "sim_common"
    assert cap["joints_locked_at_capture"] is True
    assert cap["attach_target_after_capture"] is True
    return 0.0
