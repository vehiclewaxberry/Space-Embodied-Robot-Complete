"""anim_v04_capture_impulse.mp4 -- sim_06 nominal capture-impulse replay.

Nominal grid cell: target_debris_v0 @ 3 deg/s, v_app = 0.01 m/s (row of
30_simulation/sim_06_capture_impulse/results/capture_impulse_matrix_v0.csv).

Allowed single-point recompute (milliseconds, NOT a sweep rerun):
  capture_impulse.capture_post_state + junction_couple  -> full pre/post state
  rigid_body.propagate_torque_free(I_comb, w_plus)      -> post-capture nutation

Story: approach -> CONTACT FREEZE FRAME (impulse numbers) -> combined body
keeps tumbling at ~3.06 deg/s -> "capture != detumble".

Geometry honesty: sim_06 uses the LEGACY v0 chaser stack (servicer + adapter +
2-rod placeholder arm along +X_S) -- the rods are drawn as rods and declared;
the servicer body mesh is display-only. Approach standoff distance is
compressed for display (declared); the impulse numbers do not depend on it.
"""
import _viz_bootstrap as vb
import csv
import os

import numpy as np

import video_utils as vu
import scene_assembly as sa
from frame_renderer import draw_triad, draw_arrow, set_equal_aspect
from mesh_utils import cylinder_vf
from capture_impulse import (capture_post_state, junction_couple, chaser_stack,
                             TUMBLE_AXIS, MOUNT_X, L1, L2)
from rigid_body import load_object, propagate_torque_free, q_to_R
from target_propagation import rodrigues

VIDEO = "anim_v04_capture_impulse"
OUT = os.path.join(vu.VIDEO_DIR, VIDEO + ".mp4")
CSV_06 = os.path.join(vb.REPO_ROOT, "sim", "sim_06_capture_impulse", "results",
                      "capture_impulse_matrix_v0.csv")
CSV_08 = os.path.join(vb.REPO_ROOT, "sim", "sim_08_detumble_actuator_budget",
                      "results", "actuator_budget_sweep.csv")

FPS = 24
N_A = 8 * FPS          # approach 8 s (sim pre-contact 24 s @ 3x)
N_B = 7 * FPS          # contact freeze 7 s
N_C = 12 * FPS         # post-capture tumble 12 s (sim 36 s @ 3x)
N_FRAMES = N_A + N_B + N_C
SPEED = 3.0
TUMBLE_DPS, V_APP = 3.0, 0.01
GAP0 = 0.45            # display standoff [m] (compressed; declared on screen)


def csv06_row():
    with open(CSV_06, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if float(r["tumble_dps"]) == TUMBLE_DPS and float(r["v_app_mps"]) == V_APP:
                return r
    raise KeyError("sim_06 nominal row")


def csv08_row():
    with open(CSV_08, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r["target"] == "target_debris_v0"
                    and float(r["tumble_dps"]) == 3.0
                    and float(r["t_detumble_s"]) == 900.0
                    and float(r["lever_m"]) == 0.17
                    and r["isp_class"] == "cold_gas_60s"):
                return r
    raise KeyError("sim_08 row")


def build():
    # ---------------- single-point nominal recompute (allowed) ----------------
    res, bodies, meta = capture_post_state("target_debris_v0", TUMBLE_DPS, V_APP)
    r_g = meta["r_g"]
    J_t, L_g = junction_couple(res, bodies, 1, r_g)
    w_plus = res["w_plus"]
    post_dps = float(np.rad2deg(np.linalg.norm(w_plus)))
    Jn, Ln = float(np.linalg.norm(J_t)), float(np.linalg.norm(L_g))
    H_com = res["I_comb"] @ w_plus
    Hn = float(np.linalg.norm(H_com))
    dT = float(res["dT"])
    LEVER = 0.17
    J_thr = Hn / LEVER                    # sim_08 couple formula J = |H|/l
    r6, r8 = csv06_row(), csv08_row()

    # post-capture nutation of the combined body (torque-free, validated core)
    T_POST = N_C / FPS * SPEED
    nut = propagate_torque_free(res["I_comb"], w_plus, T_POST, n=N_C)
    R_post = np.array([q_to_R(q).as_matrix() for q in nut["Q"]])
    w_post_I = np.einsum("kij,kj->ki", R_post, nut["W"])
    t_post = nut["t"]

    # pre-contact debris attitude: R(t) = rodrigues(w0 * t), identity at contact
    w0 = np.deg2rad(TUMBLE_DPS) * TUMBLE_AXIS
    t_pre = (np.arange(N_A) / FPS - N_A / FPS) * SPEED          # -24 .. 0 s

    # ---------------- chaser display group (legacy v0 stack) ----------------
    m_c, com_c, I_c, ee_x = chaser_stack()
    Vs, Fs = sa.model_vf("servicer_12U_v0", target_faces=3500)
    Va, Fa = sa.model_vf("robot_mount_adapter_v0", target_faces=1000)
    from b601_renderer import load_T_SM
    T_SM = load_T_SM()                               # adapter posed at mount (S)
    Va = Va @ T_SM[:3, :3].T + T_SM[:3, 3]
    rod1_V, rod1_F = cylinder_vf(0.02, 0.0, L1)
    rod2_V, rod2_F = cylinder_vf(0.016, 0.0, L2)
    Rrod = np.array([[0.0, 0.0, 1.0], [0.0, 1.0, 0.0], [-1.0, 0.0, 0.0]])
    rod1_V = rod1_V @ Rrod.T + np.array([MOUNT_X, 0.0, 0.0])
    rod2_V = rod2_V @ Rrod.T + np.array([MOUNT_X + L1, 0.0, 0.0])
    R_flip = np.diag([-1.0, -1.0, 1.0])              # +X_S -> -X inertial

    def chaser_T(gap):
        """S-frame -> inertial pose with the EE at r_g + gap * (+X)."""
        T = np.eye(4)
        T[:3, :3] = R_flip
        T[:3, 3] = r_g + np.array([gap, 0.0, 0.0]) - R_flip @ np.array([ee_x, 0.0, 0.0])
        return T

    # ---------------- figure ----------------
    fig = vu.make_fig()
    ax = fig.add_axes((-0.02, 0.02, 0.72, 0.90), projection="3d")
    ax.view_init(elev=18, azim=-62)
    ax.set_axis_off()
    ax.computed_zorder = False

    tgt = load_object("target_debris_v0")
    cg = np.asarray(tgt["cg"], float)
    Vd, Fd = sa.model_vf("target_debris_v0", target_faces=4000)
    Vd = Vd - cg                                     # target CoM at origin
    deb = vu.MeshActor(ax, Vd, Fd, vu.OBJ_C["target_debris_v0"], alpha=0.55)
    srv = vu.MeshActor(ax, Vs, Fs, vu.OBJ_C["servicer_12U_v0"], alpha=0.92)
    adp = vu.MeshActor(ax, Va, Fa, vu.OBJ_C["robot_mount_adapter_v0"])
    rd1 = vu.MeshActor(ax, rod1_V, rod1_F, vu.OBJ_C["arm_b601_v1"])
    rd2 = vu.MeshActor(ax, rod2_V, rod2_F, "#6d7280")
    gdot, = ax.plot([], [], [], "o", color="#111111", ms=6)
    jarrow, = ax.plot([], [], [], color="#c8443c", lw=2.6)
    warr, = ax.plot([], [], [], color="#1f77b4", lw=2.2, ls="-")
    comdot, = ax.plot([], [], [], "P", color="#222222", ms=7)
    draw_triad(ax, np.eye(4), 0.4, "I", lw=1.5)
    set_equal_aspect(ax, np.array([[-1.3, -1.1, -1.5], [2.6, 1.1, 1.9]]))

    fig.text(0.37, 0.975, "anim_v04  sim_06 capture impulse -- nominal "
             "(debris 3 deg/s, v_app 0.01 m/s, 6-DOF plastic rigidization)",
             fontsize=10.5, ha="center", va="top", fontweight="bold")
    subtitle = fig.text(0.34, 0.938, "", fontsize=8.4, ha="center", va="top",
                        color="#333333")
    cjk = fig.text(0.34, 0.075, "", fontsize=13, ha="center", va="center",
                   fontweight="bold", color="#7d0000",
                   fontfamily=vu.CJK_FONT)
    stack_note = ("chaser = sim_06 LEGACY v0 stack (servicer + adapter + "
                  "2-rod placeholder arm along +X_S); approach standoff "
                  "compressed for display -- impulse numbers are standoff-"
                  "independent")
    fig.text(0.34, 0.033, stack_note, fontsize=6.2, ha="center",
             color="#666666")

    # right-hand numbers panel (populated at contact)
    panel = fig.text(0.715, 0.90, "", fontsize=7.8, family="monospace",
                     va="top", bbox=dict(boxstyle="round,pad=0.5",
                                         fc="#f6f6f2", ec="#999999"))
    readout = fig.text(0.715, 0.16, "", fontsize=8.0, family="monospace",
                       va="top")
    vu.add_provenance(
        fig, ["capture_impulse_matrix_v0.csv", "capture_impulse.py"
              "(capture_post_state, single nominal point)",
              "actuator_budget_sweep.csv", "mass_inertia_budget_v1.csv"])

    panel_txt = (
        "CONTACT INSTANT (plastic 6-DOF lock)\n"
        "------------------------------------\n"
        f"J_linear  [{J_t[0]:+.5f}, {J_t[1]:+.5f},\n"
        f"           {J_t[2]:+.5f}] N s\n"
        f"|J|       {Jn:.5f} N s\n"
        f"L_grasp   |{Ln:.6f}| N m s (couple at\n"
        "          the grasp point, on target)\n"
        f"omega_before  {TUMBLE_DPS:.2f}  deg/s (target)\n"
        f"omega_after   {post_dps:.5f} deg/s (combined)\n"
        f"dKE (plastic) {dT:.6f} J\n"
        "------------------------------------\n"
        "DETUMBLE STILL REQUIRED (sim_08):\n"
        f"|H_combined|  {Hn:.5f} N m s\n"
        f"H_RW required {float(r8['H_Nms']):.5f} N m s\n"
        f"thruster impulse {J_thr:.4f} N s\n"
        f"  (= |H|/lever, lever {LEVER:.2f} m,\n"
        f"   sim_08 CSV: {float(r8['total_impulse_Ns']):.4f} N s)\n"
        f"post rate {post_dps:.2f} > budget 2.0 deg/s\n"
        f"  -> sim_06 flag: {r6['budget_2dps']}")

    # combined-assembly vertex snapshots at contact (locked geometry)
    Tc0 = chaser_T(0.0)

    def draw(k):
        if k < N_A:                                   # ---- approach ----
            tt = t_pre[k]
            Rk = rodrigues(w0, tt)
            Tk = np.eye(4)
            Tk[:3, :3] = Rk
            deb.set_transform(Tk)
            gap = GAP0 * (1.0 - k / max(N_A - 1, 1))
            Tc = chaser_T(gap)
            srv.set_transform(Tc)
            adp.set_transform(Tc)
            rd1.set_transform(Tc)
            rd2.set_transform(Tc)
            g_now = Rk @ r_g
            gdot.set_data_3d([g_now[0]], [g_now[1]], [g_now[2]])
            subtitle.set_text(
                "approach: EE closes on the P1 grasp feature along +X at "
                f"v_app = {V_APP} m/s (display gap {gap:.2f} m, time 3x)")
            readout.set_text(
                f"t = {tt:6.1f} s (pre-contact)\n"
                f"target |omega| = {TUMBLE_DPS:.2f} deg/s\n"
                f"closing speed  = {V_APP * 1e3:.0f} mm/s")
        elif k < N_A + N_B:                           # ---- freeze frame ----
            if k == N_A:                              # pose everything at contact
                deb.set_transform(np.eye(4))
                for actor in (srv, adp, rd1, rd2):
                    actor.set_transform(Tc0)
                gdot.set_data_3d([r_g[0]], [r_g[1]], [r_g[2]])
                Jdir = J_t / Jn
                tip = r_g + 1.2 * Jdir
                jarrow.set_data_3d(*np.stack([r_g, tip]).T)
                comdot.set_data_3d([res["r_com"][0]], [res["r_com"][1]],
                                   [res["r_com"][2]])
                panel.set_text(panel_txt)
            subtitle.set_text(
                "CONTACT -- one frame, held: impulse exchanged by the "
                "instantaneous plastic lock (red arrow = J on target, "
                "unit-scaled)")
            cjk.set_text("捕获 ≠ 消旋  (capture is NOT detumbling)")
            readout.set_text(
                "t = 0 s (capture instant)\n"
                f"|J| = {Jn:.5f} N s   |L_grasp| = {Ln:.6f} N m s\n"
                f"omega: {TUMBLE_DPS:.2f} -> {post_dps:.5f} deg/s (combined)")
        else:                                         # ---- post-capture ----
            kk = k - N_A - N_B
            Rk = R_post[kk]
            rc = res["r_com"] + res["v_com"] * t_post[kk]
            Tk = np.eye(4)
            Tk[:3, :3] = Rk
            Tk[:3, 3] = rc - Rk @ res["r_com"]
            deb.set_transform(Tk)
            for actor in (srv, adp, rd1, rd2):
                actor.set_transform(Tk @ Tc0)
            g_now = Tk[:3, :3] @ r_g + Tk[:3, 3]
            gdot.set_data_3d([g_now[0]], [g_now[1]], [g_now[2]])
            jarrow.set_data_3d([], [], [])
            comdot.set_data_3d([rc[0]], [rc[1]], [rc[2]])
            wI = w_post_I[kk]
            wmag = np.rad2deg(np.linalg.norm(wI))
            tip = rc + 0.35 * wI / np.linalg.norm(wI) * (wmag / post_dps)
            warr.set_data_3d(*np.stack([rc, tip]).T)
            subtitle.set_text(
                "post-capture: the COMBINED 176.5 kg stack keeps tumbling "
                "about its combined CoM (torque-free nutation, blue = omega)")
            cjk.set_text("捕获 ≠ 消旋  (capture is NOT detumbling)")
            readout.set_text(
                f"t = +{t_post[kk]:5.1f} s (time 3x)\n"
                f"combined |omega| = {wmag:.4f} deg/s\n"
                f"detumble budget: H = {Hn:.3f} N m s,\n"
                f"J_thr = {J_thr:.1f} N s @ lever {LEVER:.2f} m (sim_08)")

    vu.render_video(OUT, fig, N_FRAMES, draw, fps=FPS)

    # ---------------- keyframe checks ----------------
    kB = N_A + N_B // 2
    tB = kB / FPS
    rows = [
        vu.kf_row(VIDEO, kB, tB, "omega_after [deg/s] (panel)",
                  post_dps, float(r6["post_rate_full_dps"]),
                  "capture_impulse_matrix_v0.csv", tol=5e-6,
                  note="CSV printed 6 sig figs"),
        vu.kf_row(VIDEO, kB, tB, "|J| contact impulse [N s] (panel)",
                  Jn, float(r6["contact_impulse_N_s"]),
                  "capture_impulse_matrix_v0.csv", tol=5e-6),
        vu.kf_row(VIDEO, kB, tB, "|L_grasp| couple [N m s] (panel)",
                  Ln, float(r6["grasp_couple_N_m_s"]),
                  "capture_impulse_matrix_v0.csv", tol=5e-7),
        vu.kf_row(VIDEO, kB, tB, "dKE plastic loss [J] (panel)",
                  dT, float(r6["impact_energy_loss_J"]),
                  "capture_impulse_matrix_v0.csv", tol=5e-9),
        vu.kf_row(VIDEO, kB, tB, "w_after_x [rad/s] (recompute)",
                  float(w_plus[0]), float(r6["w_after_x_rps"]),
                  "capture_impulse_matrix_v0.csv", tol=5e-8),
        vu.kf_row(VIDEO, kB, tB, "H_RW required [N m s] (panel)",
                  Hn, float(r8["H_Nms"]),
                  "actuator_budget_sweep.csv", tol=5e-6),
        vu.kf_row(VIDEO, kB, tB, "thruster impulse [N s] (panel)",
                  J_thr, float(r8["total_impulse_Ns"]),
                  "actuator_budget_sweep.csv", tol=5e-5),
        vu.kf_row(VIDEO, kB, tB, "sim_06 budget flag (panel)",
                  "OVER_BUDGET", r6["budget_2dps"],
                  "capture_impulse_matrix_v0.csv"),
    ]
    import matplotlib.pyplot as plt
    plt.close(fig)
    return {"video": VIDEO, "path": OUT, "n_frames": N_FRAMES, "fps": FPS,
            "kf_rows": rows}


def main():
    out = build()
    n, bad = vu.update_keyframe_csv(VIDEO, out["kf_rows"])
    dur, mb, w, h = vu.video_info(out["path"])
    print(f"[{VIDEO}] {dur:.1f} s, {mb:.1f} MB, {w}x{h}, "
          f"keyframes {n} ({'ALL MATCH' if not bad else f'{len(bad)} MISMATCH'})")
    for r in bad:
        print("  MISMATCH:", r)
    return out


if __name__ == "__main__":
    main()
