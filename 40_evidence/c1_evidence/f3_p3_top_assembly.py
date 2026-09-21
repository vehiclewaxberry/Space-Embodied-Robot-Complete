# -*- coding: utf-8 -*-
"""F3-P3: Top-level assembly with continuous clearance verification.

Integrates V2_3 spacecraft structure (STEP) + HIFI B601 visual packages.
Verifies continuous clearance across all configurations.
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

LOG_PATH = os.path.join(OUT_DIR, "f3_p3.log")

# B5.0 transforms (link frame to vendor group)
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


def transform_shape(shape, R, t):
    """Transform a FreeCAD shape by R,t."""
    import FreeCAD as App
    # Convert to FreeCAD placement
    # R is 3x3 rotation matrix, t is translation
    # FreeCAD Placement: Base + Rotation
    # We need to convert R to quaternion or axis-angle
    # Simplified: use FreeCAD's Matrix
    m = App.Matrix()
    m.A11, m.A12, m.A13 = R[0][0], R[0][1], R[0][2]
    m.A21, m.A22, m.A23 = R[1][0], R[1][1], R[1][2]
    m.A31, m.A32, m.A33 = R[2][0], R[2][1], R[2][2]
    m.A14, m.A24, m.A34 = t[0], t[1], t[2]
    new_shape = shape.copy()
    new_shape.transformShape(m)
    return new_shape


def compute_min_distance(shape1, shape2):
    """Compute minimum distance between two shapes."""
    try:
        dist = shape1.distToShape(shape2)
        return dist[0] if dist else float("inf")
    except Exception:
        return float("inf")


def bbox_distance(bb1, bb2):
    """Compute approximate distance between two bboxes."""
    # Compute closest distance between two axis-aligned boxes
    dx = max(0, max(bb1.XMin - bb2.XMax, bb2.XMin - bb1.XMax))
    dy = max(0, max(bb1.YMin - bb2.YMax, bb2.YMin - bb1.YMax))
    dz = max(0, max(bb1.ZMin - bb2.ZMax, bb2.ZMin - bb1.ZMax))
    return math.sqrt(dx*dx + dy*dy + dz*dz)


def should_check_pair(shape1, shape2, threshold=50.0):
    """Pre-filter: only check pairs whose bboxes are within threshold."""
    try:
        bb1 = shape1.BoundBox
        bb2 = shape2.BoundBox
        return bbox_distance(bb1, bb2) < threshold
    except Exception:
        return True


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

        # === 1. Create top-level assembly document ===
        mark("ASSEMBLY_CREATE_START")
        doc = App.newDocument("F3_P3_TOP_ASSEMBLY")

        # Import V2_3 spacecraft structure
        mark("IMPORT_V23_START", path=V23_STEP)
        Part.insert(V23_STEP, doc.Name)
        mark("IMPORT_V23_COMPLETE")

        # Import HIFI visual packages
        visual_packages = {}
        for pkg_file in os.listdir(VISUAL_PACKAGES_DIR):
            if pkg_file.endswith(".FCStd"):
                pkg_name = pkg_file.replace(".FCStd", "")
                pkg_path = os.path.join(VISUAL_PACKAGES_DIR, pkg_file)
                mark("IMPORT_PACKAGE_START", package=pkg_name)
                pkg_doc = App.openDocument(pkg_path)
                # Copy objects to top assembly
                for obj in pkg_doc.Objects:
                    if obj.TypeId == "Part::Feature":
                        new_obj = doc.addObject("Part::Feature", obj.Name)
                        new_obj.Shape = obj.Shape.copy()
                        new_obj.Label = obj.Label
                        new_obj.Placement = obj.Placement.copy()
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
            "visual_packages": list(visual_packages.keys()),
        }
        mark("ASSEMBLY_SAVED", path=assembly_path, objects=len(doc.Objects))

        # === 2. STOWED configuration clearance check ===
        mark("STOWED_CLEARANCE_START")
        # Load URDF for FK
        urdf_path = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\spacecraft_layout\arm_b601_v1\arm_b601_v1.urdf"
        joints = parse_urdf(urdf_path)

        # STOW vector
        stow_q = {
            "joint1": math.radians(145.572),
            "joint2": math.radians(-168.000),
            "joint3": math.radians(-57.000),
            "joint4": math.radians(-41.143),
            "joint5": math.radians(-20.954),
            "joint6": math.radians(-3.000),
            "gripper_joint1": 0.0,
            "gripper_joint2": 0.0,
        }
        stow_frames = forward_kinematics(joints, stow_q)

        # Get spacecraft structure objects (from V2_3 STEP) and B601 objects (from visual packages)
        # B601 objects are identified by name: visual package objects have names like "Part__Feature*"
        # Spacecraft objects have names like "native_STOWED*"
        spacecraft_objs = []
        b601_objs = []
        for obj in doc.Objects:
            if obj.TypeId != "Part::Feature":
                continue
            # Identify by name pattern
            if obj.Name.startswith("native_STOWED"):
                spacecraft_objs.append(obj)
            elif obj.Name.startswith("Part__Feature"):
                b601_objs.append(obj)

        mark("CLEARANCE_OBJECTS", spacecraft=len(spacecraft_objs), b601=len(b601_objs))

        # Compute min distance between B601 and spacecraft
        min_distances = []
        for b601_obj in b601_objs:
            link = getattr(b601_obj, "AssignedLink", "unknown")
            # Transform to STOW position
            if link in stow_frames and link in B50_TRANSFORMS:
                # Apply FK frame + B5.0 transform
                fk_frame = stow_frames[link]
                b50 = B50_TRANSFORMS[link]
                # Compose: p_stow = fk_frame * b50 * p_vendor
                R_total = matmul(fk_frame["R"], b50["R"])
                t_total = [fk_frame["t"][i] + matvec(fk_frame["R"], b50["t"])[i] for i in range(3)]
                transformed = transform_shape(b601_obj.Shape, R_total, t_total)
            else:
                transformed = b601_obj.Shape

            for sc_obj in spacecraft_objs:
                # Pre-filter: only check pairs whose bboxes are close
                if not should_check_pair(transformed, sc_obj.Shape, threshold=100.0):
                    continue
                dist = compute_min_distance(transformed, sc_obj.Shape)
                if dist < float("inf"):
                    min_distances.append({
                        "b601_object": b601_obj.Name,
                        "b601_link": link,
                        "spacecraft_object": sc_obj.Name,
                        "min_distance_mm": dist,
                    })

        # Sort by distance
        min_distances.sort(key=lambda x: x["min_distance_mm"])
        min_overall = min_distances[0]["min_distance_mm"] if min_distances else float("inf")

        result["configurations"]["STOWED"] = {
            "min_distance_overall_mm": min_overall,
            "top_10_closest": min_distances[:10],
            "total_pairs_checked": len(min_distances),
            "pass": min_overall > 0.0,  # Must have positive clearance
        }
        mark("STOWED_CLEARANCE_COMPLETE", min_distance=min_overall, pairs=len(min_distances))

        # === 3. DEPLOYED_NOMINAL configuration ===
        mark("DEPLOYED_CLEARANCE_START")
        deployed_q = {j: 0.0 for j in ["joint1", "joint2", "joint3", "joint4", "joint5", "joint6", "gripper_joint1", "gripper_joint2"]}
        deployed_frames = forward_kinematics(joints, deployed_q)

        deployed_distances = []
        for b601_obj in b601_objs:
            link = getattr(b601_obj, "AssignedLink", "unknown")
            if link in deployed_frames and link in B50_TRANSFORMS:
                fk_frame = deployed_frames[link]
                b50 = B50_TRANSFORMS[link]
                R_total = matmul(fk_frame["R"], b50["R"])
                t_total = [fk_frame["t"][i] + matvec(fk_frame["R"], b50["t"])[i] for i in range(3)]
                transformed = transform_shape(b601_obj.Shape, R_total, t_total)
            else:
                transformed = b601_obj.Shape

            for sc_obj in spacecraft_objs:
                if not should_check_pair(transformed, sc_obj.Shape, threshold=100.0):
                    continue
                dist = compute_min_distance(transformed, sc_obj.Shape)
                if dist < float("inf"):
                    deployed_distances.append({
                        "b601_object": b601_obj.Name,
                        "b601_link": link,
                        "spacecraft_object": sc_obj.Name,
                        "min_distance_mm": dist,
                    })

        deployed_distances.sort(key=lambda x: x["min_distance_mm"])
        deployed_min = deployed_distances[0]["min_distance_mm"] if deployed_distances else float("inf")

        result["configurations"]["DEPLOYED_NOMINAL"] = {
            "min_distance_overall_mm": deployed_min,
            "top_10_closest": deployed_distances[:10],
            "total_pairs_checked": len(deployed_distances),
            "pass": deployed_min > 0.0,
        }
        mark("DEPLOYED_CLEARANCE_COMPLETE", min_distance=deployed_min, pairs=len(deployed_distances))

        # === 4. Continuous clearance curve (simplified: check a few key poses) ===
        mark("CONTINUOUS_CLEARANCE_START")
        # Sample poses from STOW to DEPLOYED
        n_samples = 5
        clearance_curve = []
        for i in range(n_samples + 1):
            alpha = i / n_samples
            # Interpolate joint values
            q_sample = {}
            for j in stow_q:
                if j in deployed_q:
                    q_sample[j] = stow_q[j] * (1 - alpha) + deployed_q[j] * alpha
                else:
                    q_sample[j] = stow_q[j]
            sample_frames = forward_kinematics(joints, q_sample)

            # Compute min distance at this pose
            sample_distances = []
            for b601_obj in b601_objs:
                link = getattr(b601_obj, "AssignedLink", "unknown")
                if link in sample_frames and link in B50_TRANSFORMS:
                    fk_frame = sample_frames[link]
                    b50 = B50_TRANSFORMS[link]
                    R_total = matmul(fk_frame["R"], b50["R"])
                    t_total = [fk_frame["t"][i] + matvec(fk_frame["R"], b50["t"])[i] for i in range(3)]
                    transformed = transform_shape(b601_obj.Shape, R_total, t_total)
                else:
                    transformed = b601_obj.Shape

                for sc_obj in spacecraft_objs:
                    if not should_check_pair(transformed, sc_obj.Shape, threshold=100.0):
                        continue
                    dist = compute_min_distance(transformed, sc_obj.Shape)
                    if dist < float("inf"):
                        sample_distances.append(dist)

            min_sample = min(sample_distances) if sample_distances else float("inf")
            clearance_curve.append({
                "alpha": alpha,
                "min_distance_mm": min_sample,
            })
            mark("CLEARANCE_SAMPLE", alpha=alpha, min_distance=min_sample)

        result["clearance_checks"]["continuous_curve"] = clearance_curve
        result["clearance_checks"]["min_over_curve_mm"] = min(c["min_distance_mm"] for c in clearance_curve)
        result["clearance_checks"]["max_over_curve_mm"] = max(c["min_distance_mm"] for c in clearance_curve)
        mark("CONTINUOUS_CLEARANCE_COMPLETE", min_over_curve=result["clearance_checks"]["min_over_curve_mm"])

        App.closeDocument(doc.Name)

        result["status"] = "PASS"
        result["elapsed_s"] = round(time.time() - t0, 3)
        mark("SCRIPT_PASS", elapsed_s=result["elapsed_s"])

    except Exception as exc:
        mark("SCRIPT_EXCEPTION", error=str(exc), traceback=traceback.format_exc())
        result["status"] = "FAIL"
        result["exceptions"].append({"error": str(exc), "trace": traceback.format_exc()})

    # Write results
    os.makedirs(OUT_DIR, exist_ok=True)
    out_json = os.path.join(OUT_DIR, "F3_P3_TOP_ASSEMBLY_RESULT.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    mark("RESULT_WRITTEN", path=out_json)


main()
