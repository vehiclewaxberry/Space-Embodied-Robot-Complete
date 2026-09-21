"""sim_09 -- coarse capsule-vs-primitive collision margin along the approach.

Geometry and every modelling assumption live in
20_engineering/config/grasp_evaluator/collision_geometry_v1.yaml (A1..A7). This module only
implements the declared algorithm:

  * B601 links = capsules (radius from config); endpoints from the B601Arm.fk
    joint-origin chain  mount -> o1..o6 -> EE  at each sampled q.
  * >= 9 sample points per capsule axis; analytic point-primitive SIGNED
    distance (box / cylinder SDF, negative = penetration) minus capsule radius.
  * allowed-contact zone: capsule samples within `grasp_allowed_zone_radius_m`
    of the grasp point are exempt from the TARGET keep-out check only.
  * capsule 0 (mount->joint1) vs servicer bus excluded (structurally attached).

Outputs the minimum margin along the trajectory and the time it occurs.
Pure numpy; deterministic.
"""
import _bootstrap  # noqa: F401
import os
import numpy as np
import yaml

from b601_model import T_SM_t

CFG_PATH = os.path.join(_bootstrap.CONFIG_DIR, "collision_geometry_v1.yaml")
_CFG_CACHE = {}


def load_geometry(path=CFG_PATH):
    if path not in _CFG_CACHE:
        with open(path, encoding="utf-8") as f:
            _CFG_CACHE[path] = yaml.safe_load(f)
    return _CFG_CACHE[path]


# ---------------- analytic point-primitive signed distances ----------------

def point_box_sd(p_local, half):
    """Signed distance of a point (primitive-local frame) to a box surface."""
    q = np.abs(np.asarray(p_local, float)) - np.asarray(half, float)
    outside = np.linalg.norm(np.maximum(q, 0.0))
    inside = min(float(np.max(q)), 0.0)
    return outside + inside


def point_cylinder_sd(p_local, radius, half_len):
    """Signed distance to a z-axis cylinder surface (primitive-local frame)."""
    x, y, z = p_local
    dr = float(np.hypot(x, y)) - radius
    dz = abs(float(z)) - half_len
    outside = float(np.hypot(max(dr, 0.0), max(dz, 0.0)))
    inside = min(max(dr, dz), 0.0)
    return outside + inside


def point_primitive_sd(p_S, prim):
    """prim: {type, R (3x3 primitive->S, optional), center_S, dims...}."""
    R = prim.get("R")
    c = np.asarray(prim["center_S"], float)
    p_local = (np.asarray(p_S, float) - c) if R is None else np.asarray(R, float).T @ (np.asarray(p_S, float) - c)
    if prim["type"] == "box":
        return point_box_sd(p_local, prim["half_extents_m"])
    if prim["type"] == "cylinder":
        return point_cylinder_sd(p_local, prim["radius_m"], prim["half_length_m"])
    raise ValueError(f"unknown primitive type {prim['type']}")


# ---------------- scene assembly ----------------

def static_primitives(geo=None):
    """Servicer bus + panels in S (fixed). Returns list of primitive dicts with
    a `name` key (used by the exclusion rule)."""
    geo = geo or load_geometry()
    prims = [{"name": "servicer_body", **geo["servicer_body"]}]
    for k, p in enumerate(geo["panels"]):
        prims.append({"name": f"panel_{k}", **p})
    return prims


def target_primitive(target_id, R_TS, r_T_S, cg_T, geo=None):
    """Target keep-out primitive posed in S. R_TS = target->S rotation,
    r_T_S = target CoM in S, cg_T = target CAD cg (CoM in the CAD frame) so the
    primitive center = -cg_T relative to the CoM (config A4)."""
    geo = geo or load_geometry()
    spec = geo["targets"][target_id]
    center_T = -np.asarray(cg_T, float)          # geometric center rel. CoM
    prim = {"name": "target", "type": spec["type"],
            "R": np.asarray(R_TS, float),
            "center_S": np.asarray(r_T_S, float) + np.asarray(R_TS, float) @ center_T}
    if spec["type"] == "cylinder":
        prim["radius_m"] = float(spec["radius_m"])
        prim["half_length_m"] = float(spec["half_length_m"])
    else:
        prim["half_extents_m"] = [float(v) for v in spec["half_extents_m"]]
    return prim


def capsule_chain(arm, q):
    """Capsule endpoint chain at q: mount -> o_joint1..o_joint6 -> EE (in S)."""
    f = arm.fk(q)
    pts = [np.asarray(T_SM_t, float)]
    pts.extend(f["joint_origins"])
    pts.append(f["T_E"][:3, 3])
    return np.asarray(pts)


def configuration_margin(arm, q, target_prim, grasp_point_S, geo=None):
    """Minimum collision margin [m] of the arm at configuration q against the
    static primitives and the target keep-out (allowed-contact sphere exempt)."""
    geo = geo or load_geometry()
    radius = float(geo["arm_capsules"]["radius_m"])
    n_s = max(int(geo["arm_capsules"]["n_samples_per_capsule"]), 9)
    r_allow = float(geo["grasp_allowed_zone_radius_m"])
    excl = {(int(e["capsule_index"]), e["primitive"])
            for e in geo["arm_capsules"].get("exclusions", [])}
    statics = static_primitives(geo)
    chain = capsule_chain(arm, q)
    grasp = np.asarray(grasp_point_S, float)

    margin = np.inf
    ts = np.linspace(0.0, 1.0, n_s)
    for k in range(len(chain) - 1):
        pts = chain[k][None, :] + ts[:, None] * (chain[k + 1] - chain[k])[None, :]
        for prim in statics:
            if (k, prim["name"]) in excl:
                continue
            for p in pts:
                margin = min(margin, point_primitive_sd(p, prim) - radius)
        if target_prim is not None:
            for p in pts:
                if np.linalg.norm(p - grasp) < r_allow:
                    continue                     # allowed-contact zone (A5)
                margin = min(margin, point_primitive_sd(p, target_prim) - radius)
    return float(margin)


def trajectory_margin(arm, q_of_t, t_grid, target_prim, grasp_point_S, geo=None):
    """Minimum margin along a joint trajectory. q_of_t: callable t -> q(6,).
    Returns dict {min_margin_m, t_at_min_s, margins (list)}."""
    geo = geo or load_geometry()
    margins = np.array([configuration_margin(arm, q_of_t(t), target_prim,
                                             grasp_point_S, geo) for t in t_grid])
    i = int(np.argmin(margins))
    return {"min_margin_m": float(margins[i]), "t_at_min_s": float(t_grid[i]),
            "margins": [float(m) for m in margins]}
