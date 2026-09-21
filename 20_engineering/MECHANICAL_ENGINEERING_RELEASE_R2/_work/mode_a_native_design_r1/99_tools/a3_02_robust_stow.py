"""A3.2 - robust stow optimisation with hard-limit margin sweep.

Two objectives, both over q1..q6 + mount orientation (translation analytically
centred):

  (F) FIT      minimise max_axis( extent/2 - half )     -> does it clear the 12U
  (C) CORRIDOR minimise W*H subject to L <= 340.5       -> sizes the arm corridor
                                                           in the C1-B bus

Hard-limit margin m is swept over 0/2/3/5 deg: q is constrained to
[LO+m, HI-m]. This matters because J2 and J3 have upper limit 0.0 and q=0 is
the fully folded pose - the A1/A2 optima sit ON the hard stop, which is not an
acceptable launch-locked configuration.

Convex hulls of the accepted-URDF STLs. AABB extents from a hull are EXACT
(support function is invariant under convex hull), verified to 0.000000 mm in
A2b. Bounding-box level, NOT an interference check.
"""
import numpy as np, trimesh, os, json, csv, itertools
from scipy.optimize import minimize

ROOT = r"F:\China Graduate Future Flight Vehicle Innovation Competition"
MESH = os.path.join(ROOT, r"20_engineering\cad\spacecraft_layout\arm_b601_v1\meshes_b601_gripper")
OUT = os.path.join(ROOT, r"20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\_work\mode_a_native_design_r1\10_stow")
os.makedirs(OUT, exist_ok=True)

HALF = np.array([170.25, 113.15, 113.15])
LMAX = 340.5

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

SETS = {"CORRIDOR_links1_6": [n for n in HULL if not n.startswith("gripper") and n != "base_link"],
        "FULL_ARM": list(HULL)}


def fk(q):
    Tw = {"base_link": np.eye(4)}
    for i, (c, p, x, rr, ax, a, b) in enumerate(JOINTS):
        Tw[c] = Tw[p] @ (Tm(x, rpy(*rr)) @ Tm((0, 0, 0), arot(ax, q[i])))
    for c, p, x, rr in FIXED:
        Tw[c] = Tw[p] @ Tm(x, rpy(*rr))
    return Tw


def pts(q, names):
    Tw = fk(q)
    return np.vstack([HULL[n] @ Tw[n][:3, :3].T + Tw[n][:3, 3]*1000.0 for n in names]), Tw


def ext_of(x, names, LO, HI):
    q = np.clip(x[:6], LO, HI)
    P, Tw = pts(q, names)
    P = P @ rotvec(x[6:9]).T
    return P.max(0) - P.min(0), q, Tw


def solve(names, LO, HI, mode, nseed=500, npolish=18, seed=20260904):
    def core(x):
        e, q, _ = ext_of(x, names, LO, HI)
        if mode == "FIT":
            val = float((e/2 - HALF).max())
        else:                                        # CORRIDOR
            val = float(e[1]*e[2]/100.0) + 1e3*max(0.0, e[0]-LMAX)
        return val

    def obj(x):
        return core(x) + 1e4*float(np.sum(np.abs(x[:6] - np.clip(x[:6], LO, HI))))

    rng = np.random.default_rng(seed)
    S = [np.zeros(9)]
    for rv in [np.zeros(3), [np.pi/2, 0, 0], [0, np.pi/2, 0], [0, 0, np.pi/2],
               [0.20713, -0.00716, 0.00145], np.radians([25, 0, 0])]:
        S.append(np.concatenate([np.clip(np.radians([1.79, -.54, -.26, 89.45, -45.65, -1.08]), LO, HI), rv]))
        S.append(np.concatenate([np.clip(np.zeros(6), LO, HI), rv]))
    for a, b, c, d in itertools.product([0., -1.05, -2.09, -3.14], [0., -1.05, -2.09, -3.14],
                                        [-1.87, 0., 1.57], [-1.57, 0., 1.57]):
        S.append(np.concatenate([np.clip([0., a, b, c, d, 0.], LO, HI), np.zeros(3)]))
    for _ in range(nseed):
        S.append(np.concatenate([LO + (HI-LO)*rng.random(6), rng.normal(0, 1.2, 3)]))
    S = sorted(S, key=obj)[:npolish]
    best = None
    for s in S:
        r = minimize(obj, s, method="Nelder-Mead",
                     options=dict(maxiter=7000, maxfev=7000, xatol=1e-5, fatol=1e-6))
        e, q, Tw = ext_of(r.x, names, LO, HI)
        v = core(r.x)
        if best is None or v < best[0]:
            best = (v, e, q, r.x, Tw)
    return best


rows = []
print(f"{'set':<18}{'margin':>7}{'mode':>10}{'  L x W x H (mm)':>30}{'excess':>9}{'sect cm2':>10}{'limit hits':>11}")
for sname, names in SETS.items():
    for mdeg in [0.0, 2.0, 3.0, 5.0]:
        m = np.radians(mdeg)
        LO, HI = LO0 + m, HI0 - m
        if np.any(LO > HI):
            continue
        for mode in ["FIT", "CORRIDOR"]:
            v, e, q, x, Tw = solve(names, LO, HI, mode)
            es = np.sort(e)[::-1]
            exc = float((e/2 - HALF).max())
            hits = int(np.sum((q <= LO0 + 1e-6) | (q >= HI0 - 1e-6)))
            rows.append(dict(link_set=sname, margin_deg=mdeg, mode=mode,
                             extents_mm=e.tolist(), sorted_LWH_mm=es.tolist(),
                             minimax_excess_mm=exc,
                             cross_section_cm2=float(es[1]*es[2]/100.0),
                             length_mm=float(es[0]), fits_length=bool(es[0] <= LMAX),
                             q_deg=np.degrees(q).tolist(),
                             margin_to_hard_limit_deg=float(np.degrees(np.minimum(q-LO0, HI0-q).min())),
                             mount_rotvec=x[6:9].tolist(),
                             hard_limit_hits=hits))
            print(f"{sname:<18}{mdeg:6.0f}°{mode:>10}"
                  f"{es[0]:11.1f} x{es[1]:7.1f} x{es[2]:7.1f}{exc:+9.2f}"
                  f"{es[1]*es[2]/100.0:10.1f}{hits:11d}")

with open(os.path.join(OUT, "A3_02_STOW_MARGIN_SWEEP.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["link_set", "margin_deg", "mode", "L_mm", "W_mm", "H_mm", "minimax_excess_mm",
                "cross_section_cm2", "fits_length_340p5", "min_margin_to_hard_limit_deg",
                "q1_deg", "q2_deg", "q3_deg", "q4_deg", "q5_deg", "q6_deg"])
    for r in rows:
        w.writerow([r["link_set"], r["margin_deg"], r["mode"], f"{r['sorted_LWH_mm'][0]:.3f}",
                    f"{r['sorted_LWH_mm'][1]:.3f}", f"{r['sorted_LWH_mm'][2]:.3f}",
                    f"{r['minimax_excess_mm']:.3f}", f"{r['cross_section_cm2']:.2f}",
                    r["fits_length"], f"{r['margin_to_hard_limit_deg']:.3f}"] +
                   [f"{t:.3f}" for t in r["q_deg"]])

json.dump(dict(schema="A3_02_ROBUST_STOW_V1",
               method="convex hull AABB (exact for extents); translation centred; rotation free",
               box_mm=(2*HALF).tolist(), long_axis_limit_mm=LMAX,
               note="bounding-box level, NOT an interference check",
               results=rows),
          open(os.path.join(OUT, "A3_02_ROBUST_STOW.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)

sel = [r for r in rows if r["link_set"] == "CORRIDOR_links1_6" and r["mode"] == "CORRIDOR"]
print("\n" + "="*84)
print("CORRIDOR SIZING  (links1-6, base_link recessed into structure)")
print("="*84)
for r in sel:
    print(f"  margin {r['margin_deg']:.0f}deg : corridor {r['sorted_LWH_mm'][0]:7.1f} L x "
          f"{r['sorted_LWH_mm'][1]:6.1f} x {r['sorted_LWH_mm'][2]:6.1f} mm   "
          f"section {r['cross_section_cm2']:6.1f} cm2   real margin {r['margin_to_hard_limit_deg']:.2f}deg")
print("="*84)
print("wrote", OUT)
