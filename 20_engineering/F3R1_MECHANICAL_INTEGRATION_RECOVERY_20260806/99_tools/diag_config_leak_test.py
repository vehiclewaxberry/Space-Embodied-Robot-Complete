# -*- coding: utf-8 -*-
"""DECISIVE in-memory probe (NO SAVE): does a stow-config transform write leak
into the default config when only the stow config's mates are suppressed?

The recopied arm has ONE config (default) whose as-built pose is held by 25
live mates (13 MateLock + 6 concentric + 6 coincident). Stow must be authored
by transform with those mates suppressed. The open question is whether SW keeps
component POSITIONS config-specific (so default, mates resolved, is untouched)
or shares one position store (so stow writes corrupt default -- the P4 defect).

Procedure, all in memory, file CLOSED WITHOUT SAVE, hash verified unchanged:
  1. record default component transforms (baseline)
  2. add STOWED_TEST config (donor flags), activate it
  3. suppress ITS mates only (ConfigOption=ThisConfiguration), write stow
     transforms, ForceRebuild3, record stow readback
  4. reactivate default, ForceRebuild3
  5. compare default components to baseline  -> LEAK if drift is large
  6. reactivate stow, confirm it still holds stow
  7. close WITHOUT save; check_protected proves the donor + copy are intact
This never saves, so it is safe to run against the working copy.
"""
import json
import math
import sys

import numpy as np

from f3r1_env import F3R1, JLog, check_protected, sha256_file
import b3_lib.sw_core as swc
import sw_session as ss
import urdf_chain as uc
from p3_top_integration import mat_to_t16
from p4_stow_pose import (make_transform, set_all_mates_suppressed,
                          get_comp_objs, arm_components, link_of, t16_to_mat,
                          Q_STOW_DEG)

log = JLog("diag_config_leak")
NC = F3R1 / "03_native_cad"
ARM = NC / "B601_ARM_B51_COPY/assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"
OUT = F3R1 / "04_configurations" / "F3R1_CONFIG_LEAK_TEST.json"
gm = swc.get_com_member


def comp_t16(model):
    objs = get_comp_objs(model)
    out = {}
    for nm, c2 in objs.items():
        t = gm(c2, "Transform2")
        if t is not None:
            out[nm] = list(gm(t, "ArrayData"))
    return out


def max_drift(a, b):
    d = 0.0
    for nm in a:
        if nm in b:
            d = max(d, float(np.abs(np.array(a[nm][:12]) -
                                   np.array(b[nm][:12])).max()))
    return d


def main():
    check_protected("LEAK_PRE")
    sha0 = sha256_file(ARM)
    rep = {"schema": "F3R1_CONFIG_LEAK_TEST_V1", "arm_sha_pre": sha0}
    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    blog = swc.BuildLog("leak")
    try:
        app = ss.connect(log)
        links, joints = uc.load_chain()
        qs = {j["name"]: math.radians(Q_STOW_DEG[i])
              for i, j in enumerate(joints[:6])}
        T0 = uc.fk(joints, {})
        Ts = uc.fk(joints, qs)

        arm = swc.open_document(app, blog, str(ARM))
        cm = gm(arm, "ConfigurationManager")
        default = str(cm.ActiveConfiguration.Name)
        rep["default_config"] = default

        # offsets from as-built default (mates resolved)
        comps0 = arm_components(arm)
        offsets = {}
        for nm, c in comps0.items():
            lk = link_of(nm, joints)
            if lk is None or not c.get("transform16"):
                continue
            offsets[nm] = np.linalg.inv(T0[lk]) @ t16_to_mat(c["transform16"])
        rep["offsets"] = len(offsets)

        baseline = comp_t16(arm)          # default pose, before any write

        newconf = "STOWED_TEST"
        if cm.AddConfiguration2(newconf, "leak probe", "", 0, "", False,
                                False) is None:
            raise RuntimeError("AddConfiguration2 failed")
        swc.activate_configuration(arm, blog, newconf)
        set_all_mates_suppressed(arm, log, True)

        armasm = swc.cast(arm, "IAssemblyDoc")
        objs = get_comp_objs(arm)
        rb0 = bool(armasm.EnableAssemblyRebuild)
        want_by = {}
        try:
            armasm.EnableAssemblyRebuild = False
            for nm, off in offsets.items():
                lk = link_of(nm, joints)
                want = mat_to_t16(Ts[lk] @ off)
                c2 = objs.get(nm)
                if c2 is None:
                    continue
                c2.SetTransformAndSolve3(make_transform(app, want), True)
                want_by[nm] = want
        finally:
            armasm.EnableAssemblyRebuild = rb0
        arm.ForceRebuild3(True)

        stow_after = comp_t16(arm)
        stow_err = max_drift(stow_after, want_by)
        rep["stow_write_max_err_m"] = stow_err

        # reactivate default, rebuild, compare to baseline
        swc.activate_configuration(arm, blog, default)
        arm.ForceRebuild3(True)
        default_after = comp_t16(arm)
        leak = max_drift(default_after, baseline)
        rep["default_drift_after_stow_write_m"] = leak
        rep["LEAK"] = leak > 1e-6

        # confirm stow still holds its pose
        swc.activate_configuration(arm, blog, newconf)
        arm.ForceRebuild3(True)
        stow_recheck = max_drift(comp_t16(arm), want_by)
        rep["stow_recheck_max_err_m"] = stow_recheck

        rep["verdict"] = ("CONFIG_SPECIFIC_POSITIONS_OK" if not rep["LEAK"]
                          else "POSITIONS_SHARED_STOW_CORRUPTS_DEFAULT")
        swc.close_document(app, arm, blog)   # NO SAVE
    except Exception as exc:
        import traceback
        rep["verdict"] = "FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1600:]
    finally:
        wd.stop()

    rep["arm_sha_post"] = sha256_file(ARM)
    rep["arm_unchanged"] = (rep["arm_sha_post"] == sha0)
    check_protected("LEAK_POST")
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print("verdict:", rep["verdict"])
    print("  stow_write_err_m:", rep.get("stow_write_max_err_m"))
    print("  default_drift_m :", rep.get("default_drift_after_stow_write_m"))
    print("  stow_recheck_m  :", rep.get("stow_recheck_max_err_m"))
    print("  arm_unchanged   :", rep.get("arm_unchanged"))
    if rep["verdict"] == "FAIL":
        print(rep.get("traceback"))


if __name__ == "__main__":
    main()
