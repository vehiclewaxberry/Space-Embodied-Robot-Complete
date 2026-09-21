# -*- coding: utf-8 -*-
"""Read-only (NO SAVE): for each config in the arm copy, force a full rebuild
and report (a) per-config mate suppression counts, (b) base-relative spread of
the 20 components. Distinguishes 'default mates leaked to suppressed' (needs
re-copy) from 'default left mid-solve, clean rebuild restores it' (fixable)."""
import json
import sys
import traceback

import numpy as np

from f3r1_env import F3R1, JLog
import b3_lib.sw_core as swc
import sw_session as ss

log = JLog("diag_confhealth")
NC = F3R1 / "03_native_cad"
ARM = NC / "B601_ARM_B51_COPY/assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"
OUT = F3R1 / "04_configurations" / "F3R1_CONFIG_HEALTH.json"


def mate_supp_counts(model):
    gm = swc.get_com_member
    feat = gm(model, "FirstFeature")
    total = supp = 0
    while feat is not None:
        f = swc.cast(feat, "IFeature")
        if str(gm(f, "GetTypeName2")) == "MateGroup":
            sub = gm(f, "GetFirstSubFeature")
            while sub is not None:
                s = swc.cast(sub, "IFeature")
                total += 1
                if bool(gm(s, "IsSuppressed")):
                    supp += 1
                sub = gm(s, "GetNextSubFeature")
        feat = gm(f, "GetNextFeature")
    return total, supp


def comp_centers(model):
    gm = swc.get_com_member
    conf = gm(model, "ConfigurationManager").ActiveConfiguration
    rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
    out = {}
    for c in gm(rootc, "GetChildren") or []:
        c2 = swc.cast(c, "IComponent2")
        b = gm(c2, "GetBox", False, False)
        if b is not None:
            bb = [v * 1000.0 for v in list(b)]
            out[str(gm(c2, "Name2"))] = [(bb[0] + bb[3]) / 2,
                                         (bb[1] + bb[4]) / 2,
                                         (bb[2] + bb[5]) / 2]
    return out


def main():
    rep = {"schema": "F3R1_CONFIG_HEALTH_V1"}
    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    blog = swc.BuildLog("confhealth")
    gm = swc.get_com_member
    try:
        app = ss.connect(log)
        arm = swc.open_document(app, blog, str(ARM))
        names = list(gm(arm, "GetConfigurationNames") or [])
        rep["configs"] = names
        rep["stored_active"] = str(gm(arm, "ConfigurationManager").ActiveConfiguration.Name)
        per = {}
        for cfg in names:
            swc.activate_configuration(arm, blog, cfg)
            arm.ForceRebuild3(True)
            total, supp = mate_supp_counts(arm)
            centers = comp_centers(arm)
            arr = np.array(list(centers.values()))
            span = float(np.abs(arr - arr.mean(axis=0)).max()) if len(arr) else None
            zrange = [float(arr[:, 2].min()), float(arr[:, 2].max())] if len(arr) else None
            per[cfg] = {"mates_total": total, "mates_suppressed": supp,
                        "n_components": len(centers), "center_span_mm": span,
                        "z_range_mm": zrange}
            log.ev("CONFIG_HEALTH", cfg=cfg, mates_total=total,
                   mates_suppressed=supp, span=span)
        rep["per_config"] = per
        rep["verdict"] = "HEALTH_DUMPED"
        swc.close_document(app, arm, blog)  # NO SAVE
    except Exception as exc:
        rep["verdict"] = "FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1500:]
    finally:
        wd.stop()
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("verdict:", rep["verdict"])
    print(json.dumps(rep.get("per_config", {}), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
