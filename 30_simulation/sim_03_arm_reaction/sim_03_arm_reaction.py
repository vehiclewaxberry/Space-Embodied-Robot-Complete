"""sim_03: manipulator-induced base reaction on the free-floating servicer.
Reduced-order model: planar (rotation about +Y_S), conserves total angular momentum
about the instantaneous system CoM (starts at rest, H=0). Prescribed shoulder+elbow
reach-and-retract; solves the base counter-rotation and reaction momentum.
NOTE: v0 reduced model — base translation neglected; full 3D GJM via SPART is future work.
Consumes servicer_12U_v0 inertia (frame S) + the reBot_arm_v0_min link params.
Outputs base-reaction CSV + PNG into results/."""
import os, sys, csv
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
from rigid_body import load_object

HERE = os.path.dirname(__file__); RES = os.path.join(HERE, "results")
os.makedirs(RES, exist_ok=True)

base = load_object("servicer_12U_v0")
m_b = base["mass"]; I_b = base["I"][1, 1]                 # about +Y_S through base CoM
c_b = np.array([base["cg"][0], base["cg"][2]])           # base CoM (X,Z) in frame S
mount = np.array([0.18525, 0.0])                         # frame M origin (X,Z), T_SM translation

# reBot_arm_v0_min params (consistent with reBot_arm_v0_min.urdf)
L1, L2, m1, m2 = 0.30, 0.25, 0.80, 0.50
I1 = m1 * L1**2 / 12.0; I2 = m2 * L2**2 / 12.0           # thin-rod inertia about own CoM (Y)

def minjerk(t, T, A):                                     # 0 -> A over [0,T], smooth ends
    x = np.clip(t / T, 0, 1); s = 10*x**3 - 15*x**4 + 6*x**5
    sd = (30*x**2 - 60*x**3 + 30*x**4) / T
    return A*s, A*sd

def joints(t):
    """reach out 0->60deg shoulder, 0->-40deg elbow over 0-8s; retract over 12-20s."""
    a1 = np.deg2rad(60); a2 = np.deg2rad(-40); Tm = 8.0
    if t <= Tm:
        q1, q1d = minjerk(t, Tm, a1); q2, q2d = minjerk(t, Tm, a2)
    elif t < 12.0:
        q1, q1d, q2, q2d = a1, 0.0, a2, 0.0
    elif t <= 20.0:
        s, sd = minjerk(t-12.0, 8.0, 1.0)
        q1, q1d = a1*(1-s), -a1*sd; q2, q2d = a2*(1-s), -a2*sd
    else:
        q1, q1d, q2, q2d = 0.0, 0.0, 0.0, 0.0
    return q1, q2, q1d, q2d

def bodies(q1, q2):
    """CoM positions (X,Z) in base frame and abs angular rates coefficient wrt joint rates."""
    a1 = q1; a2 = q1 + q2
    d1 = np.array([np.cos(a1), np.sin(a1)]); d2 = np.array([np.cos(a2), np.sin(a2)])
    p1 = mount + (L1/2)*d1
    p2 = mount + L1*d1 + (L2/2)*d2
    tip = mount + L1*d1 + L2*d2
    return p1, p2, tip

ts = np.linspace(0, 24.0, 2000)
theta_b = 0.0  # base attitude [rad]
rows = []
prev_t = 0.0
for t in ts:
    q1, q2, q1d, q2d = joints(t)
    p1, p2, tip = bodies(q1, q2)
    # system CoM (base translation neglected: use base-frame positions)
    m_tot = m_b + m1 + m2
    c = (m_b*c_b + m1*p1 + m2*p2) / m_tot
    Jb = I_b + m_b*np.sum((c_b - c)**2)
    J1 = I1 + m1*np.sum((p1 - c)**2)
    J2 = I2 + m2*np.sum((p2 - c)**2)
    # abs joint-driven rates: link1 = q1d, link2 = q1d+q2d ; base rate omega_b unknown
    # H = Jb*wb + J1*(wb+q1d) + J2*(wb+q1d+q2d) = 0
    num = J1*q1d + J2*(q1d + q2d)
    wb = -num / (Jb + J1 + J2)
    dt = t - prev_t; prev_t = t
    theta_b += wb * dt
    H_react = Jb * wb
    # EE in inertial: rotate arm tip (base frame) by base attitude theta_b
    ct, st = np.cos(theta_b), np.sin(theta_b)
    ee_in = np.array([ct*tip[0] - st*tip[1], st*tip[0] + ct*tip[1]])  # (X,Z)
    # clearance of EE to servicer body AABB half-extents (X,Z) = (0.170, 0.113)
    gx = max(abs(ee_in[0]) - 0.170, 0.0); gz = max(abs(ee_in[1]) - 0.113, 0.0)
    clr = np.hypot(gx, gz)
    rows.append([t, np.rad2deg(q1), np.rad2deg(q2), np.rad2deg(theta_b), np.rad2deg(wb),
                 H_react, ee_in[0], ee_in[1], clr])

R = np.array(rows)
csv_path = os.path.join(RES, "base_reaction.csv")
with open(csv_path, "w", newline="\n", encoding="utf-8") as f:
    wr = csv.writer(f)
    wr.writerow(["t_s", "q1_deg", "q2_deg", "base_theta_deg", "base_omega_dps",
                 "H_reaction_kgm2ps", "ee_x_m", "ee_z_m", "clearance_min_m"])
    for r in R:
        wr.writerow([f"{r[0]:.4f}", *[f"{v:.5f}" for v in r[1:]]])

peak_dist = np.max(np.abs(R[:, 3]))
resid = R[-1, 3]
fig, ax = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
ax[0].plot(R[:, 0], R[:, 1], label="q1 shoulder"); ax[0].plot(R[:, 0], R[:, 2], label="q2 elbow")
ax[0].plot(R[:, 0], R[:, 3], "k--", lw=2, label="base attitude")
ax[0].set_ylabel("angle [deg]"); ax[0].legend(loc="upper right")
ax[0].set_title(f"sim_03 arm-induced base reaction  servicer_12U_v0 (I_yy={I_b:.3f})\n"
                f"peak base attitude disturbance = {peak_dist:.2f} deg, residual after retract = {resid:.3f} deg")
ax[1].plot(R[:, 0], R[:, 4], "C3", label="base rate"); ax[1].set_ylabel("base rate [deg/s]"); ax[1].legend(loc="upper right")
axr = ax[1].twinx(); axr.plot(R[:, 0], R[:, 5], "C4", alpha=.6, label="H_reaction"); axr.set_ylabel("H_reaction [kg m^2/s]")
ax[2].plot(R[:, 0], R[:, 8], "C2"); ax[2].set_ylabel("EE clearance to body [m]"); ax[2].set_xlabel("time [s]")
for a in ax: a.grid(alpha=.3)
png_path = os.path.join(RES, "base_reaction.png")
fig.tight_layout(); fig.savefig(png_path, dpi=130); plt.close(fig)

print({"base": base["id"], "I_yy": round(I_b, 4), "arm": {"L1": L1, "L2": L2, "m1": m1, "m2": m2},
       "peak_base_attitude_deg": round(peak_dist, 3), "residual_base_attitude_deg": round(float(resid), 4),
       "min_clearance_m": round(float(R[:, 8].min()), 4), "csv": csv_path, "png": png_path,
       "model": "reduced planar free-floating, angular-momentum conservation about system CoM (base translation neglected)"})
