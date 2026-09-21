"""有限接触带宽捕获（contact_window，sim_11 v1.1 分支 B）快速测试。
完整 T_c/m 扫掠与 G4' 收敛裁决由 src/run_gates.py 机器裁决。"""
import os

import numpy as np
import yaml

from config_loader import REPO
from coupled_dynamics import CoupledModel
from capture_solver import solve_capture, target_state_in_S
from contact_window import run_contact_window

TH = np.deg2rad([0.0, 60.0, -40.0, 0.0, 0.0, 0.0])
R0 = np.zeros(3)
Q0 = np.array([1.0, 0, 0, 0])


def _pre(mdl, v_app=0.01):
    f = mdl.arm.fk(TH)
    u_pre = np.zeros(mdl.nu)
    u_pre[0:3] = v_app * f["T_E"][:3, 2]
    tgt = target_state_in_S(mdl, R0, Q0, TH, "target_debris_v0", 3.0)
    cap = solve_capture(mdl, TH, np.zeros(2 * mdl.n_modes), u_pre, tgt,
                        mode="rigid_lock_6dof")
    lam = np.concatenate([cap["lambda_J_S"], cap["lambda_L_S"]])
    return u_pre, tgt, cap, lam


def test_window_momentum_and_energy_audits():
    """组合系统（追踪星+目标）总动量守恒机器精度 + 窗内能量定理审计。"""
    mdl = CoupledModel()
    u_pre, tgt, cap, lam = _pre(mdl)
    win = run_contact_window(mdl, TH, R0, Q0, np.zeros(2 * mdl.n_modes),
                             u_pre, tgt, lam, T_c_s=0.020,
                             rtol=1e-10, atol=1e-12, n_out=81)
    assert win["momentum_drift_max_abs"] < 1e-12, win["momentum_drift_max_abs"]
    assert win["energy_audit_rel"] < 1e-8, win["energy_audit_rel"]
    # lockup 收口冲量必须是小量（<1% 主冲量）
    assert win["lockup_rel_to_lam"] < 1e-2, win["lockup_rel_to_lam"]
    return max(win["momentum_drift_max_abs"], win["energy_audit_rel"])


def test_small_Tc_limit_matches_instant_capture():
    """T_c→0 极限：动量级量（基座速度跳变、目标角速度）回归瞬时 Delassus 解。"""
    mdl = CoupledModel()
    u_pre, tgt, cap, lam = _pre(mdl)
    win = run_contact_window(mdl, TH, R0, Q0, np.zeros(2 * mdl.n_modes),
                             u_pre, tgt, lam, T_c_s=0.001,
                             rtol=1e-10, atol=1e-12, n_out=41)
    dVb_bw = win["u_post"][0:6] - u_pre[0:6]
    dVb_in = cap["u_post"][0:6] - u_pre[0:6]
    scale_v = float(np.max(np.abs(dVb_in)))
    worst = float(np.max(np.abs(dVb_bw - dVb_in))) / scale_v
    w_bw = win["target_post"]["w_S"]
    w_in = cap["target_w_post_S"]
    worst = max(worst, float(np.max(np.abs(w_bw - w_in)))
                / float(np.max(np.abs(w_in))))
    assert worst < 5e-3, worst
    assert win["lockup_rel_to_lam"] < 1e-3, win["lockup_rel_to_lam"]
    return worst


def test_rigid_limit_bandwidth_vs_instant():
    """帆板刚化（m=0）：带宽窗 + lockup 与瞬时解在 O(T_c·ω) 内一致。"""
    mdl = CoupledModel(rigid_panels=True)
    u_pre, tgt, cap, lam = _pre(mdl)
    win = run_contact_window(mdl, TH, R0, Q0, np.zeros(0),
                             u_pre, tgt, lam, T_c_s=0.020,
                             rtol=1e-10, atol=1e-12, n_out=41)
    assert win["momentum_drift_max_abs"] < 1e-12
    dVb_bw = win["u_post"][0:6] - u_pre[0:6]
    dVb_in = cap["u_post"][0:6] - u_pre[0:6]
    worst = (float(np.max(np.abs(dVb_bw - dVb_in)))
             / float(np.max(np.abs(dVb_in))))
    assert worst < 1e-2, worst
    return worst


def test_bandwidth_filters_modal_energy():
    """带宽滤波方向性：T_c 越长注入模态能越低，且 5 ms（宽带）不超过理想冲量注入。"""
    mdl = CoupledModel()
    u_pre, tgt, cap, lam = _pre(mdl)
    kick_ideal = cap["modal_velocity_kick_energy_J"]
    e = {}
    for tc in (0.005, 0.050):
        win = run_contact_window(mdl, TH, R0, Q0, np.zeros(2 * mdl.n_modes),
                                 u_pre, tgt, lam, T_c_s=tc,
                                 rtol=1e-9, atol=1e-12, n_out=41)
        e[tc] = float(np.max(win["modal_energy_J"]))
    assert e[0.050] < e[0.005], e
    assert e[0.005] < kick_ideal * 1.10, (e, kick_ideal)
    return e[0.050] / e[0.005]


def test_contact_params_from_yaml_and_provisional():
    """接触段参数经参数卡装载（零硬编码）且 T_c 名义值登记为 PROVISIONAL。"""
    sc = yaml.safe_load(open(os.path.join(
        REPO, "20_engineering", "config", "coupled_scene", "scene_A2_capture.yaml"),
        encoding="utf-8"))
    cw = sc["contact"]
    for k in ("model", "T_c_ms_nominal", "T_c_ms_sweep", "window_n_out",
              "lockup_after_window", "wrench_frame"):
        assert k in cw, k
    assert cw["model"] == "half_sine_equal_impulse"
    mc = yaml.safe_load(open(os.path.join(
        REPO, "20_engineering", "config", "coupled_scene", "coupled_model_v0.yaml"),
        encoding="utf-8"))
    pf = mc["panels"]["provisional_fields"]
    assert "contact_T_c" in pf, pf
    return 0.0
