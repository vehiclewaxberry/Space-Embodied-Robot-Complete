"""Eight limiting cases with closed-form expectations. These expose sign, frame,
parallel-axis, and inertia-rotation errors directly."""
import numpy as np
from _helpers import rigidize, random_bodies, random_spd_inertia, RNG
from capture_impulse import capture_post_state

TOL = 1e-10

def test_1_coincident_coms():
    """Both CoMs at the same point: no Steiner, no r x mv; w+ = (I1+I2)^-1 (I1w1+I2w2)."""
    I1, I2 = random_spd_inertia(RNG), random_spd_inertia(RNG)
    w1, w2 = np.array([0.1, -0.05, 0.02]), np.array([-0.03, 0.08, 0.06])
    bodies = [{"m": 5.0, "I": I1, "r": np.zeros(3), "v": np.zeros(3), "w": w1},
              {"m": 7.0, "I": I2, "r": np.zeros(3), "v": np.zeros(3), "w": w2}]
    r = rigidize(bodies)
    expect = np.linalg.solve(I1 + I2, I1 @ w1 + I2 @ w2)
    assert np.linalg.norm(r["w_plus"] - expect) < TOL

def test_2_zero_relative_translation():
    """All bodies translationally at rest: H reduces to sum(I w) about combined CoM."""
    bodies = random_bodies(RNG, n=3)
    for b in bodies:
        b["v"] = np.zeros(3)
    r = rigidize(bodies)
    m = np.array([b["m"] for b in bodies]); rr = np.array([b["r"] for b in bodies])
    r_com = (m[:, None] * rr).sum(axis=0) / m.sum()
    H = sum(np.asarray(b["I"]) @ b["w"] for b in bodies)          # v_i - v_com = 0 exactly? no:
    # v_com = 0 here since all v = 0, so the linear part vanishes exactly.
    expect = np.linalg.solve(r["I_comb"], H)
    assert np.linalg.norm(r["w_plus"] - expect) < TOL
    assert np.linalg.norm(r["v_com"]) == 0.0

def test_3_target_mass_to_zero():
    """Vanishing second body: combined motion -> first body's motion, dT -> 0."""
    b1 = {"m": 20.0, "I": random_spd_inertia(RNG), "r": np.zeros(3),
          "v": np.array([0.01, 0.0, 0.0]), "w": np.array([0.02, 0.05, -0.01])}
    b2 = {"m": 1e-9, "I": np.eye(3) * 1e-12, "r": np.array([1.0, 0.5, 0.0]),
          "v": np.array([-0.05, 0.02, 0.0]), "w": np.array([0.5, -0.2, 0.1])}
    r = rigidize([b1, b2])
    assert np.linalg.norm(r["w_plus"] - b1["w"]) / np.linalg.norm(b1["w"]) < 1e-6
    assert r["dT"] < 1e-9 and r["dT"] >= 0.0

def test_4_central_plastic_impact():
    """Head-on central impact of two non-spinning spheres: w+ = 0, dT = 0.5*mu*v_rel^2."""
    m1, m2, u = 3.0, 9.0, 0.04
    Isph = np.eye(3) * 0.01
    bodies = [{"m": m1, "I": Isph, "r": np.zeros(3), "v": np.array([u, 0, 0]), "w": np.zeros(3)},
              {"m": m2, "I": Isph, "r": np.array([1.0, 0, 0]), "v": np.zeros(3), "w": np.zeros(3)}]
    r = rigidize(bodies)
    mu = m1 * m2 / (m1 + m2)
    assert np.linalg.norm(r["w_plus"]) < TOL                       # central: no spin-up
    assert abs(r["dT"] - 0.5 * mu * u**2) / (0.5 * mu * u**2) < 1e-12

def test_5_pure_eccentric_translation():
    """Offset b, speed u, near-point masses: |w+| -> u/b * mu*b^2/(mu*b^2 + I_sum)."""
    m1, m2, u, b = 4.0, 6.0, 0.03, 0.8
    eps = 1e-8
    bodies = [{"m": m1, "I": np.eye(3) * eps, "r": np.zeros(3), "v": np.zeros(3), "w": np.zeros(3)},
              {"m": m2, "I": np.eye(3) * eps, "r": np.array([0.0, b, 0.0]),
               "v": np.array([u, 0.0, 0.0]), "w": np.zeros(3)}]
    r = rigidize(bodies)
    mu = m1 * m2 / (m1 + m2)
    expect = mu * b * u / (mu * b**2 + 2 * eps)                    # |H|/I_zz about com
    assert abs(np.linalg.norm(r["w_plus"]) - expect) / expect < 1e-9
    assert abs(r["w_plus"][2]) > 0 and abs(r["w_plus"][0]) < TOL   # spin about -z only

def test_6_axisymmetric_spin_about_line_of_centers():
    """Spin about the separation axis x: Steiner adds nothing about x; w+ = I2x*w/(I1x+I2x) x̂."""
    I1 = np.diag([0.4, 0.7, 0.7]); I2 = np.diag([2.0, 5.0, 5.0])
    wx = 0.06
    bodies = [{"m": 10.0, "I": I1, "r": np.zeros(3), "v": np.zeros(3), "w": np.zeros(3)},
              {"m": 30.0, "I": I2, "r": np.array([1.5, 0, 0]), "v": np.zeros(3),
               "w": np.array([wx, 0, 0])}]
    r = rigidize(bodies)
    expect = I2[0, 0] * wx / (I1[0, 0] + I2[0, 0])
    assert abs(r["w_plus"][0] - expect) < TOL and np.linalg.norm(r["w_plus"][1:]) < TOL

def test_7_mass_inertia_scaling():
    """All masses & inertias x k: w+ identical, dT scales by k."""
    bodies = random_bodies(RNG, n=2)
    r1 = rigidize(bodies)
    k = 37.0
    scaled = [{**b, "m": b["m"] * k, "I": np.asarray(b["I"]) * k} for b in bodies]
    r2 = rigidize(scaled)
    assert np.linalg.norm(r2["w_plus"] - r1["w_plus"]) / max(np.linalg.norm(r1["w_plus"]), 1e-30) < 1e-11
    assert abs(r2["dT"] - k * r1["dT"]) / max(abs(k * r1["dT"]), 1e-30) < 1e-11

def test_8_velocity_scaling():
    """All velocities & rates x lam: w+ x lam, dT x lam^2 (homogeneity of degree 1/2)."""
    bodies = random_bodies(RNG, n=2)
    r1 = rigidize(bodies)
    lam = 5.0
    scaled = [{**b, "v": np.asarray(b["v"]) * lam, "w": np.asarray(b["w"]) * lam} for b in bodies]
    r2 = rigidize(scaled)
    assert np.linalg.norm(r2["w_plus"] - lam * r1["w_plus"]) / max(lam * np.linalg.norm(r1["w_plus"]), 1e-30) < 1e-11
    assert abs(r2["dT"] - lam**2 * r1["dT"]) / max(abs(lam**2 * r1["dT"]), 1e-30) < 1e-11

def test_9_project_grasp_at_target_com():
    """Project scenario with grasp lever -> 0 and zero tumble: w+ from linear coupling only
    must vanish when the approach line passes through both CoMs (satellite ring grasp)."""
    r, bodies, meta = capture_post_state("target_satellite_v0", 0.0, 0.02, grasp_scale=1e-9)
    # lever ~ 0 -> approach line passes through target CoM AND chaser CoM lies on it (x-axis)
    assert np.rad2deg(np.linalg.norm(r["w_plus"])) < 1e-6
