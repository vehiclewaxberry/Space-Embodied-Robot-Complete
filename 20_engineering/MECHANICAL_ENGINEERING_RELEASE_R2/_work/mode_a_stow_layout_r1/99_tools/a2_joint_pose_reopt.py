"""A2 - Mode A joint + mount-clocking re-optimisation.

A1 left three protrusions (X +10.4 / Y +10.4 / Z +2.3 on the min-volume OBB).
A1 only optimised q against a *min-volume* OBB. This solves the actual question:

    minimise  max_axis( extent_axis/2 - half_axis )
    over      q1..q6 (URDF limits)  and  mount rotation R (3 params)

Rigid translation is analytically optimal (centre the cloud per axis), so it is
not a decision variable. Box axes are the project S frame: X is the 340.5 mm
long axis, Y and Z are the 226.3 mm faces.

Reference geometry only. Convex hulls of the accepted-URDF STLs -> conservative
(true links are non-convex, so the real envelope is no larger than this).
Bounding-box level, NOT an interference check.
"""
import numpy as np, trimesh, os, json, itertools
from scipy.optimize import minimize
from scipy.spatial import ConvexHull

MESH = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\spacecraft_layout\arm_b601_v1\meshes_b601_gripper"
OUT = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\_work\mode_a_stow_layout_r1"

HALF = np.array([170.25, 113.15, 113.15])      # 12U nominal half-extents, S frame
CDS_ALLOW, NR_ALLOW = 6.55, 9.50               # per-face protrusion, measured from OreSat keepouts

JOINTS = [  # child, parent, origin xyz(m), origin rpy, axis, lower, upper
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
LO = np.array([j[5] for j in JOINTS]); HI = np.array([j[6] for j in JOINTS])


def rpy(r, p, y):
    cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(p), np.sin(p), np.cos(y), np.sin(y)
    return np.array([[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr],
                     [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr], [-sp, cp*sr, cp*cr]])


def Tm(x, R):
    M = np.eye(4); M[:3, :3] = R; M[:3, 3] = x; return M


def arot(a, q):
    a = np.asarray(a, float); a = a/np.linalg.norm(a)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) + np.sin(q)*K + (1-np.cos(q))*K@K


def rotvec(v):
    th = np.linalg.norm(v)
    if th < 1e-12:
        return np.eye(3)
    return arot(v/th, th)


# ---- per-link convex hull vertices, mm, in link frame ----
H = {}
for f in sorted(os.listdir(MESH)):
    if f.lower().endswith(".stl"):
        m = trimesh.load_mesh(os.path.join(MESH, f), process=False)
        H[f[:-4]] = np.asarray(m.convex_hull.vertices, float) * 1000.0
NAMES = list(H)
print(f"links={len(NAMES)}  hull_points={sum(len(v) for v in H.values())}")


def cloud(q):
    """Arm hull points in base_link frame, mm."""
    Tw = {"base_link": np.eye(4)}
    for i, (c, p, x, rr, ax, a, b) in enumerate(JOINTS):
        Tw[c] = Tw[p] @ (Tm(x, rpy(*rr)) @ Tm((0, 0, 0), arot(ax, q[i])))
    for c, p, x, rr in FIXED:
        Tw[c] = Tw[p] @ Tm(x, rpy(*rr))
    return np.vstack([H[n] @ Tw[n][:3, :3].T + Tw[n][:3, 3]*1000.0 for n in NAMES]), Tw


def extents(P):
    return P.max(0) - P.min(0)


def excess_of(x):
    """x = [q1..q6, rx, ry, rz]; returns (max_excess, per-axis excess, extents, R)."""
    q = np.clip(x[:6], LO, HI)
    R = rotvec(x[6:9])
    P, _ = cloud(q)
    e = extents(P @ R.T)
    ex = e/2.0 - HALF
    return float(ex.max()), ex, e, R, q


def obj(x):
    q = x[:6]
    pen = 1e4*float(np.sum(np.abs(q - np.clip(q, LO, HI))))
    return excess_of(x)[0] + pen


# ---- seeds ----
rng = np.random.default_rng(20260904)
seeds = []
Q_A1 = np.radians([1.79, -0.54, -0.26, 89.45, -45.65, -1.08])
for rv in [np.zeros(3), np.array([np.pi/2, 0, 0]), np.array([0, np.pi/2, 0]), np.array([0, 0, np.pi/2]),
           np.radians([25, 0, 0]), np.radians([-25, 0, 0]), np.radians([45, 45, 0])]:
    seeds.append(np.concatenate([Q_A1, rv]))
    seeds.append(np.concatenate([np.zeros(6), rv]))
for a, b, c, d in itertools.product([0.0, -1.05, -2.09, -3.14], [0.0, -1.05, -2.09, -3.14],
                                    [-1.87, 0.0, 1.57], [-1.57, 0.0, 1.57]):
    seeds.append(np.concatenate([[0.0, a, b, c, d, 0.0], np.zeros(3)]))
for _ in range(400):
    seeds.append(np.concatenate([LO + (HI-LO)*rng.random(6), rng.normal(0, 1.2, 3)]))
print(f"seeds={len(seeds)}")

scored = sorted(((obj(s), s) for s in seeds), key=lambda t: t[0])
print(f"best seed excess = {scored[0][0]:.2f} mm")

best = None
for k, (v0, s) in enumerate(scored[:24]):
    r = minimize(obj, s, method="Nelder-Mead",
                 options=dict(maxiter=8000, maxfev=8000, xatol=1e-5, fatol=1e-5))
    v, ex, e, R, q = excess_of(r.x)
    if best is None or v < best[0]:
        best = (v, ex, e, R, q, r.x)
        print(f"  seed{k:02d} -> excess {v:+.3f} mm   ext {e[0]:.1f} x {e[1]:.1f} x {e[2]:.1f}")

v, ex, e, R, q, xstar = best
P, Tw = cloud(q)
Pb = P @ R.T
ctr = (Pb.max(0) + Pb.min(0))/2
Pb = Pb - ctr
base_origin = (np.array([0.0, 0, 0]) @ R.T) - ctr           # base_link origin in box frame
tip = (Tw["gripper_link"][:3, 3]*1000.0) @ R.T - ctr

print("\n" + "="*78)
print("A2  JOINT + MOUNT-CLOCKING RE-OPTIMISATION  (fit stowed B601 into 12U)")
print("="*78)
print(f"  q_stow (deg)   = [{', '.join(f'{np.degrees(t):+8.3f}' for t in q)}]")
print(f"  in-limit       = {bool(np.all(q >= LO-1e-9) and np.all(q <= HI+1e-9))}")
print(f"  mount rotvec   = [{', '.join(f'{t:+.5f}' for t in xstar[6:9])}] rad "
      f"(angle {np.degrees(np.linalg.norm(xstar[6:9])):.2f} deg)")
print(f"  extents        = {e[0]:8.2f} x {e[1]:8.2f} x {e[2]:8.2f} mm")
print(f"  12U box        = {2*HALF[0]:8.2f} x {2*HALF[1]:8.2f} x {2*HALF[2]:8.2f} mm")
print(f"  excess / face  = X {ex[0]:+7.2f}   Y {ex[1]:+7.2f}   Z {ex[2]:+7.2f} mm")
print(f"  worst excess   = {v:+.2f} mm")
print()
print(f"  fits 12U nominal (0 mm)        : {v <= 0}")
print(f"  fits CDS      (+{CDS_ALLOW} mm/face) : {bool(np.all(ex <= CDS_ALLOW))}")
print(f"  fits NanoRacks(+{NR_ALLOW} mm/face) : {bool(np.all(ex <= NR_ALLOW))}")
print()
print(f"  base_link origin in box  = [{base_origin[0]:+8.2f}, {base_origin[1]:+8.2f}, {base_origin[2]:+8.2f}] mm")
print(f"  gripper_link origin      = [{tip[0]:+8.2f}, {tip[1]:+8.2f}, {tip[2]:+8.2f}] mm")
print("="*78)
print("\n  A1 baseline for comparison: 361.26 x 247.12 x 230.95, excess +10.38/+10.41/+2.32")
print(f"  A2 improvement            : {361.26-e[0]:+.2f} / {247.12-e[1]:+.2f} / {230.95-e[2]:+.2f} mm on extents")

json.dump(dict(q_stow_deg=np.degrees(q).tolist(), mount_rotvec_rad=xstar[6:9].tolist(),
               mount_angle_deg=float(np.degrees(np.linalg.norm(xstar[6:9]))),
               extents_mm=e.tolist(), box_mm=(2*HALF).tolist(),
               excess_per_face_mm=ex.tolist(), worst_excess_mm=v,
               fits_nominal=bool(v <= 0), fits_cds=bool(np.all(ex <= CDS_ALLOW)),
               fits_nanoracks=bool(np.all(ex <= NR_ALLOW)),
               base_link_origin_in_box_mm=base_origin.tolist(),
               method="convex-hull / AABB after free rotation, translation analytically centred; NOT an interference check"),
          open(os.path.join(OUT, "A2_JOINT_REOPT_R1.json"), "w"), indent=1)
print("\nwrote", os.path.join(OUT, "A2_JOINT_REOPT_R1.json"))
