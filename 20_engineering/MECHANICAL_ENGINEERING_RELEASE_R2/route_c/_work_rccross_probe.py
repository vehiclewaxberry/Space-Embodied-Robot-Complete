# Identify which base_link-hosted RC part approaches vendor link2 to -2.913
# at the RC cross-clearance record pose q=(2.5407,-2.9322,-0.9948,-0.7181,-0.3657,-0.0524)
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

q = [2.540711, -2.932153, -0.994838, -0.718081, -0.365716, -0.05236]
T = arm.fk(q)
inv_TS_link2 = np.linalg.inv(arm.mount @ T["link2"])

link2_fld = None
for grp in manifest["files"]:
    if grp["group"] == "arm_vendor":
        for e in grp["entries"]:
            if e["link"] == "link2":
                link2_fld = SW.TriField("link2", np.load(
                    os.path.join(SW.P_PACK, e["file"]), allow_pickle=False))

rows = []
for grp in manifest["files"]:
    if grp["group"] == "route_c_parts":
        for e in grp["entries"]:
            if e.get("host_link") != "base_link" or not e.get("valid"):
                continue
            if e.get("kind") == "bundle_envelope":
                continue
            fld = SW.TriField(e["name"], np.load(
                os.path.join(SW.P_PACK, e["file"]), allow_pickle=False))
            P = SW.xform_batch(arm.mount @ T["base_link"] @ inv_T0["base_link"], fld.v0)
            Pl = SW.xform_batch(inv_TS_link2, P)
            c = link2_fld.signed_clearance_batch(Pl, 0.5)
            if np.isfinite(c).any():
                rows.append((float(np.nanmin(c)), e["name"], e.get("kind")))
rows.sort()
for v, n, k in rows[:10]:
    print("%8.3f  %-28s %s" % (v, n, k))
