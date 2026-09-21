# -*- coding: utf-8 -*-
"""P3 (G3): create F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION.SLDASM.

Contents: spacecraft copy (identity, fixed) + B601 arm copy (measured mount
transform: boss outer face, URDF +Z -> world +X, 25 deg human-ratified clock
about the mount axis) + wing panels L/R (STOWED + DEPLOYED donor parts,
identity, fixed). Everything saved ONLY under F3R1.

Mount station facts are MEASURED from the copied geometry (never assumed):
Central_Boss / Adapter_Plate assembly-space bounding boxes are recorded and
compared against the two historical tracks (P5C T_SM=185.25 Mode B; display
track adapter_outer_face_x=198). Any mismatch is registered, not silently
"fixed".
"""
import json
import math
import sys
import traceback

import numpy as np
import pythoncom
from win32com.client import VARIANT

from f3r1_env import F3R1, JLog, check_protected, sha256_file
import b3_lib.sw_core as swc
import sw_session as ss


def _typed_transform(app, t16):
    """IMathUtility.CreateTransform from a VARIANT(VT_ARRAY|VT_R8) SAFEARRAY,
    readback-verified. A raw Python list silently yields a WRONG transform for
    non-identity matrices (the mount has a 25 deg clock + X offset), so the
    arm would insert mis-posed; only the identity path ever worked by luck."""
    gm = swc.get_com_member
    data = [float(v) for v in t16]
    typed = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, data)
    mu = swc.cast(gm(app, "GetMathUtility"), "IMathUtility")
    xf = mu.CreateTransform(typed)
    if xf is None:
        raise RuntimeError("CreateTransform returned None")
    back = [float(v) for v in gm(xf, "ArrayData")]
    if max(abs(a - b) for a, b in zip(back, data)) > 1e-12:
        raise RuntimeError("CreateTransform SAFEARRAY readback mismatch")
    return xf

log = JLog("p3_top_integration")
NC = F3R1 / "03_native_cad"
SC_TOP = NC / "SPACECRAFT_V2_2_NATIVE_COPY/Assembly/Space_Embodied_Service_Spacecraft_V2_2.SLDASM"
ARM = NC / "B601_ARM_B51_COPY/assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"
WINGS = [NC / "WING_PANEL_DONORS" / n for n in
         ("WING_L_STOWED.SLDPRT", "WING_R_STOWED.SLDPRT",
          "WING_L_DEPLOYED.SLDPRT", "WING_R_DEPLOYED.SLDPRT")]
TOP = NC / "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION.SLDASM"
OUT = F3R1 / "03_native_cad" / "F3R1_TOP_INTEGRATION_REPORT.json"

CLOCK_DEG = 25.0  # human-ratified (O11/O13); sign candidates tested in P4


def mat_to_t16(T):
    """4x4 (mm) -> SolidWorks ArrayData 16 (m)."""
    R = T[:3, :3]
    return [R[0, 0], R[1, 0], R[2, 0],
            R[0, 1], R[1, 1], R[2, 1],
            R[0, 2], R[1, 2], R[2, 2],
            T[0, 3] / 1000.0, T[1, 3] / 1000.0, T[2, 3] / 1000.0,
            1.0, 0.0, 0.0, 0.0]


def mount_transform(x_face_mm, clock_deg):
    """URDF base frame -> world: +Z_urdf -> +X_world, clock about world X."""
    Ry90 = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], dtype=float)
    c, s = math.cos(math.radians(clock_deg)), math.sin(math.radians(clock_deg))
    Rx = np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=float)
    T = np.eye(4)
    T[:3, :3] = Rx @ Ry90
    T[:3, 3] = [x_face_mm, 0.0, 0.0]
    return T


def comp_box(c2):
    """assembly-space bbox of a component, mm."""
    box = swc.get_com_member(c2, "GetBox", False, False)
    if box is None:
        return None
    return [v * 1000.0 for v in list(box)]


def find_comp(comps_raw, predicate):
    """Nested Name2 is 'parent-1/child-1'; match on the leaf segment."""
    for c in comps_raw:
        c2 = swc.cast(c, "IComponent2")
        leaf = str(swc.get_com_member(c2, "Name2")).split("/")[-1]
        if predicate(leaf):
            return c2
        kids = swc.get_com_member(c2, "GetChildren")
        got = find_comp(kids or [], predicate)
        if got is not None:
            return got
    return None


def main():
    check_protected("P3_PRE")
    rep = {"schema": "F3R1_TOP_INTEGRATION_V1", "clock_deg": CLOCK_DEG}
    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    blog = swc.BuildLog("p3_top")
    try:
        app = ss.connect(log)

        # ---- measure mount interfaces on the spacecraft copy ----
        sc = swc.open_document(app, blog, str(SC_TOP))
        conf = swc.get_com_member(sc, "ConfigurationManager").ActiveConfiguration
        rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
        kids = swc.get_com_member(rootc, "GetChildren")

        boss = find_comp(kids, lambda n: n.startswith("Central_Boss"))
        adapter = find_comp(kids, lambda n: n.startswith("Adapter_Plate"))
        g07 = find_comp(kids, lambda n: n.startswith("Aft_Saddle"))
        g08 = find_comp(kids, lambda n: n.startswith("Fwd_Saddle"))
        mid = find_comp(kids, lambda n: n.startswith("Mid_Saddle"))
        meas = {}
        for tag, comp in [("Central_Boss", boss), ("Adapter_Plate", adapter),
                          ("Aft_Saddle_G07", g07), ("Fwd_Saddle_G08", g08),
                          ("Mid_Saddle", mid)]:
            meas[tag] = comp_box(comp) if comp is not None else None
        rep["measured_boxes_mm"] = meas
        if not meas.get("Central_Boss"):
            raise RuntimeError("Central_Boss not found in spacecraft copy")
        x_face = max(meas["Central_Boss"][0], meas["Central_Boss"][3])
        rep["mount_station"] = {
            "boss_outer_face_x_mm": x_face,
            "adapter_outer_face_x_mm": (max(meas["Adapter_Plate"][0], meas["Adapter_Plate"][3])
                                        if meas.get("Adapter_Plate") else None),
            "p5c_t_sm_mode_b_mm": 185.25,
            "display_track_adapter_x_mm": 198.0,
        }
        log.ev("MOUNT_MEASURED", **rep["mount_station"])
        swc.close_document(app, sc, blog)

        # ---- create the new top assembly (idempotent: a prior F3R1 candidate
        # is a rebuildable output, not evidence -- clear it and its swap lock so
        # re-runs after a mid-build memory-dialog stall start clean) ----
        for stale in (TOP, TOP.with_name("~$" + TOP.name)):
            if stale.exists():
                stale.unlink()
                log.ev("STALE_CANDIDATE_REMOVED", path=str(stale))
        top = swc.new_document(app, blog, "assembly")
        swc.save_as(top, blog, TOP)

        # spacecraft at identity (fixed)
        swc.insert_components_identity(app, blog, top, [str(SC_TOP)])

        # wings at identity (they are modeled in global spacecraft coordinates)
        swc.insert_components_identity(app, blog, top, [str(w) for w in WINGS])

        # arm at measured mount transform
        Tm = mount_transform(x_face, CLOCK_DEG)
        rep["arm_mount_transform_mm"] = Tm.tolist()
        asm = swc.cast(top, "IAssemblyDoc")
        swc.open_document(app, blog, str(ARM), read_only=True)
        title = swc.get_com_member(top, "GetTitle")
        try:
            app.ActivateDoc3(title, False, 0, 0)
        except TypeError:
            app.ActivateDoc3(title, False, 0, swc.byref_i4())
        armc = asm.AddComponent5(str(ARM), 0, "", False, "", 0.0, 0.0, 0.0)
        if armc is None:
            raise RuntimeError("AddComponent5(arm) failed")
        armc2 = swc.cast(armc, "IComponent2")
        want_mount = mat_to_t16(Tm)
        xf = _typed_transform(app, want_mount)
        armc2.SetTransformAndSolve3(xf, True)
        app.CloseDoc(ARM.name)
        # verify the mount landed before fixing (fail-closed): a mis-posed
        # insert would otherwise be frozen into the assembly.
        back = list(swc.get_com_member(swc.get_com_member(armc2, "Transform2"),
                                       "ArrayData"))
        mount_err = float(np.abs(np.array(back[:12]) -
                                 np.array(want_mount[:12])).max())
        rep["arm_mount_insert_err_m"] = mount_err
        log.ev("ARM_MOUNT_INSERTED", max_err_m=mount_err)
        if mount_err > 1e-9:
            raise RuntimeError("arm mount insert readback drift %g m" % mount_err)
        top.ClearSelection2(True)
        armc2.Select4(True, None, False)
        asm.FixComponent()
        top.ClearSelection2(True)
        swc.rebuild_or_fail(top, blog, "top_after_arm")
        swc.save(top, blog)

        comps = ss.components_of(top, top_only=True)
        rep["top_components"] = [{k: c[k] for k in ("name", "path", "suppressed")}
                                 for c in comps]
        # wing bbox sanity (stowed should sit near |Y| 113..119)
        conf2 = swc.get_com_member(top, "ConfigurationManager").ActiveConfiguration
        root2 = swc.cast(conf2.GetRootComponent3(True), "IComponent2")
        kids2 = swc.get_com_member(root2, "GetChildren")
        wing_boxes = {}
        for c in kids2 or []:
            c2 = swc.cast(c, "IComponent2")
            nm = str(swc.get_com_member(c2, "Name2"))
            if nm.startswith("WING_"):
                wing_boxes[nm] = comp_box(c2)
        rep["wing_boxes_mm"] = wing_boxes

        arm_box = None
        for c in kids2 or []:
            c2 = swc.cast(c, "IComponent2")
            nm = str(swc.get_com_member(c2, "Name2"))
            if nm.startswith("B51_B601"):
                arm_box = comp_box(c2)
        rep["arm_box_mm_q0_mounted"] = arm_box

        swc.close_document(app, top, blog)

        # cold reopen
        top2 = swc.open_document(app, blog, str(TOP))
        comps2 = ss.components_of(top2, top_only=True)
        t2, e2 = ss.mate_status(top2)
        rep["cold_reopen"] = {"top_components": len(comps2), "mates": t2,
                              "mate_errors": e2,
                              "paths_ok": all(str(F3R1).lower() in c["path"].lower()
                                              for c in comps2 if c["path"])}
        swc.close_document(app, top2, blog)
        rep["top_sha256"] = sha256_file(TOP)
        rep["verdict"] = ("G3_TOP_CREATED" if rep["cold_reopen"]["paths_ok"]
                          and rep["cold_reopen"]["top_components"] == 6
                          else "G3_CHECK")
    except Exception as exc:
        rep["verdict"] = "G3_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]
        log.ev("P3_FAIL", error=str(exc))
    finally:
        wd.stop()
        rep["watchdog"] = {"memory_dialogs_dismissed": wd.dismissed,
                           "other_dialogs_logged": wd.seen_other}

    check_protected("P3_POST")
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("verdict:", rep["verdict"])
    sys.exit(0 if rep["verdict"].startswith("G3_TOP") else 1)


if __name__ == "__main__":
    main()
