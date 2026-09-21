# -*- coding: utf-8 -*-
"""Diagnose the 3 floating arm parts in STOWED_O13V3.

Read-only on the arm copy: list every leaf component, its link_of() mapping,
whether an offset was captured for it, and its q0 vs stow bbox. Flags any
component that link_of() could NOT classify (-> not reposed -> floats).
"""
import json
import math
import sys

import numpy as np

from f3r1_env import F3R1, JLog
import b3_lib.sw_core as swc
import sw_session as ss
import urdf_chain as uc
from p4_stow_pose import link_of, COMP_LINK, t16_to_mat

log = JLog("diag_arm_stow")
NC = F3R1 / "03_native_cad"
ARM = NC / "B601_ARM_B51_COPY/assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"
OUT = F3R1 / "04_configurations" / "F3R1_ARM_STOW_DIAG.json"


def main():
    rep = {"schema": "F3R1_ARM_STOW_DIAG_V1"}
    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    blog = swc.BuildLog("diag")
    gm = swc.get_com_member
    try:
        app = ss.connect(log)
        links, joints = uc.load_chain()
        arm = swc.open_document(app, blog, str(ARM))
        comps = ss.components_of(arm)  # all leaves, active config
        rows = []
        unclassified = []
        for c in comps:
            nm = c["name"]
            lk = link_of(nm, joints)
            base = nm.split("-")[0]
            row = {"name": nm, "base": base, "link": lk,
                   "has_xf": bool(c.get("transform16")),
                   "in_COMP_LINK": base in COMP_LINK,
                   "is_datum": base.startswith("B51_REV_DATUM_")}
            if c.get("transform16"):
                T = t16_to_mat(c["transform16"])
                row["origin_mm"] = [round(float(v), 2) for v in T[:3, 3]]
            if lk is None:
                unclassified.append(nm)
            rows.append(row)
        rep["n_components"] = len(comps)
        rep["components"] = rows
        rep["unclassified_names"] = unclassified
        rep["n_unclassified"] = len(unclassified)
        rep["comp_link_keys"] = sorted(COMP_LINK.keys())
        rep["verdict"] = ("ALL_CLASSIFIED" if not unclassified
                          else "UNCLASSIFIED_%d" % len(unclassified))
        swc.close_document(app, arm, blog)
    except Exception as exc:
        import traceback
        rep["verdict"] = "DIAG_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1500:]
    finally:
        wd.stop()
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("verdict:", rep["verdict"], "unclassified:", rep.get("n_unclassified"))


if __name__ == "__main__":
    main()
