"""A3.2c - envelope authority correction and re-optimisation.

CORRECTION
==========
A1/A2/A3.2/A3.2b all used 340.5 mm as the 12U axial bound. That is wrong:
340.5 = 3 x 113.5 is the 3U axial dimension. The project registers the conflict
itself in 02_PRODUCT_STRUCTURE.yaml:

  HOLD_NEUTRAL_PROXY_BUS_LENGTH_340P5_VS_NATIVE_V2_2_366P0_MM_UNRECONCILED
  neutral_proxy_x_extent_mm              [-170.25, 170.25] -> 340.5
  native_V2_2_primary_structure_x_extent [-183.0 , 183.0 ] -> 366.0

and .codex/agents/spacecraft-mechanical-design-agent.md marks
340.5 x 226.3 x 226.3 as NON_FLIGHT_DISPLAY_ONLY.

This run uses exactly one profile: CDS_12U_REFERENCE = 366.0 x 226.3 x 226.3.
Prior results are retained as LEGACY_340P5_DIAGNOSTIC_ONLY / SUPERSEDED.

Protrusion hard value is 6.5 mm (CDS Rev 14.1 text), NOT the 6.55 mm read off
the OreSat keepout solid (that model carries 0.05 mm of modelling slop).

Adds, per the owner directive:
  * three independent optimisation seeds per case (stability)
  * non-adjacent self-collision clearance (Frank-Wolfe on the Minkowski
    difference of convex hulls - exact for convex sets, no FCL needed)
  * diagnostic uniform inflation delta = 0 / 0.25 / 0.50 / 1.00 mm
    (per-face protrusion grows by exactly delta; AABB grows by 2*delta)
  * explicit base_link pose in the box frame

Bounding-box level. NOT a deployer fit check. NOT an interference check
against bus structure.
"""
import numpy as np, trimesh, os, json, csv, itertools
from scipy.optimize import minimize

ROOT = r"F:\China Graduate Future Flight Vehicle Innovation Competition"
MESH = os.path.join(ROOT, r"20_engineering\cad\spacecraft_layout\arm_b601_v1\meshes_b601_gripper")
OUT = os.path.join(ROOT, r"20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\_work\mode_a_native_design_r1\01_a3_2c")
os.makedirs(OUT, exist_ok=True)

PROFILES = {
    "CDS_12U_REFERENCE":      dict(box=[366.0, 226.3, 226.3], status="ACTIVE_FOR_THIS_RUN",
                                   source="CubeSat Design Spec Rev 14.1 12U rail-reference envelope"),
    "COMPETITION_DISPLAY_V0": dict(box=[340.5, 226.3, 226.3], status="LEGACY_340P5_DIAGNOSTIC_ONLY",
                                   source="project display proxy = 3 x 113.5 (3U axial); NON_FLIGHT_DISPLAY_ONLY"),
}
BOX = np.array(PROFILES["CDS_12U_REFERENCE"]["box"])
PROTRUSION_HARD_MM = 6.5          # CDS Rev 14.1 text value
PROTRUSION_TARGET_MM = 5.0        # project design target, not a spec value

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

CORRIDOR = ["link1", "link2", "link3", "link4", "link5", "link6"]
FULLARM = list(HULL)
NONADJ = [(a, b) for i, a in enumerate(CORRIDOR) for b in CORRIDOR[i+2:]]


def fk(q):
    Tw = {"base_link": np.eye(4)}
    for i, (c, p, x, rr, ax, a, b) in enumerate(JOINTS):
        Tw[c] = Tw[p] @ (Tm(x, rpy(*rr)) @ Tm((0, 0, 0), arot(ax, q[i])))
    for c, p, x, rr in FIXED:
        Tw[c] = Tw[p] @ Tm(x, rpy(*rr))
    return Tw


def placed(q, names, R):
    Tw = fk(q)
    return {n: (HULL[n] @ Tw[n][:3, :3].T + Tw[n][:3, 3]*1000.0) @ R.T for n in names}, Tw


def fw_distance(A, B, iters=250, tol=1e-9):
    """Exact-in-the-limit distance between conv(A) and conv(B), Frank-Wolfe on
    the Minkowski difference. Returns 0.0 when the hulls interpenetrate."""
    z = A[0] - B[0]
    for _ in range(iters):
        d = z
        nz = np.linalg.norm(d)
        if nz < 1e-12:
            return 0.0
        s = A[np.argmin(A @ d)] - B[np.argmax(B @ d)]
        gap = float(d @ (z - s))
        if gap <= tol * max(1.0, nz):
            break
        w = s - z
        ww = float(w @ w)
        if ww < 1e-18:
            break
        g = float(np.clip(-(z @ w)/ww, 0.0, 1.0))
        z = z + g*w
    return float(np.linalg.norm(z))


def solve(names, LO, HI, mode, seed, nseed=450, npolish=16):
    def core(x):
        q = np.clip(x[:6], LO, HI)
        P = np.vstack(list(placed(q, names, rotvec(x[6:9]))[0].values()))
        e = P.max(0) - P.min(0)
        es = np.sort(e)[::-1]
        if mode == "FIT":
            return float((es/2 - BOX/2).max())
        viol = np.maximum(0.0, es - BOX).sum()
        return float(es[2]) + 5e3*viol

    def obj(x):
        return core(x) + 1e4*float(np.sum(np.abs(x[:6] - np.clip(x[:6], LO, HI))))

    rng = np.random.default_rng(seed)
    S = [np.zeros(9)]
    for rv in [np.zeros(3), [np.pi/2, 0, 0], [0, np.pi/2, 0], [0, 0, np.pi/2],
               [0.20713, -0.00716, 0.00145], np.radians([25, 0, 0])]:
        for qb in [np.radians([1.79, -.54, -.26, 89.45, -45.65, -1.08]), np.zeros(6)]:
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
                     options=dict(maxiter=8000, maxfev=8000, xatol=1e-6, fatol=1e-6))
        v = core(r.x)
        if best is None or v < best[0]:
            best = (v, r.x)
    return best


def report(x, names, LO, HI):
    q = np.clip(x[:6], LO, HI)
    R = rotvec(x[6:9])
    pl, Tw = placed(q, names, R)
    P = np.vstack(list(pl.values()))
    ctr = (P.max(0) + P.min(0))/2
    e = P.max(0) - P.min(0)
    order = np.argsort(e)[::-1]
    es = e[order]
    prot = (es - BOX)/2.0
    clr = [(a, b, fw_distance(pl[a], pl[b])) for a, b in NONADJ if a in pl and b in pl]
    base = (np.zeros(3) @ R.T) - ctr
    return dict(q_deg=np.degrees(q).tolist(),
                min_margin_to_hard_limit_deg=float(np.degrees(np.minimum(q-LO0, HI0-q).min())),
                mount_rotvec=x[6:9].tolist(),
                mount_angle_deg=float(np.degrees(np.linalg.norm(x[6:9]))),
                sorted_LWH_mm=es.tolist(),
                protrusion_per_face_mm=prot.tolist(),
                worst_protrusion_mm=float(prot.max()),
                inside_box=bool(np.all(es <= BOX + 1e-6)),
                corridor_thickness_mm=float(es[2]),
                gross_residual_slab_width_mm=float(BOX[1] - es[2]),
                base_link_origin_in_box_mm=base.tolist(),
                hull_self_clearance_min_mm=float(min(c[2] for c in clr)) if clr else None,
                hull_overlapping_pairs=[f"{a}|{b}" for a, b, d in clr if d <= 1e-6],
                hull_self_clearance_detail={f"{a}|{b}": round(d, 4) for a, b, d in clr},
                self_collision_status="NOT_VALIDATED_HULL_LEVEL_ONLY")


print(f"PROFILE  ACTIVE = CDS_12U_REFERENCE {BOX.tolist()} mm")
print(f"         LEGACY = COMPETITION_DISPLAY_V0 {PROFILES['COMPETITION_DISPLAY_V0']['box']} "
      f"(SUPERSEDED, 3U axial value)")
print(f"         protrusion hard value {PROTRUSION_HARD_MM} mm (CDS text), design target "
      f"{PROTRUSION_TARGET_MM} mm\n")

rows = []
hdr = f"{'set':<10}{'marg':>5}{'mode':>10}{'seed':>6}{'  L x W x H (mm)':>30}{'worst prot':>11}{'thick':>8}{'selfclr':>9}"
print(hdr); print("-"*len(hdr))
for sname, names in [("CORRIDOR", CORRIDOR), ("FULLARM", FULLARM)]:
    for mdeg in [0.0, 2.0, 3.0, 5.0]:
        m = np.radians(mdeg)
        LO, HI = LO0 + m, HI0 - m
        for mode in ["FIT", "THIN"]:
            cands = []
            for sd in ([20260905, 7717, 991] if sname == "CORRIDOR" else [20260905]):
                v, x = solve(names, LO, HI, "FIT" if mode == "FIT" else "THIN", sd)
                cands.append((v, x, sd))
            cands.sort(key=lambda t: t[0])
            v, x, sd = cands[0]
            spread = cands[-1][0] - cands[0][0]
            r = report(x, names, LO, HI)
            r.update(link_set=sname, margin_deg=mdeg, mode=mode, best_seed=sd,
                     seed_spread=float(spread), profile="CDS_12U_REFERENCE")
            rows.append(r)
            print(f"{sname:<10}{mdeg:4.0f}°{mode:>10}{sd:>6}"
                  f"{r['sorted_LWH_mm'][0]:11.1f} x{r['sorted_LWH_mm'][1]:7.1f} x{r['sorted_LWH_mm'][2]:7.1f}"
                  f"{r['worst_protrusion_mm']:+11.2f}{r['corridor_thickness_mm']:8.1f}"
                  f"{(r['hull_self_clearance_min_mm'] if r['hull_self_clearance_min_mm'] is not None else -1):9.2f}")
            json.dump(rows, open(os.path.join(OUT, "_partial_rows.json"), "w"), indent=1)

# ---- delta sensitivity on the corridor candidates ----
print("\n" + "="*96)
print("DELTA SENSITIVITY  (uniform inflation; per-face protrusion grows by exactly delta)")
print("="*96)
print(f"{'set':<10}{'marg':>5}{'mode':>7}{'d=0.00':>9}{'d=0.25':>9}{'d=0.50':>9}{'d=1.00':>9}   verdict vs 6.5 mm")
delta_rows = []
for r in rows:
    if r["link_set"] != "CORRIDOR":
        continue
    p0 = r["worst_protrusion_mm"]
    vals = {d: p0 + d for d in [0.0, 0.25, 0.5, 1.0]}
    first_fail = next((d for d in [0.0, 0.25, 0.5, 1.0] if vals[d] > PROTRUSION_HARD_MM), None)
    verdict = "inside 6.5 at all delta" if first_fail is None else f"exceeds 6.5 at delta={first_fail}"
    if p0 <= 0:
        verdict = "no protrusion (inside box)"
    delta_rows.append(dict(link_set=r["link_set"], margin_deg=r["margin_deg"], mode=r["mode"],
                           protrusion_by_delta_mm={str(k): v for k, v in vals.items()},
                           first_failing_delta_mm=first_fail, verdict=verdict))
    print(f"{r['link_set']:<10}{r['margin_deg']:4.0f}°{r['mode']:>7}"
          f"{vals[0.0]:+9.2f}{vals[0.25]:+9.2f}{vals[0.5]:+9.2f}{vals[1.0]:+9.2f}   {verdict}")

with open(os.path.join(OUT, "A3_02C_RESULTS.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["link_set", "margin_deg", "mode", "profile", "L_mm", "W_mm", "H_mm",
                "worst_protrusion_mm", "inside_box", "corridor_thickness_mm",
                "gross_residual_slab_width_mm", "hull_self_clearance_min_mm", "hull_overlapping_pairs",
                "min_margin_to_hard_limit_deg", "mount_angle_deg", "seed_spread",
                "q1_deg", "q2_deg", "q3_deg", "q4_deg", "q5_deg", "q6_deg"])
    for r in rows:
        w.writerow([r["link_set"], r["margin_deg"], r["mode"], r["profile"]] +
                   [f"{t:.3f}" for t in r["sorted_LWH_mm"]] +
                   [f"{r['worst_protrusion_mm']:.3f}", r["inside_box"],
                    f"{r['corridor_thickness_mm']:.3f}", f"{r['gross_residual_slab_width_mm']:.3f}",
                    "" if r["hull_self_clearance_min_mm"] is None else f"{r['hull_self_clearance_min_mm']:.4f}",
                    ";".join(r["hull_overlapping_pairs"]),
                    f"{r['min_margin_to_hard_limit_deg']:.3f}", f"{r['mount_angle_deg']:.3f}",
                    f"{r['seed_spread']:.4f}"] +
                   [f"{t:.3f}" for t in r["q_deg"]])

json.dump(dict(schema="A3_02C_ENVELOPE_AUTHORITY_CORRECTION_V1",
               correction="340.5 mm is the 3U axial dimension and was used in error by A1/A2/A3.2/A3.2b",
               profiles=PROFILES, active_profile="CDS_12U_REFERENCE",
               protrusion_hard_mm=PROTRUSION_HARD_MM, protrusion_design_target_mm=PROTRUSION_TARGET_MM,
               frame_mapping=dict(id="T_S_RCDS", status="PROVISIONAL_FRAME_MAPPING",
                                  note=("optimiser searches orientation freely, so results are "
                                        "mapping-independent; binding L/W/H to +-X_S/+-Y_S/+-Z_S "
                                        "requires owner signoff of T_S_RCDS")),
               method=("convex-hull AABB, exact for extents; translation centred; rotation free; "
                       "self-clearance by Frank-Wolfe on the Minkowski difference"),
               limitations=["bounding-box level, not a deployer fit check",
                            "no bus structure, HDRM, harness, MLI or tolerance in this run",
                            "links1-6 only for CORRIDOR; base_link and gripper excluded"],
               results=rows, delta_sensitivity=delta_rows),
          open(os.path.join(OUT, "A3_02C_RESULTS.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\nwrote", OUT)
