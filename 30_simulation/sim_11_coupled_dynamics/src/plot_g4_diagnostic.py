"""plot_g4_diagnostic.py -- G4 诊断双图（sim_11 v1.1）。

左：理想冲量 Δt=0 下 A2 帆板模态能峰值 vs 截断阶数 m（慢收敛尾，非 Gate 诊断）；
右：有限接触带宽下模态能峰值 vs T_c（半正弦等冲量，带宽滤波），
    并标注模态频率对应的半功率时长 1/(2 f_i)。
数据全部读 results/ 既有 summary JSON，不重跑仿真。
用法：python src/plot_g4_diagnostic.py
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   # noqa: E402
import numpy as np                # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.normpath(os.path.join(HERE, "..", "results"))
PNG = os.path.join(RES, "sim_11_g4_diagnostic.png")


def rd(name):
    with open(os.path.join(RES, name), encoding="utf-8") as f:
        return json.load(f)


def main():
    # ---- 左图：理想冲量 m 扫掠 ------------------------------------------------
    ideal = {}
    for tag, m in (("m2", 2), ("conv_m3", 3), ("m4", 4), ("m5", 5), ("m7", 7)):
        ideal[m] = rd(f"sim_11_scene_A2_summary_{tag}.json")["post"][
            "panel_modal_energy_peak_J"]
    ms = sorted(ideal)
    ei = np.array([ideal[m] for m in ms])

    # ---- 右图：T_c 扫掠（m=3） ------------------------------------------------
    bw = {}
    for tc, tag in ((5, "bw5"), (10, "bw10"), (20, "bw20"), (50, "bw50"),
                    (100, "bw100")):
        s = rd(f"sim_11_scene_A2_summary_{tag}.json")
        bw[tc] = s["combined"]["modal_energy_peak_J"]
    tcs = sorted(bw)
    eb = np.array([bw[t] for t in tcs])
    f_modes = rd("sim_11_scene_A1_summary.json")["panel_f_modes_hz"]

    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    ax[0].plot(ms, ei * 1e6, "o-", color="C3")
    for i in range(1, len(ms)):
        step = (ei[i] - ei[i - 1]) / ei[i - 1] * 100
        ax[0].annotate(f"+{step:.2f}%", ((ms[i] + ms[i - 1]) / 2, ei[i] * 1e6),
                       fontsize=8, ha="center", va="bottom", color="C3")
    ax[0].set_xlabel("modes per panel m")
    ax[0].set_ylabel("panel modal energy peak [uJ]")
    ax[0].set_title("ideal impulse ($\\Delta t$=0): slow-tail divergence\n"
                    "(flat spectrum + slow $B_{t,i}$ decay -> ill-posed, not gated)")
    ax[0].grid(alpha=0.3)

    ax[1].semilogx(tcs, eb * 1e6, "s-", color="C0")
    for f, lab in zip(f_modes, ("$f_1$", "$f_2$", "$f_3$")):
        tc_half = 1000.0 / (2.0 * f)          # ms：半正弦主瓣截止对应时长
        if tcs[0] / 2 < tc_half < tcs[-1] * 2:
            ax[1].axvline(tc_half, color="gray", ls=":", lw=1)
            ax[1].annotate(f"{lab}={f:.1f} Hz", (tc_half, ax[1].get_ylim()[0]),
                           fontsize=8, rotation=90, va="bottom", ha="right",
                           color="gray")
    ax[1].axhline(ei[1] * 1e6, color="C3", ls="--", lw=1,
                  label="ideal impulse (m=3)")
    ax[1].set_xlabel("contact duration $T_c$ [ms]")
    ax[1].set_ylabel("panel modal energy peak [uJ]")
    ax[1].set_title("finite-bandwidth contact (half-sine, equal impulse):\n"
                    "modal energy vs $T_c$, m=3 (G4' gated at $T_c$=20 ms)")
    ax[1].legend(fontsize=8)
    ax[1].grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(PNG, dpi=140)
    print(PNG)


if __name__ == "__main__":
    main()
