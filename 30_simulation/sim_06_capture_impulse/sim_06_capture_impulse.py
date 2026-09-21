"""sim_06: capture-instant impulsive momentum transfer (rigidization).
Replaces the sim_04 post-capture heuristic (post_rate ~ tumble * I_t/(I_s+I_t)) with the
exact rigid-body result via the shared solver 30_simulation/common/capture_impulse.py (moments about
the combined CoM, parallel-axis terms, r x mv linear->angular coupling; cf. Dimitrov &
Yoshida, IROS 2004). Kinetic energy is NOT conserved (perfectly plastic rigidization);
the per-body impulse (J, couple at grasp) is exported as the excitation interface for the
flexible-appendage model (ANCF sim_07) — the scalar dT is only an upper bound / check.

v0 assumptions (all labeled): instantaneous rigid capture, no grasp slip/compliance; arm
frozen at full extension along the approach line; chaser attitude held (w=0) with residual
approach speed v_app at contact; target body frame aligned with inertial at the capture
instant (phase not swept); grasp points from CAD JSON metadata (confidence=low, RA-003).
Validation: 30_simulation/sim_06_capture_impulse/tests/ (run_all.py) — momentum/energy residuals,
frame invariance, 8 limiting cases, independent 6x6 spatial-inertia cross-check.
Outputs capture_impulse_matrix_v0.csv + 3 PNG into results/."""
import os, sys, csv
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
from rigid_body import load_object, propagate_torque_free
from capture_impulse import (rigidize, junction_couple, build_capture_scenario,
                             capture_post_state, chaser_stack, GRASP, TUMBLE_AXIS)

HERE = os.path.dirname(__file__); RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True)

POST_CAP_BUDGET = 2.0                       # deg/s (same budget as sim_04)

M_C, COM_C, I_C, _ = chaser_stack()

def case(target_id, tumble_dps, v_app, grasp_scale=1.0):
    r, bodies, meta = capture_post_state(target_id, tumble_dps, v_app, grasp_scale)
    assert r["validity"]["momentum_ok"] and r["validity"]["plastic_dT_nonneg"], r["validity"]
    J_t, L_g = junction_couple(r, bodies, 1, meta["r_g"])   # impulse on target, couple at grasp
    I_t_s = float(np.mean(np.diag(bodies[1]["I"]))); I_c_s = float(np.mean(np.diag(I_C)))
    w_scalar = np.deg2rad(tumble_dps) * I_t_s / (I_t_s + I_c_s)   # scalar shortcut (dropped terms)
    return {"target": target_id, "tumble_dps": tumble_dps, "v_app": v_app,
            "grasp_r": float(np.linalg.norm(meta["r_g"])), "res": r,
            "w_after": r["w_plus"], "w_after_dps": float(np.rad2deg(np.linalg.norm(r["w_plus"]))),
            "w_scalar_dps": float(np.rad2deg(w_scalar)),
            "J_t": J_t, "L_grasp": L_g, "dKE_J": r["dT"], "KE_pre_J": r["KE_pre"]}

# ---------------- sweep grid (deterministic) ----------------
TARGETS = ["target_debris_v0", "target_satellite_v0"]
TUMBLES = [0.5, 1.0, 2.0, 3.0, 5.0]
V_APPS = [0.005, 0.01, 0.02, 0.03]

rows, maps = [], {}
for tid in TARGETS:
    grid = np.zeros((len(TUMBLES), len(V_APPS)))
    for i, tb in enumerate(TUMBLES):
        for j, va in enumerate(V_APPS):
            r = case(tid, tb, va)
            grid[i, j] = r["w_after_dps"]
            rows.append([tid, tb, va, r["grasp_r"], r["w_after_dps"], r["w_scalar_dps"],
                         100.0 * (r["w_scalar_dps"] - r["w_after_dps"]) / max(r["w_after_dps"], 1e-12),
                         *r["w_after"], np.linalg.norm(r["J_t"]), np.linalg.norm(r["L_grasp"]),
                         r["dKE_J"], r["KE_pre_J"], r["res"]["eps_H_origin"],
                         "OVER_BUDGET" if r["w_after_dps"] > POST_CAP_BUDGET else "WITHIN_BUDGET"])
    maps[tid] = grid

csv_path = os.path.join(RES, "capture_impulse_matrix_v0.csv")
with open(csv_path, "w", newline="\n", encoding="utf-8") as f:
    wr = csv.writer(f)
    wr.writerow(["target", "tumble_dps", "v_app_mps", "grasp_leverarm_m", "post_rate_full_dps",
                 "post_rate_scalar_dps", "scalar_error_pct",
                 "w_after_x_rps", "w_after_y_rps", "w_after_z_rps",
                 "contact_impulse_N_s", "grasp_couple_N_m_s",
                 "impact_energy_loss_J", "KE_pre_J", "eps_H_origin", "budget_2dps"])
    for r in rows:
        wr.writerow([r[0], *[f"{v:.6g}" if isinstance(v, float) else v for v in r[1:]]])

# ---------------- fig 1: momentum allocation before/after (nominal debris case) ----------------
nom = case("target_debris_v0", 3.0, 0.01)
tgt_nom = load_object("target_debris_v0")
w_t_nom = np.deg2rad(3.0) * TUMBLE_AXIS
H_spin = tgt_nom["I"] @ w_t_nom
H_lin = nom["res"]["H_com"] - H_spin                       # r x mv coupling part
nut = propagate_torque_free(nom["res"]["I_comb"], nom["w_after"], 120.0, n=1200)
peak_nut = float(np.rad2deg(np.max(np.linalg.norm(nut["W"], axis=1))))

fig, ax = plt.subplots(1, 2, figsize=(11, 4.5))
labels = ["target spin\nI_t w_t", "approach linear\nr x m v", "TOTAL pre", "combined post\nI_comb w_c"]
vals = [np.linalg.norm(H_spin), np.linalg.norm(H_lin), np.linalg.norm(nom["res"]["H_com"]),
        np.linalg.norm(nom["res"]["I_comb"] @ nom["w_after"])]
ax[0].bar(labels, vals, color=["C0", "C1", "k", "C2"])
ax[0].set_ylabel("|H| about combined CoM [kg m$^2$/s]")
ax[0].set_title("sim_06 momentum allocation through capture\n"
                f"debris @ 3 deg/s, v_app=0.01 m/s   (eps_H = {nom['res']['eps_H_origin']:.1e})")
ax[1].bar(["target pre", "combined post", "post peak\n(nutation, 120 s)"],
          [3.0, nom["w_after_dps"], peak_nut], color=["C0", "C2", "C3"])
ax[1].axhline(POST_CAP_BUDGET, color="r", ls="--", label=f"detumble budget {POST_CAP_BUDGET} deg/s")
ax[1].set_ylabel("rate [deg/s]"); ax[1].legend()
ax[1].set_title(f"impact energy dissipated = {nom['dKE_J']:.4f} J (upper bound for\n"
                "flexible uptake; ANCF excitation = impulse/couple, not this scalar)")
for a in ax: a.grid(alpha=.3, axis="y")
fig.tight_layout(); fig.savefig(os.path.join(RES, "before_after_momentum.png"), dpi=130); plt.close(fig)

# ---------------- fig 2: post-capture rate maps vs 2 deg/s budget ----------------
fig, axs = plt.subplots(1, 2, figsize=(11, 4.6))
for k, tid in enumerate(TARGETS):
    g = maps[tid]
    im = axs[k].imshow(g, origin="lower", aspect="auto", cmap="viridis")
    axs[k].set_xticks(range(len(V_APPS)), [f"{v}" for v in V_APPS])
    axs[k].set_yticks(range(len(TUMBLES)), [f"{t}" for t in TUMBLES])
    axs[k].set_xlabel("approach speed [m/s]"); axs[k].set_ylabel("target tumble [deg/s]")
    for i in range(len(TUMBLES)):
        for j in range(len(V_APPS)):
            over = g[i, j] > POST_CAP_BUDGET
            axs[k].text(j, i, f"{g[i, j]:.2f}", ha="center", va="center",
                        color="red" if over else "white", fontsize=8,
                        fontweight="bold" if over else "normal")
    axs[k].set_title(f"{tid}\npost-capture combined rate [deg/s] (red > {POST_CAP_BUDGET} budget)")
    fig.colorbar(im, ax=axs[k], shrink=.85)
fig.suptitle("sim_06 exact post-capture rate (replaces sim_04 heuristic) — v0 assumptions apply", y=1.02)
fig.tight_layout(); fig.savefig(os.path.join(RES, "post_capture_rate_map.png"), dpi=130,
                                bbox_inches="tight"); plt.close(fig)

# ---------------- fig 3: scalar-shortcut error vs grasp lever arm ----------------
scales = np.linspace(0.05, 1.25, 25)
fig, ax = plt.subplots(1, 2, figsize=(11, 4.3))
for tid, cstyle in zip(TARGETS, ["C0", "C1"]):
    full = [case(tid, 3.0, 0.01, s)["w_after_dps"] for s in scales]
    scal = case(tid, 3.0, 0.01, 1.0)["w_scalar_dps"]
    lever = [np.linalg.norm(GRASP[tid]) * s for s in scales]
    ax[0].plot(lever, full, cstyle + "-", label=f"{tid} full (vector)")
    ax[0].axhline(scal, color=cstyle, ls=":", alpha=.8, label=f"{tid} scalar shortcut")
    err = [100.0 * (scal - fv) / fv for fv in full]
    ax[1].plot(lever, err, cstyle + "-", label=tid)
full0 = [case("target_debris_v0", 0.0, 0.02, s)["w_after_dps"] for s in scales]
lever0 = [np.linalg.norm(GRASP["target_debris_v0"]) * s for s in scales]
ax[0].plot(lever0, full0, "C3--", label="debris, ZERO tumble, v_app=0.02\n(scalar predicts 0)")
ax[0].set_xlabel("grasp lever arm |r_g| [m]"); ax[0].set_ylabel("post-capture rate [deg/s]")
ax[0].set_title("full vector result vs scalar shortcut (tumble 3 deg/s)")
ax[1].set_xlabel("grasp lever arm |r_g| [m]"); ax[1].set_ylabel("scalar error [%]")
ax[1].set_title("scalar formula error grows with grasp offset\n(dropped Steiner + r x mv terms)")
for a in ax: a.grid(alpha=.3); a.legend(fontsize=7)
fig.tight_layout(); fig.savefig(os.path.join(RES, "scalar_vs_full_error.png"), dpi=130); plt.close(fig)

nom_sat = case("target_satellite_v0", 3.0, 0.01)
print({"chaser_stack": {"mass_kg": round(M_C, 3), "com_x_m": round(float(COM_C[0]), 5),
                        "I_diag": [round(float(v), 4) for v in np.diag(I_C)]},
       "debris_nominal_3dps_0p01": {"post_rate_dps": round(nom["w_after_dps"], 3),
                                    "scalar_dps": round(nom["w_scalar_dps"], 3),
                                    "peak_nutation_dps": round(peak_nut, 3),
                                    "impact_loss_J": round(nom["dKE_J"], 4),
                                    "grasp_couple_N_m_s": round(float(np.linalg.norm(nom["L_grasp"])), 4),
                                    "eps_H": nom["res"]["eps_H_origin"]},
       "satellite_nominal_3dps_0p01": {"post_rate_dps": round(nom_sat["w_after_dps"], 3),
                                       "scalar_dps": round(nom_sat["w_scalar_dps"], 3)},
       "budget_dps": POST_CAP_BUDGET, "cases": len(rows), "csv": csv_path,
       "model": "instantaneous plastic rigidization via 30_simulation/common/capture_impulse.py; "
                "P and H conserved (residuals in CSV); validated by tests/run_all.py"})
