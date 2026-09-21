"""sim_04_v2: capture corridor with the EXACT post-capture rate from sim_06's validated
plastic-rigidization solver (30_simulation/common/capture_impulse.py), replacing the v0 heuristic
post_rate ~ tumble * inertia_scale * I_t/(I_S+I_t).

Reuses sim_04 v0's own functions (visibility, base_peak, thresholds) by importing the v0
module — no copy-paste drift; only the post-capture gate changes. Everything else (gate
order, grid, thresholds) is identical, so any classification migration is attributable to
the impulse model alone.

Outputs into results/:
  corridor_migration_v2.csv     per-case old/new classification + reasons + post rates
  corridor_migration_matrix.png migration matrix + failure-mode share change
  corridor_boundary_v2.png      heuristic vs exact vs robust(+20% I_t) SAFE boundaries
Prints the false-safe count (v0 SAFE -> v2 FAIL) — the headline number."""
import os, sys, csv
import importlib.util
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(HERE, "results"); os.makedirs(RES, exist_ok=True)
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from capture_impulse import capture_post_state  # noqa: E402

# ---- load sim_04 v0 as a module (executes its grid once; deterministic, seconds) ----
spec = importlib.util.spec_from_file_location("sim_04_v0", os.path.join(HERE, "sim_04_capture_corridor.py"))
v0 = importlib.util.module_from_spec(spec); spec.loader.exec_module(v0)

_exact_cache = {}
def post_rate_exact(target, tumble, approach, inertia_scale):
    key = (target, round(float(tumble), 6), round(float(approach), 6), inertia_scale)
    if key not in _exact_cache:
        r, _, _ = capture_post_state(target, float(tumble), float(approach), inertia_scale=inertia_scale)
        assert r["validity"]["momentum_ok"] and r["validity"]["plastic_dT_nonneg"]
        _exact_cache[key] = float(np.rad2deg(np.linalg.norm(r["w_plus"])))
    return _exact_cache[key]

def classify_v2(target, tumble, approach, arm_speed, pose_err, inertia_scale, reaction_aware):
    """Identical gates/order to v0.classify, but the post-capture gate uses the exact rate."""
    vr, window = v0.visibility(target, tumble)
    base_used = v0.base_peak(arm_speed) * (v0.RNS_FACTOR if reaction_aware else 1.0)
    reach_time = v0.BASE_REACH_TIME / arm_speed
    v_max = v0.V0 / (1 + tumble / v0.TUMBLE_K)
    post_rate = post_rate_exact(target, tumble, approach, inertia_scale)
    if pose_err >= v0.POSE_LIMIT: r = "POSE_UNCERTAINTY_FAIL"
    elif base_used >= v0.BASE_LIMIT: r = "BASE_REACTION_FAIL"
    elif vr <= v0.VIS_MIN: r = "VISIBILITY_FAIL"
    elif window <= reach_time: r = "WINDOW_FAIL"
    elif approach > v_max: r = "APPROACH_SPEED_FAIL"
    elif v0.CLEARANCE_NOMINAL <= v0.CLR_MIN: r = "CLEARANCE_FAIL"
    elif post_rate > v0.POST_CAP_BUDGET: r = "INERTIA_UNCERTAINTY_FAIL"
    else: r = "SAFE"
    return ("SAFE" if r == "SAFE" else "FAIL"), r, post_rate

# ---- same 1620-case grid, v0 vs v2 side by side ----
import itertools
grid = list(itertools.product(v0.TARGETS, v0.TUMBLE, v0.APPROACH, v0.ARM, v0.POSE, v0.INERTIA, v0.MODE))
mig = {"SAFE->SAFE": 0, "SAFE->FAIL": 0, "FAIL->SAFE": 0, "FAIL->FAIL": 0}
old_counts = {r: 0 for r in v0.REASONS}; new_counts = {r: 0 for r in v0.REASONS}
rows = []
for i, (tg, tu, ap, ar, po, ine, mode) in enumerate(grid):
    m_old = v0.classify(tg, tu, ap, ar, po, ine, mode)
    res_new, reason_new, pr_new = classify_v2(tg, tu, ap, ar, po, ine, mode)
    key = f"{m_old['result']}->{res_new}"
    mig[key] += 1
    old_counts[m_old["failure_reason"]] += 1; new_counts[reason_new] += 1
    rows.append([f"C{i+1:04d}", tg, tu, ap, ar, po, ine, int(mode),
                 m_old["result"], m_old["failure_reason"], m_old["post_capture_rate_dps"],
                 res_new, reason_new, round(pr_new, 3), key])

with open(os.path.join(RES, "corridor_migration_v2.csv"), "w", newline="\n", encoding="utf-8") as f:
    wr = csv.writer(f)
    wr.writerow(["case_id", "target", "tumble_dps", "approach_mps", "arm_speed", "pose_err_deg",
                 "inertia_scale", "reaction_aware", "v0_result", "v0_reason", "v0_post_rate_dps",
                 "v2_result", "v2_reason", "v2_post_rate_dps", "migration"])
    wr.writerows(rows)

false_safe = [r for r in rows if r[14] == "SAFE->FAIL"]
conservative = [r for r in rows if r[14] == "FAIL->SAFE"]

# ---- fig 1: migration matrix + failure-mode share change ----
fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
mat = np.array([[mig["SAFE->SAFE"], mig["SAFE->FAIL"]], [mig["FAIL->SAFE"], mig["FAIL->FAIL"]]])
im = ax[0].imshow(mat, cmap="RdYlGn_r", vmin=0, vmax=max(1, mat.max()))
for (i, j), v in np.ndenumerate(mat):
    label = [["kept SAFE", "v0 FALSE-SAFE"], ["v0 conservative", "kept FAIL"]][i][j]
    ax[0].text(j, i, f"{label}\n{v}", ha="center", va="center", fontsize=11,
               fontweight="bold" if (i, j) == (0, 1) else "normal")
ax[0].set_xticks([0, 1], ["v2 SAFE", "v2 FAIL"]); ax[0].set_yticks([0, 1], ["v0 SAFE", "v0 FAIL"])
ax[0].set_title(f"sim_04 v0(heuristic) -> v2(exact impulse) migration, {len(grid)} cases\n"
                f"SAFE: {mig['SAFE->SAFE'] + mig['SAFE->FAIL']} -> {mig['SAFE->SAFE'] + mig['FAIL->SAFE']}")
ks = [k for k in v0.REASONS]
x = np.arange(len(ks)); w = 0.38
ax[1].bar(x - w/2, [old_counts[k] for k in ks], w, label="v0 heuristic")
ax[1].bar(x + w/2, [new_counts[k] for k in ks], w, label="v2 exact impulse")
ax[1].set_xticks(x, [k.replace("_FAIL", "").replace("_", "\n") for k in ks], fontsize=7)
ax[1].set_ylabel("cases"); ax[1].legend(); ax[1].set_title("failure-mode distribution shift")
for a in ax: a.grid(alpha=.25, axis="y")
fig.tight_layout(); fig.savefig(os.path.join(RES, "corridor_migration_matrix.png"), dpi=130); plt.close(fig)

# ---- fig 2: SAFE-boundary comparison (reaction-aware, nominal arm/pose) ----
TU = np.linspace(0.2, 6.0, 49); AP = np.linspace(0.002, 0.030, 29)
fig, axs = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
for k, tg in enumerate(v0.TARGETS):
    def safe_mask(post_fn):
        Z = np.zeros((len(TU), len(AP)), bool)
        for a, tu in enumerate(TU):
            vr, window = v0.visibility(tg, tu)
            v_max = v0.V0 / (1 + tu / v0.TUMBLE_K)
            for b, ap in enumerate(AP):
                ok = (2.0 < v0.POSE_LIMIT and
                      v0.base_peak(1.0) * v0.RNS_FACTOR < v0.BASE_LIMIT and
                      vr > v0.VIS_MIN and window > v0.BASE_REACH_TIME and
                      ap <= v_max and post_fn(tg, tu, ap) <= v0.POST_CAP_BUDGET)
                Z[a, b] = ok
        return Z
    _, I_t = v0.tgt(tg)
    Z_old = safe_mask(lambda t, tu, ap: tu * 1.0 * I_t / (v0.I_S + I_t))
    Z_new = safe_mask(lambda t, tu, ap: post_rate_exact(t, tu, ap, 1.0))
    Z_rob = safe_mask(lambda t, tu, ap: post_rate_exact(t, tu, ap, 1.2))
    ax = axs[k]
    ax.contourf(AP*1000, TU, Z_new, levels=[0.5, 1.5], colors=["#c8e6c9"])
    for Z, color, ls, lab in [(Z_old, "tab:gray", "--", "v0 heuristic boundary"),
                              (Z_new, "tab:green", "-", "v2 exact boundary"),
                              (Z_rob, "tab:red", ":", "v2 robust (+20% target inertia)")]:
        ax.contour(AP*1000, TU, Z.astype(float), levels=[0.5], colors=[color],
                   linestyles=[ls], linewidths=2)
        ax.plot([], [], color=color, ls=ls, lw=2, label=lab)
    ax.set_title(f"{tg} (reaction-aware, pose=2deg, arm=1.0)")
    ax.set_xlabel("approach velocity [mm/s]")
    ax.grid(alpha=.3); ax.legend(fontsize=8, loc="upper right")
axs[0].set_ylabel("target tumble rate [deg/s]")
fig.suptitle("sim_04_v2 SAFE-corridor boundary: heuristic vs exact impulse vs robust — "
             "shaded = v2 SAFE region", fontsize=11)
fig.tight_layout(); fig.savefig(os.path.join(RES, "corridor_boundary_v2.png"), dpi=130); plt.close(fig)

safe_v0 = mig["SAFE->SAFE"] + mig["SAFE->FAIL"]; safe_v2 = mig["SAFE->SAFE"] + mig["FAIL->SAFE"]
fs_targets = {}
for r in false_safe:
    fs_targets.setdefault(r[1], []).append((r[2], r[3], r[6]))
print({"cases": len(grid), "migration": mig,
       "safe_v0": safe_v0, "safe_v2": safe_v2,
       "false_safe_cases": len(false_safe), "conservative_cases": len(conservative),
       "false_safe_breakdown": {k: sorted(set(v)) for k, v in fs_targets.items()},
       "outputs": ["corridor_migration_v2.csv", "corridor_migration_matrix.png",
                   "corridor_boundary_v2.png"]})
