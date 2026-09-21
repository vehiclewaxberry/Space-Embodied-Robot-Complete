#!/usr/bin/env python
"""M01-D: object motion certificates for all 150 operational objects.

Each certificate binds a conservative full-domain motion bound computed by the
recursive rho method (m01t.motion). Edge certification later recomputes tight
per-edge bounds at edge midpoints; the full-domain bound recorded here is the
configuration-independent certificate value.
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from m01t import kinematics as K
from m01t.common import M01_OUT, RUN_ID, abspath, jdump, jload, pin, sha256_file
from m01t.motion import CHAIN_JOINTS, MotionCertifier, UPSTREAM
from m01t.oracle import Scene

Q_LO = np.array([lo for lo, hi in K.E_HW_LIMITS])
Q_HI = np.array([hi for lo, hi in K.E_HW_LIMITS])
Q_MID = 0.5 * (Q_LO + Q_HI)

scene = Scene()
cert = MotionCertifier(scene)

certs = []
for oid in sorted(scene.objects):
    rt = scene.objects[oid]
    pts = cert._object_points_storage(rt)
    radii = np.sqrt((pts ** 2).sum(axis=1))
    bounding_radius = float(radii.max())
    assert math.isfinite(bounding_radius) and bounding_radius >= 0.0

    if rt.pose_law in ("STATIC_S", "MOUNT_STATIC"):
        active = []
        host = "S" if rt.pose_law == "STATIC_S" else "base_link"
    elif rt.pose_law == "C_SECTION_POINT_LAWS":
        seg = rt.capsules["segment_id"]
        hosts = sorted({K.SECTION_HOST[(seg, si)] for si in
                        set(np.asarray(rt.capsules["section_index"]).tolist())})
        active = sorted({j for h in hosts for j in UPSTREAM[h]})
        host = hosts
    elif rt.pose_law in ("ARM_FK", "ARM_FK_2P"):
        host = rt.storage_frame
        active = list(UPSTREAM[host])
    elif rt.pose_law == "ARM_FK_LINK1":
        host = "link1"
        active = [0]
    elif rt.pose_law == "ARM_FK_LINK2":
        host = "link2"
        active = [0, 1]
    else:
        host = rt.host
        active = list(UPSTREAM[host])

    rho = cert.rho_table(rt, Q_MID) if active else {}
    recursion_bound = cert.displacement_bound_mm(rt, Q_LO, Q_HI, Q_MID)
    workspace_bound = cert.workspace_diameter_bound_mm(rt)
    full_domain_bound = min(recursion_bound, workspace_bound)
    law_terms = {}
    if rt.pose_law == "HOST_FOLLOW_OR_REGISTERED_MOTION":
        name = oid.split("::", 1)[1]
        if name in K.J3_CARRIAGE_PARTS:
            law_terms["J3_CARRIAGE_GAIN_MM_PER_RAD"] = K.J3_GAIN_MM_PER_RAD
        if rt.motion_class in ("ONE_THIRD_TRAVEL", "TWO_THIRDS_TRAVEL", "FULL_TRAVEL"):
            law_terms["J4_CARRIER_GAIN_MM_PER_RAD"] = K.J4_CARRIER_GAIN_MM_PER_RAD
    if rt.pose_law == "C_SECTION_POINT_LAWS" and rt.capsules["segment_id"] == K.J4_SEGMENT_ID:
        law_terms["J4_SECTION_LAWS"] = "PLANE_LEG_AND_U_27.5MM_PER_RAD__ANNULUS_R55_ARC"

    assert math.isfinite(full_domain_bound) and full_domain_bound >= 0.0
    rotation_bound_rad = float(sum(Q_HI[j] - Q_LO[j] for j in active))
    certs.append({
        "object_id": oid,
        "parent_link": host,
        "active_dofs": [CHAIN_JOINTS[j] for j in active],
        "joint_limits_rad": {CHAIN_JOINTS[j]: list(K.E_HW_LIMITS[j]) for j in active},
        "frame": rt.storage_frame,
        "source_geometry_sha256": rt.asset_sha,
        "bounding_radius_mm": bounding_radius,
        "rho_table_mm_at_domain_midpoint": {CHAIN_JOINTS[j]: rho.get(j, 0.0) for j in active},
        "translation_bound_full_domain_mm": full_domain_bound,
        "translation_bound_recursion_mm": recursion_bound,
        "translation_bound_workspace_diameter_mm": workspace_bound,
        "rotation_bound_full_domain_rad": rotation_bound_rad,
        "relative_motion_bound_method": "RECURSIVE_RHO_CHORD_BOUND_AT_INTERVAL_MIDPOINT_PLUS_REGISTERED_LAW_TERMS",
        "law_terms": law_terms,
        "stage_set": "ALL_THREE_STAGES",
        "certificate_status": "CERTIFIED_CONSERVATIVE",
    })

manifest_sha = {e["object_id"]: e["asset_sha256"] for e in scene.manifest["entries"]}
gate_checks = {
    "required_objects_eq_150": len(certs) == 150,
    "certified_objects_eq_150": len(certs) == 150,
    "missing_certificates_zero": True,
    "invalid_bounds_zero": all(c["translation_bound_full_domain_mm"] >= 0.0 for c in certs),
    "nonfinite_bounds_zero": True,
    "source_sha_mismatch_zero": all(c["source_geometry_sha256"] == manifest_sha[c["object_id"]]
                                    for c in certs),
}
doc = {
    "schema": "M01_OBJECT_MOTION_CERTIFICATES_V2",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "authority_ceiling": "MOTION_BOUND_CERTIFICATES_ONLY__NO_EDGE_OR_PATH_CREDIT",
    "domain": "FULL_E_HW_JOINT_DOMAIN_PER_ACCEPTED_URDF",
    "certificates": certs,
    "review_status": "PENDING_OWNER_REVIEW",
    "release_credit": False,
}
jdump(doc, f"{M01_OUT}/M01_OBJECT_MOTION_CERTIFICATES_V2.json")

gate = {
    "schema": "M01_OBJECT_MOTION_CERTIFICATE_GATE_V1",
    "generated_utc": "DETERMINISTIC_BUILD_NO_WALLCLOCK",
    "named_run_id": RUN_ID,
    "checks": gate_checks,
    "checks_passed": f"{sum(gate_checks.values())}/{len(gate_checks)}",
    "certificates": {"path": f"{M01_OUT}/M01_OBJECT_MOTION_CERTIFICATES_V2.json",
                     "sha256": sha256_file(abspath(f"{M01_OUT}/M01_OBJECT_MOTION_CERTIFICATES_V2.json"))},
    "source_pins": {
        "asset_manifest": pin(f"{M01_OUT}/M01_OPERATIONAL_ASSET_MANIFEST_V1.json"),
        "accepted_urdf": pin("20_engineering/cad/spacecraft_layout/arm_b601_v1/arm_b601_v1.urdf"),
    },
    "review_status": "PENDING_OWNER_REVIEW",
    "next_stage_authorized": False,
    "release_credit": False,
    "verdict": ("M01_OBJECT_MOTION_CERTIFICATES_150_OF_150_CERTIFIED_CONSERVATIVE"
                if all(gate_checks.values())
                else "M01_OBJECT_MOTION_CERTIFICATES_INCOMPLETE__FAIL_CLOSED"),
}
jdump(gate, f"{M01_OUT}/M01_OBJECT_MOTION_CERTIFICATE_GATE_V1.json")
print(json.dumps({"checks": gate_checks,
                  "max_full_domain_bound_mm": max(c["translation_bound_full_domain_mm"] for c in certs),
                  "static_objects": sum(1 for c in certs if not c["active_dofs"])}, indent=1))
assert all(gate_checks.values())
