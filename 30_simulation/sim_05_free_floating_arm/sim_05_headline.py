"""sim_05_headline.py -- headline number: base attitude excursion of the
free-floating servicer (25.2 kg composite base) while the real 6R arm
(arm_b601_v1, 4.6956 kg incl. locked gripper) performs the sim_03-comparable
reach maneuver: min-jerk joint2 0 -> +60 deg, joint3 0 -> -40 deg over 8 s,
all other joints 0; hold 8..12 s.

Full 3D momentum-conserving model (H_bb, H_bm from dynamics.py, zero initial
momentum). Outputs results/sim_05_base_attitude.csv + .png, prints the peak
base attitude deviation and the comparison against the old sim_03 2-DOF
reduced planar model (peak 13.13 deg with a 1.6 kg two-rod arm). Also outputs
the |H_bm @ qdot| history (arm-transferred spatial momentum), the baseline
signal for later reaction-minimizing trajectory work.

NOTE: q2 = +60 deg exceeds the URDF joint2 limit [-180 deg, 0] (axis (0,0,-1)
sign convention); this is a dynamics benchmark chosen for comparability with
sim_03, not a flight trajectory.
"""
import csv
import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dynamics import FreeFloatingB601, min_jerk  # noqa: E402

RES = os.path.join(HERE, "results")
os.makedirs(RES, exist_ok=True)

T_M = 8.0          # maneuver duration [s]
T_END = 12.0       # hold to 12 s
A2 = np.deg2rad(60.0)
A3 = np.deg2rad(-40.0)
OLD_SIM03_PEAK_DEG = 13.13   # 2-DOF reduced planar model, 1.6 kg arm


def q_fun(t):
    q = np.zeros(6)
    q[1] = min_jerk(t, T_M, A2)[0]
    q[2] = min_jerk(t, T_M, A3)[0]
    return q


def qd_fun(t):
    qd = np.zeros(6)
    qd[1] = min_jerk(t, T_M, A2)[1]
    qd[2] = min_jerk(t, T_M, A3)[1]
    return qd


def main():
    dyn = FreeFloatingB601()
    res = dyn.integrate_trajectory(q_fun, qd_fun, T_END, n_out=601)
    t = res["t"]
    eul = res["euler_xyz_deg"]
    dev = res["dev_angle_deg"]
    hbm = res["hbm_qdot"]
    hbm_lin = np.linalg.norm(hbm[:, :3], axis=1)
    hbm_ang = np.linalg.norm(hbm[:, 3:], axis=1)

    peak_dev = float(np.max(dev))
    t_peak = float(t[np.argmax(dev)])
    final_dev = float(dev[-1])
    peak_hbm_ang = float(np.max(hbm_ang))
    peak_hbm_lin = float(np.max(hbm_lin))
    base_shift = float(np.max(np.linalg.norm(res["r"], axis=1)))

    # ---------------- CSV -------------------------------------------------------
    csv_path = os.path.join(RES, "sim_05_base_attitude.csv")
    with open(csv_path, "w", newline="\n", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["t_s", "q2_deg", "q3_deg",
                     "base_euler_x_deg", "base_euler_y_deg", "base_euler_z_deg",
                     "base_dev_angle_deg",
                     "base_pos_x_m", "base_pos_y_m", "base_pos_z_m",
                     "Hbm_qdot_lin_kgmps", "Hbm_qdot_ang_kgm2ps"])
        for i in range(len(t)):
            wr.writerow(["%.4f" % t[i],
                         "%.5f" % np.rad2deg(q_fun(t[i])[1]),
                         "%.5f" % np.rad2deg(q_fun(t[i])[2]),
                         *("%.6f" % v for v in eul[i]),
                         "%.6f" % dev[i],
                         *("%.7f" % v for v in res["r"][i]),
                         "%.7f" % hbm_lin[i], "%.7f" % hbm_ang[i]])

    # ---------------- PNG -------------------------------------------------------
    fig, ax = plt.subplots(3, 1, figsize=(9, 10), sharex=True)
    ax[0].plot(t, [np.rad2deg(q_fun(x)[1]) for x in t], label="q2 (joint2)")
    ax[0].plot(t, [np.rad2deg(q_fun(x)[2]) for x in t], label="q3 (joint3)")
    ax[0].plot(t, dev, "k--", lw=2, label="base attitude deviation")
    ax[0].set_ylabel("angle [deg]")
    ax[0].legend(loc="center right")
    ax[0].set_title("sim_05 free-floating base reaction, arm_b601_v1 (6R, %.4f kg)\n"
                    "composite base %.1f kg | peak base deviation = %.2f deg "
                    "(old 2-DOF sim_03: %.2f deg, 1.6 kg arm)"
                    % (dyn.arm.total_mass, dyn.m_base_comp, peak_dev, OLD_SIM03_PEAK_DEG))
    ax[1].plot(t, eul[:, 0], label="euler x")
    ax[1].plot(t, eul[:, 1], label="euler y")
    ax[1].plot(t, eul[:, 2], label="euler z")
    ax[1].set_ylabel("base euler xyz [deg]")
    ax[1].legend(loc="center right")
    ax[2].plot(t, hbm_ang, "C3", label="|H_bm qdot| angular [kg m^2/s]")
    axr = ax[2].twinx()
    axr.plot(t, hbm_lin, "C4", alpha=0.7, label="|H_bm qdot| linear [kg m/s]")
    axr.set_ylabel("linear [kg m/s]")
    ax[2].set_ylabel("angular [kg m^2/s]")
    ax[2].set_xlabel("time [s]")
    lines = ax[2].get_lines() + axr.get_lines()
    ax[2].legend(lines, [l.get_label() for l in lines], loc="center right")
    for a in ax:
        a.grid(alpha=0.3)
    png_path = os.path.join(RES, "sim_05_base_attitude.png")
    fig.tight_layout()
    fig.savefig(png_path, dpi=130)
    plt.close(fig)

    summary = {
        "arm_mass_kg": round(dyn.arm.total_mass, 4),
        "base_composite_kg": round(dyn.m_base_comp, 4),
        "maneuver": "min-jerk q2 0->+60deg, q3 0->-40deg, 8 s, hold to 12 s",
        "peak_base_attitude_deviation_deg": round(peak_dev, 3),
        "t_peak_s": round(t_peak, 3),
        "final_base_attitude_deviation_deg": round(final_dev, 3),
        "final_euler_xyz_deg": [round(float(v), 3) for v in eul[-1]],
        "peak_Hbm_qdot_angular_kgm2ps": round(peak_hbm_ang, 5),
        "peak_Hbm_qdot_linear_kgmps": round(peak_hbm_lin, 5),
        "max_base_CoM_shift_m": round(base_shift, 5),
        "old_sim03_2dof_peak_deg": OLD_SIM03_PEAK_DEG,
        "ratio_vs_sim03": round(peak_dev / OLD_SIM03_PEAK_DEG, 2),
        "csv": csv_path, "png": png_path,
    }
    print(summary)
    return summary


if __name__ == "__main__":
    main()
