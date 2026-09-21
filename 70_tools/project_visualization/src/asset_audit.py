"""VIZ-Gate 0 Phase 1 -- asset inventory + verification.

Writes 40_evidence/artifacts/visualization/tables/asset_audit.csv (new file; the existing
gate_artifact_protection_manifest.csv is NOT touched).

Verification performed here (all read-only):
  * project CAD STLs: mesh bbox recomputed with trimesh and compared against
    the bbox predicted from the primitive list in
    20_engineering/cad/spacecraft_layout/model_specs_v0.json (mm) -> unit call m vs mm.
  * B601 display meshes (units previously UNVERIFIED): per-link bbox compared
    against the URDF joint-origin offsets (e.g. base_link bbox top 0.0826 vs
    joint1 z offset 0.08465 m; link2 x span 0.321 vs joint3 offset 0.264 m).
    If the meshes were mm the ratios would be ~1000x.
  * sha256 of every asset, face counts, mass/CoM pulled from the JSON specs /
    mass_inertia_budget_v1.csv / URDF inertials.
"""
import _viz_bootstrap as vb
import csv
import json
import os
import xml.etree.ElementTree as ET

import numpy as np

from mesh_utils import load_mesh, sha256_of

REPO = vb.REPO_ROOT
COMMIT = vb.repo_commit_short()
OUT_CSV = os.path.join(vb.VIZ_TABLES_DIR, "asset_audit.csv")

COLUMNS = ["asset_id", "asset_type", "path", "exists", "units", "frame",
           "parent_frame", "mesh_bounds", "mass", "com", "confidence",
           "git_commit", "sha256", "usable_for_render", "blocking_issue"]

MODELS = ["servicer_12U_v0", "servicer_6U_v0", "target_satellite_v0",
          "target_debris_v0", "robot_mount_adapter_v0"]
MODEL_FRAME = {"servicer_12U_v0": "S", "servicer_6U_v0": "S",
               "target_satellite_v0": "T", "target_debris_v0": "D",
               "robot_mount_adapter_v0": "M"}


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def primitives_bbox_mm(prims):
    """Predicted bbox (mm) of the union of the JSON primitives."""
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    for p in prims:
        c = np.asarray(p["center_offset_mm"], float)
        d = p["dims_mm"]
        if p["shape"] == "box":
            h = np.array([d["length_x"], d["width_y"], d["height_z"]]) / 2.0
        else:  # cylinder
            r, L, ax = d["radius"], d["cyl_length"], d.get("axis", "z")
            h = {"x": np.array([L / 2.0, r, r]),
                 "y": np.array([r, L / 2.0, r]),
                 "z": np.array([r, r, L / 2.0])}[ax]
        lo = np.minimum(lo, c - h)
        hi = np.maximum(hi, c + h)
    return lo, hi


def fmt_bounds(b):
    return "[" + ",".join(f"{v:.4f}" for v in b[0]) + "]..[" + \
           ",".join(f"{v:.4f}" for v in b[1]) + "]"


def load_budget():
    out = {}
    with open(vb.MASS_BUDGET_CSV, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["object_id"]] = r
    return out


def urdf_inertials(urdf_path):
    root = ET.parse(urdf_path).getroot()
    out = {}
    for le in root.findall("link"):
        ine = le.find("inertial")
        m = float(ine.find("mass").get("value"))
        o = ine.find("origin")
        xyz = [float(v) for v in (o.get("xyz") or "0 0 0").split()]
        out[le.get("name")] = (m, xyz)
    return out


def urdf_joint_offsets(urdf_path):
    root = ET.parse(urdf_path).getroot()
    out = {}
    for je in root.findall("joint"):
        o = je.find("origin")
        xyz = [float(v) for v in (o.get("xyz") or "0 0 0").split()]
        out[je.get("name")] = np.asarray(xyz, float)
    return out


def main():
    rows = []

    def add(asset_id, asset_type, path, units="n/a", frame="", parent="",
            bounds="", mass="", com="", conf="", usable="yes", issue=""):
        exists = os.path.isfile(path)
        rows.append({
            "asset_id": asset_id, "asset_type": asset_type, "path": rel(path),
            "exists": "yes" if exists else "NO",
            "units": units, "frame": frame, "parent_frame": parent,
            "mesh_bounds": bounds, "mass": mass, "com": com,
            "confidence": conf, "git_commit": COMMIT,
            "sha256": sha256_of(path) if exists else "",
            "usable_for_render": usable if exists else "no",
            "blocking_issue": issue if exists else "FILE MISSING",
        })

    budget = load_budget()
    specs = {e["key"]: e["spec"] for e in json.load(
        open(os.path.join(vb.CAD_DIR, "model_specs_v0.json"), encoding="utf-8"))}

    # ---- project CAD models (5x: stl + json + step + urdf stub) ----
    for mid in MODELS:
        d = os.path.join(vb.CAD_DIR, mid)
        spec = specs[mid]
        frame = MODEL_FRAME[mid]
        b = budget.get(mid, {})
        mass = b.get("mass_kg", spec.get("target_mass_kg", ""))
        com = (f"[{b['cg_x_m']},{b['cg_y_m']},{b['cg_z_m']}] m"
               if b else "budget row absent")
        stl = os.path.join(d, f"{mid}.stl")
        issue = ""
        units = "UNVERIFIED"
        bounds = ""
        if os.path.isfile(stl):
            mesh = load_mesh(stl)
            bounds = fmt_bounds(np.asarray(mesh.bounds))
            lo, hi = primitives_bbox_mm(spec["primitives"])
            err_m = np.max(np.abs(np.asarray(mesh.bounds)
                                  - np.stack([lo, hi]) / 1000.0))
            if err_m < 0.002:
                units = (f"m (verified: bbox matches JSON primitives within "
                         f"{err_m*1000:.2f} mm)")
            else:
                units = f"SUSPECT (bbox vs JSON primitives max err {err_m:.4f} m)"
                issue = "unit check failed against JSON primitives"
        if mid == "servicer_12U_v0":
            issue = (issue + "; " if issue else "") + (
                "flange primitive spatially overlaps robot_mount_adapter_v0 "
                "when both are drawn (display-only interpenetration)")
        add(f"{mid}_stl", "mesh_stl", stl, units, frame, "-", bounds,
            mass, com, spec.get("confidence", ""), "yes", issue)
        jissue = ""
        if mid == "servicer_6U_v0":
            jissue = ("camera FOV absent in JSON (only camera_boresight_S); "
                      "must be annotated 'absent', never fabricated")
        if mid == "servicer_12U_v0":
            jissue = ("camera_fov_cone present (apex [210,0,80] mm, half-angle "
                      "20 deg); grasp_points_mm empty by design (servicer)")
        add(f"{mid}_json", "feature_spec_json", os.path.join(d, f"{mid}.json"),
            "mm", frame, "-", "", mass, com, spec.get("confidence", ""),
            "yes", jissue)
        add(f"{mid}_step", "cad_step", os.path.join(d, f"{mid}.step"),
            "mm (assumed, unconsumed)", frame, "-", "", "", "", "",
            "no", "not consumed by matplotlib pipeline (STL used instead)")
        add(f"{mid}_urdf", "urdf_stub", os.path.join(d, f"{mid}.urdf"),
            "m", frame, "-", "", mass, "", "low", "no",
            "single-body stub; not needed for VIZ-Gate 0 render")
    add("model_specs_v0", "feature_spec_json",
        os.path.join(vb.CAD_DIR, "model_specs_v0.json"), "mm", "-", "-",
        "", "", "", "low", "yes", "")

    # ---- B601 arm: URDF + 10 display meshes (unit judgment) ----
    joff = urdf_joint_offsets(vb.URDF_PATH)
    inert = urdf_inertials(vb.URDF_PATH)
    add("arm_b601_v1_urdf", "urdf", vb.URDF_PATH, "m", "A0(=M)", "M", "",
        f"{sum(m for m, _ in inert.values()):.4f} kg total", "per-link inertials",
        "medium (vendor-consistent inertials; weighing pending)", "yes",
        "T_MA0 = identity nominal per header comment; gripper prismatic "
        "fingers locked at q=0 for display")

    mesh_expect = {
        # per-link evidence pairs: (mesh feature, URDF reference, note)
        "base_link": ("bbox z_max", float(joff["joint1"][2]),
                      "joint1 z offset"),
        "link1": ("bbox z_max", float(joff["joint2"][2]), "joint2 z offset"),
        "link2": ("bbox x_span", abs(float(joff["joint3"][0])),
                  "joint3 |x| offset"),
        "link3": ("bbox x_span", abs(float(joff["joint4"][0])),
                  "joint4 |x| offset"),
        "link4": ("bbox x_span", abs(float(joff["joint5"][0])),
                  "joint5 |x| offset"),
        "link5": ("bbox z_max", float(joff["joint6"][2]), "joint6 z offset"),
        "link6": ("bbox r", float(joff["gripper_joint"][2]),
                  "gripper_joint z offset"),
        "gripper_link": ("bbox x_span", abs(float(joff["gripper_joint1"][0])),
                         "gripper_joint1 |x| offset"),
        "gripper_left": ("bbox span", 0.0715, "finger stroke upper limit"),
        "gripper_right": ("bbox span", 0.0715, "finger stroke upper limit"),
    }
    for name in ["base_link", "link1", "link2", "link3", "link4", "link5",
                 "link6", "gripper_link", "gripper_left", "gripper_right"]:
        p = os.path.join(vb.MESH_DIR, f"{name}.STL")
        mesh = load_mesh(p)
        bnd = np.asarray(mesh.bounds)
        diag = float(np.linalg.norm(bnd[1] - bnd[0]))
        feat, ref, refnote = mesh_expect[name]
        if "z_max" in feat:
            val = float(bnd[1, 2])
        elif "x_span" in feat:
            val = float(bnd[1, 0] - bnd[0, 0])
        else:
            val = diag
        # scale call: meters if diag < 2 m AND same order as URDF reference
        if diag < 2.0 and (ref == 0 or 0.2 < (val / ref if ref else 1) < 5.0):
            units = (f"m (VERIFIED: {feat} {val:.4f} vs {refnote} {ref:.4f}; "
                     f"a mm mesh would be ~1000x off)")
            issue = (f"{len(mesh.faces)} faces; display decimation to "
                     f"<=20000 faces (vertex clustering, display-only)")
            usable = "yes"
        else:
            units = f"SUSPECT (diag {diag:.3f}, {feat} {val:.4f} vs {ref:.4f})"
            issue = "unit judgment failed"
            usable = "no"
        m, cg = inert.get(name, ("", ""))
        add(f"b601_mesh_{name}", "mesh_stl", p, units, name,
            "URDF chain (parent per joint)", fmt_bounds(bnd),
            f"{m} kg (URDF inertial)", f"{cg} (link frame)",
            "medium", usable, issue)

    # ---- kinematics truth + placement rule (read-only imports) ----
    add("b601_model_py", "code_truth_fk",
        os.path.join(REPO, "30_simulation", "sim_05_free_floating_arm", "b601_model.py"),
        "m/rad", "S", "-", "", "", "", "validated (sim_05 mainline)", "yes",
        "FK numerical truth; render chain is independent and cross-checked "
        "(<1 mm / <0.1 deg, see b601_renderer.fk_alignment_selftest)")
    add("sim09_adapters_py", "code_scene_placement",
        os.path.join(REPO, "30_simulation", "sim_09_grasp_evaluator", "src", "adapters.py"),
        "m/rad", "I/S", "-", "", "", "", "validated (E0/E1 anchored)", "yes",
        "scene_placement + general_capture_scenario imported read-only "
        "(never re-derived)")
    add("sim09_e1_thin_slice_py", "code_candidate_defs",
        os.path.join(REPO, "30_simulation", "sim_09_grasp_evaluator", "src", "e1_thin_slice.py"),
        "m", "D", "-", "", "", "",
        "E1 grid (P1/P2/P3 frames match E1.5 geometry_group_keys)", "yes",
        "E1.5 runner itself lives outside this repo; E1.5 scenario_hash is "
        "roll-parameterized and differs from E1 for identical case_ids")
    add("sim09_target_propagation_py", "code_truth_propagation",
        os.path.join(REPO, "30_simulation", "sim_09_grasp_evaluator", "src",
                     "target_propagation.py"),
        "m/rad/s", "I", "-", "", "", "", "validated (t5 anchor)", "yes", "")
    add("mass_inertia_budget_v1", "mass_budget_csv", vb.MASS_BUDGET_CSV,
        "kg, m, kg m^2", "per object", "-", "", "", "",
        "low (self-defined block-model densities)", "yes", "")
    add("frame_tree_v1", "frame_ssot_yaml", vb.FRAME_TREE_YAML,
        "mm (converted to m in code)", "tree", "-", "", "", "",
        "nominal_frozen_v1", "yes", "")
    add("coordinate_frame_definition_v0", "frame_ssot_md", vb.COORD_SSOT_MD,
        "mm/deg", "tree", "-", "", "", "", "nominal_frozen_v1 (sec 3.1)",
        "yes", "")

    # ---- E1.5 snapshot (the ONLY allowed E1.5 source) ----
    snap = vb.SNAPSHOT_DIR
    e15 = json.load(open(os.path.join(
        snap, "results__sim_09_grasp_evaluator__e15_geometry_manifest.json"),
        encoding="utf-8"))
    src_commit = e15["source_commit"][:7]
    snap_files = {
        "e15_geometry_manifest":
            ("results__sim_09_grasp_evaluator__e15_geometry_manifest.json",
             "24 groups / 96 detail rows; roll grid -90..+90 step 30; "
             "selections: P1|tc=0|pose_6d SELECTED roll 0"),
        "e15_results_72cases":
            ("results__sim_09_grasp_evaluator__e15_results_72cases.csv",
             "target_id = target_debris_v0 for ALL 72 rows (P1/P2/P3 are "
             "debris rim points, NOT the 22 kg satellite); admissible 0/72; "
             "tumble axis/omega not restated in snapshot -> E1 in-repo values "
             "are context only"),
        "e15_geometry_roll_details":
            ("results__sim_09_grasp_evaluator__e15_geometry_roll_details.csv",
             "hard-screen feasible rolls: only P1|tc=0 (pose_6d: -90..+90 all "
             "7; approach_5d: unconstrained)"),
        "e15_run_manifest":
            ("results__sim_09_grasp_evaluator__e15_run_manifest.json", ""),
        "e15_gate_check":
            ("results__sim_09_grasp_evaluator__e15_gate_check.json",
             "gate REPEAT_E1_5; state_counts SAFE 0 / UNKNOWN 3 / UNSAFE 69 "
             "-> no figure may show any grasp as physically safe"),
        "e15_summary_metrics":
            ("tables__sim_09_grasp_evaluator__e15_summary_metrics.csv", ""),
    }
    for aid, (fn, note) in snap_files.items():
        add(aid, "e15_snapshot", os.path.join(snap, fn),
            "SI (per column headers)", "-", "-", "", "", "",
            f"E1.5 evidence snapshot of commit {src_commit}", "yes", note)

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {rel(OUT_CSV)}: {len(rows)} rows")
    bad = [r for r in rows if r["exists"] != "yes"
           or r["units"].startswith("SUSPECT")]
    for r in bad:
        print("  PROBLEM:", r["asset_id"], r["exists"], r["units"])
    print("problems:", len(bad))


if __name__ == "__main__":
    main()
