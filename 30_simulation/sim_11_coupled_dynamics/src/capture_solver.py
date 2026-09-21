"""capture_solver.py -- 柔性底盘的矢量式捕获冲量（sim_06 规范推广到全耦合模型）。

物理：捕获瞬间在末端 E 点作用等值反向冲量对 (lambda = [J(3); L(3)])，
  - 服务星侧（本模型，关节抱闸：theta_dot 跳变为 0）：M_RL du_RL = Phi_RL^T lambda
  - 目标侧（刚体）：dv_t = -J/m_t,  dw_t = -I_t^{-1}((p-r_t) x J + L)
约束（S 系分量，捕获瞬时刻）：
  rigid_lock_6dof: 后向相对速度 [v_E - v_p,t; w_E - w_t]^+ = 0（6 约束，J+L 全解）
  point_capture_3dof: 仅点速度相等（3 约束，纯力冲量 J，L=0，理想球铰）
解：lambda = -(G_c + G_t)^{-1} rel_pre，G_c = Phi M^{-1} Phi^T（柔性 Delassus，
含帆板模态列 —— 冲量向帆板模态的分配由耦合质量阵自动裁定），G_t 为目标刚体 Delassus。

退化校验（tests 断言）：帆板刚化 + 关节抱闸时，本求解器与
30_simulation/common/capture_impulse.py::rigidize / rigidize_point_contact 机器精度一致。
塑性耗散 dT >= 0、组合系统动量守恒 |dP|=|dL|=0（内力冲量）为内置校验输出。"""
import numpy as np

from b601_model import skew
from rigid_body import q_to_R, load_object
from capture_impulse import GRASP, TUMBLE_AXIS      # 30_simulation/common 只读（SSOT 一致的抓点/翻滚轴）


def ee_partial_velocity(model, th):
    """末端 E 的部分速度矩阵 Phi (6 x nu)：u -> [v_E; w_E]（S 系）。"""
    f = model.arm.fk(th)
    pE = f["T_E"][:3, 3]
    Phi = np.zeros((6, model.nu))
    Phi[0:3, 0:3] = np.eye(3)
    Phi[0:3, 3:6] = -skew(pE)
    Phi[3:6, 3:6] = np.eye(3)
    for i in range(6):
        a, o = f["joint_axes"][i], f["joint_origins"][i]
        Phi[0:3, 6 + i] = np.cross(a, pE - o)
        Phi[3:6, 6 + i] = a
    return Phi, pE, f


def target_state_in_S(model, r_b, quat, th, target_id, tumble_dps, tumble_axis=None):
    """按 sim_06 约定放置目标：抓点与 E 原点重合、目标本体轴与惯性系对齐、
    平动静止、绕 tumble_axis 翻滚 tumble_dps。返回 S 系下目标状态字典。"""
    tgt = load_object(target_id)
    axis = TUMBLE_AXIS if tumble_axis is None else np.asarray(tumble_axis, float)
    axis = axis / np.linalg.norm(axis)
    R = q_to_R(np.asarray(quat, float) / np.linalg.norm(quat)).as_matrix()
    _, pE_S, _ = ee_partial_velocity(model, th)
    r_g_I = GRASP[target_id]                        # 抓点相对目标质心（惯性/目标对齐轴）
    pE_I = np.asarray(r_b, float) + R @ pE_S
    r_t_I = pE_I - r_g_I
    w_t_I = np.deg2rad(tumble_dps) * axis
    # 转 S 系（模型全部在 S 系分量下解算）
    c_t_S = R.T @ (r_t_I - np.asarray(r_b, float))
    I_t_S = R.T @ np.asarray(tgt["I"], float) @ R
    w_t_S = R.T @ w_t_I
    return {"id": target_id, "m": float(tgt["mass"]), "I_S": I_t_S, "c_S": c_t_S,
            "v_S": np.zeros(3), "w_S": w_t_S, "I_I": np.asarray(tgt["I"], float),
            "r_I": r_t_I, "w_I": w_t_I, "grasp_lever_I": r_g_I}


def solve_capture(model, th, eta, u_pre, target, mode="rigid_lock_6dof"):
    """解捕获冲量。u_pre 为捕获前瞬间广义速度（含 v_app 已叠加）。
    返回 dict：lambda(J, L), du(广义速度跳变), 目标跳变, 能量与动量校验。"""
    u_pre = np.asarray(u_pre, float)
    geo = model.geometry(th, eta)
    M = geo["M"]
    Phi, pE, _ = ee_partial_velocity(model, th)

    RL = model.i_be                                  # 关节抱闸：theta_dot 行不参与跳变
    M_RL = M[np.ix_(RL, RL)]
    Phi_RL = Phi[:, RL]
    G_c = Phi_RL @ np.linalg.solve(M_RL, Phi_RL.T)   # 柔性 Delassus (6x6)

    m_t, I_t = target["m"], target["I_S"]
    d = pE - target["c_S"]
    D = skew(d)
    I_inv = np.linalg.inv(I_t)
    G_t = np.zeros((6, 6))
    G_t[0:3, 0:3] = np.eye(3) / m_t - D @ I_inv @ D
    G_t[0:3, 3:6] = -D @ I_inv
    G_t[3:6, 0:3] = I_inv @ D
    G_t[3:6, 3:6] = I_inv

    v_E_pre = Phi @ u_pre                            # [v_E; w_E]
    v_pt_pre = target["v_S"] + np.cross(target["w_S"], d)
    rel_pre = np.concatenate([v_E_pre[0:3] - v_pt_pre, v_E_pre[3:6] - target["w_S"]])

    if mode == "rigid_lock_6dof":
        lam = np.linalg.solve(G_c + G_t, -rel_pre)
        J, L = lam[0:3], lam[3:6]
    elif mode == "point_capture_3dof":
        lam3 = np.linalg.solve((G_c + G_t)[0:3, 0:3], -rel_pre[0:3])
        J, L = lam3, np.zeros(3)
        lam = np.concatenate([J, L])
    else:
        raise ValueError(mode)

    du = np.zeros(model.nu)
    du[RL] = np.linalg.solve(M_RL, Phi_RL.T @ lam)
    u_post = u_pre + du
    dv_t = -J / m_t
    dw_t = -I_inv @ (np.cross(d, J) + L)
    v_t_post = target["v_S"] + dv_t
    w_t_post = target["w_S"] + dw_t

    # ---- 校验量：能量（塑性 dT>=0）与内力冲量动量守恒 -------------------------
    T_c_pre = float(0.5 * u_pre @ (M @ u_pre))
    T_c_post = float(0.5 * u_post @ (M @ u_post))
    T_t = lambda v, w: float(0.5 * m_t * v @ v + 0.5 * w @ (I_t @ w))  # noqa: E731
    KE_pre = T_c_pre + T_t(target["v_S"], target["w_S"])
    KE_post = T_c_post + T_t(v_t_post, w_t_post)
    A = geo["A"]
    h_c_pre = A @ u_pre
    h_c_post = A @ u_post
    h_t = lambda v, w, c: np.concatenate(                              # noqa: E731
        [m_t * v, I_t @ w + m_t * np.cross(c, v)])
    dh = (h_c_post + h_t(v_t_post, w_t_post, target["c_S"])
          - h_c_pre - h_t(target["v_S"], target["w_S"], target["c_S"]))

    m_md = model.n_modes
    detad = du[model.i_e]
    etad_pre = u_pre[model.i_e]
    etad_post = u_post[model.i_e]
    return {
        "mode": mode, "lambda_J_S": J, "lambda_L_S": L,
        "du": du, "u_post": u_post,
        "dVb": du[0:6], "detad": detad,
        "target_v_post_S": v_t_post, "target_w_post_S": w_t_post,
        "target_dv_S": dv_t, "target_dw_S": dw_t,
        "pE_S": pE, "lever_d_S": d,
        "rel_pre": rel_pre,
        "rel_post": np.concatenate([Phi @ u_post])[[0, 1, 2, 3, 4, 5]]
                    - np.concatenate([v_t_post + np.cross(w_t_post, d), w_t_post]),
        "KE_pre_J": KE_pre, "KE_post_J": KE_post, "dT_J": KE_pre - KE_post,
        "momentum_residual": dh,
        # 速度跃变量的二次项是“kick 能量尺度”；A1 末态仍有残余模态速度时，
        # 真正的模态动能变化还包含 etad_pre·detad 交叉项，二者不得混称。
        "modal_velocity_kick_energy_J": float(0.5 * detad @ detad) if m_md else 0.0,
        "modal_energy_change_J": float(
            0.5 * etad_post @ etad_post - 0.5 * etad_pre @ etad_pre
        ) if m_md else 0.0,
    }


def chaser_composite(model, th, eta):
    """当前构型下服务星整机（基座固连体+臂+帆板+已并入目标）合成刚体
    (m, c_S, I_S 对合成质心)。刚性极限校验与 sim_06 对照用。"""
    geo = model.geometry(th, eta)
    parts = []
    for b in geo["bodies"]:
        parts.append((b["m"], b["c"], b["I"]))
    for pd in geo["pans"]:
        pan, x = pd["pan"], pd["x"]
        for k in range(len(pan.m_nodes)):
            parts.append((pan.m_nodes[k], x[k], np.zeros((3, 3))))
    m_tot = sum(p[0] for p in parts)
    c = sum(p[0] * np.asarray(p[1], float) for p in parts) / m_tot
    I = np.zeros((3, 3))
    for m, ci, Ic in parts:
        dd = np.asarray(ci, float) - c
        I += Ic + m * ((dd @ dd) * np.eye(3) - np.outer(dd, dd))
    return m_tot, c, I
