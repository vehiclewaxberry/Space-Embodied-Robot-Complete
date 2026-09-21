"""sim_07 phase 1: planar gradient-deficient ANCF beam — benchmark suite (Gate B item 1).

Element: 2-node planar ANCF beam, nodal coords e_n = [rx, ry, rx', ry'] (cubic Hermite
interpolation of the position field r(x)). Berzeri-Shabana simplified elastic model:
    U = 1/2 int EA*eps^2 dx + 1/2 int EI * r''.r'' dx,   eps = 1/2(r'.r' - 1)
Bending part is LINEAR in e (constant K_b); axial part nonlinear. Both vanish exactly
for arbitrary large rigid-body motion (the property linear FE lacks).

Benchmarks (acceptance per README_benchmark_spec.md):
  1. static cantilever tip deflection vs Euler-Bernoulli delta = F L^3/(3EI)  (<1%)
  2. first/second natural frequencies vs analytic cantilever (<5%; target f1 = 1.0 Hz
     since EI was assigned by frequency, this also closes the D-4 loop)
  3. large rigid rotation zero strain (U ~ 0 at 37 deg and 90 deg)
  4. free undamped vibration energy drift (DOP853)
  5. mesh convergence table (n_el = 2/4/8/16)

Parameters from 20_engineering/config/geometry/flexible_appendage_v1.yaml (equivalent solar-panel beam:
L=0.2 m, mu=1.742 kg/m, EI envelope 0.7/1.0/1.3 Hz). Deterministic, numpy/scipy only.

Element machinery lives in ancf_beam.py (extracted, numerics identical); this script is
the acceptance suite and MUST be rerun (5/5 PASS) after any change to ancf_beam.py."""
import os, sys
import numpy as np
from scipy.integrate import solve_ivp

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True)
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, HERE)
from ancf_beam import Beam, L_TOT, MU, EI, EA, EI_CASES, BETA1  # noqa: E402

# ---------------- benchmark 1: static tip deflection ----------------
beam = Beam(n_el=8)
delta_target = 0.01 * L_TOT                                    # 1% of span: linear range
F_tip = 3 * EI * delta_target / L_TOT**3
e_s, resid = beam.static_tip_load(F_tip)
tip_y = e_s[4*(beam.n_node - 1) + 1]
delta_analytic = F_tip * L_TOT**3 / (3 * EI)
err_static = abs(tip_y - delta_analytic) / delta_analytic

# ---------------- benchmark 2: frequencies (+ D-4 closure) ----------------
freqs = beam.frequencies(3)
f1_analytic = (BETA1**2 / (2*np.pi*L_TOT**2)) * np.sqrt(EI / MU)
beta2 = 4.69409113
f2_analytic = (beta2**2 / (2*np.pi*L_TOT**2)) * np.sqrt(EI / MU)
err_f1 = abs(freqs[0] - f1_analytic) / f1_analytic
err_f2 = abs(freqs[1] - f2_analytic) / f2_analytic
env_f1 = {k: Beam(8, ei=v).frequencies(1)[0] for k, v in EI_CASES.items()}

# ---------------- benchmark 3: rigid rotation zero strain ----------------
def rotated_config(theta):
    R = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    e = np.zeros(beam.ndof)
    for n in range(beam.n_node):
        e[4*n:4*n+2] = R @ np.array([n*beam.l, 0.0])
        e[4*n+2:4*n+4] = R @ np.array([1.0, 0.0])
    return e
U_ref = beam.strain_energy(beam.e0 + 0.0)        # = 0 reference
U_37 = beam.strain_energy(rotated_config(np.deg2rad(37)))
U_90 = beam.strain_energy(rotated_config(np.deg2rad(90)))
U_scale = 0.5 * EA * 0.01                         # energy scale for normalization
zero_strain_ok = max(U_37, U_90) < 1e-14 * U_scale + 1e-18

# ---------------- benchmark 4: free vibration energy drift ----------------
def free_vib(beam, e_init, t_end, rtol):
    fr = beam.free
    Mff = beam.M[np.ix_(fr, fr)]
    Minv = np.linalg.inv(Mff)
    def deriv(t, s):
        e = beam.e0.copy(); e[fr] = s[:len(fr)]
        edot_f = s[len(fr):]
        acc = Minv @ (-beam.q_int(e)[fr])
        return np.concatenate([edot_f, acc])
    s0 = np.concatenate([e_init[fr], np.zeros(len(fr))])
    sol = solve_ivp(deriv, (0, t_end), s0, method="DOP853", rtol=rtol, atol=rtol*1e-2,
                    t_eval=np.linspace(0, t_end, 400))
    Es = []
    for k in range(sol.y.shape[1]):
        e = beam.e0.copy(); e[fr] = sol.y[:len(fr), k]
        ed = sol.y[len(fr):, k]
        Es.append(0.5 * ed @ (Mff @ ed) + beam.strain_energy(e))
    Es = np.array(Es)
    return sol, Es

T1 = 1.0 / freqs[0]
sol, Es = free_vib(beam, e_s, 2*T1, rtol=1e-8)
drift = abs(Es[-1] - Es[0]) / Es[0]
sol2, Es2 = free_vib(beam, e_s, 2*T1, rtol=1e-10)
drift_tight = abs(Es2[-1] - Es2[0]) / Es2[0]

# ---------------- benchmark 5: mesh convergence ----------------
conv = []
for n in (2, 4, 8, 16):
    b = Beam(n)
    f1n = b.frequencies(1)[0]
    en, _ = b.static_tip_load(F_tip)
    conv.append((n, f1n, abs(f1n - f1_analytic)/f1_analytic,
                 en[4*n + 1], abs(en[4*n + 1] - delta_analytic)/delta_analytic))

# ---------------- figures ----------------
fig, ax = plt.subplots(1, 3, figsize=(14, 4.2))
xs = [e_s[4*n] for n in range(beam.n_node)]; ys = [e_s[4*n+1] for n in range(beam.n_node)]
ax[0].plot(xs, ys, "o-", label="ANCF static (8 el)")
xa = np.linspace(0, L_TOT, 50)
ax[0].plot(xa, F_tip*xa**2*(3*L_TOT - xa)/(6*EI), "--", label="Euler-Bernoulli analytic")
ax[0].set_title(f"tip load {F_tip*1e3:.2f} mN: tip err {err_static*100:.3f}%")
ax[0].set_xlabel("x [m]"); ax[0].set_ylabel("y [m]"); ax[0].legend()
ns = [c[0] for c in conv]
ax[1].loglog(ns, [c[2] for c in conv], "o-", label="f1 rel err")
ax[1].loglog(ns, [c[4] for c in conv], "s-", label="static tip rel err")
ax[1].set_title("mesh convergence"); ax[1].set_xlabel("n elements"); ax[1].legend()
ax[2].plot(sol.t/T1, (Es-Es[0])/Es[0], label="rtol 1e-8")
ax[2].plot(sol2.t/T1, (Es2-Es2[0])/Es2[0], label="rtol 1e-10")
ax[2].set_title(f"free-vibration energy drift (2 periods)\n{drift:.1e} / {drift_tight:.1e}")
ax[2].set_xlabel("t / T1"); ax[2].set_ylabel("dE/E0"); ax[2].legend()
for a in ax: a.grid(alpha=.3, which="both")
fig.suptitle(f"sim_07 ANCF beam benchmarks — panel-equivalent beam L={L_TOT} m, "
             f"mu={MU:.3f} kg/m, EI={EI*1e3:.3f} mN m^2 (f1 target 1.0 Hz)", fontsize=10)
fig.tight_layout(); fig.savefig(os.path.join(RES, "ancf_beam_benchmarks.png"), dpi=130)
plt.close(fig)

report = {
    "params": {"L_m": L_TOT, "mu_kg_m": round(MU, 5), "EI_Nm2": EI, "EA_N": round(EA, 1)},
    "b1_static": {"tip_ancf_m": round(float(tip_y), 8), "tip_analytic_m": round(delta_analytic, 8),
                  "rel_err": f"{err_static:.2e}", "newton_residual": f"{resid:.1e}",
                  "PASS(<1%)": bool(err_static < 0.01)},
    "b2_freq": {"f1_hz": round(float(freqs[0]), 5), "f1_analytic": round(f1_analytic, 5),
                "err_f1": f"{err_f1:.2e}", "f2_hz": round(float(freqs[1]), 4),
                "f2_analytic": round(f2_analytic, 4), "err_f2": f"{err_f2:.2e}",
                "envelope_f1_hz": {k: round(float(v), 4) for k, v in env_f1.items()},
                "PASS(<5%)": bool(err_f1 < 0.05 and err_f2 < 0.05)},
    "b3_zero_strain": {"U_37deg_J": f"{U_37:.2e}", "U_90deg_J": f"{U_90:.2e}",
                       "PASS": bool(zero_strain_ok)},
    "b4_energy_drift": {"rtol1e-8": f"{drift:.2e}", "rtol1e-10": f"{drift_tight:.2e}",
                        "PASS(<1e-6@tight)": bool(drift_tight < 1e-6)},
    "b5_convergence": [{"n_el": c[0], "f1": round(float(c[1]), 5), "f1_err": f"{c[2]:.2e}",
                        "tip_err": f"{c[4]:.2e}"} for c in conv],
}
import json
with open(os.path.join(RES, "benchmark_results_v1.md"), "w", encoding="utf-8") as f:
    f.write("# sim_07 ANCF beam benchmark results v1 (Gate B item 1)\n\n```json\n"
            + json.dumps(report, indent=2, ensure_ascii=False) + "\n```\n")
print(json.dumps(report, ensure_ascii=False))
