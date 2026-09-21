"""3-DOF point-capture solver checks: P/H conservation, dT bounds vs 6-DOF rigid lock,
matched-velocity no-op, and central-impact equivalence."""
import numpy as np
from _helpers import rigidize, random_bodies, scenario_grid, RNG
from capture_impulse import rigidize_point_contact, build_capture_scenario

TOL = 1e-10

def _post_state(bodies, out):
    return [{**b, "v": np.asarray(b["v"]) + imp["dv"], "w": np.asarray(b["w"]) + imp["dw"]}
            for b, imp in zip(bodies, out["impulses"])]

def _H(point, bodies):
    return sum(np.asarray(b["I"]) @ b["w"] + b["m"] * np.cross(np.asarray(b["r"]) - point, b["v"])
               for b in bodies)

def test_conservation_and_bounds():
    worst = 0.0
    for key, bodies in scenario_grid():
        _, meta_rg = bodies, None
        p = np.zeros(3)  # placeholder replaced below
    for _ in range(80):
        bodies = random_bodies(RNG, n=2)
        p = RNG.normal(scale=0.8, size=3)
        out = rigidize_point_contact(bodies, p)
        post = _post_state(bodies, out)
        # P, H conserved about origin and about a random point
        for pt in (np.zeros(3), np.array([2.0, -1.0, 0.5])):
            eH = np.linalg.norm(_H(pt, post) - _H(pt, bodies)) / max(np.linalg.norm(_H(pt, bodies)), 1e-30)
            assert eH < TOL, eH
            worst = max(worst, eH)
        P_pre = sum(b["m"] * np.asarray(b["v"]) for b in bodies)
        P_post = sum(b["m"] * np.asarray(b["v"]) for b in post)
        assert np.linalg.norm(P_post - P_pre) / max(np.linalg.norm(P_pre), 1e-30) < TOL
        # point velocities matched
        vps = [np.asarray(b["v"]) + np.cross(b["w"], p - np.asarray(b["r"])) for b in post]
        assert np.linalg.norm(vps[0] - vps[1]) < 1e-9
        # 0 <= dT_point <= dT_rigid (rigid lock removes at least as much relative motion)
        rg = rigidize(bodies)
        assert out["dT"] >= -1e-12 * max(out["KE_pre"], 1e-30)
        assert out["dT"] <= rg["dT"] * (1 + 1e-9) + 1e-18, (out["dT"], rg["dT"])
    return worst

def test_matched_velocity_noop():
    bodies = random_bodies(RNG, n=2)
    p = np.array([0.3, -0.2, 0.1])
    w = RNG.normal(scale=0.1, size=3); v0 = RNG.normal(scale=0.03, size=3); r0 = bodies[0]["r"]
    for b in bodies:
        b["w"] = w.copy(); b["v"] = v0 + np.cross(w, np.asarray(b["r"]) - r0)
    out = rigidize_point_contact(bodies, p)
    assert np.linalg.norm(out["J"]) < 1e-12 and abs(out["dT"]) < 1e-15

def test_central_impact_equals_rigid():
    """Head-on central impact of non-spinning spheres: point capture == rigid lock."""
    Isph = np.eye(3) * 0.01
    bodies = [{"m": 3.0, "I": Isph, "r": np.zeros(3), "v": np.array([0.04, 0, 0]), "w": np.zeros(3)},
              {"m": 9.0, "I": Isph, "r": np.array([1.0, 0, 0]), "v": np.zeros(3), "w": np.zeros(3)}]
    out = rigidize_point_contact(bodies, np.array([0.5, 0.0, 0.0]))
    rg = rigidize(bodies)
    assert abs(out["dT"] - rg["dT"]) / rg["dT"] < 1e-12

def test_project_scenario_point_vs_rigid():
    """Debris nominal: point capture must transfer LESS |dw| to the chaser than rigid lock."""
    bodies, meta = build_capture_scenario("target_debris_v0", 3.0, 0.01)
    p = meta["r_g"]
    out = rigidize_point_contact(bodies, p)
    rg = rigidize(bodies)
    dw_point = np.linalg.norm(out["impulses"][0]["dw"])
    dw_rigid = np.linalg.norm(rg["impulses"][0]["dw"])
    assert out["dT"] <= rg["dT"]
    assert dw_point > 0 and dw_rigid > 0
    return {"dw_chaser_point": dw_point, "dw_chaser_rigid": dw_rigid,
            "dT_point": out["dT"], "dT_rigid": rg["dT"]}
