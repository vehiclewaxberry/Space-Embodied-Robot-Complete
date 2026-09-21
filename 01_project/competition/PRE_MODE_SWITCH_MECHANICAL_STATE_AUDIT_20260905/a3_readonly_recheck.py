"""Independent read-only A3 audit. Never imports/runs the production scripts.

Only writes under this script's audit directory. Uses saved poses, accepted
URDF XML and binary-STL vertices to verify rigid transforms and AABB numbers.
No optimizer, collision query, CAD application, FEA or dynamics is run.
"""
from pathlib import Path
import ast
import csv
import hashlib
import json
import math
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(r"F:\China Graduate Future Flight Vehicle Innovation Competition")
BASE = ROOT / "20_engineering/MECHANICAL_ENGINEERING_RELEASE_R2/_work/mode_a_native_design_r1"
OUT = Path(__file__).resolve().parent
assert OUT == ROOT / "01_project/competition/PRE_MODE_SWITCH_MECHANICAL_STATE_AUDIT_20260905"
URDF = ROOT / "20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"
sources = set()

def text_read(path):
    sources.add(path.resolve())
    return path.read_text(encoding="utf-8-sig")

def get_json(rel):
    return json.loads(text_read(BASE / rel))

def get_csv(rel):
    return list(csv.DictReader(text_read(BASE / rel).splitlines()))

def write_csv(name, rows):
    with (OUT / name).open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

# Read the complete bounded A3 text evidence set, including partial records,
# to make the read boundary and line-reference lookup reproducible.
for path in BASE.rglob("*"):
    if path.suffix in {".json", ".csv", ".py", ".md"}:
        text_read(path)

xml = ET.fromstring(text_read(URDF))
text_read(ROOT / "20_engineering/config/geometry/frame_tree_v1.yaml")
joints = xml.findall("joint")
rev = [j for j in joints if j.get("type") == "revolute"]
assert len(rev) == 6
limits_deg = np.degrees(np.array([[float(j.find("limit").get(k)) for k in ("lower", "upper")] for j in rev]))
names16 = ["link" + str(i) for i in range(1, 7)]
names_full = ["base_link"] + names16 + ["gripper_link", "gripper_left", "gripper_right"]

def xyz(el, name):
    return np.array([float(v) for v in el.get(name, "0 0 0").split()])

def origin(el):
    transform = np.eye(4)
    if el is not None:
        transform[:3, :3] = Rotation.from_euler("xyz", xyz(el, "rpy")).as_matrix()
        transform[:3, 3] = xyz(el, "xyz")
    return transform

vertices = {}
mesh_metadata = []
for link in xml.findall("link"):
    n = link.get("name")
    geom = link.find("visual")
    mesh = geom.find("geometry/mesh")
    fp = URDF.parent / mesh.get("filename")
    sources.add(fp.resolve())
    data = fp.read_bytes()
    count = int.from_bytes(data[80:84], "little")
    assert len(data) == 84 + 50 * count, fp
    triangles = np.frombuffer(data, dtype=np.dtype([("normal", "<f4", (3,)), ("v", "<f4", (3, 3)), ("attr", "<u2")]), offset=84, count=count)
    pts = np.unique(triangles["v"].reshape(-1, 3), axis=0).astype(float)
    scale = np.array([float(v) for v in mesh.get("scale", "1 1 1").split()])
    vis = origin(geom.find("origin"))
    pts = (pts * scale) @ vis[:3, :3].T + vis[:3, 3]
    vertices[n] = pts
    mesh_metadata.append(dict(component=n, triangle_count=count, unique_vertex_count=len(pts), sha256=hashlib.sha256(data).hexdigest().upper(), visual_origin_identity=bool(np.allclose(vis, np.eye(4))), mass_kg=float(link.find("inertial/mass").get("value"))))
write_csv("a3_mesh_inputs.csv", mesh_metadata)

def placed(q_deg, rv, names):
    values = dict(zip((j.get("name") for j in rev), np.radians(q_deg)))
    world = {"base_link": np.eye(4)}
    for j in joints:
        p = j.find("parent").get("link")
        c = j.find("child").get("link")
        motion = np.eye(4)
        jt = j.get("type")
        axis = xyz(j.find("axis"), "xyz") if j.find("axis") is not None else np.zeros(3)
        q = values.get(j.get("name"), 0.0)  # saved A3 fingers are at q=0
        if jt == "revolute":
            motion[:3, :3] = Rotation.from_rotvec(axis / np.linalg.norm(axis) * q).as_matrix()
        elif jt == "prismatic":
            motion[:3, 3] = axis * q
        world[c] = world[p] @ origin(j.find("origin")) @ motion
    mount = Rotation.from_rotvec(rv).as_matrix()
    return {n: ((vertices[n] @ world[n][:3, :3].T + world[n][:3, 3]) * 1000) @ mount.T for n in names}

def bounds(pts):
    p = np.vstack(list(pts.values()))
    return p.min(0), p.max(0)

def margins(row, label):
    q = np.array(row["q_deg"])
    m = np.minimum(q - limits_deg[:, 0], limits_deg[:, 1] - q)
    return [dict(case=label, requested_margin_deg=row["margin_deg"], joint=i+1, q_deg=float(q[i]), lower_deg=float(limits_deg[i, 0]), upper_deg=float(limits_deg[i, 1]), actual_nearest_margin_deg=float(m[i]), on_hard_stop_within_1e_minus4_deg=bool(abs(m[i]) <= 1e-4)) for i in range(6)]

c = get_json("01_a3_2c/A3_02C_RESULTS.json")
d = get_json("04_a3_2d/A3_2D_RESULTS.json")
gd = get_json("04_a3_2d/A3_2D_FINAL_GATE.json")
p1 = get_json("03_a3_4/_a3_4_part1.json")
g4 = get_json("03_a3_4/A3_4_FINAL_GATE.json")
g3 = get_json("02_a3_3/A3_3_FINAL_GATE.json")
h3 = get_json("02_a3_3/A3_36_A3_4_HANDOFF.json")
meta = get_json("02_a3_3/_candidates_meta.json")
subset = get_json("04_a3_2d/A3_2D_SUBSET_DIAGNOSTIC.json")
numeric = []
jointrows = []
box = np.array([366., 226.3, 226.3])

for phase, dataset in [("A3.2c", c), ("A3.2d", d)]:
    for i, row in enumerate(dataset["results"]):
        label = f"{phase}:{i}:{row.get('link_set', 'FULL')}:{row['margin_deg']}:{row['mode']}:{row.get('decolocate', '')}"
        names = names16 if row.get("link_set") == "CORRIDOR" else names_full
        pts = placed(row["q_deg"], row["mount_rotvec"], names)
        lo, hi = bounds(pts)
        ext = hi - lo
        saved = row.get("sorted_LWH_mm", row.get("full_sorted_LWH_mm"))
        err = float(np.max(np.abs(np.sort(ext)[::-1] - saved)))
        bestprot = float(np.max((np.sort(ext)[::-1] - box) / 2))
        numeric.append(dict(case=label, component_count=len(names), extent_X_mm=ext[0], extent_Y_mm=ext[1], extent_Z_mm=ext[2], longest_axis="XYZ"[int(ext.argmax())], recomputed_max_sorted_error_mm=err, recomputed_worst_protrusion_mm=bestprot, saved_worst_protrusion_mm=row["worst_protrusion_mm"], recomputed_inside_box=bool(np.all(np.sort(ext)[::-1] <= box + 1e-6)), saved_inside_box=row["inside_box"], root_origin_after_recenter_X_mm=-(lo[0]+hi[0])/2, root_origin_after_recenter_Y_mm=-(lo[1]+hi[1])/2, root_origin_after_recenter_Z_mm=-(lo[2]+hi[2])/2))
        jointrows.extend(margins(row, label))
write_csv("a3_saved_pose_aabb_recheck.csv", numeric)

for i, row in enumerate(subset["results"]):
    jointrows.extend(margins(row, f"SUBSET:{i}:{row['link_set']}"))
write_csv("a3_joint_margin_recheck.csv", jointrows)

primary = next(r for r in c["results"] if r["link_set"] == "CORRIDOR" and r["margin_deg"] == 2 and r["mode"] == "FIT")
pl16 = placed(primary["q_deg"], primary["mount_rotvec"], names16)
plfull = placed(primary["q_deg"], primary["mount_rotvec"], names_full)
l16, h16 = bounds(pl16)
lfull, hfull = bounds(plfull)
centre16 = (l16+h16)/2
centrefull = (lfull+hfull)/2
shift = centre16-centrefull
st = get_csv("03_a3_4/A3_41_FULLARM_STATION_ENVELOPE.csv")
absrows = []
for r in st:
    vals = {k: float(r[k]) for k in ("station_mm", "Y_min", "Y_max", "Z_min", "Z_max", "width_Y", "width_Z")}
    vals.update(Y_outside_fixed_box=vals["Y_min"] < -113.15 or vals["Y_max"] > 113.15, Z_outside_fixed_box=vals["Z_min"] < -113.15 or vals["Z_max"] > 113.15)
    vals["any_outside_fixed_box"] = vals["Y_outside_fixed_box"] or vals["Z_outside_fixed_box"]
    absrows.append(vals)
write_csv("a3_station_absolute_coordinate_recheck.csv", absrows)
xs = np.array([r["station_mm"] for r in absrows])
axislo, axishi = -(hfull-lfull)/2, (hfull-lfull)/2
expected_bins = math.ceil(axishi[0])-math.floor(axislo[0])
pockets = get_csv("03_a3_4/A3_46_LOCAL_POCKET_REQUIREMENTS.csv")
baseline = 80.3 * 226.3 * (xs.max()-xs.min()) / 1000
extra = sum(float(p["extra_Y_over_corridor_mm"]) * 226.3 * float(p["x_interval_mm"]) for p in pockets) / 1000
mono = float((hfull-lfull)[1] * (hfull-lfull)[2] * (xs.max()-xs.min()) / 1000)
union_range = lambda a, b: max(0., min(a[1], b[1])-max(a[0], b[0]))
zr = {z["zone"]: [z["x_start"], z["x_end"]] for z in g4["zones"]}
min_case = min(d["results"], key=lambda r:r["worst_protrusion_mm"])
best2 = min((r for r in d["results"] if r["margin_deg"] >= 2), key=lambda r:r["worst_protrusion_mm"])
joint0 = [r for r in jointrows if r["case"].startswith("A3.2c:") and ":CORRIDOR:0.0:THIN:" in r["case"]]
script_constants = []
for sp in sorted((BASE / "99_tools").glob("*.py")):
    tree = ast.parse(text_read(sp))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "JOINTS" not in targets and "FIXED" not in targets:
            continue
        values = ast.literal_eval(node.value)
        for rec in values:
            child, parent, translation, rpy = rec[:4]
            uj = next(j for j in joints if j.find("child").get("link") == child)
            exact_orig = bool(np.array_equal(translation, xyz(uj.find("origin"), "xyz")) and np.array_equal(rpy, xyz(uj.find("origin"), "rpy")))
            correct_parent = parent == uj.find("parent").get("link")
            axis_match = bool(np.array_equal(rec[4], xyz(uj.find("axis"), "xyz"))) if "JOINTS" in targets else True
            limit_match = bool(np.array_equal(rec[-2:], [float(uj.find("limit").get(k)) for k in ("lower", "upper")])) if "JOINTS" in targets and len(rec) >= 7 else True
            script_constants.append(dict(script=sp.name, child=child, line=node.lineno, urdf_origin_numbers_exact_match=exact_orig, parent_match=correct_parent, axis_match_when_present=axis_match, limits_match_when_present=limit_match))
write_csv("a3_hardcoded_kinematics_recheck.csv", script_constants)

component_table = get_csv("03_a3_4/A3_43_COMPONENT_TRUTH_TABLE.csv")
meshhash = {r["component"]: r["sha256"] for r in mesh_metadata}
accepted_hash = hashlib.sha256(URDF.read_bytes()).hexdigest().upper()
current_c_hash = hashlib.sha256((BASE / "01_a3_2c/A3_02C_RESULTS.json").read_bytes()).hexdigest().upper()

summary = {
    "audit_scope": "saved-pose URDF/raw-STL AABB and arithmetic only; no production-script execution, no optimization, no collision queries",
    "a3_2c_case_count": len(c["results"]),
    "a3_2d_case_count": len(d["results"]),
    "raw_stl_aabb_max_abs_error_mm": max(r["recomputed_max_sorted_error_mm"] for r in numeric),
    "aabb_inside_classification_mismatches": sum(r["saved_inside_box"] != r["recomputed_inside_box"] for r in numeric),
    "kinematic_origin_parent_axis_limits_all_match_urdf": all(r["urdf_origin_numbers_exact_match"] and r["parent_match"] and r["axis_match_when_present"] and r["limits_match_when_present"] for r in script_constants),
    "urdf_matches_A3_registered_hash": accepted_hash == "1BC2B7483CD8025D08BA6EADFD9E1F3B0477121714E7CF4DDC1794D9E471C164",
    "all10_mesh_hashes_match_A3_43": all(r["source_sha256"] == meshhash[r["component_id"]] for r in component_table if r["component_id"] in meshhash),
    "A3_36_upstream_hash_matches_current_A3_02C": current_c_hash == h3["source_hashes"]["A3_02C_RESULTS"],
    "arm_model_mass_kg": sum(r["mass_kg"] for r in mesh_metadata),
    "primary_links16_extent_xyz_mm": (h16-l16).tolist(),
    "primary_full_extent_xyz_mm": (hfull-lfull).tolist(),
    "primary_root_origin_a3_3_mm": (-centre16).tolist(),
    "primary_root_origin_a3_4_mm": (-centrefull).tolist(),
    "a3_4_vs_a3_3_implicit_recentre_translation_mm": shift.tolist(),
    "handoff_ejection_clearance_mm": h3["ejection_min_clearance_mm"],
    "gate_primary_ejection_clearance_mm": g3["summary"][h3["selected_candidate"]]["ejection_min_clearance_mm"],
    "handoff_clearance_matches_cand5thin": h3["ejection_min_clearance_mm"] == g3["summary"]["CAND_5_THIN"]["ejection_min_clearance_mm"],
    "station_rows": len(st),
    "station_x_min_mm": float(xs.min()),
    "station_x_max_mm": float(xs.max()),
    "full_x_span_mm": float((hfull-lfull)[0]),
    "full_extent_1mm_bins_expected": expected_bins,
    "bins_missing_from_csv": expected_bins-len(st),
    "recorded_bins_Y_absolute_outside": sum(r["Y_outside_fixed_box"] for r in absrows),
    "recorded_bins_Z_absolute_outside": sum(r["Z_outside_fixed_box"] for r in absrows),
    "recorded_bins_any_absolute_outside": sum(r["any_outside_fixed_box"] for r in absrows),
    "recorded_bins_widthY_gt_226p3": sum(r["width_Y"] > 226.3 for r in absrows),
    "recorded_bins_widthZ_gt_226p3": sum(r["width_Z"] > 226.3 for r in absrows),
    "volume_raw_links16_aabb_cm3": float(np.prod(h16-l16)/1000),
    "volume_rounded_links16_aabb_cm3": 353.6*80.3*205.1/1000,
    "volume_script_baseline_cm3": float(baseline),
    "volume_script_extra_cm3": extra,
    "volume_script_piecewise_cm3": float(baseline+extra),
    "volume_script_monolithic_cm3": mono,
    "volume_actual_full_aabb_cm3": float(np.prod(hfull-lfull)/1000),
    "volume_script_ratio": mono/(baseline+extra),
    "zones_x_overlap_mm": {a+" & "+b:union_range(zr[a],zr[b]) for i,a in enumerate(zr) for b in list(zr)[i+1:]},
    "gross_remaining_width_mm": 226.3-(h16-l16)[1],
    "centered_side_width_each_mm": (226.3-(h16-l16)[1])/2,
    "a3_2d_inside_count": sum(r["inside_box"] for r in d["results"]),
    "a3_2d_best0_protrusion_mm": min_case["worst_protrusion_mm"],
    "a3_2d_best2_protrusion_mm": best2["worst_protrusion_mm"],
    "a3_2d_best2_decolocate": best2["decolocate"],
    "a3_2d_corridor_thickness_range_mm": [min(r["corridor_thickness_mm"] for r in d["results"]),max(r["corridor_thickness_mm"] for r in d["results"])],
    "a3_2d_overlap_range_mm": [min(r["root_distal_overlap_mm"] for r in d["results"]),max(r["root_distal_overlap_mm"] for r in d["results"])],
    "cand0thin_actual_margins_deg": [r["actual_nearest_margin_deg"] for r in joint0],
    "cand0thin_hard_stop_count_within_1e_minus4_deg": sum(r["on_hard_stop_within_1e_minus4_deg"] for r in joint0),
    "subset_records_missing_mount_rotvec": sum("mount_rotvec" not in r for r in subset["results"]),
    "subset_records_count": len(subset["results"]),
}
(OUT / "a3_numeric_recheck.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
(OUT / "a3_sources.txt").write_text("\n".join(str(p) for p in sorted(sources)) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2, ensure_ascii=False))
