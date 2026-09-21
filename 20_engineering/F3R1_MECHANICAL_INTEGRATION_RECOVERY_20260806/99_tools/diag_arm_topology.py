# -*- coding: utf-8 -*-
"""Read-only: dump the arm donor's fixed-state + mate topology so we pick the
right stow-posing method (suppress mates vs per-component FixComponent)."""
import json
import sys

from f3r1_env import F3R1, JLog
import b3_lib.sw_core as swc
import sw_session as ss

import numpy as np

log = JLog("diag_topology")
NC = F3R1 / "03_native_cad"
ARM = NC / "B601_ARM_B51_COPY/assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"
OUT = F3R1 / "04_configurations" / "F3R1_ARM_TOPOLOGY.json"


def config_span(gm, arm):
    conf = gm(arm, "ConfigurationManager").ActiveConfiguration
    rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
    pts = []
    for c in gm(rootc, "GetChildren") or []:
        c2 = swc.cast(c, "IComponent2")
        b = gm(c2, "GetBox", False, False)
        if b is not None:
            pts.append([v * 1000.0 for v in list(b)])
    if not pts:
        return {"components": 0}
    a = np.array(pts)
    return {"components": len(pts),
            "x_mm": [float(a[:, 0].min()), float(a[:, 3].max())],
            "y_mm": [float(a[:, 1].min()), float(a[:, 4].max())],
            "z_mm": [float(a[:, 2].min()), float(a[:, 5].max())]}


def main():
    rep = {"schema": "F3R1_ARM_TOPOLOGY_V1"}
    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    blog = swc.BuildLog("topo")
    gm = swc.get_com_member
    try:
        app = ss.connect(log)
        arm = swc.open_document(app, blog, str(ARM))
        conf = gm(arm, "ConfigurationManager").ActiveConfiguration
        rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
        comps = []
        for c in gm(rootc, "GetChildren") or []:
            c2 = swc.cast(c, "IComponent2")
            comps.append({"name": str(gm(c2, "Name2")),
                          "fixed": bool(gm(c2, "IsFixed")),
                          "suppressed": bool(gm(c2, "IsSuppressed"))})
        rep["components"] = comps
        rep["n_fixed"] = sum(1 for c in comps if c["fixed"])
        rep["n_float"] = sum(1 for c in comps if not c["fixed"])

        # enumerate mates
        mates = []
        feat = gm(arm, "FirstFeature")
        while feat is not None:
            f = swc.cast(feat, "IFeature")
            if str(gm(f, "GetTypeName2")) == "MateGroup":
                sub = gm(f, "GetFirstSubFeature")
                while sub is not None:
                    s = swc.cast(sub, "IFeature")
                    mates.append({"name": str(gm(s, "Name")),
                                  "type": str(gm(s, "GetTypeName2")),
                                  "suppressed": bool(gm(s, "IsSuppressed"))})
                    sub = gm(s, "GetNextSubFeature")
            feat = gm(f, "GetNextFeature")
        rep["mates"] = mates
        rep["n_mates"] = len(mates)
        mtypes = {}
        for m in mates:
            mtypes[m["type"]] = mtypes.get(m["type"], 0) + 1
        rep["mate_types"] = mtypes

        # configs + per-config span (read-only; restore active, never save)
        cm = gm(arm, "ConfigurationManager")
        active0 = str(cm.ActiveConfiguration.Name)
        rep["active_config"] = active0
        rep["configs"] = list(gm(arm, "GetConfigurationNames") or [])
        spans = {}
        for cn in rep["configs"]:
            swc.activate_configuration(arm, blog, cn)
            arm.ForceRebuild3(True)
            spans[cn] = config_span(gm, arm)
        rep["config_spans"] = spans
        swc.activate_configuration(arm, blog, active0)

        rep["verdict"] = "TOPOLOGY_DUMPED"
        swc.close_document(app, arm, blog)
    except Exception as exc:
        import traceback
        rep["verdict"] = "FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1500:]
    finally:
        wd.stop()
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("verdict:", rep["verdict"], "fixed:", rep.get("n_fixed"),
          "float:", rep.get("n_float"), "mates:", rep.get("n_mates"))
    print("active:", rep.get("active_config"), "configs:", rep.get("configs"))
    print("mate_types:", rep.get("mate_types"))
    for cn, sp in (rep.get("config_spans") or {}).items():
        print("  span[%s]:" % cn, sp)


if __name__ == "__main__":
    main()
