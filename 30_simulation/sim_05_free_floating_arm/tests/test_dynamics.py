"""Free-floating dynamics acceptance tests (sim_05):
(1) qdot=0 -> V_b=0
(2) total momentum about the inertial origin stays < 1e-10 along a trajectory
(3) closed joint cycle (joint2 0->+60->0 deg, joint3 0->-40->0 deg, phased)
    produces a non-zero geometric phase of the base attitude
(4) scaling ALL masses/inertias by k leaves the base motion exactly unchanged
(5) generalized Jacobian J_g matches finite-differenced EE inertial velocity
    along the integrated trajectory (rel err < 1e-4)."""
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SIM05 = os.path.dirname(HERE)
sys.path.insert(0, SIM05)
sys.path.insert(0, os.path.normpath(os.path.join(SIM05, "..", "common")))

from rigid_body import q_to_R  # noqa: E402
from dynamics import FreeFloatingB601, min_jerk  # noqa: E402

_DYN = None
_TRAJ = None  # cached (q_fun, qd_fun, t_end, result-with-dense-sol)


def _dyn():
    global _DYN
    if _DYN is None:
        _DYN = FreeFloatingB601()
    return _DYN


# ---- shared all-joint test trajectory (within URDF limits) --------------------
_AMP = np.array([0.5, -0.9, -0.7, 0.6, 0.5, 1.0])
_T_END = 6.0


def _q_fun(t):
    return np.array([min_jerk(t, _T_END, a)[0] for a in _AMP])


def _qd_fun(t):
    return np.array([min_jerk(t, _T_END, a)[1] for a in _AMP])


def _traj():
    global _TRAJ
    if _TRAJ is None:
        _TRAJ = _dyn().integrate_trajectory(_q_fun, _qd_fun, _T_END,
                                            n_out=121, dense=True)
    return _TRAJ


def test_1_zero_rate_zero_base_velocity():
    """(1) qdot = 0 -> V_b = 0 at random configurations."""
    dyn = _dyn()
    rng = np.random.default_rng(3)
    worst = 0.0
    for _ in range(10):
        q = rng.uniform(-1.5, 1.5, 6)
        Vb = dyn.base_velocity_zero_momentum(q, np.zeros(6))
        worst = max(worst, float(np.max(np.abs(Vb))))
    assert worst < 1e-14, worst
    return worst


def test_2_momentum_conservation_along_trajectory():
    """(2) |[P; L_O]| about the inertial origin < 1e-10 along the trajectory
    (momentum computed body-by-body in the inertial frame, independently of the
    H-matrix assembly)."""
    dyn = _dyn()
    res = _traj()
    worst = 0.0
    for i, t in enumerate(res["t"]):
        p6 = dyn.momentum_inertial(res["r"][i], res["Q"][i],
                                   _q_fun(t), res["Vb"][i], _qd_fun(t))
        worst = max(worst, float(np.linalg.norm(p6)))
    assert worst < 1e-10, worst
    return worst


def test_3_geometric_phase_closed_cycle():
    """(3) phased rectangle cycle: joint2 0->+60deg (0..4s), joint3 0->-40deg
    (4..8s), joint2 back (8..12s), joint3 back (12..16s). Joints return exactly
    to zero but the base attitude acquires a non-zero geometric phase."""
    dyn = _dyn()
    a2, a3, Ts = np.deg2rad(60.0), np.deg2rad(-40.0), 4.0

    def qc(t):
        q = np.zeros(6)
        if t < Ts:
            q[1] = min_jerk(t, Ts, a2)[0]
        elif t < 2 * Ts:
            q[1] = a2
            q[2] = min_jerk(t - Ts, Ts, a3)[0]
        elif t < 3 * Ts:
            q[1] = a2 - min_jerk(t - 2 * Ts, Ts, a2)[0]
            q[2] = a3
        else:
            q[2] = a3 - min_jerk(t - 3 * Ts, Ts, a3)[0]
        return q

    def qdc(t):
        qd = np.zeros(6)
        if t < Ts:
            qd[1] = min_jerk(t, Ts, a2)[1]
        elif t < 2 * Ts:
            qd[2] = min_jerk(t - Ts, Ts, a3)[1]
        elif t < 3 * Ts:
            qd[1] = -min_jerk(t - 2 * Ts, Ts, a2)[1]
        else:
            qd[2] = -min_jerk(t - 3 * Ts, Ts, a3)[1]
        return qd

    res = dyn.integrate_trajectory(qc, qdc, 4 * Ts, n_out=161)
    assert np.max(np.abs(qc(4 * Ts))) < 1e-12          # joints closed the loop
    phase_deg = float(res["dev_angle_deg"][-1])
    assert phase_deg > 0.01, "geometric phase %.4f deg suspiciously small" % phase_deg
    # base rate back to ~0 after the cycle (qdot ends at 0)
    assert float(np.max(np.abs(res["Vb"][-1]))) < 1e-12
    test_3_geometric_phase_closed_cycle.phase_deg = phase_deg
    test_3_geometric_phase_closed_cycle.euler_final = res["euler_xyz_deg"][-1].tolist()
    return phase_deg


def test_4_mass_scale_invariance():
    """(4) all masses & inertias x k -> V_b(q, qdot) and the whole base motion
    are unchanged."""
    k = 3.7
    d1, dk = _dyn(), FreeFloatingB601(mass_scale=k)
    rng = np.random.default_rng(5)
    worst = 0.0
    for _ in range(8):
        q = rng.uniform(-1.5, 1.5, 6)
        qd = rng.uniform(-0.8, 0.8, 6)
        v1 = d1.base_velocity_zero_momentum(q, qd)
        vk = dk.base_velocity_zero_momentum(q, qd)
        worst = max(worst, float(np.max(np.abs(v1 - vk)) / max(np.max(np.abs(v1)), 1e-12)))
    assert worst < 1e-12, worst
    # short trajectory: identical base pose history
    r1 = d1.integrate_trajectory(_q_fun, _qd_fun, 3.0, n_out=31)
    rk = dk.integrate_trajectory(_q_fun, _qd_fun, 3.0, n_out=31)
    dq = float(np.max(np.abs(r1["Q"] - rk["Q"])))
    dr = float(np.max(np.abs(r1["r"] - rk["r"])))
    worst = max(worst, dq, dr)
    assert dq < 1e-10 and dr < 1e-10, (dq, dr)
    return worst


def test_5_generalized_jacobian_vs_finite_difference():
    """(5) EE inertial velocity (linear + angular) by central differences of the
    integrated motion vs R_b @ (J_g @ qdot); relative error < 1e-4."""
    dyn = _dyn()
    res = _traj()
    sol = res["sol"].sol
    h = 1e-3
    worst = 0.0

    def ee_pose(t):
        s = sol(t)
        quat = s[3:7] / np.linalg.norm(s[3:7])
        Rb = q_to_R(quat).as_matrix()
        T_E = dyn.arm.fk(_q_fun(t))["T_E"]
        return s[:3] + Rb @ T_E[:3, 3], Rb @ T_E[:3, :3]

    for t in np.linspace(0.5, _T_END - 0.5, 21):
        qd = _qd_fun(t)
        s = sol(t)
        quat = s[3:7] / np.linalg.norm(s[3:7])
        Rb = q_to_R(quat).as_matrix()
        Jg = dyn.generalized_jacobian(_q_fun(t))
        v_mod = Rb @ (Jg @ qd)[:3]
        w_mod = Rb @ (Jg @ qd)[3:]
        pp, Rp = ee_pose(t + h)
        pm, Rm = ee_pose(t - h)
        p0, R0 = ee_pose(t)
        v_fd = (pp - pm) / (2 * h)
        W = ((Rp - Rm) / (2 * h)) @ R0.T
        W = 0.5 * (W - W.T)
        w_fd = np.array([W[2, 1], W[0, 2], W[1, 0]])
        rel_v = np.linalg.norm(v_fd - v_mod) / max(np.linalg.norm(v_mod), 1e-6)
        rel_w = np.linalg.norm(w_fd - w_mod) / max(np.linalg.norm(w_mod), 1e-6)
        worst = max(worst, float(rel_v), float(rel_w))
        assert rel_v < 1e-4 and rel_w < 1e-4, (t, rel_v, rel_w)
    return worst


if __name__ == "__main__":
    for fn in [test_1_zero_rate_zero_base_velocity,
               test_2_momentum_conservation_along_trajectory,
               test_3_geometric_phase_closed_cycle,
               test_4_mass_scale_invariance,
               test_5_generalized_jacobian_vs_finite_difference]:
        print("%s: PASS (worst=%.3e)" % (fn.__name__, fn()))
    print("geometric phase [deg]:", test_3_geometric_phase_closed_cycle.phase_deg,
          "euler_final:", test_3_geometric_phase_closed_cycle.euler_final)
