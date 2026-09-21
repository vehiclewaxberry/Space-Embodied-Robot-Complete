# V8 design probe v3: B boss triangles + C contact zone in true A0 coords.
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
inv_mount = np.linalg.inv(arm.mount)

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

print("=== B: link1 triangles near coil contact A0 (46.2,-38.2,134) ===")
tris = np.stack([link1.v0, link1.v0 + link1.e1, link1.v0 + link1.e2], axis=1)
cen = tris.mean(axis=1)  # link1-local
# to A0 world at q=0
cen_w = SW.xform_batch(arm.mount @ T0["link1"], cen)
cen_a0 = SW.xform_batch(inv_mount, cen_w)
cp = np.array([46.2, -38.2, 134.0])
d = np.linalg.norm(cen_a0 - cp, axis=1)
near = d < 12.0
print("link1 tri centroids within 12 mm: %d" % near.sum())
if near.any():
    Pn = cen_a0[near]
    rr = np.hypot(Pn[:, 0] + 0.084, Pn[:, 1])
    azz = np.degrees(np.arctan2(Pn[:, 1], Pn[:, 0] + 0.084))
    zz = Pn[:, 2]
    print("boss tris: r %.1f..%.1f az %.1f..%.1f z %.1f..%.1f" % (
        rr.min(), rr.max(), azz.min(), azz.max(), zz.min(), zz.max()))
    print("boss inner extent r_min=%.2f -> coil R60 intrude %.2f; for raw+3 need cable r >= %.1f"
          % (rr.min(), 60.0 - rr.min(), rr.min() + 7.5))

print()
print("=== C: annulus-wall contact zone in A0 coords ===")
q = [2.540711, -2.932153, -0.994838, -0.718081, -0.365716, -0.05236]
T = arm.fk(q)
inv_T0 = {k: np.linalg.inv(v) for k, v in T0.items()}
inv_TS_l2 = np.linalg.inv(arm.mount @ T["link2"])
for name in ("RC-GDE-J1-ANNULUS-WALL", "RC-GDE-J1-ANNULUS-UP",
             "RC-GDE-J1-ANNULUS-LOW", "RC-GDE-J1-LINER"):
    fld = wall[name]
    P_S = SW.xform_batch(arm.mount @ T["base_link"] @ inv_T0["base_link"], fld.v0)
    Pl = SW.xform_batch(inv_TS_l2, P_S)
    c = link2.signed_clearance_batch(Pl, 0.5)
    ok = np.isfinite(c)
    if not ok.any():
        continue
    k = int(np.nanargmin(c))
    if c[k] > 2.0:
        continue
    P_A0 = SW.xform_batch(inv_mount, P_S)  # back to A0
    pw = P_A0[k]
    r = math.hypot(pw[0] + 0.084, pw[1])
    az = math.degrees(math.atan2(pw[1], pw[0] + 0.084))
    print("%s: min %.3f at A0 %s (r %.1f az %.1f z %.1f)" % (
        name, c[k], np.round(pw, 1).tolist(), r, az, pw[2]))
    close = ok & (c < 2.0)
    Pz = P_A0[close]
    rz = np.hypot(Pz[:, 0] + 0.084, Pz[:, 1])
    azz = np.degrees(np.arctan2(Pz[:, 1], Pz[:, 0] + 0.084))
    print("   zone(c<2): n=%d r %.1f..%.1f az %.1f..%.1f z %.1f..%.1f" % (
        len(Pz), rz.min(), rz.max(), azz.min(), azz.max(),
        Pz[:, 2].min(), Pz[:, 2].max()))
