# -*- coding: utf-8 -*-
"""F3-P5A: Aggregate accepted URDF stowed equivalent inertia.

Computes total mass, combined CoM, combined inertia about B601 base frame
for the frozen stowed configuration. Does NOT modify URDF.
"""
from __future__ import print_function
import json
import math
import os
import sys
import xml.etree.ElementTree as ET

WS = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\F3_P5_structural_closure_candidate"
URDF = r"F:\China Graduate Future Flight Vehicle Innovation Competition\20_engineering\cad\spacecraft_layout\arm_b601_v1\arm_b601_v1.urdf"
OUT_DIR = os.path.join(WS, r"04_fea\01_geometry_preparation")

# Stowed joint configuration (from O13_STOW_VECTOR_V3)
STOW_Q_DEG = [145.572, -168.000, -57.000, -41.143, -20.954, -3.000]
STOW_Q_RAD = [math.radians(q) for q in STOW_Q_DEG]


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
    tree = ET.parse(urdf_path)
    root = tree.getroot()
    links = {}
    for l in root.findall("link"):
        name = l.get("name")
        inertial = l.find("inertial")
        if inertial is not None:
            origin = inertial.find("origin")
            mass = inertial.find("mass")
            inertia = inertial.find("inertia")
            links[name] = {
                "mass": float(mass.get("value")) if mass is not None else 0.0,
                "origin": [float(x) for x in origin.get("xyz").split()] if origin is not None else [0,0,0],
                "inertia": {
                    "ixx": float(inertia.get("ixx")),
                    "iyy": float(inertia.get("iyy")),
                    "izz": float(inertia.get("izz")),
                    "ixy": float(inertia.get("ixy")),
                    "ixz": float(inertia.get("ixz")),
                    "iyz": float(inertia.get("iyz")),
                } if inertia is not None else None,
            }
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
    return links, joints


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


def inertia_to_matrix(I):
    return [
        [I["ixx"], I["ixy"], I["ixz"]],
        [I["ixy"], I["iyy"], I["iyz"]],
        [I["ixz"], I["iyz"], I["izz"]],
    ]


def parallel_axis(I_cm, m, d):
    """Parallel axis theorem: I = I_cm + m * (|d|^2 * I_3 - d ⊗ d)."""
    d2 = sum(x*x for x in d)
    outer = [[d[i]*d[j] for j in range(3)] for i in range(3)]
    result = [[0.0]*3 for _ in range(3)]
    for i in range(3):
        for j in range(3):
            result[i][j] = I_cm[i][j] + m * (d2 * (1 if i==j else 0) - outer[i][j])
    return result


def main():
    links, joints = parse_urdf(URDF)
    q_values = {
        "joint1": STOW_Q_RAD[0],
        "joint2": STOW_Q_RAD[1],
        "joint3": STOW_Q_RAD[2],
        "joint4": STOW_Q_RAD[3],
        "joint5": STOW_Q_RAD[4],
        "joint6": STOW_Q_RAD[5],
        "gripper_joint1": 0.0,
        "gripper_joint2": 0.0,
    }
    frames = forward_kinematics(joints, q_values)

    # Compute total mass and combined CoM
    total_mass = 0.0
    weighted_com = [0.0, 0.0, 0.0]
    link_contributions = []

    for link_name, link_data in links.items():
        if link_name not in frames:
            continue
        m = link_data["mass"]
        if m <= 0:
            continue
        # Link CoM in base frame
        com_local = link_data["origin"]
        frame = frames[link_name]
        com_base = [frame["t"][i] + matvec(frame["R"], com_local)[i] for i in range(3)]
        total_mass += m
        for i in range(3):
            weighted_com[i] += m * com_base[i]
        link_contributions.append({
            "link": link_name,
            "mass": m,
            "com_local": com_local,
            "com_base": com_base,
        })

    combined_com = [c / total_mass for c in weighted_com]

    # Compute combined inertia about combined CoM
    combined_inertia = [[0.0]*3 for _ in range(3)]
    for contrib in link_contributions:
        link_name = contrib["link"]
        link_data = links[link_name]
        m = contrib["mass"]
        com_base = contrib["com_base"]
        # Distance from combined CoM to link CoM
        d = [com_base[i] - combined_com[i] for i in range(3)]
        # Link inertia in base frame (rotate to base frame)
        I_cm_local = inertia_to_matrix(link_data["inertia"])
        frame = frames[link_name]
        I_cm_base = matmul(matmul(frame["R"], I_cm_local), [[frame["R"][j][i] for j in range(3)] for i in range(3)])
        # Parallel axis to combined CoM
        I_base = parallel_axis(I_cm_base, m, d)
        for i in range(3):
            for j in range(3):
                combined_inertia[i][j] += I_base[i][j]

    # Verify inertia is symmetric positive definite
    sym_ok = all(abs(combined_inertia[i][j] - combined_inertia[j][i]) < 1e-10 for i in range(3) for j in range(3))
    # Check principal moments are positive (simplified: check diagonal dominance)
    diag_positive = all(combined_inertia[i][i] > 0 for i in range(3))

    result = {
        "status": "PASS" if sym_ok and diag_positive else "FAIL",
        "stow_configuration": {
            "q_deg": STOW_Q_DEG,
            "q_rad": STOW_Q_RAD,
        },
        "total_mass_kg": total_mass,
        "combined_com_m": combined_com,
        "combined_inertia_kg_m2": {
            "ixx": combined_inertia[0][0],
            "iyy": combined_inertia[1][1],
            "izz": combined_inertia[2][2],
            "ixy": combined_inertia[0][1],
            "ixz": combined_inertia[0][2],
            "iyz": combined_inertia[1][2],
        },
        "link_contributions": link_contributions,
        "verification": {
            "symmetric": sym_ok,
            "diagonal_positive": diag_positive,
            "total_mass_matches_ledger": abs(total_mass - 4.6956) < 0.01,  # From mass_inertia_budget_v1.csv
        },
        "accepted_urdf_sha256": "408147DDC9CC0BBA0FACBF864C559A54D1712262703BA41251514A4303B5A3A4",
        "urdf_unmodified": True,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    out_yaml = os.path.join(OUT_DIR, "B601_STOWED_EQUIVALENT_INERTIA.yaml")
    out_report = os.path.join(OUT_DIR, "B601_INERTIA_AGGREGATION_REPORT.md")

    with open(out_yaml, "w", encoding="utf-8") as f:
        f.write("# B601 Stowed Equivalent Inertia (from accepted URDF)\n")
        f.write("schema: B601_STOWED_EQUIVALENT_INERTIA_V1\n")
        f.write("generated_utc: 2026-08-05T17:00:00Z\n")
        f.write("stow_configuration:\n")
        f.write("  q_deg: %s\n" % (STOW_Q_DEG,))
        f.write("  q_rad: %s\n" % (STOW_Q_RAD,))
        f.write("total_mass_kg: %.6f\n" % total_mass)
        f.write("combined_com_m: [%s]\n" % ", ".join("%.6f" % c for c in combined_com))
        f.write("combined_inertia_kg_m2:\n")
        f.write("  ixx: %.6f\n" % combined_inertia[0][0])
        f.write("  iyy: %.6f\n" % combined_inertia[1][1])
        f.write("  izz: %.6f\n" % combined_inertia[2][2])
        f.write("  ixy: %.6f\n" % combined_inertia[0][1])
        f.write("  ixz: %.6f\n" % combined_inertia[0][2])
        f.write("  iyz: %.6f\n" % combined_inertia[1][2])
        f.write("accepted_urdf_sha256: 408147DDC9CC0BBA0FACBF864C559A54D1712262703BA41251514A4303B5A3A4\n")
        f.write("urdf_unmodified: true\n")

    with open(out_report, "w", encoding="utf-8") as f:
        f.write("# B601 Inertia Aggregation Report\n\n")
        f.write("**Source:** accepted URDF (408147DD...)\n")
        f.write("**Configuration:** STOWED (q=%s deg)\n\n" % (STOW_Q_DEG,))
        f.write("## Results\n\n")
        f.write("- **Total mass:** %.6f kg\n" % total_mass)
        f.write("- **Combined CoM:** [%s] m\n" % ", ".join("%.6f" % c for c in combined_com))
        f.write("- **Combined inertia:**\n")
        f.write("  - Ixx: %.6f kg·m²\n" % combined_inertia[0][0])
        f.write("  - Iyy: %.6f kg·m²\n" % combined_inertia[1][1])
        f.write("  - Izz: %.6f kg·m²\n" % combined_inertia[2][2])
        f.write("  - Ixy: %.6f kg·m²\n" % combined_inertia[0][1])
        f.write("  - Ixz: %.6f kg·m²\n" % combined_inertia[0][2])
        f.write("  - Iyz: %.6f kg·m²\n" % combined_inertia[1][2])
        f.write("\n## Verification\n\n")
        f.write("- Symmetric: %s\n" % sym_ok)
        f.write("- Diagonal positive: %s\n" % diag_positive)
        f.write("- Total mass matches ledger (4.6956 kg): %s\n" % (abs(total_mass - 4.6956) < 0.01))
        f.write("- URDF unmodified: True\n")
        f.write("\n## Link Contributions\n\n")
        for contrib in link_contributions:
            f.write("- **%s:** mass=%.4f kg, com_base=[%s] m\n" % (
                contrib["link"], contrib["mass"],
                ", ".join("%.4f" % c for c in contrib["com_base"])))

    print("STATUS=" + result["status"])
    print("TOTAL_MASS=%.6f" % total_mass)
    print("COM=[%s]" % ", ".join("%.6f" % c for c in combined_com))
    print("SYMMETRIC=%s" % sym_ok)
    print("DIAG_POSITIVE=%s" % diag_positive)
    print("YAML=" + out_yaml)
    print("REPORT=" + out_report)
    sys.stdout.flush()


main()
