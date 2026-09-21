"""anim_v03_base_reaction.mp4 -- sim_05 free-floating base reaction replay.

PURE CSV REPLAY of 30_simulation/sim_05_free_floating_arm/results/sim_05_base_attitude.csv
(601 rows, 0..12 s): the arm maneuver q2 0->+60 deg / q3 0->-40 deg (min-jerk
8 s, hold to 12 s) and the momentum-conserving base response. Nothing is
re-integrated; the base pose is rebuilt from the CSV euler angles + position,
the arm is posed by FK at the CSV joint angles.

Left  = 3D scene: arm motion + whole-spacecraft counter-rotation (CSV euler),
        base angular-velocity vector (finite-difference of the CSV euler --
        derivation declared on screen), EE trajectory trail.
Right = time series with sliding cursor: base attitude (euler + deviation),
        base rate |omega| (finite diff), |H_bm qdot| lin/ang (CSV columns).
End   = freeze frame: final deviation 19.20 deg vs 2-DOF era 13.13 deg.

NOTE (from sim_05_headline.py, restated on screen): q2 = +60 deg exceeds the
URDF joint2 limit -- this is a dynamics benchmark for sim_03 comparability,
not a flight trajectory.
"""
import _viz_bootstrap as vb
import csv
import os

import numpy as np
from scipy.spatial.transform import Rotation

import video_utils as vu
import scene_assembly as sa
from b601_renderer import B601VisualChain, load_T_SM
from frame_renderer import draw_triad, set_equal_aspect

VIDEO = "anim_v03_base_reaction"
OUT = os.path.join(vu.VIDEO_DIR, VIDEO + ".mp4")
CSV_PATH = os.path.join(vb.REPO_ROOT, "sim", "sim_05_free_floating_arm",
                        "results", "sim_05_base_attitude.csv")

FPS = 25
N_FREEZE = 3 * FPS                     # 3 s final freeze
OLD_SIM03_PEAK_DEG = 13.13             # sim_05_headline.py comparison constant


def load_csv():
    with open(CSV_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    d = {k: np.array([float(r[k]) for r in rows]) for k in rows[0]}
    return d, rows


def build():
    d, rows = load_csv()
    t = d["t_s"]
    n = len(t)                                        # 601 -> 1 frame per row
    N_FRAMES = n + N_FREEZE

    eul = np.stack([d["base_euler_x_deg"], d["base_euler_y_deg"],
                    d["base_euler_z_deg"]], axis=1)
    R_base = Rotation.from_euler("xyz", eul, degrees=True).as_matrix()
    p_base = np.stack([d["base_pos_x_m"], d["base_pos_y_m"],
                       d["base_pos_z_m"]], axis=1)
    dev = d["base_dev_angle_deg"]
    hbm_lin, hbm_ang = d["Hbm_qdot_lin_kgmps"], d["Hbm_qdot_ang_kgm2ps"]

    # base angular velocity by finite difference of the CSV attitude (declared)
    dt = float(t[1] - t[0])
    w_base = np.zeros((n, 3))
    for k in range(n - 1):
        dR = Rotation.from_matrix(R_base[k + 1] @ R_base[k].T)
        w_base[k] = dR.as_rotvec() / dt               # world frame [rad/s]
    w_base[-1] = w_base[-2]
    w_mag_dps = np.rad2deg(np.linalg.norm(w_base, axis=1))

    # arm joint angles from the CSV
    Q = np.zeros((n, 6))
    Q[:, 1] = np.deg2rad(d["q2_deg"])
    Q[:, 2] = np.deg2rad(d["q3_deg"])

    chain = B601VisualChain()
    T_SM = load_T_SM()

    # precompute world poses: T_W_S = [R_base | p_base]; arm base = T_W_S @ T_SM
    T_WS = np.tile(np.eye(4), (n, 1, 1))
    T_WS[:, :3, :3] = R_base
    T_WS[:, :3, 3] = p_base
    pE = np.zeros((n, 3))
    for k in range(n):
        pE[k] = chain.link_poses(Q[k], T_base=T_WS[k] @ T_SM)["T_E"][:3, 3]

    peak_dev = float(np.max(dev))
    k_peak_hbm = int(np.argmax(hbm_ang))

    # ---------------- figure ----------------
    fig = vu.make_fig()
    ax = fig.add_axes((-0.04, 0.02, 0.60, 0.90), projection="3d")
    ax.view_init(elev=vu.CAMS["isometric"]["elev"],
                 azim=vu.CAMS["isometric"]["azim"])
    ax.set_axis_off()
    ax.computed_zorder = False

    pts = []
    Vs, Fs = sa.model_vf("servicer_12U_v0", target_faces=4500)
    srv = vu.MeshActor(ax, Vs, Fs, vu.OBJ_C["servicer_12U_v0"], alpha=0.92)
    pts.append(Vs)
    Va, Fa = sa.model_vf("robot_mount_adapter_v0", target_faces=1200)
    adp = vu.MeshActor(ax, Va, Fa, vu.OBJ_C["robot_mount_adapter_v0"])
    arm_actors = []
    for name, mesh_path, T in chain.visual_poses(Q[0], T_base=T_WS[0] @ T_SM):
        Vl, Fl = sa.display_mesh(mesh_path, 1200)
        a = vu.MeshActor(ax, Vl, Fl, vu.OBJ_C["arm_b601_v1"], alpha=0.95)
        arm_actors.append(a)
        pts.append(a.set_transform(T))
    pts.append(pE)
    trail, = ax.plot([], [], [], color="#1f77b4", lw=1.6)
    warrow, = ax.plot([], [], [], color="#c8443c", lw=2.2)
    wtip, = ax.plot([], [], [], "o", color="#c8443c", ms=4)
    draw_triad(ax, np.eye(4), 0.20, "I", lw=1.5)
    P = np.vstack(pts + [np.array([[0.75, 0.35, 0.45], [-0.35, -0.35, -0.35]])])
    set_equal_aspect(ax, P)

    fig.text(0.325, 0.975, "anim_v03  sim_05 free-floating base reaction "
             "(momentum-conserving, zero initial momentum)",
             fontsize=10.5, ha="center", va="top", fontweight="bold")
    fig.text(0.325, 0.942,
             "pure CSV replay (sim_05_base_attitude.csv): base euler/position "
             "+ q2/q3; arm posed by the FK truth chain.\nq2 = +60 deg exceeds "
             "the URDF joint2 limit -- sim_03-comparable dynamics benchmark, "
             "NOT a flight trajectory.",
             fontsize=7.0, ha="center", va="top", color="#333333")
    wnote = ("base omega vector: finite-difference of CSV euler (derived "
             "display quantity); arrow scaled x0.06/(deg/s)")
    fig.text(0.30, 0.055, wnote, fontsize=6.4, ha="center", color="#666666")

    # ---------------- right time-series panels ----------------
    axs = [fig.add_axes((0.645, y, 0.335, 0.205)) for y in (0.745, 0.45, 0.155)]
    ax_e, ax_w, ax_h = axs
    for a in axs:
        a.tick_params(labelsize=6.5)
        a.grid(alpha=0.25, lw=0.4)
        a.set_xlim(0, float(t[-1]))
    ax_e.plot(t, eul[:, 0], lw=1.0, label="euler x")
    ax_e.plot(t, eul[:, 1], lw=1.0, label="euler y")
    ax_e.plot(t, eul[:, 2], lw=1.0, label="euler z")
    ax_e.plot(t, dev, lw=1.6, color="k", label="deviation")
    ax_e.set_ylim(-2.5, 25.5)
    ax_e.legend(fontsize=5.6, ncol=4, loc="upper left", frameon=False)
    ax_e.set_ylabel("base attitude [deg]", fontsize=7)
    ax_w.plot(t, w_mag_dps, color="#c8443c", lw=1.3)
    ax_w.set_ylabel("|omega_base| [deg/s]\n(finite diff of CSV)", fontsize=6.5)
    ax_h.plot(t, hbm_lin, lw=1.2, label="|H_bm qdot| lin [kg m/s]")
    ax_h.plot(t, hbm_ang, lw=1.2, label="|H_bm qdot| ang [kg m^2/s]")
    ax_h.legend(fontsize=5.6, loc="upper right", frameon=False)
    ax_h.set_ylabel("arm-transferred\nmomentum", fontsize=6.5)
    ax_h.set_xlabel("t [s]", fontsize=7)
    cursors = [a.axvline(0, color="#c8443c", lw=1.1) for a in axs]
    readout = fig.text(0.645, 0.085, "", fontsize=7.6, family="monospace",
                       va="top")
    freeze_txt = fig.text(0.30, 0.72, "", fontsize=12, ha="center",
                          va="center", fontweight="bold", color="#7d0000",
                          bbox=dict(boxstyle="round,pad=0.6", fc="#fff8f0",
                                    ec="#7d0000", lw=1.2, alpha=0.0))

    vu.add_provenance(
        fig, ["sim_05_base_attitude.csv", "arm_b601_v1.urdf+meshes",
              "b601_renderer(FK-aligned chain)", "frame_tree_v1.yaml"])

    def draw(kf):
        k = min(kf, n - 1)
        srv.set_transform(T_WS[k])
        adp.set_transform(T_WS[k] @ T_SM)
        for a, (nm, mp, T) in zip(arm_actors,
                                  chain.visual_poses(Q[k],
                                                     T_base=T_WS[k] @ T_SM)):
            a.set_transform(T)
        trail.set_data_3d(pE[:k + 1, 0], pE[:k + 1, 1], pE[:k + 1, 2])
        wmag = w_mag_dps[k]
        if wmag > 1e-4:
            tip = p_base[k] + 0.06 * wmag * (w_base[k] / np.linalg.norm(w_base[k]))
            warrow.set_data_3d(*np.stack([p_base[k], tip]).T)
            wtip.set_data_3d([tip[0]], [tip[1]], [tip[2]])
        for c in cursors:
            c.set_xdata([t[k], t[k]])
        readout.set_text(
            f"t = {t[k]:5.2f} s   q2 = {d['q2_deg'][k]:7.3f} deg   "
            f"q3 = {d['q3_deg'][k]:8.3f} deg\n"
            f"base deviation = {dev[k]:8.4f} deg   "
            f"|omega_b| = {wmag:6.3f} deg/s\n"
            f"|H_bm qdot| ang = {hbm_ang[k]:7.4f} kg m^2/s")
        if kf >= n:                                   # freeze annotation
            freeze_txt.set_text(
                f"final base deviation {dev[-1]:.2f} deg\n"
                f"vs 2-DOF era {OLD_SIM03_PEAK_DEG:.2f} deg\n"
                "(sim_03 reduced planar model, 1.6 kg arm --\n"
                "the real 6R B601 arm moves ~3x the mass)")
            freeze_txt.get_bbox_patch().set_alpha(0.92)

    vu.render_video(OUT, fig, N_FRAMES, draw, fps=FPS)

    # ---------------- keyframe checks (replay -> CSV identity) ----------------
    k4 = int(np.argmin(np.abs(t - 4.0)))
    rows_kf = [
        vu.kf_row(VIDEO, k4, k4 / FPS, "q2 [deg] @ t=4.00 s (readout)",
                  float(d["q2_deg"][k4]), float(rows[k4]["q2_deg"]),
                  "sim_05_base_attitude.csv"),
        vu.kf_row(VIDEO, k4, k4 / FPS, "base deviation [deg] @ t=4.00 s",
                  float(dev[k4]), float(rows[k4]["base_dev_angle_deg"]),
                  "sim_05_base_attitude.csv"),
        vu.kf_row(VIDEO, k_peak_hbm, k_peak_hbm / FPS,
                  "|H_bm qdot| ang peak [kg m^2/s] (readout)",
                  float(hbm_ang[k_peak_hbm]),
                  float(rows[k_peak_hbm]["Hbm_qdot_ang_kgm2ps"]),
                  "sim_05_base_attitude.csv"),
        vu.kf_row(VIDEO, n - 1, (n - 1) / FPS, "final base deviation [deg]",
                  float(dev[-1]), float(rows[-1]["base_dev_angle_deg"]),
                  "sim_05_base_attitude.csv"),
        vu.kf_row(VIDEO, N_FRAMES - 1, (N_FRAMES - 1) / FPS,
                  "freeze card value 19.20 [deg] (2 dp display)",
                  round(float(dev[-1]), 2), round(float(rows[-1]["base_dev_angle_deg"]), 2),
                  "sim_05_base_attitude.csv", note="display rounding 2 dp"),
        vu.kf_row(VIDEO, n - 1, (n - 1) / FPS, "final euler y [deg]",
                  float(eul[-1, 1]), float(rows[-1]["base_euler_y_deg"]),
                  "sim_05_base_attitude.csv"),
    ]
    import matplotlib.pyplot as plt
    plt.close(fig)
    return {"video": VIDEO, "path": OUT, "n_frames": N_FRAMES, "fps": FPS,
            "kf_rows": rows_kf}


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
