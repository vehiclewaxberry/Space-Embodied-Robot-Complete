"""A3.3 - deployer zone mapping and virtual insertion / ejection.

Scope: verify that the A3.2c stowed-arm candidates, placed at a real position
inside the 12U envelope, do not intrude the deployer rail / end / keep-out
regions, and that the spacecraft can be inserted and ejected.

METHOD NOTE - why the ejection test is exact, not sampled
---------------------------------------------------------
A CubeSat deployer channel is prismatic along the deployment axis. A rigid body
translating along that axis sweeps exactly the extrusion of its own projection
onto the cross-section plane. Therefore:

    axial ejection interference  <=>  cross-section interference

so the ejection result is fully determined by the UNION cross-section (the
projection of every point of the stowed arm onto the Y-Z plane), plus the
non-prismatic end features (door / pusher plate). This is exact and does not
depend on a travel step size. A travel trace is still emitted for the record.

Everything here is generic CDS reference geometry. No deployer-specific ICD
exists in the repository, so no compatibility claim is made.

Read-only over all project inputs. Writes only under 02_a3_3/.
"""
import numpy as np, trimesh, os, json, csv, hashlib
from scipy.optimize import minimize
from scipy.spatial import ConvexHull

ROOT = r"F:\China Graduate Future Flight Vehicle Innovation Competition"
BASE = os.path.join(ROOT, r"20_engineering\MECHANICAL_ENGINEERING_RELEASE_R2\_work\mode_a_native_design_r1")
MESH = os.path.join(ROOT, r"20_engineering\cad\spacecraft_layout\arm_b601_v1\meshes_b601_gripper")
OUT = os.path.join(BASE, "02_a3_3")
os.makedirs(OUT, exist_ok=True)

# ---------------- generic CDS reference constants (Rev 14.1 text) ----------------
BOX = np.array([366.0, 226.3, 226.3])          # 12U rail-reference envelope
HALF = BOX/2.0
RAIL_WIDTH = 8.5            # rail contact-surface width on each face at a corner
RAIL_END_CONTACT = 6.5      # rail end contact square
FIRST_PROT_CLEAR = 8.5      # first protrusion must be >= this from the rail
LAT_PROT_MAX = 6.5          # max protrusion normal to the rail plane
STATION_MM = 1.0

# ---------------- 0. authority bootstrap ----------------
def sha(fp):
    h = hashlib.sha256()
    with open(fp, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest().upper()


AUTH = json.load(open(os.path.join(BASE, "00_authority", "A3_00_INPUT_AUTHORITY.json"), encoding="utf-8"))
A2C = json.load(open(os.path.join(BASE, "01_a3_2c", "A3_02C_RESULTS.json"), encoding="utf-8"))

boot = {"A3_00_INPUT_AUTHORITY.json": sha(os.path.join(BASE, "00_authority", "A3_00_INPUT_AUTHORITY.json")),
        "A3_02C_RESULTS.json": sha(os.path.join(BASE, "01_a3_2c", "A3_02C_RESULTS.json"))}
abort = []
if A2C.get("active_profile") != "CDS_12U_REFERENCE" or A2C.get("box_mm") != BOX.tolist():
    abort.append("A3.2c active profile / box mismatch")
if AUTH["counts"]["identity_mismatch"] != 1:
    abort.append("input authority mismatch count changed")
# re-verify the two hard inputs the arm geometry depends on
for r_role, r_path, r_exp in [("L0_ACCEPTED_URDF",
                               r"20_engineering\cad\spacecraft_layout\arm_b601_v1\arm_b601_v1.urdf",
                               "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164")]:
    cur = sha(os.path.join(ROOT, r_path))
    boot[r_role] = cur
    if cur != r_exp:
        abort.append(f"{r_role} hash drift")
if abort:
    json.dump(dict(verdict="A3_3_ABORT_INPUT_IDENTITY_CHANGED", reasons=abort, hashes=boot),
              open(os.path.join(OUT, "A3_3_ABORT.json"), "w", encoding="utf-8"), indent=1)
    raise SystemExit("A3_3_ABORT_INPUT_IDENTITY_CHANGED: " + "; ".join(abort))
print("authority bootstrap OK; A3.2c profile = CDS_12U_REFERENCE", BOX.tolist())

# ---------------- kinematics ----------------
JOINTS = [("link1", "base_link", (-8.416e-05, 0, 0.08465), (0, 0, 0), (0, 0, 1), -2.8, 2.8),
          ("link2", "link1", (0.020084, 0.031625, 0.05555), (-1.5708, 0, 0), (0, 0, -1), -3.14, 0.0),
          ("link3", "link2", (-0.264, 0, 0), (0, 0, 0), (0, 0, 1), -3.14, 0.0),
          ("link4", "link3", (0.2426, -0.054, -0.001625), (0, 0, 0), (0, 0, 1), -1.87, 1.57),
          ("link5", "link4", (0.078308, -0.0375, -0.03), (-1.5708, 0, 0), (0, 0, 1), -1.57, 1.57),
          ("link6", "link5", (0.023692, 0, 0.04), (0, 1.5708, 0), (0, 0, 1), -3.14, 3.14)]
FIXED = [("gripper_link", "link6", (0, 0, 0.15971), (0, -1.5708, 0)),
         ("gripper_left", "gripper_link", (-0.042091, 2.7531e-05, -1.3031e-05), (0, 0, -1.5708)),
         ("gripper_right", "gripper_link", (-0.042091, -2.7531e-05, 1.3031e-05), (0, 0, 1.5708))]


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
CORRIDOR = ["link1", "link2", "link3", "link4", "link5", "link6"]


def fk(q):
    Tw = {"base_link": np.eye(4)}
    for i, (c, p, x, rr, ax, a, b) in enumerate(JOINTS):
        Tw[c] = Tw[p] @ (Tm(x, rpy(*rr)) @ Tm((0, 0, 0), arot(ax, q[i])))
    for c, p, x, rr in FIXED:
        Tw[c] = Tw[p] @ Tm(x, rpy(*rr))
    return Tw


def placed(q_deg, rv, names):
    q = np.radians(q_deg); R = rotvec(rv); Tw = fk(q)
    return {n: (HULL[n] @ Tw[n][:3, :3].T + Tw[n][:3, 3]*1000.0) @ R.T for n in names}, Tw, R


# ---------------- 3. frame normalisation ----------------
FRAMES = dict(
    R_CDS=dict(description="generic CDS 12U reference frame", origin="centre of the 366.0 x 226.3 x 226.3 envelope",
               x="+X = deployment / longitudinal axis, ejection direction +X",
               y="+Y lateral face normal", z="+Z lateral face normal"),
    S=dict(description="spacecraft mechanical frame (project SSOT)",
           note="frame_tree_v1.yaml: S origin = 12U geometric centre; bus long axis = X_S"),
    A=dict(description="B601 arm base frame (accepted URDF base_link)"),
    T_S_RCDS=dict(rotation="identity (X_S -> X_RCDS, Y_S -> Y_RCDS, Z_S -> Z_RCDS)",
                  translation_mm=[0, 0, 0],
                  status="PROVISIONAL_BUT_EXPLICIT",
                  basis=("frame_tree_v1.yaml puts the bus long axis on X_S and the project bus "
                         "x-extent is symmetric about 0; the CDS long axis is therefore mapped to X_S. "
                         "No owner signoff of this mapping exists.")),
    axis_roles=dict(longitudinal_axis="X", lateral_faces=["+Y", "-Y", "+Z", "-Z"],
                    rail_planes="four corner rails running the full X length at (+-Y_max, +-Z_max)",
                    insertion_direction="-X", ejection_direction="+X",
                    spacecraft_base_datum="R_CDS origin (envelope centre)"),
)

# ---------------- 4. generic CDS reference zones ----------------
ZONES = []


def zone(zid, ztype, origin, dims, hard, enabled=True, notes=""):
    ZONES.append(dict(zone_id=zid, zone_type=ztype, frame="R_CDS",
                      origin_mm=list(map(float, origin)), axis="X_longitudinal",
                      dimensions_mm=list(map(float, dims)),
                      source_authority="CDS Rev 14.1 generic text (no deployer-specific ICD present)",
                      hard_or_provisional=hard, enabled=bool(enabled), notes=notes))


zone("NOMINAL_12U_ENVELOPE", "ENVELOPE", [0, 0, 0], BOX, "REFERENCE",
     notes="366.0 x 226.3 x 226.3 rail-reference envelope")
for sy in (+1, -1):
    for sz in (+1, -1):
        cy, cz = sy*(HALF[1]-RAIL_WIDTH/2), sz*(HALF[2]-RAIL_WIDTH/2)
        zone(f"RAIL_CONTACT_{'P' if sy>0 else 'N'}Y_{'P' if sz>0 else 'N'}Z", "RAIL_CONTACT",
             [0, cy, cz], [BOX[0], RAIL_WIDTH, RAIL_WIDTH], "HARD",
             notes="8.5 x 8.5 corner rail strip, full length; must be free for bus rail material")
        for sx in (+1, -1):
            zone(f"RAIL_END_CONTACT_{'P' if sx>0 else 'N'}X_{'P' if sy>0 else 'N'}Y_{'P' if sz>0 else 'N'}Z",
                 "RAIL_END_CONTACT", [sx*(HALF[0]-RAIL_END_CONTACT/2), cy, cz],
                 [RAIL_END_CONTACT, RAIL_END_CONTACT, RAIL_END_CONTACT], "HARD",
                 notes="6.5 x 6.5 rail end contact square")
zone("FIRST_PROTRUSION_KEEPOUT", "PROTRUSION_RULE", [0, 0, 0], [BOX[0], 0, 0], "HARD",
     notes=f"any protruding feature must be >= {FIRST_PROT_CLEAR} mm from a rail edge")
zone("LATERAL_PROTRUSION_REFERENCE_REGION", "PROTRUSION_RULE", [0, 0, 0], [BOX[0], 0, 0], "HARD",
     notes=f"max {LAT_PROT_MAX} mm protrusion normal to a rail plane, outside the rail strips")
zone("INSERTION_DIRECTION_KEEP_OUT", "END_FEATURE", [-HALF[0], 0, 0], [0, BOX[1], BOX[2]], "PROVISIONAL",
     notes="pusher-plate side; nothing may extend beyond -X end face")
zone("EJECTION_DIRECTION_KEEP_OUT", "END_FEATURE", [+HALF[0], 0, 0], [0, BOX[1], BOX[2]], "PROVISIONAL",
     notes="door side; nothing may extend beyond +X end face")
zone("END_FACE_KEEP_OUT", "END_FEATURE", [0, 0, 0], [BOX[0], BOX[1], BOX[2]], "PROVISIONAL",
     notes="both end faces treated as flat plates")
zone("OPTIONAL_EXTRA_VOLUME", "OPTIONAL", [0, 0, 0], [0, 0, 0], "PROVISIONAL", enabled=False,
     notes="tuna-can / extra volume is deployer dependent; DISABLED BY DEFAULT")

json.dump(dict(schema="A3_30_DEPLOYER_REFERENCE_MODEL_V1",
               model_class="CDS_R14_1_GENERIC_PRELIMINARY",
               deployer_specific_icd="MISSING",
               nanoracks_12u="NOT_EVALUATED__DEPLOYER_ICD_MISSING",
               constants=dict(rail_width_mm=RAIL_WIDTH, rail_end_contact_mm=RAIL_END_CONTACT,
                              first_protrusion_clearance_mm=FIRST_PROT_CLEAR,
                              lateral_protrusion_max_mm=LAT_PROT_MAX),
               frames=FRAMES, zones=ZONES),
          open(os.path.join(OUT, "A3_30_DEPLOYER_REFERENCE_MODEL.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"zones built: {len(ZONES)} (rail 4, rail-end 8, envelope 1, rules 2, end 3, optional 1 disabled)")

# ---------------- 5. candidates ----------------
WANT = {"CAND_0_THIN": (0.0, "THIN"), "CAND_2_FIT": (2.0, "FIT"), "CAND_2_THIN": (2.0, "THIN"),
        "CAND_3_THIN": (3.0, "THIN"), "CAND_5_THIN": (5.0, "THIN")}
cands = {}
for cid, (mg, md) in WANT.items():
    src = next((r for r in A2C["results"]
                if r["link_set"] == "CORRIDOR" and r["margin_deg"] == mg and r["mode"] == md), None)
    if src is None:
        print(f"  {cid}: MISSING in A3.2c"); continue
    pl, Tw, R = placed(src["q_deg"], src["mount_rotvec"], CORRIDOR)
    P = np.vstack(list(pl.values()))
    e = np.sort(P.max(0) - P.min(0))[::-1]
    ref = np.array(src["sorted_LWH_mm"])
    err = float(np.abs(e - ref).max())
    ok = err < 1e-6
    rh = hashlib.sha256(json.dumps(dict(q=src["q_deg"], rv=src["mount_rotvec"]),
                                   sort_keys=True).encode()).hexdigest()[:16].upper()
    print(f"  {cid}: reconstruction err {err:.3e} mm -> {'OK' if ok else 'MISMATCH'}  hash {rh}")
    if not ok:
        cands[cid] = dict(status="A3_3_RECONSTRUCTION_MISMATCH", err_mm=err); continue
    cands[cid] = dict(status="OK", src=src, points=pl, reconstruction_hash=rh,
                      sorted_LWH_mm=e.tolist(), margin_deg=mg, mode=md)

# ---------------- placement: maximise rail clearance inside the envelope ----------------
RAILS = [(sy*(HALF[1]-RAIL_WIDTH), sz*(HALF[2]-RAIL_WIDTH), sy, sz) for sy in (1, -1) for sz in (1, -1)]


def rail_clearance(Pyz):
    """min distance from the projected point cloud to the four corner rail strips
    (negative = intrusion depth)."""
    out = []
    for iy, iz, sy, sz in RAILS:
        dy = sy*Pyz[:, 0] - sy*iy          # >0 means inside the rail band in Y
        dz = sz*Pyz[:, 1] - sz*iz
        inside = (dy > 0) & (dz > 0)
        if inside.any():
            out.append(-float(np.minimum(dy[inside], dz[inside]).max()))
        else:
            d = np.maximum(np.maximum(-dy, 0), 0)**2 + np.maximum(np.maximum(-dz, 0), 0)**2
            out.append(float(np.sqrt(d.min())))
    return out


def place(cand):
    """translate the bundle inside the envelope to maximise the minimum rail clearance."""
    P = np.vstack(list(cand["points"].values()))
    c0 = (P.max(0) + P.min(0))/2
    P0 = P - c0
    lo, hi = P0.min(0), P0.max(0)
    tlo, thi = -HALF - lo, HALF - hi          # translation range keeping the body in the envelope
    if np.any(tlo > thi + 1e-9):
        return None, None, "DOES_NOT_FIT_ENVELOPE"

    def neg(t):
        """maximise the WORST clearance, rail and face together.
        Rail clearance alone is nearly insensitive to the in-plane position of a
        thin centred slab, so optimising it alone lets the body drift onto a face."""
        yz = P0[:, 1:] + t
        face = min(HALF[1]-yz[:, 0].max(), yz[:, 0].min()+HALF[1],
                   HALF[2]-yz[:, 1].max(), yz[:, 1].min()+HALF[2])
        return -min(min(rail_clearance(yz)), float(face))

    best, bt = None, None
    for t0 in [np.zeros(2)] + [np.array([a, b]) for a in np.linspace(tlo[1], thi[1], 7)
                               for b in np.linspace(tlo[2], thi[2], 7)]:
        t0 = np.clip(t0, tlo[1:], thi[1:])
        r = minimize(lambda t: neg(np.clip(t, tlo[1:], thi[1:])), t0, method="Nelder-Mead",
                     options=dict(maxiter=2000, xatol=1e-6, fatol=1e-6))
        t = np.clip(r.x, tlo[1:], thi[1:]); v = neg(t)
        if best is None or v < best:
            best, bt = v, t
    tx = float(np.clip(0.0, tlo[0], thi[0]))
    T = np.array([tx, bt[0], bt[1]])
    return {k: v - c0 + T for k, v in cand["points"].items()}, T, "PLACED"


print("\nplacement (translation only, maximising rail clearance):")
for cid, c in cands.items():
    if c["status"] != "OK":
        continue
    pl, T, st = place(c)
    c["placed"], c["translation_mm"], c["placement_status"] = pl, (None if T is None else T.tolist()), st
    print(f"  {cid}: {st}  T={None if T is None else np.round(T,2).tolist()}")

json.dump({k: {kk: vv for kk, vv in v.items() if kk not in ("points", "placed", "src")}
           for k, v in cands.items()},
          open(os.path.join(OUT, "_candidates_meta.json"), "w", encoding="utf-8"), indent=1)
print("\nwrote", OUT)
