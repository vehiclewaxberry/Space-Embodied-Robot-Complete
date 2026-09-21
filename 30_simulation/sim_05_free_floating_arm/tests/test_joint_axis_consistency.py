"""Joint-axis checks: unit axes, revolute about local z, joint2 axis = -z,
and FK world-axis consistency (a joint's own world axis is invariant to its
own angle)."""
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SIM05 = os.path.dirname(HERE)
sys.path.insert(0, SIM05)

from b601_model import B601Arm  # noqa: E402


def test_axes_local_z():
    """All 6 revolute axes are unit +/-z in the joint frame; joint2 is (0,0,-1),
    all others (0,0,1)."""
    arm = B601Arm()
    worst = 0.0
    for j in arm.joints:
        a = j["axis"]
        worst = max(worst, abs(np.linalg.norm(a) - 1.0))
        assert abs(np.linalg.norm(a) - 1.0) < 1e-12, j["name"]
        expect = np.array([0.0, 0.0, -1.0]) if j["name"] == "joint2" \
            else np.array([0.0, 0.0, 1.0])
        r = float(np.max(np.abs(a - expect)))
        worst = max(worst, r)
        assert r < 1e-12, "%s axis %s != %s" % (j["name"], a, expect)
    return worst


def test_fk_axes_unit():
    """World axes from FK stay unit-norm at random configurations."""
    arm = B601Arm()
    rng = np.random.default_rng(7)
    worst = 0.0
    for _ in range(10):
        q = rng.uniform(-1.5, 1.5, 6)
        ax = arm.fk(q)["joint_axes"]
        r = float(np.max(np.abs(np.linalg.norm(ax, axis=1) - 1.0)))
        worst = max(worst, r)
        assert r < 1e-12, r
    return worst


def test_own_axis_invariant():
    """Rotating joint i must not move joint i's own world axis or origin."""
    arm = B601Arm()
    rng = np.random.default_rng(11)
    worst = 0.0
    for _ in range(5):
        q = rng.uniform(-1.5, 1.5, 6)
        f0 = arm.fk(q)
        for i in range(6):
            q2 = q.copy()
            q2[i] += 0.83
            f2 = arm.fk(q2)
            r = float(np.max(np.abs(f2["joint_axes"][i] - f0["joint_axes"][i])))
            r = max(r, float(np.max(np.abs(f2["joint_origins"][i] - f0["joint_origins"][i]))))
            worst = max(worst, r)
            assert r < 1e-12, "joint%d axis/origin moved by its own angle: %g" % (i + 1, r)
    return worst


if __name__ == "__main__":
    for fn in [test_axes_local_z, test_fk_axes_unit, test_own_axis_invariant]:
        print("%s: PASS (worst=%.3e)" % (fn.__name__, fn()))
