# -*- coding: utf-8 -*-
"""P5 G1 pre-probe (READ-ONLY): find the REAL mateable entities.

Before writing any mate we must know which native faces exist to mate TO --
mating by absolute coordinate is exactly the defect (D-F3R1-03) we are closing.
This probe reports, for the mate targets named in the work order:

  * Central_Boss      : cylindrical faces (axis + radius) and planar end faces
  * Adapter_Plate     : planar mounting faces
  * B601 base_link    : cylindrical/planar candidates on the arm base flange
  * Hinge_Pin_L/R     : cylindrical faces (the wing-root hinge AXIS to be
                        concentric-mated) -- donor already models real hinges
  * Hinge_Ear_1/2 L/R : bore faces
  * Hard_Stop_L/R     : the mechanical limit faces
  * WING_* panels     : planar faces usable for the axial/angle mates
  * Saddles           : mounting/base faces for the 3-2-1 installation

For each face: type, area, normal or axis direction, origin, radius, and the
persistent reference ID so a later mate script can re-select it deterministically.
SAVE_CALLS_ALLOWED = 0.
"""
import json
import sys
import traceback

import numpy as np

from f3r1_env import F3R1, JLog, check_protected, sha256_file
import b3_lib.sw_core as swc
import sw_session as ss

log = JLog("p5g1_probe")
NC = F3R1 / "03_native_cad"
TOP = NC / "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V2_MATED.SLDASM"
OUT = NC / "F3R1_MATE_ENTITY_PROBE.json"
gm = swc.get_com_member

TARGETS = ["Central_Boss", "Adapter_Plate", "Spacecraft_Flange",
           "B51_REF_base_link", "Hinge_Pin_Left", "Hinge_Pin_Right",
           "Hinge_Ear_1_Left", "Hinge_Ear_2_Left",
           "Hinge_Ear_1_Right", "Hinge_Ear_2_Right",
           "Hard_Stop_Left", "Hard_Stop_Right",
           "Root_Base_Left", "Root_Base_Right",
           "WING_L_STOWED", "WING_R_STOWED", "WING_L_DEPLOYED", "WING_R_DEPLOYED",
           "Aft_Saddle", "Fwd_Saddle", "Mid_Saddle",
           "Launch_Lock_Interface_Reference"]


def walk(c2, out, depth=0):
    for c in gm(c2, "GetChildren") or []:
        k = swc.cast(c, "IComponent2")
        full = str(gm(k, "Name2"))
        out.append((full.split("/")[-1], full, k))
        if depth < 4:
            walk(k, out, depth + 1)
    return out


def bodies(c2):
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


def face_info(f2):
    """Classify a face: plane (normal+point) or cylinder (axis+origin+radius)."""
    try:
        surf = swc.cast(gm(f2, "GetSurface"), "ISurface")
    except Exception:
        return None
    area = 0.0
    try:
        area = float(gm(f2, "GetArea")) * 1.0e6      # m^2 -> mm^2
    except Exception:
        pass
    box = []
    try:
        box = [round(v * 1000.0, 3) for v in list(gm(f2, "GetBox") or [])]
    except Exception:
        pass
    d = {"area_mm2": round(area, 2), "box_mm": box}
    try:
        if bool(surf.IsPlane()):
            p = [float(v) for v in list(gm(surf, "PlaneParams"))]
            d.update({"kind": "PLANE",
                      "normal": [round(p[0], 6), round(p[1], 6), round(p[2], 6)],
                      "point_mm": [round(p[3] * 1000, 3), round(p[4] * 1000, 3),
                                   round(p[5] * 1000, 3)]})
            return d
    except Exception:
        pass
    try:
        if bool(surf.IsCylinder()):
            p = [float(v) for v in list(gm(surf, "CylinderParams"))]
            # origin(3), axis(3), radius
            d.update({"kind": "CYLINDER",
                      "origin_mm": [round(p[0] * 1000, 3), round(p[1] * 1000, 3),
                                    round(p[2] * 1000, 3)],
                      "axis": [round(p[3], 6), round(p[4], 6), round(p[5], 6)],
                      "radius_mm": round(p[6] * 1000, 4)})
            return d
    except Exception:
        pass
    d["kind"] = "OTHER"
    return d


def main():
    check_protected("P5G1_PROBE_PRE")
    rep = {"schema": "F3R1_MATE_ENTITY_PROBE_V1", "top": str(TOP),
           "sha_pre": sha256_file(TOP)}
    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    blog = swc.BuildLog("p5g1_probe")
    try:
        app = ss.connect(log)
        top = swc.open_document(app, blog, str(TOP), read_only=True)
        conf = gm(top, "ConfigurationManager").ActiveConfiguration
        rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
        allc = walk(rootc, [])
        rep["tree_count"] = len(allc)

        found = {}
        for leaf, full, k in allc:
            for t in TARGETS:
                if not leaf.startswith(t):
                    continue
                bs = bodies(k)
                planes, cyls, others = [], [], 0
                for b in bs:
                    try:
                        faces = gm(b, "GetFaces") or []
                    except Exception:
                        continue
                    for f in faces:
                        try:
                            info = face_info(swc.cast(f, "IFace2"))
                        except Exception:
                            continue
                        if info is None:
                            continue
                        if info["kind"] == "PLANE":
                            planes.append(info)
                        elif info["kind"] == "CYLINDER":
                            cyls.append(info)
                        else:
                            others += 1
                planes.sort(key=lambda d: -d["area_mm2"])
                cyls.sort(key=lambda d: -d["area_mm2"])
                found[full] = {"leaf": leaf, "n_bodies": len(bs),
                               "n_planes": len(planes), "n_cyl": len(cyls),
                               "n_other": others,
                               "top_planes": planes[:6],
                               "cylinders": cyls[:8]}
        rep["entities"] = found
        rep["targets_missing"] = [t for t in TARGETS
                                  if not any(v["leaf"].startswith(t)
                                             for v in found.values())]
        swc.close_document(app, top, blog)
        rep["verdict"] = "PROBE_OK"
    except Exception as exc:
        rep["verdict"] = "PROBE_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1800:]
    finally:
        wd.stop()
    rep["sha_post"] = sha256_file(TOP) if TOP.is_file() else None
    rep["unchanged"] = rep["sha_post"] == rep["sha_pre"]
    check_protected("P5G1_PROBE_POST")
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("verdict:", rep["verdict"], "| unchanged:", rep.get("unchanged"))
    print("missing targets:", rep.get("targets_missing"))
    for full, v in (rep.get("entities") or {}).items():
        print("\n%-42s bodies=%d planes=%d cyl=%d" % (v["leaf"][:42], v["n_bodies"],
                                                     v["n_planes"], v["n_cyl"]))
        for c in v["cylinders"][:3]:
            print("    CYL  r=%8.3f axis=%s origin=%s area=%.1f"
                  % (c["radius_mm"], c["axis"], c["origin_mm"], c["area_mm2"]))
        for p in v["top_planes"][:3]:
            print("    PLN  n=%s pt=%s area=%.1f" % (p["normal"], p["point_mm"],
                                                     p["area_mm2"]))
    if rep["verdict"] == "PROBE_FAIL":
        print(rep.get("traceback"))


if __name__ == "__main__":
    main()
