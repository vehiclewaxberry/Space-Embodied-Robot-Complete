"""scene_a1_arm_slew.py -- 场景 A1：臂收拢位形 -> 预抓取位形（五次多项式轨迹）。

参数全部来自 20_engineering/config/coupled_scene/scene_A1_arm_slew.yaml（零硬编码）。
输出 results/：CSV 时程 + summary JSON + PNG。
CLI 覆写（Gate 扫掠用，不改参数卡）：
    --rigid-panels          帆板刚化（退化到 sim_05 口径）
    --n-modes N  --zeta Z  --rtol R  --method Radau|BDF|DOP853  --mode reduced|full
    --stiffness-case NAME  --t-end T  --tag SUFFIX（结果文件后缀）  --no-plot
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
from coupled_dynamics import CoupledModel, JointTrajectory    # noqa: E402

RES = os.path.normpath(os.path.join(HERE, "..", "results"))
SCENE_YAML = os.path.join("config", "coupled_scene", "scene_A1_arm_slew.yaml")


def run_scene_a1(rigid_panels=False, n_modes=None, zeta=None, rtol=None, method=None,
                 mode="reduced", stiffness_case=None, t_end=None, n_out=None,
                 scene_path=SCENE_YAML):
    """按参数卡跑 A1，返回 (res, meta, model)。覆写项仅用于 Gate 扫掠。"""
    sc = load_scene(scene_path)
    scene, cfg = sc["scene"], sc["cfg"]
    tr = scene["trajectory"]
    integ = cfg["integrator"]
    model = CoupledModel(cfg=cfg, n_modes=n_modes, rigid_panels=rigid_panels,
                         zeta=zeta, stiffness_case=stiffness_case)
    traj = JointTrajectory(np.deg2rad(tr["q_start_deg"]), np.deg2rad(tr["q_end_deg"]),
                           tr["t_maneuver_s"])
    kw = dict(method=integ["method"] if method is None else method,
              rtol=float(integ["rtol"]) if rtol is None else float(rtol),
              atol=float(integ["atol"]),
              n_out=int(scene["output"]["n_out"]) if n_out is None else int(n_out))
    t_end = float(tr["t_end_s"]) if t_end is None else float(t_end)
    if mode == "reduced":
        res = model.integrate_reduced(traj, t_end, **kw)
    elif mode == "full":
        res = model.integrate_full(traj, t_end, **kw)
    else:
        raise ValueError(mode)
    meta = {"scene": scene, "traj": traj, "t_end": t_end, "mode": mode,
            "method": kw["method"], "rtol": kw["rtol"],
            "n_modes": model.n_modes, "rigid_panels": model.rigid_panels,
            "zeta": model.panels[0].zeta, "stiffness_case": model.stiffness_case}
    return res, meta, model


def summarize(res, meta, model):
    t = res["t"]
    dev = res["dev_angle_deg"]
    dh = np.abs(res["h_I"] - res["h_I"][0])
    audit = np.abs(res["W_joint"] - (res["E"] - res["E"][0]) - res["E_damp"])
    scale = max(float(np.max(np.abs(res["W_joint"]))), float(np.max(res["E"])), 1e-300)
    m = model.n_modes
    out = {
        "scene_id": meta["scene"]["scene_id"],
        "mode": meta["mode"], "method": meta["method"], "rtol": meta["rtol"],
        "n_modes_per_panel": m, "rigid_panels": meta["rigid_panels"],
        "zeta_modal": meta["zeta"], "stiffness_case": meta["stiffness_case"],
        "PROVISIONAL_PARAMS": bool(model.cfg["provisional"] and not meta["rigid_panels"]),
        "peak_base_attitude_deviation_deg": float(np.max(dev)),
        "t_peak_s": float(t[np.argmax(dev)]),
        "final_base_attitude_deviation_deg": float(dev[-1]),
        "final_euler_xyz_deg": [float(v) for v in res["euler_xyz_deg"][-1]],
        "max_base_origin_shift_m": float(np.max(np.linalg.norm(res["r"], axis=1))),
        "tip_L_peak_mm": float(np.max(np.abs(res["tip_L_m"])) * 1e3),
        "tip_R_peak_mm": float(np.max(np.abs(res["tip_R_m"])) * 1e3),
        "panel_modal_energy_final_J": float(
            model.panels[0].modal_energy(res["eta"][-1][:m], res["etad"][-1][:m])
            + model.panels[1].modal_energy(res["eta"][-1][m:], res["etad"][-1][m:]))
            if m else 0.0,
        "momentum_max_abs_dP": float(np.max(dh[:, :3])),
        "momentum_max_abs_dL": float(np.max(dh[:, 3:])),
        "energy_audit_rel": float(np.max(audit) / scale),
        "W_joint_final_J": float(res["W_joint"][-1]),
        "E_damp_final_J": float(res["E_damp"][-1]),
        "nfev": res["nfev"],
    }
    if m:
        thf = np.deg2rad(meta["scene"]["trajectory"]["q_end_deg"])
        Jg = model.generalized_jacobian(thf, res["eta"][-1])
        out["generalized_jacobian_Jstar_at_qf"] = np.round(Jg, 8).tolist()
        out["panel_B_t"] = np.round(model.panels[0].B_t, 8).tolist()
        out["panel_B_r"] = np.round(model.panels[0].B_r, 8).tolist()
        out["panel_f_modes_hz"] = np.round(model.panels[0].f_modes_hz, 6).tolist()
    return out


def write_outputs(res, meta, model, summary, tag=""):
    os.makedirs(RES, exist_ok=True)
    base = meta["scene"]["output"]
    suffix = f"_{tag}" if tag else ""
    csv_path = os.path.join(RES, base["csv"].replace(".csv", f"{suffix}.csv"))
    m = model.n_modes
    with open(csv_path, "w", newline="\n", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        head = ["t_s", "q2_deg", "q3_deg",
                "base_euler_x_deg", "base_euler_y_deg", "base_euler_z_deg",
                "base_dev_angle_deg", "base_pos_x_m", "base_pos_y_m", "base_pos_z_m",
                "tip_L_mm", "tip_R_mm",
                *[f"eta_L{i+1}" for i in range(m)], *[f"eta_R{i+1}" for i in range(m)],
                "W_joint_J", "E_damp_J", "abs_dP", "abs_dL"]
        wr.writerow(head)
        dh = res["h_I"] - res["h_I"][0]
        for i, t in enumerate(res["t"]):
            th, _, _ = meta["traj"](t)
            wr.writerow([f"{t:.4f}", f"{np.rad2deg(th[1]):.5f}", f"{np.rad2deg(th[2]):.5f}",
                         *(f"{v:.6f}" for v in res["euler_xyz_deg"][i]),
                         f"{res['dev_angle_deg'][i]:.6f}",
                         *(f"{v:.7f}" for v in res["r"][i]),
                         f"{res['tip_L_m'][i]*1e3:.6f}", f"{res['tip_R_m'][i]*1e3:.6f}",
                         *(f"{v:.8e}" for v in res["eta"][i]),
                         f"{res['W_joint'][i]:.8e}", f"{res['E_damp'][i]:.8e}",
                         f"{np.max(np.abs(dh[i, :3])):.3e}", f"{np.max(np.abs(dh[i, 3:])):.3e}"])
    summary["csv"] = os.path.relpath(csv_path, REPO)
    json_path = os.path.join(RES, base["summary_json"].replace(".json", f"{suffix}.json"))
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    return csv_path, json_path


def plot(res, meta, summary, tag=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    base = meta["scene"]["output"]
    suffix = f"_{tag}" if tag else ""
    png = os.path.join(RES, base["png"].replace(".png", f"{suffix}.png"))
    t = res["t"]
    fig, ax = plt.subplots(3, 1, figsize=(9, 10), sharex=True)
    q2 = [np.rad2deg(meta["traj"](x)[0][1]) for x in t]
    q3 = [np.rad2deg(meta["traj"](x)[0][2]) for x in t]
    ax[0].plot(t, q2, label="q2")
    ax[0].plot(t, q3, label="q3")
    ax[0].plot(t, res["dev_angle_deg"], "k--", lw=2, label="base dev angle")
    ax[0].set_ylabel("angle [deg]")
    ax[0].set_title("sim_11 A1 arm slew (quintic) - coupled base+arm+FFR panels\n"
                    f"m={meta['n_modes']}/panel, zeta={meta['zeta']}, "
                    f"peak dev={summary['peak_base_attitude_deviation_deg']:.4f} deg "
                    f"(sim_05 rigid ref 19.20 deg)")
    ax[0].legend(loc="center right")
    ax[1].plot(t, res["euler_xyz_deg"][:, 0], label="euler x")
    ax[1].plot(t, res["euler_xyz_deg"][:, 1], label="euler y")
    ax[1].plot(t, res["euler_xyz_deg"][:, 2], label="euler z")
    ax[1].set_ylabel("base euler xyz [deg]")
    ax[1].legend(loc="center right")
    ax[2].plot(t, res["tip_L_m"] * 1e3, label="panel L tip")
    ax[2].plot(t, res["tip_R_m"] * 1e3, label="panel R tip")
    ax[2].set_ylabel("tip deflection [mm]")
    ax[2].set_xlabel("time [s]")
    ax[2].legend(loc="center right")
    for a in ax:
        a.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(png, dpi=130)
    plt.close(fig)
    return png


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rigid-panels", action="store_true")
    ap.add_argument("--n-modes", type=int, default=None)
    ap.add_argument("--zeta", type=float, default=None)
    ap.add_argument("--rtol", type=float, default=None)
    ap.add_argument("--method", default=None)
    ap.add_argument("--mode", default="reduced", choices=["reduced", "full"])
    ap.add_argument("--stiffness-case", default=None)
    ap.add_argument("--t-end", type=float, default=None)
    ap.add_argument("--tag", default="")
    ap.add_argument("--no-plot", action="store_true")
    a = ap.parse_args()
    res, meta, model = run_scene_a1(rigid_panels=a.rigid_panels, n_modes=a.n_modes,
                                    zeta=a.zeta, rtol=a.rtol, method=a.method,
                                    mode=a.mode, stiffness_case=a.stiffness_case,
                                    t_end=a.t_end)
    summary = summarize(res, meta, model)
    csv_path, json_path = write_outputs(res, meta, model, summary, tag=a.tag)
    if not a.no_plot:
        summary["png"] = os.path.relpath(plot(res, meta, summary, tag=a.tag), REPO)
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2, ensure_ascii=False)
    print(json.dumps({k: v for k, v in summary.items()
                      if k != "generalized_jacobian_Jstar_at_qf"},
                     indent=2, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    main()
