"""sim_02: target_debris_v0 free tumble (non-cooperative rocket upper stage).
Establishes the "why capture is hard" background: a tumbling target whose grasp
feature is only intermittently presented to an approaching servicer (+X inertial).
Tracks a rim grasp point in the inertial frame and its visibility window.
Outputs pose/rate + grasp-track CSV + PNG into results/."""
import os, sys, csv
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
from rigid_body import load_object, propagate_torque_free, conservation_report, q_to_R

HERE = os.path.dirname(__file__); RES = os.path.join(HERE, "results")
os.makedirs(RES, exist_ok=True)

obj = load_object("target_debris_v0")            # frame D, Izz (symmetry axis) < Ixx=Iyy -> tumble
w0 = np.deg2rad([8.0, 1.0, 3.0])                  # transverse-dominant tumble [deg/s]
res = propagate_torque_free(obj["I"], w0, t_end=120.0, n=1800)
cons = conservation_report(res)

# grasp feature: a point on the upper rim; its outward normal is radial (+X_D at t0)
p_grasp_D = np.array([0.6, 0.0, 1.0])            # [m] rim point in body frame D
n_grasp_D = np.array([1.0, 0.0, 0.0])            # outward normal (radial)
APPROACH = np.array([1.0, 0.0, 0.0])             # servicer approaches from +X inertial
VIS_COS = np.cos(np.deg2rad(70))                 # visible if feature normal within 70 deg of -approach

track, vis = [], []
for q in res["Q"]:
    R = q_to_R(q)
    p_in = R.apply(p_grasp_D); n_in = R.apply(n_grasp_D)
    facing = float(np.dot(n_in, -APPROACH))       # >0 means normal points back toward the servicer
    track.append(p_in); vis.append(facing > VIS_COS)
track = np.array(track); vis = np.array(vis)

# CSV
csv_path = os.path.join(RES, "tumble_pose.csv")
with open(csv_path, "w", newline="\n", encoding="utf-8") as f:
    wr = csv.writer(f)
    wr.writerow(["t_s", "roll_deg", "pitch_deg", "yaw_deg", "wx_dps", "wy_dps", "wz_dps",
                 "grasp_x_m", "grasp_y_m", "grasp_z_m", "grasp_visible"])
    for i, t in enumerate(res["t"]):
        e = res["euler"][i]; w = np.rad2deg(res["W"][i]); p = track[i]
        wr.writerow([f"{t:.4f}", *[f"{v:.4f}" for v in e], *[f"{v:.4f}" for v in w],
                     *[f"{v:.5f}" for v in p], int(vis[i])])

duty = 100.0 * vis.mean()
# PNG
fig, ax = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
for k, lab in enumerate(["wx", "wy", "wz"]):
    ax[0].plot(res["t"], np.rad2deg(res["W"][:, k]), label=lab)
ax[0].set_ylabel("Body rate [deg/s]"); ax[0].legend(loc="upper right")
ax[0].set_title(f"sim_02 target_debris_v0 tumble (m={obj['mass']} kg, Ixx=Iyy={obj['I'][0,0]:.1f}, Izz={obj['I'][2,2]:.1f})\n"
                f"grasp-feature visible {duty:.0f}% of the time; |H| cons {cons['max_rel_dH']:.1e}")
for k, lab in enumerate(["grasp_x", "grasp_y", "grasp_z"]):
    ax[1].plot(res["t"], track[:, k], label=lab)
ax[1].set_ylabel("grasp point (inertial) [m]"); ax[1].legend(loc="upper right")
ax[2].fill_between(res["t"], 0, vis.astype(int), step="pre", alpha=.6)
ax[2].set_ylabel("visible (0/1)"); ax[2].set_xlabel("time [s]"); ax[2].set_ylim(-.1, 1.1)
for a in ax: a.grid(alpha=.3)
png_path = os.path.join(RES, "tumble_pose.png")
fig.tight_layout(); fig.savefig(png_path, dpi=130); plt.close(fig)

print({"object": obj["id"], "I_diag": list(np.round(np.diag(obj["I"]), 3)),
       "w0_dps": [8.0, 1.0, 3.0], "grasp_visible_duty_pct": round(duty, 1),
       "conservation": {k: (round(v, 12) if "rel" in k else round(v, 4)) for k, v in cons.items()},
       "csv": csv_path, "png": png_path})
