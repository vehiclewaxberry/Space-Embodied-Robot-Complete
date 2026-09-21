"""sim_08: post-capture detumbling actuator & propellant budget (v0, analytic).

Physical fact this quantifies: reaction wheels only REDISTRIBUTE angular momentum inside
the stack; to bring the captured combined body to rest w.r.t. inertial space the total
|H| must either be stored in the wheels or expelled by external torque (thrusters /
magnetorquers). So the budget is a two-stage architecture:

    coarse detumble : thruster couple removes |H_c|            tau = |H_c| / t_d
    fine  stabilize : wheels handle residual low-rate control  (capacity check)
    unload          : thrusters/magnetorquers dump wheel momentum

Thruster couple (2 thrusters, moment arm l_T):  F_req = tau / (2 l_T)
Total impulse (couple, both thrusters):          J    = 2 F t_d = |H_c| / l_T
Propellant:                                      m_p  = J / (Isp * g0)

|H_c| comes from the VALIDATED sim_06 rigidization solver (nominal v_app = 0.01 m/s),
not from a heuristic. All actuator constants in assumptions.yaml (typical CubeSat-class
values, to be replaced by selected COTS datasheets). Deterministic; outputs 3 PNG + CSV."""
import os, sys, csv
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from capture_impulse import capture_post_state  # noqa: E402

G0 = 9.80665
V_APP = 0.01                                   # m/s nominal residual approach speed
TARGETS = ["target_debris_v0", "target_satellite_v0"]
TUMBLES = np.linspace(0.25, 5.0, 20)           # deg/s
T_DETUMBLE = [60.0, 300.0, 900.0, 3600.0]      # s allowed coarse-detumble durations
LEVER = [0.05, 0.10, 0.17]                     # m thruster moment arms on a 12U (max half-dim ~0.17)
ISP = {"cold_gas_60s": 60.0, "green_mono_220s": 220.0}
WHEEL_CLASSES = {"CubeSat RW 15 mNms": 0.015, "CubeSat RW 50 mNms": 0.050,
                 "CubeSat RW 100 mNms": 0.100, "smallsat RW 1 Nms": 1.0}

def H_after(target, tumble):
    r, _, _ = capture_post_state(target, float(tumble), V_APP)
    return float(np.linalg.norm(r["I_comb"] @ r["w_plus"]))  # = |H_com|, conserved

Hmap = {t: np.array([H_after(t, tu) for tu in TUMBLES]) for t in TARGETS}

rows = []
for t in TARGETS:
    for i, tu in enumerate(TUMBLES):
        H = Hmap[t][i]
        for td in T_DETUMBLE:
            tau = H / td
            for lT in LEVER:
                F = tau / (2 * lT); J = H / lT
                for isp_name, isp in ISP.items():
                    rows.append([t, round(float(tu), 3), round(H, 5), td, lT,
                                 round(tau, 6), round(F, 6), round(J, 4),
                                 isp_name, round(J / (isp * G0) * 1000, 4)])
with open(os.path.join(RES, "actuator_budget_sweep.csv"), "w", newline="\n", encoding="utf-8") as f:
    wr = csv.writer(f)
    wr.writerow(["target", "tumble_dps", "H_Nms", "t_detumble_s", "lever_m",
                 "torque_Nm", "thruster_force_N", "total_impulse_Ns", "isp_class", "propellant_g"])
    wr.writerows(rows)

# ---- fig 1: tumble -> |H_c| with wheel capacity bands ----
fig, ax = plt.subplots(figsize=(8, 5))
for t, c in zip(TARGETS, ["C3", "C0"]):
    ax.plot(TUMBLES, Hmap[t], c, lw=2, label=f"{t}  |H| after capture")
for (name, h), ls in zip(WHEEL_CLASSES.items(), [":", "-.", "--", "-"]):
    ax.axhline(h, color="gray", ls=ls, lw=1)
    ax.text(5.05, h, f" {name}", va="center", fontsize=7, color="gray")
ax.set_yscale("log"); ax.set_xlabel("target tumble rate [deg/s]")
ax.set_ylabel("post-capture angular momentum |H_c| [N m s]")
ax.set_title("sim_08 momentum to remove vs wheel storage classes\n"
             "(exact sim_06 rigidization, v_app=0.01 m/s; wheels alone cannot absorb debris capture)")
ax.grid(alpha=.3, which="both"); ax.legend()
fig.tight_layout(); fig.savefig(os.path.join(RES, "budget_H_vs_wheels.png"), dpi=130); plt.close(fig)

# ---- fig 2: detumble time -> thruster force (debris @ 3 deg/s) ----
H_nom = H_after("target_debris_v0", 3.0)
tds = np.logspace(np.log10(30), np.log10(7200), 60)
fig, ax = plt.subplots(figsize=(8, 5))
for lT, c in zip(LEVER, ["C0", "C1", "C2"]):
    ax.loglog(tds, H_nom / tds / (2 * lT), c, lw=2, label=f"lever arm {lT:.2f} m")
for F_typ, name in [(0.01, "10 mN cold-gas class"), (0.1, "100 mN class"), (1.0, "1 N class")]:
    ax.axhline(F_typ, color="gray", ls=":", lw=1)
    ax.text(7400, F_typ, f" {name}", va="center", fontsize=7, color="gray")
ax.set_xlabel("allowed coarse-detumble time [s]")
ax.set_ylabel("required thruster force per unit (couple) [N]")
ax.set_title(f"sim_08 thruster sizing — debris capture @3 deg/s (|H|={H_nom:.2f} N m s)\n"
             "tau = |H|/t_d,  F = tau/(2 l_T)")
ax.grid(alpha=.3, which="both"); ax.legend()
fig.tight_layout(); fig.savefig(os.path.join(RES, "budget_force_vs_time.png"), dpi=130); plt.close(fig)

# ---- fig 3: propellant vs tumble (Isp x lever) + wheel-only feasibility shading ----
fig, axs = plt.subplots(1, 2, figsize=(12, 4.8))
for k, t in enumerate(TARGETS):
    ax = axs[k]
    for isp_name, isp in ISP.items():
        for lT, ls in zip([0.05, 0.17], ["--", "-"]):
            mp = Hmap[t] / lT / (isp * G0) * 1000
            ax.plot(TUMBLES, mp, ls, lw=2,
                    label=f"{isp_name}, l_T={lT:.2f} m")
    wheel_ok = Hmap[t] <= 3 * WHEEL_CLASSES["CubeSat RW 100 mNms"]
    if wheel_ok.any():
        ax.axvspan(TUMBLES[0], TUMBLES[wheel_ok][-1], color="green", alpha=.12,
                   label="3x100 mNms wheels could store |H|")
    ax.set_xlabel("target tumble rate [deg/s]"); ax.set_yscale("log")
    ax.set_title(f"{t}: propellant for full |H| removal")
    ax.grid(alpha=.3, which="both"); ax.legend(fontsize=7)
axs[0].set_ylabel("propellant mass [g]")
fig.suptitle("sim_08 propellant budget (m_p = |H| / (l_T Isp g0)) — thruster-couple coarse detumble", y=1.02)
fig.tight_layout(); fig.savefig(os.path.join(RES, "budget_propellant.png"), dpi=130,
                                bbox_inches="tight"); plt.close(fig)

H_sat3 = H_after("target_satellite_v0", 3.0)
print({"H_debris_3dps_Nms": round(H_nom, 3), "H_satellite_3dps_Nms": round(H_sat3, 4),
       "wheels_3x100mNms_capacity_Nms": 0.3,
       "debris_wheel_only_feasible": bool(H_nom <= 0.3),
       "satellite_wheel_only_feasible": bool(H_sat3 <= 0.3),
       "example_debris_3dps": {"t_d_900s_torque_Nm": round(H_nom/900, 4),
                               "F_lever0p17_N": round(H_nom/900/(2*0.17), 4),
                               "propellant_coldgas_lever0p17_g": round(H_nom/0.17/(60*G0)*1000, 1),
                               "propellant_green_lever0p17_g": round(H_nom/0.17/(220*G0)*1000, 1)},
       "outputs": ["actuator_budget_sweep.csv", "budget_H_vs_wheels.png",
                   "budget_force_vs_time.png", "budget_propellant.png"]})
