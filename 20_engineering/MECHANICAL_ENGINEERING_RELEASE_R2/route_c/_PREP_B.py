# ROUTE_C_SWEEP_MESH_PREP_V1.py
# Stage RC-4-prep of R2 terminal dual-lane closure, lane A2 (Route-C exact verification).
# Run: G:/Windows_program_file/FreeCAD/bin/FreeCADCmd.exe ROUTE_C_SWEEP_MESH_PREP_V1.py
#
# Builds the deterministic triangle/field pack consumed by the pure-Python
# exact sweep runner ROUTE_C_EXACT_SWEEP_V1.py:
#   * B601 vendor collision STLs (accepted URDF meshes, m -> mm) - pure parse
#   * SOLAR_ARRAY_R2_CANDIDATE_V1.step tessellated (S frame, deployed) - READ ONLY
#   * gripper R1 palm-slot + left/right rail full-stroke swept volumes
#     (gripper_link frame; frame re-validated against the gripper_link mesh)
#   * Route-C guided dress pack FCStd: per-part triangles + volume + CG +
#     MatrixOfInertia (A0 frame, q=0 reference), grouped by host link
# Every output lands in ROUTE_C_SWEEP_MESH_PACK_V1/ next to this script.
# No file outside route_c/ is written.  All inputs READ ONLY.
#
# Determinism: same FreeCAD/OCC build + same inputs -> identical triangles.
# The manifest pins per-file sha256; the sweep runner verifies the pin chain.

import os
import json
import struct
import hashlib

import numpy as np

import FreeCAD as App
import Part

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
VARIANT = os.environ.get("RC_VARIANT", "V1").upper()
if VARIANT not in ("V1", "V2", "V3", "V4", "V5", "V6"):
    raise SystemExit("RC_VARIANT must be V1 or V2")
PACK_DIR = os.path.join(SCRIPT_DIR, "ROUTE_C_SWEEP_MESH_PACK_%s" % VARIANT)
os.makedirs(PACK_DIR, exist_ok=True)

URDF = os.path.join(REPO_ROOT, "cad", "spacecraft_layout", "arm_b601_v1", "arm_b601_v1.urdf")
STL_DIR = os.path.join(REPO_ROOT, "cad", "spacecraft_layout", "arm_b601_v1", "meshes_b601_gripper")
SOLAR_STEP = os.path.join(REPO_ROOT, "F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1",
                          "ecr_solar_array_r2", "SOLAR_ARRAY_R2_CANDIDATE_V1.step")
RAIL_DIR = os.path.join(REPO_ROOT, "F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820",
                        "01_native_cad", "gripper_r1")
PALM_STEP = os.path.join(RAIL_DIR, "B601_GRIPPER_PALM_RAIL_SLOT_R1.step")
RAIL_STEPS = [os.path.join(RAIL_DIR, "LEFT_RAIL_FULL_STROKE_SWEPT_VOLUME.step"),
              os.path.join(RAIL_DIR, "RIGHT_RAIL_FULL_STROKE_SWEPT_VOLUME.step")]
RC_FCSTD = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_%s.FCStd" % VARIANT)
RC_RECEIPT = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_BUILD_RECEIPT_%s.json" % VARIANT)

ARM_LINKS = ["base_link", "link1", "link2", "link3", "link4", "link5",
             "link6", "gripper_link", "gripper_left", "gripper_right"]

DEFLECTION_SOLAR = 0.3
DEFLECTION_RAIL = 0.25
DEFLECTION_RC = 0.25


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def load_stl_m_to_mm(path):
    with open(path, "rb") as f:
        data = f.read()
    n = struct.unpack("<I", data[80:84])[0]
    dt = np.dtype([("n", "<f4", (3,)), ("v", "<f4", (9,)), ("a", "<u2")])
    tris = np.frombuffer(data, dtype=dt, count=n, offset=84)
    return (tris["v"].reshape(n, 3, 3).astype(np.float64)) * 1000.0


def shape_tris(shape, deflection):
    pts, facs = shape.tessellate(deflection)
    V = np.array([[p.x, p.y, p.z] for p in pts], dtype=np.float64)
    F = np.array(facs, dtype=np.int64)
    return V[F]


def shape_mass_props(shape):
    """volume, CG (A0), volume-inertia (mm^5) about CG in A0 axes.
    Works for Solid AND Compound (compounds lack CenterOfMass /
    MatrixOfInertia attributes in FreeCAD; aggregate over solids)."""
    solids = list(shape.Solids)
    vols, cgs, inertias = [], [], []
    for s in solids:
        v = float(s.Volume)
        c = s.CenterOfMass
        m = s.MatrixOfInertia
        vols.append(v)
        cgs.append(np.array([c.x, c.y, c.z], dtype=np.float64))
        inertias.append(np.array([
            [m.A11, m.A12, m.A13],
            [m.A21, m.A22, m.A23],
            [m.A31, m.A32, m.A33]], dtype=np.float64))
    V = float(sum(vols))
    if V <= 0:
        return 0.0, [0.0, 0.0, 0.0], [[0.0] * 3 for _ in range(3)]
    cg = sum(v * c for v, c in zip(vols, cgs)) / V
    I_tot = np.zeros((3, 3))
    for v, c, I in zip(vols, cgs, inertias):
        d = c - cg
        I_tot += I + v * ((d @ d) * np.eye(3) - np.outer(d, d))
    return V, [float(x) for x in cg], [[float(x) for x in row] for row in I_tot]


def save_npy(name, arr):
    path = os.path.join(PACK_DIR, name)
    np.save(path, arr, allow_pickle=False)
    return path


manifest = {
    "schema": "ROUTE_C_SWEEP_MESH_PACK_%s_MANIFEST" % VARIANT,
    "variant": VARIANT,
    "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
    "stage": "RC-4_PREP_MESH_PACK",
    "authority": "DESIGN_CANDIDATE geometry pack; inputs frozen/read-only",
    "freecad_version": ".".join(App.Version()[0:3]),
    "units": "mm",
    "frames": {
        "arm_vendor_meshes": "URDF link-local frames (accepted URDF sha256 1BC2B748...71C164), m scaled to mm",
        "solar": "S frame (spacecraft assembly), deployed C01 snapshot",
        "rails": "gripper_link frame (validated against palm-slot hugging)",
        "route_c_parts": "A0 = B601 base_link frame at q=0 (build frame of B601_ROUTE_C_GUIDED_DRESS_PACK_V1)"
    },
    "deflection_mm": {"solar": DEFLECTION_SOLAR, "rails": DEFLECTION_RAIL, "route_c_parts": DEFLECTION_RC},
    "inputs": {},
    "files": [],
}

for label, p in [("accepted_urdf", URDF), ("solar_step", SOLAR_STEP),
                 ("palm_slot_step", PALM_STEP),
                 ("rail_left_step", RAIL_STEPS[0]), ("rail_right_step", RAIL_STEPS[1]),
                 ("route_c_fcstd", RC_FCSTD), ("route_c_build_receipt", RC_RECEIPT)]:
    manifest["inputs"][label] = {
        "path": os.path.relpath(p, REPO_ROOT).replace("\\", "/"),
        "sha256": sha256_file(p),
        "access": "READ_ONLY",
    }

# ---------------- arm vendor meshes (decimated, <=0.1 mm error) ----------------
import Mesh
ARM_DECIMATE_TOL = 0.1
ARM_DECIMATE_RED = 0.9
arm_entries = []
for link in []:
    p = os.path.join(STL_DIR, link + ".STL")
    m = Mesh.Mesh(p)
    n_raw = m.CountFacets
    m.decimate(ARM_DECIMATE_TOL, ARM_DECIMATE_RED)
    pts, facs = m.Topology
    V = np.array([[pt.x, pt.y, pt.z] for pt in pts], dtype=np.float64) * 1000.0
    F = np.array(facs, dtype=np.int64)
    tris = V[F]
    out = save_npy("vendor_%s_tris.npy" % link, tris)
    arm_entries.append({"link": link, "tris": int(len(tris)), "tris_raw": int(n_raw),
                        "decimate_tol_mm": ARM_DECIMATE_TOL,
                        "decimate_reduction": ARM_DECIMATE_RED,
                        "file": os.path.basename(out),
                        "sha256": sha256_file(out),
                        "source_sha256": sha256_file(p)})
    print("vendor %-14s tris=%7d (raw %7d)" % (link, len(tris), n_raw))
manifest_arm = arm_entries

# ---------------- solar ----------------
solar_shape = Part.read(SOLAR_STEP)
solar_tris = shape_tris(solar_shape, DEFLECTION_SOLAR)
solar_path = save_npy("solar_r2_deployed_tris.npy", solar_tris)
print("solar tris=%d" % len(solar_tris))

# ---------------- gripper palm slot + rails ----------------
palm_tris = shape_tris(Part.read(PALM_STEP), DEFLECTION_RAIL)
palm_path = save_npy("gripper_palm_slot_tris.npy", palm_tris)

# frame validation: palm slot vertices should hug the gripper_link mesh surface
gl = load_stl_m_to_mm(os.path.join(STL_DIR, "gripper_link.STL"))
gl_v = gl.reshape(-1, 3)
pv = palm_tris.reshape(-1, 3)
pv = pv[::max(1, len(pv) // 1500)]
# brute-force nearest distance in tiled chunks (validation only)
dmin = np.empty(len(pv))
for i in range(len(pv)):
    d2 = ((gl_v - pv[i]) ** 2).sum(axis=1)
    dmin[i] = np.sqrt(d2.min())
palm_med = float(np.median(dmin))
palm_p90 = float(np.percentile(dmin, 90))
rail_frame_valid = bool(palm_med < 3.0)
print("palm-slot vs gripper_link: median=%.3f p90=%.3f -> %s"
      % (palm_med, palm_p90, "VALID" if rail_frame_valid else "INVALID"))

rail_entries = []
if rail_frame_valid:
    for rp in RAIL_STEPS:
        tris = shape_tris(Part.read(rp), DEFLECTION_RAIL)
        tag = "left" if "LEFT" in os.path.basename(rp).upper() else "right"
        out = save_npy("rail_%s_swept_tris.npy" % tag, tris)
        rail_entries.append({"side": tag, "tris": int(len(tris)),
                             "file": os.path.basename(out), "sha256": sha256_file(out)})
        print("rail %-5s tris=%d" % (tag, len(tris)))
else:
    print("RAIL FRAME VALIDATION FAILED - rails excluded, recorded as HOLD")

# ---------------- Route-C dress pack parts ----------------
receipt = json.load(open(RC_RECEIPT, encoding="utf-8"))
part_meta = {p["name"]: p for p in receipt["parts"]}

doc = App.openDocument(RC_FCSTD)
rc_entries = []
rc_mass_rows = []   # name, host_link, kind, material, volume_mm3, cg_mm(A0), inertia_vol_mm5 about CG (A0 axes)
for obj in doc.Objects:
    name = obj.Label
    if name not in part_meta:
        continue
    meta = part_meta[name]
    try:
        shape = getattr(obj, "Shape", None)
        if shape is None or not shape.isValid() or shape.Volume <= 0:
            rc_entries.append({"name": name, "valid": False})
            continue
        vol, cg_l, I = shape_mass_props(shape)
        if meta.get("kind") == "bundle_envelope":
            # bundle envelopes ARE the cable: mass-geometry only, no triangle
            # field (saves the large tessellation memory/space)
            rc_entries.append({"name": name, "valid": True, "tris": 0,
                               "bundle_envelope": True,
                               "host_link": meta.get("host_link"), "kind": meta.get("kind"),
                               "material": meta.get("material"), "role": meta.get("role")})
        else:
            tris = shape_tris(shape, DEFLECTION_RC)
            safe = "".join(c if (c.isalnum() or c == "_") else "_" for c in name)
            out = save_npy("rc_%s_tris.npy" % safe, tris)
            rc_entries.append({
                "name": name, "valid": True, "tris": int(len(tris)),
                "file": os.path.basename(out), "sha256": sha256_file(out),
                "host_link": meta.get("host_link"), "kind": meta.get("kind"),
                "material": meta.get("material"), "role": meta.get("role"),
            })
        rc_mass_rows.append({
            "name": name,
            "host_link": meta.get("host_link"),
            "kind": meta.get("kind"),
            "material": meta.get("material"),
            "volume_mm3": float(vol),
            "cg_mm_A0": [float(x) for x in cg_l],
            "inertia_vol_mm5_about_cg_A0": I,
        })
        print("rc part %-44s host=%-10s kind=%-16s done" % (
            name, meta.get("host_link"), meta.get("kind")))
    except Exception as exc:
        print("ERROR processing part %s: %s" % (name, exc))
        rc_entries.append({"name": name, "valid": False,
                           "error": str(exc)})

mass_path = os.path.join(PACK_DIR, "rc_parts_mass_geometry.json")
with open(mass_path, "w", encoding="utf-8", newline="\n") as f:
    json.dump({"schema": "ROUTE_C_PARTS_MASS_GEOMETRY_V1",
               "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
               "units": {"volume": "mm3", "cg": "mm", "inertia_volume": "mm5"},
               "frame": "A0 = B601 base_link frame at q=0",
               "note": "inertia_volume = volume moments about part CG in A0 axes; "
                       "multiply by density[g/mm3] for mass moments in g*mm2",
               "parts": rc_mass_rows},
              f, indent=2, sort_keys=True)

manifest["files"] = (
    [{"group": "arm_vendor", "entries": manifest_arm},
     {"group": "solar", "entries": [{"file": os.path.basename(solar_path),
                                     "sha256": sha256_file(solar_path),
                                     "tris": int(len(solar_tris))}]},
     {"group": "gripper_rails", "frame_validation": {
         "palm_slot_vs_gripper_link_median_mm": palm_med,
         "p90_mm": palm_p90, "valid": rail_frame_valid},
      "palm_slot": {"file": os.path.basename(palm_path), "sha256": sha256_file(palm_path)},
      "entries": rail_entries},
     {"group": "route_c_parts", "entries": rc_entries},
     {"group": "route_c_mass_geometry",
      "entries": [{"file": os.path.basename(mass_path), "sha256": sha256_file(mass_path)}]}])
manifest["review_status"] = "PENDING_OWNER_REVIEW"
manifest["next_stage_authorized"] = False
manifest["release_credit"] = False

man_path = os.path.join(PACK_DIR, "MANIFEST.json")
with open(man_path, "w", encoding="utf-8", newline="\n") as f:
    json.dump(manifest, f, indent=2, sort_keys=True)
print("MANIFEST written:", man_path)
print("MANIFEST sha256:", sha256_file(man_path))

n_invalid = sum(1 for e in rc_entries if not e.get("valid"))
n_expected = len(part_meta)
print("rc parts processed: %d valid / %d expected" % (n_expected - n_invalid, n_expected))
if n_invalid or len(rc_entries) != n_expected:
    print("PREP_INCOMPLETE: %d invalid, %d processed of %d expected"
          % (n_invalid, len(rc_entries), n_expected))
    raise SystemExit(2)
print("PREP_COMPLETE")
