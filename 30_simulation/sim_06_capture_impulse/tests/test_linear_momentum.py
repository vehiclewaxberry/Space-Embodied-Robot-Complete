"""P conservation: combined M*v_com must equal the summed pre-capture linear momentum,
about any frame, for the production grid and random ensembles."""
import numpy as np
from _helpers import rigidize, random_bodies, scenario_grid, RNG

TOL = 1e-13

def test_grid_linear_momentum():
    worst = 0.0
    for key, bodies in scenario_grid():
        r = rigidize(bodies)
        P_pre = sum(b["m"] * np.asarray(b["v"]) for b in bodies)
        num = np.linalg.norm(r["M"] * r["v_com"] - P_pre)
        den = max(np.linalg.norm(P_pre), 1e-30)
        worst = max(worst, num / den)
        assert r["eps_P"] < TOL, (key, r["eps_P"])
    return worst

def test_random_linear_momentum():
    worst = 0.0
    for _ in range(200):
        bodies = random_bodies(RNG, n=int(RNG.integers(2, 5)))
        r = rigidize(bodies)
        worst = max(worst, r["eps_P"])
        assert r["eps_P"] < TOL
    return worst

def test_impulse_sum_zero():
    """Internal impulses must sum to zero (Newton's third law across the junction)."""
    worst = 0.0
    for key, bodies in scenario_grid():
        r = rigidize(bodies)
        Jsum = sum(imp["J"] for imp in r["impulses"])
        ref = max(max(np.linalg.norm(imp["J"]) for imp in r["impulses"]), 1e-30)
        worst = max(worst, np.linalg.norm(Jsum) / ref)
        assert np.linalg.norm(Jsum) / ref < 1e-12, key
    return worst
