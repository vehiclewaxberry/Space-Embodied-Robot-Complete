"""scene_a2_capture.py -- 场景 A2：A1 末态叠加 sim_06 矢量式捕获冲量（150 kg 碎片 @3°/s）。

流程（参数全部来自 20_engineering/config/coupled_scene/scene_A2_capture.yaml）：
  1. 复跑场景 A1 至末态（柔性、约简模式）；
  2. 叠加沿工具轴 +z_E 的接近速度 v_app（整星平动）；
  3. 按 sim_06 约定放置 target_debris_v0（抓点与 E 重合、翻滚 3°/s），
     解 rigid_lock_6dof 柔性 Delassus 捕获冲量（对比案 point_capture_3dof 只解冲量）；
  4. 目标并入组合体（关节抱闸），以捕获后常动量 h_I 约简积分 t_post；
  5. 输出帆板振铃、基座姿态/角速度、整星动量按体组（base/arm/panels/target）
     对系统质心的重分配时程。
CLI 覆写（Gate 用）：--rtol --method --n-modes --zeta --t-post --tag --no-plot
"""
import argparse
import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from config_loader import load_scene, REPO                    # noqa: E402
from coupled_dynamics import CoupledModel, HoldTrajectory     # noqa: E402
from capture_solver import (solve_capture, target_state_in_S,  # noqa: E402
                            chaser_composite)
from contact_window import run_contact_window                  # noqa: E402
from scene_a1_arm_slew import run_scene_a1                    # noqa: E402
from rigid_body import q_to_R                                  # noqa: E402

RES = os.path.normpath(os.path.join(HERE, "..", "results"))
SCENE_YAML = os.path.join("config", "coupled_scene", "scene_A2_capture.yaml")


def run_scene_a2(rtol=None, method=None, n_modes=None, zeta=None, t_post=None,
                 n_out=None, contact_ms=None):
    scene_bundle = load_scene(SCENE_YAML)
    scene, cfg = scene_bundle["scene"], scene_bundle["cfg"]
    cap = scene["capture"]
    integ = cfg["integrator"]
    supported_modes = cfg["capture_interface"]["constraint_modes"]
    for field in ("constraint_mode", "secondary_mode"):
        if cap[field] not in supported_modes:
            raise ValueError(f"A2 {field} 未在 capture_interface SSOT 中定义: {cap[field]}")
    if cap.get("tumble_axis_convention") != "sim_common":
        raise ValueError("A2 当前只支持 sim_common 翻滚轴约定")
    if not cap.get("joints_locked_at_capture", False):
        raise ValueError("A2 当前冲量求解契约要求捕获瞬间关节抱闸")
    if not cap.get("attach_target_after_capture", False):
        raise ValueError("A2 当前捕获后积分契约要求目标并入组合体")

    # ---- 1. A1 末态（同一参数卡链路复跑） ------------------------------------
    resA1, metaA1, model = run_scene_a1(n_modes=n_modes, zeta=zeta,
                                        rtol=rtol, method=method,
                                        scene_path=scene_bundle["base_scene_path"])
    th_f = np.deg2rad(metaA1["scene"]["trajectory"]["q_end_deg"])
    r0 = resA1["r"][-1]
    quat0 = resA1["Q"][-1]
    eta0 = resA1["eta"][-1].copy()
    etad0 = resA1["etad"][-1].copy()
    u_end = np.concatenate([resA1["Vb"][-1], np.zeros(6), etad0])

    # ---- 2. 叠加接近速度 v_app（沿工具轴 +z_E，S 系） -------------------------
    f = model.arm.fk(th_f)
    zE = f["T_E"][:3, 2]
    v_app = float(cap["v_app_m_s"])
    u_pre = u_end.copy()
    u_pre[0:3] += v_app * zE

    # ---- 3. 捕获冲量（主案 6DOF + 对比案 3DOF） ------------------------------
    target = target_state_in_S(model, r0, quat0, th_f,
                               cap["target_object_id"], float(cap["tumble_dps"]))
    cap6 = solve_capture(model, th_f, eta0, u_pre, target, mode=cap["constraint_mode"])
    cap3 = solve_capture(model, th_f, eta0, u_pre, target, mode=cap["secondary_mode"])

    method_eff = integ["method"] if method is None else method
    rtol_eff = float(integ["rtol"]) if rtol is None else float(rtol)
    atol_eff = float(integ["atol"])

    # ---- 3b. 可选：有限接触带宽窗（sim_11 v1.1 分支 B） -----------------------
    window = None
    if contact_ms is not None:
        cw = scene.get("contact")
        if cw is None:
            raise ValueError("--contact-ms 需要 scene_A2_capture.yaml 提供 contact 段")
        if cw["model"] != "half_sine_equal_impulse":
            raise ValueError(f"未实现的接触模型: {cw['model']}")
        lam = np.concatenate([cap6["lambda_J_S"], cap6["lambda_L_S"]])
        window = run_contact_window(
            model, th_f, r0, quat0, eta0, u_pre, target, lam,
            T_c_s=float(contact_ms) * 1e-3, method=method_eff,
            rtol=rtol_eff, atol=atol_eff,
            n_out=int(cw["window_n_out"]),
            lockup=bool(cw["lockup_after_window"]),
            mode=cap["constraint_mode"])
        # 窗末状态取代瞬时跳变态作为捕获后初态
        u_post = window["u_post"]
        r_att, quat_att = window["r_Tc"], window["quat_Tc"]
        eta_att = window["eta_Tc"]
        tgt_att = window["target_Tc"]
        v_t_post_S, w_t_post_S = (window["target_post"]["v_S"],
                                  window["target_post"]["w_S"])
    else:
        u_post = cap6["u_post"]
        r_att, quat_att, eta_att = r0, quat0, eta0
        tgt_att = target
        v_t_post_S, w_t_post_S = cap6["target_v_post_S"], cap6["target_w_post_S"]

    # ---- 4. 目标并入 + 捕获后常动量 ------------------------------------------
    model.attach_target(tgt_att["m"], tgt_att["I_S"], tgt_att["c_S"], th_f)
    h_post = model.momentum_inertial(r_att, quat_att, th_f, eta_att, u_post)
    # 一致性：并入路径动量 = 分体路径动量（机器精度）
    R0 = q_to_R(quat_att / np.linalg.norm(quat_att)).as_matrix()
    model.detach_target()
    h_chaser = model.momentum_inertial(r_att, quat_att, th_f, eta_att, u_post)
    model.attach_target(tgt_att["m"], tgt_att["I_S"], tgt_att["c_S"], th_f)
    v_t_I = R0 @ v_t_post_S
    w_t_I = R0 @ w_t_post_S
    r_t_I = r_att + R0 @ tgt_att["c_S"]
    I_t_I = R0 @ tgt_att["I_S"] @ R0.T
    h_target = np.concatenate([tgt_att["m"] * v_t_I,
                               I_t_I @ w_t_I + tgt_att["m"] * np.cross(r_t_I, v_t_I)])
    attach_residual = float(np.max(np.abs(h_post - h_chaser - h_target)))

    t_post = float(scene["post"]["t_post_s"]) if t_post is None else float(t_post)
    kw = dict(method=method_eff, rtol=rtol_eff, atol=atol_eff,
              n_out=int(scene["post"]["n_out"]) if n_out is None else int(n_out))
    traj_hold = HoldTrajectory(th_f)
    res = model.integrate_reduced(traj_hold, t_post, r0=r_att, quat0=quat_att,
                                  eta0=eta_att + 0.0, etad0=u_post[model.i_e],
                                  h_I=h_post, **kw)

    meta = {"scene": scene, "cfg": cfg, "model": model, "traj": traj_hold,
            "th_f": th_f, "cap6": cap6, "cap3": cap3, "target": target,
            "h_post": h_post, "attach_residual": attach_residual,
            "u_pre": u_pre, "u_post": u_post, "r0": r0, "quat0": quat0,
            "eta0": eta0, "etad0": etad0, "resA1": resA1,
            "window": window, "contact_ms": contact_ms,
            "method": kw["method"], "rtol": kw["rtol"], "t_post": t_post,
            "zeta": model.panels[0].zeta, "n_modes": model.n_modes,
            "base_scene_id": scene_bundle["base_scene"]["scene_id"],
            "base_scene_path": scene_bundle["base_scene_path"]}
    return res, meta, model


def group_momentum_series(res, meta, model):
    """各体组对系统质心的角动量模时程（动量重分配诊断）。"""
    th_f = meta["th_f"]
    t = res["t"]
    n = len(t)
    names = ("base", "arm", "panels", "target")
    Lmag = {g: np.zeros(n) for g in names}
    Ltot = np.zeros(n)
    for i in range(n):
        r_b, quat = res["r"][i], res["Q"][i]
        eta = res["eta"][i]
        u = np.concatenate([res["Vb"][i], np.zeros(6), res["etad"][i]])
        groups = model.momentum_inertial_groups(r_b, quat, th_f, eta, u)
        R = q_to_R(quat / np.linalg.norm(quat)).as_matrix()
        m_c, c_S, _ = chaser_composite(model, th_f, eta)
        r_com = r_b + R @ c_S
        Lsum = np.zeros(3)
        for g in names:
            P, L = groups[g][:3], groups[g][3:]
            L_com = L - np.cross(r_com, P)
            Lmag[g][i] = np.linalg.norm(L_com)
            Lsum += L_com
        Ltot[i] = np.linalg.norm(Lsum)
    return Lmag, Ltot


def dominant_frequency(t, x):
    dt = t[1] - t[0]
    w = np.hanning(len(x))
    X = np.abs(np.fft.rfft((x - x.mean()) * w, n=8 * len(x)))
    fr = np.fft.rfftfreq(8 * len(x), dt)
    k = int(np.argmax(X[1:]) + 1)
    if 1 <= k < len(X) - 1:
        de = 0.5 * (X[k - 1] - X[k + 1]) / (X[k - 1] - 2 * X[k] + X[k + 1] + 1e-300)
        return float(fr[k] + de * (fr[1] - fr[0]))
    return float(fr[k])


def summarize(res, meta, model, Lmag, Ltot):
    cap6, cap3 = meta["cap6"], meta["cap3"]
    t = res["t"]
    dh = np.abs(res["h_I"] - res["h_I"][0])
    m = model.n_modes
    wb = res["Vb"][:, 3:6]
    modal_energy = (
        0.5 * np.einsum("ij,ij->i", res["etad"], res["etad"])
        + 0.5 * np.einsum("ij,jk,ik->i", res["eta"], model.K_eta, res["eta"])
    ) if m else np.zeros_like(t)
    audit = np.abs(res["W_joint"] - (res["E"] - res["E"][0]) - res["E_damp"])
    audit_scale = max(float(np.max(np.abs(res["W_joint"]))),
                      float(np.max(np.abs(res["E"]))),
                      float(np.max(np.abs(res["E_damp"]))), 1e-300)

    def _cap_dict(c):
        constrained_dof = 6 if c["mode"] == "rigid_lock_6dof" else 3
        return {
            "J_impulse_S_Ns": np.round(c["lambda_J_S"], 8).tolist(),
            "L_couple_S_Nms": np.round(c["lambda_L_S"], 8).tolist(),
            "|J|_Ns": float(np.linalg.norm(c["lambda_J_S"])),
            "|L|_Nms": float(np.linalg.norm(c["lambda_L_S"])),
            "dT_J": c["dT_J"],
            "modal_velocity_kick_energy_J": c["modal_velocity_kick_energy_J"],
            "modal_energy_change_J": c["modal_energy_change_J"],
            "base_dw_S_rad_s": np.round(c["dVb"][3:6], 8).tolist(),
            "momentum_residual_max": float(np.max(np.abs(c["momentum_residual"]))),
            "constraint_residual_max": float(
                np.max(np.abs(c["rel_post"][:constrained_dof]))),
            "unconstrained_angular_mismatch_rad_s": (
                float(np.linalg.norm(c["rel_post"][3:])) if constrained_dof == 3 else 0.0
            ),
        }
    win = meta.get("window")
    contact_block = None
    if win is not None:
        w_modal_peak = float(np.max(win["modal_energy_J"])) if m else 0.0
        contact_block = {
            "model": meta["scene"]["contact"]["model"],
            "T_c_ms": float(meta["contact_ms"]),
            "T_c_ms_is_provisional": True,
            "window_modal_energy_peak_J": w_modal_peak,
            "window_tip_L_peak_mm": float(np.max(np.abs(win["tip_L_m"])) * 1e3),
            "window_tip_R_peak_mm": float(np.max(np.abs(win["tip_R_m"])) * 1e3),
            "window_base_rate_peak_dps": float(
                np.max(np.linalg.norm(win["Vb"][:, 3:6], axis=1)) * 180 / np.pi),
            "window_momentum_drift_max": win["momentum_drift_max_abs"],
            "window_energy_audit_rel": win["energy_audit_rel"],
            "lockup_dJ_Ns": win.get("lockup_dJ_Ns"),
            "lockup_dL_Nms": win.get("lockup_dL_Nms"),
            "lockup_rel_to_lam": win.get("lockup_rel_to_lam"),
            "window_nfev": win["nfev"],
        }
    return {
        "scene_id": meta["scene"]["scene_id"],
        "base_scene_id": meta["base_scene_id"],
        "base_scene_path": os.path.relpath(meta["base_scene_path"], REPO),
        "method": meta["method"], "rtol": meta["rtol"],
        "n_modes_per_panel": m, "zeta_modal": meta["zeta"],
        "PROVISIONAL_PARAMS": bool(model.cfg["provisional"]),
        "target": {"id": meta["target"]["id"], "mass_kg": meta["target"]["m"],
                   "tumble_dps": float(meta["scene"]["capture"]["tumble_dps"]),
                   "v_app_m_s": float(meta["scene"]["capture"]["v_app_m_s"])},
        "capture_6dof": _cap_dict(cap6),
        "capture_3dof_comparison": _cap_dict(cap3),
        "contact": contact_block,
        "combined": None if win is None else {
            "modal_energy_peak_J": max(contact_block["window_modal_energy_peak_J"],
                                       float(np.max(modal_energy))),
            "tip_L_peak_mm": max(contact_block["window_tip_L_peak_mm"],
                                 float(np.max(np.abs(res["tip_L_m"])) * 1e3)),
            "base_rate_peak_dps": max(
                contact_block["window_base_rate_peak_dps"],
                float(np.max(np.linalg.norm(wb, axis=1)) * 180 / np.pi)),
        },
        "attach_momentum_residual": meta["attach_residual"],
        "post": {
            "t_post_s": meta["t_post"],
            "H_total_about_inertial_origin_Nms": float(np.linalg.norm(meta["h_post"][3:])),
            "L_total_about_com_Nms": float(Ltot[0]),
            "P_total_Ns": float(np.linalg.norm(meta["h_post"][:3])),
            "base_rate_peak_dps": float(np.max(np.linalg.norm(wb, axis=1)) * 180 / np.pi),
            "base_rate_final_dps": float(np.linalg.norm(wb[-1]) * 180 / np.pi),
            "base_dev_final_deg": float(res["dev_angle_deg"][-1]),
            "tip_L_peak_mm": float(np.max(np.abs(res["tip_L_m"])) * 1e3),
            "tip_R_peak_mm": float(np.max(np.abs(res["tip_R_m"])) * 1e3),
            "tip_L_dominant_freq_hz": dominant_frequency(t, res["tip_L_m"]),
            "panel_modal_energy_peak_J": float(np.max(modal_energy)),
            "panel_modal_energy_final_J": float(modal_energy[-1]),
            "E_damp_final_J": float(res["E_damp"][-1]),
            "W_joint_final_J": float(res["W_joint"][-1]),
            "energy_audit_rel": float(np.max(audit) / audit_scale),
            "momentum_max_abs_dP": float(np.max(dh[:, :3])),
            "momentum_max_abs_dL": float(np.max(dh[:, 3:])),
            "L_about_com_initial_Nms": {g: float(v[0]) for g, v in Lmag.items()},
            "L_about_com_final_Nms": {g: float(v[-1]) for g, v in Lmag.items()},
            "L_total_check_Nms": [float(Ltot[0]), float(Ltot[-1])],
        },
        "nfev": res["nfev"],
    }


def write_outputs(res, meta, model, summary, Lmag, tag=""):
    os.makedirs(RES, exist_ok=True)
    base = meta["scene"]["output"]
    suffix = f"_{tag}" if tag else ""
    csv_path = os.path.join(RES, base["csv"].replace(".csv", f"{suffix}.csv"))
    m = model.n_modes
    dh = res["h_I"] - res["h_I"][0]
    with open(csv_path, "w", newline="\n", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["t_s", "base_dev_angle_deg",
                     "base_euler_x_deg", "base_euler_y_deg", "base_euler_z_deg",
                     "wb_x_dps", "wb_y_dps", "wb_z_dps",
                     "tip_L_mm", "tip_R_mm",
                     *[f"eta_L{i+1}" for i in range(m)],
                     *[f"eta_R{i+1}" for i in range(m)],
                     "L_base_Nms", "L_arm_Nms", "L_panels_Nms", "L_target_Nms",
                     "E_damp_J", "abs_dP", "abs_dL"])
        for i, t in enumerate(res["t"]):
            wr.writerow([f"{t:.4f}", f"{res['dev_angle_deg'][i]:.6f}",
                         *(f"{v:.6f}" for v in res["euler_xyz_deg"][i]),
                         *(f"{np.rad2deg(v):.6f}" for v in res["Vb"][i, 3:6]),
                         f"{res['tip_L_m'][i]*1e3:.6f}", f"{res['tip_R_m'][i]*1e3:.6f}",
                         *(f"{v:.8e}" for v in res["eta"][i]),
                         f"{Lmag['base'][i]:.8e}", f"{Lmag['arm'][i]:.8e}",
                         f"{Lmag['panels'][i]:.8e}", f"{Lmag['target'][i]:.8e}",
                         f"{res['E_damp'][i]:.8e}",
                         f"{np.max(np.abs(dh[i, :3])):.3e}",
                         f"{np.max(np.abs(dh[i, 3:])):.3e}"])
    summary["csv"] = os.path.relpath(csv_path, REPO)
    json_path = os.path.join(RES, base["summary_json"].replace(".json", f"{suffix}.json"))
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    return csv_path, json_path


def plot(res, meta, summary, Lmag, tag=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    base = meta["scene"]["output"]
    suffix = f"_{tag}" if tag else ""
    png = os.path.join(RES, base["png"].replace(".png", f"{suffix}.png"))
    t = res["t"]
    fig, ax = plt.subplots(3, 1, figsize=(10, 11), sharex=True)
    ax[0].plot(t, res["tip_L_m"] * 1e3, lw=0.8, label="panel L tip")
    ax[0].plot(t, res["tip_R_m"] * 1e3, lw=0.8, label="panel R tip")
    ax[0].set_ylabel("tip deflection [mm]")
    c6 = summary["capture_6dof"]
    ax[0].set_title("sim_11 A2 capture ringing & momentum redistribution "
                    f"({summary['target']['id']} @{summary['target']['tumble_dps']} deg/s)\n"
                    f"|J|={c6['|J|_Ns']:.4f} N·s, |L|={c6['|L|_Nms']:.4f} N·m·s, "
                    f"dT={c6['dT_J']*1e3:.2f} mJ, "
                    f"modal ΔE={c6['modal_energy_change_J']*1e3:.3f} mJ")
    ax[0].legend(loc="upper right")
    wb = np.linalg.norm(res["Vb"][:, 3:6], axis=1) * 180 / np.pi
    ax[1].plot(t, wb, "C3", label="|w_base| [deg/s]")
    ax[1].plot(t, res["dev_angle_deg"], "k--", lw=1.2, label="base dev angle [deg]")
    ax[1].set_ylabel("rate / angle")
    ax[1].legend(loc="center right")
    for g, cc in zip(("base", "arm", "panels", "target"), ("C0", "C1", "C2", "C4")):
        ax[2].semilogy(t, np.maximum(Lmag[g], 1e-16), cc, lw=0.9, label=f"|L_{g}|")
    ax[2].axhline(summary["post"]["L_total_about_com_Nms"], color="k", ls=":",
                  label=f"|L_total,CoM|={summary['post']['L_total_about_com_Nms']:.3f} N·m·s")
    ax[2].set_ylabel("|L| about system CoM [N·m·s]")
    ax[2].set_xlabel("time [s]")
    ax[2].legend(loc="center right", fontsize=8)
    for a in ax:
        a.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(png, dpi=130)
    plt.close(fig)
    return png


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rtol", type=float, default=None)
    ap.add_argument("--method", default=None)
    ap.add_argument("--n-modes", type=int, default=None)
    ap.add_argument("--zeta", type=float, default=None)
    ap.add_argument("--t-post", type=float, default=None)
    ap.add_argument("--n-out", type=int, default=None)
    ap.add_argument("--contact-ms", type=float, default=None,
                    help="有限接触带宽 T_c [ms]（不给=瞬时冲量旧口径）")
    ap.add_argument("--tag", default="")
    ap.add_argument("--no-plot", action="store_true")
    a = ap.parse_args()
    res, meta, model = run_scene_a2(rtol=a.rtol, method=a.method, n_modes=a.n_modes,
                                    zeta=a.zeta, t_post=a.t_post, n_out=a.n_out,
                                    contact_ms=a.contact_ms)
    Lmag, Ltot = group_momentum_series(res, meta, model)
    summary = summarize(res, meta, model, Lmag, Ltot)
    csv_path, json_path = write_outputs(res, meta, model, summary, Lmag, tag=a.tag)
    if not a.no_plot:
        summary["png"] = os.path.relpath(plot(res, meta, summary, Lmag, tag=a.tag), REPO)
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    main()
