# Wrist-descent geometry probe: link4 body envelope vs SEG-04/05 cable legs.
import os
import json
import importlib.util

import numpy as np
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("RC_VARIANT", "V7")
os.environ["RC_FAST"] = "1"
spec = importlib.util.spec_from_file_location(
    "rc_sweep", os.path.join(HERE, "ROUTE_C_EXACT_SWEEP_V1.py"))
SW = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SW)

manifest = json.load(open(SW.P_MANIFEST, encoding="utf-8"))
mount = yaml.safe_load(open(SW.P_MOUNT, encoding="utf-8"))
arm = SW.ArmModel(SW.P_URDF, mount["mount"]["transform_mm_rows"])
T0 = arm.fk([0.0] * 6)
inv_T0 = {k: np.linalg.inv(v) for k, v in T0.items()}

# vendor link4 mesh bounds in A0(q=0) and in link4-local
for grp in manifest["files"]:
    if grp["group"] == "arm_vendor":
        for e in grp["entries"]:
            if e["link"] in ("link4", "link5", "link3", "gripper_link"):
                fld = SW.TriField(e["link"], np.load(
                    os.path.join(SW.P_PACK, e["file"]), allow_pickle=False))
                print("%s local bounds: min %s max %s" % (
                    e["link"], np.round(fld.bmin, 1).tolist(), np.round(fld.bmax, 1).tolist()))

# pose link4 bounds into A0 at q=0 for intuition
fld4 = None
for grp in manifest["files"]:
    if grp["group"] == "arm_vendor":
        for e in grp["entries"]:
            if e["link"] == "link4":
                fld4 = SW.TriField("link4", np.load(
                    os.path.join(SW.P_PACK, e["file"]), allow_pickle=False))
corners = np.array([[x, y, z] for x in (fld4.bmin[0], fld4.bmax[0])
                    for y in (fld4.bmin[1], fld4.bmax[1])
                    for z in (fld4.bmin[2], fld4.bmax[2])])
cs = SW.xform_batch(arm.mount @ T0["link4"] @ inv_T0["link4"], corners)
print("link4 posed AABB in S(q=0): min", np.round(cs.min(0), 1).tolist(),
      "max", np.round(cs.max(0), 1).tolist())

# offending cable legs: SEG-04 sec1 poly [j4_end, M4, K2, T1_J5]; SEG-05 sec1 poly
center = json.load(open(SW.P_CENTER, encoding="utf-8"))
for seg in center["segments"]:
    if seg["id"] == "SEG-04_J4_LOOP_LINK4_CHANNEL_RISER":
        for ci, sec in enumerate(seg["sections"]):
            pts, L, rmin = SW.build_section(sec)
            print("SEG-04 sec%d pts %d: first %s last %s" % (
                ci, len(pts), np.round(pts[0], 1).tolist(), np.round(pts[-1], 1).tolist()))
            if ci == 1:
                # distance profile vs link4 along this section
                P = SW.xform_batch(arm.mount @ T0["link4"] @ inv_T0["link4"], pts)
                Pl = SW.xform_batch(np.linalg.inv(arm.mount @ T0["link4"]), P)
                c = fld4.signed_clearance_batch(Pl, 4.5)
                ok = ~np.isnan(c)
                print("  sec1 vs link4: min signed %.3f at pt %s" % (
                    np.nanmin(c), np.round(pts[int(np.nanargmin(c))], 1).tolist()))
                # print z profile near the worst region
                idx = np.argsort(c)[:6]
                for i in idx:
                    print("    c=%.2f pt=%s" % (c[i], np.round(pts[i], 1).tolist()))
    if seg["id"] == "SEG-05_J5_WRIST_WRAP":
        for ci, sec in enumerate(seg["sections"]):
            pts, L, rmin = SW.build_section(sec)
            print("SEG-05 sec%d pts %d: first %s last %s" % (
                ci, len(pts), np.round(pts[0], 1).tolist(), np.round(pts[-1], 1).tolist()))
            if ci == 1:
                P = SW.xform_batch(arm.mount @ T0["link4"] @ inv_T0["link4"], pts)
                Pl = SW.xform_batch(np.linalg.inv(arm.mount @ T0["link4"]), P)
                c = fld4.signed_clearance_batch(Pl, 4.5)
                idx = np.argsort(c)[:6]
                for i in idx:
                    print("    c=%.2f pt=%s" % (c[i], np.round(pts[i], 1).tolist()))

# where do the RC-CHN-L4 channel parts sit? (intended guide location)
for grp in manifest["files"]:
    if grp["group"] == "route_c_parts":
        for e in grp["entries"]:
            if e["name"].startswith("RC-CHN-L4") or e["name"].startswith("RC-GDE-J4"):
                f2 = SW.TriField(e["name"], np.load(
                    os.path.join(SW.P_PACK, e["file"]), allow_pickle=False))
                print("RC part %-22s host %-6s bounds min %s max %s" % (
                    e["name"], e["host_link"], np.round(f2.bmin, 1).tolist(),
                    np.round(f2.bmax, 1).tolist()))
