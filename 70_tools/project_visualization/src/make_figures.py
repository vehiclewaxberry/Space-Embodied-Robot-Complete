"""VIZ-Gate 0 Phase 2 -- the six unified-scene static figures.

40_evidence/artifacts/visualization/figures/
  fig_v01_system_assembly_isometric.png
  fig_v02_system_assembly_top.png
  fig_v03_system_assembly_side.png
  fig_v04_mount_and_frames.png
  fig_v05_target_grasp_points.png
  fig_v06_workspace_keepout.png

All views share 20_engineering/config/visualization/camera_presets_v1.yaml and the color
language of display_semantics_v1.yaml. Every figure carries a lower-right
provenance stamp (runtime git commit + data sources + scenario_hash where
applicable). After generation each PNG is opened with PIL and checked for
non-blankness (pixel std > threshold).
"""
import _viz_bootstrap as vb
import os

import numpy as np
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import scene_assembly as sa                       # noqa: E402
from b601_model import B601Arm                    # noqa: E402 (FK truth, read-only)
from frame_renderer import (draw_triad, draw_arrow, draw_com_marker,          # noqa: E402
                            draw_scale_bar, set_equal_aspect, axis_length_for)
from mesh_utils import (shaded_collection, transform_vf, cylinder_vf,         # noqa: E402
                        cone_vf, box_vf)

FIG_DIR = vb.VIZ_FIGURES_DIR
COMMIT = vb.repo_commit_short()
DPI = 170

with open(os.path.join(vb.VIZ_CONFIG_DIR, "camera_presets_v1.yaml"),
          encoding="utf-8") as f:
    CAMS = yaml.safe_load(f)["presets"]
with open(os.path.join(vb.VIZ_CONFIG_DIR, "display_semantics_v1.yaml"),
          encoding="utf-8") as f:
    SEM = yaml.safe_load(f)
OBJ_C = SEM["object_colors"]
SC = {k: v["hex"] for k, v in SEM["semantic_colors"].items()}
OV = SEM["overlay_styles"]


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def new_fig(preset, figsize=(11.5, 8.0)):
    fig = plt.figure(figsize=figsize)
    ax = fig.add_subplot(111, projection="3d",
                         proj_type=CAMS[preset].get("proj_type", "persp"))
    ax.view_init(elev=CAMS[preset]["elev"], azim=CAMS[preset]["azim"])
    ax.set_axis_off()
    ax.set_position((0.01, 0.05, 0.98, 0.86))
    # manual paint order: meshes are added back-to-front per scene; explicit
    # zorder then keeps annotation markers/triads visible (mplot3d's computed
    # z-order would bury markers inside solids).
    ax.computed_zorder = False
    return fig, ax


def stamp(fig, sources, scenario_hash=None):
    txt = f"git {COMMIT} | data: {', '.join(sources)}"
    if scenario_hash:
        txt += f" | scenario_hash {scenario_hash}"
    fig.text(0.988, 0.006, txt, ha="right", va="bottom", fontsize=5.5,
             color="#555555", family="monospace", wrap=True)


def add_mesh(ax, V, F, color, alpha=1.0, edge=False):
    ax.add_collection3d(shaded_collection(V, F, hex_rgb(color), alpha=alpha,
                                          edge=edge))


def label3d(ax, p, pos, text, color, fontsize=6.3, box=True, ha="center",
            leader=True):
    """Text at pos with a dashed leader line back to p."""
    p = np.asarray(p, float)
    pos = np.asarray(pos, float)
    if leader:
        ax.plot(*np.stack([p, pos]).T, color=color, lw=0.7, ls="--", alpha=0.75)
    kw = dict(fontsize=fontsize, color=color, ha=ha, va="center")
    if box:
        kw["bbox"] = dict(boxstyle="round,pad=0.3", fc="white", ec=color,
                          lw=0.6, alpha=0.88)
    ax.text(pos[0], pos[1], pos[2], text, **kw)


# ==========================================================================
# shared assembly scene (satellite mainline, figures v01..v03)
# ==========================================================================
def build_assembly(ax, sel, sat, alpha_arm=1.0):
    pts = []
    V, F = sa.model_vf("servicer_12U_v0")
    add_mesh(ax, V, F, OBJ_C["servicer_12U_v0"], alpha=0.95)
    pts.append(V)
    T_SM = sa.arm_frames(sel["q"])["T_SM"]
    V, F = sa.model_vf("robot_mount_adapter_v0")
    V2, _ = transform_vf(V, F, T_SM)
    add_mesh(ax, V2, F, OBJ_C["robot_mount_adapter_v0"], alpha=1.0)
    pts.append(V2)
    for name, Vw, Fw in sa.arm_visuals(sel["q"]):
        add_mesh(ax, Vw, Fw, OBJ_C["arm_b601_v1"], alpha=alpha_arm)
        pts.append(Vw)
    V, F = sa.model_vf("target_satellite_v0")
    V2, _ = transform_vf(V, F, sat["T_S_T"])
    add_mesh(ax, V2, F, OBJ_C["target_satellite_v0"], alpha=0.95)
    pts.append(V2)
    return np.vstack(pts)


GRASP_LABEL_POS = {
    "launch_adapter_ring": np.array([0.50, -0.62, -0.40]),
    "solar_panel_yoke_+Y": np.array([1.35, -0.62, 0.42]),
    "solar_panel_yoke_-Y": np.array([1.35, 0.62, 0.42]),
}


def annotate_assembly(ax, sel, sat, tri_len, label_mode="full"):
    fr = sa.arm_frames(sel["q"])
    draw_triad(ax, np.eye(4), tri_len, "S", lw=2.0)
    draw_triad(ax, fr["T_SM"], 0.6 * tri_len, "M", lw=1.6)
    draw_triad(ax, fr["T_E"], 0.55 * tri_len, "E", lw=1.6)
    draw_triad(ax, sat["T_S_T"], 0.8 * tri_len, "T", lw=1.8)
    srv_com = np.array([-0.00242, 0.0, 0.00057])
    draw_com_marker(ax, srv_com, 30, label="CoM 24 kg" if label_mode == "full" else None)
    draw_com_marker(ax, sat["com_S"], 30, label="CoM 22 kg" if label_mode == "full" else None)
    for g in sat["grasp_points"]:
        c = SC["dynamics_unverified"]
        m = "*" if g["priority"] == "primary" else "o"
        ax.scatter(*g["p_S"], s=90 if m == "*" else 36, c=c, marker=m,
                   edgecolors="k", linewidths=0.5, depthshade=False, zorder=10)
        if label_mode == "full":
            label3d(ax, g["p_S"], GRASP_LABEL_POS[g["id"]],
                    f"{g['id']} ({g['priority']})\napproach {g['approach_axis']}",
                    "#444444", fontsize=6.2)


ASSEMBLY_SOURCES = ["servicer_12U_v0.stl", "robot_mount_adapter_v0.stl",
                    "arm_b601_v1.urdf+meshes", "target_satellite_v0.{stl,json}",
                    "frame_tree_v1.yaml", "mass_inertia_budget_v1.csv",
                    "e15_results_72cases.csv(selected_q)"]
GRASP_NOTE = ("satellite grasp points from target_satellite_v0.json: "
              "geometry-verified only, no dynamics evidence (E1/E1.5 evaluated "
              "the DEBRIS target, not this satellite)")


def fig_v01(sel, sat):
    fig, ax = new_fig("isometric")
    P = build_assembly(ax, sel, sat)
    c, r = set_equal_aspect(ax, P)
    tri = axis_length_for(2 * r)
    annotate_assembly(ax, sel, sat, tri, label_mode="full")
    # B free-flyer base note near S
    label3d(ax, np.zeros(3), np.array([-0.30, 0.35, 0.42]),
            "B (free-flyer base) = S\nT_SB = identity (default, unverified)",
            SC["evidence_missing"], fontsize=6.4)
    # relative-position dimension S -> target CoM
    d = float(np.linalg.norm(sat["com_S"]))
    draw_arrow(ax, np.zeros(3), sat["com_S"], "#444444", lw=1.0, head_frac=0.03,
               alpha=0.8, ls="--")
    ax.text(0.52, 0.62, -0.38, f"|r(S->CoM_T)| = {d:.3f} m", fontsize=7,
            color="#444444", ha="center")
    draw_scale_bar(ax, np.array([-0.50, 0.0, -0.55]), 0.5, label="0.5 m")
    fig.text(0.5, 0.045, GRASP_NOTE, ha="center", fontsize=7, color="#555555")
    ax.set_title(
        "fig_v01  System assembly (isometric) -- servicer_12U + adapter + B601 "
        f"@ E1.5 selected q (case {sel['case_id']}) + target_satellite_v0\n"
        "arm pose: geometry-selected (E1.5 roll 0 deg); dynamics admissibility "
        "NOT established (E1.5: admissible 0/72, gate REPEAT_E1_5)",
        fontsize=9.5)
    stamp(fig, ASSEMBLY_SOURCES, sel["scenario_hash"])
    return fig


def fig_v02(sel, sat):
    fig, ax = new_fig("top")
    P = build_assembly(ax, sel, sat)
    c, r = set_equal_aspect(ax, P)
    tri = axis_length_for(2 * r)
    annotate_assembly(ax, sel, sat, tri, label_mode="markers")
    draw_scale_bar(ax, np.array([0.30, -0.55, 0.2]), 0.5, label="0.5 m",
                   updir=(0, 1, 0))
    fig.text(0.5, 0.045, GRASP_NOTE, ha="center", fontsize=7, color="#555555")
    ax.set_title(
        "fig_v02  System assembly (top view, +Z_S down-look, orthographic)\n"
        f"same scene/case as fig_v01 ({sel['case_id']})", fontsize=9.5)
    stamp(fig, ASSEMBLY_SOURCES, sel["scenario_hash"])
    return fig


def fig_v03(sel, sat):
    fig, ax = new_fig("side")
    P = build_assembly(ax, sel, sat)
    c, r = set_equal_aspect(ax, P)
    tri = axis_length_for(2 * r)
    annotate_assembly(ax, sel, sat, tri, label_mode="markers")
    draw_scale_bar(ax, np.array([0.30, 0.0, -0.42]), 0.5, label="0.5 m")
    fig.text(0.5, 0.045, GRASP_NOTE, ha="center", fontsize=7, color="#555555")
    ax.set_title(
        "fig_v03  System assembly (side view from -Y_S, orthographic)\n"
        f"same scene/case as fig_v01 ({sel['case_id']})", fontsize=9.5)
    stamp(fig, ASSEMBLY_SOURCES, sel["scenario_hash"])
    return fig


# ==========================================================================
# fig_v04 -- mount chain S -> M(=A0) -> E with frame tables
# ==========================================================================
def fig_v04(sel):
    fig, ax = new_fig("isometric", figsize=(12.5, 8.0))
    ax.set_position((0.20, 0.04, 0.79, 0.88))
    q0 = np.zeros(6)
    pts = []
    V, F = sa.model_vf("servicer_12U_v0")
    add_mesh(ax, V, F, OBJ_C["servicer_12U_v0"], alpha=0.25)
    T_SM = sa.arm_frames(q0)["T_SM"]
    V, F = sa.model_vf("robot_mount_adapter_v0")
    V2, _ = transform_vf(V, F, T_SM)
    add_mesh(ax, V2, F, OBJ_C["robot_mount_adapter_v0"], alpha=1.0)
    pts.append(V2)
    for name, Vw, Fw in sa.arm_visuals(q0):
        add_mesh(ax, Vw, Fw, OBJ_C["arm_b601_v1"], alpha=0.95)
        pts.append(Vw)
    fr0 = sa.arm_frames(q0)
    pE0 = fr0["T_E"][:3, 3]
    pts.append(np.array([[-0.30, -0.40, -0.48], [0.80, 0.40, 0.34]]))
    P = np.vstack(pts)
    c, r = set_equal_aspect(ax, P)
    tri = axis_length_for(2 * r, frac=0.14)

    draw_triad(ax, np.eye(4), tri, "S", lw=2.0)
    draw_triad(ax, T_SM, 0.75 * tri, "M = A0", lw=1.8)
    draw_triad(ax, fr0["T_E"], 0.65 * tri, "", lw=1.8)
    # chain arrows
    pM = T_SM[:3, 3]
    draw_arrow(ax, np.zeros(3), pM, "#666666", lw=1.1, head_frac=0.10,
               alpha=0.9, ls="--")
    ax.text(0.09, 0.0, 0.10, "T_SM", fontsize=8, color="#444444", ha="center")
    draw_arrow(ax, pM, pE0 - pM, "#666666", lw=1.1, head_frac=0.06,
               alpha=0.9, ls="--")
    mid = 0.5 * (pM + pE0)
    ax.text(mid[0] + 0.05, mid[1] - 0.16, mid[2], "T_ME(q=0)", fontsize=8,
            color="#444444", ha="center")
    # 160x160 interface plate outline (JSON: plate spans x_S 158.25..170.25 mm)
    sq = np.array([[-0.08, -0.08], [0.08, -0.08], [0.08, 0.08], [-0.08, 0.08],
                   [-0.08, -0.08]])
    xs = 0.18525 - 0.027
    ax.plot(np.full(5, xs), sq[:, 0], sq[:, 1], color="#333333", lw=1.0)
    label3d(ax, [xs, 0.08, 0.08], np.array([0.10, 0.34, 0.26]),
            "160 x 160 x 12 plate + O100 x 15 boss\n(robot_mount_adapter_v0, "
            "mount face M at x_S = 185.25 mm)", "#333333", fontsize=6.4)
    label3d(ax, pE0, pE0 + np.array([0.16, -0.24, -0.16]),
            f"E @ q=0\n[{pE0[0]:.4f}, {pE0[1]:.4f}, {pE0[2]:.4f}] m (S)",
            "#222222", fontsize=6.6)
    label3d(ax, T_SM[:3, 3] + np.array([0.02, 0.0, 0.04]),
            np.array([0.32, 0.30, 0.10]),
            "B601 base_link (A0) bolts on mount face\nT_MA0 = identity (nominal)",
            "#444444", fontsize=6.4)

    # frame mini-tables (2D overlay)
    tables = [
        ("S  (servicer body)", ["parent : -", "origin : 12U geometric centre",
                                "source : frame_tree_v1.yaml",
                                "conf   : nominal_frozen_v1"]),
        ("M  (arm mount face)", ["parent : S",
                                 "t      : [185.25, 0, 0] mm",
                                 "quat   : [0.7071, 0, 0.7071, 0]",
                                 "         (wxyz, R_y +90 deg)",
                                 "source : coordinate_frame_definition_v0.md 3.1",
                                 "conf   : nominal_frozen_v1 (D-2)"]),
        ("A0 (B601 base_link)", ["parent : M",
                                 "T_MA0  : identity (nominal)",
                                 "source : arm_b601_v1.urdf header",
                                 "conf   : nominal, mounting not measured"]),
        ("E  (tool centre)", ["parent : link6",
                              "t      : [0, 0, 0.15971] m (link6 axes)",
                              "axes   : = link6 (z_E = approach)",
                              "source : URDF gripper_joint + b601_model",
                              "conf   : nominal"]),
    ]
    y0 = 0.90
    for title, lines in tables:
        txt = title + "\n" + "\n".join(lines)
        fig.text(0.012, y0, txt, fontsize=6.8, family="monospace", va="top",
                 bbox=dict(boxstyle="round,pad=0.4", fc="#f6f6f2",
                           ec="#999999", lw=0.6))
        y0 -= 0.033 + 0.0245 * (len(lines) + 1)
    ax.set_title(
        "fig_v04  Mount chain S -> M(=A0) -> E: frozen T_SM, 160x160 adapter "
        "interface, B601 base and zero configuration\n"
        "(q = 0 shown; joints 2/3 sit ON their upper limits at q=0 -- E1 note)",
        fontsize=9.5)
    stamp(fig, ["frame_tree_v1.yaml", "coordinate_frame_definition_v0.md#3.1",
                "arm_b601_v1.urdf", "robot_mount_adapter_v0.{stl,json}"])
    return fig


# ==========================================================================
# fig_v05 -- E1.5 target (debris) grasp candidates in D frame
# ==========================================================================
def fig_v05(deb, states):
    fig, ax = new_fig("isometric_xy", figsize=(12.5, 8.6))
    V, F = sa.model_vf("target_debris_v0")
    add_mesh(ax, V, F, OBJ_C["target_debris_v0"], alpha=0.45)
    pts = [V]

    keep = hex_rgb(OV["keepout_fill"]["hex"])
    Vc, Fc = cylinder_vf(0.615, -0.9, 0.9, cap=False)
    ax.add_collection3d(shaded_collection(Vc, Fc, keep, alpha=0.16))
    Vc, Fc = cylinder_vf(0.68, -1.55, -1.0, cap=True)
    ax.add_collection3d(shaded_collection(Vc, Fc, keep, alpha=0.16))
    label3d(ax, [-0.44, -0.44, 0.5], np.array([-1.55, -0.9, 0.75]),
            "keepout: smooth shell wall\n(r ~ 0.6 m, |z| < 0.9 m, JSON)",
            SC["physical_violation"], fontsize=6.4)
    label3d(ax, [-0.48, -0.48, -1.25], np.array([-1.55, -0.9, -1.35]),
            "keepout: aft engine region\n(z < -1.0 m, JSON)",
            SC["physical_violation"], fontsize=6.4)

    # tumble axis -- E1 context value, evidence-missing for E1.5
    w = np.array([1.0, 0.15, 0.4])
    w = w / np.linalg.norm(w)
    cg = deb["cg_D"]
    draw_arrow(ax, cg - 1.5 * w, 3.1 * w, SC["evidence_missing"], lw=2.0,
               head_frac=0.05, ls="--")
    label3d(ax, cg + 1.6 * w, np.array([1.9, 0.9, 1.05]),
            "omega axis [1, 0.15, 0.4]/|.| @ 3 deg/s\n(E1 grid context -- E1.5 "
            "snapshot does not\nrestate it: evidence missing)",
            SC["evidence_missing"], fontsize=6.4)

    state_note = {
        "P1": ("unknown", "selected v=10 mm/s: FLEX_SOLVER_UNKNOWN;\n"
               "same geometry group v=5/20 mm/s: PHYSICAL_LIMIT_EXCEEDED"),
        "P2": ("geometry_infeasible", "GEOMETRY IK_FAIL (all t_c); dynamics: "
               "MISSING_FRESH_EVIDENCE\n(not a physical-safety verdict)"),
        "P3": ("geometry_infeasible", "GEOMETRY IK_FAIL (all t_c); dynamics: "
               "MISSING_FRESH_EVIDENCE\n(not a physical-safety verdict)"),
    }
    rolls_p1 = states["feasible_rolls"].get("P1|tc=0|pose_6d", [])
    roll_txt = {
        "P1": (f"roll in [{min(rolls_p1):.0f}, {max(rolls_p1):.0f}] deg "
               f"({len(rolls_p1)}/7 grid feasible, pose_6d, t_c=0;\n"
               "approach_5d: roll unconstrained, realized -95.6 deg)"),
        "P2": "no feasible roll (0/7 at every t_c)",
        "P3": "no feasible roll (0/7 at every t_c)",
    }
    box_pos = {"P1": np.array([2.15, -0.4, 1.55]),
               "P2": np.array([-1.15, 1.7, 1.55]),
               "P3": np.array([2.15, -0.3, -1.45])}
    for pid, p in deb["grasp_points_D"].items():
        ckey, note = state_note[pid]
        col = SC[ckey]
        ax.scatter(*p, s=80, c=col, marker="o", edgecolors="k", linewidths=0.7,
                   depthshade=False, zorder=10)
        a = deb["approach_D"][pid]
        draw_arrow(ax, p, 0.45 * a, col, lw=2.2, head_frac=0.14)
        Tc = np.eye(4)
        Tc[:3, :3] = deb["grasp_frames_D"][pid]   # columns = x_C,y_C,z_C in D
        Tc[:3, 3] = p
        draw_triad(ax, Tc, 0.18, None, lw=1.3)
        Vk, Fk = cone_vf(p, a, 12.0, 0.5)
        ax.add_collection3d(shaded_collection(Vk, Fk, hex_rgb(col), alpha=0.10))
        label3d(ax, p + 0.45 * a, box_pos[pid],
                f"{pid}  [{p[0]:.2f}, {p[1]:.2f}, {p[2]:.2f}] m (D)\n"
                f"approach n = [{a[0]:.0f}, {a[1]:.0f}, {a[2]:.0f}]  "
                f"(cone half-angle schematic)\n{roll_txt[pid]}\n{note}",
                col, fontsize=6.3)
        pts.append((p + 0.6 * a)[None, :])

    draw_triad(ax, np.eye(4), 0.5, "D", lw=2.0)
    draw_com_marker(ax, cg, 34, label="CoM 150 kg")
    P = np.vstack(pts + [np.array([[1.9, 1.5, 1.7], [-1.6, -1.1, -1.7]])])
    set_equal_aspect(ax, P)
    fig.text(0.5, 0.022,
             "Geometry screen: only P1@tc0 has feasible rolls; P2/P3 are "
             "IK_FAIL. Point colors are not physical-safety verdicts.\n"
             "E1.5 reasons: PHYSICAL_LIMIT_EXCEEDED 3 | FLEX_SOLVER_UNKNOWN 3 | "
             "MISSING_FRESH_EVIDENCE 66 | VERIFIED_SAFE 0\n"
             "gate REPEAT_E1_5. Approach cones are schematic; half-angle is "
             "illustrative, not data.",
             ha="center", va="bottom", fontsize=6.6, color="#333333",
             linespacing=1.2)
    ax.set_title(
        "fig_v05  E1.5 grasp candidates P1/P2/P3 on target_debris_v0 (frame D)\n"
        "positions/frames: e1_thin_slice grid == E1.5 geometry_group_keys; "
        "feasible-roll sets: e15_geometry_roll_details.csv", fontsize=9.5)
    stamp(fig, ["target_debris_v0.{stl,json}", "e1_thin_slice.py(GRASP_POINTS)",
                "e15_geometry_manifest.json", "e15_geometry_roll_details.csv",
                "e15_gate_check.json"],
          "4648e26f6240b367")
    return fig


# ==========================================================================
# fig_v06 -- B601 reachable cloud + condition number + keepouts
# ==========================================================================
def workspace_cloud(n_per=9, j5=0.0, j6=0.0):
    arm = B601Arm()
    lims = [(-2.8, 2.8), (-3.14, 0.0), (-3.14, 0.0), (-1.87, 1.57)]
    grids = [np.linspace(lo, hi, n_per) for lo, hi in lims]
    Q = np.stack(np.meshgrid(*grids, indexing="ij"), axis=-1).reshape(-1, 4)
    P = np.zeros((len(Q), 3))
    C = np.zeros(len(Q))
    q = np.zeros(6)
    q[4], q[5] = j5, j6
    for i, q4 in enumerate(Q):
        q[:4] = q4
        f = arm.fk(q)
        P[i] = f["T_E"][:3, 3]
        J = arm.jacobian(q, fk_out=f)
        s = np.linalg.svd(J, compute_uv=False)
        C[i] = s[0] / max(s[-1], 1e-16)
    return P, C


def fig_v06(sel, deb):
    fig, ax = new_fig("isometric", figsize=(12.5, 8.6))
    P, C = workspace_cloud()
    ok = C <= 1e3

    pts = [P]
    V, F = sa.model_vf("servicer_12U_v0")
    add_mesh(ax, V, F, OBJ_C["servicer_12U_v0"], alpha=0.45)
    pts.append(V)
    T_SM = sa.arm_frames(sel["q"])["T_SM"]
    V, F = sa.model_vf("robot_mount_adapter_v0")
    V2, _ = transform_vf(V, F, T_SM)
    add_mesh(ax, V2, F, OBJ_C["robot_mount_adapter_v0"], alpha=0.7)
    for name, Vw, Fw in sa.arm_visuals(sel["q"]):
        add_mesh(ax, Vw, Fw, OBJ_C["arm_b601_v1"], alpha=0.45)

    ax.scatter(P[ok, 0], P[ok, 1], P[ok, 2], s=2.0,
               c=OV["workspace_cloud_ok"]["hex"], alpha=0.15, linewidths=0,
               depthshade=False)
    ax.scatter(P[~ok, 0], P[~ok, 1], P[~ok, 2], s=10.0,
               c=OV["workspace_cloud_singular"]["hex"], alpha=0.95,
               linewidths=0, depthshade=False, zorder=6)

    keep = hex_rgb(OV["keepout_fill"]["hex"])
    # solar panels = fragile keepout boxes (12U JSON primitives, mm -> m)
    for cy in (0.21315, -0.21315):
        Vb, Fb = box_vf([-0.05675, cy, 0.0], [0.227, 0.200, 0.006])
        ax.add_collection3d(shaded_collection(Vb, Fb, keep, alpha=0.30))
    label3d(ax, [-0.057, 0.31, 0.0], np.array([-0.55, 0.75, 0.35]),
            "solar panel keepout\n(both +/-Y_S panels)",
            SC["physical_violation"], fontsize=6.4)
    # camera FOV cone (12U JSON: apex [210,0,80] mm, +X, half-angle 20 deg)
    Vk, Fk = cone_vf([0.210, 0.0, 0.080], [1, 0, 0], 20.0, 0.9)
    ax.add_collection3d(shaded_collection(
        Vk, Fk, hex_rgb(OV["camera_fov"]["hex"]), alpha=OV["camera_fov"]["alpha"]))
    label3d(ax, [0.9, 0.0, 0.33], np.array([0.75, 0.75, 0.72]),
            "camera FOV cone 20 deg (JSON)", "#8a7200", fontsize=6.4)
    # target (E1.5 debris) collision envelope as keepout, placed in S.
    # Drawn only above z_S ~ -0.95 (envelope continues to z_S = -2.05; cropped
    # for framing -- see label).
    T_S_D = deb["T_S_T"]
    Vc, Fc = cylinder_vf(0.66, 0.12, 1.0, cap=True)        # z_D 0.12..1.0
    Vc2, _ = transform_vf(Vc, Fc, T_S_D)
    ax.add_collection3d(shaded_collection(Vc2, Fc, keep, alpha=0.16))
    label3d(ax, [1.61 + 0.4, 0.4, -0.5], np.array([2.05, 0.9, -0.15]),
            "target_debris_v0 collision envelope\n(E1.5 scene placement, P1 @ "
            "t_c=0;\ncropped below z_S = -0.95 for framing)",
            SC["physical_violation"], fontsize=6.4)
    pts.append(Vc2)

    # capture point + frames
    cp = deb["capture_point_S"]
    ax.scatter(*cp, s=150, c="#111111", marker="*", depthshade=False, zorder=10)
    label3d(ax, cp, np.array([1.35, -0.75, -0.72]),
            "pre-grasp capture point\n[0.95, 0, -0.10] m (evaluator E0 policy)",
            "#111111", fontsize=6.6)
    draw_triad(ax, np.eye(4), 0.22, "S", lw=1.8)
    draw_triad(ax, T_SM, 0.13, "M", lw=1.4)

    # +X_S axial singular band
    band = P[(~ok) & (np.abs(P[:, 1]) < 0.08) & (np.abs(P[:, 2]) < 0.08)]
    ax.plot([0.185, 1.35], [0, 0], [0, 0],
            color=OV["workspace_cloud_singular"]["hex"], lw=1.2, ls=":",
            alpha=0.95)
    label3d(ax, [1.05, 0.0, 0.0], np.array([0.05, -1.2, -0.80]),
            "+X_S on-axis singular band (dotted line):\n"
            f"cond(J) > 1e3 in red; max sampled = {C.max():.1e}\n"
            f"{len(band)} of {int((~ok).sum())} singular samples lie on-axis;\n"
            "capture point is offset z = -0.10 m to avoid it",
            SC["physical_violation"], fontsize=6.4)

    Pex = np.vstack(pts + [cp[None, :]])
    Pex = Pex[Pex[:, 2] > -1.1]
    set_equal_aspect(ax, Pex)
    fig.text(0.5, 0.040,
             "Reachable-set point cloud: FK truth (b601_model.B601Arm), grid "
             "9^4 over j1..j4 (6561 samples), j5 = j6 = 0 representative; "
             "color = cond(6x6 geometric Jacobian), threshold 1e3. Display "
             "only -- no controllability claim.",
             ha="center", fontsize=7.5, color="#333333")
    ax.set_title(
        "fig_v06  B601 reachable cloud + singular band + keepouts (frame S)\n"
        f"arm ghost @ E1.5 selected q ({sel['case_id']}); target keepout at "
        "E1.5 scene placement", fontsize=9.5)
    stamp(fig, ["b601_model.py(FK)", "arm_b601_v1.urdf", "servicer_12U_v0.json",
                "target_debris_v0.json", "adapters.scene_placement",
                "e15_results_72cases.csv"], sel["scenario_hash"])
    return fig


# ==========================================================================
def blank_check(path, min_std=18.0):
    from PIL import Image
    im = np.asarray(Image.open(path).convert("L"), float)
    return float(im.std()), float(im.std()) >= min_std


def main():
    sel = sa.e15_selected_case()
    sat = sa.satellite_scene()
    deb = sa.debris_scene()
    states = sa.e15_states()
    jobs = [
        ("fig_v01_system_assembly_isometric.png", lambda: fig_v01(sel, sat)),
        ("fig_v02_system_assembly_top.png", lambda: fig_v02(sel, sat)),
        ("fig_v03_system_assembly_side.png", lambda: fig_v03(sel, sat)),
        ("fig_v04_mount_and_frames.png", lambda: fig_v04(sel)),
        ("fig_v05_target_grasp_points.png", lambda: fig_v05(deb, states)),
        ("fig_v06_workspace_keepout.png", lambda: fig_v06(sel, deb)),
    ]
    results = []
    for name, fn in jobs:
        fig = fn()
        out = os.path.join(FIG_DIR, name)
        fig.savefig(out, dpi=DPI, facecolor="white")
        plt.close(fig)
        std, ok = blank_check(out)
        results.append((name, std, ok))
        print(f"{name}: pixel_std={std:.1f} non-blank={'PASS' if ok else 'FAIL'}")
    if not all(ok for _, _, ok in results):
        raise SystemExit("blank-figure self-check FAILED")
    print("all 6 figures generated + non-blank self-check PASS")


if __name__ == "__main__":
    main()
