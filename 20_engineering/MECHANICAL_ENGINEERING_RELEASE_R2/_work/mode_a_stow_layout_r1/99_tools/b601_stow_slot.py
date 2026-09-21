"""B601 stowed SLOT feasibility for Mode A.

Right question for a 12U: the arm must share the 226.3 x 226.3 x 340.5 volume
with the bus. So minimise the arm's CROSS-SECTION subject to its length fitting
the 340.5 mm long axis -> "how many U does the stowed arm eat".

Objective: min (d2 * d3) s.t. d1 <= 340.5, over the 6 revolute joints.
d1>=d2>=d3 are the extents of a bounding box in the best orientation.
Orientation is searched explicitly (not min-volume OBB, which optimises the
wrong thing here).
"""
import numpy as np, trimesh, os, itertools, json
from scipy.optimize import minimize
from scipy.spatial import ConvexHull

BASE = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\spacecraft_layout\arm_b601_v1"
MESH = os.path.join(BASE, "meshes_b601_gripper")
LMAX = 340.5   # 12U long axis
UVOL = 100.0 * 100.0 * 113.5  # 1U in mm^3

JOINTS = [
    ("link1", "base_link", (-8.416e-05, 0, 0.08465), (0, 0, 0), (0, 0, 1), -2.8, 2.8),
    ("link2", "link1", (0.020084, 0.031625, 0.05555), (-1.5708, 0, 0), (0, 0, -1), -3.14, 0.0),
    ("link3", "link2", (-0.264, 0, 0), (0, 0, 0), (0, 0, 1), -3.14, 0.0),
    ("link4", "link3", (0.2426, -0.054, -0.001625), (0, 0, 0), (0, 0, 1), -1.87, 1.57),
    ("link5", "link4", (0.078308, -0.0375, -0.03), (-1.5708, 0, 0), (0, 0, 1), -1.57, 1.57),
    ("link6", "link5", (0.023692, 0, 0.04), (0, 1.5708, 0), (0, 0, 1), -3.14, 3.14),
]
FIXED = [
    ("gripper_link", "link6", (0, 0, 0.15971), (0, -1.5708, 0)),
    ("gripper_left", "gripper_link", (-0.042091, 2.7531e-05, -1.3031e-05), (0, 0, -1.5708)),
    ("gripper_right", "gripper_link", (-0.042091, -2.7531e-05, 1.3031e-05), (0, 0, 1.5708)),
]
lo = np.array([j[5] for j in JOINTS]); hi = np.array([j[6] for j in JOINTS])


def rpy(r, p, y):
    cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
    return np.array([[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                     [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr],
                     [-sp, cp*sr, cp*cr]])


def T(xyz, r):
    M = np.eye(4); M[:3, :3] = r; M[:3, 3] = xyz; return M


def axis_rot(axis, q):
    a = np.asarray(axis, float); a = a/np.linalg.norm(a)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(q)*K + (1-np.cos(q))*K @ K


HULL = {}
for f in os.listdir(MESH):
    if f.lower().endswith(".stl"):
        m = trimesh.load_mesh(os.path.join(MESH, f), process=False)
        HULL[f[:-4]] = np.asarray(m.convex_hull.vertices, float) * 1000.0  # mm


def cloud(q):
    Tw = {"base_link": np.eye(4)}
    for i, (c, p, xyz, rr, ax, a, b) in enumerate(JOINTS):
        Tw[c] = Tw[p] @ (T(xyz, rpy(*rr)) @ T((0, 0, 0), axis_rot(ax, q[i])))
    for c, p, xyz, rr in FIXED:
        Tw[c] = Tw[p] @ T(xyz, rpy(*rr))
    return np.vstack([HULL[n] @ (Tw[n][:3, :3]).T + Tw[n][:3, 3]*1000.0 for n in HULL])


def hull_pts(q):
    P = cloud(q)
    try:
        return P[ConvexHull(P).vertices]
    except Exception:
        return P


def _sec(P, ang, axis_dir):
    """cross-section area of P projected perpendicular to axis_dir, rotated by ang."""
    n = axis_dir/np.linalg.norm(axis_dir)
    a = np.array([1.0, 0, 0])
    if abs(n @ a) > 0.9:
        a = np.array([0, 1.0, 0])
    u = np.cross(n, a); u /= np.linalg.norm(u); v = np.cross(n, u)
    c, s = np.cos(ang), np.sin(ang)
    u2, v2 = c*u + s*v, -s*u + c*v
    x = P @ u2; y = P @ v2
    return (x.max()-x.min()), (y.max()-y.min())


def slot(q):
    """Return (length, w1, w2) for the best long-axis orientation."""
    P = hull_pts(q)
    Pc = P - P.mean(0)
    best = None
    # candidate long axes: PCA principal + a coarse sphere sample
    U, S, Vt = np.linalg.svd(Pc, full_matrices=False)
    cands = [Vt[0]]
    g = 9
    for i in range(g):
        th = np.pi*i/g
        for j in range(2*g):
            ph = np.pi*j/g
            cands.append(np.array([np.sin(th)*np.cos(ph), np.sin(th)*np.sin(ph), np.cos(th)]))
    for n in cands:
        n = n/np.linalg.norm(n)
        proj = Pc @ n
        L = float(proj.max() - proj.min())
        for ang in np.linspace(0, np.pi/2, 12, endpoint=False):
            w1, w2 = _sec(Pc, ang, n)
            key = (max(0.0, L-LMAX)*1e3) + w1*w2
            if best is None or key < best[0]:
                best = (key, L, min(w1, w2), max(w1, w2))
    return best[1], best[3], best[2]   # length, wmax, wmin


def obj(q):
    qc = np.clip(q, lo, hi)
    L, w1, w2 = slot(qc)
    return max(0.0, L-LMAX)*1e3 + w1*w2 + 1e4*float(np.sum(np.abs(q-qc)))


rng = np.random.default_rng(20260902)
seeds = [np.zeros(6)]
for a, b, c, d in itertools.product([0.0, -0.79, -1.57, -2.36, -3.14],
                                    [0.0, -0.79, -1.57, -2.36, -3.14],
                                    [-1.87, -0.9, 0.0, 0.9, 1.57],
                                    [-1.57, 0.0, 1.57]):
    seeds.append(np.array([0.0, a, b, c, d, 0.0]))
for _ in range(150):
    seeds.append(lo + (hi-lo)*rng.random(6))

print(f"evaluating {len(seeds)} seeds ...")
scored = sorted(((obj(s), s) for s in seeds), key=lambda t: t[0])
best = None
for sc, s in scored[:10]:
    r = minimize(obj, s, method="Nelder-Mead",
                 options=dict(maxiter=1500, xatol=1e-3, fatol=1e-2))
    qb = np.clip(r.x, lo, hi)
    L, w1, w2 = slot(qb)
    key = max(0.0, L-LMAX)*1e3 + w1*w2
    if best is None or key < best[0]:
        best = (key, qb, L, w1, w2)

_, q, L, w1, w2 = best
U = (L*w1*w2)/UVOL
print("\n" + "="*70)
print("B601 MINIMUM STOWED SLOT  (share the 12U with the bus)")
print("="*70)
print(f"  q_stow (deg) = [{', '.join(f'{np.degrees(x):+7.2f}' for x in q)}]")
print(f"  slot         = {L:.1f} (length) x {w1:.1f} x {w2:.1f} mm")
print(f"  12U long axis= {LMAX:.1f} mm      length fits = {L <= LMAX}")
print(f"  cross-section= {w1:.1f} x {w2:.1f} mm  (12U face is 226.3 x 226.3)")
print(f"  slot volume  = {L*w1*w2/1e3:.1f} cm3  =  {U:.2f} U  of the 12 U")
print(f"  remaining    = {12-U:.2f} U for bus + payload")
print("="*70)
json.dump(dict(q_deg=np.degrees(q).tolist(), L=L, w1=w1, w2=w2, U=U),
          open(r"C:\Users\stude\AppData\Local\Temp\b601_stow_slot.json", "w"), indent=1)
