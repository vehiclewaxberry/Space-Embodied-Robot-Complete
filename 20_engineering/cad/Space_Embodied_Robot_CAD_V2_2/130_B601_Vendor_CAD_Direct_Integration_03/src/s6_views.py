"""VENDOR-CAD-03 S6a：轻量视图渲染（快照工具无法承载 252MB STEP 的替代管线）。

臂=网格缓存顶点×位姿变换；上下文=OCC 粗网格化轻 STEP。matplotlib 三角面渲染，
>30 万三角形时确定性子采样（视觉用途，几何裁决不依赖视图）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "src"))
import s4_repose as s4
from s4b_mesh_cache import SCRATCH, mesh_group

GROUP_COLORS = {"G01": "#5a6b80", "G02": "#9aa4b0", "G03": "#9aa4b0",
                "G04": "#8a93a0", "G05": "#4a5568", "G06": "#3d4a63",
                "G07": "#6b7686", "G08": "#d97c26"}
CTX_COLOR = "#7c93b5"
MAX_TRIS = 80_000


def arm_mesh(pose):
    cache = np.load(SCRATCH / "mesh_cache.npz")
    adopted = json.loads((HERE / "design/group_link_transforms.json")
                         .read_text(encoding="utf-8"))["adopted"]
    if pose == "STOW":
        q = np.array(json.loads(s4.STOW_JSON.read_text(encoding="utf-8"))["q_rad"])
    else:
        q = np.zeros(6)
    frames = s4.link_frames_cs_s(q)
    tris, cols = [], []
    for gid, a in adopted.items():
        R_fk, p_fk = frames[a["urdf_link_frame"]]
        R_l, t_l = np.array(a["R_rows"]), np.array(a["t_mm"])
        v = cache[f"{gid}_v"].astype(float) @ (R_fk @ R_l).T + (R_fk @ t_l + p_fk)
        t = cache[f"{gid}_t"]
        tris.append(v[t])
        cols.append(np.full(len(t), GROUP_COLORS[gid], dtype=object))
    return np.vstack(tris), np.concatenate(cols)


_ctx_cache = {}


def ctx_mesh(step_path):
    key = step_path.name
    if key not in _ctx_cache:
        v, t = mesh_group(step_path)
        _ctx_cache[key] = v.astype(float)[t]
    tri = _ctx_cache[key]
    return tri, np.full(len(tri), CTX_COLOR, dtype=object)


def render(tris, cols, out, elev=28, azim=-60, title=""):
    if len(tris) > MAX_TRIS:
        idx = np.linspace(0, len(tris) - 1, MAX_TRIS).astype(int)
        tris, cols = tris[idx], cols[idx]
    fig = plt.figure(figsize=(11, 8), dpi=110)
    ax = fig.add_subplot(projection="3d")
    rgba = matplotlib.colors.to_rgba_array(list(cols))
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    nn = np.linalg.norm(n, axis=1, keepdims=True)
    n = n / np.where(nn < 1e-12, 1.0, nn)
    L = np.array([0.4, -0.5, 0.77])
    lam = 0.35 + 0.65 * np.abs(n @ L)          # 手工 Lambert（双面）
    rgba[:, :3] = rgba[:, :3] * lam[:, None]
    pc = Poly3DCollection(tris, facecolors=rgba, edgecolors="none")
    ax.add_collection3d(pc)
    lo = tris.reshape(-1, 3).min(axis=0)
    hi = tris.reshape(-1, 3).max(axis=0)
    c = (lo + hi) / 2
    r = float((hi - lo).max()) / 2
    ax.set_xlim(c[0] - r, c[0] + r)
    ax.set_ylim(c[1] - r, c[1] + r)
    ax.set_zlim(c[2] - r, c[2] + r)
    ax.view_init(elev=elev, azim=azim)
    ax.set_box_aspect((1, 1, 1))
    ax.set_xlabel("X_S"); ax.set_ylabel("Y_S"); ax.set_zlabel("Z_S")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(HERE / "views" / out)
    plt.close(fig)
    import gc
    gc.collect()
    print("view:", out)


def main():
    (HERE / "views").mkdir(exist_ok=True)
    a_stow = arm_mesh("STOW")
    a_q0 = arm_mesh("Q0")
    render(*a_stow, "v01_arm_stow_iso.png", title="B601 vendor real, STOW v2 (clock 25°)")
    render(*a_q0, "v02_arm_q0_iso.png", title="B601 vendor real, Q0 (clock 25°)")
    ctx_states = {"STOWED": ("STOW", [("v03_state_stowed_iso.png", 28, -60),
                                        ("v04_state_stowed_front.png", 0, 0),
                                        ("v05_state_stowed_top.png", 90, -90)]),
                  "DEPLOYED_NOMINAL": ("Q0", [("v06_state_deployed_iso.png", 28, -60)]),
                  "L_FAIL": ("Q0", [("v07_state_lfail_top.png", 90, -90)]),
                  "R_FAIL": ("Q0", [("v08_state_rfail_top.png", 90, -90)])}
    for sid, (rep, jobs) in ctx_states.items():
        ct, cc = ctx_mesh(HERE / f"staging/state_{sid}_CONTEXT.step")
        at, ac = a_stow if rep == "STOW" else a_q0
        tris = np.vstack([ct, at])
        cols = np.concatenate([cc, ac])
        for out, elev, azim in jobs:
            render(tris, cols, out, elev, azim, f"{sid} (context + real arm)")
    ad, _ = ctx_mesh(HERE / "cad/B601_SPACECRAFT_ADAPTER.step")
    render(ad, np.full(len(ad), "#3d6a8f", dtype=object),
           "v09_adapter_iso.png", 22, -35, "Spacecraft adapter (clock 25°)")
    sp, _ = ctx_mesh(HERE / "cad/B601_STOW_SUPPORT_V2.step")
    render(sp, np.full(len(sp), "#c06a1a", dtype=object),
           "v10_support_iso.png", 22, -60, "Stow support v2 (real-contact heights)")


if __name__ == "__main__":
    main()
