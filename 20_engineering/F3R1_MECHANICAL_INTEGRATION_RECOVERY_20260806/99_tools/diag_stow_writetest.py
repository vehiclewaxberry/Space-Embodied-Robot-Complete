# -*- coding: utf-8 -*-
"""Read-only probe (NO SAVE): in STOWED_O13V3, report IsFixed for all 20 arm
components, then test whether one Transform2 write sticks (a) as-is and
(b) after UnfixComponent. Roots the 1.978 m no-op: fixed-state or something else.
"""
import json
import sys
import traceback

import numpy as np

from f3r1_env import F3R1, JLog
import b3_lib.sw_core as swc
import sw_session as ss
import urdf_chain as uc
from p3_top_integration import mat_to_t16

log = JLog("diag_writetest")
NC = F3R1 / "03_native_cad"
ARM = NC / "B601_ARM_B51_COPY/assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"
OUT = F3R1 / "04_configurations" / "F3R1_STOW_WRITETEST.json"


def comp_objs(model):
    gm = swc.get_com_member
    conf = gm(model, "ConfigurationManager").ActiveConfiguration
    rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
    out = {}
    for c in gm(rootc, "GetChildren") or []:
        c2 = swc.cast(c, "IComponent2")
        out[str(gm(c2, "Name2"))] = c2
    return out


def arr(gm, c2):
    return list(gm(gm(c2, "Transform2"), "ArrayData"))[:12]


def main():
    rep = {"schema": "F3R1_STOW_WRITETEST_V1"}
    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    blog = swc.BuildLog("writetest")
    gm = swc.get_com_member
    try:
        app = ss.connect(log)
        arm = swc.open_document(app, blog, str(ARM))
        asm = swc.cast(arm, "IAssemblyDoc")
        # activate the stow config that P4 created
        names = list(gm(arm, "GetConfigurationNames") or [])
        rep["configs"] = names
        swc.activate_configuration(arm, blog, "STOWED_O13V3")

        objs = comp_objs(arm)
        rep["fixed_state"] = {nm: bool(gm(c2, "IsFixed")) for nm, c2 in objs.items()}
        rep["n_fixed"] = sum(1 for v in rep["fixed_state"].values() if v)

        # pick link1 as the probe; write a +100mm X translation of its current pose
        probe = "B51_REF_link1_LINKLOCAL-1"
        c2 = objs[probe]
        mu = swc.cast(gm(app, "GetMathUtility"), "IMathUtility")
        cur = np.array(arr(gm, c2))
        want = cur.copy()
        want[9] += 0.1  # +100 mm in X (ArrayData[9]=tx, meters)

        # (a) write as-is (no unfix), rebuild suspended
        r0 = bool(asm.EnableAssemblyRebuild)
        asm.EnableAssemblyRebuild = False
        c2.Transform2 = mu.CreateTransform(list(want) + [0, 0, 0, 1.0])
        imm_a = np.abs(np.array(arr(gm, c2)) - want).max()
        asm.EnableAssemblyRebuild = r0
        arm.ForceRebuild3(True)
        post_a = np.abs(np.array(arr(gm, comp_objs(arm)[probe])) - want).max()
        rep["write_as_is"] = {"fixed": rep["fixed_state"][probe],
                              "immediate_err": float(imm_a),
                              "post_rebuild_err": float(post_a)}
        log.ev("WRITE_AS_IS", immediate=float(imm_a), post=float(post_a))

        # (b) unfix then write
        objs = comp_objs(arm)
        c2 = objs[probe]
        arm.ClearSelection2(True)
        c2.Select4(False, None, False)
        if bool(gm(c2, "IsFixed")):
            asm.UnfixComponent()
        arm.ClearSelection2(True)
        now_fixed = bool(gm(c2, "IsFixed"))
        cur = np.array(arr(gm, c2))
        want = cur.copy(); want[9] += 0.1
        r0 = bool(asm.EnableAssemblyRebuild)
        asm.EnableAssemblyRebuild = False
        c2.Transform2 = mu.CreateTransform(list(want) + [0, 0, 0, 1.0])
        imm_b = np.abs(np.array(arr(gm, c2)) - want).max()
        asm.EnableAssemblyRebuild = r0
        arm.ForceRebuild3(True)
        post_b = np.abs(np.array(arr(gm, comp_objs(arm)[probe])) - want).max()
        rep["write_after_unfix"] = {"fixed_after_unfix": now_fixed,
                                    "immediate_err": float(imm_b),
                                    "post_rebuild_err": float(post_b)}
        log.ev("WRITE_AFTER_UNFIX", immediate=float(imm_b), post=float(post_b))

        rep["verdict"] = "WRITETEST_DONE"
        swc.close_document(app, arm, blog)  # NO SAVE
    except Exception as exc:
        rep["verdict"] = "FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1500:]
    finally:
        wd.stop()
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("verdict:", rep["verdict"])
    print("n_fixed:", rep.get("n_fixed"))
    print("as_is:", rep.get("write_as_is"))
    print("after_unfix:", rep.get("write_after_unfix"))


if __name__ == "__main__":
    main()
