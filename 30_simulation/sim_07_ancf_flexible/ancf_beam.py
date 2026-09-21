"""Planar gradient-deficient ANCF beam (Berzeri-Shabana) — importable module.

Extracted from ancf_beam_benchmark.py (benchmarks 5/5 PASS, Gate B item 1) so that
sim_07a task-response and later phases can reuse the validated element. Numerics of
shape(), element_matrices() and the original Beam methods are kept IDENTICAL to the
benchmarked version (same construction path, incl. the K8 * ei/EI rescale).

Element: 2-node planar ANCF beam, nodal coords e_n = [rx, ry, rx', ry'] (cubic Hermite
interpolation of the position field r(x)). Berzeri-Shabana simplified elastic model:
    U = 1/2 int EA*eps^2 dx + 1/2 int EI * r''.r'' dx,   eps = 1/2(r'.r' - 1)
Bending part is LINEAR in e (constant K_b); axial part nonlinear. Both vanish exactly
for arbitrary large rigid-body motion.

Local axes convention: beam axis = local x (maps to the panel's +Y_F), transverse =
local y (maps to the panel's bending direction +Z_S in sim_07a).

Additions over the benchmark version (phase A needs):
  - set_rayleigh_damping(): constant C = alpha*M + beta*K_t, zeta matched at two freqs
  - initial_velocity_field(): project a prescribed velocity field v0(y) onto nodal
    velocity DOFs (position rate + slope rate by central difference), clamped root zeroed
  - root_moment(): M_root = EI * d2(transverse)/dx^2 at x=0 (small-deflection curvature)
  - tip_transverse(): transverse tip displacement

Parameters from 20_engineering/config/geometry/flexible_appendage_v1.yaml (equivalent solar-panel beam:
L=0.2 m, mu=1.742 kg/m, EI envelope 0.7/1.0/1.3 Hz). Deterministic, numpy/scipy only."""
import os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "..", "..", "config", "geometry", "flexible_appendage_v1.yaml")


def load_params():
    try:
        import yaml
        d = yaml.safe_load(open(CFG, encoding="utf-8"))
        g, m, s = d["geometry"], d["mass"], d["stiffness"]
        cases = {k: v["EI_Nm2"] for k, v in s["cases"].items()}
        return float(g["span_L_m"]), float(m["mu_kg_per_m"]), cases, float(s["beta1"])
    except Exception as ex:                       # yaml missing -> frozen fallback (same SSOT values)
        print(f"[warn] yaml load failed ({ex}); using frozen fallback values")
        return 0.200, 1.7419665, {"flexible_low": 4.3630e-3, "nominal": 8.9042e-3,
                                  "flexible_high": 1.5047e-2}, 1.87510407


L_TOT, MU, EI_CASES, BETA1 = load_params()
EI = EI_CASES["nominal"]
I_SEC = 0.227 * 0.006**3 / 12.0                  # b t^3/12 (equivalent section)
EA = EI / I_SEC * (0.227 * 0.006)                # E_eq * A  (consistent equivalent beam)

# ---- ANCF element machinery ----
GP, GW = np.polynomial.legendre.leggauss(6)      # Gauss points on [-1,1]


def shape(xi, l):
    """Hermite S and derivatives wrt physical x at xi in [0,1]."""
    S = np.array([1 - 3*xi**2 + 2*xi**3, l*(xi - 2*xi**2 + xi**3),
                  3*xi**2 - 2*xi**3, l*(-xi**2 + xi**3)])
    Sx = np.array([(-6*xi + 6*xi**2), l*(1 - 4*xi + 3*xi**2),
                   (6*xi - 6*xi**2), l*(-2*xi + 3*xi**2)]) / l
    Sxx = np.array([(-6 + 12*xi), l*(-4 + 6*xi), (6 - 12*xi), l*(-2 + 6*xi)]) / l**2
    return S, Sx, Sxx


def element_matrices(l):
    """Constant element mass matrix (8x8) and bending stiffness (8x8)."""
    Me = np.zeros((4, 4)); Kb = np.zeros((4, 4))
    for gp, gw in zip(GP, GW):
        xi = 0.5 * (gp + 1); w = 0.5 * gw * l
        S, Sx, Sxx = shape(xi, l)
        Me += w * np.outer(S, S)
        Kb += w * np.outer(Sxx, Sxx)
    M8 = np.zeros((8, 8)); K8 = np.zeros((8, 8))
    for a in range(4):
        for b in range(4):
            for d in range(2):                    # x and y components decouple
                M8[2*a + d, 2*b + d] = MU * Me[a, b]
                K8[2*a + d, 2*b + d] = EI * Kb[a, b]
    return M8, K8


class Beam:
    """Cantilever along +x, clamped at node 0 (r=(0,0), r'=(1,0)). Vectorized internals."""
    def __init__(self, n_el, ei=EI, ea=EA):
        self.n_el, self.l = n_el, L_TOT / n_el
        self.ei, self.ea = ei, ea
        self.n_node = n_el + 1; self.ndof = 4 * self.n_node
        M8, K8 = element_matrices(self.l)
        self.K8 = K8 * (ei / EI)                  # rescale if ei differs
        self.M = np.zeros((self.ndof, self.ndof)); self.Kb = np.zeros_like(self.M)
        for e in range(n_el):
            idx = np.arange(4*e, 4*e + 8)
            self.M[np.ix_(idx, idx)] += M8
            self.Kb[np.ix_(idx, idx)] += self.K8
        self.e0 = np.zeros(self.ndof)             # straight reference
        for n in range(self.n_node):
            self.e0[4*n:4*n+4] = [n * self.l, 0.0, 1.0, 0.0]
        self.fixed = np.array([0, 1, 2, 3]); self.free = np.arange(4, self.ndof)
        # precomputed Gauss data (shared by all elements: equal length)
        xis = 0.5 * (GP + 1); self.wq = 0.5 * GW * self.l          # (6,)
        self.SxG = np.stack([shape(x, self.l)[1] for x in xis])    # (6,4)
        # element dof index map: (n_el, 8) -> reshaped nodal (n_el, 4, 2)
        self.eidx = np.stack([np.arange(4*e, 4*e + 8) for e in range(n_el)])
        self._eidx_flat = self.eidx.reshape(-1)    # for fast bincount assembly
        self._SxGT = np.ascontiguousarray(self.SxG.T)              # (4,6)
        self._ea_wq = self.ea * self.wq                            # (6,)
        self.C = None                              # optional constant damping matrix
        self.rayleigh = None

    def _rp(self, e):
        """r'(x) at all Gauss points: (n_el, 6, 2)."""
        ee = e[self.eidx].reshape(self.n_el, 4, 2)
        return np.matmul(self.SxG, ee)             # (6,4)@(n_el,4,2) -> (n_el,6,2)

    def q_axial(self, e):
        rp = self._rp(e)                                            # (n_el,6,2)
        eps = 0.5 * ((rp * rp).sum(axis=2) - 1.0)                   # (n_el,6)
        coef = self._ea_wq * eps                                    # (n_el,6)
        dQ = np.matmul(self._SxGT, coef[:, :, None] * rp)           # (n_el,4,2)
        return np.bincount(self._eidx_flat, weights=dQ.reshape(-1),
                           minlength=self.ndof)

    def strain_energy(self, e):
        rp = self._rp(e)
        eps = 0.5 * ((rp * rp).sum(axis=2) - 1.0)
        Ua = float(np.sum(self.wq[None, :] * 0.5 * self.ea * eps**2))
        return Ua + 0.5 * e @ (self.Kb @ e)

    def q_int(self, e):
        return self.Kb @ e + self.q_axial(e)

    def static_tip_load(self, F_tip, tol=1e-12, itmax=40):
        e = self.e0.copy()
        F = np.zeros(self.ndof); F[4*(self.n_node - 1) + 1] = F_tip   # +y at tip
        fr = self.free
        for _ in range(itmax):
            R = self.q_int(e) - F
            if np.linalg.norm(R[fr]) < tol: break
            J = self.num_jacobian(e)
            de = np.linalg.solve(J[np.ix_(fr, fr)], -R[fr])
            e[fr] += de
        return e, np.linalg.norm((self.q_int(e) - F)[fr])

    def num_jacobian(self, e, h=1e-7):
        J = np.zeros((self.ndof, self.ndof))
        for i in range(self.ndof):
            ep = e.copy(); ep[i] += h
            em = e.copy(); em[i] -= h
            J[:, i] = (self.q_int(ep) - self.q_int(em)) / (2*h)
        return J

    def frequencies(self, n=3):
        from scipy.linalg import eigh
        K = self.num_jacobian(self.e0)
        fr = self.free
        w2 = eigh(K[np.ix_(fr, fr)], self.M[np.ix_(fr, fr)], eigvals_only=True)
        w2 = np.sort(w2[w2 > 1e-9])
        return np.sqrt(w2[:n]) / (2*np.pi)

    # ---------------- phase-A additions ----------------

    def tangent_stiffness(self, e=None):
        """Tangent stiffness (numerical) about configuration e (default: straight e0)."""
        return self.num_jacobian(self.e0 if e is None else e)

    def set_rayleigh_damping(self, zeta, f_lo=None, f_hi_factor=5.0, K_t=None):
        """Constant Rayleigh damping C = alpha*M + beta*K_t with modal damping ratio
        `zeta` matched EXACTLY at w1 = 2*pi*f_lo and w2 = 2*pi*(f_hi_factor*f_lo):
            zeta(w) = alpha/(2 w) + beta*w/2
            alpha = 2 zeta w1 w2/(w1+w2),  beta = 2 zeta/(w1+w2)
        f_lo defaults to the beam's own first frequency. K_t defaults to the tangent
        stiffness at the straight configuration (constant matrix; valid in the small-
        deflection regime of phase A). Stores self.C, returns (alpha, beta)."""
        if f_lo is None:
            f_lo = float(self.frequencies(1)[0])
        w1 = 2.0 * np.pi * f_lo
        w2 = 2.0 * np.pi * f_lo * f_hi_factor
        alpha = 2.0 * zeta * w1 * w2 / (w1 + w2)
        beta = 2.0 * zeta / (w1 + w2)
        if K_t is None:
            K_t = self.tangent_stiffness()
        self.C = alpha * self.M + beta * K_t
        self.rayleigh = {"alpha": alpha, "beta": beta, "zeta": zeta,
                         "f_lo_hz": f_lo, "f_hi_hz": f_lo * f_hi_factor}
        return alpha, beta

    def initial_velocity_field(self, v_transverse, v_axial=None, h=1e-6):
        """Project a prescribed initial velocity field (expressed in the clamped base
        frame) onto the nodal velocity DOFs edot(0).

        v_transverse: callable y -> transverse velocity (local y), y in [-h, L+h]
        v_axial:      callable y -> axial velocity (local x), or None (zero)
        Per node at y_n: position rates = field values; slope rates = d(field)/dy by
        central difference (step h). Clamped-root DOFs are forced to zero (the root is
        kinematically attached to the base, which has already jumped)."""
        ed = np.zeros(self.ndof)
        for n in range(self.n_node):
            y = n * self.l
            vt = float(v_transverse(y))
            dvt = (float(v_transverse(y + h)) - float(v_transverse(y - h))) / (2.0 * h)
            if v_axial is not None:
                va = float(v_axial(y))
                dva = (float(v_axial(y + h)) - float(v_axial(y - h))) / (2.0 * h)
            else:
                va = dva = 0.0
            ed[4*n:4*n+4] = [va, vt, dva, dvt]
        ed[self.fixed] = 0.0
        return ed

    def root_moment(self, e):
        """Root bending moment M = EI * d2(transverse)/dx^2 at x=0 (small-deflection
        curvature approximation of kappa = |r' x r''|/|r'|^3), from the root element's
        transverse nodal DOFs [ry0, ry0', ry1, ry1']."""
        _, _, Sxx0 = shape(0.0, self.l)
        ey = e[self.eidx[0]].reshape(4, 2)[:, 1]
        return self.ei * float(Sxx0 @ ey)

    def tip_transverse(self, e):
        """Transverse (local y) tip displacement."""
        return float(e[4*(self.n_node - 1) + 1])

    def node_y(self):
        """Axial positions of nodes along the undeformed beam."""
        return np.arange(self.n_node) * self.l
