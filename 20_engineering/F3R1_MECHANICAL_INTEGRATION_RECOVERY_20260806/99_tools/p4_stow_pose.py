# -*- coding: utf-8 -*-
"""P4: write the O13-v3 stow pose into the arm copy as configuration
STOWED_O13V3, wire top-level configurations, and land the arm on the saddles.

Method (proven in the B51 build trace): compute URDF FK at q_stow, then set
every component's Transform2 to T_link(q_stow) @ offset_i, where
offset_i = inv(T_link(q0)) @ T_comp(q0) captured from the as-built pose.
Datum parts ride their joint's parent (FEMALE) / child (MALE) link.

Mount-sign selection: the mount maps URDF +Z -> world +X with a 25 deg clock
about world X (human-ratified magnitude; SIGN is selected by measurement).
Both signs are scored against the frozen saddle windows; scores are recorded
and the better one is kept. This selects between two writings of the SAME
ratified intent -- it does not tune geometry to pass.
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
import urdf_chain as uc
from p3_top_integration import mat_to_t16, mount_transform


def make_transform(app, t16):
    """IMathUtility.CreateTransform from a 16-float row, wrapped as a typed
    SAFEARRAY (VT_ARRAY|VT_R8) and readback-verified -- the donor primitive
    (b51 _math_transform). A raw Python list silently yields a wrong transform
    for non-identity matrices (P4 v1-v3 root cause: 1.98 m no-op), which is why
    the shared swc IDENT16 path only ever worked for identity inserts."""
    gm = swc.get_com_member
    data = [float(v) for v in t16]
    typed = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, data)
    mu = swc.cast(gm(app, "GetMathUtility"), "IMathUtility")
    xf = mu.CreateTransform(typed)
    if xf is None:
        raise RuntimeError("CreateTransform returned None")
    back = [float(v) for v in gm(xf, "ArrayData")]
    err = max(abs(a - b) for a, b in zip(back, data))
    if err > 1e-12:
        raise RuntimeError("CreateTransform SAFEARRAY readback mismatch: %g" % err)
    return xf

log = JLog("p4_stow_pose")
NC = F3R1 / "03_native_cad"
ARM = NC / "B601_ARM_B51_COPY/assembly/B51_B601_ARTICULATED_ENGINEERING_ARM.SLDASM"
TOP = NC / "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION.SLDASM"
OUT = F3R1 / "04_configurations" / "F3R1_STOW_POSE_REPORT.json"

Q_STOW_DEG = [145.572, -168.0, -57.0, -41.143, -20.954, -3.0]  # O13 v3, PROVISIONAL
SADDLES = {"G07": {"x": (-20.0, 0.0), "top_z": 261.08},
           "MID": {"x": (80.0, 100.0), "top_z": 214.92},
           "G08": {"x": (160.0, 180.0), "top_z": 209.42}}

COMP_LINK = {
    "B51_REF_base_link_LINKLOCAL": "base_link",
    "B51_REF_link1_LINKLOCAL": "link1", "B51_REF_link2_LINKLOCAL": "link2",
    "B51_REF_link3_LINKLOCAL": "link3", "B51_REF_link4_LINKLOCAL": "link4",
    "B51_REF_link5_LINKLOCAL": "link5", "B51_REF_link6_LINKLOCAL": "link6",
    "B51_REF_gripper_detail_LINKLOCAL": "gripper_link",
}


def t16_to_mat(t16):
    r = np.array(t16[:9], dtype=float).reshape(3, 3).T
    t = np.array(t16[9:12], dtype=float) * 1000.0
    T = np.eye(4)
    T[:3, :3] = r
    T[:3, 3] = t
    return T


def _float_component(model, asm, comp):
    """Ground -> free so Transform2 writes take effect (B5.0 proven pattern);
    a FIXED component silently swallows Transform2, which is the P4 v1 bug."""
    gm = swc.get_com_member
    model.ClearSelection2(True)
    comp.Select4(False, None, False)
    if bool(gm(comp, "IsFixed")):
        asm.UnfixComponent()
    model.ClearSelection2(True)
    return not bool(gm(comp, "IsFixed"))


def _refix_component(model, asm, comp):
    gm = swc.get_com_member
    model.ClearSelection2(True)
    comp.Select4(False, None, False)
    asm.FixComponent()
    model.ClearSelection2(True)
    return bool(gm(comp, "IsFixed"))


def _iter_mate_features(model):
    """Yield each mate IFeature under the MateGroup(s)."""
    gm = swc.get_com_member
    feat = gm(model, "FirstFeature")
    while feat is not None:
        f = swc.cast(feat, "IFeature")
        if str(gm(f, "GetTypeName2")) == "MateGroup":
            sub = gm(f, "GetFirstSubFeature")
            while sub is not None:
                s = swc.cast(sub, "IFeature")
                yield s
                sub = gm(s, "GetNextSubFeature")
        feat = gm(f, "GetNextFeature")


def set_all_mates_suppressed(model, log, suppress):
    """Suppress/unsuppress every mate IN THE ACTIVE CONFIG ONLY, fail-closed.

    The B51 donor holds its 19 links with 25 mates (13 MateLock + 6 concentric
    + 6 coincident) locked at the AS-BUILT pose. Writing a stow Transform2 with
    those active makes SolidWorks re-solve and fling the wrist (P4 v1 bug: link5+
    parts to Z=-997). Posing by transform requires the mates suppressed in this
    configuration; the default config keeps them, preserving the as-built pose.

    IFeature.SetSuppression2(State, ConfigOption, Names):
      State      0=swSuppressFeature, 1=swUnSuppressFeature
      ConfigOpt  1=swThisConfiguration (2=AllConfigurations -- NEVER here,
                 that would mutate the frozen as-built/deployed configs)
    Every mate's IsSuppressed is read back and MUST match the request; any
    mismatch raises (the pose would silently re-solve otherwise).
    """
    gm = swc.get_com_member
    state = 0 if suppress else 1
    n = fail = 0
    for s in _iter_mate_features(model):
        try:
            s.SetSuppression2(state, 1, None)
        except Exception:
            model.ClearSelection2(True)
            s.Select2(False, 0)
            if suppress:
                model.EditSuppress2()
            else:
                model.EditUnsuppress2()
            model.ClearSelection2(True)
        if bool(gm(s, "IsSuppressed")) != bool(suppress):
            fail += 1
            log.ev("MATE_SUPPRESS_MISMATCH", name=str(gm(s, "Name")),
                   wanted=bool(suppress))
        n += 1
    log.ev("MATES_SUPPRESSED" if suppress else "MATES_RESOLVED",
           count=n, failed=fail)
    if fail:
        raise RuntimeError("%d/%d mates did not reach suppressed=%s"
                           % (fail, n, suppress))
    return n


def set_transform_verified(app, model, comp, T, log, what, tol=1e-9):
    """Apply a 4x4 (mm) transform and PROVE the readback matches; raise on
    mismatch (fail-closed). Component must be floating first. Uses the donor
    primitive: VARIANT-typed CreateTransform + SetTransformAndSolve3."""
    gm = swc.get_com_member
    want = mat_to_t16(T)
    xf = make_transform(app, want)
    comp.SetTransformAndSolve3(xf, True)
    model.EditRebuild3()
    back = list(gm(gm(comp, "Transform2"), "ArrayData"))
    err = float(np.abs(np.array(back[:12]) - np.array(want[:12])).max())
    log.ev("TRANSFORM_VERIFIED", what=what, max_err=err)
    if err > tol:
        raise RuntimeError("transform readback mismatch %s: err=%g" % (what, err))
    return err


def link_of(comp_name, joints):
    base = comp_name.split("-")[0]
    if base in COMP_LINK:
        return COMP_LINK[base]
    if base.startswith("B51_REV_DATUM_"):
        idx = int(comp_name.split("-")[-1])
        j = joints[idx - 1]  # joint1..6 are the first six URDF joints
        return j["parent"] if "FEMALE" in base else j["child"]
    return None


def arm_components(model):
    comps = ss.components_of(model)
    return {c["name"]: c for c in comps}


def get_comp_objs(model):
    gm = swc.get_com_member
    conf = gm(model, "ConfigurationManager").ActiveConfiguration
    rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
    out = {}
    for c in gm(rootc, "GetChildren") or []:
        c2 = swc.cast(c, "IComponent2")
        out[str(gm(c2, "Name2"))] = c2
    return out


def score_pose(app, top_model, mount_T):
    """After posing, score arm bodies against saddle windows (bbox level)."""
    gm = swc.get_com_member
    conf = gm(top_model, "ConfigurationManager").ActiveConfiguration
    rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
    arm_children = []

    def walk(cs):
        for c in cs or []:
            c2 = swc.cast(c, "IComponent2")
            nm = str(gm(c2, "Name2"))
            if "B51_REF_" in nm or "B51_REV_" in nm:
                arm_children.append(c2)
            walk(gm(c2, "GetChildren"))

    walk(gm(rootc, "GetChildren"))
    boxes = []
    for c2 in arm_children:
        b = gm(c2, "GetBox", False, False)
        if b is not None:
            boxes.append([v * 1000.0 for v in list(b)])
    if not boxes:
        return {"score": -1e9, "reason": "no arm boxes"}
    allb = np.array(boxes)
    zmax = float(allb[:, 5].max())
    ymin, ymax = float(allb[:, 1].min()), float(allb[:, 4].max())
    per_saddle = {}
    score = 0.0
    for tag, s in SADDLES.items():
        x0, x1 = s["x"]
        over = [b for b in boxes if b[3] > x0 and b[0] < x1]
        zs = [b[2] for b in over]  # lowest arm z over the window
        low = min(zs) if zs else None
        per_saddle[tag] = {"bodies_over_window": len(over),
                           "lowest_arm_z_mm": low,
                           "saddle_top_z_mm": s["top_z"],
                           "gap_mm": (low - s["top_z"]) if low is not None else None}
        if low is None:
            score -= 1000.0
        else:
            gap = low - s["top_z"]
            score -= abs(gap - 3.0)          # design intent: ~3 mm pad stack
            if gap < -1.0:
                score -= 500.0               # penetration into the tower
    score -= max(0.0, zmax - 380.0)          # stay near O13 maxZ 359
    score -= max(0.0, max(abs(ymin), abs(ymax)) - 160.0)
    return {"score": score, "per_saddle": per_saddle, "arm_zmax_mm": zmax,
            "arm_y_range_mm": [ymin, ymax]}


def pose_config_transform_authored(app, arm, armasm, log, config_name,
                                   offsets, joints, Tfk, blog):
    """Author one arm configuration purely by component transforms.

    Suppress THIS config's mates (the 25 as-built locks would re-solve and
    fling any transform), batch-write every component's transform
    T_link(q) @ offset with assembly rebuild suspended, one ForceRebuild3,
    then read every component back and prove it landed (<1e-6 m, fail-closed).
    A Transform2 write in the active config makes that position specific to
    it (donor b51 _create_pose_configurations), so distinct configs keep
    distinct poses instead of sharing one and corrupting each other."""
    gm = swc.get_com_member
    swc.activate_configuration(arm, blog, config_name)
    n_sup = set_all_mates_suppressed(arm, log, True)
    objs = get_comp_objs(arm)
    want_by_name = {}
    rebuild0 = bool(armasm.EnableAssemblyRebuild)
    wrote = 0
    try:
        armasm.EnableAssemblyRebuild = False
        for nm, off in offsets.items():
            lk = link_of(nm, joints)
            want = mat_to_t16(Tfk[lk] @ off)
            c2 = objs.get(nm)
            if c2 is None:
                continue
            c2.SetTransformAndSolve3(make_transform(app, want), True)
            want_by_name[nm] = want
            wrote += 1
    finally:
        armasm.EnableAssemblyRebuild = rebuild0
    if not arm.ForceRebuild3(True):
        raise RuntimeError("pose ForceRebuild3 failed: %s" % config_name)
    objs_chk = get_comp_objs(arm)
    perr = 0.0
    for nm, want in want_by_name.items():
        c2 = objs_chk.get(nm)
        if c2 is None:
            continue
        back = list(gm(gm(c2, "Transform2"), "ArrayData"))
        perr = max(perr, float(
            np.abs(np.array(back[:12]) - np.array(want[:12])).max()))
    log.ev("CONFIG_POSED", config=config_name, mates_suppressed=n_sup,
           written=wrote, max_err_m=perr)
    if perr > 1e-6:
        raise RuntimeError("%s pose readback drift %g m > 1e-6"
                           % (config_name, perr))
    return {"config": config_name, "mates_suppressed": n_sup,
            "written": wrote, "max_err_m": perr}


def main():
    check_protected("P4_PRE")
    rep = {"schema": "F3R1_STOW_POSE_V1", "q_stow_deg": Q_STOW_DEG,
           "q_status": "O13_V3_CANDIDATE_HOLD_PROVISIONAL"}
    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    blog = swc.BuildLog("p4_stow")
    try:
        app = ss.connect(log)
        links, joints = uc.load_chain()
        q0 = {}
        qs = {j["name"]: math.radians(Q_STOW_DEG[i]) for i, j in enumerate(joints[:6])}
        T0 = uc.fk(joints, q0)
        Ts = uc.fk(joints, qs)

        # ---- arm doc: capture q0 offsets, add STOWED config, write pose ----
        arm = swc.open_document(app, blog, str(ARM))
        gm = swc.get_com_member
        cm = gm(arm, "ConfigurationManager")
        active0 = str(cm.ActiveConfiguration.Name)
        rep["arm_default_config"] = active0

        comps_q0 = arm_components(arm)
        offsets = {}
        for nm, c in comps_q0.items():
            lk = link_of(nm, joints)
            if lk is None or not c.get("transform16"):
                continue
            offsets[nm] = np.linalg.inv(T0[lk]) @ t16_to_mat(c["transform16"])
        rep["offsets_captured"] = len(offsets)
        if len(offsets) != 20:
            rep["offset_warning"] = "expected 20 components, got %d" % len(offsets)

        newconf = "STOWED_O13V3"
        existing = list(gm(arm, "GetConfigurationNames") or [])
        if newconf not in existing:
            # Donor flags (b51 _create_pose_configurations): the last two args are
            # False, False -- no InheritProperties / LinkToParent -- so the new
            # config does NOT share component positions with the default. The leak
            # probe (diag_config_leak_test: default drift 0.0) proved these flags
            # + config-specific mate suppression leave the default untouched; the
            # earlier "", True call is what let a stow write bleed into default
            # (P4 v4 defect: default span flung to 2236 mm, G2_FAIL).
            ok = cm.AddConfiguration2(newconf, "O13 v3 stow pose (PROVISIONAL)",
                                      "", 0, "", False, False)
            log.ev("CONFIG_ADDED", name=newconf, ok=bool(ok is not None))

        # Author STOWED_O13V3 purely by transform, mates suppressed in THIS config
        # only (donor VARIANT CreateTransform + SetTransformAndSolve3, batched with
        # rebuild suspended). The default keeps its 25 resolved mates and its
        # as-built pose -- proven config-specific by the leak probe.
        stow_info = pose_config_transform_authored(
            app, arm, swc.cast(arm, "IAssemblyDoc"), log, newconf,
            offsets, joints, Ts, blog)
        rep["arm_stow"] = stow_info
        rep["arm_stow_pose_max_err_m"] = stow_info["max_err_m"]
        rep["arm_stow_mates_suppressed"] = stow_info["mates_suppressed"]
        t_all, t_err = ss.mate_status(arm)
        rep["arm_stow_mates"] = {"total": t_all, "errors": t_err}

        # Fail-closed default guard: reactivate default and PROVE it still holds
        # the as-built pose captured before any write. Non-zero drift means the
        # stow write bled into default; refuse to save corruption (the exact hole
        # in P4 v4, which only recorded this drift and saved anyway).
        swc.activate_configuration(arm, blog, active0)
        if not arm.ForceRebuild3(True):
            raise RuntimeError("default reactivation rebuild failed")
        comps_chk = arm_components(arm)
        drift = 0.0
        for nm, c in comps_chk.items():
            if nm in offsets and c.get("transform16") and comps_q0[nm].get("transform16"):
                d = np.abs(np.array(c["transform16"]) -
                           np.array(comps_q0[nm]["transform16"])).max()
                drift = max(drift, float(d))
        rep["default_config_max_drift"] = drift
        log.ev("DEFAULT_CONFIG_DRIFT", max_err_m=drift)
        if drift > 1e-6:
            raise RuntimeError(
                "stow write leaked into default config: drift %g m > 1e-6" % drift)
        swc.save(arm, blog)
        swc.close_document(app, arm, blog)

        # ---- top doc: configs + mount-sign scoring ----
        top = swc.open_document(app, blog, str(TOP))
        cmt = gm(top, "ConfigurationManager")
        topconfs = list(gm(top, "GetConfigurationNames") or [])
        rep["top_configs_before"] = topconfs

        armcomp = None
        conf = cmt.ActiveConfiguration
        rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
        wingcomps = {}
        for c in gm(rootc, "GetChildren") or []:
            c2 = swc.cast(c, "IComponent2")
            nm = str(gm(c2, "Name2"))
            if nm.startswith("B51_B601"):
                armcomp = c2
            if nm.startswith("WING_"):
                wingcomps[nm] = c2
        if armcomp is None:
            raise RuntimeError("arm component not found in top")

        # switch the arm component to the stow config, then score both clock signs
        armcomp.ReferencedConfiguration = newconf
        swc.rebuild_or_fail(top, blog, "top after arm config switch")

        # P3 grounded the arm with FixComponent(); float it so the clock-sign
        # Transform2 writes actually apply (the P4 v1 identical-score bug).
        asm = swc.cast(top, "IAssemblyDoc")
        if not _float_component(top, asm, armcomp):
            raise RuntimeError("arm did not float; Transform2 would be a no-op")
        rep["arm_floated_for_scoring"] = True

        x_face = json.loads((NC / "F3R1_TOP_INTEGRATION_REPORT.json")
                            .read_text(encoding="utf-8"))["mount_station"]["boss_outer_face_x_mm"]
        scores = {}
        best = None
        for sign in (+1.0, -1.0):
            Tm = mount_transform(x_face, sign * 25.0)
            set_transform_verified(app, top, armcomp, Tm, log, "score_sign_%+g" % sign)
            sc = score_pose(app, top, Tm)
            scores["clock_%+g" % sign] = sc
            log.ev("SIGN_SCORED", sign=sign, score=sc["score"])
            if best is None or sc["score"] > scores["clock_%+g" % best]["score"]:
                best = sign
        rep["mount_sign_scores"] = scores
        rep["mount_sign_selected"] = best
        if abs(scores["clock_+1"]["score"] - scores["clock_-1"]["score"]) < 1e-6:
            rep["sign_selection_note"] = ("SIGNS_DEGENERATE: both clock signs give "
                                          "identical saddle relation; selection is arbitrary")
        Tm = mount_transform(x_face, best * 25.0)
        set_transform_verified(app, top, armcomp, Tm, log, "final_mount")
        rep["final_saddle_relation"] = score_pose(app, top, Tm)
        # re-ground the arm at the selected mount so the saved assembly is stable
        rep["arm_refixed"] = _refix_component(top, asm, armcomp)

        # top configurations: STOWED_LOCKED / DEPLOYED_NOMINAL
        for cname, armcfg, wing_state in [
                ("STOWED_LOCKED", newconf, "STOWED"),
                ("DEPLOYED_NOMINAL", active0, "DEPLOYED")]:
            if cname not in list(gm(top, "GetConfigurationNames") or []):
                # donor flags (False, False): independent config, no LinkToParent
                cmt.AddConfiguration2(cname, "", "", 0, "", False, False)
            swc.activate_configuration(top, blog, cname)
            armcomp.ReferencedConfiguration = armcfg
            for nm, c2 in wingcomps.items():
                want = 2 if wing_state in nm else 0  # 2=FullyResolved, 0=Suppressed
                c2.SetSuppression2(want)
            swc.rebuild_or_fail(top, blog, "config %s" % cname)
        swc.activate_configuration(top, blog, "STOWED_LOCKED")
        swc.save(top, blog)
        swc.close_document(app, top, blog)

        # cold reopen sanity
        top2 = swc.open_document(app, blog, str(TOP))
        rep["cold_reopen_configs"] = list(gm(top2, "GetConfigurationNames") or [])
        swc.activate_configuration(top2, blog, "STOWED_LOCKED")
        rep["cold_reopen_saddle_relation"] = score_pose(app, top2, None)
        swc.close_document(app, top2, blog)
        rep["top_sha256"] = sha256_file(TOP)
        rep["arm_sha256"] = sha256_file(ARM)
        rep["verdict"] = "P4_STOW_POSE_WRITTEN"
    except Exception as exc:
        rep["verdict"] = "P4_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]
        log.ev("P4_FAIL", error=str(exc))
    finally:
        wd.stop()

    check_protected("P4_POST")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("verdict:", rep["verdict"])
    sys.exit(0 if rep["verdict"] == "P4_STOW_POSE_WRITTEN" else 1)


if __name__ == "__main__":
    main()
