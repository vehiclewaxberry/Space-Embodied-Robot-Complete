"""A1 layout - three orthographic packaging views with the 12U envelope."""
import numpy as np, trimesh, os, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon
from scipy.spatial import ConvexHull

MESH = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\spacecraft_layout\arm_b601_v1\meshes_b601_gripper"
OUT = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\_work\mode_a_stow_layout_r1"
HX, HY, HZ = 170.25, 113.15, 113.15
Q = np.radians([1.79, -0.54, -0.26, 89.45, -45.65, -1.08])

JOINTS = [("link1", "base_link", (-8.416e-05, 0, 0.08465), (0, 0, 0), (0, 0, 1)),
          ("link2", "link1", (0.020084, 0.031625, 0.05555), (-1.5708, 0, 0), (0, 0, -1)),
          ("link3", "link2", (-0.264, 0, 0), (0, 0, 0), (0, 0, 1)),
          ("link4", "link3", (0.2426, -0.054, -0.001625), (0, 0, 0), (0, 0, 1)),
          ("link5", "link4", (0.078308, -0.0375, -0.03), (-1.5708, 0, 0), (0, 0, 1)),
          ("link6", "link5", (0.023692, 0, 0.04), (0, 1.5708, 0), (0, 0, 1))]
FIXED = [("gripper_link", "link6", (0, 0, 0.15971), (0, -1.5708, 0)),
         ("gripper_left", "gripper_link", (-0.042091, 2.7531e-05, -1.3031e-05), (0, 0, -1.5708)),
         ("gripper_right", "gripper_link", (-0.042091, -2.7531e-05, 1.3031e-05), (0, 0, 1.5708))]


def rpy(r, p, y):
    cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
    return np.array([[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                     [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr], [-sp, cp*sr, cp*cr]])


def Tm(x, r):
    M = np.eye(4); M[:3, :3] = r; M[:3, 3] = x; return M


def arot(a, q):
    a = np.asarray(a, float); a = a/np.linalg.norm(a)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3)+np.sin(q)*K+(1-np.cos(q))*K@K


Tw = {"base_link": np.eye(4)}
for i, (c, p, x, rr, ax) in enumerate(JOINTS):
    Tw[c] = Tw[p] @ (Tm(x, rpy(*rr)) @ Tm((0, 0, 0), arot(ax, Q[i])))
for c, p, x, rr in FIXED:
    Tw[c] = Tw[p] @ Tm(x, rpy(*rr))

links = {}
for f in sorted(os.listdir(MESH)):
    if f.lower().endswith(".stl"):
        n = f[:-4]
        m = trimesh.load_mesh(os.path.join(MESH, f), process=False)
        links[n] = np.asarray(m.convex_hull.vertices, float)*1000.0 @ Tw[n][:3, :3].T + Tw[n][:3, 3]*1000.0

ALL = np.vstack(list(links.values()))
hull = trimesh.convex.convex_hull(trimesh.PointCloud(ALL))
T, ext = trimesh.bounds.oriented_bounds(hull)
order = np.argsort(ext)[::-1]; P = np.eye(3)[order]
links = {k: (v @ T[:3, :3].T + T[:3, 3]) @ P.T for k, v in links.items()}
A = np.vstack(list(links.values())); ctr = (A.max(0)+A.min(0))/2
links = {k: v-ctr for k, v in links.items()}

ORDER = ["base_link", "link1", "link2", "link3", "link4", "link5", "link6",
         "gripper_link", "gripper_left", "gripper_right"]
CM = plt.get_cmap("tab10")
VIEWS = [((0, 1), "X (bus long axis)", "Y", HX, HY, "俯视 XY"),
         ((0, 2), "X (bus long axis)", "Z", HX, HZ, "侧视 XZ"),
         ((1, 2), "Y", "Z", HY, HZ, "端视 YZ (沿长轴看)")]

fig, axes = plt.subplots(1, 3, figsize=(21, 6.6))
for ax, ((i, j), xl, yl, hx, hy, ttl) in zip(axes, VIEWS):
    for k, n in enumerate(ORDER):
        p = links[n][:, [i, j]]
        try:
            h = ConvexHull(p)
            ax.add_patch(Polygon(p[h.vertices], closed=True, fc=CM(k % 10),
                                 ec=CM(k % 10), alpha=0.45, lw=1.4, zorder=2, label=n))
        except Exception:
            pass
    ax.add_patch(Rectangle((-hx, -hy), 2*hx, 2*hy, fill=False, ec="k", lw=2.6, zorder=5))
    for lim, c, ls, lab in [(6.55, "tab:orange", "--", "CDS +6.55"),
                            (9.50, "tab:red", ":", "NanoRacks +9.50")]:
        ax.add_patch(Rectangle((-hx-lim, -hy-lim), 2*(hx+lim), 2*(hy+lim),
                               fill=False, ec=c, lw=1.5, ls=ls, zorder=5, label=lab))
    ax.set_aspect("equal"); ax.grid(alpha=.25, zorder=0)
    ax.set_xlabel(xl+" [mm]"); ax.set_ylabel(yl+" [mm]"); ax.set_title(ttl, fontsize=12)
    m = 55
    ax.set_xlim(-hx-m, hx+m); ax.set_ylim(-hy-m, hy+m)

h, l = axes[0].get_legend_handles_labels()
seen, hh, ll = set(), [], []
for a, b in zip(h, l):
    if b not in seen:
        seen.add(b); hh.append(a); ll.append(b)
fig.legend(hh, ll, loc="lower center", ncol=7, fontsize=9, frameon=False)
fig.suptitle("A1  B601 stowed at q_stow inside the 12U envelope  (project S frame, mm)",
             fontsize=14)
fig.tight_layout(rect=[0, 0.07, 1, 0.96])
p1 = os.path.join(OUT, "A1_STOW_LAYOUT_VIEWS_R1.png")
fig.savefig(p1, dpi=110); print("wrote", p1)
