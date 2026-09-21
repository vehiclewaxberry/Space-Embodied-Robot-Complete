"""Fixed-step RK4 integration of the floating-base state with quaternion base
orientation. Deterministic: no wall-clock, no RNG inside the stepper."""
from __future__ import annotations

import numpy as np

from .frames import quat_derivative, quat_normalize, quat_to_R


class SolverNonConvergence(RuntimeError):
    """Raised when the state leaves the finite/plausible domain (fail-closed)."""


def pack_state(p, quat, q, v_base, qd):
    return np.concatenate([p, quat, q, v_base, qd])


def unpack_state(x, nj):
    p = x[0:3]
    quat = x[3:7]
    q = x[7 : 7 + nj]
    v_base = x[7 + nj : 13 + nj]
    qd = x[13 + nj : 13 + 2 * nj]
    return p, quat, q, v_base, qd


def state_derivative(plant, x, tau_fn, t):
    nj = plant.nj
    p, quat, q, v_base, qd = unpack_state(x, nj)
    qn, _ = quat_normalize(quat)
    R_WB = quat_to_R(qn)
    tau = tau_fn(t, q, qd, v_base)
    udot, _, _ = plant.forward_dynamics(q, v_base, qd, tau)
    dp = R_WB @ v_base[3:]
    dquat = quat_derivative(qn, v_base[:3])
    return np.concatenate([dp, dquat, qd, udot])


def rk4_run(plant, x0, t_end, dt, tau_fn=None, sample_every=1, callbacks=None):
    """Integrate and sample. Returns dict of stacked sample arrays.

    tau_fn(t, q, qd, v_base) -> joint torques; defaults to zero torque.
    Raises SolverNonConvergence when the state becomes non-finite or the base
    rate exceeds a hard plausibility ceiling.
    """
    nj = plant.nj
    if tau_fn is None:
        tau_fn = lambda t, q, qd, v_base: np.zeros(nj)
    n_steps = int(round(t_end / dt))
    x = np.asarray(x0, dtype=float).copy()
    samples = {"t": [], "x": [], "h_O": [], "h_C": [], "E": [], "p_com": [], "quat_renorm": []}
    renorm_acc = 0.0

    def record(t, x):
        p, quat, q, v_base, qd = unpack_state(x, nj)
        qn, _ = quat_normalize(quat)
        R_WB = quat_to_R(qn)
        h_O, h_C, p_com, _, E = plant.momentum_world(R_WB, p, q, v_base, qd)
        samples["t"].append(t)
        samples["x"].append(x.copy())
        samples["h_O"].append(h_O)
        samples["h_C"].append(h_C)
        samples["E"].append(E)
        samples["p_com"].append(p_com)
        samples["quat_renorm"].append(renorm_acc)
        if callbacks:
            for cb in callbacks:
                cb(t, x)

    record(0.0, x)
    for k in range(n_steps):
        t = k * dt
        k1 = state_derivative(plant, x, tau_fn, t)
        k2 = state_derivative(plant, x + 0.5 * dt * k1, tau_fn, t + 0.5 * dt)
        k3 = state_derivative(plant, x + 0.5 * dt * k2, tau_fn, t + 0.5 * dt)
        k4 = state_derivative(plant, x + dt * k3, tau_fn, t + dt)
        x = x + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        if not np.all(np.isfinite(x)):
            raise SolverNonConvergence(f"non-finite state at t={t + dt:.6f}s")
        # renormalize quaternion, keep audit of how much was removed
        qraw = x[3:7]
        qn, drift = quat_normalize(qraw)
        renorm_acc += drift
        x[3:7] = qn
        if np.linalg.norm(x[7 + nj : 10 + nj]) > 1.0e3:
            raise SolverNonConvergence(f"base angular rate implausible at t={t + dt:.6f}s")
        if (k + 1) % sample_every == 0:
            record((k + 1) * dt, x)

    for key in samples:
        samples[key] = np.asarray(samples[key])
    return samples
