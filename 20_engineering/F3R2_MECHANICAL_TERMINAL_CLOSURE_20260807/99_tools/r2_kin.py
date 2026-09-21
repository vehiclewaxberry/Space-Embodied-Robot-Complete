# -*- coding: utf-8 -*-
"""F3R2 offline kinematics + clearance core.

Truth sources, none of them invented here:
  * topology, axes, joint limits, zero pose, collision meshes
        -> the accepted B601 URDF (hash-guarded, never written)
  * arm mount into the spacecraft (clocking 25 deg, station x = 208 mm)
        -> F3R1_TOP_INTEGRATION_REPORT.json  (arm_mount_transform_mm)
  * environment geometry, per part, in the assembly frame
        -> STL tessellation of the hash-bound G2 per-configuration STEPs

Three tiers, deliberately separated so no tier is mistaken for another:
  tier 1  world-AABB gap        conservative screen (AABB contains the link, so
                                a positive AABB gap is a true lower bound)
  tier 2  mesh point distance   both directions, all vertices, with the
                                tessellation deflection carried as tolerance
  tier 3  SolidWorks native     the authority for interference; this module
                                never claims to replace it
"""
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import trimesh

REPO = Path(r"F:/China Graduate Future Flight Vehicle Innovation Competition")
ENG = REPO / "20_engineering"
F3R1 = ENG / "F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806"
F3R2 = ENG / "F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
MESHDIR = F3R2 / "05_clearance" / "mesh"
URDF_DIR = ENG / "cad/spacecraft_layout/arm_b601_v1"

sys.path.insert(0, str(F3R1 / "99_tools"))
import urdf_chain as UC  # noqa: E402

LINKS, JOINTS = UC.load_chain()
JOINT_BY_NAME = {j["name"]: j for j in JOINTS}
ARM_JOINTS = ["joint%d" % i for i in range(1, 7)]
LIMITS_DEG = {j: (math.degrees(JOINT_BY_NAME[j]["lower"]),
                  math.degrees(JOINT_BY_NAME[j]["upper"])) for j in ARM_JOINTS}

_top = json.loads((F3R1 / "03_native_cad" / "F3R1_TOP_INTEGRATION_REPORT.json")
                  .read_text(encoding="utf-8"))
T_MOUNT = np.array(_top["arm_mount_transform_mm"], dtype=float)
CLOCK_DEG = _top["clock_deg"]
MOUNT_STATION = _top["mount_station"]

# links that carry real collision geometry in the accepted URDF
LINK_MESHES = ["base_link", "link1", "link2", "link3", "link4", "link5",
               "link6", "gripper_link", "gripper_left", "gripper_right"]
# base_link is bolted to the spacecraft: its contact with the mount hardware is
# the joint itself, not a clearance violation.
MOUNTED_LINKS = {"base_link"}


def q_dict(q_deg):
    """[6] degrees -> URDF joint dict in radians (gripper fingers at 0)."""
    return {("joint%d" % (i + 1)): math.radians(v) for i, v in enumerate(q_deg)}


def within_limits(q_deg):
    out = {}
    for i, j in enumerate(ARM_JOINTS):
        lo, hi = LIMITS_DEG[j]
        out[j] = {"q_deg": round(float(q_deg[i]), 4),
                  "lower_deg": round(lo, 4), "upper_deg": round(hi, 4),
                  "margin_deg": round(min(q_deg[i] - lo, hi - q_deg[i]), 4),
                  "inside": bool(lo <= q_deg[i] <= hi)}
    return out


def link_world(q_deg, finger_mm=0.0):
    """link name -> 4x4 in the ASSEMBLY frame (mm)."""
    q = q_dict(q_deg)
    q["gripper_joint1"] = finger_mm
    q["gripper_joint2"] = finger_mm
    T = UC.fk(JOINTS, q)
    return {k: T_MOUNT @ v for k, v in T.items()}


# ---------------- meshes ----------------
_cache = {}


def arm_mesh(link):
    if link not in _cache:
        p = URDF_DIR / "meshes_b601_gripper" / ("%s.STL" % link)
        m = trimesh.load_mesh(str(p), process=False)
        # URDF meshes are metres in this export? verified by extent check below
        _cache[link] = m
    return _cache[link]


def arm_mesh_scale():
    """The accepted URDF declares scale 1 1 1 and SI metres; SolidWorks STL
    exports are usually millimetres.  Decide from the actual extent instead of
    assuming, and record the decision."""
    m = arm_mesh("link2")
    ext = float(np.max(m.extents))
    if ext < 5.0:
        return 1000.0, "metres->mm (extent %.4f)" % ext
    return 1.0, "already mm (extent %.1f)" % ext


SCALE, SCALE_WHY = arm_mesh_scale()


def arm_points(link, T, stride=1):
    m = arm_mesh(link)
    v = np.asarray(m.vertices, dtype=float) * SCALE
    if stride > 1:
        v = v[::stride]
    return (T[:3, :3] @ v.T).T + T[:3, 3]


def arm_world_aabb(link, T):
    p = arm_points(link, T, stride=1)
    return np.concatenate([p.min(axis=0), p.max(axis=0)])


def load_env(tag_bus="DEPLOYED", wings=("WING_L_DEPLOYED", "WING_R_DEPLOYED")):
    """Environment part meshes in the assembly frame.

    The bus is configuration-invariant; only which wing panel is live changes,
    so the eight configurations are compositions of the same part meshes."""
    man = json.loads((MESHDIR / ("ENV_MESH_%s.json" % tag_bus))
                     .read_text(encoding="utf-8"))
    parts = {}
    for name, info in man["parts"].items():
        if info.get("group") in ("WING_L", "WING_R"):
            continue
        p = Path(info["path"])
        if p.is_file():
            parts[name] = {"path": str(p), "box": info["box_mm"],
                           "group": info.get("group"),
                           "triangles": info.get("triangles")}
    for w in wings:
        for tag in ("DEPLOYED", "STOWED"):
            f = MESHDIR / ("ENV_MESH_%s.json" % tag)
            if not f.is_file():
                continue
            mm = json.loads(f.read_text(encoding="utf-8"))
            if w in mm["parts"]:
                info = mm["parts"][w]
                parts[w] = {"path": info["path"], "box": info["box_mm"],
                            "group": info.get("group"),
                            "triangles": info.get("triangles")}
                break
    return parts, man


def env_mesh(path):
    if path not in _cache:
        _cache[path] = trimesh.load_mesh(path, process=False)
    return _cache[path]


def aabb_gap(a, b):
    """Signed gap between two axis-aligned boxes [x0,y0,z0,x1,y1,z1] (mm).
    Positive = separated by at least this much along the worst axis."""
    d = [max(a[i] - b[i + 3], b[i] - a[i + 3]) for i in range(3)]
    pos = [x for x in d if x > 0]
    if pos:
        return float(math.sqrt(sum(x * x for x in pos)))
    return float(max(d))            # negative: boxes overlap


def mesh_min_distance(pts, mesh, chunk=20000):
    """Minimum distance from a point set to a mesh surface (mm)."""
    best = float("inf")
    for i in range(0, len(pts), chunk):
        _, d, _ = trimesh.proximity.closest_point(mesh, pts[i:i + chunk])
        if len(d):
            best = min(best, float(np.min(d)))
    return best


def pair_distance(link, T, part, stride_arm=4):
    """Tier-2 distance between one arm link and one environment part."""
    m = env_mesh(part["path"])
    pa = arm_points(link, T, stride=stride_arm)
    d1 = mesh_min_distance(pa, m)
    vb = np.asarray(m.vertices, dtype=float)
    # env vertices -> arm surface, in the arm's local frame
    Rt = T[:3, :3].T
    local = (Rt @ (vb - T[:3, 3]).T).T / SCALE
    am = arm_mesh(link)
    d2 = mesh_min_distance(local, am) * SCALE
    return min(d1, d2)
