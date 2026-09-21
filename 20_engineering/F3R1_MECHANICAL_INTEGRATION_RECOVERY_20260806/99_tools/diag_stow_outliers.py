# -*- coding: utf-8 -*-
"""Identify the 3 floating parts in STOWED_O13V3 by bbox-center outlier test.

Read-only: activate STOWED_O13V3 on the arm copy, read each leaf component's
assembly-space bbox center, compute the median center, and rank by distance.
Also compares each component's written stow origin against the FK-predicted
link origin so we can see whether the transform WRITE or a MATE fight caused
the fling.
"""
import json
import math
import sys

import numpy as np

from f3r1_env import F3R1, JLog
import b3_lib.sw_core as swc
import sw_session as ss
import urdf_chain as uc
from p4_stow_pose import link_of, t16_to_mat

log = JLog("diag_stow_outliers")
NC = F3R1 / "03_native_cad"
ARM = NC / "B601_ARM_B51_COPY/assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"
OUT = F3R1 / "04_configurations" / "F3R1_STOW_OUTLIERS.json"
Q_STOW_DEG = [145.572, -168.0, -57.0, -41.143, -20.954, -3.0]


def main():
    rep = {"schema": "F3R1_STOW_OUTLIERS_V1"}
    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    blog = swc.BuildLog("diag2")
    gm = swc.get_com_member
    try:
        app = ss.connect(log)
        links, joints = uc.load_chain()
        qs = {j["name"]: math.radians(Q_STOW_DEG[i]) for i, j in enumerate(joints[:6])}
        Ts = uc.fk(joints, qs)

        arm = swc.open_document(app, blog, str(ARM))
        cfgs = list(gm(arm, "GetConfigurationNames") or [])
        rep["configs"] = cfgs
        swc.activate_configuration(arm, blog, "STOWED_O13V3")
        swc.rebuild_or_fail(arm, blog, "activate stow for diag")

        conf = gm(arm, "ConfigurationManager").ActiveConfiguration
        rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
        rows = []
        for c in gm(rootc, "GetChildren") or []:
            c2 = swc.cast(c, "IComponent2")
            nm = str(gm(c2, "Name2"))
            b = gm(c2, "GetBox", False, False)
            if b is None:
                rows.append({"name": nm, "center": None})
                continue
            bb = [v * 1000.0 for v in list(b)]
            center = [(bb[0] + bb[3]) / 2, (bb[1] + bb[4]) / 2, (bb[2] + bb[5]) / 2]
            lk = link_of(nm, joints)
            pred = Ts[lk][:3, 3].tolist() if lk in Ts else None
            rows.append({"name": nm, "link": lk,
                         "center_mm": [round(v, 1) for v in center],
                         "fk_link_origin_mm": [round(v, 1) for v in pred] if pred else None,
                         "bbox_mm": [round(v, 1) for v in bb]})
        centers = np.array([r["center_mm"] for r in rows if r.get("center_mm")])
        med = np.median(centers, axis=0)
        for r in rows:
            if r.get("center_mm"):
                r["dist_from_median_mm"] = round(float(
                    np.linalg.norm(np.array(r["center_mm"]) - med)), 1)
            else:
                r["dist_from_median_mm"] = None
        rows.sort(key=lambda r: -(r["dist_from_median_mm"] or -1))
        rep["median_center_mm"] = [round(v, 1) for v in med.tolist()]
        rep["components_by_distance"] = rows
        rep["outliers"] = [r["name"] for r in rows
                           if (r["dist_from_median_mm"] or 0) > 300.0]
        rep["n_outliers"] = len(rep["outliers"])
        swc.activate_configuration(arm, blog, "默认")
        swc.close_document(app, arm, blog)
        rep["verdict"] = "OUTLIERS_%d" % rep["n_outliers"]
    except Exception as exc:
        import traceback
        rep["verdict"] = "DIAG_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1500:]
    finally:
        wd.stop()
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("verdict:", rep["verdict"], "outliers:", rep.get("outliers"))


if __name__ == "__main__":
    main()
