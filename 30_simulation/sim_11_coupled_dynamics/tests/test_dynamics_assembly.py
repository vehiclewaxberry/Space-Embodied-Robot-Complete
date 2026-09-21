"""动力学装配一致性测试：质量阵 / 动量映射 / 偏置功率恒等式 / 输运项回归 / J*。"""
import numpy as np

from coupled_dynamics import CoupledModel, quintic

RNG = np.random.default_rng(20260717)
TH = RNG.uniform(-1.2, 1.2, 6)
ETA = 0.01 * RNG.standard_normal(6)
U = 0.1 * RNG.standard_normal(18)


def _model():
    if not hasattr(_model, "m"):
        _model.m = CoupledModel()
    return _model.m


def test_mass_matrix_symmetric_pd_block_structure():
    mdl = _model()
    M = mdl.mass_matrix(TH, ETA)
    sym = float(np.max(np.abs(M - M.T)))
    assert sym < 1e-12, sym
    eig = float(np.linalg.eigvalsh(M).min())
    assert eig > 0.0, eig
    # 拟速度坐标下臂-帆板块结构性为零（耦合经基座块传递）
    cross = float(np.max(np.abs(M[np.ix_(mdl.i_a, mdl.i_e)])))
    assert cross == 0.0, cross
    # M_etaeta = 单位阵（质量归一模态）
    Mee = M[np.ix_(mdl.i_e, mdl.i_e)]
    dev = float(np.max(np.abs(Mee - np.eye(len(mdl.i_e)))))
    assert dev < 1e-10, dev
    return sym


def test_momentum_rows_equal_mass_matrix_base_rows():
    """A(q)=M(q) 前 6 行是拟速度定义要求的结构恒等式。
    本测试只作装配回归；独立动量路径由下一项逐质点校验。"""
    mdl = _model()
    geo = mdl.geometry(TH, ETA)
    err = float(np.max(np.abs(geo["M"][:6, :] - geo["A"])))
    assert err < 1e-12, err
    return err


def test_momentum_map_vs_independent_inertial_path():
    mdl = _model()
    hS = mdl.momentum_S(TH, ETA, U)
    hI = mdl.momentum_inertial(np.zeros(3), np.array([1.0, 0, 0, 0]), TH, ETA, U)
    err = float(np.max(np.abs(hS - hI)))
    assert err < 1e-12, err
    return err


def test_bias_power_identity():
    """能量恒等式 u^T c(q,u) = 1/2 u^T Mdot u（Mdot 沿运动方向中心差分）。
    该式对任意 u 精确成立，独立校验偏置装配与质量阵的一致性。"""
    mdl = _model()
    u = U.copy()
    thd, etad = u[6:12], u[12:]
    dt = 1e-6
    Mp = mdl.mass_matrix(TH + thd * dt, ETA + etad * dt)
    Mm = mdl.mass_matrix(TH - thd * dt, ETA - etad * dt)
    Mdot = (Mp - Mm) / (2 * dt)
    lhs = float(u @ mdl.bias_vector(TH, ETA, u))
    rhs = float(0.5 * u @ (Mdot @ u))
    scale = max(abs(lhs), abs(rhs), 1e-12)
    err = abs(lhs - rhs) / scale
    assert err < 1e-6, (lhs, rhs, err)
    return err


def test_transport_term_regression():
    """回归：w_b x v_b 输运项必须在偏置中（实现教训：该项虚功率=P·(w x v)，
    在零动量流形上恰为零，只有全量模式动量漂移能暴露；c(v_b) - c(0) 必须
    等于 A_P^T (w x v_b)。"""
    mdl = _model()
    u0 = U.copy()
    u0[0:3] = 0.0
    c0 = mdl.bias_vector(TH, ETA, u0)
    u1 = U.copy()
    c1 = mdl.bias_vector(TH, ETA, u1)
    A = mdl.momentum_matrix(TH, ETA)
    wxv = np.cross(U[3:6], U[0:3])
    expected = A[0:3, :].T @ wxv
    err = float(np.max(np.abs((c1 - c0) - expected)))
    assert err < 1e-12, err
    return err


def test_generalized_jacobian_consistency():
    """J* 与部分速度矩阵恒等式：零动量下 V_b = -Hbb^{-1} Hbm qdot_m，
    末端速度 Phi u == J* qdot_m（精确）。另与 sim_05 J_g 对齐（刚化）。"""
    from capture_solver import ee_partial_velocity
    mdl = _model()
    qdm = 0.2 * RNG.standard_normal(6 + 2 * mdl.n_modes)
    A = mdl.momentum_matrix(TH, ETA)
    Vb = -np.linalg.solve(A[:, :6], A[:, 6:] @ qdm)
    u = np.concatenate([Vb, qdm])
    Phi, _, _ = ee_partial_velocity(mdl, TH)
    v1 = Phi @ u
    v2 = mdl.generalized_jacobian(TH, ETA) @ qdm
    err = float(np.max(np.abs(v1 - v2)))
    assert err < 1e-12, err

    import sys, os
    sys.path.insert(0, os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "sim_05_free_floating_arm")))
    from dynamics import FreeFloatingB601
    mdl_r = CoupledModel(rigid_panels=True)
    Jg11 = mdl_r.generalized_jacobian(TH, np.zeros(0))
    Jg5 = FreeFloatingB601().generalized_jacobian(TH)
    err5 = float(np.max(np.abs(Jg11[:, :6] - Jg5)))
    assert err5 < 5e-6, err5      # 残差 = 质量分割 CSV 7 位舍入（H_bb 差 ~1e-6）
    return max(err, err5)


def test_rigidized_H_matrices_vs_sim05():
    import sys, os
    sys.path.insert(0, os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "sim_05_free_floating_arm")))
    from dynamics import FreeFloatingB601
    mdl_r = CoupledModel(rigid_panels=True)
    A = mdl_r.momentum_matrix(TH, np.zeros(0))
    Hbb5, Hbm5 = FreeFloatingB601().momentum_matrices(TH)
    err_bm = float(np.max(np.abs(A[:, 6:12] - Hbm5)))
    err_bb = float(np.max(np.abs(A[:, :6] - Hbb5)))
    assert err_bm < 1e-12, err_bm         # 臂侧严格一致
    assert err_bb < 5e-6, err_bb          # 基座侧差 = CSV 舍入（见 README/报告）
    return err_bb


def test_quintic_equals_sim05_minjerk():
    import sys, os
    sys.path.insert(0, os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "sim_05_free_floating_arm")))
    from dynamics import min_jerk
    ts = np.linspace(-0.5, 10.0, 401)
    worst = 0.0
    for t in ts:
        p11, v11, _ = quintic(t, 8.0, 0.0, 1.3)
        p5, v5 = min_jerk(t, 8.0, 1.3)
        worst = max(worst, abs(float(p11) - float(p5)), abs(float(v11) - float(v5)))
    assert worst < 1e-14, worst
    return worst
