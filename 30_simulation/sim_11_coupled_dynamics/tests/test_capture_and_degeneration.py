"""捕获冲量刚性极限 vs sim_06 + 短窗退化/守恒动力学测试（快速版；
完整 12 s/40 s 场景与五项 Gate 由 src/run_gates.py 机器裁决）。"""
import numpy as np

from coupled_dynamics import CoupledModel, JointTrajectory
from capture_solver import (solve_capture, target_state_in_S, chaser_composite)
from capture_impulse import rigidize, rigidize_point_contact, junction_couple

TH = np.deg2rad([0.0, 60.0, -40.0, 0.0, 0.0, 0.0])


def test_capture_rigid_limit_vs_sim06_rigidize():
    """帆板刚化 + 关节抱闸时，柔性 Delassus 求解 == sim_06 rigidize（机器精度）。"""
    mdl = CoupledModel(rigid_panels=True)
    eta = np.zeros(0)
    f = mdl.arm.fk(TH)
    zE = f["T_E"][:3, 2]
    u_pre = np.zeros(mdl.nu)
    u_pre[0:3] = 0.01 * zE
    tgt = target_state_in_S(mdl, np.zeros(3), np.array([1.0, 0, 0, 0]), TH,
                            "target_debris_v0", 3.0)
    res = solve_capture(mdl, TH, eta, u_pre, tgt, mode="rigid_lock_6dof")
    m_c, c_c, I_c = chaser_composite(mdl, TH, eta)
    bodies = [{"m": m_c, "I": I_c, "r": c_c, "v": 0.01 * zE, "w": np.zeros(3)},
              {"m": tgt["m"], "I": tgt["I_S"], "r": tgt["c_S"],
               "v": tgt["v_S"], "w": tgt["w_S"]}]
    ref = rigidize(bodies)
    dw_c = res["dVb"][3:6]
    dv_c = res["dVb"][0:3] + np.cross(dw_c, c_c)
    J_ref, L_ref = junction_couple(ref, bodies, 0, res["pE_S"])
    worst = max(
        float(np.max(np.abs(dv_c - ref["impulses"][0]["dv"]))),
        float(np.max(np.abs(dw_c - ref["impulses"][0]["dw"]))),
        float(np.max(np.abs(res["target_dv_S"] - ref["impulses"][1]["dv"]))),
        float(np.max(np.abs(res["target_dw_S"] - ref["impulses"][1]["dw"]))),
        float(np.max(np.abs(res["lambda_J_S"] - J_ref))),
        float(np.max(np.abs(res["lambda_L_S"] - L_ref))),
        abs(res["dT_J"] - ref["dT"]) / ref["dT"],
    )
    assert worst < 1e-12, worst
    assert float(np.max(np.abs(res["momentum_residual"]))) < 1e-12
    assert float(np.max(np.abs(res["rel_post"]))) < 1e-12
    assert res["dT_J"] >= 0.0
    # 3DOF 点捕获同理
    res3 = solve_capture(mdl, TH, eta, u_pre, tgt, mode="point_capture_3dof")
    ref3 = rigidize_point_contact(bodies, res["pE_S"])
    worst3 = max(
        float(np.max(np.abs(res3["lambda_J_S"] - ref3["J"]))),
        abs(res3["dT_J"] - ref3["dT"]) / max(ref3["dT"], 1e-30))
    assert worst3 < 1e-10, worst3
    assert float(np.max(np.abs(res3["rel_post"][:3]))) < 1e-12
    assert float(np.linalg.norm(res3["rel_post"][3:])) > 0.0  # 未约束角速度，不是求解残差
    return worst


def test_capture_flexible_conserves_momentum_and_dissipates():
    mdl = CoupledModel()
    eta = np.zeros(2 * mdl.n_modes)
    f = mdl.arm.fk(TH)
    u_pre = np.zeros(mdl.nu)
    u_pre[0:3] = 0.01 * f["T_E"][:3, 2]
    tgt = target_state_in_S(mdl, np.zeros(3), np.array([1.0, 0, 0, 0]), TH,
                            "target_debris_v0", 3.0)
    res = solve_capture(mdl, TH, eta, u_pre, tgt, mode="rigid_lock_6dof")
    assert float(np.max(np.abs(res["momentum_residual"]))) < 1e-12
    assert float(np.max(np.abs(res["rel_post"]))) < 1e-12
    assert res["dT_J"] >= 0.0
    assert res["modal_velocity_kick_energy_J"] > 0.0
    return float(np.max(np.abs(res["momentum_residual"])))


def test_short_window_momentum_and_energy():
    """2.5 s 短窗（快跑）：约简模式动量机器精度 + 无阻尼能量审计 <1e-8。
    完整 12 s 版本见 run_gates.py G1/G2。"""
    mdl = CoupledModel(zeta=0.0)
    traj = JointTrajectory(np.zeros(6), np.deg2rad([0, 45, -30, 0, 0, 0]), 2.0)
    res = mdl.integrate_reduced(traj, 2.5, method="Radau", rtol=1e-10, atol=1e-12,
                                n_out=26)
    dh = float(np.max(np.abs(res["h_I"] - res["h_I"][0])))
    assert dh < 1e-12, dh
    audit = np.abs(res["W_joint"] - (res["E"] - res["E"][0]) - res["E_damp"])
    scale = max(float(np.max(np.abs(res["W_joint"]))), float(np.max(res["E"])))
    rel = float(np.max(audit) / scale)
    assert rel < 1e-8, rel
    return max(dh, rel)


def test_short_window_full_vs_reduced():
    """全量模式 vs 约简模式互证（同一方程两条积分路径）+ 全量模式动量漂移。"""
    mdl = CoupledModel(zeta=0.0)
    traj = JointTrajectory(np.zeros(6), np.deg2rad([0, 45, -30, 0, 0, 0]), 2.0)
    r1 = mdl.integrate_reduced(traj, 2.5, method="Radau", rtol=1e-10, atol=1e-12, n_out=26)
    r2 = mdl.integrate_full(traj, 2.5, method="Radau", rtol=1e-10, atol=1e-12, n_out=26)
    dev = float(np.max(np.abs(r1["dev_angle_deg"] - r2["dev_angle_deg"])))
    deta = float(np.max(np.abs(r1["eta"] - r2["eta"])))
    dhf = float(np.max(np.abs(r2["h_I"] - r2["h_I"][0])))
    assert dev < 1e-8, dev
    assert deta < 1e-10, deta
    assert dhf < 1e-10, dhf
    return max(dev, deta, dhf)


def test_rigidized_short_trajectory_matches_sim05():
    """帆板刚化 + 同轨迹：与 sim_05 动力学逐点姿态一致（差 = CSV 舍入量级）。"""
    import sys, os
    sys.path.insert(0, os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "sim_05_free_floating_arm")))
    from dynamics import FreeFloatingB601
    from coupled_dynamics import quintic
    q1 = np.deg2rad([0.0, 60.0, -40.0, 0.0, 0.0, 0.0])
    traj = JointTrajectory(np.zeros(6), q1, 2.0)
    mdl = CoupledModel(rigid_panels=True)
    r11 = mdl.integrate_reduced(traj, 2.5, method="Radau", rtol=1e-11, atol=1e-13, n_out=26)
    dyn5 = FreeFloatingB601()
    r5 = dyn5.integrate_trajectory(lambda t: quintic(t, 2.0, np.zeros(6), q1)[0],
                                   lambda t: quintic(t, 2.0, np.zeros(6), q1)[1],
                                   t_end=2.5, n_out=26)
    err = float(np.max(np.abs(r11["dev_angle_deg"] - r5["dev_angle_deg"])))
    assert err < 1e-4, err        # 残差源：质量分割 CSV 7 位小数舍入
    return err
