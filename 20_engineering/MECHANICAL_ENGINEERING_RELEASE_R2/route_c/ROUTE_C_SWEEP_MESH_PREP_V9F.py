# ROUTE_C_SWEEP_MESH_PREP_V9F.py
# Light per-variant mesh pack builder.  Vendor B601 meshes, solar, gripper
# rails/palm are variant-invariant and are COPIED from the V1 pack (they were
# already decimated/tessellated by the full prep); only the Route-C dress-pack
# parts of the CURRENT variant FCStd are re-tessellated.  This avoids the
# memory-heavy vendor decimation on every variant iteration.
#
# Run: FreeCADCmd.exe ROUTE_C_SWEEP_MESH_PREP_V9F.py
import os
import json
import shutil
import hashlib

import numpy as np
import FreeCAD as App
import Part

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
VARIANT = "V9F"
BASE_PACK = os.path.join(SCRIPT_DIR, "ROUTE_C_SWEEP_MESH_PACK_V1")
PACK_DIR = os.path.join(SCRIPT_DIR, "ROUTE_C_SWEEP_MESH_PACK_%s" % VARIANT)
os.makedirs(PACK_DIR, exist_ok=True)

RC_FCSTD = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_GUIDED_DRESS_PACK_%s.FCStd" % VARIANT)
RC_RECEIPT = os.path.join(SCRIPT_DIR, "B601_ROUTE_C_BUILD_RECEIPT_%s.json" % VARIANT)
V9_INPUT_MANIFEST = os.path.join(SCRIPT_DIR, "ROUTE_C_V9_INPUT_MANIFEST.json")
V9_INPUT_MANIFEST_SHA256 = "24B9E2BFB21930E44945C0BA979351CFB9EB23358755D1018FCC4602CDED7E7C"

SOLAR_STEP = os.path.join(REPO_ROOT, "F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1",
                          "ecr_solar_array_r2", "SOLAR_ARRAY_R2_CANDIDATE_V1.step")
RAIL_DIR = os.path.join(REPO_ROOT, "F3R2_V5R_RAPID_MECHANICAL_CLOSURE_20260820",
                        "01_native_cad", "gripper_r1")
URDF = os.path.join(REPO_ROOT, "cad", "spacecraft_layout", "arm_b601_v1", "arm_b601_v1.urdf")
STL_DIR = os.path.join(REPO_ROOT, "cad", "spacecraft_layout", "arm_b601_v1", "meshes_b601_gripper")
PALM_STEP = os.path.join(RAIL_DIR, "B601_GRIPPER_PALM_RAIL_SLOT_R1.step")
RAIL_STEPS = [os.path.join(RAIL_DIR, "LEFT_RAIL_FULL_STROKE_SWEPT_VOLUME.step"),
              os.path.join(RAIL_DIR, "RIGHT_RAIL_FULL_STROKE_SWEPT_VOLUME.step")]
ARM_LINKS = ["base_link", "link1", "link2", "link3", "link4", "link5",
             "link6", "gripper_link", "gripper_left", "gripper_right"]
DEFLECTION_RC = 0.25


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def shape_tris(shape, deflection):
    pts, facs = shape.tessellate(deflection)
    V = np.array([[p.x, p.y, p.z] for p in pts], dtype=np.float64)
    F = np.array(facs, dtype=np.int64)
    return V[F]


def save_npy(name, arr):
    path = os.path.join(PACK_DIR, name)
    np.save(path, arr, allow_pickle=False)
    return path


base_manifest = json.load(open(os.path.join(BASE_PACK, "MANIFEST.json"), encoding="utf-8"))

manifest = {
    "schema": "ROUTE_C_SWEEP_MESH_PACK_%s_MANIFEST" % VARIANT,
    "variant": VARIANT,
    "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
    "stage": "RC-4_PREP_MESH_PACK_LIGHT",
    "authority": "DESIGN_CANDIDATE geometry pack; inputs frozen/read-only",
    "freecad_version": ".".join(App.Version()[0:3]),
    "units": "mm",
    "note": "vendor/solar/rail/palm assets copied byte-identical from the V1 pack (variant-invariant); only Route-C parts re-tessellated from the %s FCStd" % VARIANT,
    "deflection_mm": {"route_c_parts": DEFLECTION_RC},
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
manifest["inputs"]["v9_input_manifest"] = {
    "path": os.path.relpath(V9_INPUT_MANIFEST, REPO_ROOT).replace("\\", "/"),
    "sha256": sha256_file(V9_INPUT_MANIFEST),
    "expected_sha256": V9_INPUT_MANIFEST_SHA256,
    "match": sha256_file(V9_INPUT_MANIFEST) == V9_INPUT_MANIFEST_SHA256,
    "access": "READ_ONLY_FAIL_CLOSED",
}
if not manifest["inputs"]["v9_input_manifest"]["match"]:
    raise RuntimeError("V9 input manifest hash mismatch")

# ---- copy variant-invariant assets from the V1 pack --------------------------
copied_arm = []
for grp in base_manifest["files"]:
    if grp["group"] == "arm_vendor":
        for e in grp["entries"]:
            src = os.path.join(BASE_PACK, e["file"])
            dst = os.path.join(PACK_DIR, e["file"])
            shutil.copyfile(src, dst)
            copied_arm.append(dict(e, sha256=sha256_file(dst)))
solar_entry = None
rail_entries = []
palm_entry = None
for grp in base_manifest["files"]:
    if grp["group"] == "solar":
        e = grp["entries"][0]
        shutil.copyfile(os.path.join(BASE_PACK, e["file"]), os.path.join(PACK_DIR, e["file"]))
        solar_entry = dict(e, sha256=sha256_file(os.path.join(PACK_DIR, e["file"])))
    if grp["group"] == "gripper_rails":
        for e in grp.get("entries", []):
            shutil.copyfile(os.path.join(BASE_PACK, e["file"]), os.path.join(PACK_DIR, e["file"]))
            rail_entries.append(dict(e, sha256=sha256_file(os.path.join(PACK_DIR, e["file"]))))
        ps = grp.get("palm_slot")
        if ps:
            shutil.copyfile(os.path.join(BASE_PACK, ps["file"]), os.path.join(PACK_DIR, ps["file"]))
            palm_entry = dict(ps, sha256=sha256_file(os.path.join(PACK_DIR, ps["file"])))
        rail_frame_validation = grp.get("frame_validation")

# ---- RC parts of the current variant -----------------------------------------
receipt = json.load(open(RC_RECEIPT, encoding="utf-8"))
part_meta = {p["name"]: p for p in receipt["parts"]}
doc = App.openDocument(RC_FCSTD)
# drop the big read-only vendor-mesh reference objects immediately (they are
# not pack inputs; deleting them frees the bulk of the document memory on this
# memory-tight host)
import gc
for obj in list(doc.Objects):
    if obj.Label.startswith("REF_FROZEN"):
        try:
            doc.removeObject(obj.Name)
        except Exception:
            pass
gc.collect()
rc_entries = []
rc_mass_rows = []
for obj in list(doc.Objects):
    name = obj.Label
    if name not in part_meta:
        continue
    meta = part_meta[name]
    shape = getattr(obj, "Shape", None)
    if shape is None or not shape.isValid() or shape.Volume <= 0:
        rc_entries.append({"name": name, "valid": False})
        continue
    # mass props (works for solids and compounds)
    solids = list(shape.Solids)
    vols, cgs, inertias = [], [], []
    for s in solids:
        v = float(s.Volume)
        c = s.CenterOfMass
        m = s.MatrixOfInertia
        vols.append(v)
        cgs.append(np.array([c.x, c.y, c.z]))
        inertias.append(np.array([[m.A11, m.A12, m.A13],
                                  [m.A21, m.A22, m.A23],
                                  [m.A31, m.A32, m.A33]]))
    V = float(sum(vols))
    cg = sum(v * c for v, c in zip(vols, cgs)) / V
    I_tot = np.zeros((3, 3))
    for v, c, I in zip(vols, cgs, inertias):
        d = c - cg
        I_tot += I + v * ((d @ d) * np.eye(3) - np.outer(d, d))
    if meta.get("kind") == "bundle_envelope":
        rc_entries.append({"name": name, "valid": True, "tris": 0,
                           "bundle_envelope": True,
                           "host_link": meta.get("host_link"), "kind": meta.get("kind"),
                           "material": meta.get("material"), "role": meta.get("role"),
                           "geometry_role": meta.get("geometry_role"),
                           "mass_counted": meta.get("mass_counted"),
                           "overlap_disposition": meta.get("overlap_disposition")})
    else:
        tris = shape_tris(shape, DEFLECTION_RC)
        safe = "".join(c if (c.isalnum() or c == "_") else "_" for c in name)
        out = save_npy("rc_%s_tris.npy" % safe, tris)
        rc_entries.append({
            "name": name, "valid": True, "tris": int(len(tris)),
            "file": os.path.basename(out), "sha256": sha256_file(out),
            "host_link": meta.get("host_link"), "kind": meta.get("kind"),
            "material": meta.get("material"), "role": meta.get("role"),
            "geometry_role": meta.get("geometry_role"),
            "mass_counted": meta.get("mass_counted"),
            "overlap_disposition": meta.get("overlap_disposition"),
            "motion_class": meta.get("motion_class"),
        })
        motion_class = meta.get("motion_class")
        if motion_class in {"ONE_THIRD_TRAVEL", "TWO_THIRDS_TRAVEL",
                            "FULL_TRAVEL"}:
            gain = {"ONE_THIRD_TRAVEL": 1.0/3.0,
                    "TWO_THIRDS_TRAVEL": 2.0/3.0,
                    "FULL_TRAVEL": 1.0}[motion_class]
            rc_entries[-1]["motion_law"] = (
                "rigid_translation_dx_mm=%.12g*(-27.5*q4_rad)" % gain)
        elif motion_class == "FOLLOWER_LINK4":
            rc_entries[-1]["motion_law"] = (
                "rigid_link4_FK_from_q0; no mesh scaling or distributed deformation")
    rc_mass_rows.append({
        "name": name, "host_link": meta.get("host_link"), "kind": meta.get("kind"),
        "material": meta.get("material"), "volume_mm3": float(V),
        "geometry_role": meta.get("geometry_role"),
        "mass_counted": meta.get("mass_counted"),
        "overlap_disposition": meta.get("overlap_disposition"),
        "cg_mm_A0": [float(x) for x in cg],
        "inertia_vol_mm5_about_cg_A0": [[float(x) for x in row] for row in I_tot],
    })
    print("rc part %-44s %s" % (name, meta.get("kind")))
    # free the part's shape memory progressively on this memory-tight host
    try:
        doc.removeObject(obj.Name)
    except Exception:
        pass
    gc.collect()

mass_path = os.path.join(PACK_DIR, "rc_parts_mass_geometry.json")
with open(mass_path, "w", encoding="utf-8", newline="\n") as f:
    json.dump({"schema": "ROUTE_C_PARTS_MASS_GEOMETRY_V1",
               "generated_utc": "DETERMINISTIC_REPLAY_NO_WALLCLOCK",
               "units": {"volume": "mm3", "cg": "mm", "inertia_volume": "mm5"},
               "frame": "A0 = B601 base_link frame at q=0",
               "note": "inertia_volume = volume moments about part CG in A0 axes; multiply by density[g/mm3] for mass moments in g*mm2",
               "parts": rc_mass_rows},
              f, indent=2, sort_keys=True)

manifest["files"] = (
    [{"group": "arm_vendor", "entries": copied_arm},
     {"group": "solar", "entries": [solar_entry]},
     {"group": "gripper_rails", "frame_validation": rail_frame_validation,
      "palm_slot": palm_entry, "entries": rail_entries},
     {"group": "route_c_parts", "entries": rc_entries},
     {"group": "route_c_mass_geometry",
      "entries": [{"file": os.path.basename(mass_path), "sha256": sha256_file(mass_path)}]}])
manifest["review_status"] = "PENDING_OWNER_REVIEW"
manifest["next_stage_authorized"] = False
manifest["release_credit"] = False

man_path = os.path.join(PACK_DIR, "MANIFEST.json")
with open(man_path, "w", encoding="utf-8", newline="\n") as f:
    json.dump(manifest, f, indent=2, sort_keys=True)
n_invalid = sum(1 for e in rc_entries if not e.get("valid"))
print("MANIFEST sha256:", sha256_file(man_path))
if n_invalid or len(rc_entries) != len(part_meta):
    print("PREP_INCOMPLETE")
    raise SystemExit(2)
print("PREP_COMPLETE")
