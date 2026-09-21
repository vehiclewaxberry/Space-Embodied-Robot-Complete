# -*- coding: utf-8 -*-
"""Read-only probe (NO SAVE): test whether re-asserting q0 component transforms
in the DEFAULT config (mates LIVE) snaps it back to as-built. If the readback
matches URDF FK(q0) to <1e-6 m, the P4 fix is 'write both configs'; otherwise
the arm copy must be regenerated from the donor. Nothing is saved either way.
"""
import json
import sys
import traceback

import math

import numpy as np

from f3r1_env import F3R1, JLog
import b3_lib.sw_core as swc
import sw_session as ss
import urdf_chain as uc
from p3_top_integration import mat_to_t16
from p4_stow_pose import make_transform, link_of, get_comp_objs, Q_STOW_DEG

log = JLog("diag_reassert")
NC = F3R1 / "03_native_cad"
ARM = NC / "B601_ARM_B51_COPY/assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"
OUT = F3R1 / "04_configurations" / "F3R1_DEFAULT_REASSERT_PROBE.json"


def main():
    rep = {"schema": "F3R1_DEFAULT_REASSERT_PROBE_V1"}
    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    blog = swc.BuildLog("reassert")
    gm = swc.get_com_member
    try:
        links, joints = uc.load_chain()
        # fk() takes a dict joint_name->value; q0 = empty dict (all zero)
        T0 = uc.fk(joints, {})
        qs = {j["name"]: math.radians(Q_STOW_DEG[i]) for i, j in enumerate(joints[:6])}
        Ts = uc.fk(joints, qs)

        app = ss.connect(log)
        arm = swc.open_document(app, blog, str(ARM))
        armasm = swc.cast(arm, "IAssemblyDoc")
        active0 = str(gm(arm, "ConfigurationManager").ActiveConfiguration.Name)
        rep["default_config"] = active0
        swc.activate_configuration(arm, blog, active0)
        arm.ForceRebuild3(True)

        # capture the CURRENT (corrupted) offsets are meaningless; instead we
        # recompute the target from FK(q0): each comp rides its link at q0, so
        # the target transform IS T0[link] @ offset_i. We need offset_i, which
        # is invariant. Recover it from the STOWED config (where pose is exact):
        swc.activate_configuration(arm, blog, "STOWED_O13V3")
        arm.ForceRebuild3(True)
        objs_s = get_comp_objs(arm)
        offsets = {}
        for nm, c2 in objs_s.items():
            lk = link_of(nm, joints)
            if lk is None:
                continue
            back = list(gm(gm(c2, "Transform2"), "ArrayData"))
            Tcomp = np.eye(4)
            Tcomp[:3, 0] = back[0:3]; Tcomp[:3, 1] = back[3:6]
            Tcomp[:3, 2] = back[6:9]
            Tcomp[:3, 3] = [back[9] * 1000, back[10] * 1000, back[11] * 1000]
            offsets[nm] = np.linalg.inv(Ts[lk]) @ Tcomp
        rep["offsets_recovered"] = len(offsets)

        # now re-assert q0 in default: write T0[link] @ offset_i for every comp
        swc.activate_configuration(arm, blog, active0)
        objs = get_comp_objs(arm)
        r0 = bool(armasm.EnableAssemblyRebuild)
        armasm.EnableAssemblyRebuild = False
        want_by = {}
        for nm, off in offsets.items():
            lk = link_of(nm, joints)
            want = mat_to_t16(T0[lk] @ off)
            c2 = objs.get(nm)
            if c2 is None:
                continue
            c2.SetTransformAndSolve3(make_transform(app, want), True)
            want_by[nm] = want
        armasm.EnableAssemblyRebuild = r0
        arm.ForceRebuild3(True)

        # verify default now matches FK(q0)
        objs_chk = get_comp_objs(arm)
        err = 0.0
        for nm, want in want_by.items():
            c2 = objs_chk.get(nm)
            back = list(gm(gm(c2, "Transform2"), "ArrayData"))
            d = float(np.abs(np.array(back[:12]) - np.array(want[:12])).max())
            err = max(err, d)
        rep["default_reassert_max_err_m"] = err
        log.ev("DEFAULT_REASSERT", max_err_m=err)
        rep["verdict"] = "REASSERT_CLEAN" if err < 1e-6 else "REASSERT_FAILED"
        swc.close_document(app, arm, blog)  # NO SAVE
    except Exception as exc:
        rep["verdict"] = "FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1800:]
    finally:
        wd.stop()
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("verdict:", rep["verdict"])
    print("default_reassert_max_err_m:", rep.get("default_reassert_max_err_m"))
    print("offsets_recovered:", rep.get("offsets_recovered"))
    if rep.get("error"):
        print("error:", rep["error"])


if __name__ == "__main__":
    main()
