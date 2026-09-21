"""sim_09 -- target state propagation to the capture instant t_c.

Default model ("const_omega"): rigid body spinning at CONSTANT angular velocity
(inertially fixed omega vector):

    omega_I   = deg2rad(omega_dps) * tumble_axis / |tumble_axis|   (inertial axes)
    R_T(t_c)  = expm([omega_I]x * t_c) @ R_T(0)                    (Rodrigues)
    r_g(t_c)  = r_T + R_T(t_c) @ r_g^T          (target CoM r_T = 0, at rest)
    v_g(t_c)  = omega_I x (R_T(t_c) @ r_g^T)    (CoM translationally at rest)

This is exact for an axisymmetric target spinning about its symmetry axis and is
the standard scenario assumption of sim_04/sim_06 (t_c = 0 there). The general
Euler (torque-free) propagation is available via mode="torque_free", which calls
the VALIDATED 30_simulation/common/rigid_body.propagate_torque_free (DOP853, rtol 1e-10)
-- no new physics in this module.

Conventions: tumble_axis is given in the INERTIAL frame (identical to the target
frame axes when attitude0_quat = [1,0,0,0], the sim_04/sim_06 nominal).
Quaternions are scalar-first [w,x,y,z], body->inertial (rigid_body convention).
"""
import _bootstrap  # noqa: F401
import numpy as np

from rigid_body import propagate_torque_free, q_to_R   # validated 30_simulation/common core


def _skew(v):
    return np.array([[0.0, -v[2], v[1]],
                     [v[2], 0.0, -v[0]],
                     [-v[1], v[0], 0.0]])


def rodrigues(w, t):
    """expm([w]x * t) via Rodrigues; exact identity for |w|*t = 0.
    Valid for NEGATIVE t as well (sin/cos handle the signed angle)."""
    w = np.asarray(w, float)
    th = np.linalg.norm(w) * t
    if abs(th) < 1e-300:
        return np.eye(3)
    a = w / np.linalg.norm(w)
    K = _skew(a)
    return np.eye(3) + np.sin(th) * K + (1.0 - np.cos(th)) * (K @ K)


def omega_inertial(target_state):
    """Inertial angular velocity vector [rad/s] from the candidate target_state."""
    axis = np.asarray(target_state["tumble_axis"], float)
    n = np.linalg.norm(axis)
    if n < 1e-12:
        raise ValueError("tumble_axis must be a nonzero vector")
    return np.deg2rad(float(target_state["omega_dps"])) * axis / n


def attitude0(target_state):
    """Initial attitude R_T(0) from scalar-first quaternion (default identity)."""
    q = np.asarray(target_state.get("attitude0_quat", (1.0, 0.0, 0.0, 0.0)), float)
    q = q / np.linalg.norm(q)
    return q_to_R(q).as_matrix(), q


def propagate(target_state, r_g_T, t_c, mode="const_omega", target_I=None, n=1500):
    """Propagate the target to t_c and express the grasp geometry inertially.

    Parameters
    ----------
    target_state : dict {omega_dps, tumble_axis (inertial), attitude0_quat}
    r_g_T        : (3,) grasp point relative to the target CoM, TARGET frame
    t_c          : capture time [s]
    mode         : "const_omega" (analytic, default) | "torque_free"
                   (general Euler dynamics via validated rigid_body core;
                   requires target_I = 3x3 inertia about CoM, target axes)
    Returns dict: R_T (3x3 target->inertial at t_c), omega_I (3,) at t_c,
                  r_g_I (3,), v_g_I (3,), ee_twist_des (6,) = [v_g_I; omega_I].
    """
    r_g_T = np.asarray(r_g_T, float).reshape(3)
    R0, q0 = attitude0(target_state)
    w_I0 = omega_inertial(target_state)

    if mode == "const_omega":
        R_T = rodrigues(w_I0, float(t_c)) @ R0
        w_I = w_I0
    elif mode == "torque_free":
        if target_I is None:
            raise ValueError("torque_free mode requires target_I (3x3 about CoM)")
        if float(t_c) == 0.0:
            R_T, w_I = R0, w_I0
        else:
            w_body0 = R0.T @ w_I0             # rigid_body integrates body-frame omega
            res = propagate_torque_free(np.asarray(target_I, float), w_body0,
                                        float(t_c), n=n, q0=tuple(q0))
            R_T = q_to_R(res["Q"][-1]).as_matrix()
            w_I = R_T @ res["W"][-1]
    else:
        raise ValueError(f"unknown propagation mode: {mode}")

    r_arm = R_T @ r_g_T                       # grasp lever arm, inertial
    r_g_I = r_arm                             # target CoM at scene origin
    v_g_I = np.cross(w_I, r_arm)              # CoM translationally at rest
    return {"R_T": R_T, "omega_I": w_I, "r_g_I": r_g_I, "v_g_I": v_g_I,
            "ee_twist_des": np.concatenate([v_g_I, w_I]), "mode": mode}
