"""A3.2b - the corridor number that actually sizes the C1-B bus.

A3.2 showed two extremes:
  FIT      : links1-6 clear the 12U outright (-2.97 mm at 2 deg margin) but the
             cross-section is 220.4 x 220.4 - the arm fills the whole bay.
  CORRIDOR : a 80 mm slab exists, but 238.7 mm wide - 6.18 mm outside the face.

Neither is the design answer. The design answer is:

  minimise the slab thickness  min(W,H)
  subject to  L <= 340.5  and  W <= 226.3  and  H <= 226.3

i.e. the thinnest arm corridor that still lies wholly inside the nominal 12U.
Whatever is left of the 226.3 x 226.3 face is the avionics cell of the
asymmetric twin-cell bus.

Hard-limit margin swept 0/2/3/5 deg. Convex-hull AABB (exact for extents).
Bounding-box level, NOT an interference check.
"""
import numpy as np, trimesh, os, json, csv, itertools
from scipy.optimize import minimize

ROOT = r"F:\China Graduate Future Flight Vehicle Innovation Competition"
MESH = os.path.join(ROOT, r"20_engineering\cad\spacecraft_layout\arm_b601_v1\meshes_b601_gripper")
OUT = os.path.join(ROOT, r"20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\_work\mode_a_native_design_r1\10_stow")
os.makedirs(OUT, exist_ok=True)

BOX = np.array([340.5, 226.3, 226.3])

JOINTS = [("link1", "base_link", (-8.416e-05, 0, 0.08465), (0, 0, 0), (0, 0, 1), -2.8, 2.8),
          ("link2", "link1", (0.020084, 0.031625, 0.05555), (-1.5708, 0, 0), (0, 0, -1), -3.14, 0.0),
          ("link3", "link2", (-0.264, 0, 0), (0, 0, 0), (0, 0, 1), -3.14, 0.0),
          ("link4", "link3", (0.2426, -0.054, -0.001625), (0, 0, 0), (0, 0, 1), -1.87, 1.57),
          ("link5", "link4", (0.078308, -0.0375, -0.03), (-1.5708, 0, 0), (0, 0, 1), -1.57, 1.57),
          ("link6", "link5", (0.023692, 0, 0.04), (0, 1.5708, 0), (0, 0, 1), -3.14, 3.14)]
FIXED = [("gripper_link", "link6", (0, 0, 0.15971), (0, -1.5708, 0)),
         ("gripper_left", "gripper_link", (-0.042091, 2.7531e-05, -1.3031e-05), (0, 0, -1.5708)),
         ("gripper_right", "gripper_link", (-0.042091, -2.7531e-05, 1.3031e-05), (0, 0, 1.5708))]
LO0 = np.array([j[5] for j in JOINTS]); HI0 = np.array([j[6] for j in JOINTS])


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


HULL = {}
for f in sorted(os.listdir(MESH)):
    if f.lower().endswith(".stl"):
        m = trimesh.load_mesh(os.path.join(MESH, f), process=False)
        HULL[f[:-4]] = np.asarray(m.convex_hull.vertices, float)*1000.0
NAMES = [n for n in HULL if not n.startswith("gripper") and n != "base_link"]
print("corridor link set:", NAMES)


def fk(q):
    Tw = {"base_link": np.eye(4)}
    for i, (c, p, x, rr, ax, a, b) in enumerate(JOINTS):
        Tw[c] = Tw[p] @ (Tm(x, rpy(*rr)) @ Tm((0, 0, 0), arot(ax, q[i])))
    for c, p, x, rr in FIXED:
        Tw[c] = Tw[p] @ Tm(x, rpy(*rr))
    return Tw


def extents(x, LO, HI):
    q = np.clip(x[:6], LO, HI)
    Tw = fk(q)
    P = np.vstack([HULL[n] @ Tw[n][:3, :3].T + Tw[n][:3, 3]*1000.0 for n in NAMES])
    P = P @ rotvec(x[6:9]).T
    return P.max(0) - P.min(0), q, Tw, P


def solve(LO, HI, nseed=700, npolish=22, seed=20260904):
    def core(x):
        e, q, _, _ = extents(x, LO, HI)
        es = np.sort(e)[::-1]                                  # L >= W >= H
        viol = np.maximum(0.0, es - BOX).sum()                 # must lie in the box
        return es[2] + 5e3*viol                                # minimise thickness

    def obj(x):
        return core(x) + 1e4*float(np.sum(np.abs(x[:6] - np.clip(x[:6], LO, HI))))

    rng = np.random.default_rng(seed)
    S = [np.zeros(9)]
    for rv in [np.zeros(3), [np.pi/2, 0, 0], [0, np.pi/2, 0], [0, 0, np.pi/2],
               [0.20713, -0.00716, 0.00145], np.radians([25, 0, 0]), np.radians([0, 25, 0])]:
        for qb in [np.radians([1.79, -.54, -.26, 89.45, -45.65, -1.08]), np.zeros(6),
                   np.radians([0, -2, -2, 90, -50, 0])]:
            S.append(np.concatenate([np.clip(qb, LO, HI), rv]))
    for a, b, c, d in itertools.product([0., -1.05, -2.09, -3.14], [0., -1.05, -2.09, -3.14],
                                        [-1.87, 0., 1.57], [-1.57, 0., 1.57]):
        S.append(np.concatenate([np.clip([0., a, b, c, d, 0.], LO, HI), np.zeros(3)]))
    for _ in range(nseed):
        S.append(np.concatenate([LO + (HI-LO)*rng.random(6), rng.normal(0, 1.3, 3)]))
    S = sorted(S, key=obj)[:npolish]
    best = None
    for s in S:
        r = minimize(obj, s, method="Nelder-Mead",
                     options=dict(maxiter=9000, maxfev=9000, xatol=1e-6, fatol=1e-6))
        e, q, Tw, P = extents(r.x, LO, HI)
        v = core(r.x)
        if best is None or v < best[0]:
            best = (v, e, q, r.x, Tw, P)
    return best


rows = []
print(f"\n{'margin':>7}{'  L x W x H (mm)':>34}{'in box':>8}{'thick':>8}{'free face cm2':>15}{'avionics W':>12}")
for mdeg in [0.0, 2.0, 3.0, 5.0]:
    m = np.radians(mdeg)
    LO, HI = LO0 + m, HI0 - m
    v, e, q, x, Tw, P = solve(LO, HI)
    es = np.sort(e)[::-1]
    inbox = bool(np.all(es <= BOX + 1e-6))
    thick = float(es[2])
    free_face = float((226.3*226.3 - es[1]*thick)/100.0)
    avionics_w = float(226.3 - thick)
    rows.append(dict(margin_deg=mdeg, extents_mm=e.tolist(), sorted_LWH_mm=es.tolist(),
                     inside_nominal_12U=inbox, corridor_thickness_mm=thick,
                     corridor_width_mm=float(es[1]), corridor_length_mm=float(es[0]),
                     free_face_area_cm2=free_face, avionics_cell_width_mm=avionics_w,
                     q_deg=np.degrees(q).tolist(),
                     min_margin_to_hard_limit_deg=float(np.degrees(np.minimum(q-LO0, HI0-q).min())),
                     mount_rotvec=x[6:9].tolist()))
    print(f"{mdeg:6.0f}°{es[0]:12.1f} x{es[1]:7.1f} x{es[2]:7.1f}{str(inbox):>8}"
          f"{thick:8.1f}{free_face:15.1f}{avionics_w:12.1f}")

with open(os.path.join(OUT, "A3_02B_CORRIDOR_IN_BOX.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["margin_deg", "L_mm", "W_mm", "thickness_mm", "inside_nominal_12U",
                "free_face_area_cm2", "avionics_cell_width_mm", "min_margin_to_hard_limit_deg",
                "q1_deg", "q2_deg", "q3_deg", "q4_deg", "q5_deg", "q6_deg"])
    for r in rows:
        w.writerow([r["margin_deg"], f"{r['corridor_length_mm']:.3f}", f"{r['corridor_width_mm']:.3f}",
                    f"{r['corridor_thickness_mm']:.3f}", r["inside_nominal_12U"],
                    f"{r['free_face_area_cm2']:.2f}", f"{r['avionics_cell_width_mm']:.2f}",
                    f"{r['min_margin_to_hard_limit_deg']:.3f}"] + [f"{t:.3f}" for t in r["q_deg"]])

json.dump(dict(schema="A3_02B_CORRIDOR_IN_BOX_V1",
               objective="minimise corridor thickness subject to the bundle lying wholly inside 340.5 x 226.3 x 226.3",
               link_set=NAMES, box_mm=BOX.tolist(),
               note="bounding-box level, NOT an interference check; base_link and gripper excluded (recessed / separately stowed)",
               results=rows),
          open(os.path.join(OUT, "A3_02B_CORRIDOR_IN_BOX.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\nwrote", OUT)
