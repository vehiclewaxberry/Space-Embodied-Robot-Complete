"""A3.4 part 2 - zone partition, pocket requirements, full-system CDS recheck,
architecture trade, gate, A3.5 handoff.

Consumes part 1 outputs. No joint angle is re-optimised anywhere in A3.4.
"""
import numpy as np, trimesh, os, json, csv, hashlib, importlib

ROOT = r"F:\China Graduate Future Flight Vehicle Innovation Competition"
BASE = os.path.join(ROOT, r"20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\_work\mode_a_native_design_r1")
MESH = os.path.join(ROOT, r"20_engineering\cad\spacecraft_layout\arm_b601_v1\meshes_b601_gripper")
OUT = os.path.join(BASE, "03_a3_4")

BOX = np.array([366.0, 226.3, 226.3]); HALF = BOX/2.0
RAIL_W = 8.5

P1 = json.load(open(os.path.join(OUT, "_a3_4_part1.json"), encoding="utf-8"))
A2C = json.load(open(os.path.join(BASE, "01_a3_2c", "A3_02C_RESULTS.json"), encoding="utf-8"))
HAND3 = json.load(open(os.path.join(BASE, "02_a3_3", "A3_36_A3_4_HANDOFF.json"), encoding="utf-8"))
PRI = P1["primary"]

JOINTS = [("link1", "base_link", (-8.416e-05, 0, 0.08465), (0, 0, 0), (0, 0, 1)),
          ("link2", "link1", (0.020084, 0.031625, 0.05555), (-1.5708, 0, 0), (0, 0, -1)),
          ("link3", "link2", (-0.264, 0, 0), (0, 0, 0), (0, 0, 1)),
          ("link4", "link3", (0.2426, -0.054, -0.001625), (0, 0, 0), (0, 0, 1)),
          ("link5", "link4", (0.078308, -0.0375, -0.03), (-1.5708, 0, 0), (0, 0, 1)),
          ("link6", "link5", (0.023692, 0, 0.04), (0, 1.5708, 0), (0, 0, 1))]
FIXED = [("gripper_link", "link6", (0, 0, 0.15971), (0, -1.5708, 0)),
         ("gripper_left", "gripper_link", (-0.042091, 2.7531e-05, -1.3031e-05), (0, 0, -1.5708)),
         ("gripper_right", "gripper_link", (-0.042091, -2.7531e-05, 1.3031e-05), (0, 0, 1.5708))]
LINKS16 = ["link1", "link2", "link3", "link4", "link5", "link6"]
DISTAL = ["gripper_link", "gripper_left", "gripper_right"]
FULL = ["base_link"] + LINKS16 + DISTAL


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


HULL = {f[:-4]: np.asarray(trimesh.load_mesh(os.path.join(MESH, f), process=False).convex_hull.vertices,
                           float)*1000.0 for f in os.listdir(MESH) if f.lower().endswith(".stl")}

src = next(r for r in A2C["results"] if r["link_set"] == "CORRIDOR"
           and r["margin_deg"] == P1["candidates"][PRI]["margin_deg"]
           and r["mode"] == P1["candidates"][PRI]["mode"])
q = np.radians(src["q_deg"]); R = rotvec(src["mount_rotvec"])
Tw = {"base_link": np.eye(4)}
for i, (c, p, x, rr, ax) in enumerate(JOINTS):
    Tw[c] = Tw[p] @ (Tm(x, rpy(*rr)) @ Tm((0, 0, 0), arot(ax, q[i])))
for c, p, x, rr in FIXED:
    Tw[c] = Tw[p] @ Tm(x, rpy(*rr))
PL = {n: (HULL[n] @ Tw[n][:3, :3].T + Tw[n][:3, 3]*1000.0) @ R.T for n in FULL}
PF = np.vstack(list(PL.values()))
PL = {n: v - (PF.max(0)+PF.min(0))/2 for n, v in PL.items()}
PF = np.vstack(list(PL.values()))

xr = {n: (float(v[:, 0].min()), float(v[:, 0].max())) for n, v in PL.items()}
print("component X ranges (mm):")
for n in FULL:
    print(f"  {n:<14}{xr[n][0]:9.1f} .. {xr[n][1]:9.1f}   len {xr[n][1]-xr[n][0]:7.1f}")

# ---------------- 7. zone partition ----------------
bx = xr["base_link"]; dx = (min(xr[n][0] for n in DISTAL), max(xr[n][1] for n in DISTAL))
ax16 = (min(xr[n][0] for n in LINKS16), max(xr[n][1] for n in LINKS16))
ZONES = [dict(zone="ROOT_BASE_BAY", x_start=bx[0], x_end=bx[1], driver="base_link"),
         dict(zone="DISTAL_STOW_BAY", x_start=dx[0], x_end=dx[1], driver="gripper system"),
         dict(zone="ARM_CORRIDOR", x_start=ax16[0], x_end=ax16[1], driver="links1-6")]
for z in ZONES:
    m = (PF[:, 0] >= z["x_start"]) & (PF[:, 0] <= z["x_end"])
    S = PF[m]
    z.update(max_Y_occupancy_mm=float(S[:, 1].max()-S[:, 1].min()),
             max_Z_occupancy_mm=float(S[:, 2].max()-S[:, 2].min()),
             length_mm=float(z["x_end"]-z["x_start"]))
print("\nzone partition:")
for z in ZONES:
    print(f"  {z['zone']:<18} x [{z['x_start']:7.1f}, {z['x_end']:7.1f}]  len {z['length_mm']:6.1f}"
          f"   maxY {z['max_Y_occupancy_mm']:6.1f}  maxZ {z['max_Z_occupancy_mm']:6.1f}   ({z['driver']})")
overlap = max(0.0, min(bx[1], dx[1]) - max(bx[0], dx[0]))
print(f"  ROOT_BASE_BAY / DISTAL_STOW_BAY axial overlap = {overlap:.1f} mm  "
      f"{'<-- co-located, this is the Y-width driver' if overlap > 0 else ''}")

# ---------------- 12. pocket requirements ----------------
st = np.load(os.path.join(OUT, "_primary_station.npy"))
wy = st[:, 2]-st[:, 1]; wz = st[:, 4]-st[:, 3]; xs = st[:, 0]
CORR_T = 80.3
pockets, prows = [], []
over = xs[wy > CORR_T]
if len(over):
    # contiguous runs where the Y demand exceeds the corridor thickness
    runs, s0 = [], over[0]
    for a, b in zip(over[:-1], over[1:]):
        if b - a > 2.0:
            runs.append((s0, a)); s0 = b
    runs.append((s0, over[-1]))
    for i, (a, b) in enumerate(runs, 1):
        m = (xs >= a) & (xs <= b)
        prows.append(dict(pocket_id=f"POCKET_{i}", x_start_mm=float(a), x_end_mm=float(b),
                          x_interval_mm=float(b-a+1),
                          required_Y_depth_mm=float(wy[m].max()),
                          required_Z_depth_mm=float(wz[m].max()),
                          extra_Y_over_corridor_mm=float(wy[m].max()-CORR_T),
                          responsible=("base_link + gripper" if a < 0 else "links"),
                          exceeds_226p3=bool(wy[m].max() > 226.3)))
with open(os.path.join(OUT, "A3_46_LOCAL_POCKET_REQUIREMENTS.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(prows[0].keys()) if prows else ["pocket_id"])
    w.writeheader(); w.writerows(prows)
print(f"\nlocal pockets required (Y demand > {CORR_T} mm corridor): {len(prows)}")
for p in prows:
    print(f"  {p['pocket_id']}: x [{p['x_start_mm']:7.1f},{p['x_end_mm']:7.1f}] "
          f"len {p['x_interval_mm']:6.1f}  needs Y {p['required_Y_depth_mm']:6.1f} "
          f"(+{p['extra_Y_over_corridor_mm']:5.1f})  >226.3={p['exceeds_226p3']}")

vol_corr = CORR_T*226.3*float(xs.max()-xs.min())/1e3
vol_extra = sum(p["extra_Y_over_corridor_mm"]*226.3*p["x_interval_mm"] for p in prows)/1e3
vol_mono = float(PF[:, 1].max()-PF[:, 1].min())*float(PF[:, 2].max()-PF[:, 2].min())*float(xs.max()-xs.min())/1e3
print(f"\n  ARM_CORRIDOR baseline void   {vol_corr:9.1f} cm3")
print(f"  pocket additional void       {vol_extra:9.1f} cm3")
print(f"  piecewise total              {vol_corr+vol_extra:9.1f} cm3")
print(f"  monolithic global-AABB void  {vol_mono:9.1f} cm3   "
      f"({vol_mono/(vol_corr+vol_extra):.2f}x the piecewise cost)")

# ---------------- 16. full-system generic CDS recheck ----------------
RAILS = [(f"{'P' if sy>0 else 'N'}Y_{'P' if sz>0 else 'N'}Z", sy*(HALF[1]-RAIL_W), sz*(HALF[2]-RAIL_W), sy, sz)
         for sy in (1, -1) for sz in (1, -1)]


def rail_clear(yz):
    out = {}
    for nme, iy, iz, sy, sz in RAILS:
        dy = sy*(yz[:, 0]-iy); dz = sz*(yz[:, 1]-iz); ins = (dy > 0) & (dz > 0)
        out[nme] = (-float(np.minimum(dy[ins], dz[ins]).max()) if ins.any()
                    else float(np.sqrt(np.maximum(-dy, 0)**2 + np.maximum(-dz, 0)**2).min()))
    return out


yz = PF[:, 1:]
rc = rail_clear(yz); rail_min = min(rc.values())
face = dict(pY=HALF[1]-yz[:, 0].max(), nY=yz[:, 0].min()+HALF[1],
            pZ=HALF[2]-yz[:, 1].max(), nZ=yz[:, 1].min()+HALF[2])
endc = dict(pX=HALF[0]-PF[:, 0].max(), nX=PF[:, 0].min()+HALF[0])
face_min = float(min(face.values())); end_min = float(min(endc.values()))
recheck = dict(schema="A3_42_FULL_SYSTEM_CDS_RECHECK_V1", candidate=PRI,
               object="FULL_STOWED_ARM_SYSTEM (base_link + links1-6 + gripper_link + 2 fingers)",
               fullarm_extents_XYZ_mm=(PF.max(0)-PF.min(0)).tolist(),
               rail_min_clearance_mm=float(rail_min), rail_governing=min(rc, key=rc.get),
               face_clearances_mm={k: float(v) for k, v in face.items()}, face_min_clearance_mm=face_min,
               end_clearances_mm={k: float(v) for k, v in endc.items()}, end_min_clearance_mm=end_min,
               RAIL_KEEP_OUT="PASS" if rail_min > 0 else "FAIL",
               LATERAL_ENVELOPE="PASS" if face_min >= 0 else "FAIL",
               END_ZONE="PASS" if end_min >= 0 else "FAIL",
               GENERIC_PRISMATIC_EJECTION="PASS" if (rail_min > 0 and face_min >= 0 and end_min >= 0) else "FAIL",
               propagation_note=("ARM_ONLY_PASS_DOES_NOT_PROPAGATE_TO_FULL_SYSTEM"
                                 if not (rail_min > 0 and face_min >= 0 and end_min >= 0)
                                 else "FULL_SYSTEM_ALSO_PASSES"),
               ejection_method="EXACT_PRISMATIC_REDUCTION_UNION_CROSS_SECTION")
json.dump(recheck, open(os.path.join(OUT, "A3_42_FULL_SYSTEM_CDS_RECHECK.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"\nFULL SYSTEM generic CDS recheck:")
print(f"  rail  {rail_min:8.2f}  {recheck['RAIL_KEEP_OUT']}")
print(f"  faceYZ{face_min:8.2f}  {recheck['LATERAL_ENVELOPE']}   (+Y {face['pY']:.1f} -Y {face['nY']:.1f} "
      f"+Z {face['pZ']:.1f} -Z {face['nZ']:.1f})")
print(f"  endX  {end_min:8.2f}  {recheck['END_ZONE']}   (+X {endc['pX']:.1f} -X {endc['nX']:.1f})")
print(f"  ejection = {recheck['GENERIC_PRISMATIC_EJECTION']}   {recheck['propagation_note']}")

# ---------------- 9. distal options ----------------
distal = [dict(option="G0_AUTHORIZED_CURRENT_STATE", available=True,
               note="fingers at prismatic q=0 which the project three-state mesh check records as CLOSED",
               fullarm_Y_span_mm=float(PF[:, 1].max()-PF[:, 1].min())),
          dict(option="G1_WRIST_REINDEX", available=False,
               note=("the wrist DOF are joint4/5/6, i.e. part of the six-axis q. Changing them is "
                     "re-optimising q, which A3.4 forbids -> A3_4_REQUIRES_A3_2D_REOPTIMIZATION")),
          dict(option="G2_FINGER_CLOSE", available=False,
               note=("gripper_joint1/2 limits are [0, 0.0715] m and the current state is q=0 = fully "
                     "closed. There is no closure travel left.")),
          dict(option="G3_WRIST_REINDEX_PLUS_FINGER_CLOSE", available=False,
               note="requires G1; same restriction"),
          dict(option="NEW_FOLDING_MECHANISM", available=False,
               note="NEW_MECHANISM_REQUIRED / OUT_OF_SCOPE_FOR_CURRENT_BASELINE")]
with open(os.path.join(OUT, "A3_45_DISTAL_STOW_TRADE.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["option", "available", "note", "fullarm_Y_span_mm"],
                       extrasaction="ignore")
    w.writeheader(); w.writerows(distal)

# ---------------- 15. self-collision backend probe ----------------
backends = {}
for mod in ["fcl", "manifold3d", "embreex", "pyembree", "open3d", "vtk", "pyvista", "OCP", "trimesh"]:
    try:
        importlib.import_module(mod); backends[mod] = "AVAILABLE"
    except Exception:
        backends[mod] = "ABSENT"
narrow = any(backends[m] == "AVAILABLE" for m in ["fcl", "manifold3d", "open3d", "embreex", "pyembree"])
json.dump(dict(schema="A3_49_SELF_COLLISION_STATUS_V1", backends=backends,
               narrow_phase_available=narrow,
               status=("NOT_VALIDATED_NO_NARROW_PHASE_BACKEND" if not narrow else "BACKEND_AVAILABLE_NOT_YET_RUN"),
               note=("convex-hull overlap is NOT a collision result and is not used here. "
                     "OCP is present but the arm geometry is tessellated STL, not B-rep, so an "
                     "OCP boolean would need a mesh->BRep conversion that is not part of A3.4.")),
          open(os.path.join(OUT, "A3_49_SELF_COLLISION_STATUS.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"\nself-collision backends: " + ", ".join(f"{k}={v}" for k, v in backends.items() if v == "AVAILABLE"))
print(f"  narrow-phase available = {narrow} -> "
      f"{'NOT_VALIDATED_NO_NARROW_PHASE_BACKEND' if not narrow else 'BACKEND_AVAILABLE'}")

# ---------------- 17. architecture trade ----------------
arch = [dict(arch="ARCH_A_MONOLITHIC_ENVELOPE",
             required_void_cm3=round(vol_mono, 1), pockets=0,
             lateral_envelope="FAIL" if face_min < 0 else "PASS",
             note=("treats the global AABB as the bay. Rejected as over-conservative: only "
                   f"{int((wy > 226.3).sum())}/{len(wy)} stations actually exceed 226.3 in Y and "
                   "0 exceed it in Z."),
             recommended=False),
        dict(arch="ARCH_B_PIECEWISE_CORRIDOR",
             required_void_cm3=round(vol_corr+vol_extra, 1), pockets=len(prows),
             lateral_envelope="FAIL" if face_min < 0 else "PASS",
             note=("ROOT_BASE_BAY + ~80 mm ARM_CORRIDOR + DISTAL_STOW_BAY. Structurally the right "
                   "shape, but the root bay and the distal bay are axially co-located over "
                   f"{overlap:.1f} mm, which is what drives the Y overrun."),
             recommended=False),
        dict(arch="ARCH_C_PIECEWISE_WITH_AUTHORIZED_DISTAL_REINDEX",
             required_void_cm3=None, pockets=None, lateral_envelope="NOT_EVALUABLE",
             note=("does not exist under A3.4 rules: the only distal DOF are joint4/5/6 (part of the "
                   "six-axis q, re-optimisation forbidden) and the finger prismatics (already at the "
                   "closed limit). No new mechanism may be invented."),
             recommended=False)]
with open(os.path.join(OUT, "A3_4_ARCHITECTURE_TRADE.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(arch[0].keys())); w.writeheader(); w.writerows(arch)

# ---------------- 19. gate ----------------
gate = ("A3_4_REQUIRES_A3_2D_REOPTIMIZATION"
        if recheck["GENERIC_PRISMATIC_EJECTION"] == "FAIL" else
        "A3_4_CONDITIONAL_PASS_WITH_PROXY_OPEN_ITEMS")
G = dict(schema="A3_4_FINAL_GATE_V1", gate=gate, primary=PRI,
         headline=(f"FULL system {np.round(PF.max(0)-PF.min(0),1).tolist()} mm; the global AABB is NOT "
                   f"locally realised - only {int((wy > 226.3).sum())}/{len(wy)} stations exceed 226.3 in Y "
                   f"and 0 in Z; the violation is an {float(prows[-1]['x_interval_mm']) if prows else 0:.0f} mm "
                   f"axial band where base_link and the gripper are co-located on opposite Y sides"),
         zones=ZONES, root_distal_axial_overlap_mm=float(overlap),
         pockets=prows, void_cost=dict(corridor_cm3=round(vol_corr, 1), pocket_cm3=round(vol_extra, 1),
                                       piecewise_cm3=round(vol_corr+vol_extra, 1),
                                       monolithic_cm3=round(vol_mono, 1)),
         full_system_cds=recheck, distal_options=distal, architectures=arch,
         SELF_COLLISION="NOT_VALIDATED_NO_NARROW_PHASE_BACKEND" if not narrow else "BACKEND_AVAILABLE_NOT_RUN",
         DEPLOYER_SPECIFIC_ICD="MISSING", LAUNCH_AND_DEPLOYER_COMPLIANCE="HOLD",
         SOLIDWORKS_NATIVE_VALIDATION="NOT_EXECUTED_RESOURCE_GATED",
         a3_3_gate_unchanged=True,
         next_action=("A3.2d must re-optimise with base_link and the distal system IN the objective, "
                      "de-colocating the root bay and the distal stow bay along X. A3.4 must not do "
                      "this silently."))
json.dump(G, open(os.path.join(OUT, "A3_4_FINAL_GATE.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
json.dump(dict(schema="A3_5_HANDOFF_V1", status="BLOCKED_PENDING_A3_2D", gate=gate,
               usable_now=dict(
                   station_envelope_csv="03_a3_4/A3_41_FULLARM_STATION_ENVELOPE.csv",
                   note=("the station envelope is the real X-dependent bus cross-section function "
                         "A3.5 asked for, but it is only valid once A3.2d fixes the root/distal "
                         "co-location; do not size avionics against the current one")),
               open_items=["A3.2d distal-aware re-optimisation required",
                           "SELF_COLLISION not validated (no narrow-phase backend)",
                           "M3R, HDRM, saddles, harness, connectors: MISSING_GEOMETRY_HOLD (8 components)",
                           "DEPLOYER_SPECIFIC_ICD MISSING"]),
          open(os.path.join(OUT, "A3_5_HANDOFF.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\nGATE = {gate}")
print("wrote", OUT)
