"""sim_01: servicer_12U_v0 free (uncontrolled) attitude drift.
Validates that the CAD-derived mass/inertia produce a usable rigid-body attitude
propagation with conserved angular momentum + energy (no control, no torque).
Outputs attitude/rate CSV + PNG into results/."""
import os, sys, csv
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
from rigid_body import load_object, propagate_torque_free, conservation_report

HERE = os.path.dirname(__file__); RES = os.path.join(HERE, "results")
os.makedirs(RES, exist_ok=True)

obj = load_object("servicer_12U_v0")
w0 = np.deg2rad([1.0, 5.0, 2.0])   # initial tumble [deg/s] -> rad/s
res = propagate_torque_free(obj["I"], w0, t_end=120.0, n=1500)
cons = conservation_report(res)

# CSV
csv_path = os.path.join(RES, "attitude_rate.csv")
with open(csv_path, "w", newline="\n", encoding="utf-8") as f:
    wr = csv.writer(f)
    wr.writerow(["t_s", "qw", "qx", "qy", "qz", "roll_deg", "pitch_deg", "yaw_deg",
                 "wx_dps", "wy_dps", "wz_dps", "H_mag_kgm2ps", "E_rot_J"])
    for i, t in enumerate(res["t"]):
        q = res["Q"][i]; e = res["euler"][i]; w = np.rad2deg(res["W"][i])
        wr.writerow([f"{t:.4f}", *[f"{v:.8f}" for v in q], *[f"{v:.5f}" for v in e],
                     *[f"{v:.5f}" for v in w], f"{res['Hmag'][i]:.8e}", f"{res['E'][i]:.8e}"])

# PNG
fig, ax = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
for k, lab in enumerate(["roll", "pitch", "yaw"]):
    ax[0].plot(res["t"], res["euler"][:, k], label=lab)
ax[0].set_ylabel("Euler angle [deg]"); ax[0].legend(loc="upper right")
ax[0].set_title(f"sim_01 free drift  servicer_12U_v0 (m={obj['mass']} kg)\n"
                f"|H| conserved to {cons['max_rel_dH']:.1e}, E to {cons['max_rel_dE']:.1e} (rel)")
for k, lab in enumerate(["wx", "wy", "wz"]):
    ax[1].plot(res["t"], np.rad2deg(res["W"][:, k]), label=lab)
ax[1].set_ylabel("Body rate [deg/s]"); ax[1].set_xlabel("time [s]"); ax[1].legend(loc="upper right")
ax[0].grid(alpha=.3); ax[1].grid(alpha=.3)
png_path = os.path.join(RES, "attitude_rate.png")
fig.tight_layout(); fig.savefig(png_path, dpi=130); plt.close(fig)

print({"object": obj["id"], "I_diag": list(np.round(np.diag(obj["I"]), 4)),
       "w0_dps": [1.0, 5.0, 2.0], "t_end_s": 120.0,
       "conservation": {k: (round(v, 12) if "rel" in k else round(v, 6)) for k, v in cons.items()},
       "csv": csv_path, "png": png_path})
