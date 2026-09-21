# V8 wrist design probe: link3/link4 body top-surface profiles in the wrist
# corridor (A0 frame, q=0), plus palm/link5 presence above the wrap plane.
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
T0 = arm.fk([0.0]*6)

def load(name, f):
    return SW.TriField(name, np.load(os.path.join(SW.P_PACK, f), allow_pickle=False))

fields = {}
palm = None
for grp in manifest["files"]:
    if grp["group"] == "arm_vendor":
        for e in grp["entries"]:
            if e["link"] in ("link3", "link4", "link5", "gripper_link"):
                fields[e["link"]] = load(e["link"], e["file"])
    if grp["group"] == "gripper_rails":
        palm = load("PALM", grp["palm_slot"]["file"])

def top_profile(fld, link, x_lo, x_hi, y_lo, y_hi, dx=10.0, dy=10.0):
    """max z of the posed mesh within each (x,y) bin; A0 coords."""
    v0, e1, e2 = fld.v0, fld.e1, fld.e2
    verts = np.concatenate([v0, v0 + e1, v0 + e2], axis=0)
    Pw = SW.xform_batch(arm.mount @ T0[link], verts)
    Pa0 = SW.xform_batch(np.linalg.inv(arm.mount), Pw)
    print("  %s top-z profile (x\\y):" % link)
    hdr = "      " + "".join("%7d" % y for y in range(int(y_lo), int(y_hi) + 1, int(dy)))
    print(hdr)
    for x in range(int(x_lo), int(x_hi) + 1, int(dx)):
        row = []
        for y in range(int(y_lo), int(y_hi) + 1, int(dy)):
            m = (Pa0[:, 0] >= x - dx / 2) & (Pa0[:, 0] < x + dx / 2) & \
                (Pa0[:, 1] >= y - dy / 2) & (Pa0[:, 1] < y + dy / 2)
            row.append(Pa0[m, 2].max() if m.any() else np.nan)
        print("  x=%4d " % x + "".join("%7.1f" % v if np.isfinite(v) else "      -" for v in row))

print("=== link4 body top (wrist corridor) ===")
top_profile(fields["link4"], "link4", 60, 130, -90, 60)
print("=== link3 body top (wrap zone) ===")
top_profile(fields["link3"], "link3", -60, 90, -90, 60)
print("=== link5 top near helix entry ===")
top_profile(fields["link5"], "link5", 60, 140, -90, 30)
print("=== palm z extent (A0) ===")
v0 = palm.v0
verts = np.concatenate([v0, v0 + palm.e1, v0 + palm.e2], axis=0)
Pw = SW.xform_batch(arm.mount @ T0["gripper_link"], verts)
Pa0 = SW.xform_batch(np.linalg.inv(arm.mount), Pw)
print("  palm bounds A0: min %s max %s" % (np.round(Pa0.min(0), 1).tolist(), np.round(Pa0.max(0), 1).tolist()))
