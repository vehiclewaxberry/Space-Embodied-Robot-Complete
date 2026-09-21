"""D2：独立自由漂浮参考动力学（动量层）。

**独立性纪律**：本模块只从 accepted URDF 构造模型，不 import sim_05/sim_11 的任何
求解器代码，不读取它们的中间量。冻结锚点只在事后对拍，绝不用于反调参数。

公式
----
广义速度 u = [v_b; omega_b; qdot] in R^(6+n)。
每个连杆质心速度与角速度对 u 的雅可比：
    Jv_i = [ I3 , -skew(c_i - p_b) , dv_ci/dqdot ]
    Jw_i = [ 0  ,  I3              , dw_i /dqdot ]
对旋转关节 j（世界轴 a_j、轴上一点 o_j），若 j 是 i 的祖先：
    dv_ci/dqdot_j = a_j x (c_i - o_j)
    dw_i /dqdot_j = a_j
对移动关节 j：dv_ci/dqdot_j = a_j，dw_i/dqdot_j = 0。

系统动量（线动量 + 关于基座原点 p_b 的角动量）：
    A(x) u = [ sum m_i Jv_i ;  sum ( I_i^w Jw_i + m_i skew(c_i - p_b) Jv_i ) ]
自由漂浮、零初始动量、无外力矩 =>  A_b V_b + A_m qdot = 0
    V_b = -A_b^{-1} A_m qdot
"""
import numpy as np
from scipy.integrate import solve_ivp

from b601_kinematics import B601, REVOLUTE_ORDER, PRISMATIC_ORDER


def skew(v):
    return np.array([[0.0, -v[2], v[1]], [v[2], 0.0, -v[0]], [-v[1], v[0], 0.0]])


def min_jerk(t, T):
    """位置比例与其时间导数。"""
    if t <= 0:
        return 0.0, 0.0
    if t >= T:
        return 1.0, 0.0
    s = t / T
    return (10 * s ** 3 - 15 * s ** 4 + 6 * s ** 5,
            (30 * s ** 2 - 60 * s ** 3 + 30 * s ** 4) / T)


class ReferenceFreeFloating:
    """从 accepted URDF 构造的动量层自由漂浮参考模型。"""

    def __init__(self, lock_prismatic=True, base_bodies=None, T_SM=None):
        """base_bodies: [{'name','mass','com'(S 系),'I'(关于自身质心、S 系)}]。
        T_SM: 4x4，臂 base_link 帧在基座帧 S 中的位姿；None 表示臂即基座。"""
        self.arm = B601()                       # 内含 URDF SHA-256 fail-closed
        self.lock_prismatic = lock_prismatic
        self.dof = list(REVOLUTE_ORDER)
        if not lock_prismatic:
            self.dof += list(PRISMATIC_ORDER)
        self.n = len(self.dof)
        self.T_SM = np.eye(4) if T_SM is None else np.asarray(T_SM, float)
        self.base_bodies = list(base_bodies or [])
        # 有惯性的 URDF 连杆
        self.bodies = [k for k, v in self.arm.links.items() if "mass" in v]
        # 每个连杆的祖先关节集合（只计入活动自由度；锁死关节自动刚性随动）
        self.ancestors = {b: self._ancestors(b) for b in self.bodies}

    def _ancestors(self, link):
        out, cur = [], link
        parent_of = {j["child"]: (n, j["parent"]) for n, j in self.arm.joints.items()}
        while cur in parent_of:
            jn, par = parent_of[cur]
            if jn in self.dof:
                out.append(jn)
            cur = par
        return set(out)

    # ------------------------------------------------------------------
    def _world(self, q, R_b, p_b):
        """返回每个连杆的世界系质心、旋转，以及每个自由度关节的世界轴与轴上点。"""
        q6 = [q[self.dof.index(j)] if j in self.dof else 0.0 for j in REVOLUTE_ORDER]
        qp = [q[self.dof.index(j)] if j in self.dof else 0.0 for j in PRISMATIC_ORDER]
        T = self.arm.fk(q6=q6, qp=qp)           # base_link 系
        base_T = np.eye(4)
        base_T[:3, :3], base_T[:3, 3] = R_b, p_b
        base_T = base_T @ self.T_SM             # S 帧 -> 臂 base_link 帧
        Tw = {k: base_T @ v for k, v in T.items()}
        com, rot = {}, {}
        for b in self.bodies:
            rec = self.arm.links[b]
            com[b] = Tw[b][:3, :3] @ rec["com"] + Tw[b][:3, 3]
            rot[b] = Tw[b][:3, :3]
        axis, point = {}, {}
        for jn in self.dof:
            jr = self.arm.joints[jn]
            Rc = Tw[jr["child"]][:3, :3]
            axis[jn] = Rc @ jr["axis_child"]
            point[jn] = Tw[jr["child"]][:3, 3]
        return com, rot, axis, point

    def momentum_map(self, q, R_b, p_b):
        """A = [A_b | A_m] (6 x (6+n))。"""
        com, rot, axis, point = self._world(q, R_b, p_b)
        A = np.zeros((6, 6 + self.n))
        # 基座固连体（航天器本体、适配器等），随 S 帧刚性运动
        for bb in self.base_bodies:
            m = float(bb["mass"])
            c = R_b @ np.asarray(bb["com"], float) + p_b
            Iw = R_b @ np.asarray(bb["I"], float) @ R_b.T
            Jv = np.zeros((3, 6 + self.n))
            Jw = np.zeros((3, 6 + self.n))
            Jv[:, 0:3] = np.eye(3)
            Jv[:, 3:6] = -skew(c - p_b)
            Jw[:, 3:6] = np.eye(3)
            A[0:3, :] += m * Jv
            A[3:6, :] += Iw @ Jw + m * skew(c - p_b) @ Jv
        for b in self.bodies:
            rec = self.arm.links[b]
            m, c, Rl = rec["mass"], com[b], rot[b]
            Iw = Rl @ rec["I"] @ Rl.T
            Jv = np.zeros((3, 6 + self.n))
            Jw = np.zeros((3, 6 + self.n))
            Jv[:, 0:3] = np.eye(3)
            Jv[:, 3:6] = -skew(c - p_b)
            Jw[:, 3:6] = np.eye(3)
            for jn in self.ancestors[b]:
                k = 6 + self.dof.index(jn)
                a = axis[jn]
                if self.arm.joints[jn]["type"] == "prismatic":
                    Jv[:, k] = a
                else:
                    Jv[:, k] = np.cross(a, c - point[jn])
                    Jw[:, k] = a
            A[0:3, :] += m * Jv
            A[3:6, :] += Iw @ Jw + m * skew(c - p_b) @ Jv
        return A

    def base_velocity(self, q, qd, R_b, p_b):
        A = self.momentum_map(q, R_b, p_b)
        Vb = np.linalg.solve(A[:, :6], -A[:, 6:] @ qd)
        return Vb, A

    # ------------------------------------------------------------------
    def integrate(self, q_fun, qd_fun, t_end, n_out=601, rtol=1e-11, atol=1e-12):
        """状态 y = [p_b(3), R_b flattened(9)]；零总动量下积分基座位姿。"""
        def rhs(t, y):
            p_b = y[0:3]
            R_b = y[3:12].reshape(3, 3)
            q, qd = np.asarray(q_fun(t), float), np.asarray(qd_fun(t), float)
            Vb, _ = self.base_velocity(q, qd, R_b, p_b)
            v_b, w_b = Vb[:3], Vb[3:]
            dR = skew(w_b) @ R_b
            return np.concatenate([v_b, dR.ravel()])

        y0 = np.concatenate([np.zeros(3), np.eye(3).ravel()])
        ts = np.linspace(0.0, t_end, n_out)
        sol = solve_ivp(rhs, (0.0, t_end), y0, t_eval=ts, method="DOP853",
                        rtol=rtol, atol=atol, dense_output=False)
        if not sol.success:
            raise RuntimeError(f"integration failed: {sol.message}")

        dev, orth, mom_lin, mom_ang = [], [], [], []
        for i, t in enumerate(ts):
            R = sol.y[3:12, i].reshape(3, 3)
            # 正交性漂移
            orth.append(float(np.max(np.abs(R.T @ R - np.eye(3)))))
            # 重新正交化仅用于角度读数，不回写状态
            U, _, Vt = np.linalg.svd(R)
            Rn = U @ Vt
            c = (np.trace(Rn) - 1.0) / 2.0
            dev.append(float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0)))))
            q, qd = np.asarray(q_fun(t), float), np.asarray(qd_fun(t), float)
            Vb, A = self.base_velocity(q, qd, Rn, sol.y[0:3, i])
            u = np.concatenate([Vb, qd])
            h = A @ u
            mom_lin.append(float(np.linalg.norm(h[:3])))
            mom_ang.append(float(np.linalg.norm(h[3:])))
        R_hist = []
        for i in range(len(ts)):
            R = sol.y[3:12, i].reshape(3, 3)
            U, _, Vt = np.linalg.svd(R)
            R_hist.append(U @ Vt)
        return {"t": ts, "dev_angle_deg": np.array(dev), "R_b": R_hist,
                "peak_dev_deg": float(np.max(dev)),
                "max_orthonormality_drift": float(np.max(orth)),
                "max_residual_linear_momentum_Ns": float(np.max(mom_lin)),
                "max_residual_angular_momentum_Nms": float(np.max(mom_ang)),
                "p_b": sol.y[0:3, :]}

    # ------------------------------------------------------------------
    def generalized_jacobian(self, q, R_b=None, p_b=None, link="gripper_link"):
        """自由漂浮广义雅可比：末端速度对 qdot 的映射（含基座反作用）。"""
        R_b = np.eye(3) if R_b is None else R_b
        p_b = np.zeros(3) if p_b is None else p_b
        com, rot, axis, point = self._world(q, R_b, p_b)
        q6 = [q[self.dof.index(j)] if j in self.dof else 0.0 for j in REVOLUTE_ORDER]
        qp = [q[self.dof.index(j)] if j in self.dof else 0.0 for j in PRISMATIC_ORDER]
        base_T = np.eye(4)
        base_T[:3, :3], base_T[:3, 3] = R_b, p_b
        base_T = base_T @ self.T_SM             # 与 _world 一致：S 帧 -> 臂 base_link 帧
        Te = base_T @ self.arm.fk(q6=q6, qp=qp)[link]
        pe = Te[:3, 3]
        Jv = np.zeros((3, self.n))
        Jw = np.zeros((3, self.n))
        for jn in self.ancestors[link]:
            k = self.dof.index(jn)
            a = axis[jn]
            if self.arm.joints[jn]["type"] == "prismatic":
                Jv[:, k] = a
            else:
                Jv[:, k] = np.cross(a, pe - point[jn])
                Jw[:, k] = a
        A = self.momentum_map(q, R_b, p_b)
        Phi = -np.linalg.solve(A[:, :6], A[:, 6:])          # V_b = Phi qdot
        Jb_v = np.hstack([np.eye(3), -skew(pe - p_b)])
        Jb_w = np.hstack([np.zeros((3, 3)), np.eye(3)])
        return np.vstack([Jv + Jb_v @ Phi, Jw + Jb_w @ Phi]), pe

    def system_com(self, q, R_b=None, p_b=None):
        R_b = np.eye(3) if R_b is None else R_b
        p_b = np.zeros(3) if p_b is None else p_b
        com, _, _, _ = self._world(q, R_b, p_b)
        M = sum(self.arm.links[b]["mass"] for b in self.bodies)
        c = sum(self.arm.links[b]["mass"] * com[b] for b in self.bodies)
        for bb in self.base_bodies:
            m = float(bb["mass"])
            M += m
            c = c + m * (R_b @ np.asarray(bb["com"], float) + p_b)
        return c / M, M
