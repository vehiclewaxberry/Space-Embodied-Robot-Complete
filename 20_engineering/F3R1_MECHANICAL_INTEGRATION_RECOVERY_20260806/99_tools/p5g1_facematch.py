# -*- coding: utf-8 -*-
"""P5 G1 pre-probe #3 (READ-ONLY): for each non-root top-level component, find
the best ALREADY-COINCIDENT planar face pairs against the rest of the assembly.

This decides the mate strategy empirically. A component that is already touching
the structure on 3 orthogonal faces can be fully constrained by 3 coincident
mates with ZERO position change (the honest replacement for FixComponent). A
component with no coincident counterpart faces is only coordinate-placed and
cannot be mated without new interface geometry -- that gets registered, not
forced.

For each moving component we report, per candidate spacecraft face, the signed
plane distance and normal dot; a "coincident" pair is |dist|<0.2 mm and
|dot|>0.999 (parallel) or the faces are co-planar.
SAVE_CALLS_ALLOWED = 0.
"""
import json
import sys
import traceback

import numpy as np

from f3r1_env import F3R1, JLog, check_protected, sha256_file
import b3_lib.sw_core as swc
import sw_session as ss

log = JLog("p5g1_facematch")
NC = F3R1 / "03_native_cad"
TOP = NC / "F3R1_SPACE_EMBODIED_ROBOT_INTEGRATION_V2_MATED.SLDASM"
OUT = NC / "F3R1_FACEMATCH_PROBE.json"
gm = swc.get_com_member

MOVERS = ["WING_L_STOWED", "WING_R_STOWED", "WING_L_DEPLOYED",
          "WING_R_DEPLOYED", "B51_B601_ARTICULATED"]


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


def planes_world(c2, min_area=200.0):
    """Planar faces as (normal_unit, signed_offset_mm, area, centroid_mm).

    PlaneParams already returns the face plane in ASSEMBLY space for a component
    in the active config, so normal.p = offset defines the world plane.
    """
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
                area = float(gm(f2, "GetArea")) * 1e6
                if area < min_area:
                    continue
                p = [float(v) for v in list(gm(surf, "PlaneParams"))]
                n = np.array(p[:3], float)
                nn = n / (np.linalg.norm(n) + 1e-30)
                pt = np.array([p[3], p[4], p[5]], float) * 1000.0
                off = float(nn @ pt)
                out.append((nn, off, area, pt))
            except Exception:
                continue
    return out


def collect(model):
    conf = gm(model, "ConfigurationManager").ActiveConfiguration
    rootc = swc.cast(conf.GetRootComponent3(True), "IComponent2")
    movers, structure = {}, []

    def walk(c2, depth=0, top_owner=None):
        for c in gm(c2, "GetChildren") or []:
            k = swc.cast(c, "IComponent2")
            leaf = str(gm(k, "Name2")).split("/")[-1]
            owner = top_owner or leaf
            is_mover = any(leaf.startswith(m) for m in MOVERS)
            if is_mover and top_owner is None:
                movers[leaf] = k
            elif top_owner is None:
                # structural top-level (spacecraft) -- descend for its faces
                pass
            if depth < 4:
                walk(k, depth + 1, owner if is_mover else top_owner)
    walk(rootc)

    # structure = every planar face NOT belonging to a mover
    def gather_struct(c2, depth=0, in_mover=False):
        for c in gm(c2, "GetChildren") or []:
            k = swc.cast(c, "IComponent2")
            leaf = str(gm(k, "Name2")).split("/")[-1]
            m = in_mover or any(leaf.startswith(x) for x in MOVERS)
            if not m:
                for pl in planes_world(k):
                    structure.append((leaf, pl))
            if depth < 4:
                gather_struct(k, depth + 1, m)
    gather_struct(rootc)
    return movers, structure


def main():
    check_protected("P5G1_FACEMATCH_PRE")
    rep = {"schema": "F3R1_FACEMATCH_PROBE_V1", "top": str(TOP),
           "sha_pre": sha256_file(TOP)}
    wd = ss.MemoryDialogWatchdog(log)
    wd.start()
    blog = swc.BuildLog("p5g1_facematch")
    try:
        app = ss.connect(log)
        top = swc.open_document(app, blog, str(TOP), read_only=True)
        movers, structure = collect(top)
        rep["n_structure_faces"] = len(structure)
        res = {}
        for leaf, k in movers.items():
            mp = planes_world(k)
            pairs = []
            for nm, off, area, pt in mp:
                best = None
                for sleaf, (sn, soff, sarea, spt) in structure:
                    dot = abs(float(nm @ sn))
                    if dot < 0.999:
                        continue
                    # signed distance between the two parallel planes
                    dist = abs(off - soff * np.sign(nm @ sn))
                    if best is None or dist < best[0]:
                        best = (dist, sleaf, round(sarea, 1))
                if best is not None and best[0] < 1.0:
                    pairs.append({"mover_face_area": round(area, 1),
                                  "mover_normal": [round(x, 4) for x in nm],
                                  "gap_mm": round(best[0], 4),
                                  "structure_part": best[1],
                                  "structure_face_area": best[2]})
            pairs.sort(key=lambda d: (d["gap_mm"], -d["mover_face_area"]))
            res[leaf] = {"n_planes": len(mp), "coincident_pairs": pairs[:8],
                         "n_coincident": len(pairs)}
        rep["match"] = res
        swc.close_document(app, top, blog)
        rep["verdict"] = "FACEMATCH_OK"
    except Exception as exc:
        rep["verdict"] = "FACEMATCH_FAIL"
        rep["error"] = str(exc)
        rep["traceback"] = traceback.format_exc()[-1600:]
    finally:
        wd.stop()
    rep["sha_post"] = sha256_file(TOP) if TOP.is_file() else None
    rep["unchanged"] = rep["sha_post"] == rep["sha_pre"]
    check_protected("P5G1_FACEMATCH_POST")
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
    print("verdict:", rep["verdict"], "| unchanged:", rep.get("unchanged"),
          "| structure_faces:", rep.get("n_structure_faces"))
    for leaf, v in (rep.get("match") or {}).items():
        print("\n%-30s planes=%d coincident=%d" % (leaf, v["n_planes"],
                                                    v["n_coincident"]))
        for p in v["coincident_pairs"][:5]:
            print("   gap=%6.3f  mover_n=%s a=%8.1f  <-> %s a=%8.1f"
                  % (p["gap_mm"], p["mover_normal"], p["mover_face_area"],
                     p["structure_part"], p["structure_face_area"]))
    if rep["verdict"] != "FACEMATCH_OK":
        print(rep.get("traceback"))


if __name__ == "__main__":
    main()
