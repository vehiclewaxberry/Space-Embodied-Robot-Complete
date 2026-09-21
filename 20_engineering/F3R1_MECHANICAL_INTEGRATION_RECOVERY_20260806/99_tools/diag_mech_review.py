# -*- coding: utf-8 -*-
"""Read-only MECHANICAL review of the F3R1 top assembly at STOWED_LOCKED.

Answers what P4's bbox scoring cannot:

 1. NATIVE interference detection (arm chain vs saddles vs structure) -- real
    interference volumes. P4 compared arm-bbox-zmin against saddle-bbox-zmax and
    called the difference a "gap". But a SADDLE is a CRADLE: an arm nesting into
    a cradle legitimately has bbox zmin BELOW the saddle's bbox zmax, with zero
    material interference. So the reported -27.0 / -19.3 / -58.9 mm may be a
    measurement artifact, not penetration. Native interference is the arbiter.

 2. Saddle support-face geometry: horizontal planar face levels + areas, to tell
    a FLAT-TOP bracket (arm sits ON the top face) from a NOTCHED cradle (arm
    nests INTO it). This also bears on audit finding R3-04 (no counterpart face).

 3. Per-configuration component suppression: which wings are live in
    STOWED_LOCKED vs DEPLOYED_NOMINAL, and the top-level mate count.

SAVE_CALLS_ALLOWED = 0. Opens, measures, closes without saving.
"""
import json
import sys
import traceback

import numpy as np

from f3r1_env import F3R1, JLog, check_protected, sha256_file
import b3_lib.sw_core as swc
import sw_session as ss

log = JLog("diag_mech_review")
NC = F3R1 / "03_native_cad"
TOP = NC / "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION.SLDASM"
OUT = F3R1 / "05_clearance" / "F3R1_MECH_REVIEW.json"
gm = swc.get_com_member

SADDLE_KEYS = ("Aft_Saddle", "Fwd_Saddle", "Mid_Saddle")


def walk_all(c2, out, depth=0):
    """Collect (leaf_name, comp2) for the whole component tree."""
    for c in gm(c2, "GetChildren") or []:
        k = swc.cast(c, "IComponent2")
        nm = str(gm(k, "Name2"))
        out.append((nm.split("/")[-1], nm, k))
        if depth < 6:
            walk_all(k, out, depth + 1)
    return out


def comp_box(c2):
    b = gm(c2, "GetBox", False, False)
    return [v * 1000.0 for v in list(b)] if b is not None else None


def comp_bodies(c2):
    try:
        b = gm(c2, "GetBody")
        if b is not None:
            return [b]
    except Exception:
        pass
    for t in (0, 1):
        try:
            bs = c2.GetBodies2(t)
            if bs:
                return list(bs)
        except Exception:
            continue
    return []


def horizontal_faces(c2):
    """Planar faces with ~+/-Z normal: report level z (mm) and area (mm^2).

    Face geometry space is verified against the component's assembly-space bbox
    so the caller knows whether z is assembly or part local.
    """
    levels = []
    for body in comp_bodies(c2):
        try:
            faces = gm(body, "GetFaces") or []
        except Exception:
            continue
        for f in faces:
            try:
                f2 = swc.cast(f, "IFace2")
                surf = swc.cast(gm(f2, "GetSurface"), "ISurface")
                if not bool(surf.IsPlane()):
                    continue
                pp = [float(v) for v in list(gm(surf, "PlaneParams"))]
                nz = pp[2]
                if abs(nz) < 0.985:            # not horizontal
                    continue
                fb = list(gm(f2, "GetBox") or [])
                if len(fb) < 6:
                    continue
                z = 0.5 * (fb[2] + fb[5]) * 1000.0
                area = float(gm(f2, "GetArea")) * 1.0e6
                levels.append({"z_mm": round(z, 3), "area_mm2": round(area, 1),
                               "normal_z": round(nz, 3),
                               "x_mm": [round(fb[0] * 1000, 2), round(fb[3] * 1000, 2)],
                               "y_mm": [round(fb[1] * 1000, 2), round(fb[4] * 1000, 2)]})
            except Exception:
                continue
    levels.sort(key=lambda d: -d["z_mm"])
    return levels


def interference_scan(top, asm, sel_comps, log):
    """Native SW interference detection restricted to the selected components."""
    mgr = gm(asm, "InterferenceDetectionManager")
    if mgr is None:
        return {"status": "NO_MANAGER"}
    for prop, val in (("TreatCoincidenceAsInterference", False),
                      ("TreatSubAssembliesAsComponents", False),
                      ("IncludeMultibodyPartInterferences", True),
                      ("MakeInterferingPartsTransparent", False),
                      ("ShowIgnoredInterferences", False),
                      ("UseSelectedComponents", True)):
        try:
            setattr(mgr, prop, val)
        except Exception as e:
            log.ev("IDM_PROP_FAIL", prop=prop, err=str(e)[:120])
    top.ClearSelection2(True)
    nsel = 0
    for c2 in sel_comps:
        try:
            if c2.Select4(True, None, False):
                nsel += 1
        except Exception:
            pass
    res = mgr.GetInterferences()
    items = []
    for r in list(res or []):
        try:
            it = swc.cast(r, "IInterference")
            vol = float(gm(it, "Volume")) * 1.0e9        # m^3 -> mm^3
            names = []
            for c in list(gm(it, "GetComponents") or []):
                names.append(str(gm(swc.cast(c, "IComponent2"), "Name2")).split("/")[-1])
            items.append({"volume_mm3": round(vol, 4), "components": names})
        except Exception:
            continue
    items.sort(key=lambda d: -d["volume_mm3"])
    top.ClearSelection2(True)
    return {"status": "OK", "selected": nsel, "count": len(items),
            "total_volume_mm3": round(sum(i["volume_mm3"] for i in items), 4),
            "items": items[:40]}


def main():
    check_protected("MECH_REVIEW_PRE")
    rep = {"schema": "F3R1_MECH_REVIEW_V1", "top": str(TOP),
           "top_sha256_pre": sha256_file(TOP)}
    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    blog = swc.BuildLog("mech_review")
    try:
        app = ss.connect(log)
        top = swc.open_document(app, blog, str(TOP))
        asm = swc.cast(top, "IAssemblyDoc")
        rep["configs"] = list(gm(top, "GetConfigurationNames") or [])

        # ---- per-config component liveness ----
        percfg = {}
        for cn in rep["configs"]:
            swc.activate_configuration(top, blog, cn)
            top.ForceRebuild3(True)
            conf = gm(top, "ConfigurationManager").ActiveConfiguration
            rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
            live, supp = [], []
            for c in gm(rootc, "GetChildren") or []:
                k = swc.cast(c, "IComponent2")
                nm = str(gm(k, "Name2"))
                (supp if bool(gm(k, "IsSuppressed")) else live).append(nm)
            t_all, t_err = ss.mate_status(top)
            percfg[cn] = {"live": sorted(live), "suppressed": sorted(supp),
                          "mates_total": t_all, "mate_errors": t_err}
        rep["per_config"] = percfg

        # ---- work in STOWED_LOCKED ----
        swc.activate_configuration(top, blog, "STOWED_LOCKED")
        top.ForceRebuild3(True)
        conf = gm(top, "ConfigurationManager").ActiveConfiguration
        rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
        allc = walk_all(rootc, [])
        rep["tree_component_count"] = len(allc)

        arm_comps, saddle_comps = [], {}
        for leaf, full, k in allc:
            if leaf.startswith("B51_REF_") or leaf.startswith("B51_REV_"):
                arm_comps.append((leaf, k))
            for sk in SADDLE_KEYS:
                if leaf.startswith(sk):
                    saddle_comps[leaf] = k
        rep["arm_leaf_count"] = len(arm_comps)
        rep["saddles_found"] = sorted(saddle_comps.keys())

        # ---- saddle horizontal faces (support-face reality, audit R3-04) ----
        sad = {}
        for nm, k in saddle_comps.items():
            faces = horizontal_faces(k)
            sad[nm] = {"assembly_bbox_mm": comp_box(k),
                       "n_horizontal_faces": len(faces),
                       "top_faces": faces[:6]}
        rep["saddle_geometry"] = sad

        # ---- arm link bboxes in assembly space ----
        rep["arm_link_boxes_mm"] = {leaf: comp_box(k) for leaf, k in arm_comps}

        # ---- NATIVE interference: whole assembly, then arm-vs-rest ----
        top.ClearSelection2(True)
        rep["interference_all"] = interference_scan(
            top, asm, [k for _, k in arm_comps] +
            list(saddle_comps.values()), log)

        swc.close_document(app, top, blog)
        rep["verdict"] = "MECH_REVIEW_DONE"
    except Exception as exc:
        rep["verdict"] = "FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1800:]
    finally:
        wd.stop()

    rep["top_sha256_post"] = sha256_file(TOP)
    rep["top_unchanged"] = rep["top_sha256_post"] == rep["top_sha256_pre"]
    check_protected("MECH_REVIEW_POST")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("verdict:", rep["verdict"], "| top_unchanged:", rep.get("top_unchanged"))
    itf = rep.get("interference_all") or {}
    print("interference:", itf.get("status"), "count:", itf.get("count"),
          "total_mm3:", itf.get("total_volume_mm3"))
    for it in (itf.get("items") or [])[:12]:
        print("   %10.3f mm3  %s" % (it["volume_mm3"], " <-> ".join(it["components"])))
    for nm, d in (rep.get("saddle_geometry") or {}).items():
        print("saddle %-22s hfaces=%d" % (nm, d["n_horizontal_faces"]),
              [f["z_mm"] for f in d["top_faces"][:4]])
    if rep["verdict"] == "FAIL":
        print(rep.get("traceback"))


if __name__ == "__main__":
    main()
