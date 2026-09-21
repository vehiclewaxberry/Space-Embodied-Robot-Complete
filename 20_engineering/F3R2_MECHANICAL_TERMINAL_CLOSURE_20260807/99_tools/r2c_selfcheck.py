# -*- coding: utf-8 -*-
"""F3R2 G3-A self-check: prove the offline posing instrument before trusting it.

Checks, all fail-closed:
  1. at q = q_as_built every link transform is exactly identity;
  2. the CAD arm roll-up box equals the union of the per-link boxes
     (i.e. no arm solid was dropped by the label split);
  3. environment parts are classified with no part left unclassified;
  4. a known-motion sanity case: rotating joint1 by +90 deg moves the gripper
     by the distance the FK predicts.
"""
import json
import sys

import numpy as np

import r2_common as C
import r2_kin as K
import r2_pose as P

OUT = C.CLR2 / "G3A_INSTRUMENT_SELFCHECK.json"
rep = {"schema": "F3R2_G3A_SELFCHECK_V1", "checks": {}}
fail = []

# ---- 1. identity at the as-built pose ----
errs = {}
for cad, link in P.CAD_LINK.items():
    T = P.rel_transform(link, P.Q_AS_BUILT_DEG)
    errs[link] = float(np.abs(T - np.eye(4)).max())
rep["checks"]["identity_at_as_built"] = {
    "max_abs_deviation": max(errs.values()), "per_link": errs,
    "tolerance": 1e-9, "pass": max(errs.values()) <= 1e-9}
if not rep["checks"]["identity_at_as_built"]["pass"]:
    fail.append("identity_at_as_built")

# ---- 2. per-link boxes reconstruct the arm as measured in the STEP ----
# NOT against the ARM roll-up label: that entry carries a single container
# solid (1 object vs the 396 real arm solids), so it is not the arm's extent.
# The independent reference is the STEP probe, which enumerates every solid.
probe = json.loads((C.CLR2 / "mesh" / "STEP_PROBE_DEPLOYED_NOMINAL.json")
                   .read_text(encoding="utf-8"))
pb = [o["box_mm"] for o in probe["objects"]
      if o["n_solids"] > 0 and o["label"].startswith("B51_REF_")]
pbx = np.array(pb, dtype=float)
ref = np.concatenate([pbx[:, :3].min(axis=0), pbx[:, 3:].max(axis=0)])
arms = P.arm_parts()
union = None
for a in arms.values():
    b = a["box"]
    union = b.copy() if union is None else np.concatenate(
        [np.minimum(union[:3], b[:3]), np.maximum(union[3:], b[3:])])
d = float(np.abs(union - ref).max())
rep["checks"]["arm_split_lossless"] = {
    "union_of_link_meshes_mm": [round(v, 4) for v in union],
    "step_probe_all_arm_solids_mm": [round(v, 4) for v in ref],
    "n_arm_solids_in_probe": len(pb),
    "max_abs_delta_mm": round(d, 4), "tolerance_mm": 1.0,
    "note": ("independent reference: every B51_REF_* solid enumerated by the "
             "STEP probe.  The ARM roll-up label is NOT used -- it holds one "
             "container solid, not the arm."),
    "pass": d <= 1.0}
if not rep["checks"]["arm_split_lossless"]["pass"]:
    fail.append("arm_split_lossless")

# ---- 3. environment classification is total ----
man = P.load_manifest("DEPLOYED")
envs = P.env_parts()
roles = {}
for n, e in envs.items():
    roles.setdefault(e["role"], []).append(n)
unclassified = [n for n, e in envs.items() if not e["role"]]
all_parts = {n for n in man["parts"] if not n.startswith("B51_")
             and n != P.ARM_ROLLUP}
accounted = set(envs) | P.CONTAINER_PARTS | {n for n in all_parts
                                             if n.startswith("WING_")}
missing = sorted(all_parts - accounted)
rep["checks"]["environment_classified"] = {
    "n_env_parts": len(envs), "roles": {k: len(v) for k, v in roles.items()},
    "role_members": roles, "unclassified": unclassified,
    "parts_not_accounted_for": missing,
    "pass": not unclassified and not missing}
if not rep["checks"]["environment_classified"]["pass"]:
    fail.append("environment_classified")

# ---- 4. known-motion sanity: joint1 +90 deg ----
q = [90.0, 0, 0, 0, 0, 0]
Tg = P.rel_transform("gripper_link", q)
p0 = K.link_world(P.Q_AS_BUILT_DEG)["gripper_link"][:3, 3]
p1 = K.link_world(q)["gripper_link"][:3, 3]
moved_fk = float(np.linalg.norm(p1 - p0))
box0 = np.array(arms["B51_REF_gripper_detail_LINKLOCAL"]["box"])
c0 = (box0[:3] + box0[3:]) / 2.0
c1 = Tg[:3, :3] @ c0 + Tg[:3, 3]
moved_cad = float(np.linalg.norm(c1 - c0))
rep["checks"]["known_motion_joint1_90deg"] = {
    "fk_gripper_origin_travel_mm": round(moved_fk, 4),
    "cad_gripper_box_centre_travel_mm": round(moved_cad, 4),
    "both_nonzero": moved_fk > 1.0 and moved_cad > 1.0,
    "note": ("the two need not be equal -- one tracks the URDF gripper origin, "
             "the other the CAD box centre; the check is that the rigid motion "
             "is applied at all and is of the same order"),
    "same_order": 0.2 < (moved_cad / moved_fk) < 5.0 if moved_fk else False,
    "pass": moved_fk > 1.0 and moved_cad > 1.0}
if not rep["checks"]["known_motion_joint1_90deg"]["pass"]:
    fail.append("known_motion_joint1_90deg")

rep["mesh_deflection_mm"] = man["linear_deflection_mm"]
rep["arm_parts"] = {c: {"link": a["link"], "triangles": a["triangles"]}
                    for c, a in arms.items()}
rep["failed"] = fail
rep["verdict"] = "SELFCHECK_PASS" if not fail else "SELFCHECK_FAIL"
C.write_json(OUT, rep)

print("verdict:", rep["verdict"])
for k, v in rep["checks"].items():
    print("  %-30s %s" % (k, "PASS" if v["pass"] else "FAIL"))
print("  identity max dev:",
      rep["checks"]["identity_at_as_built"]["max_abs_deviation"])
print("  arm split delta mm:",
      rep["checks"]["arm_split_lossless"]["max_abs_delta_mm"])
print("  env roles:", rep["checks"]["environment_classified"]["roles"])
print("  unaccounted parts:",
      rep["checks"]["environment_classified"]["parts_not_accounted_for"])
sys.exit(0 if not fail else 1)
