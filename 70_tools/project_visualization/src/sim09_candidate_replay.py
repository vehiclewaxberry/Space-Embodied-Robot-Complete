"""anim_v02_b601_approach.mp4 -- B601 min-jerk approach to the E1.5 selected q_c.

Case: P1_tc00_v10mm_pose_6d (E1.5 G0 baseline grid cell). The target joint
configuration is the SNAPSHOT value selected_q_json (iron rule 2); the on-screen
declaration states it is GEOMETRY-SELECTED (E1.5 roll 0 deg) with dynamics
admissibility NOT established (gate REPEAT_E1_5).

Read-only recompute chain (cheap kinematics, not a sweep):
  * trajectory      adapters.approach_trajectory (min-jerk, 8 s -- evaluator
                    DEFAULT_CONFIG approach.duration_s)
  * FK / Jacobian   b601_model.B601Arm (numerical truth) via ik.residual_and_
                    jacobian for the SAME pose_6d task Jacobian the evaluator
                    conditions on
  * collision       30_simulation/sim_09_grasp_evaluator/src/collision.py on the evaluator's
                    exact 25-sample grid (coarse capsule model, phase-A grade)
  * placement       adapters.scene_placement at t_c = 0 (same chain as E1.5)

Keyframe checks tie cond(J), min collision margin and q_c back to the E1.5
snapshot CSV row bit-exactly.
"""
import _viz_bootstrap as vb
import os

import numpy as np

import video_utils as vu
import scene_assembly as sa
import adapters
import collision
import evaluator
import ik as ik_mod
import target_propagation
from b601_renderer import B601VisualChain
from e1_thin_slice import make_candidate
from frame_renderer import draw_triad, set_equal_aspect
from rigid_body import load_object

VIDEO = "anim_v02_b601_approach"
OUT = os.path.join(vu.VIDEO_DIR, VIDEO + ".mp4")
CASE_ID = "P1_tc00_v10mm_pose_6d"

FPS = 24
T_TRAJ = 8.0                        # evaluator approach duration
SLOWDOWN = 2.0                      # 2x slow motion -> 16 s
N_MOVE = int(T_TRAJ * SLOWDOWN * FPS)            # 384
N_HOLD = 4 * FPS                                 # 4 s end hold
N_FRAMES = N_MOVE + N_HOLD


def build():
    sel = sa.e15_selected_case(CASE_ID)
    deb = sa.debris_scene()
    q_c = sel["q"]
    q0 = np.zeros(6)
    arm = ik_mod.get_arm()

    # --- placement chain (identical to the evaluator at t_c = 0) ---
    cand = make_candidate({"grasp_point_id": "P1", "t_c": 0.0,
                           "v_app": 0.01, "mode": "pose_6d"})
    prop = target_propagation.propagate(cand.target_state,
                                        cand.grasp_pose_target[:3, 3], 0.0)
    p_cap = evaluator.DEFAULT_CONFIG["scenario"]["capture_point_S"]
    placement = adapters.scene_placement(cand, prop, p_cap)
    task = ik_mod.make_task("pose_6d", placement["p_des_S"],
                            R_des=placement["R_des_S"])

    # --- trajectory + per-frame kinematics ---
    q_fun, qd_fun = adapters.approach_trajectory(q0, q_c, T_TRAJ)
    t_frames = np.minimum(np.arange(N_FRAMES) / (SLOWDOWN * FPS), T_TRAJ)
    Q = np.array([q_fun(t) for t in t_frames])
    QD = np.array([qd_fun(t) for t in t_frames])
    ee_speed = np.zeros(N_FRAMES)
    condJ = np.zeros(N_FRAMES)
    pE = np.zeros((N_FRAMES, 3))
    for k in range(N_FRAMES):
        f = arm.fk(Q[k])
        pE[k] = f["T_E"][:3, 3]
        ee_speed[k] = np.linalg.norm(arm.jacobian(Q[k], fk_out=f)[:3] @ QD[k])
        _, Jt, _ = ik_mod.residual_and_jacobian(arm, Q[k], task)
        sv = np.linalg.svd(Jt, compute_uv=False)
        condJ[k] = sv[0] / max(sv[-1], 1e-300)

    # --- collision margins on the evaluator's exact grid (25 samples) ---
    cg_T = load_object("target_debris_v0")["cg"]
    tprim = collision.target_primitive("target_debris_v0", placement["R_TS"],
                                       placement["r_T_S"], cg_T)
    t_grid = np.linspace(0.0, T_TRAJ,
                         int(evaluator.DEFAULT_CONFIG["collision"]["n_time_samples"]))
    col = collision.trajectory_margin(arm, q_fun, t_grid, tprim,
                                      placement["p_des_S"])
    margins = np.asarray(col["margins"])

    # ---------------- figure ----------------
    fig = vu.make_fig()
    ax = fig.add_axes((-0.03, 0.05, 0.60, 0.86), projection="3d")
    ax.view_init(elev=vu.CAMS["isometric"]["elev"],
                 azim=vu.CAMS["isometric"]["azim"])
    ax.set_axis_off()
    ax.computed_zorder = False

    pts = []
    V, F = sa.model_vf("servicer_12U_v0", target_faces=5000)
    vu.MeshActor(ax, V, F, vu.OBJ_C["servicer_12U_v0"], alpha=0.9)
    pts.append(V)
    chain = B601VisualChain()
    T_SM = sa.arm_frames(q0)["T_SM"]
    V, F = sa.model_vf("robot_mount_adapter_v0", target_faces=1500)
    vu.MeshActor(ax, V, F, vu.OBJ_C["robot_mount_adapter_v0"]).set_transform(T_SM)
    arm_actors = []
    for name, mesh_path, T in chain.visual_poses(q0):
        Vl, Fl = sa.display_mesh(mesh_path, 1200)
        a = vu.MeshActor(ax, Vl, Fl, vu.OBJ_C["arm_b601_v1"], alpha=0.95)
        arm_actors.append((a, mesh_path))
        pts.append(a.set_transform(T))
    V, F = sa.model_vf("target_debris_v0", target_faces=4000)
    dact = vu.MeshActor(ax, V, F, vu.OBJ_C["target_debris_v0"], alpha=0.45)
    pts.append(dact.set_transform(deb["T_S_T"]))

    cp = np.asarray(deb["capture_point_S"], float)
    ax.scatter(*cp, s=140, c="#111111", marker="*", depthshade=False, zorder=10)
    ax.text(cp[0], cp[1], cp[2] - 0.17, "capture point\n[0.95, 0, -0.10] m",
            fontsize=6.5, ha="center")
    draw_triad(ax, np.eye(4), 0.22, "S", lw=1.6)
    trail, = ax.plot([], [], [], color="#1f77b4", lw=1.6)
    P = np.vstack(pts + [cp[None, :]])
    set_equal_aspect(ax, P[P[:, 2] > -1.0])

    fig.text(0.30, 0.972,
             f"anim_v02  B601 approach q0 -> E1.5 selected q_c  (case {CASE_ID})",
             fontsize=11, ha="center", va="top", fontweight="bold")
    fig.text(0.30, 0.935,
             "arm pose target: GEOMETRY-SELECTED (E1.5 roll 0 deg) -- dynamics "
             "admissibility NOT established\n(E1.5 admissible 0/72, gate "
             "REPEAT_E1_5); min-jerk 8 s (evaluator config), playback 0.5x",
             fontsize=7.2, ha="center", va="top", color="#333333")

    # ---------------- right-hand live curves ----------------
    t_all = t_frames
    axs = [fig.add_axes((0.645, y, 0.335, 0.16)) for y in
           (0.79, 0.565, 0.34, 0.115)]
    ax_q, ax_v, ax_c, ax_k = axs
    for a in axs:
        a.tick_params(labelsize=6.5)
        a.grid(alpha=0.25, lw=0.4)
        a.set_xlim(0, T_TRAJ)
    for j in range(6):
        ax_q.plot(t_all, np.rad2deg(Q[:, j]), lw=1.1, label=f"q{j + 1}")
    ax_q.legend(fontsize=5.2, ncol=6, loc="lower left", frameon=False)
    ax_q.set_ylabel("joint angle [deg]", fontsize=7)
    ax_v.plot(t_all, ee_speed * 1e3, color="#1f77b4", lw=1.3)
    ax_v.set_ylabel("EE speed [mm/s]", fontsize=7)
    ax_c.step(t_grid, margins, where="mid", color="#2ca02c", lw=1.3)
    ax_c.axhline(0.02, color=vu.SC["physical_violation"], lw=0.9, ls="--")
    ax_c.text(7.9, 0.024, "hard limit 0.02 m", fontsize=5.8, ha="right",
              color=vu.SC["physical_violation"])
    ax_c.set_ylabel("min collision\nmargin [m]", fontsize=7)
    ax_c.text(0.02, 0.05, "coarse capsule model, evaluator 25-sample grid",
              transform=ax_c.transAxes, fontsize=5.4, color="#666666")
    ax_k.semilogy(t_all, condJ, color="#9467bd", lw=1.3)
    ax_k.set_ylabel("cond(J_task)", fontsize=7)
    ax_k.set_xlabel("trajectory time [s]", fontsize=7)
    cursors = [a.axvline(0, color="#c8443c", lw=1.2) for a in axs]
    readout = fig.text(0.035, 0.855, "", fontsize=7.6, family="monospace",
                       va="top")

    vu.add_provenance(
        fig, ["e15_results_72cases.csv(selected_q)", "arm_b601_v1.urdf+meshes",
              "b601_model.py(FK)", "collision_geometry_v1.yaml",
              "adapters.scene_placement", "target_debris_v0.stl"],
        scenario_hash=sel["scenario_hash"])

    def draw(k):
        tk = t_frames[k]
        lp = chain.visual_poses(Q[k])
        for (a, mesh_path), (_, mp2, T) in zip(arm_actors, lp):
            a.set_transform(T)
        trail.set_data_3d(pE[:k + 1, 0], pE[:k + 1, 1], pE[:k + 1, 2])
        for c in cursors:
            c.set_xdata([tk, tk])
        gi = int(np.argmin(np.abs(t_grid - tk)))
        readout.set_text(
            f"t = {tk:5.2f} s / {T_TRAJ:.0f} s\n"
            f"cond(J_task) = {condJ[k]:9.2f}   EE speed = {ee_speed[k] * 1e3:6.2f} mm/s\n"
            f"margin(grid) = {margins[gi]:.5f} m   min = {col['min_margin_m']:.5f} m "
            f"@ t = {col['t_at_min_s']:.1f} s")

    vu.render_video(OUT, fig, N_FRAMES, draw, fps=FPS)

    # ---------------- keyframe checks vs the E1.5 snapshot row ----------------
    import csv as _csv
    p = os.path.join(vb.SNAPSHOT_DIR,
                     "results__sim_09_grasp_evaluator__e15_results_72cases.csv")
    with open(p, encoding="utf-8") as f:
        row = next(r for r in _csv.DictReader(f) if r["case_id"] == CASE_ID)
    import json as _json
    q_csv = _json.loads(row["selected_q_json"])
    kf = N_FRAMES - 1
    rows = [
        vu.kf_row(VIDEO, kf, kf / FPS, "cond(J_task) at q_c (readout)",
                  float(condJ[N_MOVE]), float(row["condition_number"]),
                  "e15_results_72cases.csv", tol=1e-9,
                  note="recomputed task-Jacobian conditioning, bit-level"),
        vu.kf_row(VIDEO, kf, kf / FPS, "min collision margin [m] (readout)",
                  float(col["min_margin_m"]),
                  float(row["collision_margin_min_m"]),
                  "e15_results_72cases.csv", tol=0.0,
                  note="evaluator 25-sample grid, exact"),
        vu.kf_row(VIDEO, kf, kf / FPS, "collision t_at_min [s] (readout)",
                  float(col["t_at_min_s"]), float(row["collision_t_at_min_s"]),
                  "e15_results_72cases.csv"),
        vu.kf_row(VIDEO, kf, kf / FPS, "q_c joint2 [rad] (curve endpoint)",
                  float(Q[N_MOVE][1]), float(q_csv[1]),
                  "e15_results_72cases.csv(selected_q_json)"),
        vu.kf_row(VIDEO, kf, kf / FPS, "q_c joint3 [rad] (curve endpoint)",
                  float(Q[N_MOVE][2]), float(q_csv[2]),
                  "e15_results_72cases.csv(selected_q_json)"),
        vu.kf_row(VIDEO, kf, kf / FPS, "q_c joint4 [rad] (curve endpoint)",
                  float(Q[N_MOVE][3]), float(q_csv[3]),
                  "e15_results_72cases.csv(selected_q_json)"),
        vu.kf_row(VIDEO, 0, 0.0, "scenario_hash (footer)",
                  sel["scenario_hash"], row["scenario_hash"],
                  "e15_results_72cases.csv"),
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
