"""A2b - exactness check + "what has to give" subset study.

(1) Verify that the convex-hull AABB equals the full-mesh AABB.
    The support function of a point set equals that of its convex hull, so the
    axis-aligned extents are EXACT, not conservative. This corrects an earlier
    claim that hull-based numbers over-estimate the envelope.

(2) Re-run the A2 minimax fit for progressively reduced link sets, to show what
    would have to change for the stowed arm to clear a 12U.
"""
import numpy as np, trimesh, os, json, itertools
from scipy.optimize import minimize

MESH = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\spacecraft_layout\arm_b601_v1\meshes_b601_gripper"
OUT = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\_work\mode_a_stow_layout_r1"
HALF = np.array([170.25, 113.15, 113.15])
CDS, NR = 6.55, 9.50

JOINTS = [("link1", "base_link", (-8.416e-05, 0, 0.08465), (0, 0, 0), (0, 0, 1), -2.8, 2.8),
          ("link2", "link1", (0.020084, 0.031625, 0.05555), (-1.5708, 0, 0), (0, 0, -1), -3.14, 0.0),
          ("link3", "link2", (-0.264, 0, 0), (0, 0, 0), (0, 0, 1), -3.14, 0.0),
          ("link4", "link3", (0.2426, -0.054, -0.001625), (0, 0, 0), (0, 0, 1), -1.87, 1.57),
          ("link5", "link4", (0.078308, -0.0375, -0.03), (-1.5708, 0, 0), (0, 0, 1), -1.57, 1.57),
          ("link6", "link5", (0.023692, 0, 0.04), (0, 1.5708, 0), (0, 0, 1), -3.14, 3.14)]
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
    return np.eye(3) if th < 1e-12 else arot(v/th, th)


HULL, FULL = {}, {}
for f in sorted(os.listdir(MESH)):
    if f.lower().endswith(".stl"):
        m = trimesh.load_mesh(os.path.join(MESH, f), process=False)
        HULL[f[:-4]] = np.asarray(m.convex_hull.vertices, float)*1000.0
        FULL[f[:-4]] = np.asarray(m.vertices, float)*1000.0
print("link            hull_v     full_v")
for n in HULL:
    print(f"  {n:14s} {len(HULL[n]):6d} {len(FULL[n]):10d}")


def fk(q):
    Tw = {"base_link": np.eye(4)}
    for i, (c, p, x, rr, ax, a, b) in enumerate(JOINTS):
        Tw[c] = Tw[p] @ (Tm(x, rpy(*rr)) @ Tm((0, 0, 0), arot(ax, q[i])))
    for c, p, x, rr in FIXED:
        Tw[c] = Tw[p] @ Tm(x, rpy(*rr))
    return Tw


def cloud(q, src, names):
    Tw = fk(q)
    return np.vstack([src[n] @ Tw[n][:3, :3].T + Tw[n][:3, 3]*1000.0 for n in names])


ALL = list(HULL)
SETS = {
    "full arm + gripper + fingers": ALL,
    "arm + gripper_link (no fingers)": [n for n in ALL if not n.startswith("gripper_") or n == "gripper_link"],
    "arm only (base..link6)": [n for n in ALL if not n.startswith("gripper")],
    "links1-6 (base_link recessed/removed)": [n for n in ALL if not n.startswith("gripper") and n != "base_link"],
}

# ---------- (1) exactness ----------
q_a2 = np.radians([0.825, -0.336, -0.249, 89.954, -55.631, -2.715])
R_a2 = rotvec(np.array([0.20713, -0.00716, 0.00145]))
Ph = cloud(q_a2, HULL, ALL) @ R_a2.T
Pf = cloud(q_a2, FULL, ALL) @ R_a2.T
eh, ef = Ph.max(0)-Ph.min(0), Pf.max(0)-Pf.min(0)
print("\n" + "="*74)
print("(1) HULL vs FULL MESH extents at the A2 optimum")
print("="*74)
print(f"  convex-hull AABB : {eh[0]:9.4f} {eh[1]:9.4f} {eh[2]:9.4f} mm")
print(f"  full-mesh   AABB : {ef[0]:9.4f} {ef[1]:9.4f} {ef[2]:9.4f} mm")
print(f"  difference       : {eh[0]-ef[0]:+9.6f} {eh[1]-ef[1]:+9.6f} {eh[2]-ef[2]:+9.6f} mm")
print("  -> AABB extents of a point set equal those of its convex hull;")
print("     the hull is NOT conservative for bounding-box extents.")

# ---------- (2) subsets ----------
rng = np.random.default_rng(20260904)
Q_A1 = np.radians([1.79, -0.54, -0.26, 89.45, -45.65, -1.08])


def solve(names, nseed=320, npolish=14):
    src = HULL

    def exc(x):
        q = np.clip(x[:6], LO, HI)
        P = cloud(q, src, names) @ rotvec(x[6:9]).T
        e = P.max(0) - P.min(0)
        return float((e/2 - HALF).max()), e, q

    def obj(x):
        return exc(x)[0] + 1e4*float(np.sum(np.abs(x[:6] - np.clip(x[:6], LO, HI))))

    S = [np.concatenate([Q_A1, np.zeros(3)]), np.concatenate([q_a2, np.array([0.20713, -0.00716, 0.00145])]),
         np.zeros(9)]
    for a, b, c in itertools.product([0.0, -1.05, -2.09, -3.14], [0.0, -1.05, -2.09, -3.14], [-1.87, 0.0, 1.57]):
        S.append(np.concatenate([[0.0, a, b, c, 0.0, 0.0], np.zeros(3)]))
    for _ in range(nseed):
        S.append(np.concatenate([LO + (HI-LO)*rng.random(6), rng.normal(0, 1.2, 3)]))
    S = sorted(S, key=obj)[:npolish]
    best = None
    for s in S:
        r = minimize(obj, s, method="Nelder-Mead", options=dict(maxiter=6000, maxfev=6000, xatol=1e-5, fatol=1e-5))
        v, e, q = exc(r.x)
        if best is None or v < best[0]:
            best = (v, e, q, r.x)
    return best


print("\n" + "="*98)
print("(2) MINIMAX FIT BY LINK SET   (box 340.5 x 226.3 x 226.3; excess is per face, all 3 axes)")
print("="*98)
print(f"  {'link set':<40} {'extents (mm)':>26} {'excess':>9}  {'nominal':>8} {'CDS':>5} {'NR':>4}")
rows = []
for label, names in SETS.items():
    v, e, q, x = solve(names)
    rows.append(dict(set=label, links=names, extents_mm=e.tolist(), worst_excess_mm=v,
                     q_deg=np.degrees(q).tolist(), mount_rotvec=x[6:9].tolist()))
    print(f"  {label:<40} {e[0]:7.1f} x{e[1]:7.1f} x{e[2]:7.1f} {v:+9.2f}  "
          f"{'YES' if v <= 0 else 'no':>8} {'YES' if v <= CDS else 'no':>5} {'YES' if v <= NR else 'no':>4}")
print("="*98)

json.dump(dict(exactness=dict(hull_extents_mm=eh.tolist(), full_mesh_extents_mm=ef.tolist(),
                              max_abs_difference_mm=float(np.abs(eh-ef).max()),
                              conclusion="AABB extents from convex hull are exact, not conservative"),
               subsets=rows,
               box_mm=(2*HALF).tolist(), cds_allow_mm=CDS, nanoracks_allow_mm=NR),
          open(os.path.join(OUT, "A2B_EXACTNESS_AND_SUBSETS_R1.json"), "w"), indent=1)
print("\nwrote", os.path.join(OUT, "A2B_EXACTNESS_AND_SUBSETS_R1.json"))
