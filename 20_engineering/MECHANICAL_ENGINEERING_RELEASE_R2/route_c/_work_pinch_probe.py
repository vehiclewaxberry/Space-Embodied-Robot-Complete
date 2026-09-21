# Pinch probe: locate worst SEG-01 (joint1) / SEG-04 (joint4) / SEG-05 (joint5)
# cable points vs the joint housings (vendor parent/child meshes) at q=0.
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
inv_T0 = {k: np.linalg.inv(v) for k, v in T0.items()}
inv_TS0 = {k: np.linalg.inv(arm.mount @ v) for k, v in T0.items()}
vendor = {}
for grp in manifest["files"]:
    if grp["group"] == "arm_vendor":
        for e in grp["entries"]:
            vendor[e["link"]] = SW.TriField(
                e["link"], np.load(os.path.join(SW.P_PACK, e["file"]), allow_pickle=False))

center = json.load(open(SW.P_CENTER, encoding="utf-8"))
SEG_BAND = {0: "SEG-01_J1_ANNULAR_SERVICE_LOOP",
            1: "SEG-02_J2_GUIDED_U_LOOP_AND_LINK2_CHANNEL",
            2: "SEG-03_J3_CARRIER_HYBRID_WRAP",
            3: "SEG-04_J4_LOOP_LINK4_CHANNEL_RISER",
            4: "SEG-05_J5_WRIST_WRAP",
            5: "SEG-06_J6_HELICAL_WRAP_AND_WRIST_RUN"}
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

band_pts = {}
for si, seg in enumerate(center["segments"]):
    sid = seg["id"]
    for ci, sec in enumerate(seg["sections"]):
        if sid not in band_pts:
            band_pts[sid] = []
        pts, L, rmin = SW.build_section(sec)
        band_pts[sid].append((pts, host_plan[(sid, ci)]))

for ji in (0, 3, 4):
    j = arm.rev[ji]
    sid = SEG_BAND[ji]
    housings = (j["parent"], j["child"])
    for hs in housings:
        if hs not in vendor:
            continue
        fld = vendor[hs]
        for pts, (h, alt) in band_pts[sid]:
            for hh in (h, alt):
                if hh is None:
                    continue
                P = SW.xform_batch(arm.mount @ T0[hh] @ inv_T0[hh], pts)
                Pl = SW.xform_batch(inv_TS0[hs], P)
                c = fld.signed_clearance_batch(Pl, SW.BUNDLE_R)
                if not np.isfinite(c).any():
                    continue
                k = int(np.nanargmin(c))
                if c[k] < 6.0:
                    print("%s vs %s: min %.2f at %s" % (
                        sid, hs, c[k], np.round(pts[k], 1).tolist()))
