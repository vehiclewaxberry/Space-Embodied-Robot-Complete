# -*- coding: utf-8 -*-
"""F3-P3: Top-level assembly with fast clearance verification.

Uses bbox pre-filtering + approximate distance for speed.
"""
from __future__ import print_function
import faulthandler
import json
import hashlib
import math
import os
import sys
import time
import traceback

faulthandler.enable()
faulthandler.dump_traceback_later(300, repeat=True)

WS = r"F:\Space-Embodied-Robot-HAG_A_20260804"
V23_STEP = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\Space_Embodied_Robot_CAD_V2_3_NATIVE_INTEGRATION\evidence\config_steps\native_STOWED.step"
VISUAL_PACKAGES_DIR = os.path.join(WS, r"12_f3_p1_hifi_attachment\01_visual_packages")
OUT_DIR = os.path.join(WS, r"12_f3_p1_hifi_attachment\15_f3_p3_top_assembly")

LOG_PATH = os.path.join(OUT_DIR, "f3_p3_fast.log")

B50_TRANSFORMS = {
    "base_link": {"R": [[-1,0,0],[0,-1,0],[0,0,1]], "t": [0.085, -0.022, -3.395]},
    "link1": {"R": [[-1,0,0],[0,-1,0],[0,0,1]], "t": [0.318, -0.149, -84.05]},
    "link2": {"R": [[-1,0,0],[0,0,-1],[0,-1,0]], "t": [-19.747, 143.464, -31.68]},
    "link3": {"R": [[-1,0,0],[0,0,-1],[0,-1,0]], "t": [244.02, 144.672, -31.539]},
    "link4": {"R": [[-1,0,0],[0,0,-1],[0,-1,0]], "t": [-0.052, 199.167, -29.99]},
    "link5": {"R": [[-1,0,0],[0,1,0],[0,0,-1]], "t": [-75.775, -0.087, 236.219]},
    "link6": {"R": [[3.67e-6,-7.35e-6,1.0],[0,1.0,7.35e-6],[-1.0,-2.7e-11,3.67e-6]], "t": [-195.036, 0.006, -100.555]},
    "gripper_link": {"R": [[-1,0,0],[0,1.0,7.35e-6],[0,7.35e-6,-1.0]], "t": [-260.264, 0.006, 195.037]},
}

LINK_NAME_MAP = {
    "base_link": "base_link",
    "link1": "link1",
    "link2": "link2",
    "link3": "link3",
    "link4": "link4",
    "link5": "link5",
    "link6": "link6",
    "gripper_link": "gripper_link",
    "gripper_left": "gripper_left",
    "gripper_right": "gripper_right",
}


def mark(stage, **data):
    record = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "pid": os.getpid(), "stage": stage}
    record.update(data)
    line = json.dumps(record, ensure_ascii=False)
    print(line, flush=True)
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        print("LOG_ERROR: " + str(e), file=sys.stderr, flush=True)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def matmul(A, B):
    return [[sum(A[i][k]*B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def matvec(M, v):
    return [sum(M[i][k]*v[k] for k in range(3)) for i in range(3)]


def rpy_to_matrix(rpy):
    r, p, y = rpy
    Rx = [[1,0,0],[0,math.cos(r),-math.sin(r)],[0,math.sin(r),math.cos(r)]]
    Ry = [[math.cos(p),0,math.sin(p)],[0,1,0],[-math.sin(p),0,math.cos(p)]]
    Rz = [[math.cos(y),-math.sin(y),0],[math.sin(y),math.cos(y),0],[0,0,1]]
    return matmul(matmul(Rz, Ry), Rx)


def rodrigues(axis, angle):
    K = [[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]]
    K2 = matmul(K, K)
    R = [[0]*3 for _ in range(3)]
    for i in range(3):
        for j in range(3):
            R[i][j] = (math.cos(angle) * (1 if i==j else 0) +
                      math.sin(angle) * K[i][j] +
                      (1 - math.cos(angle)) * K2[i][j])
    return R


def parse_urdf(urdf_path):
    import xml.etree.ElementTree as ET
    tree = ET.parse(urdf_path)
    root = tree.getroot()
    joints = {}
    for j in root.findall("joint"):
        name = j.get("name")
        origin = j.find("origin")
        joints[name] = {
            "type": j.get("type"),
            "parent": j.find("parent").get("link"),
            "child": j.find("child").get("link"),
            "origin_xyz": [float(x) for x in origin.get("xyz").split()] if origin is not None else [0,0,0],
            "origin_rpy": [float(x) for x in origin.get("rpy").split()] if origin is not None and origin.get("rpy") else [0,0,0],
            "axis": [float(x) for x in j.find("axis").get("xyz").split()] if j.find("axis") is not None else [0,0,0],
        }
    return joints


def forward_kinematics(joints, q_values):
    frames = {"base_link": {"R": [[1,0,0],[0,1,0],[0,0,1]], "t": [0,0,0]}}
    joint_order = ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6",
                   "gripper_joint", "gripper_joint1", "gripper_joint2"]
    for jname in joint_order:
        j = joints.get(jname)
        if not j:
            continue
        parent = j["parent"]
        child = j["child"]
        if parent not in frames:
            continue
        R_origin = rpy_to_matrix(j["origin_rpy"])
        t_origin = j["origin_xyz"]
        q = q_values.get(jname, 0.0)
        if j["type"] == "revolute" and q != 0.0:
            R_rot = rodrigues(j["axis"], q)
            R_origin = matmul(R_origin, R_rot)
        elif j["type"] == "prismatic" and q != 0.0:
            t_origin = [t_origin[i] + q * j["axis"][i] for i in range(3)]
        parent_frame = frames[parent]
        R_new = matmul(parent_frame["R"], R_origin)
        t_new = [parent_frame["t"][i] + matvec(parent_frame["R"], t_origin)[i] for i in range(3)]
        frames[child] = {"R": R_new, "t": t_new}
    return frames


def transform_bbox(bb, R, t):
    """Transform a bbox by R,t. Returns new bbox."""
    # Transform all 8 corners
    corners = [
        [bb.XMin, bb.YMin, bb.ZMin],
        [bb.XMin, bb.YMin, bb.ZMax],
        [bb.XMin, bb.YMax, bb.ZMin],
        [bb.XMin, bb.YMax, bb.ZMax],
        [bb.XMax, bb.YMin, bb.ZMin],
        [bb.XMax, bb.YMin, bb.ZMax],
        [bb.XMax, bb.YMax, bb.ZMin],
        [bb.XMax, bb.YMax, bb.ZMax],
    ]
    transformed = []
    for c in corners:
        tc = matvec(R, c)
        transformed.append([tc[i] + t[i] for i in range(3)])
    xs = [c[0] for c in transformed]
    ys = [c[1] for c in transformed]
    zs = [c[2] for c in transformed]
    return {
        "xmin": min(xs), "xmax": max(xs),
        "ymin": min(ys), "ymax": max(ys),
        "zmin": min(zs), "zmax": max(zs),
    }


def bbox_distance_dict(bb1, bb2):
    """Compute approximate distance between two bbox dicts."""
    dx = max(0, max(bb1["xmin"] - bb2["xmax"], bb2["xmin"] - bb1["xmax"]))
    dy = max(0, max(bb1["ymin"] - bb2["ymax"], bb2["ymin"] - bb1["ymax"]))
    dz = max(0, max(bb1["zmin"] - bb2["zmax"], bb2["zmin"] - bb1["zmax"]))
    return math.sqrt(dx*dx + dy*dy + dz*dz)


def bbox_to_dict(bb):
    """Convert FreeCAD BoundBox to dict."""
    return {
        "xmin": bb.XMin, "xmax": bb.XMax,
        "ymin": bb.YMin, "ymax": bb.YMax,
        "zmin": bb.ZMin, "zmax": bb.ZMax,
    }


def main():
    t0 = time.time()
    result = {
        "status": "STARTED",
        "exceptions": [],
        "assembly": {},
        "configurations": {},
        "clearance_checks": {},
    }

    try:
        mark("SCRIPT_START")
        mark("BEFORE_FREECAD_IMPORT")
        import FreeCAD as App
        import Part
        mark("AFTER_FREECAD_IMPORT", version=str(App.Version()))

        # === 1. Create top-level assembly ===
        mark("ASSEMBLY_CREATE_START")
        doc = App.newDocument("F3_P3_TOP_ASSEMBLY")

        # Import V2_3 spacecraft
        mark("IMPORT_V23_START", path=V23_STEP)
        Part.insert(V23_STEP, doc.Name)
        spacecraft_objs = [obj for obj in doc.Objects if obj.TypeId == "Part::Feature"]
        mark("IMPORT_V23_COMPLETE", objects=len(spacecraft_objs))

        # Import HIFI visual packages
        b601_objs = []
        visual_packages = {}
        for pkg_file in os.listdir(VISUAL_PACKAGES_DIR):
            if pkg_file.endswith(".FCStd"):
                pkg_name = pkg_file.replace(".FCStd", "")
                pkg_path = os.path.join(VISUAL_PACKAGES_DIR, pkg_file)
                mark("IMPORT_PACKAGE_START", package=pkg_name)
                pkg_doc = App.openDocument(pkg_path)
                for obj in pkg_doc.Objects:
                    if obj.TypeId == "Part::Feature":
                        new_obj = doc.addObject("Part::Feature", obj.Name)
                        new_obj.Shape = obj.Shape.copy()
                        new_obj.Label = obj.Label
                        new_obj.Placement = obj.Placement.copy()
                        b601_objs.append(new_obj)
                App.closeDocument(pkg_doc.Name)
                visual_packages[pkg_name] = True
                mark("IMPORT_PACKAGE_COMPLETE", package=pkg_name)

        # Save assembly
        assembly_path = os.path.join(OUT_DIR, "F3_P3_TOP_ASSEMBLY.FCStd")
        doc.saveAs(assembly_path)
        assembly_sha = sha256_file(assembly_path)
        result["assembly"] = {
            "path": assembly_path,
            "sha256": assembly_sha,
            "objects": len(doc.Objects),
            "spacecraft_objects": len(spacecraft_objs),
            "b601_objects": len(b601_objs),
            "visual_packages": list(visual_packages.keys()),
        }
        mark("ASSEMBLY_SAVED", path=assembly_path, objects=len(doc.Objects))

        # === 2. Fast clearance check using bbox only ===
        mark("CLEARANCE_FAST_START")
        urdf_path = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\spacecraft_layout\arm_b601_v1\arm_b601_v1.urdf"
        joints = parse_urdf(urdf_path)

        # Map object names to links from ownership CSV
        import csv
        ownership_csv = os.path.join(WS, r"05_link_ownership\B601_HIFI_LINK_OWNERSHIP.csv")
        name_to_link = {}
        with open(ownership_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["ownership_class"] == "EXACTLY_ONE_LINK":
                    name_to_link[row["donor_object_id"]] = row["assigned_link"]

        def get_link_from_name(name):
            return name_to_link.get(name, "unknown")

        # Compute spacecraft bboxes
        spacecraft_bboxes = []
        for obj in spacecraft_objs:
            try:
                bb = bbox_to_dict(obj.Shape.BoundBox)
                spacecraft_bboxes.append({"name": obj.Name, "bbox": bb})
            except Exception:
                pass

        mark("SPACECRAFT_BBOXES", count=len(spacecraft_bboxes))

        # Check configurations
        configs = {
            "STOWED": {
                "joint1": math.radians(145.572),
                "joint2": math.radians(-168.000),
                "joint3": math.radians(-57.000),
                "joint4": math.radians(-41.143),
                "joint5": math.radians(-20.954),
                "joint6": math.radians(-3.000),
                "gripper_joint1": 0.0,
                "gripper_joint2": 0.0,
            },
            "DEPLOYED_NOMINAL": {j: 0.0 for j in ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "gripper_joint1", "gripper_joint2"]},
        }

        for config_name, q_values in configs.items():
            mark("CONFIG_CHECK_START", config=config_name)
            frames = forward_kinematics(joints, q_values)

            # Compute transformed B601 bboxes
            min_distances = []
            for b601_obj in b601_objs:
                link = get_link_from_name(b601_obj.Name)
                if link in frames and link in B50_TRANSFORMS:
                    fk_frame = frames[link]
                    b50 = B50_TRANSFORMS[link]
                    R_total = matmul(fk_frame["R"], b50["R"])
                    t_total = [fk_frame["t"][i] + matvec(fk_frame["R"], b50["t"])[i] for i in range(3)]
                    bb_orig = bbox_to_dict(b601_obj.Shape.BoundBox)
                    bb_trans = transform_bbox(b601_obj.Shape.BoundBox, R_total, t_total)
                else:
                    bb_trans = bbox_to_dict(b601_obj.Shape.BoundBox)

                # Check against spacecraft
                for sc in spacecraft_bboxes:
                    dist = bbox_distance_dict(bb_trans, sc["bbox"])
                    if dist < 100.0:  # Only record close pairs
                        min_distances.append({
                            "b601_object": b601_obj.Name,
                            "b601_link": link,
                            "spacecraft_object": sc["name"],
                            "bbox_distance_mm": dist,
                        })

            min_distances.sort(key=lambda x: x["bbox_distance_mm"])
            min_overall = min_distances[0]["bbox_distance_mm"] if min_distances else float("inf")

            result["configurations"][config_name] = {
                "min_bbox_distance_overall_mm": min_overall,
                "top_10_closest": min_distances[:10],
                "total_pairs_checked": len(min_distances),
                "pass": min_overall > 0.0,
            }
            mark("CONFIG_CHECK_COMPLETE", config=config_name, min_distance=min_overall, pairs=len(min_distances))

        # === 3. Continuous clearance curve (simplified) ===
        mark("CONTINUOUS_CLEARANCE_START")
        n_samples = 5
        clearance_curve = []
        for i in range(n_samples + 1):
            alpha = i / n_samples
            q_sample = {}
            for j in configs["STOWED"]:
                if j in configs["DEPLOYED_NOMINAL"]:
                    q_sample[j] = configs["STOWED"][j] * (1 - alpha) + configs["DEPLOYED_NOMINAL"][j] * alpha
                else:
                    q_sample[j] = configs["STOWED"][j]
            sample_frames = forward_kinematics(joints, q_sample)

            sample_distances = []
            for b601_obj in b601_objs:
                link = get_link_from_name(b601_obj.Name)
                if link in sample_frames and link in B50_TRANSFORMS:
                    fk_frame = sample_frames[link]
                    b50 = B50_TRANSFORMS[link]
                    R_total = matmul(fk_frame["R"], b50["R"])
                    t_total = [fk_frame["t"][i] + matvec(fk_frame["R"], b50["t"])[i] for i in range(3)]
                    bb_trans = transform_bbox(b601_obj.Shape.BoundBox, R_total, t_total)
                else:
                    bb_trans = bbox_to_dict(b601_obj.Shape.BoundBox)

                for sc in spacecraft_bboxes:
                    dist = bbox_distance_dict(bb_trans, sc["bbox"])
                    if dist < 100.0:
                        sample_distances.append(dist)

            min_sample = min(sample_distances) if sample_distances else float("inf")
            clearance_curve.append({"alpha": alpha, "min_bbox_distance_mm": min_sample})
            mark("CLEARANCE_SAMPLE", alpha=alpha, min_distance=min_sample)

        result["clearance_checks"]["continuous_curve"] = clearance_curve
        result["clearance_checks"]["min_over_curve_mm"] = min(c["min_bbox_distance_mm"] for c in clearance_curve)
        result["clearance_checks"]["max_over_curve_mm"] = max(c["min_bbox_distance_mm"] for c in clearance_curve)
        mark("CONTINUOUS_CLEARANCE_COMPLETE", min_over_curve=result["clearance_checks"]["min_over_curve_mm"])

        App.closeDocument(doc.Name)

        result["status"] = "PASS"
        result["elapsed_s"] = round(time.time() - t0, 3)
        mark("SCRIPT_PASS", elapsed_s=result["elapsed_s"])

    except Exception as exc:
        mark("SCRIPT_EXCEPTION", error=str(exc), traceback=traceback.format_exc())
        result["status"] = "FAIL"
        result["exceptions"].append({"error": str(exc), "trace": traceback.format_exc()})

    os.makedirs(OUT_DIR, exist_ok=True)
    out_json = os.path.join(OUT_DIR, "F3_P3_TOP_ASSEMBLY_RESULT.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    mark("RESULT_WRITTEN", path=out_json)


main()
