"""A1 corrected occupancy map - true cross-sections, not hull vertices.

The first pass binned hull VERTICES, so mid-span slices of the long links
reported empty. This version sections the actual convex-hull solids.
"""
import numpy as np, trimesh, os, json, matplotlib
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

raw = {}
for f in sorted(os.listdir(MESH)):
    if f.lower().endswith(".stl"):
        n = f[:-4]
        m = trimesh.load_mesh(os.path.join(MESH, f), process=False)
        raw[n] = np.asarray(m.convex_hull.vertices, float)*1000.0 @ Tw[n][:3, :3].T + Tw[n][:3, 3]*1000.0

ALL = np.vstack(list(raw.values()))
T, ext = trimesh.bounds.oriented_bounds(trimesh.convex.convex_hull(trimesh.PointCloud(ALL)))
order = np.argsort(ext)[::-1]; P = np.eye(3)[order]
pts = {k: (v @ T[:3, :3].T + T[:3, 3]) @ P.T for k, v in raw.items()}
A = np.vstack(list(pts.values())); ctr = (A.max(0)+A.min(0))/2
pts = {k: v-ctr for k, v in pts.items()}

# rebuild watertight convex hull meshes in the box frame
solids = {k: trimesh.convex.convex_hull(trimesh.PointCloud(v)) for k, v in pts.items()}

NS = 28
edges = np.linspace(-HX-11, HX+11, NS+1)
rows = []
for i in range(NS):
    xc = 0.5*(edges[i]+edges[i+1])
    ys, zs = [], []
    for k, s in solids.items():
        try:
            sec = s.section(plane_origin=[xc, 0, 0], plane_normal=[1, 0, 0])
            if sec is None:
                continue
            V = np.asarray(sec.vertices)
            ys += [V[:, 1].min(), V[:, 1].max()]
            zs += [V[:, 2].min(), V[:, 2].max()]
        except Exception:
            pass
    if not ys:
        rows.append((edges[i], edges[i+1], 0.0, 0.0, 0.0, 0.0)); continue
    rows.append((edges[i], edges[i+1], min(ys), max(ys), min(zs), max(zs)))

print("="*92)
print("A1 CORRECTED OCCUPANCY  (true cross-sections of the stowed arm, S frame, mm)")
print("="*92)
print(f"  12U: x +/-{HX}, y +/-{HY}, z +/-{HZ}")
print(f"  {'x_lo':>7s} {'x_hi':>7s} | {'y_min':>7s} {'y_max':>7s} {'dY':>6s} | "
      f"{'z_min':>7s} {'z_max':>7s} {'dZ':>6s} | bbox-free%  flags")
worst = {}
for a, b, y0, y1, z0, z1 in rows:
    dy, dz = y1-y0, z1-z0
    free = 100.0*(1 - (dy*dz)/(2*HY*2*HZ)) if dy > 0 else 100.0
    fl = []
    if y1 > HY: fl.append(f"+Y {y1-HY:+.1f}")
    if y0 < -HY: fl.append(f"-Y {-HY-y0:+.1f}")
    if z1 > HZ: fl.append(f"+Z {z1-HZ:+.1f}")
    if z0 < -HZ: fl.append(f"-Z {-HZ-z0:+.1f}")
    if a < -HX or b > HX: fl.append("OUT-X")
    print(f"  {a:7.1f} {b:7.1f} | {y0:7.1f} {y1:7.1f} {dy:6.1f} | "
          f"{z0:7.1f} {z1:7.1f} {dz:6.1f} | {free:8.1f}%  {' '.join(fl)}")
print("="*92)

occ = [r for r in rows if r[3]-r[2] > 0]
xmin = min(r[0] for r in occ); xmax = max(r[1] for r in occ)
print(f"  arm occupies x in [{xmin:.1f}, {xmax:.1f}]  -> spans {xmax-xmin:.1f} mm of the {2*HX:.1f} mm bus")
print(f"  contiguous EMPTY x-bands: ", [(round(r[0],1),round(r[1],1)) for r in rows if r[3]-r[2]==0])
json.dump([list(map(float, r)) for r in rows],
          open(os.path.join(OUT, "A1_OCCUPANCY_R2.json"), "w"), indent=1)

# ---- redraw with English labels ----
ORDER = ["base_link","link1","link2","link3","link4","link5","link6",
         "gripper_link","gripper_left","gripper_right"]
CM = plt.get_cmap("tab10")
VIEWS = [((0,1),"X (bus long axis)","Y",HX,HY,"TOP  XY"),
         ((0,2),"X (bus long axis)","Z",HX,HZ,"SIDE  XZ"),
         ((1,2),"Y","Z",HY,HZ,"END  YZ (down the long axis)")]
fig, axes = plt.subplots(1,3, figsize=(21,6.6))
for ax, ((i,j),xl,yl,hx,hy,ttl) in zip(axes, VIEWS):
    for k,n in enumerate(ORDER):
        p = pts[n][:,[i,j]]
        h = ConvexHull(p)
        ax.add_patch(Polygon(p[h.vertices], closed=True, fc=CM(k%10), ec=CM(k%10),
                             alpha=0.45, lw=1.4, zorder=2, label=n))
    ax.add_patch(Rectangle((-hx,-hy),2*hx,2*hy, fill=False, ec="k", lw=2.6, zorder=5))
    for lim,c,ls,lab in [(6.55,"tab:orange","--","CDS +6.55"),(9.50,"tab:red",":","NanoRacks +9.50")]:
        ax.add_patch(Rectangle((-hx-lim,-hy-lim),2*(hx+lim),2*(hy+lim), fill=False,
                               ec=c, lw=1.5, ls=ls, zorder=5, label=lab))
    ax.set_aspect("equal"); ax.grid(alpha=.25, zorder=0)
    ax.set_xlabel(xl+" [mm]"); ax.set_ylabel(yl+" [mm]"); ax.set_title(ttl, fontsize=12)
    ax.set_xlim(-hx-55, hx+55); ax.set_ylim(-hy-55, hy+55)
h,l = axes[0].get_legend_handles_labels()
seen,hh,ll = set(),[],[]
for a,b in zip(h,l):
    if b not in seen: seen.add(b); hh.append(a); ll.append(b)
fig.legend(hh,ll, loc="lower center", ncol=7, fontsize=9, frameon=False)
fig.suptitle("A1  B601 stowed at q_stow inside the 12U envelope (project S frame, mm)", fontsize=14)
fig.tight_layout(rect=[0,0.07,1,0.96])
p2 = os.path.join(OUT,"A1_STOW_LAYOUT_VIEWS_R2.png"); fig.savefig(p2, dpi=110)
print("wrote", p2)
