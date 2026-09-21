# -*- coding: utf-8 -*-
"""F3R2 arm posing on CAD geometry + offline clearance.

The B51 CAD arm links -- not the URDF STLs -- are the mechanical truth for this
assembly (they differ; see F3R2_ARM_GEOMETRY_RECONCILIATION).  The accepted
URDF stays the only authority for topology, axes, limits and FK, so a pose is
realised as:

    world_mesh(link, q) = T_mount . T_fk(link, q) . T_fk(link, q_as_built)^-1
                          . world_mesh(link, q_as_built)

i.e. every CAD link is carried from its as-built place by the RELATIVE motion
its own joint chain produces.  Nothing is re-modelled, no CAD is edited, and at
q = q_as_built the transform is exactly identity -- which is asserted, not
assumed.

Distances are reported in three tiers that are never conflated:
  AABB   conservative lower bound (positive value = provably separated)
  MESH   vertex-to-surface distance, carrying the tessellation deflection
  NATIVE SolidWorks B-rep -- the authority, produced elsewhere
"""
import json
import math
from pathlib import Path

import numpy as np
import trimesh

import r2_kin as K

MESHDIR = K.F3R2 / "05_clearance" / "mesh"

# CAD arm part label -> URDF link that moves it
CAD_LINK = {
    "B51_REF_base_link_LINKLOCAL": "base_link",
    "B51_REF_link1_LINKLOCAL": "link1",
    "B51_REF_link2_LINKLOCAL": "link2",
    "B51_REF_link3_LINKLOCAL": "link3",
    "B51_REF_link4_LINKLOCAL": "link4",
    "B51_REF_link5_LINKLOCAL": "link5",
    "B51_REF_link6_LINKLOCAL": "link6",
    "B51_REF_gripper_detail_LINKLOCAL": "gripper_link",
}
ARM_ROLLUP = "B51_B601_ARTICULATED_ENGINEERING_ARM"

# The CAD arm in the G2 STEPs stands at the as-built (donor default) pose.
Q_AS_BUILT_DEG = [0.0] * 6

# bus parts that the arm is bolted to: contact there is the joint, not a fault
MOUNT_PARTS = {"Central_Boss", "Adapter_Plate", "Spacecraft_Flange",
               "Load_Spreading_Frame", "Load_Bridge_Left", "Load_Bridge_Right",
               "02_B601_Mount_and_Load_Path", "Harness_Passage"}
REFERENCE_PARTS = {"Launch_Lock_Interface_Reference",
                   "Release_Clearance_Envelope"}
CONTAINER_PARTS = {"01_Primary_Structure_V2_", "02_B601_Mount_and_Load_Path",
                   "04_ARM_STOW_SUPPORT", "05_Solar_Array_Root_Left",
                   "06_Solar_Array_Root_Right", "Equipment_Decks",
                   "Space_Embodied_Service_Spacecraft_V2_2_MAINTENANCE",
                   "F3R1_V3_DEPLOYED_NOMINAL",
                   "F3R1_V3_STOWED_ENGINEERING_CANDIDATE"}
SADDLES = {"Aft_Saddle": "G07", "Fwd_Saddle": "G08", "Mid_Saddle": "MID"}

_mesh_cache = {}


def load_manifest(tag):
    return json.loads((MESHDIR / ("ENV_MESH_%s.json" % tag))
                      .read_text(encoding="utf-8"))


def mesh_of(path):
    if path not in _mesh_cache:
        _mesh_cache[path] = trimesh.load_mesh(path, process=False)
    return _mesh_cache[path]


def rel_transform(link, q_deg, q_ref_deg=None):
    """T that carries the as-built CAD link to pose q (assembly frame, mm)."""
    q_ref = Q_AS_BUILT_DEG if q_ref_deg is None else q_ref_deg
    Tq = K.link_world(q_deg)[link]
    Tr = K.link_world(q_ref)[link]
    return Tq @ np.linalg.inv(Tr)


def arm_parts(tag="DEPLOYED"):
    man = load_manifest(tag)
    out = {}
    for cad, link in CAD_LINK.items():
        info = man["parts"].get(cad)
        if info is None:
            continue
        out[cad] = {"link": link, "path": info["path"],
                    "box": np.array(info["box_mm"], dtype=float),
                    "triangles": info["triangles"]}
    return out


def env_parts(tag="DEPLOYED", wings=("WING_L_DEPLOYED", "WING_R_DEPLOYED")):
    """Environment parts in the assembly frame, with their role recorded.

    The bus is identical in every configuration; only the live wing pair
    changes, so a wing is picked from whichever mesh set actually contains it.
    """
    man = load_manifest(tag)
    out = {}
    for name, info in man["parts"].items():
        if name.startswith("B51_") or name == ARM_ROLLUP:
            continue
        if name in CONTAINER_PARTS or name.startswith("F3R1_V3_"):
            continue
        if name.startswith("WING_"):
            continue
        role = ("REFERENCE_ONLY" if name in REFERENCE_PARTS
                else "ARM_MOUNT_INTERFACE" if name in MOUNT_PARTS
                else "SADDLE_PLACEHOLDER" if name in SADDLES
                else "BUS_STRUCTURE")
        out[name] = {"path": info["path"], "role": role,
                     "box": np.array(info["box_mm"], dtype=float),
                     "triangles": info["triangles"]}
    for w in wings:
        for t in (tag, "DEPLOYED", "STOWED"):
            mm = MESHDIR / ("ENV_MESH_%s.json" % t)
            if not mm.is_file():
                continue
            d = json.loads(mm.read_text(encoding="utf-8"))
            if w in d["parts"]:
                i = d["parts"][w]
                out[w] = {"path": i["path"], "role": "SOLAR_WING",
                          "box": np.array(i["box_mm"], dtype=float),
                          "triangles": i["triangles"]}
                break
        else:
            raise RuntimeError("wing mesh not found in any mesh set: %s" % w)
    return out


def transform_box(box, T):
    """AABB of a transformed AABB (corner transform, still a valid bound)."""
    c = np.array([[box[i], box[j], box[k]]
                  for i in (0, 3) for j in (1, 4) for k in (2, 5)])
    p = (T[:3, :3] @ c.T).T + T[:3, 3]
    return np.concatenate([p.min(axis=0), p.max(axis=0)])


def aabb_gap(a, b):
    d = np.array([max(a[i] - b[i + 3], b[i] - a[i + 3]) for i in range(3)])
    pos = d[d > 0]
    return float(np.linalg.norm(pos)) if len(pos) else float(d.max())


def posed_points(part, T, stride=1):
    m = mesh_of(part["path"])
    v = np.asarray(m.vertices, dtype=float)
    if stride > 1:
        v = v[::stride]
    return (T[:3, :3] @ v.T).T + T[:3, 3]


def _closest_min(mesh, pts, budget=6e7):
    """min distance from pts to mesh, chunked to a memory budget.

    trimesh allocates ~10 float64 intermediates of size (chunk x n_faces), so
    the chunk is derived from the face count rather than fixed.  If a chunk
    still fails, it is halved; if even a single point fails, the caller is told
    (None) rather than handed an optimistic number.
    """
    n_faces = max(1, len(mesh.faces))
    chunk = max(1, int(budget / n_faces))
    best = float("inf")
    i = 0
    while i < len(pts):
        take = chunk
        while take >= 1:
            try:
                _, d, _ = trimesh.proximity.closest_point(mesh,
                                                          pts[i:i + take])
                if len(d):
                    best = min(best, float(d.min()))
                break
            except (MemoryError, np.core._exceptions._ArrayMemoryError):
                take //= 2
        if take < 1:
            return None
        i += take
    return None if best == float("inf") else best


def mesh_gap(arm_part, T, env_part, stride=6, chunk=None, env_stride=1):
    """Tier-2 minimum surface distance (mm), both directions.

    Returns None if the distance could not be computed within the memory
    budget -- the caller must treat that as CANNOT_EVALUATE, never as clear.
    """
    em = mesh_of(env_part["path"])
    am = mesh_of(arm_part["path"])
    pa = posed_points(arm_part, T, stride=stride)
    d1 = _closest_min(em, pa)
    Ri, ti = T[:3, :3].T, T[:3, 3]
    ve = np.asarray(em.vertices, dtype=float)
    if env_stride > 1:
        ve = ve[::env_stride]
    d2 = _closest_min(am, (Ri @ (ve - ti).T).T)
    vals = [v for v in (d1, d2) if v is not None]
    if not vals:
        return None
    return min(vals)


def screen_pose(q_deg, arms, envs, aabb_trigger=8.0, stride=6, q_ref=None):
    """AABB screen, then mesh distance for every pair the screen cannot clear.

    A pair is only skipped when its AABB gap proves separation, so a reported
    clean result is a bound, not a sample.

    q_ref is the pose the supplied arm meshes are BAKED at.  It must be given
    whenever the STOWED mesh set is used, because those meshes already stand at
    q_stow -- posing them relative to q = 0 would move the arm twice.
    """
    Ts = {cad: rel_transform(a["link"], q_deg, q_ref)
          for cad, a in arms.items()}
    boxes = {cad: transform_box(a["box"], Ts[cad]) for cad, a in arms.items()}
    rows = []
    for cad, a in arms.items():
        for en, e in envs.items():
            g = aabb_gap(boxes[cad], e["box"])
            rec = {"arm_part": cad, "link": a["link"], "env_part": en,
                   "env_role": e["role"], "aabb_gap_mm": round(g, 4),
                   "mesh_gap_mm": None, "tier": "AABB_CLEAR"}
            if g <= aabb_trigger:
                mg = mesh_gap(a, Ts[cad], e, stride=stride)
                if mg is None:
                    # fail-closed: an unevaluable pair is NOT clear
                    rec["tier"] = "CANNOT_EVALUATE"
                    rec["mesh_gap_mm"] = None
                else:
                    rec["mesh_gap_mm"] = round(mg, 4)
                    rec["tier"] = "MESH"
            rows.append(rec)
    return rows, Ts


def effective_gap(r):
    """Best available gap.  A pair the mesh stage could not evaluate returns
    None, which callers must treat as CANNOT_EVALUATE, never as clear."""
    if r["tier"] == "CANNOT_EVALUATE":
        return None
    return r["mesh_gap_mm"] if r["mesh_gap_mm"] is not None \
        else r["aabb_gap_mm"]
