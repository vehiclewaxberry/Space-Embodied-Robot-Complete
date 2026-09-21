"""Inertial sanity for every merged/composite body: mass > 0, inertia symmetric
positive definite, principal moments satisfy the triangle inequality."""
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SIM05 = os.path.dirname(HERE)
sys.path.insert(0, SIM05)

from b601_model import B601Arm, CHAIN_LINKS  # noqa: E402
from dynamics import build_base_composite    # noqa: E402


def _all_bodies():
    arm = B601Arm()
    bodies = [("base_composite_25p2", build_base_composite()["mass"],
               build_base_composite()["I"])]
    for ln in CHAIN_LINKS:  # base_link, link1..link6 (link6 = gripper composite)
        b = arm.body[ln]
        bodies.append((ln, b["mass"], b["I"]))
    return bodies


def test_mass_positive():
    worst = np.inf
    for name, m, _ in _all_bodies():
        assert m > 0.0, "%s mass %g <= 0" % (name, m)
        worst = min(worst, m)
    return worst  # smallest mass (must be > 0)


def test_inertia_symmetric():
    worst = 0.0
    for name, _, I in _all_bodies():
        r = float(np.max(np.abs(I - I.T)))
        worst = max(worst, r)
        assert r < 1e-12, "%s inertia asymmetry %g" % (name, r)
    return worst


def test_inertia_positive_definite():
    worst = np.inf
    for name, _, I in _all_bodies():
        lam = np.linalg.eigvalsh(0.5 * (I + I.T))
        worst = min(worst, float(lam[0]))
        assert lam[0] > 0.0, "%s inertia not PD, eig=%s" % (name, lam)
    return worst  # smallest eigenvalue (must be > 0)


def test_triangle_inequality():
    """For principal moments l1<=l2<=l3: l1 + l2 >= l3 (physical body)."""
    worst = np.inf
    for name, _, I in _all_bodies():
        l1, l2, l3 = np.linalg.eigvalsh(0.5 * (I + I.T))
        margin = float(l1 + l2 - l3)
        worst = min(worst, margin)
        assert margin > -1e-15, "%s violates triangle inequality by %g (%g,%g,%g)" \
            % (name, -margin, l1, l2, l3)
    return worst  # smallest (l1+l2-l3) margin


if __name__ == "__main__":
    for fn in [test_mass_positive, test_inertia_symmetric,
               test_inertia_positive_definite, test_triangle_inequality]:
        print("%s: PASS (worst=%.3e)" % (fn.__name__, fn()))
