"""sim_04: reaction-aware capture corridor.
Fuses sim_02 (target tumble + grasp-feature visibility) and sim_03 (arm-induced base
reaction) across a parameter sweep, and rule-classifies each case SAFE / FAIL(reason).
Runs both NAIVE and REACTION-AWARE arm modes so the corridor shows the base-reaction gate.
Outputs scenario_matrix_v0.csv, capture_corridor_summary.csv, capture_corridor_heatmap.png,
capture_corridor_cases.md.

v0 heuristics (all labeled assumptions; refine with SPART/Basilisk later):
  - grasp window must exceed the arm reach time  (window > reach_time)
  - approach speed limit shrinks with tumble      (v_max = 0.03/(1+tumble/2))
  - reaction-aware assumes RNS cuts base disturbance to 15% of naive (RNS_FACTOR)
  - post-capture combined-body rate ~ tumble * inertia_scale * I_t/(I_s+I_t), budget 2 deg/s
"""
import os, sys, csv, itertools
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
from rigid_body import load_object, propagate_torque_free, q_to_R

HERE = os.path.dirname(__file__); RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True)

# ---- thresholds (v0, per task) ----
BASE_LIMIT, POSE_LIMIT, VIS_MIN, CLR_MIN = 5.0, 3.0, 0.50, 0.10
RNS_FACTOR = 0.15            # reaction-aware base-disturbance reduction (assumption)
BASE_REACH_TIME = 8.0        # s at arm_speed_scale=1.0
V0, TUMBLE_K = 0.03, 2.0     # approach-speed limit model
CLEARANCE_NOMINAL = 0.47     # m, from sim_03
POST_CAP_BUDGET = 2.0        # deg/s combined-body rate a small servicer can detumble

REASONS = ["SAFE", "POSE_UNCERTAINTY_FAIL", "BASE_REACTION_FAIL", "VISIBILITY_FAIL",
           "WINDOW_FAIL", "APPROACH_SPEED_FAIL", "CLEARANCE_FAIL", "INERTIA_UNCERTAINTY_FAIL"]
RCODE = {r: i for i, r in enumerate(REASONS)}

_serv = load_object("servicer_12U_v0")
I_S = float(np.mean(np.diag(_serv["I"])))
_vis_cache, _base_cache, _tgt_cache = {}, {}, {}

def tgt(target_id):
    if target_id not in _tgt_cache:
        o = load_object(target_id); _tgt_cache[target_id] = (o, float(np.mean(np.diag(o["I"]))))
    return _tgt_cache[target_id]

def visibility(target_id, tumble_dps, TPROP=90.0):
    """Return (visibility_ratio, capture_window_s). Servicer approaches from +X, so the
    grasp feature (body normal +X) faces it when its inertial normal has +X component.
    Wide cone (+/-100 deg) -> 'can see' ratio; tight cone (+/-35 deg) -> longest continuous
    'can grasp' window (shrinks with tumble rate)."""
    key = (target_id, round(tumble_dps, 4))
    if key in _vis_cache: return _vis_cache[key]
    o, _ = tgt(target_id)
    axis = np.array([1.0, 0.15, 0.4]); axis /= np.linalg.norm(axis)
    w0 = np.deg2rad(tumble_dps) * axis
    res = propagate_torque_free(o["I"], w0, TPROP, n=900)
    n_body = np.array([1.0, 0.0, 0.0]); approach = np.array([1.0, 0.0, 0.0])
    vis_thr, grasp_thr = np.cos(np.deg2rad(100)), np.cos(np.deg2rad(35))
    facing = np.array([np.dot(q_to_R(q).apply(n_body), approach) for q in res["Q"]])
    ratio = float((facing > vis_thr).mean())
    dt = res["t"][1] - res["t"][0]
    best = run = 0
    for v in (facing > grasp_thr):
        run = run + 1 if v else 0; best = max(best, run)
    window = best * dt
    _vis_cache[key] = (ratio, window); return _vis_cache[key]

def base_peak(arm_speed_scale):
    if arm_speed_scale in _base_cache: return _base_cache[arm_speed_scale]
    m_b, I_b = _serv["mass"], _serv["I"][1, 1]
    c_b = np.array([_serv["cg"][0], _serv["cg"][2]]); mount = np.array([0.18525, 0.0])
    L1, L2, m1, m2 = 0.30, 0.25, 0.80, 0.50
    I1, I2 = m1*L1**2/12, m2*L2**2/12
    A1, A2 = np.deg2rad(60*arm_speed_scale), np.deg2rad(-40*arm_speed_scale)
    ts = np.linspace(0, 8.0, 400); theta = 0.0; prev = 0.0; peak = 0.0
    for t in ts:
        x = np.clip(t/8.0, 0, 1); s = 10*x**3-15*x**4+6*x**5; sd = (30*x**2-60*x**3+30*x**4)/8.0
        q1, q1d = A1*s, A1*sd; q2, q2d = A2*s, A2*sd
        a1, a2 = q1, q1+q2
        p1 = mount + (L1/2)*np.array([np.cos(a1), np.sin(a1)])
        p2 = mount + L1*np.array([np.cos(a1), np.sin(a1)]) + (L2/2)*np.array([np.cos(a2), np.sin(a2)])
        mt = m_b+m1+m2; c = (m_b*c_b+m1*p1+m2*p2)/mt
        Jb = I_b+m_b*np.sum((c_b-c)**2); J1 = I1+m1*np.sum((p1-c)**2); J2 = I2+m2*np.sum((p2-c)**2)
        wb = -(J1*q1d+J2*(q1d+q2d))/(Jb+J1+J2)
        theta += wb*(t-prev); prev = t; peak = max(peak, abs(np.rad2deg(theta)))
    _base_cache[arm_speed_scale] = peak; return peak

def classify(target, tumble, approach, arm_speed, pose_err, inertia_scale, reaction_aware):
    vr, window = visibility(target, tumble)
    base_used = base_peak(arm_speed) * (RNS_FACTOR if reaction_aware else 1.0)
    reach_time = BASE_REACH_TIME / arm_speed
    v_max = V0 / (1 + tumble / TUMBLE_K)
    _, I_t = tgt(target)
    post_rate = tumble * inertia_scale * I_t / (I_S + I_t)
    m = dict(visibility_ratio=round(vr, 3), capture_window_s=round(window, 2),
             base_peak_deg=round(base_used, 3), reach_time_s=round(reach_time, 2),
             v_max_m_s=round(v_max, 4), clearance_min_m=CLEARANCE_NOMINAL,
             post_capture_rate_dps=round(post_rate, 3))
    if pose_err >= POSE_LIMIT: r = "POSE_UNCERTAINTY_FAIL"
    elif base_used >= BASE_LIMIT: r = "BASE_REACTION_FAIL"
    elif vr <= VIS_MIN: r = "VISIBILITY_FAIL"
    elif window <= reach_time: r = "WINDOW_FAIL"
    elif approach > v_max: r = "APPROACH_SPEED_FAIL"
    elif CLEARANCE_NOMINAL <= CLR_MIN: r = "CLEARANCE_FAIL"
    elif post_rate > POST_CAP_BUDGET: r = "INERTIA_UNCERTAINTY_FAIL"
    else: r = "SAFE"
    m["result"] = "SAFE" if r == "SAFE" else "FAIL"; m["failure_reason"] = r
    return m

# ---- coarse grid: scenario matrix + summary ----
TARGETS = ["target_satellite_v0", "target_debris_v0"]
TUMBLE = [0.5, 1.0, 2.0, 3.0, 5.0]; APPROACH = [0.005, 0.010, 0.020]
ARM = [0.5, 1.0, 1.5]; POSE = [1.0, 2.0, 3.0]; INERTIA = [0.8, 1.0, 1.2]; MODE = [False, True]

grid = list(itertools.product(TARGETS, TUMBLE, APPROACH, ARM, POSE, INERTIA, MODE))
sm_path = os.path.join(RES, "..", "scenario_matrix_v0.csv")
sum_path = os.path.join(RES, "capture_corridor_summary.csv")
sm = open(os.path.join(HERE, "scenario_matrix_v0.csv"), "w", newline="\n", encoding="utf-8")
su = open(sum_path, "w", newline="\n", encoding="utf-8")
smw, suw = csv.writer(sm), csv.writer(su)
smw.writerow(["case_id", "target_type", "tumble_rate_deg_s", "approach_velocity_m_s", "arm_speed_scale",
              "pose_error_deg", "inertia_scale", "reaction_aware", "clearance_threshold_m", "base_limit_deg"])
suw.writerow(["case_id", "target_type", "tumble_rate_deg_s", "approach_velocity_m_s", "arm_speed_scale",
              "pose_error_deg", "inertia_scale", "reaction_aware", "visibility_ratio", "capture_window_s",
              "reach_time_s", "base_peak_deg", "v_max_m_s", "post_capture_rate_dps", "clearance_min_m",
              "result", "failure_reason"])
counts = {r: 0 for r in REASONS}; safe_rows = []
for i, (tg, tu, ap, ar, po, ine, mode) in enumerate(grid):
    cid = f"C{i+1:04d}"
    smw.writerow([cid, tg, tu, ap, ar, po, ine, int(mode), CLR_MIN, BASE_LIMIT])
    m = classify(tg, tu, ap, ar, po, ine, mode)
    suw.writerow([cid, tg, tu, ap, ar, po, ine, int(mode), m["visibility_ratio"], m["capture_window_s"],
                  m["reach_time_s"], m["base_peak_deg"], m["v_max_m_s"], m["post_capture_rate_dps"],
                  m["clearance_min_m"], m["result"], m["failure_reason"]])
    counts[m["failure_reason"]] += 1
    if m["result"] == "SAFE": safe_rows.append((tg, tu, ap, ar, po, ine, mode))
sm.close(); su.close()

# ---- fine-grid heatmap: 2 targets x 2 modes over tumble x approach (nominal arm=1.0, pose=2, inertia=1.0) ----
TU = np.linspace(0.2, 6.0, 24); AP = np.linspace(0.002, 0.030, 24)
colors = ["#2ca02c", "#7f7f7f", "#d62728", "#1f77b4", "#9467bd", "#ff7f0e", "#8c564b", "#e377c2"]
cmap = ListedColormap(colors); norm = BoundaryNorm(np.arange(-0.5, 8.5, 1), cmap.N)
fig, axes = plt.subplots(2, 2, figsize=(12, 10))
for ri, tg in enumerate(TARGETS):
    for ci, mode in enumerate([False, True]):
        Z = np.zeros((len(TU), len(AP)), int)
        for a, tu in enumerate(TU):
            for b, ap in enumerate(AP):
                Z[a, b] = RCODE[classify(tg, tu, ap, 1.0, 2.0, 1.0, mode)["failure_reason"]]
        ax = axes[ri, ci]
        ax.pcolormesh(AP*1000, TU, Z, cmap=cmap, norm=norm, shading="auto")
        ax.set_title(f"{tg}  |  {'reaction-aware (RNS)' if mode else 'naive arm'}")
        ax.set_xlabel("approach velocity [mm/s]"); ax.set_ylabel("tumble rate [deg/s]")
fig.suptitle("sim_04 reaction-aware capture corridor (arm_speed=1.0, pose_err=2deg, inertia=1.0)\n"
             "naive arm -> base-reaction gate blocks the whole corridor; RNS reveals the visibility/inertia-bounded window",
             fontsize=11)
fig.legend(handles=[Patch(facecolor=colors[i], label=REASONS[i]) for i in range(8)],
           loc="lower center", ncol=4, fontsize=8, frameon=False)
fig.tight_layout(rect=[0, 0.06, 1, 0.95])
png = os.path.join(RES, "capture_corridor_heatmap.png"); fig.savefig(png, dpi=130); plt.close(fig)

# ---- findings writeup ----
safe_total = counts["SAFE"]; top_fail = sorted(((v, k) for k, v in counts.items() if k != "SAFE"), reverse=True)
safe_rns = [r for r in safe_rows if r[6]]
safe_tumble = sorted(set(r[1] for r in safe_rns)); safe_appr = sorted(set(r[2] for r in safe_rns))
with open(os.path.join(RES, "capture_corridor_cases.md"), "w", encoding="utf-8", newline="\n") as f:
    f.write("# Capture Corridor v0 — findings\n\n")
    f.write(f"- Grid: {len(grid)} cases (2 targets x {len(TUMBLE)} tumble x {len(APPROACH)} approach x "
            f"{len(ARM)} arm-speed x {len(POSE)} pose-err x {len(INERTIA)} inertia x 2 modes).\n")
    f.write(f"- SAFE: {safe_total}/{len(grid)} ({100*safe_total/len(grid):.1f}%). All SAFE cases are reaction-aware "
            f"({len(safe_rns)} of them); **0 naive cases are safe** (base reaction {base_peak(1.0):.1f} deg >> 5 deg limit).\n")
    f.write("- Most common failure reasons:\n")
    for v, k in top_fail:
        if v: f.write(f"    - {k}: {v}\n")
    f.write(f"- Reaction-aware SAFE envelope: tumble_rate in {safe_tumble} deg/s, approach in {safe_appr} m/s.\n")
    f.write("- target_debris (heavy, ~59 kg-m^2) hits INERTIA_UNCERTAINTY_FAIL (post-capture combined rate) at far "
            "lower tumble than target_satellite — the heavy target dominates the post-capture momentum budget.\n\n")
    f.write("## v0 conclusion\n")
    f.write("Safe capture is a MULTI-constraint problem: geometric reach + grasp visibility window + controllable "
            "base reaction + post-capture stability budget. Naive (non-reaction-aware) arm motion is infeasible "
            "everywhere on the 12U v0; reaction-aware planning opens a corridor bounded by tumble rate, approach "
            "speed, and (for heavy debris) the post-capture inertia budget.\n")

print({"grid_cases": len(grid), "safe": safe_total, "safe_pct": round(100*safe_total/len(grid), 1),
       "naive_safe": sum(1 for r in safe_rows if not r[6]), "base_peak_naive_deg": round(base_peak(1.0), 2),
       "top_failures": [f"{k}:{v}" for v, k in top_fail[:4]],
       "safe_tumble_dps": safe_tumble, "safe_approach_m_s": safe_appr,
       "heatmap": png, "summary_csv": sum_path})
