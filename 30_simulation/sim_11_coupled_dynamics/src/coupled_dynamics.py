"""coupled_dynamics.py -- 星-臂-帆板全耦合动力学核心（路线 A：浮动基座树形多体 + FFR 帆板）。

广义坐标 / 拟速度（S = 服务星本体系，基座量用 S 系分量的拟速度）：
    q  = [r_b(3, 惯性系), q_b(quat4, 本体->惯性, scalar-first), theta(6), eta_L(m), eta_R(m)]
    u  = [v_b(3), w_b(3), thetad(6), etad_L(m), etad_R(m)]      (v_b = R^T rdot_b)

动力学方程（Kane / 投影 Newton-Euler，与拉格朗日严格一致）：
    M(q) udot + c(q,u) = Q ,   Q = [0(基座, 自由漂浮); tau(关节); -K eta - D etad(模态)]
质量阵按 基座 b / 臂 a / 帆板 eta 分块：M_bb, M_ba, M_beta, M_aa, M_aeta, M_etaeta。
本拟速度坐标下 M_a,eta ≡ 0（臂与帆板速度都相对基座定义，耦合经基座块传递——报告 2.4 节）。

点/体运动学（S 系分量；R = 本体->惯性）：
    v_S = v_b + w_b x x + xdot_rel
    a_S = vdot_b + w_b x v_b + wdot_b x x + w_b x (w_b x x) + 2 w_b x xdot_rel + a_rel
（`w_b x v_b` 输运项不可省：其虚功率 = P_S·(w_b x v_b)，在零动量流形上恰为零，
 因此只有 full 模式的动量漂移能暴露它 —— 本模块的实现教训，tests 有专门断言。）

体系构成（全部 SSOT 装载，见 config_loader）：
  - 基座固连刚体：bus(servicer_12U_bus_v1) / adapter(T_SM) / 臂 base_link / 帆板切片转动惯量集中块
  - 臂 link1..6（B601，link6 含锁定夹爪，复用 sim_05 b601_model 只读）
  - 帆板 L/R：FFR 质点切片（ffr_panel）
  - 可选：捕获后与 link6 固连的目标刚体

两种积分模式：
  reduced_momentum —— 惯性系动量 h_I 守恒为代数约束，V_b = H_bb^{-1}(h_S - H_bm qdot_m)，
      动量守恒到机器精度（对齐 sim_05 证据文化 7.3e-17）；模态/基座加速度由 [b,eta] 行联立求解。
  full —— V_b 进入状态量，全部二阶动力学积分；动量漂移作为装配一致性交叉证据。

能量定理（精确成立，能量审计 Gate 依据）：d(T+U)/dt = tau·thetad - etad^T D etad。
纯 numpy/scipy（Radau/BDF/DOP853 均可选）。"""
import numpy as np
from scipy.integrate import solve_ivp

from config_loader import load_model_config, MODEL_CARD_DEFAULT
from ffr_panel import FFRPanel
from b601_model import B601Arm, T_SM_4x4, skew, transform_inertial   # sim_05 只读
from rigid_body import qmult, q_to_R, q_to_euler_deg                  # 30_simulation/common 只读


def quintic(t, T, q0, q1):
    """五次多项式 10-15-6 形函数（端点速度/加速度为零；与 sim_05 min_jerk 同一多项式）。
    返回 (pos, vel, acc)，t 标量。区间外钳位保持。"""
    x = np.clip(t / T, 0.0, 1.0)
    s = 10 * x ** 3 - 15 * x ** 4 + 6 * x ** 5
    inside = (t >= 0.0) & (t <= T)
    sd = np.where(inside, (30 * x ** 2 - 60 * x ** 3 + 30 * x ** 4) / T, 0.0)
    sdd = np.where(inside, (60 * x - 180 * x ** 2 + 120 * x ** 3) / T ** 2, 0.0)
    dq = np.asarray(q1, float) - np.asarray(q0, float)
    return np.asarray(q0, float) + dq * s, dq * sd, dq * sdd


class JointTrajectory:
    """关节五次多项式轨迹 q0 -> q1，时长 T；T 后保持 q1。"""
    def __init__(self, q_start, q_end, T):
        self.q0 = np.asarray(q_start, float)
        self.q1 = np.asarray(q_end, float)
        self.T = float(T)

    def __call__(self, t):
        return quintic(t, self.T, self.q0, self.q1)


class HoldTrajectory:
    """定位形保持（捕获后关节抱闸）。"""
    def __init__(self, q_hold):
        self.q = np.asarray(q_hold, float)
        self.z = np.zeros_like(self.q)

    def __call__(self, t):
        return self.q, self.z, self.z


class CoupledModel:
    """全耦合模型：装配 M / 偏置 / 动量 / 能量 / 广义雅可比，并提供两种模式的积分。"""

    def __init__(self, cfg=None, n_modes=None, rigid_panels=False, zeta=None,
                 stiffness_case=None, n_quad=None):
        self.cfg = cfg if cfg is not None else load_model_config(MODEL_CARD_DEFAULT)
        pc = self.cfg["panel_cfg"]
        m = 0 if rigid_panels else int(pc["n_modes"] if n_modes is None else n_modes)
        zeta = float(pc["zeta_modal"] if zeta is None else zeta)
        case = str(pc["stiffness_case"] if stiffness_case is None else stiffness_case)
        nq = int(pc["n_quad"] if n_quad is None else n_quad)
        p = self.cfg["panel"]
        EI = p["EI_cases_Nm2"][case]
        self.stiffness_case = case
        self.n_modes = m
        self.rigid_panels = bool(rigid_panels or m == 0)

        # ---- 帆板 L/R（界面位姿取 frame_tree SSOT） ---------------------------
        self.panels = []
        for side in ("L", "R"):
            fr = self.cfg["panels_frames"][side]
            self.panels.append(FFRPanel(
                side, fr["root_S"], fr["deploy_S"], fr["normal_S"],
                p["span_L_m"], p["mu_kg_per_m"], p["chord_b_m"], p["thickness_t_m"],
                EI, n_modes=m, n_quad=nq, zeta=zeta))

        # ---- 基座固连刚体（S 系，惯量对各自质心） ------------------------------
        self.arm = B601Arm()
        bus = self.cfg["bus"]
        adp = self.cfg["adapter"]
        m_a, cg_a, I_a = transform_inertial(T_SM_4x4(), adp["mass"], adp["cg"], adp["I"])
        m0, c0, I0 = self.arm.base_link_inertial_in_S()
        self.fixed_bodies = [
            ("bus", bus["mass"], np.asarray(bus["cg"], float), np.asarray(bus["I"], float)),
            ("adapter", m_a, cg_a, I_a),
            ("arm_base_link", m0, c0, I0),
        ]
        for pan in self.panels:   # 切片自转惯量集中块（零质量，纯惯量，基座固连）
            self.fixed_bodies.append((f"panel_{pan.name}_rotary_lump",
                                      0.0, pan.root.copy(), pan.J_rot_S))

        # ---- 模态刚度/阻尼（块对角 [eta_L, eta_R]） ----------------------------
        self.K_eta = np.zeros((2 * m, 2 * m))
        self.D_eta = np.zeros((2 * m, 2 * m))
        for ip, pan in enumerate(self.panels):
            sl = slice(ip * m, (ip + 1) * m)
            self.K_eta[sl, sl] = pan.K
            self.D_eta[sl, sl] = pan.D

        # ---- 目标（捕获后并入，attach_target 设定） ----------------------------
        self.target = None

        self.nu = 12 + 2 * m                     # [V_b(6), thetad(6), etad(2m)]
        self.i_b = np.arange(0, 6)
        self.i_a = np.arange(6, 12)
        self.i_e = np.arange(12, 12 + 2 * m)
        self.i_be = np.concatenate([self.i_b, self.i_e])

    # ================= 目标并入（6DOF 刚性锁定后） ============================
    def attach_target(self, m_t, I_t_S, c_t_S, th):
        """把目标刚体（当前 S 系下质心 c_t_S、对质心惯量 I_t_S）与 link6 固连。"""
        f = self.arm.fk(th)
        T6 = f["T"]["link6"]
        R6, p6 = T6[:3, :3], T6[:3, 3]
        self.target = {"m": float(m_t),
                       "c_rel6": R6.T @ (np.asarray(c_t_S, float) - p6),
                       "I_rel6": R6.T @ np.asarray(I_t_S, float) @ R6}

    def detach_target(self):
        self.target = None

    def _eta_split(self, eta):
        m = self.n_modes
        eta = np.asarray(eta, float)
        return eta[:m], eta[m:]

    # ================= 单遍几何装配（每个 RHS 调一次） =========================
    def geometry(self, th, eta):
        """一次 FK，装配并缓存：M(q)、动量映射 A(q)、逐体 (V, W, c, I, k) 与
        臂轴/原点数据（bias 复用）。返回 geo 字典。"""
        nu = self.nu
        m_md = self.n_modes
        f = self.arm.fk(th)
        bodies = []                                       # 刚体（含目标）
        for name, mass, c, I in self.fixed_bodies:
            bodies.append({"m": mass, "c": c, "I": I, "k": 0, "Jv": None, "Jw": None})
        for k, s in enumerate(self.arm.link_com_states(th), start=1):
            bodies.append({"m": s["mass"], "c": s["c"], "I": s["I"], "k": k,
                           "Jv": s["Jv"], "Jw": s["Jw"]})
        if self.target is not None:
            T6 = f["T"]["link6"]
            R6, p6 = T6[:3, :3], T6[:3, 3]
            c_t = p6 + R6 @ self.target["c_rel6"]
            I_t = R6 @ self.target["I_rel6"] @ R6.T
            Jv = np.zeros((3, 6))
            Jw = np.zeros((3, 6))
            for i in range(6):
                a, o = f["joint_axes"][i], f["joint_origins"][i]
                Jv[:, i] = np.cross(a, c_t - o)
                Jw[:, i] = a
            bodies.append({"m": self.target["m"], "c": c_t, "I": I_t, "k": 6,
                           "Jv": Jv, "Jw": Jw})

        M = np.zeros((nu, nu))
        A = np.zeros((6, nu))
        for b in bodies:
            V = np.zeros((3, nu)); W = np.zeros((3, nu))
            V[:, 0:3] = np.eye(3); V[:, 3:6] = -skew(b["c"])
            W[:, 3:6] = np.eye(3)
            if b["Jv"] is not None:
                V[:, 6:12] = b["Jv"]
                W[:, 6:12] = b["Jw"]
            b["V"], b["W"] = V, W
            mV = b["m"] * V
            M += V.T @ mV + W.T @ b["I"] @ W
            A[0:3] += mV
            A[3:6] += skew(b["c"]) @ mV + b["I"] @ W

        etaL, etaR = self._eta_split(eta)
        pans = []
        for ip, (pan, et) in enumerate(zip(self.panels, (etaL, etaR))):
            x = pan.node_positions(et)                    # (n,3)
            mk = pan.m_nodes
            cols = 12 + ip * m_md + np.arange(m_md)
            m_tot = mk.sum()
            Sx = np.einsum("k,kij->ij", mk, _skew_batch(x))       # sum m_k [x]x
            St = np.einsum("k,kij->ij", mk, _skewT_skew_batch(x))
            M[0:3, 0:3] += m_tot * np.eye(3)
            M[0:3, 3:6] += -Sx
            M[3:6, 0:3] += Sx                              # (-[x]x)^T = +[x]x
            M[3:6, 3:6] += St
            A[0:3, 0:3] += m_tot * np.eye(3)
            A[0:3, 3:6] += -Sx
            A[3:6, 0:3] += Sx
            A[3:6, 3:6] += St
            if m_md:
                B_cols = np.einsum("k,ki->i", mk, pan.Phi)          # = B_t
                xc3 = np.cross(x, pan.e3[None, :])                  # (n,3) x_k x e3
                Mrot = np.einsum("k,ki,kj->ji", mk, pan.Phi, xc3)   # (3,m)
                Mee = np.einsum("k,ki,kj->ij", mk, pan.Phi, pan.Phi)
                M[0:3, cols] += np.outer(pan.e3, B_cols)
                M[cols, 0:3] += np.outer(B_cols, pan.e3)
                M[3:6, cols] += Mrot
                M[cols, 3:6] += Mrot.T
                M[np.ix_(cols, cols)] += Mee
                A[0:3, cols] += np.outer(pan.e3, B_cols)
                A[3:6, cols] += Mrot
            pans.append({"pan": pan, "x": x, "cols": cols, "eta": et})
        return {"f": f, "bodies": bodies, "pans": pans, "M": M, "A": A,
                "th": np.asarray(th, float)}

    def bias_from_geometry(self, geo, u):
        """c(q,u) = F*(udot=0)：M udot + c = Q 中的速度二次项（复用 geometry 缓存）。"""
        nu = self.nu
        m_md = self.n_modes
        u = np.asarray(u, float)
        vb, wb = u[0:3], u[3:6]
        thd = u[6:12]
        etad = u[12:]
        wxv = np.cross(wb, vb)                 # 基座平移输运项 w_b x v_b（勿省）
        c_vec = np.zeros(nu)
        f = geo["f"]

        # ---- 臂速度递推数据（S 系；轴 i 固连于 link i-1） ----------------------
        axes, origins = f["joint_axes"], f["joint_origins"]
        omega_prev = np.zeros((6, 3))          # 装 link i-1 的相对角速度
        acc = np.zeros(3)
        for i in range(6):
            omega_prev[i] = acc
            acc = acc + axes[i] * thd[i]
        adot = np.cross(omega_prev, axes)                     # (6,3) 轴变率
        odot = np.zeros((6, 3))
        for i in range(6):
            for j in range(i):
                odot[i] += thd[j] * np.cross(axes[j], origins[i] - origins[j])

        for b in geo["bodies"]:
            k = b["k"]
            c_b, I_S = b["c"], b["I"]
            if k == 0:                                        # 基座固连
                a_bias = wxv + np.cross(wb, np.cross(wb, c_b))
                hd = np.cross(wb, I_S @ wb)
            else:
                w_rel = axes[:k].T @ thd[:k]
                alpha_rel = adot[:k].T @ thd[:k]              # 速度相关部分
                cdot = b["Jv"] @ thd
                a_rel = np.zeros(3)
                for i in range(k):
                    a_rel += thd[i] * (np.cross(adot[i], c_b - origins[i])
                                       + np.cross(axes[i], cdot - odot[i]))
                a_bias = (wxv + np.cross(wb, np.cross(wb, c_b))
                          + 2.0 * np.cross(wb, cdot) + a_rel)
                w_S = wb + w_rel
                hd = (I_S @ alpha_rel + np.cross(w_rel, I_S @ w_S)
                      - I_S @ np.cross(w_rel, w_S) + np.cross(wb, I_S @ w_S))
            c_vec += b["V"].T @ (b["m"] * a_bias) + b["W"].T @ hd

        etadL, etadR = (etad[:m_md], etad[m_md:]) if m_md else (etad, etad)
        for pd, etd in zip(geo["pans"], (etadL, etadR)):
            pan, x = pd["pan"], pd["x"]
            mk = pan.m_nodes
            vrel = pan.node_rel_velocities(etd)
            wbb = np.broadcast_to(wb, x.shape)
            a_bias = (wxv[None, :] + np.cross(wbb, np.cross(wbb, x))
                      + 2.0 * np.cross(wbb, vrel))
            c_vec[0:3] += np.einsum("k,ki->i", mk, a_bias)
            c_vec[3:6] += np.einsum("k,ki->i", mk, np.cross(x, a_bias))
            if m_md:
                c_vec[pd["cols"]] += np.einsum("k,ki,k->i", mk, pan.Phi, a_bias @ pan.e3)
        return c_vec

    # ---- 兼容包装（tests / 诊断用） -------------------------------------------
    def mass_matrix(self, th, eta):
        return self.geometry(th, eta)["M"]

    def momentum_matrix(self, th, eta):
        """A (6 x nu)：S 系、对 S 原点的 [P; L]。H_bb = A[:, :6]，H_bm = A[:, 6:]。"""
        return self.geometry(th, eta)["A"]

    def bias_vector(self, th, eta, u):
        return self.bias_from_geometry(self.geometry(th, eta), u)

    # ================= 动量 / 能量 / 诊断 ======================================
    def momentum_S(self, th, eta, u):
        return self.momentum_matrix(th, eta) @ np.asarray(u, float)

    def momentum_inertial(self, r_b, quat, th, eta, u):
        """独立路径：逐体在惯性系合成 [P; L_对惯性原点]（不经 A 矩阵装配）。"""
        R = q_to_R(np.asarray(quat, float) / np.linalg.norm(quat)).as_matrix()
        r_b = np.asarray(r_b, float)
        u = np.asarray(u, float)
        vb, wb, thd, etad = u[0:3], u[3:6], u[6:12], u[12:]
        P = np.zeros(3)
        L = np.zeros(3)
        f = self.arm.fk(th)
        geo_bodies = self.geometry(th, eta)["bodies"]
        for b in geo_bodies:
            v_S = vb + np.cross(wb, b["c"]) + (b["Jv"] @ thd if b["Jv"] is not None else 0.0)
            w_S = wb + (b["Jw"] @ thd if b["Jw"] is not None else 0.0)
            r_I = r_b + R @ b["c"]
            v_I = R @ v_S
            P += b["m"] * v_I
            L += (R @ b["I"] @ R.T) @ (R @ w_S) + b["m"] * np.cross(r_I, v_I)
        m_md = self.n_modes
        etaL, etaR = self._eta_split(eta)
        etadL, etadR = (etad[:m_md], etad[m_md:]) if m_md else (etad, etad)
        for pan, et, etd in zip(self.panels, (etaL, etaR), (etadL, etadR)):
            x = pan.node_positions(et)
            vrel = pan.node_rel_velocities(etd)
            wbb = np.broadcast_to(wb, x.shape)
            v_S = vb[None, :] + np.cross(wbb, x) + vrel
            r_I = r_b[None, :] + x @ R.T
            v_I = v_S @ R.T
            P += np.einsum("k,ki->i", pan.m_nodes, v_I)
            L += np.einsum("k,ki->i", pan.m_nodes, np.cross(r_I, v_I))
        return np.concatenate([P, L])

    def momentum_inertial_groups(self, r_b, quat, th, eta, u):
        """按体组分解惯性系动量 [P; L_对惯性原点]：base(基座固连) / arm(连杆) /
        panels(帆板切片) / target(已并入目标)。A2 动量重分配诊断用。"""
        R = q_to_R(np.asarray(quat, float) / np.linalg.norm(quat)).as_matrix()
        r_b = np.asarray(r_b, float)
        u = np.asarray(u, float)
        vb, wb, thd, etad = u[0:3], u[3:6], u[6:12], u[12:]
        groups = {g: np.zeros(6) for g in ("base", "arm", "panels", "target")}
        geo = self.geometry(th, eta)
        n_fixed = len(self.fixed_bodies)
        for ib, b in enumerate(geo["bodies"]):
            if ib < n_fixed:
                g = "base"
            elif self.target is not None and ib == len(geo["bodies"]) - 1:
                g = "target"
            else:
                g = "arm"
            v_S = vb + np.cross(wb, b["c"]) + (b["Jv"] @ thd if b["Jv"] is not None else 0.0)
            w_S = wb + (b["Jw"] @ thd if b["Jw"] is not None else 0.0)
            r_I = r_b + R @ b["c"]
            v_I = R @ v_S
            groups[g][0:3] += b["m"] * v_I
            groups[g][3:6] += (R @ b["I"] @ R.T) @ (R @ w_S) + b["m"] * np.cross(r_I, v_I)
        m_md = self.n_modes
        etaL, etaR = self._eta_split(eta)
        etadL, etadR = (etad[:m_md], etad[m_md:]) if m_md else (etad, etad)
        for pan, et, etd in zip(self.panels, (etaL, etaR), (etadL, etadR)):
            x = pan.node_positions(et)
            vrel = pan.node_rel_velocities(etd)
            wbb = np.broadcast_to(wb, x.shape)
            v_I = (vb[None, :] + np.cross(wbb, x) + vrel) @ R.T
            r_I = r_b[None, :] + x @ R.T
            groups["panels"][0:3] += np.einsum("k,ki->i", pan.m_nodes, v_I)
            groups["panels"][3:6] += np.einsum("k,ki->i", pan.m_nodes, np.cross(r_I, v_I))
        return groups

    def kinetic_energy(self, th, eta, u):
        u = np.asarray(u, float)
        return float(0.5 * u @ (self.mass_matrix(th, eta) @ u))

    def strain_energy(self, eta):
        eta = np.asarray(eta, float)
        return float(0.5 * eta @ (self.K_eta @ eta))

    # ================= 广义雅可比 J*（帆板增广） ================================
    def generalized_jacobian(self, th, eta):
        """J* (6 x (6+2m))：零动量流形上 [thetad; etad] -> 末端 E 空间速度（S 系）。
        J* = [J_m, 0] - J_b H_bb^{-1} H_bm（Umetani-Yoshida 增广形式）。"""
        f = self.arm.fk(th)
        J_m = self.arm.jacobian(th, fk_out=f)
        rE = f["T_E"][:3, 3]
        J_b = np.eye(6)
        J_b[:3, 3:] = -skew(rE)
        A = self.momentum_matrix(th, eta)
        J_full = np.zeros((6, 6 + 2 * self.n_modes))
        J_full[:, :6] = J_m
        return J_full - J_b @ np.linalg.solve(A[:, :6], A[:, 6:])

    # ================= 加速度求解（theta 规定） ================================
    def accelerations(self, th, eta, u, thdd, geo=None, Q_ext=None):
        """规定 thetadd，解 [基座; 模态] 行：M_RR udot_R = Q_R - c_R - M_Ra thdd。
        Q_ext: 可选外部广义力（nu 向量，如接触窗 EE 力旋量的 Phi^T w 投影）；
        None 时与旧行为逐位一致（自由漂浮）。返回 (udot 全量, tau 关节力矩)。"""
        if geo is None:
            geo = self.geometry(th, eta)
        M = geo["M"]
        c = self.bias_from_geometry(geo, u)
        eta = np.asarray(eta, float)
        etad = np.asarray(u, float)[12:]
        Q = np.zeros(self.nu)
        if self.n_modes:
            Q[self.i_e] = -(self.K_eta @ eta) - (self.D_eta @ etad)
        if Q_ext is not None:
            Q = Q + np.asarray(Q_ext, float)
        R = self.i_be
        rhs = Q[R] - c[R] - M[np.ix_(R, self.i_a)] @ np.asarray(thdd, float)
        udot_R = np.linalg.solve(M[np.ix_(R, R)], rhs)
        udot = np.zeros(self.nu)
        udot[R] = udot_R
        udot[self.i_a] = thdd
        tau = M[self.i_a] @ udot + c[self.i_a] - Q[self.i_a]
        return udot, tau

    # ================= 积分：reduced_momentum 模式 =============================
    def integrate_reduced(self, traj, t_end, r0=None, quat0=None, eta0=None, etad0=None,
                          h_I=None, method="Radau", rtol=1e-10, atol=1e-12, n_out=601,
                          t0=0.0):
        """动量流形约简积分。状态 y = [r_b(3), quat(4), eta(2m), etad(2m), W_joint, E_damp]。
        h_I: 惯性系常动量 6 向量（None = 零动量自由漂浮）。"""
        m2 = 2 * self.n_modes
        r0 = np.zeros(3) if r0 is None else np.asarray(r0, float)
        quat0 = np.array([1.0, 0, 0, 0]) if quat0 is None else np.asarray(quat0, float)
        eta0 = np.zeros(m2) if eta0 is None else np.asarray(eta0, float)
        etad0 = np.zeros(m2) if etad0 is None else np.asarray(etad0, float)
        h_I = np.zeros(6) if h_I is None else np.asarray(h_I, float)

        def base_velocity_from_geo(geo, r_b, quat, thd, etad):
            R = q_to_R(quat / np.linalg.norm(quat)).as_matrix()
            P_I, L_I = h_I[:3], h_I[3:]
            h_S = np.concatenate([R.T @ P_I, R.T @ (L_I - np.cross(r_b, P_I))])
            A = geo["A"]
            qdot_m = np.concatenate([thd, etad])
            return np.linalg.solve(A[:, :6], h_S - A[:, 6:] @ qdot_m)

        def rhs(t, y):
            r_b, quat = y[0:3], y[3:7]
            eta, etad = y[7:7 + m2], y[7 + m2:7 + 2 * m2]
            th, thd, thdd = traj(t)
            geo = self.geometry(th, eta)
            Vb = base_velocity_from_geo(geo, r_b, quat, thd, etad)
            u = np.concatenate([Vb, thd, etad])
            udot, tau = self.accelerations(th, eta, u, thdd, geo=geo)
            qn = quat / np.linalg.norm(quat)
            Rb = q_to_R(qn).as_matrix()
            dy = np.empty_like(y)
            dy[0:3] = Rb @ Vb[:3]
            dy[3:7] = 0.5 * qmult(qn, np.array([0.0, *Vb[3:6]]))
            dy[7:7 + m2] = etad
            dy[7 + m2:7 + 2 * m2] = udot[self.i_e]
            dy[7 + 2 * m2] = float(tau @ thd)                       # 关节输入功率
            dy[8 + 2 * m2] = float(etad @ (self.D_eta @ etad)) if m2 else 0.0  # 阻尼耗散率
            return dy

        y0 = np.concatenate([r0, quat0, eta0, etad0, [0.0, 0.0]])
        ts = np.linspace(t0, t_end, n_out)
        sol = solve_ivp(rhs, (t0, t_end), y0, t_eval=ts, method=method,
                        rtol=rtol, atol=atol)
        assert sol.success, sol.message

        def vb_recompute(r_b, quat, th, eta, thd, etad):
            return base_velocity_from_geo(self.geometry(th, eta), r_b, quat, thd, etad)

        return self._collect(sol, traj, vb_recompute, full=False)

    # ================= 积分：full 模式（交叉证据） ==============================
    def integrate_full(self, traj, t_end, r0=None, quat0=None, Vb0=None, eta0=None,
                       etad0=None, method="Radau", rtol=1e-10, atol=1e-12, n_out=601,
                       t0=0.0):
        """全量二阶积分。状态 y = [r_b, quat, V_b(6), eta, etad, W_joint, E_damp]。"""
        m2 = 2 * self.n_modes
        r0 = np.zeros(3) if r0 is None else np.asarray(r0, float)
        quat0 = np.array([1.0, 0, 0, 0]) if quat0 is None else np.asarray(quat0, float)
        Vb0 = np.zeros(6) if Vb0 is None else np.asarray(Vb0, float)
        eta0 = np.zeros(m2) if eta0 is None else np.asarray(eta0, float)
        etad0 = np.zeros(m2) if etad0 is None else np.asarray(etad0, float)

        def rhs(t, y):
            quat = y[3:7]
            Vb = y[7:13]
            eta, etad = y[13:13 + m2], y[13 + m2:13 + 2 * m2]
            th, thd, thdd = traj(t)
            u = np.concatenate([Vb, thd, etad])
            udot, tau = self.accelerations(th, eta, u, thdd)
            qn = quat / np.linalg.norm(quat)
            Rb = q_to_R(qn).as_matrix()
            dy = np.empty_like(y)
            dy[0:3] = Rb @ Vb[:3]
            dy[3:7] = 0.5 * qmult(qn, np.array([0.0, *Vb[3:6]]))
            dy[7:13] = udot[self.i_b]
            dy[13:13 + m2] = etad
            dy[13 + m2:13 + 2 * m2] = udot[self.i_e]
            dy[13 + 2 * m2] = float(tau @ thd)
            dy[14 + 2 * m2] = float(etad @ (self.D_eta @ etad)) if m2 else 0.0
            return dy

        y0 = np.concatenate([r0, quat0, Vb0, eta0, etad0, [0.0, 0.0]])
        ts = np.linspace(t0, t_end, n_out)
        sol = solve_ivp(rhs, (t0, t_end), y0, t_eval=ts, method=method,
                        rtol=rtol, atol=atol)
        assert sol.success, sol.message
        return self._collect(sol, traj, None, full=True)

    # ================= 结果整理 ================================================
    def _collect(self, sol, traj, vb_recompute, full=False):
        m2 = 2 * self.n_modes
        ts = sol.t
        n = len(ts)
        r = sol.y[0:3].T
        Q = sol.y[3:7].T
        Q = Q / np.linalg.norm(Q, axis=1, keepdims=True)
        if full:
            Vb_hist = sol.y[7:13].T.copy()
            eta_hist = sol.y[13:13 + m2].T
            etad_hist = sol.y[13 + m2:13 + 2 * m2].T
            W_joint = sol.y[13 + 2 * m2]
            E_damp = sol.y[14 + 2 * m2]
        else:
            eta_hist = sol.y[7:7 + m2].T
            etad_hist = sol.y[7 + m2:7 + 2 * m2].T
            W_joint = sol.y[7 + 2 * m2]
            E_damp = sol.y[8 + 2 * m2]
            Vb_hist = np.zeros((n, 6))
        T_hist = np.zeros(n)
        U_hist = np.zeros(n)
        hI_hist = np.zeros((n, 6))
        dev = np.zeros(n)
        eul = np.zeros((n, 3))
        tip = np.zeros((n, 2))
        tau_hist = np.zeros((n, 6))
        for i, t in enumerate(ts):
            th, thd, thdd = traj(t)
            eta, etad = eta_hist[i], etad_hist[i]
            if not full:
                Vb_hist[i] = vb_recompute(r[i], Q[i], th, eta, thd, etad)
            u = np.concatenate([Vb_hist[i], thd, etad])
            geo = self.geometry(th, eta)
            _, tau_hist[i] = self.accelerations(th, eta, u, thdd, geo=geo)
            T_hist[i] = float(0.5 * u @ (geo["M"] @ u))
            U_hist[i] = self.strain_energy(eta)
            hI_hist[i] = self.momentum_inertial(r[i], Q[i], th, eta, u)
            w = float(np.clip(abs(Q[i, 0]), 0.0, 1.0))
            dev[i] = np.degrees(2.0 * np.arccos(w))
            eul[i] = q_to_euler_deg(Q[i])
            if self.n_modes:
                tip[i, 0] = self.panels[0].tip_deflection(eta[:self.n_modes])
                tip[i, 1] = self.panels[1].tip_deflection(eta[self.n_modes:])
        return {"t": ts, "r": r, "Q": Q, "Vb": Vb_hist,
                "eta": eta_hist, "etad": etad_hist,
                "dev_angle_deg": dev, "euler_xyz_deg": eul,
                "tip_L_m": tip[:, 0], "tip_R_m": tip[:, 1],
                "T": T_hist, "U": U_hist, "E": T_hist + U_hist,
                "W_joint": W_joint, "E_damp": E_damp, "tau": tau_hist,
                "h_I": hI_hist, "nfev": int(sol.nfev)}


# ---------------- 小工具（批量斜对称阵） -------------------------------------
def _skew_batch(x):
    """(n,3) -> (n,3,3) 斜对称阵批量。"""
    n = x.shape[0]
    S = np.zeros((n, 3, 3))
    S[:, 0, 1] = -x[:, 2]; S[:, 0, 2] = x[:, 1]
    S[:, 1, 0] = x[:, 2];  S[:, 1, 2] = -x[:, 0]
    S[:, 2, 0] = -x[:, 1]; S[:, 2, 1] = x[:, 0]
    return S


def _skewT_skew_batch(x):
    """(n,3) -> (n,3,3)：[x]x^T [x]x = (x.x)E - x x^T（点质量 Steiner 核）。"""
    n = x.shape[0]
    d2 = np.einsum("ki,ki->k", x, x)
    out = np.zeros((n, 3, 3))
    out[:, 0, 0] = out[:, 1, 1] = out[:, 2, 2] = d2
    out -= np.einsum("ki,kj->kij", x, x)
    return out


if __name__ == "__main__":
    mdl = CoupledModel()
    th0 = np.zeros(6)
    eta0 = np.zeros(2 * mdl.n_modes)
    M = mdl.mass_matrix(th0, eta0)
    print("nu =", mdl.nu, " M symmetric err:", float(np.max(np.abs(M - M.T))))
    print("M eig min:", float(np.linalg.eigvalsh(M).min()))
    print("M_a,eta block max:", float(np.max(np.abs(M[np.ix_(mdl.i_a, mdl.i_e)]))))
    A = mdl.momentum_matrix(th0, eta0)
    print("H_bb[:3,:3] = m_tot*I:", A[0, 0], A[1, 1], A[2, 2])
    Jg = mdl.generalized_jacobian(th0, eta0)
    print("J* shape:", Jg.shape)
