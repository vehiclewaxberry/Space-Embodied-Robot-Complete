"""Frame invariance: rigid translation + rotation + Galilean boost of the entire scene
must transform vector results covariantly and leave scalars (|w+|, dT) unchanged.
This is the highest-value check on the r x mv, Steiner, and tensor-rotation bookkeeping."""
import numpy as np
from _helpers import rigidize, random_bodies, scenario_grid, RNG

TOL = 1e-10

def rot_matrix(rng):
    """Deterministic-random proper rotation via QR."""
    A = rng.normal(size=(3, 3))
    Q, R = np.linalg.qr(A)
    Q = Q @ np.diag(np.sign(np.diag(R)))
    if np.linalg.det(Q) < 0:
        Q[:, 0] = -Q[:, 0]
    return Q

def transform(bodies, R, t, v_boost):
    return [{"m": b["m"], "I": R @ np.asarray(b["I"]) @ R.T,
             "r": R @ np.asarray(b["r"]) + t,
             "v": R @ np.asarray(b["v"]) + v_boost,
             "w": R @ np.asarray(b["w"])} for b in bodies]

def _check(bodies, R, t, v_boost):
    a = rigidize(bodies)
    b = rigidize(transform(bodies, R, t, v_boost))
    wmag = abs(np.linalg.norm(a["w_plus"]) - np.linalg.norm(b["w_plus"])) \
        / max(np.linalg.norm(a["w_plus"]), 1e-30)
    wcov = np.linalg.norm(b["w_plus"] - R @ a["w_plus"]) / max(np.linalg.norm(a["w_plus"]), 1e-30)
    dT = abs(a["dT"] - b["dT"]) / max(abs(a["dT"]), 1e-30) if abs(a["dT"]) > 1e-20 else 0.0
    com = np.linalg.norm(b["r_com"] - (R @ a["r_com"] + t)) / max(np.linalg.norm(t) + 1.0, 1.0)
    Icov = np.linalg.norm(b["I_comb"] - R @ a["I_comb"] @ R.T) / np.linalg.norm(a["I_comb"])
    assert wmag < TOL and wcov < TOL and dT < 1e-8 and com < TOL and Icov < TOL, \
        (wmag, wcov, dT, com, Icov)
    return max(wmag, wcov, dT, com, Icov)

def test_grid_frame_invariance():
    worst = 0.0
    R = rot_matrix(RNG); t = np.array([12.3, -4.5, 6.7]); vb = np.array([0.4, -0.1, 0.25])
    for key, bodies in scenario_grid():
        worst = max(worst, _check(bodies, R, t, vb))
    return worst

def test_random_frame_invariance():
    worst = 0.0
    for _ in range(60):
        bodies = random_bodies(RNG, n=int(RNG.integers(2, 4)))
        R = rot_matrix(RNG)
        t = RNG.normal(scale=20.0, size=3)
        vb = RNG.normal(scale=1.0, size=3)
        worst = max(worst, _check(bodies, R, t, vb))
    return worst
