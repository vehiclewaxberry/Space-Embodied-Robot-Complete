"""Vectorized equal-output fast path for the frozen sim_11 CoupledModel.

Physics SSOT remains 30_simulation/sim_11_coupled_dynamics/src/coupled_dynamics.py.
This module re-implements ONLY the assembly of M(q), A(q), the bias vector
c(q,u), and the prescribed-theta_ddot acceleration solve, using batched numpy
so the solver-grade CTRL-01 energy ledger becomes affordable. It introduces
no new physics and no new parameters.

Fail-closed contract: `cross_check_against_ssot` compares M, A, c, udot and
tau against the frozen CoupledModel on random states. run_experiments.py runs
it before the matrix and refuses to run on mismatch; run_gates.py refuses to
adjudicate without a recorded PASS.
"""
from __future__ import annotations

import numpy as np

from repo_imports import CoupledModel


def _skew(v: np.ndarray) -> np.ndarray:
    return np.array(
        [
            [0.0, -v[2], v[1]],
            [v[2], 0.0, -v[0]],
            [-v[1], v[0], 0.0],
        ]
    )


class FastPlant:
    """Drop-in provider of the CoupledModel methods used by CTRL-01."""

    def __init__(self, model: CoupledModel):
        if model.target is not None:
            raise ValueError("FastPlant supports the pre-capture free arm only")
        self.slow = model
        self.arm = model.arm
        self.panels = model.panels
        self.n_modes = model.n_modes
        self.nu = model.nu
        self.i_b = model.i_b
        self.i_a = model.i_a
        self.i_e = model.i_e
        self.i_be = model.i_be
        self.K_eta = model.K_eta
        self.D_eta = model.D_eta

        # ---- fixed base-attached bodies pre-combined (exact M/A/bias) --------
        m_F = 0.0
        S_F = np.zeros(3)
        I_F = np.zeros((3, 3))
        for _, mass, c, inertia in model.fixed_bodies:
            m_F += mass
            S_F = S_F + mass * c
            I_F = I_F + inertia + mass * (
                float(c @ c) * np.eye(3) - np.outer(c, c)
            )
        self.m_F = float(m_F)
        self.S_F = S_F
        self.I_F = I_F

        # ---- panel constant moments (same einsum kernels as sim_11) ----------
        self.pan_const = []
        for pan in model.panels:
            mk = pan.m_nodes
            x0 = pan.x0
            const = {
                "pan": pan,
                "m_tot": float(mk.sum()),
                "S0": np.einsum("k,ki->i", mk, x0),
                "C0m": np.einsum("k,ki,kj->ij", mk, x0, x0),
                "C1": np.einsum("k,ki,kj->ij", mk, pan.Phi, x0)
                if pan.n_modes
                else np.zeros((0, 3)),
                "G": np.einsum("k,ki,kj->ij", mk, pan.Phi, pan.Phi)
                if pan.n_modes
                else np.zeros((0, 0)),
                "B_t": np.einsum("k,ki->i", mk, pan.Phi)
                if pan.n_modes
                else np.zeros(0),
                "e3": pan.e3,
            }
            if pan.n_modes:
                const["Mrot0"] = np.cross(const["C1"], pan.e3[None, :]).T
            else:
                const["Mrot0"] = np.zeros((3, 0))
            self.pan_const.append(const)

        self._cache_key = None
        self._cache_geo = None

    # ------------------------------------------------------------------ FK+M+A
    def geometry(self, th, eta):
        th = np.asarray(th, float)
        eta = np.asarray(eta, float)
        key = (th.tobytes(), eta.tobytes())
        if self._cache_key == key:
            return self._cache_geo
        m_md = self.n_modes
        nu = self.nu
        f = self.arm.fk(th)
        axes = np.asarray(f["joint_axes"], float)          # (6,3)
        origins = np.asarray(f["joint_origins"], float)    # (6,3)

        # ---- arm link batch data ------------------------------------------------
        masses = np.empty(6)
        coms = np.empty((6, 3))
        inertias = np.empty((6, 3, 3))
        for k, name in enumerate(
            ("link1", "link2", "link3", "link4", "link5", "link6")
        ):
            Tk = f["T"][name]
            Rk, pk = Tk[:3, :3], Tk[:3, 3]
            body = self.arm.body[name]
            masses[k] = body["mass"]
            coms[k] = Rk @ body["cg"] + pk
            inertias[k] = Rk @ body["I"] @ Rk.T
        # mask[L, i] = joint i moves link L (0-based: i <= L)
        mask = np.tril(np.ones((6, 6)))
        diff = coms[:, None, :] - origins[None, :, :]          # (L,i,3)
        Jv = np.cross(axes[None, :, :], diff) * mask[:, :, None]   # (L,3->axis?) fix below
        # np.cross over last axis gives (L,i,3); reorder to (L,3,6)
        Jv = np.transpose(Jv, (0, 2, 1))
        Jw = np.transpose(
            np.broadcast_to(axes[None, :, :], (6, 6, 3)) * mask[:, :, None],
            (0, 2, 1),
        )

        M = np.zeros((nu, nu))
        A = np.zeros((6, nu))

        # ---- fixed bodies (pre-combined, exact) --------------------------------
        SkF = _skew(self.S_F)
        M[0:3, 0:3] += self.m_F * np.eye(3)
        M[0:3, 3:6] += -SkF
        M[3:6, 0:3] += SkF
        M[3:6, 3:6] += self.I_F
        A[0:3, 0:3] += self.m_F * np.eye(3)
        A[0:3, 3:6] += -SkF
        A[3:6, 0:3] += SkF
        A[3:6, 3:6] += self.I_F

        # ---- arm links (batched) ----------------------------------------------
        m_sum = float(masses.sum())
        S_a = np.einsum("l,li->i", masses, coms)
        SkA = _skew(S_a)
        I_a_origin = np.einsum("lij->ij", inertias) + (
            np.einsum("l,l->", masses, np.einsum("li,li->l", coms, coms))
            * np.eye(3)
            - np.einsum("l,li,lj->ij", masses, coms, coms)
        )
        mJv = masses[:, None, None] * Jv                       # (L,3,6)
        sum_mJv = np.einsum("lij->ij", mJv)                    # (3,6)
        cxJv = np.cross(
            coms[:, None, :], np.transpose(mJv, (0, 2, 1))
        )                                                      # (L,6,3)
        sum_c_x_mJv = np.einsum("lji->ij", cxJv)               # (3,6)
        IJw = np.einsum("lik,lkj->lij", inertias, Jw)          # (L,3,6)
        sum_IJw = np.einsum("lij->ij", IJw)
        M_aa = np.einsum("lki,lkj->ij", Jv, mJv) + np.einsum(
            "lki,lkj->ij", Jw, IJw
        )
        M[0:3, 0:3] += m_sum * np.eye(3)
        M[0:3, 3:6] += -SkA
        M[3:6, 0:3] += SkA
        M[3:6, 3:6] += I_a_origin
        M[0:3, 6:12] += sum_mJv
        M[6:12, 0:3] += sum_mJv.T
        M36 = sum_c_x_mJv + sum_IJw
        M[3:6, 6:12] += M36
        M[6:12, 3:6] += M36.T
        M[6:12, 6:12] += M_aa
        A[0:3, 0:3] += m_sum * np.eye(3)
        A[0:3, 3:6] += -SkA
        A[3:6, 0:3] += SkA
        A[3:6, 3:6] += I_a_origin
        A[0:3, 6:12] += sum_mJv
        A[3:6, 6:12] += M36

        # ---- panels (closed-form moments) --------------------------------------
        etaL = eta[:m_md]
        etaR = eta[m_md:]
        pans = []
        for ip, const in enumerate(self.pan_const):
            et = etaL if ip == 0 else etaR
            e3 = const["e3"]
            cols = 12 + ip * m_md + np.arange(m_md)
            Sx_vec = const["S0"] + (
                float(const["B_t"] @ et) * e3 if m_md else 0.0
            )
            if m_md:
                C1eta = const["C1"].T @ et                      # sum m x0 phi.eta
                quad = float(et @ (const["G"] @ et))
                J2 = (
                    const["C0m"]
                    + np.outer(C1eta, e3)
                    + np.outer(e3, C1eta)
                    + quad * np.outer(e3, e3)
                )
            else:
                J2 = const["C0m"]
            Sk = _skew(Sx_vec)
            St = np.trace(J2) * np.eye(3) - J2
            M[0:3, 0:3] += const["m_tot"] * np.eye(3)
            M[0:3, 3:6] += -Sk
            M[3:6, 0:3] += Sk
            M[3:6, 3:6] += St
            A[0:3, 0:3] += const["m_tot"] * np.eye(3)
            A[0:3, 3:6] += -Sk
            A[3:6, 0:3] += Sk
            A[3:6, 3:6] += St
            if m_md:
                outer_e3B = np.outer(e3, const["B_t"])
                M[0:3, cols] += outer_e3B
                M[np.ix_(cols, np.arange(0, 3))] += outer_e3B.T
                M[3:6, cols] += const["Mrot0"]
                M[np.ix_(cols, np.arange(3, 6))] += const["Mrot0"].T
                M[np.ix_(cols, cols)] += const["G"]
                A[0:3, cols] += outer_e3B
                A[3:6, cols] += const["Mrot0"]
            pans.append(
                {"const": const, "eta": et, "cols": cols, "J2": J2, "Sx": Sx_vec}
            )

        geo = {
            "f": f,
            "M": M,
            "A": A,
            "th": th,
            "axes": axes,
            "origins": origins,
            "arm_masses": masses,
            "arm_coms": coms,
            "arm_inertias": inertias,
            "arm_Jv": Jv,
            "arm_Jw": Jw,
            "pans": pans,
        }
        self._cache_key = key
        self._cache_geo = geo
        return geo

    # ------------------------------------------------------------------ bias
    def bias_from_geometry(self, geo, u):
        u = np.asarray(u, float)
        m_md = self.n_modes
        vb, wb = u[0:3], u[3:6]
        thd = u[6:12]
        etad = u[12:]
        wxv = np.cross(wb, vb)
        c_vec = np.zeros(self.nu)

        # ---- fixed bodies (closed form) ---------------------------------------
        c_vec[0:3] += self.m_F * wxv + np.cross(wb, np.cross(wb, self.S_F))
        c_vec[3:6] += np.cross(self.S_F, wxv) + np.cross(wb, self.I_F @ wb)

        # ---- arm links (batched recursion) ------------------------------------
        axes = geo["axes"]
        origins = geo["origins"]
        masses = geo["arm_masses"]
        coms = geo["arm_coms"]
        inertias = geo["arm_inertias"]
        Jv = geo["arm_Jv"]
        Jw = geo["arm_Jw"]

        aw = axes * thd[:, None]                       # (6,3) a_i * thd_i
        cum = np.cumsum(aw, axis=0)
        omega_prev = np.vstack([np.zeros(3), cum[:-1]])  # (6,3) before joint i
        adot = np.cross(omega_prev, axes)              # (6,3)
        # odot_i = sum_{j<i} thd_j a_j x (o_i - o_j)
        rel = origins[:, None, :] - origins[None, :, :]      # (i,j,3)
        cr = np.cross(aw[None, :, :], rel)                    # (i,j,3)
        strict = np.tril(np.ones((6, 6)), k=-1)
        odot = np.einsum("ij,ijk->ik", strict, cr)            # (6,3)

        mask = np.tril(np.ones((6, 6)))                       # (L,i) i<=L
        w_rel = mask @ aw                                     # (6,3)
        alpha_rel = mask @ (adot * thd[:, None])              # (6,3)
        cdot = np.einsum("lij,j->li", Jv, thd)                # (6,3)
        dca = coms[:, None, :] - origins[None, :, :]          # (L,i,3)
        term1 = np.cross(adot[None, :, :], dca)               # (L,i,3)
        term2 = np.cross(
            np.broadcast_to(axes[None, :, :], (6, 6, 3)),
            cdot[:, None, :] - odot[None, :, :],
        )
        a_rel = np.einsum(
            "li,lik->lk", mask * thd[None, :], term1 + term2
        )                                                     # (6,3)
        wbb = wb[None, :]
        a_bias = (
            wxv[None, :]
            + np.cross(wbb, np.cross(wbb, coms))
            + 2.0 * np.cross(wbb, cdot)
            + a_rel
        )
        w_S = wb[None, :] + w_rel
        Iw_S = np.einsum("lij,lj->li", inertias, w_S)
        hd = (
            np.einsum("lij,lj->li", inertias, alpha_rel)
            + np.cross(w_rel, Iw_S)
            - np.einsum(
                "lij,lj->li", inertias, np.cross(w_rel, w_S)
            )
            + np.cross(wbb, Iw_S)
        )
        ma = masses[:, None] * a_bias
        c_vec[0:3] += np.einsum("li->i", ma)
        c_vec[3:6] += np.einsum("li->i", np.cross(coms, ma) + hd)
        c_vec[6:12] += np.einsum("lki,lk->i", Jv, ma) + np.einsum(
            "lki,lk->i", Jw, hd
        )

        # ---- panels (closed form) ---------------------------------------------
        etadL = etad[:m_md]
        etadR = etad[m_md:]
        for ip, pd in enumerate(geo["pans"]):
            const = pd["const"]
            e3 = const["e3"]
            etd = etadL if ip == 0 else etadR
            et = pd["eta"]
            J2 = pd["J2"]
            Sx_vec = pd["Sx"]
            Bt_etad = float(const["B_t"] @ etd) if m_md else 0.0
            c_vec[0:3] += (
                const["m_tot"] * wxv
                + np.cross(wb, np.cross(wb, Sx_vec))
                + 2.0 * Bt_etad * np.cross(wb, e3)
            )
            if m_md:
                p_vec = const["C1"].T @ etd + float(
                    etd @ (const["G"] @ et)
                ) * e3
            else:
                p_vec = np.zeros(3)
            c_vec[3:6] += (
                np.cross(Sx_vec, wxv)
                - np.cross(wb, J2 @ wb)
                + 2.0 * np.cross(p_vec, np.cross(wb, e3))
            )
            if m_md:
                q_mat = const["C1"] + np.outer(
                    const["G"] @ et, e3
                )                                             # (m,3)
                c_vec[pd["cols"]] += (
                    const["B_t"] * float(wxv @ e3)
                    + float(wb @ e3) * (q_mat @ wb)
                    - float(wb @ wb) * (q_mat @ e3)
                )
        return c_vec

    # ---------------------------------------------------------------- dynamics
    def accelerations(self, th, eta, u, thdd, geo=None, Q_ext=None):
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
        udot[self.i_a] = np.asarray(thdd, float)
        tau = M[self.i_a] @ udot + c[self.i_a] - Q[self.i_a]
        return udot, tau

    # --------------------------------------------------------------- wrappers
    def momentum_matrix(self, th, eta):
        return self.geometry(th, eta)["A"]

    def mass_matrix(self, th, eta):
        return self.geometry(th, eta)["M"]

    def generalized_jacobian(self, th, eta):
        f = self.arm.fk(np.asarray(th, float))
        J_m = self.arm.jacobian(th, fk_out=f)
        rE = f["T_E"][:3, 3]
        J_b = np.eye(6)
        J_b[:3, 3:] = -_skew(rE)
        A = self.momentum_matrix(th, eta)
        J_full = np.zeros((6, 6 + 2 * self.n_modes))
        J_full[:, :6] = J_m
        return J_full - J_b @ np.linalg.solve(A[:, :6], A[:, 6:])

    def kinetic_energy(self, th, eta, u):
        u = np.asarray(u, float)
        return float(0.5 * u @ (self.geometry(th, eta)["M"] @ u))

    def strain_energy(self, eta):
        return self.slow.strain_energy(eta)

    def momentum_inertial(self, r_b, quat, th, eta, u):
        """Deliberately delegated to the frozen sim_11 independent path."""
        return self.slow.momentum_inertial(r_b, quat, th, eta, u)


def cross_check_against_ssot(
    model: CoupledModel,
    fast: FastPlant | None = None,
    n_samples: int = 12,
    seed: int = 20260719,
    tolerance: float = 1e-9,
) -> dict:
    """Machine equivalence proof of the fast path against the frozen SSOT.

    Random joint states span the URDF limits and beyond; modal states span the
    observed closed-loop amplitudes with margin. Fail-closed: any field above
    `tolerance` (max-abs, scale-normalized) marks FAIL.
    """
    fast = fast or FastPlant(model)
    rng = np.random.default_rng(seed)
    m2 = 2 * model.n_modes
    worst = {"M": 0.0, "A": 0.0, "bias": 0.0, "udot": 0.0, "tau": 0.0}
    for _ in range(n_samples):
        th = rng.uniform(-2.5, 2.5, 6)
        eta = rng.uniform(-5e-3, 5e-3, m2)
        u = np.concatenate(
            [
                rng.uniform(-0.2, 0.2, 3),
                rng.uniform(-0.3, 0.3, 3),
                rng.uniform(-1.0, 1.0, 6),
                rng.uniform(-0.05, 0.05, m2),
            ]
        )
        thdd = rng.uniform(-5.0, 5.0, 6)
        geo_s = model.geometry(th, eta)
        geo_f = fast.geometry(th, eta)
        scale_M = max(float(np.max(np.abs(geo_s["M"]))), 1.0)
        scale_A = max(float(np.max(np.abs(geo_s["A"]))), 1.0)
        worst["M"] = max(
            worst["M"],
            float(np.max(np.abs(geo_s["M"] - geo_f["M"]))) / scale_M,
        )
        worst["A"] = max(
            worst["A"],
            float(np.max(np.abs(geo_s["A"] - geo_f["A"]))) / scale_A,
        )
        c_s = model.bias_from_geometry(geo_s, u)
        c_f = fast.bias_from_geometry(geo_f, u)
        scale_c = max(float(np.max(np.abs(c_s))), 1.0)
        worst["bias"] = max(
            worst["bias"], float(np.max(np.abs(c_s - c_f))) / scale_c
        )
        udot_s, tau_s = model.accelerations(th, eta, u, thdd, geo=geo_s)
        udot_f, tau_f = fast.accelerations(th, eta, u, thdd, geo=geo_f)
        scale_ud = max(float(np.max(np.abs(udot_s))), 1.0)
        scale_tau = max(float(np.max(np.abs(tau_s))), 1.0)
        worst["udot"] = max(
            worst["udot"], float(np.max(np.abs(udot_s - udot_f))) / scale_ud
        )
        worst["tau"] = max(
            worst["tau"], float(np.max(np.abs(tau_s - tau_f))) / scale_tau
        )
    overall = max(worst.values())
    return {
        "status": "PASS" if overall <= tolerance else "FAIL",
        "tolerance": tolerance,
        "n_samples": n_samples,
        "seed": seed,
        "worst_normalized_abs_error": worst,
        "overall_worst": overall,
        "ssot": "30_simulation/sim_11_coupled_dynamics/src/coupled_dynamics.py",
    }
