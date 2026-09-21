"""contact_window.py -- 有限接触带宽捕获（sim_11 v1.1 分支 B）。

动机（G4 裁决 SIM11_GATES_FAIL 的物理根因）：理想冲量 Δt=0 频谱平坦，
每阶模态注入能量 ∝ (B_t,i·J)²，而悬臂模态动量系数 B_t 衰减缓慢（≈1/(2i-1) 律），
故帆板模态能对截断阶数 m 的收敛是慢级数——m=2/3/4 变化 2.78%/1.27% > 1% Gate。
真实夹爪闭合 5–100 ms，对 >1/(2T_c) 的模态激励带限衰减，模态能收敛恢复适定。

模型（等冲量半正弦，参数卡 scene_A2_capture.yaml contact 段）：
    w_I(t) = lam_I * s(t),  s(t) = (pi/(2 T_c)) sin(pi t/T_c),  ∫_0^{T_c} s dt = 1
lam = [J; L] 取瞬时柔性 Delassus 解（capture_solver.solve_capture），方向按捕获
瞬间惯性系冻结（窗内基座转角 << 1°）。作用点 = 末端 E（追踪星侧材料点），
目标在同一空间点受 -w_I(t)：作用反作用同点 => 组合系统总动量守恒为机器审计。

积分：追踪星 full 模式（V_b 入状态量，外力经 Q_ext = Phi^T w_S 注入；关节抱闸
θ̇=0 => W_joint ≡ 0）与目标刚体（惯性系 Newton-Euler）联立单一 ODE。
窗末残余相对速度用一次 Delassus 小冲量收口（lockup，物理对应夹爪最终锁死），
总传递冲量 = lam + delta_lam(T_c)，delta_lam 模长如实输出。

机器审计（tests 断言 + summary 输出）：
  - 组合动量守恒 |Δ(h_chaser + h_target)| —— 机器精度；
  - 能量定理 |（W_c + W_t）-（ΔE_chaser + ΔT_target + E_damp）| —— 积分器精度；
  - T_c→0 极限回归瞬时解（基座/目标动量级量一致，lockup 冲量 → 0）。
纯 numpy/scipy；参数零硬编码（T_c 名义值为 PROVISIONAL：待 B601 夹爪实测）。"""
import numpy as np
from scipy.integrate import solve_ivp

from rigid_body import qmult, q_to_R
from capture_solver import ee_partial_velocity, solve_capture


def _R_of(quat):
    q = np.asarray(quat, float)
    return q_to_R(q / np.linalg.norm(q)).as_matrix()


def run_contact_window(model, th, r0, quat0, eta0, u_pre, target, lam,
                       T_c_s, method="Radau", rtol=1e-10, atol=1e-12,
                       n_out=201, lockup=True, mode="rigid_lock_6dof"):
    """有限带宽接触窗积分。

    输入：th 关节角（抱闸不变）、r0/quat0 基座初态、eta0 模态坐标、
    u_pre 捕获前广义速度（v_app 已叠加）、target = target_state_in_S 输出、
    lam = [J(3); L(3)]（S 系，瞬时 Delassus 解）、T_c_s 接触时长。
    返回 dict：窗内时间序列、窗末状态、lockup 冲量、动量/能量审计。"""
    th = np.asarray(th, float)
    m2 = 2 * model.n_modes
    Phi, pE_S, _ = ee_partial_velocity(model, th)      # th 抱闸 => Phi/pE_S 常量
    R0 = _R_of(quat0)
    lam = np.asarray(lam, float)
    lam_I = np.concatenate([R0 @ lam[:3], R0 @ lam[3:]])
    m_t = float(target["m"])
    I_t0 = np.asarray(target["I_I"], float)            # 目标体轴 t=0 与惯性系对齐
    T_c = float(T_c_s)

    def s_pulse(t):
        if t <= 0.0 or t >= T_c:
            return 0.0
        return (np.pi / (2.0 * T_c)) * np.sin(np.pi * t / T_c)

    # 状态 y = [r_b(3), quat(4), Vb(6), eta(2m), etad(2m), W_c, E_damp,
    #           v_t_I(3), w_t_I(3), r_t_I(3), q_t(4), W_t]
    iVb = slice(7, 13)
    ie1 = slice(13, 13 + m2)
    ie2 = slice(13 + m2, 13 + 2 * m2)
    iWc = 13 + 2 * m2
    iEd = 14 + 2 * m2
    ivt = slice(15 + 2 * m2, 18 + 2 * m2)
    iwt = slice(18 + 2 * m2, 21 + 2 * m2)
    irt = slice(21 + 2 * m2, 24 + 2 * m2)
    iqt = slice(24 + 2 * m2, 28 + 2 * m2)
    iWt = 28 + 2 * m2

    v_t0_I = R0 @ np.asarray(target["v_S"], float)
    w_t0_I = np.asarray(target["w_I"], float)
    r_t0_I = np.asarray(target["r_I"], float)
    y0 = np.concatenate([
        np.asarray(r0, float), np.asarray(quat0, float),
        np.asarray(u_pre, float)[0:6], np.asarray(eta0, float),
        np.asarray(u_pre, float)[model.i_e] if m2 else np.zeros(0),
        [0.0, 0.0],
        v_t0_I, w_t0_I, r_t0_I, np.array([1.0, 0, 0, 0]), [0.0],
    ])

    def rhs(t, y):
        s = s_pulse(t)
        F_I, L_I = lam_I[:3] * s, lam_I[3:] * s
        r_b, quat = y[0:3], y[3:7]
        Vb = y[iVb]
        eta, etad = y[ie1], y[ie2]
        qn = quat / np.linalg.norm(quat)
        Rb = q_to_R(qn).as_matrix()
        u = np.concatenate([Vb, np.zeros(6), etad])
        w_S = np.concatenate([Rb.T @ F_I, Rb.T @ L_I])
        Q_ext = Phi.T @ w_S
        udot, _ = model.accelerations(th, eta, u, np.zeros(6), Q_ext=Q_ext)
        dy = np.zeros_like(y)
        dy[0:3] = Rb @ Vb[:3]
        dy[3:7] = 0.5 * qmult(qn, np.array([0.0, *Vb[3:6]]))
        dy[iVb] = udot[model.i_b]
        if m2:
            dy[ie1] = etad
            dy[ie2] = udot[model.i_e]
            dy[iEd] = float(etad @ (model.D_eta @ etad))
        dy[iWc] = float((Phi @ u) @ w_S)               # 接触力旋量对追踪星功率
        # ---- 目标刚体（惯性系 Newton-Euler，受 -w_I 于同一点） ----------------
        v_t, w_t, r_t = y[ivt], y[iwt], y[irt]
        q_t = y[iqt] / np.linalg.norm(y[iqt])
        Rt = q_to_R(q_t).as_matrix()
        I_I = Rt @ I_t0 @ Rt.T
        pE_I = r_b + Rb @ pE_S
        lever = pE_I - r_t
        tau_I = -(np.cross(lever, F_I) + L_I)
        dy[ivt] = -F_I / m_t
        dy[iwt] = np.linalg.solve(I_I, tau_I - np.cross(w_t, I_I @ w_t))
        dy[irt] = v_t
        dy[iqt] = 0.5 * qmult(q_t, np.array([0.0, *(Rt.T @ w_t)]))
        v_pt = v_t + np.cross(w_t, lever)
        dy[iWt] = float(-F_I @ v_pt - L_I @ w_t)
        return dy

    ts = np.linspace(0.0, T_c, int(n_out))
    sol = solve_ivp(rhs, (0.0, T_c), y0, t_eval=ts, method=method,
                    rtol=rtol, atol=atol)
    assert sol.success, sol.message

    # ---- 序列整理与审计 -------------------------------------------------------
    n = len(ts)
    r = sol.y[0:3].T
    Q = sol.y[3:7].T
    Q = Q / np.linalg.norm(Q, axis=1, keepdims=True)
    Vb = sol.y[iVb].T
    eta_h = sol.y[ie1].T
    etad_h = sol.y[ie2].T
    W_c = sol.y[iWc]
    E_damp = sol.y[iEd]
    v_t_h = sol.y[ivt].T
    w_t_h = sol.y[iwt].T
    r_t_h = sol.y[irt].T
    q_t_h = sol.y[iqt].T
    W_t = sol.y[iWt]

    h_tot = np.zeros((n, 6))
    E_c = np.zeros(n)
    T_t = np.zeros(n)
    modal_E = np.zeros(n)
    tip = np.zeros((n, 2))
    for i in range(n):
        u_i = np.concatenate([Vb[i], np.zeros(6), etad_h[i]])
        h_c = model.momentum_inertial(r[i], Q[i], th, eta_h[i], u_i)
        q_ti = q_t_h[i] / np.linalg.norm(q_t_h[i])
        Rt = q_to_R(q_ti).as_matrix()
        I_I = Rt @ I_t0 @ Rt.T
        h_t = np.concatenate([m_t * v_t_h[i],
                              I_I @ w_t_h[i] + m_t * np.cross(r_t_h[i], v_t_h[i])])
        h_tot[i] = h_c + h_t
        E_c[i] = model.kinetic_energy(th, eta_h[i], u_i) + model.strain_energy(eta_h[i])
        T_t[i] = float(0.5 * m_t * v_t_h[i] @ v_t_h[i]
                       + 0.5 * w_t_h[i] @ (I_I @ w_t_h[i]))
        if model.n_modes:
            modal_E[i] = float(0.5 * etad_h[i] @ etad_h[i]
                               + 0.5 * eta_h[i] @ (model.K_eta @ eta_h[i]))
            tip[i, 0] = model.panels[0].tip_deflection(eta_h[i][:model.n_modes])
            tip[i, 1] = model.panels[1].tip_deflection(eta_h[i][model.n_modes:])

    mom_drift = np.max(np.abs(h_tot - h_tot[0]), axis=0)
    W_ext = W_c + W_t
    dE = (E_c - E_c[0]) + (T_t - T_t[0]) + E_damp
    audit = np.abs(W_ext - dE)
    audit_scale = max(float(np.max(np.abs(W_ext))), float(np.max(np.abs(dE))), 1e-300)

    # ---- 窗末状态 + lockup 收口 ----------------------------------------------
    Rb_Tc = _R_of(Q[-1])                              # 基座 body->inertial @ T_c
    Rt_Tc = _R_of(q_t_h[-1])                          # 目标 body->inertial @ T_c
    u_Tc = np.concatenate([Vb[-1], np.zeros(6), etad_h[-1]])
    target_Tc = {
        "id": target["id"], "m": m_t,
        "I_S": Rb_Tc.T @ (Rt_Tc @ I_t0 @ Rt_Tc.T) @ Rb_Tc,
        "c_S": Rb_Tc.T @ (r_t_h[-1] - r[-1]),
        "v_S": Rb_Tc.T @ v_t_h[-1], "w_S": Rb_Tc.T @ w_t_h[-1],
    }
    out = {
        "t": ts, "r": r, "Q": Q, "Vb": Vb, "eta": eta_h, "etad": etad_h,
        "tip_L_m": tip[:, 0], "tip_R_m": tip[:, 1], "modal_energy_J": modal_E,
        "E_damp": E_damp, "W_c": W_c, "W_t": W_t,
        "target_v_I": v_t_h, "target_w_I": w_t_h, "target_r_I": r_t_h,
        "momentum_drift_max": mom_drift,
        "momentum_drift_max_abs": float(np.max(mom_drift)),
        "energy_audit_rel": float(np.max(audit) / audit_scale),
        "u_Tc": u_Tc, "eta_Tc": eta_h[-1], "r_Tc": r[-1], "quat_Tc": Q[-1],
        "target_Tc": target_Tc, "nfev": int(sol.nfev),
        "lam_S": lam, "T_c_s": T_c,
    }
    if lockup:
        cap_lock = solve_capture(model, th, eta_h[-1], u_Tc, target_Tc, mode=mode)
        out["lockup"] = cap_lock
        out["lockup_dJ_Ns"] = float(np.linalg.norm(cap_lock["lambda_J_S"]))
        out["lockup_dL_Nms"] = float(np.linalg.norm(cap_lock["lambda_L_S"]))
        out["lockup_rel_to_lam"] = float(
            np.linalg.norm(np.concatenate([cap_lock["lambda_J_S"],
                                           cap_lock["lambda_L_S"]]))
            / max(np.linalg.norm(lam), 1e-300))
        out["u_post"] = cap_lock["u_post"]
        out["target_post"] = {"v_S": cap_lock["target_v_post_S"],
                              "w_S": cap_lock["target_w_post_S"]}
    return out
