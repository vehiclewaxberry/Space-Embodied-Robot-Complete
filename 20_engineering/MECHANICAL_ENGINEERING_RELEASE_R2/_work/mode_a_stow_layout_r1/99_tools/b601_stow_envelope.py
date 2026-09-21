"""B601 stowed-envelope feasibility for Mode A (12U deployer compliant).

Question: what is the smallest box the stowed B601 (with gripper) can occupy,
optimising over the 6 revolute joint angles within their URDF limits?

Method: URDF forward kinematics -> per-link convex hulls -> union hull ->
minimum-volume oriented bounding box (trimesh.bounds.oriented_bounds).
Deterministic seeds + local refinement. No project authority is written.
"""
import numpy as np, trimesh, os, itertools, json
from scipy.optimize import minimize

BASE = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\spacecraft_layout\arm_b601_v1"
MESH = os.path.join(BASE, "meshes_b601_gripper")

# (child_link, parent_link, origin_xyz_m, origin_rpy, axis, lower, upper)
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


def rpy(r, p, y):
    cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
    return np.array([
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr]])


def T(xyz, r):
    M = np.eye(4); M[:3, :3] = r; M[:3, 3] = xyz; return M


def axis_rot(axis, q):
    a = np.asarray(axis, float); a = a / np.linalg.norm(a)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(q) * K + (1 - np.cos(q)) * K @ K


print("loading meshes ...")
HULL = {}
for f in os.listdir(MESH):
    if not f.lower().endswith(".stl"):
        continue
    m = trimesh.load_mesh(os.path.join(MESH, f), process=False)
    h = m.convex_hull
    HULL[f[:-4]] = np.asarray(h.vertices, float)
    print(f"  {f[:-4]:14s} tris={len(m.faces):7d} hull_v={len(h.vertices):4d}")


def fk(q):
    """Return world 4x4 per link (metres)."""
    Tw = {"base_link": np.eye(4)}
    for i, (child, parent, xyz, rr, ax, lo, hi) in enumerate(JOINTS):
        Tj = T(xyz, rpy(*rr)) @ T((0, 0, 0), axis_rot(ax, q[i]))
        Tw[child] = Tw[parent] @ Tj
    for child, parent, xyz, rr in FIXED:
        Tw[child] = Tw[parent] @ T(xyz, rpy(*rr))
    return Tw


def cloud(q):
    Tw = fk(q)
    pts = []
    for name, V in HULL.items():
        M = Tw[name]
        pts.append(V @ M[:3, :3].T + M[:3, 3])
    return np.vstack(pts)


def obb_extents_mm(q):
    P = cloud(q)
    hull = trimesh.convex.convex_hull(trimesh.PointCloud(P))
    _, ext = trimesh.bounds.oriented_bounds(hull)
    return np.sort(np.asarray(ext, float))[::-1] * 1000.0


BOX = np.array([340.5, 226.3, 226.3])  # 12U, sorted desc


def excess(q):
    e = obb_extents_mm(q)
    return float(np.max(e - BOX)), e


def obj(q):
    lo = np.array([j[5] for j in JOINTS]); hi = np.array([j[6] for j in JOINTS])
    qc = np.clip(q, lo, hi)
    pen = 1e4 * float(np.sum(np.abs(q - qc)))
    return excess(qc)[0] + pen


lo = np.array([j[5] for j in JOINTS]); hi = np.array([j[6] for j in JOINTS])

seeds = [np.zeros(6)]
rng = np.random.default_rng(20260902)
# deterministic structured seeds: J2/J3 at fold extremes, wrist swept
for a, b, c, d in itertools.product([0.0, -1.57, -3.14], [0.0, -1.57, -3.14],
                                    [-1.87, 0.0, 1.57], [-1.57, 0.0, 1.57]):
    seeds.append(np.array([0.0, a, b, c, d, 0.0]))
for _ in range(120):
    seeds.append(lo + (hi - lo) * rng.random(6))

print(f"\nevaluating {len(seeds)} seeds ...")
scored = sorted(((obj(s), s) for s in seeds), key=lambda t: t[0])
print(f"  best seed excess = {scored[0][0]:.1f} mm")

best = None
for sc, s in scored[:12]:
    r = minimize(obj, s, method="Nelder-Mead",
                 options=dict(maxiter=2500, xatol=1e-3, fatol=1e-3))
    qb = np.clip(r.x, lo, hi)
    v, e = excess(qb)
    if best is None or v < best[0]:
        best = (v, qb, e)

v, q, e = best
print("\n" + "=" * 66)
print("MINIMUM STOWED ENVELOPE (min-volume OBB over joint limits)")
print("=" * 66)
print(f"  q_stow (rad) = [{', '.join(f'{x:+.4f}' for x in q)}]")
print(f"  q_stow (deg) = [{', '.join(f'{np.degrees(x):+7.2f}' for x in q)}]")
print(f"  OBB extents  = {e[0]:.1f} x {e[1]:.1f} x {e[2]:.1f} mm")
print(f"  12U box      = {BOX[0]:.1f} x {BOX[1]:.1f} x {BOX[2]:.1f} mm")
print(f"  excess       = {e[0]-BOX[0]:+.1f} / {e[1]-BOX[1]:+.1f} / {e[2]-BOX[2]:+.1f} mm")
print(f"  FITS IN 12U  = {v <= 0}")
vol_U = (e[0] * e[1] * e[2]) / (100.0 * 100.0 * 113.5)
print(f"  OBB volume   = {e[0]*e[1]*e[2]/1e3:.1f} cm3  ~= {vol_U:.2f} U (bounding, not solid)")
print("=" * 66)
json.dump(dict(q_stow_rad=q.tolist(), obb_mm=e.tolist(), box_mm=BOX.tolist(),
               excess_mm=(e - BOX).tolist(), fits=bool(v <= 0)),
          open(r"C:\Users\stude\AppData\Local\Temp\b601_stow_result.json", "w"), indent=1)
