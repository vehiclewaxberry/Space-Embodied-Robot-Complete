"""A3.4 part 1 - FULLARM component truth table, extrema attribution, station envelope.

METHOD NOTE
-----------
A global AABB of 381.6 x 242.0 x 242.0 does NOT mean the arm needs a
381.6 x 242 x 242 bay. The six extrema may come from different components at
different X stations. This script answers, before any repackaging:

  who produces each of the six global extrema, and what does the cross-section
  actually look like at every 1 mm station.

Consumes 02_a3_3/A3_36_A3_4_HANDOFF.json. Does not re-optimise any joint angle.
Read-only over project inputs; writes only under 03_a3_4/.
"""
import numpy as np, trimesh, os, json, csv, hashlib

ROOT = r"F:\China Graduate Future Flight Vehicle Innovation Competition"
BASE = os.path.join(ROOT, r"20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\_work\mode_a_native_design_r1")
MESH = os.path.join(ROOT, r"20_engineering\cad\spacecraft_layout\arm_b601_v1\meshes_b601_gripper")
URDF = os.path.join(ROOT, r"20_engineering\cad\spacecraft_layout\arm_b601_v1\arm_b601_v1.urdf")
OUT = os.path.join(BASE, "03_a3_4")
os.makedirs(OUT, exist_ok=True)

BOX = np.array([366.0, 226.3, 226.3]); HALF = BOX/2.0
RAIL_W = 8.5
STATION = 1.0


def sha(fp):
    h = hashlib.sha256()
    with open(fp, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest().upper()


HAND = json.load(open(os.path.join(BASE, "02_a3_3", "A3_36_A3_4_HANDOFF.json"), encoding="utf-8"))
GATE3 = json.load(open(os.path.join(BASE, "02_a3_3", "A3_3_FINAL_GATE.json"), encoding="utf-8"))
A2C = json.load(open(os.path.join(BASE, "01_a3_2c", "A3_02C_RESULTS.json"), encoding="utf-8"))
if GATE3["gate"] != "A3_3_PASS_GENERIC_CDS_GEOMETRY":
    raise SystemExit("A3_4_ABORT_UPSTREAM_IDENTITY_CHANGED: A3.3 gate is " + GATE3["gate"])
if sha(URDF) != "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164":
    raise SystemExit("A3_4_ABORT_UPSTREAM_IDENTITY_CHANGED: accepted URDF hash drift")
print("upstream OK   A3.3 gate =", GATE3["gate"], "  PRIMARY =", HAND["selected_candidate"])

# ---------------- kinematics (accepted URDF, verbatim) ----------------
JOINTS = [("link1", "base_link", (-8.416e-05, 0, 0.08465), (0, 0, 0), (0, 0, 1), "revolute", -2.8, 2.8),
          ("link2", "link1", (0.020084, 0.031625, 0.05555), (-1.5708, 0, 0), (0, 0, -1), "revolute", -3.14, 0.0),
          ("link3", "link2", (-0.264, 0, 0), (0, 0, 0), (0, 0, 1), "revolute", -3.14, 0.0),
          ("link4", "link3", (0.2426, -0.054, -0.001625), (0, 0, 0), (0, 0, 1), "revolute", -1.87, 1.57),
          ("link5", "link4", (0.078308, -0.0375, -0.03), (-1.5708, 0, 0), (0, 0, 1), "revolute", -1.57, 1.57),
          ("link6", "link5", (0.023692, 0, 0.04), (0, 1.5708, 0), (0, 0, 1), "revolute", -3.14, 3.14)]
FIXED = [("gripper_link", "link6", (0, 0, 0.15971), (0, -1.5708, 0), "fixed"),
         ("gripper_left", "gripper_link", (-0.042091, 2.7531e-05, -1.3031e-05), (0, 0, -1.5708), "prismatic"),
         ("gripper_right", "gripper_link", (-0.042091, -2.7531e-05, 1.3031e-05), (0, 0, 1.5708), "prismatic")]

GROUP = {"base_link": "BASE_FIXED_SYSTEM",
         "link1": "SERIAL_ARM", "link2": "SERIAL_ARM", "link3": "SERIAL_ARM",
         "link4": "SERIAL_ARM", "link5": "SERIAL_ARM", "link6": "SERIAL_ARM",
         "gripper_link": "DISTAL_SYSTEM", "gripper_left": "DISTAL_SYSTEM", "gripper_right": "DISTAL_SYSTEM"}
LINKS16 = ["link1", "link2", "link3", "link4", "link5", "link6"]
FULL = ["base_link"] + LINKS16 + ["gripper_link", "gripper_left", "gripper_right"]
MASS = {"base_link": 0.83660, "link1": 0.16130, "link2": 1.32660, "link3": 0.83530,
        "link4": 0.52000, "link5": 0.38300, "link6": 0.36630,
        "gripper_link": 0.181800159145243, "gripper_left": 0.0423278952416158,
        "gripper_right": 0.0423278949561274}


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
    v = np.asarray(v, float); th = np.linalg.norm(v)
    return np.eye(3) if th < 1e-12 else arot(v/th, th)


HULL, NF, SRCH = {}, {}, {}
for f in sorted(os.listdir(MESH)):
    if f.lower().endswith(".stl"):
        m = trimesh.load_mesh(os.path.join(MESH, f), process=False)
        HULL[f[:-4]] = np.asarray(m.convex_hull.vertices, float)*1000.0
        NF[f[:-4]] = len(m.faces)
        SRCH[f[:-4]] = sha(os.path.join(MESH, f))

# ---------------- 3. component truth table ----------------
rows = []
for n in FULL:
    j = next((x for x in JOINTS if x[0] == n), None)
    fx = next((x for x in FIXED if x[0] == n), None)
    parent = j[1] if j else (fx[1] if fx else None)
    jtype = j[5] if j else (fx[4] if fx else "root")
    lim = f"[{j[6]}, {j[7]}]" if j else ("[0, 0.0715] m" if jtype == "prismatic" else "-")
    rows.append(dict(component_id=n, group=GROUP[n],
                     source_file=f"meshes_b601_gripper/{n}.STL", source_sha256=SRCH[n],
                     authority="ACCEPTED_URDF_L0", kinematic_parent=parent, joint_type=jtype,
                     joint_limits=lim, geometry="convex hull of accepted STL",
                     hull_vertices=len(HULL[n]), source_faces=NF[n],
                     mass_kg=MASS[n], mass_ownership="accepted URDF (immutable)",
                     included_in_links1_6=n in LINKS16, included_in_fullarm=True,
                     missing_geometry=False))
for pid, grp, note in [("M3R_STAGE_A_RING", "BASE_FIXED_SYSTEM", "interface ring; no local B-rep in this package"),
                       ("M3R_STAGE_B_DIFFUSION", "BASE_FIXED_SYSTEM", "load diffusion plate; geometry not present"),
                       ("HDRM_ROOT", "STOW_SYSTEM", "primary root restraint; not selected"),
                       ("HDRM_DISTAL", "STOW_SYSTEM", "distal stow restraint; not selected"),
                       ("STOW_SADDLE_A", "STOW_SYSTEM", "support saddle; placeholder only"),
                       ("STOW_SADDLE_B", "STOW_SYSTEM", "support saddle; placeholder only"),
                       ("HARNESS_TRUNK", "STOW_SYSTEM", "Route-C authority only; no stowed CAD"),
                       ("CONNECTOR_SET", "STOW_SYSTEM", "not modelled")]:
    rows.append(dict(component_id=pid, group=grp, source_file="", source_sha256="",
                     authority="MISSING_GEOMETRY_HOLD", kinematic_parent="", joint_type="",
                     joint_limits="", geometry="DESIGN_PROXY_NOT_FLIGHT_GEOMETRY", hull_vertices=0,
                     source_faces=0, mass_kg=None, mass_ownership="UNKNOWN",
                     included_in_links1_6=False, included_in_fullarm=False, missing_geometry=True,
                     note=note))
with open(os.path.join(OUT, "A3_43_COMPONENT_TRUTH_TABLE.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) + ["note"], extrasaction="ignore")
    w.writeheader(); w.writerows(rows)
nmiss = sum(1 for r in rows if r["missing_geometry"])
print(f"component truth table: {len(rows)} rows, {nmiss} MISSING_GEOMETRY_HOLD")

# ---------------- 4/5. deterministic FULLARM for all five candidates ----------------
CAND = {"CAND_0_THIN": (0.0, "THIN"), "CAND_2_FIT": (2.0, "FIT"), "CAND_2_THIN": (2.0, "THIN"),
        "CAND_3_THIN": (3.0, "THIN"), "CAND_5_THIN": (5.0, "THIN")}


def place_full(q_deg, rv, names, T=None):
    q = np.radians(q_deg); R = rotvec(rv)
    Tw = {"base_link": np.eye(4)}
    for i, (c, p, x, rr, ax, jt, lo, hi) in enumerate(JOINTS):
        Tw[c] = Tw[p] @ (Tm(x, rpy(*rr)) @ Tm((0, 0, 0), arot(ax, q[i])))
    for c, p, x, rr, jt in FIXED:
        Tw[c] = Tw[p] @ Tm(x, rpy(*rr))
    pl = {n: (HULL[n] @ Tw[n][:3, :3].T + Tw[n][:3, 3]*1000.0) @ R.T for n in names}
    P = np.vstack(list(pl.values()))
    c0 = (P.max(0) + P.min(0))/2
    off = (np.zeros(3) if T is None else np.asarray(T, float))
    return {n: v - c0 + off for n, v in pl.items()}, Tw


summary = {}
extrema_rows = []
for cid, (mg, md) in CAND.items():
    src = next(r for r in A2C["results"] if r["link_set"] == "CORRIDOR"
               and r["margin_deg"] == mg and r["mode"] == md)
    pl16, _ = place_full(src["q_deg"], src["mount_rotvec"], LINKS16)
    plF, _ = place_full(src["q_deg"], src["mount_rotvec"], FULL)
    P16 = np.vstack(list(pl16.values())); PF = np.vstack(list(plF.values()))
    e16, eF = P16.max(0)-P16.min(0), PF.max(0)-PF.min(0)
    summary[cid] = dict(margin_deg=mg, mode=md, distal_state="G0_AUTHORIZED_CURRENT_STATE",
                        links16_extents_XYZ=e16.tolist(), fullarm_extents_XYZ=eF.tolist(),
                        growth_XYZ=(eF-e16).tolist())
    # extrema attribution
    for ax, an in enumerate("XYZ"):
        for which, fn in (("MIN", np.argmin), ("MAX", np.argmax)):
            best, bn, bi = None, None, None
            for n, v in plF.items():
                k = fn(v[:, ax]); val = v[k, ax]
                if best is None or (val < best if which == "MIN" else val > best):
                    best, bn, bi = float(val), n, int(k)
            extrema_rows.append([cid, f"{an}_{which}", f"{best:.4f}", bn, GROUP[bn],
                                 f"hull_vertex_{bi}", f"{plF[bn][bi][0]:.2f}"])
print(f"\nFULLARM deterministic evaluation: {len(summary)}/5 candidates "
      f"(3deg and 5deg gaps from A3.2c now filled)")
for cid, s in summary.items():
    print(f"  {cid:<13} links1-6 {np.round(s['links16_extents_XYZ'],1)}  "
          f"FULLARM {np.round(s['fullarm_extents_XYZ'],1)}  growth {np.round(s['growth_XYZ'],1)}")

with open(os.path.join(OUT, "A3_40_FULLARM_EXTREMA_ATTRIBUTION.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["candidate", "extremum", "coordinate_mm", "component", "group", "vertex_id", "station_x_mm"])
    w.writerows(extrema_rows)

# ---------------- 6. station-wise envelope for PRIMARY ----------------
PRI = HAND["selected_candidate"]
src = next(r for r in A2C["results"] if r["link_set"] == "CORRIDOR"
           and r["margin_deg"] == summary[PRI]["margin_deg"] and r["mode"] == summary[PRI]["mode"])
plF, _ = place_full(src["q_deg"], src["mount_rotvec"], FULL)
PF = np.vstack(list(plF.values()))
own = np.concatenate([[i]*len(v) for i, v in enumerate(plF.values())])
NAMES = list(plF.keys())

x0, x1 = PF[:, 0].min(), PF[:, 0].max()
edges = np.arange(np.floor(x0), np.ceil(x1)+STATION, STATION)
st_rows, st = [], []
for i in range(len(edges)-1):
    m = (PF[:, 0] >= edges[i]) & (PF[:, 0] < edges[i+1])
    if m.sum() < 1:
        continue
    S, ow = PF[m], own[m]
    ymin, ymax = S[:, 1].min(), S[:, 1].max()
    zmin, zmax = S[:, 2].min(), S[:, 2].max()
    r_ymin = NAMES[ow[int(np.argmin(S[:, 1]))]]; r_ymax = NAMES[ow[int(np.argmax(S[:, 1]))]]
    r_zmin = NAMES[ow[int(np.argmin(S[:, 2]))]]; r_zmax = NAMES[ow[int(np.argmax(S[:, 2]))]]
    comps = sorted({NAMES[k] for k in np.unique(ow)})
    st.append((float(edges[i]), ymin, ymax, zmin, zmax))
    st_rows.append([f"{edges[i]:.1f}", f"{ymin:.3f}", f"{ymax:.3f}", f"{zmin:.3f}", f"{zmax:.3f}",
                    f"{ymax-ymin:.3f}", f"{zmax-zmin:.3f}", r_ymin, r_ymax, r_zmin, r_zmax,
                    "|".join(comps)])
with open(os.path.join(OUT, "A3_41_FULLARM_STATION_ENVELOPE.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["station_mm", "Y_min", "Y_max", "Z_min", "Z_max", "width_Y", "width_Z",
                "responsible_Y_min", "responsible_Y_max", "responsible_Z_min", "responsible_Z_max",
                "component_set_at_station"])
    w.writerows(st_rows)

wy = np.array([s[2]-s[1] for s in st]); wz = np.array([s[4]-s[3] for s in st])
xs = np.array([s[0] for s in st])
gy, gz = PF[:, 1].max()-PF[:, 1].min(), PF[:, 2].max()-PF[:, 2].min()
locally_realised = bool(np.any((wy > 0.98*gy) & (wz > 0.98*gz)))

print(f"\nPRIMARY {PRI} station envelope: {len(st)} stations at {STATION} mm")
print(f"  global  Y span {gy:.1f}   Z span {gz:.1f}")
print(f"  max local width_Y {wy.max():.1f} @ x={xs[int(np.argmax(wy))]:.0f}")
print(f"  max local width_Z {wz.max():.1f} @ x={xs[int(np.argmax(wz))]:.0f}")
print(f"  any station reaching both simultaneously (>=98%): {locally_realised}")
print(f"  GLOBAL_AABB_{gy:.0f}x{gz:.0f}_IS_"
      f"{'' if locally_realised else 'NOT_'}LOCALLY_REALIZED")

json.dump(dict(schema="A3_4_PART1_V1", primary=PRI,
               upstream=dict(a3_3_gate=GATE3["gate"], handoff=HAND["selected_candidate"]),
               candidates=summary,
               station_analysis=dict(n_stations=len(st), spacing_mm=STATION,
                                     global_Y_span_mm=float(gy), global_Z_span_mm=float(gz),
                                     max_local_width_Y_mm=float(wy.max()),
                                     max_local_width_Y_station_mm=float(xs[int(np.argmax(wy))]),
                                     max_local_width_Z_mm=float(wz.max()),
                                     max_local_width_Z_station_mm=float(xs[int(np.argmax(wz))]),
                                     global_aabb_locally_realized=locally_realised,
                                     verdict=("GLOBAL_AABB_LOCALLY_REALIZED" if locally_realised
                                              else "GLOBAL_AABB_OVERSTATES_LOCAL_PACKAGING_DEMAND"))),
          open(os.path.join(OUT, "_a3_4_part1.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
np.save(os.path.join(OUT, "_primary_station.npy"), np.array(st))
print("\nwrote", OUT)
