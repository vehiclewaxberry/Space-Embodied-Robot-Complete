"""figures.py -- sim_10 论文图 F1-F4（设计书 §6）。数据全部读 results/ 扫描工件。
F1 Mission Feasibility Map：(μ, ω̂) 四区域 ×3 几何类 + 解析(虚线)/精确(实线)边界 +
   两任务锚点星标 + e16 REPEAT_CORE 18 例动力学评估点投影。
F2 h*-j* 资源平面；F3 λ 敏感性边界族（G1）；F4 δ_analytic 偏差场。
用法：python src/figures.py"""
import csv
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt            # noqa: E402
from matplotlib.colors import ListedColormap, LogNorm   # noqa: E402
from matplotlib.patches import Patch       # noqa: E402
import numpy as np                         # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from feasibility_core import load_cfg, geometry_classes, analytic_point, REPO  # noqa: E402

RES = os.path.normpath(os.path.join(HERE, "..", "results"))
REGION_ORDER = ["WHEELS_ONLY_FEASIBLE", "THRUSTER_REQUIRED_FEASIBLE",
                "INFEASIBLE_RESOURCE", "INFEASIBLE_RATE"]
REGION_COLOR = {"WHEELS_ONLY_FEASIBLE": "#1b9e77",
                "THRUSTER_REQUIRED_FEASIBLE": "#7570b3",
                "INFEASIBLE_RESOURCE": "#e7298a",
                "INFEASIBLE_RATE": "#d95f02"}
REGION_LABEL = {"WHEELS_ONLY_FEASIBLE": "wheels-only feasible",
                "THRUSTER_REQUIRED_FEASIBLE": "thruster required",
                "INFEASIBLE_RESOURCE": "infeasible (resource)",
                "INFEASIBLE_RATE": "infeasible (rate)"}


def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_data(cfg):
    phys = read_csv(os.path.join(RES, cfg["output"]["physics_csv"]))
    gates = read_csv(os.path.join(RES, cfg["output"]["gates_csv"]))
    dt = cfg["actuator_tiers"]["default_tier"]
    tid = f"{dt['wheel']}|{dt['isp']}|l{float(dt['lever_m']):g}"
    gmap = {r["point_id"]: r for r in gates if r["tier_id"] == tid}
    for p in phys:
        p.update(gmap[p["point_id"]])
    return phys, tid


def slice_grid(phys, cls, lam=1.0, alpha=0.0):
    rows = [r for r in phys if r["geometry_class"] == cls and not r["anchor"]
            and abs(float(r["lambda_scale"]) - lam) < 1e-12
            and abs(float(r["alpha"]) - alpha) < 1e-12]
    mus = np.array(sorted({float(r["mu"]) for r in rows}))
    oms = np.array(sorted({float(r["omega_hat"]) for r in rows}))
    Z = np.zeros((len(oms), len(mus)), dtype=int)
    for r in rows:
        i = np.searchsorted(oms, float(r["omega_hat"]))
        j = np.searchsorted(mus, float(r["mu"]))
        Z[i, j] = REGION_ORDER.index(r["region"])
    return mus, oms, Z, rows


def analytic_boundary(cfg, classes, cls, lam=1.0):
    """门1 解析边界：ω̂_crit = (Ī_t+Ī_s+μ_red d⊥²)/Ī_t（ω⁺≈κ_ω ω_t 的标量反解）。"""
    sc = cfg["scan"]
    w_b = float(cfg["gates"]["post_capture_rate_max_dps"])
    m_bus = float(cfg["mass_reference"]["servicer_bus_kg"])
    mus = np.geomspace(*map(float, sc["mu_range_log"]), 200)
    crit = []
    for mu in mus:
        an = analytic_point(classes[cls], mu * m_bus, 1.0, lam)   # ω⁺(1°/s) -> κ_ω
        kappa = an["w_plus_analytic_dps"]
        crit.append(w_b / kappa / w_b if kappa > 0 else np.inf)   # ω̂_crit = 1/κ_ω
    return mus, np.array(crit)


def e16_projection():
    rows = read_csv(os.path.join(REPO, "30_simulation", "e16_sync_capture", "results",
                                 "sync_capture_216.csv"))
    return [float(r["post_capture_omega_dps"]) for r in rows
            if r["dynamics_status"] == "EVALUATED"]


def fig_f1(cfg, classes, phys, tid):
    cmap = ListedColormap([REGION_COLOR[k] for k in REGION_ORDER])
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), sharey=True)
    anchors = [r for r in phys if r["anchor"]]
    w_b = float(cfg["gates"]["post_capture_rate_max_dps"])
    e16_w = e16_projection()
    for ax, cls in zip(axes, cfg["scan"]["geometry_classes"]):
        mus, oms, Z, _ = slice_grid(phys, cls)
        ax.pcolormesh(mus, oms, Z, cmap=cmap, vmin=-0.5, vmax=3.5, shading="nearest")
        bm, bc = analytic_boundary(cfg, classes, cls)
        ax.plot(bm, bc, "k--", lw=1.4, label="gate-1 boundary (coaxial analytic)")
        for a in anchors:
            if a["geometry_class"] != cls:
                continue
            ax.plot(float(a["mu"]), float(a["omega_hat"]), "k*", ms=16,
                    mfc="yellow", mew=1.2)
            name = "debris 150 kg" if "debris" in a["anchor"] else "satellite 22 kg"
            ax.annotate(f"{name}\n$\\omega^+$={float(a['w_plus_dps']):.2f}°/s",
                        (float(a["mu"]), float(a["omega_hat"])),
                        textcoords="offset points", xytext=(8, -2), fontsize=8)
        if cls == "G1_slender" and e16_w:
            jitter = np.linspace(0.92, 1.08, len(e16_w))
            ax.scatter(6.25 * jitter, np.full(len(e16_w), 1.5), s=12,
                       c="k", marker=".", zorder=5)
            ax.annotate(f"e16: {len(e16_w)} rigid-sync cases\n"
                        f"$\\omega^+$∈[{min(e16_w):.2f},{max(e16_w):.2f}]°/s "
                        "all CORE_UNSAFE", (6.25, 1.5),
                        textcoords="offset points", xytext=(-120, 22), fontsize=7)
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_xlim(mus.min() * 0.9, mus.max() * 1.1)
        ax.set_ylim(oms.min() * 0.85, oms.max() * 1.25)   # 裁剪解析线，锁定网格范围
        ax.set_xlabel("mass ratio $\\mu = m_t/m_s$")
        ax.set_title(cls.replace("_", " "))
        ax.grid(alpha=0.25, which="both", lw=0.3)
    axes[0].set_ylabel("$\\hat\\omega = \\omega_t/\\omega_{budget}$"
                       f"  ($\\omega_b$={w_b}°/s)")
    handles = [Patch(fc=REGION_COLOR[k], label=REGION_LABEL[k]) for k in REGION_ORDER]
    handles.append(plt.Line2D([], [], color="k", ls="--",
                              label="coaxial analytic boundary"))
    fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=8,
               frameon=False, bbox_to_anchor=(0.5, -0.03))
    fig.suptitle(f"sim_10 Mission Feasibility Map (tier {tid}, $\\lambda$=1, "
                 "$\\alpha$=0; rigid-body gates, FLEX=UNKNOWN)", fontsize=11)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    p = os.path.join(RES, "sim_10_F1_feasibility_map.png")
    fig.savefig(p, dpi=150, bbox_inches="tight"); plt.close(fig)
    return p


def fig_f2(cfg, phys, tid):
    fig, ax = plt.subplots(figsize=(6.4, 5.2))
    for reg in REGION_ORDER:
        rows = [r for r in phys if r["region"] == reg and not r["anchor"]]
        if not rows:
            continue
        ax.scatter([float(r["h_star"]) for r in rows],
                   [max(float(r["j_star"]), 1e-4) for r in rows],
                   s=5, c=REGION_COLOR[reg], label=REGION_LABEL[reg], alpha=0.5)
    ax.axvline(1.0, color="k", lw=1, ls="-"); ax.axhline(1.0, color="k", lw=1, ls="-")
    ax.annotate("$h^*$=1 wheel line", (1.05, ax.get_ylim()[0] * 1.5), fontsize=8)
    ax.annotate("$j^*$=1 thruster line", (ax.get_xlim()[0] * 1.5, 1.1), fontsize=8)
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("$h^* = |H_c| / (n_w h_w)$")
    ax.set_ylabel("$j^* = J_{avail} / J_{req}$")
    ax.set_title(f"sim_10 F2: resource plane (tier {tid})")
    ax.legend(fontsize=7, loc="lower left"); ax.grid(alpha=0.3, which="both", lw=0.3)
    p = os.path.join(RES, "sim_10_F2_resource_plane.png")
    fig.tight_layout(); fig.savefig(p, dpi=150); plt.close(fig)
    return p


def fig_f3(cfg, classes):
    """λ 边界族（G1，精确二分，与 X2 同一函数口径）。"""
    from run_gates import gate_x2_lambda_monotonic  # noqa: F401  （复用其内部实现思路）
    import feasibility_core as fc
    sc = cfg["scan"]
    w_b = float(cfg["gates"]["post_capture_rate_max_dps"])
    m_bus = float(cfg["mass_reference"]["servicer_bus_kg"])
    v_app = float(sc["v_app_mps"])
    gc = classes["G1_slender"]
    mus = np.geomspace(*map(float, sc["mu_range_log"]), 40)
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    for lam, cstyle in zip(map(float, sc["lambda_scale"]), ("C0-", "C1-", "C3-")):
        crit = []
        for mu in mus:
            lo, hi = 1e-3, 100.0
            f = lambda om: fc.exact_point(gc, mu * m_bus, om, lam, 0.0, v_app)["w_plus_dps"] - w_b  # noqa: E731,E501
            if f(hi) < 0:
                crit.append(np.nan); continue
            for _ in range(50):
                mid = 0.5 * (lo + hi)
                if f(mid) > 0:
                    hi = mid
                else:
                    lo = mid
            crit.append(0.5 * (lo + hi) / w_b)
        ax.plot(mus, crit, cstyle, lw=1.5, label=f"$\\lambda$={lam:g}")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("$\\mu$"); ax.set_ylabel("$\\hat\\omega_{crit}$ (gate-1, exact)")
    ax.set_title("sim_10 F3: grasp-lever sensitivity of the rate boundary (G1)")
    ax.legend(); ax.grid(alpha=0.3, which="both", lw=0.3)
    p = os.path.join(RES, "sim_10_F3_lambda_family.png")
    fig.tight_layout(); fig.savefig(p, dpi=150); plt.close(fig)
    return p


def fig_f4(cfg, phys):
    mus, oms, _, rows = slice_grid(phys, "G1_slender")
    D = np.full((len(oms), len(mus)), np.nan)
    for r in rows:
        i = np.searchsorted(oms, float(r["omega_hat"]))
        j = np.searchsorted(mus, float(r["mu"]))
        D[i, j] = float(r["delta_analytic"])
    fig, ax = plt.subplots(figsize=(6.6, 4.8))
    pc = ax.pcolormesh(mus, oms, D, norm=LogNorm(vmin=1e-4, vmax=1.0),
                       cmap="viridis", shading="nearest")
    fig.colorbar(pc, ax=ax, label="$\\delta_{analytic}$ (rel.)")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("$\\mu$"); ax.set_ylabel("$\\hat\\omega$")
    ax.set_title("sim_10 F4: coaxial-analytic vs exact deviation (G1, $\\lambda$=1, "
                 "$\\alpha$=0)\nlarge $\\delta$ at small $\\mu$/$\\hat\\omega$ = "
                 "v_app translational coupling dominates (CL02 amplification)")
    ax.grid(alpha=0.3, which="both", lw=0.3)
    p = os.path.join(RES, "sim_10_F4_delta_analytic.png")
    fig.tight_layout(); fig.savefig(p, dpi=150); plt.close(fig)
    return p


def main():
    cfg = load_cfg()
    classes = geometry_classes(cfg)
    phys, tid = load_data(cfg)
    out = [fig_f1(cfg, classes, phys, tid), fig_f2(cfg, phys, tid),
           fig_f3(cfg, classes), fig_f4(cfg, phys)]
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
