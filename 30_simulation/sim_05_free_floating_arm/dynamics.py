"""dynamics.py -- free-floating base dynamics for the servicer + arm_b601_v1 (sim_05).

Momentum-level model (no external forces, system starts at rest => total linear
and angular momentum stay exactly zero):

    p = H_bb @ V_b + H_bm @ qdot            (6-vector [P; L_about_base_origin])

with V_b = [v_b; w_b] the base spatial velocity about the base (S) origin,
H_bb (6x6) the system locked inertia and H_bm (6x6) the base/arm coupling
matrix. Both are assembled with the unit-velocity method: momentum is linear in
(V_b, qdot), so each column is the total system momentum for one unit velocity
component. All matrices are expressed in the base (S) frame, so they depend on
q only.

Zero-momentum base reaction:   V_b = -H_bb^{-1} @ H_bm @ qdot
Generalized Jacobian:          J_g = J_m - J_b @ H_bb^{-1} @ H_bm
    J_b = [[I3, -[r_E]x], [0, I3]]  maps V_b (about the base origin) to the EE
    spatial velocity; J_m is the fixed-base geometric Jacobian.

Bodies
------
- composite base body = servicer_12U_v0 (24 kg whole-spacecraft rigid line from
  mass_inertia_budget_v1.csv, frame S about CoM) + robot_mount_adapter_v0
  (1.2 kg, frame M about CoM, placed via T_SM: cg_S = t_SM + R_SM@cg_M,
  I_S = R_SM@I_M@R_SM^T) -> m = 25.2 kg (parallel-axis composite).
- arm base_link (0.8366 kg): bolted to the mount (T_MA0 = identity), rigid with
  the base -> contributes to H_bb only. Kept as a separate base-fixed body so
  the 25.2 kg composite-base bookkeeping stays exactly servicer+adapter.
- link1..link6 moving bodies (link6 = composite with the locked gripper).

Base pose integration: state = [r_b (3), quat (4, scalar-first, base->inertial)],
qdot of the base pose driven by the zero-momentum V_b; solve_ivp DOP853.
"""
import os
import sys
import numpy as np
from scipy.integrate import solve_ivp

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "common")))

from rigid_body import load_object, qmult, q_to_R, q_to_euler_deg  # noqa: E402
from b601_model import (B601Arm, T_SM_t, R_SM, T_SM_4x4, skew,     # noqa: E402
                        transform_inertial, combine_inertials)


# ---------------------------------------------------------------- base composite
def build_base_composite():
    """servicer_12U_v0 (frame S, about CoM) + robot_mount_adapter_v0 (frame M,
    about CoM, mapped to S via the frozen T_SM). Returns dict(mass, cg, I) --
    inertia about the composite CoM, S axes."""
    srv = load_object("servicer_12U_v0")
    adp = load_object("robot_mount_adapter_v0")
    m_a, cg_a_S, I_a_S = transform_inertial(T_SM_4x4(), adp["mass"], adp["cg"], adp["I"])
    m, cg, I = combine_inertials([(srv["mass"], srv["cg"], srv["I"]),
                                  (m_a, cg_a_S, I_a_S)])
    return {"mass": m, "cg": cg, "I": I,
            "parts": {"servicer_12U_v0": srv["mass"], "robot_mount_adapter_v0": adp["mass"]},
            "adapter_cg_S": cg_a_S}


def min_jerk(t, T, A):
    """Min-jerk 0 -> A over [0, T]; returns (pos, vel). Clamped outside."""
    x = np.clip(t / T, 0.0, 1.0)
    s = 10 * x**3 - 15 * x**4 + 6 * x**5
    sd = np.where((t >= 0) & (t <= T), (30 * x**2 - 60 * x**3 + 30 * x**4) / T, 0.0)
    return A * s, A * sd


def attitude_angle_deg(quat):
    """Total rotation angle of a (scalar-first) quaternion, degrees."""
    w = np.clip(abs(np.asarray(quat)[..., 0] if np.ndim(quat) > 1 else quat[0]), 0, 1)
    return np.degrees(2.0 * np.arccos(w))


# ---------------------------------------------------------------- dynamics model
class FreeFloatingB601:
    def __init__(self, mass_scale=1.0):
        self.k = float(mass_scale)
        self.arm = B601Arm()
        self.base_comp = build_base_composite()          # 25.2 kg servicer+adapter
        mb, cb, Ib = self.base_comp["mass"], self.base_comp["cg"], self.base_comp["I"]
        m0, c0, I0 = self.arm.base_link_inertial_in_S()  # arm base_link, base-fixed
        self.fixed_bodies = [(self.k * mb, cb, self.k * Ib),
                             (self.k * m0, c0, self.k * I0)]
        self.m_base_comp = mb                            # 25.2 (unscaled bookkeeping)

    # -- body set at configuration q (base pose = identity -> S frame) ----------
    def _bodies(self, q):
        Z = np.zeros((3, 6))
        bodies = [{"mass": m, "c": c, "I": I, "Jv": Z, "Jw": Z}
                  for (m, c, I) in self.fixed_bodies]
        for s in self.arm.link_com_states(q):
            bodies.append({"mass": self.k * s["mass"], "c": s["c"],
                           "I": self.k * s["I"], "Jv": s["Jv"], "Jw": s["Jw"]})
        return bodies

    @staticmethod
    def _momentum_of(bodies, Vb, qdot):
        """Total [P; L_about_base_origin] in the base frame for base spatial
        velocity Vb = [v_b; w_b] (about the base origin) and joint rates qdot."""
        vb, wb = Vb[:3], Vb[3:]
        P = np.zeros(3)
        L = np.zeros(3)
        for b in bodies:
            vc = vb + np.cross(wb, b["c"]) + b["Jv"] @ qdot
            om = wb + b["Jw"] @ qdot
            P += b["mass"] * vc
            L += b["I"] @ om + b["mass"] * np.cross(b["c"], vc)
        return np.concatenate([P, L])

    def momentum_base_frame(self, q, Vb, qdot):
        return self._momentum_of(self._bodies(q), np.asarray(Vb, float),
                                 np.asarray(qdot, float))

    def momentum_matrices(self, q):
        """(H_bb 6x6, H_bm 6x6) via the unit-velocity method."""
        bodies = self._bodies(q)
        H = np.zeros((6, 12))
        for j in range(12):
            Vb = np.zeros(6)
            qd = np.zeros(6)
            if j < 6:
                Vb[j] = 1.0
            else:
                qd[j - 6] = 1.0
            H[:, j] = self._momentum_of(bodies, Vb, qd)
        return H[:, :6], H[:, 6:]

    def base_velocity_zero_momentum(self, q, qdot):
        """V_b = -H_bb^{-1} H_bm qdot (zero total momentum), base-frame coords."""
        H_bb, H_bm = self.momentum_matrices(q)
        return -np.linalg.solve(H_bb, H_bm @ np.asarray(qdot, float))

    # -- generalized Jacobian -----------------------------------------------------
    def generalized_jacobian(self, q, return_parts=False):
        """J_g = J_m - J_b @ H_bb^{-1} @ H_bm  (EE spatial velocity in the base
        frame per unit qdot under zero total momentum)."""
        f = self.arm.fk(q)
        J_m = self.arm.jacobian(q, fk_out=f)
        rE = f["T_E"][:3, 3]
        J_b = np.eye(6)
        J_b[:3, 3:] = -skew(rE)
        H_bb, H_bm = self.momentum_matrices(q)
        J_g = J_m - J_b @ np.linalg.solve(H_bb, H_bm)
        if return_parts:
            return J_g, {"J_m": J_m, "J_b": J_b, "H_bb": H_bb, "H_bm": H_bm, "T_E": f["T_E"]}
        return J_g

    # -- inertial-frame momentum check ---------------------------------------------
    def momentum_inertial(self, r_b, quat, q, Vb, qdot):
        """Total [P; L_about_inertial_origin] in the INERTIAL frame, computed
        body-by-body (independent of the H-matrix assembly). r_b, quat = base
        pose; Vb = base spatial velocity in base-frame coords."""
        R = q_to_R(np.asarray(quat) / np.linalg.norm(quat)).as_matrix()
        vb, wb = Vb[:3], Vb[3:]
        P = np.zeros(3)
        L = np.zeros(3)
        for b in self._bodies(q):
            r_I = r_b + R @ b["c"]
            v_I = R @ (vb + np.cross(wb, b["c"]) + b["Jv"] @ qdot)
            w_I = R @ (wb + b["Jw"] @ qdot)
            I_I = R @ b["I"] @ R.T
            P += b["mass"] * v_I
            L += I_I @ w_I + b["mass"] * np.cross(r_I, v_I)
        return np.concatenate([P, L])

    # -- trajectory integration ------------------------------------------------------
    def integrate_trajectory(self, q_fun, qd_fun, t_end, n_out=400,
                             rtol=1e-11, atol=1e-13, dense=False):
        """Integrate the base pose along a prescribed joint trajectory under zero
        total momentum. q_fun(t)/qd_fun(t) -> (6,). Returns dict with t, r (n,3),
        Q (n,4 scalar-first), euler_xyz_deg (n,3), dev_angle_deg (n,), Vb (n,6),
        hbm_qdot (n,6) and (if dense) the solve_ivp solution object."""
        def deriv(t, s):
            quat = s[3:7] / np.linalg.norm(s[3:7])
            q = q_fun(t)
            qd = qd_fun(t)
            Vb = self.base_velocity_zero_momentum(q, qd)
            Rb = q_to_R(quat).as_matrix()
            rdot = Rb @ Vb[:3]
            qdot_quat = 0.5 * qmult(quat, np.array([0.0, *Vb[3:]]))
            return np.concatenate([rdot, qdot_quat])

        s0 = np.array([0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
        ts = np.linspace(0.0, t_end, n_out)
        sol = solve_ivp(deriv, (0.0, t_end), s0, t_eval=ts, rtol=rtol, atol=atol,
                        method="DOP853", dense_output=dense)
        r = sol.y[:3].T
        Q = sol.y[3:7].T
        Q = Q / np.linalg.norm(Q, axis=1, keepdims=True)
        Vb_hist = np.zeros((len(ts), 6))
        hbm = np.zeros((len(ts), 6))
        for i, t in enumerate(ts):
            q = q_fun(t)
            qd = qd_fun(t)
            _, H_bm = self.momentum_matrices(q)
            Vb_hist[i] = self.base_velocity_zero_momentum(q, qd)
            hbm[i] = H_bm @ qd
        eul = np.array([q_to_euler_deg(qq) for qq in Q])
        dev = np.array([attitude_angle_deg(qq) for qq in Q])
        out = {"t": ts, "r": r, "Q": Q, "euler_xyz_deg": eul,
               "dev_angle_deg": dev, "Vb": Vb_hist, "hbm_qdot": hbm}
        if dense:
            out["sol"] = sol
        return out


if __name__ == "__main__":
    dyn = FreeFloatingB601()
    bc = dyn.base_comp
    print("composite base: m=%.4f kg  cg=%s" % (bc["mass"], np.round(bc["cg"], 6)))
    print("I_comp [kg m^2]:\n", np.round(bc["I"], 6))
    q = np.zeros(6)
    H_bb, H_bm = dyn.momentum_matrices(q)
    print("H_bb[3:,3:] (locked angular inertia about S origin):\n", np.round(H_bb[3:, 3:], 5))
    print("Vb for qdot=e2:", np.round(dyn.base_velocity_zero_momentum(q, np.eye(6)[1]), 6))
