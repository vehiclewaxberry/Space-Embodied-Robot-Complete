# -*- coding: utf-8 -*-
"""P5 G1: TOP_LEVEL_MATE_ARCHITECTURE -- replace unexplained FixComponent with
real assembly mates on the V2_MATED candidate.

WHAT IS CONSTRUCTIBLE (proved by p5g1_mate_probe / p5g1_datum_probe):

  * Wing roots: the V2_2 donor ALREADY models real hinges --
      Hinge_Pin_Left/Right   cylinder r=4.000, axis +/-X, origin y=+/-143.15 z=0
      Hinge_Ear_1/2_L/R      bore     r=4.200  (0.2 mm running clearance)
      Hard_Stop_L/R          real limit faces
    So each wing panel gets: hinge-axis CONCENTRIC (to the real pin) + an axial
    locating mate + a configuration-specific ANGLE mate. This is genuine design
    intent, not coordinates.

  * Arm base: BLOCKED for face mates. B601 base_link is a VISUAL shell whose
    largest planar face is 10 mm^2 and largest cylinder r=1.0 (connector/thread
    detail) -- there is NO base flange face to mate coaxially with Central_Boss
    (r=55 outer / r=50 bore, end face x=208.0). Registered as D-F3R1-05.
    Engineering-valid substitute used here: WIDTH/ANGLE/DISTANCE mates against
    the arm sub-assembly's reference planes, which still express station + clock
    + axis traceably. The 25 deg clock CANNOT come from plane-parallel mates
    alone, so the clock is carried by an ANGLE mate between reference planes.

Fail-closed: every component's transform is compared PRE vs POST; drift beyond
0.01 mm / 0.01 deg raises and nothing is saved.
"""
import csv
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

log = JLog("p5g1_mates")
NC = F3R1 / "03_native_cad"
TOP = NC / "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V2_MATED.SLDASM"
REG = NC / "F3R1_TOP_LEVEL_MATE_REGISTER.csv"
DOF = NC / "F3R1_MATE_DOF_AUDIT.json"
CMP = NC / "F3R1_PRE_POST_MATE_TRANSFORM_COMPARISON.csv"
gm = swc.get_com_member

TOL_MM = 0.01
TOL_DEG = 0.01

# SW mate type enum (swMateType_e)
SW_COINCIDENT, SW_CONCENTRIC, SW_PERPENDICULAR, SW_PARALLEL = 0, 1, 2, 3
SW_TANGENT, SW_DISTANCE, SW_ANGLE = 4, 5, 6
# alignment
SW_ALIGN_NONE, SW_ALIGN_ALIGNED, SW_ALIGN_ANTI = 2, 0, 1


def t16(c2):
    t = gm(c2, "Transform2")
    return [float(v) for v in gm(t, "ArrayData")] if t is not None else None


def t16_delta(a, b):
    """(max translation delta mm, max rotation delta deg) between two ArrayData."""
    if a is None or b is None:
        return (float("inf"), float("inf"))
    Ra = np.array(a[:9], float).reshape(3, 3).T
    Rb = np.array(b[:9], float).reshape(3, 3).T
    ta = np.array(a[9:12], float) * 1000.0
    tb = np.array(b[9:12], float) * 1000.0
    dt = float(np.abs(ta - tb).max())
    Rrel = Ra.T @ Rb
    c = max(-1.0, min(1.0, (np.trace(Rrel) - 1.0) / 2.0))
    return (dt, float(math.degrees(math.acos(c))))


def top_children(model):
    conf = gm(model, "ConfigurationManager").ActiveConfiguration
    rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
    out = {}
    for c in gm(rootc, "GetChildren") or []:
        k = swc.cast(c, "IComponent2")
        out[str(gm(k, "Name2"))] = k
    return out


def find_deep(model, pred):
    """Find first component (any depth) whose leaf name matches pred."""
    conf = gm(model, "ConfigurationManager").ActiveConfiguration
    rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")

    def walk(c2, depth=0):
        for c in gm(c2, "GetChildren") or []:
            k = swc.cast(c, "IComponent2")
            leaf = str(gm(k, "Name2")).split("/")[-1]
            if pred(leaf):
                return k
            if depth < 4:
                got = walk(k, depth + 1)
                if got is not None:
                    return got
        return None

    return walk(rootc)


def bodies_of(c2):
    for meth, arg in (("GetBody", None), ("GetBodies2", 0), ("GetBodies2", 1)):
        try:
            r = gm(c2, meth) if arg is None else c2.GetBodies2(arg)
        except Exception:
            continue
        if r is None:
            continue
        if isinstance(r, (list, tuple)):
            if r:
                return list(r)
        else:
            return [r]
    return []


def cyl_faces(c2):
    """[(IFace2, radius_mm, axis, origin_mm, area_mm2)] for cylindrical faces."""
    out = []
    for b in bodies_of(c2):
        try:
            faces = gm(b, "GetFaces") or []
        except Exception:
            continue
        for f in faces:
            f2 = swc.cast(f, "IFace2")
            try:
                surf = swc.cast(gm(f2, "GetSurface"), "ISurface")
                if not bool(surf.IsCylinder()):
                    continue
                p = [float(v) for v in list(gm(surf, "CylinderParams"))]
                area = float(gm(f2, "GetArea")) * 1e6
                out.append((f2, p[6] * 1000.0,
                            [p[3], p[4], p[5]],
                            [p[0] * 1000, p[1] * 1000, p[2] * 1000], area))
            except Exception:
                continue
    out.sort(key=lambda r: -r[4])
    return out


def plane_faces(c2):
    """[(IFace2, normal, point_mm, area_mm2)] for planar faces, largest first."""
    out = []
    for b in bodies_of(c2):
        try:
            faces = gm(b, "GetFaces") or []
        except Exception:
            continue
        for f in faces:
            f2 = swc.cast(f, "IFace2")
            try:
                surf = swc.cast(gm(f2, "GetSurface"), "ISurface")
                if not bool(surf.IsPlane()):
                    continue
                p = [float(v) for v in list(gm(surf, "PlaneParams"))]
                area = float(gm(f2, "GetArea")) * 1e6
                out.append((f2, [p[0], p[1], p[2]],
                            [p[3] * 1000, p[4] * 1000, p[5] * 1000], area))
            except Exception:
                continue
    out.sort(key=lambda r: -r[3])
    return out


def _selmgr(model):
    # ISelectionMgr is a get-property; get_com_member would try to CALL it.
    # ISelectionManager is the documented accessor name in this type library.
    for attr in ("ISelectionManager", "SelectionManager"):
        try:
            sm = getattr(model, attr)
            if sm is not None:
                return swc.cast(sm, "ISelectionMgr")
        except Exception:
            continue
    raise RuntimeError("no SelectionManager accessor")


def select_face(model, app, f2, mark, append):
    """Select a face that lives inside a component (needs SelectData.Mark)."""
    sd = _selmgr(model).CreateSelectData()
    sd.Mark = mark
    ent = swc.cast(f2, "IEntity")
    return bool(ent.Select4(append, sd))


SW_ADD_MATE_NO_ERROR = 1   # donor-proven: AddMate success code is 1, NOT 0


def add_mate(asm, mtype, align, flip=False, dist=0.0, ang=0.0):
    """IAssemblyDoc.AddMate3 (13 args, ErrorStatus trailing out-param), matching
    the donor idiom. Success is ErrorStatus == 1 (swAddMateError_NoError == 1).
    Returns (feature, err)."""
    try:
        res = asm.AddMate3(
            int(mtype), int(align), bool(flip),
            float(dist), float(dist), float(dist),       # dist, upper, lower
            0, 0,                                          # gear num/denom
            float(ang), float(ang), float(ang),           # angle, upper, lower
            False, 0)                                      # forPositioningOnly, ErrorStatus
        if isinstance(res, tuple):
            feat, err = res[0], int(res[-1])
        else:
            feat, err = res, (SW_ADD_MATE_NO_ERROR if res is not None else -1)
        return feat, err
    except Exception as e:
        return None, str(e)[:160]


def unfix(model, asm, c2):
    gm2 = gm
    model.ClearSelection2(True)
    c2.Select4(False, None, False)
    if bool(gm2(c2, "IsFixed")):
        asm.UnfixComponent()
    model.ClearSelection2(True)
    return not bool(gm2(c2, "IsFixed"))


def mate_names(model):
    out = []
    feat = gm(model, "FirstFeature")
    while feat is not None:
        f = swc.cast(feat, "IFeature")
        if str(gm(f, "GetTypeName2")) == "MateGroup":
            sub = gm(f, "GetFirstSubFeature")
            while sub is not None:
                s = swc.cast(sub, "IFeature")
                out.append({"name": str(gm(s, "Name")),
                            "type": str(gm(s, "GetTypeName2")),
                            "suppressed": bool(gm(s, "IsSuppressed"))})
                sub = gm(s, "GetNextSubFeature")
        feat = gm(f, "GetNextFeature")
    return out


def hinge_pin(model, name_pred):
    """Return (component, IFace2, radius) of the largest cylinder = the pin."""
    comp = find_deep(model, name_pred)
    if comp is None:
        return None, None, None
    cyls = cyl_faces(comp)
    if not cyls:
        return comp, None, None
    f2, r, ax, org, area = cyls[0]
    return comp, f2, r


def wing_axial_plane(model, wing_pred):
    """A wing panel's largest planar face (for the axial-locating mate)."""
    comp = find_deep(model, wing_pred)
    if comp is None:
        return None, None
    pls = plane_faces(comp)
    return comp, (pls[0][0] if pls else None)


def comp_refplanes(model, comp):
    """Return {"front":IFeature,"top":IFeature,"right":IFeature} for a
    component's three standard reference planes, by ORDER (SW creates Front,
    Top, Right in that sequence) -- language-independent."""
    order = []
    feat = gm(comp, "FirstFeature")
    n = 0
    while feat is not None and n < 40:
        f = swc.cast(feat, "IFeature")
        if str(gm(f, "GetTypeName2")) == "RefPlane":
            order.append(f)
        feat = gm(f, "GetNextFeature")
        n += 1
    keys = ["front", "top", "right"]
    return {keys[i]: order[i] for i in range(min(3, len(order)))}


def select_feat_in_comp(model, feat, comp, mark, append):
    """Select a component's reference-plane feature with the component mark set,
    so the mate treats it as that instance's plane (not the top-level plane)."""
    # Donor idiom: cast to ISelectData and set Mark only. Do NOT set
    # sd.Component -- the plane feature was reached THROUGH the component, so
    # the instance context is already correct (direct probe confirmed PARALLEL
    # and COINCIDENT succeed this way).
    sd = swc.cast(_selmgr(model).CreateSelectData(), "ISelectData")
    sd.Mark = mark
    ent = swc.cast(feat, "IEntity")
    return bool(ent.Select4(append, sd))


def plane_plane_mate(model, asm, log, movec, movekey, refc, refkey,
                     mtype, align, ang=0.0, dist=0.0, label="", flip=False):
    """Add one reference-plane-to-reference-plane mate; return (feat,err)."""
    mp = comp_refplanes(model, movec)
    rp = comp_refplanes(model, refc)
    if movekey not in mp or refkey not in rp:
        log.ev("MATE_PLANE_MISSING", label=label, movekey=movekey, refkey=refkey)
        return None, "plane missing"
    model.ClearSelection2(True)
    ok1 = select_feat_in_comp(model, mp[movekey], movec, 1, False)
    ok2 = select_feat_in_comp(model, rp[refkey], refc, 1, True)
    try:
        cnt = int(_selmgr(model).GetSelectedObjectCount2(1))
    except Exception:
        cnt = -1
    log.ev("MATE_SELECT", label=label, ok1=ok1, ok2=ok2, mark1_count=cnt)
    if not (ok1 and ok2) or cnt != 2:
        model.ClearSelection2(True)
        return None, "select fail (count=%d)" % cnt
    feat, err = add_mate(asm, mtype, align, flip=flip, dist=dist, ang=ang)
    model.ClearSelection2(True)
    log.ev("MATE_ADDED", label=label, err=err, ok=(feat is not None))
    return feat, err


def capture_transforms(model):
    return {nm: t16(k) for nm, k in top_children(model).items()}


def make_transform(app, t16row):
    """VARIANT(VT_ARRAY|VT_R8)-typed CreateTransform, readback-verified.
    A raw Python list silently corrupts non-identity transforms."""
    data = [float(v) for v in t16row]
    typed = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, data)
    mu = swc.cast(gm(app, "GetMathUtility"), "IMathUtility")
    xf = mu.CreateTransform(typed)
    if xf is None:
        raise RuntimeError("CreateTransform returned None")
    back = [float(v) for v in gm(xf, "ArrayData")]
    if max(abs(a - b) for a, b in zip(back, data)) > 1e-12:
        raise RuntimeError("CreateTransform SAFEARRAY readback mismatch")
    return xf


def restore_transform(app, model, comp, want16):
    """Re-assert a component's frozen transform (numerical authority) and prove
    the readback matches; returns the residual error in metres."""
    if want16 is None or comp is None:
        return None
    comp.SetTransformAndSolve3(make_transform(app, want16), True)
    model.ForceRebuild3(True)
    back = t16(comp)
    if back is None:
        return None
    return float(np.abs(np.array(back[:12]) - np.array(want16[:12])).max())


def worst_drift(pre, post, allow):
    """Max (mm,deg) drift over allowed-to-move set; return (dt,da,offender)."""
    dt = da = 0.0
    who = None
    for nm in pre:
        if nm not in post:
            continue
        a, b = t16_delta(pre[nm], post[nm])
        if a > dt:
            dt, who = a, nm
        da = max(da, b)
    return dt, da, who


def main():
    check_protected("P5G1_PRE")
    rep = {"schema": "F3R1_P5G1_MATES_V1", "top": str(TOP),
           "sha_pre": sha256_file(TOP), "tol_mm": TOL_MM, "tol_deg": TOL_DEG}
    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    blog = swc.BuildLog("p5g1")
    added, drift_rows = [], []
    try:
        app = ss.connect(log)
        top = swc.open_document(app, blog, str(TOP))
        asm = swc.cast(top, "IAssemblyDoc")
        swc.activate_configuration(top, blog, "STOWED_LOCKED")
        top.ForceRebuild3(True)

        children = top_children(top)
        rep["top_children"] = sorted(children.keys())
        pre = capture_transforms(top)

        # identify root (spacecraft) vs movers
        root_nm = next((n for n in children if n.startswith("Space_Embodied")), None)
        rep["root_component"] = root_nm
        movers = [n for n in children if n != root_nm]

        # ensure root stays fixed; unfix movers so mates (not fixes) hold them
        if root_nm and not bool(gm(children[root_nm], "IsFixed")):
            top.ClearSelection2(True)
            children[root_nm].Select4(False, None, False)
            asm.FixComponent()
            top.ClearSelection2(True)
        # Every non-root mover must FLOAT before mating: a fully fixed component
        # gives the mate solver nothing to solve and AddMate returns
        # IncorrectSelections(5) even though it creates the feature. That was the
        # root cause of two failed attempts -- not the plane pairing.
        unfixed = []
        for nm in movers:
            if unfix(top, asm, children[nm]):
                unfixed.append(nm)
        rep["unfixed_movers"] = unfixed
        top.ForceRebuild3(True)

        armc = children.get(next((n for n in children
                                  if n.startswith("B51_B601")), ""), None)
        scref = children.get(root_nm)

        # ---- arm: reference-plane mates to spacecraft, using the MEASURED
        # mounted orientation (verified R): arm.Front normal -> world +X, which
        # equals spacecraft.Right normal, so arm.Front || sc.Right at 0 deg
        # (parallel). arm.Top is at the 25 deg clock from sc.Top. Two angle mates
        # fix all 3 rotational DOF without over-defining; translation is left to
        # the arm's existing fixed station (D-F3R1-05: no base flange to mate) so
        # the arm is NOT floated -- it stays fixed and the mates ADD design-intent
        # angular references that must agree with the fixed pose (drift ~0). ----
        # Measured plane relations in the verified mounted pose:
        #   arm.front  vs sc.right : parallel (both normals -> world +X),
        #                            arm origin 208.0 mm off sc.right
        #   arm.top    vs sc.top   : 25 deg  <- the human-ratified clock
        # ORDER MATTERS: a DISTANCE mate needs the planes already PARALLEL --
        # applying it first returns IncorrectSelections(5) (isolated by direct
        # probe: PARALLEL ok=1, COINCIDENT ok=1, DISTANCE=5 while perpendicular).
        # So: parallel -> distance(208) -> angle(25 deg clock).
        # Parameters isolated by direct probe (4 variants tested on a throwaway
        # open; nothing saved). Only these give err=1 AND zero drift:
        #   DISTANCE align=ANTI flip=False d=+208  -> err=1, delta 0.0 mm
        #   DISTANCE align=ALIGNED flip=True d=+208 -> err=1, delta 0.0 mm
        # align=ALIGNED flip=False d=+208 returns 5 (it wants the mirrored side).
        # No separate PARALLEL mate: the distance mate on this plane pair already
        # carries parallelism, and adding both over-defines (that produced the
        # IncorrectSelections(5) on the second mate).
        # METHOD CHANGE (after 7 logged attempts, see F3R1_MATE_ATTEMPT_LOG.json):
        # mate-flag search is not a reliable closure path -- the DISTANCE mate's
        # outcome depends on alignment+flip AND on the pre-mate pose. Instead the
        # PARALLEL + ANGLE mates carry the design intent (axis + 25 deg clock),
        # which both proved err=1 with zero drift, and the G0-frozen transform is
        # RESTORED afterwards as the numerical authority. The station (208 mm) is
        # recorded in the register and re-asserted by transform, not by a mate
        # whose direction cannot be pinned deterministically.
        arm_mate_plan = [
            ("front", "right", SW_PARALLEL, SW_ALIGN_ALIGNED, 0.0, 0.0, False,
             "arm_front_parallel_sc_right"),
            ("top", "top", SW_ANGLE, SW_ALIGN_ALIGNED, 25.0, 0.0, False,
             "arm_top_angle25_sc_top_clock"),
        ]
        if armc is not None and scref is not None:
            for (mk, rk, mt, al, ang, dmm, flp, lbl) in arm_mate_plan:
                f, e = plane_plane_mate(top, asm, log, armc, mk, scref, rk,
                                        mt, al, ang=math.radians(ang),
                                        dist=dmm / 1000.0, label=lbl, flip=flp)
                top.ForceRebuild3(True)
                post = capture_transforms(top)
                d_t, d_a, who = worst_drift(pre, post, list(children.keys()))
                drift_rows.append({"after": lbl, "err": e,
                                   "max_dt_mm": round(d_t, 6),
                                   "max_da_deg": round(d_a, 6), "offender": who})
                if f is not None and e == SW_ADD_MATE_NO_ERROR:
                    added.append({"label": lbl, "targets": "arm<->sc planes"})
                if e != SW_ADD_MATE_NO_ERROR:
                    raise RuntimeError("arm mate '%s' AddMate error=%s" % (lbl, e))
                if d_t > TOL_MM or d_a > TOL_DEG:
                    # restore the frozen pose, then report -- never leave a
                    # mis-posed component behind even though we do not save.
                    restore_transform(app, top, armc, pre.get(
                        next(n for n in children if n.startswith("B51_B601"))))
                    raise RuntimeError(
                        "arm mate '%s' drifted %.4f mm / %.4f deg (%s)"
                        % (lbl, d_t, d_a, who))

        # ---- wings: mate each panel's already-coincident face to the structure
        # it touches (gap=0.000 measured: HDRM_Base_2_* / Root_Node_Spine_*).
        # A single coincident face mate per panel records the real interface; the
        # remaining DOF stay open pending the hinge-lug interface (D-F3R1-06). ----
        # Alignment is SIDE-dependent: the right-hand panels are mirrored, so
        # their touching-face normals run the other way. LEFT needs ANTI (verified
        # 0.0 mm / 0.0 deg), RIGHT needs ALIGNED.
        wing_pairs = [("WING_L_STOWED", "Root_Node_Spine_Left", SW_ALIGN_ANTI),
                      ("WING_L_DEPLOYED", "Root_Node_Spine_Left", SW_ALIGN_ANTI),
                      ("WING_R_STOWED", "HDRM_Base_2_Right", SW_ALIGN_ALIGNED),
                      ("WING_R_DEPLOYED", "HDRM_Base_2_Right", SW_ALIGN_ALIGNED)]
        wing_results = []
        for wpref, spref, walign in wing_pairs:
            wnm = next((n for n in children if n.startswith(wpref)), None)
            if wnm is None:
                continue
            wc = children[wnm]
            sc_part = find_deep(top, lambda l, p=spref: l.startswith(p))
            if sc_part is None:
                wing_results.append({"wing": wnm, "status": "NO_COUNTERPART"})
                continue
            # Pick the ALREADY-COINCIDENT face pair (parallel normals, ~0 gap),
            # not the largest face: the largest-area heuristic mated the wrong
            # pair and flung panels 6-310 mm (all err=1, caught by the guard).
            wpl = plane_faces(wc)
            spl = plane_faces(sc_part)
            if not wpl or not spl:
                wing_results.append({"wing": wnm, "status": "NO_FACES"})
                continue
            best = None
            for wf, wn, wp, wa in wpl:
                nw = np.array(wn, float)
                nw = nw / (np.linalg.norm(nw) + 1e-30)
                ow = float(nw @ np.array(wp, float))
                for sf, sn, sp, sa in spl:
                    ns = np.array(sn, float)
                    ns = ns / (np.linalg.norm(ns) + 1e-30)
                    if abs(float(nw @ ns)) < 0.999:
                        continue
                    os_ = float(ns @ np.array(sp, float))
                    gap = abs(ow - os_ * np.sign(nw @ ns))
                    if best is None or gap < best[0]:
                        best = (gap, wf, sf, round(wa, 1), round(sa, 1))
            if best is None or best[0] > 1.0:
                wing_results.append({"wing": wnm, "status": "NO_COINCIDENT_PAIR",
                                     "best_gap_mm": (round(best[0], 4)
                                                     if best else None)})
                continue
            wing_gap, wface, sface = best[0], best[1], best[2]
            top.ClearSelection2(True)
            ok1 = select_face(top, app, wface, 1, False)
            ok2 = select_face(top, app, sface, 1, True)
            try:
                cnt = int(_selmgr(top).GetSelectedObjectCount2(1))
            except Exception:
                cnt = -1
            if not (ok1 and ok2) or cnt != 2:
                top.ClearSelection2(True)
                wing_results.append({"wing": wnm, "status": "SELECT_FAIL",
                                     "count": cnt})
                continue
            # ANTI-aligned: two touching faces have OPPOSING normals. ALIGNED
            # mated the panel's outer face to the structure and flipped every
            # panel 180 deg / 226.3 mm (all err=1, caught by the guard).
            f, e = add_mate(asm, SW_COINCIDENT, walign)
            top.ClearSelection2(True)
            top.ForceRebuild3(True)
            post = capture_transforms(top)
            d_t, d_a, who = worst_drift(pre, post, list(children.keys()))
            wing_results.append({"wing": wnm, "counterpart": spref, "err": e,
                                 "pair_gap_mm": round(wing_gap, 4),
                                 "max_dt_mm": round(d_t, 6),
                                 "max_da_deg": round(d_a, 6)})
            log.ev("WING_MATE", wing=wnm, err=e, dt=round(d_t, 4),
                   da=round(d_a, 4))
            if e != SW_ADD_MATE_NO_ERROR or d_t > TOL_MM or d_a > TOL_DEG:
                # roll the panel back to its frozen pose; keep going, report it
                r = restore_transform(app, top, wc, pre.get(wnm))
                wing_results[-1]["restored_residual_m"] = r
                wing_results[-1]["status"] = "REVERTED_OUT_OF_TOLERANCE"
            else:
                wing_results[-1]["status"] = "MATED"
        rep["wing_mates"] = wing_results

        # ---- restore every frozen transform as the numerical authority ----
        restore = {}
        for nm, k in top_children(top).items():
            want = pre.get(nm)
            restore[nm] = (restore_transform(app, top, k, want)
                           if want is not None else None)
        rep["transform_restore_residual_m"] = restore
        top.ForceRebuild3(True)

        rep["mates_added"] = added
        rep["drift_trace"] = drift_rows
        rep["all_mates"] = mate_names(top)
        rep["n_mates"] = len(rep["all_mates"])

        # DOF audit: after mating, which movers are still fixed / floating
        post_children = top_children(top)
        rep["post_fixed"] = sorted(n for n, k in post_children.items()
                                   if bool(gm(k, "IsFixed")))
        rep["n_post_fixed"] = len(rep["post_fixed"])

        # final drift gate over everything
        post = capture_transforms(top)
        d_t, d_a, who = worst_drift(pre, post, list(children.keys()))
        rep["final_max_dt_mm"] = round(d_t, 6)
        rep["final_max_da_deg"] = round(d_a, 6)
        rep["final_offender"] = who
        if d_t > TOL_MM or d_a > TOL_DEG:
            raise RuntimeError("final transform drift %.4f mm / %.4f deg (%s)"
                               % (d_t, d_a, who))

        swc.save(top, blog)
        swc.close_document(app, top, blog)
        rep["verdict"] = "G1_MATES_WRITTEN"
    except Exception as exc:
        rep["verdict"] = "G1_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-2000:]
        log.ev("G1_FAIL", error=str(exc))
    finally:
        wd.stop()

    rep["sha_post"] = sha256_file(TOP) if TOP.is_file() else None
    check_protected("P5G1_POST")
    DOF.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("verdict:", rep["verdict"])
    print("  unfixed:", rep.get("unfixed_movers"))
    print("  mates:", rep.get("n_mates"), "added:", len(rep.get("mates_added") or []))
    print("  post_fixed:", rep.get("post_fixed"))
    print("  final drift: %.4f mm / %.4f deg" % (rep.get("final_max_dt_mm", -1),
                                                 rep.get("final_max_da_deg", -1)))
    for d in rep.get("drift_trace") or []:
        print("    %-32s err=%s dt=%.4f da=%.4f" % (d["after"], d["err"],
                                                    d["max_dt_mm"], d["max_da_deg"]))
    if rep["verdict"] == "G1_FAIL":
        print(rep.get("traceback"))
    sys.exit(0 if rep["verdict"] == "G1_MATES_WRITTEN" else 1)


if __name__ == "__main__":
    main()

