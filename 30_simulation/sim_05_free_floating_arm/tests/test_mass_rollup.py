"""Mass roll-up: total arm mass (with gripper merged) = 4.6956 +/- 0.001 kg,
composite base (servicer_12U_v0 + robot_mount_adapter_v0) = 25.2 kg."""
import os
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SIM05 = os.path.dirname(HERE)
sys.path.insert(0, SIM05)

from b601_model import B601Arm  # noqa: E402
from dynamics import build_base_composite, FreeFloatingB601  # noqa: E402


def test_arm_total_mass():
    arm = B601Arm()
    r = abs(arm.total_mass - 4.6956)
    assert r < 1e-3, "arm total mass %.6f != 4.6956 +/- 0.001" % arm.total_mass
    return r


def test_link6_composite_mass():
    """link6 composite = link6 + gripper_link + gripper_left + gripper_right."""
    arm = B601Arm()
    expect = 0.3663 + 0.181800159145243 + 0.0423278952416158 + 0.0423278949561274
    r = abs(arm.body["link6"]["mass"] - expect)
    assert r < 1e-12, r
    return r


def test_base_composite_mass():
    bc = build_base_composite()
    r = abs(bc["mass"] - 25.2)
    assert r < 1e-9, "composite base mass %.6f != 25.2" % bc["mass"]
    return r


def test_system_total_mass():
    """Whole free-floating system = 25.2 + 4.6956 = 29.8956 kg (per H_bb)."""
    dyn = FreeFloatingB601()
    H_bb, _ = dyn.momentum_matrices(np.zeros(6))
    m_sys = H_bb[0, 0]  # locked-inertia linear block = m_total * I3
    r = abs(m_sys - (25.2 + 4.6956))
    assert r < 1e-3, m_sys
    assert np.allclose(H_bb[:3, :3], m_sys * np.eye(3), atol=1e-12)
    return r


if __name__ == "__main__":
    for fn in [test_arm_total_mass, test_link6_composite_mass,
               test_base_composite_mass, test_system_total_mass]:
        print("%s: PASS (worst=%.3e)" % (fn.__name__, fn()))
