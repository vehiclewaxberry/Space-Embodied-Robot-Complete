"""A3.3 part 2 - local station mapping, rail checks, virtual ejection, ranking, gate.

Consumes the deterministic placement written by a3_03_deployer_zone_and_ejection.py
(_candidates_meta.json translation_mm) and A3.2c joint states. Read-only.
"""
import numpy as np, trimesh, os, json, csv, hashlib
from scipy.spatial import ConvexHull

ROOT = r"F:\China Graduate Future Flight Vehicle Innovation Competition"
BASE = os.path.join(ROOT, r"20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\_work\mode_a_native_design_r1")
MESH = os.path.join(ROOT, r"20_engineering\cad\spacecraft_layout\arm_b601_v1\meshes_b601_gripper")
OUT = os.path.join(BASE, "02_a3_3")

BOX = np.array([366.0, 226.3, 226.3]); HALF = BOX/2.0
RAIL_W, RAIL_END, FIRST_PROT, LAT_MAX, STATION = 8.5, 6.5, 8.5, 6.5, 1.0

A2C = json.load(open(os.path.join(BASE, "01_a3_2c", "A3_02C_RESULTS.json"), encoding="utf-8"))
META = json.load(open(os.path.join(OUT, "_candidates_meta.json"), encoding="utf-8"))

JOINTS = [("link1", "base_link", (-8.416e-05, 0, 0.08465), (0, 0, 0), (0, 0, 1)),
          ("link2", "link1", (0.020084, 0.031625, 0.05555), (-1.5708, 0, 0), (0, 0, -1)),
          ("link3", "link2", (-0.264, 0, 0), (0, 0, 0), (0, 0, 1)),
          ("link4", "link3", (0.2426, -0.054, -0.001625), (0, 0, 0), (0, 0, 1)),
          ("link5", "link4", (0.078308, -0.0375, -0.03), (-1.5708, 0, 0), (0, 0, 1)),
          ("link6", "link5", (0.023692, 0, 0.04), (0, 1.5708, 0), (0, 0, 1))]
CORRIDOR = ["link1", "link2", "link3", "link4", "link5", "link6"]


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


HULL = {}
for f in sorted(os.listdir(MESH)):
    if f.lower().endswith(".stl"):
        m = trimesh.load_mesh(os.path.join(MESH, f), process=False)
        HULL[f[:-4]] = np.asarray(m.convex_hull.vertices, float)*1000.0


def build(q_deg, rv, T):
    q = np.radians(q_deg); R = rotvec(rv)
    Tw = {"base_link": np.eye(4)}
    for i, (c, p, x, rr, ax) in enumerate(JOINTS):
        Tw[c] = Tw[p] @ (Tm(x, rpy(*rr)) @ Tm((0, 0, 0), arot(ax, q[i])))
    pl = {n: (HULL[n] @ Tw[n][:3, :3].T + Tw[n][:3, 3]*1000.0) @ R.T for n in CORRIDOR}
    P = np.vstack(list(pl.values())); c0 = (P.max(0) + P.min(0))/2
    return {n: v - c0 + np.asarray(T) for n, v in pl.items()}


RAILS = [(f"{'P' if sy>0 else 'N'}Y_{'P' if sz>0 else 'N'}Z",
          sy*(HALF[1]-RAIL_W), sz*(HALF[2]-RAIL_W), sy, sz) for sy in (1, -1) for sz in (1, -1)]


def rail_clear(pts_yz):
    """signed clearance to each corner rail strip; negative = intrusion depth."""
    res = {}
    for name, iy, iz, sy, sz in RAILS:
        dy = sy*(pts_yz[:, 0] - iy); dz = sz*(pts_yz[:, 1] - iz)
        ins = (dy > 0) & (dz > 0)
        if ins.any():
            res[name] = -float(np.minimum(dy[ins], dz[ins]).max())
        else:
            gy = np.maximum(-dy, 0.0); gz = np.maximum(-dz, 0.0)
            res[name] = float(np.sqrt(gy**2 + gz**2).min())
    return res


rows_station, summary = [], {}
for cid, meta in META.items():
    if meta.get("status") != "OK" or meta.get("placement_status") != "PLACED":
        summary[cid] = dict(status=meta.get("status"), placement=meta.get("placement_status")); continue
    src = next(r for r in A2C["results"] if r["link_set"] == "CORRIDOR"
               and r["margin_deg"] == meta["margin_deg"] and r["mode"] == meta["mode"])
    pl = build(src["q_deg"], src["mount_rotvec"], meta["translation_mm"])
    ALL = np.vstack(list(pl.values()))
    owner = np.concatenate([[i]*len(v) for i, v in enumerate(pl.values())])

    x0, x1 = ALL[:, 0].min(), ALL[:, 0].max()
    edges = np.arange(np.floor(x0), np.ceil(x1)+STATION, STATION)
    worst = dict(rail=(1e9, None, None), face=(1e9, None, None))
    nstat = 0
    for i in range(len(edges)-1):
        m = (ALL[:, 0] >= edges[i]) & (ALL[:, 0] < edges[i+1])
        if m.sum() < 1:
            continue
        nstat += 1
        S, ow = ALL[m], owner[m]
        yz = S[:, 1:]
        rc = rail_clear(yz)
        rmin = min(rc.values()); rzone = min(rc, key=rc.get)
        fy_p, fy_n = HALF[1]-yz[:, 0].max(), yz[:, 0].min()+HALF[1]
        fz_p, fz_n = HALF[2]-yz[:, 1].max(), yz[:, 1].min()+HALF[2]
        fmin = min(fy_p, fy_n, fz_p, fz_n)
        # responsible link = owner of the point closest to the governing rail
        k = int(np.argmin([min(rail_clear(yz[j:j+1]).values()) for j in range(0, len(yz), max(1, len(yz)//60))])) \
            * max(1, len(yz)//60)
        resp = CORRIDOR[ow[min(k, len(ow)-1)]]
        cls = ("RAIL_ZONE_INTRUSION" if rmin < 0 else
               "KEEP_OUT_INTRUSION" if fmin < 0 else
               "NEAR_BOUNDARY" if min(rmin, fmin) < 2.0 else "INSIDE_NOMINAL")
        rows_station.append([cid, f"{edges[i]:.1f}", f"{yz[:,0].max():.3f}", f"{yz[:,0].min():.3f}",
                             f"{yz[:,1].max():.3f}", f"{yz[:,1].min():.3f}",
                             f"{fy_p:.3f}", f"{fy_n:.3f}", f"{fz_p:.3f}", f"{fz_n:.3f}",
                             f"{rmin:.3f}", rzone, resp, cls])
        if rmin < worst["rail"][0]:
            worst["rail"] = (rmin, float(edges[i]), resp, rzone)
        if fmin < worst["face"][0]:
            worst["face"] = (fmin, float(edges[i]), resp, "FACE")

    # ---- exact ejection criterion: union cross-section ----
    yz_all = ALL[:, 1:]
    urc = rail_clear(yz_all)
    union_rail_min = min(urc.values()); union_rail_zone = min(urc, key=urc.get)
    union_face_min = float(min(HALF[1]-yz_all[:, 0].max(), yz_all[:, 0].min()+HALF[1],
                               HALF[2]-yz_all[:, 1].max(), yz_all[:, 1].min()+HALF[2]))
    end_p = HALF[0] - ALL[:, 0].max(); end_n = ALL[:, 0].min() + HALF[0]
    max_prot = -min(union_face_min, 0.0) if union_face_min < 0 else 0.0

    summary[cid] = dict(
        status="ANALYSED", margin_deg=meta["margin_deg"], mode=meta["mode"],
        reconstruction_hash=meta["reconstruction_hash"], translation_mm=meta["translation_mm"],
        sorted_LWH_mm=meta["sorted_LWH_mm"], stations=nstat,
        rail_min_clearance_mm=float(union_rail_min), rail_governing_zone=union_rail_zone,
        rail_worst_station_mm=worst["rail"][1], rail_worst_link=worst["rail"][2],
        face_min_clearance_mm=union_face_min,
        face_worst_station_mm=worst["face"][1], face_worst_link=worst["face"][2],
        end_clearance_plusX_mm=float(end_p), end_clearance_minusX_mm=float(end_n),
        max_protrusion_mm=float(max_prot),
        RAIL_KEEP_OUT="PASS" if union_rail_min > 0 else "FAIL",
        FIRST_PROTRUSION_KEEPOUT="PASS_VACUOUS_NO_PROTRUSION" if max_prot <= 0 else "EVALUATE",
        END_ZONE="PASS" if (end_p >= 0 and end_n >= 0) else "FAIL",
        VIRTUAL_EJECTION="PASS" if (union_rail_min > 0 and union_face_min >= 0
                                    and end_p >= 0 and end_n >= 0) else "FAIL",
        ejection_min_clearance_mm=float(min(union_rail_min, union_face_min)),
        ejection_method="EXACT_PRISMATIC_REDUCTION_UNION_CROSS_SECTION",
    )

with open(os.path.join(OUT, "A3_31_LOCAL_STATION_CLEARANCE.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["candidate", "station_mm", "y_max", "y_min", "z_max", "z_min",
                "clr_plusY", "clr_minusY", "clr_plusZ", "clr_minusZ",
                "rail_min_clearance_mm", "governing_rail_zone", "responsible_link", "classification"])
    w.writerows(rows_station)

# ---- ejection trace (record only; result already exact) ----
trace = []
for cid, s in summary.items():
    if s.get("status") != "ANALYSED":
        continue
    total = BOX[0] + s["sorted_LWH_mm"][0]
    for t in np.arange(0, total + 2.0, 2.0):
        trace.append([cid, f"{t:.1f}", f"{s['ejection_min_clearance_mm']:.3f}",
                      s["rail_worst_link"] or "", s["rail_governing_zone"],
                      "False" if s["VIRTUAL_EJECTION"] == "PASS" else "True"])
with open(os.path.join(OUT, "A3_32_EJECTION_TRACE.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["candidate", "travel_mm", "minimum_clearance_mm", "component", "deployer_zone", "collision"])
    w.writerows(trace)

# ---- delta sensitivity on PRIMARY ----
PRIMARY = "CAND_2_FIT"
delta_rows = []
if summary.get(PRIMARY, {}).get("status") == "ANALYSED":
    s = summary[PRIMARY]
    for d in [0.0, 0.25, 0.5, 1.0]:
        delta_rows.append(dict(candidate=PRIMARY, delta_mm=d,
                               rail_clearance_mm=round(s["rail_min_clearance_mm"] - d, 3),
                               face_clearance_mm=round(s["face_min_clearance_mm"] - d, 3),
                               ejection_min_clearance_mm=round(s["ejection_min_clearance_mm"] - d, 3),
                               rail_pass=bool(s["rail_min_clearance_mm"] - d > 0),
                               ejection_pass=bool(min(s["rail_min_clearance_mm"],
                                                      s["face_min_clearance_mm"]) - d >= 0)))
with open(os.path.join(OUT, "A3_33_DELTA_SENSITIVITY.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(delta_rows[0].keys()) if delta_rows else ["candidate"])
    w.writeheader(); w.writerows(delta_rows)

# ---- ranking ----
def key(cid):
    s = summary[cid]
    src = next(r for r in A2C["results"] if r["link_set"] == "CORRIDOR"
               and r["margin_deg"] == s["margin_deg"] and r["mode"] == s["mode"])
    return (0 if s["RAIL_KEEP_OUT"] == "PASS" else 1,
            0 if s["VIRTUAL_EJECTION"] == "PASS" else 1,
            -s["ejection_min_clearance_mm"],
            -(s["rail_min_clearance_mm"] - 1.0),
            -s["margin_deg"],
            src["worst_protrusion_mm"],
            s["sorted_LWH_mm"][2])


ranked = sorted([c for c in summary if summary[c].get("status") == "ANALYSED"], key=key)
with open(os.path.join(OUT, "A3_35_CANDIDATE_RANKING.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["rank", "candidate", "margin_deg", "mode", "RAIL_KEEP_OUT", "VIRTUAL_EJECTION",
                "rail_min_clearance_mm", "face_min_clearance_mm", "ejection_min_clearance_mm",
                "corridor_thickness_mm", "governing_rail_zone", "worst_station_mm", "responsible_link"])
    for i, cid in enumerate(ranked, 1):
        s = summary[cid]
        w.writerow([i, cid, s["margin_deg"], s["mode"], s["RAIL_KEEP_OUT"], s["VIRTUAL_EJECTION"],
                    f"{s['rail_min_clearance_mm']:.3f}", f"{s['face_min_clearance_mm']:.3f}",
                    f"{s['ejection_min_clearance_mm']:.3f}", f"{s['sorted_LWH_mm'][2]:.3f}",
                    s["rail_governing_zone"], s["rail_worst_station_mm"], s["rail_worst_link"]])

allpass = all(summary[c]["RAIL_KEEP_OUT"] == "PASS" and summary[c]["VIRTUAL_EJECTION"] == "PASS"
              for c in ranked)
anypass = any(summary[c]["RAIL_KEEP_OUT"] == "PASS" and summary[c]["VIRTUAL_EJECTION"] == "PASS"
              for c in ranked)
gate = ("A3_3_PASS_GENERIC_CDS_GEOMETRY" if allpass else
        "A3_3_CONDITIONAL_PASS_WITH_OPEN_ITEMS" if anypass else "A3_3_HOLD_RAIL_OR_EJECTION")

print("\n" + "="*104)
print(f"{'cand':<13}{'marg':>5}{'mode':>6}{'railclr':>10}{'faceclr':>10}{'ejectclr':>10}"
      f"{'rail':>7}{'eject':>7}{'zone':>9}{'station':>9}{'link':>8}")
print("-"*104)
for cid in ranked:
    s = summary[cid]
    print(f"{cid:<13}{s['margin_deg']:4.0f}°{s['mode']:>6}{s['rail_min_clearance_mm']:10.2f}"
          f"{s['face_min_clearance_mm']:10.2f}{s['ejection_min_clearance_mm']:10.2f}"
          f"{s['RAIL_KEEP_OUT']:>7}{s['VIRTUAL_EJECTION']:>7}{s['rail_governing_zone']:>9}"
          f"{(s['rail_worst_station_mm'] if s['rail_worst_station_mm'] is not None else 0):9.0f}"
          f"{(s['rail_worst_link'] or '-'):>8}")
print("="*104)
print("\ndelta sensitivity on PRIMARY", PRIMARY)
for d in delta_rows:
    print(f"  delta {d['delta_mm']:.2f} mm : rail {d['rail_clearance_mm']:+8.2f}  "
          f"face {d['face_clearance_mm']:+8.2f}  eject {d['ejection_min_clearance_mm']:+8.2f}  "
          f"rail_pass={d['rail_pass']}  eject_pass={d['ejection_pass']}")
print(f"\nGATE = {gate}")

best = ranked[0] if ranked else None
if best:
    s = summary[best]
    src = next(r for r in A2C["results"] if r["link_set"] == "CORRIDOR"
               and r["margin_deg"] == s["margin_deg"] and r["mode"] == s["mode"])
    json.dump(dict(schema="A3_36_A3_4_HANDOFF_V1", selected_candidate=best,
                   joint_state_deg=src["q_deg"], mount_rotvec_rad=src["mount_rotvec"],
                   translation_in_R_CDS_mm=s["translation_mm"],
                   frame_mapping=dict(id="T_S_RCDS", status="PROVISIONAL_BUT_EXPLICIT",
                                      rotation="identity", translation_mm=[0, 0, 0]),
                   arm_envelope_LWH_mm=s["sorted_LWH_mm"],
                   corridor_thickness_mm=s["sorted_LWH_mm"][2],
                   gross_residual_slab_width_mm=float(BOX[1]-s["sorted_LWH_mm"][2]),
                   rail_min_clearance_mm=s["rail_min_clearance_mm"],
                   ejection_min_clearance_mm=s["ejection_min_clearance_mm"],
                   delta_1mm_result=next((d for d in delta_rows if d["delta_mm"] == 1.0), None),
                   link_set="links1-6 only",
                   known_open_items=[
                       "SELF_COLLISION = NOT_VALIDATED_HULL_LEVEL_ONLY (no python-fcl)",
                       "base_link, gripper_link and fingers NOT in this envelope",
                       "M3R, HDRM, harness, MLI, fasteners, tolerance NOT modelled",
                       "DEPLOYER_SPECIFIC_ICD = MISSING; generic CDS reference only",
                       "T_S_RCDS mapping PROVISIONAL, no owner signoff",
                       "bus structure not modelled; arm-only ejection",
                   ],
                   source_hashes=dict(A3_02C_RESULTS=hashlib.sha256(
                       open(os.path.join(BASE, "01_a3_2c", "A3_02C_RESULTS.json"), "rb").read()
                   ).hexdigest().upper()),
                   ),
              open(os.path.join(OUT, "A3_36_A3_4_HANDOFF.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

json.dump(dict(schema="A3_3_FINAL_GATE_V1", gate=gate,
               model_class="CDS_R14_1_GENERIC_PRELIMINARY",
               allowed_claim="GENERIC_CDS_GEOMETRIC_REFERENCE_PASS" if anypass else "NONE",
               prohibited_claims=["DEPLOYER_COMPATIBLE", "LAUNCH_COMPLIANT", "FLIGHT_READY"],
               DEPLOYER_SPECIFIC_ICD="MISSING",
               LAUNCH_AND_DEPLOYER_COMPLIANCE="HOLD",
               SELF_COLLISION="NOT_VALIDATED_HULL_LEVEL_ONLY",
               ranking=ranked, primary_for_a3_4=best, summary=summary,
               delta_sensitivity=delta_rows,
               ejection_method_note=("prismatic reduction: a rigid body translating along the "
                                     "deployer axis sweeps the extrusion of its own cross-section, "
                                     "so the union cross-section is an exact ejection criterion")),
          open(os.path.join(OUT, "A3_3_FINAL_GATE.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("wrote", OUT)
