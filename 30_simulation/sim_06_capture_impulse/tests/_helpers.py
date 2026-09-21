"""Shared helpers for sim_06 verification tests: path setup, deterministic random-body
ensembles (seeded), and the project 40-case scenario grid."""
import os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "common"))
from capture_impulse import rigidize, build_capture_scenario  # noqa: E402

RNG = np.random.default_rng(20260710)   # fixed seed -> deterministic tests

def random_spd_inertia(rng, scale=1.0):
    """Random symmetric positive-definite inertia satisfying triangle inequalities."""
    A = rng.normal(size=(3, 3))
    I = A @ A.T + 3.0 * np.eye(3)
    return I * scale

def random_bodies(rng, n=2, mass_scale=10.0, len_scale=1.0, vel_scale=0.05, rate_scale=0.1):
    return [{"m": float(rng.uniform(0.5, 1.5) * mass_scale),
             "I": random_spd_inertia(rng, mass_scale * len_scale**2 * 0.05),
             "r": rng.normal(scale=len_scale, size=3),
             "v": rng.normal(scale=vel_scale, size=3),
             "w": rng.normal(scale=rate_scale, size=3)} for _ in range(n)]

def scenario_grid():
    """The sim_06 production sweep: 2 targets x 5 tumbles x 4 approach speeds."""
    out = []
    for tid in ["target_debris_v0", "target_satellite_v0"]:
        for tb in [0.5, 1.0, 2.0, 3.0, 5.0]:
            for va in [0.005, 0.01, 0.02, 0.03]:
                bodies, _ = build_capture_scenario(tid, tb, va)
                out.append(((tid, tb, va), bodies))
    return out

def skew(a):
    return np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
