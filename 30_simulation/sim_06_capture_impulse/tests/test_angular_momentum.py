"""H conservation about the INERTIAL ORIGIN and about arbitrary alternative origins —
this exercises the r x mv bookkeeping and parallel-axis terms independently of the
solver's own combined-CoM formulation."""
import numpy as np
from _helpers import rigidize, random_bodies, scenario_grid, RNG

TOL = 1e-11

def H_about(point, bodies):
    return sum(np.asarray(b["I"]) @ b["w"] + b["m"] * np.cross(np.asarray(b["r"]) - point, b["v"])
               for b in bodies)

def H_post_about(point, r):
    return r["I_comb"] @ r["w_plus"] + r["M"] * np.cross(r["r_com"] - point, r["v_com"])

def test_grid_angular_momentum_origin():
    worst = 0.0
    for key, bodies in scenario_grid():
        r = rigidize(bodies)
        worst = max(worst, r["eps_H_origin"])
        assert r["eps_H_origin"] < TOL, (key, r["eps_H_origin"])
    return worst

def test_arbitrary_origin():
    """H must be conserved about ANY fixed point, not just the origin/CoM."""
    worst = 0.0
    points = [np.array([1.7, -2.3, 0.9]), np.array([-10.0, 4.0, 25.0]), np.zeros(3)]
    for _ in range(60):
        bodies = random_bodies(RNG, n=int(RNG.integers(2, 4)))
        r = rigidize(bodies)
        for p in points:
            pre, post = H_about(p, bodies), H_post_about(p, r)
            eps = np.linalg.norm(post - pre) / max(np.linalg.norm(pre), 1e-30)
            worst = max(worst, eps)
            assert eps < TOL, (p, eps)
    return worst
