"""FK self-consistency: (a) zero-configuration origin accumulation against an
independent scipy-Rotation chain, (b) EE hand-check values + independent-chain
comparison at typical configurations, (c) Jacobian vs central finite differences.

The independent chain below uses scipy.spatial.transform.Rotation (extrinsic
'xyz' == URDF fixed-axis rpy) and its own Rodrigues-free axis rotation, i.e. a
separate implementation path from b601_model."""
import os
import sys
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation

HERE = os.path.dirname(os.path.abspath(__file__))
SIM05 = os.path.dirname(HERE)
sys.path.insert(0, SIM05)

from b601_model import (B601Arm, URDF_PATH, CHAIN_JOINTS, EE_OFFSET_LINK6,  # noqa: E402
                        T_SM_t, R_SM)

EPS = 1e-7  # central-difference step (spec)


def _urdf_chain():
    """Independent URDF read: [(xyz, rpy, axis), ...] for joint1..joint6 and the
    gripper_joint origin."""
    root = ET.parse(URDF_PATH).getroot()
    jd = {}
    for j in root.findall("joint"):
        o = j.find("origin")
        xyz = np.array([float(v) for v in o.get("xyz").split()])
        rpy = np.array([float(v) for v in (o.get("rpy") or "0 0 0").split()])
        ax = j.find("axis")
        axis = np.array([float(v) for v in ax.get("xyz").split()]) if ax is not None else None
        jd[j.get("name")] = (xyz, rpy, axis)
    return jd


def _indep_fk(q):
    """Independent FK in the A0 (base_link) frame using scipy Rotation only.
    Returns joint origins (6,3), link rotations list, EE pose (R_link6, p_E)."""
    jd = _urdf_chain()
    R = np.eye(3)
    p = np.zeros(3)
    origins = np.zeros((6, 3))
    Rs = []
    for i, name in enumerate(CHAIN_JOINTS):
        xyz, rpy, axis = jd[name]
        p = p + R @ xyz
        R = R @ Rotation.from_euler("xyz", rpy).as_matrix()   # extrinsic XYZ = URDF rpy
        origins[i] = p
        R = R @ Rotation.from_rotvec(q[i] * axis).as_matrix()  # joint rotation
        Rs.append(R.copy())
    p_E = p + R @ EE_OFFSET_LINK6
    return origins, Rs, (R, p_E)


def test_zero_config_origin_accumulation():
    """(a) q=0: model joint origins == direct accumulation of URDF origins."""
    arm = B601Arm()
    q = np.zeros(6)
    f = arm.fk(q, T_base=np.eye(4))
    origins_i, _, (R6_i, pE_i) = _indep_fk(q)
    worst = float(np.max(np.abs(f["joint_origins"] - origins_i)))
    worst = max(worst, float(np.max(np.abs(f["T_E"][:3, 3] - pE_i))))
    worst = max(worst, float(np.max(np.abs(f["T"]["link6"][:3, :3] - R6_i))))
    assert worst < 1e-12, worst
    return worst


def test_ee_hand_values():
    """(b) Hand-checked EE positions. q=0 in A0 (chain arithmetic done by hand
    with Rx(-90), Rx(-180), Ry(+90) blocks): E ~= (0.26031, 0, 0.19170) m.
    S-frame placement: p_S = R_SM @ p_A0 + t_SM -> (0.37695, 0, -0.26031) m."""
    arm = B601Arm()
    q = np.zeros(6)
    pE_A0 = arm.fk(q, T_base=np.eye(4))["T_E"][:3, 3]
    pE_S = arm.fk(q)["T_E"][:3, 3]
    hand_A0 = np.array([0.26031, 0.0, 0.19170])
    r1 = float(np.max(np.abs(pE_A0 - hand_A0)))
    assert r1 < 1e-3, "q=0 EE in A0 %s vs hand %s" % (pE_A0, hand_A0)
    r2 = float(np.max(np.abs(pE_S - (R_SM @ pE_A0 + T_SM_t))))
    assert r2 < 1e-12, r2
    # typical (nonzero) configurations vs the independent scipy chain
    worst = max(r2, 0.0)
    for q in [np.array([0.3, -0.7, -0.5, 0.2, 0.4, -0.6]),
              np.array([-1.0, -1.2, -0.3, 0.9, -0.8, 1.4])]:
        f = arm.fk(q, T_base=np.eye(4))
        origins_i, _, (R6_i, pE_i) = _indep_fk(q)
        r = float(np.max(np.abs(f["T_E"][:3, 3] - pE_i)))
        r = max(r, float(np.max(np.abs(f["T"]["link6"][:3, :3] - R6_i))))
        r = max(r, float(np.max(np.abs(f["joint_origins"] - origins_i))))
        worst = max(worst, r)
        assert r < 1e-12, r
    return max(worst, r1)


def test_jacobian_finite_difference():
    """(c) 6x6 geometric Jacobian vs central differences (eps=1e-7), >=5 random
    configurations, fixed seed; relative Frobenius error < 1e-6."""
    arm = B601Arm()
    rng = np.random.default_rng(42)
    worst = 0.0
    for _ in range(6):
        q = rng.uniform(-1.4, 1.4, 6)
        J = arm.jacobian(q)
        J_fd = np.zeros((6, 6))
        R0 = arm.fk(q)["T_E"][:3, :3]
        for i in range(6):
            qp = q.copy(); qp[i] += EPS
            qm = q.copy(); qm[i] -= EPS
            fp = arm.fk(qp); fm = arm.fk(qm)
            J_fd[:3, i] = (fp["T_E"][:3, 3] - fm["T_E"][:3, 3]) / (2 * EPS)
            dR = (fp["T_E"][:3, :3] - fm["T_E"][:3, :3]) / (2 * EPS)
            W = dR @ R0.T
            W = 0.5 * (W - W.T)
            J_fd[3:, i] = np.array([W[2, 1], W[0, 2], W[1, 0]])
        rel = np.linalg.norm(J_fd - J) / np.linalg.norm(J)
        worst = max(worst, float(rel))
        assert rel < 1e-6, "Jacobian FD relative error %g at q=%s" % (rel, q)
    return worst


if __name__ == "__main__":
    for fn in [test_zero_config_origin_accumulation, test_ee_hand_values,
               test_jacobian_finite_difference]:
        print("%s: PASS (worst=%.3e)" % (fn.__name__, fn()))
