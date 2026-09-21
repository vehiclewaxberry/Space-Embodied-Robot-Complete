"""S00 (unit/frame/inertia invariance) and S01 (accepted-URDF FK/topology).

Every check returns a machine record {check, kind, passed, detail}. Negative
controls PASS when the violation IS detected (fail-closed proof), and the
report keeps positive and negative counts separate.
"""
from __future__ import annotations

import numpy as np

from . import frames, units
from .frames import (
    FrameContractViolation,
    R_to_quat,
    invert_T,
    make_T,
    parallel_axis_about_point,
    quat_normalize,
    quat_to_R,
    rpy_to_R,
)
from .spatial import X_force, X_motion, spatial_inertia, transform_spatial_inertia
from .units import UnitContractViolation, assert_si_plausible_arm_model, scale_model_units
from .urdf_extract import extract_urdf, total_mass, validate_tree


def _rec(check: str, kind: str, passed: bool, detail: str) -> dict:
    return {"check": check, "kind": kind, "passed": bool(passed), "detail": detail}


def assert_joint_limits_plausible_rad(model: dict, margin: float = 1.05) -> None:
    """Revolute limits beyond ~2*pi indicate degrees leaked into the rad channel."""
    cap = 2.0 * np.pi * margin
    for j in model["joints"]:
        if j["type"] == "revolute" and j["limits"] is not None:
            for k in ("lower", "upper"):
                if k in j["limits"] and abs(j["limits"][k]) > cap:
                    raise UnitContractViolation(
                        f"joint {j['name']} limit {k}={j['limits'][k]} rad exceeds {cap:.3f}: suspected degrees"
                    )


def run_s00(arm_model: dict, rng_seed: int = 20260827) -> dict:
    rng = np.random.default_rng(rng_seed)
    R_checks: list[dict] = []

    # ---------- positive checks ----------
    x = np.array([1.2345, -0.5, 7.75])
    R_checks.append(
        _rec("units.mm_m_roundtrip", "positive", bool(np.allclose(units.mm_to_m(units.m_to_mm(x)), x, rtol=0, atol=1e-15)), "m->mm->m exact")
    )
    R_checks.append(
        _rec("units.kg_g_roundtrip", "positive", bool(np.allclose(units.g_to_kg(units.kg_to_g(x)), x, rtol=0, atol=1e-15)), "kg->g->kg exact")
    )
    R_checks.append(
        _rec(
            "units.rad_deg_roundtrip",
            "positive",
            bool(np.allclose(units.deg_to_rad(units.rad_to_deg(x)), x, rtol=1e-15, atol=1e-15)),
            "rad->deg->rad to machine precision",
        )
    )
    R_checks.append(
        _rec(
            "units.inertia_gmm2_kgm2",
            "positive",
            abs(units.inertia_gmm2_to_kgm2(1.0e9) - 1.0) < 1e-15 and abs(units.inertia_kgm2_to_gmm2(1.0) - 1.0e9) < 1e-6,
            "1 kg*m^2 == 1e9 g*mm^2",
        )
    )
    # parallel axis: point-mass analytic case
    m, d = 2.5, 0.7
    I_shift = parallel_axis_about_point(np.zeros((3, 3)), m, [d, 0.0, 0.0])
    ok = abs(I_shift[1, 1] - m * d * d) < 1e-14 and abs(I_shift[2, 2] - m * d * d) < 1e-14 and abs(I_shift[0, 0]) < 1e-14
    R_checks.append(_rec("frames.parallel_axis_point_mass", "positive", ok, "I_perp = m d^2, I_axis = 0"))

    # quaternion / rotation round trips on random rotations
    ok = True
    max_err = 0.0
    for _ in range(50):
        rpy = rng.uniform(-np.pi, np.pi, 3)
        R = rpy_to_R(rpy)
        q = R_to_quat(R)
        err = float(np.max(np.abs(quat_to_R(q) - R)))
        max_err = max(max_err, err)
        ok = ok and err < 1e-12
    R_checks.append(_rec("frames.quat_R_roundtrip_x50", "positive", ok, f"max |R - R(q(R))| = {max_err:.3e}"))

    qn, drift = quat_normalize([2.0, 0.0, 0.0, 0.0])
    R_checks.append(
        _rec("frames.quat_normalization", "positive", abs(np.linalg.norm(qn) - 1.0) < 1e-15 and drift == 1.0, f"norm restored, recorded drift={drift}")
    )

    T = make_T(rpy_to_R([0.3, -0.2, 0.9]), [0.1, -0.5, 0.25])
    err = float(np.max(np.abs(T @ invert_T(T) - np.eye(4))))
    R_checks.append(_rec("frames.transform_inverse", "positive", err < 1e-14, f"|T T^-1 - I| = {err:.3e}"))

    # spatial inertia frame-shift round trip
    I_sp = spatial_inertia(3.2, [0.1, -0.02, 0.05], np.diag([0.02, 0.03, 0.04]))
    T_ab = make_T(rpy_to_R([0.5, 0.1, -0.4]), [0.3, 0.2, -0.1])
    I_back = transform_spatial_inertia(transform_spatial_inertia(I_sp, T_ab), invert_T(T_ab))
    err = float(np.max(np.abs(I_back - I_sp)))
    R_checks.append(_rec("spatial.inertia_shift_roundtrip", "positive", err < 1e-12, f"round-trip error {err:.3e}"))

    # momentum transform consistency: body-frame h vs direct world computation
    mass, com, Icom = 4.0, np.array([0.05, 0.1, -0.02]), np.diag([0.05, 0.06, 0.07])
    R_WB = rpy_to_R([0.2, 0.4, -0.3])
    p_WB = np.array([1.0, -2.0, 0.5])
    omega_B = np.array([0.3, -0.1, 0.2])
    v_B = np.array([0.05, 0.02, -0.04])  # velocity of body origin, body coords
    h_body = spatial_inertia(mass, com, Icom) @ np.concatenate([omega_B, v_B])
    h_world = X_force(make_T(R_WB, p_WB)) @ h_body
    # direct: world-frame CoM velocity and angular momentum about world origin
    omega_W = R_WB @ omega_B
    r_com_W = p_WB + R_WB @ com
    v_com_W = R_WB @ (v_B + np.cross(omega_B, com))
    f_direct = mass * v_com_W
    n_direct = R_WB @ (Icom @ omega_B) + np.cross(r_com_W, f_direct)
    err = float(max(np.max(np.abs(h_world[3:] - f_direct)), np.max(np.abs(h_world[:3] - n_direct))))
    R_checks.append(_rec("spatial.momentum_transform_vs_direct", "positive", err < 1e-12, f"max component error {err:.3e}"))

    # ---------- negative controls (violation MUST be detected) ----------
    def expect_raise(name: str, fn, exc, detail: str):
        try:
            fn()
        except exc as e:
            R_checks.append(_rec(name, "negative", True, f"{detail}; detected: {e}"))
        except Exception as e:  # wrong exception type = not a clean fail-closed path
            R_checks.append(_rec(name, "negative", False, f"wrong exception {type(e).__name__}: {e}"))
        else:
            R_checks.append(_rec(name, "negative", False, f"{detail}; VIOLATION NOT DETECTED"))

    expect_raise(
        "neg.mm_data_in_si_channel",
        lambda: assert_si_plausible_arm_model(scale_model_units(arm_model, 1000.0, 1.0)),
        UnitContractViolation,
        "mm lengths injected as SI",
    )
    expect_raise(
        "neg.gram_masses_in_si_channel",
        lambda: assert_si_plausible_arm_model(scale_model_units(arm_model, 1.0, 1000.0)),
        UnitContractViolation,
        "gram masses injected as SI",
    )
    expect_raise(
        "neg.gmm2_inertia_in_si_channel",
        lambda: assert_si_plausible_arm_model(scale_model_units(arm_model, 1000.0, 1000.0)),
        UnitContractViolation,
        "g*mm^2 inertia injected as SI",
    )

    def _deg_limits():
        import copy

        m2 = copy.deepcopy(arm_model)
        for j in m2["joints"]:
            if j["limits"] is not None and j["type"] == "revolute":
                j["limits"] = {k: units.rad_to_deg(v) if k in ("lower", "upper") else v for k, v in j["limits"].items()}
        assert_joint_limits_plausible_rad(m2)

    expect_raise("neg.deg_limits_in_rad_channel", _deg_limits, UnitContractViolation, "degree limits injected as rad")
    expect_raise(
        "neg.non_rotation_matrix",
        lambda: R_to_quat(np.diag([1.0, 2.0, 1.0])),
        FrameContractViolation,
        "non-orthonormal matrix passed as rotation",
    )
    expect_raise("neg.zero_quaternion", lambda: quat_normalize([0, 0, 0, 0]), FrameContractViolation, "zero quaternion")

    # transform misuse: motion transform applied to a momentum covector must disagree
    h_wrong = X_motion(make_T(R_WB, p_WB)) @ h_body
    mis = float(np.max(np.abs(h_wrong - h_world)))
    R_checks.append(
        _rec("neg.motion_xform_on_momentum_detected", "negative", mis > 1e-3, f"X_motion vs X_force discrepancy {mis:.3e} (must be visible)")
    )
    # composition-order misuse must disagree with the contract order
    T_A_B = make_T(rpy_to_R([0.1, 0.7, -0.2]), [0.4, 0.0, -0.3])
    T_B_C = make_T(rpy_to_R([-0.5, 0.2, 0.3]), [0.0, 0.2, 0.1])
    mis = float(np.max(np.abs(T_A_B @ T_B_C - T_B_C @ T_A_B)))
    R_checks.append(_rec("neg.composition_order_detected", "negative", mis > 1e-6, f"wrong-order composition differs by {mis:.3e}"))

    n_pos = sum(1 for r in R_checks if r["kind"] == "positive")
    n_pos_ok = sum(1 for r in R_checks if r["kind"] == "positive" and r["passed"])
    n_neg = sum(1 for r in R_checks if r["kind"] == "negative")
    n_neg_ok = sum(1 for r in R_checks if r["kind"] == "negative" and r["passed"])
    return {
        "scenario_id": "S00_UNIT_FRAME_INERTIA_INVARIANCE",
        "positive_total": n_pos,
        "positive_passed": n_pos_ok,
        "negative_total": n_neg,
        "negative_passed": n_neg_ok,
        "all_passed": (n_pos_ok == n_pos) and (n_neg_ok == n_neg),
        "checks": R_checks,
        "rng_seed": rng_seed,
    }


EXPECTED_TOPOLOGY = {
    "n_links": 10,
    "n_joints": 9,
    "revolute": 6,
    "fixed": 1,
    "prismatic": 2,
    "root_link": "base_link",
    "movable": ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "gripper_joint1", "gripper_joint2"],
}


def run_s01(urdf_path: str, rng_seed: int = 20260827) -> dict:
    from .plant import FloatingPlant

    rng = np.random.default_rng(rng_seed)
    checks: list[dict] = []
    model = extract_urdf(urdf_path)
    topo = validate_tree(model)

    checks.append(_rec("topology.n_links", "positive", topo["n_links"] == EXPECTED_TOPOLOGY["n_links"], f"{topo['n_links']} links"))
    checks.append(_rec("topology.n_joints", "positive", topo["n_joints"] == EXPECTED_TOPOLOGY["n_joints"], f"{topo['n_joints']} joints"))
    jb = topo["joints_by_type"]
    checks.append(
        _rec(
            "topology.6R_1F_2P",
            "positive",
            jb.get("revolute", 0) == 6 and jb.get("fixed", 0) == 1 and jb.get("prismatic", 0) == 2,
            f"joints_by_type={jb}",
        )
    )
    checks.append(_rec("topology.root", "positive", topo["root_link"] == "base_link", f"root={topo['root_link']}"))
    checks.append(
        _rec("topology.movable_order", "positive", topo["movable_joints"] == EXPECTED_TOPOLOGY["movable"], str(topo["movable_joints"]))
    )
    checks.append(
        _rec(
            "inertial.all_links",
            "positive",
            topo["links_with_inertial"] == topo["n_links"],
            f"{topo['links_with_inertial']}/{topo['n_links']} links carry full inertial",
        )
    )
    mt = total_mass(model)
    checks.append(_rec("inertial.total_mass", "positive", abs(mt - 4.6956) < 5e-4, f"total mass {mt:.6f} kg vs header ~4.695 kg"))
    assert_si_plausible_arm_model(model)
    assert_joint_limits_plausible_rad(model)
    checks.append(_rec("units.si_plausibility", "positive", True, "SI plausibility and rad-limit tripwires passed"))

    # limits present on all movable joints
    movable = [j for j in model["joints"] if j["type"] in ("revolute", "prismatic")]
    ok = all(j["limits"] is not None and "lower" in j["limits"] and "upper" in j["limits"] for j in movable)
    checks.append(_rec("limits.present", "positive", ok, "lower/upper on all 8 movable joints"))

    plant = FloatingPlant(model)
    checks.append(_rec("plant.nj", "positive", plant.nj == 8, f"{plant.nj} movable DOF over floating base"))

    Rb, pb = np.eye(3), np.zeros(3)
    fk0 = plant.fk_links_world(Rb, pb, np.zeros(8))
    p_ee0 = fk0["gripper_link"][:3, 3]
    reach0 = float(np.linalg.norm(p_ee0))
    checks.append(_rec("fk.q0_finite", "positive", bool(np.all(np.isfinite(fk0["gripper_link"]))), f"T_W_gripper at q0 finite, |p|={reach0:.4f} m"))
    checks.append(_rec("fk.q0_reach_plausible", "positive", 0.05 < reach0 < 1.2, f"gripper origin distance {reach0:.4f} m in (0.05, 1.2)"))

    # joint6 axis-invariance: gripper_link origin lies on joint6 axis
    q = np.zeros(8)
    q[5] = 1.1
    p_rot = plant.fk_links_world(Rb, pb, q)["gripper_link"][:3, 3]
    err = float(np.linalg.norm(p_rot - p_ee0))
    checks.append(_rec("fk.joint6_axis_invariance", "positive", err < 1e-12, f"gripper origin motion under joint6 = {err:.3e} m"))

    # independent prismatic fingers
    qL = np.zeros(8)
    qL[6] = 0.05
    fkL = plant.fk_links_world(Rb, pb, qL)
    moved_L = float(np.linalg.norm(fkL["gripper_left"][:3, 3] - fk0["gripper_left"][:3, 3]))
    moved_R = float(np.linalg.norm(fkL["gripper_right"][:3, 3] - fk0["gripper_right"][:3, 3]))
    checks.append(
        _rec("fk.prismatic_independence", "positive", moved_L > 0.049 and moved_R < 1e-12, f"gj1: left moved {moved_L:.4f} m, right moved {moved_R:.3e} m")
    )

    # random interior configurations: finite FK, bounded span
    limits = [(j["limits"]["lower"], j["limits"]["upper"]) for j in movable]
    max_span = 0.0
    ok = True
    for _ in range(25):
        qr = np.array([rng.uniform(lo + 0.05 * (hi - lo), hi - 0.05 * (hi - lo)) for lo, hi in limits])
        fk = plant.fk_links_world(Rb, pb, qr)
        for name, T in fk.items():
            if not np.all(np.isfinite(T)):
                ok = False
            max_span = max(max_span, float(np.linalg.norm(T[:3, 3])))
    checks.append(_rec("fk.random_interior_x25", "positive", ok and max_span < 1.5, f"all finite, max link-origin distance {max_span:.4f} m"))

    n = len(checks)
    n_ok = sum(1 for c in checks if c["passed"])
    return {
        "scenario_id": "S01_ACCEPTED_URDF_FK_TOPOLOGY",
        "urdf_sha256": model["provenance"]["source_sha256"],
        "checks_total": n,
        "checks_passed": n_ok,
        "all_passed": n_ok == n,
        "topology": topo,
        "total_mass_kg": mt,
        "checks": checks,
        "rng_seed": rng_seed,
    }
