"""FFR 帆板模态测试：特征根 / 频率 / 正交性 / 刚度对角 / 动量系数 / 刚化惯量闭合。"""
import numpy as np

from config_loader import load_model_config
from ffr_panel import FFRPanel, cantilever_beta_roots


def _panel(n_modes=3, case="nominal"):
    cfg = load_model_config()
    p = cfg["panel"]
    fl = cfg["panels_frames"]["L"]
    return FFRPanel("L", fl["root_S"], fl["deploy_S"], fl["normal_S"],
                    p["span_L_m"], p["mu_kg_per_m"], p["chord_b_m"],
                    p["thickness_t_m"], p["EI_cases_Nm2"][case],
                    n_modes=n_modes), p


def test_beta_roots_vs_ssot():
    cfg = load_model_config()
    roots = cantilever_beta_roots(4)
    err = abs(roots[0] - cfg["panel"]["beta1_ssot"])
    assert err < 1e-7, err
    ref = [1.87510407, 4.69409113, 7.85475744, 10.99554073]   # 悬臂梁经典值
    worst = float(np.max(np.abs(roots - ref)))
    assert worst < 1e-6, worst
    return worst


def test_first_mode_frequency_matches_assignment():
    """D-4 频率指派：nominal EI -> f1 = 1.000 Hz（解析公式），与 ANCF 1.00021 同级。"""
    pan, p = _panel()
    L, mu = p["span_L_m"], p["mu_kg_per_m"]
    EI = p["EI_cases_Nm2"]["nominal"]
    b1 = cantilever_beta_roots(1)[0]
    f1_analytic = b1 ** 2 / (2 * np.pi * L ** 2) * np.sqrt(EI / mu)
    err = abs(pan.f_modes_hz[0] - f1_analytic) / f1_analytic
    assert err < 1e-9, err
    assert abs(pan.f_modes_hz[0] - 1.0002) < 5e-4              # vs sim_07 ANCF 1.00021
    return err


def test_orthogonality_and_stiffness_diagonal():
    pan, _ = _panel(n_modes=4)
    assert pan.mode_orthogonality_residual < 1e-10
    offdiag = pan.K - np.diag(np.diag(pan.K))
    rel = float(np.max(np.abs(offdiag)) / pan.K[0, 0])
    assert rel < 1e-8, rel
    # K 对角 = omega_i^2（解析 EB 频率）
    for i, bl in enumerate(pan.betaL):
        w_analytic = (bl / pan.L) ** 2 * np.sqrt(pan.EI / pan.mu)
        assert abs(np.sqrt(pan.K[i, i]) - w_analytic) / w_analytic < 1e-9
    return rel


def test_momentum_coefficients_positive_and_crosschecked():
    """B_t/B_r 由参数卡生成；用独立细分梯形积分交叉核对。"""
    pan, _ = _panel()
    s = np.linspace(0.0, pan.L, 20001)
    from ffr_panel import _phi_raw
    sigma = (np.cosh(pan.betaL) + np.cos(pan.betaL)) / (np.sinh(pan.betaL) + np.sin(pan.betaL))
    worst = 0.0
    for i in range(pan.n_modes):
        phi = _phi_raw(pan.betaL[i] / pan.L, sigma[i], s)[0]
        nrm = np.sqrt(np.trapezoid(pan.mu * phi ** 2, s))
        phi = phi / nrm
        Bt_ref = np.trapezoid(pan.mu * phi, s)
        Br_ref = np.trapezoid(pan.mu * s * phi, s)
        worst = max(worst, abs(pan.B_t[i] - Bt_ref), abs(pan.B_r[i] - Br_ref))
    assert worst < 1e-6, worst
    assert pan.B_t[0] > 0 and pan.B_r[0] > 0
    return worst


def test_rigid_limit_plate_inertia_closure():
    """eta=0 刚化：切片质点 + 集中惯量 = 精确平板惯量公式（机器精度）。"""
    pan, p = _panel()
    _, I = pan.rigid_inertia_check()
    m, L, b, t = pan.m, pan.L, pan.b, pan.t
    I_exact = np.diag([m / 12 * (L ** 2 + t ** 2), m / 12 * (b ** 2 + t ** 2),
                       m / 12 * (b ** 2 + L ** 2)])
    err = float(np.max(np.abs(I - I_exact)))
    assert err < 1e-14, err
    # 与 SSOT YAML 值一致到其 7 位小数舍入
    I_yaml = np.diag([p["I_own_com_kgm2"]["Ixx"], p["I_own_com_kgm2"]["Iyy"],
                      p["I_own_com_kgm2"]["Izz"]])
    err_yaml = float(np.max(np.abs(I - I_yaml)))
    assert err_yaml < 1e-9, err_yaml
    return err
