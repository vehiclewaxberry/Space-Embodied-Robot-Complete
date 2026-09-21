# V8 design probe for root causes B (J1 coil vs link1 boss) and C (annulus
# wall vs link2 @ STOW q1=2.54). Reports contact-zone geometry for notch/bump
# sizing.
import os
import json
import math
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
inv_T0 = {k: np.linalg.inv(v) for k, v in T0.items()}

def load_field(name, fname):
    return SW.TriField(name, np.load(os.path.join(SW.P_PACK, fname), allow_pickle=False))

link1 = link2 = None
wall = {}
for grp in manifest["files"]:
    if grp["group"] == "arm_vendor":
        for e in grp["entries"]:
            if e["link"] == "link1":
                link1 = load_field("link1", e["file"])
            if e["link"] == "link2":
                link2 = load_field("link2", e["file"])
    if grp["group"] == "route_c_parts":
        for e in grp["entries"]:
            if e["name"].startswith("RC-GDE-J1-ANNULUS") or e["name"] == "RC-GDE-J1-LINER":
                wall[e["name"]] = load_field(e["name"], e["file"])

J1_AXIS_PT = np.array([-0.084, 0.0, 0.0])   # J1 axis line x=-0.084, y=0 (z any)

def cyl_report(P, label, r_lo=40.0, r_hi=90.0, z_lo=100.0, z_hi=160.0):
    """cylindrical coords about the J1 axis (x,y) for points in the zone."""
    r = np.hypot(P[:, 0] - J1_AXIS_PT[0], P[:, 1] - J1_AXIS_PT[1])
    az = np.degrees(np.arctan2(P[:, 1] - J1_AXIS_PT[1], P[:, 0] - J1_AXIS_PT[0]))
    m = (r >= r_lo) & (r <= r_hi) & (P[:, 2] >= z_lo) & (P[:, 2] <= z_hi)
    if not m.any():
        print("%s: no verts in zone" % label)
        return None
    print("%s: zone verts %d, r %.1f..%.1f, az %.1f..%.1f, z %.1f..%.1f" % (
        label, int(m.sum()), r[m].min(), r[m].max(), az[m].min(), az[m].max(),
        P[m, 2].min(), P[m, 2].max()))
    return r, az, m

print("=== B: link1 boss near coil contact (46.2,-38.2,134) ===")
# link1 posed at q=0 (rigid with base for this inspection of geometry in A0)
P1 = SW.xform_batch(arm.mount @ T0["link1"] @ inv_T0["link1"], link1.v0)
cyl_report(P1, "link1 verts")
# find link1 verts close to the contact point
cp = np.array([46.2, -38.2, 134.0])
d = np.linalg.norm(P1 - cp, axis=1)
near = d < 15.0
print("link1 verts within 15 mm of contact: %d" % near.sum())
if near.any():
    r, az, m = cyl_report(P1[near], "  near-contact link1", 0, 1e9, -1e9, 1e9)
    rr = np.hypot(P1[near, 0] + 0.084, P1[near, 1])
    print("  radial extent of boss verts: r %.1f..%.1f (coil R60 -> boss intrudes %.2f mm)"
          % (rr.min(), rr.max(), 60.0 - rr.min()))

print()
print("=== C: annulus wall vs link2 @ q1=2.540711 (STOW) ===")
q = [2.540711, -2.932153, -0.994838, -0.718081, -0.365716, -0.05236]
T = arm.fk(q)
inv_TS_l2 = np.linalg.inv(arm.mount @ T["link2"])
for name, fld in wall.items():
    P = SW.xform_batch(arm.mount @ T["base_link"] @ inv_T0["base_link"], fld.v0)
    Pl = SW.xform_batch(inv_TS_l2, P)
    c = link2.signed_clearance_batch(Pl, 0.5)
    ok = np.isfinite(c)
    if not ok.any():
        print("%s: no eval" % name); continue
    k = int(np.nanargmin(c))
    if c[k] > 2.0:
        continue
    # worst contact point in A0 frame
    pw = P[ok][np.array([k])] if False else P[np.flatnonzero(ok)[k]]
    r = math.hypot(pw[0] + 0.084, pw[1])
    az = math.degrees(math.atan2(pw[1], pw[0] + 0.084))
    print("%s: min %.3f at A0 %s (r %.1f az %.1f z %.1f)" % (
        name, c[k], np.round(pw, 1).tolist(), r, az, pw[2]))
    # zone: all verts with c < +2
    close = ok & (c < 2.0)
    Pz = P[close]
    if len(Pz):
        rz = np.hypot(Pz[:, 0] + 0.084, Pz[:, 1])
        azz = np.degrees(np.arctan2(Pz[:, 1], Pz[:, 0] + 0.084))
        print("   contact zone verts %d: r %.1f..%.1f az %.1f..%.1f z %.1f..%.1f" % (
            len(Pz), rz.min(), rz.max(), azz.min(), azz.max(),
            Pz[:, 2].min(), Pz[:, 2].max()))
