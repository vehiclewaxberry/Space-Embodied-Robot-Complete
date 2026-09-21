"""ffr_panel.py -- 浮动坐标法（FFR）柔性帆板：悬臂 Euler-Bernoulli 解析模态（假设模态法）。

模型定义（与报告 2.2 节一致）：
  帆板根部 F 固支于基座（S 系），本体三轴 (e1 弦向, e2 展向/deploy, e3 法向) 构成右手系，
  e1 = e2 x e3。挠度场 w(s,t) = sum_i phi_i(s) * eta_i(t)，方向 e3；
  质量按展向线密度 mu 的“质点切片”离散（Gauss-Legendre 节点），切片自身弦向/厚向
  转动惯量积分为一个基座固连的集中惯量块 J_rot（保证 eta=0 刚化极限与 SSOT 平板
  惯量精确闭合，mass_split_check 不变式），模态转动惯量（Rayleigh 修正）忽略 ——
  标准 Euler-Bernoulli FFR，量级 (t/L)^2/12 ~ 7.5e-5。

生成量（全部由参数卡 + SSOT 运行时生成，禁止手抄）：
  - 模态形函数 phi_i(s)（质量归一：∫ mu phi_i phi_j ds = delta_ij）
  - 模态刚度 K = ∫ EI phi_i'' phi_j'' ds（精确 EB 模态下 = diag(omega_i^2)）
  - 模态阻尼 D = diag(2 zeta omega_i)
  - 平动/转动模态动量系数 B_t_i = ∫ mu phi_i ds（方向 e3），
    B_r_i = ∫ mu s phi_i ds（对根部、方向 e1）

纯 numpy/scipy，确定性。"""
import numpy as np
from scipy.optimize import brentq


def cantilever_beta_roots(n_modes):
    """悬臂梁特征方程 cosh(x)cos(x) + 1 = 0 的前 n 个根（beta_i * L）。"""
    roots = []
    f = lambda x: np.cosh(x) * np.cos(x) + 1.0  # noqa: E731
    for i in range(1, n_modes + 1):
        lo = (i - 0.5) * np.pi - 1.0
        hi = (i - 0.5) * np.pi + 1.0
        # 根落在 (i-1/2)pi 附近；扩到必含变号的区间
        while f(lo) * f(hi) > 0:
            lo -= 0.2
            hi += 0.2
        roots.append(brentq(f, lo, hi, xtol=1e-15, rtol=8.9e-16))
    return np.asarray(roots)


def _phi_raw(beta, sigma, s):
    """未归一悬臂模态形函数及其一二阶导（对 s）。beta 为量纲化波数 beta_i（1/m）。"""
    bs = beta * s
    phi = np.cosh(bs) - np.cos(bs) - sigma * (np.sinh(bs) - np.sin(bs))
    dphi = beta * (np.sinh(bs) + np.sin(bs) - sigma * (np.cosh(bs) - np.cos(bs)))
    ddphi = beta ** 2 * (np.cosh(bs) + np.cos(bs) - sigma * (np.sinh(bs) + np.sin(bs)))
    return phi, dphi, ddphi


class FFRPanel:
    """单侧 FFR 帆板。root_S/deploy/normal 来自 frame_tree SSOT；几何/质量/EI 来自
    flexible_appendage SSOT。n_modes=0 表示刚化（无模态自由度，仅刚体贡献）。"""

    def __init__(self, name, root_S, deploy_S, normal_S, L, mu, chord_b, thick_t,
                 EI, n_modes, n_quad=24, zeta=0.005):
        self.name = name
        self.root = np.asarray(root_S, float)
        self.e2 = np.asarray(deploy_S, float) / np.linalg.norm(deploy_S)
        self.e3 = np.asarray(normal_S, float) / np.linalg.norm(normal_S)
        self.e1 = np.cross(self.e2, self.e3)
        self.L, self.mu, self.b, self.t = float(L), float(mu), float(chord_b), float(thick_t)
        self.EI = float(EI)
        self.m = self.mu * self.L
        self.n_modes = int(n_modes)
        self.zeta = float(zeta)

        # Gauss-Legendre 质量积分节点（多项式精确阶 2*n_quad-1；模态积分谱收敛）
        gp, gw = np.polynomial.legendre.leggauss(int(n_quad))
        self.s = 0.5 * (gp + 1.0) * self.L              # (n,) 展向站位
        self.wq = 0.5 * gw * self.L                     # (n,) 权
        self.m_nodes = self.mu * self.wq                # (n,) 节点质量
        self.x0 = self.root[None, :] + self.s[:, None] * self.e2[None, :]  # (n,3) 未变形位形

        # 切片弦向/厚向自转惯量集中块（S 轴系，常量；e1/e2/e3 为 ±S 轴 -> 对角不变）
        Rp = np.column_stack([self.e1, self.e2, self.e3])
        j_local = self.m / 12.0 * np.diag([self.t ** 2, self.b ** 2 + self.t ** 2, self.b ** 2])
        self.J_rot_S = Rp @ j_local @ Rp.T

        if self.n_modes == 0:
            self.Phi = np.zeros((len(self.s), 0))
            self.phi_tip = np.zeros(0)
            self.K = np.zeros((0, 0))
            self.D = np.zeros((0, 0))
            self.omega = np.zeros(0)
            self.B_t = np.zeros(0)
            self.B_r = np.zeros(0)
            self.betaL = np.zeros(0)
            return

        # ---- 解析悬臂模态 + 质量归一 ------------------------------------------
        betaL = cantilever_beta_roots(self.n_modes)
        beta = betaL / self.L
        sigma = (np.cosh(betaL) + np.cos(betaL)) / (np.sinh(betaL) + np.sin(betaL))
        Phi = np.zeros((len(self.s), self.n_modes))
        dPhi = np.zeros_like(Phi)
        ddPhi = np.zeros_like(Phi)
        for i in range(self.n_modes):
            Phi[:, i], dPhi[:, i], ddPhi[:, i] = _phi_raw(beta[i], sigma[i], self.s)
        # 质量归一：∫ mu phi_i^2 ds = 1
        norm = np.sqrt(np.einsum("k,ki,ki->i", self.m_nodes, Phi, Phi))
        Phi /= norm[None, :]
        dPhi /= norm[None, :]
        ddPhi /= norm[None, :]
        # 正交性数值残差（应为机器精度量级；tests 断言）
        Mmod = np.einsum("k,ki,kj->ij", self.m_nodes, Phi, Phi)
        self.mode_orthogonality_residual = float(np.max(np.abs(Mmod - np.eye(self.n_modes))))

        self.betaL = betaL
        self.Phi = Phi                                   # (n_quad, m)
        tip_phi, _, _ = _phi_raw(beta, sigma, np.full(self.n_modes, self.L))
        self.phi_tip = tip_phi / norm                    # 端部形函数值（挠度输出用）
        # 模态刚度：∫ EI phi'' phi'' ds（对称化；精确 EB 模态下 ~diag(omega^2)）
        K = self.EI * np.einsum("k,ki,kj->ij", self.wq, ddPhi, ddPhi)
        self.K = 0.5 * (K + K.T)
        self.omega = np.sqrt(np.clip(np.diag(self.K), 0.0, None))
        self.f_modes_hz = self.omega / (2.0 * np.pi)
        self.D = np.diag(2.0 * self.zeta * self.omega)
        # 模态动量系数（对根部）：平动沿 e3；转动沿 e1（(s e2) x (phi e3) = s phi e1）
        self.B_t = np.einsum("k,ki->i", self.m_nodes, Phi)
        self.B_r = np.einsum("k,k,ki->i", self.m_nodes, self.s, Phi)

    # ---- 运动学 ---------------------------------------------------------------
    def node_positions(self, eta):
        """节点 S 系位置 (n,3)：x = root + s*e2 + (Phi @ eta)*e3。"""
        if self.n_modes == 0:
            return self.x0
        return self.x0 + (self.Phi @ np.asarray(eta, float))[:, None] * self.e3[None, :]

    def node_rel_velocities(self, etad):
        """节点相对基座速度 (n,3)（S 系分量）：v_rel = (Phi @ etad)*e3。"""
        if self.n_modes == 0:
            return np.zeros_like(self.x0)
        return (self.Phi @ np.asarray(etad, float))[:, None] * self.e3[None, :]

    def tip_deflection(self, eta):
        """端部法向挠度 [m]。"""
        if self.n_modes == 0:
            return 0.0
        return float(self.phi_tip @ np.asarray(eta, float))

    def strain_energy(self, eta):
        if self.n_modes == 0:
            return 0.0
        eta = np.asarray(eta, float)
        return float(0.5 * eta @ (self.K @ eta))

    def modal_energy(self, eta, etad):
        """模态机械能：1/2 etad^2 + 应变能（质量归一 -> 模态质量为 1）。"""
        if self.n_modes == 0:
            return 0.0
        etad = np.asarray(etad, float)
        return float(0.5 * etad @ etad) + self.strain_energy(eta)

    def rigid_inertia_check(self):
        """刚化极限自检：切片质点 + 集中惯量的合成惯量（对帆板自身质心） vs SSOT 平板公式。"""
        c = self.x0.mean(axis=0) * 0  # 计算用：直接对质心求
        c = np.einsum("k,ki->i", self.m_nodes, self.x0) / self.m
        d = self.x0 - c[None, :]
        I = self.J_rot_S.copy()
        for k in range(len(self.s)):
            dk = d[k]
            I += self.m_nodes[k] * (np.dot(dk, dk) * np.eye(3) - np.outer(dk, dk))
        return c, I


if __name__ == "__main__":
    from config_loader import load_model_config
    cfg = load_model_config()
    p = cfg["panel"]
    pf = cfg["panels_frames"]["L"]
    pan = FFRPanel("L", pf["root_S"], pf["deploy_S"], pf["normal_S"],
                   p["span_L_m"], p["mu_kg_per_m"], p["chord_b_m"], p["thickness_t_m"],
                   p["EI_cases_Nm2"]["nominal"], n_modes=3)
    print("betaL:", pan.betaL, " (SSOT beta1:", p["beta1_ssot"], ")")
    print("f_modes [Hz]:", pan.f_modes_hz)
    print("orthogonality residual:", pan.mode_orthogonality_residual)
    print("K offdiag max:", float(np.max(np.abs(pan.K - np.diag(np.diag(pan.K))))))
    print("B_t:", pan.B_t, " B_r:", pan.B_r)
    ccheck, Icheck = pan.rigid_inertia_check()
    Iplate = np.diag([p["I_own_com_kgm2"]["Ixx"], p["I_own_com_kgm2"]["Iyy"], p["I_own_com_kgm2"]["Izz"]])
    print("rigid inertia err vs SSOT plate:", float(np.max(np.abs(Icheck - Iplate))))
