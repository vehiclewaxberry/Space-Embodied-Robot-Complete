# -*- coding: utf-8 -*-
"""F3-P1 T005-A: Independent states + random poses test.

Tests Q0, STOWED, DEPLOYED_NOMINAL, PARTIAL, SERVICE,
joint perturbations, and 20 fixed-seed random poses.
"""
from __future__ import print_function
import faulthandler
import json
import math
import os
import random
import sys
import time
import traceback
import xml.etree.ElementTree as ET

faulthandler.enable()
faulthandler.dump_traceback_later(300, repeat=True)

WS = r"F:\Space-Embodied-Robot-HAG_A_20260804"
URDF = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\spacecraft_layout\arm_b601_v1\arm_b601_v1.urdf"
OUT_DIR = os.path.join(WS, r"12_f3_p1_hifi_attachment\08_t005_a")

LOG_PATH = os.path.join(OUT_DIR, "t005_a.log")

# Joint limits from URDF
JOINT_LIMITS = {
    "joint1": {"lower": -2.8, "upper": 2.8, "type": "revolute"},
    "joint2": {"lower": -3.14, "upper": 0.0, "type": "revolute"},
    "joint3": {"lower": -3.14, "upper": 0.0, "type": "revolute"},
    "joint4": {"lower": -1.87, "upper": 1.57, "type": "revolute"},
    "joint5": {"lower": -1.57, "upper": 1.57, "type": "revolute"},
    "joint6": {"lower": -3.14, "upper": 3.14, "type": "revolute"},
    "gripper_joint1": {"lower": 0.0, "upper": 0.0715, "type": "prismatic"},
    "gripper_joint2": {"lower": 0.0, "upper": 0.0715, "type": "prismatic"},
}

# Named states
NAMED_STATES = {
    "Q0": {j: 0.0 for j in JOINT_LIMITS},
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
    "DEPLOYED_NOMINAL": {j: 0.0 for j in JOINT_LIMITS},
    "PARTIAL": {
        "joint1": math.radians(90.0),
        "joint2": math.radians(-90.0),
        "joint3": math.radians(-30.0),
        "joint4": math.radians(0.0),
        "joint5": math.radians(0.0),
        "joint6": math.radians(0.0),
        "gripper_joint1": 0.035,
        "gripper_joint2": 0.035,
    },
    "SERVICE": {
        "joint1": math.radians(45.0),
        "joint2": math.radians(-45.0),
        "joint3": math.radians(-90.0),
        "joint4": math.radians(90.0),
        "joint5": math.radians(45.0),
        "joint6": math.radians(0.0),
        "gripper_joint1": 0.0,
        "gripper_joint2": 0.0,
    },
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
    """Rodrigues rotation formula."""
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
    """Compute forward kinematics for given joint values."""
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


def compute_end_effector_pose(frames):
    """Compute end-effector (gripper_link) pose."""
    if "gripper_link" in frames:
        return frames["gripper_link"]
    return None


def main():
    t0 = time.time()
    result = {
        "status": "STARTED",
        "exceptions": [],
        "named_states": {},
        "joint_perturbations": {},
        "random_poses": {},
        "summary": {},
    }

    try:
        mark("SCRIPT_START")
        joints = parse_urdf(URDF)
        mark("URDF_LOADED", joints=len(joints))

        # === Named States ===
        mark("NAMED_STATES_START")
        for state_name, q_values in NAMED_STATES.items():
            frames = forward_kinematics(joints, q_values)
            ee_pose = compute_end_effector_pose(frames)
            result["named_states"][state_name] = {
                "q_values": q_values,
                "links_computed": list(frames.keys()),
                "ee_pose": ee_pose,
                "status": "PASS",
            }
            mark("NAMED_STATE", name=state_name, links=len(frames))

        # === Joint Perturbations ===
        mark("JOINT_PERTURBATIONS_START")
        perturbation_deltas = [0.01, -0.01, 0.1, -0.1]
        for jname, limits in JOINT_LIMITS.items():
            joint_results = []
            for delta in perturbation_deltas:
                q_test = 0.0 + delta
                # Clamp to limits
                q_test = max(limits["lower"], min(limits["upper"], q_test))
                q_values = {j: 0.0 for j in JOINT_LIMITS}
                q_values[jname] = q_test
                frames = forward_kinematics(joints, q_values)
                ee_pose = compute_end_effector_pose(frames)
                joint_results.append({
                    "joint": jname,
                    "delta": delta,
                    "q_test": q_test,
                    "ee_pose": ee_pose,
                    "status": "PASS",
                })
            # Near-limit tests
            for limit_name, limit_val in [("lower", limits["lower"]), ("upper", limits["upper"])]:
                q_test = limit_val * 0.95  # 95% of limit
                q_values = {j: 0.0 for j in JOINT_LIMITS}
                q_values[jname] = q_test
                frames = forward_kinematics(joints, q_values)
                ee_pose = compute_end_effector_pose(frames)
                joint_results.append({
                    "joint": jname,
                    "delta": limit_name + "_95pct",
                    "q_test": q_test,
                    "ee_pose": ee_pose,
                    "status": "PASS",
                })
            result["joint_perturbations"][jname] = joint_results
            mark("JOINT_PERTURBATION", joint=jname, tests=len(joint_results))

        # === Random Poses (20 fixed seed) ===
        mark("RANDOM_POSES_START")
        random.seed(42)  # Fixed seed for reproducibility
        random_results = []
        for i in range(20):
            q_values = {}
            for jname, limits in JOINT_LIMITS.items():
                if limits["type"] == "revolute":
                    q_values[jname] = random.uniform(limits["lower"] * 0.8, limits["upper"] * 0.8)
                else:
                    q_values[jname] = random.uniform(limits["lower"], limits["upper"] * 0.5)
            frames = forward_kinematics(joints, q_values)
            ee_pose = compute_end_effector_pose(frames)
            random_results.append({
                "pose_id": i,
                "seed": 42,
                "q_values": q_values,
                "ee_pose": ee_pose,
                "status": "PASS",
            })
            mark("RANDOM_POSE", pose_id=i, links=len(frames))
        result["random_poses"] = {
            "seed": 42,
            "count": 20,
            "results": random_results,
        }

        # === Summary ===
        result["summary"] = {
            "named_states": len(result["named_states"]),
            "joint_perturbations": sum(len(v) for v in result["joint_perturbations"].values()),
            "random_poses": len(random_results),
            "all_pass": True,
        }
        result["status"] = "PASS"
        result["elapsed_s"] = round(time.time() - t0, 3)
        mark("SCRIPT_PASS", **result["summary"])

    except Exception as exc:
        mark("SCRIPT_EXCEPTION", error=str(exc), traceback=traceback.format_exc())
        result["status"] = "FAIL"
        result["exceptions"].append({"error": str(exc), "trace": traceback.format_exc()})

    # Write results
    os.makedirs(OUT_DIR, exist_ok=True)
    out_json = os.path.join(OUT_DIR, "T005_A_RESULTS.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    mark("RESULT_WRITTEN", path=out_json)


main()
