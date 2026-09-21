"""Plastic rigidization must never create kinetic energy: dT = KE_pre - KE_post >= 0
for every case (grid + random ensembles), and dT <= KE_pre. Also: an already-rigidly-
moving pair must dissipate exactly zero."""
import numpy as np
from _helpers import rigidize, random_bodies, scenario_grid, RNG

def test_grid_energy():
    worst = 0.0
    for key, bodies in scenario_grid():
        r = rigidize(bodies)
        assert r["dT"] >= -1e-12 * max(r["KE_pre"], 1e-30), (key, r["dT"])
        assert r["dT"] <= r["KE_pre"] * (1 + 1e-12), key
        worst = min(worst, r["dT"])
    return worst

def test_random_energy():
    for _ in range(300):
        bodies = random_bodies(RNG, n=int(RNG.integers(2, 5)))
        r = rigidize(bodies)
        assert r["dT"] >= -1e-12 * max(r["KE_pre"], 1e-30)
        assert r["dT"] <= r["KE_pre"] * (1 + 1e-12)

def test_already_rigid_zero_dissipation():
    """Bodies already moving as one rigid body: w common, v_i = v0 + w x (r_i - r0)."""
    worst = 0.0
    for _ in range(50):
        bodies = random_bodies(RNG, n=3)
        w = RNG.normal(scale=0.2, size=3); v0 = RNG.normal(scale=0.05, size=3)
        r0 = bodies[0]["r"]
        for b in bodies:
            b["w"] = w.copy()
            b["v"] = v0 + np.cross(w, np.asarray(b["r"]) - r0)
        r = rigidize(bodies)
        rel = abs(r["dT"]) / max(r["KE_pre"], 1e-30)
        werr = np.linalg.norm(r["w_plus"] - w) / max(np.linalg.norm(w), 1e-30)
        worst = max(worst, rel, werr)
        assert rel < 1e-11 and werr < 1e-11, (rel, werr)
    return worst
