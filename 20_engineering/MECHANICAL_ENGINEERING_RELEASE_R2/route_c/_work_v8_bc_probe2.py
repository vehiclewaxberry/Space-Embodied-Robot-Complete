# V8 design probe v2 for root causes B and C (frame rules fixed).
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

print("=== B: link1 boss near coil contact A0 (46.2,-38.2,134) ===")
# vendor mesh local -> A0 world at q=0: P = mount @ T0[link] @ v0
P1 = SW.xform_batch(arm.mount @ T0["link1"], link1.v0)
cp = np.array([46.2, -38.2, 134.0])
d = np.linalg.norm(P1 - cp, axis=1)
for rad in (10.0, 20.0, 30.0):
    near = d < rad
    print("link1 verts within %.0f mm: %d" % (rad, near.sum()))
    if near.any() and rad == 20.0:
        Pn = P1[near]
        rr = np.hypot(Pn[:, 0] + 0.084, Pn[:, 1])
        azz = np.degrees(np.arctan2(Pn[:, 1], Pn[:, 0] + 0.084))
        print("  boss zone: r %.1f..%.1f az %.1f..%.1f z %.1f..%.1f" % (
            rr.min(), rr.max(), azz.min(), azz.max(), Pn[:, 2].min(), Pn[:, 2].max()))
        print("  boss inner radial extent r_min=%.2f (coil R60 intrude %.2f)" %
              (rr.min(), 60.0 - rr.min()))

# coil cable points near contact: SEG-01 section 0 (helix)
center = json.load(open(SW.P_CENTER, encoding="utf-8"))
for seg in center["segments"]:
    if seg["id"] == "SEG-01_J1_ANNULAR_SERVICE_LOOP":
        pts, L, rmin = SW.build_section(seg["sections"][0])
        dd = np.linalg.norm(pts - cp, axis=1)
        k = int(np.argmin(dd))
        print("coil pt nearest contact: %s (d=%.1f)" % (np.round(pts[k], 1).tolist(), dd[k]))
        az_c = math.degrees(math.atan2(pts[k][1], pts[k][0] + 0.084))
        print("  coil contact azimuth %.1f deg, z %.1f" % (az_c, pts[k][2]))
        # coil points within az +-20 of contact: their z range
        az_all = np.degrees(np.arctan2(pts[:, 1], pts[:, 0] + 0.084))
        az_diff = np.abs((az_all - az_c + 180.0) % 360.0 - 180.0)
        mz = az_diff < 20.0
        print("  coil z-range in +-20deg sector: %.1f..%.1f" % (pts[mz, 2].min(), pts[mz, 2].max()))

print()
print("=== C: annulus wall vs link2 @ q1=2.540711 (STOW) ===")
q = [2.540711, -2.932153, -0.994838, -0.718081, -0.365716, -0.05236]
T = arm.fk(q)
inv_T0 = {k: np.linalg.inv(v) for k, v in T0.items()}
inv_TS_l2 = np.linalg.inv(arm.mount @ T["link2"])
for name, fld in sorted(wall.items()):
    P = SW.xform_batch(arm.mount @ T["base_link"] @ inv_T0["base_link"], fld.v0)
    Pl = SW.xform_batch(inv_TS_l2, P)
    c = link2.signed_clearance_batch(Pl, 0.5)
    ok = np.isfinite(c)
    if not ok.any():
        print("%s: no eval" % name); continue
    k = int(np.nanargmin(c))           # full-length index
    if c[k] > 2.0:
        print("%s: min %.3f (clear)" % (name, c[k])); continue
    pw = P[k]
    r = math.hypot(pw[0] + 0.084, pw[1])
    az = math.degrees(math.atan2(pw[1], pw[0] + 0.084))
    print("%s: min %.3f at A0 %s (r %.1f az %.1f z %.1f)" % (
        name, c[k], np.round(pw, 1).tolist(), r, az, pw[2]))
    close = ok & (c < 2.0)
    Pz = P[close]
    rz = np.hypot(Pz[:, 0] + 0.084, Pz[:, 1])
    azz = np.degrees(np.arctan2(Pz[:, 1], Pz[:, 0] + 0.084))
    print("   zone(c<2): n=%d r %.1f..%.1f az %.1f..%.1f z %.1f..%.1f" % (
        len(Pz), rz.min(), rz.max(), azz.min(), azz.max(),
        Pz[:, 2].min(), Pz[:, 2].max()))
