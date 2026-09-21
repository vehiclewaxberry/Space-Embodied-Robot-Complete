"""Independent cross-check: solve the same plastic rigidization with 6x6 SPATIAL momentum
about a fixed reference point O (Featherstone convention), sharing NO intermediate code
with capture_impulse.rigidize. Spatial inertia of a rigid body (CoM offset c = r_com - O):

    Phi = [[ I_C + m [c]x [c]x^T ,  m [c]x ],
           [ m [c]x^T             ,  m E   ]]
    h   = [H_O; P] = Phi @ [w; v_O]        (v_O = velocity of body point at O)

Pre-capture total h is summed body-wise directly from definitions; post-capture we solve
the 6x6 system for the combined body's [w; v_O] and compare against rigidize()."""
import numpy as np
from _helpers import rigidize, random_bodies, scenario_grid, RNG, skew

TOL = 1e-9

def spatial_solve(bodies, O):
    """Independent implementation: no reuse of rigidize/steiner."""
    O = np.asarray(O, float)
    # total spatial momentum about O, straight from definitions
    H_O = np.zeros(3); P = np.zeros(3)
    for b in bodies:
        H_O += np.asarray(b["I"]) @ b["w"] + b["m"] * np.cross(np.asarray(b["r"]) - O, b["v"])
        P += b["m"] * np.asarray(b["v"])
    # combined-body mass properties, computed independently
    M = sum(b["m"] for b in bodies)
    c = sum(b["m"] * np.asarray(b["r"]) for b in bodies) / M - O
    I_C = np.zeros((3, 3))
    for b in bodies:
        d = np.asarray(b["r"]) - (c + O)
        Dx = skew(d)
        I_C += np.asarray(b["I"]) + b["m"] * (Dx @ Dx.T)
    Cx = skew(c)
    Phi = np.block([[I_C + M * (Cx @ Cx.T), M * Cx],
                    [M * Cx.T, M * np.eye(3)]])
    wv = np.linalg.solve(Phi, np.concatenate([H_O, P]))
    w = wv[:3]; v_O = wv[3:]
    v_com = v_O + np.cross(w, c)
    return w, v_com, I_C

def _compare(bodies, O):
    a = rigidize(bodies)
    w, v_com, I_C = spatial_solve(bodies, O)
    ew = np.linalg.norm(w - a["w_plus"]) / max(np.linalg.norm(a["w_plus"]), 1e-30)
    ev = np.linalg.norm(v_com - a["v_com"]) / max(np.linalg.norm(a["v_com"]), 1e-30)
    eI = np.linalg.norm(I_C - a["I_comb"]) / np.linalg.norm(a["I_comb"])
    assert ew < TOL and ev < TOL and eI < TOL, (ew, ev, eI)
    return max(ew, ev, eI)

def test_grid_crosscheck():
    worst = 0.0
    for O in [np.zeros(3), np.array([2.0, -1.0, 3.0])]:
        for key, bodies in scenario_grid():
            worst = max(worst, _compare(bodies, O))
    return worst

def test_random_crosscheck():
    worst = 0.0
    for _ in range(100):
        bodies = random_bodies(RNG, n=int(RNG.integers(2, 5)))
        O = RNG.normal(scale=5.0, size=3)
        worst = max(worst, _compare(bodies, O))
    return worst
