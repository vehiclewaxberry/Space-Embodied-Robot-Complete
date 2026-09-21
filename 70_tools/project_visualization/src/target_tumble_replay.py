"""anim_v01_target_tumble.mp4 -- debris tumble replay + capture-phase timeline.

Truth sources (all read-only):
  * inertia / mass / cg          20_engineering/stage1_spacecraft_layout/04_mass_inertia_budget/mass_inertia_budget_v1.csv (SSOT)
  * propagation                  30_simulation/common/rigid_body.propagate_torque_free
                                 (DOP853 rtol 1e-10 -- validated core)
  * grasp points P1/P2/P3        30_simulation/sim_09_grasp_evaluator/src/e1_thin_slice.GRASP_POINTS
  * capture phases t_c           E1.5 snapshot e15_results_72cases.csv (t_c grid)
  * window cones (+/-35, +/-100) 30_simulation/sim_04_capture_corridor/sim_04_capture_corridor.py
                                 visibility() thresholds (cited on screen)
  * lever arm |r_g|              sim_06 capture_impulse_matrix_v0.csv (keyframe check)

SEMANTICS: the tumble axis [1, 0.15, 0.4]/|.| @ 3 deg/s is the E1 grid context;
the E1.5 snapshot does not restate it -> declared on screen as
"E1 context tumble axis (E1.5 evidence missing)" in the evidence_missing color.
Point colors identify the three candidates only -- NO safety state is claimed.
"""
import _viz_bootstrap as vb
import csv
import os

import numpy as np

import video_utils as vu
import scene_assembly as sa
from frame_renderer import draw_triad, set_equal_aspect
from rigid_body import load_object, propagate_torque_free, q_to_R
from e1_thin_slice import GRASP_POINTS

VIDEO = "anim_v01_target_tumble"
OUT = os.path.join(vu.VIDEO_DIR, VIDEO + ".mp4")

FPS = 24
T_SIM = 120.0                 # one const-omega tumble period at 3 deg/s
SPEED = 4.0                   # 4x playback -> 30 s video
N_FRAMES = int(T_SIM / SPEED * FPS) + 1          # 721

OMEGA_DPS = 3.0
TUMBLE_AXIS = np.array([1.0, 0.15, 0.4])
TUMBLE_AXIS = TUMBLE_AXIS / np.linalg.norm(TUMBLE_AXIS)
T_C_GRID = (0.0, 30.0, 60.0, 90.0)               # cross-checked vs snapshot CSV
APPROACH_S = 8.0              # evaluator approach duration -> PREGRASP = t_c - 8 s
GRASP_CONE_DEG, VIS_CONE_DEG = 35.0, 100.0       # sim_04 visibility() thresholds

PT_COLORS = {"P1": "#1f77b4", "P2": "#ff7f0e", "P3": "#9467bd"}  # identity only


def snapshot_tc_grid():
    p = os.path.join(vb.SNAPSHOT_DIR,
                     "results__sim_09_grasp_evaluator__e15_results_72cases.csv")
    with open(p, encoding="utf-8") as f:
        vals = sorted({float(r["t_c_s"]) for r in csv.DictReader(f)})
    return vals


def sim06_nominal_row():
    p = os.path.join(vb.REPO_ROOT, "sim", "sim_06_capture_impulse", "results",
                     "capture_impulse_matrix_v0.csv")
    with open(p, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if float(r["tumble_dps"]) == 3.0 and float(r["v_app_mps"]) == 0.01:
                return r
    raise KeyError("sim_06 nominal row")


def mass_csv_row(object_id="target_debris_v0"):
    with open(vb.MASS_BUDGET_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["object_id"] == object_id:
                return r
    raise KeyError(object_id)


def build():
    tgt = load_object("target_debris_v0")
    cg = np.asarray(tgt["cg"], float)
    w0 = np.deg2rad(OMEGA_DPS) * TUMBLE_AXIS
    res = propagate_torque_free(tgt["I"], w0, T_SIM, n=N_FRAMES)
    t = res["t"]
    R_hist = np.array([q_to_R(q).as_matrix() for q in res["Q"]])       # body->I
    w_I = np.einsum("kij,kj->ki", R_hist, res["W"])                    # inertial

    # grasp points (body-fixed, rel. CoM) -> inertial histories
    pts_D = {k: np.asarray(v["p_D"], float) - cg for k, v in GRASP_POINTS.items()}
    nrm_D = {k: np.asarray(v["approach_T"], float) for k, v in GRASP_POINTS.items()}
    p_hist = {k: np.einsum("kij,j->ki", R_hist, p) for k, p in pts_D.items()}
    v_hist = {k: np.cross(w_I, p_hist[k]) for k in pts_D}

    # sim_04 visibility / grasp window for P1 (normal +X_T vs approach +X_I)
    facing = np.einsum("kij,j->ki", R_hist, nrm_D["P1"])[:, 0]
    graspable = facing > np.cos(np.deg2rad(GRASP_CONE_DEG))
    visible = facing > np.cos(np.deg2rad(VIS_CONE_DEG))
    # falling edge of the (single) grasp window
    edges = np.flatnonzero(np.diff(graspable.astype(int)) < 0)
    t_close = float(t[edges[0] + 1]) if len(edges) else float("nan")

    lever = float(np.linalg.norm(pts_D["P1"]))     # |r_g| of P1 (vs sim_06 CSV)

    # ---------------- figure ----------------
    fig = vu.make_fig()
    ax = fig.add_axes((-0.06, 0.10, 0.76, 0.88), projection="3d")
    ax.view_init(elev=vu.CAMS["isometric_xy"]["elev"],
                 azim=vu.CAMS["isometric_xy"]["azim"])
    ax.set_axis_off()
    ax.computed_zorder = False

    V, F = sa.model_vf("target_debris_v0", target_faces=4500)
    Vc = V - cg                                    # CoM at inertial origin
    body = vu.MeshActor(ax, Vc, F, vu.OBJ_C["target_debris_v0"], alpha=0.55)

    # tumble axis (E1 context, evidence-missing color, dashed)
    axis_line, = ax.plot([], [], [], color=vu.SC["evidence_missing"], lw=2.0,
                         ls="--")
    axL = 1.9
    axis_line.set_data_3d(*np.stack([-axL * TUMBLE_AXIS, axL * TUMBLE_AXIS]).T)

    trails, dots, varrows = {}, {}, {}
    VEL_SCALE = 8.0                                # m per (m/s) -- declared
    for k, c in PT_COLORS.items():
        trails[k], = ax.plot([], [], [], color=c, lw=1.1, alpha=0.8)
        dots[k], = ax.plot([], [], [], "o", color=c, ms=7, mec="k", mew=0.5)
        varrows[k], = ax.plot([], [], [], color=c, lw=2.0)
    draw_triad(ax, np.eye(4), 0.45, "I", lw=1.6)
    ext = 1.45
    set_equal_aspect(ax, np.array([[-ext, -ext, -ext], [ext, ext, ext]]))

    # ---------------- timeline bar ----------------
    axb = fig.add_axes((0.045, 0.065, 0.60, 0.075))
    axb.set_xlim(0, T_SIM)
    axb.set_ylim(0, 1)
    axb.set_yticks([])
    axb.set_xlabel("sim time [s]  (playback 4x)", fontsize=8, labelpad=1)
    axb.tick_params(labelsize=7)
    # OBSERVE base band (wide cone) + WINDOW_OPEN band (tight cone)
    axb.fill_between(t, 0, 1, where=visible, step="mid",
                     color=vu.SC["dynamics_unverified"], alpha=0.35)
    axb.fill_between(t, 0, 1, where=graspable, step="mid",
                     color=vu.SC["geometry_verified"], alpha=0.75)
    for tc in T_C_GRID:
        axb.axvline(tc, color="k", lw=1.4)
        axb.annotate(f"CAPTURE_TIME\nt_c={tc:.0f}s", (tc, 1.02), fontsize=6,
                     ha="center", va="bottom", annotation_clip=False)
        axb.axvline(tc - APPROACH_S, color="#444444", lw=0.9, ls=":")
        if tc > 0:
            axb.annotate("PREGRASP", (tc - APPROACH_S, -0.06), fontsize=5.2,
                         ha="center", va="top", color="#444444",
                         annotation_clip=False)
    axb.axvline(t_close, color=vu.SC["physical_violation"], lw=1.4, ls="--")
    axb.annotate(f"WINDOW_CLOSED\n{t_close:.1f}s",
                 (t_close, 1.02), fontsize=6, ha="center", va="bottom",
                 color=vu.SC["physical_violation"], annotation_clip=False)
    axb.text(0.5 * t_close, 0.5, "WINDOW_OPEN (grasp cone +/-35 deg)",
             fontsize=6.5, ha="center", va="center")
    axb.text(0.5 * (t_close + T_SIM), 0.5, "OBSERVE (visible +/-100 deg)",
             fontsize=6.5, ha="center", va="center")
    cursor = axb.axvline(0.0, color="#c8443c", lw=1.8)

    # ---------------- info panel (right) ----------------
    info = (
        "anim_v01  target_debris_v0 tumble replay\n"
        "---------------------------------------\n"
        f"mass          {tgt['mass']:.1f} kg (SSOT budget CSV)\n"
        f"I diag        [{tgt['I'][0, 0]:.6f}, {tgt['I'][1, 1]:.6f},\n"
        f"               {tgt['I'][2, 2]:.6f}] kg m^2\n"
        f"|omega_0|     {OMEGA_DPS:.2f} deg/s\n"
        f"tumble axis   [1, 0.15, 0.4]/|.|\n"
        "  = E1 grid context value; the E1.5\n"
        "  snapshot does NOT restate it\n"
        "  (evidence missing)\n"
        "propagation   torque-free Euler\n"
        "  rigid_body.propagate_torque_free\n"
        "  (DOP853, rtol 1e-10)\n"
        f"|r_g(P1)|     {lever:.5f} m lever arm\n"
        f"window cones  grasp +/-{GRASP_CONE_DEG:.0f} deg, vis +/-{VIS_CONE_DEG:.0f} deg\n"
        "  (sim_04_capture_corridor.visibility)\n"
        f"capture grid  t_c in {{0, 30, 60, 90}} s (E1.5 CSV)\n"
        "\n"
        "point colors identify P1/P2/P3 only --\n"
        "NO capture-safety state is claimed here\n"
        f"velocity vectors scaled x{VEL_SCALE:.0f}"
    )
    fig.text(0.695, 0.90, info, fontsize=7.6, family="monospace", va="top",
             bbox=dict(boxstyle="round,pad=0.5", fc="#f6f6f2", ec="#999999"))
    readout = fig.text(0.695, 0.205, "", fontsize=8.0, family="monospace",
                       va="top")
    fig.text(0.34, 0.965,
             "anim_v01  Debris tumble + P1/P2/P3 inertial trajectories + "
             "capture-phase timeline", fontsize=11, ha="center", va="top",
             fontweight="bold")
    vu.add_provenance(
        fig, ["mass_inertia_budget_v1.csv", "rigid_body.propagate_torque_free",
              "e1_thin_slice.GRASP_POINTS", "e15_results_72cases.csv(t_c)",
              "sim_04_capture_corridor.visibility(cones)"],
        extra="tumble axis: E1 context (not E1.5 evidence)")

    # ---------------- per-frame draw ----------------
    def draw(k):
        Tk = np.eye(4)
        Tk[:3, :3] = R_hist[k]
        body.set_transform(Tk)
        for key in PT_COLORS:
            P = p_hist[key]
            trails[key].set_data_3d(P[:k + 1, 0], P[:k + 1, 1], P[:k + 1, 2])
            dots[key].set_data_3d([P[k, 0]], [P[k, 1]], [P[k, 2]])
            tip = P[k] + VEL_SCALE * v_hist[key][k]
            varrows[key].set_data_3d(*np.stack([P[k], tip]).T)
        cursor.set_xdata([t[k], t[k]])
        state = ("WINDOW_OPEN" if graspable[k]
                 else ("OBSERVE" if visible[k] else "OUT_OF_VIEW"))
        near_tc = [tc for tc in T_C_GRID if abs(t[k] - tc) <= 0.5 * SPEED / FPS]
        if near_tc:
            state = f"CAPTURE_TIME t_c={near_tc[0]:.0f}s"
        elif any(0.0 <= tc - t[k] <= APPROACH_S for tc in T_C_GRID):
            state += " | PREGRASP"
        readout.set_text(
            f"t = {t[k]:6.2f} s   state: {state}\n"
            f"|omega| = {np.rad2deg(np.linalg.norm(w_I[k])):.4f} deg/s\n"
            f"|v_P1| = {np.linalg.norm(v_hist['P1'][k]) * 1e3:6.2f} mm/s   "
            f"|v_P2| = {np.linalg.norm(v_hist['P2'][k]) * 1e3:6.2f} mm/s\n"
            f"|v_P3| = {np.linalg.norm(v_hist['P3'][k]) * 1e3:6.2f} mm/s")

    vu.render_video(OUT, fig, N_FRAMES, draw, fps=FPS)

    # ---------------- keyframe checks ----------------
    mrow = mass_csv_row()
    srow = sim06_nominal_row()
    tcs = snapshot_tc_grid()
    k30 = int(np.argmin(np.abs(t - 30.0)))
    rows = [
        vu.kf_row(VIDEO, 0, 0.0, "target mass [kg] (info box)",
                  tgt["mass"], float(mrow["mass_kg"]),
                  "mass_inertia_budget_v1.csv"),
        vu.kf_row(VIDEO, 0, 0.0, "Ixx [kg m^2] (info box)",
                  float(tgt["I"][0, 0]), float(mrow["Ixx_kgm2"]),
                  "mass_inertia_budget_v1.csv"),
        vu.kf_row(VIDEO, 0, 0.0, "Izz [kg m^2] (info box)",
                  float(tgt["I"][2, 2]), float(mrow["Izz_kgm2"]),
                  "mass_inertia_budget_v1.csv"),
        vu.kf_row(VIDEO, 0, 0.0, "|omega_0| [deg/s] (info box)",
                  OMEGA_DPS, float(srow["tumble_dps"]),
                  "capture_impulse_matrix_v0.csv"),
        vu.kf_row(VIDEO, 0, 0.0, "|r_g(P1)| lever arm [m] (info box)",
                  lever, float(srow["grasp_leverarm_m"]),
                  "capture_impulse_matrix_v0.csv", tol=5e-6,
                  note="recomputed from GRASP_POINTS+cg vs sim_06 CSV (5 dp)"),
        vu.kf_row(VIDEO, k30, k30 / FPS, "t_c marker #2 [s] (timeline)",
                  30.0, tcs[1],
                  "e15_results_72cases.csv(t_c_s)"),
        vu.kf_row(VIDEO, N_FRAMES - 1, (N_FRAMES - 1) / FPS,
                  "t_c grid (info box)",
                  "0/30/60/90", "/".join(f"{v:.0f}" for v in tcs),
                  "e15_results_72cases.csv(t_c_s)"),
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
