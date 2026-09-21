"""sim_07 phase A — ANCF solar-panel task response to the capture impulse (one-way).

Scenario: capture of target_debris_v0 tumbling at 3 deg/s, residual closing speed
v_app = 0.01 m/s (nominal sim_04/sim_06 case). Two capture idealizations:
  - 6dof_rigid_lock : instantaneous plastic rigidization (capture_post_state), the
    chaser base receives (dv_B, dw_B) = result["impulses"][0]
  - 3dof_point      : ideal ball-joint point capture (rigidize_point_contact at the
    grasp point meta["r_g"]), force impulse only, no couple transmitted

PHASE-A MODEL (one-way, prescribed base — no flexible feedback on the base):
  At the capture instant the base jumps by (dv_B, dw_B) (inertial frame, about the
  chaser stack CoM). The +Y_S panel root frame F (r_F_S = [-0.05675, +0.11315, 0] in S)
  is a material point of the base, so its velocity jump is
      dv_F = dv_B + dw_B x (r_F - r_com_chaser)                      (inertial frame)
  Seen from the base-fixed frame, the still-undeformed panel keeps its pre-capture
  velocity: the initial condition is e(0) = straight, and an initial velocity field
      v0(y) = -[dv_F + dw_B x (y * yF_hat)],   y in [0, L]  along the panel
  (root node clamped to the base -> its DOFs are zero).

  PLANARIZATION (documented convention): the ANCF beam bends in the (y, z) plane —
  beam axis = +Y_F (local x), transverse = +Z_S = panel normal (local y, primary
  bending direction). The Z_S component of v0 is the transverse excitation; the X_S
  (chord-wise, in-plane) component is IGNORED (plate chord-wise stiffness >> bending
  stiffness). The AXIAL (Y_F) component is ALSO DROPPED from the initial conditions
  ("axial quasi-rigid" assumption): with EA ~ 3e3 N the axial response is a ~52+ Hz
  micro-oscillation (amplitude ~6e-5 m, energy that Rayleigh damping kills within a few
  cycles) irrelevant to every bending metric, but exciting it forces the integrator to
  resolve it. Both dropped components are printed per case (audit trail). The axial
  DOFs themselves REMAIN in the model (membrane/bending coupling intact).

  Base motion AFTER the jump (uniform velocity + rotation at |w_post| ~ 0.05 rad/s) is
  neglected: the induced quasi-static centrifugal tip deflection and the Coriolis force
  ratio 2|w|/omega_1 are ESTIMATED NUMERICALLY below and declared in the outputs/README.

Damping: constant Rayleigh C = alpha*M + beta*K_t with zeta = 0.01 matched exactly at
f1 and 5*f1 of each beam (config damping.zeta). EA is scaled with EI/EI_nominal per
stiffness case (same equivalent section => E scales, EA follows).

Regression checks (all must pass, thresholds fixed):
  R1 undamped nominal case energy conservation drift < 1e-6 (DOP853 rtol 1e-10)
  R2 damped cases: energy decays strictly over every half-period window + no pointwise
     energy injection above 1e-3*E0 (the pointwise-only form is ill-posed: dE/dt =
     -edot' C edot touches zero at velocity turning points, where any integrator noise
     flips the sign)
  R3 integrator cross-check: Radau (scan) vs DOP853 on a damped 2 s window, tip
     trajectory max deviation < 1e-3 relative (the Rayleigh beta*K term overdamps the
     ~3.5 kHz discrete modes -> explicit methods are stability-limited to dt ~ 2e-5 s,
     so the production scan uses the implicit Radau; R3 pins its accuracy)

Outputs (results/): tip_response_matrix.png, root_moment_and_energy.png,
task_response_summary.csv + structured result dict on stdout.

Uses the benchmarked beam from ancf_beam.py (5/5 PASS — rerun ancf_beam_benchmark.py
after any change there). Pure numpy/scipy, deterministic."""
import os, sys, json, csv, time
# pin BLAS to 1 thread BEFORE importing numpy: the RHS works on 64x64 operators where
# MKL/OpenBLAS threading only adds spin-wait overhead (scan cases already run as
# parallel processes); numerics are unaffected
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
import numpy as np
from scipy.integrate import solve_ivp
from scipy.signal import hilbert
from scipy.linalg import eigh

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ancf_beam import Beam, L_TOT, MU, EI_CASES, EI as EI_NOM, EA as EA_NOM   # noqa: E402
from capture_impulse import (capture_post_state, build_capture_scenario,      # noqa: E402
                             rigidize_point_contact, chaser_stack)

# ---------------- scenario constants ----------------
TARGET, TUMBLE_DPS, V_APP = "target_debris_v0", 3.0, 0.01
ZETA, N_EL = 0.01, 8
T_END, N_EVAL = 15.0, 1500
# Scan integrator: the Rayleigh beta*K term overdamps the ~3.5 kHz discrete modes
# (lambda ~ -beta*w^2 ~ -2.6e5 1/s), which STABILITY-limits any explicit method to
# dt ~ 2e-5 s regardless of what is excited. The damped scan therefore uses the implicit
# stiff-friendly Radau (cross-checked against DOP853 on a 2 s window in --smoke);
# the undamped R1 energy regression keeps DOP853 (non-stiff without C, symplectic-like
# accuracy at rtol 1e-10).
SCAN_METHOD, SCAN_RTOL, ATOL = "Radau", 1e-6, 1e-10
R_FLIP = np.diag([-1.0, -1.0, 1.0])              # S frame -> inertial (build_capture_scenario)
R_F_S = np.array([-0.05675, +0.11315, 0.0])      # +Y-side panel root frame F in S [m]
Y_F_S = np.array([0.0, 1.0, 0.0])                # panel axis +Y_F in S
X_S   = np.array([1.0, 0.0, 0.0])
Z_HAT = np.array([0.0, 0.0, 1.0])                # +Z_S == +Z inertial (R_FLIP leaves z)

EI_ORDER = ["flexible_low", "nominal", "flexible_high"]
MODE_ORDER = ["6dof_rigid_lock", "3dof_point"]


# ---------------- excitation from the validated capture solver ----------------
def capture_excitations():
    """Both capture modes -> chaser-base velocity jump (dv, dw), dT, post-capture
    rotation rate and the lever d = r_chaser - r_rotation_center (for the centrifugal
    estimate: 6DOF combined body spins about the COMBINED CoM, 3DOF chaser about its
    own CoM)."""
    res6, bodies6, _ = capture_post_state(TARGET, TUMBLE_DPS, V_APP)
    imp6 = res6["impulses"][0]
    b3, meta3 = build_capture_scenario(TARGET, TUMBLE_DPS, V_APP)
    res3 = rigidize_point_contact(b3, meta3["r_g"])
    imp3 = res3["impulses"][0]
    return {
        "6dof_rigid_lock": {
            "dv": np.asarray(imp6["dv"]), "dw": np.asarray(imp6["dw"]),
            "dT_J": float(res6["dT"]), "w_post": np.asarray(res6["w_plus"]),
            "d_lever": np.asarray(bodies6[0]["r"]) - np.asarray(res6["r_com"])},
        "3dof_point": {
            "dv": np.asarray(imp3["dv"]), "dw": np.asarray(imp3["dw"]),
            "dT_J": float(res3["dT"]),
            "w_post": np.asarray(b3[0]["w"]) + np.asarray(imp3["dw"]),
            "d_lever": np.zeros(3)},
    }


def panel_excitation(dv, dw):
    """Project the base velocity jump onto the +Y_S panel. Returns the coefficients of
    the (linear-in-y) initial velocity field in the base frame, plus the ignored X_S
    (in-plane) component for the audit trail. All fields carry the -(...) sign of the
    base-frame initial condition."""
    _, com_c, _, _ = chaser_stack()
    r_rel = R_FLIP @ (R_F_S - com_c)             # root F rel. chaser CoM, inertial
    yF = R_FLIP @ Y_F_S                          # panel axis, inertial ([0,-1,0])
    xS = R_FLIP @ X_S                            # chord direction, inertial
    dv_F = dv + np.cross(dw, r_rel)              # root material-point velocity jump
    wxy = np.cross(dw, yF)                       # d(dv)/dy along the panel
    return {
        "r_rel_I": r_rel, "yF_I": yF, "dv_F_I": dv_F,
        # transverse (Z_S) field: v_tr(y) = a_tr + b_tr*y
        "a_tr": -float(dv_F @ Z_HAT), "b_tr": -float(wxy @ Z_HAT),
        # axial (Y_F) field: constant ((dw x y*yF).yF == 0)
        "a_ax": -float(dv_F @ yF),
        # ignored in-plane (X_S) field, root + linear coefficient (declared, not used)
        "ign_a": -float(dv_F @ xS), "ign_b": -float(wxy @ xS),
    }


def centrifugal_estimate(w_post, d_lever, exc, ei):
    """Quasi-static transverse deflection induced by the NEGLECTED post-capture base
    rotation (phase-A one-way approximation). In the base frame rotating at w the panel
    feels -mu*[w x (w x (d + rho(y)))] with rho(y) = r_rel + y*yF (d = base CoM offset
    from the rotation center). Transverse (Z) component is linear in y: a_z = c0 + c1*y.
    Cantilever tip deflection bound (uniform + triangular analytic formulas):
        delta_c <= mu*L^4/EI * (|c0|/8 + 11*|c1|*L/120)
    Also returns the Coriolis ratio 2|w|/omega_1."""
    rho0 = exc["r_rel_I"] + d_lever
    a0 = np.cross(w_post, np.cross(w_post, rho0))
    aL = np.cross(w_post, np.cross(w_post, rho0 + L_TOT * exc["yF_I"]))
    c0, c1 = float(a0 @ Z_HAT), float((aL - a0) @ Z_HAT) / L_TOT
    delta_c = MU * L_TOT**4 / ei * (abs(c0) / 8.0 + 11.0 * abs(c1) * L_TOT / 120.0)
    return {"c0_m_s2": c0, "c1_m_s2_per_m": c1, "delta_c_tip_m": delta_c,
            "w_post_rad_s": float(np.linalg.norm(w_post))}


# ---------------- integration ----------------
def simulate(beam, ed0, t_end, n_eval, rtol, damped=True, method="DOP853"):
    """Time integration of M eddot + C edot + Kb e + q_axial(e) = 0 on the free DOFs.
    Linear operators are pre-reduced (A_K = Minv Kb_ff etc.); only the nonlinear
    axial force is evaluated per call (Beam is vectorized, C is a constant matrix)."""
    fr = beam.free; nf = len(fr)
    Mff = beam.M[np.ix_(fr, fr)]
    Minv = np.linalg.inv(Mff)
    e_work = beam.e0.copy()                       # fixed root DOFs stay at e0 values
    A_K = Minv @ beam.Kb[np.ix_(fr, fr)]
    c_K = Minv @ (beam.Kb[:, beam.fixed] @ beam.e0[beam.fixed])[fr]   # const (root) part
    A_C = (Minv @ beam.C[np.ix_(fr, fr)]) if (damped and beam.C is not None) else None
    q_axial = beam.q_axial

    def rhs(t, s):
        ef = s[:nf]; ed = s[nf:]
        e_work[fr] = ef
        acc = -(A_K @ ef) - c_K - Minv @ q_axial(e_work)[fr]
        if A_C is not None:
            acc -= A_C @ ed
        return np.concatenate([ed, acc])          # fresh array: solver keeps references

    s0 = np.concatenate([beam.e0[fr], ed0[fr]])
    kw = {}
    if method != "DOP853":
        # constant Jacobian for the implicit solver: exact linear part (tangent stiffness
        # at e0 incl. axial membrane tangent + Rayleigh C). The neglected geometric
        # nonlinearity is O(mm/L)^2 here — only Newton convergence uses this matrix, and
        # regression R3 pins the resulting trajectory against DOP853 anyway.
        Ktff = beam.tangent_stiffness()[np.ix_(fr, fr)]
        J = np.zeros((2 * nf, 2 * nf))
        J[:nf, nf:] = np.eye(nf)
        J[nf:, :nf] = -(Minv @ Ktff)
        if A_C is not None:
            J[nf:, nf:] = -A_C
        kw["jac"] = J
    sol = solve_ivp(rhs, (0.0, t_end), s0, method=method, rtol=rtol, atol=ATOL,
                    t_eval=np.linspace(0.0, t_end, n_eval), **kw)
    assert sol.success, sol.message
    n_t = sol.t.size
    tip = np.empty(n_t); Mr = np.empty(n_t); U = np.empty(n_t); T = np.empty(n_t)
    for k in range(n_t):
        e = beam.e0.copy(); e[fr] = sol.y[:nf, k]
        ed = sol.y[nf:, k]
        tip[k] = beam.tip_transverse(e)
        Mr[k] = beam.root_moment(e)
        U[k] = beam.strain_energy(e)
        T[k] = 0.5 * ed @ (Mff @ ed)
    return {"t": sol.t, "tip": tip, "Mroot": Mr, "U": U, "T": T, "E": U + T,
            "nfev": int(sol.nfev)}


# ---------------- metrics ----------------
def dominant_frequency(t, x):
    """FFT peak of the tip history (Hann window, 8x zero padding, parabolic interp)."""
    dt = t[1] - t[0]
    w = np.hanning(len(x))
    X = np.abs(np.fft.rfft((x - x.mean()) * w, n=8 * len(x)))
    f = np.fft.rfftfreq(8 * len(x), dt)
    k = int(np.argmax(X[1:]) + 1)
    if 1 <= k < len(X) - 1:                       # parabolic peak interpolation
        de = 0.5 * (X[k-1] - X[k+1]) / (X[k-1] - 2*X[k] + X[k+1])
        return float(f[k] + de * (f[1] - f[0]))
    return float(f[k])


def decay_time_5pct(t, x, f1):
    """Time for the Hilbert envelope of the tip response to fall to 5% of its peak.
    If not reached inside the window (expected here: zeta=0.01 -> t5 ~ ln20/(zeta*w1)
    = 36-68 s > 20 s), extrapolate from a log-linear envelope fit (method flagged)."""
    A = np.abs(hilbert(x))
    k_edge = max(int(0.02 * len(t)), 4)           # trim Hilbert edge effects
    Ain, tin = A[k_edge:-k_edge], t[k_edge:-k_edge]
    ipk = int(np.argmax(Ain)); Apk = Ain[ipk]
    thr = 0.05 * Apk
    below = Ain <= thr
    for i in range(ipk + 1, len(Ain)):
        if below[i:].all():
            return float(tin[i]), "measured"
    i0 = min(ipk + int(2.0 / f1 / (t[1] - t[0])), len(Ain) - 10)   # skip ~2 periods
    coef = np.polyfit(tin[i0:], np.log(np.maximum(Ain[i0:], 1e-300)), 1)
    sigma = -coef[0]
    if sigma <= 0:
        return float("inf"), "fit_failed"
    return float(tin[ipk] + np.log(Apk / thr) / sigma), "fit_extrapolated"


# ---------------- case builder / worker ----------------
def build_beam(ei_name):
    """Beam for one stiffness case: EA scales with EI (same equivalent section), constant
    Rayleigh damping zeta=0.01 matched at (f1, 5 f1) of THIS beam. Returns beam + modal
    info (f1, stiffest discrete mode, alpha, beta)."""
    ei = EI_CASES[ei_name]
    b = Beam(N_EL, ei=ei, ea=EA_NOM * (ei / EI_NOM))
    Kt = b.tangent_stiffness()
    fr = b.free
    w2 = eigh(Kt[np.ix_(fr, fr)], b.M[np.ix_(fr, fr)], eigvals_only=True)
    w2 = np.sort(w2[w2 > 1e-9])
    f1 = float(np.sqrt(w2[0]) / (2 * np.pi))
    alpha, beta = b.set_rayleigh_damping(ZETA, f_lo=f1, K_t=Kt)
    return b, {"f1": f1, "f_max": float(np.sqrt(w2[-1]) / (2 * np.pi)),
               "alpha": alpha, "beta": beta}


def initial_velocity(beam, e):
    """Nodal initial velocities from the planarized base-jump field: TRANSVERSE ONLY
    (linear in y). The axial component e["a_ax"] is deliberately dropped (axial
    quasi-rigid assumption, see module docstring / README A2a)."""
    return beam.initial_velocity_field(lambda y: e["a_tr"] + e["b_tr"] * y, None)


def _case_worker(args):
    """One damped scan case (module-level: picklable for ProcessPoolExecutor; each
    worker rebuilds its beam deterministically -> results identical to serial)."""
    mode, ei_name, exc_c, t_end, n_eval, rtol, method = args
    b, info = build_beam(ei_name)
    ed0 = initial_velocity(b, exc_c)
    r = simulate(b, ed0, t_end, n_eval, rtol, damped=True, method=method)
    return mode, ei_name, info, r


# ---------------- main ----------------
def main(smoke=False, serial=False):
    t_wall = time.time()
    exc_modes = capture_excitations()

    # --- excitation projection + 3DOF vs 6DOF comparison ---
    exc = {m: panel_excitation(d["dv"], d["dw"]) for m, d in exc_modes.items()}
    comparison = {}
    for m in MODE_ORDER:
        e, d = exc[m], exc_modes[m]
        comparison[m] = {
            "|dv_B|_m_s": float(np.linalg.norm(d["dv"])),
            "|dw_B|_rad_s": float(np.linalg.norm(d["dw"])),
            "dw_B_rad_s": d["dw"].tolist(),
            "v0_transverse_root_mm_s": e["a_tr"] * 1e3,
            "v0_transverse_tip_mm_s": (e["a_tr"] + e["b_tr"] * L_TOT) * 1e3,
            "v0_axial_mm_s": e["a_ax"] * 1e3,
            "ignored_inplane_X_S_root_mm_s": e["ign_a"] * 1e3,
            "ignored_inplane_X_S_tip_mm_s": (e["ign_a"] + e["ign_b"] * L_TOT) * 1e3,
            "dT_capture_J": d["dT_J"],
        }

    # --- beam modal setup summary ---
    binfos = {name: build_beam(name) for name in EI_ORDER}
    print("[setup] f1 per case: "
          + ", ".join(f"{n}={binfos[n][1]['f1']:.4f} Hz" for n in EI_ORDER)
          + f"; stiffest discrete mode {max(v[1]['f_max'] for v in binfos.values()):.0f} Hz"
          f" (beta*K overdamps it: stability-limits explicit methods -> damped scan uses"
          f" {SCAN_METHOD} rtol={SCAN_RTOL})")

    # --- regression R1: undamped nominal 6DOF case, energy conservation (DOP853) ---
    bnom = binfos["nominal"][0]
    ed0 = initial_velocity(bnom, exc["6dof_rigid_lock"])
    r0 = simulate(bnom, ed0, t_end=5.0, n_eval=1000, rtol=1e-10, damped=False)
    drift = float(np.max(np.abs(r0["E"] - r0["E"][0])) / r0["E"][0])
    reg_R1 = drift < 1e-6
    print(f"[R1] undamped energy drift (5 s, DOP853 rtol 1e-10): {drift:.2e}  "
          f"{'PASS' if reg_R1 else 'FAIL'} (<1e-6)")

    # --- regression R3: integrator cross-check, damped nominal 6DOF, 2 s window ---
    t_x = time.time()
    ra = simulate(bnom, ed0, 2.0, 400, 1e-8, damped=True, method="DOP853")
    t_dop = time.time() - t_x; t_x = time.time()
    rb = simulate(bnom, ed0, 2.0, 400, SCAN_RTOL, damped=True, method=SCAN_METHOD)
    t_rad = time.time() - t_x
    xerr = float(np.max(np.abs(ra["tip"] - rb["tip"])) / np.max(np.abs(ra["tip"])))
    reg_R3 = xerr < 1e-3
    print(f"[R3] {SCAN_METHOD}(rtol {SCAN_RTOL}) vs DOP853(rtol 1e-8), damped 2 s: "
          f"max tip diff {xerr:.2e} rel  {'PASS' if reg_R3 else 'FAIL'} (<1e-3); "
          f"wall {t_dop:.1f}s vs {t_rad:.1f}s, nfev {ra['nfev']} vs {rb['nfev']}")
    if smoke:
        print("[smoke] regressions only; wall", f"{time.time()-t_wall:.1f} s")
        return

    # --- scan: 2 capture modes x 3 EI cases, damped, 15 s (parallel, deterministic) ---
    exc_scalars = {m: {k: exc[m][k] for k in ("a_tr", "b_tr", "a_ax")} for m in MODE_ORDER}
    jobs = [(m, n, exc_scalars[m], T_END, N_EVAL, SCAN_RTOL, SCAN_METHOD)
            for m in MODE_ORDER for n in EI_ORDER]
    raw = {}
    if serial:
        for j in jobs:
            m, n, info, r = _case_worker(j)
            raw[(m, n)] = (info, r)
    else:
        try:
            from concurrent.futures import ProcessPoolExecutor
            with ProcessPoolExecutor(max_workers=min(len(jobs), os.cpu_count() or 1)) as ex:
                for m, n, info, r in ex.map(_case_worker, jobs):
                    raw[(m, n)] = (info, r)
        except Exception as e:
            print(f"[warn] parallel scan failed ({e}); falling back to serial")
            for j in jobs:
                m, n, info, r = _case_worker(j)
                raw[(m, n)] = (info, r)

    cases, reg_R2 = {}, True
    for m in MODE_ORDER:
        for name in EI_ORDER:
            info, r = raw[(m, name)]
            # R2 energy decay, well-posed form: dE/dt = -edot' C edot <= 0 touches ZERO
            # at every velocity turning point, so a pointwise diff(E)<=eps test only
            # measures integrator noise there. Test instead:
            #  (i) strict decay over every half-period window (true signal ~ 2*pi*zeta
            #      ~ 6% of E per period >> noise ~ 1e-5*E0), and
            # (ii) pointwise guard against gross energy injection (> 1e-3*E0 per sample)
            k_half = max(1, int(round(0.5 / info["f1"] / (r["t"][1] - r["t"][0]))))
            E = r["E"]
            mono = bool(np.all(E[k_half:] < E[:-k_half])
                        and np.all(np.diff(E) <= 1e-3 * max(E[0], 1e-300)))
            reg_R2 &= mono
            f_dom = dominant_frequency(r["t"], r["tip"])
            t5, t5_method = decay_time_5pct(r["t"], r["tip"], info["f1"])
            ce = centrifugal_estimate(exc_modes[m]["w_post"], exc_modes[m]["d_lever"],
                                      exc[m], EI_CASES[name])
            tip_peak = float(np.max(np.abs(r["tip"])))
            cases[(m, name)] = {
                "res": r, "f1_hz": info["f1"],
                "tip_peak_mm": tip_peak * 1e3,
                "Mroot_peak_mNm": float(np.max(np.abs(r["Mroot"]))) * 1e3,
                "U_max_J": float(np.max(r["U"])),
                "f_dom_hz": f_dom, "t5pct_s": t5, "t5_method": t5_method,
                "E_monotonic": mono, "nfev": r["nfev"],
                "centrifugal_tip_m": ce["delta_c_tip_m"],
                "centrifugal_over_peak": ce["delta_c_tip_m"] / max(tip_peak, 1e-300),
                "coriolis_ratio_2w_over_w1": 2.0 * ce["w_post_rad_s"]
                                             / (2 * np.pi * info["f1"]),
            }
            print(f"[case] {m:16s} {name:14s} tip {tip_peak*1e3:8.4f} mm  "
                  f"Mroot {cases[(m,name)]['Mroot_peak_mNm']:8.4f} mNm  "
                  f"f {f_dom:.3f} Hz  t5 {t5:6.1f} s ({t5_method})  nfev {r['nfev']}")
    print(f"[R2] damped energy monotonic decay: {'PASS' if reg_R2 else 'FAIL'}")

    # --- figure (a): tip response matrix 2x3 ---
    fig, ax = plt.subplots(2, 3, figsize=(15, 7), sharex=True)
    for i, m in enumerate(MODE_ORDER):
        for j, name in enumerate(EI_ORDER):
            c = cases[(m, name)]; r = c["res"]
            A = np.abs(hilbert(r["tip"]))
            a = ax[i, j]
            a.plot(r["t"], r["tip"] * 1e3, lw=0.7, color="tab:blue")
            a.plot(r["t"], A * 1e3, "--", lw=1.0, color="tab:red", label="envelope")
            a.plot(r["t"], -A * 1e3, "--", lw=1.0, color="tab:red")
            a.set_title(f"{m} | {name} (f1={c['f1_hz']:.2f} Hz)\n"
                        f"peak {c['tip_peak_mm']:.3g} mm, f_dom {c['f_dom_hz']:.3f} Hz",
                        fontsize=9)
            a.grid(alpha=.3)
            if i == 1: a.set_xlabel("t [s]")
            if j == 0: a.set_ylabel("tip transverse disp [mm]")
    ax[0, 0].legend(fontsize=8)
    fig.suptitle(f"sim_07a tip transverse response — {TARGET} @{TUMBLE_DPS} deg/s, "
                 f"v_app={V_APP} m/s, one-way base-jump excitation, zeta={ZETA}", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(RES, "tip_response_matrix.png"), dpi=130); plt.close(fig)

    # --- figure (b): root moment + strain energy ---
    fig, ax = plt.subplots(2, 2, figsize=(13, 7.5), sharex=True)
    colors = {"flexible_low": "tab:green", "nominal": "tab:blue",
              "flexible_high": "tab:red"}
    for jm, m in enumerate(MODE_ORDER):
        for name in EI_ORDER:
            c = cases[(m, name)]; r = c["res"]
            ax[0, jm].plot(r["t"], r["Mroot"] * 1e3, lw=0.7, color=colors[name],
                           label=f"{name} (f1={c['f1_hz']:.2f} Hz)")
            ax[1, jm].semilogy(r["t"], np.maximum(r["U"], 1e-16), lw=0.8,
                               color=colors[name], label=name)
        dT = exc_modes[m]["dT_J"]
        ax[1, jm].axhline(dT, color="k", ls="--", lw=1.2,
                          label=f"capture dT = {dT*1e3:.2f} mJ (upper bound)")
        ax[0, jm].set_title(f"root bending moment — {m}", fontsize=10)
        ax[1, jm].set_title(f"strain energy — {m}", fontsize=10)
        ax[1, jm].set_xlabel("t [s]")
        for a in (ax[0, jm], ax[1, jm]): a.grid(alpha=.3, which="both")
        ax[0, jm].legend(fontsize=8); ax[1, jm].legend(fontsize=8)
    ax[0, 0].set_ylabel("M_root [mN m]"); ax[1, 0].set_ylabel("U [J] (log)")
    fig.suptitle("sim_07a root moment & strain energy vs capture-dT consistency bound\n"
                 "(one-way model: beam energy is set kinematically by 1/2 int mu v0^2 dy, "
                 "NOT bounded by dT — see README)", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(RES, "root_moment_and_energy.png"), dpi=130); plt.close(fig)

    # --- (c) CSV summary ---
    csv_path = os.path.join(RES, "task_response_summary.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        wtr = csv.writer(f)
        wtr.writerow(["capture_mode", "ei_case", "EI_Nm2", "f1_hz",
                      "tip_peak_mm", "Mroot_peak_mNm", "U_max_J", "f_dom_hz",
                      "t5pct_s", "t5_method", "v0_tr_root_mm_s", "v0_tr_tip_mm_s",
                      "dT_capture_J", "Umax_over_dT",
                      "centrifugal_tip_over_peak", "coriolis_2w_over_w1"])
        for m in MODE_ORDER:
            for name in EI_ORDER:
                c = cases[(m, name)]; e = exc[m]
                wtr.writerow([m, name, EI_CASES[name], round(c["f1_hz"], 5),
                              round(c["tip_peak_mm"], 6), round(c["Mroot_peak_mNm"], 6),
                              f"{c['U_max_J']:.4e}", round(c["f_dom_hz"], 4),
                              round(c["t5pct_s"], 2), c["t5_method"],
                              round(e["a_tr"] * 1e3, 6),
                              round((e["a_tr"] + e["b_tr"] * L_TOT) * 1e3, 6),
                              f"{exc_modes[m]['dT_J']:.4e}",
                              f"{c['U_max_J'] / exc_modes[m]['dT_J']:.3e}",
                              f"{c['centrifugal_over_peak']:.3e}",
                              f"{c['coriolis_ratio_2w_over_w1']:.3e}"])

    # --- structured result dict ---
    summary = {
        "scenario": {"target": TARGET, "tumble_dps": TUMBLE_DPS, "v_app_m_s": V_APP,
                     "panel": "+Y_S (root F at [-0.05675,+0.11315,0] in S)",
                     "n_el": N_EL, "zeta": ZETA, "t_end_s": T_END,
                     "integrator": f"{SCAN_METHOD} rtol={SCAN_RTOL} (scan; stiff via "
                                    "Rayleigh beta*K), DOP853 for regressions"},
        "excitation_comparison_3dof_vs_6dof": comparison,
        "conclusion_3dof_vs_6dof": (
            "|dw_B| is similar (0.047 vs 0.053 rad/s) but its DIRECTION differs: the "
            "6DOF rigid lock transmits a couple that puts ~0.046 rad/s about X_inertial "
            "(bending direction of the panel) while the 3DOF point capture's dw is "
            "almost purely about Z (in-plane) -> out-of-plane transverse excitation and "
            "response are ~2 orders of magnitude smaller for the point capture."),
        "regressions": {"R1_undamped_drift": drift, "R1_PASS": bool(reg_R1),
                        "R2_damped_monotonic_PASS": bool(reg_R2),
                        "R3_integrator_crosscheck_rel": xerr, "R3_PASS": bool(reg_R3)},
        "cases": {f"{m}/{n}": {k: v for k, v in cases[(m, n)].items() if k != "res"}
                  for m in MODE_ORDER for n in EI_ORDER},
        "outputs": ["results/tip_response_matrix.png",
                    "results/root_moment_and_energy.png",
                    "results/task_response_summary.csv"],
        "wall_time_s": round(time.time() - t_wall, 1),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False, default=float))
    return summary


if __name__ == "__main__":
    main(smoke="--smoke" in sys.argv, serial="--serial" in sys.argv)
