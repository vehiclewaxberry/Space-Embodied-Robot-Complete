"""A3.2d - distal-aware full-system re-optimisation.

A3.4 verdict: A3_4_REQUIRES_A3_2D_REOPTIMIZATION.

Root cause found in A3.4: the corridor pose was optimised for links1-6 only, so
base_link and the gripper ended up axially co-located (39.5 mm overlap) on
opposite Y sides, giving a 276.2 mm local Y width over an 8 mm band. Only
3/229 stations exceeded 226.3 in Y and 0/229 in Z.

A3.2d therefore re-optimises with the FULL system in the objective:

  FIT_FULL   minimise max_axis protrusion of the full system vs 366 x 226.3 x 226.3
  THIN_FULL  minimise the links1-6 corridor thickness, subject to the FULL system
             lying inside the envelope
  each also run with an explicit ROOT/DISTAL axial de-colocation term

Hard-limit margin swept 0/2/3/5 deg. Two independent seeds per case.
Convex-hull AABB (exact for extents). No URDF, no link geometry, no joint limit
is modified. Bounding-box level, NOT an interference check.
"""
import numpy as np, trimesh, os, json, csv, itertools, time
from scipy.optimize import minimize

ROOT = r"F:\China Graduate Future Flight Vehicle Innovation Competition"
BASE = os.path.join(ROOT, r"20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\_work\mode_a_native_design_r1")
MESH = os.path.join(ROOT, r"20_engineering\cad\spacecraft_layout\arm_b601_v1\meshes_b601_gripper")
OUT = os.path.join(BASE, "04_a3_2d")
os.makedirs(OUT, exist_ok=True)

BOX = np.array([366.0, 226.3, 226.3]); HALF = BOX/2.0

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
ORDER = ["base_link", "link1", "link2", "link3", "link4", "link5", "link6",
         "gripper_link", "gripper_left", "gripper_right"]
I16 = slice(1, 7)          # links1-6 body indices
IROOT, IDIST = 0, slice(7, 10)


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


H = []
for n in ORDER:
    m = trimesh.load_mesh(os.path.join(MESH, n + ".STL"), process=False)
    H.append(np.asarray(m.convex_hull.vertices, float)*1000.0)
SIZES = [len(h) for h in H]
STACK = np.vstack(H)
OFFS = np.cumsum([0]+SIZES)
print(f"bodies {len(ORDER)}  hull points {len(STACK)}")


def world(qv, rv):
    """all hull points of the full system in the (rotated) box frame."""
    Tw = {"base_link": np.eye(4)}
    for i, (c, p, x, rr, ax, a, b) in enumerate(JOINTS):
        Tw[c] = Tw[p] @ (Tm(x, rpy(*rr)) @ Tm((0, 0, 0), arot(ax, qv[i])))
    for c, p, x, rr in FIXED:
        Tw[c] = Tw[p] @ Tm(x, rpy(*rr))
    R = rotvec(rv)
    P = np.empty_like(STACK)
    for k, n in enumerate(ORDER):
        M = Tw[n]
        P[OFFS[k]:OFFS[k+1]] = (H[k] @ M[:3, :3].T + M[:3, 3]*1000.0) @ R.T
    return P


def metrics(x, LO, HI):
    qv = np.clip(x[:6], LO, HI)
    P = world(qv, x[6:9])
    ext = P.max(0) - P.min(0)
    es = np.sort(ext)[::-1]
    prot = float((es/2 - HALF/2).max()) if False else float(((es - BOX)/2).max())
    P16 = P[OFFS[1]:OFFS[7]]
    e16 = np.sort(P16.max(0) - P16.min(0))[::-1]
    xr_root = (P[OFFS[0]:OFFS[1], 0].min(), P[OFFS[0]:OFFS[1], 0].max())
    xd = P[OFFS[7]:OFFS[10], 0]
    xr_dist = (xd.min(), xd.max())
    ov = max(0.0, min(xr_root[1], xr_dist[1]) - max(xr_root[0], xr_dist[0]))
    return dict(q=qv, ext_sorted=es, prot=prot, corridor_t=float(e16[2]),
                links16_sorted=e16, overlap=float(ov),
                root_x=xr_root, distal_x=xr_dist, ext_xyz=ext)


def make_obj(LO, HI, mode, decoloc):
    def core(x):
        m = metrics(x, LO, HI)
        pen = (0.05*m["overlap"] if decoloc else 0.0)
        if mode == "FIT_FULL":
            return m["prot"] + pen
        viol = float(np.maximum(0.0, m["ext_sorted"] - BOX).sum())
        return m["corridor_t"] + 5e3*viol + pen

    def obj(x):
        return core(x) + 1e4*float(np.sum(np.abs(x[:6] - np.clip(x[:6], LO, HI))))
    return core, obj


def solve(LO, HI, mode, decoloc, seed, nseed=320, npolish=8, maxit=2500):
    core, obj = make_obj(LO, HI, mode, decoloc)
    rng = np.random.default_rng(seed)
    S = [np.zeros(9)]
    for rv in [np.zeros(3), [np.pi/2, 0, 0], [0, np.pi/2, 0], [0, 0, np.pi/2],
               [0.20713, -0.00716, 0.00145]]:
        for qb in [np.radians([1.79, -.54, -.26, 89.45, -45.65, -1.08]), np.zeros(6),
                   np.radians([0, -90, -90, 0, 0, 0]), np.radians([0, -170, -170, 80, -50, 0])]:
            S.append(np.concatenate([np.clip(qb, LO, HI), rv]))
    for a, b, c in itertools.product([0., -1.05, -2.09, -3.14], [0., -1.05, -2.09, -3.14],
                                     [-1.87, 0., 1.57]):
        S.append(np.concatenate([np.clip([0., a, b, c, 0., 0.], LO, HI), np.zeros(3)]))
    for _ in range(nseed):
        S.append(np.concatenate([LO + (HI-LO)*rng.random(6), rng.normal(0, 1.3, 3)]))
    S = sorted(S, key=obj)[:npolish]
    best = None
    for s in S:
        r = minimize(obj, s, method="Nelder-Mead",
                     options=dict(maxiter=maxit, maxfev=maxit, xatol=1e-5, fatol=1e-5))
        v = core(r.x)
        if best is None or v < best[0]:
            best = (v, r.x)
    return best


t0 = time.time()
rows = []
hdr = (f"{'marg':>5}{'mode':>10}{'dcl':>5}{'seed':>7}"
       f"{'  FULL L x W x H':>32}{'prot':>8}{'corr_t':>8}{'ovlap':>8}{'inbox':>7}")
print("\n" + hdr); print("-"*len(hdr))
for mdeg in [0.0, 2.0, 3.0, 5.0]:
    m = np.radians(mdeg); LO, HI = LO0 + m, HI0 - m
    for mode in ["FIT_FULL", "THIN_FULL"]:
        for dcl in [False, True]:
            cands = []
            for sd in [20260905, 4242]:
                v, x = solve(LO, HI, mode, dcl, sd)
                cands.append((v, x, sd))
            cands.sort(key=lambda t: t[0])
            v, x, sd = cands[0]
            mm = metrics(x, LO, HI)
            inbox = bool(np.all(mm["ext_sorted"] <= BOX + 1e-6))
            rec = dict(margin_deg=mdeg, mode=mode, decolocate=dcl, best_seed=sd,
                       seed_spread=float(cands[-1][0]-cands[0][0]),
                       full_sorted_LWH_mm=mm["ext_sorted"].tolist(),
                       full_extents_XYZ_mm=mm["ext_xyz"].tolist(),
                       worst_protrusion_mm=mm["prot"], corridor_thickness_mm=mm["corridor_t"],
                       links16_sorted_LWH_mm=mm["links16_sorted"].tolist(),
                       root_distal_overlap_mm=mm["overlap"],
                       root_x_range_mm=list(map(float, mm["root_x"])),
                       distal_x_range_mm=list(map(float, mm["distal_x"])),
                       inside_box=inbox, q_deg=np.degrees(mm["q"]).tolist(),
                       min_margin_to_hard_limit_deg=float(np.degrees(
                           np.minimum(mm["q"]-LO0, HI0-mm["q"]).min())),
                       mount_rotvec=x[6:9].tolist())
            rows.append(rec)
            print(f"{mdeg:4.0f}°{mode:>10}{str(dcl):>5}{sd:>7}"
                  f"{mm['ext_sorted'][0]:11.1f} x{mm['ext_sorted'][1]:7.1f} x{mm['ext_sorted'][2]:7.1f}"
                  f"{mm['prot']:+8.2f}{mm['corridor_t']:8.1f}{mm['overlap']:8.1f}{str(inbox):>7}")
            json.dump(rows, open(os.path.join(OUT, "_partial.json"), "w"), indent=1)
print(f"\nelapsed {time.time()-t0:.0f} s")

ok = [r for r in rows if r["inside_box"]]
print(f"\nfull system inside 366 x 226.3 x 226.3 : {len(ok)} / {len(rows)} cases")
if ok:
    ok2 = [r for r in ok if r["min_margin_to_hard_limit_deg"] >= 1.99]
    print(f"  of which with >= 2 deg hard-limit margin : {len(ok2)}")
    for r in sorted(ok2 or ok, key=lambda r: r["corridor_thickness_mm"])[:6]:
        print(f"   marg {r['margin_deg']:.0f}° {r['mode']:<10} dcl={str(r['decolocate']):<5} "
              f"FULL {np.round(r['full_sorted_LWH_mm'],1)}  prot {r['worst_protrusion_mm']:+.2f}  "
              f"corridor {r['corridor_thickness_mm']:.1f}  overlap {r['root_distal_overlap_mm']:.1f}")

with open(os.path.join(OUT, "A3_2D_RESULTS.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["margin_deg", "mode", "decolocate", "L_mm", "W_mm", "H_mm", "worst_protrusion_mm",
                "inside_box", "corridor_thickness_mm", "root_distal_overlap_mm",
                "min_margin_to_hard_limit_deg", "seed_spread",
                "q1", "q2", "q3", "q4", "q5", "q6"])
    for r in rows:
        w.writerow([r["margin_deg"], r["mode"], r["decolocate"]] +
                   [f"{t:.3f}" for t in r["full_sorted_LWH_mm"]] +
                   [f"{r['worst_protrusion_mm']:.3f}", r["inside_box"],
                    f"{r['corridor_thickness_mm']:.3f}", f"{r['root_distal_overlap_mm']:.3f}",
                    f"{r['min_margin_to_hard_limit_deg']:.3f}", f"{r['seed_spread']:.4f}"] +
                   [f"{t:.3f}" for t in r["q_deg"]])
json.dump(dict(schema="A3_2D_FULLSYSTEM_REOPT_V1",
               trigger="A3_4_REQUIRES_A3_2D_REOPTIMIZATION",
               objective_change="base_link and the distal system are now IN the objective",
               box_mm=BOX.tolist(), profile="CDS_12U_REFERENCE",
               method="convex-hull AABB (exact for extents); translation centred; rotation free",
               limitations=["bounding-box level, not an interference check",
                            "self-collision still NOT_VALIDATED (no narrow-phase backend)",
                            "M3R/HDRM/saddle/harness/connector geometry still MISSING_GEOMETRY_HOLD"],
               results=rows),
          open(os.path.join(OUT, "A3_2D_RESULTS.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("wrote", OUT)
