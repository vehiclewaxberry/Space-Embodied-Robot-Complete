# -*- coding: utf-8 -*-
"""Accepted-URDF parser + FK. READ-ONLY on the URDF (hash-guarded by f3r1_env).

All outputs in millimetres / world = URDF base_link frame. The URDF is the L0
truth for topology, axes, ordering, zero pose, mass and inertia (ECR §2).
"""
import math
import xml.etree.ElementTree as ET

import numpy as np

from f3r1_env import PROTECTED

URDF_PATH = PROTECTED["accepted_b601_urdf"]["path"]


def _rpy_to_R(r, p, y):
    cr, sr = math.cos(r), math.sin(r)
    cp, sp = math.cos(p), math.sin(p)
    cy, sy = math.cos(y), math.sin(y)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


def _T(R, t):
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = t
    return T


def load_chain():
    tree = ET.parse(str(URDF_PATH))
    root = tree.getroot()
    links = [l.attrib["name"] for l in root.findall("link")]
    joints = []
    for j in root.findall("joint"):
        o = j.find("origin")
        xyz = [float(v) * 1000.0 for v in (o.attrib.get("xyz", "0 0 0").split()
                                           if o is not None else "0 0 0".split())]
        rpy = [float(v) for v in (o.attrib.get("rpy", "0 0 0").split()
                                  if o is not None else "0 0 0".split())]
        ax = j.find("axis")
        axis = ([float(v) for v in ax.attrib.get("xyz", "0 0 1").split()]
                if ax is not None else [0, 0, 1])
        lim = j.find("limit")
        joints.append({
            "name": j.attrib["name"], "type": j.attrib["type"],
            "parent": j.find("parent").attrib["link"],
            "child": j.find("child").attrib["link"],
            "xyz_mm": xyz, "rpy": rpy, "axis": axis,
            "lower": float(lim.attrib["lower"]) if lim is not None and "lower" in lim.attrib else None,
            "upper": float(lim.attrib["upper"]) if lim is not None and "upper" in lim.attrib else None,
        })
    return links, joints


def fk(joints, q):
    """World (base_link) 4x4 per link, mm. q: dict joint_name -> value
    (rad for revolute, mm for prismatic). Missing entries = 0."""
    T = {"base_link": np.eye(4)}
    remaining = list(joints)
    guard = 0
    while remaining and guard < 100:
        guard += 1
        rest = []
        for j in remaining:
            if j["parent"] not in T:
                rest.append(j)
                continue
            Tj = _T(_rpy_to_R(*j["rpy"]), np.array(j["xyz_mm"]))
            v = q.get(j["name"], 0.0)
            a = np.array(j["axis"], dtype=float)
            a = a / (np.linalg.norm(a) or 1.0)
            if j["type"] in ("revolute", "continuous") and v != 0.0:
                c, s = math.cos(v), math.sin(v)
                x, y, z = a
                Rj = np.array([
                    [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                    [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                    [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]])
                Tm = _T(Rj, np.zeros(3))
            elif j["type"] == "prismatic" and v != 0.0:
                Tm = _T(np.eye(3), a * v)
            else:
                Tm = np.eye(4)
            T[j["child"]] = T[j["parent"]] @ Tj @ Tm
        remaining = rest
    if remaining:
        raise RuntimeError("unresolved kinematic chain: %s" % [j["name"] for j in remaining])
    return T


def joint_world_frames(joints, q):
    """World origin+axis of each joint at pose q (before its own motion)."""
    Tlinks = fk(joints, q)
    out = {}
    for j in joints:
        Tp = Tlinks[j["parent"]]
        Tj = Tp @ _T(_rpy_to_R(*j["rpy"]), np.array(j["xyz_mm"]))
        a = np.array(j["axis"], dtype=float)
        a = a / (np.linalg.norm(a) or 1.0)
        out[j["name"]] = {"origin_mm": Tj[:3, 3].tolist(),
                          "axis_world": (Tj[:3, :3] @ a).tolist(),
                          "type": j["type"]}
    return out
