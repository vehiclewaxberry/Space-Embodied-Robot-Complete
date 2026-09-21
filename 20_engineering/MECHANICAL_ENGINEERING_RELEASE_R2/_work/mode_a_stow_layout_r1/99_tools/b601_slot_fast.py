"""B601 stowed-slot feasibility, fast version.

Long axis = PCA principal component of the hull (near-optimal for a folded
slender arm); rotation about it sampled at 24 angles. Objective = minimise
cross-section area subject to length <= 340.5 mm (12U long axis).
"""
import numpy as np, trimesh, os, itertools, json, sys
from scipy.optimize import minimize
from scipy.spatial import ConvexHull

MESH = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\spacecraft_layout\arm_b601_v1\meshes_b601_gripper"
LMAX, UVOL = 340.5, 100.0 * 100.0 * 113.5
FACE = 226.3

JOINTS = [
    ("link1", "base_link", (-8.416e-05, 0, 0.08465), (0, 0, 0), (0, 0, 1), -2.8, 2.8),
    ("link2", "link1", (0.020084, 0.031625, 0.05555), (-1.5708, 0, 0), (0, 0, -1), -3.14, 0.0),
    ("link3", "link2", (-0.264, 0, 0), (0, 0, 0), (0, 0, 1), -3.14, 0.0),
    ("link4", "link3", (0.2426, -0.054, -0.001625), (0, 0, 0), (0, 0, 1), -1.87, 1.57),
    ("link5", "link4", (0.078308, -0.0375, -0.03), (-1.5708, 0, 0), (0, 0, 1), -1.57, 1.57),
    ("link6", "link5", (0.023692, 0, 0.04), (0, 1.5708, 0), (0, 0, 1), -3.14, 3.14),
]
FIXED = [("gripper_link", "link6", (0, 0, 0.15971), (0, -1.5708, 0)),
         ("gripper_left", "gripper_link", (-0.042091, 2.7531e-05, -1.3031e-05), (0, 0, -1.5708)),
         ("gripper_right", "gripper_link", (-0.042091, -2.7531e-05, 1.3031e-05), (0, 0, 1.5708))]
lo = np.array([j[5] for j in JOINTS]); hi = np.array([j[6] for j in JOINTS])


def rpy(r, p, y):
    cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
    return np.array([[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                     [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr], [-sp, cp*sr, cp*cr]])


def Tm(xyz, r):
    M = np.eye(4); M[:3, :3] = r; M[:3, 3] = xyz; return M


def arot(a, q):
    a = np.asarray(a, float); a = a/np.linalg.norm(a)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(q)*K + (1-np.cos(q))*K@K


H = {}
for f in os.listdir(MESH):
    if f.lower().endswith(".stl"):
        m = trimesh.load_mesh(os.path.join(MESH, f), process=False)
        V = np.asarray(m.convex_hull.vertices, float)*1000.0
        H[f[:-4]] = V
NAMES = list(H)
ANG = np.linspace(0, np.pi/2, 24, endpoint=False)


def hullpts(q):
    Tw = {"base_link": np.eye(4)}
    for i, (c, p, xyz, rr, ax, a, b) in enumerate(JOINTS):
        Tw[c] = Tw[p] @ (Tm(xyz, rpy(*rr)) @ Tm((0, 0, 0), arot(ax, q[i])))
    for c, p, xyz, rr in FIXED:
        Tw[c] = Tw[p] @ Tm(xyz, rpy(*rr))
    P = np.vstack([H[n] @ Tw[n][:3, :3].T + Tw[n][:3, 3]*1000.0 for n in NAMES])
    try:
        return P[ConvexHull(P).vertices]
    except Exception:
        return P


def slot(q):
    P = hullpts(q); P = P - P.mean(0)
    n = np.linalg.svd(P, full_matrices=False)[2][0]
    pr = P @ n; L = float(pr.max() - pr.min())
    a = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(n, a); u /= np.linalg.norm(u); v = np.cross(n, u)
    X = P @ u; Y = P @ v
    c, s = np.cos(ANG), np.sin(ANG)
    xs = np.outer(c, X) + np.outer(s, Y)
    ys = -np.outer(s, X) + np.outer(c, Y)
    w1 = xs.max(1) - xs.min(1); w2 = ys.max(1) - ys.min(1)
    k = int(np.argmin(w1*w2))
    return L, float(max(w1[k], w2[k])), float(min(w1[k], w2[k]))


def obj(q):
    qc = np.clip(q, lo, hi)
    L, a, b = slot(qc)
    return max(0.0, L-LMAX)*1e3 + a*b + 1e4*float(np.sum(np.abs(q-qc)))


rng = np.random.default_rng(20260902)
seeds = [np.zeros(6)]
for a, b, c in itertools.product([0.0, -1.05, -2.09, -3.14], [0.0, -1.05, -2.09, -3.14],
                                 [-1.87, -0.9, 0.0, 0.9, 1.57]):
    seeds.append(np.array([0.0, a, b, c, 0.0, 0.0]))
    seeds.append(np.array([0.0, a, b, c, -1.57, 0.0]))
    seeds.append(np.array([0.0, a, b, c, 1.57, 0.0]))
for _ in range(90):
    seeds.append(lo + (hi-lo)*rng.random(6))
print(f"seeds={len(seeds)}", flush=True)
sc = sorted(((obj(s), s) for s in seeds), key=lambda t: t[0])
print(f"best seed obj={sc[0][0]:.0f}", flush=True)

best = None
for k, (v0, s) in enumerate(sc[:8]):
    r = minimize(obj, s, method="Nelder-Mead", options=dict(maxiter=600, xatol=2e-3, fatol=5.0))
    qb = np.clip(r.x, lo, hi); L, a, b = slot(qb)
    key = max(0.0, L-LMAX)*1e3 + a*b
    print(f"  refine {k}: L={L:.1f} sec={a:.1f}x{b:.1f}", flush=True)
    if best is None or key < best[0]:
        best = (key, qb, L, a, b)

_, q, L, a, b = best
U = L*a*b/UVOL
print("\n" + "="*72)
print("B601 MINIMUM STOWED SLOT (must share the 12U with the bus)")
print("="*72)
print(f"  q_stow deg   = [{', '.join(f'{np.degrees(x):+7.2f}' for x in q)}]")
print(f"  length       = {L:8.1f} mm   (12U long axis {LMAX})   fits={L<=LMAX}")
print(f"  cross-section= {a:8.1f} x {b:.1f} mm   (12U face {FACE} x {FACE})")
print(f"  slot volume  = {L*a*b/1e3:8.1f} cm3  = {U:.2f} U   -> leaves {12-U:.2f} U")
print(f"  section fits in 12U face = {a<=FACE and b<=FACE}")
print("="*72)
json.dump(dict(q_deg=np.degrees(q).tolist(), L_mm=L, w_mm=[a, b], U=U),
          open(r"C:\Users\stude\AppData\Local\Temp\b601_stow_slot.json", "w"), indent=1)
