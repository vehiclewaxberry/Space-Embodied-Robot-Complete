"""Unified coordinate-frame triad drawing (VIZ-Gate 0, shared by all figures).

One drawing style everywhere: x axis red, y green, z blue (RGB=XYZ), axis
length auto-scaled from the scene extent, label at the origin. Downstream
agents should import draw_triad / draw_arrow instead of re-implementing.
"""
import _viz_bootstrap  # noqa: F401
import numpy as np

AXIS_COLORS = ("#d62728", "#2ca02c", "#1f77b4")     # x, y, z


def axis_length_for(extent_m, frac=0.09, lo=0.02, hi=0.6):
    """Adaptive triad axis length from the scene extent (max bbox span)."""
    return float(np.clip(frac * extent_m, lo, hi))


def draw_arrow(ax, p0, vec, color, lw=1.6, head_frac=0.18, alpha=1.0, ls="-"):
    """3D arrow as line + small head cross (quiver heads render badly at DPI)."""
    p0 = np.asarray(p0, float)
    v = np.asarray(vec, float)
    p1 = p0 + v
    ax.plot(*np.stack([p0, p1]).T, color=color, lw=lw, alpha=alpha,
            ls=ls, solid_capstyle="round")
    n = np.linalg.norm(v)
    if n <= 0:
        return
    d = v / n
    seed = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(d, seed)
    u /= np.linalg.norm(u)
    w = np.cross(d, u)
    h = head_frac * n
    for side in (u, -u, w, -w):
        q = p1 - h * d + 0.5 * h * side
        ax.plot(*np.stack([p1, q]).T, color=color, lw=lw, alpha=alpha,
                solid_capstyle="round")


def draw_triad(ax, T, length, label=None, lw=1.8, alpha=1.0,
               label_axis=True, fontsize=8, label_color="k"):
    """Draw a frame triad from a 4x4 pose. Columns of R = frame axes."""
    T = np.asarray(T, float)
    o = T[:3, 3]
    for k in range(3):
        draw_arrow(ax, o, length * T[:3, k], AXIS_COLORS[k], lw=lw, alpha=alpha)
        if label_axis:
            tip = o + 1.18 * length * T[:3, k]
            ax.text(*tip, "xyz"[k], color=AXIS_COLORS[k],
                    fontsize=fontsize - 1, ha="center", va="center")
    if label:
        ax.text(*(o - 0.22 * length * (T[:3, 0] + T[:3, 2])), label,
                color=label_color, fontsize=fontsize, fontweight="bold",
                ha="center", va="center")


def draw_com_marker(ax, p, size, color="#222222", label=None, fontsize=7):
    """Ball-and-cross CoM marker."""
    p = np.asarray(p, float)
    ax.scatter(*p, s=size, c=color, marker="o", depthshade=False,
               edgecolors="white", linewidths=0.6, zorder=6)
    if label:
        ax.text(p[0], p[1], p[2] + 0.6 * np.sqrt(size) * 1e-3 + 0.01, label,
                fontsize=fontsize, color=color, ha="center")


def draw_scale_bar(ax, p0, length_m, direction=(1, 0, 0), color="k",
                   label=None, fontsize=8, tick=0.02, updir=None):
    """Simple 3D scale bar with end ticks (updir = tick/label direction)."""
    p0 = np.asarray(p0, float)
    d = np.asarray(direction, float)
    d = d / np.linalg.norm(d)
    p1 = p0 + length_m * d
    if updir is None:
        updir = (0.0, 0.0, 1.0) if abs(d[2]) < 0.9 else (1.0, 0.0, 0.0)
    up = np.asarray(updir, float)
    up = up / np.linalg.norm(up)
    ax.plot(*np.stack([p0, p1]).T, color=color, lw=2.0)
    for p in (p0, p1):
        ax.plot(*np.stack([p - tick * up, p + tick * up]).T, color=color, lw=2.0)
    mid = 0.5 * (p0 + p1) - 3.0 * tick * up
    ax.text(*mid, label or f"{length_m:g} m", fontsize=fontsize,
            color=color, ha="center", va="top")


def set_equal_aspect(ax, pts, pad=0.06, min_frac=0.28):
    """TRUE equal-scale limits around the points (n,3): per-axis spans with a
    box aspect proportional to the spans, so elongated scenes fill the figure
    instead of floating inside an equal cube. min_frac keeps flat axes from
    collapsing."""
    pts = np.asarray(pts, float)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    c = 0.5 * (lo + hi)
    span = (hi - lo) * (1.0 + pad)
    span = np.maximum(span, min_frac * span.max())
    for setl, k in ((ax.set_xlim, 0), (ax.set_ylim, 1), (ax.set_zlim, 2)):
        setl(c[k] - span[k] / 2.0, c[k] + span[k] / 2.0)
    ax.set_box_aspect(tuple(span / span.max()))
    return c, 0.5 * float(span.max())
