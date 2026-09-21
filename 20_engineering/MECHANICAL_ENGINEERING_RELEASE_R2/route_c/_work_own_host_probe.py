# Own-host (rigid pair) clearance probe: which segment's cable points penetrate
# their own attachment host vendor mesh at q=0. Fast (skips mission/key/cross).
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
T0 = arm.fk([0.0] * 6)
inv_T0 = {k: np.linalg.inv(v) for k, v in T0.items()}
inv_TS0 = {k: np.linalg.inv(arm.mount @ v) for k, v in T0.items()}

vendor_fields = {}
for grp in manifest["files"]:
    if grp["group"] == "arm_vendor":
        for e in grp["entries"]:
            vendor_fields[e["link"]] = SW.TriField(
                e["link"], np.load(os.path.join(SW.P_PACK, e["file"]), allow_pickle=False))

center = json.load(open(SW.P_CENTER, encoding="utf-8"))
host_plan = {
    ("SEG-00_BUS_FEEDTHROUGH_AND_RISER", 0): ("base_link", None),
    ("SEG-01_J1_ANNULAR_SERVICE_LOOP", 0): ("base_link", None),
    ("SEG-01_J1_ANNULAR_SERVICE_LOOP", 1): ("link1", None),
    ("SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL", 0): ("link1", "link2"),
    ("SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL", 1): ("link2", "link1"),
    ("SEG-03_J3_CARRIER_HYBRID_WRAP", 0): ("link2", "link3"),
    ("SEG-03_J3_CARRIER_HYBRID_WRAP", 1): ("link3", "link2"),
    ("SEG-04_J4_LOOP_LINK4_CHANNEL_RISER", 0): ("link3", "link4"),
    ("SEG-04_J4_LOOP_LINK4_CHANNEL_RISER", 1): ("link4", "link3"),
    ("SEG-05_J5_WRIST_WRAP", 0): ("link4", "link5"),
    ("SEG-05_J5_WRIST_WRAP", 1): ("link5", "link4"),
    ("SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN", 0): ("link5", None),
    ("SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN", 1): ("link6", None),
    ("SEG-07A_WRIST_TAIL_DATA", 0): ("link6", None),
    ("SEG-07B_WRIST_TAIL_POWER", 0): ("link6", None),
}
HOSTS = SW.HOSTS
BUNDLE_R = SW.BUNDLE_R
D_STATIC = SW.D_STATIC

rows = []
for si, seg in enumerate(center["segments"]):
    sid = seg["id"]
    for ci, sec in enumerate(seg["sections"]):
        pts, L, rmin = SW.build_section(sec)
        host, alt = host_plan[(sid, ci)]
        for h, altflag in ((host, 0), (alt, 1)):
            if h is None or h not in vendor_fields:
                continue
            hi = HOSTS.index(h)
            Mh = T0[h] @ inv_T0[h]
            P = SW.xform_batch(arm.mount @ Mh, pts)
            Pl = SW.xform_batch(inv_TS0[h], P)
            fld = vendor_fields[h]
            c = fld.signed_clearance_batch(Pl, BUNDLE_R)
            ok = ~np.isnan(c)
            if not ok.any():
                continue
            gated = c[ok] - D_STATIC
            k = int(np.argmin(gated))
            idxs = np.flatnonzero(ok)
            pi = int(idxs[k])
            rows.append({
                "segment": sid, "section": ci, "host": h, "alternate": bool(altflag),
                "gated_mm": float(gated[k]), "raw_mm": float(c[pi]),
                "point_A0_q0": [float(x) for x in pts[pi]],
            })

rows.sort(key=lambda r: r["gated_mm"])
print("%-44s %-3s %-9s %-5s %9s %9s  %s" % ("segment", "sec", "host", "alt", "gated", "raw", "point_A0_q0"))
for r in rows[:14]:
    print("%-44s %-3d %-9s %-5s %9.3f %9.3f  %s" % (
        r["segment"], r["section"], r["host"], str(r["alternate"]),
        r["gated_mm"], r["raw_mm"], [round(x, 1) for x in r["point_A0_q0"]]))
print("...")
for r in rows[-4:]:
    print("%-44s %-3d %-9s %-5s %9.3f %9.3f  %s" % (
        r["segment"], r["section"], r["host"], str(r["alternate"]),
        r["gated_mm"], r["raw_mm"], [round(x, 1) for x in r["point_A0_q0"]]))
